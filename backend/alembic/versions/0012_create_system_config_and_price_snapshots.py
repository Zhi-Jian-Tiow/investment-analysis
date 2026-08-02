"""create system_config and price_snapshots; seed price refresh config

Corresponds to the system_config portion of BursaTrack-DB-Stage3-Physical-Schema.md
§3.11 ("Migration 004 — Admin Tables") and the price_snapshots portion of §3.10
("Migration 003 — Pricing Table", pulled forward here since BE-5.1 needs it, not
just the reference-data half of that migration).

Pulled forward from Epic 9 (DEP-9.4) for BE-5.1 — the price refresh cron needs
somewhere to store the Bursa holiday calendar, the price deviation threshold, and
its process lock. Only BE-5.1's own needs are seeded here; BE-8.3's admin
PATCH-config endpoint and the rest of DEP-9.4's seed data (system brokers already
exist via 0004; stocks reference table remains deferred) are still out of scope.

price_snapshots.stock_code has no FK to a `stocks` reference table, matching the
same, already-established deviation on positions.stock_code (BE-2.1) — that table
doesn't exist yet either.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-02

"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE system_config (
            key         TEXT        PRIMARY KEY,
            value       TEXT,
            description TEXT,
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        -- No FK to stocks(code) — see this migration's own docstring.
        CREATE TABLE price_snapshots (
            id                   UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
            stock_code           TEXT          NOT NULL,
            price                NUMERIC(12,4) NOT NULL
                CONSTRAINT price_snapshots_price_positive CHECK (price > 0),
            source               TEXT          NOT NULL
                CONSTRAINT price_snapshots_source_check
                    CHECK (source IN ('automated', 'manual', 'stale')),
            trading_date         DATE          NOT NULL,
            last_refreshed_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
            created_by_user_id   UUID          REFERENCES users(id) ON DELETE RESTRICT,
            created_at           TIMESTAMPTZ   NOT NULL DEFAULT now(),
            CONSTRAINT price_snapshots_unique_per_day UNIQUE (stock_code, trading_date)
        )
        """
    )
    # architecture §8.3: price_snapshots(stock_code, trading_date) — already
    # covered by the UNIQUE constraint's own index above (same columns, same
    # order), so no separate CREATE INDEX is needed.

    op.execute(
        """
        INSERT INTO system_config (key, value, description) VALUES
            ('price_deviation_max_pct', '75',
             'BE-5.1/MED-R-006: max allowed percent price move between consecutive snapshots before a fetched price is rejected as a probable data error rather than a real corporate-action move.'),
            ('bursa_holidays', '[]',
             'BE-5.1/MED-R-004: JSON array of ISO date strings (Bursa Malaysia non-trading days). Seeded empty — fixed-date holidays are easy to get wrong and moveable ones (Hari Raya, CNY, Deepavali, Wesak) cannot be predicted without a verified official calendar. An admin must populate this before the first scheduled run of each calendar year; the refresh job logs a WARNING if it finds no entries for the current year.'),
            ('price_refresh_lock', NULL,
             'BE-5.1/HIGH-R-004: ISO timestamp of the currently in-progress refresh run, or NULL if no run is active.')
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE price_snapshots")
    op.execute("DROP TABLE system_config")
