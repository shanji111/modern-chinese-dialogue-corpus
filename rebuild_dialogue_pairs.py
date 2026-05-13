from __future__ import annotations

import argparse

import corpus_repository


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the derived dialogue_pairs table for fast resonance search.")
    parser.add_argument("--batch-size", type=int, default=5000, help="Rows to insert per batch.")
    parser.add_argument("--indexes-only", action="store_true", help="Only create/confirm dialogue_pairs indexes.")
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
            corpus_repository.create_dialogue_pairs_schema(conn)
            conn.commit()
        finally:
            conn.close()
        corpus_repository.ensure_postgres_dialogue_pairs_trigram_indexes()
        print("dialogue_pairs indexes checked")
        return

    stats = corpus_repository.rebuild_dialogue_pairs(batch_size=max(1, args.batch_size))
    corpus_repository.ensure_postgres_dialogue_pairs_trigram_indexes()
    print(f"dialogue_turns: {stats['turns']}")
    print(f"dialogue_pairs: {stats['pairs']}")
    print(f"lexical_echo: {stats['lexical_echo']}")
    print(f"pattern_reuse: {stats['pattern_reuse']}")
    print(f"question_response: {stats['question_response']}")
    print(f"negation_turn: {stats['negation_turn']}")
    print(f"repair_repetition: {stats['repair_repetition']}")


if __name__ == "__main__":
    main()
