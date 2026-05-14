from __future__ import annotations

import argparse
import sys
import time

import corpus_repository


def render_progress(payload, started_at):
    total = max(1, int(payload.get("total") or 0))
    processed = min(total, int(payload.get("processed") or 0))
    inserted_turns = int(payload.get("inserted_turns") or 0)
    entries_with_turns = int(payload.get("entries_with_turns") or 0)
    ratio = processed / total if total else 1.0
    bar_width = 28
    filled = min(bar_width, int(bar_width * ratio))
    bar = "#" * filled + "-" * (bar_width - filled)
    elapsed = max(0.0, time.perf_counter() - started_at)
    line = (
        f"\r[dialogue_turns] [{bar}] {processed}/{total} "
        f"({ratio * 100:5.1f}%) 已拆条目={entries_with_turns} 已写话轮={inserted_turns} "
        f"耗时={elapsed:,.1f}s"
    )
    sys.stdout.write(line)
    sys.stdout.flush()
    if payload.get("phase") == "done":
        sys.stdout.write("\n")
        sys.stdout.flush()


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

    started_at = time.perf_counter()
    stats = corpus_repository.rebuild_dialogue_turns(
        batch_size=max(1, args.batch_size),
        progress_callback=lambda payload: render_progress(payload, started_at),
    )
    corpus_repository.ensure_postgres_dialogue_turn_text_trigram_index()
    print(f"dialogue_turns rebuilt: entries={stats['entries']} turns={stats['turns']}")


if __name__ == "__main__":
    main()
