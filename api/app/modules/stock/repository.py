from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Stock


class StockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_product_id(self, product_id: UUID) -> Stock | None:
        statement = select(Stock).where(Stock.produto_id == product_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_product_id_for_update(
        self,
        product_id: UUID,
    ) -> Stock | None:
        statement = (
            select(Stock).where(Stock.produto_id == product_id).with_for_update()
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def add(self, stock: Stock) -> Stock:
        self.session.add(stock)
        await self.session.flush()
        return stock

    async def update(self, stock: Stock) -> Stock:
        await self.session.flush()
        return stock
