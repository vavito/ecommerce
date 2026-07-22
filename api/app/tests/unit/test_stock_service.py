from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

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


@pytest.mark.parametrize("quantity", [0, -1])
async def test_stock_operations_reject_non_positive_quantity(quantity: int) -> None:
    repository = AsyncMock(spec=StockRepository)
    service = StockService(repository)

    with pytest.raises(BusinessRuleException) as exc_info:
        await service.increase(uuid4(), quantity)

    assert exc_info.value.code == "INVALID_STOCK_QUANTITY"
    repository.get_by_product_id_for_update.assert_not_awaited()
