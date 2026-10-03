import json

import pytest

from auth import AuthManager


@pytest.fixture
def auth(tmp_path):
    return AuthManager(users_path=str(tmp_path / "users.json"))


def test_hash_is_salted_and_repeatable():
    h1, salt = AuthManager.hash_password("pw")
    h2, _ = AuthManager.hash_password("pw", salt)
    h3, other = AuthManager.hash_password("pw")
    assert h1 == h2
    assert salt != other and h1 != h3


def test_register_and_verify(auth):
    assert auth.register_user("ann", "s3cret")
    assert not auth.register_user("ann", "again")
    assert auth.verify_password("ann", "s3cret")
    assert not auth.verify_password("ann", "wrong")
    assert not auth.verify_password("nobody", "s3cret")


def test_password_not_stored_in_plain_text(auth):
    auth.register_user("ann", "s3cret")
    raw = json.loads(auth.users_path.read_text())
    assert "s3cret" not in json.dumps(raw)


def test_token_flow(auth):
    auth.register_user("ann", "s3cret")
    assert auth.authenticate("ann", "wrong") is None
    token = auth.authenticate("ann", "s3cret")
    assert token and auth.verify_token("ann", token)
    assert not auth.verify_token("ann", token + "x")
    assert not auth.verify_token("bob", token)


def test_no_token_never_verifies(auth):
    auth.register_user("ann", "s3cret")
    assert not auth.verify_token("ann", None)
    assert not auth.verify_token("ann", "")


def test_delete_user(auth):
    auth.register_user("ann", "s3cret")
    assert auth.delete_user("ann")
    assert auth.list_users() == []
    assert not auth.delete_user("ann")
