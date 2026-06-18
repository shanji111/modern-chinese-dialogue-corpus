"""Inspect dialogue-syntax-related corpus schema in SQLite read-only mode."""

from __future__ import annotations

import argparse
from pathlib import Path

from io_utils import connect_sqlite_readonly


RELEVANT_TABLES = ("dialogue_pairs", "dialogue_turns", "corpus_entries", "corpus_stats")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to SQLite corpus.db.")
    return parser.parse_args()


def table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def table_columns(conn, table_name: str) -> list[dict[str, object]]:
    return [
        {
            "cid": row["cid"],
            "name": row["name"],
            "type": row["type"],
            "notnull": row["notnull"],
            "pk": row["pk"],
        }
        for row in conn.execute(f"PRAGMA table_info({table_name})")
    ]


def table_indexes(conn, table_name: str) -> list[dict[str, object]]:
    indexes = []
    for row in conn.execute(f"PRAGMA index_list({table_name})"):
        indexes.append({
            "name": row["name"],
            "unique": row["unique"],
            "origin": row["origin"],
            "partial": row["partial"],
        })
    return indexes


def count_rows(conn, table_name: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) AS total FROM {table_name}").fetchone()["total"])


def pair_length_summary(conn) -> dict[str, object]:
    if not table_exists(conn, "dialogue_pairs"):
        return {}
    row = conn.execute(
        """
        SELECT
          MIN(LENGTH(COALESCE(text_a, ''))) AS min_a,
          MAX(LENGTH(COALESCE(text_a, ''))) AS max_a,
          AVG(LENGTH(COALESCE(text_a, ''))) AS avg_a,
          MIN(LENGTH(COALESCE(text_b, ''))) AS min_b,
          MAX(LENGTH(COALESCE(text_b, ''))) AS max_b,
          AVG(LENGTH(COALESCE(text_b, ''))) AS avg_b,
          SUM(CASE WHEN COALESCE(text_a, '') = '' THEN 1 ELSE 0 END) AS empty_a,
          SUM(CASE WHEN COALESCE(text_b, '') = '' THEN 1 ELSE 0 END) AS empty_b
        FROM dialogue_pairs
        """
    ).fetchone()
    return dict(row)


def pair_flag_counts(conn) -> dict[str, int]:
    if not table_exists(conn, "dialogue_pairs"):
        return {}
    flag_columns = (
        "has_lexical_echo",
        "has_pattern_reuse",
        "has_question_response",
        "has_negation_turn",
        "has_repair_repetition",
    )
    columns = {column["name"] for column in table_columns(conn, "dialogue_pairs")}
    available_flags = [flag for flag in flag_columns if flag in columns]
    if not available_flags:
        return {}
    selected = ", ".join(
        f"SUM(CASE WHEN {flag} = 1 THEN 1 ELSE 0 END) AS {flag}"
        for flag in available_flags
    )
    row = conn.execute(f"SELECT {selected} FROM dialogue_pairs").fetchone()
    return {flag: int(row[flag] or 0) for flag in available_flags}


def source_distribution(conn, limit: int = 20) -> list[dict[str, object]]:
    if not table_exists(conn, "dialogue_pairs"):
        return []
    rows = conn.execute(
        """
        SELECT
          COALESCE(source, '') AS source,
          COALESCE(category, '') AS category,
          COALESCE(dataset_name, '') AS dataset_name,
          COUNT(*) AS total
        FROM dialogue_pairs
        GROUP BY source, category, dataset_name
        ORDER BY total DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def main() -> None:
    args = parse_args()
    db_path = Path(args.db).resolve()
    with connect_sqlite_readonly(db_path) as conn:
        print(f"read_only_connection=file:{db_path.as_posix()}?mode=ro")
        print("database_list=" + repr([tuple(row) for row in conn.execute("PRAGMA database_list")]))
        for table_name in RELEVANT_TABLES:
            exists = table_exists(conn, table_name)
            print(f"\nTABLE {table_name} exists={exists}")
            if not exists:
                continue
            print(f"count={count_rows(conn, table_name)}")
            print("columns=" + repr(table_columns(conn, table_name)))
            print("indexes=" + repr(table_indexes(conn, table_name)))
        print("\nPAIR_TEXT_LENGTHS=" + repr(pair_length_summary(conn)))
        print("PAIR_FLAG_COUNTS=" + repr(pair_flag_counts(conn)))
        print("PAIR_SOURCE_DISTRIBUTION_TOP=" + repr(source_distribution(conn)))


if __name__ == "__main__":
    main()

