from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.modules.user.models import User
from app.shared.enums import UserRole


@asynccontextmanager
async def _authenticated_headers(
    role: UserRole,
) -> AsyncIterator[dict[str, str]]:
    unique_value = uuid4()

    async with async_session_maker() as session:
        user = User(
            nome=f"Usuario {role.value}",
            email=f"{role.value.lower()}-{unique_value.hex}@example.com",
            cpf=f"{unique_value.int % 100_000_000_000:011d}",
            senha_hash="hash",
            role=role,
            ativo=True,
        )
        session.add(user)
        await session.commit()

        try:
            yield {
                "Authorization": f"Bearer {create_access_token(str(user.id))}",
            }
        finally:
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()


@pytest.fixture
async def admin_headers() -> AsyncGenerator[dict[str, str], None]:
    async with _authenticated_headers(UserRole.ADMIN) as headers:
        yield headers


@pytest.fixture
async def customer_headers() -> AsyncGenerator[dict[str, str], None]:
    async with _authenticated_headers(UserRole.CUSTOMER) as headers:
        yield headers
