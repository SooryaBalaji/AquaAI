"""
Usage entered by the household's owner: one gallons total per calendar day.

Everything for a user-created household is computed from these entries.
With no entries every number is zero and the screens ask the person to add
data. Only the shared demo household uses simulated readings (see data.py).
"""

import calendar
import math
import statistics
from datetime import date, timedelta

import storage
import weather
from config import DAYS_IN_MONTH

MAX_DAILY_GALLONS = 100_000
MAX_ENTRIES_PER_REQUEST = 1000
MAX_ENTRIES_PER_HOUSEHOLD = 4000
EARLIEST_DATE = date(2000, 1, 1)
MIN_DAYS_FOR_SCORE = 7


class UsageError(ValueError):
    """Bad usage input. The message is safe to show the user."""


def parse_entries(raw, today):
    if not isinstance(raw, list) or not raw:
        raise UsageError("Send at least one entry.")
    if len(raw) > MAX_ENTRIES_PER_REQUEST:
        raise UsageError(f"Send at most {MAX_ENTRIES_PER_REQUEST} entries at a time.")
    parsed = {}
    for i, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise UsageError(f"Entry {i} is not valid.")
        try:
            day = date.fromisoformat(str(item.get("date")))
        except ValueError:
            raise UsageError(f"Entry {i}: the date must look like 2026-10-15.")
        if day < EARLIEST_DATE or day > today + timedelta(days=1):
            raise UsageError(f"Entry {i}: {day.isoformat()} is not a valid date for usage.")
        gallons = item.get("gallons")
        if isinstance(gallons, bool) or not isinstance(gallons, (int, float)) or not math.isfinite(gallons):
            raise UsageError(f"Entry {i}: gallons must be a number.")
        if not (0 <= gallons <= MAX_DAILY_GALLONS):
            raise UsageError(f"Entry {i}: gallons must be between 0 and {MAX_DAILY_GALLONS:,}.")
        parsed[day.isoformat()] = round(float(gallons), 2)
    return parsed


def add_entries(profile_id, raw, today):
    parsed = parse_entries(raw, today)
    existing = storage.list_usage(profile_id)
    if len(set(existing) | set(parsed)) > MAX_ENTRIES_PER_HOUSEHOLD:
        raise UsageError(f"A household can hold up to {MAX_ENTRIES_PER_HOUSEHOLD:,} days of usage.")
    storage.save_usage(profile_id, parsed)
    return len(parsed)


def remove_days(profile_id, days):
    clean = []
    for d in days:
        try:
            clean.append(date.fromisoformat(d).isoformat())
        except ValueError:
            raise UsageError("The date must look like 2026-10-15.")
    storage.delete_usage(profile_id, clean)


def clear(profile_id):
    storage.delete_usage(profile_id)


def history(profile_id, limit=400):
    daily = storage.list_usage(profile_id)
    rows = [{"date": d, "gallons": g} for d, g in sorted(daily.items(), reverse=True)]
    return {"count": len(rows), "entries": rows[:limit]}


# ---------------------------------------------------------------------------
# Analytics for user households
# ---------------------------------------------------------------------------
def dashboard(daily, tier1_limit_gal, today):
    last7 = [round(daily.get((today - timedelta(days=6 - i)).isoformat(), 0), 1) for i in range(7)]
    return {
        "source": "manual",
        "has_data": bool(daily),
        "days_logged": len(daily),
        "last_entry_date": max(daily) if daily else None,
        "today_total_gallons": round(daily.get(today.isoformat(), 0), 1),
        "hourly_breakdown": None,
        "daily_limit_gallons": round(tier1_limit_gal / DAYS_IN_MONTH, 1),
        "last_7_days_gallons": last7,
    }


def forecast(daily, lat, lon, tier1_limit_gal, today):
    recent = [
        daily[d] for d in ((today - timedelta(days=i)).isoformat() for i in range(30)) if d in daily
    ]
    avg_daily = sum(recent) / len(recent) if recent else 0
    prefix = today.strftime("%Y-%m")
    month_used = sum(g for d, g in daily.items() if d.startswith(prefix) and d <= today.isoformat())
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    result = weather.forecast_from_daily(avg_daily, month_used, today.day, days_in_month, lat, lon, tier1_limit_gal)
    result["source"] = "manual"
    result["has_data"] = bool(daily)
    return result


def score(daily, forecast_data, today):
    days = len(daily)
    if days < MIN_DAYS_FOR_SCORE:
        return {
            "score": None, "needs_more_data": True, "days_logged": days, "min_days": MIN_DAYS_FOR_SCORE,
            "breakdown": {"leak_free_usage": None, "tier_compliance": None, "usage_consistency": None},
        }
    recent = [daily[d] for d in ((today - timedelta(days=i)).isoformat() for i in range(14)) if d in daily]
    mean = sum(recent) / len(recent) if recent else 0
    spread = statistics.pstdev(recent) / mean if len(recent) > 1 and mean > 0 else 0
    tier_component = 30 if forecast_data["month_end_total_gallons"] <= forecast_data["tier1_limit_gallons"] else 12
    consistency_component = 30 if spread <= 0.35 else 18
    return {
        "score": round((tier_component + consistency_component) / 60 * 100),
        "needs_more_data": False, "days_logged": days, "min_days": MIN_DAYS_FOR_SCORE,
        "breakdown": {"leak_free_usage": None, "tier_compliance": tier_component, "usage_consistency": consistency_component},
    }


def anomalies():
    return {
        "source": "manual",
        "model": None,
        "trained_on_readings": 0,
        "anomalies_found": 0,
        "anomalies": [],
        "weekly_counts": [],
    }
