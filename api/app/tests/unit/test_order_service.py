from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.modules.cart.enums import CartStatus
from app.modules.cart.models import Cart, CartItem
from app.modules.cart.repository import CartRepository
from app.modules.order.enums import OrderStatus
from app.modules.order.models import Order
from app.modules.order.repository import OrderRepository
from app.modules.order.service import OrderService
from app.modules.payment.enums import PaymentMethod, PaymentStatus
from app.modules.product.models import Product
from app.modules.stock.service import StockService
from app.modules.user.models import Address
from app.modules.user.repository import UserRepository
from app.shared.exceptions import (
    BusinessRuleException,
    ConflictException,
    NotFoundException,
)


def make_product(*, product_id: UUID, name: str, price: Decimal) -> Product:
    return Product(
        id=product_id,
        categoria_id=uuid4(),
        nome=name,
        slug=name.lower().replace(" ", "-"),
        descricao=None,
        sku=f"SKU-{product_id}",
        preco=price,
        ativo=True,
    )


def make_address(user_id: UUID) -> Address:
    return Address(
        id=uuid4(),
        usuario_id=user_id,
        cep="01001000",
        rua="Praca da Se",
        numero="1",
        complemento=None,
        bairro="Se",
        cidade="Sao Paulo",
        estado="SP",
        principal=True,
    )


def make_cart(user_id: UUID, products: list[tuple[Product, int]]) -> Cart:
    cart = Cart(
        id=uuid4(),
        usuario_id=user_id,
        status=CartStatus.OPEN,
    )
    cart.itens = [
        CartItem(
            id=uuid4(),
            carrinho_id=cart.id,
            produto_id=product.id,
            quantidade=quantity,
            preco_unitario_atual=product.preco,
            produto=product,
        )
        for product, quantity in products
    ]
    return cart


