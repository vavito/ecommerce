from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel

from .enums import PaymentMethod, PaymentStatus

if TYPE_CHECKING:
    from app.modules.order.models import Order


def _get_order_model() -> type["Order"]:
    from app.modules.order.models import Order

    return Order


class Payment(BaseModel):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "valor > 0",
            name="ck_payments_valor_positive",
        ),
    )

    pedido_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        unique=True,
        index=True,
    )
    metodo: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"),
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"),
        default=PaymentStatus.PENDING,
        server_default=PaymentStatus.PENDING.value,
    )
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    gateway: Mapped[str] = mapped_column(
        String(50),
        default="MOCK",
        server_default="MOCK",
    )
    gateway_transaction_id: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
    )

    pedido: Mapped["Order"] = relationship(
        _get_order_model,
        back_populates="pagamento",
    )
