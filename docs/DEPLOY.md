# Deploying AquaAI

AquaAI runs as one web service: the Flask backend also serves the pages. In production it uses Firebase Authentication for login and Firestore for data.

## 1. Create the Firebase project

1. Go to https://console.firebase.google.com and add a project.
2. Build, Authentication, Get started. Under Sign-in method, enable **Email/Password** and **Google**.
3. Build, Firestore Database, Create database. Pick a region near your users. Open the Rules tab, paste in the contents of `firestore.rules`, and publish. This blocks all direct browser access, because only the backend reads and writes data.
4. Project settings, General, Your apps, add a **Web app**. Copy `apiKey`, `appId`, `authDomain` and `projectId`. These are public identifiers, not secrets.
5. Project settings, Service accounts, Generate new private key. This downloads a JSON file. It is a secret. Never commit it or paste it anywhere public.

## 2. Run it locally against Firebase (optional)

Put the values in `backend/.env`, using `FIREBASE_CREDENTIALS_PATH` for the JSON file's location. Run `python app.py`. The health page at http://localhost:5000/healthz should show `"auth": "firebase"` and `"storage": "firestore"`.

## 3. Deploy to Render

1. Push this folder to a GitHub repository.
2. On https://render.com choose New, Blueprint, and select the repository. It reads `render.yaml` and builds the `Dockerfile`.
3. Fill in the environment variables when asked:
   - `FIREBASE_PROJECT_ID`, `FIREBASE_WEB_API_KEY`, `FIREBASE_APP_ID`, `FIREBASE_AUTH_DOMAIN` from step 4 above.
   - `FIREBASE_CREDENTIALS_JSON`: paste the **entire contents** of the service account JSON file.
   - `GEMINI_API_KEY` for live assistant answers (optional).
4. After the first deploy, copy the service's address, for example `aquaai.onrender.com`. In Firebase, Authentication, Settings, Authorized domains, add it. Without this, sign in fails with an "unauthorized domain" error.

In production the app refuses to start if it would run unsafely: no Firebase configured, or SQLite storage. The deploy log then lists exactly what is missing.

## 4. After the first deploy

- Open `/healthz` and confirm Firebase and Firestore show as active.
- Create an account with a real email. A verification email should arrive. Check spam.
- Create a household and confirm it is still there after a redeploy.
- Open the Report Waste tab and run a photo. It loads its model from external servers, and the page security policy must allow that. If it fails, set `CSP_OVERRIDE` to a looser policy, or tell the maintainer.
- In Firebase, Authentication, Templates, edit the verification and reset emails so they say AquaAI.
- Restrict the Gemini key in Google AI Studio and set a spending limit.

## Limits to know about

- The free Render plan sleeps when idle, so the first visit after a quiet period takes about a minute.
- Rate limits live in each server's memory. That is accurate with one server. If you scale to several, set `RATELIMIT_STORAGE_URI` to a Redis address.
- Meter readings are simulated. Nothing is live until a real data source feeds the app.
- Back up Firestore with its scheduled exports before you hold anyone's real data.
