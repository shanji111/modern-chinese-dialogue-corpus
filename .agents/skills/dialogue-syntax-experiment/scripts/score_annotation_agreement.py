from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


DEFAULT_FIELDS = [
    "resonance_present",
    "label_reproduction",
    "label_parallelism",
    "label_selective_reuse",
    "label_repair",
    "label_contrast",
    "label_analogy_candidate",
]


def read_rows(path: Path, key: str) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key, "").strip()
        if not value:
            raise ValueError(f"Missing {key} in {path}")
        if value in result:
            raise ValueError(f"Duplicate {key}={value} in {path}")
        result[value] = row
    return result


def cohen_kappa(a: list[str], b: list[str]) -> tuple[float | None, float]:
    if len(a) != len(b) or not a:
        raise ValueError("Agreement vectors must be non-empty and equal length")
    observed = sum(x == y for x, y in zip(a, b)) / len(a)
    labels = sorted(set(a) | set(b))
    counts_a = Counter(a)
    counts_b = Counter(b)
    expected = sum((counts_a[label] / len(a)) * (counts_b[label] / len(b)) for label in labels)
    if expected == 1.0:
        return None, observed
    return (observed - expected) / (1.0 - expected), observed


def main() -> int:
    parser = argparse.ArgumentParser(description="Score pre-adjudication annotation agreement.")
    parser.add_argument("--annotator-a", type=Path, required=True)
    parser.add_argument("--annotator-b", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--key", default="annotation_id")
    parser.add_argument("--fields", nargs="+", default=DEFAULT_FIELDS)
    args = parser.parse_args()

    rows_a = read_rows(args.annotator_a, args.key)
    rows_b = read_rows(args.annotator_b, args.key)
    shared = sorted(set(rows_a) & set(rows_b))
    only_a = sorted(set(rows_a) - set(rows_b))
    only_b = sorted(set(rows_b) - set(rows_a))
    if not shared:
        raise ValueError("The two files have no shared annotation IDs")

    fields: dict[str, dict[str, object]] = {}
    disagreements: list[dict[str, str]] = []
    for field in args.fields:
        values_a = [rows_a[key].get(field, "").strip() for key in shared]
        values_b = [rows_b[key].get(field, "").strip() for key in shared]
        kappa, observed = cohen_kappa(values_a, values_b)
        fields[field] = {
            "n": len(shared),
            "raw_agreement": observed,
            "cohen_kappa": kappa,
            "distribution_a": dict(Counter(values_a)),
            "distribution_b": dict(Counter(values_b)),
        }
        for key, value_a, value_b in zip(shared, values_a, values_b):
            if value_a != value_b:
                disagreements.append(
                    {args.key: key, "field": field, "annotator_a": value_a, "annotator_b": value_b}
                )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "annotator_a": str(args.annotator_a),
        "annotator_b": str(args.annotator_b),
        "shared_rows": len(shared),
        "only_a": only_a,
        "only_b": only_b,
        "fields": fields,
        "disagreement_count": len(disagreements),
    }
    json_path = args.output_dir / "annotation_agreement.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    csv_path = args.output_dir / "annotation_disagreements.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[args.key, "field", "annotator_a", "annotator_b"])
        writer.writeheader()
        writer.writerows(disagreements)
    print(json.dumps({"report": str(json_path), "disagreements": str(csv_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
