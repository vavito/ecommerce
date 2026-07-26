from decimal import Decimal
from uuid import uuid4

from app.core.database import async_session_maker
from app.modules.product.models import Category, Product
from app.modules.stock.models import Stock
from app.modules.stock.repository import StockRepository


async def test_stock_repository_adds_updates_and_finds_stock() -> None:
    unique_value = uuid4().hex

    async with async_session_maker() as session:
        try:
            category = Category(
                nome="Informatica",
                slug=f"informatica-{unique_value}",
                ativo=True,
            )
            session.add(category)
            await session.flush()

            product = Product(
                categoria_id=category.id,
                nome="Mouse sem fio",
                slug=f"mouse-sem-fio-{unique_value}",
                descricao=None,
                sku=f"MOUSE-{unique_value}",
                preco=Decimal("149.90"),
                ativo=True,
            )
            session.add(product)
            await session.flush()

            repository = StockRepository(session)
            stock = Stock(
                produto_id=product.id,
                quantidade=10,
            )

            created_stock = await repository.add(stock)
            stock_by_product = await repository.get_by_product_id(product.id)
            locked_stock = await repository.get_by_product_id_for_update(product.id)

            assert created_stock.quantidade_reservada == 0
            assert created_stock.quantidade_disponivel == 10

            stock.quantidade = 8
            updated_stock = await repository.update(stock)

            assert created_stock is stock
            assert stock_by_product is stock
            assert locked_stock is stock
            assert updated_stock.quantidade == 8
            assert updated_stock.quantidade_disponivel == 8
        finally:
            await session.rollback()


async def test_stock_repository_returns_none_for_product_without_stock() -> None:
    async with async_session_maker() as session:
        repository = StockRepository(session)
        product_id = uuid4()

        stock = await repository.get_by_product_id(product_id)
        locked_stock = await repository.get_by_product_id_for_update(product_id)

        assert stock is None
        assert locked_stock is None
