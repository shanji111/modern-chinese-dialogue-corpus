from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import DATABASE_BACKEND, describe_database_target, get_db_connection


TEXT_SOURCE = "文本对话"
TEXT_DATASETS = (
    "水浒传",
    "西游记",
    "平凡的世界",
    "骆驼祥子",
    "唐传奇",
    "清平山堂话本",
    "世说新语",
    "朱子语类",
    "孟子",
    "论语",
    "战国策",
    "老乞大",
    "朴通事",
    "西厢记",
    "红楼梦",
)


def marker() -> str:
    return "%s" if DATABASE_BACKEND == "postgres" else "?"


def rows_to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        result.append(row if isinstance(row, dict) else dict(row))
    return result


def scalar(row: Any) -> Any:
    if row is None:
        return None
    if isinstance(row, dict):
        return next(iter(row.values()))
    return row[0]


def print_rows(title: str, rows: list[dict[str, Any]], limit: int = 80) -> None:
    print(f"\n## {title}")
    if not rows:
        print("(none)")
        return
    for row in rows[:limit]:
        print(" | ".join(f"{key}={row.get(key)}" for key in row.keys()))
    if len(rows) > limit:
        print(f"... {len(rows) - limit} more")


def main() -> None:
    info = describe_database_target()
    print(f"db backend: {info['backend']}")
    print(f"db target: {info['host']}")
    print(f"db name: {info['db_name']}")
    ph = marker()
    conn = get_db_connection()
    try:
        total = scalar(conn.execute("SELECT COUNT(*) FROM corpus_entries").fetchone())
        text_total = scalar(conn.execute(f"SELECT COUNT(*) FROM corpus_entries WHERE source = {ph}", (TEXT_SOURCE,)).fetchone())
        print(f"corpus_entries total: {total}")
        print(f"source=文本对话 total: {text_total}")

        rows = rows_to_dicts(conn.execute(
            f"""
            SELECT dataset_name, category, COUNT(*) AS n
            FROM corpus_entries
            WHERE source = {ph}
            GROUP BY dataset_name, category
            ORDER BY n DESC, dataset_name, category
            """,
            (TEXT_SOURCE,),
        ).fetchall())
        print_rows("文本对话 by dataset/category", rows)

        exact_rows = []
        for dataset in TEXT_DATASETS:
            row = conn.execute(
                f"""
                SELECT
                    {ph} AS dataset_name,
                    COUNT(*) AS entries,
                    COUNT(*) FILTER (WHERE source = {ph}) AS source_entries
                FROM corpus_entries
                WHERE dataset_name = {ph}
                """,
                (dataset, TEXT_SOURCE, dataset),
            ).fetchone() if DATABASE_BACKEND == "postgres" else conn.execute(
                f"""
                SELECT
                    {ph} AS dataset_name,
                    COUNT(*) AS entries,
                    SUM(CASE WHEN source = {ph} THEN 1 ELSE 0 END) AS source_entries
                FROM corpus_entries
                WHERE dataset_name = {ph}
                """,
                (dataset, TEXT_SOURCE, dataset),
            ).fetchone()
            exact_rows.append(dict(row) if isinstance(row, dict) else dict(row))
        print_rows("目标文本精确 dataset_name 计数", exact_rows)

        batch_rows = rows_to_dicts(conn.execute(
            f"""
            SELECT import_batch, dataset_name, COUNT(*) AS n
            FROM corpus_entries
            WHERE source = {ph}
            GROUP BY import_batch, dataset_name
            ORDER BY import_batch DESC, n DESC
            """,
            (TEXT_SOURCE,),
        ).fetchall())
        print_rows("文本对话 import_batch", batch_rows, limit=120)

        turn_rows = rows_to_dicts(conn.execute(
            f"""
            SELECT dataset_name, category, COUNT(*) AS turns
            FROM dialogue_turns
            WHERE source = {ph}
            GROUP BY dataset_name, category
            ORDER BY turns DESC, dataset_name, category
            """,
            (TEXT_SOURCE,),
        ).fetchall())
        print_rows("dialogue_turns by dataset/category", turn_rows)

        sample_rows = rows_to_dicts(conn.execute(
            f"""
            SELECT id, title, source, category, dataset_name, import_batch
            FROM corpus_entries
            WHERE dataset_name IN ({", ".join(ph for _ in TEXT_DATASETS)})
            ORDER BY id DESC
            LIMIT 30
            """,
            TEXT_DATASETS,
        ).fetchall())
        print_rows("目标文本最近样例", sample_rows, limit=30)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
