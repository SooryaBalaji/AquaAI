

from datetime import datetime

from config import TIER_1_LIMIT_GAL, TIER_1_RATE

REGIONAL_AVG_DAILY_GAL = 175.0  # regional average for a household this size


def compute_score(forecast, anomaly_count):
    leak_component = max(0, 40 - anomaly_count * 2)  # fewer anomalies = higher score
    tier_component = 30 if forecast["month_end_total_gallons"] <= TIER_1_LIMIT_GAL else 12
    consistency_component = 30 if forecast["avg_daily_gallons"] < 160 else 18
    return {
        "score": leak_component + tier_component + consistency_component,
        "breakdown": {
            "leak_free_usage": leak_component,
            "tier_compliance": tier_component,
            "usage_consistency": consistency_component,
        },
    }


def compute_savings(forecast, anomaly_count):
    saved_per_day = max(0, REGIONAL_AVG_DAILY_GAL - forecast["avg_daily_gallons"])
    return {
        "gallons_saved_this_month": round(saved_per_day * datetime.now().day, 1),
        "gallons_saved_projected_year": round(saved_per_day * 365, 1),
        "dollars_saved_projected_year": round(saved_per_day * 365 * TIER_1_RATE, 2),
        "badges": [b for b, cond in [
            ("Leak-Free Week", anomaly_count == 0),
            ("Under Tier 1", forecast["month_end_total_gallons"] <= TIER_1_LIMIT_GAL),
            ("Below Regional Average", saved_per_day > 0),
        ] if cond],
    }
