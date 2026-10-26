from app.core.security import hash_password, hash_session_token, verify_password


def test_password_round_trip() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert verify_password(password_hash, "correct horse battery staple")
    assert not verify_password(password_hash, "wrong password")


def test_verify_rejects_malformed_hash() -> None:
    assert not verify_password("not-an-argon2-hash", "anything")


def test_session_token_hash_fits_column() -> None:
    # `user_sessions.token_hash` has a CHECK requiring exactly 32 bytes.
    assert len(hash_session_token("some-token")) == 32
