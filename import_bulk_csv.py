from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

from db_utils import compute_content_hash, parse_year, utc_timestamp


DB_FILE = Path("corpus.db")
REQUIRED_FIELDS = ("title", "content", "source")
OPTIONAL_FIELDS = ("year", "category", "dataset_name")
SCHEMA_FIELDS = (
    "title",
    "content",
    "source",
    "year",
    "category",
    "dataset_name",
    "created_at",
    "import_batch",
    "content_hash",
)


def clean_value(value: str | None) -> str:
    return (value or "").strip()


def ensure_ready(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("corpus_entries",),
    ).fetchone()
    if row is None:
        raise RuntimeError("数据库中未找到 corpus_entries 表，请先运行 init_db.py 初始化数据库。")

    columns = {item[1] for item in conn.execute("PRAGMA table_info(corpus_entries)").fetchall()}
    missing = [field for field in SCHEMA_FIELDS if field not in columns]
    if missing:
        raise RuntimeError(f"数据库缺少字段: {', '.join(missing)}。请先运行 migrate_db.py。")


def is_duplicate(conn: sqlite3.Connection, content_hash: str) -> bool:
    row = conn.execute(
        "SELECT id FROM corpus_entries WHERE content_hash = ? LIMIT 1",
        (content_hash,),
    ).fetchone()
    return row is not None


def import_csv(csv_path: Path, db_path: Path, import_batch: str, dry_run: bool = False) -> tuple[int, int, int]:
    if not csv_path.exists():
        raise FileNotFoundError(f"找不到 CSV 文件: {csv_path}")
    if not db_path.exists():
        raise FileNotFoundError(f"找不到 SQLite 数据库: {db_path}")

    success_count = 0
    failed_count = 0
    duplicate_count = 0
    created_at = utc_timestamp()

    conn = sqlite3.connect(db_path)
    try:
        ensure_ready(conn)
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise RuntimeError("CSV 文件为空或缺少表头。")

            missing_headers = [field for field in REQUIRED_FIELDS if field not in reader.fieldnames]
            if missing_headers:
                raise RuntimeError(f"CSV 缺少必要表头: {', '.join(missing_headers)}")

            for row in reader:
                title = clean_value(row.get("title"))
                content = clean_value(row.get("content"))
                source = clean_value(row.get("source"))
                year = parse_year(row.get("year"))
                category = clean_value(row.get("category"))
                dataset_name = clean_value(row.get("dataset_name")) or category or source

                if not title or not content or not source:
                    failed_count += 1
                    continue

                content_hash = compute_content_hash(content)
                if is_duplicate(conn, content_hash):
                    duplicate_count += 1
                    continue

                if not dry_run:
                    conn.execute(
                        """
                        INSERT INTO corpus_entries (
                            title, content, source, year, category,
                            dataset_name, created_at, import_batch, content_hash
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            title,
                            content,
                            source,
                            year,
                            category,
                            dataset_name,
                            created_at,
                            import_batch,
                            content_hash,
                        ),
                    )
                success_count += 1

        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return success_count, failed_count, duplicate_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk import normalized corpus CSV into SQLite.")
    parser.add_argument("csv", type=Path, help="统一格式 CSV 文件路径")
    parser.add_argument("--db", type=Path, default=DB_FILE, help="SQLite 数据库路径")
    parser.add_argument("--batch", required=True, help="本次导入批次名称，例如 preview_20260415")
    parser.add_argument("--dry-run", action="store_true", help="只检查并统计，不写入数据库")
    args = parser.parse_args()

    success_count, failed_count, duplicate_count = import_csv(
        args.csv,
        args.db,
        args.batch,
        args.dry_run,
    )

    action = "预检查完成" if args.dry_run else "批量导入完成"
    print(action)
    print(f"成功导入 {success_count} 条")
    print(f"重复跳过 {duplicate_count} 条")
    print(f"失败 {failed_count} 条")


if __name__ == "__main__":
    main()
