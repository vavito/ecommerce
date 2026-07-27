from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.modules.user.models import User
from app.shared.enums import UserRole


@pytest.fixture
async def admin_headers() -> AsyncGenerator[dict[str, str], None]:
    unique_value = uuid4()

    async with async_session_maker() as session:
        admin = User(
            nome="Admin teste",
            email=f"admin-{unique_value.hex}@example.com",
            cpf=f"{unique_value.int % 100_000_000_000:011d}",
            senha_hash="hash",
            role=UserRole.ADMIN,
            ativo=True,
        )
        session.add(admin)
        await session.commit()

        try:
            yield {
                "Authorization": f"Bearer {create_access_token(str(admin.id))}",
            }
        finally:
            await session.execute(delete(User).where(User.id == admin.id))
            await session.commit()
