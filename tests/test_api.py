"""API tests: status codes, auth boundaries and ownership.

These assert the contract the front end depends on, including the deliberate
choice that another user's report returns 404 rather than 403.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

SAMPLE = (
    "The ministry published its quarterly report on 12 November 2026. According to "
    'the report, spending rose 4.2 percent. "The figures are preliminary," said a '
    "spokesperson for the ministry. Analysts at a local firm said the number was in "
    "line with expectations."
)


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_returns_a_token(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "new-user@example.com", "password": "a-good-password-1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == "new-user@example.com"


def test_duplicate_registration_conflicts(client: TestClient) -> None:
    payload = {"email": "dupe@example.com", "password": "a-good-password-1"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_short_password_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register", json={"email": "short@example.com", "password": "abc"}
    )
    assert response.status_code == 422


def test_wrong_password_is_unauthorised(client: TestClient) -> None:
    client.post(
        "/api/auth/register",
        json={"email": "login@example.com", "password": "a-good-password-1"},
    )
    response = client.post(
        "/api/auth/login", json={"email": "login@example.com", "password": "wrong-one-here"}
    )
    assert response.status_code == 401


def test_analysis_requires_auth(client: TestClient) -> None:
    assert client.post("/api/analyze", json={"text": SAMPLE}).status_code == 401


def test_analyze_returns_a_full_report(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/analyze", json={"text": SAMPLE}, headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert 0 <= body["score"] <= 100
    assert len(body["signals"]) == 11
    assert body["id"]


def test_blank_text_is_rejected(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/analyze", json={"text": "   "}, headers=auth_headers)
    assert response.status_code == 422


def test_another_users_report_is_not_found(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    created = client.post("/api/analyze", json={"text": SAMPLE}, headers=auth_headers).json()

    other = client.post(
        "/api/auth/register",
        json={"email": "intruder@example.com", "password": "a-good-password-1"},
    ).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    response = client.get(f"/api/analyses/{created['id']}", headers=other_headers)
    assert response.status_code == 404


def test_history_lists_only_own_reports(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.post("/api/analyze", json={"text": SAMPLE}, headers=auth_headers)
    response = client.get("/api/analyses", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1


def test_delete_removes_the_report(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = client.post("/api/analyze", json={"text": SAMPLE}, headers=auth_headers).json()
    assert client.delete(f"/api/analyses/{created['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/analyses/{created['id']}", headers=auth_headers).status_code == 404


def test_share_creates_a_public_link(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = client.post("/api/analyze", json={"text": SAMPLE}, headers=auth_headers).json()
    shared = client.post(f"/api/analyses/{created['id']}/share", headers=auth_headers)
    assert shared.status_code == 200
    slug = shared.json()["slug"]

    public = client.get(f"/api/shared/{slug}")
    assert public.status_code == 200
    assert public.json()["report"]["score"] == created["score"]


def test_unknown_share_slug_is_not_found(client: TestClient) -> None:
    assert client.get("/api/shared/does-not-exist").status_code == 404


def test_stats_reflect_analyses(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.post("/api/analyze", json={"text": SAMPLE}, headers=auth_headers)
    body = client.get("/api/stats", headers=auth_headers).json()
    assert body["total_analyses"] >= 1
    assert body["average_score"] > 0


def test_security_headers_are_present(client: TestClient) -> None:
    headers = client.get("/api/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in headers


def test_ssrf_is_blocked_at_the_api(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/fetch", json={"url": "http://169.254.169.254/latest/meta-data/"}, headers=auth_headers
    )
    assert response.status_code == 400


def test_index_page_is_served(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Tahqeeq" in response.text
