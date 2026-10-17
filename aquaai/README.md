# AquaAI

**A household water-intelligence app: log how much water a household uses, and it shows where you stand against your budget, projects the month, scores your usage, and answers questions grounded in your own numbers.**

Most people learn about high water use when the bill arrives. AquaAI makes the numbers visible while there is still time to act. It:

1. **Tracks:** records daily usage per household, by hand or from a CSV, and compares it with a daily budget derived from the household's Tier 1 limit.
2. **Forecasts:** projects the rest of the month from recent use, adjusted by the National Weather Service forecast, and shows the day usage is expected to cross into Tier 2 pricing and the estimated bill.
3. **Scores:** gives a Water Score once a household has 7 days of data.
4. **Detects leaks:** an Isolation Forest trained on a household's own 15-minute readings flags intervals that do not match its normal pattern. This needs interval data, so it currently runs on the Demo household.
5. **Answers:** a chat assistant (Gemini) that is given the selected household's dashboard, forecast and score, and falls back to rule-based answers when no key is set.
6. **Reports waste:** classifies a photo of public water waste in the browser with TensorFlow.js, so the photo is never uploaded, and drafts the report.

---

## Quick start

You need **Python 3.10+**. Docker is optional.

**1. Install** (once, in the project folder):

| Windows (PowerShell) | macOS / Linux |
|---|---|
| `cd backend` | `cd backend` |
| `py -m venv .venv` | `python3 -m venv .venv` |
| `.venv\Scripts\activate` | `source .venv/bin/activate` |
| `pip install -r requirements.txt` | `pip install -r requirements.txt` |

