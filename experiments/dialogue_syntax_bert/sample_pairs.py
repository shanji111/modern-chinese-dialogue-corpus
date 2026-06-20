"""Sample dialogue pairs for offline dialogue-syntax annotation.

The script reads `dialogue_pairs` from a SQLite database in read-only mode and
writes annotation-ready CSV/JSONL/report artifacts. It never writes to the
corpus database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from io_utils import artifact_path, connect_sqlite_readonly, write_csv, write_jsonl, write_text


PAIR_TABLE = "dialogue_pairs"
SCHEMA_VERSION = "dialogue_syntax_bert_v1"
FLAG_COLUMNS = (
    "has_lexical_echo",
    "has_pattern_reuse",
    "has_question_response",
    "has_negation_turn",
    "has_repair_repetition",
)

RULE_OUTPUT_COLUMNS = [
    "rule_any_positive",
    "rule_reproduction",
    "rule_parallelism",
    "rule_selective_reuse",
    "rule_repair",
    "rule_contrast",
    "rule_question_response",
    "rule_summary",
    "rule_evidence_terms",
    "rule_markers",
]

HUMAN_ANNOTATION_COLUMNS = [
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
]

OUTPUT_COLUMNS = [
    "schema_version",
    "sampling_seed",
    "normalized_pair_hash",
    "conversation_group_key",
    "sample_stratum",
    "pair_id",
    "conversation_id",
    "entry_id",
    "turn_a_id",
    "turn_b_id",
    "turn_index_a",
    "turn_index_b",
    "source",
    "category",
    "dataset",
    "speaker_a",
    "turn_a",
    "speaker_b",
    "turn_b",
    *FLAG_COLUMNS,
    "shared_terms",
    "markers",
    *RULE_OUTPUT_COLUMNS,
    *HUMAN_ANNOTATION_COLUMNS,
]

PILOT_TARGET_RATIOS = (
    ("rule_positive", 0.36),
    ("rule_negative_random", 0.28),
    ("hard_negative_shared_weak_rule", 0.20),
    ("source_dataset_diverse", 0.16),
)

FORMAL_V1_TARGET_RATIOS = (
    ("rule_positive", 0.30),
    ("rule_negative_random", 0.20),
    ("hard_negative_or_boundary", 0.20),
    ("potential_false_negative", 0.20),
    ("analogy_or_parallel_candidate", 0.10),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to a SQLite corpus database to read in mode=ro.")
    parser.add_argument(
        "--output-dir",
        default=str(artifact_path("pilot_50")),
        help="Artifact directory for sample CSV/JSONL/report outputs.",
    )
    parser.add_argument("--sample-size", type=int, default=50, help="Total sample size.")
    parser.add_argument(
        "--sampling-plan",
        choices=("pilot", "formal_300_v1"),
        default="pilot",
        help="Stratified sampling plan to use.",
    )
    parser.add_argument(
        "--output-prefix",
        default="pilot_50",
        help="Prefix for generated CSV/JSONL filenames, e.g. formal_300_v1.",
    )
    parser.add_argument("--source", default="", help="Optional source filter.")
    parser.add_argument("--category", default="", help="Optional category filter.")
    parser.add_argument("--max-text-chars", type=int, default=260, help="Skip pairs with either turn longer than this.")
    parser.add_argument("--max-per-conversation", type=int, default=2, help="Maximum sampled pairs per conversation.")
    parser.add_argument("--seed", type=int, default=20260616, help="Python sampling seed.")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting existing artifact files.")
    parser.add_argument(
        "--force-overwrite-labels",
        action="store_true",
        help="Also allow overwriting existing CSV/JSONL artifacts that contain human annotation values.",
    )
    return parser.parse_args()


def add_common_filters(clauses: list[str], params: list[object], args: argparse.Namespace) -> None:
    clauses.append("COALESCE(text_a, '') <> ''")
    clauses.append("COALESCE(text_b, '') <> ''")
    if args.max_text_chars > 0:
        clauses.append("LENGTH(text_a) <= ?")
        clauses.append("LENGTH(text_b) <= ?")
        params.extend([args.max_text_chars, args.max_text_chars])
    if args.source:
        clauses.append("source = ?")
        params.append(args.source)
    if args.category:
        clauses.append("category = ?")
        params.append(args.category)


def build_where_sql(args: argparse.Namespace, extra_clause: str = "") -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []
    add_common_filters(clauses, params, args)
    if extra_clause:
        clauses.append(extra_clause)
    return " AND ".join(clauses) if clauses else "1 = 1", params


def safe_json_list(raw: object) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def normalize_text_for_hash(text: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or "")).lower()
    return re.sub(r"\s+", " ", normalized).strip()


def normalized_pair_hash(text_a: object, text_b: object) -> str:
    payload = normalize_text_for_hash(text_a) + "\n<PAIR>\n" + normalize_text_for_hash(text_b)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def conversation_group_key(dataset_name: object, conversation_key: object) -> str:
    dataset = str(dataset_name or "").strip() or "unknown_dataset"
    conversation = str(conversation_key or "").strip() or "unknown_conversation"
    return f"{dataset}::{conversation}"


def rule_values(row: dict[str, object]) -> dict[str, object]:
    reproduction = int(row.get("has_lexical_echo") or 0) == 1
    parallelism = int(row.get("has_pattern_reuse") or 0) == 1
    question = int(row.get("has_question_response") or 0) == 1
    contrast = int(row.get("has_negation_turn") or 0) == 1
    repair = int(row.get("has_repair_repetition") or 0) == 1
    labels = []
    if reproduction:
        labels.append("reproduction")
    if parallelism:
        labels.append("parallelism")
    if repair:
        labels.append("selective_reuse/repair")
    if contrast:
        labels.append("contrast")
    if question:
        labels.append("question_response")
    shared_terms = safe_json_list(row.get("shared_terms"))
    markers = safe_json_list(row.get("markers"))
    return {
        "rule_any_positive": 1 if labels else 0,
        "rule_reproduction": 1 if reproduction else 0,
        "rule_parallelism": 1 if parallelism else 0,
        "rule_selective_reuse": 1 if repair else 0,
        "rule_repair": 1 if repair else 0,
        "rule_contrast": 1 if contrast else 0,
        "rule_question_response": 1 if question else 0,
        "rule_summary": " | ".join(labels) if labels else "no_rule_hit",
        "rule_evidence_terms": " / ".join(shared_terms[:8]),
        "rule_markers": " / ".join(markers[:12]),
    }


def candidate_rows(conn, args: argparse.Namespace, extra_clause: str = "") -> list[dict[str, object]]:
    where_sql, params = build_where_sql(args, extra_clause)
    rows = conn.execute(
        f"""
        SELECT
          id AS pair_id,
          turn_a_id,
          turn_b_id,
          entry_id,
          conversation_key AS conversation_id,
          turn_index_a,
          turn_index_b,
          COALESCE(speaker_a, '') AS speaker_a,
          COALESCE(speaker_b, '') AS speaker_b,
          text_a AS turn_a,
          text_b AS turn_b,
          COALESCE(source, '') AS source,
          COALESCE(category, '') AS category,
          COALESCE(dataset_name, '') AS dataset,
          COALESCE(shared_terms, '[]') AS shared_terms,
          COALESCE(markers, '[]') AS markers,
          {", ".join(FLAG_COLUMNS)},
          LENGTH(COALESCE(text_a, '')) AS len_a,
          LENGTH(COALESCE(text_b, '')) AS len_b
        FROM {PAIR_TABLE}
        WHERE {where_sql}
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def layer_ratios(sampling_plan: str) -> tuple[tuple[str, float], ...]:
    if sampling_plan == "formal_300_v1":
        return FORMAL_V1_TARGET_RATIOS
    return PILOT_TARGET_RATIOS


