"""
AquaAI backend entry point.

Every household-data endpoint (dashboard, anomalies, forecast, score,
savings, ask) takes a ?profile=<id> query parameter, defaulting to the
public demo household if omitted. A profile is only readable if it's
public or owned by the signed-in caller (see profiles.can_view).

Auth is a Bearer JWT in the Authorization header, issued by
POST /api/auth/login or /api/auth/register. It's optional for reading
public data and required for creating or deleting a household.

  data.py             simulated household meter readings, scaled by size
  anomaly_model.py     Isolation Forest (leak/anomaly detection)
  weather.py           NOAA forecast + tier-pricing projection
  score.py             Water Score + savings tracker
  civic.py              Report Waste categories + report generation
  assistant.py          chat-style AI assistant, grounded in this data
  profiles.py           household profile logic + per-profile model cache
  storage.py             Firestore or local SQLite, picked automatically
  auth.py                Firebase token checks (production) or local accounts (development)
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, g, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

import assistant
import auth
import checks
import profiles
from civic import WASTE_CATEGORIES, build_civic_report
from config import DAYS_IN_MONTH
from score import compute_savings, compute_score
from weather import build_forecast

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("aquaai.app")

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

IS_PRODUCTION = checks.is_production()
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

_proxy_hops = int(os.environ.get("TRUSTED_PROXIES", "1" if IS_PRODUCTION else "0"))
if _proxy_hops:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=_proxy_hops, x_proto=_proxy_hops, x_host=_proxy_hops)

_frontend_origin = os.environ.get("FRONTEND_ORIGIN")
if _frontend_origin:
    CORS(app, origins=_frontend_origin.split(","))
elif not IS_PRODUCTION:
    CORS(app, origins="*")

profiles.init()

if IS_PRODUCTION:
    _problems = checks.production_problems(auth.provider(), profiles.storage_backend(), auth.SECRET_KEY)
    if _problems:
        raise RuntimeError("Refusing to start in production:\n- " + "\n- ".join(_problems))


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
@app.before_request
def load_current_user():
    g.user = auth.user_from_auth_header(request.headers.get("Authorization"))


def _rate_key():
    user = g.get("user")
    return f"user:{user['id']}" if user else get_remote_address()


limiter = Limiter(
    _rate_key,
    app=app,
    default_limits=["600 per hour"],
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI") or "memory://",
)
limiter.enabled = os.environ.get("RATELIMIT_ENABLED", "1") == "1"


def require_verified():
    user = require_auth()
    if not user.get("email_verified"):
        raise auth.AuthError("Verify your email address first. Check your inbox for the link.", status=403, code="email_not_verified")
    return user


def require_auth():
    """Returns the current user dict, or raises via abort if signed out."""
    if not g.get("user"):
        raise auth.AuthError("Sign in required.", status=401)
    return g.user


# ---------------------------------------------------------------------------
# Structured error handling. Every error, expected or not, comes back as
# {"error": "..."} with an appropriate status code, never a raw traceback.
# ---------------------------------------------------------------------------
@app.errorhandler(auth.AuthError)
def handle_auth_error(e):
    body = {"error": e.message}
    if e.code:
        body["code"] = e.code
    return jsonify(body), e.status


@app.errorhandler(429)
def handle_rate_limit(e):
    return jsonify({"error": "Too many requests. Wait a moment and try again."}), 429


@app.errorhandler(profiles.ValidationError)
def handle_validation_error(e):
    return jsonify({"error": str(e)}), 400


@app.errorhandler(404)
def handle_404(e):
    return jsonify({"error": "not found"}), 404


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    if isinstance(e, HTTPException):
        return jsonify({"error": e.description or e.name}), e.code
    log.exception("unhandled error on %s %s", request.method, request.path)
    return jsonify({"error": "something went wrong on our end"}), 500


_CSP = os.environ.get("CSP_OVERRIDE") or (
    "default-src 'self'; "
    "script-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://www.gstatic.com; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self'; "
    "connect-src 'self' https:; "
    "frame-src https:; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(self)")
    if os.environ.get("DISABLE_CSP") != "1" and not request.path.startswith("/api/"):
        response.headers.setdefault("Content-Security-Policy", _CSP)
    if IS_PRODUCTION:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.route("/")
def landing_page():
    return send_from_directory(FRONTEND_DIR, "landing.html")


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@app.get("/api/auth/config")
def auth_config():
    return jsonify(auth.public_config())


@app.get("/healthz")
@limiter.exempt
def healthz():
    return jsonify({"status": "ok", "storage": profiles.storage_backend(), "auth": auth.provider()})


@app.post("/api/auth/register")
@limiter.limit("10 per hour")
def register():
    body = request.get_json(force=True, silent=True) or {}
    token, user = auth.register(body.get("email"), body.get("password"))
    return jsonify({"token": token, "user": user}), 201


@app.post("/api/auth/login")
@limiter.limit("10 per minute")
def login():
    body = request.get_json(force=True, silent=True) or {}
    token, user = auth.login(body.get("email"), body.get("password"))
    return jsonify({"token": token, "user": user})


@app.get("/api/auth/me")
def me():
    user = require_auth()
    return jsonify({"user": user})


@app.delete("/api/account")
@limiter.limit("3 per hour")
def delete_account_route():
    user = require_auth()
    removed = profiles.delete_all_for_owner(user["id"])
    auth.delete_account(user["id"])
    log.info("account %s deleted with %d household(s)", user["id"], removed)
    return jsonify({"deleted": True, "households_removed": removed})


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------
@app.get("/api/profiles")
def list_profiles_route():
    owner_id = g.user["id"] if g.get("user") else None
    return jsonify([{k: v for k, v in p.items() if k != "seed"} for p in profiles.list_profiles(owner_id)])


@app.post("/api/profiles")
@limiter.limit("10 per hour")
def create_profile_route():
    user = require_verified()
    body = request.get_json(force=True, silent=True) or {}
    profile = profiles.create_profile(
        owner_id=user["id"],
        name=body.get("name"),
        lat=body.get("lat"),
        lon=body.get("lon"),
        household_size=body.get("household_size"),
        tier1_limit_gal=body.get("tier1_limit_gal"),
    )
    profiles.get_household_data(profile["id"])  # train immediately so the first request is fast
    return jsonify({k: v for k, v in profile.items() if k != "seed"}), 201


@app.delete("/api/profiles/<profile_id>")
def delete_profile_route(profile_id):
    user = require_auth()
    ok = profiles.delete_profile(profile_id, user["id"])
    if not ok:
        return jsonify({"error": "cannot delete this profile"}), 403
    return jsonify({"deleted": profile_id})


# ---------------------------------------------------------------------------
# Household data, scoped to the requested profile
# ---------------------------------------------------------------------------
def _load_authorized_profile():
    """Returns (profile, household_data) for ?profile=<id>, checked
    against the current user's access. Raises AuthError on denial."""
    profile_id = request.args.get("profile", profiles.DEFAULT_PROFILE_ID)
    profile = profiles.get_profile(profile_id)
    user_id = g.user["id"] if g.get("user") else None

    if not profile:
        raise auth.AuthError("Unknown household.", status=404)
    if not profiles.can_view(profile, user_id):
        raise auth.AuthError("You don't have access to this household.", status=403)

    household = profiles.get_household_data(profile_id)
    return profile, household


