from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.order.models import Order

from .models import Payment


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id_for_update(self, payment_id: UUID) -> Payment | None:
        statement = (
            select(Payment)
            .options(selectinload(Payment.pedido).selectinload(Order.itens))
            .where(Payment.id == payment_id)
            .with_for_update()
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def update(self, payment: Payment) -> Payment:
        await self.session.flush()
        return payment
