def test_settings_require_sign_in(client):
    assert client.get("/api/settings").status_code == 401
    assert client.put("/api/settings", json={"leak_alerts": False}).status_code == 401


def test_defaults_then_update_persist(client, registered_user):
    headers, _, _ = registered_user
    body = client.get("/api/settings", headers=headers).get_json()
    assert body["settings"]["leak_alerts"] is True
    assert body["settings"]["weekly_summary"] is False

    r = client.put("/api/settings", json={"weekly_summary": True, "leak_alerts": False}, headers=headers)
    assert r.status_code == 200
    again = client.get("/api/settings", headers=headers).get_json()["settings"]
    assert again["weekly_summary"] is True and again["leak_alerts"] is False
    assert again["budget_alerts"] is True


def test_rejects_unknown_keys_and_non_booleans(client, registered_user):
    headers, _, _ = registered_user
    assert client.put("/api/settings", json={"admin": True}, headers=headers).status_code == 400
    assert client.put("/api/settings", json={"leak_alerts": "yes"}, headers=headers).status_code == 400
    assert client.put("/api/settings", json=["x"], headers=headers).status_code == 400


def test_settings_are_private_per_user(client, registered_user):
    headers, _, _ = registered_user
    client.put("/api/settings", json={"weekly_summary": True}, headers=headers)
    other = client.post("/api/auth/register", json={"email": "other-settings@example.com", "password": "password123"}).get_json()
    other_headers = {"Authorization": f"Bearer {other['token']}"}
    assert client.get("/api/settings", headers=other_headers).get_json()["settings"]["weekly_summary"] is False


def test_deleting_account_removes_settings(client, registered_user):
    import storage
    headers, user_id, _ = registered_user
    client.put("/api/settings", json={"weekly_summary": True}, headers=headers)
    assert storage.get_settings(user_id) is not None
    assert client.delete("/api/account", headers=headers).status_code == 200
    assert storage.get_settings(user_id) is None