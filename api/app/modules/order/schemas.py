from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from .enums import OrderStatus


class AddressSnapshotOut(BaseModel):
    cep: str
    rua: str
    numero: str
    complemento: str | None
    bairro: str
    cidade: str
    estado: str


class OrderItemOut(BaseModel):
    id: UUID
    produto_id: UUID
    nome_produto_snapshot: str
    sku_snapshot: str
    quantidade: int
    preco_unitario_snapshot: Decimal
    preco_total: Decimal


class OrderOut(BaseModel):
    id: UUID
    usuario_id: UUID
    status: OrderStatus
    valor_produtos: Decimal
    valor_frete: Decimal
    valor_total: Decimal
    endereco_snapshot: AddressSnapshotOut
    itens: list[OrderItemOut]
    criado_em: datetime
    atualizado_em: datetime
