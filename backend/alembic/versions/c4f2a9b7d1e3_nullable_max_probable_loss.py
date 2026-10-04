"""Make portfolio max_probable_loss_usd nullable.

The portfolio summary does not always carry a realised maximum probable loss
sample; rather than inventing a figure (e.g. a multiple of VaR99) the pipeline
now reports NULL. This migration relaxes the NOT NULL constraint accordingly.

Revision ID: c4f2a9b7d1e3
Revises: 6301fba125fc
Create Date: 2026-10-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4f2a9b7d1e3"
down_revision: Union[str, Sequence[str], None] = "6301fba125fc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("portfolio_risk_results") as batch_op:
        batch_op.alter_column(
            "max_probable_loss_usd",
            existing_type=sa.Float(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("portfolio_risk_results") as batch_op:
        batch_op.alter_column(
            "max_probable_loss_usd",
            existing_type=sa.Float(),
            nullable=False,
            server_default="0",
        )
