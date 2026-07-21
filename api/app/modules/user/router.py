from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth.dependencies import get_current_user

from .mapper import AddressMapper, UserMapper
from .models import User
from .repository import UserRepository
from .schemas import AddressCreate, AddressOut, UserOut
from .service import UserService

router = APIRouter(
    prefix="/users",
    tags=["users"],
)

CurrentUser = Annotated[User, Depends(get_current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/me",
    response_model=UserOut,
)
async def get_me(current_user: CurrentUser) -> UserOut:
    return UserMapper.to_output(current_user)


@router.post(
    "/me/addresses",
    response_model=AddressOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_address(
    data: AddressCreate,
    current_user: CurrentUser,
    session: SessionDep,
) -> AddressOut:
    repository = UserRepository(session)
    service = UserService(repository)

    address = AddressMapper.to_entity(data)
    created_address = await service.create_address(current_user, address)

    await session.commit()
    await session.refresh(created_address)

    return AddressMapper.to_output(created_address)
