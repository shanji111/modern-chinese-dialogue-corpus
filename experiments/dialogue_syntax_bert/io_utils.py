"""Filesystem, CSV, JSON, and SQLite helpers for offline experiments."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from urllib.parse import quote


EXPERIMENT_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = EXPERIMENT_DIR / "artifacts"

HUMAN_LABEL_COLUMNS = {
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
}


def ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def artifact_path(*parts: str) -> Path:
    return ARTIFACTS_DIR.joinpath(*parts)


def has_human_annotation_values(path: str | Path) -> bool:
    target = Path(path)
    if not target.exists():
        return False
    if target.suffix.lower() == ".csv":
        try:
            with target.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                annotation_columns = HUMAN_LABEL_COLUMNS & set(reader.fieldnames or [])
                return any(
                    (row.get(column) or "").strip()
                    for row in reader
                    for column in annotation_columns
                )
        except UnicodeDecodeError:
            return False
    if target.suffix.lower() == ".jsonl":
        try:
            with target.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    if any(str(row.get(column, "")).strip() for column in HUMAN_LABEL_COLUMNS):
                        return True
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
    return False


def ensure_can_write(
    path: str | Path,
    *,
    overwrite: bool = False,
    force_overwrite_labels: bool = False,
) -> Path:
    target = ensure_parent(Path(path))
    artifacts_root = ARTIFACTS_DIR.resolve()
    try:
        target.resolve().relative_to(artifacts_root)
    except ValueError as exc:
        raise ValueError(f"Generated artifacts must be written under {artifacts_root}: {target}") from exc
    if not target.exists():
        return target
    if not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing artifact: {target}")
    if has_human_annotation_values(target) and not force_overwrite_labels:
        raise RuntimeError(
            f"Refusing to overwrite artifact containing human annotation values: {target}"
        )
    return target


def connect_sqlite_readonly(db_path: str | Path) -> sqlite3.Connection:
    resolved = Path(db_path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Corpus database not found: {resolved}")
    uri_path = quote(str(resolved).replace("\\", "/"), safe="/:")
    conn = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def write_csv(
    path: str | Path,
    rows: list[dict[str, object]],
    fieldnames: list[str],
    *,
    overwrite: bool = False,
    force_overwrite_labels: bool = False,
) -> Path:
    output_path = ensure_can_write(path, overwrite=overwrite, force_overwrite_labels=force_overwrite_labels)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: str | Path, payload: object, *, overwrite: bool = False) -> Path:
    output_path = ensure_can_write(path, overwrite=overwrite)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return output_path


def write_jsonl(
    path: str | Path,
    rows: list[dict[str, object]],
    *,
    overwrite: bool = False,
    force_overwrite_labels: bool = False,
) -> Path:
    output_path = ensure_can_write(path, overwrite=overwrite, force_overwrite_labels=force_overwrite_labels)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")
    return output_path


def write_text(path: str | Path, text: str, *, overwrite: bool = False) -> Path:
    output_path = ensure_can_write(path, overwrite=overwrite)
    output_path.write_text(text, encoding="utf-8")
    return output_path
