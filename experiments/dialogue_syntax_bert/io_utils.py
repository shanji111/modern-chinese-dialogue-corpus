"""Filesystem, CSV, JSON, and SQLite helpers for offline experiments."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from urllib.parse import quote


EXPERIMENT_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = EXPERIMENT_DIR / "artifacts"


def ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def artifact_path(*parts: str) -> Path:
    return ARTIFACTS_DIR.joinpath(*parts)


def connect_sqlite_readonly(db_path: str | Path) -> sqlite3.Connection:
    resolved = Path(db_path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Corpus database not found: {resolved}")
    uri_path = quote(str(resolved).replace("\\", "/"), safe="/:")
    conn = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def write_csv(path: str | Path, rows: list[dict[str, object]], fieldnames: list[str]) -> Path:
    output_path = ensure_parent(Path(path))
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: str | Path, payload: object) -> Path:
    output_path = ensure_parent(Path(path))
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return output_path


def write_jsonl(path: str | Path, rows: list[dict[str, object]]) -> Path:
    output_path = ensure_parent(Path(path))
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")
    return output_path

