"""extend audit_log for PRICE_OVERRIDE_CREATED / PriceSnapshot

BE-5.2: Price Outage Handling & Manual Override.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-02

"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

# Kept in sync with app.admin.models.AUDIT_LOG_ACTIONS / AUDIT_LOG_ENTITY_TYPES.
_OLD_ACTIONS = (
    "('USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED', 'LOT_CREATED', 'LOT_UPDATED', 'LOT_DELETED', "
    "'POSITION_UPDATED', 'POSITION_DELETED', 'DIVIDEND_CREATED', 'DIVIDEND_UPDATED', 'DIVIDEND_DELETED')"
)
_NEW_ACTIONS = (
    "('USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED', 'LOT_CREATED', 'LOT_UPDATED', 'LOT_DELETED', "
    "'POSITION_UPDATED', 'POSITION_DELETED', 'DIVIDEND_CREATED', 'DIVIDEND_UPDATED', 'DIVIDEND_DELETED', "
    "'PRICE_OVERRIDE_CREATED')"
)
_OLD_ENTITY_TYPES = "('User', 'Lot', 'Position', 'DividendTranche')"
_NEW_ENTITY_TYPES = "('User', 'Lot', 'Position', 'DividendTranche', 'PriceSnapshot')"


def upgrade() -> None:
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT audit_log_action_check")
    op.execute(f"ALTER TABLE audit_log ADD CONSTRAINT audit_log_action_check CHECK (action IN {_NEW_ACTIONS})")
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT audit_log_entity_type_check")
    op.execute(
        f"ALTER TABLE audit_log ADD CONSTRAINT audit_log_entity_type_check CHECK (entity_type IN {_NEW_ENTITY_TYPES})"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT audit_log_entity_type_check")
    op.execute(
        f"ALTER TABLE audit_log ADD CONSTRAINT audit_log_entity_type_check CHECK (entity_type IN {_OLD_ENTITY_TYPES})"
    )
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT audit_log_action_check")
    op.execute(f"ALTER TABLE audit_log ADD CONSTRAINT audit_log_action_check CHECK (action IN {_OLD_ACTIONS})")
