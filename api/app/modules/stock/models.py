from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.product.models import Product
from app.shared.base_model import BaseModel


class Stock(BaseModel):
    __tablename__ = "stocks"
    __table_args__ = (
        CheckConstraint(
            "quantidade >= 0",
            name="ck_stocks_quantidade_non_negative",
        ),
    )

    produto_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    quantidade: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
    )

    produto: Mapped[Product] = relationship()
