import os
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_BACKEND = os.environ.get("DATABASE_BACKEND", "sqlite").strip().lower() or "sqlite"
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "corpus.db"))
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = BASE_DIR / DATABASE_PATH


class SQLiteDatabaseBackend:
    def __init__(self, database_path=DATABASE_PATH):
        self.database_path = Path(database_path)

    def connect(self):
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn


class PostgresDatabaseBackend:
    """Initial PostgreSQL backend.

    This establishes PostgreSQL connectivity for migration scripts and later app
    work. app.py still contains SQLite-style '?' placeholders and FTS5 queries,
    so DATABASE_BACKEND=postgres is not yet a complete runtime switch.
    """

    def __init__(self, database_url=DATABASE_URL):
        self.database_url = database_url

    def connect(self):
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is required when DATABASE_BACKEND=postgres.")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("PostgreSQL support requires psycopg[binary].") from exc
        return psycopg.connect(self.database_url, row_factory=dict_row)


def row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)


def get_database_backend():
    if DATABASE_BACKEND == "sqlite":
        return SQLiteDatabaseBackend(DATABASE_PATH)
    if DATABASE_BACKEND == "postgres":
        return PostgresDatabaseBackend(DATABASE_URL)
    raise NotImplementedError(f"Unsupported DATABASE_BACKEND: {DATABASE_BACKEND}")


def get_db_connection():
    return get_database_backend().connect()
