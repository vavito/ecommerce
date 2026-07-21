from app.core.security import create_access_token, verify_password
from app.modules.user.repository import UserRepository
from app.shared.exceptions import ForbiddenException, UnauthorizedException


class AuthService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def login(self, email: str, password: str) -> str:
        normalized_email = email.strip().lower()
        user = await self.repository.get_by_email(normalized_email)

        if user is None or not verify_password(password, user.senha_hash):
            raise UnauthorizedException(
                code="INVALID_CREDENTIALS",
                message="Email ou senha invalidos.",
            )

        if not user.ativo:
            raise ForbiddenException(
                code="INACTIVE_USER",
                message="Usuario inativo.",
            )

        return create_access_token(str(user.id))
