# AquaIQ v4
### Know your water.

A household water-intelligence app built for the Congressional App Challenge.
Written from scratch — no code reused from earlier drafts of this project.

## The idea, in one sentence
Most people only find out they had a leak when the bill arrives. AquaIQ
watches usage in real time, tells you the moment something looks wrong,
shows you the exact dollar cost of doing nothing about it, and lets you
ask it directly what's going on.

## What it actually does (5 tabs, one story)
1. **Dashboard** — today's usage against a daily budget, plus a Water Score.
2. **Leak Detective** — a real scikit-learn Isolation Forest, trained on 60
   days of this household's own 15-minute usage history, flags intervals
   that don't match its learned normal (a genuine leak, a stuck irrigation
   valve) instead of a hardcoded "over X gallons" rule.
3. **Forecast & Savings** — a 7-day usage projection corrected against a
   **live NOAA National Weather Service forecast** (api.weather.gov, free,
   no key), showing exactly when and by how much you'll cross into
   Tier 2 pricing.
4. **Report Waste** — upload a photo of public water waste (broken
   sprinkler, open hydrant); a MobileNetV2 convolutional neural network
   classifies it **entirely in your browser** via TensorFlow.js — no photo
   ever reaches a server — and AquaIQ drafts the report for you.
5. **Ask AquaIQ** — a chat assistant for plain-English questions like "why
   is my bill high?" or "do I have any leaks?" It's grounded: every
   question is answered using this household's actual dashboard, forecast,
   and leak data, not invented. If no API key is configured, or the
   request fails, it falls back to a rule-based answer built from the same
   real data — so the demo never goes blank in front of a judge.

## The three AI techniques, and why each one is there
| Where | Technique | Why this one |
|---|---|---|
| Leak Detective | Isolation Forest (scikit-learn) | Learns *this household's* normal from its own history — no fixed threshold, explainable, cheap to train (~1 second) |
| Report Waste | MobileNetV2 CNN (TensorFlow.js) | Runs free, in the browser, with zero backend cost and a real privacy win (no photo upload) |
| Ask AquaIQ | Claude (Anthropic API), grounded in real app data | A natural-language layer over the other two — genuinely different from a prediction model, and honest about what it does and doesn't know |

Earlier drafts of this project also used a Keras/TensorFlow LSTM on the
backend. That's a ~500MB dependency for predicting seven numbers, and a
real risk during a live demo on a judge's machine or a free hosting tier —
cut in favor of a lighter, still-real weather-corrected projection.

## What's real vs. simulated
- **Real:** the NOAA weather forecast, the Isolation Forest training and
  inference, the MobileNetV2 image classification, the Claude API call.
- **Simulated, clearly labeled:** the household's water-meter readings.
  A real deployment would pull these from a utility's smart-meter API
  (e.g. WaterSmart); that requires a utility partnership this project
  doesn't have. The simulated data includes realistic daily/weekly
  patterns plus three planted anomalies so the leak detector has
  something genuine to find.

## Running it
```bash
cd backend
pip install -r requirements.txt   # installs in seconds — no TensorFlow here
python app.py
```
Then open `frontend/index.html` in a browser.

### To enable the Ask AquaIQ chat assistant
```bash
cp backend/.env.example backend/.env
# edit backend/.env and paste in a key from https://console.anthropic.com
```
The assistant works without a key too — it just answers from the real
data directly instead of holding a natural conversation. Never commit a
real `.env` file or share your API key.

## Project structure
```
aquaiq_v4/
├── backend/
│   ├── app.py              Flask routes only
│   ├── config.py           Shared constants (tier pricing, coordinates)
│   ├── data.py             Simulated household meter readings
│   ├── anomaly_model.py    Isolation Forest (Leak Detective)
│   ├── weather.py          NOAA forecast + tier-pricing projection
│   ├── score.py            Water Score + savings tracker
│   ├── civic.py            Report Waste categories + report generation
│   ├── assistant.py        Ask AquaIQ — grounded chat, with offline fallback
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html          Markup only
│   ├── css/styles.css
│   └── js/
│       ├── api.js          Shared fetch helper
│       ├── main.js         Tab switching + startup
│       ├── dashboard.js
│       ├── leaks.js
│       ├── forecast.js
│       ├── report.js
│       └── assistant.js
└── README.md
```

## API endpoints
| Endpoint | Method | Returns |
|---|---|---|
| `/health` | GET | Server status |
| `/api/dashboard` | GET | Today's usage + hourly breakdown |
| `/api/anomalies` | GET | Isolation Forest results |
| `/api/forecast` | GET | 7-day NOAA-corrected forecast + tier breach |
| `/api/score` | GET | Water Score breakdown |
| `/api/savings` | GET | Gallons/dollars saved + badges |
| `/api/cnn-labels` | GET | Waste category dictionary for the browser CNN |
| `/api/civic-report` | POST | Generates a report ID, email draft, Open311-style payload |
| `/api/ask` | POST | `{"question": "..."}` → grounded chat answer |
