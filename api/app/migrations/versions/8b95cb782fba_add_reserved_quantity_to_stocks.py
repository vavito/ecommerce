"""add reserved quantity to stocks

Revision ID: 8b95cb782fba
Revises: e7a302f1fdfe
Create Date: 2026-07-22 17:59:21.786306

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b95cb782fba"
down_revision: str | Sequence[str] | None = "e7a302f1fdfe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "stocks",
        sa.Column(
            "quantidade_reservada",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_stocks_quantidade_reservada_non_negative",
        "stocks",
        "quantidade_reservada >= 0",
    )
    op.create_check_constraint(
        "ck_stocks_quantidade_reservada_lte_quantidade",
        "stocks",
        "quantidade_reservada <= quantidade",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_stocks_quantidade_reservada_lte_quantidade",
        "stocks",
        type_="check",
    )
    op.drop_constraint(
        "ck_stocks_quantidade_reservada_non_negative",
        "stocks",
        type_="check",
    )
    op.drop_column("stocks", "quantidade_reservada")
