from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, String, false, true
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel
from app.shared.enums import UserRole


class User(BaseModel):
    __tablename__ = "users"
    nome: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    cpf: Mapped[str] = mapped_column(String(11), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        default=UserRole.CUSTOMER,
        server_default=UserRole.CUSTOMER.value,
    )
    ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
    )

class Address(BaseModel):
    __tablename__ = "addresses"

    usuario_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    cep: Mapped[str] = mapped_column(String(8))
    rua: Mapped[str] = mapped_column(String(200))
    numero: Mapped[str] = mapped_column(String(20))
    complemento: Mapped[str | None] = mapped_column(String(150))
    bairro: Mapped[str] = mapped_column(String(100))
    cidade: Mapped[str] = mapped_column(String(100))
    estado: Mapped[str] = mapped_column(String(2))

    principal: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
    )