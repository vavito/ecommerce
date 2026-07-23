from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.product.models import Product
from app.modules.user.models import User
from app.shared.base_model import BaseModel

from .enums import CartStatus


class Cart(BaseModel):
    __tablename__ = "carts"
    __table_args__ = (
        Index(
            "uq_carts_usuario_open",
            "usuario_id",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
        ),
    )

    usuario_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[CartStatus] = mapped_column(
        Enum(CartStatus, name="cart_status"),
        default=CartStatus.OPEN,
        server_default=CartStatus.OPEN.value,
    )

    usuario: Mapped[User] = relationship()
    itens: Mapped[list["CartItem"]] = relationship(
        back_populates="carrinho",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CartItem(BaseModel):
    __tablename__ = "cart_items"
    __table_args__ = (
        CheckConstraint(
            "quantidade > 0",
            name="ck_cart_items_quantidade_positive",
        ),
        CheckConstraint(
            "preco_unitario_atual > 0",
            name="ck_cart_items_preco_unitario_atual_positive",
        ),
        UniqueConstraint(
            "carrinho_id",
            "produto_id",
            name="uq_cart_items_carrinho_produto",
        ),
    )

    carrinho_id: Mapped[UUID] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"),
        index=True,
    )
    produto_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        index=True,
    )
    quantidade: Mapped[int] = mapped_column(Integer)
    preco_unitario_atual: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    carrinho: Mapped[Cart] = relationship(
        back_populates="itens",
    )
    produto: Mapped[Product] = relationship()
