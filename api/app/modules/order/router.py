from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.cart.repository import CartRepository
from app.modules.stock.repository import StockRepository
from app.modules.stock.service import StockService
from app.modules.user.models import User
from app.modules.user.repository import UserRepository

from .mapper import OrderMapper
from .repository import OrderRepository
from .schemas import CheckoutRequest, OrderOut
from .service import OrderService

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
)

CurrentUser = Annotated[User, Depends(get_current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _build_order_service(session: AsyncSession) -> OrderService:
    return OrderService(
        OrderRepository(session),
        CartRepository(session),
        StockService(StockRepository(session)),
        UserRepository(session),
    )


@router.post(
    "/checkout",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
)
async def checkout(
    data: CheckoutRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> OrderOut:
    service = _build_order_service(session)
    order = await service.checkout(
        current_user.id,
        data.endereco_id,
        data.metodo_pagamento,
    )

    await session.commit()

    return OrderMapper.to_output(order)
