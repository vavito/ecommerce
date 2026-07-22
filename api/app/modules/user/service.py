from app.shared.exceptions import ConflictException

from .models import Address, User
from .repository import UserRepository


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def _ensure_email_is_available(self, email: str) -> None:
        existing_user = await self.repository.get_by_email(email)

        if existing_user is not None:
            raise ConflictException(
                code="EMAIL_ALREADY_EXISTS",
                message="Email ja cadastrado.",
            )

    async def _ensure_cpf_is_available(self, cpf: str) -> None:
        existing_user = await self.repository.get_by_cpf(cpf)

        if existing_user is not None:
            raise ConflictException(
                code="CPF_ALREADY_EXISTS",
                message="CPF ja cadastrado.",
            )

    async def create_user(self, user: User) -> User:
        user.email = user.email.strip().lower()

        await self._ensure_email_is_available(user.email)
        await self._ensure_cpf_is_available(user.cpf)

        return await self.repository.add(user)

    async def create_address(self, user: User, address: Address) -> Address:
        address.estado = address.estado.strip().upper()

        address.usuario_id = user.id

        return await self.repository.add_address(address)
