from __future__ import annotations

import corpus_repository


def main() -> None:
    conn = corpus_repository.get_db_connection()
    try:
        if corpus_repository.is_postgres():
            rows = conn.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename IN (%s, %s)
                ORDER BY indexname
                """,
                (corpus_repository.TURN_TABLE, corpus_repository.PAIR_TABLE),
            ).fetchall()
            for row in rows:
                print(f"{row['indexname']}: {row['indexdef']}")
            if not rows:
                print("No indexes found for dialogue_turns/dialogue_pairs.")
            return

        try:
            corpus_repository.prepare_sqlite_for_safe_indexing(conn)
            integrity = corpus_repository.sqlite_integrity_check(conn)
        except Exception as exc:
            print(f"SQLite index check could not start: {exc!r}")
            print("Please stop Flask and all Python processes, keep corpus.db/corpus.db-journal in place, then rerun this script.")
            return
        print(f"PRAGMA integrity_check: {integrity}")
        if integrity != "ok":
            print("Integrity check failed. Stop Flask/all Python processes, back up corpus.db, and recover before indexing.")
            return
        for table_name in (corpus_repository.TURN_TABLE, corpus_repository.PAIR_TABLE):
            print(f"[{table_name}]")
            rows = conn.execute(f"PRAGMA index_list({table_name})").fetchall()
            if not rows:
                print(f"No indexes found for {table_name}.")
                continue
            for row in rows:
                info = dict(row)
                name = info.get("name") or row[1]
                print(f"{name}: {info}")
                columns = conn.execute(f"PRAGMA index_info({name})").fetchall()
                for column in columns:
                    print(f"  - {dict(column)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
