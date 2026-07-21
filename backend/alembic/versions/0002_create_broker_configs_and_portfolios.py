"""create broker_configs and portfolios

Corresponds to the broker_configs / portfolios portion of
BursaTrack-DB-Stage3-Physical-Schema.md "Migration 002 — Portfolio Tables".
positions, lots, and dividend_tranches are deferred to Epics 2-3.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-19

"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE broker_configs (
            id                   UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
            name                 TEXT          NOT NULL,
            fee_type             TEXT          NOT NULL
                CONSTRAINT broker_configs_fee_type_check
                    CHECK (fee_type IN ('percentage', 'flat')),
            rate                 NUMERIC(10,6),
            minimum_fee          NUMERIC(14,2),
            flat_fee             NUMERIC(14,2),
            is_system            BOOLEAN       NOT NULL DEFAULT false,
            created_by_user_id   UUID          REFERENCES users(id) ON DELETE RESTRICT,
            created_at           TIMESTAMPTZ   NOT NULL DEFAULT now(),
            updated_at           TIMESTAMPTZ   NOT NULL DEFAULT now(),
            CONSTRAINT broker_configs_percentage_fields_check CHECK (
                (fee_type = 'percentage' AND rate IS NOT NULL AND minimum_fee IS NOT NULL AND flat_fee IS NULL)
                OR (fee_type = 'flat' AND flat_fee IS NOT NULL AND rate IS NULL AND minimum_fee IS NULL)
            ),
            CONSTRAINT broker_configs_system_ownership_check CHECK (
                (is_system = true AND created_by_user_id IS NULL)
                OR (is_system = false AND created_by_user_id IS NOT NULL)
            )
        )
        """
    )

    op.execute(
        "ALTER TABLE users ADD COLUMN default_broker_config_id UUID REFERENCES broker_configs(id) ON DELETE SET NULL"
    )

    op.execute(
        """
        CREATE TABLE portfolios (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT portfolios_user_unique UNIQUE (user_id)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE portfolios")
    op.execute("ALTER TABLE users DROP COLUMN default_broker_config_id")
    op.execute("DROP TABLE broker_configs")
