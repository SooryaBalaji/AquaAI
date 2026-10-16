import json
import logging
import os

log = logging.getLogger("aquaai.firebase")

_state = {"ready": False, "firestore": None}


def init():
    if _state["ready"]:
        return True

    raw = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    path = os.environ.get("FIREBASE_CREDENTIALS_PATH")

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError:
        if raw or path:
            log.warning("Firebase credentials are set but firebase-admin is not installed.")
        return False

    if raw:
        try:
            cert_source = json.loads(raw)
        except ValueError:
            log.warning("FIREBASE_CREDENTIALS_JSON is not valid JSON.")
            return False
    elif path and os.path.exists(path):
        cert_source = path
    else:
        if path:
            log.warning("FIREBASE_CREDENTIALS_PATH is set but %s does not exist.", path)
        return False

    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(cert_source))
        _state["firestore"] = firestore.client()
        _state["ready"] = True
        log.info("connected to Firebase")
        return True
    except Exception as e:
        log.warning("Firebase unavailable (%s).", e)
        return False


def ready():
    return _state["ready"]


def firestore_client():
    return _state["firestore"]
