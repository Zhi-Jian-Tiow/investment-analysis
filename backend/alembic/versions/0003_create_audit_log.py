"""create audit_log

Corresponds to the audit_log portion of BursaTrack-DB-Stage3-Physical-Schema.md
§3.12 ("Migration 004 — Admin Tables" in the design doc's numbering). Pulled
forward here because audit logging starts with the first story, BE-1.1
(USER_REGISTERED). system_config and system_deletion_log are deferred to the
epics that actually need them.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-19

"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Kept in sync with app.admin.models.AUDIT_LOG_ACTIONS / AUDIT_LOG_ENTITY_TYPES —
# only the values Epic 1 BE stories emit so far.
_ACTIONS = "('USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED')"
_ENTITY_TYPES = "('User')"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE audit_log (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id      UUID        REFERENCES users(id) ON DELETE CASCADE,
            action       TEXT        NOT NULL
                CONSTRAINT audit_log_action_check CHECK (action IN {_ACTIONS}),
            entity_type  TEXT
                CONSTRAINT audit_log_entity_type_check CHECK (entity_type IN {_ENTITY_TYPES}),
            entity_id    UUID,
            metadata     JSONB,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE audit_log")
