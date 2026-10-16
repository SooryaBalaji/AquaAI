from anomaly_model import engineer_features, train_anomaly_model
from data import build_dataset


def test_engineer_features_matches_reading_count():
    readings = build_dataset(seed=1)
    features = engineer_features(readings)
    assert len(features) == len(readings)
    assert all(len(f) == 7 for f in features)


def test_finds_the_planted_anomalies():
    readings = build_dataset(seed=7)
    _, anomalies = train_anomaly_model(readings)
    injected_count = sum(1 for r in readings if r["injected_anomaly"])
    found_injected = sum(1 for a in anomalies if a["was_injected_leak"])
    # Not every planted anomaly is guaranteed to be flagged (contamination
    # is a fixed fraction of all readings), but the model should catch a
    # meaningful share of them, not zero.
    assert found_injected > 0
    assert found_injected <= injected_count


def test_anomaly_count_is_within_expected_contamination_range():
    readings = build_dataset(seed=1)
    _, anomalies = train_anomaly_model(readings)
    # contamination=0.02 on ~5760 readings should flag roughly 115, give
    # generous slack since Isolation Forest's contamination is approximate.
    assert 50 <= len(anomalies) <= 250
