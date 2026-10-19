import argparse
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

import assistant

parser = argparse.ArgumentParser(description="Check that Ask AquaAI can use Gemini.")
parser.add_argument("--url", help="a running AquaAI server, for example https://aquaai.onrender.com")
args = parser.parse_args()

if args.url:
    base = args.url.rstrip("/")
    try:
        health = requests.get(f"{base}/healthz", timeout=30).json()
    except (requests.RequestException, ValueError) as e:
        sys.exit(f"could not reach {base}: {type(e).__name__}")
    a = health.get("assistant") or {}
    print(f"server: {base}")
    print(f"key set on server: {a.get('key_set')}")
    print(f"model: {a.get('model')} (backup {a.get('backup_model')})")
    last = a.get("last_call") or {}
    print(f"last Gemini call: {'OK' if last.get('ok') else 'FAILED' if last.get('ok') is False else 'none yet'}"
          f"{' - ' + str(last.get('detail')) if last.get('detail') else ''} {last.get('at') or ''}")
    start = time.time()
    try:
        r = requests.post(f"{base}/api/ask", json={"question": "How am I doing this month?"}, timeout=90)
        res = r.json()
    except (requests.RequestException, ValueError) as e:
        sys.exit(f"ask failed: {type(e).__name__}")
    ok = res.get("source") == "gemini"
    print(f"ask on the Demo household: {'OK' if ok else 'FAILED'} in {time.time() - start:.1f}s")
    print(f"  label: {res.get('source') or res.get('error')}")
    print(f"  answer: {(res.get('answer') or '')[:160]}")
    sys.exit(0 if ok else 1)

if not os.environ.get("GEMINI_API_KEY", "").strip():
    sys.exit("GEMINI_API_KEY is not set in backend/.env")

print(f"model: {os.environ.get('GEMINI_MODEL', assistant.DEFAULT_MODEL)} (backup {os.environ.get('GEMINI_FALLBACK_MODEL', assistant.FALLBACK_MODEL)})")
result = assistant.self_check()
print(f"app request: {'OK' if result['ok'] else 'FAILED'} in {result['seconds']}s")
print(f"  label: {result['source']}")
print(f"  answer: {result['answer'][:160]}")
sys.exit(0 if result["ok"] else 1)