def make_service() -> tuple[
    OrderService,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    repository = AsyncMock(spec=OrderRepository)
    cart_repository = AsyncMock(spec=CartRepository)
    stock_service = AsyncMock(spec=StockService)
    user_repository = AsyncMock(spec=UserRepository)
    service = OrderService(
        repository,
        cart_repository,
        stock_service,
        user_repository,
    )
    return (
        service,
        repository,
        cart_repository,
        stock_service,
        user_repository,
    )


async def test_checkout_creates_order_payment_and_reserves_stock() -> None:
    service, repository, cart_repository, stock_service, user_repository = (
        make_service()
    )
    user_id = uuid4()
    first_product = make_product(
        product_id=UUID(int=1),
        name="Teclado mecanico",
        price=Decimal("200.00"),
    )
    second_product = make_product(
        product_id=UUID(int=2),
        name="Mouse sem fio",
        price=Decimal("100.00"),
    )
    cart = make_cart(
        user_id,
        [(second_product, 2), (first_product, 1)],
    )
    address = make_address(user_id)
    cart_repository.get_open_by_user_id_for_update.return_value = cart
    user_repository.get_address_by_id_and_user_id.return_value = address
    repository.add.side_effect = lambda order: order
    cart_repository.update.side_effect = lambda updated_cart: updated_cart

    result = await service.checkout(
        user_id,
        address.id,
        PaymentMethod.PIX,
        Decimal("20.00"),
    )

    assert result.status is OrderStatus.PENDING_PAYMENT
    assert result.valor_produtos == Decimal("400.00")
    assert result.valor_frete == Decimal("20.00")
    assert result.valor_total == Decimal("420.00")
    assert result.endereco_snapshot["cep"] == address.cep
    assert {item.nome_produto_snapshot for item in result.itens} == {
        first_product.nome,
        second_product.nome,
    }
    assert result.pagamento.metodo is PaymentMethod.PIX
    assert result.pagamento.status is PaymentStatus.PENDING
    assert result.pagamento.valor == result.valor_total
    assert cart.status is CartStatus.CLOSED
    assert stock_service.reserve_for_sale.await_count == 2
    repository.add.assert_awaited_once_with(result)
    cart_repository.update.assert_awaited_once_with(cart)


@pytest.mark.parametrize("cart", [None, Cart(usuario_id=uuid4(), itens=[])])
async def test_checkout_rejects_missing_or_empty_cart(cart: Cart | None) -> None:
    service, repository, cart_repository, stock_service, user_repository = (
        make_service()
    )
    cart_repository.get_open_by_user_id_for_update.return_value = cart

    with pytest.raises(BusinessRuleException) as exc_info:
        await service.checkout(
            uuid4(),
            uuid4(),
            PaymentMethod.CREDIT_CARD,
        )

    assert exc_info.value.code == "CART_EMPTY"
    user_repository.get_address_by_id_and_user_id.assert_not_awaited()
    stock_service.reserve_for_sale.assert_not_awaited()
    repository.add.assert_not_awaited()


async def test_checkout_rejects_address_from_another_user() -> None:
    service, repository, cart_repository, stock_service, user_repository = (
        make_service()
    )
    user_id = uuid4()
    product = make_product(
        product_id=uuid4(),
        name="Teclado mecanico",
        price=Decimal("200.00"),
    )
    cart_repository.get_open_by_user_id_for_update.return_value = make_cart(
        user_id,
        [(product, 1)],
    )
    user_repository.get_address_by_id_and_user_id.return_value = None
    address_id = uuid4()

    with pytest.raises(NotFoundException) as exc_info:
        await service.checkout(
            user_id,
            address_id,
            PaymentMethod.BOLETO,
        )

    assert exc_info.value.code == "ADDRESS_NOT_FOUND"
    assert exc_info.value.details == {"address_id": str(address_id)}
    stock_service.reserve_for_sale.assert_not_awaited()
    repository.add.assert_not_awaited()


async def test_checkout_stops_before_order_when_stock_is_insufficient() -> None:
    service, repository, cart_repository, stock_service, user_repository = (
        make_service()
    )
    user_id = uuid4()
    first_product = make_product(
        product_id=UUID(int=1),
        name="Teclado mecanico",
        price=Decimal("200.00"),
    )
    second_product = make_product(
        product_id=UUID(int=2),
        name="Mouse sem fio",
        price=Decimal("100.00"),
    )
    cart = make_cart(
        user_id,
        [(first_product, 1), (second_product, 2)],
    )
    address = make_address(user_id)
    cart_repository.get_open_by_user_id_for_update.return_value = cart
    user_repository.get_address_by_id_and_user_id.return_value = address
    stock_service.reserve_for_sale.side_effect = [
        None,
        ConflictException(
            code="INSUFFICIENT_STOCK",
            message="Estoque insuficiente.",
        ),
    ]

    with pytest.raises(ConflictException) as exc_info:
        await service.checkout(
            user_id,
            address.id,
            PaymentMethod.PIX,
        )

    assert exc_info.value.code == "INSUFFICIENT_STOCK"
    assert cart.status is CartStatus.OPEN
    repository.add.assert_not_awaited()
    cart_repository.update.assert_not_awaited()


async def test_checkout_rejects_negative_shipping_amount() -> None:
    service, repository, cart_repository, stock_service, user_repository = (
        make_service()
    )

    with pytest.raises(BusinessRuleException) as exc_info:
        await service.checkout(
            uuid4(),
            uuid4(),
            PaymentMethod.PIX,
            Decimal("-0.01"),
        )

    assert exc_info.value.code == "INVALID_SHIPPING_AMOUNT"
    cart_repository.get_open_by_user_id_for_update.assert_not_awaited()
    user_repository.get_address_by_id_and_user_id.assert_not_awaited()
    stock_service.reserve_for_sale.assert_not_awaited()
    repository.add.assert_not_awaited()


async def test_list_orders_delegates_user_and_pagination_to_repository() -> None:
    service, repository, _cart_repository, _stock_service, _user_repository = (
        make_service()
    )
    user_id = uuid4()
    repository.list_by_user_id.return_value = ([], 0)

    orders, total = await service.list_orders(
        user_id,
        offset=20,
        limit=10,
    )

    assert orders == []
    assert total == 0
    repository.list_by_user_id.assert_awaited_once_with(
        user_id,
        offset=20,
        limit=10,
    )


async def test_get_order_returns_order_owned_by_user() -> None:
    service, repository, _cart_repository, _stock_service, _user_repository = (
        make_service()
    )
    user_id = uuid4()
    order = Order(
        id=uuid4(),
        usuario_id=user_id,
        status=OrderStatus.PENDING_PAYMENT,
        valor_produtos=Decimal("100.00"),
        valor_frete=Decimal("0.00"),
        valor_total=Decimal("100.00"),
        endereco_snapshot={},
        itens=[],
    )
    repository.get_by_id_and_user_id.return_value = order

    result = await service.get_order(user_id, order.id)

    assert result is order
    repository.get_by_id_and_user_id.assert_awaited_once_with(
        order.id,
        user_id,
    )


async def test_get_order_hides_missing_or_other_users_order() -> None:
    service, repository, _cart_repository, _stock_service, _user_repository = (
        make_service()
    )
    user_id = uuid4()
    order_id = uuid4()
    repository.get_by_id_and_user_id.return_value = None

    with pytest.raises(NotFoundException) as exc_info:
        await service.get_order(user_id, order_id)

    assert exc_info.value.code == "ORDER_NOT_FOUND"
    assert exc_info.value.details == {"order_id": str(order_id)}
