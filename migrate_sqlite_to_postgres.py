from __future__ import annotations

import argparse
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = Path(
    os.environ.get("SQLITE_DATABASE_PATH")
    or os.environ.get("DATABASE_PATH")
    or BASE_DIR / "corpus.db"
)
if not DEFAULT_SQLITE_PATH.is_absolute():
    DEFAULT_SQLITE_PATH = BASE_DIR / DEFAULT_SQLITE_PATH

SCHEMA_PATH = BASE_DIR / "schema_postgres.sql"

TABLE_COLUMNS = {
    "corpus_entries": [
        "id",
        "title",
        "content",
        "source",
        "year",
        "category",
        "dataset_name",
        "created_at",
        "import_batch",
        "content_hash",
        "audio_file",
        "segment_text",
        "current_segment",
        "prev_segment",
        "next_segment",
        "start_time",
        "end_time",
        "speaker",
        "conversation_id",
        "segment_index",
    ],
    "corpus_submissions": [
        "id",
        "submitter_name",
        "submitter_email",
        "title",
        "source",
        "category",
        "genre",
        "language",
        "modality",
        "text_content",
        "original_filename",
        "stored_filename",
        "file_path",
        "file_mime_type",
        "file_size",
        "storage_backend",
        "object_key",
        "file_url",
        "file_hash",
        "status",
        "admin_note",
        "created_at",
        "reviewed_at",
        "reviewed_by",
    ],
    "multimodal_entries": [
        "id",
        "submission_id",
        "title",
        "source",
        "category",
        "genre",
        "language",
        "modality",
        "text_content",
        "original_filename",
        "stored_filename",
        "file_path",
        "file_mime_type",
        "file_size",
        "storage_backend",
        "object_key",
        "file_url",
        "file_hash",
        "created_at",
    ],
}


@dataclass
class TableStats:
    read: int = 0
    inserted: int = 0
    skipped: int = 0
    failed: int = 0


MAX_ERROR_SAMPLES = 5
SEARCH_TEXT_COLUMNS = ("title", "content", "speaker", "current_segment", "segment_text")


def connect_sqlite(path: Path, immutable: bool = False) -> sqlite3.Connection:
    if immutable:
        conn = sqlite3.connect(f"file:{path.as_posix()}?immutable=1", uri=True)
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def connect_postgres(database_url: str):
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for PostgreSQL migration.")
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("Install PostgreSQL dependency first: pip install -r requirements.txt") from exc
    return psycopg.connect(database_url)


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def sqlite_table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()}


def sqlite_count(conn: sqlite3.Connection, table_name: str, limit: int | None = None) -> int:
    total = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
    return min(total, limit) if limit else total


def execute_schema(pg_conn, schema_path: Path) -> None:
    sql = schema_path.read_text(encoding="utf-8")
    with pg_conn.cursor() as cur:
        cur.execute(sql)
    pg_conn.commit()


def fetch_sqlite_batches(
    conn: sqlite3.Connection,
    table_name: str,
    columns: list[str],
    batch_size: int,
    limit: int | None,
):
    selected = ", ".join(f'"{column}"' for column in columns)
    remaining = limit
    last_id = 0

    while True:
        current_batch_size = batch_size
        if remaining is not None:
            if remaining <= 0:
                return
            current_batch_size = min(current_batch_size, remaining)

        rows = conn.execute(
            f'''
            SELECT {selected}
            FROM "{table_name}"
            WHERE id > ?
            ORDER BY id
            LIMIT ?
            ''',
            (last_id, current_batch_size),
        ).fetchall()
        if not rows:
            return

        yield rows
        last_id = rows[-1]["id"]
        if remaining is not None:
            remaining -= len(rows)


def build_search_text_from_mapping(row) -> str:
    return " ".join(
        str(row[column]).strip()
        for column in SEARCH_TEXT_COLUMNS
        if column in row.keys() and row[column] is not None and str(row[column]).strip()
    )


def postgres_insert_columns(table_name: str, columns: list[str]) -> list[str]:
    if table_name == "corpus_entries":
        return [*columns, "search_text"]
    return columns


def row_to_insert_tuple(table_name: str, columns: list[str], row) -> tuple:
    row_columns = row.keys()
    values = []
    for column in columns:
        if column in row_columns:
            value = row[column]
        elif column == "storage_backend":
            value = "local"
        elif column == "object_key" and "stored_filename" in row_columns:
            value = row["stored_filename"]
        else:
            value = None
        values.append(value)
    if table_name == "corpus_entries":
        values.append(build_search_text_from_mapping(row))
    return tuple(values)


