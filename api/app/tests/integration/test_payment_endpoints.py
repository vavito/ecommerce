from collections.abc import AsyncGenerator
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, get_session
from app.core.security import create_access_token
from app.main import app
from app.modules.cart.enums import CartStatus
from app.modules.cart.models import Cart, CartItem
from app.modules.cart.repository import CartRepository
from app.modules.order.enums import OrderStatus
from app.modules.order.models import Order
from app.modules.order.repository import OrderRepository
from app.modules.order.service import OrderService
from app.modules.payment.enums import PaymentMethod, PaymentStatus
from app.modules.payment.models import Payment
from app.modules.product.models import Category, Product
from app.modules.stock.models import Stock
from app.modules.stock.repository import StockRepository
from app.modules.stock.service import StockService
from app.modules.user.models import Address, User
from app.modules.user.repository import UserRepository


@pytest.fixture
async def payment_endpoint_data() -> AsyncGenerator[
    tuple[AsyncSession, User, str, Payment, Order, Stock],
    None,
]:
    unique_value = uuid4().hex

    async with async_session_maker() as session:
        user = User(
            nome="Joao",
            email=f"joao-payment-endpoint-{unique_value}@example.com",
            cpf=unique_value[:11],
            senha_hash="hash",
            ativo=True,
        )
        category = Category(
            nome="Informatica",
            slug=f"informatica-payment-endpoint-{unique_value}",
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
            slug=f"teclado-payment-endpoint-{unique_value}",
            descricao=None,
            sku=f"PAY-{unique_value}",
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

        order_service = OrderService(
            OrderRepository(session),
            CartRepository(session),
            StockService(StockRepository(session)),
            UserRepository(session),
        )
        order = await order_service.checkout(
            user.id,
            address.id,
            PaymentMethod.PIX,
        )
        payment = order.pagamento
        await session.commit()

        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            yield session

        app.dependency_overrides[get_session] = override_get_session
        token = create_access_token(str(user.id))
        payment_id = payment.id
        order_id = order.id
        user_id = user.id
        product_id = product.id
        category_id = category.id

        try:
            yield session, user, token, payment, order, stock
        finally:
            app.dependency_overrides.pop(get_session, None)
            await session.rollback()
            await session.execute(delete(Payment).where(Payment.id == payment_id))
            await session.execute(delete(Order).where(Order.id == order_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.execute(delete(Product).where(Product.id == product_id))
            await session.execute(delete(Category).where(Category.id == category_id))
            await session.commit()


async def test_approve_payment_endpoint_confirms_order_and_stock(
    payment_endpoint_data: tuple[AsyncSession, User, str, Payment, Order, Stock],
) -> None:
    session, _user, token, payment, order, stock = payment_endpoint_data
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/payments/{payment.id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )

    await session.refresh(order)
    await session.refresh(stock)
    await session.refresh(payment)
    body = response.json()

    assert response.status_code == 200
    assert body["id"] == str(payment.id)
    assert body["pedido_id"] == str(order.id)
    assert body["status"] == "APPROVED"
    assert body["valor"] == "299.80"
    assert "idempotency_key" not in body
    assert payment.status is PaymentStatus.APPROVED
    assert order.status is OrderStatus.PAID
    assert stock.quantidade == 8
    assert stock.quantidade_reservada == 0
    assert stock.quantidade_disponivel == 8


async def test_approve_payment_endpoint_hides_another_users_payment(
    payment_endpoint_data: tuple[AsyncSession, User, str, Payment, Order, Stock],
) -> None:
    session, _user, _token, payment, order, stock = payment_endpoint_data
    unique_value = uuid4().hex
    other_user = User(
        nome="Maria",
        email=f"maria-payment-endpoint-{unique_value}@example.com",
        cpf=unique_value[:11],
        senha_hash="hash",
        ativo=True,
    )
    session.add(other_user)
    await session.flush()
    token = create_access_token(str(other_user.id))
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/payments/{payment.id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )

    await session.rollback()
    await session.refresh(order)
    await session.refresh(stock)
    await session.refresh(payment)

    assert response.status_code == 404
    assert response.json()["code"] == "PAYMENT_NOT_FOUND"
    assert payment.status is PaymentStatus.PENDING
    assert order.status is OrderStatus.PENDING_PAYMENT
    assert stock.quantidade == 10
    assert stock.quantidade_reservada == 2


async def test_approve_payment_endpoint_rejects_second_approval(
    payment_endpoint_data: tuple[AsyncSession, User, str, Payment, Order, Stock],
) -> None:
    session, _user, token, payment, _order, stock = payment_endpoint_data
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.post(
            f"/payments/{payment.id}/approve",
            headers=headers,
        )
        second_response = await client.post(
            f"/payments/{payment.id}/approve",
            headers=headers,
        )

    await session.refresh(stock)

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["code"] == "INVALID_PAYMENT_TRANSITION"
    assert stock.quantidade == 8
    assert stock.quantidade_reservada == 0


async def test_approve_payment_endpoint_requires_access_token() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/payments/{uuid4()}/approve")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"


async def test_refuse_payment_endpoint_releases_reservation_and_cancels_order(
    payment_endpoint_data: tuple[AsyncSession, User, str, Payment, Order, Stock],
) -> None:
    session, _user, token, payment, order, stock = payment_endpoint_data
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/payments/{payment.id}/refuse",
            headers={"Authorization": f"Bearer {token}"},
        )

    await session.refresh(order)
    await session.refresh(stock)
    await session.refresh(payment)
    body = response.json()

    assert response.status_code == 200
    assert body["id"] == str(payment.id)
    assert body["pedido_id"] == str(order.id)
    assert body["status"] == "REFUSED"
    assert payment.status is PaymentStatus.REFUSED
    assert order.status is OrderStatus.CANCELED
    assert stock.quantidade == 10
    assert stock.quantidade_reservada == 0
    assert stock.quantidade_disponivel == 10


async def test_refuse_payment_endpoint_rejects_second_refusal(
    payment_endpoint_data: tuple[AsyncSession, User, str, Payment, Order, Stock],
) -> None:
    session, _user, token, payment, _order, stock = payment_endpoint_data
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.post(
            f"/payments/{payment.id}/refuse",
            headers=headers,
        )
        second_response = await client.post(
            f"/payments/{payment.id}/refuse",
            headers=headers,
        )

    await session.refresh(stock)

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["code"] == "INVALID_PAYMENT_TRANSITION"
    assert stock.quantidade == 10
    assert stock.quantidade_reservada == 0


async def test_refuse_payment_endpoint_requires_access_token() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/payments/{uuid4()}/refuse")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"
