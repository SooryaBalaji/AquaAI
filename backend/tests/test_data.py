from data import build_dataset


def test_build_dataset_shape():
    readings = build_dataset(seed=1)
    assert len(readings) == 60 * 96  # 60 days, 96 fifteen-minute intervals per day
    assert all(r["gallons"] >= 0 for r in readings)


def test_build_dataset_is_deterministic_per_seed():
    a = build_dataset(seed=42)
    b = build_dataset(seed=42)
    assert [r["gallons"] for r in a] == [r["gallons"] for r in b]


def test_different_seeds_produce_different_usage():
    a = build_dataset(seed=1)
    b = build_dataset(seed=2)
    assert [r["gallons"] for r in a] != [r["gallons"] for r in b]


def test_household_size_scales_usage():
    small = build_dataset(seed=1, household_size=1)
    large = build_dataset(seed=1, household_size=8)
    small_total = sum(r["gallons"] for r in small)
    large_total = sum(r["gallons"] for r in large)
    assert large_total > small_total


def test_plants_at_least_two_anomalies():
    readings = build_dataset(seed=1)
    injected_days = {r["day"] for r in readings if r["injected_anomaly"]}
    assert 2 <= len(injected_days) <= 3
