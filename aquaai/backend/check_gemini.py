import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()
key = os.environ.get("GEMINI_API_KEY", "").strip()
if not key:
    raise SystemExit("GEMINI_API_KEY is not set in backend/.env")

base = "https://generativelanguage.googleapis.com/v1beta"
headers = {"x-goog-api-key": key, "content-type": "application/json"}

start = time.time()
try:
    r = requests.get(f"{base}/models?pageSize=1", headers=headers, timeout=15)
    print(f"reach Google: HTTP {r.status_code} in {time.time() - start:.1f}s")
    if r.status_code != 200:
        print(r.text[:300])
except requests.RequestException as e:
    raise SystemExit(f"cannot reach Google: {type(e).__name__}. Check VPN, firewall or antivirus.")

models = [os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"), "gemini-3.5-flash-lite"]
for model in dict.fromkeys(models):
    start = time.time()
    try:
        r = requests.post(
            f"{base}/models/{model}:generateContent",
            headers=headers,
            json={"contents": [{"role": "user", "parts": [{"text": "Say hello in five words."}]}]},
            timeout=60,
        )
        took = time.time() - start
        if r.status_code == 200:
            parts = r.json()["candidates"][0]["content"]["parts"]
            print(f"{model}: OK in {took:.1f}s: {''.join(p.get('text', '') for p in parts)[:60]}")
        else:
            print(f"{model}: HTTP {r.status_code} in {took:.1f}s: {r.text[:200]}")
    except requests.RequestException as e:
        print(f"{model}: {type(e).__name__} after {time.time() - start:.1f}s")
