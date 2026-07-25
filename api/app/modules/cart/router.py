from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.product.repository import ProductRepository
from app.modules.product.service import ProductService
from app.modules.stock.repository import StockRepository
from app.modules.stock.service import StockService
from app.modules.user.models import User

from .mapper import CartMapper
from .repository import CartRepository
from .schemas import CartItemCreate, CartItemOut, CartItemUpdate, CartOut
from .service import CartService

router = APIRouter(tags=["cart"])

CurrentUser = Annotated[User, Depends(get_current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _build_cart_service(session: AsyncSession) -> CartService:
    return CartService(
        CartRepository(session),
        ProductService(ProductRepository(session)),
        StockService(StockRepository(session)),
    )


@router.get(
    "/cart",
    response_model=CartOut,
)
async def get_cart(
    current_user: CurrentUser,
    session: SessionDep,
) -> CartOut:
    service = _build_cart_service(session)
    cart = await service.get_or_create_open_cart(current_user.id)

    await session.commit()

    return CartMapper.to_output(cart)


@router.post(
    "/cart/items",
    response_model=CartItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_cart_item(
    data: CartItemCreate,
    current_user: CurrentUser,
    session: SessionDep,
) -> CartItemOut:
    service = _build_cart_service(session)
    item = await service.add_item(
        current_user.id,
        data.produto_id,
        data.quantidade,
    )

    await session.commit()
    await session.refresh(item)

    return CartMapper.item_to_output(item)


@router.patch(
    "/cart/items/{item_id}",
    response_model=CartItemOut,
)
async def update_cart_item(
    item_id: UUID,
    data: CartItemUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> CartItemOut:
    service = _build_cart_service(session)
    item = await service.update_item_quantity(
        current_user.id,
        item_id,
        data.quantidade,
    )

    await session.commit()
    await session.refresh(item)

    return CartMapper.item_to_output(item)