def build_insert_sql(table_name: str, columns: list[str], on_conflict: str) -> str:
    column_sql = ", ".join(f'"{column}"' for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    if on_conflict == "update":
        update_columns = [column for column in columns if column != "id"]
        update_sql = ", ".join(f'"{column}" = EXCLUDED."{column}"' for column in update_columns)
        conflict_sql = f"ON CONFLICT (id) DO UPDATE SET {update_sql}"
    else:
        conflict_sql = "ON CONFLICT (id) DO NOTHING"
    return f'INSERT INTO "{table_name}" ({column_sql}) VALUES ({placeholders}) {conflict_sql}'


def fetch_existing_values(pg_conn, table_name: str, column: str, values: list) -> set:
    clean_values = [value for value in values if value is not None]
    if not clean_values:
        return set()
    with pg_conn.cursor() as cur:
        cur.execute(
            f'SELECT "{column}" FROM "{table_name}" WHERE "{column}" = ANY(%s)',
            (clean_values,),
        )
        return {row[0] for row in cur.fetchall()}


def filter_existing_rows(pg_conn, table_name: str, columns: list[str], values: list[tuple]) -> tuple[list[tuple], int]:
    if not values:
        return [], 0

    id_index = columns.index("id")
    existing_ids = fetch_existing_values(pg_conn, table_name, "id", [value[id_index] for value in values])
    existing_content_hashes = set()
    existing_submission_ids = set()

    if table_name == "corpus_entries" and "content_hash" in columns:
        hash_index = columns.index("content_hash")
        existing_content_hashes = fetch_existing_values(
            pg_conn,
            table_name,
            "content_hash",
            [value[hash_index] for value in values if value[hash_index]],
        )

    if table_name == "multimodal_entries" and "submission_id" in columns:
        submission_index = columns.index("submission_id")
        existing_submission_ids = fetch_existing_values(
            pg_conn,
            table_name,
            "submission_id",
            [value[submission_index] for value in values if value[submission_index] is not None],
        )

    filtered = []
    skipped = 0
    for value in values:
        if value[id_index] in existing_ids:
            skipped += 1
            continue
        if table_name == "corpus_entries":
            hash_index = columns.index("content_hash")
            if value[hash_index] and value[hash_index] in existing_content_hashes:
                skipped += 1
                continue
        if table_name == "multimodal_entries":
            submission_index = columns.index("submission_id")
            if value[submission_index] is not None and value[submission_index] in existing_submission_ids:
                skipped += 1
                continue
        filtered.append(value)
    return filtered, skipped


def print_progress(table_name: str, stats: TableStats, start_time: float, batch_number: int) -> None:
    print(
        f"{table_name}: batch={batch_number} processed={stats.read} "
        f"inserted={stats.inserted} skipped={stats.skipped} failed={stats.failed} "
        f"elapsed_seconds={time.perf_counter() - start_time:.2f}",
        flush=True,
    )


def print_batch_start(table_name: str, batch_number: int, batch_rows: int, processed_before: int) -> None:
    print(
        f"{table_name}: starting batch={batch_number} "
        f"rows={batch_rows} processed_before={processed_before}",
        flush=True,
    )


def migrate_table(
    sqlite_conn: sqlite3.Connection,
    pg_conn,
    table_name: str,
    columns: list[str],
    batch_size: int,
    limit: int | None,
    on_conflict: str,
) -> TableStats:
    stats = TableStats()
    source_columns = [column for column in columns if column in sqlite_table_columns(sqlite_conn, table_name)]
    insert_columns = postgres_insert_columns(table_name, columns)
    insert_sql = build_insert_sql(table_name, insert_columns, on_conflict)
    start_time = time.perf_counter()
    batch_number = 0
    error_samples = []

    with pg_conn.cursor() as cur:
        for rows in fetch_sqlite_batches(sqlite_conn, table_name, source_columns, batch_size, limit):
            batch_number += 1
            print_batch_start(table_name, batch_number, len(rows), stats.read)
            values = [row_to_insert_tuple(table_name, columns, row) for row in rows]
            stats.read += len(values)
            values, skipped_existing = filter_existing_rows(pg_conn, table_name, insert_columns, values)
            stats.skipped += skipped_existing

            if not values:
                print(f"{table_name}: batch={batch_number} all rows already exist, skip insert", flush=True)
                print_progress(table_name, stats, start_time, batch_number)
                continue

            try:
                print(f"{table_name}: batch={batch_number} inserting={len(values)}", flush=True)
                cur.executemany(insert_sql, values)
                pg_conn.commit()
                affected = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else len(values)
                stats.inserted += affected
                stats.skipped += len(values) - affected
            except Exception as batch_exc:
                pg_conn.rollback()
                print(
                    f"{table_name}: batch={batch_number} batch insert failed; "
                    f"falling back to row-by-row. error={batch_exc}",
                    flush=True,
                )
                if len(error_samples) < MAX_ERROR_SAMPLES:
                    error_samples.append(f"batch {batch_number}: {batch_exc}")
                for value in values:
                    try:
                        cur.execute(insert_sql, value)
                        pg_conn.commit()
                        affected = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 1
                        if affected:
                            stats.inserted += affected
                        else:
                            stats.skipped += 1
                    except Exception as exc:
                        pg_conn.rollback()
                        stats.failed += 1
                        row_id = value[0] if value else "unknown"
                        if len(error_samples) < MAX_ERROR_SAMPLES:
                            error_samples.append(f"id={row_id}: {exc}")
            print_progress(table_name, stats, start_time, batch_number)

    if error_samples:
        print(f"{table_name}: error_samples:", flush=True)
        for sample in error_samples:
            print(f"  - {sample}", flush=True)
    return stats


def postgres_count(pg_conn, table_name: str) -> int | None:
    try:
        with pg_conn.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            return cur.fetchone()[0]
    except Exception as exc:
        print(f"{table_name}: PostgreSQL count unavailable: {exc}", flush=True)
        pg_conn.rollback()
        return None


def print_progress_only(sqlite_conn: sqlite3.Connection, pg_conn) -> None:
    print("Progress-only check; no data will be written.", flush=True)
    for table_name in TABLE_COLUMNS:
        if not table_exists(sqlite_conn, table_name):
            print(f"{table_name}: sqlite_source=missing postgres_target=not_checked", flush=True)
            continue
        source_count = sqlite_count(sqlite_conn, table_name)
        target_count = postgres_count(pg_conn, table_name)
        remaining = None if target_count is None else max(source_count - target_count, 0)
        print(
            f"{table_name}: sqlite_source={source_count} "
            f"postgres_target={target_count if target_count is not None else 'unknown'} "
            f"remaining_by_count={remaining if remaining is not None else 'unknown'}",
            flush=True,
        )


def rebuild_search_text(pg_conn, batch_size: int) -> int:
    total_updated = 0
    start = time.perf_counter()
    batch_number = 0
    update_sql = """
        WITH batch AS (
            SELECT id
            FROM corpus_entries
            WHERE search_text IS DISTINCT FROM concat_ws(' ', title, content, speaker, current_segment, segment_text)
            ORDER BY id
            LIMIT %s
        )
        UPDATE corpus_entries AS target
        SET search_text = concat_ws(' ', target.title, target.content, target.speaker, target.current_segment, target.segment_text)
        FROM batch
        WHERE target.id = batch.id
        RETURNING target.id
    """
    with pg_conn.cursor() as cur:
        while True:
            batch_number += 1
            cur.execute(update_sql, (batch_size,))
            updated = len(cur.fetchall())
            pg_conn.commit()
            total_updated += updated
            print(
                f"rebuild_search_text: batch={batch_number} updated={updated} "
                f"total_updated={total_updated} elapsed_seconds={time.perf_counter() - start:.2f}",
                flush=True,
            )
            if updated == 0:
                break
        cur.execute("ANALYZE corpus_entries")
        pg_conn.commit()
    print(f"rebuild_search_text complete: updated={total_updated}", flush=True)
    return total_updated


def reset_identity_sequences(pg_conn) -> None:
    statements = [
        "SELECT setval(pg_get_serial_sequence('corpus_entries', 'id'), COALESCE((SELECT MAX(id) FROM corpus_entries), 1), true)",
        "SELECT setval(pg_get_serial_sequence('corpus_submissions', 'id'), COALESCE((SELECT MAX(id) FROM corpus_submissions), 1), true)",
        "SELECT setval(pg_get_serial_sequence('multimodal_entries', 'id'), COALESCE((SELECT MAX(id) FROM multimodal_entries), 1), true)",
    ]
    with pg_conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)
    pg_conn.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate corpus SQLite tables to PostgreSQL.")
    parser.add_argument("--sqlite-db", type=Path, default=DEFAULT_SQLITE_PATH, help="Path to corpus.db")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""), help="PostgreSQL DATABASE_URL")
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH, help="PostgreSQL schema SQL file")
    parser.add_argument("--skip-schema", action="store_true", help="Do not execute schema_postgres.sql")
    parser.add_argument("--dry-run", action="store_true", help="Only count source rows; do not connect to PostgreSQL")
    parser.add_argument("--progress-only", action="store_true", help="Read SQLite/PostgreSQL row counts without writing")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows per table for test migrations")
    parser.add_argument("--batch-size", type=int, default=1000, help="Rows fetched per SQLite batch")
    parser.add_argument("--on-conflict", choices=("skip", "update"), default="skip", help="Handle PostgreSQL id conflicts")
    parser.add_argument("--rebuild-search-text", action="store_true", help="Only rebuild corpus_entries.search_text in PostgreSQL and ANALYZE; do not migrate rows")
    parser.add_argument("--apply-schema-only", action="store_true", help="Only execute schema_postgres.sql against PostgreSQL; do not migrate rows")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start = time.perf_counter()

    if not args.sqlite_db.exists():
        raise FileNotFoundError(f"SQLite database not found: {args.sqlite_db}")

    sqlite_conn = connect_sqlite(args.sqlite_db, immutable=args.dry_run)
    try:
        print(f"SQLite: {args.sqlite_db}")
        mode = "apply-schema-only" if args.apply_schema_only else "rebuild-search-text" if args.rebuild_search_text else "progress-only" if args.progress_only else "dry-run" if args.dry_run else "migrate"
        print(f"Mode: {mode}")
        print(f"Limit per table: {args.limit if args.limit else 'none'}")

        for table_name in TABLE_COLUMNS:
            if not table_exists(sqlite_conn, table_name):
                print(f"{table_name}: missing, skip")
                continue
            print(f"{table_name}: source_rows={sqlite_count(sqlite_conn, table_name, args.limit)}")

        if args.dry_run:
            elapsed = time.perf_counter() - start
            print(f"Dry run complete in {elapsed:.2f}s")
            return

        pg_conn = connect_postgres(args.database_url)
        try:
            if args.apply_schema_only:
                execute_schema(pg_conn, args.schema)
                print(f"Schema applied: {args.schema}")
                elapsed = time.perf_counter() - start
                print(f"Apply-schema-only complete in {elapsed:.2f}s")
                return

            if args.rebuild_search_text:
                if not args.skip_schema:
                    execute_schema(pg_conn, args.schema)
                    print(f"Schema applied: {args.schema}")
                rebuild_search_text(pg_conn, args.batch_size)
                elapsed = time.perf_counter() - start
                print(f"Rebuild search_text complete in {elapsed:.2f}s")
                return

            if args.progress_only:
                print_progress_only(sqlite_conn, pg_conn)
                elapsed = time.perf_counter() - start
                print(f"Progress-only complete in {elapsed:.2f}s")
                return

            if not args.skip_schema:
                execute_schema(pg_conn, args.schema)
                print(f"Schema applied: {args.schema}")

            totals = TableStats()
            for table_name, columns in TABLE_COLUMNS.items():
                if not table_exists(sqlite_conn, table_name):
                    continue
                print(f"{table_name}: starting migration batch_size={args.batch_size}", flush=True)
                table_start = time.perf_counter()
                stats = migrate_table(
                    sqlite_conn,
                    pg_conn,
                    table_name,
                    columns,
                    args.batch_size,
                    args.limit,
                    args.on_conflict,
                )
                totals.read += stats.read
                totals.inserted += stats.inserted
                totals.skipped += stats.skipped
                totals.failed += stats.failed
                print(
                    f"{table_name}: read={stats.read} inserted={stats.inserted} "
                    f"skipped={stats.skipped} failed={stats.failed} "
                    f"elapsed={time.perf_counter() - table_start:.2f}s"
                )

            reset_identity_sequences(pg_conn)
            print(
                f"TOTAL: read={totals.read} inserted={totals.inserted} "
                f"skipped={totals.skipped} failed={totals.failed} "
                f"elapsed={time.perf_counter() - start:.2f}s"
            )
        finally:
            pg_conn.close()
    finally:
        sqlite_conn.close()


if __name__ == "__main__":
    main()
