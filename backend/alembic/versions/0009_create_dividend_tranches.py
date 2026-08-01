"""create dividend_tranches; extend audit_log for DIVIDEND_CREATED

Corresponds to the dividend_tranches portion of
BursaTrack-DB-Stage3-Physical-Schema.md §3.8 ("Migration 003 — Portfolio
Detail Tables" in the design doc's numbering, continued). BE-3.1.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-01

"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

# Kept in sync with app.admin.models.AUDIT_LOG_ACTIONS / AUDIT_LOG_ENTITY_TYPES.
_OLD_ACTIONS = (
    "('USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED', 'LOT_CREATED', 'LOT_UPDATED', 'LOT_DELETED', "
    "'POSITION_UPDATED', 'POSITION_DELETED')"
)
_NEW_ACTIONS = (
    "('USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED', 'LOT_CREATED', 'LOT_UPDATED', 'LOT_DELETED', "
    "'POSITION_UPDATED', 'POSITION_DELETED', 'DIVIDEND_CREATED')"
)
_OLD_ENTITY_TYPES = "('User', 'Lot', 'Position')"
_NEW_ENTITY_TYPES = "('User', 'Lot', 'Position', 'DividendTranche')"


def upgrade() -> None:
    op.execute(
        """
        -- P0 INVARIANT: total_amount is stored at logging time as per_share_amount x qualifying_shares.
        -- It must NEVER be recomputed from the current position share count.
        -- No trigger, generated column, or view may derive or update total_amount from lots.shares.
        -- The only permitted update to total_amount is an explicit user edit of this tranche record.
        CREATE TABLE dividend_tranches (
            id               UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
            position_id      UUID          NOT NULL REFERENCES positions(id) ON DELETE RESTRICT,
            tranche_label    TEXT          NOT NULL
                CONSTRAINT dividend_tranches_label_check
                    CHECK (tranche_label IN ('1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th')),
            per_share_amount NUMERIC(12,6) NOT NULL
                CONSTRAINT dividend_tranches_per_share_positive CHECK (per_share_amount > 0),
            qualifying_shares INTEGER      NOT NULL
                CONSTRAINT dividend_tranches_qualifying_shares_positive CHECK (qualifying_shares >= 1),
            total_amount     NUMERIC(14,2) NOT NULL
                CONSTRAINT dividend_tranches_total_amount_positive CHECK (total_amount > 0),
            year             INTEGER       NOT NULL
                CONSTRAINT dividend_tranches_year_range CHECK (year >= 1990 AND year <= 2100),
            payment_date     DATE          NOT NULL,
            ex_dividend_date DATE,
            version          INTEGER       NOT NULL DEFAULT 1,
            is_deleted       BOOLEAN       NOT NULL DEFAULT false,
            deleted_at       TIMESTAMPTZ,
            created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
        )
        """
    )

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

    op.execute("DROP TABLE dividend_tranches")
