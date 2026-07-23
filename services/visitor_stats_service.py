import hashlib
import ipaddress
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from database import DATABASE_BACKEND, get_db_connection


VISITOR_COOKIE_NAME = "corpus_visitor_id"
VISITOR_COOKIE_MAX_AGE = 365 * 24 * 60 * 60
VISITOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32}$")
SNAPSHOT_INTERVAL_SECONDS = 5 * 60


def _read_int_env(name, default, minimum, maximum):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


def _read_bool_env(name, default=False):
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    return raw not in {"0", "false", "no", "off"}


ONLINE_WINDOW_SECONDS = _read_int_env("VISITOR_ONLINE_WINDOW_SECONDS", 90, 30, 300)
IP_LOGGING_ENABLED = _read_bool_env("VISITOR_IP_LOGGING", True)
IP_LOG_RETENTION_DAYS = _read_int_env("VISITOR_IP_RETENTION_DAYS", 30, 1, 365)
HISTORY_RETENTION_DAYS = _read_int_env("VISITOR_HISTORY_RETENTION_DAYS", 365, 7, 1095)
TRUST_X_FORWARDED_FOR = _read_bool_env("TRUST_X_FORWARDED_FOR", False)

try:
    VISITOR_TIMEZONE = ZoneInfo(os.getenv("VISITOR_STATS_TIMEZONE", "Asia/Shanghai"))
except ZoneInfoNotFoundError:
    VISITOR_TIMEZONE = ZoneInfo("UTC")

_init_lock = threading.Lock()
_tables_initialized = False
_cleanup_lock = threading.Lock()
_last_cleanup_epoch = 0
_activity_lock = threading.Lock()
_pending_ip_activity = {}
_last_activity_flush_monotonic = 0.0
_blocked_cache_lock = threading.Lock()
_blocked_ip_cache = set()
_blocked_cache_monotonic = 0.0


def new_visitor_id():
    return secrets.token_urlsafe(24)


def normalize_visitor_id(value):
    candidate = str(value or "").strip()
    if VISITOR_ID_PATTERN.fullmatch(candidate):
        return candidate
    return ""


def normalize_ip_address(value):
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    try:
        return ipaddress.ip_address(candidate).compressed
    except ValueError:
        return ""


def mask_ip_address(value):
    normalized = normalize_ip_address(value)
    if not normalized:
        return "未知"
    address = ipaddress.ip_address(normalized)
    if address.version == 4:
        parts = normalized.split(".")
        return ".".join(parts[:3] + ["*"])
    network = ipaddress.ip_network(f"{normalized}/64", strict=False)
    return f"{network.network_address.compressed}/64"


def get_request_client_ip(headers, remote_addr):
    cloudflare_ip = normalize_ip_address(headers.get("CF-Connecting-IP"))
    if cloudflare_ip and headers.get("CF-Ray"):
        return cloudflare_ip

    if TRUST_X_FORWARDED_FOR:
        forwarded = (headers.get("X-Forwarded-For") or "").split(",", 1)[0]
        forwarded_ip = normalize_ip_address(forwarded)
        if forwarded_ip:
            return forwarded_ip

    return normalize_ip_address(remote_addr)


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


def _row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    return dict(row)


def _marker():
    return "%s" if DATABASE_BACKEND == "postgres" else "?"


def _local_datetime(epoch):
    return datetime.fromtimestamp(int(epoch), VISITOR_TIMEZONE)


def _format_local_time(epoch, include_date=True):
    if not epoch:
        return "—"
    pattern = "%Y-%m-%d %H:%M:%S" if include_date else "%H:%M"
    return _local_datetime(epoch).strftime(pattern)


