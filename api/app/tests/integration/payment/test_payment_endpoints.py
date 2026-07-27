import asyncio
from collections.abc import AsyncGenerator
from decimal import Decimal
from uuid import UUID, uuid4

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
from app.modules.order.models import Order, OrderItem
from app.modules.order.repository import OrderRepository
from app.modules.order.service import OrderService
from app.modules.payment.enums import PaymentMethod, PaymentStatus
from app.modules.payment.models import Payment
from app.modules.payment.repository import PaymentRepository
from app.modules.payment.service import PaymentService
from app.modules.product.models import Category, Product
from app.modules.stock.models import Stock
from app.modules.stock.repository import StockRepository
from app.modules.stock.service import StockService
from app.modules.user.models import Address, User
from app.modules.user.repository import UserRepository
from app.shared.enums import UserRole
from app.shared.exceptions import ConflictException


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
            role=UserRole.ADMIN,
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


async def test_approve_payment_endpoint_blocks_customer(
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

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
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


async def test_mock_webhook_approves_payment_idempotently(
    payment_endpoint_data: tuple[AsyncSession, User, str, Payment, Order, Stock],
) -> None:
    session, _user, _token, payment, order, stock = payment_endpoint_data
    transport = ASGITransport(app=app)
    request = {
        "payment_id": str(payment.id),
        "status": "APPROVED",
        "gateway_transaction_id": "gateway-tx-approved",
    }
    headers = {"Idempotency-Key": "event-approved"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.post(
            "/payments/webhook/mock",
            json=request,
            headers=headers,
        )
        second_response = await client.post(
            "/payments/webhook/mock",
            json=request,
            headers=headers,
        )

    await session.refresh(order)
    await session.refresh(stock)
    await session.refresh(payment)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()
    assert first_response.json()["status"] == "APPROVED"
    assert first_response.json()["gateway_transaction_id"] == "gateway-tx-approved"
    assert payment.status is PaymentStatus.APPROVED
    assert payment.idempotency_key == "event-approved"
    assert order.status is OrderStatus.PAID
    assert stock.quantidade == 8
    assert stock.quantidade_reservada == 0


async def test_mock_webhook_rejects_changed_payload_for_processed_key(
    payment_endpoint_data: tuple[AsyncSession, User, str, Payment, Order, Stock],
) -> None:
    session, _user, _token, payment, order, stock = payment_endpoint_data
    transport = ASGITransport(app=app)
    headers = {"Idempotency-Key": "event-changed-payload"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.post(
            "/payments/webhook/mock",
            json={
                "payment_id": str(payment.id),
                "status": "APPROVED",
                "gateway_transaction_id": "gateway-tx-changed-payload",
            },
            headers=headers,
        )
        second_response = await client.post(
            "/payments/webhook/mock",
            json={
                "payment_id": str(payment.id),
                "status": "REFUSED",
                "gateway_transaction_id": "gateway-tx-changed-payload",
            },
            headers=headers,
        )

    await session.refresh(order)
    await session.refresh(stock)
    await session.refresh(payment)

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert payment.status is PaymentStatus.APPROVED
    assert order.status is OrderStatus.PAID
    assert stock.quantidade == 8
    assert stock.quantidade_reservada == 0


async def test_mock_webhook_refuses_payment_and_releases_reservation(
    payment_endpoint_data: tuple[AsyncSession, User, str, Payment, Order, Stock],
) -> None:
    session, _user, _token, payment, order, stock = payment_endpoint_data
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/payments/webhook/mock",
            json={
                "payment_id": str(payment.id),
                "status": "REFUSED",
                "gateway_transaction_id": "gateway-tx-refused",
            },
            headers={"Idempotency-Key": "event-refused"},
        )

    await session.refresh(order)
    await session.refresh(stock)
    await session.refresh(payment)

    assert response.status_code == 200
    assert response.json()["status"] == "REFUSED"
    assert payment.status is PaymentStatus.REFUSED
    assert payment.idempotency_key == "event-refused"
    assert order.status is OrderStatus.CANCELED
    assert stock.quantidade == 10
    assert stock.quantidade_reservada == 0
    assert stock.quantidade_disponivel == 10


async def test_mock_webhook_requires_idempotency_key_header() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/payments/webhook/mock",
            json={
                "payment_id": str(uuid4()),
                "status": "APPROVED",
                "gateway_transaction_id": "gateway-tx-missing-header",
            },
        )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_concurrent_webhook_key_reuse_rolls_back_losing_payment(
    payment_endpoint_data: tuple[AsyncSession, User, str, Payment, Order, Stock],
) -> None:
    session, user, _token, first_payment, first_order, stock = payment_endpoint_data
    first_item = first_order.itens[0]
    second_payment = Payment(
        metodo=PaymentMethod.PIX,
        status=PaymentStatus.PENDING,
        valor=first_order.valor_total,
        gateway="MOCK",
    )
    second_order = Order(
        usuario_id=user.id,
        status=OrderStatus.PENDING_PAYMENT,
        valor_produtos=first_order.valor_produtos,
        valor_frete=first_order.valor_frete,
        valor_total=first_order.valor_total,
        endereco_snapshot=first_order.endereco_snapshot,
        itens=[
            OrderItem(
                produto_id=first_item.produto_id,
                nome_produto_snapshot=first_item.nome_produto_snapshot,
                sku_snapshot=first_item.sku_snapshot,
                quantidade=first_item.quantidade,
                preco_unitario_snapshot=first_item.preco_unitario_snapshot,
                preco_total=first_item.preco_total,
            )
        ],
        pagamento=second_payment,
    )
    stock.quantidade_reservada += first_item.quantidade
    session.add(second_order)
    await session.commit()

    second_payment_id = second_payment.id
    second_order_id = second_order.id
    barrier = asyncio.Barrier(2)

    class SynchronizedPaymentRepository(PaymentRepository):
        def __init__(self, worker_session: AsyncSession) -> None:
            super().__init__(worker_session)
            self.first_idempotency_lookup = True

        async def get_by_idempotency_key(
            self,
            idempotency_key: str,
        ) -> Payment | None:
            payment = await super().get_by_idempotency_key(idempotency_key)

            if self.first_idempotency_lookup:
                self.first_idempotency_lookup = False
                await barrier.wait()

            return payment

    async def process(payment_id: UUID) -> str:
        async with async_session_maker() as worker_session:
            service = PaymentService(
                SynchronizedPaymentRepository(worker_session),
                StockService(StockRepository(worker_session)),
            )

            try:
                await service.process_webhook(
                    payment_id,
                    PaymentStatus.APPROVED,
                    "event-concurrent",
                    "gateway-tx-concurrent",
                )
                await worker_session.commit()
                return "APPROVED"
            except ConflictException as exc:
                await worker_session.rollback()
                return exc.code

    try:
        results = await asyncio.gather(
            process(first_payment.id),
            process(second_payment.id),
        )

        async with async_session_maker() as verification_session:
            verified_first_payment = await verification_session.get(
                Payment,
                first_payment.id,
            )
            verified_second_payment = await verification_session.get(
                Payment,
                second_payment.id,
            )
            verified_first_order = await verification_session.get(
                Order,
                first_order.id,
            )
            verified_second_order = await verification_session.get(
                Order,
                second_order.id,
            )
            verified_stock = await verification_session.get(Stock, stock.id)

        assert sorted(results) == ["APPROVED", "IDEMPOTENCY_KEY_CONFLICT"]
        assert {
            verified_first_payment.status,
            verified_second_payment.status,
        } == {
            PaymentStatus.PENDING,
            PaymentStatus.APPROVED,
        }
        assert {
            verified_first_order.status,
            verified_second_order.status,
        } == {
            OrderStatus.PENDING_PAYMENT,
            OrderStatus.PAID,
        }
        assert verified_stock.quantidade == 8
        assert verified_stock.quantidade_reservada == 2
    finally:
        async with async_session_maker() as cleanup_session:
            await cleanup_session.execute(
                delete(Payment).where(Payment.id == second_payment_id)
            )
            await cleanup_session.execute(
                delete(Order).where(Order.id == second_order_id)
            )
            await cleanup_session.commit()
