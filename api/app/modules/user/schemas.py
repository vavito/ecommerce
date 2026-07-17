from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.shared.enums import UserRole


class UserCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    email: EmailStr = Field(max_length=255)
    cpf: str = Field(pattern=r"^\d{11}$")
    senha: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    email: EmailStr
    role: UserRole
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime


class AddressCreate(BaseModel):
    cep: str = Field(pattern=r"^\d{8}$")
    rua: str = Field(min_length=2, max_length=200)
    numero: str = Field(min_length=1, max_length=20)
    complemento: str | None = Field(default=None, max_length=150)
    bairro: str = Field(min_length=2, max_length=100)
    cidade: str = Field(min_length=2, max_length=100)
    estado: str = Field(pattern=r"^[A-Za-z]{2}$")
    principal: bool = Field(default=False)


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    cep: str
    rua: str
    numero: str
    complemento: str | None
    bairro: str
    cidade: str
    estado: str
    principal: bool
    criado_em: datetime
    atualizado_em: datetime