**2. Add your keys (optional).** Copy `backend/.env.example` to `backend/.env` and fill in only what you need. With no `.env` at all, AquaAI uses local accounts and a local SQLite file. See [Keys](#keys-yours-someone-elses-or-none) for what each one adds.

```
GEMINI_API_KEY=...          # live assistant answers (free: aistudio.google.com/apikey)
FIREBASE_PROJECT_ID=...     # Firebase sign-in and Firestore; see docs/DEPLOY.md
```

The file is read once at startup, so restart the app after changing it.

**3. Run it:**

```
python app.py
```

Open http://localhost:5000, choose **Get started** and create an account.

**4. Try it with sample data.** Create a household in the **Households** tab, open **Add data**, and upload `sample_usage.csv` (45 days of synthetic usage). The dashboard, forecast, score and assistant then have numbers to work with.

Check what is running at http://localhost:5000/healthz. It reports the active storage (`sqlite` or `firestore`) and sign-in provider (`local` or `firebase`).

| Route | What it is |
|---|---|
| `/` | landing page |
| `/app` | the application (`/app#signup` and `/app#signin` open the account form) |
| `/privacy` | privacy policy |
| `/healthz` | status, storage and sign-in provider |

### Where the data comes from

| Source | What it provides |
|---|---|
| **Your households** | Start with no data, so every value is zero. Usage is whatever you add on the **Add data** page, stored as one total per day. |
| **Demo household** | Generated sample data: 60 days of 15-minute readings with planted leaks. Read-only, and the only household the Leak Detective and hourly chart work on. |
| **Weather** | National Weather Service (api.weather.gov, no key). If it is unreachable, the forecast says it fell back to simulated weather. |
| **City and ZIP search** | Open-Meteo geocoding, and Zippopotam.us for ZIP codes. |
| `sample_usage.csv` | Synthetic data for testing the CSV upload. |

---

## How it works

### Add data

Usage is entered as a daily total, in gallons or CCF (1 CCF = 748.052 gallons), through the form or a CSV.

```
date,gallons
2026-10-15,180
10/16/2026,172.5
```

A header row is optional. Dates may be `YYYY-MM-DD` or `M/D/YYYY`. Rows that cannot be read are skipped and counted. Saving a date that already exists replaces it.

Server-side limits: 0 to 100,000 gallons per day, dates from 2000-01-01 to tomorrow, 1,000 entries per request, 2,000 days per household. Only the household's owner can add or delete data. The Demo household cannot be edited.

### Forecast

The projection uses the average of the last 30 logged days. Each of the next 7 days is scaled by 2.5% per degree Fahrenheit that the NWS forecast high is above 85°F. The rest of the month uses the plain average. From that it reports the month-end total, the day Tier 1 is exceeded (if any), gallons remaining in Tier 1, and an estimated bill from the Tier 1 and Tier 2 rates in `backend/config.py`.

The daily budget is the household's Tier 1 limit divided by the days in the month.

### Water Score

For user households the score is 0 to 100, from two components, and appears after 7 days of data:

- **Tier compliance (30):** full marks if the projected month-end total stays within the Tier 1 limit, reduced otherwise.
- **Consistency (30):** based on day-to-day variation over the last 14 days.

The leak component (40 points on the Demo household) is not scored for manual households, because it needs interval readings.

### Leak Detective

An Isolation Forest (scikit-learn, 200 trees, 2% contamination) is trained on a household's own 15-minute history and flags intervals that deviate from it, rather than applying a fixed "over X gallons" threshold. Daily totals do not contain enough information for this, so manual households show an explanation instead of results. Importing hourly or 15-minute readings would enable it.

### Ask AquaAI

The assistant never answers from general knowledge about the household. Each request builds a context from the selected household's dashboard, forecast, score and leak results (or, for a household with no data, a note saying so), and sends it to Gemini with the question. If `GEMINI_API_KEY` is missing, the request fails, or the key is rejected, it answers from the same context with simple rules.

The label under each answer says which path was used: **Answered by Gemini**, or **offline** with the reason (`no API key configured`, or the error Google returned). The model defaults to `gemini-3.8-flash`; override it with `GEMINI_MODEL`.

### Report Waste

A MobileNetV2 model runs in the browser through TensorFlow.js and classifies an uploaded photo into a waste category. The image is not sent anywhere. The server only receives the resulting category to draft a report, with an Open311-style payload.

### Accounts and storage

| | Development | Production |
|---|---|---|
| **Sign-in** | local email and password accounts | Firebase Authentication: email and password, Google, password reset, email verification |
| **Storage** | SQLite (`backend/aquaai.db`) | Firestore |

Storage is chosen automatically: Firestore when service account credentials load (`FIREBASE_CREDENTIALS_PATH` for a file, or `FIREBASE_CREDENTIALS_JSON` for the full JSON on a host), otherwise SQLite. The sign-in provider is Firebase when `FIREBASE_WEB_API_KEY` is set, otherwise local. Verify both at `/healthz`.

Creating or changing a household requires a verified email when Firebase sign-in is used. Each account can have up to 5 households. Deleting an account removes its households, usage and settings.

Set `APP_ENV=production` on deployed servers. The app then refuses to start with an unsafe setup: local accounts, SQLite storage, or missing Firebase settings. Leave it unset on your own machine.

Notification preferences are stored, but email and text alerts are not yet delivered.

---

## Deployment

The app is one web service. The `Dockerfile` and `render.yaml` are set up for Render, which builds the image and checks `/healthz`.

1. Push the project to GitHub.
2. In Render, choose New, Blueprint, and select the repository.
3. Enter the `FIREBASE_*` values and, optionally, `GEMINI_API_KEY`.
4. After the first deploy, add the service's domain under Firebase, Authentication, Settings, Authorized domains. Without it, sign-in fails with an "unauthorized domain" error.

Full Firebase and Render steps are in [docs/DEPLOY.md](docs/DEPLOY.md). To run the image yourself:

```
docker build -t aquaai .
docker run --rm -p 5000:5000 --env-file backend/.env aquaai
```

Do not bake `.env` or the service account file into the image. They are excluded by `.dockerignore` and `.gitignore`.

---

## API

All `/api/` routes return JSON. Routes marked *household* accept `?profile=<id>` (the Demo household is used if it is omitted) and `?today=YYYY-MM-DD`, the browser's local date, which the server accepts only within one day of its own UTC date.

| Endpoint | Method | Purpose |
|---|---|---|
| `/healthz` | GET | status, storage and sign-in provider |
| `/api/auth/config` | GET | public Firebase settings for the browser |
| `/api/auth/register`, `/api/auth/login` | POST | local accounts (development only) |
| `/api/auth/me` | GET | current user |
| `/api/account` | DELETE | delete the account and its data |
| `/api/settings` | GET, PUT | notification preferences |
| `/api/profiles` | GET, POST | list and create households |
| `/api/profiles/<id>` | PATCH, DELETE | edit or delete a household (owner only) |
| `/api/geocode` | GET | city and ZIP search |
| `/api/dashboard` | GET | today's usage and budget *(household)* |
| `/api/anomalies` | GET | Leak Detective results *(household)* |
| `/api/forecast` | GET | month projection and tier breach *(household)* |
| `/api/score` | GET | Water Score *(household)* |
| `/api/savings` | GET | savings and badges *(household)* |
| `/api/usage` | GET | list logged days *(household)* |
| `/api/usage` | PUT | add or replace days: `{"entries": [{"date", "gallons"}]}` (owner only) |
| `/api/usage` | DELETE | `?date=YYYY-MM-DD` or `?all=true` (owner only) |
| `/api/ask` | POST | `{"question": "..."}`, grounded answer *(household)* |
| `/api/cnn-labels` | GET | waste categories for the browser model |
| `/api/civic-report` | POST | draft a waste report |

### Security

- Every protected route verifies the Firebase ID token (or the local token in development) and checks ownership of the household.
- Rate limits: 600 requests per hour by default, with tighter limits on sign-up, sign-in, account deletion, geocoding, usage writes, and the assistant (8 per minute, 100 per day).
- Responses carry a Content-Security-Policy, and `Strict-Transport-Security` in production. Firestore rules deny all direct browser access; only the backend reads and writes data.
- User-supplied text is escaped before it is rendered.

---

## Configuration

Secrets come only from the environment. Put them in `backend/.env` (one `NAME=value` per line); variables already set in your shell win. Every one is optional for local development.

| Variable | Used for | Without it |
|---|---|---|
| `GEMINI_API_KEY` | live assistant answers | rule-based answers |
| `GEMINI_MODEL` | choose the Gemini model | `gemini-3.8-flash` |
| `GEMINI_FALLBACK_MODEL` | model tried once when the main one is busy | `gemini-3.5-flash-lite` |
| `GEMINI_BASE_URL` | point the assistant at a different Gemini-compatible endpoint (used for testing) | Google's API |
| `FIREBASE_PROJECT_ID`, `FIREBASE_WEB_API_KEY`, `FIREBASE_APP_ID`, `FIREBASE_AUTH_DOMAIN` | Firebase sign-in in the browser | local accounts |
| `FIREBASE_CREDENTIALS_PATH` or `FIREBASE_CREDENTIALS_JSON` | backend access to Firebase and Firestore | SQLite storage |
| `SECRET_KEY` | signing local-account tokens | an insecure development default |
| `APP_ENV` | `production` turns on startup safety checks and HSTS | `development` |
| `PORT` | listening port | `5000` |
| `FRONTEND_ORIGIN` | CORS, only if the frontend is on another domain | same origin only |
| `RATELIMIT_STORAGE_URI` | shared rate limits across servers (`redis://...`) | in-memory, per process |
| `WEB_CONCURRENCY` | gunicorn worker count | `1` |

### Keys: yours, someone else's, or none

**Everyone who runs AquaAI uses their own keys**, in their own `backend/.env`. That file is in `.gitignore`, so keys are never committed. Do not paste keys into code, issues or chat. If one leaks, delete it at its provider and create a new one.

**No keys at all** still gives you the whole app:

| Feature | With no keys |
|---|---|
| Accounts, households, Add data, dashboard, forecast, score | works fully (local accounts, SQLite) |
| Weather | works; NWS needs no key |
| Ask AquaAI | rule-based answers; add a free Gemini key for live answers |
| Production deploy | needs Firebase |

---

## Testing

```
cd backend
pip install -r requirements-dev.txt
python -m pytest
```

The suite (115 tests, run in CI on every push) covers:

- Auth: local accounts, token checks, email verification rules.
- Households: creation limits, edit, ownership, and cleanup on delete.
- Usage entry: validation, limits, replace-by-date, delete one and clear all, owner-only writes.
- Analytics for households with no data, under 7 days, and with enough data.
- Assistant: Gemini success, missing key, failed call, and the no-data context (the network is mocked).
- Production startup checks and security headers.
- Geocoding, settings, forecast and score logic.

Firebase, Google sign-in, Firestore and the live Gemini and NWS calls are not exercised by the suite; check them by hand against your own project (`/healthz` should report `firebase` and `firestore` once configured).

In PyCharm, mark `backend` as **Sources Root** so test imports resolve.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `/healthz` says `"storage": "sqlite"` but you want Firestore | The service account did not load. Check `FIREBASE_CREDENTIALS_PATH` (a real file path) or `FIREBASE_CREDENTIALS_JSON`, then restart. |
| Changes to `.env` have no effect | The file is read at startup. Restart `python app.py`. |
| Assistant label says "offline (no API key configured)" | `GEMINI_API_KEY` is not being read. Check the spelling, that the file is `backend/.env`, and restart. |
| Assistant label says "offline (the AI service did not respond)" | The key was found but the call failed: an invalid key, a rate limit, or no network. |
| Google sign-in popup opens a broken page | `FIREBASE_AUTH_DOMAIN` must end in `.firebaseapp.com`. Check it for a typo such as `.co`. |
| Sign-in fails with "unauthorized domain" | Add the domain under Firebase, Authentication, Settings, Authorized domains. |
| Google sign-in shows a generic error | Enable Google under Firebase, Authentication, Sign-in method. |
| App refuses to start with `APP_ENV=production` | The error lists what is missing: usually Firebase settings or Firestore credentials. |
| Dashboard shows zeros | Expected for a new household. Add data on the **Add data** tab, or upload `sample_usage.csv`. |
| Leak Detective says it needs interval readings | Expected for households with daily totals. Only the Demo household has 15-minute data. |
| Water Score shows "–" | It needs 7 days of entries. |
| Forecast says "simulated" weather | The National Weather Service could not be reached, or the location is outside the US. |
| `address already in use` on port 5000 | Another copy is running. Stop it, or set `PORT=5001`. |
| `pip install` says the environment is externally managed | Use a virtual environment as in Quick start. |
| PyCharm underlines `import storage` in tests | Mark `backend` as Sources Root. |

---

## Project structure

```
aquaai/
├── backend/
│   ├── app.py               Flask routes
│   ├── auth.py              Firebase token checks, or local accounts
│   ├── checks.py            production startup checks
│   ├── config.py            shared constants and tier rates
│   ├── data.py              generated sample readings (Demo household)
│   ├── usage.py             manual daily usage: validation and analytics
│   ├── anomaly_model.py     Isolation Forest (Leak Detective)
│   ├── weather.py           NWS forecast and tier projection
│   ├── score.py             Water Score and savings
│   ├── civic.py             waste categories and report drafts
│   ├── assistant.py         Ask AquaAI (Gemini, offline fallback)
│   ├── geocode.py           city and ZIP search
│   ├── profiles.py          households
│   ├── settings.py          per-user settings
│   ├── storage.py           Firestore or SQLite, picked automatically
│   ├── firebase_client.py   Firebase Admin setup
│   ├── gunicorn.conf.py, Procfile
│   ├── requirements.txt, requirements-dev.txt
│   ├── .env.example
│   └── tests/
├── frontend/
│   ├── landing.html, index.html, privacy.html
│   ├── css/                 tokens (light and dark), styles, landing
│   └── js/                  one file per tab, plus auth, theme and shared helpers
├── docs/DEPLOY.md
├── Dockerfile, render.yaml, firestore.rules
└── sample_usage.csv
```
