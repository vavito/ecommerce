from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import decode_access_token
from app.modules.user.models import User
from app.modules.user.repository import UserRepository
from app.shared.enums import UserRole
from app.shared.exceptions import ForbiddenException, UnauthorizedException

bearer_scheme = HTTPBearer(auto_error=False)

BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme),
]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _invalid_token_exception() -> UnauthorizedException:
    return UnauthorizedException(
        code="INVALID_TOKEN",
        message="Token de autenticacao invalido.",
    )


async def get_current_user(
    credentials: BearerCredentials,
    session: SessionDep,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedException(
            code="AUTHENTICATION_REQUIRED",
            message="Token de autenticacao nao informado.",
        )

    try:
        subject = decode_access_token(credentials.credentials)
        user_id = UUID(subject)
    except (InvalidTokenError, ValueError):
        raise _invalid_token_exception() from None

    repository = UserRepository(session)
    user = await repository.get_by_id(user_id)

    if user is None:
        raise _invalid_token_exception()

    if not user.ativo:
        raise ForbiddenException(
            code="INACTIVE_USER",
            message="Usuario inativo.",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(current_user: CurrentUser) -> User:
    if current_user.role is not UserRole.ADMIN:
        raise ForbiddenException(
            code="FORBIDDEN",
            message="Acesso permitido apenas para administradores.",
        )

    return current_user


AdminUser = Annotated[User, Depends(require_admin)]
