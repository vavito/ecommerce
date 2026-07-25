from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Order


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, order_id: UUID) -> Order | None:
        statement = (
            select(Order).options(selectinload(Order.itens)).where(Order.id == order_id)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_user_id(self, user_id: UUID) -> list[Order]:
        statement = (
            select(Order)
            .options(selectinload(Order.itens))
            .where(Order.usuario_id == user_id)
            .order_by(Order.criado_em.desc(), Order.id.desc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def add(self, order: Order) -> Order:
        self.session.add(order)
        await self.session.flush()
        return order
