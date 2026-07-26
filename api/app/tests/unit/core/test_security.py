import pytest
from jwt.exceptions import InvalidTokenError

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password() -> None:
    plain_password = "senha123"
    hashed_password = hash_password(plain_password)

    assert hashed_password != plain_password
    assert verify_password(plain_password, hashed_password)
    assert not verify_password("senha-errada", hashed_password)


def test_create_and_decode_access_token() -> None:
    subject = "user-test-id"

    token = create_access_token(subject)
    decoded_subject = decode_access_token(token)

    assert isinstance(token, str)
    assert decoded_subject == subject


def test_decode_rejects_invalid_access_token() -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token("token-invalido")
