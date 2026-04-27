from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from db_utils import compute_content_hash, create_indexes, utc_timestamp


DB_FILE = Path("corpus.db")

NEW_COLUMNS = {
    "dataset_name": "TEXT",
    "created_at": "TEXT",
    "import_batch": "TEXT",
    "content_hash": "TEXT",
}


def get_columns(conn: sqlite3.Connection) -> set[str]:
    return {row[1] for row in conn.execute("PRAGMA table_info(corpus_entries)").fetchall()}


def ensure_table_exists(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("corpus_entries",),
    ).fetchone()
    if row is None:
        raise RuntimeError("数据库中未找到 corpus_entries 表，请先运行 init_db.py 初始化数据库。")


def migrate(db_path: Path) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"找不到 SQLite 数据库: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_table_exists(conn)

        existing_columns = get_columns(conn)
        for column, column_type in NEW_COLUMNS.items():
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE corpus_entries ADD COLUMN {column} {column_type}")
                print(f"已新增字段: {column}")

        timestamp = utc_timestamp()
        conn.execute(
            """
            UPDATE corpus_entries
            SET created_at = ?
            WHERE created_at IS NULL OR TRIM(created_at) = ''
            """,
            (timestamp,),
        )
        conn.execute(
            """
            UPDATE corpus_entries
            SET import_batch = 'legacy'
            WHERE import_batch IS NULL OR TRIM(import_batch) = ''
            """
        )
        conn.execute(
            """
            UPDATE corpus_entries
            SET dataset_name = category
            WHERE (dataset_name IS NULL OR TRIM(dataset_name) = '')
              AND category IS NOT NULL
              AND TRIM(category) != ''
            """
        )

        rows = conn.execute(
            """
            SELECT id, content FROM corpus_entries
            WHERE content_hash IS NULL OR TRIM(content_hash) = ''
            """
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE corpus_entries SET content_hash = ? WHERE id = ?",
                (compute_content_hash(row["content"]), row["id"]),
            )

        create_indexes(conn)
        conn.commit()
        print(f"迁移完成，补全 content_hash {len(rows)} 条，并已创建必要索引。")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate corpus.db for larger corpus imports.")
    parser.add_argument("--db", type=Path, default=DB_FILE, help="SQLite 数据库路径")
    args = parser.parse_args()
    migrate(args.db)


if __name__ == "__main__":
    main()
