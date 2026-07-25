from collections.abc import AsyncGenerator
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, get_session
from app.core.security import create_access_token
from app.main import app
from app.modules.cart.enums import CartStatus
from app.modules.cart.models import Cart, CartItem
from app.modules.order.models import Order, OrderItem
from app.modules.order.repository import OrderRepository
from app.modules.payment.enums import PaymentStatus
from app.modules.payment.models import Payment
from app.modules.product.models import Category, Product
from app.modules.stock.models import Stock
from app.modules.user.models import Address, User


def make_order(
    user_id: UUID,
    product: Product,
    address: Address,
    *,
    shipping_amount: Decimal = Decimal("0.00"),
) -> Order:
    return Order(
        usuario_id=user_id,
        valor_produtos=product.preco,
        valor_frete=shipping_amount,
        valor_total=product.preco + shipping_amount,
        endereco_snapshot={
            "cep": address.cep,
            "rua": address.rua,
            "numero": address.numero,
            "complemento": address.complemento,
            "bairro": address.bairro,
            "cidade": address.cidade,
            "estado": address.estado,
        },
        itens=[
            OrderItem(
                produto_id=product.id,
                nome_produto_snapshot=product.nome,
                sku_snapshot=product.sku,
                quantidade=1,
                preco_unitario_snapshot=product.preco,
                preco_total=product.preco,
            )
        ],
    )


