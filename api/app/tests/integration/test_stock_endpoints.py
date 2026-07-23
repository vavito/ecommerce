from collections.abc import AsyncGenerator
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, get_session
from app.main import app
from app.modules.product.models import Category, Product
from app.modules.stock.models import Stock
from app.modules.stock.repository import StockRepository


@pytest.fixture
async def stock_product() -> AsyncGenerator[tuple[AsyncSession, Product], None]:
    unique_value = uuid4().hex

    async with async_session_maker() as session:
        category = Category(
            nome="Informatica",
            slug=f"informatica-stock-{unique_value}",
            ativo=True,
        )
        session.add(category)
        await session.flush()

        product = Product(
            categoria_id=category.id,
            nome="Mouse sem fio",
            slug=f"mouse-stock-{unique_value}",
            descricao=None,
            sku=f"MOUSE-STOCK-{unique_value}",
            preco=Decimal("149.90"),
            ativo=True,
        )
        session.add(product)
        await session.flush()

        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            yield session

        app.dependency_overrides[get_session] = override_get_session
        product_id = product.id
        category_id = category.id

        try:
            yield session, product
        finally:
            app.dependency_overrides.pop(get_session, None)
            await session.rollback()
            await session.execute(delete(Stock).where(Stock.produto_id == product_id))
            await session.execute(delete(Product).where(Product.id == product_id))
            await session.execute(delete(Category).where(Category.id == category_id))
            await session.commit()


async def test_create_stock_endpoint_persists_initial_stock(
    stock_product: tuple[AsyncSession, Product],
) -> None:
    session, product = stock_product
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/admin/products/{product.id}/stock",
            json={"quantidade": 20},
        )

    body = response.json()
    saved_stock = await StockRepository(session).get_by_product_id(product.id)

    assert response.status_code == 201
    assert body["produto_id"] == str(product.id)
    assert body["quantidade"] == 20
    assert body["quantidade_reservada"] == 0
    assert body["quantidade_disponivel"] == 20
    assert saved_stock is not None
    assert str(saved_stock.id) == body["id"]


async def test_create_stock_endpoint_rejects_duplicate_stock(
    stock_product: tuple[AsyncSession, Product],
) -> None:
    _, product = stock_product
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.post(
            f"/admin/products/{product.id}/stock",
            json={"quantidade": 10},
        )
        second_response = await client.post(
            f"/admin/products/{product.id}/stock",
            json={"quantidade": 10},
        )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {
        "code": "STOCK_ALREADY_EXISTS",
        "message": "Estoque ja cadastrado para este produto.",
        "details": {"product_id": str(product.id)},
    }


async def test_create_stock_endpoint_returns_product_not_found() -> None:
    product_id = uuid4()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/admin/products/{product_id}/stock",
            json={"quantidade": 10},
        )

    assert response.status_code == 404
    assert response.json() == {
        "code": "PRODUCT_NOT_FOUND",
        "message": "Produto nao encontrado.",
        "details": {"product_id": str(product_id)},
    }


async def test_adjust_stock_endpoint_adds_entry(
    stock_product: tuple[AsyncSession, Product],
) -> None:
    _, product = stock_product
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            f"/admin/products/{product.id}/stock",
            json={"quantidade": 10},
        )
        response = await client.patch(
            f"/admin/products/{product.id}/stock",
            json={"operacao": "ENTRADA", "quantidade": 5},
        )

    assert response.status_code == 200
    assert response.json()["quantidade"] == 15
    assert response.json()["quantidade_disponivel"] == 15


async def test_adjust_stock_endpoint_removes_exit(
    stock_product: tuple[AsyncSession, Product],
) -> None:
    _, product = stock_product
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            f"/admin/products/{product.id}/stock",
            json={"quantidade": 10},
        )
        response = await client.patch(
            f"/admin/products/{product.id}/stock",
            json={"operacao": "SAIDA", "quantidade": 4},
        )

    assert response.status_code == 200
    assert response.json()["quantidade"] == 6
    assert response.json()["quantidade_disponivel"] == 6


async def test_adjust_stock_endpoint_rejects_exit_above_available_stock(
    stock_product: tuple[AsyncSession, Product],
) -> None:
    session, product = stock_product
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            f"/admin/products/{product.id}/stock",
            json={"quantidade": 3},
        )
        response = await client.patch(
            f"/admin/products/{product.id}/stock",
            json={"operacao": "SAIDA", "quantidade": 4},
        )

    saved_stock = await StockRepository(session).get_by_product_id(product.id)

    assert response.status_code == 409
    assert response.json() == {
        "code": "INSUFFICIENT_STOCK",
        "message": "Estoque insuficiente.",
        "details": {
            "quantidade_solicitada": 4,
            "quantidade_disponivel": 3,
        },
    }
    assert saved_stock is not None
    assert saved_stock.quantidade == 3


async def test_adjust_stock_endpoint_returns_stock_not_found(
    stock_product: tuple[AsyncSession, Product],
) -> None:
    _, product = stock_product
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            f"/admin/products/{product.id}/stock",
            json={"operacao": "ENTRADA", "quantidade": 5},
        )

    assert response.status_code == 404
    assert response.json() == {
        "code": "STOCK_NOT_FOUND",
        "message": "Estoque nao encontrado.",
        "details": {"product_id": str(product.id)},
    }


async def test_get_stock_endpoint_returns_stock_output(
    stock_product: tuple[AsyncSession, Product],
) -> None:
    _, product = stock_product
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            f"/admin/products/{product.id}/stock",
            json={"quantidade": 12},
        )
        response = await client.get(f"/admin/products/{product.id}/stock")

    body = response.json()

    assert create_response.status_code == 201
    assert response.status_code == 200
    assert body["id"] == create_response.json()["id"]
    assert body["produto_id"] == str(product.id)
    assert body["quantidade"] == 12
    assert body["quantidade_reservada"] == 0
    assert body["quantidade_disponivel"] == 12
    assert "criado_em" in body
    assert "atualizado_em" in body


async def test_get_stock_endpoint_returns_not_found_for_product_without_stock(
    stock_product: tuple[AsyncSession, Product],
) -> None:
    _, product = stock_product
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/admin/products/{product.id}/stock")

    assert response.status_code == 404
    assert response.json() == {
        "code": "STOCK_NOT_FOUND",
        "message": "Estoque nao encontrado.",
        "details": {"product_id": str(product.id)},
    }