def _dashboard_data(readings, tier1_limit_gal):
    today_readings = [r for r in readings if r["day"] == 59]
    today_total = round(sum(r["gallons"] for r in today_readings), 1)
    hourly = {}
    for r in today_readings:
        hourly[int(r["hour"])] = hourly.get(int(r["hour"]), 0) + r["gallons"]

    last_7_days = []
    for d in range(53, 60):
        day_total = round(sum(r["gallons"] for r in readings if r["day"] == d), 1)
        last_7_days.append(day_total)

    return {
        "today_total_gallons": today_total,
        "hourly_breakdown": [round(hourly.get(h, 0), 1) for h in range(24)],
        "daily_limit_gallons": round(tier1_limit_gal / DAYS_IN_MONTH, 1),
        "last_7_days_gallons": last_7_days,
    }


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "profiles": len(profiles.list_profiles()),
        "storage": profiles.storage_backend(),
    })


@app.get("/api/dashboard")
def dashboard():
    profile, household = _load_authorized_profile()
    return jsonify(_dashboard_data(household["readings"], profile["tier1_limit_gal"]))


@app.get("/api/anomalies")
def anomalies():
    profile, household = _load_authorized_profile()
    found = household["anomalies"]

    days_back = request.args.get("days", type=int)
    if days_back:
        cutoff = 59 - days_back
        found = [a for a in found if a["day"] > cutoff]

    confirmed_only = request.args.get("confirmed_only") == "true"
    if confirmed_only:
        found = [a for a in found if a["was_injected_leak"]]

    weekly_counts = {}
    weekly_source = [a for a in household["anomalies"] if a["was_injected_leak"]] if confirmed_only else household["anomalies"]
    for a in weekly_source:
        week = a["day"] // 7
        weekly_counts[week] = weekly_counts.get(week, 0) + 1
    weekly_series = [weekly_counts.get(w, 0) for w in range(9)]  # 60 days is just under 9 weeks

    return jsonify({
        "model": "IsolationForest (scikit-learn), n_estimators=200, contamination=0.02",
        "trained_on_readings": len(household["readings"]),
        "anomalies_found": len(found),
        "anomalies": found[:15],
        "weekly_counts": weekly_series,
    })


