from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import async_session_maker, get_session
from app.core.security import create_access_token, decode_access_token, hash_password
from app.main import app
from app.modules.user.models import User


@pytest.fixture
async def active_user() -> AsyncGenerator[tuple[User, str], None]:
    unique_value = uuid4()
    password = "senha123"

    async with async_session_maker() as session:
        user = User(
            nome="John",
            email=f"john-{unique_value.hex}@example.com",
            cpf=f"{unique_value.int % 100_000_000_000:011d}",
            senha_hash=hash_password(password),
            ativo=True,
        )
        session.add(user)
        await session.flush()

        async def override_get_session() -> AsyncGenerator:
            yield session

        app.dependency_overrides[get_session] = override_get_session

        try:
            yield user, password
        finally:
            app.dependency_overrides.pop(get_session, None)
            await session.rollback()


async def test_login_endpoint_returns_valid_access_token(
    active_user: tuple[User, str],
) -> None:
    user, password = active_user
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/auth/login",
            json={"email": user.email, "senha": password},
        )

    body = response.json()

    assert response.status_code == 200
    assert body["token_type"] == "bearer"
    assert decode_access_token(body["access_token"]) == str(user.id)


async def test_login_endpoint_returns_standard_error_for_incorrect_password(
    active_user: tuple[User, str],
) -> None:
    user, _password = active_user
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/auth/login",
            json={"email": user.email, "senha": "senha-errada"},
        )

    assert response.status_code == 401
    assert response.json() == {
        "code": "INVALID_CREDENTIALS",
        "message": "Email ou senha invalidos.",
        "details": {},
    }


async def test_users_me_returns_authenticated_user(
    active_user: tuple[User, str],
) -> None:
    user, _password = active_user
    token = create_access_token(str(user.id))
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    body = response.json()

    assert response.status_code == 200
    assert body["id"] == str(user.id)
    assert body["email"] == user.email
    assert "cpf" not in body
    assert "senha_hash" not in body


async def test_users_me_requires_access_token() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/users/me")

    assert response.status_code == 401
    assert response.json() == {
        "code": "AUTHENTICATION_REQUIRED",
        "message": "Token de autenticacao nao informado.",
        "details": {},
    }


async def test_users_me_rejects_invalid_access_token() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/users/me",
            headers={"Authorization": "Bearer token-invalido"},
        )

    assert response.status_code == 401
    assert response.json() == {
        "code": "INVALID_TOKEN",
        "message": "Token de autenticacao invalido.",
        "details": {},
    }
