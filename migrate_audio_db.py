from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


DB_FILE = Path("corpus.db")

NEW_COLUMNS = {
    "audio_file": "TEXT",
    "segment_text": "TEXT",
    "current_segment": "TEXT",
    "prev_segment": "TEXT",
    "next_segment": "TEXT",
    "start_time": "REAL",
    "end_time": "REAL",
    "speaker": "TEXT",
    "conversation_id": "TEXT",
    "segment_index": "INTEGER",
}

INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_corpus_audio_file ON corpus_entries (audio_file)",
    "CREATE INDEX IF NOT EXISTS idx_corpus_conversation_id ON corpus_entries (conversation_id)",
    "CREATE INDEX IF NOT EXISTS idx_corpus_segment_index ON corpus_entries (segment_index)",
)


def migrate(db_path: Path) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"找不到 SQLite 数据库: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("corpus_entries",),
        ).fetchone()
        if exists is None:
            raise RuntimeError("数据库中未找到 corpus_entries 表，请先初始化数据库。")

        columns = {row[1] for row in conn.execute("PRAGMA table_info(corpus_entries)").fetchall()}
        for column, column_type in NEW_COLUMNS.items():
            if column not in columns:
                conn.execute(f"ALTER TABLE corpus_entries ADD COLUMN {column} {column_type}")
                print(f"已新增字段: {column}")

        for sql in INDEX_SQL:
            conn.execute(sql)

        conn.commit()
        print("音频检索字段迁移完成，并已创建必要索引。")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Add audio transcript fields to corpus_entries.")
    parser.add_argument("--db", type=Path, default=DB_FILE, help="SQLite 数据库路径")
    args = parser.parse_args()
    migrate(args.db)


if __name__ == "__main__":
    main()
