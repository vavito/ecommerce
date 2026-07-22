from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    produto_id: UUID
    quantidade: int
    quantidade_reservada: int
    quantidade_disponivel: int
    criado_em: datetime
    atualizado_em: datetime
