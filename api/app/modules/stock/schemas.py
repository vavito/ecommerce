from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .enums import StockOperation


class StockCreate(BaseModel):
    quantidade: int = Field(ge=0)


class StockAdjust(BaseModel):
    operacao: StockOperation
    quantidade: int = Field(gt=0)


class StockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    produto_id: UUID
    quantidade: int
    quantidade_reservada: int
    quantidade_disponivel: int
    criado_em: datetime
    atualizado_em: datetime
