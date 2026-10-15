
import statistics

from sklearn.ensemble import IsolationForest

from config import RNG_SEED


def engineer_features(readings):
    by_hour = {}
    for r in readings:
        by_hour.setdefault(round(r["hour"]), []).append(r["gallons"])
    hour_median = {h: statistics.median(v) for h, v in by_hour.items()}

    features = []
    for i, r in enumerate(readings):
        window = readings[max(0, i - 3):i + 1]
        rolling_avg = sum(x["gallons"] for x in window) / len(window)
        features.append([
            r["gallons"],
            r["hour"] / 24,
            r["dow"] / 6,
            1.0 if r["hour"] < 5 else 0.0,                       # is_night
            1.0 if r["dow"] in (1, 5) and r["hour"] < 7 else 0.0,  # irrigation window
            rolling_avg,
            r["gallons"] - hour_median.get(round(r["hour"]), r["gallons"]),
        ])
    return features


def train_anomaly_model(readings):
    features = engineer_features(readings)
    model = IsolationForest(n_estimators=200, contamination=0.02, random_state=RNG_SEED)
    model.fit(features)
    scores = model.decision_function(features)
    predictions = model.predict(features)  # -1 = anomaly, 1 = normal

    anomalies = []
    for r, score, pred in zip(readings, scores, predictions):
        if pred == -1:
            anomalies.append({
                "day": r["day"],
                "hour": round(r["hour"], 2),
                "gallons": r["gallons"],
                "anomaly_score": round(float(score), 4),
                "was_injected_leak": r["injected_anomaly"],
            })
    anomalies.sort(key=lambda a: a["anomaly_score"])
    return model, anomalies
