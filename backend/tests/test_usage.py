from datetime import date, datetime, timedelta, timezone

import pytest

import storage
import weather

TODAY = datetime.now(timezone.utc).date()
NEW = {"name": "Usage house", "lat": 37.7, "lon": -121.9, "household_size": 3, "tier1_limit_gal": 4500, "place": "Dublin, California"}


@pytest.fixture(autouse=True)
def offline_weather(monkeypatch):
    monkeypatch.setattr(weather, "fetch_noaa_forecast", lambda lat, lon: {"source": "test", "daily_highs": [80] * 7})


def make(client, headers):
    r = client.post("/api/profiles", json=NEW, headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]


def q(pid, extra=""):
    return f"?profile={pid}&today={TODAY.isoformat()}{extra}"


def put(client, headers, pid, entries):
    return client.put("/api/usage" + q(pid), json={"entries": entries}, headers=headers)


def test_new_household_is_all_zeros(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)
    d = client.get("/api/dashboard" + q(pid), headers=headers).get_json()
    assert d["has_data"] is False and d["today_total_gallons"] == 0
    assert d["last_7_days_gallons"] == [0] * 7 and d["hourly_breakdown"] is None
    f = client.get("/api/forecast" + q(pid), headers=headers).get_json()
    assert f["month_used_so_far"] == 0 and f["bill_estimate_dollars"] == 0 and f["tier_breach_day_of_month"] is None
    assert f["has_data"] is False
    s = client.get("/api/score" + q(pid), headers=headers).get_json()
    assert s["score"] is None and s["needs_more_data"] is True
    sv = client.get("/api/savings" + q(pid), headers=headers).get_json()
    assert sv["gallons_saved_projected_year"] == 0 and sv["badges"] == []
    a = client.get("/api/anomalies" + q(pid), headers=headers).get_json()
    assert a["anomalies_found"] == 0 and a["source"] == "manual" and a["days_checked"] == 0


def test_entered_usage_drives_the_numbers(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)
    entries = [{"date": (TODAY - timedelta(days=i)).isoformat(), "gallons": 100 + i} for i in range(10)]
    assert put(client, headers, pid, entries).get_json() == {"saved": 10}
    d = client.get("/api/dashboard" + q(pid), headers=headers).get_json()
    assert d["has_data"] is True and d["today_total_gallons"] == 100 and d["days_logged"] == 10
    assert d["last_7_days_gallons"][-1] == 100 and d["last_7_days_gallons"][0] == 106
    f = client.get("/api/forecast" + q(pid), headers=headers).get_json()
    assert f["month_used_so_far"] == sum(100 + i for i in range(10)) and f["avg_daily_gallons"] == pytest.approx(104.5)
    s = client.get("/api/score" + q(pid), headers=headers).get_json()
    assert s["score"] == 100 and s["breakdown"]["leak_free_usage"] is None
    assert client.get("/api/savings" + q(pid), headers=headers).get_json()["gallons_saved_projected_year"] > 0


def test_same_day_is_replaced_and_history_lists_newest_first(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)
    day = TODAY.isoformat()
    put(client, headers, pid, [{"date": day, "gallons": 50}, {"date": "2026-10-01", "gallons": 70}])
    put(client, headers, pid, [{"date": day, "gallons": 55.5}])
    h = client.get("/api/usage" + q(pid), headers=headers).get_json()
    assert h["count"] == 2 and h["entries"][0] == {"date": day, "gallons": 55.5}


def test_delete_one_day_and_clear_all(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)
    put(client, headers, pid, [{"date": "2026-10-01", "gallons": 70}, {"date": "2026-10-02", "gallons": 80}])
    assert client.delete("/api/usage" + q(pid, "&date=2026-10-01"), headers=headers).status_code == 200
    assert client.get("/api/usage" + q(pid), headers=headers).get_json()["count"] == 1
    assert client.delete("/api/usage" + q(pid, "&all=true"), headers=headers).status_code == 200
    assert client.get("/api/usage" + q(pid), headers=headers).get_json()["count"] == 0


