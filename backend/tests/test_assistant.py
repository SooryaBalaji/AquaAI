import pytest
import requests

import assistant


class FakeResponse:
    def __init__(self, status=200, data=None, text=""):
        self.status_code, self._data, self.text = status, data or {}, text

    def json(self):
        return self._data


CTX = {
    "profile_name": "Test house",
    "dashboard": {"today_total_gallons": 30, "daily_limit_gallons": 150},
    "forecast": {
        "tier_breach_day_of_month": None, "month_used_so_far": 500, "tier1_limit_gallons": 4500,
        "gallons_to_tier2": 4000, "bill_estimate_dollars": 10.5, "weather_source": "test",
    },
    "anomaly_count": 3,
    "score": {"score": 70, "breakdown": {"leak_free_usage": 20, "tier_compliance": 30, "usage_consistency": 20}},
    "savings": {"gallons_saved_projected_year": 1000, "dollars_saved_projected_year": 40},
}


def test_uses_gemini_when_key_is_set(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-123")
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, body=json)
        return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": "You are fine."}]}}]})

    monkeypatch.setattr(assistant.requests, "post", fake_post)
    result = assistant.answer_question("how is my bill?", CTX)
    assert result == {"answer": "You are fine.", "source": "gemini"}
    assert "gemini-3.5-flash-lite:generateContent" in seen["url"]
    assert seen["headers"]["x-goog-api-key"] == "key-123"
    assert "Test house" in seen["body"]["systemInstruction"]["parts"][0]["text"]


def test_no_key_says_so(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    result = assistant.answer_question("how is my bill?", CTX)
    assert "no API key configured" in result["source"]


@pytest.mark.parametrize("failure", [
    lambda *a, **k: FakeResponse(403, text="bad key"),
    lambda *a, **k: FakeResponse(200, {"candidates": []}),
    lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("down")),
])
def test_key_set_but_call_fails_says_service_did_not_respond(monkeypatch, failure):
    monkeypatch.setenv("GEMINI_API_KEY", "key-123")
    monkeypatch.setattr(assistant.requests, "post", failure)
    result = assistant.answer_question("how is my bill?", CTX)
    assert "did not respond" in result["source"] or "Gemini error" in result["source"]
    assert "10.5" in result["answer"]


def test_rejected_key_shows_http_status(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-123")
    monkeypatch.setattr(assistant.requests, "post", lambda *a, **k: FakeResponse(403, text="bad key"))
    result = assistant.answer_question("how is my bill?", CTX)
    assert "HTTP 403" in result["source"]
    assert "key-123" not in result["source"]


def test_unreachable_gemini_adds_a_warning(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-123")
    monkeypatch.setattr(assistant.requests, "post", lambda *a, **k: (_ for _ in ()).throw(requests.Timeout("slow")))
    result = assistant.answer_question("how is my bill?", CTX)
    assert "VPN" in result["warning"]


def test_no_warning_without_a_key_or_on_success(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    assert "warning" not in assistant.answer_question("how is my bill?", CTX)


def test_busy_main_model_retries_with_backup_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-123")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    urls = []

    def fake_post(url, **kwargs):
        urls.append(url)
        if len(urls) == 1:
            return FakeResponse(503, text="busy")
        return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": "backup answer"}]}}]})

    monkeypatch.setattr(assistant.requests, "post", fake_post)
    result = assistant.answer_question("how is my bill?", CTX)
    assert result["answer"] == "backup answer" and result["source"] == "gemini"
    assert assistant.FALLBACK_MODEL in urls[1]


def test_busy_everywhere_shows_busy_warning_not_vpn(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-123")
    monkeypatch.setattr(assistant.requests, "post", lambda *a, **k: FakeResponse(503, text="busy"))
    result = assistant.answer_question("how is my bill?", CTX)
    assert "busy" in result["warning"] and "VPN" not in result["warning"]


def test_rejected_request_does_not_blame_the_network(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-123")
    monkeypatch.setattr(assistant.requests, "post", lambda *a, **k: FakeResponse(400, text="bad"))
    result = assistant.answer_question("how is my bill?", CTX)
    assert "HTTP 400" in result["source"] and "VPN" not in result["warning"]


def test_request_does_not_send_thinking_settings(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-123")
    seen = {}

    def fake_post(url, **kwargs):
        seen.update(kwargs["json"])
        return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

    monkeypatch.setattr(assistant.requests, "post", fake_post)
    assistant.answer_question("how is my bill?", CTX)
    assert "thinkingConfig" not in seen["generationConfig"]


def test_timeout_on_main_model_tries_backup(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-123")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    urls = []

    def fake_post(url, **kwargs):
        urls.append(url)
        if len(urls) == 1:
            raise requests.Timeout("slow")
        return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": "backup answer"}]}}]})

    monkeypatch.setattr(assistant.requests, "post", fake_post)
    result = assistant.answer_question("how is my bill?", CTX)
    assert result["answer"] == "backup answer" and assistant.FALLBACK_MODEL in urls[1]


def test_status_and_last_call(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-123")
    monkeypatch.setattr(assistant.requests, "post", lambda *a, **k: FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}))
    assistant.answer_question("hi", CTX)
    st = assistant.status()
    assert st["key_set"] and st["last_call"]["ok"] is True and st["last_call"]["at"]


def test_self_check_reports_failure(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-123")
    monkeypatch.setattr(assistant.requests, "post", lambda *a, **k: FakeResponse(400, text="bad"))
    res = assistant.self_check()
    assert res["ok"] is False and "HTTP 400" in res["source"]
    assert assistant.status()["last_call"]["ok"] is False
