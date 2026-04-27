import sqlite3
import json
import os

from db_utils import compute_content_hash, create_indexes, utc_timestamp

DB_FILE = "corpus.db"
JSON_FILE = os.path.join("data", "sample_corpus.json")


def init_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 删除旧表，方便反复测试
    cursor.execute("DROP TABLE IF EXISTS corpus_entries")

    # 创建新表
    cursor.execute("""
        CREATE TABLE corpus_entries (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT NOT NULL,
            year INTEGER,
            category TEXT,
            dataset_name TEXT,
            created_at TEXT,
            import_batch TEXT,
            content_hash TEXT
        )
    """)

    # 读取 JSON 数据
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 插入数据
    created_at = utc_timestamp()
    for item in data:
        content = item.get("content")
        category = item.get("category")
        source = item.get("source")
        cursor.execute("""
            INSERT INTO corpus_entries (
                id, title, content, source, year, category,
                dataset_name, created_at, import_batch, content_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.get("id"),
            item.get("title"),
            content,
            source,
            item.get("year"),
            category,
            category or source,
            created_at,
            "sample_init",
            compute_content_hash(content)
        ))

    create_indexes(conn)
    conn.commit()
    conn.close()
    print("数据库初始化完成，数据已导入 corpus.db")


if __name__ == "__main__":
    init_database()
