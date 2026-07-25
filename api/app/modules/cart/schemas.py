from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from .enums import CartStatus


class CartItemCreate(BaseModel):
    produto_id: UUID
    quantidade: int = Field(gt=0)


class CartItemUpdate(BaseModel):
    quantidade: int = Field(gt=0)


class CartItemOut(BaseModel):
    id: UUID
    produto_id: UUID
    quantidade: int
    preco_unitario_atual: Decimal
    subtotal: Decimal


class CartOut(BaseModel):
    id: UUID
    usuario_id: UUID
    status: CartStatus
    itens: list[CartItemOut]
    total_estimado: Decimal
    criado_em: datetime
    atualizado_em: datetime
