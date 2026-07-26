"""add positions.notes; extend audit_log for LOT_UPDATED/POSITION_UPDATED

`notes` is documented on CreatePositionRequest/UpdatePositionRequest in
03-openapi-specification.md but was missing from the physical schema's
`positions` table (§3.6) — BE-2.1 accepted it but silently dropped it since
there was nowhere to store it. Added here, alongside the audit_log CHECK
constraint updates BE-2.3 needs for editing.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-26

"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# Kept in sync with app.admin.models.AUDIT_LOG_ACTIONS / AUDIT_LOG_ENTITY_TYPES.
_OLD_ACTIONS = "('USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED', 'LOT_CREATED')"
_NEW_ACTIONS = (
    "('USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED', 'LOT_CREATED', 'LOT_UPDATED', 'POSITION_UPDATED')"
)
_OLD_ENTITY_TYPES = "('User', 'Lot')"
_NEW_ENTITY_TYPES = "('User', 'Lot', 'Position')"


def upgrade() -> None:
    op.execute("ALTER TABLE positions ADD COLUMN notes TEXT")

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

    op.execute("ALTER TABLE positions DROP COLUMN notes")
