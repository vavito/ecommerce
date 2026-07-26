from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .enums import PaymentMethod, PaymentStatus


class PaymentWebhookRequest(BaseModel):
    payment_id: UUID
    status: PaymentStatus
    gateway_transaction_id: str = Field(min_length=1, max_length=100)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pedido_id: UUID
    metodo: PaymentMethod
    status: PaymentStatus
    valor: Decimal
    gateway: str
    gateway_transaction_id: str | None
    criado_em: datetime
    atualizado_em: datetime
