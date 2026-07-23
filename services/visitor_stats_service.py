import hashlib
import os
import re
import secrets
import threading
import time

from database import DATABASE_BACKEND, get_db_connection


VISITOR_COOKIE_NAME = "corpus_visitor_id"
VISITOR_COOKIE_MAX_AGE = 365 * 24 * 60 * 60
VISITOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32}$")


def _read_online_window_seconds():
    try:
        value = int(os.getenv("VISITOR_ONLINE_WINDOW_SECONDS", "90"))
    except ValueError:
        value = 90
    return max(30, min(value, 300))


ONLINE_WINDOW_SECONDS = _read_online_window_seconds()
_init_lock = threading.Lock()
_tables_initialized = False


def new_visitor_id():
    return secrets.token_urlsafe(24)


def normalize_visitor_id(value):
    candidate = str(value or "").strip()
    if VISITOR_ID_PATTERN.fullmatch(candidate):
        return candidate
    return ""


def _hash_visitor_id(visitor_id, secret_key):
    secret = secret_key if isinstance(secret_key, bytes) else str(secret_key or "").encode("utf-8")
    payload = visitor_id.encode("ascii")
    return hashlib.sha256(secret + b":" + payload).hexdigest()


def _first_value(row):
    if row is None:
        return 0
    if isinstance(row, dict):
        return next(iter(row.values()), 0)
    return row[0]


def init_visitor_stats_table():
    global _tables_initialized
    if _tables_initialized:
        return

    with _init_lock:
        if _tables_initialized:
            return
        conn = get_db_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS site_visitors (
                    visitor_hash VARCHAR(64) PRIMARY KEY,
                    first_seen_epoch BIGINT NOT NULL,
                    last_seen_epoch BIGINT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_site_visitors_last_seen "
                "ON site_visitors (last_seen_epoch)"
            )
            conn.commit()
            _tables_initialized = True
        finally:
            conn.close()


def record_visitor_and_get_stats(visitor_id, secret_key, now_epoch=None):
    init_visitor_stats_table()
    current_epoch = int(time.time() if now_epoch is None else now_epoch)
    visitor_hash = _hash_visitor_id(visitor_id, secret_key)
    marker = "%s" if DATABASE_BACKEND == "postgres" else "?"
    cutoff_epoch = current_epoch - ONLINE_WINDOW_SECONDS

    conn = get_db_connection()
    try:
        conn.execute(
            f"""
            INSERT INTO site_visitors (visitor_hash, first_seen_epoch, last_seen_epoch)
            VALUES ({marker}, {marker}, {marker})
            ON CONFLICT(visitor_hash) DO UPDATE
            SET last_seen_epoch = excluded.last_seen_epoch
            """,
            (visitor_hash, current_epoch, current_epoch),
        )
        conn.commit()

        total_row = conn.execute("SELECT COUNT(*) FROM site_visitors").fetchone()
        online_row = conn.execute(
            f"SELECT COUNT(*) FROM site_visitors WHERE last_seen_epoch >= {marker}",
            (cutoff_epoch,),
        ).fetchone()
        return {
            "online": int(_first_value(online_row) or 0),
            "total": int(_first_value(total_row) or 0),
            "window_seconds": ONLINE_WINDOW_SECONDS,
            "updated_at_epoch": current_epoch,
        }
    finally:
        conn.close()
