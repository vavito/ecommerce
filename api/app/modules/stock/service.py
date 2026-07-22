from uuid import UUID

from app.shared.exceptions import (
    BusinessRuleException,
    ConflictException,
    NotFoundException,
)

from .models import Stock
from .repository import StockRepository


class StockService:
    def __init__(self, repository: StockRepository) -> None:
        self.repository = repository

    @staticmethod
    def _validate_positive_quantity(quantity: int) -> None:
        if quantity <= 0:
            raise BusinessRuleException(
                code="INVALID_STOCK_QUANTITY",
                message="Quantidade deve ser maior que zero.",
                details={"quantidade": quantity},
            )

    @staticmethod
    def _raise_stock_not_found(product_id: UUID) -> None:
        raise NotFoundException(
            code="STOCK_NOT_FOUND",
            message="Estoque nao encontrado.",
            details={"product_id": str(product_id)},
        )

    @staticmethod
    def _ensure_stock_has_availability(stock: Stock, quantity: int) -> None:
        if stock.quantidade_disponivel < quantity:
            raise ConflictException(
                code="INSUFFICIENT_STOCK",
                message="Estoque insuficiente.",
                details={
                    "quantidade_solicitada": quantity,
                    "quantidade_disponivel": stock.quantidade_disponivel,
                },
            )

    @staticmethod
    def _ensure_reservation_exists(stock: Stock, quantity: int) -> None:
        if stock.quantidade_reservada < quantity:
            raise ConflictException(
                code="INVALID_STOCK_RESERVATION",
                message="Quantidade reservada insuficiente.",
                details={
                    "quantidade_solicitada": quantity,
                    "quantidade_reservada": stock.quantidade_reservada,
                },
            )

    async def get_stock(self, product_id: UUID) -> Stock:
        stock = await self.repository.get_by_product_id(product_id)

        if stock is None:
            self._raise_stock_not_found(product_id)

        return stock

    async def _get_stock_for_update(self, product_id: UUID) -> Stock:
        stock = await self.repository.get_by_product_id_for_update(product_id)

        if stock is None:
            self._raise_stock_not_found(product_id)

        return stock

    async def ensure_available(self, product_id: UUID, quantity: int) -> Stock:
        self._validate_positive_quantity(quantity)
        stock = await self.get_stock(product_id)
        self._ensure_stock_has_availability(stock, quantity)
        return stock

    async def increase(self, product_id: UUID, quantity: int) -> Stock:
        self._validate_positive_quantity(quantity)
        stock = await self._get_stock_for_update(product_id)
        stock.quantidade += quantity
        return await self.repository.update(stock)

    async def decrease(self, product_id: UUID, quantity: int) -> Stock:
        self._validate_positive_quantity(quantity)
        stock = await self._get_stock_for_update(product_id)
        self._ensure_stock_has_availability(stock, quantity)
        stock.quantidade -= quantity
        return await self.repository.update(stock)

    async def reserve(self, product_id: UUID, quantity: int) -> Stock:
        self._validate_positive_quantity(quantity)
        stock = await self._get_stock_for_update(product_id)
        self._ensure_stock_has_availability(stock, quantity)
        stock.quantidade_reservada += quantity
        return await self.repository.update(stock)

    async def release_reservation(self, product_id: UUID, quantity: int) -> Stock:
        self._validate_positive_quantity(quantity)
        stock = await self._get_stock_for_update(product_id)
        self._ensure_reservation_exists(stock, quantity)
        stock.quantidade_reservada -= quantity
        return await self.repository.update(stock)

    async def confirm_reservation(self, product_id: UUID, quantity: int) -> Stock:
        self._validate_positive_quantity(quantity)
        stock = await self._get_stock_for_update(product_id)
        self._ensure_reservation_exists(stock, quantity)
        stock.quantidade -= quantity
        stock.quantidade_reservada -= quantity
        return await self.repository.update(stock)
