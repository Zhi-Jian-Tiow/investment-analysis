"""seed system broker configs

Corresponds to the broker_configs rows from BursaTrack-DB-Stage3-Physical-Schema.md
"Migration 007 — Seed Reference Data", pulled forward because registration
(BE-1.1) requires at least one BrokerConfig to exist as a selectable default
broker. The system_config seed rows in that same migration 007 are deferred —
the system_config table doesn't exist yet in this trimmed migration set.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-19

"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO broker_configs (id, name, fee_type, rate, minimum_fee, flat_fee, is_system, created_by_user_id)
        VALUES
            (gen_random_uuid(), 'Maybank IB',    'percentage', 0.007000, 8.00,  NULL, true, NULL),
            (gen_random_uuid(), 'CIMB Clicks',   'percentage', 0.007000, 8.00,  NULL, true, NULL),
            (gen_random_uuid(), 'RHB Reflex',    'percentage', 0.007000, 8.00,  NULL, true, NULL),
            (gen_random_uuid(), 'Rakuten Trade', 'percentage', 0.007000, 7.00,  NULL, true, NULL),
            (gen_random_uuid(), 'Mirae Asset',   'percentage', 0.004200, 8.00,  NULL, true, NULL),
            (gen_random_uuid(), 'M+ Online',     'percentage', 0.006000, 8.00,  NULL, true, NULL)
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM broker_configs WHERE is_system = true")
