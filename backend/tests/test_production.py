import pytest

import auth
import checks
import profiles
from conftest import aquaai_app


@pytest.fixture
def firebase_mode(monkeypatch):
    tokens = {
        "verified-token": {"uid": "fb-user-1", "email": "a@example.com", "email_verified": True},
        "unverified-token": {"uid": "fb-user-2", "email": "b@example.com", "email_verified": False},
        "other-token": {"uid": "fb-user-3", "email": "c@example.com", "email_verified": True},
    }

    def fake_verify(token):
        if token not in tokens:
            raise ValueError("bad token")
        return tokens[token]

    monkeypatch.setattr(auth, "_PROVIDER", "firebase")
    monkeypatch.setattr(auth, "_firebase_verify", fake_verify)
    monkeypatch.setenv("FIREBASE_WEB_API_KEY", "web-key")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "demo-project")


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


NEW_HOUSEHOLD = {"name": "Test house", "lat": 37.3, "lon": -121.9, "household_size": 3, "tier1_limit_gal": 4500}


def test_firebase_token_identifies_user(client, firebase_mode):
    r = client.get("/api/auth/me", headers=bearer("verified-token"))
    assert r.status_code == 200
    assert r.get_json()["user"] == {"id": "fb-user-1", "email": "a@example.com", "email_verified": True}


def test_firebase_rejects_unknown_token(client, firebase_mode):
    assert client.get("/api/auth/me", headers=bearer("forged")).status_code == 401


def test_firebase_mode_disables_local_register_and_login(client, firebase_mode):
    assert client.post("/api/auth/register", json={"email": "x@example.com", "password": "password123"}).status_code == 404
    assert client.post("/api/auth/login", json={"email": "x@example.com", "password": "password123"}).status_code == 404


def test_auth_config_exposes_only_public_firebase_settings(client, firebase_mode):
    body = client.get("/api/auth/config").get_json()
    assert body["provider"] == "firebase"
    assert body["firebase"]["projectId"] == "demo-project"
    assert body["firebase"]["authDomain"] == "demo-project.firebaseapp.com"
    assert set(body["firebase"]) == {"apiKey", "authDomain", "projectId", "appId"}


def test_unverified_email_cannot_create_household(client, firebase_mode):
    r = client.post("/api/profiles", json=NEW_HOUSEHOLD, headers=bearer("unverified-token"))
    assert r.status_code == 403
    assert r.get_json()["code"] == "email_not_verified"


def test_verified_user_owns_household_and_others_cannot_read_or_delete_it(client, firebase_mode):
    created = client.post("/api/profiles", json=NEW_HOUSEHOLD, headers=bearer("verified-token"))
    assert created.status_code == 201
    pid = created.get_json()["id"]
    assert created.get_json()["owner_id"] == "fb-user-1"

    assert client.get(f"/api/dashboard?profile={pid}", headers=bearer("verified-token")).status_code == 200
    assert client.get(f"/api/dashboard?profile={pid}", headers=bearer("other-token")).status_code == 403
    assert client.get(f"/api/dashboard?profile={pid}").status_code == 403
    assert client.delete(f"/api/profiles/{pid}", headers=bearer("other-token")).status_code == 403
    assert client.delete(f"/api/profiles/{pid}", headers=bearer("verified-token")).status_code == 200


def test_household_cap_per_user(client, registered_user):
    headers, _, _ = registered_user
    for _ in range(profiles.MAX_PROFILES_PER_USER):
        assert client.post("/api/profiles", json=NEW_HOUSEHOLD, headers=headers).status_code == 201
    r = client.post("/api/profiles", json=NEW_HOUSEHOLD, headers=headers)
    assert r.status_code == 400
    assert "up to" in r.get_json()["error"]


def test_production_checks_flag_unsafe_setup(monkeypatch):
    monkeypatch.delenv("ALLOW_LOCAL_AUTH", raising=False)
    monkeypatch.delenv("ALLOW_SQLITE_IN_PRODUCTION", raising=False)
    problems = checks.production_problems("local", "sqlite", auth.DEFAULT_SECRET)
    assert len(problems) == 3


def test_production_checks_pass_for_firebase_setup(monkeypatch):
    monkeypatch.setenv("FIREBASE_WEB_API_KEY", "k")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "p")
    assert checks.production_problems("firebase", "firestore", "anything") == []


def test_production_checks_require_firebase_settings(monkeypatch):
    monkeypatch.delenv("FIREBASE_WEB_API_KEY", raising=False)
    monkeypatch.delenv("FIREBASE_PROJECT_ID", raising=False)
    assert len(checks.production_problems("firebase", "firestore", "x")) == 2


def test_security_headers_on_pages_and_api(client):
    page = client.get("/")
    assert page.status_code == 200
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    assert page.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]
    api = client.get("/api/profiles")
    assert api.headers["Cache-Control"] == "no-store"
    assert "Content-Security-Policy" not in api.headers


def test_healthz(client):
    body = client.get("/healthz").get_json()
    assert body["status"] == "ok"
    assert body["storage"] == "sqlite"


def test_oversized_body_rejected_as_json(client):
    r = client.post("/api/ask", data="x" * (70 * 1024), content_type="application/json")
    assert r.status_code == 413
    assert "error" in r.get_json()


def test_overlong_question_rejected(client):
    r = client.post("/api/ask", json={"question": "a" * 501})
    assert r.status_code == 400


def test_ask_is_rate_limited(client):
    limiter = aquaai_app.limiter
    limiter.reset()
    limiter.enabled = True
    try:
        codes = [client.post("/api/ask", json={"question": "hello"}).status_code for _ in range(10)]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert 429 in codes
    assert codes[0] == 200


def test_local_account_deletion_removes_households_and_login(client, registered_user, unique_email):
    headers, _, email = registered_user
    pid = client.post("/api/profiles", json=NEW_HOUSEHOLD, headers=headers).get_json()["id"]
    r = client.delete("/api/account", headers=headers)
    assert r.status_code == 200
    assert r.get_json()["households_removed"] == 1
    assert client.get(f"/api/dashboard?profile={pid}").status_code == 404
    assert client.post("/api/auth/login", json={"email": email, "password": "password123"}).status_code == 401


def test_account_deletion_requires_sign_in(client):
    assert client.delete("/api/account").status_code == 401


def test_firebase_account_deletion_calls_firebase(client, firebase_mode, monkeypatch):
    deleted = []
    monkeypatch.setattr(auth, "_firebase_delete", deleted.append)
    created = client.post("/api/profiles", json=NEW_HOUSEHOLD, headers=bearer("other-token"))
    assert created.status_code == 201
    r = client.delete("/api/account", headers=bearer("other-token"))
    assert r.status_code == 200
    assert deleted == ["fb-user-3"]
