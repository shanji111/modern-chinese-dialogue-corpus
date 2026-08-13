from services.anti_scraping_service import AntiScrapingGuard, RatePolicy


def build_guard(limit=3):
    policies = {
        name: RatePolicy(name, limit, 60, 120)
        for name in ("general", "search", "resonance", "context", "export", "audio", "login")
    }
    return AntiScrapingGuard(
        policies=policies,
        enabled=True,
        max_search_page=10,
        honeypot_penalty_seconds=600,
    )


def request(guard, **overrides):
    values = {
        "path": "/search",
        "method": "GET",
        "client_ip": "203.0.113.10",
        "visitor_id": "visitor-a",
        "user_agent": "Mozilla/5.0",
        "fetch_site": "same-origin",
        "requested_with": "fetch",
        "page": 1,
        "now": 1000,
    }
    values.update(overrides)
    return guard.evaluate(**values)


def test_rate_limit_applies_a_temporary_block():
    guard = build_guard(limit=3)

    assert request(guard, now=1000).allowed
    assert request(guard, now=1001).allowed
    third = request(guard, now=1002)
    assert third.allowed
    assert third.remaining == 0

    blocked = request(guard, now=1003)
    assert not blocked.allowed
    assert blocked.status_code == 429
    assert blocked.reason == "rate_limit"
    assert blocked.retry_after == 120

    still_blocked = request(guard, path="/", now=1060)
    assert not still_blocked.allowed
    assert still_blocked.reason == "temporary_block"


def test_cookie_identity_catches_ip_rotation():
    guard = build_guard(limit=2)

    assert request(guard, client_ip="203.0.113.1", now=1000).allowed
    assert request(guard, client_ip="203.0.113.2", now=1001).allowed
    blocked = request(guard, client_ip="203.0.113.3", now=1002)

    assert not blocked.allowed
    assert blocked.status_code == 429


def test_ip_identity_catches_cookie_rotation():
    guard = build_guard(limit=2)

    assert request(guard, visitor_id="visitor-a", now=1000).allowed
    assert request(guard, visitor_id="visitor-b", now=1001).allowed
    blocked = request(guard, visitor_id="visitor-c", now=1002)

    assert not blocked.allowed
    assert blocked.status_code == 429


def test_sensitive_api_requires_first_party_fetch_signal():
    guard = build_guard()

    blocked = request(
        guard,
        path="/api/resonance",
        requested_with="",
    )

    assert not blocked.allowed
    assert blocked.status_code == 403
    assert blocked.reason == "missing_fetch_signal"


def test_known_automation_user_agent_is_rejected_on_data_route():
    guard = build_guard()

    blocked = request(guard, user_agent="python-requests/2.32")

    assert not blocked.allowed
    assert blocked.status_code == 403
    assert blocked.reason == "automation_client"


def test_deep_pagination_is_rejected():
    guard = build_guard()

    blocked = request(guard, page=11)

    assert not blocked.allowed
    assert blocked.status_code == 403
    assert blocked.reason == "deep_pagination"


def test_honeypot_triggers_longer_temporary_block():
    guard = build_guard()

    trapped = request(guard, path="/corpus-export-all")
    assert not trapped.allowed
    assert trapped.status_code == 403
    assert trapped.reason == "honeypot"

    blocked = request(guard, path="/", now=1100)
    assert not blocked.allowed
    assert blocked.retry_after == 500


def test_admin_and_trusted_ip_bypass_guard():
    guard = build_guard(limit=1)
    guard.trusted_ips = frozenset({"203.0.113.99"})

    assert request(guard, is_admin=True, user_agent="curl/8").allowed
    assert request(guard, client_ip="203.0.113.99", user_agent="curl/8").allowed