@app.get("/api/forecast")
def forecast():
    profile, household = _load_authorized_profile()
    return jsonify(build_forecast(household["readings"], profile["lat"], profile["lon"], profile["tier1_limit_gal"]))


@app.get("/api/score")
def score():
    profile, household = _load_authorized_profile()
    f = build_forecast(household["readings"], profile["lat"], profile["lon"], profile["tier1_limit_gal"])
    return jsonify(compute_score(f, len(household["anomalies"])))


@app.get("/api/savings")
def savings():
    profile, household = _load_authorized_profile()
    f = build_forecast(household["readings"], profile["lat"], profile["lon"], profile["tier1_limit_gal"])
    return jsonify(compute_savings(f, len(household["anomalies"]), profile["household_size"]))


@app.get("/api/cnn-labels")
def cnn_labels():
    return jsonify(WASTE_CATEGORIES)


@app.post("/api/civic-report")
def civic_report():
    body = request.get_json(force=True, silent=True) or {}
    result = build_civic_report(body.get("category", "unclassified"), body.get("lat"), body.get("lon"))
    return jsonify(result)


@app.post("/api/ask")
@limiter.limit("8 per minute;100 per day")
def ask():
    body = request.get_json(force=True, silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400
    if len(question) > 500:
        return jsonify({"error": "Keep questions under 500 characters."}), 400

    profile, household = _load_authorized_profile()
    f = build_forecast(household["readings"], profile["lat"], profile["lon"], profile["tier1_limit_gal"])
    anomaly_count = len(household["anomalies"])
    ctx = {
        "profile_name": profile["name"],
        "dashboard": _dashboard_data(household["readings"], profile["tier1_limit_gal"]),
        "forecast": f,
        "anomaly_count": anomaly_count,
        "score": compute_score(f, anomaly_count),
        "savings": compute_savings(f, anomaly_count, profile["household_size"]),
    }
    return jsonify(assistant.answer_question(question, ctx))


if __name__ == "__main__":
    log.info("AquaAI backend starting, %d profile(s) seeded", len(profiles.list_profiles()))
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", port=int(os.environ.get("PORT", 5000)))
