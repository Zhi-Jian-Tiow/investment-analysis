"""create positions and lots; extend audit_log for LOT_CREATED

Corresponds to the positions / lots portion of
BursaTrack-DB-Stage3-Physical-Schema.md §3.6-3.7 ("Migration 003 — Portfolio
Detail Tables" in the design doc's numbering). No FK from positions.stock_code
to a `stocks` reference table yet — that table and its FK are deferred to
Epic 9 (BE-2.1 Dependencies). dividend_tranches (§3.8) is deferred to Epic 3.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-26

"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# Kept in sync with app.admin.models.AUDIT_LOG_ACTIONS / AUDIT_LOG_ENTITY_TYPES.
_OLD_ACTIONS = "('USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED')"
_NEW_ACTIONS = "('USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED', 'LOT_CREATED')"
_OLD_ENTITY_TYPES = "('User')"
_NEW_ENTITY_TYPES = "('User', 'Lot')"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE positions (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            portfolio_id UUID        NOT NULL REFERENCES portfolios(id) ON DELETE RESTRICT,
            stock_code   TEXT        NOT NULL,
            stock_name   TEXT        NOT NULL,
            category_tag TEXT        NOT NULL DEFAULT 'Dividend'
                CONSTRAINT positions_category_tag_check
                    CHECK (category_tag IN ('Dividend', 'Volatile', 'Growth')),
            is_deleted   BOOLEAN     NOT NULL DEFAULT false,
            deleted_at   TIMESTAMPTZ,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE lots (
            id               UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
            position_id      UUID          NOT NULL REFERENCES positions(id) ON DELETE RESTRICT,
            shares           INTEGER       NOT NULL
                CONSTRAINT lots_shares_positive CHECK (shares >= 1),
            purchase_price   NUMERIC(12,4) NOT NULL
                CONSTRAINT lots_purchase_price_positive CHECK (purchase_price > 0),
            initial_amount   NUMERIC(14,2) NOT NULL
                CONSTRAINT lots_initial_amount_positive CHECK (initial_amount > 0),
            brokerage_fee    NUMERIC(14,2) NOT NULL
                CONSTRAINT lots_brokerage_fee_nonneg CHECK (brokerage_fee >= 0),
            clearing_fee     NUMERIC(14,2) NOT NULL
                CONSTRAINT lots_clearing_fee_nonneg CHECK (clearing_fee >= 0),
            stamp_duty       NUMERIC(14,2) NOT NULL
                CONSTRAINT lots_stamp_duty_nonneg CHECK (stamp_duty >= 0),
            all_in_cost      NUMERIC(14,2) NOT NULL
                CONSTRAINT lots_all_in_cost_positive CHECK (all_in_cost > 0),
            purchase_date    DATE          NOT NULL,
            broker_config_id UUID          NOT NULL REFERENCES broker_configs(id) ON DELETE RESTRICT,
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

    op.execute("DROP TABLE lots")
    op.execute("DROP TABLE positions")
