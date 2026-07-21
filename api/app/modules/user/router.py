from typing import Annotated

from fastapi import APIRouter, Depends

from app.modules.auth.dependencies import get_current_user

from .mapper import UserMapper
from .models import User
from .schemas import UserOut

router = APIRouter(
    prefix="/users",
    tags=["users"],
)

CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get(
    "/me",
    response_model=UserOut,
)
async def get_me(current_user: CurrentUser) -> UserOut:
    return UserMapper.to_output(current_user)
