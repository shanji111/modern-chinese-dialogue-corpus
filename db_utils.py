from __future__ import annotations

import hashlib
from datetime import datetime, timezone


INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_corpus_source ON corpus_entries (source)",
    "CREATE INDEX IF NOT EXISTS idx_corpus_year ON corpus_entries (year)",
    "CREATE INDEX IF NOT EXISTS idx_corpus_category ON corpus_entries (category)",
    "CREATE INDEX IF NOT EXISTS idx_corpus_dataset_name ON corpus_entries (dataset_name)",
    "CREATE INDEX IF NOT EXISTS idx_corpus_import_batch ON corpus_entries (import_batch)",
    "CREATE INDEX IF NOT EXISTS idx_corpus_content_hash ON corpus_entries (content_hash)",
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def compute_content_hash(content: str) -> str:
    normalized = (content or "").strip().replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def create_indexes(conn) -> None:
    for sql in INDEX_SQL:
        conn.execute(sql)


def parse_year(value: str | int | None) -> int | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None
