"""HTTP-level integration tests, through the real Flask app and routing,
as opposed to calling the auth.py/profiles.py functions directly like the
other test files do."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["storage"] == "sqlite"
    assert body["profiles"] >= 1


def test_anonymous_can_read_demo_household(client):
    for path in ["/api/dashboard", "/api/anomalies", "/api/forecast", "/api/score", "/api/savings"]:
        r = client.get(path)
        assert r.status_code == 200, (path, r.get_json())


def test_unknown_profile_is_404(client):
    r = client.get("/api/dashboard?profile=does-not-exist")
    assert r.status_code == 404


def test_creating_a_profile_requires_auth(client):
    r = client.post("/api/profiles", json={"name": "x", "lat": 1, "lon": 1, "household_size": 4, "tier1_limit_gal": 4000})
    assert r.status_code == 401


def test_signed_in_user_can_create_view_and_delete_own_profile(client, registered_user):
    headers, user_id, _ = registered_user

    r = client.post("/api/profiles", json={
        "name": "Integration test house", "lat": 34.0, "lon": -118.2,
        "household_size": 3, "tier1_limit_gal": 4000,
    }, headers=headers)
    assert r.status_code == 201
    profile = r.get_json()
    assert profile["owner_id"] == user_id

    # visible to its owner
    names = [p["name"] for p in client.get("/api/profiles", headers=headers).get_json()]
    assert "Integration test house" in names

    # not visible to an anonymous caller
    anon_names = [p["name"] for p in client.get("/api/profiles").get_json()]
    assert "Integration test house" not in anon_names

    # data endpoints work for the owner
    r = client.get(f"/api/dashboard?profile={profile['id']}", headers=headers)
    assert r.status_code == 200

    # data endpoints are forbidden for anonymous callers
    r = client.get(f"/api/dashboard?profile={profile['id']}")
    assert r.status_code == 403

    # owner can delete
    r = client.delete(f"/api/profiles/{profile['id']}", headers=headers)
    assert r.status_code == 200


def test_bad_json_body_does_not_crash_the_server(client):
    r = client.post("/api/profiles", data="not json", content_type="application/json", headers={"Authorization": "Bearer garbage"})
    assert r.status_code in (400, 401)
    assert "error" in r.get_json()


def test_ask_requires_a_question(client):
    r = client.post("/api/ask", json={})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_ask_falls_back_without_an_api_key(client):
    r = client.post("/api/ask", json={"question": "why is my bill high?"})
    assert r.status_code == 200
    body = r.get_json()
    assert "offline" in body["source"]


def test_civic_report_returns_a_draft(client):
    r = client.post("/api/civic-report", json={"category": "fountain", "lat": 1, "lon": 2})
    assert r.status_code == 200
    assert "report_id" in r.get_json()


def test_cnn_labels_available(client):
    r = client.get("/api/cnn-labels")
    assert r.status_code == 200
    assert "fountain" in r.get_json()


def test_dashboard_includes_seven_day_trend(client):
    r = client.get("/api/dashboard")
    body = r.get_json()
    assert len(body["last_7_days_gallons"]) == 7


def test_anomalies_days_filter_narrows_results(client):
    full = client.get("/api/anomalies").get_json()
    narrowed = client.get("/api/anomalies?days=7").get_json()
    assert narrowed["anomalies_found"] <= full["anomalies_found"]
    assert len(narrowed["weekly_counts"]) == 9


def test_anomalies_confirmed_only_filter(client):
    full = client.get("/api/anomalies").get_json()
    confirmed = client.get("/api/anomalies?confirmed_only=true").get_json()
    assert confirmed["anomalies_found"] <= full["anomalies_found"]
    assert all(a["was_injected_leak"] for a in confirmed["anomalies"])


def test_deleting_someone_elses_profile_is_forbidden(client, registered_user):
    headers_a, _, _ = registered_user
    r = client.post("/api/profiles", json={
        "name": "Owner A's house", "lat": 1, "lon": 1, "household_size": 4, "tier1_limit_gal": 4000,
    }, headers=headers_a)
    profile_id = r.get_json()["id"]

    r = client.post("/api/auth/register", json={"email": "second-user-test@example.com", "password": "password123"})
    headers_b = {"Authorization": f"Bearer {r.get_json()['token']}"}

    r = client.delete(f"/api/profiles/{profile_id}", headers=headers_b)
    assert r.status_code == 403
