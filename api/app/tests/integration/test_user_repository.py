from uuid import uuid4

from app.core.database import async_session_maker
from app.modules.user.models import User
from app.modules.user.repository import UserRepository


async def test_user_repository_finds_user_by_email_cpf_and_id() -> None:
    unique_value = uuid4()

    async with async_session_maker() as session:
        try:
            user = User(
                nome="John",
                # geração de email e cpf aleatórios a cada execução
                email=f"john-{unique_value.hex}@example.com",
                cpf=f"{unique_value.int % 100_000_000_000:011d}",
                senha_hash="hash-de-teste",
            )

            session.add(user)
            await session.flush()

            repository = UserRepository(session)

            user_by_email = await repository.get_by_email(user.email)
            user_by_cpf = await repository.get_by_cpf(user.cpf)
            user_by_id = await repository.get_by_id(user.id)

            assert user_by_email is not None
            assert user_by_email.id == user.id

            assert user_by_cpf is not None
            assert user_by_cpf.id == user.id

            assert user_by_id is not None
            assert user_by_id.id == user.id
        finally:
            await session.rollback()
