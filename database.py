import os
import sqlite3
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlparse, urlunparse


BASE_DIR = Path(__file__).resolve().parent
DATABASE_BACKEND = os.environ.get("DATABASE_BACKEND", "sqlite").strip().lower() or "sqlite"
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "corpus.db"))
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = BASE_DIR / DATABASE_PATH


def redact_database_url(database_url=DATABASE_URL):
    if not database_url:
        return ""
    parsed = urlparse(database_url)
    if not parsed.scheme:
        return database_url
    username = quote(unquote(parsed.username or ""), safe="") if parsed.username else ""
    password = ":***" if parsed.password else ""
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port else ""
    auth = ""
    if username or password:
        auth = f"{username}{password}@"
    query = "&".join(f"{key}=***" if "password" in key.lower() else f"{key}={value}" for key, value in parse_qsl(parsed.query, keep_blank_values=True))
    return urlunparse((parsed.scheme, f"{auth}{host}{port}", parsed.path, parsed.params, query, parsed.fragment))


def describe_database_target(database_backend=DATABASE_BACKEND, database_url=DATABASE_URL, database_path=DATABASE_PATH):
    backend = (database_backend or "sqlite").strip().lower() or "sqlite"
    if backend == "postgres":
        parsed = urlparse(database_url or "")
        host = parsed.hostname or ""
        host_kind = "localhost" if host in {"localhost", "127.0.0.1", "::1"} else (host or "unknown")
        db_name = unquote((parsed.path or "").lstrip("/")) or ""
        return {
            "backend": backend,
            "host": host_kind,
            "raw_host": host,
            "db_name": db_name,
            "redacted_url": redact_database_url(database_url),
            "sqlite_path": "",
        }
    resolved_path = Path(database_path).resolve()
    return {
        "backend": backend,
        "host": str(resolved_path),
        "raw_host": "",
        "db_name": resolved_path.name,
        "redacted_url": "",
        "sqlite_path": str(resolved_path),
    }


def print_database_identity(prefix="[db]"):
    info = describe_database_target()
    print(f"{prefix} DB backend: {info['backend']}", flush=True)
    print(f"{prefix} DB host: {info['host']}", flush=True)
    print(f"{prefix} DB name: {info['db_name']}", flush=True)


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


def get_readonly_db_connection():
    if DATABASE_BACKEND != "sqlite":
        return get_db_connection()
    sqlite_path = quote(str(DATABASE_PATH.resolve()).replace(os.sep, "/"), safe="/:")
    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
