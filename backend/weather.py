"""
Real call to the National Weather Service (api.weather.gov — free, no key
required) used to weather-correct the 7-day usage forecast. Falls back to a
seasonally reasonable synthetic forecast if the network call fails, so the
forecast keeps working when the service is unreachable.
"""

import random
from datetime import datetime

import requests

from config import DAYS_IN_MONTH, TIER_1_RATE, TIER_2_RATE


def fetch_noaa_forecast(lat, lon):
    try:
        points = requests.get(
            f"https://api.weather.gov/points/{lat},{lon}",
            headers={"User-Agent": "AquaAI"},
            timeout=5,
        ).json()
        forecast_url = points["properties"]["forecast"]
        periods = requests.get(forecast_url, timeout=5).json()["properties"]["periods"]

        daily_highs = []
        for p in periods:
            if p.get("isDaytime"):
                daily_highs.append(p["temperature"])
            if len(daily_highs) == 7:
                break
        return {"source": "NOAA api.weather.gov (live)", "daily_highs": daily_highs}
    except Exception:
        rng = random.Random(datetime.now().day)
        return {
            "source": "simulated (NOAA unreachable)",
            "daily_highs": [rng.randint(78, 96) for _ in range(7)],
        }


def build_forecast(readings, lat, lon, tier1_limit_gal):
    """Forecast for the simulated demo household, built from its fake readings."""
    daily_totals = [round(sum(r["gallons"] for r in readings if r["day"] == d), 1) for d in range(60)]
    recent_30 = daily_totals[-30:]
    avg_daily = sum(recent_30) / len(recent_30)
    today_of_month = datetime.now().day
    month_used_so_far = sum(recent_30[:today_of_month]) if today_of_month <= len(recent_30) else sum(recent_30)
    return forecast_from_daily(avg_daily, month_used_so_far, today_of_month, DAYS_IN_MONTH, lat, lon, tier1_limit_gal)


def forecast_from_daily(avg_daily, month_used_so_far, today_of_month, days_in_month, lat, lon, tier1_limit_gal):
    weather = fetch_noaa_forecast(lat, lon)
    highs = weather["daily_highs"]

    projected_daily = []
    running_total = month_used_so_far
    breach_day = None
    for i in range(7):
        high = highs[i] if i < len(highs) else 85
        heat_multiplier = 1 + max(0, high - 85) * 0.025  # +2.5% per degree above 85F
        day_total = round(avg_daily * heat_multiplier, 1)
        running_total += day_total
        projected_daily.append({"day_offset": i + 1, "high_f": high, "gallons": day_total})
        if breach_day is None and running_total > tier1_limit_gal:
            breach_day = today_of_month + i + 1

    month_end_total = round(
        month_used_so_far + sum(d["gallons"] for d in projected_daily)
        + avg_daily * max(0, days_in_month - today_of_month - 7), 1
    )
    tier2_gallons = max(0, month_end_total - tier1_limit_gal)
    bill_estimate = round(min(month_end_total, tier1_limit_gal) * TIER_1_RATE + tier2_gallons * TIER_2_RATE, 2)

    tips = [
        "Shift lawn watering to before 6am to cut evaporation loss by up to 30%.",
        "A running toilet can waste 200+ gallons a day. Check for silent leaks with food coloring in the tank.",
        "Shortening showers by 2 minutes saves roughly 5 gallons per shower.",
    ]

    return {
        "weather_source": weather["source"],
        "avg_daily_gallons": round(avg_daily, 1),
        "month_used_so_far": round(month_used_so_far, 1),
        "projected_daily": projected_daily,
        "month_end_total_gallons": month_end_total,
        "tier1_limit_gallons": tier1_limit_gal,
        "gallons_to_tier2": max(0, tier1_limit_gal - month_used_so_far),
        "tier_breach_day_of_month": breach_day,
        "bill_estimate_dollars": bill_estimate,
        "savings_tips": tips,
    }