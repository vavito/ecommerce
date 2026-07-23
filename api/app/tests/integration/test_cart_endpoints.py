from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, get_session
from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.cart.repository import CartRepository
from app.modules.user.models import User


@pytest.fixture
async def authenticated_cart_user() -> AsyncGenerator[
    tuple[AsyncSession, User, str],
    None,
]:
    unique_value = uuid4()

    async with async_session_maker() as session:
        user = User(
            nome="Joao",
            email=f"joao-cart-{unique_value.hex}@example.com",
            cpf=f"{unique_value.int % 100_000_000_000:011d}",
            senha_hash=hash_password("senha123"),
            ativo=True,
        )
        session.add(user)
        await session.flush()

        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            yield session

        app.dependency_overrides[get_session] = override_get_session
        token = create_access_token(str(user.id))
        user_id = user.id

        try:
            yield session, user, token
        finally:
            app.dependency_overrides.pop(get_session, None)
            await session.rollback()
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_get_cart_creates_and_returns_empty_cart(
    authenticated_cart_user: tuple[AsyncSession, User, str],
) -> None:
    session, user, token = authenticated_cart_user
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/cart",
            headers={"Authorization": f"Bearer {token}"},
        )

    body = response.json()
    saved_cart = await CartRepository(session).get_open_by_user_id(user.id)

    assert response.status_code == 200
    assert body["usuario_id"] == str(user.id)
    assert body["status"] == "OPEN"
    assert body["itens"] == []
    assert body["total_estimado"] == "0.00"
    assert saved_cart is not None
    assert str(saved_cart.id) == body["id"]


async def test_get_cart_returns_same_open_cart_on_next_request(
    authenticated_cart_user: tuple[AsyncSession, User, str],
) -> None:
    _, _user, token = authenticated_cart_user
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.get("/cart", headers=headers)
        second_response = await client.get("/cart", headers=headers)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["id"] == first_response.json()["id"]


async def test_get_cart_requires_access_token() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/cart")

    assert response.status_code == 401
    assert response.json() == {
        "code": "AUTHENTICATION_REQUIRED",
        "message": "Token de autenticacao nao informado.",
        "details": {},
    }
