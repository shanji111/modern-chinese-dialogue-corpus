"""Validate a filled blind annotation CSV without modifying it."""

from __future__ import annotations

import argparse
from collections import Counter

from io_utils import read_csv
from split_blind_annotation import BLIND_COLUMNS


RESONANCE_VALUES = {"yes", "no", "uncertain"}
LABEL_VALUES = {"1", "0", "?"}
CORE_LABEL_COLUMNS = (
    "label_reproduction",
    "label_parallelism",
    "label_selective_reuse",
    "label_repair",
    "label_contrast",
)
LABEL_COLUMNS = (*CORE_LABEL_COLUMNS, "label_analogy_candidate")
REQUIRED_METADATA_COLUMNS = (
    "annotation_id",
    "pair_id",
    "source",
    "dataset_name",
    "turn_a",
    "turn_b",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", help="Filled blind annotation CSV.")
    parser.add_argument("--self-test", action="store_true", help="Run in-memory legal/illegal smoke tests.")
    return parser.parse_args()


def split_spans(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split("|||") if part.strip()]


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    issues: list[str] = []
    if not rows:
        return ["file has no rows"]
    columns = set(rows[0].keys())
    missing_columns = [column for column in BLIND_COLUMNS if column not in columns]
    if missing_columns:
        issues.append(f"missing columns: {missing_columns}")

    annotation_counts = Counter(row.get("annotation_id", "") for row in rows)
    pair_counts = Counter(row.get("pair_id", "") for row in rows)
    for annotation_id, count in annotation_counts.items():
        if annotation_id and count > 1:
            issues.append(f"duplicate annotation_id={annotation_id} count={count}")
    for pair_id, count in pair_counts.items():
        if pair_id and count > 1:
            issues.append(f"duplicate pair_id={pair_id} count={count}")

    for row_number, row in enumerate(rows, 2):
        for column in REQUIRED_METADATA_COLUMNS:
            if not (row.get(column) or "").strip():
                issues.append(f"row {row_number}: required field {column} is empty")

        resonance = (row.get("resonance_present") or "").strip()
        if resonance not in RESONANCE_VALUES:
            issues.append(f"row {row_number}: illegal resonance_present={resonance!r}")

        label_values = {}
        for column in LABEL_COLUMNS:
            value = (row.get(column) or "").strip()
            label_values[column] = value
            if value not in LABEL_VALUES:
                issues.append(f"row {row_number}: illegal {column}={value!r}")

        core_positive = [column for column in CORE_LABEL_COLUMNS if label_values.get(column) == "1"]
        if resonance == "yes" and not core_positive:
            issues.append(f"row {row_number}: resonance_present=yes but all core labels are 0/?")
        if resonance == "no" and core_positive:
            issues.append(f"row {row_number}: resonance_present=no but core labels are 1: {core_positive}")

        turn_a = row.get("turn_a") or ""
        turn_b = row.get("turn_b") or ""
        for span in split_spans(row.get("evidence_span_a") or ""):
            if span not in turn_a:
                issues.append(f"row {row_number}: evidence_span_a not found in turn_a: {span!r}")
        for span in split_spans(row.get("evidence_span_b") or ""):
            if span not in turn_b:
                issues.append(f"row {row_number}: evidence_span_b not found in turn_b: {span!r}")
    return issues


def self_test() -> None:
    legal = [{
        "annotation_id": "T-0001",
        "pair_id": "1",
        "source": "test",
        "dataset_name": "testset",
        "speaker_a": "A",
        "turn_a": "你为什么不去北京",
        "speaker_b": "B",
        "turn_b": "不是不去北京，是明天去",
        "resonance_present": "yes",
        "label_reproduction": "1",
        "label_parallelism": "0",
        "label_selective_reuse": "0",
        "label_repair": "1",
        "label_contrast": "1",
        "label_analogy_candidate": "0",
        "evidence_span_a": "不去北京",
        "evidence_span_b": "不是不去北京",
        "annotator_note": "",
        "uncertainty_reason": "",
    }]
    illegal = [dict(legal[0], annotation_id="T-0002", resonance_present="maybe", label_reproduction="yes", evidence_span_a="不存在")]
    legal_issues = validate_rows(legal)
    illegal_issues = validate_rows(illegal)
    print(f"self_test_legal_issues={len(legal_issues)}")
    print(f"self_test_illegal_issues={len(illegal_issues)}")
    if legal_issues:
        print("\n".join(legal_issues))
        raise SystemExit(1)
    if not illegal_issues:
        print("illegal sample unexpectedly passed")
        raise SystemExit(1)


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    if not args.csv:
        raise SystemExit("--csv is required unless --self-test is used.")
    rows = read_csv(args.csv)
    issues = validate_rows(rows)
    print(f"rows={len(rows)}")
    print(f"issues={len(issues)}")
    for issue in issues:
        print(f"issue={issue}")
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

