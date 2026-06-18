"""Split an unblinded pilot CSV into blind annotation and evaluation key CSVs."""

from __future__ import annotations

import argparse
from pathlib import Path

from io_utils import artifact_path, read_csv, write_csv
from sample_pairs import FLAG_COLUMNS, SCHEMA_VERSION, conversation_group_key, normalized_pair_hash


BLIND_COLUMNS = [
    "annotation_id",
    "pair_id",
    "source",
    "dataset_name",
    "speaker_a",
    "turn_a",
    "speaker_b",
    "turn_b",
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

KEY_COLUMNS = [
    "annotation_id",
    "pair_id",
    "conversation_key",
    "entry_id",
    "sample_stratum",
    "sampling_seed",
    "schema_version",
    "normalized_pair_hash",
    "conversation_group_key",
    "split_group_key",
    "rule_summary",
    "rule_any_positive",
    *FLAG_COLUMNS,
    "shared_terms",
    "markers",
]

FORBIDDEN_BLIND_COLUMNS = {
    "sample_layer",
    "sample_stratum",
    "sampling_seed",
    "schema_version",
    "normalized_pair_hash",
    "conversation_group_key",
    "rule_summary",
    "rule_any_positive",
    "rule_reproduction",
    "rule_parallelism",
    "rule_selective_reuse",
    "rule_repair",
    "rule_contrast",
    "rule_question_response",
    "rule_evidence_terms",
    "rule_markers",
    "shared_terms",
    "markers",
    *FLAG_COLUMNS,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-csv",
        default=str(artifact_path("pilot_50", "pilot_50.csv")),
        help="Unblinded pilot CSV produced by sample_pairs.py.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(artifact_path("pilot_50")),
        help="Directory for blind annotation and evaluation key CSVs.",
    )
    parser.add_argument("--prefix", default="P50", help="Annotation ID prefix.")
    parser.add_argument("--sampling-seed", default="20260616")
    parser.add_argument("--schema-version", default=SCHEMA_VERSION)
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting existing output CSVs.")
    parser.add_argument(
        "--force-overwrite-labels",
        action="store_true",
        help="Also allow overwriting existing CSVs that contain human annotation values.",
    )
    return parser.parse_args()


def annotation_id(prefix: str, index: int) -> str:
    return f"{prefix}-{index:04d}"


def source_value(row: dict[str, str], *columns: str) -> str:
    for column in columns:
        value = row.get(column, "")
        if value != "":
            return value
    return ""


def build_rows(rows: list[dict[str, str]], args: argparse.Namespace) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    blind_rows = []
    key_rows = []
    for index, row in enumerate(rows, 1):
        ann_id = annotation_id(args.prefix, index)
        dataset_name = source_value(row, "dataset_name", "dataset")
        conversation_key = source_value(row, "conversation_key", "conversation_id")
        pair_hash = source_value(row, "normalized_pair_hash") or normalized_pair_hash(row.get("turn_a"), row.get("turn_b"))
        conv_group = source_value(row, "conversation_group_key") or conversation_group_key(dataset_name, conversation_key)
        blind_rows.append({
            "annotation_id": ann_id,
            "pair_id": row.get("pair_id", ""),
            "source": row.get("source", ""),
            "dataset_name": dataset_name,
            "speaker_a": row.get("speaker_a", ""),
            "turn_a": row.get("turn_a", ""),
            "speaker_b": row.get("speaker_b", ""),
            "turn_b": row.get("turn_b", ""),
            "resonance_present": "",
            "label_reproduction": "",
            "label_parallelism": "",
            "label_selective_reuse": "",
            "label_repair": "",
            "label_contrast": "",
            "label_analogy_candidate": "",
            "evidence_span_a": "",
            "evidence_span_b": "",
            "annotator_note": "",
            "uncertainty_reason": "",
        })
        key_rows.append({
            "annotation_id": ann_id,
            "pair_id": row.get("pair_id", ""),
            "conversation_key": conversation_key,
            "entry_id": row.get("entry_id", ""),
            "sample_stratum": source_value(row, "sample_stratum", "sample_layer"),
            "sampling_seed": source_value(row, "sampling_seed") or str(args.sampling_seed),
            "schema_version": source_value(row, "schema_version") or args.schema_version,
            "normalized_pair_hash": pair_hash,
            "conversation_group_key": conv_group,
            "rule_summary": row.get("rule_summary", ""),
            "rule_any_positive": row.get("rule_any_positive", ""),
            **{flag: row.get(flag, "") for flag in FLAG_COLUMNS},
            "shared_terms": source_value(row, "shared_terms", "rule_evidence_terms"),
            "markers": source_value(row, "markers", "rule_markers"),
        })
    return blind_rows, key_rows


def assert_blind_has_no_forbidden_columns(blind_rows: list[dict[str, str]]) -> None:
    if not blind_rows:
        return
    leaked = sorted(FORBIDDEN_BLIND_COLUMNS & set(blind_rows[0].keys()))
    if leaked:
        raise RuntimeError(f"Blind annotation columns leak rule/sampling fields: {leaked}")


def main() -> None:
    args = parse_args()
    rows = read_csv(args.input_csv)
    blind_rows, key_rows = build_rows(rows, args)
    assert_blind_has_no_forbidden_columns(blind_rows)
    output_dir = Path(args.output_dir)
    blind_path = write_csv(
        output_dir / "pilot_50_annotation_blind.csv",
        blind_rows,
        BLIND_COLUMNS,
        overwrite=args.overwrite,
        force_overwrite_labels=args.force_overwrite_labels,
    )
    key_path = write_csv(
        output_dir / "pilot_50_evaluation_key.csv",
        key_rows,
        KEY_COLUMNS,
        overwrite=args.overwrite,
        force_overwrite_labels=args.force_overwrite_labels,
    )
    print(f"input_rows={len(rows)}")
    print(f"wrote_blind={blind_path}")
    print(f"wrote_key={key_path}")


if __name__ == "__main__":
    main()
