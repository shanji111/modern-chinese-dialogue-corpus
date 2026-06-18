"""Sample dialogue pairs for pilot annotation.

The script reads `dialogue_pairs` from a SQLite database in read-only mode and
writes annotation-ready CSV/JSONL/report artifacts. It never writes to the
corpus database.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from io_utils import artifact_path, connect_sqlite_readonly, write_csv, write_jsonl


PAIR_TABLE = "dialogue_pairs"
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
    *RULE_OUTPUT_COLUMNS,
    *HUMAN_ANNOTATION_COLUMNS,
]

LAYER_TARGET_RATIOS = (
    ("rule_positive", 0.36),
    ("rule_negative_random", 0.28),
    ("hard_negative_shared_weak_rule", 0.20),
    ("source_dataset_diverse", 0.16),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to a SQLite corpus database to read in mode=ro.")
    parser.add_argument(
        "--output-dir",
        default=str(artifact_path("pilot_50")),
        help="Artifact directory for pilot_50.csv, pilot_50.jsonl, and sampling_report.md.",
    )
    parser.add_argument("--sample-size", type=int, default=50, help="Total pilot sample size.")
    parser.add_argument("--source", default="", help="Optional source filter.")
    parser.add_argument("--category", default="", help="Optional category filter.")
    parser.add_argument("--max-text-chars", type=int, default=260, help="Skip pairs with either turn longer than this.")
    parser.add_argument("--max-per-conversation", type=int, default=2, help="Maximum sampled pairs per conversation.")
    parser.add_argument("--seed", type=int, default=20260616, help="Python sampling seed.")
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


def layer_targets(sample_size: int) -> dict[str, int]:
    remaining = sample_size
    targets = {}
    for index, (layer, ratio) in enumerate(LAYER_TARGET_RATIOS):
        if index == len(LAYER_TARGET_RATIOS) - 1:
            count = remaining
        else:
            count = int(round(sample_size * ratio))
            remaining -= count
        targets[layer] = max(0, count)
    return targets


def choose_candidates(
    candidates: list[dict[str, object]],
    layer: str,
    target: int,
    rng: random.Random,
    selected_ids: set[int],
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
        conversation_id = str(row.get("conversation_id") or "")
        if pair_id in selected_ids:
            continue
        if conversation_counts[conversation_id] >= max_per_conversation:
            continue
        selected_ids.add(pair_id)
        conversation_counts[conversation_id] += 1
        row = dict(row)
        row["sample_layer"] = layer
        selected.append(row)
        if selected_datasets is not None:
            selected_datasets.add(str(row.get("dataset") or ""))
        if len(selected) >= target:
            break
    return selected


def sample_pilot_rows(conn, args: argparse.Namespace) -> tuple[list[dict[str, object]], dict[str, object]]:
    rng = random.Random(args.seed)
    targets = layer_targets(args.sample_size)
    selected_ids: set[int] = set()
    conversation_counts: Counter = Counter()
    selected_datasets: set[str] = set()
    selected_rows: list[dict[str, object]] = []

    positive_clause = "(" + " OR ".join(f"{flag} = 1" for flag in FLAG_COLUMNS) + ")"
    negative_clause = " AND ".join(f"{flag} = 0" for flag in FLAG_COLUMNS)
    weak_shared_clause = (
        "COALESCE(shared_terms, '[]') NOT IN ('[]', '') "
        "AND has_pattern_reuse = 0 "
        "AND has_question_response = 0 "
        "AND has_negation_turn = 0 "
        "AND has_repair_repetition = 0"
    )

    layer_candidates = {
        "rule_positive": candidate_rows(conn, args, positive_clause),
        "rule_negative_random": candidate_rows(conn, args, negative_clause),
        "hard_negative_shared_weak_rule": candidate_rows(conn, args, weak_shared_clause),
        "source_dataset_diverse": candidate_rows(conn, args),
    }

    for layer in ("rule_positive", "rule_negative_random", "hard_negative_shared_weak_rule"):
        rows = choose_candidates(
            layer_candidates[layer],
            layer,
            targets[layer],
            rng,
            selected_ids,
            conversation_counts,
            args.max_per_conversation,
            prefer_new_datasets=True,
            selected_datasets=selected_datasets,
        )
        selected_rows.extend(rows)

    diverse_rows = choose_candidates(
        layer_candidates["source_dataset_diverse"],
        "source_dataset_diverse",
        targets["source_dataset_diverse"],
        rng,
        selected_ids,
        conversation_counts,
        args.max_per_conversation,
        prefer_new_datasets=True,
        selected_datasets=selected_datasets,
    )
    selected_rows.extend(diverse_rows)

    if len(selected_rows) < args.sample_size:
        filler = choose_candidates(
            layer_candidates["source_dataset_diverse"],
            "fill_random",
            args.sample_size - len(selected_rows),
            rng,
            selected_ids,
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
        "sample_size_requested": args.sample_size,
        "sample_size_actual": len(selected_rows),
    }
    return selected_rows[:args.sample_size], metadata


def build_output_row(row: dict[str, object]) -> dict[str, object]:
    output = {column: "" for column in OUTPUT_COLUMNS}
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
    ):
        output[column] = row.get(column, "")
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
    layer_counts = Counter(str(row.get("sample_layer") or "") for row in rows)
    pair_ids = [int(row["pair_id"]) for row in rows]
    conversation_ids = [str(row.get("conversation_id") or "") for row in rows]
    conversation_counts = Counter(conversation_ids)
    empty_a = sum(1 for row in rows if not str(row.get("turn_a") or "").strip())
    empty_b = sum(1 for row in rows if not str(row.get("turn_b") or "").strip())
    lengths_a = [len(str(row.get("turn_a") or "")) for row in rows]
    lengths_b = [len(str(row.get("turn_b") or "")) for row in rows]
    duplicate_pairs = len(pair_ids) - len(set(pair_ids))
    repeated_conversations = sum(1 for count in conversation_counts.values() if count > 1)
    max_conversation_count = max(conversation_counts.values()) if conversation_counts else 0

    lines = [
        "# Pilot 50 Sampling Report",
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
        f"- Max per conversation: {metadata['max_per_conversation']}",
        "",
        "## Layer Counts",
        "",
        "| layer | target | sampled | candidate_pool |",
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
        "## Source / Dataset Distribution",
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
        f"- Conversations appearing more than once: {repeated_conversations}",
        f"- Max samples from one conversation: {max_conversation_count}",
        f"- Empty A-turn texts: {empty_a}",
        f"- Empty B-turn texts: {empty_b}",
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
        "- rule evidence: `shared_terms`, `markers` are flattened into short evidence columns.",
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


def write_sampling_report(path: Path, report: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    return path


def main() -> None:
    args = parse_args()
    db_path = Path(args.db).resolve()
    with connect_sqlite_readonly(db_path) as conn:
        rows, metadata = sample_pilot_rows(conn, args)

    output_rows = [build_output_row(row) for row in rows]
    output_dir = Path(args.output_dir)
    csv_path = write_csv(output_dir / "pilot_50.csv", output_rows, OUTPUT_COLUMNS)
    jsonl_path = write_jsonl(output_dir / "pilot_50.jsonl", output_rows)
    report = build_sampling_report(output_rows, metadata, db_path)
    report_path = write_sampling_report(output_dir / "sampling_report.md", report)
    print(f"sampled_pairs={len(output_rows)}")
    print(f"wrote_csv={csv_path}")
    print(f"wrote_jsonl={jsonl_path}")
    print(f"wrote_report={report_path}")


if __name__ == "__main__":
    main()
