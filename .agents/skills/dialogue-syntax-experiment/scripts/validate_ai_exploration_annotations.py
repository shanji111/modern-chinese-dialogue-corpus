"""Validate provenance and schema for an AI exploratory annotation run."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


MECHANISM_FIELDS = (
    "label_reproduction",
    "label_parallelism",
    "label_selective_reuse",
    "label_repair",
    "label_contrast",
    "label_analogy_candidate",
)
ANNOTATION_FIELDS = (
    "resonance_present",
    *MECHANISM_FIELDS,
    "evidence_span_a",
    "evidence_span_b",
    "annotator_note",
    "uncertainty_reason",
)
PROVENANCE_FIELDS = (
    "ai_model",
    "ai_prompt_version",
    "ai_run_id",
    "ai_confidence",
    "ai_review_status",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--allow-subset", action="store_true")
    args = parser.parse_args()

    packet = read_csv(args.packet)
    annotations = read_csv(args.annotations)
    packet_by_id = {row.get("annotation_id", ""): row for row in packet}
    annotation_ids = [row.get("annotation_id", "") for row in annotations]
    errors: list[dict[str, Any]] = []

    if len(packet_by_id) != len(packet):
        errors.append({"type": "packet_duplicate_annotation_id"})
    if len(set(annotation_ids)) != len(annotation_ids):
        errors.append({"type": "annotation_duplicate_annotation_id"})
    packet_ids = set(packet_by_id)
    annotation_id_set = set(annotation_ids)
    missing = sorted(packet_ids - annotation_id_set)
    extra = sorted(annotation_id_set - packet_ids)
    if (missing and not args.allow_subset) or extra:
        errors.append({"type": "annotation_id_mismatch", "missing": missing[:20], "extra": extra[:20]})

    required = ("annotation_id", *ANNOTATION_FIELDS, *PROVENANCE_FIELDS)
    allowed_resonance = {"yes", "no", "uncertain"}
    allowed_mechanism = {"1", "0", "?"}
    for row in annotations:
        annotation_id = row.get("annotation_id", "")
        packet_row = packet_by_id.get(annotation_id)
        missing_fields = [field for field in required if field not in row]
        if missing_fields:
            errors.append({"type": "missing_columns", "annotation_id": annotation_id, "fields": missing_fields})
            continue
        if row["resonance_present"].strip().lower() not in allowed_resonance:
            errors.append({"type": "invalid_resonance_label", "annotation_id": annotation_id})
        for field in MECHANISM_FIELDS:
            if row[field].strip() not in allowed_mechanism:
                errors.append({"type": "invalid_mechanism_label", "annotation_id": annotation_id, "field": field})
        try:
            confidence = float(row["ai_confidence"])
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError
        except ValueError:
            errors.append({"type": "invalid_ai_confidence", "annotation_id": annotation_id})
        if not row["ai_model"].strip() or not row["ai_prompt_version"].strip() or not row["ai_run_id"].strip():
            errors.append({"type": "incomplete_ai_provenance", "annotation_id": annotation_id})
        if not row["ai_review_status"].strip().startswith("ai_"):
            errors.append({"type": "invalid_ai_review_status", "annotation_id": annotation_id})
        if packet_row is not None:
            for span_field, turn_field in (("evidence_span_a", "turn_a"), ("evidence_span_b", "turn_b")):
                span = row[span_field].strip()
                if span and span not in packet_row.get(turn_field, ""):
                    errors.append({"type": "evidence_span_not_substring", "annotation_id": annotation_id, "field": span_field})

    report = {
        "status": "pass" if not errors else "fail",
        "packet": str(args.packet),
        "annotations": str(args.annotations),
        "packet_rows": len(packet),
        "annotation_rows": len(annotations),
        "allow_subset": args.allow_subset,
        "errors": errors,
    }
    if args.report.exists():
        raise FileExistsError(f"Refusing to overwrite: {args.report}")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
