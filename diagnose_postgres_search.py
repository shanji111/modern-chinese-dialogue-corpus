from __future__ import annotations

import argparse
import os
import re
import sys
import time

from corpus_repository import (
    POSTGRES_SEARCH_FIELDS,
    POSTGRES_SEARCH_TEXT_FIELD,
    build_postgres_legacy_search_where,
    build_postgres_search_where,
)


KEYWORDS = ["你", "谢谢", "吃麦当劳"]


def connect_postgres(database_url: str):
    if not database_url:
        raise RuntimeError("DATABASE_URL is required. It is read from the environment and is never printed.")
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("Install dependencies first: pip install -r requirements.txt") from exc
    return psycopg.connect(database_url)


def build_count_sql(keyword: str, legacy: bool = False):
    builder = build_postgres_legacy_search_where if legacy else build_postgres_search_where
    where_sql, params = builder(keyword)
    return f"SELECT COUNT(*) AS total FROM corpus_entries {where_sql}", params


def build_page_sql(keyword: str, limit: int, legacy: bool = False):
    builder = build_postgres_legacy_search_where if legacy else build_postgres_search_where
    where_sql, params = builder(keyword)
    return f"""
        SELECT *
        FROM corpus_entries
        {where_sql}
        ORDER BY id DESC
        LIMIT %s OFFSET %s
    """, [*params, limit, 0]


def explain_query(conn, label: str, sql: str, params: list):
    start = time.perf_counter()
    with conn.cursor() as cur:
        cur.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) " + sql, params)
        lines = [row[0] for row in cur.fetchall()]
    elapsed = time.perf_counter() - start
    text = "\n".join(lines)
    lower_text = text.lower()
    uses_search_text_index = "idx_corpus_search_text_trgm" in lower_text
    uses_trgm = "bitmap index scan" in lower_text and ("trgm" in lower_text or "gin" in lower_text)
    has_seq_scan = "seq scan" in lower_text
    execution_ms = None
    match = re.search(r"Execution Time: ([0-9.]+) ms", text)
    if match:
        execution_ms = float(match.group(1))
    rows_removed = sum(int(value) for value in re.findall(r"Rows Removed by Filter: ([0-9]+)", text))
    print(f"\n[{label}]")
    print(f"client_elapsed_ms={elapsed * 1000:.2f}")
    print(f"execution_ms={execution_ms if execution_ms is not None else 'unknown'}")
    print(f"uses_search_text_trgm_index={uses_search_text_index}")
    print(f"uses_trigram_or_gin={uses_trgm}")
    print(f"has_seq_scan={has_seq_scan}")
    print(f"rows_removed_by_filter={rows_removed}")
    print("plan:")
    for line in lines:
        print(line)


def check_indexes(conn):
    print("legacy_search_fields:", ", ".join(POSTGRES_SEARCH_FIELDS))
    print("new_search_field:", POSTGRES_SEARCH_TEXT_FIELD)
    with conn.cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'pg_trgm'")
        print(f"pg_trgm_enabled={cur.fetchone() is not None}")
        cur.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'corpus_entries'
                  AND column_name = 'search_text'
            )
        """)
        print(f"search_text_column_exists={cur.fetchone()[0]}")
        cur.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'corpus_entries'
              AND (indexdef ILIKE '%gin%' OR indexdef ILIKE '%trgm%')
            ORDER BY indexname
        """)
        rows = cur.fetchall()
    print("gin_or_trgm_indexes:")
    if not rows:
        print("  none")
    for name, definition in rows:
        print(f"  {name}: {definition}")


def parse_args():
    parser = argparse.ArgumentParser(description="Read-only EXPLAIN ANALYZE diagnostics for PostgreSQL corpus search.")
    parser.add_argument("--limit", type=int, default=50, help="Page query LIMIT")
    parser.add_argument("--keyword", action="append", help="Keyword to diagnose; can be repeated")
    parser.add_argument("--skip-plans", action="store_true", help="Only show extension/index status")
    parser.add_argument("--new-only", action="store_true", help="Only diagnose search_text ILIKE queries")
    return parser.parse_args()


def main():
    args = parse_args()
    database_url = os.environ.get("DATABASE_URL", "").strip()
    try:
        conn = connect_postgres(database_url)
    except Exception as exc:
        print(exc)
        return 2
    try:
        conn.read_only = True
        check_indexes(conn)
        if args.skip_plans:
            return 0
        for keyword in args.keyword or KEYWORDS:
            print(f"\n=== keyword={keyword!r} ===")
            count_sql, count_params = build_count_sql(keyword, legacy=False)
            page_sql, page_params = build_page_sql(keyword, args.limit, legacy=False)
            print("new_count_sql_shape=SELECT COUNT(*) FROM corpus_entries WHERE search_text ILIKE pattern")
            print("new_page_sql_shape=SELECT * FROM corpus_entries WHERE search_text ILIKE pattern ORDER BY id DESC LIMIT/OFFSET")
            explain_query(conn, f"new search_text count keyword={keyword}", count_sql, count_params)
            explain_query(conn, f"new search_text page keyword={keyword}", page_sql, page_params)

            if not args.new_only:
                legacy_count_sql, legacy_count_params = build_count_sql(keyword, legacy=True)
                legacy_page_sql, legacy_page_params = build_page_sql(keyword, args.limit, legacy=True)
                print("legacy_count_sql_shape=SELECT COUNT(*) FROM corpus_entries WHERE multiple fields OR ILIKE pattern")
                print("legacy_page_sql_shape=SELECT * FROM corpus_entries WHERE multiple fields OR ILIKE pattern ORDER BY id DESC LIMIT/OFFSET")
                explain_query(conn, f"legacy OR count keyword={keyword}", legacy_count_sql, legacy_count_params)
                explain_query(conn, f"legacy OR page keyword={keyword}", legacy_page_sql, legacy_page_params)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
