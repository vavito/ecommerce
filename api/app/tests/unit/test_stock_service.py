from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.product.models import Product
from app.modules.stock.models import Stock
from app.modules.stock.repository import StockRepository
from app.modules.stock.service import StockService
from app.shared.exceptions import (
    BusinessRuleException,
    ConflictException,
    NotFoundException,
)


def make_stock(*, quantity: int = 10, reserved: int = 0) -> Stock:
    return Stock(
        produto_id=uuid4(),
        quantidade=quantity,
        quantidade_reservada=reserved,
    )


def make_product(*, active: bool = True) -> Product:
    unique_value = uuid4().hex
    return Product(
        id=uuid4(),
        categoria_id=uuid4(),
        nome="Teclado mecanico",
        slug=f"teclado-mecanico-{unique_value}",
        descricao=None,
        sku=f"TEC-{unique_value}",
        preco=Decimal("299.90"),
        ativo=active,
    )


async def test_create_initial_stock_accepts_zero_quantity() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    product_id = uuid4()
    repository.get_by_product_id.return_value = None
    repository.add.side_effect = lambda stock: stock

    result = await service.create_initial_stock(product_id, 0)

    assert result.produto_id == product_id
    assert result.quantidade == 0
    assert result.quantidade_reservada == 0
    repository.add.assert_awaited_once_with(result)


async def test_create_initial_stock_rejects_duplicate_stock() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    stock = make_stock()
    repository.get_by_product_id.return_value = stock

    with pytest.raises(ConflictException) as exc_info:
        await service.create_initial_stock(stock.produto_id, 10)

    assert exc_info.value.code == "STOCK_ALREADY_EXISTS"
    assert exc_info.value.details == {"product_id": str(stock.produto_id)}
    repository.add.assert_not_awaited()


async def test_create_initial_stock_rejects_negative_quantity() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)

    with pytest.raises(BusinessRuleException) as exc_info:
        await service.create_initial_stock(uuid4(), -1)

    assert exc_info.value.code == "INVALID_STOCK_QUANTITY"
    repository.get_by_product_id.assert_not_awaited()


async def test_increase_adds_to_physical_stock() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    stock = make_stock(quantity=10, reserved=3)
    repository.get_by_product_id_for_update.return_value = stock
    repository.update.return_value = stock

    result = await service.increase(stock.produto_id, 5)

    assert result.quantidade == 15
    assert result.quantidade_reservada == 3
    assert result.quantidade_disponivel == 12
    repository.update.assert_awaited_once_with(stock)


async def test_decrease_removes_only_available_stock() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    stock = make_stock(quantity=10, reserved=3)
    repository.get_by_product_id_for_update.return_value = stock
    repository.update.return_value = stock

    result = await service.decrease(stock.produto_id, 4)

    assert result.quantidade == 6
    assert result.quantidade_reservada == 3
    assert result.quantidade_disponivel == 3


async def test_decrease_rejects_quantity_above_available_stock() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    stock = make_stock(quantity=10, reserved=7)
    repository.get_by_product_id_for_update.return_value = stock

    with pytest.raises(ConflictException) as exc_info:
        await service.decrease(stock.produto_id, 4)

    assert exc_info.value.code == "INSUFFICIENT_STOCK"
    assert exc_info.value.details == {
        "quantidade_solicitada": 4,
        "quantidade_disponivel": 3,
    }
    repository.update.assert_not_awaited()


async def test_ensure_available_returns_stock_when_quantity_is_sufficient() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    stock = make_stock(quantity=10, reserved=4)
    repository.get_by_product_id.return_value = stock

    result = await service.ensure_available(stock.produto_id, 6)

    assert result is stock


async def test_reserve_increases_reserved_quantity() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    stock = make_stock(quantity=10, reserved=2)
    repository.get_by_product_id_for_update.return_value = stock
    repository.update.return_value = stock

    result = await service.reserve(stock.produto_id, 3)

    assert result.quantidade == 10
    assert result.quantidade_reservada == 5
    assert result.quantidade_disponivel == 5