def layer_targets(sample_size: int, sampling_plan: str) -> dict[str, int]:
    ratios = layer_ratios(sampling_plan)
    remaining = sample_size
    targets = {}
    for index, (layer, ratio) in enumerate(ratios):
        if index == len(ratios) - 1:
            count = remaining
        else:
            count = int(round(sample_size * ratio))
            remaining -= count
        targets[layer] = max(0, count)
    return targets


def flags_positive_clause() -> str:
    return "(" + " OR ".join(f"COALESCE({flag}, 0) = 1" for flag in FLAG_COLUMNS) + ")"


def flags_negative_clause() -> str:
    return " AND ".join(f"COALESCE({flag}, 0) = 0" for flag in FLAG_COLUMNS)


def like_any(columns: tuple[str, ...], patterns: tuple[str, ...]) -> str:
    clauses = []
    for column in columns:
        for pattern in patterns:
            clauses.append(f"{column} LIKE '%{pattern}%'")
    return "(" + " OR ".join(clauses) + ")"


def formal_layer_clauses() -> dict[str, str]:
    negative = flags_negative_clause()
    has_shared_terms = "COALESCE(shared_terms, '[]') NOT IN ('[]', '')"
    questionish = like_any(("text_a",), ("？", "?", "什么", "谁", "哪", "何", "吗", "么"))
    demonstrative_b = like_any(("text_b",), ("这", "此", "那个", "这些", "这俩", "那"))
    handoff_b = (
        "(text_b LIKE '%请%回答%' OR text_b LIKE '%请%说%' "
        "OR text_b LIKE '%让%回答%' OR text_b LIKE '%让%说%')"
    )
    short_answer = "(LENGTH(COALESCE(text_b, '')) <= 12 OR LENGTH(COALESCE(text_a, '')) <= 12)"
    repair_or_contrast = like_any(
        ("text_b",),
        ("不", "不是", "没有", "但是", "不过", "其实", "错", "应该", "不对"),
    )
    analogy_or_parallel = like_any(
        ("text_a", "text_b"),
        ("胜于", "不如", "比", "像", "如同", "一样", "不是", "而是", "反过来"),
    )
    hard_boundary = (
        f"({has_shared_terms} OR COALESCE(has_question_response, 0) = 1 "
        f"OR {demonstrative_b} OR {handoff_b} OR {short_answer})"
    )
    potential_false_negative = (
        f"({negative}) AND ({questionish} OR {demonstrative_b} OR {short_answer} OR {repair_or_contrast})"
    )
    return {
        "rule_positive": flags_positive_clause(),
        "rule_negative_random": negative,
        "hard_negative_or_boundary": hard_boundary,
        "potential_false_negative": potential_false_negative,
        "analogy_or_parallel_candidate": f"({analogy_or_parallel} OR COALESCE(has_pattern_reuse, 0) = 1)",
    }


