import hashlib
import os
import re
import threading
import time
from collections import deque
from dataclasses import dataclass


def _read_bool(name, default=True):
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _read_int(name, default, minimum=1, maximum=1_000_000):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


@dataclass(frozen=True)
class RatePolicy:
    name: str
    limit: int
    window_seconds: int
    penalty_seconds: int


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    policy: str = ""
    reason: str = ""
    status_code: int = 200
    retry_after: int = 0
    limit: int = 0
    remaining: int = 0
    reset_after: int = 0


BOT_USER_AGENT_PATTERN = re.compile(
    r"(?:python-requests|python-urllib|curl/|wget/|scrapy|go-http-client|"
    r"apache-httpclient|libwww-perl|httpx/|aiohttp/|headlesschrome)",
    re.IGNORECASE,
)

HONEYPOT_PATHS = frozenset({
    "/api/internal/corpus-dump",
    "/corpus-export-all",
})

FETCH_ONLY_PATHS = frozenset({
    "/api/search/count",
    "/api/resonance",
    "/resonance/data",
})

PROTECTED_PREFIXES = (
    "/api/diagraph/",
    "/api/resonance",
    "/resonance/context/",
    "/resonance/data",
)


def _default_policies():
    return {
        "general": RatePolicy(
            "general",
            _read_int("ANTI_SCRAPE_GENERAL_REQUESTS", 240),
            60,
            _read_int("ANTI_SCRAPE_GENERAL_PENALTY_SECONDS", 60),
        ),
        "search": RatePolicy(
            "search",
            _read_int("ANTI_SCRAPE_SEARCH_REQUESTS", 40),
            60,
            _read_int("ANTI_SCRAPE_SEARCH_PENALTY_SECONDS", 120),
        ),
        "resonance": RatePolicy(
            "resonance",
            _read_int("ANTI_SCRAPE_RESONANCE_REQUESTS", 24),
            60,
            _read_int("ANTI_SCRAPE_RESONANCE_PENALTY_SECONDS", 180),
        ),
        "context": RatePolicy(
            "context",
            _read_int("ANTI_SCRAPE_CONTEXT_REQUESTS", 36),
            60,
            _read_int("ANTI_SCRAPE_CONTEXT_PENALTY_SECONDS", 180),
        ),
        "export": RatePolicy(
            "export",
            _read_int("ANTI_SCRAPE_EXPORT_REQUESTS", 6),
            10 * 60,
            _read_int("ANTI_SCRAPE_EXPORT_PENALTY_SECONDS", 15 * 60),
        ),
        "audio": RatePolicy(
            "audio",
            _read_int("ANTI_SCRAPE_AUDIO_REQUESTS", 30),
            60,
            _read_int("ANTI_SCRAPE_AUDIO_PENALTY_SECONDS", 5 * 60),
        ),
        "login": RatePolicy(
            "login",
            _read_int("ANTI_SCRAPE_LOGIN_REQUESTS", 10),
            15 * 60,
            _read_int("ANTI_SCRAPE_LOGIN_PENALTY_SECONDS", 15 * 60),
        ),
    }


