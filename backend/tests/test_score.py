from score import compute_savings, compute_score


def _fake_forecast(month_end_total, tier1_limit, avg_daily=100):
    return {
        "month_end_total_gallons": month_end_total,
        "tier1_limit_gallons": tier1_limit,
        "avg_daily_gallons": avg_daily,
    }


def test_score_is_higher_with_fewer_anomalies():
    forecast = _fake_forecast(3000, 4500)
    clean = compute_score(forecast, anomaly_count=0)
    messy = compute_score(forecast, anomaly_count=20)
    assert clean["score"] > messy["score"]


def test_score_penalizes_crossing_tier1():
    under = compute_score(_fake_forecast(3000, 4500), anomaly_count=0)
    over = compute_score(_fake_forecast(6000, 4500), anomaly_count=0)
    assert under["breakdown"]["tier_compliance"] > over["breakdown"]["tier_compliance"]


def test_score_components_sum_to_total():
    result = compute_score(_fake_forecast(3000, 4500), anomaly_count=3)
    assert sum(result["breakdown"].values()) == result["score"]


def test_savings_scale_with_household_size():
    forecast = _fake_forecast(3000, 4500, avg_daily=100)
    small_household = compute_savings(forecast, anomaly_count=0, household_size=2)
    large_household = compute_savings(forecast, anomaly_count=0, household_size=8)
    # The same 100 gal/day looks frugal for an 8-person household and
    # wasteful for a 2-person one, so savings should differ.
    assert small_household["gallons_saved_projected_year"] != large_household["gallons_saved_projected_year"]


def test_badges_awarded_correctly():
    good = compute_savings(_fake_forecast(3000, 4500, avg_daily=50), anomaly_count=0, household_size=4)
    assert "Leak-Free Week" in good["badges"]
    assert "Under Tier 1" in good["badges"]

    bad = compute_savings(_fake_forecast(6000, 4500, avg_daily=500), anomaly_count=5, household_size=4)
    assert "Leak-Free Week" not in bad["badges"]
    assert "Under Tier 1" not in bad["badges"]
