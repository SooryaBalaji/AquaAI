import os

from auth import DEFAULT_SECRET


def production_problems(auth_provider, storage_backend, secret_key):
    problems = []
    if auth_provider == "local" and os.environ.get("ALLOW_LOCAL_AUTH") != "1":
        problems.append("AUTH_PROVIDER is local. Set the FIREBASE_* variables to use Firebase Authentication.")
    if auth_provider == "local" and secret_key == DEFAULT_SECRET:
        problems.append("SECRET_KEY is the insecure default.")
    if storage_backend != "firestore" and os.environ.get("ALLOW_SQLITE_IN_PRODUCTION") != "1":
        problems.append("Storage is SQLite. Hosted disks are wiped on redeploy. Configure Firestore.")
    if auth_provider == "firebase":
        for name in ("FIREBASE_WEB_API_KEY", "FIREBASE_PROJECT_ID"):
            if not os.environ.get(name):
                problems.append(f"{name} is not set.")
    return problems


def is_production():
    return os.environ.get("APP_ENV", "development").lower() == "production"
