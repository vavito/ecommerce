from collections.abc import AsyncGenerator
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, get_session
from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.cart.enums import CartStatus
from app.modules.cart.models import Cart, CartItem
from app.modules.cart.repository import CartRepository
from app.modules.product.models import Category, Product
from app.modules.stock.models import Stock
from app.modules.user.models import User


@pytest.fixture
async def authenticated_cart_user() -> AsyncGenerator[
    tuple[AsyncSession, User, str],
    None,
]:
    unique_value = uuid4()

    async with async_session_maker() as session:
        user = User(
            nome="Joao",
            email=f"joao-cart-{unique_value.hex}@example.com",
            cpf=f"{unique_value.int % 100_000_000_000:011d}",
            senha_hash=hash_password("senha123"),
            ativo=True,
        )
        session.add(user)
        await session.flush()

        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            yield session

        app.dependency_overrides[get_session] = override_get_session
        token = create_access_token(str(user.id))
        user_id = user.id

        try:
            yield session, user, token
        finally:
            app.dependency_overrides.pop(get_session, None)
            await session.rollback()
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


@pytest.fixture
async def stocked_cart_product(
    authenticated_cart_user: tuple[AsyncSession, User, str],
) -> AsyncGenerator[tuple[AsyncSession, User, str, Product, Stock], None]:
    session, user, token = authenticated_cart_user
    unique_value = uuid4().hex
    category = Category(
        nome="Informatica",
        slug=f"informatica-cart-endpoint-{unique_value}",
        ativo=True,
    )
    session.add(category)
    await session.flush()

    product = Product(
        categoria_id=category.id,
        nome="Mouse sem fio",
        slug=f"mouse-cart-endpoint-{unique_value}",
        descricao=None,
        sku=f"CART-{unique_value}",
        preco=Decimal("149.90"),
        ativo=True,
    )
    session.add(product)
    await session.flush()

    stock = Stock(
        produto_id=product.id,
        quantidade=10,
        quantidade_reservada=0,
    )
    session.add(stock)
    await session.flush()
    user_id = user.id
    product_id = product.id
    category_id = category.id

    try:
        yield session, user, token, product, stock
    finally:
        await session.rollback()
        user_cart_ids = select(Cart.id).where(Cart.usuario_id == user_id)
        await session.execute(
            delete(CartItem).where(CartItem.carrinho_id.in_(user_cart_ids))
        )
        await session.execute(delete(Cart).where(Cart.usuario_id == user_id))
        await session.execute(delete(Stock).where(Stock.produto_id == product_id))
        await session.execute(delete(Product).where(Product.id == product_id))
        await session.execute(delete(Category).where(Category.id == category_id))
        await session.commit()


async def create_item_for_other_user(
    session: AsyncSession,
    product: Product,
) -> tuple[UUID, UUID]:
    unique_value = uuid4()
    other_user = User(
        nome="Maria",
        email=f"maria-cart-{unique_value.hex}@example.com",
        cpf=f"{unique_value.int % 100_000_000_000:011d}",
        senha_hash="hash",
        ativo=True,
    )
    session.add(other_user)
    await session.flush()
    other_cart = Cart(
        usuario_id=other_user.id,
        status=CartStatus.OPEN,
    )
    session.add(other_cart)
    await session.flush()
    other_item = CartItem(
        carrinho_id=other_cart.id,
        produto_id=product.id,
        quantidade=1,
        preco_unitario_atual=product.preco,
    )
    session.add(other_item)
    await session.flush()

    return other_user.id, other_item.id


async def test_get_cart_creates_and_returns_empty_cart(
    authenticated_cart_user: tuple[AsyncSession, User, str],
) -> None:
    session, user, token = authenticated_cart_user
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/cart",
            headers={"Authorization": f"Bearer {token}"},
        )

    body = response.json()
    saved_cart = await CartRepository(session).get_open_by_user_id(user.id)

    assert response.status_code == 200
    assert body["usuario_id"] == str(user.id)
    assert body["status"] == "OPEN"
    assert body["itens"] == []
    assert body["total_estimado"] == "0.00"
    assert saved_cart is not None
    assert str(saved_cart.id) == body["id"]


async def test_get_cart_returns_same_open_cart_on_next_request(
    authenticated_cart_user: tuple[AsyncSession, User, str],
) -> None:
    _, _user, token = authenticated_cart_user
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.get("/cart", headers=headers)
        second_response = await client.get("/cart", headers=headers)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["id"] == first_response.json()["id"]


