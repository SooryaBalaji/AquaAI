import logging
import os
import time
import uuid
from datetime import datetime, timezone

import jwt
from werkzeug.security import check_password_hash, generate_password_hash

import storage

log = logging.getLogger("aquaai.auth")

DEFAULT_SECRET = "dev-secret-change-me-before-deploying"
SECRET_KEY = os.environ.get("SECRET_KEY", DEFAULT_SECRET)
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7

_PROVIDER = os.environ.get("AUTH_PROVIDER") or ("firebase" if os.environ.get("FIREBASE_WEB_API_KEY") else "local")


class AuthError(Exception):
    def __init__(self, message, status=400, code=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def provider():
    return _PROVIDER


def public_config():
    if _PROVIDER != "firebase":
        return {"provider": "local"}
    project_id = os.environ.get("FIREBASE_PROJECT_ID", "")
    return {
        "provider": "firebase",
        "firebase": {
            "apiKey": os.environ.get("FIREBASE_WEB_API_KEY", ""),
            "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN") or (f"{project_id}.firebaseapp.com" if project_id else ""),
            "projectId": project_id,
            "appId": os.environ.get("FIREBASE_APP_ID", ""),
        },
    }


def _firebase_verify(token):
    from firebase_admin import auth as firebase_auth
    return firebase_auth.verify_id_token(token)


def _firebase_delete(uid):
    from firebase_admin import auth as firebase_auth
    firebase_auth.delete_user(uid)


def delete_account(user_id):
    if _PROVIDER == "firebase":
        _firebase_delete(user_id)
    else:
        storage.delete_user(user_id)


def _verify_firebase_token(token):
    try:
        decoded = _firebase_verify(token)
    except Exception:
        return None
    uid = decoded.get("uid") or decoded.get("user_id") or decoded.get("sub")
    if not uid:
        return None
    return {
        "id": uid,
        "email": decoded.get("email") or "",
        "email_verified": bool(decoded.get("email_verified")),
    }


def _verify_local_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return {"id": payload["sub"], "email": payload["email"], "email_verified": True}
    except jwt.PyJWTError:
        return None


def verify_token(token):
    if not token:
        return None
    if _PROVIDER == "firebase":
        return _verify_firebase_token(token)
    return _verify_local_token(token)


def user_from_auth_header(header_value):
    if not header_value or not header_value.startswith("Bearer "):
        return None
    return verify_token(header_value[len("Bearer "):])


def register(email, password):
    _require_local()
    email = _normalize_email(email)
    _validate_password(password)

    if storage.get_user_by_email(email):
        raise AuthError("An account with that email already exists.", status=409)

    user = {
        "id": uuid.uuid4().hex[:12],
        "email": email,
        "password_hash": generate_password_hash(password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    storage.save_user(user)
    return _issue_token(user), _public_user(user)


def login(email, password):
    _require_local()
    email = _normalize_email(email)
    user = storage.get_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password or ""):
        raise AuthError("Incorrect email or password.", status=401)
    return _issue_token(user), _public_user(user)


def _require_local():
    if _PROVIDER != "local":
        raise AuthError("Sign in is handled by Firebase.", status=404)


def _issue_token(user):
    payload = {"sub": user["id"], "email": user["email"], "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _public_user(user):
    return {"id": user["id"], "email": user["email"], "email_verified": True}


def _normalize_email(email):
    email = (email or "").strip().lower()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise AuthError("Enter a valid email address.")
    return email


def _validate_password(password):
    if not password or len(password) < 8:
        raise AuthError("Password must be at least 8 characters.")