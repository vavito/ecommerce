from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import hash_password
from app.modules.auth.schemas import LoginRequest, TokenResponse
from app.modules.auth.service import AuthService
from app.modules.user.mapper import UserMapper
from app.modules.user.repository import UserRepository
from app.modules.user.schemas import UserCreate, UserOut
from app.modules.user.service import UserService

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    data: UserCreate,
    session: SessionDep,
) -> UserOut:
    repository = UserRepository(session)
    service = UserService(repository)

    hashed_password = hash_password(data.senha)
    user = UserMapper.to_entity(data, hashed_password)

    created_user = await service.create_user(user)

    await session.commit()
    await session.refresh(created_user)

    return UserMapper.to_output(created_user)


@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    data: LoginRequest,
    session: SessionDep,
) -> TokenResponse:
    repository = UserRepository(session)
    service = AuthService(repository)

    access_token = await service.login(str(data.email), data.senha)

    return TokenResponse(
        access_token=access_token,
    )
