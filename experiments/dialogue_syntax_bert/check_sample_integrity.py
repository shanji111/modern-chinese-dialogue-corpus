"""Check integrity of a dialogue-syntax annotation sample CSV."""

from __future__ import annotations

import argparse
from collections import Counter

from io_utils import read_csv


REQUIRED_COLUMNS = (
    "pair_id",
    "conversation_id",
    "entry_id",
    "source",
    "dataset",
    "speaker_a",
    "turn_a",
    "speaker_b",
    "turn_b",
    "rule_any_positive",
    "rule_summary",
    "rule_evidence_terms",
    "rule_markers",
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

HUMAN_COLUMNS = (
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Sample CSV to check.")
    parser.add_argument("--expected-count", type=int, default=50)
    parser.add_argument("--max-per-conversation", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = read_csv(args.csv)
    errors = []
    columns = set(rows[0].keys()) if rows else set()
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in columns]
    if missing_columns:
        errors.append(f"missing_columns={missing_columns}")
    if len(rows) != args.expected_count:
        errors.append(f"expected_count={args.expected_count} actual_count={len(rows)}")

    pair_ids = [row.get("pair_id", "") for row in rows]
    duplicate_pair_ids = len(pair_ids) - len(set(pair_ids))
    if duplicate_pair_ids:
        errors.append(f"duplicate_pair_ids={duplicate_pair_ids}")

    conversation_counts = Counter(row.get("conversation_id", "") for row in rows)
    max_seen = max(conversation_counts.values()) if conversation_counts else 0
    if max_seen > args.max_per_conversation:
        errors.append(f"max_conversation_count={max_seen} limit={args.max_per_conversation}")

    empty_a = sum(1 for row in rows if not (row.get("turn_a") or "").strip())
    empty_b = sum(1 for row in rows if not (row.get("turn_b") or "").strip())
    if empty_a or empty_b:
        errors.append(f"empty_texts turn_a={empty_a} turn_b={empty_b}")

    filled_human = {
        column: sum(1 for row in rows if (row.get(column) or "").strip())
        for column in HUMAN_COLUMNS
    }
    accidentally_filled = {column: count for column, count in filled_human.items() if count}
    if accidentally_filled:
        errors.append(f"human_columns_not_blank={accidentally_filled}")

    layer_counts = Counter(row.get("sample_layer", "") for row in rows)
    source_counts = Counter(row.get("source", "") for row in rows)
    dataset_counts = Counter(row.get("dataset", "") for row in rows)

    print("integrity_check")
    print(f"rows={len(rows)}")
    print(f"duplicate_pair_ids={duplicate_pair_ids}")
    print(f"max_conversation_count={max_seen}")
    print(f"empty_turn_a={empty_a}")
    print(f"empty_turn_b={empty_b}")
    print(f"layer_counts={dict(layer_counts)}")
    print(f"source_counts={dict(source_counts)}")
    print(f"dataset_count={len(dataset_counts)}")
    if errors:
        print("status=FAIL")
        for error in errors:
            print(f"error={error}")
        raise SystemExit(1)
    print("status=OK")


if __name__ == "__main__":
    main()