async def test_get_cart_requires_access_token() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/cart")

    assert response.status_code == 401
    assert response.json() == {
        "code": "AUTHENTICATION_REQUIRED",
        "message": "Token de autenticacao nao informado.",
        "details": {},
    }


async def test_add_cart_item_persists_item_with_current_price(
    stocked_cart_product: tuple[AsyncSession, User, str, Product, Stock],
) -> None:
    session, user, token, product, _stock = stocked_cart_product
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/cart/items",
            json={
                "produto_id": str(product.id),
                "quantidade": 2,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    body = response.json()
    cart = await CartRepository(session).get_open_by_user_id(user.id)
    assert cart is not None
    saved_item = await CartRepository(session).get_item_by_product_id(
        cart.id,
        product.id,
    )

    assert response.status_code == 201
    assert body["produto_id"] == str(product.id)
    assert body["quantidade"] == 2
    assert body["preco_unitario_atual"] == "149.90"
    assert body["subtotal"] == "299.80"
    assert saved_item is not None
    assert str(saved_item.id) == body["id"]


async def test_add_same_product_increases_existing_item_quantity(
    stocked_cart_product: tuple[AsyncSession, User, str, Product, Stock],
) -> None:
    _session, _user, token, product, _stock = stocked_cart_product
    transport = ASGITransport(app=app)
    payload = {
        "produto_id": str(product.id),
        "quantidade": 2,
    }
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.post(
            "/cart/items",
            json=payload,
            headers=headers,
        )
        second_response = await client.post(
            "/cart/items",
            json={
                "produto_id": str(product.id),
                "quantidade": 3,
            },
            headers=headers,
        )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json()["id"] == first_response.json()["id"]
    assert second_response.json()["quantidade"] == 5
    assert second_response.json()["subtotal"] == "749.50"


async def test_add_cart_item_rejects_inactive_product(
    stocked_cart_product: tuple[AsyncSession, User, str, Product, Stock],
) -> None:
    session, _user, token, product, _stock = stocked_cart_product
    product.ativo = False
    await session.flush()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/cart/items",
            json={
                "produto_id": str(product.id),
                "quantidade": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 409
    assert response.json()["code"] == "PRODUCT_INACTIVE"


async def test_add_cart_item_rejects_quantity_above_available_stock(
    stocked_cart_product: tuple[AsyncSession, User, str, Product, Stock],
) -> None:
    _session, _user, token, product, stock = stocked_cart_product
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/cart/items",
            json={
                "produto_id": str(product.id),
                "quantidade": stock.quantidade + 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 409
    assert response.json() == {
        "code": "INSUFFICIENT_STOCK",
        "message": "Estoque insuficiente.",
        "details": {
            "quantidade_solicitada": 11,
            "quantidade_disponivel": 10,
        },
    }


async def test_add_cart_item_requires_access_token() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/cart/items",
            json={
                "produto_id": str(uuid4()),
                "quantidade": 1,
            },
        )

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"


async def test_update_cart_item_changes_quantity_and_subtotal(
    stocked_cart_product: tuple[AsyncSession, User, str, Product, Stock],
) -> None:
    session, _user, token, product, _stock = stocked_cart_product
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/cart/items",
            json={
                "produto_id": str(product.id),
                "quantidade": 2,
            },
            headers=headers,
        )
        item_id = create_response.json()["id"]
        response = await client.patch(
            f"/cart/items/{item_id}",
            json={"quantidade": 4},
            headers=headers,
        )

    saved_item = await CartRepository(session).get_item_by_id(UUID(item_id))

    assert create_response.status_code == 201
    assert response.status_code == 200
    assert response.json()["id"] == item_id
    assert response.json()["quantidade"] == 4
    assert response.json()["subtotal"] == "599.60"
    assert saved_item is not None
    assert saved_item.quantidade == 4


async def test_update_cart_item_rejects_quantity_above_available_stock(
    stocked_cart_product: tuple[AsyncSession, User, str, Product, Stock],
) -> None:
    session, _user, token, product, stock = stocked_cart_product
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/cart/items",
            json={
                "produto_id": str(product.id),
                "quantidade": 2,
            },
            headers=headers,
        )
        item_id = create_response.json()["id"]
        response = await client.patch(
            f"/cart/items/{item_id}",
            json={"quantidade": stock.quantidade + 1},
            headers=headers,
        )

    saved_item = await CartRepository(session).get_item_by_id(UUID(item_id))

    assert response.status_code == 409
    assert response.json()["code"] == "INSUFFICIENT_STOCK"
    assert saved_item is not None
    assert saved_item.quantidade == 2


