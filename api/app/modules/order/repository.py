from uuid import UUID

from sqlalchemy import func, select
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

    async def list_by_user_id(
        self,
        user_id: UUID,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Order], int]:
        count_statement = select(func.count(Order.id)).where(
            Order.usuario_id == user_id
        )
        count_result = await self.session.execute(count_statement)
        total = count_result.scalar_one()

        statement = (
            select(Order)
            .options(selectinload(Order.itens))
            .where(Order.usuario_id == user_id)
            .order_by(Order.criado_em.desc(), Order.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(statement)
        orders = list(result.scalars().all())

        return orders, total

    async def add(self, order: Order) -> Order:
        self.session.add(order)
        await self.session.flush()
        return order
