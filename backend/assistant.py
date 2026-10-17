"""
Ask AquaAI — a chat assistant users can ask plain-English questions like
"why is my bill high?" or "am I going to hit Tier 2?"

Design choice: the assistant is grounded. Instead of letting the model
guess, every request packages this household's actual dashboard, forecast,
anomaly, and savings data into the prompt, so answers are built from real
numbers instead of being invented. This is a genuinely different kind of AI
from the Isolation Forest and the CNN — a natural-language layer on top of
the app's own analytics, not a third prediction model.

If no GEMINI_API_KEY is set (or the call fails for any reason, such as being
offline, rate limited, or a bad key), this falls back to a small rule-based
answer generator built from the same real data, so a live demo never goes blank.
"""

import logging
import os
import time
from datetime import datetime, timezone

import requests

log = logging.getLogger("aquaai.assistant")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-3.5-flash-lite"


def _context_summary(ctx):
    #Turn the app's live data into a short, factual briefing for the model
    if not ctx.get("has_data", True):
        return (
            "No water usage has been added for this household yet, so every number is zero. "
            "Tell the resident there is nothing to analyze and that they can add their daily "
            "gallons on the Add data tab."
        )
    breach_day = ctx['forecast']['tier_breach_day_of_month']
    breach_line = (
        f"Tier 2 breach projected on day {breach_day} of the month.\n"
        if breach_day else
        "Not projected to reach Tier 2 pricing this month.\n"
    )
    if ctx.get("manual"):
        leak_line = (
            f"Usage was entered as daily totals ({ctx.get('days_logged')} days logged), so there are "
            "no hourly readings and the Leak Detective is not available for this household.\n"
        )
    else:
        leak_line = (
            f"Leak Detective (Isolation Forest) has flagged {ctx['anomaly_count']} unusual usage "
            f"intervals in the last 60 days.\n"
        )
    score = ctx['score']
    score_line = (
        f"Water Score: {score['score']}/100.\n" if score.get('score') is not None
        else "Water Score: not available yet, it needs about a week of logged usage.\n"
    )
    return (
        f"Today's usage: {ctx['dashboard']['today_total_gallons']} gallons "
        f"(daily budget {ctx['dashboard']['daily_limit_gallons']} gallons).\n"
        f"This month so far: {ctx['forecast']['month_used_so_far']} gallons used, "
        f"Tier 1 limit is {ctx['forecast']['tier1_limit_gallons']} gallons, "
        f"{ctx['forecast']['gallons_to_tier2']} gallons remain before Tier 2 pricing.\n"
        f"{breach_line}"
        f"Projected month-end bill: ${ctx['forecast']['bill_estimate_dollars']}.\n"
        f"Weather source used for the forecast: {ctx['forecast']['weather_source']}.\n"
        f"{leak_line}"
        f"{score_line}"
        f"Projected to save {ctx['savings']['gallons_saved_projected_year']} gallons "
        f"(${ctx['savings']['dollars_saved_projected_year']}) this year vs. the regional average."
    )


def _error_detail(response):
    try:
        err = response.json().get("error") or {}
        message = str(err.get("message") or "").strip().replace("\n", " ")
    except ValueError:
        message = ""
    detail = f"HTTP {response.status_code}"
    if message:
        detail += f": {message[:140]}"
    return detail


BUSY_STATUSES = {429, 500, 502, 503, 504}
FALLBACK_MODEL = "gemini-3.8-flash"


