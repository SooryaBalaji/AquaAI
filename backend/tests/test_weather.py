from data import build_dataset
from weather import build_forecast, fetch_noaa_forecast


def test_fetch_noaa_forecast_always_returns_seven_highs():
    # In most test environments this will hit the real network and either
    # succeed or fail; either way it must fall back cleanly and never raise.
    result = fetch_noaa_forecast(37.3382, -121.8863)
    assert "source" in result
    assert len(result["daily_highs"]) == 7


def test_build_forecast_shape():
    readings = build_dataset(seed=1)
    forecast = build_forecast(readings, lat=37.3382, lon=-121.8863, tier1_limit_gal=4500)
    assert forecast["tier1_limit_gallons"] == 4500
    assert len(forecast["projected_daily"]) == 7
    assert forecast["month_end_total_gallons"] >= 0
    assert forecast["bill_estimate_dollars"] >= 0


def test_lower_tier_limit_breaches_sooner():
    readings = build_dataset(seed=1, household_size=8)  # a heavy user
    generous = build_forecast(readings, 37.3, -121.9, tier1_limit_gal=50_000)
    strict = build_forecast(readings, 37.3, -121.9, tier1_limit_gal=1_000)
    assert generous["tier_breach_day_of_month"] is None
    assert strict["tier_breach_day_of_month"] is not None
