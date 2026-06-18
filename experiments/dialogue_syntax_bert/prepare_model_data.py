"""Convert annotation CSV rows into train/dev/test JSONL files."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from io_utils import artifact_path, read_csv, write_json, write_jsonl
from labels import ALL_LABEL_KEYS, POSITIVE_LABEL_KEYS, human_labels_from_row, parse_bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", required=True, help="Filled annotation CSV.")
    parser.add_argument(
        "--output-dir",
        default=str(artifact_path("model_data")),
        help="Directory for train/dev/test JSONL files.",
    )
    parser.add_argument("--dev-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=20260616)
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting existing model-data artifacts.")
    parser.add_argument(
        "--force-overwrite-labels",
        action="store_true",
        help="Also allow overwriting existing JSONL artifacts that contain human annotation values.",
    )
    return parser.parse_args()


def has_any_human_label(row: dict[str, object]) -> bool:
    return any(parse_bool(row.get(f"label_{label_key}")) for label_key in ALL_LABEL_KEYS)


def row_to_record(row: dict[str, str]) -> dict[str, object]:
    human = human_labels_from_row(row)
    return {
        "pair_id": row.get("pair_id", ""),
        "text_a": row.get("text_a", ""),
        "text_b": row.get("text_b", ""),
        "source": row.get("source", ""),
        "category": row.get("category", ""),
        "dataset_name": row.get("dataset_name", ""),
        "label_keys": list(POSITIVE_LABEL_KEYS),
        "labels": [1 if human[label_key] else 0 for label_key in POSITIVE_LABEL_KEYS],
        "no_relation": 1 if human["no_relation"] else 0,
    }


def split_records(records: list[dict[str, object]], dev_ratio: float, test_ratio: float, seed: int):
    rng = random.Random(seed)
    shuffled = list(records)
    rng.shuffle(shuffled)
    total = len(shuffled)
    test_count = int(round(total * test_ratio))
    dev_count = int(round(total * dev_ratio))
    test = shuffled[:test_count]
    dev = shuffled[test_count:test_count + dev_count]
    train = shuffled[test_count + dev_count:]
    return train, dev, test


def main() -> None:
    args = parse_args()
    rows = read_csv(args.annotations)
    records = [
        row_to_record(row)
        for row in rows
        if has_any_human_label(row)
    ]
    train, dev, test = split_records(records, args.dev_ratio, args.test_ratio, args.seed)
    output_dir = Path(args.output_dir)
    write_jsonl(output_dir / "all.jsonl", records, overwrite=args.overwrite, force_overwrite_labels=args.force_overwrite_labels)
    write_jsonl(output_dir / "train.jsonl", train, overwrite=args.overwrite, force_overwrite_labels=args.force_overwrite_labels)
    write_jsonl(output_dir / "dev.jsonl", dev, overwrite=args.overwrite, force_overwrite_labels=args.force_overwrite_labels)
    write_jsonl(output_dir / "test.jsonl", test, overwrite=args.overwrite, force_overwrite_labels=args.force_overwrite_labels)
    metadata = {
        "label_keys": list(POSITIVE_LABEL_KEYS),
        "record_count": len(records),
        "train_count": len(train),
        "dev_count": len(dev),
        "test_count": len(test),
        "seed": args.seed,
    }
    metadata_path = write_json(output_dir / "metadata.json", metadata, overwrite=args.overwrite)
    print(f"records={len(records)} train={len(train)} dev={len(dev)} test={len(test)}")
    print(f"wrote_metadata={metadata_path}")


if __name__ == "__main__":
    main()