def _request_gemini(model, api_key, system_prompt, question):
    """One attempt. Returns (text, None) or (None, reason). A reason starting
    with "busy:" means Google was overloaded or rate limiting, so another
    model may still work."""
    try:
        response = requests.post(
            f"{os.environ.get('GEMINI_BASE_URL', GEMINI_BASE_URL).rstrip('/')}/models/{model}:generateContent",
            headers={"x-goog-api-key": api_key, "content-type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": question}]}],
                "generationConfig": {"maxOutputTokens": 1500, "temperature": 0.3},
            },
            timeout=25,
        )
        if response.status_code != 200:
            log.warning("Gemini (%s) returned %s: %s", model, response.status_code, response.text[:300])
            kind = "busy" if response.status_code in BUSY_STATUSES else "error"
            return None, f"{kind}:{_error_detail(response)}"
        candidates = response.json().get("candidates") or []
        parts = (candidates[0].get("content") or {}).get("parts", []) if candidates else []
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            log.warning("Gemini (%s) returned no text: %s", model, response.text[:300])
            finish = candidates[0].get("finishReason") if candidates else None
            block = (response.json().get("promptFeedback") or {}).get("blockReason")
            return None, f"error:the reply was empty ({block or finish or 'no candidates'})"
        return text, None
    except requests.Timeout:
        log.warning("Gemini (%s) request timed out", model, exc_info=True)
        return None, "slow:the request timed out after 25 seconds"
    except requests.RequestException as e:
        log.warning("Gemini (%s) request failed", model, exc_info=True)
        return None, f"failed:could not reach Google ({type(e).__name__})"
    except (ValueError, KeyError, IndexError, AttributeError) as e:
        log.warning("Gemini (%s) reply could not be read", model, exc_info=True)
        return None, f"error:unreadable reply ({type(e).__name__})"


