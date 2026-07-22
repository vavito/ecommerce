from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.product.repository import ProductRepository
from app.modules.product.service import ProductService

from .mapper import StockMapper
from .repository import StockRepository
from .schemas import StockCreate, StockOut
from .service import StockService

router = APIRouter(tags=["stock"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/admin/products/{product_id}/stock",
    response_model=StockOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_stock(
    product_id: UUID,
    data: StockCreate,
    session: SessionDep,
) -> StockOut:
    product_service = ProductService(ProductRepository(session))
    stock_service = StockService(StockRepository(session))

    await product_service.get_product(product_id)
    stock = await stock_service.create_initial_stock(product_id, data.quantidade)

    await session.commit()
    await session.refresh(stock)

    return StockMapper.to_output(stock)
