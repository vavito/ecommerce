from decimal import Decimal
from uuid import uuid4

from app.core.database import async_session_maker
from app.modules.product.models import Category, Product
from app.modules.product.repository import ProductRepository


async def test_product_repository_adds_updates_and_finds_product() -> None:
    unique_value = uuid4()

    async with async_session_maker() as session:
        try:
            category = Category(
                nome="Eletronicos",
                slug=f"eletronicos-{unique_value.hex}",
                ativo=True,
            )
            session.add(category)
            await session.flush()

            repository = ProductRepository(session)
            product = Product(
                categoria_id=category.id,
                nome="Teclado mecanico",
                slug=f"teclado-mecanico-{unique_value.hex}",
                descricao=None,
                sku=f"TEC-{unique_value.hex}",
                preco=Decimal("299.90"),
                ativo=True,
            )

            created_product = await repository.add(product)

            product_by_id = await repository.get_by_id(product.id)
            product_by_sku = await repository.get_by_sku(product.sku)
            product_by_slug = await repository.get_by_slug(product.slug)
            category_by_id = await repository.get_category_by_id(category.id)

            product.nome = "Teclado mecanico atualizado"
            updated_product = await repository.update(product)

            assert created_product is product
            assert product_by_id is product
            assert product_by_sku is product
            assert product_by_slug is product
            assert category_by_id is category
            assert updated_product.nome == "Teclado mecanico atualizado"
        finally:
            await session.rollback()


async def test_product_repository_filters_and_paginates_products() -> None:
    unique_value = uuid4()

    async with async_session_maker() as session:
        try:
            electronics = Category(
                nome="Eletronicos",
                slug=f"eletronicos-{unique_value.hex}",
                ativo=True,
            )
            books = Category(
                nome="Livros",
                slug=f"livros-{unique_value.hex}",
                ativo=True,
            )
            session.add_all([electronics, books])
            await session.flush()

            products = [
                Product(
                    categoria_id=electronics.id,
                    nome="Teclado compacto",
                    slug=f"teclado-compacto-{unique_value.hex}",
                    descricao=None,
                    sku=f"TEC-COM-{unique_value.hex}",
                    preco=Decimal("199.90"),
                    ativo=True,
                ),
                Product(
                    categoria_id=electronics.id,
                    nome="Teclado mecanico",
                    slug=f"teclado-mecanico-{unique_value.hex}",
                    descricao=None,
                    sku=f"TEC-MEC-{unique_value.hex}",
                    preco=Decimal("299.90"),
                    ativo=True,
                ),
                Product(
                    categoria_id=electronics.id,
                    nome="Teclado antigo",
                    slug=f"teclado-antigo-{unique_value.hex}",
                    descricao=None,
                    sku=f"TEC-ANT-{unique_value.hex}",
                    preco=Decimal("99.90"),
                    ativo=False,
                ),
                Product(
                    categoria_id=books.id,
                    nome="Livro sobre teclados",
                    slug=f"livro-sobre-teclados-{unique_value.hex}",
                    descricao=None,
                    sku=f"LIV-TEC-{unique_value.hex}",
                    preco=Decimal("59.90"),
                    ativo=True,
                ),
            ]
            session.add_all(products)
            await session.flush()

            repository = ProductRepository(session)

            first_page, total = await repository.list(
                nome="TECLADO",
                categoria_id=electronics.id,
                ativo=True,
                offset=0,
                limit=1,
            )
            second_page, second_total = await repository.list(
                nome="teclado",
                categoria_id=electronics.id,
                ativo=True,
                offset=1,
                limit=1,
            )

            assert total == 2
            assert second_total == 2
            assert len(first_page) == 1
            assert len(second_page) == 1
            assert first_page[0].nome == "Teclado compacto"
            assert second_page[0].nome == "Teclado mecanico"
        finally:
            await session.rollback()