def _call_gemini(question, ctx):
    """Returns (answer_text, None) on success or (None, reason) on failure.
    reason is "no_key", "busy:<detail>", "slow:<detail>" (timed out), "error:<detail>" (Google rejected or returned nothing) or "failed:<detail>" (could not connect). If the main model
    is overloaded, one retry goes to a lighter backup model."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None, "no_key"

    system_prompt = (
        f"You are the in-app assistant for AquaAI, a household water-intelligence app. "
        f"You are answering for {ctx['profile_name']}. "
        "Answer the resident's question in 2-4 short sentences, in plain English, using "
        "ONLY the household data below. Never invent numbers that aren't given. "
        "If the data doesn't cover what's asked, say so honestly.\n\n"
        f"HOUSEHOLD DATA:\n{_context_summary(ctx)}"
    )
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    text, reason = _request_gemini(model, api_key, system_prompt, question)
    if text:
        return text, None

    backup = os.environ.get("GEMINI_FALLBACK_MODEL", FALLBACK_MODEL)
    if reason.startswith(("busy:", "slow:")) and backup and backup != model:
        log.info("Gemini model %s is busy, retrying with %s", model, backup)
        text, backup_reason = _request_gemini(backup, api_key, system_prompt, question)
        if text:
            return text, None
        reason = backup_reason
    return None, reason


def _fallback_answer(question, ctx):
    """Rule-based answer built from the same real data, used when no API key
    is configured or the API call fails — so the demo never goes blank."""
    q = question.lower()
    f, s, sc = ctx["forecast"], ctx["savings"], ctx["score"]

    if not ctx.get("has_data", True):
        return (
            "You haven't added any water usage for this household yet, so there is nothing to "
            "analyze. Open the Add data tab and log your daily gallons, then ask me again."
        )

    if "bill" in q or "cost" in q or "expensive" in q:
        if f["tier_breach_day_of_month"]:
            return (
                f"Your bill is trending up mainly because usage is projected to cross into "
                f"Tier 2 pricing around day {f['tier_breach_day_of_month']} of the month, which "
                f"roughly doubles the per-gallon rate. Projected month-end bill: "
                f"${f['bill_estimate_dollars']}."
            )
        return f"You're projected to stay within Tier 1 pricing this month. Estimated bill: ${f['bill_estimate_dollars']}."

    if "leak" in q or "anomal" in q or "unusual" in q:
        if ctx.get("manual"):
            return (
                "The Leak Detective needs hourly or 15 minute readings, and this household only has "
                "daily totals, so it can't check for leaks yet."
            )
        return (
            f"The Leak Detective model has flagged {ctx['anomaly_count']} unusual usage intervals "
            f"in the last 60 days. Check the Leak Detective tab for exactly when they happened."
        )

    if "tier" in q or "budget" in q:
        return (
            f"You've used {f['month_used_so_far']} of your {f['tier1_limit_gallons']}-gallon "
            f"Tier 1 budget this month. {f['gallons_to_tier2']} gallons remain."
        )

    if "score" in q:
        if sc.get("score") is None:
            return "Your Water Score needs about a week of logged usage. Keep adding your daily gallons and it will appear."
        return f"Your Water Score is {sc['score']}/100, based on leak-free usage, tier compliance, and usage consistency."

    if "save" in q or "saving" in q:
        return (
            f"At this rate you're projected to save {s['gallons_saved_projected_year']} gallons "
            f"(${s['dollars_saved_projected_year']}) this year compared to the regional average."
        )

    if ctx.get("manual"):
        return (
            f"Here's where things stand: {f['month_used_so_far']} of {f['tier1_limit_gallons']} gallons "
            f"used this month. Ask about your bill, tier budget, or savings for more detail."
        )
    return (
        f"Here's where things stand: {f['month_used_so_far']} of {f['tier1_limit_gallons']} gallons "
        f"used this month, {ctx['anomaly_count']} unusual intervals flagged, Water Score {sc['score']}/100. "
        f"Ask about your bill, leaks, tier budget, or savings for more detail."
    )


OFFLINE_LABELS = {
    "no_key": "offline (grounded in your data, no API key configured)",
    "failed": "offline (grounded in your data, the AI service did not respond)",
}


BUSY_WARNING = (
    "Google's AI service is busy right now, so this is a basic answer from your data. "
    "This is usually temporary. Wait a minute and ask again."
)

ERROR_WARNING = (
    "The AI assistant returned an error, so this is a basic answer from your data. "
    "Ask again in a moment. If it keeps happening, the server log has the details."
)

UNREACHABLE_WARNING = (
    "The AI assistant could not be reached, so this is a basic answer from your data. "
    "This can be a temporary problem with the service, or a network issue such as a VPN, "
    "firewall, or work or school network blocking the connection. Try turning off your VPN "
    "or switching networks, then ask again."
)


LAST_CALL = {"ok": None, "detail": None, "at": None}

SAMPLE_CTX = {
    "profile_name": "Self-check household",
    "dashboard": {"today_total_gallons": 120, "daily_limit_gallons": 150},
    "forecast": {
        "tier_breach_day_of_month": None, "month_used_so_far": 1800, "tier1_limit_gallons": 4500,
        "gallons_to_tier2": 2700, "bill_estimate_dollars": 32.4, "weather_source": "self-check",
    },
    "anomaly_count": 0,
    "score": {"score": 80},
    "savings": {"gallons_saved_projected_year": 500, "dollars_saved_projected_year": 20},
}


def _record(ok, detail):
    LAST_CALL.update(ok=ok, detail=detail, at=datetime.now(timezone.utc).isoformat(timespec="seconds"))


def status():
    """What the health page reports: no API call is made here."""
    return {
        "key_set": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
        "model": os.environ.get("GEMINI_MODEL", DEFAULT_MODEL),
        "backup_model": os.environ.get("GEMINI_FALLBACK_MODEL", FALLBACK_MODEL),
        "last_call": dict(LAST_CALL),
    }


def self_check():
    """Sends the same request the app sends for a real question, with sample data."""
    start = time.time()
    result = answer_question("How am I doing this month?", SAMPLE_CTX)
    return {
        "ok": result["source"] == "gemini",
        "source": result["source"],
        "answer": result["answer"],
        "seconds": round(time.time() - start, 1),
    }


def answer_question(question, ctx):
    reply, reason = _call_gemini(question, ctx)
    if reply:
        _record(True, "answered")
        return {"answer": reply, "source": "gemini"}
    _record(False, reason)
    result = {"answer": _fallback_answer(question, ctx)}
    kind, _, detail = reason.partition(":")
    if kind == "slow":
        kind = "failed"
    if kind in ("failed", "busy", "error"):
        result["source"] = f"offline (grounded in your data, Gemini error - {detail})"
        result["warning"] = {"busy": BUSY_WARNING, "error": ERROR_WARNING}.get(kind, UNREACHABLE_WARNING)
    else:
        result["source"] = OFFLINE_LABELS[reason]
    return result