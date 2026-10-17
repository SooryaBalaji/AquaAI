import sqlite3

import profiles
import storage

NEW = {"name": "Edit me", "lat": 37.7, "lon": -121.9, "household_size": 3, "tier1_limit_gal": 4500, "place": "Dublin, California"}


def make(client, headers):
    r = client.post("/api/profiles", json=NEW, headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def test_place_is_stored_on_create(client, registered_user):
    headers, _, _ = registered_user
    assert make(client, headers)["place"] == "Dublin, California"


def test_owner_can_edit_fields(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)["id"]
    r = client.patch(f"/api/profiles/{pid}", json={"name": "Renamed", "tier1_limit_gal": 6000}, headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body["name"] == "Renamed" and body["tier1_limit_gal"] == 6000 and body["household_size"] == 3
    assert "seed" not in body
    listed = [p for p in client.get("/api/profiles", headers=headers).get_json() if p["id"] == pid][0]
    assert listed["name"] == "Renamed"


def test_changing_household_size_rebuilds_usage_data(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)["id"]
    before = sum(r["gallons"] for r in profiles.get_household_data(pid)["readings"])
    client.patch(f"/api/profiles/{pid}", json={"household_size": 8}, headers=headers)
    after = sum(r["gallons"] for r in profiles.get_household_data(pid)["readings"])
    assert after > before


def test_edit_validates_input(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)["id"]
    for bad in ({"name": ""}, {"household_size": 0}, {"tier1_limit_gal": 5}, {"lat": 999}, {}):
        assert client.patch(f"/api/profiles/{pid}", json=bad, headers=headers).status_code == 400, bad


def test_cannot_edit_someone_elses_or_the_demo_household(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)["id"]
    other = client.post("/api/auth/register", json={"email": "editor-other@example.com", "password": "password123"}).get_json()
    other_headers = {"Authorization": f"Bearer {other['token']}"}
    assert client.patch(f"/api/profiles/{pid}", json={"name": "Hacked"}, headers=other_headers).status_code == 403
    assert client.patch("/api/profiles/demo", json={"name": "Hacked"}, headers=headers).status_code == 403
    assert client.patch(f"/api/profiles/{pid}", json={"name": "x"}).status_code == 401


def test_old_sqlite_files_gain_the_place_column(tmp_path, monkeypatch):
    old = tmp_path / "old.db"
    with sqlite3.connect(old) as conn:
        conn.execute("""CREATE TABLE profiles (id TEXT PRIMARY KEY, owner_id TEXT, name TEXT NOT NULL, lat REAL NOT NULL,
                        lon REAL NOT NULL, household_size INTEGER NOT NULL, tier1_limit_gal REAL NOT NULL, seed INTEGER NOT NULL)""")
        conn.execute("INSERT INTO profiles VALUES ('a', 'u', 'Old house', 1, 2, 3, 4500, 7)")
    monkeypatch.setattr(storage, "SQLITE_PATH", str(old))
    storage._init_sqlite()
    with sqlite3.connect(old) as conn:
        assert "place" in [r[1] for r in conn.execute("PRAGMA table_info(profiles)")]
    assert storage.get_profile("a")["place"] is None