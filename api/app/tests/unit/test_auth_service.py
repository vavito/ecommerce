from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.security import decode_access_token, hash_password
from app.modules.auth.service import AuthService
from app.modules.user.models import User
from app.modules.user.repository import UserRepository
from app.shared.exceptions import ForbiddenException, UnauthorizedException


async def test_login_returns_token_for_valid_credentials() -> None:
    repository = AsyncMock(spec=UserRepository)
    service = AuthService(repository)

    password = "senha123"
    user = User(
        id=uuid4(),
        nome="John",
        email="john@example.com",
        cpf="12345678901",
        senha_hash=hash_password(password),
        ativo=True,
    )

    repository.get_by_email.return_value = user

    token = await service.login(" JOHN@EXAMPLE.COM ", password)

    assert decode_access_token(token) == str(user.id)
    repository.get_by_email.assert_awaited_once_with("john@example.com")


async def test_login_raises_unauthorized_when_user_does_not_exist() -> None:
    repository = AsyncMock(spec=UserRepository)
    service = AuthService(repository)

    repository.get_by_email.return_value = None

    with pytest.raises(UnauthorizedException) as exc_info:
        await service.login("missing@example.com", "senha123")

    assert exc_info.value.code == "INVALID_CREDENTIALS"
    repository.get_by_email.assert_awaited_once_with("missing@example.com")


async def test_login_raises_unauthorized_when_password_is_incorrect() -> None:
    repository = AsyncMock(spec=UserRepository)
    service = AuthService(repository)

    user = User(
        id=uuid4(),
        nome="John",
        email="john@example.com",
        cpf="12345678901",
        senha_hash=hash_password("senha-correta"),
        ativo=True,
    )

    repository.get_by_email.return_value = user

    with pytest.raises(UnauthorizedException) as exc_info:
        await service.login(user.email, "senha-errada")

    assert exc_info.value.code == "INVALID_CREDENTIALS"
    repository.get_by_email.assert_awaited_once_with(user.email)


async def test_login_raises_forbidden_when_user_is_inactive() -> None:
    repository = AsyncMock(spec=UserRepository)
    service = AuthService(repository)

    password = "senha-correta"
    user = User(
        id=uuid4(),
        nome="John",
        email="john@example.com",
        cpf="12345678901",
        senha_hash=hash_password(password),
        ativo=False,
    )

    repository.get_by_email.return_value = user

    with pytest.raises(ForbiddenException) as exc_info:
        await service.login(user.email, password)

    assert exc_info.value.code == "INACTIVE_USER"
    repository.get_by_email.assert_awaited_once_with(user.email)
