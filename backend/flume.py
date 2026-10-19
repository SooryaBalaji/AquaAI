import base64
import json
import os
from datetime import timedelta

import requests

BASE_URL = os.environ.get("FLUME_BASE_URL", "https://api.flumewater.com")
TIMEOUT = 20
MAX_DAYS = 365
SENSOR_TYPE = 2


class FlumeError(Exception):
    """The message is safe to show the user."""


def _base():
    return os.environ.get("FLUME_BASE_URL", BASE_URL).rstrip("/")


def _data(response):
    try:
        body = response.json()
    except ValueError:
        raise FlumeError("Flume sent a reply AquaAI could not read. Try again in a minute.")
    return body


def _request(method, path, token=None, **kwargs):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.request(method, _base() + path, headers=headers, timeout=TIMEOUT, **kwargs)
    except requests.Timeout:
        raise FlumeError("Flume took too long to answer. Try again in a minute.")
    except requests.RequestException:
        raise FlumeError("AquaAI could not reach Flume. Try again in a minute.")
    if r.status_code == 429:
        raise FlumeError("Flume allows personal API clients 120 requests an hour. Wait a while and try again.")
    return r


def _user_id(token):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return int(json.loads(base64.urlsafe_b64decode(payload))["user_id"])
    except (IndexError, KeyError, ValueError, TypeError):
        raise FlumeError("Flume sent an access token AquaAI could not read.")


def get_token(client_id, client_secret, email, password):
    r = _request("POST", "/oauth/token", json={
        "grant_type": "password", "client_id": client_id, "client_secret": client_secret,
        "username": email, "password": password,
    })
    if r.status_code == 403:
        raise FlumeError("Your Flume account has not finished signing up.")
    if r.status_code in (400, 401):
        raise FlumeError("Flume did not accept those details. Check the client ID, client secret, email and password.")
    if r.status_code != 200:
        raise FlumeError("Flume could not sign in right now. Try again in a minute.")
    data = _data(r).get("data")
    if isinstance(data, list):
        data = data[0] if data else None
    token = data.get("access_token") if isinstance(data, dict) else None
    if not token:
        raise FlumeError("Flume did not return an access token.")
    return token


def get_sensor(token, user_id):
    r = _request("GET", f"/users/{user_id}/devices", token=token)
    if r.status_code != 200:
        raise FlumeError("Flume would not list your devices.")
    devices = _data(r).get("data") or []
    sensors = [d for d in devices if isinstance(d, dict) and d.get("type") == SENSOR_TYPE]
    if not sensors:
        raise FlumeError("No Flume sensor was found on that account.")
    return sensors[0]["id"]


def fetch_daily(client_id, client_secret, email, password, days, today):
    days = max(1, min(int(days), MAX_DAYS))
    token = get_token(client_id, client_secret, email, password)
    user_id = _user_id(token)
    device_id = get_sensor(token, user_id)
    since = today - timedelta(days=days - 1)
    r = _request("POST", f"/users/{user_id}/devices/{device_id}/query", token=token, json={"queries": [{
        "request_id": "daily", "bucket": "DAY", "units": "GALLONS",
        "since_datetime": f"{since.isoformat()} 00:00:00",
    }]})
    if r.status_code != 200:
        raise FlumeError("Flume would not return your usage.")
    data = _data(r).get("data")
    rows = data[0].get("daily") if isinstance(data, list) and data and isinstance(data[0], dict) else None
    if rows is None:
        raise FlumeError("Flume returned usage in a shape AquaAI did not expect.")
    entries = []
    for row in rows:
        try:
            day = str(row["datetime"])[:10]
            gallons = float(row["value"])
        except (KeyError, TypeError, ValueError):
            continue
        entries.append({"date": day, "gallons": round(max(gallons, 0), 2)})
    return entries
