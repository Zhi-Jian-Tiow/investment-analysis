"""extend audit_log for POSITION_DELETED

BE-2.4 needs a POSITION_DELETED audit action for the cascading soft-delete
endpoint.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-26

"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# Kept in sync with app.admin.models.AUDIT_LOG_ACTIONS.
_OLD_ACTIONS = (
    "('USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED', 'LOT_CREATED', 'LOT_UPDATED', 'POSITION_UPDATED')"
)
_NEW_ACTIONS = (
    "('USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED', 'LOT_CREATED', 'LOT_UPDATED', "
    "'POSITION_UPDATED', 'POSITION_DELETED')"
)


def upgrade() -> None:
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT audit_log_action_check")
    op.execute(f"ALTER TABLE audit_log ADD CONSTRAINT audit_log_action_check CHECK (action IN {_NEW_ACTIONS})")


def downgrade() -> None:
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT audit_log_action_check")
    op.execute(f"ALTER TABLE audit_log ADD CONSTRAINT audit_log_action_check CHECK (action IN {_OLD_ACTIONS})")
