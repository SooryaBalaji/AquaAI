import base64
import json
import threading
from datetime import datetime, timezone

import pytest
from flask import Flask, jsonify, request
from werkzeug.serving import make_server

import flume
import storage
import weather

TODAY = datetime.now(timezone.utc).date()
NEW = {"name": "Flume house", "lat": 37.7, "lon": -121.9, "household_size": 3, "tier1_limit_gal": 4500, "place": "Dublin, California"}
GOOD = {"client_id": "cid", "client_secret": "sec", "email": "a@b.com", "password": "pw"}


def jwt(uid):
    seg = lambda o: base64.urlsafe_b64encode(json.dumps(o).encode()).decode().rstrip("=")
    return f"{seg({'alg': 'none'})}.{seg({'user_id': uid, 'type': 'USER'})}.sig"


def fake_flume(devices=None, usage_rows=None, token_status=200):
    app = Flask("fake")
    seen = {"auth": [], "queries": []}

    @app.post("/oauth/token")
    def token():
        b = request.get_json()
        seen["token_body"] = b
        if token_status != 200 or b["password"] != "pw":
            return jsonify({"success": False}), token_status if token_status != 200 else 400
        return jsonify({"success": True, "data": [{"access_token": jwt(77), "refresh_token": "r"}]})

    @app.get("/users/<int:uid>/devices")
    def devs(uid):
        seen["auth"].append(request.headers.get("Authorization"))
        return jsonify({"success": True, "data": devices if devices is not None else [{"id": "b1", "type": 1}, {"id": "s1", "type": 2}]})

    @app.post("/users/<int:uid>/devices/<did>/query")
    def query(uid, did):
        seen["queries"].append((uid, did, request.get_json()))
        rows = usage_rows if usage_rows is not None else [
            {"datetime": f"{TODAY.replace(day=1).isoformat()} 00:00:00", "value": 150.5},
            {"datetime": f"{TODAY.isoformat()} 00:00:00", "value": 90},
        ]
        return jsonify({"success": True, "data": [{"daily": rows}]})

    server = make_server("127.0.0.1", 0, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, seen


@pytest.fixture
def flume_server(monkeypatch):
    servers = []

    def start(**kw):
        server, seen = fake_flume(**kw)
        servers.append(server)
        monkeypatch.setenv("FLUME_BASE_URL", f"http://127.0.0.1:{server.server_port}")
        return seen

    yield start
    for s in servers:
        s.shutdown()


@pytest.fixture(autouse=True)
def offline_weather(monkeypatch):
    monkeypatch.setattr(weather, "fetch_noaa_forecast", lambda lat, lon: {"source": "test", "daily_highs": [80] * 7})


def make(client, headers):
    return client.post("/api/profiles", json=NEW, headers=headers).get_json()["id"]


def post(client, headers, pid, body):
    return client.post(f"/api/usage/flume?profile={pid}&today={TODAY.isoformat()}", json=body, headers=headers)


def test_import_saves_daily_totals(client, registered_user, flume_server):
    seen = flume_server()
    headers, _, _ = registered_user
    pid = make(client, headers)
    r = post(client, headers, pid, {**GOOD, "days": 30})
    assert r.status_code == 200 and r.get_json()["saved"] == 2
    assert storage.list_usage(pid)[TODAY.isoformat()] == 90
    uid, did, body = seen["queries"][0]
    assert (uid, did) == (77, "s1")
    assert body["queries"][0]["bucket"] == "DAY" and body["queries"][0]["units"] == "GALLONS"
    assert seen["auth"][0].startswith("Bearer ")


def test_credentials_are_not_stored_or_returned(client, registered_user, flume_server):
    flume_server()
    headers, _, _ = registered_user
    pid = make(client, headers)
    r = post(client, headers, pid, GOOD)
    assert "pw" not in r.get_data(as_text=True) and "sec" not in r.get_data(as_text=True)


def test_wrong_login_gives_clear_error(client, registered_user, flume_server):
    flume_server()
    headers, _, _ = registered_user
    pid = make(client, headers)
    r = post(client, headers, pid, {**GOOD, "password": "nope"})
    assert r.status_code == 502 and "did not accept" in r.get_json()["error"]
    assert storage.list_usage(pid) == {}


def test_no_sensor(client, registered_user, flume_server):
    flume_server(devices=[{"id": "b1", "type": 1}])
    headers, _, _ = registered_user
    pid = make(client, headers)
    r = post(client, headers, pid, GOOD)
    assert r.status_code == 502 and "No Flume sensor" in r.get_json()["error"]


def test_empty_usage(client, registered_user, flume_server):
    flume_server(usage_rows=[])
    headers, _, _ = registered_user
    pid = make(client, headers)
    assert post(client, headers, pid, GOOD).status_code == 404


def test_missing_fields_and_ownership(client, registered_user, flume_server):
    flume_server()
    headers, _, _ = registered_user
    pid = make(client, headers)
    assert post(client, headers, pid, {"client_id": "x"}).status_code == 400
    assert post(client, {}, pid, GOOD).status_code in (401, 403)


def test_unreachable_flume(client, registered_user, monkeypatch):
    monkeypatch.setenv("FLUME_BASE_URL", "http://127.0.0.1:9")
    headers, _, _ = registered_user
    pid = make(client, headers)
    r = post(client, headers, pid, GOOD)
    assert r.status_code == 502 and "could not reach" in r.get_json()["error"]


def test_rate_limit_message(monkeypatch):
    class R:
        status_code = 429
    monkeypatch.setattr(flume.requests, "request", lambda *a, **k: R())
    with pytest.raises(flume.FlumeError, match="120 requests"):
        flume.get_token("a", "b", "c", "d")
