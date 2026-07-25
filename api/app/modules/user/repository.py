from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Address, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_cpf(self, cpf: str) -> User | None:
        statement = select(User).where(User.cpf == cpf)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        statement = select(User).where(User.id == user_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_address_by_id_and_user_id(
        self,
        address_id: UUID,
        user_id: UUID,
    ) -> Address | None:
        statement = select(Address).where(
            Address.id == address_id,
            Address.usuario_id == user_id,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def add_address(self, address: Address) -> Address:
        self.session.add(address)
        await self.session.flush()
        return address