async def test_update_cart_item_rejects_item_from_another_user(
    stocked_cart_product: tuple[AsyncSession, User, str, Product, Stock],
) -> None:
    session, _user, token, product, _stock = stocked_cart_product
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/cart", headers=headers)
        other_user_id, other_item_id = await create_item_for_other_user(
            session,
            product,
        )

        response = await client.patch(
            f"/cart/items/{other_item_id}",
            json={"quantidade": 2},
            headers=headers,
        )

    await session.rollback()
    await session.execute(delete(User).where(User.id == other_user_id))
    await session.commit()

    assert response.status_code == 404
    assert response.json() == {
        "code": "CART_ITEM_NOT_FOUND",
        "message": "Item do carrinho nao encontrado.",
        "details": {"item_id": str(other_item_id)},
    }


async def test_update_cart_item_requires_access_token() -> None:
    item_id = uuid4()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            f"/cart/items/{item_id}",
            json={"quantidade": 2},
        )

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"


async def test_delete_cart_item_removes_item_and_updates_cart(
    stocked_cart_product: tuple[AsyncSession, User, str, Product, Stock],
) -> None:
    session, _user, token, product, _stock = stocked_cart_product
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/cart/items",
            json={
                "produto_id": str(product.id),
                "quantidade": 2,
            },
            headers=headers,
        )
        item_id = create_response.json()["id"]
        response = await client.delete(
            f"/cart/items/{item_id}",
            headers=headers,
        )
        cart_response = await client.get("/cart", headers=headers)

    saved_item = await CartRepository(session).get_item_by_id(UUID(item_id))

    assert create_response.status_code == 201
    assert response.status_code == 204
    assert response.content == b""
    assert saved_item is None
    assert cart_response.status_code == 200
    assert cart_response.json()["itens"] == []
    assert cart_response.json()["total_estimado"] == "0.00"


async def test_delete_cart_item_rejects_item_from_another_user(
    stocked_cart_product: tuple[AsyncSession, User, str, Product, Stock],
) -> None:
    session, _user, token, product, _stock = stocked_cart_product
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/cart", headers=headers)
        other_user_id, other_item_id = await create_item_for_other_user(
            session,
            product,
        )

        response = await client.delete(
            f"/cart/items/{other_item_id}",
            headers=headers,
        )

    await session.rollback()
    await session.execute(delete(User).where(User.id == other_user_id))
    await session.commit()

    assert response.status_code == 404
    assert response.json()["code"] == "CART_ITEM_NOT_FOUND"


async def test_delete_cart_item_requires_access_token() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(f"/cart/items/{uuid4()}")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"


async def test_cart_flow_keeps_total_after_repeated_product_and_stock_error(
    stocked_cart_product: tuple[AsyncSession, User, str, Product, Stock],
) -> None:
    _session, _user, token, product, stock = stocked_cart_product
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.post(
            "/cart/items",
            json={
                "produto_id": str(product.id),
                "quantidade": 2,
            },
            headers=headers,
        )
        second_response = await client.post(
            "/cart/items",
            json={
                "produto_id": str(product.id),
                "quantidade": 3,
            },
            headers=headers,
        )
        cart_response = await client.get("/cart", headers=headers)
        rejected_response = await client.post(
            "/cart/items",
            json={
                "produto_id": str(product.id),
                "quantidade": stock.quantidade - 4,
            },
            headers=headers,
        )
        unchanged_cart_response = await client.get("/cart", headers=headers)

    cart_body = cart_response.json()
    unchanged_cart_body = unchanged_cart_response.json()

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json()["id"] == first_response.json()["id"]
    assert len(cart_body["itens"]) == 1
    assert cart_body["itens"][0]["quantidade"] == 5
    assert cart_body["itens"][0]["subtotal"] == "749.50"
    assert cart_body["total_estimado"] == "749.50"

    assert rejected_response.status_code == 409
    assert rejected_response.json()["code"] == "INSUFFICIENT_STOCK"
    assert unchanged_cart_body["itens"] == cart_body["itens"]
    assert unchanged_cart_body["total_estimado"] == "749.50"
