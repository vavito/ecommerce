"""add slug to products

Revision ID: aced18019ff3
Revises: 194bf7a1b12a
Create Date: 2026-07-22 16:09:41.880619

"""

import re
import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aced18019ff3"
down_revision: str | Sequence[str] | None = "194bf7a1b12a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _slugify(value: str) -> str:
    normalized_value = unicodedata.normalize("NFKD", value)
    ascii_value = normalized_value.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "products",
        sa.Column("slug", sa.String(length=220), nullable=True),
    )

    products = sa.table(
        "products",
        sa.column("id", sa.Uuid()),
        sa.column("nome", sa.String()),
        sa.column("slug", sa.String()),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(products.c.id, products.c.nome).order_by(products.c.id)
    ).all()
    used_slugs: set[str] = set()

    for product_id, product_name in rows:
        base_slug = _slugify(product_name) or "produto"
        slug = base_slug[:220]
        suffix = 2

        while slug in used_slugs:
            suffix_text = f"-{suffix}"
            slug = f"{base_slug[: 220 - len(suffix_text)]}{suffix_text}"
            suffix += 1

        connection.execute(
            products.update().where(products.c.id == product_id).values(slug=slug)
        )
        used_slugs.add(slug)

    op.alter_column(
        "products",
        "slug",
        existing_type=sa.String(length=220),
        nullable=False,
    )
    op.create_index(
        op.f("ix_products_slug"),
        "products",
        ["slug"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_products_slug"), table_name="products")
    op.drop_column("products", "slug")
