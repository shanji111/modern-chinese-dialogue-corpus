from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

from database import DATABASE_BACKEND, get_db_connection
from db_utils import compute_content_hash, parse_year, utc_timestamp


DB_FILE = Path("corpus.db")
REQUIRED_FIELDS = ("title", "content", "source")
OPTIONAL_FIELDS = (
    "year",
    "category",
    "dataset_name",
    "source_url",
    "crawl_source",
    "crawl_date",
    "license_note",
)
METADATA_FIELDS = ("source_url", "crawl_source", "crawl_date", "license_note")
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
POSTGRES_EXTRA_FIELDS = ("search_text",)


def clean_value(value: str | None) -> str:
    return (value or "").strip()


def placeholder() -> str:
    return "%s" if DATABASE_BACKEND == "postgres" else "?"


def fetch_one_value(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return next(iter(row.values()))
    try:
        return row[0]
    except KeyError:
        return next(iter(dict(row).values()))


def get_columns(conn) -> set[str]:
    if DATABASE_BACKEND == "postgres":
        rows = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
            """,
            ("corpus_entries",),
        ).fetchall()
        return {fetch_one_value(row) for row in rows}
    return {item[1] for item in conn.execute("PRAGMA table_info(corpus_entries)").fetchall()}


def ensure_ready(conn) -> None:
    marker = placeholder()
    if DATABASE_BACKEND == "postgres":
        row = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name = %s
            """,
            ("corpus_entries",),
        ).fetchone()
    else:
        row = conn.execute(
            f"SELECT name FROM sqlite_master WHERE type = 'table' AND name = {marker}",
            ("corpus_entries",),
        ).fetchone()
    if row is None:
        raise RuntimeError("数据库中未找到 corpus_entries 表，请先运行 init_db.py 初始化数据库。")

    columns = get_columns(conn)
    missing = [field for field in SCHEMA_FIELDS if field not in columns]
    if missing:
        raise RuntimeError(f"数据库缺少字段: {', '.join(missing)}。请先运行 migrate_db.py。")


def is_duplicate(conn, content_hash: str) -> bool:
    marker = placeholder()
    row = conn.execute(
        f"SELECT id FROM corpus_entries WHERE content_hash = {marker} LIMIT 1",
        (content_hash,),
    ).fetchone()
    return row is not None


def build_search_text(*values: str | None) -> str:
    return " ".join((value or "").strip() for value in values if (value or "").strip())


def build_insert_columns(available_metadata_fields: list[str], include_search_text: bool) -> list[str]:
    insert_columns = [
        "title",
        "content",
        "source",
        "year",
        "category",
        "dataset_name",
        "created_at",
        "import_batch",
        "content_hash",
    ]
    insert_columns.extend(available_metadata_fields)
    if include_search_text:
        insert_columns.append("search_text")
    return insert_columns


def build_insert_sql(insert_columns: list[str], marker: str) -> str:
    column_sql = ", ".join(insert_columns)
    placeholder_sql = ", ".join(marker for _ in insert_columns)
    return f"INSERT INTO corpus_entries ({column_sql}) VALUES ({placeholder_sql})"


def prepare_csv_rows(
    csv_path: Path,
    available_metadata_fields: list[str],
    include_search_text: bool,
    created_at: str,
    import_batch: str,
) -> tuple[list[dict[str, object]], int]:
    failed_count = 0
    prepared_rows: list[dict[str, object]] = []

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
            values: dict[str, object] = {
                "title": title,
                "content": content,
                "source": source,
                "year": year,
                "category": category,
                "dataset_name": dataset_name,
                "created_at": created_at,
                "import_batch": import_batch,
                "content_hash": content_hash,
            }
            for field in available_metadata_fields:
                values[field] = clean_value(row.get(field))
            if include_search_text:
                values["search_text"] = build_search_text(title, content)
            prepared_rows.append(values)

    return prepared_rows, failed_count


def postgres_existing_hashes(conn, content_hashes: list[str]) -> set[str]:
    if not content_hashes:
        return set()
    rows = conn.execute(
        """
        SELECT content_hash
        FROM corpus_entries
        WHERE content_hash = ANY(%s)
        """,
        (content_hashes,),
    ).fetchall()
    return {fetch_one_value(row) for row in rows}


