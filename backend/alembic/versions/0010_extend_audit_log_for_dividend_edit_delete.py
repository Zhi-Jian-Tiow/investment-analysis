"""extend audit_log for DIVIDEND_UPDATED/DIVIDEND_DELETED

BE-3.2: Edit / Delete Dividend Tranche.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-01

"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

# Kept in sync with app.admin.models.AUDIT_LOG_ACTIONS.
_OLD_ACTIONS = (
    "('USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED', 'LOT_CREATED', 'LOT_UPDATED', 'LOT_DELETED', "
    "'POSITION_UPDATED', 'POSITION_DELETED', 'DIVIDEND_CREATED')"
)
_NEW_ACTIONS = (
    "('USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED', 'LOT_CREATED', 'LOT_UPDATED', 'LOT_DELETED', "
    "'POSITION_UPDATED', 'POSITION_DELETED', 'DIVIDEND_CREATED', 'DIVIDEND_UPDATED', 'DIVIDEND_DELETED')"
)


def upgrade() -> None:
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT audit_log_action_check")
    op.execute(f"ALTER TABLE audit_log ADD CONSTRAINT audit_log_action_check CHECK (action IN {_NEW_ACTIONS})")


def downgrade() -> None:
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT audit_log_action_check")
    op.execute(f"ALTER TABLE audit_log ADD CONSTRAINT audit_log_action_check CHECK (action IN {_OLD_ACTIONS})")
