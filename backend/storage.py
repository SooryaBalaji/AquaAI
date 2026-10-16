"""
Storage: profiles and user accounts.

Tries Firestore (Firebase's cloud document database) first. If
firebase-admin isn't installed, or no service account credentials are
configured, falls back automatically to a local SQLite database file.
Either way, data survives a server restart.

Each profile has an owner_id. NULL/None means it's a shared, public
profile visible to everyone (the seeded demo household is one of these).
A non-null owner_id means it's private to that one user.

To enable Firestore:
  1. Create a project at https://console.firebase.google.com and enable
     Firestore (Native mode) in it.
  2. Project settings, Service accounts, Generate new private key.
     This downloads a JSON credentials file. Keep it out of git.
  3. pip install -r requirements-firebase.txt
  4. In backend/.env, set FIREBASE_CREDENTIALS_PATH to the path of that
     JSON file.
Without those steps, AquaAI runs on SQLite automatically. No setup needed.
"""

import logging
import os
import sqlite3
import threading

log = logging.getLogger("aquaai.storage")

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "aquaai.db")

_backend = None  # "firestore" or "sqlite", set by init_storage()
_firestore_client = None
_lock = threading.Lock()


def init_storage():
    global _backend, _firestore_client
    import firebase_client

    if firebase_client.init():
        _firestore_client = firebase_client.firestore_client()
        _backend = "firestore"
        log.info("using Firestore")
        return

    _init_sqlite()
    _backend = "sqlite"
    log.info("using local SQLite database at %s", SQLITE_PATH)


def backend_name():
    return _backend


def _init_sqlite():
    with sqlite3.connect(SQLITE_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                owner_id TEXT,
                name TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                household_size INTEGER NOT NULL,
                tier1_limit_gal REAL NOT NULL,
                seed INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------
def list_profiles(owner_id=None):
    """Public profiles (owner_id IS NULL) plus, if owner_id is given, that
    user's own private profiles."""
    if _backend == "firestore":
        col = _firestore_client.collection("profiles")
        rows = [d.to_dict() for d in col.where("owner_id", "==", None).stream()]
        if owner_id:
            rows += [d.to_dict() for d in col.where("owner_id", "==", owner_id).stream()]
        return rows
    with sqlite3.connect(SQLITE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM profiles WHERE owner_id IS NULL OR owner_id = ?", (owner_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_profile(profile_id):
    if _backend == "firestore":
        doc = _firestore_client.collection("profiles").document(profile_id).get()
        return doc.to_dict() if doc.exists else None
    with sqlite3.connect(SQLITE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        return dict(row) if row else None


def save_profile(profile):
    with _lock:
        if _backend == "firestore":
            _firestore_client.collection("profiles").document(profile["id"]).set(profile)
            return
        with sqlite3.connect(SQLITE_PATH) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO profiles
                    (id, owner_id, name, lat, lon, household_size, tier1_limit_gal, seed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile["id"], profile.get("owner_id"), profile["name"], profile["lat"], profile["lon"],
                profile["household_size"], profile["tier1_limit_gal"], profile["seed"],
            ))


def delete_profile_row(profile_id):
    with _lock:
        if _backend == "firestore":
            _firestore_client.collection("profiles").document(profile_id).delete()
            return
        with sqlite3.connect(SQLITE_PATH) as conn:
            conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
def get_user_by_email(email):
    if _backend == "firestore":
        docs = list(_firestore_client.collection("users").where("email", "==", email).limit(1).stream())
        return docs[0].to_dict() if docs else None
    with sqlite3.connect(SQLITE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def save_user(user):
    with _lock:
        if _backend == "firestore":
            _firestore_client.collection("users").document(user["id"]).set(user)
            return
        with sqlite3.connect(SQLITE_PATH) as conn:
            conn.execute("""
                INSERT INTO users (id, email, password_hash, created_at)
                VALUES (?, ?, ?, ?)
            """, (user["id"], user["email"], user["password_hash"], user["created_at"]))


def delete_user(user_id):
    with _lock:
        if _backend == "firestore":
            _firestore_client.collection("users").document(user_id).delete()
            return
        with sqlite3.connect(SQLITE_PATH) as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
