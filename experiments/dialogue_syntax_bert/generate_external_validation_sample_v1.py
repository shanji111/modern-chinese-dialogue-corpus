"""Generate a frozen, leakage-safe external-validation selection from corpus.db.

The corpus database is opened in SQLite mode=ro. Public blind packets and a
selection manifest are written to a versioned reproducibility directory. A
rule-bearing private master is written separately under ignored artifacts.
Existing outputs are never overwritten.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import json
import math
import os
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from io_utils import connect_sqlite_readonly
from sample_pairs import conversation_group_key, normalized_pair_hash, safe_json_list


FLAG_COLUMNS = (
    "has_lexical_echo",
    "has_pattern_reuse",
    "has_question_response",
    "has_negation_turn",
    "has_repair_repetition",
)

STRATUM_RATIOS = (
    ("rule_positive", 0.30),
    ("rule_negative_random", 0.20),
    ("hard_negative_or_boundary", 0.20),
    ("potential_false_negative", 0.20),
    ("analogy_or_parallel_candidate", 0.10),
)

ANNOTATION_COLUMNS = (
    "resonance_present",
    "label_reproduction",
    "label_parallelism",
    "label_selective_reuse",
    "label_repair",
    "label_contrast",
    "label_analogy_candidate",
    "evidence_span_a",
    "evidence_span_b",
    "annotator_note",
    "uncertainty_reason",
)

BLIND_COLUMNS = (
    "annotation_id",
    "source",
    "category",
    "dataset_name",
    "speaker_a",
    "turn_a",
    "speaker_b",
    "turn_b",
    *ANNOTATION_COLUMNS,
)

SELECTION_KEY_COLUMNS = (
    "annotation_id",
    "pair_id",
    "normalized_pair_hash",
    "conversation_group_key",
    "source",
    "category",
    "dataset_name",
    "sample_stratum",
    "confirmatory_partition",
    "double_annotation_overlap",
)

PRIVATE_COLUMNS = (
    *SELECTION_KEY_COLUMNS,
    "entry_id",
    "conversation_key",
    "turn_a_id",
    "turn_b_id",
    "speaker_a",
    "turn_a",
    "speaker_b",
    "turn_b",
    "shared_terms",
    "markers",
    *FLAG_COLUMNS,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--existing-gold", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--private-output-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=800)
    parser.add_argument("--holdout-size", type=int, default=200)
    parser.add_argument("--overlap-rate", type=float, default=0.30)
    parser.add_argument("--max-text-chars", type=int, default=260)
    parser.add_argument("--max-per-dataset", type=int, default=80)
    parser.add_argument(
        "--exclude-source-contains",
        action="append",
        default=[],
        help="Exclude rows whose source contains any supplied substring; repeatable.",
    )
    parser.add_argument(
        "--selection-version",
        default="external_validation_v1",
        help="Version label written to the manifest.",
    )
    parser.add_argument("--seed", type=int, default=20260713)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_new(path: Path, rows: Iterable[dict[str, object]], columns: Iterable[str]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json_new(path: Path, payload: object) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def target_counts(sample_size: int) -> dict[str, int]:
    remaining = sample_size
    result: dict[str, int] = {}
    for index, (name, ratio) in enumerate(STRATUM_RATIOS):
        count = remaining if index == len(STRATUM_RATIOS) - 1 else round(sample_size * ratio)
        result[name] = count
        remaining -= count
    return result


def priority(seed: int, namespace: str, pair_id: int) -> int:
    payload = f"{seed}|{namespace}|{pair_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def candidate_strata(row: dict[str, object]) -> tuple[str, ...]:
    flags = {name: int(row.get(name) or 0) == 1 for name in FLAG_COLUMNS}
    rule_any = any(flags.values())
    turn_a = str(row["turn_a"])
    turn_b = str(row["turn_b"])
    shared = bool(safe_json_list(row.get("shared_terms")))
    questionish = has_any(turn_a, ("?", "？", "什么", "谁", "哪", "怎么", "吗", "么", "是否", "为何", "何以"))
    demonstrative = has_any(turn_b, ("这", "此", "那个", "这些", "这俩", "那"))
    short_answer = len(turn_a) <= 12 or len(turn_b) <= 12
    repair_contrast = has_any(turn_b, ("不", "不是", "没有", "但是", "不过", "其实", "错", "应该", "不对"))
    analogy = has_any(turn_a + "\n" + turn_b, ("胜于", "不如", "比", "像", "如同", "一样", "不是", "而是", "反过来"))

    result: list[str] = []
    if rule_any:
        result.append("rule_positive")
    else:
        result.append("rule_negative_random")
        if shared or questionish or demonstrative or short_answer:
            result.append("hard_negative_or_boundary")
        if questionish or demonstrative or short_answer or repair_contrast:
            result.append("potential_false_negative")
    if analogy or flags["has_pattern_reuse"]:
        result.append("analogy_or_parallel_candidate")
    return tuple(result)


def keep_candidate(heap: list[tuple[int, int, dict[str, object]]], score: int, row: dict[str, object], capacity: int) -> None:
    item = (-score, -int(row["pair_id"]), row)
    if len(heap) < capacity:
        heapq.heappush(heap, item)
    elif item > heap[0]:
        heapq.heapreplace(heap, item)


def ordered_diverse_pool(
    heaps: dict[tuple[str, str], list[tuple[int, int, dict[str, object]]]],
    seed: int,
    stratum: str,
) -> list[dict[str, object]]:
    buckets: dict[tuple[str, str], deque[dict[str, object]]] = {}
    for group, heap in heaps.items():
        ordered = sorted(((-neg_score, row) for neg_score, _neg_id, row in heap), key=lambda item: item[0])
        buckets[group] = deque(row for _score, row in ordered)
    groups = sorted(
        buckets,
        key=lambda group: hashlib.sha256(f"{seed}|{stratum}|{group}".encode("utf-8")).digest(),
    )
    result: list[dict[str, object]] = []
    while groups:
        next_groups: list[tuple[str, str]] = []
        for group in groups:
            bucket = buckets[group]
            if bucket:
                result.append(bucket.popleft())
            if bucket:
                next_groups.append(group)
        groups = next_groups
    return result


def choose_holdout_datasets(rows: list[dict[str, object]], target: int, seed: int) -> set[str]:
    counts = Counter(str(row["dataset_name"]) for row in rows)
    dataset_sources: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        dataset_sources[str(row["dataset_name"])].add(str(row["source"]))
    sources = sorted({source for values in dataset_sources.values() for source in values})
    source_bits = {source: 1 << index for index, source in enumerate(sources)}
    all_sources_mask = (1 << len(sources)) - 1
    dataset_masks = {
        dataset: sum(source_bits[source] for source in values)
        for dataset, values in dataset_sources.items()
    }
    datasets = sorted(counts, key=lambda name: hashlib.sha256(f"{seed}|holdout|{name}".encode("utf-8")).digest())
    max_total = min(len(rows), target + max(counts.values()))
    states: dict[tuple[int, int], tuple[str, ...]] = {(0, 0): ()}
    for dataset in datasets:
        count = counts[dataset]
        mask = dataset_masks[dataset]
        for (total, current_mask), chosen in sorted(list(states.items()), reverse=True):
            new_total = total + count
            state = (new_total, current_mask | mask)
            if new_total <= max_total and state not in states:
                states[state] = chosen + (dataset,)
    eligible = [
        state
        for state, chosen in states.items()
        if len(chosen) >= 2 and state[1] == all_sources_mask
    ]
    if not eligible:
        raise RuntimeError("Could not form a dataset-disjoint holdout covering every selected source")
    best = min(eligible, key=lambda state: (abs(state[0] - target), state[0] < target, state[0]))
    return set(states[best])


def select_overlap(rows: list[dict[str, object]], rate: float, seed: int) -> set[str]:
    by_stratum: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_stratum[str(row["sample_stratum"])].append(row)
    selected: set[str] = set()
    for stratum, group in by_stratum.items():
        group.sort(key=lambda row: priority(seed, f"overlap:{stratum}", int(row["pair_id"])))
        count = max(1, round(len(group) * rate))
        selected.update(str(row["annotation_id"]) for row in group[:count])
    return selected


def main() -> int:
    args = parse_args()
    if args.sample_size <= 0 or args.holdout_size <= 0 or args.holdout_size >= args.sample_size:
        raise ValueError("Require 0 < holdout-size < sample-size")
    if not 0 < args.overlap_rate <= 1:
        raise ValueError("overlap-rate must be in (0, 1]")
    for directory in (args.output_dir, args.private_output_dir):
        if directory.exists() and any(directory.iterdir()):
            raise FileExistsError(f"Refusing to write into non-empty directory: {directory}")

    gold_rows = read_csv(args.existing_gold)
    excluded_ids = {int(row["pair_id"]) for row in gold_rows}
    excluded_hashes = {normalized_pair_hash(row["turn_a"], row["turn_b"]) for row in gold_rows}
    targets = target_counts(args.sample_size)
    capacity_per_group = max(40, math.ceil(max(targets.values()) / 10) * 5)
    candidate_heaps: dict[str, dict[tuple[str, str], list[tuple[int, int, dict[str, object]]]]] = {
        name: defaultdict(list) for name in targets
    }
    candidate_counts = Counter()

    conn = connect_sqlite_readonly(args.db)
    placeholders = ",".join("?" for _ in excluded_ids)
    excluded_groups = {
        conversation_group_key(row["dataset_name"], row["conversation_key"])
        for row in conn.execute(
            f"SELECT dataset_name, conversation_key FROM dialogue_pairs WHERE id IN ({placeholders})",
            sorted(excluded_ids),
        )
    }
    db_pair_count = conn.execute("SELECT COUNT(*) FROM dialogue_pairs").fetchone()[0]
    query = f"""
        SELECT id AS pair_id, turn_a_id, turn_b_id, entry_id, conversation_key,
               COALESCE(speaker_a, '') AS speaker_a, COALESCE(speaker_b, '') AS speaker_b,
               text_a AS turn_a, text_b AS turn_b,
               COALESCE(source, '') AS source, COALESCE(category, '') AS category,
               COALESCE(dataset_name, '') AS dataset_name,
               COALESCE(shared_terms, '[]') AS shared_terms,
               COALESCE(markers, '[]') AS markers,
               {', '.join(FLAG_COLUMNS)}
        FROM dialogue_pairs
        WHERE COALESCE(text_a, '') <> '' AND COALESCE(text_b, '') <> ''
          AND LENGTH(text_a) <= ? AND LENGTH(text_b) <= ?
    """
    scanned = 0
    excluded_existing = 0
    for sqlite_row in conn.execute(query, (args.max_text_chars, args.max_text_chars)):
        scanned += 1
        row = dict(sqlite_row)
        source_text = str(row.get("source") or "")
        if any(pattern and pattern in source_text for pattern in args.exclude_source_contains):
            continue
        pair_id = int(row["pair_id"])
        pair_hash = normalized_pair_hash(row["turn_a"], row["turn_b"])
        group_key = conversation_group_key(row["dataset_name"], row["conversation_key"])
        if pair_id in excluded_ids or pair_hash in excluded_hashes or group_key in excluded_groups:
            excluded_existing += 1
            continue
        row["normalized_pair_hash"] = pair_hash
        row["conversation_group_key"] = group_key
        group = (str(row["source"]), str(row["dataset_name"]))
        for stratum in candidate_strata(row):
            if stratum not in targets:
                continue
            candidate_counts[stratum] += 1
            keep_candidate(
                candidate_heaps[stratum][group],
                priority(args.seed, stratum, pair_id),
                row,
                capacity_per_group,
            )
    conn.close()

    selected: list[dict[str, object]] = []
    selected_ids: set[int] = set()
    selected_hashes: set[str] = set()
    selected_groups: set[str] = set()
    dataset_counts: Counter[str] = Counter()
    selection_order = (
        "analogy_or_parallel_candidate",
        "potential_false_negative",
        "hard_negative_or_boundary",
        "rule_positive",
        "rule_negative_random",
    )
    for stratum in selection_order:
        for row in ordered_diverse_pool(candidate_heaps[stratum], args.seed, stratum):
            pair_id = int(row["pair_id"])
            pair_hash = str(row["normalized_pair_hash"])
            group_key = str(row["conversation_group_key"])
            dataset = str(row["dataset_name"])
            if pair_id in selected_ids or pair_hash in selected_hashes or group_key in selected_groups:
                continue
            if dataset_counts[dataset] >= args.max_per_dataset:
                continue
            chosen = dict(row)
            chosen["sample_stratum"] = stratum
            selected.append(chosen)
            selected_ids.add(pair_id)
            selected_hashes.add(pair_hash)
            selected_groups.add(group_key)
            dataset_counts[dataset] += 1
            if sum(1 for item in selected if item["sample_stratum"] == stratum) >= targets[stratum]:
                break
        actual = sum(1 for item in selected if item["sample_stratum"] == stratum)
        if actual != targets[stratum]:
            raise RuntimeError(f"Could not fill {stratum}: target={targets[stratum]} actual={actual}")

    selected.sort(key=lambda row: priority(args.seed, "final-order", int(row["pair_id"])))
    for index, row in enumerate(selected, start=1):
        row["annotation_id"] = f"EV1-{index:04d}"

    holdout_datasets = choose_holdout_datasets(selected, args.holdout_size, args.seed)
    for row in selected:
        row["confirmatory_partition"] = (
            "external_holdout" if str(row["dataset_name"]) in holdout_datasets else "development"
        )
    development = [row for row in selected if row["confirmatory_partition"] == "development"]
    holdout = [row for row in selected if row["confirmatory_partition"] == "external_holdout"]
    development_overlap_ids = select_overlap(development, args.overlap_rate, args.seed)
    holdout_overlap_ids = select_overlap(holdout, args.overlap_rate, args.seed + 1)
    overlap_ids = development_overlap_ids | holdout_overlap_ids
    for row in selected:
        row["double_annotation_overlap"] = 1 if str(row["annotation_id"]) in overlap_ids else 0
        for column in ANNOTATION_COLUMNS:
            row[column] = ""

    audit_subset_filename = (
        "development_ai_audit_subset.csv"
        if "ai_exploratory" in args.selection_version
        else "development_overlap_annotator_b_blind.csv"
    )
    holdout_audit_subset_filename = (
        "external_holdout_ai_audit_subset.csv"
        if "ai_exploratory" in args.selection_version
        else "external_holdout_overlap_annotator_b_blind.csv"
    )
    public_files = {
        "development_annotation_blind.csv": (development, BLIND_COLUMNS),
        audit_subset_filename: (
            [row for row in development if str(row["annotation_id"]) in development_overlap_ids],
            BLIND_COLUMNS,
        ),
        "external_holdout_annotation_blind.csv": (holdout, BLIND_COLUMNS),
        holdout_audit_subset_filename: (
            [row for row in holdout if str(row["annotation_id"]) in holdout_overlap_ids],
            BLIND_COLUMNS,
        ),
        "selection_key.csv": (selected, SELECTION_KEY_COLUMNS),
    }
    for filename, (rows, columns) in public_files.items():
        write_csv_new(args.output_dir / filename, rows, columns)
    write_csv_new(args.private_output_dir / "master_rule_key_private.csv", selected, PRIVATE_COLUMNS)

    source_counts = Counter(str(row["source"]) for row in selected)
    stratum_counts = Counter(str(row["sample_stratum"]) for row in selected)
    partition_counts = Counter(str(row["confirmatory_partition"]) for row in selected)
    partition_datasets = {
        name: sorted({str(row["dataset_name"]) for row in selected if row["confirmatory_partition"] == name})
        for name in ("development", "external_holdout")
    }
    partition_sources = {
        name: dict(Counter(str(row["source"]) for row in selected if row["confirmatory_partition"] == name))
        for name in ("development", "external_holdout")
    }
    public_hashes = {
        filename: {
            "sha256": file_sha256(args.output_dir / filename),
            "size_bytes": (args.output_dir / filename).stat().st_size,
        }
        for filename in public_files
    }
    manifest = {
        "schema_version": 1,
        "selection_version": args.selection_version,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "sampling_seed": args.seed,
        "database": {
            "path_recorded_for_provenance": str(args.db.resolve()),
            "opened_read_only": True,
            "size_bytes": os.path.getsize(args.db),
            "mtime": datetime.fromtimestamp(os.path.getmtime(args.db), timezone.utc).isoformat(),
            "dialogue_pairs": db_pair_count,
        },
        "exclusions": {
            "existing_gold_rows": len(gold_rows),
            "existing_pair_ids": len(excluded_ids),
            "existing_pair_hashes": len(excluded_hashes),
            "existing_conversation_groups": len(excluded_groups),
            "candidate_rows_excluded_by_existing_gold_or_group": excluded_existing,
        },
        "sampling": {
            "rows_scanned": scanned,
            "sample_size": len(selected),
            "stratum_targets": targets,
            "stratum_counts": dict(stratum_counts),
            "candidate_counts": dict(candidate_counts),
            "source_counts": dict(source_counts),
            "dataset_counts": dict(sorted(dataset_counts.items())),
            "max_per_dataset": args.max_per_dataset,
            "max_per_conversation_group": 1,
            "excluded_source_substrings": list(args.exclude_source_contains),
        },
        "partitions": {
            "target_holdout_size": args.holdout_size,
            "counts": dict(partition_counts),
            "dataset_disjoint": not (set(partition_datasets["development"]) & set(partition_datasets["external_holdout"])),
            "datasets": partition_datasets,
            "source_counts": partition_sources,
            "external_holdout_covers_all_selected_sources": (
                set(partition_sources["external_holdout"]) == set(source_counts)
            ),
            "development_double_annotation_overlap": len(development_overlap_ids),
            "external_holdout_double_annotation_overlap": len(holdout_overlap_ids),
            "total_double_annotation_overlap": len(overlap_ids),
            "overlap_rate_requested": args.overlap_rate,
        },
        "public_files": public_hashes,
        "audit_subset_files": {
            "development": audit_subset_filename,
            "external_holdout": holdout_audit_subset_filename,
            "purpose": (
                "AI second-pass audit subset; not an independent human overlap"
                if "ai_exploratory" in args.selection_version
                else "independent annotator overlap handoff"
            ),
        },
        "private_master": {
            "path": str(args.private_output_dir / "master_rule_key_private.csv"),
            "sha256": file_sha256(args.private_output_dir / "master_rule_key_private.csv"),
            "must_not_be_shown_to_annotators": True,
        },
        "labels_present": False,
        "exploratory_only": "ai_exploratory" in args.selection_version,
        "ai_labels_are_confirmatory": False,
        "holdout_labels_sealed": "ai_exploratory" not in args.selection_version,
    }
    write_json_new(args.output_dir / "selection_manifest.json", manifest)
    print(
        json.dumps(
            {
                "status": "ok",
                "sample_size": len(selected),
                "development": len(development),
                "external_holdout": len(holdout),
                "double_annotation_overlap": len(overlap_ids),
                "output_dir": str(args.output_dir.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
