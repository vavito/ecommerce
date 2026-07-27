from uuid import uuid4

import pytest

from app.modules.auth.dependencies import require_admin
from app.modules.user.models import User
from app.shared.enums import UserRole
from app.shared.exceptions import ForbiddenException


def make_user(role: UserRole) -> User:
    unique_value = uuid4()
    return User(
        id=unique_value,
        nome="Usuario teste",
        email=f"user-{unique_value.hex}@example.com",
        cpf=f"{unique_value.int % 100_000_000_000:011d}",
        senha_hash="hash",
        role=role,
        ativo=True,
    )


async def test_require_admin_accepts_admin_user() -> None:
    admin = make_user(UserRole.ADMIN)

    result = await require_admin(admin)

    assert result is admin


async def test_require_admin_blocks_customer_with_standard_error() -> None:
    customer = make_user(UserRole.CUSTOMER)

    with pytest.raises(ForbiddenException) as exc_info:
        await require_admin(customer)

    assert exc_info.value.code == "FORBIDDEN"
    assert exc_info.value.status_code == 403
    assert exc_info.value.message == "Acesso permitido apenas para administradores."
