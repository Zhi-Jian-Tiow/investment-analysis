"""create users and pending_tokens

Corresponds to BursaTrack-DB-Stage3-Physical-Schema.md "Migration 001 — Auth
Tables", minus pending_email_notifications (deferred to Epic 8, not needed
until the PDPA hard-delete notification gate is implemented).

Revision ID: 0001
Revises:
Create Date: 2026-07-19

"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
            id                        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            email                     TEXT         NOT NULL,
            password_hash             TEXT         NOT NULL,
            email_verified            BOOLEAN      NOT NULL DEFAULT false,
            account_status            TEXT         NOT NULL DEFAULT 'trial'
                CONSTRAINT users_account_status_check
                    CHECK (account_status IN ('trial', 'active', 'grace_period', 'trial_expired', 'pending_deletion')),
            token_version             INTEGER      NOT NULL DEFAULT 0,
            stripe_customer_id        TEXT,
            trial_start_date          DATE         NOT NULL,
            trial_expiry_date        DATE         NOT NULL,
            subscription_start_date   DATE,
            subscription_renewal_date DATE,
            deletion_requested_date   DATE,
            permanent_deletion_date   DATE,
            created_at                TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at                TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX users_email_lower_unique ON users(LOWER(email))")

    op.execute(
        """
        CREATE TABLE pending_tokens (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            token_hash   TEXT        NOT NULL,
            type         TEXT        NOT NULL
                CONSTRAINT pending_tokens_type_check
                    CHECK (type IN ('email_verification', 'password_reset', 'deletion_cancellation')),
            user_id      UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at   TIMESTAMPTZ NOT NULL,
            used_at      TIMESTAMPTZ,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT pending_tokens_hash_unique UNIQUE (token_hash),
            CONSTRAINT pending_tokens_user_type_unique UNIQUE (user_id, type)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE pending_tokens")
    op.execute("DROP INDEX users_email_lower_unique")
    op.execute("DROP TABLE users")
