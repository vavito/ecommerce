from uuid import UUID

from app.modules.product.models import Product
from app.modules.product.service import ProductService
from app.modules.stock.service import StockService
from app.shared.exceptions import BusinessRuleException, NotFoundException

from .enums import CartStatus
from .models import Cart, CartItem
from .repository import CartRepository


class CartService:
    def __init__(
        self,
        repository: CartRepository,
        product_service: ProductService,
        stock_service: StockService,
    ) -> None:
        self.repository = repository
        self.product_service = product_service
        self.stock_service = stock_service

    @staticmethod
    def _validate_quantity(quantity: int) -> None:
        if quantity <= 0:
            raise BusinessRuleException(
                code="INVALID_CART_ITEM_QUANTITY",
                message="Quantidade deve ser maior que zero.",
                details={"quantidade": quantity},
            )

    @staticmethod
    def _raise_item_not_found(item_id: UUID) -> None:
        raise NotFoundException(
            code="CART_ITEM_NOT_FOUND",
            message="Item do carrinho nao encontrado.",
            details={"item_id": str(item_id)},
        )

    async def get_or_create_open_cart(self, user_id: UUID) -> Cart:
        cart = await self.repository.get_open_by_user_id(user_id)

        if cart is not None:
            return cart

        return await self.repository.add(
            Cart(
                usuario_id=user_id,
                status=CartStatus.OPEN,
                itens=[],
            )
        )

    async def _get_owned_item(self, user_id: UUID, item_id: UUID) -> CartItem:
        cart = await self.repository.get_open_by_user_id(user_id)
        item = await self.repository.get_item_by_id(item_id)

        if cart is None or item is None or item.carrinho_id != cart.id:
            self._raise_item_not_found(item_id)

        return item

    async def _get_sellable_product(
        self,
        product_id: UUID,
        quantity: int,
    ) -> Product:
        product = await self.product_service.get_product(product_id)
        await self.stock_service.ensure_sellable(product, quantity)
        return product

    async def add_item(
        self,
        user_id: UUID,
        product_id: UUID,
        quantity: int,
    ) -> CartItem:
        self._validate_quantity(quantity)
        cart = await self.get_or_create_open_cart(user_id)
        existing_item = await self.repository.get_item_by_product_id(
            cart.id,
            product_id,
        )
        total_quantity = quantity

        if existing_item is not None:
            total_quantity += existing_item.quantidade

        product = await self._get_sellable_product(product_id, total_quantity)

        if existing_item is not None:
            existing_item.quantidade = total_quantity
            existing_item.preco_unitario_atual = product.preco
            return await self.repository.update_item(existing_item)

        return await self.repository.add_item(
            CartItem(
                carrinho_id=cart.id,
                produto_id=product.id,
                quantidade=quantity,
                preco_unitario_atual=product.preco,
            )
        )

    async def update_item_quantity(
        self,
        user_id: UUID,
        item_id: UUID,
        quantity: int,
    ) -> CartItem:
        self._validate_quantity(quantity)
        item = await self._get_owned_item(user_id, item_id)
        product = await self._get_sellable_product(item.produto_id, quantity)

        item.quantidade = quantity
        item.preco_unitario_atual = product.preco
        return await self.repository.update_item(item)

    async def remove_item(self, user_id: UUID, item_id: UUID) -> None:
        item = await self._get_owned_item(user_id, item_id)
        await self.repository.delete_item(item)