def choose_candidates(
    candidates: list[dict[str, object]],
    stratum: str,
    target: int,
    rng: random.Random,
    selected_ids: set[int],
    selected_hashes: set[str],
    conversation_counts: Counter,
    max_per_conversation: int,
    prefer_new_datasets: bool = False,
    selected_datasets: set[str] | None = None,
) -> list[dict[str, object]]:
    if prefer_new_datasets:
        grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
        for row in candidates:
            grouped[
                (
                    str(row.get("source") or ""),
                    str(row.get("category") or ""),
                    str(row.get("dataset") or ""),
                )
            ].append(row)
        group_keys = list(grouped.keys())
        rng.shuffle(group_keys)
        if selected_datasets is not None:
            group_keys.sort(key=lambda key: key[2] in selected_datasets)
        for key in group_keys:
            rng.shuffle(grouped[key])
        pool = []
        while group_keys:
            next_keys = []
            for key in group_keys:
                bucket = grouped[key]
                if bucket:
                    pool.append(bucket.pop())
                if bucket:
                    next_keys.append(key)
            group_keys = next_keys
    else:
        pool = list(candidates)
        rng.shuffle(pool)
    selected = []
    for row in pool:
        pair_id = int(row["pair_id"])
        pair_hash = normalized_pair_hash(row.get("turn_a"), row.get("turn_b"))
        conv_group = conversation_group_key(row.get("dataset"), row.get("conversation_id"))
        if pair_id in selected_ids:
            continue
        if pair_hash in selected_hashes:
            continue
        if conversation_counts[conv_group] >= max_per_conversation:
            continue
        selected_ids.add(pair_id)
        selected_hashes.add(pair_hash)
        conversation_counts[conv_group] += 1
        row = dict(row)
        row["sample_stratum"] = stratum
        selected.append(row)
        if selected_datasets is not None:
            selected_datasets.add(str(row.get("dataset") or ""))
        if len(selected) >= target:
            break
    return selected


