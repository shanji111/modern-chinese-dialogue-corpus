from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


DB_FILE = Path("corpus.db")
FTS_TABLE = "corpus_entries_fts"

DROP_FTS_SQL = f"DROP TABLE IF EXISTS {FTS_TABLE}"

CREATE_FTS_SQL = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE}
USING fts5(
    title,
    content,
    current_segment,
    prev_segment,
    next_segment,
    source UNINDEXED,
    category UNINDEXED,
    dataset_name UNINDEXED,
    tokenize='trigram',
    content='corpus_entries',
    content_rowid='id'
)
"""

DROP_TRIGGER_SQL = (
    "DROP TRIGGER IF EXISTS corpus_entries_ai",
    "DROP TRIGGER IF EXISTS corpus_entries_ad",
    "DROP TRIGGER IF EXISTS corpus_entries_au",
)

CREATE_TRIGGER_SQL = (
    f"""
    CREATE TRIGGER corpus_entries_ai AFTER INSERT ON corpus_entries BEGIN
        INSERT INTO {FTS_TABLE} (
            rowid, title, content, current_segment, prev_segment, next_segment,
            source, category, dataset_name
        )
        VALUES (
            new.id, new.title, new.content, new.current_segment, new.prev_segment, new.next_segment,
            new.source, new.category, new.dataset_name
        );
    END
    """,
    f"""
    CREATE TRIGGER corpus_entries_ad AFTER DELETE ON corpus_entries BEGIN
        INSERT INTO {FTS_TABLE}(
            {FTS_TABLE}, rowid, title, content, current_segment, prev_segment, next_segment,
            source, category, dataset_name
        )
        VALUES(
            'delete', old.id, old.title, old.content, old.current_segment, old.prev_segment, old.next_segment,
            old.source, old.category, old.dataset_name
        );
    END
    """,
    f"""
    CREATE TRIGGER corpus_entries_au AFTER UPDATE ON corpus_entries BEGIN
        INSERT INTO {FTS_TABLE}(
            {FTS_TABLE}, rowid, title, content, current_segment, prev_segment, next_segment,
            source, category, dataset_name
        )
        VALUES(
            'delete', old.id, old.title, old.content, old.current_segment, old.prev_segment, old.next_segment,
            old.source, old.category, old.dataset_name
        );
        INSERT INTO {FTS_TABLE} (
            rowid, title, content, current_segment, prev_segment, next_segment,
            source, category, dataset_name
        )
        VALUES (
            new.id, new.title, new.content, new.current_segment, new.prev_segment, new.next_segment,
            new.source, new.category, new.dataset_name
        );
    END
    """,
)


def ensure_fts_ready(conn: sqlite3.Connection) -> None:
    for sql in DROP_TRIGGER_SQL:
        conn.execute(sql)
    conn.execute(DROP_FTS_SQL)
    conn.execute(CREATE_FTS_SQL)
    for sql in CREATE_TRIGGER_SQL:
        conn.execute(sql)


def rebuild_fts(conn: sqlite3.Connection) -> None:
    conn.execute(f"INSERT INTO {FTS_TABLE}({FTS_TABLE}) VALUES('rebuild')")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare FTS5 index table for corpus_entries.")
    parser.add_argument("--db", type=Path, default=DB_FILE, help="SQLite database path")
    parser.add_argument("--no-rebuild", action="store_true", help="Create table/triggers only, skip rebuild")
    args = parser.parse_args()

    if not args.db.exists():
        raise FileNotFoundError(f"找不到数据库: {args.db}")

    conn = sqlite3.connect(args.db)
    try:
        ensure_fts_ready(conn)
        if not args.no_rebuild:
            rebuild_fts(conn)
        conn.commit()

        total = conn.execute("SELECT COUNT(*) FROM corpus_entries").fetchone()[0]
        fts_total = conn.execute(f"SELECT COUNT(*) FROM {FTS_TABLE}").fetchone()[0]
        print("FTS5 准备完成")
        print(f"- 主表 corpus_entries: {total} 条")
        print(f"- FTS 表 {FTS_TABLE}: {fts_total} 条")
        print("- 已创建 INSERT / UPDATE / DELETE 触发器")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
