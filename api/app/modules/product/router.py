from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session

from .mapper import ProductMapper
from .repository import ProductRepository
from .schemas import ProductCreate, ProductOut
from .service import ProductService

router = APIRouter(tags=["products"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/admin/products",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    data: ProductCreate,
    session: SessionDep,
) -> ProductOut:
    repository = ProductRepository(session)
    service = ProductService(repository)

    product = ProductMapper.to_entity(data)
    created_product = await service.create_product(product)

    await session.commit()
    await session.refresh(created_product)

    return ProductMapper.to_output(created_product)
