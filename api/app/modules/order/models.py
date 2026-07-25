from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.product.models import Product
from app.modules.user.models import User
from app.shared.base_model import BaseModel

from .enums import OrderStatus

if TYPE_CHECKING:
    from app.modules.payment.models import Payment


class Order(BaseModel):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "valor_produtos > 0",
            name="ck_orders_valor_produtos_positive",
        ),
        CheckConstraint(
            "valor_frete >= 0",
            name="ck_orders_valor_frete_non_negative",
        ),
        CheckConstraint(
            "valor_total > 0",
            name="ck_orders_valor_total_positive",
        ),
        CheckConstraint(
            "valor_total = valor_produtos + valor_frete",
            name="ck_orders_valor_total_consistent",
        ),
    )

    usuario_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"),
        default=OrderStatus.PENDING_PAYMENT,
        server_default=OrderStatus.PENDING_PAYMENT.value,
    )
    valor_produtos: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valor_frete: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        server_default="0",
    )
    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    endereco_snapshot: Mapped[dict[str, object]] = mapped_column(JSON)

    usuario: Mapped[User] = relationship()
    itens: Mapped[list["OrderItem"]] = relationship(
        back_populates="pedido",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    pagamento: Mapped["Payment"] = relationship(
        back_populates="pedido",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )


class OrderItem(BaseModel):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint(
            "quantidade > 0",
            name="ck_order_items_quantidade_positive",
        ),
        CheckConstraint(
            "preco_unitario_snapshot > 0",
            name="ck_order_items_preco_unitario_snapshot_positive",
        ),
        CheckConstraint(
            "preco_total > 0",
            name="ck_order_items_preco_total_positive",
        ),
        CheckConstraint(
            "preco_total = preco_unitario_snapshot * quantidade",
            name="ck_order_items_preco_total_consistent",
        ),
    )

    pedido_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        index=True,
    )
    produto_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        index=True,
    )
    nome_produto_snapshot: Mapped[str] = mapped_column(String(200))
    sku_snapshot: Mapped[str] = mapped_column(String(50))
    quantidade: Mapped[int] = mapped_column(Integer)
    preco_unitario_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    preco_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    pedido: Mapped[Order] = relationship(
        back_populates="itens",
    )
    produto: Mapped[Product] = relationship()