def import_csv_postgres(
    conn,
    csv_path: Path,
    available_metadata_fields: list[str],
    include_search_text: bool,
    created_at: str,
    import_batch: str,
    dry_run: bool,
    insert_batch_size: int,
) -> tuple[int, int, int]:
    prepared_rows, failed_count = prepare_csv_rows(
        csv_path,
        available_metadata_fields,
        include_search_text,
        created_at,
        import_batch,
    )

    unique_rows: list[dict[str, object]] = []
    csv_seen_hashes: set[str] = set()
    duplicate_count = 0
    for row in prepared_rows:
        content_hash = str(row["content_hash"])
        if content_hash in csv_seen_hashes:
            duplicate_count += 1
            continue
        csv_seen_hashes.add(content_hash)
        unique_rows.append(row)

    existing_hashes = postgres_existing_hashes(conn, list(csv_seen_hashes))
    insert_rows = [
        row
        for row in unique_rows
        if row["content_hash"] not in existing_hashes
    ]
    duplicate_count += len(unique_rows) - len(insert_rows)

    if dry_run:
        return len(insert_rows), failed_count, duplicate_count

    insert_columns = build_insert_columns(available_metadata_fields, include_search_text)
    insert_sql = build_insert_sql(insert_columns, "%s")
    success_count = 0
    batch_size = max(1, insert_batch_size)

    with conn.cursor() as cur:
        for start in range(0, len(insert_rows), batch_size):
            batch = insert_rows[start:start + batch_size]
            values = [
                tuple(row[column] for column in insert_columns)
                for row in batch
            ]
            try:
                cur.executemany(insert_sql, values)
                conn.commit()
                success_count += len(values)
            except Exception:
                conn.rollback()
                for value in values:
                    try:
                        cur.execute(insert_sql, value)
                        conn.commit()
                        success_count += 1
                    except Exception:
                        conn.rollback()
                        failed_count += 1

    return success_count, failed_count, duplicate_count


def import_csv(
    csv_path: Path,
    db_path: Path,
    import_batch: str,
    dry_run: bool = False,
    no_rollback_journal: bool = False,
    insert_batch_size: int = 1000,
) -> tuple[int, int, int]:
    if not csv_path.exists():
        raise FileNotFoundError(f"找不到 CSV 文件: {csv_path}")
    if DATABASE_BACKEND == "sqlite" and not db_path.exists():
        raise FileNotFoundError(f"找不到 SQLite 数据库: {db_path}")

    success_count = 0
    failed_count = 0
    duplicate_count = 0
    created_at = utc_timestamp()

    conn = sqlite3.connect(db_path) if DATABASE_BACKEND == "sqlite" else get_db_connection()
    try:
        if DATABASE_BACKEND == "sqlite" and no_rollback_journal:
            conn.execute("PRAGMA journal_mode = OFF")
            conn.execute("PRAGMA synchronous = OFF")
        ensure_ready(conn)
        columns = get_columns(conn)
        available_metadata_fields = [field for field in METADATA_FIELDS if field in columns]
        include_search_text = DATABASE_BACKEND == "postgres" and "search_text" in columns
        marker = placeholder()
        if DATABASE_BACKEND == "postgres":
            return import_csv_postgres(
                conn,
                csv_path,
                available_metadata_fields,
                include_search_text,
                created_at,
                import_batch,
                dry_run,
                insert_batch_size,
            )

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
                metadata_values = {
                    field: clean_value(row.get(field))
                    for field in available_metadata_fields
                }

                if not title or not content or not source:
                    failed_count += 1
                    continue

                content_hash = compute_content_hash(content)
                if is_duplicate(conn, content_hash):
                    duplicate_count += 1
                    continue

                if not dry_run:
                    insert_columns = build_insert_columns(available_metadata_fields, include_search_text)
                    insert_params = [
                        title,
                        content,
                        source,
                        year,
                        category,
                        dataset_name,
                        created_at,
                        import_batch,
                        content_hash,
                    ]
                    metadata_params: list[str] = []
                    if available_metadata_fields:
                        metadata_params = [metadata_values[field] for field in available_metadata_fields]
                        insert_params.extend(metadata_params)
                    if include_search_text:
                        insert_params.append(build_search_text(title, content))

                    insert_sql = build_insert_sql(insert_columns, marker)

                    conn.execute(
                        insert_sql,
                        tuple(insert_params),
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
    parser.add_argument(
        "--no-rollback-journal",
        action="store_true",
        help="SQLite 专用：禁用 rollback journal；仅建议在已备份且本机 journal I/O 异常时使用",
    )
    parser.add_argument("--insert-batch-size", type=int, default=1000, help="PostgreSQL batch insert size")
    args = parser.parse_args()

    success_count, failed_count, duplicate_count = import_csv(
        args.csv,
        args.db,
        args.batch,
        args.dry_run,
        args.no_rollback_journal,
        args.insert_batch_size,
    )

    action = "预检查完成" if args.dry_run else "批量导入完成"
    print(action)
    print(f"成功导入 {success_count} 条")
    print(f"重复跳过 {duplicate_count} 条")
    print(f"失败 {failed_count} 条")


if __name__ == "__main__":
    main()
