from typing import Annotated

from fastapi import APIRouter, Depends
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
from .schemas import CartOut
from .service import CartService

router = APIRouter(tags=["cart"])

CurrentUser = Annotated[User, Depends(get_current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/cart",
    response_model=CartOut,
)
async def get_cart(
    current_user: CurrentUser,
    session: SessionDep,
) -> CartOut:
    service = CartService(
        CartRepository(session),
        ProductService(ProductRepository(session)),
        StockService(StockRepository(session)),
    )
    cart = await service.get_or_create_open_cart(current_user.id)

    await session.commit()

    return CartMapper.to_output(cart)