@pytest.fixture
async def checkout_endpoint_data() -> AsyncGenerator[
    tuple[AsyncSession, User, str, Address, Product, Stock, Cart],
    None,
]:
    unique_value = uuid4().hex

    async with async_session_maker() as session:
        user = User(
            nome="Joao",
            email=f"joao-order-endpoint-{unique_value}@example.com",
            cpf=unique_value[:11],
            senha_hash="hash",
            ativo=True,
        )
        category = Category(
            nome="Informatica",
            slug=f"informatica-order-endpoint-{unique_value}",
            ativo=True,
        )
        session.add_all([user, category])
        await session.flush()

        address = Address(
            usuario_id=user.id,
            cep="01001000",
            rua="Praca da Se",
            numero="1",
            complemento=None,
            bairro="Se",
            cidade="Sao Paulo",
            estado="SP",
            principal=True,
        )
        product = Product(
            categoria_id=category.id,
            nome="Teclado mecanico",
            slug=f"teclado-order-endpoint-{unique_value}",
            descricao=None,
            sku=f"ORD-{unique_value}",
            preco=Decimal("149.90"),
            ativo=True,
        )
        session.add_all([address, product])
        await session.flush()

        stock = Stock(
            produto_id=product.id,
            quantidade=10,
            quantidade_reservada=0,
        )
        cart = Cart(
            usuario_id=user.id,
            status=CartStatus.OPEN,
            itens=[
                CartItem(
                    produto_id=product.id,
                    quantidade=2,
                    preco_unitario_atual=product.preco,
                )
            ],
        )
        session.add_all([stock, cart])
        await session.flush()

        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            yield session

        app.dependency_overrides[get_session] = override_get_session
        token = create_access_token(str(user.id))
        user_id = user.id
        product_id = product.id
        category_id = category.id

        try:
            yield session, user, token, address, product, stock, cart
        finally:
            app.dependency_overrides.pop(get_session, None)
            await session.rollback()
            order_ids = select(Order.id).where(Order.usuario_id == user_id)
            await session.execute(
                delete(Payment).where(Payment.pedido_id.in_(order_ids))
            )
            await session.execute(delete(Order).where(Order.usuario_id == user_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.execute(delete(Product).where(Product.id == product_id))
            await session.execute(delete(Category).where(Category.id == category_id))
            await session.commit()


async def test_checkout_endpoint_creates_and_returns_order(
    checkout_endpoint_data: tuple[
        AsyncSession,
        User,
        str,
        Address,
        Product,
        Stock,
        Cart,
    ],
) -> None:
    session, user, token, address, product, stock, cart = checkout_endpoint_data
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/orders/checkout",
            json={
                "endereco_id": str(address.id),
                "metodo_pagamento": "PIX",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    body = response.json()
    saved_order = await OrderRepository(session).get_by_id(UUID(body["id"]))
    payment_result = await session.execute(
        select(Payment).where(Payment.pedido_id == UUID(body["id"]))
    )
    saved_payment = payment_result.scalar_one_or_none()
    await session.refresh(stock)
    await session.refresh(cart)

    assert response.status_code == 201
    assert body["usuario_id"] == str(user.id)
    assert body["status"] == "PENDING_PAYMENT"
    assert body["valor_produtos"] == "299.80"
    assert body["valor_frete"] == "0.00"
    assert body["valor_total"] == "299.80"
    assert body["endereco_snapshot"]["cep"] == address.cep
    assert len(body["itens"]) == 1
    assert body["itens"][0]["produto_id"] == str(product.id)
    assert body["itens"][0]["quantidade"] == 2
    assert body["itens"][0]["preco_unitario_snapshot"] == "149.90"
    assert body["itens"][0]["preco_total"] == "299.80"
    assert saved_order is not None
    assert saved_payment is not None
    assert saved_payment.status is PaymentStatus.PENDING
    assert stock.quantidade_reservada == 2
    assert stock.quantidade_disponivel == 8
    assert cart.status is CartStatus.CLOSED


async def test_checkout_endpoint_requires_access_token() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/orders/checkout",
            json={
                "endereco_id": str(uuid4()),
                "metodo_pagamento": "PIX",
            },
        )

    assert response.status_code == 401
    assert response.json() == {
        "code": "AUTHENTICATION_REQUIRED",
        "message": "Token de autenticacao nao informado.",
        "details": {},
    }


async def test_checkout_flow_preserves_snapshots_after_source_changes(
    checkout_endpoint_data: tuple[
        AsyncSession,
        User,
        str,
        Address,
        Product,
        Stock,
        Cart,
    ],
) -> None:
    session, _user, token, address, product, _stock, _cart = checkout_endpoint_data
    original_product_name = product.nome
    original_product_sku = product.sku
    original_address = {
        "cep": address.cep,
        "rua": address.rua,
        "numero": address.numero,
        "complemento": address.complemento,
        "bairro": address.bairro,
        "cidade": address.cidade,
        "estado": address.estado,
    }
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        checkout_response = await client.post(
            "/orders/checkout",
            json={
                "endereco_id": str(address.id),
                "metodo_pagamento": "PIX",
            },
            headers=headers,
        )
        order_id = checkout_response.json()["id"]

        product.nome = "Produto atualizado"
        product.sku = f"HIST-{uuid4().hex}"
        product.preco = Decimal("999.90")
        address.cep = "20040002"
        address.rua = "Rua atualizada"
        address.numero = "999"
        address.bairro = "Centro"
        address.cidade = "Rio de Janeiro"
        address.estado = "RJ"
        await session.commit()

        detail_response = await client.get(
            f"/orders/{order_id}",
            headers=headers,
        )

    detail = detail_response.json()
    saved_item = detail["itens"][0]

    assert checkout_response.status_code == 201
    assert detail_response.status_code == 200
    assert detail["valor_produtos"] == "299.80"
    assert detail["valor_total"] == "299.80"
    assert detail["endereco_snapshot"] == original_address
    assert saved_item["nome_produto_snapshot"] == original_product_name
    assert saved_item["sku_snapshot"] == original_product_sku
    assert saved_item["preco_unitario_snapshot"] == "149.90"
    assert saved_item["preco_total"] == "299.80"


async def test_list_orders_returns_authenticated_users_paginated_history(
    checkout_endpoint_data: tuple[
        AsyncSession,
        User,
        str,
        Address,
        Product,
        Stock,
        Cart,
    ],
) -> None:
    session, user, token, address, product, _stock, _cart = checkout_endpoint_data
    repository = OrderRepository(session)

    for shipping_amount in (Decimal("0.00"), Decimal("10.00")):
        await repository.add(
            make_order(
                user.id,
                product,
                address,
                shipping_amount=shipping_amount,
            )
        )
    await session.commit()

    nested_transaction = await session.begin_nested()
    try:
        unique_value = uuid4().hex
        other_user = User(
            nome="Maria",
            email=f"maria-order-history-{unique_value}@example.com",
            cpf=unique_value[:11],
            senha_hash="hash",
        )
        session.add(other_user)
        await session.flush()
        await repository.add(
            Order(
                usuario_id=other_user.id,
                valor_produtos=product.preco,
                valor_frete=Decimal("0.00"),
                valor_total=product.preco,
                endereco_snapshot=make_order(
                    other_user.id,
                    product,
                    address,
                ).endereco_snapshot,
                itens=[],
            )
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/orders",
                params={"offset": 1, "limit": 1},
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        await nested_transaction.rollback()

    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 2
    assert body["offset"] == 1
    assert body["limit"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["usuario_id"] == str(user.id)
    assert len(body["items"][0]["itens"]) == 1
    assert body["items"][0]["itens"][0]["produto_id"] == str(product.id)


async def test_list_orders_requires_access_token() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/orders")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"


async def test_get_order_returns_owned_order_details(
    checkout_endpoint_data: tuple[
        AsyncSession,
        User,
        str,
        Address,
        Product,
        Stock,
        Cart,
    ],
) -> None:
    session, user, token, address, product, _stock, _cart = checkout_endpoint_data
    order = await OrderRepository(session).add(make_order(user.id, product, address))
    await session.commit()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/orders/{order.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    body = response.json()

    assert response.status_code == 200
    assert body["id"] == str(order.id)
    assert body["usuario_id"] == str(user.id)
    assert body["valor_total"] == "149.90"
    assert body["endereco_snapshot"]["cep"] == address.cep
    assert len(body["itens"]) == 1
    assert body["itens"][0]["produto_id"] == str(product.id)


async def test_get_order_hides_order_from_another_user(
    checkout_endpoint_data: tuple[
        AsyncSession,
        User,
        str,
        Address,
        Product,
        Stock,
        Cart,
    ],
) -> None:
    session, _user, token, address, product, _stock, _cart = checkout_endpoint_data
    nested_transaction = await session.begin_nested()
    try:
        unique_value = uuid4().hex
        other_user = User(
            nome="Maria",
            email=f"maria-order-detail-{unique_value}@example.com",
            cpf=unique_value[:11],
            senha_hash="hash",
        )
        session.add(other_user)
        await session.flush()
        order = await OrderRepository(session).add(
            make_order(other_user.id, product, address)
        )
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/orders/{order.id}",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        await nested_transaction.rollback()

    assert response.status_code == 404
    assert response.json() == {
        "code": "ORDER_NOT_FOUND",
        "message": "Pedido nao encontrado.",
        "details": {"order_id": str(order.id)},
    }


async def test_get_order_returns_not_found_for_unknown_id(
    checkout_endpoint_data: tuple[
        AsyncSession,
        User,
        str,
        Address,
        Product,
        Stock,
        Cart,
    ],
) -> None:
    _session, _user, token, _address, _product, _stock, _cart = checkout_endpoint_data
    order_id = uuid4()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/orders/{order_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert response.json()["code"] == "ORDER_NOT_FOUND"


async def test_get_order_requires_access_token() -> None:
    order_id = uuid4()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/orders/{order_id}")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"
