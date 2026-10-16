"""Water Score and gallons/dollars-saved calculations, derived from the
forecast and the Isolation Forest's anomaly count."""

from datetime import datetime

from config import TIER_1_RATE

REGIONAL_AVG_DAILY_GAL_PER_PERSON = 43.75  # regional average, 175 gal / 4-person household


def compute_score(forecast, anomaly_count):
    leak_component = max(0, 40 - anomaly_count * 2)  # fewer anomalies = higher score
    tier_component = 30 if forecast["month_end_total_gallons"] <= forecast["tier1_limit_gallons"] else 12
    consistency_component = 30 if forecast["avg_daily_gallons"] < 160 else 18
    return {
        "score": leak_component + tier_component + consistency_component,
        "breakdown": {
            "leak_free_usage": leak_component,
            "tier_compliance": tier_component,
            "usage_consistency": consistency_component,
        },
    }


def compute_savings(forecast, anomaly_count, household_size=4):
    regional_avg_daily = REGIONAL_AVG_DAILY_GAL_PER_PERSON * household_size
    saved_per_day = max(0, regional_avg_daily - forecast["avg_daily_gallons"])
    return {
        "gallons_saved_this_month": round(saved_per_day * datetime.now().day, 1),
        "gallons_saved_projected_year": round(saved_per_day * 365, 1),
        "dollars_saved_projected_year": round(saved_per_day * 365 * TIER_1_RATE, 2),
        "badges": [b for b, cond in [
            ("Leak-Free Week", anomaly_count == 0),
            ("Under Tier 1", forecast["month_end_total_gallons"] <= forecast["tier1_limit_gallons"]),
            ("Below Regional Average", saved_per_day > 0),
        ] if cond],
    }
