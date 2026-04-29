from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

from db_utils import compute_content_hash, create_indexes, utc_timestamp


DB_FILE = Path("corpus.db")
NEW_COLUMNS = {
    "source_url": "TEXT",
    "crawl_source": "TEXT",
    "crawl_date": "TEXT",
    "license_note": "TEXT",
}
METADATA_FIELDS = ("source_url", "crawl_source", "crawl_date", "license_note")


def clean_value(value: str | None) -> str:
    return (value or "").strip()


def get_columns(conn: sqlite3.Connection) -> set[str]:
    return {row[1] for row in conn.execute("PRAGMA table_info(corpus_entries)").fetchall()}


def ensure_table_exists(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("corpus_entries",),
    ).fetchone()
    if row is None:
        raise RuntimeError("数据库中未找到 corpus_entries 表，请先运行 init_db.py 初始化数据库。")


def add_missing_columns(conn: sqlite3.Connection) -> list[str]:
    existing_columns = get_columns(conn)
    added: list[str] = []
    for column, column_type in NEW_COLUMNS.items():
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE corpus_entries ADD COLUMN {column} {column_type}")
            added.append(column)
    return added


def backfill_defaults(conn: sqlite3.Connection) -> None:
    today = utc_timestamp()[:10]
    conn.execute(
        """
        UPDATE corpus_entries
        SET crawl_source = COALESCE(NULLIF(TRIM(crawl_source), ''), dataset_name, category),
            crawl_date = COALESCE(NULLIF(TRIM(crawl_date), ''), ?),
            license_note = COALESCE(
                NULLIF(TRIM(license_note), ''),
                '公开网页文字片段，仅用于语料检索展示；上线展示短片段，并提供原文链接，版权归原网站及相关权利人所有。'
            )
        WHERE source = '访谈语料'
        """,
        (today,),
    )


def backfill_from_csv(conn: sqlite3.Connection, csv_path: Path) -> int:
    if not csv_path:
        return 0
    if not csv_path.exists():
        raise FileNotFoundError(f"找不到元数据 CSV: {csv_path}")

    updated = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return 0
        if "content" not in reader.fieldnames:
            raise RuntimeError("元数据 CSV 缺少 content 字段，无法按 content_hash 回填。")

        for row in reader:
            content = clean_value(row.get("content"))
            if not content:
                continue
            values = {field: clean_value(row.get(field)) for field in METADATA_FIELDS}
            if not any(values.values()):
                continue
            cursor = conn.execute(
                """
                UPDATE corpus_entries
                SET source_url = COALESCE(NULLIF(?, ''), source_url),
                    crawl_source = COALESCE(NULLIF(?, ''), crawl_source),
                    crawl_date = COALESCE(NULLIF(?, ''), crawl_date),
                    license_note = COALESCE(NULLIF(?, ''), license_note)
                WHERE content_hash = ?
                  AND source = '访谈语料'
                """,
                (
                    values["source_url"],
                    values["crawl_source"],
                    values["crawl_date"],
                    values["license_note"],
                    compute_content_hash(content),
                ),
            )
            updated += max(cursor.rowcount, 0)
    return updated


def migrate(db_path: Path, metadata_csv: Path | None = None, no_rollback_journal: bool = False) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"找不到 SQLite 数据库: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        if no_rollback_journal:
            conn.execute("PRAGMA journal_mode = OFF")
            conn.execute("PRAGMA synchronous = OFF")
        ensure_table_exists(conn)
        added = add_missing_columns(conn)
        backfill_defaults(conn)
        csv_updates = backfill_from_csv(conn, metadata_csv) if metadata_csv else 0
        create_indexes(conn)
        conn.commit()

        interview_total = conn.execute(
            "SELECT COUNT(*) FROM corpus_entries WHERE source = '访谈语料'"
        ).fetchone()[0]
        with_url = conn.execute(
            """
            SELECT COUNT(*)
            FROM corpus_entries
            WHERE source = '访谈语料'
              AND source_url IS NOT NULL
              AND TRIM(source_url) != ''
            """
        ).fetchone()[0]

        print("访谈语料元数据迁移完成")
        print(f"- 新增字段: {', '.join(added) if added else '无'}")
        print(f"- CSV 回填尝试更新: {csv_updates}")
        print(f"- 访谈语料总数: {interview_total}")
        print(f"- 已有原文链接: {with_url}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Add and backfill public interview metadata fields.")
    parser.add_argument("--db", type=Path, default=DB_FILE, help="SQLite 数据库路径")
    parser.add_argument("--metadata-csv", type=Path, default=None, help="可选：含 source_url 等字段的导入 CSV")
    parser.add_argument(
        "--no-rollback-journal",
        action="store_true",
        help="禁用 SQLite rollback journal；仅建议在已备份数据库且本机 journal I/O 异常时使用",
    )
    args = parser.parse_args()
    migrate(args.db, args.metadata_csv, args.no_rollback_journal)


if __name__ == "__main__":
    main()
