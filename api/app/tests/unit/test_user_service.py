from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.user.models import Address, User
from app.modules.user.repository import UserRepository
from app.modules.user.service import UserService
from app.shared.exceptions import ConflictException


async def test_create_user_with_available_email_and_cpf() -> None:
    repository = AsyncMock(spec=UserRepository)
    service = UserService(repository)

    unique_value = uuid4()
    user = User(
        nome="John",
        email=f"JOHN-{unique_value.hex}@example.com",
        cpf=f"{unique_value.int % 100_000_000_000:011d}",
        senha_hash="hash-de-teste",
    )

    repository.get_by_email.return_value = None
    repository.get_by_cpf.return_value = None
    repository.add.return_value = user

    result = await service.create_user(user)

    expected_email = f"john-{unique_value.hex}@example.com"

    assert result is user
    assert user.email == expected_email
    repository.get_by_email.assert_awaited_once_with(expected_email)
    repository.get_by_cpf.assert_awaited_once_with(user.cpf)
    repository.add.assert_awaited_once_with(user)


async def test_create_user_raises_conflict_when_email_already_exists() -> None:
    repository = AsyncMock(spec=UserRepository)
    service = UserService(repository)
    existing_user = User(
        nome="Existing User",
        email="existing@example.com",
        cpf="12345678901",
        senha_hash="existing-hash",
    )
    new_user = User(
        nome="New User",
        email="EXISTING@EXAMPLE.COM",
        cpf="10987654321",
        senha_hash="new-hash",
    )
    repository.get_by_email.return_value = existing_user

    with pytest.raises(ConflictException) as exc_info:
        await service.create_user(new_user)

    assert exc_info.value.code == "EMAIL_ALREADY_EXISTS"
    repository.get_by_email.assert_awaited_once_with("existing@example.com")
    repository.get_by_cpf.assert_not_awaited()
    repository.add.assert_not_awaited()


async def test_create_user_raises_conflict_when_cpf_already_exists() -> None:
    repository = AsyncMock(spec=UserRepository)
    service = UserService(repository)
    existing_user = User(
        nome="Existing User",
        email="existing@example.com",
        cpf="12345678901",
        senha_hash="existing-hash",
    )
    new_user = User(
        nome="New User",
        email="new@example.com",
        cpf=existing_user.cpf,
        senha_hash="new-hash",
    )
    repository.get_by_email.return_value = None
    repository.get_by_cpf.return_value = existing_user

    with pytest.raises(ConflictException) as exc_info:
        await service.create_user(new_user)

    assert exc_info.value.code == "CPF_ALREADY_EXISTS"
    repository.get_by_email.assert_awaited_once_with(new_user.email)
    repository.get_by_cpf.assert_awaited_once_with(new_user.cpf)
    repository.add.assert_not_awaited()


async def test_create_address_links_address_to_user() -> None:
    repository = AsyncMock(spec=UserRepository)
    service = UserService(repository)
    user = User(
        id=uuid4(),
        nome="John",
        email="john@example.com",
        cpf="12345678901",
        senha_hash="hash-de-teste",
    )
    address = Address(
        cep="12345678",
        rua="Rua das Flores",
        numero="10",
        complemento=None,
        bairro="Centro",
        cidade="Sao Paulo",
        estado="sp",
        principal=False,
    )
    repository.add_address.return_value = address

    result = await service.create_address(user, address)

    assert result is address
    assert address.usuario_id == user.id
    assert address.estado == "SP"
    repository.add_address.assert_awaited_once_with(address)