def parse_local_datetime(value):
    parsed = datetime.fromisoformat(str(value or "").strip())
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=VISITOR_TIMEZONE)
    return int(parsed.timestamp())


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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS site_visitor_daily (
                    day_key VARCHAR(10) NOT NULL,
                    visitor_hash VARCHAR(64) NOT NULL,
                    first_seen_epoch BIGINT NOT NULL,
                    last_seen_epoch BIGINT NOT NULL,
                    PRIMARY KEY (day_key, visitor_hash)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS site_visit_snapshots (
                    bucket_epoch BIGINT PRIMARY KEY,
                    online_visitors INTEGER NOT NULL,
                    peak_online_visitors INTEGER NOT NULL,
                    total_visitors BIGINT NOT NULL,
                    daily_visitors BIGINT NOT NULL,
                    recorded_at_epoch BIGINT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS site_ip_activity (
                    ip_address VARCHAR(45) NOT NULL,
                    bucket_epoch BIGINT NOT NULL,
                    first_seen_epoch BIGINT NOT NULL,
                    last_seen_epoch BIGINT NOT NULL,
                    request_count BIGINT NOT NULL,
                    blocked_count BIGINT NOT NULL DEFAULT 0,
                    last_path VARCHAR(255),
                    last_method VARCHAR(12),
                    last_status INTEGER,
                    PRIMARY KEY (ip_address, bucket_epoch)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS site_blocked_ips (
                    ip_address VARCHAR(45) PRIMARY KEY,
                    reason TEXT,
                    blocked_at_epoch BIGINT NOT NULL,
                    blocked_by VARCHAR(120)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_site_visitors_last_seen "
                "ON site_visitors (last_seen_epoch)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_site_visitor_daily_day "
                "ON site_visitor_daily (day_key)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_site_visit_snapshots_bucket "
                "ON site_visit_snapshots (bucket_epoch)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_site_ip_activity_last_seen "
                "ON site_ip_activity (last_seen_epoch)"
            )
            conn.commit()
            _tables_initialized = True
        finally:
            conn.close()


def _query_current_stats(conn, current_epoch):
    marker = _marker()
    cutoff_epoch = current_epoch - ONLINE_WINDOW_SECONDS
    total_row = conn.execute("SELECT COUNT(*) FROM site_visitors").fetchone()
    online_row = conn.execute(
        f"SELECT COUNT(*) FROM site_visitors WHERE last_seen_epoch >= {marker}",
        (cutoff_epoch,),
    ).fetchone()
    return int(_first_value(online_row) or 0), int(_first_value(total_row) or 0)


def _query_daily_visitors(conn, day_key):
    marker = _marker()
    row = conn.execute(
        f"SELECT COUNT(*) FROM site_visitor_daily WHERE day_key = {marker}",
        (day_key,),
    ).fetchone()
    return int(_first_value(row) or 0)


def _upsert_snapshot(conn, current_epoch, online, total, daily):
    marker = _marker()
    bucket_epoch = current_epoch - (current_epoch % SNAPSHOT_INTERVAL_SECONDS)
    conn.execute(
        f"""
        INSERT INTO site_visit_snapshots (
            bucket_epoch,
            online_visitors,
            peak_online_visitors,
            total_visitors,
            daily_visitors,
            recorded_at_epoch
        )
        VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker})
        ON CONFLICT(bucket_epoch) DO UPDATE
        SET online_visitors = excluded.online_visitors,
            peak_online_visitors = CASE
                WHEN excluded.peak_online_visitors > site_visit_snapshots.peak_online_visitors
                THEN excluded.peak_online_visitors
                ELSE site_visit_snapshots.peak_online_visitors
            END,
            total_visitors = excluded.total_visitors,
            daily_visitors = excluded.daily_visitors,
            recorded_at_epoch = excluded.recorded_at_epoch
        """,
        (bucket_epoch, online, online, total, daily, current_epoch),
    )


def _maybe_cleanup(conn, current_epoch):
    global _last_cleanup_epoch
    if current_epoch - _last_cleanup_epoch < 6 * 60 * 60:
        return
    with _cleanup_lock:
        if current_epoch - _last_cleanup_epoch < 6 * 60 * 60:
            return
        marker = _marker()
        ip_cutoff = current_epoch - IP_LOG_RETENTION_DAYS * 24 * 60 * 60
        history_cutoff = current_epoch - HISTORY_RETENTION_DAYS * 24 * 60 * 60
        day_cutoff = (_local_datetime(current_epoch) - timedelta(days=HISTORY_RETENTION_DAYS)).date().isoformat()
        conn.execute(
            f"DELETE FROM site_ip_activity WHERE last_seen_epoch < {marker}",
            (ip_cutoff,),
        )
        conn.execute(
            f"DELETE FROM site_visit_snapshots WHERE bucket_epoch < {marker}",
            (history_cutoff,),
        )
        conn.execute(
            f"DELETE FROM site_visitor_daily WHERE day_key < {marker}",
            (day_cutoff,),
        )
        _last_cleanup_epoch = current_epoch


def record_visitor_and_get_stats(visitor_id, secret_key, now_epoch=None):
    init_visitor_stats_table()
    current_epoch = int(time.time() if now_epoch is None else now_epoch)
    visitor_hash = _hash_visitor_id(visitor_id, secret_key)
    marker = _marker()
    day_key = _local_datetime(current_epoch).date().isoformat()

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
        conn.execute(
            f"""
            INSERT INTO site_visitor_daily (
                day_key,
                visitor_hash,
                first_seen_epoch,
                last_seen_epoch
            )
            VALUES ({marker}, {marker}, {marker}, {marker})
            ON CONFLICT(day_key, visitor_hash) DO UPDATE
            SET last_seen_epoch = excluded.last_seen_epoch
            """,
            (day_key, visitor_hash, current_epoch, current_epoch),
        )

        online, total = _query_current_stats(conn, current_epoch)
        daily = _query_daily_visitors(conn, day_key)
        _upsert_snapshot(conn, current_epoch, online, total, daily)
        _maybe_cleanup(conn, current_epoch)
        conn.commit()
        return {
            "online": online,
            "total": total,
            "window_seconds": ONLINE_WINDOW_SECONDS,
            "updated_at_epoch": current_epoch,
        }
    finally:
        conn.close()


def _flush_activity_batch(batch):
    if not batch or not IP_LOGGING_ENABLED:
        return
    init_visitor_stats_table()
    marker = _marker()
    conn = get_db_connection()
    try:
        for item in batch.values():
            conn.execute(
                f"""
                INSERT INTO site_ip_activity (
                    ip_address,
                    bucket_epoch,
                    first_seen_epoch,
                    last_seen_epoch,
                    request_count,
                    blocked_count,
                    last_path,
                    last_method,
                    last_status
                )
                VALUES (
                    {marker}, {marker}, {marker}, {marker}, {marker},
                    {marker}, {marker}, {marker}, {marker}
                )
                ON CONFLICT(ip_address, bucket_epoch) DO UPDATE
                SET first_seen_epoch = CASE
                        WHEN excluded.first_seen_epoch < site_ip_activity.first_seen_epoch
                        THEN excluded.first_seen_epoch
                        ELSE site_ip_activity.first_seen_epoch
                    END,
                    last_seen_epoch = CASE
                        WHEN excluded.last_seen_epoch > site_ip_activity.last_seen_epoch
                        THEN excluded.last_seen_epoch
                        ELSE site_ip_activity.last_seen_epoch
                    END,
                    request_count = site_ip_activity.request_count + excluded.request_count,
                    blocked_count = site_ip_activity.blocked_count + excluded.blocked_count,
                    last_path = excluded.last_path,
                    last_method = excluded.last_method,
                    last_status = excluded.last_status
                """,
                (
                    item["ip_address"],
                    item["bucket_epoch"],
                    item["first_seen_epoch"],
                    item["last_seen_epoch"],
                    item["request_count"],
                    item["blocked_count"],
                    item["last_path"],
                    item["last_method"],
                    item["last_status"],
                ),
            )
        _maybe_cleanup(conn, int(time.time()))
        conn.commit()
    finally:
        conn.close()


def buffer_ip_activity(
    ip_address,
    path,
    method,
    status_code,
    blocked=False,
    now_epoch=None,
    force=False,
):
    global _last_activity_flush_monotonic
    if not IP_LOGGING_ENABLED:
        return
    normalized_ip = normalize_ip_address(ip_address)
    if not normalized_ip:
        return

    current_epoch = int(time.time() if now_epoch is None else now_epoch)
    bucket_epoch = current_epoch - (current_epoch % SNAPSHOT_INTERVAL_SECONDS)
    key = (normalized_ip, bucket_epoch)
    batch = None

    with _activity_lock:
        item = _pending_ip_activity.setdefault(
            key,
            {
                "ip_address": normalized_ip,
                "bucket_epoch": bucket_epoch,
                "first_seen_epoch": current_epoch,
                "last_seen_epoch": current_epoch,
                "request_count": 0,
                "blocked_count": 0,
                "last_path": "",
                "last_method": "",
                "last_status": 0,
            },
        )
        item["first_seen_epoch"] = min(item["first_seen_epoch"], current_epoch)
        item["last_seen_epoch"] = max(item["last_seen_epoch"], current_epoch)
        item["request_count"] += 1
        item["blocked_count"] += 1 if blocked else 0
        item["last_path"] = str(path or "")[:255]
        item["last_method"] = str(method or "")[:12]
        item["last_status"] = int(status_code or 0)

        monotonic_now = time.monotonic()
        should_flush = (
            force
            or len(_pending_ip_activity) >= 100
            or monotonic_now - _last_activity_flush_monotonic >= 5
        )
        if should_flush:
            batch = dict(_pending_ip_activity)
            _pending_ip_activity.clear()
            _last_activity_flush_monotonic = monotonic_now

    if batch:
        _flush_activity_batch(batch)


def flush_ip_activity():
    global _last_activity_flush_monotonic
    if not IP_LOGGING_ENABLED:
        return
    with _activity_lock:
        if not _pending_ip_activity:
            return
        batch = dict(_pending_ip_activity)
        _pending_ip_activity.clear()
        _last_activity_flush_monotonic = time.monotonic()
    _flush_activity_batch(batch)


def _load_blocked_ips(force=False):
    global _blocked_cache_monotonic, _blocked_ip_cache
    monotonic_now = time.monotonic()
    with _blocked_cache_lock:
        if not force and monotonic_now - _blocked_cache_monotonic < 5:
            return set(_blocked_ip_cache)
        init_visitor_stats_table()
        conn = get_db_connection()
        try:
            rows = conn.execute("SELECT ip_address FROM site_blocked_ips").fetchall()
        finally:
            conn.close()
        _blocked_ip_cache = {
            normalize_ip_address(_first_value(row))
            for row in rows
            if normalize_ip_address(_first_value(row))
        }
        _blocked_cache_monotonic = monotonic_now
        return set(_blocked_ip_cache)


def is_ip_blocked(ip_address):
    normalized = normalize_ip_address(ip_address)
    return bool(normalized and normalized in _load_blocked_ips())


def block_ip_address(ip_address, reason="", blocked_by=""):
    normalized = normalize_ip_address(ip_address)
    if not normalized:
        raise ValueError("IP 地址格式无效。")
    init_visitor_stats_table()
    marker = _marker()
    current_epoch = int(time.time())
    conn = get_db_connection()
    try:
        conn.execute(
            f"""
            INSERT INTO site_blocked_ips (
                ip_address,
                reason,
                blocked_at_epoch,
                blocked_by
            )
            VALUES ({marker}, {marker}, {marker}, {marker})
            ON CONFLICT(ip_address) DO UPDATE
            SET reason = excluded.reason,
                blocked_at_epoch = excluded.blocked_at_epoch,
                blocked_by = excluded.blocked_by
            """,
            (normalized, str(reason or "")[:500], current_epoch, str(blocked_by or "")[:120]),
        )
        conn.commit()
    finally:
        conn.close()
    _load_blocked_ips(force=True)
    return normalized


def unblock_ip_address(ip_address):
    normalized = normalize_ip_address(ip_address)
    if not normalized:
        raise ValueError("IP 地址格式无效。")
    init_visitor_stats_table()
    marker = _marker()
    conn = get_db_connection()
    try:
        conn.execute(
            f"DELETE FROM site_blocked_ips WHERE ip_address = {marker}",
            (normalized,),
        )
        conn.commit()
    finally:
        conn.close()
    _load_blocked_ips(force=True)
    return normalized


def _build_today_points(snapshot_rows, day_start_epoch, current_epoch):
    snapshot_map = {
        int(row["bucket_epoch"]): row
        for row in snapshot_rows
    }
    first_bucket = day_start_epoch - (day_start_epoch % SNAPSHOT_INTERVAL_SECONDS)
    last_bucket = current_epoch - (current_epoch % SNAPSHOT_INTERVAL_SECONDS)
    points = []
    bucket = first_bucket
    while bucket <= last_bucket:
        row = snapshot_map.get(bucket)
        points.append({
            "epoch": bucket,
            "label": _format_local_time(bucket, include_date=False),
            "online": int(row["online_visitors"]) if row else 0,
            "peak_online": int(row["peak_online_visitors"]) if row else 0,
        })
        bucket += SNAPSHOT_INTERVAL_SECONDS
    return points


def _aggregate_recent_ip_rows(rows, blocked_ips, show_full_ip):
    aggregated = {}
    for row in rows:
        item = _row_to_dict(row)
        ip_address = normalize_ip_address(item.get("ip_address"))
        if not ip_address:
            continue
        current = aggregated.get(ip_address)
        if current is None:
            current = {
                "ip_address": ip_address,
                "display_ip": ip_address if show_full_ip else mask_ip_address(ip_address),
                "first_seen_epoch": int(item["first_seen_epoch"]),
                "last_seen_epoch": int(item["last_seen_epoch"]),
                "request_count": 0,
                "blocked_count": 0,
                "last_path": item.get("last_path") or "",
                "last_method": item.get("last_method") or "",
                "last_status": int(item.get("last_status") or 0),
                "is_blocked": ip_address in blocked_ips,
            }
            aggregated[ip_address] = current
        current["first_seen_epoch"] = min(current["first_seen_epoch"], int(item["first_seen_epoch"]))
        current["last_seen_epoch"] = max(current["last_seen_epoch"], int(item["last_seen_epoch"]))
        current["request_count"] += int(item.get("request_count") or 0)
        current["blocked_count"] += int(item.get("blocked_count") or 0)

    result = sorted(aggregated.values(), key=lambda item: item["last_seen_epoch"], reverse=True)
    for item in result:
        item["first_seen_label"] = _format_local_time(item["first_seen_epoch"])
        item["last_seen_label"] = _format_local_time(item["last_seen_epoch"])
    return result[:100]


def get_admin_visitor_dashboard(
    show_full_ip=False,
    selected_epoch=None,
    now_epoch=None,
    daily_days=14,
):
    init_visitor_stats_table()
    flush_ip_activity()
    current_epoch = int(time.time() if now_epoch is None else now_epoch)
    marker = _marker()
    local_now = _local_datetime(current_epoch)
    day_start = datetime.combine(local_now.date(), datetime.min.time(), tzinfo=VISITOR_TIMEZONE)
    day_start_epoch = int(day_start.timestamp())
    day_key = local_now.date().isoformat()

    conn = get_db_connection()
    try:
        online, total = _query_current_stats(conn, current_epoch)
        today_visitors = _query_daily_visitors(conn, day_key)
        _upsert_snapshot(conn, current_epoch, online, total, today_visitors)
        _maybe_cleanup(conn, current_epoch)
        conn.commit()

        snapshot_rows = [
            _row_to_dict(row)
            for row in conn.execute(
                f"""
                SELECT *
                FROM site_visit_snapshots
                WHERE bucket_epoch >= {marker}
                  AND bucket_epoch <= {marker}
                ORDER BY bucket_epoch
                """,
                (day_start_epoch, current_epoch),
            ).fetchall()
        ]
        today_points = _build_today_points(snapshot_rows, day_start_epoch, current_epoch)
        peak_today = max((point["peak_online"] for point in today_points), default=0)

        hourly_map = {}
        for point in today_points:
            hour_label = _local_datetime(point["epoch"]).strftime("%H:00")
            hourly_map[hour_label] = max(hourly_map.get(hour_label, 0), point["peak_online"])
        hourly_peaks = [
            {"hour": hour, "peak": peak}
            for hour, peak in sorted(hourly_map.items())
        ]

        first_daily_date = local_now.date() - timedelta(days=daily_days - 1)
        daily_rows = conn.execute(
            f"""
            SELECT day_key, COUNT(*) AS unique_visitors
            FROM site_visitor_daily
            WHERE day_key >= {marker}
            GROUP BY day_key
            ORDER BY day_key
            """,
            (first_daily_date.isoformat(),),
        ).fetchall()
        daily_map = {
            str(_row_to_dict(row)["day_key"]): int(_row_to_dict(row)["unique_visitors"])
            for row in daily_rows
        }
        daily_visitors = []
        for day_offset in range(daily_days):
            date_value = first_daily_date + timedelta(days=day_offset)
            date_key = date_value.isoformat()
            daily_visitors.append({
                "day_key": date_key,
                "label": date_value.strftime("%m-%d"),
                "visitors": daily_map.get(date_key, 0),
            })

        blocked_rows = [
            _row_to_dict(row)
            for row in conn.execute(
                "SELECT * FROM site_blocked_ips ORDER BY blocked_at_epoch DESC"
            ).fetchall()
        ]
        blocked_ips = {
            normalize_ip_address(row.get("ip_address"))
            for row in blocked_rows
        }
        for row in blocked_rows:
            row["display_ip"] = (
                normalize_ip_address(row.get("ip_address"))
                if show_full_ip
                else mask_ip_address(row.get("ip_address"))
            )
            row["blocked_at_label"] = _format_local_time(row.get("blocked_at_epoch"))

        recent_cutoff = current_epoch - 24 * 60 * 60
        recent_ip_rows = conn.execute(
            f"""
            SELECT *
            FROM site_ip_activity
            WHERE last_seen_epoch >= {marker}
            ORDER BY bucket_epoch DESC
            LIMIT 2000
            """,
            (recent_cutoff,),
        ).fetchall()
        recent_ip_activity = _aggregate_recent_ip_rows(
            recent_ip_rows,
            blocked_ips,
            show_full_ip,
        )

        selected_snapshot = None
        if selected_epoch is not None:
            selected_bucket = int(selected_epoch) - (int(selected_epoch) % SNAPSHOT_INTERVAL_SECONDS)
            selected_row = conn.execute(
                f"""
                SELECT *
                FROM site_visit_snapshots
                WHERE bucket_epoch = {marker}
                """,
                (selected_bucket,),
            ).fetchone()
            selected_snapshot = _row_to_dict(selected_row) if selected_row else {
                "bucket_epoch": selected_bucket,
                "online_visitors": 0,
                "peak_online_visitors": 0,
                "total_visitors": 0,
                "daily_visitors": 0,
                "missing": True,
            }
            selected_snapshot["time_label"] = _format_local_time(selected_bucket)

        return {
            "online": online,
            "total": total,
            "today_visitors": today_visitors,
            "peak_today": peak_today,
            "today_points": today_points,
            "hourly_peaks": hourly_peaks,
            "daily_visitors": daily_visitors,
            "recent_ip_activity": recent_ip_activity,
            "blocked_ips": blocked_rows,
            "selected_snapshot": selected_snapshot,
            "show_full_ip": bool(show_full_ip),
            "ip_logging_enabled": IP_LOGGING_ENABLED,
            "ip_retention_days": IP_LOG_RETENTION_DAYS,
            "history_retention_days": HISTORY_RETENTION_DAYS,
            "timezone_name": str(VISITOR_TIMEZONE),
            "snapshot_interval_minutes": SNAPSHOT_INTERVAL_SECONDS // 60,
            "updated_at_label": _format_local_time(current_epoch),
        }
    finally:
        conn.close()
