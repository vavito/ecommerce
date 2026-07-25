from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .enums import CartStatus
from .models import Cart, CartItem


class CartRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_open_by_user_id(self, user_id: UUID) -> Cart | None:
        statement = (
            select(Cart)
            .options(selectinload(Cart.itens))
            .where(
                Cart.usuario_id == user_id,
                Cart.status == CartStatus.OPEN,
            )
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_item_by_id(self, item_id: UUID) -> CartItem | None:
        statement = select(CartItem).where(CartItem.id == item_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_item_by_product_id(
        self,
        cart_id: UUID,
        product_id: UUID,
    ) -> CartItem | None:
        statement = select(CartItem).where(
            CartItem.carrinho_id == cart_id,
            CartItem.produto_id == product_id,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def add(self, cart: Cart) -> Cart:
        self.session.add(cart)
        await self.session.flush()
        return cart

    async def add_item(self, item: CartItem) -> CartItem:
        self.session.add(item)
        await self.session.flush()
        return item

    async def update_item(self, item: CartItem) -> CartItem:
        await self.session.flush()
        return item

    async def delete_item(self, item: CartItem) -> None:
        await self.session.delete(item)
        await self.session.flush()
