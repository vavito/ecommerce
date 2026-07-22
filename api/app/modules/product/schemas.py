from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    categoria_id: UUID
    nome: str = Field(min_length=2, max_length=200)
    descricao: str | None = Field(default=None, max_length=2000)
    sku: str = Field(min_length=1, max_length=50)
    preco: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class ProductUpdate(BaseModel):
    categoria_id: UUID | None = None
    nome: str | None = Field(default=None, min_length=2, max_length=200)
    descricao: str | None = Field(default=None, max_length=2000)
    sku: str | None = Field(default=None, min_length=1, max_length=50)
    preco: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=10,
        decimal_places=2,
    )
    ativo: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    slug: str
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    categoria_id: UUID
    nome: str
    descricao: str | None
    sku: str
    preco: Decimal
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime


class ProductListOut(BaseModel):
    items: list[ProductOut]
    total: int
    offset: int
    limit: int