async def test_release_reservation_restores_available_stock() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    stock = make_stock(quantity=10, reserved=5)
    repository.get_by_product_id_for_update.return_value = stock
    repository.update.return_value = stock

    result = await service.release_reservation(stock.produto_id, 2)

    assert result.quantidade == 10
    assert result.quantidade_reservada == 3
    assert result.quantidade_disponivel == 7


async def test_confirm_reservation_decrements_total_and_reserved_stock() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    stock = make_stock(quantity=10, reserved=5)
    repository.get_by_product_id_for_update.return_value = stock
    repository.update.return_value = stock

    result = await service.confirm_reservation(stock.produto_id, 2)

    assert result.quantidade == 8
    assert result.quantidade_reservada == 3
    assert result.quantidade_disponivel == 5


async def test_stock_not_found_returns_standard_error() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    product_id = uuid4()
    repository.get_by_product_id.return_value = None

    with pytest.raises(NotFoundException) as exc_info:
        await service.get_stock(product_id)

    assert exc_info.value.code == "STOCK_NOT_FOUND"
    assert exc_info.value.details == {"product_id": str(product_id)}


async def test_ensure_sellable_accepts_active_product_with_available_stock() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    product = make_product()
    stock = Stock(
        produto_id=product.id,
        quantidade=10,
        quantidade_reservada=2,
    )
    repository.get_by_product_id.return_value = stock

    result = await service.ensure_sellable(product, 8)

    assert result is stock
    assert result.quantidade_disponivel == 8


async def test_ensure_sellable_rejects_inactive_product() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    product = make_product(active=False)

    with pytest.raises(ConflictException) as exc_info:
        await service.ensure_sellable(product, 1)

    assert exc_info.value.code == "PRODUCT_INACTIVE"
    assert exc_info.value.details == {"product_id": str(product.id)}
    repository.get_by_product_id.assert_not_awaited()


async def test_ensure_sellable_treats_missing_stock_as_unavailable() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    product = make_product()
    repository.get_by_product_id.return_value = None

    with pytest.raises(ConflictException) as exc_info:
        await service.ensure_sellable(product, 1)

    assert exc_info.value.code == "INSUFFICIENT_STOCK"
    assert exc_info.value.details == {
        "quantidade_solicitada": 1,
        "quantidade_disponivel": 0,
    }


async def test_ensure_sellable_rejects_zero_stock() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    product = make_product()
    repository.get_by_product_id.return_value = Stock(
        produto_id=product.id,
        quantidade=0,
        quantidade_reservada=0,
    )

    with pytest.raises(ConflictException) as exc_info:
        await service.ensure_sellable(product, 1)

    assert exc_info.value.code == "INSUFFICIENT_STOCK"


async def test_ensure_sellable_considers_reserved_quantity() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    product = make_product()
    repository.get_by_product_id.return_value = Stock(
        produto_id=product.id,
        quantidade=10,
        quantidade_reservada=8,
    )

    with pytest.raises(ConflictException) as exc_info:
        await service.ensure_sellable(product, 3)

    assert exc_info.value.code == "INSUFFICIENT_STOCK"
    assert exc_info.value.details == {
        "quantidade_solicitada": 3,
        "quantidade_disponivel": 2,
    }


async def test_reserve_for_sale_uses_lock_and_reserves_stock() -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)
    product = make_product()
    stock = Stock(
        produto_id=product.id,
        quantidade=10,
        quantidade_reservada=2,
    )
    repository.get_by_product_id_for_update.return_value = stock
    repository.update.return_value = stock

    result = await service.reserve_for_sale(product, 3)

    assert result.quantidade == 10
    assert result.quantidade_reservada == 5
    assert result.quantidade_disponivel == 5
    repository.get_by_product_id_for_update.assert_awaited_once_with(product.id)
    repository.update.assert_awaited_once_with(stock)


@pytest.mark.parametrize("quantity", [0, -1])
async def test_stock_operations_reject_non_positive_quantity(quantity: int) -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)

    with pytest.raises(BusinessRuleException) as exc_info:
        await service.increase(uuid4(), quantity)

    assert exc_info.value.code == "INVALID_STOCK_QUANTITY"
    repository.get_by_product_id_for_update.assert_not_awaited()
