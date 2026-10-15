
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

import assistant
from anomaly_model import train_anomaly_model
from civic import WASTE_CATEGORIES, build_civic_report
from config import TIER_1_LIMIT_GAL, DAYS_IN_MONTH
from data import build_dataset
from score import compute_savings, compute_score
from weather import build_forecast

load_dotenv()

app = Flask(__name__)
CORS(app)

DATA = build_dataset()
ANOMALY_MODEL, ANOMALIES = train_anomaly_model(DATA)


def _dashboard_data():
    today_readings = [r for r in DATA if r["day"] == 59]
    today_total = round(sum(r["gallons"] for r in today_readings), 1)
    hourly = {}
    for r in today_readings:
        hourly[int(r["hour"])] = hourly.get(int(r["hour"]), 0) + r["gallons"]
    return {
        "today_total_gallons": today_total,
        "hourly_breakdown": [round(hourly.get(h, 0), 1) for h in range(24)],
        "daily_limit_gallons": round(TIER_1_LIMIT_GAL / DAYS_IN_MONTH, 1),
    }


@app.get("/health")
def health():
    return jsonify({"status": "ok", "readings_loaded": len(DATA), "anomalies_found": len(ANOMALIES)})


@app.get("/api/dashboard")
def dashboard():
    return jsonify(_dashboard_data())


@app.get("/api/anomalies")
def anomalies():
    return jsonify({
        "model": "IsolationForest (scikit-learn), n_estimators=200, contamination=0.02",
        "trained_on_readings": len(DATA),
        "anomalies_found": len(ANOMALIES),
        "anomalies": ANOMALIES[:15],
    })


@app.get("/api/forecast")
def forecast():
    return jsonify(build_forecast(DATA))


@app.get("/api/score")
def score():
    return jsonify(compute_score(build_forecast(DATA), len(ANOMALIES)))


@app.get("/api/savings")
def savings():
    return jsonify(compute_savings(build_forecast(DATA), len(ANOMALIES)))


@app.get("/api/cnn-labels")
def cnn_labels():
    return jsonify(WASTE_CATEGORIES)


@app.post("/api/civic-report")
def civic_report():
    body = request.get_json(force=True, silent=True) or {}
    result = build_civic_report(body.get("category", "unclassified"), body.get("lat"), body.get("lon"))
    return jsonify(result)


@app.post("/api/ask")
def ask():
    body = request.get_json(force=True, silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    f = build_forecast(DATA)
    ctx = {
        "dashboard": _dashboard_data(),
        "forecast": f,
        "anomaly_count": len(ANOMALIES),
        "score": compute_score(f, len(ANOMALIES)),
        "savings": compute_savings(f, len(ANOMALIES)),
    }
    return jsonify(assistant.answer_question(question, ctx))


if __name__ == "__main__":
    print(f"AquaIQ v4 backend — {len(DATA)} readings loaded, {len(ANOMALIES)} anomalies detected")
    app.run(debug=True, port=5000)
