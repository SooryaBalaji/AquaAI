"""
Shared pytest fixtures.

Points storage at a throwaway SQLite file before app.py is ever imported,
so the test suite never touches the real backend/aquaai.db a developer
might be using locally, and starts from a clean slate every run.
"""

import os
import sys
import uuid

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

TEST_DB_PATH = os.path.join(BACKEND_DIR, "tests", "test_aquaai.db")
if os.path.exists(TEST_DB_PATH):
    os.remove(TEST_DB_PATH)

os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["RATELIMIT_ENABLED"] = "0"
os.environ["AUTH_PROVIDER"] = "local"
os.environ["GEMINI_API_KEY"] = ""  # never call the real API from tests, even if a developer .env has a key
os.environ.pop("FIREBASE_CREDENTIALS_PATH", None)  # force SQLite for tests

import storage  # noqa: E402

storage.SQLITE_PATH = TEST_DB_PATH

import app as aquaai_app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    aquaai_app.app.testing = True
    with aquaai_app.app.test_client() as c:
        yield c


@pytest.fixture
def unique_email():
    return f"test-{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture
def registered_user(client, unique_email):
    #Registers a fresh user and returns (headers, user_id, email)
    r = client.post("/api/auth/register", json={"email": unique_email, "password": "password123"})
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]["id"], unique_email