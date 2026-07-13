"""Freeze network-reply rows as a separate exploratory stress-test packet."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from generate_external_validation_sample_v1 import ANNOTATION_COLUMNS, file_sha256, read_csv, write_csv_new


AI_COLUMNS = (
    "ai_model",
    "ai_prompt_version",
    "ai_run_id",
    "ai_confidence",
    "ai_review_status",
)

PUBLIC_COLUMNS = (
    "annotation_id",
    "pair_id",
    "normalized_pair_hash",
    "conversation_group_key",
    "source",
    "category",
    "dataset_name",
    "speaker_a",
    "turn_a",
    "speaker_b",
    "turn_b",
    "stress_profile",
    *ANNOTATION_COLUMNS,
    *AI_COLUMNS,
)

PRIVATE_COLUMNS = (
    "annotation_id",
    "pair_id",
    "normalized_pair_hash",
    "conversation_group_key",
    "source",
    "category",
    "dataset_name",
    "sample_stratum",
    "confirmatory_partition",
    "turn_a",
    "turn_b",
    "shared_terms",
    "markers",
    "has_lexical_echo",
    "has_pattern_reuse",
    "has_question_response",
    "has_negation_turn",
    "has_repair_repetition",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-master", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--private-output-dir", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=65)
    return parser.parse_args()


def write_json_new(path: Path, payload: object) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    rows = [row for row in read_csv(args.private_master) if "网络" in str(row.get("source") or "")]
    if len(rows) != args.expected_count:
        raise RuntimeError(f"Expected {args.expected_count} network rows, found {len(rows)}")
    rows.sort(key=lambda row: int(row["pair_id"]))

    public_rows = []
    private_rows = []
    for index, row in enumerate(rows, start=1):
        annotation_id = f"NAS1-{index:04d}"
        public = {
            "annotation_id": annotation_id,
            "pair_id": row["pair_id"],
            "normalized_pair_hash": row["normalized_pair_hash"],
            "conversation_group_key": row["conversation_group_key"],
            "source": row["source"],
            "category": row["category"],
            "dataset_name": row["dataset_name"],
            "speaker_a": row.get("speaker_a", ""),
            "turn_a": row["turn_a"],
            "speaker_b": row.get("speaker_b", ""),
            "turn_b": row["turn_b"],
            "stress_profile": "async_network_reply",
        }
        public.update({column: "" for column in (*ANNOTATION_COLUMNS, *AI_COLUMNS)})
        public_rows.append(public)
        private_rows.append(
            {
                "annotation_id": annotation_id,
                **{column: row.get(column, "") for column in PRIVATE_COLUMNS if column != "annotation_id"},
            }
        )

    output_dir = args.output_dir
    private_output_dir = args.private_output_dir
    for directory in (output_dir, private_output_dir):
        if directory.exists() and any(directory.iterdir()):
            raise FileExistsError(f"Refusing to write into non-empty directory: {directory}")
    write_csv_new(output_dir / "network_async_stress_v1_ai_packet.csv", public_rows, PUBLIC_COLUMNS)
    write_csv_new(private_output_dir / "network_async_stress_v1_private_key.csv", private_rows, PRIVATE_COLUMNS)
    public_path = output_dir / "network_async_stress_v1_ai_packet.csv"
    private_path = private_output_dir / "network_async_stress_v1_private_key.csv"
    manifest = {
        "schema_version": 1,
        "stress_test_version": "network_async_stress_v1",
        "source_selection": "65 network rows removed from external_validation_v1 primary selection",
        "count": len(public_rows),
        "profile": "asynchronous_or_threaded_network_reply",
        "exploratory_only": True,
        "not_a_confirmatory_holdout": True,
        "labels_present": False,
        "source_counts": dict(Counter(row["source"] for row in public_rows)),
        "public_file": {"path": public_path.name, "size_bytes": public_path.stat().st_size, "sha256": file_sha256(public_path)},
        "private_key": {
            "path": str(private_path),
            "size_bytes": private_path.stat().st_size,
            "sha256": file_sha256(private_path),
            "must_not_be_shown_to_annotators": True,
        },
        "ai_columns": list(AI_COLUMNS),
    }
    write_json_new(output_dir / "network_async_stress_v1_manifest.json", manifest)
    print(json.dumps({"status": "ok", "count": len(public_rows), "output_dir": str(output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
