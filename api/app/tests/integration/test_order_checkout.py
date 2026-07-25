from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.modules.cart.enums import CartStatus
from app.modules.cart.models import Cart, CartItem
from app.modules.cart.repository import CartRepository
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
from app.shared.exceptions import ConflictException


async def create_checkout_data(
    session: AsyncSession,
    *,
    second_stock_unavailable: bool = False,
) -> tuple[User, Address, list[Product], list[Stock], Cart]:
    unique_value = uuid4().hex
    user = User(
        nome="Joao",
        email=f"joao-checkout-{unique_value}@example.com",
        cpf=unique_value[:11],
        senha_hash="hash",
    )
    category = Category(
        nome="Informatica",
        slug=f"informatica-checkout-{unique_value}",
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
    products = [
        Product(
            categoria_id=category.id,
            nome="Teclado mecanico",
            slug=f"teclado-checkout-{unique_value}",
            descricao=None,
            sku=f"TEC-CHECKOUT-{unique_value}",
            preco=Decimal("120.00"),
            ativo=True,
        ),
        Product(
            categoria_id=category.id,
            nome="Mouse sem fio",
            slug=f"mouse-checkout-{unique_value}",
            descricao=None,
            sku=f"MOU-CHECKOUT-{unique_value}",
            preco=Decimal("80.00"),
            ativo=True,
        ),
    ]
    session.add_all([address, *products])
    await session.flush()

    ordered_products = sorted(products, key=lambda product: str(product.id))
    stock_quantity_by_product = {
        ordered_products[0].id: 10,
        ordered_products[1].id: 0 if second_stock_unavailable else 10,
    }
    stocks = [
        Stock(
            produto_id=product.id,
            quantidade=stock_quantity_by_product[product.id],
            quantidade_reservada=0,
        )
        for product in products
    ]
    cart = Cart(
        usuario_id=user.id,
        status=CartStatus.OPEN,
        itens=[
            CartItem(
                produto_id=products[0].id,
                quantidade=1,
                preco_unitario_atual=Decimal("1.00"),
            ),
            CartItem(
                produto_id=products[1].id,
                quantidade=2,
                preco_unitario_atual=Decimal("1.00"),
            ),
        ],
    )
    session.add_all([*stocks, cart])
    await session.flush()

    return user, address, products, stocks, cart


def build_order_service(session: AsyncSession) -> OrderService:
    return OrderService(
        OrderRepository(session),
        CartRepository(session),
        StockService(StockRepository(session)),
        UserRepository(session),
    )


async def test_checkout_persists_order_payment_and_stock_reservations() -> None:
    async with async_session_maker() as session:
        try:
            user, address, products, stocks, cart = await create_checkout_data(session)
            service = build_order_service(session)

            order = await service.checkout(
                user.id,
                address.id,
                PaymentMethod.PIX,
                Decimal("15.00"),
            )

            payment_result = await session.execute(
                select(Payment).where(Payment.pedido_id == order.id)
            )
            saved_payment = payment_result.scalar_one()
            saved_order = await OrderRepository(session).get_by_id(order.id)

            assert saved_order is not None
            assert saved_order.valor_produtos == Decimal("280.00")
            assert saved_order.valor_frete == Decimal("15.00")
            assert saved_order.valor_total == Decimal("295.00")
            assert len(saved_order.itens) == 2
            assert {item.preco_unitario_snapshot for item in saved_order.itens} == {
                products[0].preco,
                products[1].preco,
            }
            assert saved_order.endereco_snapshot["rua"] == address.rua
            assert saved_payment.status is PaymentStatus.PENDING
            assert saved_payment.metodo is PaymentMethod.PIX
            assert saved_payment.valor == order.valor_total
            assert cart.status is CartStatus.CLOSED
            assert {
                stock.produto_id: stock.quantidade_reservada for stock in stocks
            } == {
                products[0].id: 1,
                products[1].id: 2,
            }
            assert {
                stock.produto_id: stock.quantidade_disponivel for stock in stocks
            } == {
                products[0].id: 9,
                products[1].id: 8,
            }
        finally:
            await session.rollback()


async def test_checkout_transaction_rolls_back_when_stock_reservation_fails() -> None:
    async with async_session_maker() as session:
        try:
            user, address, _products, stocks, cart = await create_checkout_data(
                session,
                second_stock_unavailable=True,
            )
            service = build_order_service(session)

            with pytest.raises(ConflictException) as exc_info:
                async with session.begin_nested():
                    await service.checkout(
                        user.id,
                        address.id,
                        PaymentMethod.CREDIT_CARD,
                    )

            for stock in stocks:
                await session.refresh(stock)
            await session.refresh(cart)

            order_count = await session.scalar(
                select(func.count(Order.id)).where(Order.usuario_id == user.id)
            )
            payment_count = await session.scalar(
                select(func.count(Payment.id))
                .join(Order)
                .where(Order.usuario_id == user.id)
            )

            assert exc_info.value.code == "INSUFFICIENT_STOCK"
            assert order_count == 0
            assert payment_count == 0
            assert cart.status is CartStatus.OPEN
            assert all(stock.quantidade_reservada == 0 for stock in stocks)
        finally:
            await session.rollback()
