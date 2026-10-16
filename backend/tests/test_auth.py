import pytest

import auth


def test_register_then_login_succeeds():
    email = "unit-test-auth@example.com"
    auth.register(email, "password123")
    token, user = auth.login(email, "password123")
    assert user["email"] == email
    assert auth.verify_token(token)["email"] == email


def test_duplicate_registration_rejected():
    email = "dup-test@example.com"
    auth.register(email, "password123")
    with pytest.raises(auth.AuthError) as exc:
        auth.register(email, "password123")
    assert exc.value.status == 409


def test_wrong_password_rejected():
    email = "wrongpass-test@example.com"
    auth.register(email, "password123")
    with pytest.raises(auth.AuthError) as exc:
        auth.login(email, "not-the-password")
    assert exc.value.status == 401


def test_short_password_rejected():
    with pytest.raises(auth.AuthError):
        auth.register("shortpass-test@example.com", "short")


def test_invalid_email_rejected():
    with pytest.raises(auth.AuthError):
        auth.register("not-an-email", "password123")


def test_verify_token_rejects_garbage():
    assert auth.verify_token("not.a.valid.token") is None
    assert auth.verify_token(None) is None


def test_user_from_auth_header_requires_bearer_prefix():
    token, _ = auth.register("header-test@example.com", "password123")
    assert auth.user_from_auth_header(f"Bearer {token}") is not None
    assert auth.user_from_auth_header(token) is None  # missing "Bearer " prefix
    assert auth.user_from_auth_header(None) is None
