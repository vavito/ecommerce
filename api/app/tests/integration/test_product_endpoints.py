from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

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


async def test_update_product_endpoint_changes_only_sent_fields(
    product_category: tuple[AsyncSession, Category],
) -> None:
    session, category = product_category
    transport = ASGITransport(app=app)
    create_payload = {
        "categoria_id": str(category.id),
        "nome": "Teclado mecanico",
        "descricao": "Teclado com switches mecanicos.",
        "sku": "tec-mec-001",
        "preco": "299.90",
    }

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/admin/products",
            json=create_payload,
        )
        product_id = create_response.json()["id"]
        update_response = await client.patch(
            f"/admin/products/{product_id}",
            json={"preco": "249.90"},
        )

    body = update_response.json()
    saved_product = await ProductRepository(session).get_by_id(UUID(product_id))

    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert body["preco"] == "249.90"
    assert body["nome"] == create_payload["nome"]
    assert body["sku"] == "TEC-MEC-001"
    assert saved_product is not None
    assert str(saved_product.preco) == "249.90"
    assert saved_product.nome == create_payload["nome"]


async def test_update_product_endpoint_returns_not_found() -> None:
    product_id = uuid4()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            f"/admin/products/{product_id}",
            json={"preco": "249.90"},
        )

    assert response.status_code == 404
    assert response.json() == {
        "code": "PRODUCT_NOT_FOUND",
        "message": "Produto nao encontrado.",
        "details": {"product_id": str(product_id)},
    }
