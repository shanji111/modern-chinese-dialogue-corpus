from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path


DB_FILE = Path("corpus.db")
CSV_FILE = Path("talkdata") / "import_ready" / "preview_import.csv"
REQUIRED_FIELDS = ("title", "content", "source")
ALL_FIELDS = ("title", "content", "source", "year", "category")


def clean_value(value: str | None) -> str:
    return (value or "").strip()


def parse_year(value: str) -> int | None:
    value = clean_value(value)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def ensure_table_exists(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("corpus_entries",),
    ).fetchone()
    if row is None:
        raise RuntimeError("数据库中未找到 corpus_entries 表，请先确认数据库已初始化。")


def import_csv(csv_path: Path, db_path: Path, dry_run: bool = False) -> tuple[int, int]:
    if not csv_path.exists():
        raise FileNotFoundError(f"找不到 CSV 文件: {csv_path}")
    if not db_path.exists():
        raise FileNotFoundError(f"找不到 SQLite 数据库: {db_path}")

    success_count = 0
    failed_count = 0

    conn = sqlite3.connect(db_path)
    try:
        ensure_table_exists(conn)
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise RuntimeError("CSV 文件为空或缺少表头。")

            missing_headers = [field for field in ALL_FIELDS if field not in reader.fieldnames]
            if missing_headers:
                raise RuntimeError(f"CSV 缺少必要表头: {', '.join(missing_headers)}")

            for row in reader:
                title = clean_value(row.get("title"))
                content = clean_value(row.get("content"))
                source = clean_value(row.get("source"))
                year = parse_year(row.get("year", ""))
                category = clean_value(row.get("category"))

                if not title or not content or not source:
                    failed_count += 1
                    continue

                if not dry_run:
                    conn.execute(
                        """
                        INSERT INTO corpus_entries (title, content, source, year, category)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (title, content, source, year, category),
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

    return success_count, failed_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Import preview_import.csv into corpus_entries.")
    parser.add_argument("--csv", type=Path, default=CSV_FILE, help="CSV 文件路径")
    parser.add_argument("--db", type=Path, default=DB_FILE, help="SQLite 数据库路径")
    parser.add_argument("--dry-run", action="store_true", help="只检查并统计，不写入数据库")
    args = parser.parse_args()

    success_count, failed_count = import_csv(args.csv, args.db, args.dry_run)
    action = "预检查完成" if args.dry_run else "导入完成"
    print(action)
    print(f"成功导入 {success_count} 条")
    print(f"失败 {failed_count} 条")


if __name__ == "__main__":
    main()
