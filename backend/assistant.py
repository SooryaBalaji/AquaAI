"""
Ask AquaAI — a chat assistant users can ask plain-English questions like
"why is my bill high?" or "am I going to hit Tier 2?"

Design choice: the assistant is grounded. Instead of letting the model
guess, every request packages this household's actual dashboard, forecast,
anomaly, and savings data into the prompt, so answers are built from real
numbers instead of being invented. This is a genuinely different kind of AI
from the Isolation Forest and the CNN — a natural-language layer on top of
the app's own analytics, not a third prediction model.

If no ANTHROPIC_API_KEY is set (or the call fails for any reason — offline,
rate limited, bad key), this falls back to a small rule-based answer
generator built from the same real data, so a live demo never goes blank.
"""

import os

import requests

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-5"  # see README if this model string changes


def _context_summary(ctx):
    """Turn the app's live data into a short, factual briefing for the model."""
    breach_day = ctx['forecast']['tier_breach_day_of_month']
    breach_line = (
        f"Tier 2 breach projected on day {breach_day} of the month.\n"
        if breach_day else
        "Not projected to reach Tier 2 pricing this month.\n"
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
        f"Leak Detective (Isolation Forest) has flagged {ctx['anomaly_count']} unusual usage "
        f"intervals in the last 60 days.\n"
        f"Water Score: {ctx['score']['score']}/100 "
        f"(leak-free usage {ctx['score']['breakdown']['leak_free_usage']}/40, "
        f"tier compliance {ctx['score']['breakdown']['tier_compliance']}/30, "
        f"usage consistency {ctx['score']['breakdown']['usage_consistency']}/30).\n"
        f"Projected to save {ctx['savings']['gallons_saved_projected_year']} gallons "
        f"(${ctx['savings']['dollars_saved_projected_year']}) this year vs. the regional average."
    )


def _call_claude(question, ctx):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    system_prompt = (
        f"You are the in-app assistant for AquaAI, a household water-intelligence app. "
        f"You are answering for {ctx['profile_name']}. "
        "Answer the resident's question in 2-4 short sentences, in plain English, using "
        "ONLY the household data below. Never invent numbers that aren't given. "
        "If the data doesn't cover what's asked, say so honestly.\n\n"
        f"HOUSEHOLD DATA:\n{_context_summary(ctx)}"
    )

    try:
        response = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 300,
                "system": system_prompt,
                "messages": [{"role": "user", "content": question}],
            },
            timeout=15,
        )
        response.raise_for_status()
        blocks = response.json().get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        return text.strip() or None
    except Exception:
        return None


def _fallback_answer(question, ctx):
    """Rule-based answer built from the same real data, used when no API key
    is configured or the API call fails — so the demo never goes blank."""
    q = question.lower()
    f, s, sc = ctx["forecast"], ctx["savings"], ctx["score"]

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
        return f"Your Water Score is {sc['score']}/100, based on leak-free usage, tier compliance, and usage consistency."

    if "save" in q or "saving" in q:
        return (
            f"At this rate you're projected to save {s['gallons_saved_projected_year']} gallons "
            f"(${s['dollars_saved_projected_year']}) this year compared to the regional average."
        )

    return (
        f"Here's where things stand: {f['month_used_so_far']} of {f['tier1_limit_gallons']} gallons "
        f"used this month, {ctx['anomaly_count']} unusual intervals flagged, Water Score {sc['score']}/100. "
        f"Ask about your bill, leaks, tier budget, or savings for more detail."
    )


def answer_question(question, ctx):
    reply = _call_claude(question, ctx)
    if reply:
        return {"answer": reply, "source": "claude"}
    return {"answer": _fallback_answer(question, ctx), "source": "offline (grounded in your data, no API key configured)"}
