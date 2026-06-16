"""Sample dialogue pairs for multi-label annotation.

The script reads `dialogue_pairs` from a SQLite database in read-only mode and
writes annotation-ready CSV/JSONL artifacts. It never writes to the corpus
database.
"""

from __future__ import annotations

import argparse
import random
from collections import defaultdict
from pathlib import Path

from io_utils import artifact_path, connect_sqlite_readonly, write_csv, write_jsonl
from labels import ANNOTATION_COLUMNS, POSITIVE_LABEL_KEYS, RULE_COLUMNS, RULE_FLAG_COLUMNS, rule_labels_from_row


PAIR_TABLE = "dialogue_pairs"
FLAG_COLUMNS = (
    "has_lexical_echo",
    "has_pattern_reuse",
    "has_question_response",
    "has_negation_turn",
    "has_repair_repetition",
)

BASE_COLUMNS = [
    "sample_bucket",
    "pair_id",
    "turn_a_id",
    "turn_b_id",
    "entry_id",
    "conversation_key",
    "turn_index_a",
    "turn_index_b",
    "speaker_a",
    "speaker_b",
    "text_a",
    "text_b",
    "source",
    "category",
    "dataset_name",
    "shared_terms",
    "markers",
    *FLAG_COLUMNS,
    *RULE_COLUMNS,
    *ANNOTATION_COLUMNS,
    "annotation_confidence",
    "annotator",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to a SQLite corpus database to read in mode=ro.")
    parser.add_argument(
        "--output-csv",
        default=str(artifact_path("annotation", "dialogue_pair_annotation_sample.csv")),
        help="Annotation CSV output path.",
    )
    parser.add_argument(
        "--output-jsonl",
        default=str(artifact_path("annotation", "dialogue_pair_annotation_sample.jsonl")),
        help="JSONL mirror output path for later model experiments.",
    )
    parser.add_argument("--per-label", type=int, default=200, help="Pairs to sample for each rule-backed label.")
    parser.add_argument("--negative", type=int, default=400, help="Pairs to sample where all current rule flags are 0.")
    parser.add_argument("--random", type=int, default=200, help="Extra random pairs to sample across the table.")
    parser.add_argument("--source", default="", help="Optional source filter.")
    parser.add_argument("--category", default="", help="Optional category filter.")
    parser.add_argument("--max-text-chars", type=int, default=220, help="Skip pairs with either turn longer than this.")
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


def fetch_candidate_ids(conn, args: argparse.Namespace, extra_clause: str = "") -> list[int]:
    clauses: list[str] = []
    params: list[object] = []
    add_common_filters(clauses, params, args)
    if extra_clause:
        clauses.append(extra_clause)
    where_sql = " AND ".join(clauses) if clauses else "1 = 1"
    rows = conn.execute(f"SELECT id FROM {PAIR_TABLE} WHERE {where_sql}", params).fetchall()
    return [int(row["id"]) for row in rows]


def take_sample(ids: list[int], limit: int, rng: random.Random) -> list[int]:
    if limit <= 0 or not ids:
        return []
    if len(ids) <= limit:
        sample = list(ids)
    else:
        sample = rng.sample(ids, limit)
    sample.sort(reverse=True)
    return sample


def fetch_pairs_by_ids(conn, pair_ids: list[int]) -> dict[int, dict[str, object]]:
    if not pair_ids:
        return {}
    selected = ", ".join(
        [
            "id AS pair_id",
            "turn_a_id",
            "turn_b_id",
            "entry_id",
            "conversation_key",
            "turn_index_a",
            "turn_index_b",
            "speaker_a",
            "speaker_b",
            "text_a",
            "text_b",
            "source",
            "category",
            "dataset_name",
            "shared_terms",
            "markers",
            *FLAG_COLUMNS,
        ]
    )
    rows_by_id: dict[int, dict[str, object]] = {}
    chunk_size = 500
    for start in range(0, len(pair_ids), chunk_size):
        chunk = pair_ids[start:start + chunk_size]
        placeholders = ", ".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT {selected} FROM {PAIR_TABLE} WHERE id IN ({placeholders})",
            chunk,
        ).fetchall()
        for row in rows:
            row_dict = dict(row)
            rows_by_id[int(row_dict["pair_id"])] = row_dict
    return rows_by_id


def build_annotation_row(row: dict[str, object], buckets: list[str]) -> dict[str, object]:
    rule_predictions = rule_labels_from_row(row)
    output = {column: "" for column in BASE_COLUMNS}
    output.update(row)
    output["sample_bucket"] = "|".join(buckets)
    for label_key, predicted in rule_predictions.items():
        output[f"rule_{label_key}"] = 1 if predicted else 0
    for label_column in ANNOTATION_COLUMNS:
        output[label_column] = ""
    output["annotation_confidence"] = ""
    output["annotator"] = ""
    output["notes"] = ""
    return output


def sample_pair_ids(conn, args: argparse.Namespace) -> tuple[list[int], dict[int, list[str]]]:
    rng = random.Random(args.seed)
    bucket_map: dict[int, list[str]] = defaultdict(list)
    ordered_ids: list[int] = []
    seen: set[int] = set()

    def add_bucket(bucket: str, ids: list[int]) -> None:
        for pair_id in ids:
            bucket_map[pair_id].append(bucket)
            if pair_id not in seen:
                seen.add(pair_id)
                ordered_ids.append(pair_id)

    for label_key in POSITIVE_LABEL_KEYS:
        flag_name = RULE_FLAG_COLUMNS[label_key]
        if not flag_name:
            continue
        ids = fetch_candidate_ids(conn, args, f"{flag_name} = 1")
        add_bucket(label_key, take_sample(ids, args.per_label, rng))

    negative_clause = " AND ".join(f"{flag} = 0" for flag in FLAG_COLUMNS)
    negative_ids = fetch_candidate_ids(conn, args, negative_clause)
    add_bucket("rule_negative", take_sample(negative_ids, args.negative, rng))

    random_ids = fetch_candidate_ids(conn, args)
    add_bucket("random", take_sample(random_ids, args.random, rng))

    return ordered_ids, bucket_map


def main() -> None:
    args = parse_args()
    with connect_sqlite_readonly(args.db) as conn:
        pair_ids, bucket_map = sample_pair_ids(conn, args)
        rows_by_id = fetch_pairs_by_ids(conn, pair_ids)

    rows = [
        build_annotation_row(rows_by_id[pair_id], bucket_map[pair_id])
        for pair_id in pair_ids
        if pair_id in rows_by_id
    ]
    csv_path = write_csv(args.output_csv, rows, BASE_COLUMNS)
    jsonl_path = write_jsonl(args.output_jsonl, rows)
    print(f"sampled_pairs={len(rows)}")
    print(f"wrote_csv={csv_path}")
    print(f"wrote_jsonl={jsonl_path}")


if __name__ == "__main__":
    main()

