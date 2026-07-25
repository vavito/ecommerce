from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.modules.cart.enums import CartStatus
from app.modules.cart.models import Cart, CartItem
from app.modules.cart.repository import CartRepository
from app.modules.cart.service import CartService
from app.modules.product.models import Product
from app.modules.product.service import ProductService
from app.modules.stock.service import StockService
from app.shared.exceptions import BusinessRuleException, NotFoundException


def make_cart(*, user_id: UUID | None = None) -> Cart:
    return Cart(
        id=uuid4(),
        usuario_id=user_id or uuid4(),
        status=CartStatus.OPEN,
    )


def make_product() -> Product:
    return Product(
        id=uuid4(),
        categoria_id=uuid4(),
        nome="Teclado mecanico",
        slug="teclado-mecanico",
        descricao=None,
        sku="TEC-MEC-001",
        preco=Decimal("299.90"),
        ativo=True,
    )


def make_service() -> tuple[
    CartService,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    repository = AsyncMock(spec=CartRepository)
    product_service = AsyncMock(spec=ProductService)
    stock_service = AsyncMock(spec=StockService)
    service = CartService(
        repository,
        product_service,
        stock_service,
    )
    return service, repository, product_service, stock_service


async def test_get_or_create_open_cart_returns_existing_cart() -> None:
    service, repository, _, _ = make_service()
    cart = make_cart()
    repository.get_open_by_user_id.return_value = cart

    result = await service.get_or_create_open_cart(cart.usuario_id)

    assert result is cart
    repository.add.assert_not_awaited()


async def test_get_or_create_open_cart_creates_cart_when_none_exists() -> None:
    service, repository, _, _ = make_service()
    user_id = uuid4()
    repository.get_open_by_user_id.return_value = None
    repository.add.side_effect = lambda cart: cart

    result = await service.get_or_create_open_cart(user_id)

    assert result.usuario_id == user_id
    assert result.status is CartStatus.OPEN
    repository.add.assert_awaited_once_with(result)


async def test_add_item_creates_item_with_current_product_price() -> None:
    service, repository, product_service, stock_service = make_service()
    cart = make_cart()
    product = make_product()
    repository.get_open_by_user_id_for_update.return_value = cart
    repository.get_item_by_product_id.return_value = None
    repository.add_item.side_effect = lambda item: item
    product_service.get_product.return_value = product

    result = await service.add_item(cart.usuario_id, product.id, 2)

    assert result.carrinho_id == cart.id
    assert result.produto_id == product.id
    assert result.quantidade == 2
    assert result.preco_unitario_atual == product.preco
    repository.get_open_by_user_id_for_update.assert_awaited_once_with(cart.usuario_id)
    repository.get_open_by_user_id.assert_not_awaited()
    stock_service.ensure_sellable.assert_awaited_once_with(product, 2)
    repository.add_item.assert_awaited_once_with(result)


async def test_add_existing_product_increases_quantity_and_validates_total() -> None:
    service, repository, product_service, stock_service = make_service()
    cart = make_cart()
    product = make_product()
    item = CartItem(
        id=uuid4(),
        carrinho_id=cart.id,
        produto_id=product.id,
        quantidade=3,
        preco_unitario_atual=Decimal("289.90"),
    )
    repository.get_open_by_user_id_for_update.return_value = cart
    repository.get_item_by_product_id.return_value = item
    repository.update_item.return_value = item
    product_service.get_product.return_value = product

    result = await service.add_item(cart.usuario_id, product.id, 2)

    assert result is item
    assert result.quantidade == 5
    assert result.preco_unitario_atual == product.preco
    repository.get_open_by_user_id_for_update.assert_awaited_once_with(cart.usuario_id)
    stock_service.ensure_sellable.assert_awaited_once_with(product, 5)
    repository.add_item.assert_not_awaited()
    repository.update_item.assert_awaited_once_with(item)


async def test_update_item_quantity_validates_ownership_product_and_stock() -> None:
    service, repository, product_service, stock_service = make_service()
    cart = make_cart()
    product = make_product()
    item = CartItem(
        id=uuid4(),
        carrinho_id=cart.id,
        produto_id=product.id,
        quantidade=1,
        preco_unitario_atual=Decimal("289.90"),
    )
    repository.get_open_by_user_id_for_update.return_value = cart
    repository.get_item_by_id.return_value = item
    repository.update_item.return_value = item
    product_service.get_product.return_value = product

    result = await service.update_item_quantity(cart.usuario_id, item.id, 4)

    assert result.quantidade == 4
    assert result.preco_unitario_atual == product.preco
    repository.get_open_by_user_id_for_update.assert_awaited_once_with(cart.usuario_id)
    stock_service.ensure_sellable.assert_awaited_once_with(product, 4)
    repository.update_item.assert_awaited_once_with(item)


async def test_remove_item_deletes_owned_item() -> None:
    service, repository, _, _ = make_service()
    cart = make_cart()
    item = CartItem(
        id=uuid4(),
        carrinho_id=cart.id,
        produto_id=uuid4(),
        quantidade=1,
        preco_unitario_atual=Decimal("99.90"),
    )
    repository.get_open_by_user_id_for_update.return_value = cart
    repository.get_item_by_id.return_value = item

    await service.remove_item(cart.usuario_id, item.id)

    repository.get_open_by_user_id_for_update.assert_awaited_once_with(cart.usuario_id)
    repository.delete_item.assert_awaited_once_with(item)


async def test_update_rejects_item_from_another_users_cart() -> None:
    service, repository, product_service, stock_service = make_service()
    cart = make_cart()
    item = CartItem(
        id=uuid4(),
        carrinho_id=uuid4(),
        produto_id=uuid4(),
        quantidade=1,
        preco_unitario_atual=Decimal("99.90"),
    )
    repository.get_open_by_user_id_for_update.return_value = cart
    repository.get_item_by_id.return_value = item

    with pytest.raises(NotFoundException) as exc_info:
        await service.update_item_quantity(cart.usuario_id, item.id, 2)

    assert exc_info.value.code == "CART_ITEM_NOT_FOUND"
    product_service.get_product.assert_not_awaited()
    stock_service.ensure_sellable.assert_not_awaited()
    repository.update_item.assert_not_awaited()


@pytest.mark.parametrize("quantity", [0, -1])
async def test_cart_item_operations_reject_non_positive_quantity(
    quantity: int,
) -> None:
    service, repository, _, _ = make_service()

    with pytest.raises(BusinessRuleException) as exc_info:
        await service.add_item(uuid4(), uuid4(), quantity)

    assert exc_info.value.code == "INVALID_CART_ITEM_QUANTITY"
    repository.get_open_by_user_id.assert_not_awaited()
    repository.get_open_by_user_id_for_update.assert_not_awaited()
