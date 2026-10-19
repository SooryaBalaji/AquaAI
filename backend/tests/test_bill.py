import io
import json

import pytest

import bill

GOOD = {
    "is_water_bill": True, "utility_name": "Sample Water District",
    "billing_period_start": "2026-09-01", "billing_period_end": "2026-09-30", "due_date": "2026-10-20",
    "usage_amount": 6, "usage_unit": "ccf",
    "tiers": [
        {"name": "Tier 1", "usage_amount": 4, "rate_per_unit": 4.2, "charge": 16.8},
        {"name": "Tier 2", "usage_amount": 2, "rate_per_unit": 6.3, "charge": 12.6},
    ],
    "other_charges": [{"name": "Service charge", "amount": 18.5}, {"name": "Sewer", "amount": 22.0}],
    "total_amount_due": 69.9,
}
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def gemini_reply(obj):
    return FakeResponse({"candidates": [{"content": {"parts": [{"text": json.dumps(obj)}]}}]})


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


def upload(client, headers, data=PNG, name="bill.png"):
    return client.post("/api/bill", data={"file": (io.BytesIO(data), name)}, headers=headers, content_type="multipart/form-data")


def test_clean_converts_units_and_explains():
    r = bill.clean(GOOD)
    assert r["usage_gallons"] == pytest.approx(4488.3, abs=0.1)
    assert r["days"] == 30 and r["gallons_per_day"] == pytest.approx(149.6, abs=0.1)
    assert r["warnings"] == [] and r["can_log"] is True
    assert "$69.90" in r["explanation"] and "2026-10-20" in r["explanation"] and "Tier 2" in r["explanation"]


def test_not_a_bill():
    with pytest.raises(bill.BillError) as e:
        bill.clean({"is_water_bill": False})
    assert e.value.status == 422


def test_nothing_usable():
    with pytest.raises(bill.BillError):
        bill.clean({"is_water_bill": True, "tiers": [], "other_charges": []})


def test_mismatched_total_is_flagged():
    r = bill.clean({**GOOD, "total_amount_due": 120.0})
    assert any("add up" in w for w in r["warnings"])


def test_bad_values_are_dropped_not_trusted():
    r = bill.clean({**GOOD, "usage_amount": -5, "billing_period_start": "nonsense", "usage_unit": "barrels", "total_amount_due": "69.9"})
    assert r["usage_gallons"] is None and r["days"] is None and r["total_amount_due"] is None
    assert r["can_log"] is False


def test_period_longer_than_allowed_is_ignored():
    r = bill.clean({**GOOD, "billing_period_start": "2025-01-01", "billing_period_end": "2026-09-30"})
    assert r["days"] is None and r["can_log"] is False


def test_other_units():
    assert bill.clean({**GOOD, "usage_amount": 5, "usage_unit": "kgal"})["usage_gallons"] == 5000
    assert bill.clean({**GOOD, "usage_amount": 4488, "usage_unit": "gallons"})["usage_gallons"] == 4488


def test_file_types():
    assert bill.detect_type(PNG) == "image/png"
    assert bill.detect_type(b"\xff\xd8\xff\xe0" + b"0" * 20) == "image/jpeg"
    assert bill.detect_type(b"%PDF-1.7 ...") == "application/pdf"
    assert bill.detect_type(b"GIF89a") is None


def test_route_requires_sign_in(client):
    r = client.post("/api/bill", data={"file": (io.BytesIO(PNG), "b.png")}, content_type="multipart/form-data")
    assert r.status_code == 401


def test_route_success(client, registered_user, key, monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["body"] = json
        seen["key"] = headers["x-goog-api-key"]
        return gemini_reply(GOOD)

    monkeypatch.setattr(bill.requests, "post", fake_post)
    headers, _, _ = registered_user
    r = upload(client, headers)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()["bill"]
    assert body["total_amount_due"] == 69.9 and body["explanation"]
    part = seen["body"]["contents"][0]["parts"][0]["inlineData"]
    assert part["mimeType"] == "image/png" and part["data"]
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"


def test_route_rejects_bad_input(client, registered_user, key):
    headers, _, _ = registered_user
    assert client.post("/api/bill", headers=headers).status_code == 400
    assert upload(client, headers, data=b"hello world").status_code == 400
    assert upload(client, headers, data=b"").status_code == 400
    assert upload(client, headers, data=b"\x89PNG\r\n\x1a\n" + b"0" * (bill.MAX_BYTES + 10)).status_code == 413


def test_route_without_key(client, registered_user, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    headers, _, _ = registered_user
    r = upload(client, headers)
    assert r.status_code == 503 and "Gemini" in r.get_json()["error"]


def test_busy_then_backup_model(client, registered_user, key, monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(url)
        return FakeResponse({"error": {"message": "overloaded"}}, 503) if len(calls) == 1 else gemini_reply(GOOD)

    monkeypatch.setattr(bill.requests, "post", fake_post)
    headers, _, _ = registered_user
    assert upload(client, headers).status_code == 200
    assert len(calls) == 2 and calls[0] != calls[1]


def test_unreadable_reply(client, registered_user, key, monkeypatch):
    monkeypatch.setattr(bill.requests, "post", lambda *a, **k: FakeResponse({"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}))
    headers, _, _ = registered_user
    r = upload(client, headers)
    assert r.status_code == 502


def test_not_a_bill_route(client, registered_user, key, monkeypatch):
    monkeypatch.setattr(bill.requests, "post", lambda *a, **k: gemini_reply({"is_water_bill": False}))
    headers, _, _ = registered_user
    r = upload(client, headers)
    assert r.status_code == 422 and "does not look like a water bill" in r.get_json()["error"]