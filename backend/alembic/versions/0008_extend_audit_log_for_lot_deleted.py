"""extend audit_log for LOT_DELETED

Backfills a Delete Lot endpoint (DELETE /api/v1/portfolio/positions/{id}/lots/{lot_id})
that has been fully documented in 03-openapi-specification.md since the API design
phase (x-audit-event: LOT_DELETED) but was never claimed by any user story in
Epic 2. Implemented now, alongside BE-2.4/FE-2.4, as a small deliberate scope
addition since the position-level delete flow was already being built.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-01

"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# Kept in sync with app.admin.models.AUDIT_LOG_ACTIONS.
_OLD_ACTIONS = (
    "('USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED', 'LOT_CREATED', 'LOT_UPDATED', "
    "'POSITION_UPDATED', 'POSITION_DELETED')"
)
_NEW_ACTIONS = (
    "('USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED', 'LOT_CREATED', 'LOT_UPDATED', 'LOT_DELETED', "
    "'POSITION_UPDATED', 'POSITION_DELETED')"
)


def upgrade() -> None:
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT audit_log_action_check")
    op.execute(f"ALTER TABLE audit_log ADD CONSTRAINT audit_log_action_check CHECK (action IN {_NEW_ACTIONS})")


def downgrade() -> None:
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT audit_log_action_check")
    op.execute(f"ALTER TABLE audit_log ADD CONSTRAINT audit_log_action_check CHECK (action IN {_OLD_ACTIONS})")
