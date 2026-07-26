from collections.abc import AsyncGenerator
from decimal import Decimal
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
    unique_value = uuid4().hex
    sku = f"tec-mec-{unique_value}"
    payload = {
        "categoria_id": str(category.id),
        "nome": f"Teclado mecanico {unique_value}",
        "descricao": "Teclado com switches mecanicos.",
        "sku": sku,
        "preco": "299.90",
    }

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/admin/products", json=payload)

    body = response.json()
    saved_product = await ProductRepository(session).get_by_sku(sku.upper())

    assert response.status_code == 201
    assert body["categoria_id"] == str(category.id)
    assert body["nome"] == payload["nome"]
    assert body["slug"] == f"teclado-mecanico-{unique_value}"
    assert body["sku"] == sku.upper()
    assert body["preco"] == "299.90"
    assert body["ativo"] is True
    assert saved_product is not None
    assert str(saved_product.id) == body["id"]


async def test_update_product_endpoint_changes_only_sent_fields(
    product_category: tuple[AsyncSession, Category],
) -> None:
    session, category = product_category
    transport = ASGITransport(app=app)
    sku = f"tec-mec-{uuid4().hex}"
    create_payload = {
        "categoria_id": str(category.id),
        "nome": "Teclado mecanico",
        "descricao": "Teclado com switches mecanicos.",
        "sku": sku,
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
    assert body["sku"] == sku.upper()
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


async def test_list_products_endpoint_returns_only_active_products(
    product_category: tuple[AsyncSession, Category],
) -> None:
    session, category = product_category
    unique_value = uuid4().hex
    session.add_all(
        [
            Product(
                categoria_id=category.id,
                nome="Mouse sem fio",
                slug=f"mouse-sem-fio-{unique_value}",
                descricao=None,
                sku=f"MOUSE-ATIVO-{unique_value}",
                preco=Decimal("149.90"),
                ativo=True,
            ),
            Product(
                categoria_id=category.id,
                nome="Mouse antigo",
                slug=f"mouse-antigo-{unique_value}",
                descricao=None,
                sku=f"MOUSE-INATIVO-{unique_value}",
                preco=Decimal("49.90"),
                ativo=False,
            ),
        ]
    )
    await session.flush()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/products",
            params={"nome": "mouse", "categoria_id": str(category.id)},
        )

    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 1
    assert body["offset"] == 0
    assert body["limit"] == 20
    assert [product["nome"] for product in body["items"]] == ["Mouse sem fio"]


async def test_list_products_endpoint_paginates_results(
    product_category: tuple[AsyncSession, Category],
) -> None:
    session, category = product_category
    unique_value = uuid4().hex
    session.add_all(
        [
            Product(
                categoria_id=category.id,
                nome="Teclado compacto",
                slug=f"teclado-compacto-{unique_value}",
                descricao=None,
                sku=f"TEC-COM-{unique_value}",
                preco=Decimal("199.90"),
                ativo=True,
            ),
            Product(
                categoria_id=category.id,
                nome="Teclado mecanico",
                slug=f"teclado-mecanico-{unique_value}",
                descricao=None,
                sku=f"TEC-MEC-{unique_value}",
                preco=Decimal("299.90"),
                ativo=True,
            ),
        ]
    )
    await session.flush()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/products",
            params={
                "nome": "teclado",
                "categoria_id": str(category.id),
                "offset": 1,
                "limit": 1,
            },
        )

    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 2
    assert body["offset"] == 1
    assert body["limit"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["nome"] == "Teclado mecanico"


async def test_get_product_endpoint_returns_active_product(
    product_category: tuple[AsyncSession, Category],
) -> None:
    session, category = product_category
    unique_value = uuid4().hex
    product = Product(
        categoria_id=category.id,
        nome="Monitor ultrawide",
        slug=f"monitor-ultrawide-{unique_value}",
        descricao="Monitor de 34 polegadas.",
        sku=f"MONITOR-{unique_value}",
        preco=Decimal("2499.90"),
        ativo=True,
    )
    session.add(product)
    await session.flush()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/products/{product.id}")

    body = response.json()

    assert response.status_code == 200
    assert body["id"] == str(product.id)
    assert body["categoria_id"] == str(category.id)
    assert body["nome"] == product.nome
    assert body["sku"] == product.sku
    assert body["preco"] == "2499.90"
    assert body["ativo"] is True


async def test_get_product_endpoint_returns_not_found() -> None:
    product_id = uuid4()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/products/{product_id}")

    assert response.status_code == 404
    assert response.json() == {
        "code": "PRODUCT_NOT_FOUND",
        "message": "Produto nao encontrado.",
        "details": {"product_id": str(product_id)},
    }


async def test_get_product_endpoint_hides_inactive_product(
    product_category: tuple[AsyncSession, Category],
) -> None:
    session, category = product_category
    unique_value = uuid4().hex
    product = Product(
        categoria_id=category.id,
        nome="Produto desativado",
        slug=f"produto-desativado-{unique_value}",
        descricao=None,
        sku=f"INATIVO-{unique_value}",
        preco=Decimal("10.00"),
        ativo=False,
    )
    session.add(product)
    await session.flush()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/products/{product.id}")

    assert response.status_code == 404
    assert response.json()["code"] == "PRODUCT_NOT_FOUND"


async def test_get_product_by_slug_endpoint_returns_active_product(
    product_category: tuple[AsyncSession, Category],
) -> None:
    session, category = product_category
    unique_value = uuid4().hex
    product = Product(
        categoria_id=category.id,
        nome="Webcam Full HD",
        slug=f"webcam-full-hd-{unique_value}",
        descricao=None,
        sku=f"WEBCAM-{unique_value}",
        preco=Decimal("399.90"),
        ativo=True,
    )
    session.add(product)
    await session.flush()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/products/by-slug/{product.slug}")

    assert response.status_code == 200
    assert response.json()["id"] == str(product.id)
    assert response.json()["slug"] == product.slug


async def test_get_product_by_slug_endpoint_returns_not_found() -> None:
    slug = f"produto-inexistente-{uuid4().hex}"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/products/by-slug/{slug}")

    assert response.status_code == 404
    assert response.json() == {
        "code": "PRODUCT_NOT_FOUND",
        "message": "Produto nao encontrado.",
        "details": {"slug": slug},
    }