@pytest.mark.parametrize("bad", [
    [], "x", [{"date": "nope", "gallons": 5}], [{"date": "2026-10-01", "gallons": -1}],
    [{"date": "2026-10-01", "gallons": "5"}], [{"date": "2026-10-01", "gallons": True}],
    [{"date": "2026-10-01", "gallons": 999999}], [{"date": "2026-12-25", "gallons": 5}],
    [{"date": "1990-01-01", "gallons": 5}], ["not a dict"],
])
def test_rejects_bad_entries(client, registered_user, bad):
    headers, _, _ = registered_user
    pid = make(client, headers)
    assert put(client, headers, pid, bad).status_code == 400


def test_only_the_owner_can_change_usage(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)
    other = client.post("/api/auth/register", json={"email": "usage-other@example.com", "password": "password123"}).get_json()
    other_headers = {"Authorization": f"Bearer {other['token']}"}
    entry = [{"date": "2026-10-01", "gallons": 70}]
    assert put(client, other_headers, pid, entry).status_code == 403
    assert put(client, headers, "demo", entry).status_code == 403
    assert client.put("/api/usage" + q(pid), json={"entries": entry}).status_code == 401
    assert client.delete("/api/usage" + q(pid, "&all=true"), headers=other_headers).status_code == 403


def test_deleting_a_household_removes_its_usage(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)
    put(client, headers, pid, [{"date": "2026-10-01", "gallons": 70}])
    client.delete(f"/api/profiles/{pid}", headers=headers)
    assert storage.list_usage(pid) == {}


def test_demo_household_stays_simulated(client):
    d = client.get("/api/dashboard").get_json()
    assert d["source"] == "simulated" and d["has_data"] is True and len(d["hourly_breakdown"]) == 24


def test_assistant_asks_for_data_when_household_is_empty(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)
    r = client.post("/api/ask" + q(pid), json={"question": "why is my bill high?"}, headers=headers)
    assert "Add data" in r.get_json()["answer"]


def test_forecast_follows_the_weekly_pattern(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)
    entries = []
    for i in range(60):
        d = TODAY - timedelta(days=i)
        entries.append({"date": d.isoformat(), "gallons": 300 if d.weekday() >= 5 else 150})
    assert put(client, headers, pid, entries).status_code == 200
    f = client.get("/api/forecast" + q(pid), headers=headers).get_json()
    values = {d["gallons"] for d in f["projected_daily"]}
    assert len(values) == 2 and max(values) > min(values) * 1.5


def test_forecast_stays_flat_with_too_little_history(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)
    entries = [{"date": (TODAY - timedelta(days=i)).isoformat(), "gallons": 100 + i * 10} for i in range(5)]
    put(client, headers, pid, entries)
    f = client.get("/api/forecast" + q(pid), headers=headers).get_json()
    assert len({d["gallons"] for d in f["projected_daily"]}) == 1


def test_unusual_days_are_flagged_from_daily_totals(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)
    entries = []
    for i in range(30):
        d = TODAY - timedelta(days=i)
        entries.append({"date": d.isoformat(), "gallons": 150 + (i % 5)})
    spike_day = (TODAY - timedelta(days=3)).isoformat()
    for e in entries:
        if e["date"] == spike_day:
            e["gallons"] = 600
    put(client, headers, pid, entries)
    a = client.get("/api/anomalies" + q(pid), headers=headers).get_json()
    assert a["anomalies_found"] == 1
    assert a["unusual_days"][0]["date"] == spike_day and a["unusual_days"][0]["gallons"] == 600
    assert sum(a["weekly_counts"]) == 1 and len(a["weekly_counts"]) == 8


def test_steady_usage_has_no_unusual_days(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)
    put(client, headers, pid, [{"date": (TODAY - timedelta(days=i)).isoformat(), "gallons": 150 + (i % 4)} for i in range(30)])
    a = client.get("/api/anomalies" + q(pid), headers=headers).get_json()
    assert a["anomalies_found"] == 0 and a["typical_daily_gallons"] is not None


def test_too_few_days_for_unusual_check(client, registered_user):
    headers, _, _ = registered_user
    pid = make(client, headers)
    put(client, headers, pid, [{"date": (TODAY - timedelta(days=i)).isoformat(), "gallons": 150} for i in range(5)])
    a = client.get("/api/anomalies" + q(pid), headers=headers).get_json()
    assert a["anomalies_found"] == 0 and a["days_checked"] == 5 and a["typical_daily_gallons"] is None