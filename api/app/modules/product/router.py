from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session

from .mapper import ProductMapper
from .repository import ProductRepository
from .schemas import ProductCreate, ProductOut, ProductUpdate
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


@router.patch(
    "/admin/products/{product_id}",
    response_model=ProductOut,
)
async def update_product(
    product_id: UUID,
    data: ProductUpdate,
    session: SessionDep,
) -> ProductOut:
    repository = ProductRepository(session)
    service = ProductService(repository)

    updated_product = await service.update_product(product_id, data)

    await session.commit()
    await session.refresh(updated_product)

    return ProductMapper.to_output(updated_product)
