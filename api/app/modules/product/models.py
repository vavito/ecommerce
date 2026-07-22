from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    Text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel


class Category(BaseModel):
    __tablename__ = "categories"

    nome: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
    )

    produtos: Mapped[list["Product"]] = relationship(
        back_populates="categoria",
        passive_deletes=True,
    )


class Product(BaseModel):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "preco > 0",
            name="ck_products_preco_positive",
        ),
    )

    categoria_id: Mapped[UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        index=True,
    )
    nome: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    descricao: Mapped[str | None] = mapped_column(Text)
    sku: Mapped[str] = mapped_column(String(50), unique=True)
    preco: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    ativo: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
    )

    categoria: Mapped["Category"] = relationship(
        back_populates="produtos",
    )