def sample_pilot_rows(conn, args: argparse.Namespace) -> tuple[list[dict[str, object]], dict[str, object]]:
    rng = random.Random(args.seed)
    targets = layer_targets(args.sample_size, args.sampling_plan)
    selected_ids: set[int] = set()
    selected_hashes: set[str] = set()
    conversation_counts: Counter = Counter()
    selected_datasets: set[str] = set()
    selected_rows: list[dict[str, object]] = []

    positive_clause = flags_positive_clause()
    negative_clause = flags_negative_clause()
    weak_shared_clause = (
        "COALESCE(shared_terms, '[]') NOT IN ('[]', '') "
        "AND COALESCE(has_pattern_reuse, 0) = 0 "
        "AND COALESCE(has_question_response, 0) = 0 "
        "AND COALESCE(has_negation_turn, 0) = 0 "
        "AND COALESCE(has_repair_repetition, 0) = 0"
    )

    if args.sampling_plan == "formal_300_v1":
        clauses = formal_layer_clauses()
        layer_candidates = {layer: candidate_rows(conn, args, clause) for layer, clause in clauses.items()}
        layer_order = tuple(targets.keys())
    else:
        layer_candidates = {
            "rule_positive": candidate_rows(conn, args, positive_clause),
            "rule_negative_random": candidate_rows(conn, args, negative_clause),
            "hard_negative_shared_weak_rule": candidate_rows(conn, args, weak_shared_clause),
            "source_dataset_diverse": candidate_rows(conn, args),
        }
        layer_order = ("rule_positive", "rule_negative_random", "hard_negative_shared_weak_rule")

    for layer in layer_order:
        rows = choose_candidates(
            layer_candidates[layer],
            layer,
            targets[layer],
            rng,
            selected_ids,
            selected_hashes,
            conversation_counts,
            args.max_per_conversation,
            prefer_new_datasets=True,
            selected_datasets=selected_datasets,
        )
        selected_rows.extend(rows)

    if args.sampling_plan != "formal_300_v1":
        diverse_rows = choose_candidates(
            layer_candidates["source_dataset_diverse"],
            "source_dataset_diverse",
            targets["source_dataset_diverse"],
            rng,
            selected_ids,
            selected_hashes,
            conversation_counts,
            args.max_per_conversation,
            prefer_new_datasets=True,
            selected_datasets=selected_datasets,
        )
        selected_rows.extend(diverse_rows)

    if len(selected_rows) < args.sample_size:
        filler_candidates = candidate_rows(conn, args)
        filler = choose_candidates(
            filler_candidates,
            "fill_random",
            args.sample_size - len(selected_rows),
            rng,
            selected_ids,
            selected_hashes,
            conversation_counts,
            args.max_per_conversation,
            selected_datasets=selected_datasets,
        )
        selected_rows.extend(filler)

    metadata = {
        "targets": targets,
        "candidate_counts": {layer: len(rows) for layer, rows in layer_candidates.items()},
        "seed": args.seed,
        "max_per_conversation": args.max_per_conversation,
        "sampling_plan": args.sampling_plan,
        "sample_size_requested": args.sample_size,
        "sample_size_actual": len(selected_rows),
    }
    return selected_rows[:args.sample_size], metadata


def build_output_row(row: dict[str, object]) -> dict[str, object]:
    output = {column: "" for column in OUTPUT_COLUMNS}
    pair_hash = normalized_pair_hash(row.get("turn_a"), row.get("turn_b"))
    output["schema_version"] = SCHEMA_VERSION
    output["sampling_seed"] = row.get("sampling_seed", "")
    output["normalized_pair_hash"] = pair_hash
    output["conversation_group_key"] = conversation_group_key(row.get("dataset"), row.get("conversation_id"))
    for column in (
        "sample_layer",
        "pair_id",
        "conversation_id",
        "entry_id",
        "turn_a_id",
        "turn_b_id",
        "turn_index_a",
        "turn_index_b",
        "source",
        "category",
        "dataset",
        "speaker_a",
        "turn_a",
        "speaker_b",
        "turn_b",
        *FLAG_COLUMNS,
        "shared_terms",
        "markers",
    ):
        output[column] = row.get(column, "")
    output["sample_stratum"] = row.get("sample_stratum", row.get("sample_layer", ""))
    output.update(rule_values(row))
    for column in HUMAN_ANNOTATION_COLUMNS:
        output[column] = ""
    return output


def length_stats(values: list[int]) -> dict[str, float | int]:
    if not values:
        return {"min": 0, "p50": 0, "avg": 0.0, "max": 0}
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        p50 = ordered[midpoint]
    else:
        p50 = (ordered[midpoint - 1] + ordered[midpoint]) / 2
    return {"min": ordered[0], "p50": p50, "avg": mean(ordered), "max": ordered[-1]}


