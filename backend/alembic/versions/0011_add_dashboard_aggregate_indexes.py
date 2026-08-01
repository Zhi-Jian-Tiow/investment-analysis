"""add dashboard aggregate indexes on lots and dividend_tranches

Architecture Solution Architecture §8.3 "Key indexes required": BE-4.1's
dashboard endpoint fans out per-position lot/tranche reads across up to 50
positions; without these, every one of those reads is a sequential scan.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-01

"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_lots_position_id_is_deleted ON lots (position_id, is_deleted)"
    )
    op.execute(
        "CREATE INDEX ix_dividend_tranches_position_id_year_is_deleted "
        "ON dividend_tranches (position_id, year, is_deleted)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_dividend_tranches_position_id_year_is_deleted")
    op.execute("DROP INDEX ix_lots_position_id_is_deleted")
