from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import database
import corpus_repository


EXPECTED_TURN_INDEXES = {
    "idx_dialogue_turns_entry",
    "idx_dialogue_turns_entry_id",
    "idx_dialogue_turns_conversation",
    "idx_dialogue_turns_conversation_turn",
    "idx_dialogue_turns_source",
    "idx_dialogue_turns_category",
    "idx_dialogue_turns_source_category_id",
}

EXPECTED_PAIR_INDEXES = {
    "idx_dialogue_pairs_a",
    "idx_dialogue_pairs_b",
    "idx_dialogue_pairs_entry",
    "idx_dialogue_pairs_source_category_id",
    "idx_dialogue_pairs_lexical",
    "idx_dialogue_pairs_pattern",
    "idx_dialogue_pairs_question",
    "idx_dialogue_pairs_negation",
    "idx_dialogue_pairs_repair",
}

POSTGRES_TRIGRAM_INDEXES = {
    "idx_dialogue_turns_turn_text_trgm",
    "idx_dialogue_pairs_text_a_trgm",
    "idx_dialogue_pairs_text_b_trgm",
}


def parse_simple_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def render_yaml_mentions_database(path: Path) -> dict[str, bool]:
    if not path.exists():
        return {"exists": False, "DATABASE_BACKEND": False, "DATABASE_URL": False, "DATABASE_PATH": False}
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "exists": True,
        "DATABASE_BACKEND": "DATABASE_BACKEND" in text,
        "DATABASE_URL": "DATABASE_URL" in text,
        "DATABASE_PATH": "DATABASE_PATH" in text,
    }


def first_value(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return next(iter(row.values()))
    try:
        return row[0]
    except (KeyError, IndexError):
        return next(iter(dict(row).values()))


def table_exists(conn, table_name: str) -> bool:
    try:
        if corpus_repository.is_postgres():
            row = conn.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = %s
                LIMIT 1
                """,
                (table_name,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
                (table_name,),
            ).fetchone()
        return row is not None
    except Exception as exc:
        raise RuntimeError(f"cannot inspect table {table_name}: {exc!r}") from exc


def count_table(conn, table_name: str) -> int | str:
    try:
        if not table_exists(conn, table_name):
            return "missing table"
        return first_value(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone())
    except Exception as exc:
        return f"error: {exc!r}"


def sqlite_indexes(conn, table_name: str) -> set[str] | None:
    try:
        if not table_exists(conn, table_name):
            return set()
        rows = conn.execute(f"PRAGMA index_list({table_name})").fetchall()
        names = set()
        for row in rows:
            data = dict(row)
            names.add(data.get("name") or row[1])
        return names
    except Exception as exc:
        print(f"  could not inspect indexes for {table_name}: {exc!r}")
        return None


def postgres_indexes(conn, table_name: str) -> set[str] | None:
    try:
        rows = conn.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = %s
            """,
            (table_name,),
        ).fetchall()
        return {row["indexname"] for row in rows}
    except Exception as exc:
        print(f"  could not inspect indexes for {table_name}: {exc!r}")
        return None


def print_index_status(found: set[str] | None, expected: set[str], label: str) -> None:
    print(f"{label} indexes:")
    if found is None:
        for name in sorted(expected):
            print(f"  [UNKNOWN] {name}")
        return
    for name in sorted(expected):
        print(f"  [{'OK' if name in found else 'MISSING'}] {name}")


def main() -> None:
    root = Path(__file__).resolve().parent
    env_file_values = parse_simple_env_file(root / ".env")
    render_info = render_yaml_mentions_database(root / "render.yaml")
    target = database.describe_database_target()

    print("Configuration:")
    print(f"  DATABASE_BACKEND: {database.DATABASE_BACKEND}")
    print(f"  DATABASE_URL exists: {bool(database.DATABASE_URL)}")
    print(f"  DATABASE_URL redacted: {database.redact_database_url(database.DATABASE_URL) or '(empty)'}")
    print(f"  DATABASE_PATH: {database.DATABASE_PATH.resolve()}")
    print(f"  .env exists: {bool(env_file_values)}")
    print(f"  .env DATABASE_BACKEND present: {'DATABASE_BACKEND' in env_file_values}")
    print(f"  .env DATABASE_URL present: {'DATABASE_URL' in env_file_values}")
    print(f"  render.yaml exists: {render_info['exists']}")
    print(f"  render.yaml DATABASE_BACKEND present: {render_info['DATABASE_BACKEND']}")
    print(f"  render.yaml DATABASE_URL present: {render_info['DATABASE_URL']}")

    print("\nResolved target:")
    print(f"  DB backend: {target['backend']}")
    print(f"  DB host: {target['host']}")
    print(f"  DB name: {target['db_name']}")

    conn = None
    try:
        conn = database.get_db_connection()
        if isinstance(conn, sqlite3.Connection):
            actual_type = "sqlite"
            actual_detail = str(database.DATABASE_PATH.resolve())
        else:
            actual_type = "postgres"
            actual_detail = f"{target['raw_host']}/{target['db_name']}"
        print("\nConnection:")
        print(f"  actual connection type: {actual_type}")
        print(f"  actual connection target: {actual_detail}")

        print("\nCounts:")
        print(f"  corpus_entries: {count_table(conn, 'corpus_entries')}")
        print(f"  dialogue_turns: {count_table(conn, corpus_repository.TURN_TABLE)}")
        print(f"  dialogue_pairs: {count_table(conn, corpus_repository.PAIR_TABLE)}")

        print("\nIndexes:")
        if actual_type == "sqlite":
            turn_indexes = sqlite_indexes(conn, corpus_repository.TURN_TABLE)
            pair_indexes = sqlite_indexes(conn, corpus_repository.PAIR_TABLE)
            print_index_status(turn_indexes, EXPECTED_TURN_INDEXES, "dialogue_turns")
            print_index_status(pair_indexes, EXPECTED_PAIR_INDEXES, "dialogue_pairs")
        else:
            turn_indexes = postgres_indexes(conn, corpus_repository.TURN_TABLE)
            pair_indexes = postgres_indexes(conn, corpus_repository.PAIR_TABLE)
            print_index_status(turn_indexes, EXPECTED_TURN_INDEXES | {"idx_dialogue_turns_turn_text_trgm"}, "dialogue_turns")
            print_index_status(pair_indexes, EXPECTED_PAIR_INDEXES | POSTGRES_TRIGRAM_INDEXES, "dialogue_pairs")
    except Exception as exc:
        print("\nConnection:")
        print(f"  actual connection type: error")
        print(f"  connection error: {exc!r}")
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