class AntiScrapingGuard:
    """Small application-layer guard; edge/WAF rate limiting is still required.

    State is intentionally short-lived and in memory. Each identity is counted by
    IP and, when present, by a hashed anonymous visitor cookie. This catches both
    many sessions behind one address and one session rotating through addresses.
    """

    def __init__(
        self,
        policies=None,
        enabled=True,
        max_search_page=100,
        honeypot_penalty_seconds=24 * 60 * 60,
        trusted_ips=None,
    ):
        self.enabled = bool(enabled)
        self.policies = dict(policies or _default_policies())
        self.max_search_page = max(0, int(max_search_page))
        self.honeypot_penalty_seconds = max(60, int(honeypot_penalty_seconds))
        self.trusted_ips = frozenset(trusted_ips or ())
        self._lock = threading.Lock()
        self._buckets = {}
        self._blocked_until = {}
        self._block_reasons = {}
        self._last_cleanup = 0.0
        self._blocked_total = 0

    @classmethod
    def from_environment(cls):
        trusted_ips = {
            item.strip()
            for item in os.getenv("ANTI_SCRAPE_TRUSTED_IPS", "").split(",")
            if item.strip()
        }
        return cls(
            enabled=_read_bool("ANTI_SCRAPING_ENABLED", True),
            max_search_page=_read_int("ANTI_SCRAPE_MAX_SEARCH_PAGE", 100, 0, 100_000),
            honeypot_penalty_seconds=_read_int(
                "ANTI_SCRAPE_HONEYPOT_PENALTY_SECONDS", 24 * 60 * 60
            ),
            trusted_ips=trusted_ips,
        )

    @staticmethod
    def _identity_keys(client_ip, visitor_id):
        keys = []
        if client_ip:
            keys.append(f"ip:{client_ip}")
        if visitor_id:
            visitor_hash = hashlib.sha256(visitor_id.encode("utf-8")).hexdigest()[:24]
            keys.append(f"visitor:{visitor_hash}")
        return tuple(keys or ("anonymous",))

    @staticmethod
    def _policy_name(path, method):
        if path == "/admin/login" and method == "POST":
            return "login"
        if path in {"/api/diagraph/export_csv", "/api/diagraph/export_excel"}:
            return "export"
        if path.startswith("/audio/") or path.startswith("/corpus/audio/"):
            return "audio"
        if path in {"/api/resonance", "/resonance/data"}:
            return "resonance"
        if path.startswith("/api/diagraph/") or path.startswith("/resonance/context/"):
            return "context"
        if path in {"/search", "/browse", "/api/search/count"}:
            return "search"
        return "general"

    @staticmethod
    def _is_data_path(path):
        return (
            path in {"/search", "/browse"}
            or path.startswith("/audio/")
            or path.startswith("/corpus/audio/")
            or any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES)
            or path in FETCH_ONLY_PATHS
        )

    @staticmethod
    def _is_fetch_only(path):
        return path in FETCH_ONLY_PATHS or (
            path.startswith("/api/diagraph/")
            and path not in {"/api/diagraph/export_csv", "/api/diagraph/export_excel"}
        ) or path.startswith("/resonance/context/")

    def _cleanup(self, now):
        if now - self._last_cleanup < 60:
            return
        longest_window = max(policy.window_seconds for policy in self.policies.values())
        for key, bucket in list(self._buckets.items()):
            cutoff = now - longest_window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if not bucket:
                self._buckets.pop(key, None)
        for key, blocked_until in list(self._blocked_until.items()):
            if blocked_until <= now:
                self._blocked_until.pop(key, None)
                self._block_reasons.pop(key, None)
        self._last_cleanup = now

    def _block(self, identity_keys, until, reason):
        for identity in identity_keys:
            self._blocked_until[identity] = max(self._blocked_until.get(identity, 0), until)
            self._block_reasons[identity] = reason
        self._blocked_total += 1

    def evaluate(
        self,
        *,
        path,
        method="GET",
        client_ip="",
        visitor_id="",
        user_agent="",
        fetch_site="",
        requested_with="",
        page=1,
        is_admin=False,
        now=None,
    ):
        if not self.enabled or is_admin or client_ip in self.trusted_ips:
            return GuardDecision(True)
        if method == "OPTIONS" or path.startswith("/static/") or path == "/api/visitor-stats":
            return GuardDecision(True)

        current = float(time.time() if now is None else now)
        identity_keys = self._identity_keys(client_ip, visitor_id)
        policy = self.policies[self._policy_name(path, method)]

        with self._lock:
            self._cleanup(current)

            active_blocks = [
                self._blocked_until.get(identity, 0)
                for identity in identity_keys
                if self._blocked_until.get(identity, 0) > current
            ]
            if active_blocks:
                retry_after = max(1, int(max(active_blocks) - current + 0.999))
                return GuardDecision(
                    False, policy.name, "temporary_block", 429, retry_after,
                    policy.limit, 0, retry_after,
                )

            if path in HONEYPOT_PATHS:
                self._block(
                    identity_keys,
                    current + self.honeypot_penalty_seconds,
                    "honeypot",
                )
                return GuardDecision(
                    False, "honeypot", "honeypot", 403,
                    self.honeypot_penalty_seconds, 0, 0,
                    self.honeypot_penalty_seconds,
                )

            if fetch_site.lower() == "cross-site" and self._is_data_path(path):
                self._block(identity_keys, current + 10 * 60, "cross_site_data_request")
                return GuardDecision(False, policy.name, "cross_site", 403, 600)

            if self._is_fetch_only(path) and requested_with.lower() != "fetch":
                self._block(identity_keys, current + 5 * 60, "missing_browser_fetch_signal")
                return GuardDecision(False, policy.name, "missing_fetch_signal", 403, 300)

            if self._is_data_path(path) and (
                not user_agent.strip() or BOT_USER_AGENT_PATTERN.search(user_agent)
            ):
                self._block(identity_keys, current + 30 * 60, "known_automation_client")
                return GuardDecision(False, policy.name, "automation_client", 403, 1800)

            if (
                self.max_search_page
                and path in {"/search", "/browse"}
                and int(page or 1) > self.max_search_page
            ):
                return GuardDecision(False, "search", "deep_pagination", 403)

            most_used = 0
            reset_after = policy.window_seconds
            for identity in identity_keys:
                bucket_key = (identity, policy.name)
                bucket = self._buckets.setdefault(bucket_key, deque())
                cutoff = current - policy.window_seconds
                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()
                if len(bucket) >= policy.limit:
                    retry_after = max(1, int(bucket[0] + policy.window_seconds - current + 0.999))
                    penalty = max(policy.penalty_seconds, retry_after)
                    self._block(identity_keys, current + penalty, f"rate:{policy.name}")
                    return GuardDecision(
                        False, policy.name, "rate_limit", 429, penalty,
                        policy.limit, 0, penalty,
                    )
                bucket.append(current)
                most_used = max(most_used, len(bucket))
                reset_after = min(
                    reset_after,
                    max(1, int(bucket[0] + policy.window_seconds - current + 0.999)),
                )

            return GuardDecision(
                True,
                policy.name,
                limit=policy.limit,
                remaining=max(0, policy.limit - most_used),
                reset_after=reset_after,
            )

    def status(self, now=None):
        current = float(time.time() if now is None else now)
        with self._lock:
            self._cleanup(current)
            return {
                "enabled": self.enabled,
                "active_temporary_blocks": sum(
                    1 for until in self._blocked_until.values() if until > current
                ),
                "blocked_total": self._blocked_total,
                "max_search_page": self.max_search_page,
                "policies": {
                    name: {
                        "limit": policy.limit,
                        "window_seconds": policy.window_seconds,
                        "penalty_seconds": policy.penalty_seconds,
                    }
                    for name, policy in self.policies.items()
                },
            }

    def reset(self):
        with self._lock:
            self._buckets.clear()
            self._blocked_until.clear()
            self._block_reasons.clear()
            self._blocked_total = 0
            self._last_cleanup = 0.0


anti_scraping_guard = AntiScrapingGuard.from_environment()


def evaluate_request(**kwargs):
    return anti_scraping_guard.evaluate(**kwargs)


def get_anti_scraping_status():
    return anti_scraping_guard.status()
