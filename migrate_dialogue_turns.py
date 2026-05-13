from __future__ import annotations

import argparse

import corpus_repository


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the derived dialogue_turns table for resonance search.")
    parser.add_argument("--batch-size", type=int, default=1000, help="Rows to insert per batch.")
    parser.add_argument("--indexes-only", action="store_true", help="Only create/confirm dialogue_turns indexes.")
    args = parser.parse_args()

    if args.indexes_only:
        conn = corpus_repository.get_db_connection()
        try:
            if not corpus_repository.is_postgres():
                try:
                    corpus_repository.prepare_sqlite_for_safe_indexing(conn)
                    integrity = corpus_repository.sqlite_integrity_check(conn)
                except Exception as exc:
                    raise RuntimeError(
                        "SQLite is not ready for index creation. Please stop Flask and all Python processes, "
                        "keep corpus.db/corpus.db-journal in place, then rerun --indexes-only. "
                        f"Original error: {exc!r}"
                    ) from exc
                if integrity != "ok":
                    raise RuntimeError(
                        "SQLite integrity_check failed. Please stop Flask/all Python processes, "
                        "back up corpus.db, and recover from a known-good database before creating indexes. "
                        f"Result: {integrity}"
                    )
            corpus_repository.create_dialogue_turns_schema(conn)
            conn.commit()
        finally:
            conn.close()
        corpus_repository.ensure_postgres_dialogue_turn_text_trigram_index()
        print("dialogue_turns indexes checked")
        return

    stats = corpus_repository.rebuild_dialogue_turns(batch_size=max(1, args.batch_size))
    corpus_repository.ensure_postgres_dialogue_turn_text_trigram_index()
    print(f"dialogue_turns rebuilt: entries={stats['entries']} turns={stats['turns']}")


if __name__ == "__main__":
    main()
