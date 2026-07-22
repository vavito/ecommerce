from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Category, Product


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, product_id: UUID) -> Product | None:
        statement = select(Product).where(Product.id == product_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_sku(self, sku: str) -> Product | None:
        statement = select(Product).where(Product.sku == sku)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Product | None:
        statement = select(Product).where(Product.slug == slug)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_category_by_id(self, category_id: UUID) -> Category | None:
        statement = select(Category).where(Category.id == category_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def add(self, product: Product) -> Product:
        self.session.add(product)
        await self.session.flush()
        return product

    async def update(self, product: Product) -> Product:
        await self.session.flush()
        return product

    async def list(
        self,
        *,
        nome: str | None = None,
        categoria_id: UUID | None = None,
        ativo: bool | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Product], int]:
        filters = []

        if nome is not None:
            filters.append(Product.nome.ilike(f"%{nome}%"))

        if categoria_id is not None:
            filters.append(Product.categoria_id == categoria_id)

        if ativo is not None:
            filters.append(Product.ativo == ativo)

        count_statement = select(func.count(Product.id)).where(*filters)
        count_result = await self.session.execute(count_statement)
        total = count_result.scalar_one()

        statement = (
            select(Product)
            .where(*filters)
            .order_by(Product.nome.asc(), Product.id.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(statement)
        products = list(result.scalars().all())

        return products, total