def source_distribution(rows: list[dict[str, object]]) -> list[tuple[str, str, str, int]]:
    counts = Counter(
        (
            str(row.get("source") or ""),
            str(row.get("category") or ""),
            str(row.get("dataset") or ""),
        )
        for row in rows
    )
    return [(source, category, dataset, count) for (source, category, dataset), count in counts.most_common()]


def build_sampling_report(
    rows: list[dict[str, object]],
    metadata: dict[str, object],
    db_path: Path,
) -> str:
    layer_counts = Counter(str(row.get("sample_stratum") or row.get("sample_layer") or "") for row in rows)
    pair_ids = [int(row["pair_id"]) for row in rows]
    conversation_groups = [str(row.get("conversation_group_key") or "") for row in rows]
    conversation_counts = Counter(conversation_groups)
    pair_hashes = [str(row.get("normalized_pair_hash") or "") for row in rows]
    hash_counts = Counter(pair_hashes)
    empty_a = sum(1 for row in rows if not str(row.get("turn_a") or "").strip())
    empty_b = sum(1 for row in rows if not str(row.get("turn_b") or "").strip())
    lengths_a = [len(str(row.get("turn_a") or "")) for row in rows]
    lengths_b = [len(str(row.get("turn_b") or "")) for row in rows]
    duplicate_pairs = len(pair_ids) - len(set(pair_ids))
    duplicate_hashes = len(pair_hashes) - len(set(pair_hashes))
    repeated_conversations = sum(1 for count in conversation_counts.values() if count > 1)
    max_conversation_count = max(conversation_counts.values()) if conversation_counts else 0
    source_counts = Counter(str(row.get("source") or "") for row in rows)
    dataset_counts = Counter(str(row.get("dataset") or "") for row in rows)

    lines = [
        "# Sampling Report",
        "",
        "## Database Access",
        "",
        f"- SQLite URI mode: `file:{db_path.as_posix()}?mode=ro`",
        "- Operations executed: `SELECT`, `PRAGMA`, and aggregation only.",
        "- Database writes: none.",
        "",
        "## Sample Size",
        "",
        f"- Requested: {metadata['sample_size_requested']}",
        f"- Actual: {metadata['sample_size_actual']}",
        f"- Seed: {metadata['seed']}",
        f"- Sampling plan: {metadata.get('sampling_plan', 'pilot')}",
        f"- Max per conversation: {metadata['max_per_conversation']}",
        "",
        "## Stratum Counts",
        "",
        "| sample_stratum | target | sampled | candidate_pool |",
        "| --- | ---: | ---: | ---: |",
    ]
    targets = metadata["targets"]
    candidate_counts = metadata["candidate_counts"]
    for layer in [*targets.keys(), "fill_random"]:
        lines.append(
            f"| {layer} | {targets.get(layer, 0)} | {layer_counts.get(layer, 0)} | {candidate_counts.get(layer, '')} |"
        )

    lines.extend([
        "",
        "## Source Distribution",
        "",
        "| source | count |",
        "| --- | ---: |",
    ])
    for source, count in source_counts.most_common():
        lines.append(f"| {source or '(empty)'} | {count} |")

    lines.extend([
        "",
        "## Dataset Distribution",
        "",
        "| dataset | count |",
        "| --- | ---: |",
    ])
    for dataset, count in dataset_counts.most_common():
        lines.append(f"| {dataset or '(empty)'} | {count} |")

    lines.extend([
        "",
        "## Source / Category / Dataset Distribution",
        "",
        "| source | category | dataset | count |",
        "| --- | --- | --- | ---: |",
    ])
    for source, category, dataset, count in source_distribution(rows):
        lines.append(f"| {source or '(empty)'} | {category or '(empty)'} | {dataset or '(empty)'} | {count} |")

    lines.extend([
        "",
        "## Duplicate And Empty Checks",
        "",
        f"- Duplicate pair IDs: {duplicate_pairs}",
        f"- Duplicate normalized_pair_hash values: {duplicate_hashes}",
        f"- conversation_group_key values appearing more than once: {repeated_conversations}",
        f"- Max samples from one conversation_group_key: {max_conversation_count}",
        f"- Empty A-turn texts: {empty_a}",
        f"- Empty B-turn texts: {empty_b}",
        "",
        "## Repeated Conversation Groups",
        "",
        "| conversation_group_key | count |",
        "| --- | ---: |",
    ])
    for group, count in conversation_counts.most_common(20):
        if count > 1:
            lines.append(f"| {group} | {count} |")
    if all(count <= 1 for count in conversation_counts.values()):
        lines.append("| (none) | 0 |")

    lines.extend([
        "",
        "## Repeated normalized_pair_hash Values",
        "",
        "| normalized_pair_hash | count |",
        "| --- | ---: |",
    ])
    for pair_hash, count in hash_counts.most_common(20):
        if count > 1:
            lines.append(f"| `{pair_hash}` | {count} |")
    if all(count <= 1 for count in hash_counts.values()):
        lines.append("| (none) | 0 |")

    lines.extend([
        "",
        "## Text Lengths",
        "",
        "| side | min | p50 | avg | max |",
        "| --- | ---: | ---: | ---: | ---: |",
    ])
    stats_a = length_stats(lengths_a)
    stats_b = length_stats(lengths_b)
    lines.append(f"| A | {stats_a['min']} | {stats_a['p50']} | {stats_a['avg']:.1f} | {stats_a['max']} |")
    lines.append(f"| B | {stats_b['min']} | {stats_b['p50']} | {stats_b['avg']:.1f} | {stats_b['max']} |")
    lines.extend([
        "",
        "## Field Mapping",
        "",
        "- pair primary key: `dialogue_pairs.id` -> `pair_id`",
        "- conversation identifier: `dialogue_pairs.conversation_key` -> `conversation_id`",
        "- entry identifier: `dialogue_pairs.entry_id` -> `entry_id`",
        "- A/B text: `text_a`, `text_b` -> `turn_a`, `turn_b`",
        "- speaker: `speaker_a`, `speaker_b`",
        "- source/category/dataset: `source`, `category`, `dataset_name` -> `dataset`",
        "- rule flags: `has_lexical_echo`, `has_pattern_reuse`, `has_question_response`, `has_negation_turn`, `has_repair_repetition`",
        "- rule evidence: raw `shared_terms`, raw `markers`, plus flattened `rule_evidence_terms` and `rule_markers`.",
        "- duplicate-text protection: `normalized_pair_hash` is SHA-256 over normalized `turn_a + turn_b`.",
        "- conversation split protection: `conversation_group_key` is `dataset_name::conversation_key` and should not cross train/dev/test.",
        "- experiment metadata: `schema_version` and `sampling_seed` are written into each row.",
        "- future train/dev/test checks must require disjoint `pair_id`, `normalized_pair_hash`, and `conversation_group_key` sets.",
        "",
        "## Annotation Columns",
        "",
        "- Leave all human annotation columns blank before manual annotation.",
        "- `resonance_present` should be filled with `yes`, `no`, or `uncertain`.",
        "- Relation labels are multi-label: fill `1` only when the relation is present.",
        "- Use `evidence_span_a` and `evidence_span_b` for short supporting spans, not full-turn copies.",
        "- Use `uncertainty_reason` when `resonance_present=uncertain` or labels are borderline.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    db_path = Path(args.db).resolve()
    with connect_sqlite_readonly(db_path) as conn:
        rows, metadata = sample_pilot_rows(conn, args)

    for row in rows:
        row["sampling_seed"] = args.seed
    output_rows = [build_output_row(row) for row in rows]
    output_dir = Path(args.output_dir)
    output_prefix = args.output_prefix
    csv_path = write_csv(
        output_dir / f"{output_prefix}.csv",
        output_rows,
        OUTPUT_COLUMNS,
        overwrite=args.overwrite,
        force_overwrite_labels=args.force_overwrite_labels,
    )
    jsonl_path = write_jsonl(
        output_dir / f"{output_prefix}.jsonl",
        output_rows,
        overwrite=args.overwrite,
        force_overwrite_labels=args.force_overwrite_labels,
    )
    report = build_sampling_report(output_rows, metadata, db_path)
    report_path = write_text(output_dir / "sampling_report.md", report, overwrite=args.overwrite)
    print(f"sampled_pairs={len(output_rows)}")
    print(f"wrote_csv={csv_path}")
    print(f"wrote_jsonl={jsonl_path}")
    print(f"wrote_report={report_path}")


if __name__ == "__main__":
    main()
