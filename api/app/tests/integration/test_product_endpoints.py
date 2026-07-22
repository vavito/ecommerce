from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, get_session
from app.main import app
from app.modules.product.models import Category, Product
from app.modules.product.repository import ProductRepository


@pytest.fixture
async def product_category() -> AsyncGenerator[tuple[AsyncSession, Category], None]:
    unique_value = uuid4()

    async with async_session_maker() as session:
        category = Category(
            nome="Eletronicos",
            slug=f"eletronicos-{unique_value.hex}",
            ativo=True,
        )
        session.add(category)
        await session.flush()

        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            yield session

        app.dependency_overrides[get_session] = override_get_session
        category_id = category.id

        try:
            yield session, category
        finally:
            app.dependency_overrides.pop(get_session, None)
            await session.rollback()
            await session.execute(
                delete(Product).where(Product.categoria_id == category_id)
            )
            await session.execute(delete(Category).where(Category.id == category_id))
            await session.commit()


async def test_create_product_endpoint_returns_persisted_product(
    product_category: tuple[AsyncSession, Category],
) -> None:
    session, category = product_category
    transport = ASGITransport(app=app)
    payload = {
        "categoria_id": str(category.id),
        "nome": "Teclado mecanico",
        "descricao": "Teclado com switches mecanicos.",
        "sku": "tec-mec-001",
        "preco": "299.90",
    }

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/admin/products", json=payload)

    body = response.json()
    saved_product = await ProductRepository(session).get_by_sku("TEC-MEC-001")

    assert response.status_code == 201
    assert body["categoria_id"] == str(category.id)
    assert body["nome"] == payload["nome"]
    assert body["sku"] == "TEC-MEC-001"
    assert body["preco"] == "299.90"
    assert body["ativo"] is True
    assert saved_product is not None
    assert str(saved_product.id) == body["id"]
