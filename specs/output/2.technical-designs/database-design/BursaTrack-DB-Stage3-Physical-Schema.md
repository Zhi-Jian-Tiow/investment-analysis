# BursaTrack — Database Design: Stage 3 Physical Schema Design

**Stage:** 3 of 3 — Physical Schema Design  
**Date:** 2026-06-28  
**Target:** PostgreSQL 16 (Render managed); async SQLAlchemy; Alembic migrations  
**Input documents:** Stage 1 Domain Model Review; Stage 2 Logical Data Modelling Decision Record; Solution Architecture v1.1  
**Output:** Complete DDL + Alembic migration plan (implementation-ready)

---

## 1. Schema Summary

### Tables

**16 tables** across 5 domain modules:

| Module | Tables |
|--------|--------|
| **auth** | `users`, `pending_tokens`, `pending_email_notifications` |
| **portfolio** | `portfolios`, `positions`, `lots`, `dividend_tranches`, `broker_configs` |
| **pricing** | `stocks`, `price_snapshots` |
| **admin** | `system_config`, `audit_log`, `system_deletion_log` |
| **subscription** | `subscription_records`, `processed_webhook_events`, `import_jobs` |

### Key Design Decisions Carried Forward from Stage 2

| Decision | Physical implementation |
|----------|------------------------|
| Circular FK (users ↔ broker_configs) | Resolved via ALTER TABLE in migration 002 |
| Stock FK deferred | positions.stock_code plain TEXT in migration 002; FK added in migration 003 |
| UNIQUE (user_id, type) on pending_tokens | Prevents race condition on token regeneration |
| Partial unique index on dividend_tranches | Enforces BR-014 (max 8 per position per year) by label |
| system_deletion_log | New table (architecture gap resolved in Stage 1) |
| processed_webhook_events.user_id | Added to enable PDPA deletion without JOIN |
| audit_log.user_id ON DELETE CASCADE | Audit records deleted with the user row |
| subscription_records.user_id ON DELETE SET NULL | Anonymised, not deleted, for 7-year retention |

### Exceptions to the UUID Primary Key Rule

Three tables use natural keys, not UUID:

| Table | PK type | Rationale |
|-------|---------|-----------|
| `stocks` | `code TEXT` | Bursa stock code is the authoritative identifier |
| `system_config` | `key TEXT` | Key-value config store; key is the identity |
| `processed_webhook_events` | `event_id TEXT` | Stripe event ID is the idempotency key |

### Migration Deployment Summary

7 migrations, deployed sequentially by Render pre-deploy command (`alembic upgrade head`). All migrations are backwards-compatible (additive only). Seed data in migration 007.

---

## 2. Table Inventory

| Table | Module | Lifecycle |
|-------|--------|-----------|
| `users` | auth | Created at registration; hard-deleted on PDPA (with cascades) |
| `pending_tokens` | auth | Short-lived; CASCADE-deleted on user deletion; cleaned up by nightly cron |
| `pending_email_notifications` | auth | Retry queue; CASCADE-deleted on user deletion |
| `broker_configs` | portfolio | System rows: permanent; Custom rows: deleted after referencing lots are removed |
| `portfolios` | portfolio | Created at registration; explicitly deleted on PDPA (step 8) |
| `positions` | portfolio | Soft-deleteable; explicitly hard-deleted on PDPA (step 7) |
| `lots` | portfolio | Soft-deleteable; explicitly hard-deleted on PDPA (step 6) |
| `dividend_tranches` | portfolio | Soft-deleteable; explicitly hard-deleted on PDPA (step 5) |
| `stocks` | pricing | System-shared; permanent; updated by admin script |
| `price_snapshots` | pricing | Automated records: permanent; Manual records: deleted on PDPA (step 1) |
| `system_config` | admin | System-shared; permanent; updated via admin API |
| `audit_log` | admin | Append-only; CASCADE-deleted on user deletion (step 11) |
| `system_deletion_log` | admin | Append-only; no user PII; permanent |
| `subscription_records` | subscription | Anonymised (user_id → NULL) on PDPA; retained 7 years |
| `processed_webhook_events` | subscription | CASCADE-deleted on user deletion; explicit in PDPA step 3 |
| `import_jobs` | subscription | Explicitly deleted on PDPA (step 2) |

---

## 3. Complete Table Definitions

### 3.1 Table: `users`

```sql
-- Migration 001: Initial users table WITHOUT default_broker_config_id.
-- That column is added in migration 002 after broker_configs exists.
-- [DI-011] email uniqueness enforced via functional index on LOWER(email), not a column constraint,
-- so that case variations ('Aaron@x.com' vs 'aaron@x.com') are treated as duplicates at the DB level.
CREATE TABLE users (
    id                        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    email                     TEXT         NOT NULL,
    password_hash             TEXT         NOT NULL,       -- bcrypt cost factor 12
    email_verified            BOOLEAN      NOT NULL DEFAULT false,
    account_status            TEXT         NOT NULL DEFAULT 'trial'
        CONSTRAINT users_account_status_check
            CHECK (account_status IN ('trial', 'active', 'grace_period', 'trial_expired', 'pending_deletion')),
    token_version             INTEGER      NOT NULL DEFAULT 0,  -- incremented on logout, password change, deletion initiation
    stripe_customer_id        TEXT,                            -- set when user subscribes; used for webhook → user lookup (see Risk 1 / OQ-001)
    trial_start_date          DATE         NOT NULL,
    trial_expiry_date         DATE         NOT NULL,           -- trial_start_date + 14 days, set at registration
    subscription_start_date   DATE,                            -- set on first successful Stripe payment
    subscription_renewal_date DATE,                            -- updated from Stripe current_period_end
    deletion_requested_date   DATE,                            -- set when user initiates PDPA deletion
    permanent_deletion_date   DATE,                            -- deletion_requested_date + 30 days
    created_at                TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Case-insensitive email uniqueness (DI-011: replaces column-level UNIQUE constraint)
CREATE UNIQUE INDEX users_email_lower_unique ON users(LOWER(email));

-- Stripe customer lookup index
CREATE UNIQUE INDEX idx_users_stripe_customer_id_unique ON users(stripe_customer_id)
    WHERE stripe_customer_id IS NOT NULL;

-- Migration 002 addition (after broker_configs exists):
-- ALTER TABLE users
--     ADD COLUMN default_broker_config_id UUID REFERENCES broker_configs(id) ON DELETE SET NULL;
```

---

### 3.2 Table: `pending_tokens`

```sql
CREATE TABLE pending_tokens (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash   TEXT        NOT NULL,       -- SHA-256 of the raw token sent to the user; raw token is discarded
    type         TEXT        NOT NULL
        CONSTRAINT pending_tokens_type_check
            CHECK (type IN ('email_verification', 'password_reset', 'deletion_cancellation')),
    user_id      UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at   TIMESTAMPTZ NOT NULL,       -- 24 hours from creation
    used_at      TIMESTAMPTZ,                -- NULL until first valid use; reuse rejected if not NULL
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pending_tokens_hash_unique UNIQUE (token_hash),
    CONSTRAINT pending_tokens_user_type_unique UNIQUE (user_id, type)  -- one active token per user per type
);
```

---

### 3.3 Table: `pending_email_notifications`

```sql
CREATE TABLE pending_email_notifications (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type             TEXT        NOT NULL,        -- e.g. 'PDPA_DELETION_CONFIRMED', 'EMAIL_VERIFICATION'
    recipient_email  TEXT        NOT NULL,
    attempt_count    INTEGER     NOT NULL DEFAULT 0,
    sent_at          TIMESTAMPTZ,                 -- NULL until successfully delivered; non-NULL = delivery confirmed
    next_retry_at    TIMESTAMPTZ,                 -- NULL = not yet scheduled or no more retries
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()  -- [LC-005b] tracks retry scheduling updates
);
```

---

### 3.4 Table: `broker_configs`

```sql
-- Created in migration 002 before the ALTER TABLE on users.
CREATE TABLE broker_configs (
    id                   UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    name                 TEXT          NOT NULL,
    fee_type             TEXT          NOT NULL
        CONSTRAINT broker_configs_fee_type_check
            CHECK (fee_type IN ('percentage', 'flat')),
    rate                 NUMERIC(10,6),        -- populated for fee_type = 'percentage'; NULL for 'flat'
    minimum_fee          NUMERIC(14,2),        -- populated for fee_type = 'percentage'; NULL for 'flat'
    flat_fee             NUMERIC(14,2),        -- populated for fee_type = 'flat'; NULL for 'percentage'
    is_system            BOOLEAN       NOT NULL DEFAULT false,
    created_by_user_id   UUID          REFERENCES users(id) ON DELETE RESTRICT,  -- NULL for system brokers
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ   NOT NULL DEFAULT now(),  -- [LC-005] required for custom config edits
    CONSTRAINT broker_configs_percentage_fields_check CHECK (
        (fee_type = 'percentage' AND rate IS NOT NULL AND minimum_fee IS NOT NULL AND flat_fee IS NULL)
        OR (fee_type = 'flat' AND flat_fee IS NOT NULL AND rate IS NULL AND minimum_fee IS NULL)
    ),
    CONSTRAINT broker_configs_system_ownership_check CHECK (
        (is_system = true  AND created_by_user_id IS NULL)
        OR
        (is_system = false AND created_by_user_id IS NOT NULL)
    )
);
```

---

### 3.5 Table: `portfolios`

```sql
CREATE TABLE portfolios (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT portfolios_user_unique UNIQUE (user_id)   -- one portfolio per user at V1
);
```

---

### 3.6 Table: `positions`

```sql
-- Note: stock_code has no FK constraint here.
-- FK to stocks(code) is added in migration 003 via ALTER TABLE.
CREATE TABLE positions (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID        NOT NULL REFERENCES portfolios(id) ON DELETE RESTRICT,
    stock_code   TEXT        NOT NULL,    -- FK added in migration 003: REFERENCES stocks(code) ON DELETE RESTRICT
    stock_name   TEXT        NOT NULL,    -- denormalised for display; entered by user at position creation
    category_tag TEXT        NOT NULL DEFAULT 'Dividend'
        CONSTRAINT positions_category_tag_check
            CHECK (category_tag IN ('Dividend', 'Volatile', 'Growth')),
    is_deleted   BOOLEAN     NOT NULL DEFAULT false,
    deleted_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

### 3.7 Table: `lots`

```sql
-- All fee components stored individually. all_in_cost = initial_amount + brokerage_fee + clearing_fee + stamp_duty.
-- The application enforces this relationship; no CHECK constraint can verify it without a computed expression.
CREATE TABLE lots (
    id               UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id      UUID          NOT NULL REFERENCES positions(id) ON DELETE RESTRICT,
    shares           INTEGER       NOT NULL
        CONSTRAINT lots_shares_positive CHECK (shares >= 1),
    purchase_price   NUMERIC(12,4) NOT NULL
        CONSTRAINT lots_purchase_price_positive CHECK (purchase_price > 0),
    initial_amount   NUMERIC(14,2) NOT NULL       -- shares × purchase_price; stored at creation
        CONSTRAINT lots_initial_amount_positive CHECK (initial_amount > 0),
    brokerage_fee    NUMERIC(14,2) NOT NULL        -- MAX(initial_amount × rate, minimum_fee) for percentage brokers
        CONSTRAINT lots_brokerage_fee_nonneg CHECK (brokerage_fee >= 0),
    clearing_fee     NUMERIC(14,2) NOT NULL        -- initial_amount × 0.0003; capped at RM1,000
        CONSTRAINT lots_clearing_fee_nonneg CHECK (clearing_fee >= 0),
    stamp_duty       NUMERIC(14,2) NOT NULL        -- ROUNDUP(initial_amount/1000, 0) × rate; min RM1
        CONSTRAINT lots_stamp_duty_nonneg CHECK (stamp_duty >= 0),
    all_in_cost      NUMERIC(14,2) NOT NULL        -- initial_amount + brokerage_fee + clearing_fee + stamp_duty
        CONSTRAINT lots_all_in_cost_positive CHECK (all_in_cost > 0),
    purchase_date    DATE          NOT NULL,
    broker_config_id UUID          NOT NULL REFERENCES broker_configs(id) ON DELETE RESTRICT,
    version          INTEGER       NOT NULL DEFAULT 1,  -- optimistic locking; increment on every UPDATE
    is_deleted       BOOLEAN       NOT NULL DEFAULT false,
    deleted_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);
```

---

### 3.8 Table: `dividend_tranches`

```sql
-- P0 INVARIANT: total_amount is stored at logging time as per_share_amount × qualifying_shares.
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
    qualifying_shares INTEGER      NOT NULL               -- stored at logging time; user may override before saving
        CONSTRAINT dividend_tranches_qualifying_shares_positive CHECK (qualifying_shares >= 1),
    total_amount     NUMERIC(14,2) NOT NULL               -- stored at logging time = per_share_amount × qualifying_shares
        CONSTRAINT dividend_tranches_total_amount_positive CHECK (total_amount > 0),
    year             INTEGER       NOT NULL               -- calendar year of the dividend payment
        CONSTRAINT dividend_tranches_year_range CHECK (year >= 2000 AND year <= 2100),
    payment_date     DATE          NOT NULL,
    ex_dividend_date DATE,                               -- nullable; not always known at logging time
    version          INTEGER       NOT NULL DEFAULT 1,   -- optimistic locking; increment on every UPDATE
    is_deleted       BOOLEAN       NOT NULL DEFAULT false,
    deleted_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);
```

---

### 3.9 Table: `stocks`

```sql
-- Natural key: Bursa stock code (e.g., '1023' for CIMB, '1295' for Maybank).
-- NOT a UUID primary key — the exception to the UUID PK rule.
-- Updated monthly by admin script as new IPOs are listed and delistings occur.
CREATE TABLE stocks (
    code             TEXT        PRIMARY KEY,    -- Bursa stock code; natural identifier
    name             TEXT        NOT NULL,
    market           TEXT        NOT NULL,       -- e.g. 'MAIN', 'ACE', 'LEAP'
    sector           TEXT,                       -- GICS sector; nullable for newly listed stocks
    instrument_type  TEXT        NOT NULL DEFAULT 'equity',
    is_active        BOOLEAN     NOT NULL DEFAULT true,   -- false for delisted stocks
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()   -- [NM-004] updated by monthly admin seed script on name/sector changes
);

-- FK from positions added here (after stocks exists), using NOT VALID to allow deferred validation
-- after the stock seeding script runs (see Risk 4 and [MS-002]):
-- ALTER TABLE positions
--     ADD CONSTRAINT positions_stock_code_fk
--     FOREIGN KEY (stock_code) REFERENCES stocks(code) ON DELETE RESTRICT NOT VALID;
```

---

### 3.10 Table: `price_snapshots`

```sql
-- UPSERT key: (stock_code, trading_date).
-- One record per stock per trading day.
-- created_by_user_id is NULL for automated/stale records; non-NULL for manual overrides.
-- Manual override records are hard-deleted on PDPA erasure of the creating user.
CREATE TABLE price_snapshots (
    id                   UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_code           TEXT          NOT NULL REFERENCES stocks(code) ON DELETE RESTRICT,
    price                NUMERIC(12,4) NOT NULL
        CONSTRAINT price_snapshots_price_positive CHECK (price > 0),
    source               TEXT          NOT NULL
        CONSTRAINT price_snapshots_source_check
            CHECK (source IN ('automated', 'manual', 'stale')),
    trading_date         DATE          NOT NULL,
    last_refreshed_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),  -- updated on every UPSERT; used for staleness detection
    created_by_user_id   UUID          REFERENCES users(id) ON DELETE RESTRICT,  -- NULL = automated; non-NULL = manual override
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT price_snapshots_unique_per_day UNIQUE (stock_code, trading_date)
);
```

---

### 3.11 Table: `system_config`

```sql
-- Key-value store for operational parameters. NOT a UUID PK — key is the natural identifier.
-- All values stored as TEXT; application parses to required type (Decimal, JSON, datetime, etc.).
-- Updated via admin API (ADMIN_API_KEY protected). Each change produces a CONFIG_UPDATED audit_log entry.
CREATE TABLE system_config (
    key         TEXT        PRIMARY KEY,
    value       TEXT,                       -- NULL is valid (e.g., price_refresh_lock when no lock is held)
    description TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

### 3.12 Table: `audit_log`

```sql
-- Immutable, append-only. Never updated. CASCADE-deleted when the parent user is hard-deleted.
-- metadata JSONB structure: {"previous_values": {...}, "new_values": {...}, "ip": "..."}
-- IP field in metadata is excluded from PDPA data exports.
CREATE TABLE audit_log (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID        REFERENCES users(id) ON DELETE CASCADE,  -- NULL for system-initiated events (e.g., CONFIG_UPDATED by admin)
    action       TEXT        NOT NULL
        CONSTRAINT audit_log_action_check CHECK (action IN (
            'USER_REGISTERED',        'USER_LOGIN',             'PASSWORD_CHANGED',
            'LOT_CREATED',            'LOT_UPDATED',            'LOT_DELETED',
            'DIVIDEND_CREATED',       'DIVIDEND_UPDATED',       'DIVIDEND_DELETED',
            'PRICE_OVERRIDE_CREATED', 'IMPORT_COMPLETED',
            'SUBSCRIPTION_ACTIVATED', 'SUBSCRIPTION_CANCELLED',
            'DELETION_REQUESTED',     'DELETION_CANCELLED',     'ACCOUNT_DELETED',
            'CONFIG_UPDATED',         'DATA_EXPORT_DOWNLOADED'
        )),
    entity_type  TEXT
        CONSTRAINT audit_log_entity_type_check CHECK (entity_type IN (
            'User', 'Portfolio', 'Position', 'Lot', 'DividendTranche',
            'PriceSnapshot', 'SystemConfig', 'ImportJob'
        )),
    entity_id    UUID,                      -- NULL for events without a single entity (e.g., CONFIG_UPDATED uses key in metadata)
    metadata     JSONB,                     -- {previous_values: {...}, new_values: {...}, ip: "..."}
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

### 3.13 Table: `system_deletion_log`

```sql
-- Records PDPA hard-deletion events. Contains NO user PII. Retained permanently.
-- Inserted at step 10 of the PDPA deletion sequence, before the user row is removed.
CREATE TABLE system_deletion_log (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    deleted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason      TEXT        NOT NULL DEFAULT 'PDPA erasure'
);
```

---

### 3.14 Table: `subscription_records`

```sql
-- Billing records retained for 7-year Malaysian accounting compliance.
-- On PDPA deletion: user_id SET TO NULL (anonymised); record is retained, not deleted.
-- Stripe customer and subscription IDs are retained for accounting audit trail.
CREATE TABLE subscription_records (
    id                      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID          REFERENCES users(id) ON DELETE SET NULL,   -- anonymised on PDPA; set to NULL
    stripe_customer_id      TEXT,
    stripe_subscription_id  TEXT,
    status                  TEXT          NOT NULL,    -- Stripe subscription status: 'active', 'past_due', 'canceled', etc.
    plan_name               TEXT,
    amount                  NUMERIC(14,2),             -- subscription amount in currency below
    currency                TEXT          NOT NULL DEFAULT 'MYR',
    period_start            DATE,
    period_end              DATE,
    created_at              TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ   NOT NULL DEFAULT now()
);
```

---

### 3.15 Table: `processed_webhook_events`

```sql
-- Stripe webhook idempotency table. event_id is the Stripe event ID (natural PK).
-- user_id added (vs. original architecture) to support PDPA deletion by user without a JOIN.
-- CASCADE on user deletion; also explicitly deleted in PDPA step 3.
CREATE TABLE processed_webhook_events (
    event_id      TEXT        PRIMARY KEY,            -- Stripe event ID (e.g. 'evt_1Nxxx...')
    user_id       UUID        REFERENCES users(id) ON DELETE CASCADE,  -- NULL if event not user-scoped
    processed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

### 3.16 Table: `import_jobs`

```sql
CREATE TABLE import_jobs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status          TEXT        NOT NULL DEFAULT 'processing'
        CONSTRAINT import_jobs_status_check
            CHECK (status IN ('processing', 'complete', 'failed')),
    result_payload  JSONB,                  -- NULL while processing; set to outcome summary on completion or failure
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),   -- [LC-007] job creation timestamp
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 4. CHECK Constraints Reference

| Table | Constraint name | Expression | Business rule source |
|-------|-----------------|------------|---------------------|
| `users` | `users_account_status_check` | `account_status IN ('trial', 'active', 'grace_period', 'trial_expired', 'pending_deletion')` | BR-004, §12.5 account lifecycle |
| `pending_tokens` | `pending_tokens_type_check` | `type IN ('email_verification', 'password_reset', 'deletion_cancellation')` | §14.1, FR-011, FR-012, FR-019 |
| `broker_configs` | `broker_configs_fee_type_check` | `fee_type IN ('percentage', 'flat')` | BAS BR-002 |
| `broker_configs` | `broker_configs_percentage_fields_check` | `(fee_type = 'percentage' AND rate IS NOT NULL AND minimum_fee IS NOT NULL AND flat_fee IS NULL) OR (fee_type = 'flat' AND flat_fee IS NOT NULL AND rate IS NULL AND minimum_fee IS NULL)` | BAS BR-002 |
| `broker_configs` | `broker_configs_system_ownership_check` | `(is_system = true AND created_by_user_id IS NULL) OR (is_system = false AND created_by_user_id IS NOT NULL)` | LDM-007 |
| `positions` | `positions_category_tag_check` | `category_tag IN ('Dividend', 'Volatile', 'Growth')` | BAS FR-002 |
| `lots` | `lots_shares_positive` | `shares >= 1` | BAS VR-003 |
| `lots` | `lots_purchase_price_positive` | `purchase_price > 0` | BAS VR-004 |
| `lots` | `lots_initial_amount_positive` | `initial_amount > 0` | Financial correctness |
| `lots` | `lots_brokerage_fee_nonneg` | `brokerage_fee >= 0` | Financial correctness |
| `lots` | `lots_clearing_fee_nonneg` | `clearing_fee >= 0` | Financial correctness |
| `lots` | `lots_stamp_duty_nonneg` | `stamp_duty >= 0` | Financial correctness |
| `lots` | `lots_all_in_cost_positive` | `all_in_cost > 0` | Financial correctness |
| `dividend_tranches` | `dividend_tranches_label_check` | `tranche_label IN ('1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th')` | BAS BR-014 |
| `dividend_tranches` | `dividend_tranches_per_share_positive` | `per_share_amount > 0` | BAS VR-009 |
| `dividend_tranches` | `dividend_tranches_qualifying_shares_positive` | `qualifying_shares >= 1` | BAS VR-001 / P0 |
| `dividend_tranches` | `dividend_tranches_total_amount_positive` | `total_amount > 0` | P0 invariant support |
| `dividend_tranches` | `dividend_tranches_year_range` | `year >= 2000 AND year <= 2100` | Sanity validation |
| `price_snapshots` | `price_snapshots_price_positive` | `price > 0` | Financial correctness |
| `price_snapshots` | `price_snapshots_source_check` | `source IN ('automated', 'manual', 'stale')` | §15.1 yfinance reliability design |
| `audit_log` | `audit_log_action_check` | `action IN (...)` (18 values) | §14.7 audit event list |
| `audit_log` | `audit_log_entity_type_check` | `entity_type IN (...)` (8 values) | LDM-005 |
| `import_jobs` | `import_jobs_status_check` | `status IN ('processing', 'complete', 'failed')` | LDM-010 |

---

## 5. Index Strategy

### Functional indexes from Architecture §8.3

```sql
-- Dashboard aggregate queries: position total_shares and total_all_in_cost
-- Query: SUM(lots.shares), SUM(lots.all_in_cost) WHERE position_id = ? AND is_deleted = false
CREATE INDEX idx_lots_position_active
    ON lots(position_id)
    WHERE is_deleted = false;

-- YTD dividend sum per position
-- Query: SUM(dividend_tranches.total_amount) WHERE position_id = ? AND year = ? AND is_deleted = false
CREATE INDEX idx_dividend_tranches_position_year_active
    ON dividend_tranches(position_id, year)
    WHERE is_deleted = false;

-- Price lookups for dashboard (latest price per stock)
-- Query: SELECT ... FROM price_snapshots WHERE stock_code = ? ORDER BY trading_date DESC LIMIT 1
CREATE INDEX idx_price_snapshots_stock_date
    ON price_snapshots(stock_code, trading_date DESC);

-- PDPA deletion job and data export: all audit entries for a user
CREATE INDEX idx_audit_log_user_id
    ON audit_log(user_id);

-- Drill-down audit queries: all events for a specific entity
CREATE INDEX idx_audit_log_entity
    ON audit_log(entity_type, entity_id);

-- Import status polling: active imports for a user
-- Query: SELECT ... FROM import_jobs WHERE user_id = ? AND status = ?
CREATE INDEX idx_import_jobs_user_status
    ON import_jobs(user_id, status);
```

### Additional indexes from Stage 2 decisions

```sql
-- Active token lookup for a user (login, password reset, deletion cancellation flows)
-- Partial index: only rows where the token has not been used
-- Query: SELECT ... FROM pending_tokens WHERE user_id = ? AND type = ? AND used_at IS NULL
CREATE INDEX idx_pending_tokens_user_type_active
    ON pending_tokens(user_id, type)
    WHERE used_at IS NULL;

-- PDPA deletion: locate manual price overrides for a specific user
-- Query: DELETE FROM price_snapshots WHERE created_by_user_id = ?
CREATE INDEX idx_price_snapshots_manual_by_user
    ON price_snapshots(created_by_user_id)
    WHERE created_by_user_id IS NOT NULL;

-- Uniqueness: one active position per stock per portfolio (business rule)
-- Soft-deleted positions are excluded, allowing recreation
CREATE UNIQUE INDEX idx_positions_unique_stock_per_portfolio
    ON positions(portfolio_id, stock_code)
    WHERE is_deleted = false;

-- Uniqueness: one active tranche label per position per year (BR-014, VR-007)
CREATE UNIQUE INDEX idx_dividend_tranches_unique_label_per_position_year
    ON dividend_tranches(position_id, tranche_label, year)
    WHERE is_deleted = false;

-- Uniqueness: one processing import job per user at a time (LDM-010)
CREATE UNIQUE INDEX idx_import_jobs_one_processing_per_user
    ON import_jobs(user_id)
    WHERE status = 'processing';

-- Stripe customer lookup: webhook → user mapping
-- Query: SELECT id FROM users WHERE stripe_customer_id = ?
CREATE INDEX idx_users_stripe_customer_id
    ON users(stripe_customer_id)
    WHERE stripe_customer_id IS NOT NULL;

-- [PQ-003] PDPA deletion cron: find all users whose 30-day grace period has expired
-- Query: SELECT id FROM users WHERE account_status = 'pending_deletion' AND permanent_deletion_date <= now()
-- Partial index on pending_deletion subset only; this set is always small (few active deletions at a time)
CREATE INDEX idx_users_pending_deletion
    ON users(permanent_deletion_date)
    WHERE account_status = 'pending_deletion';
```

---

## 6. FK Cascade and Lifecycle Behaviour

### ON DELETE CASCADE (automatic cleanup)

| FK | Behaviour |
|----|-----------|
| `pending_tokens.user_id → users(id)` | All tokens for a deleted user are automatically removed |
| `pending_email_notifications.user_id → users(id)` | Notification queue cleaned up automatically |
| `processed_webhook_events.user_id → users(id)` | Webhook idempotency records cleaned up automatically |
| `audit_log.user_id → users(id)` | All audit records for a deleted user are automatically removed |

### ON DELETE SET NULL (anonymisation)

| FK | Behaviour |
|----|-----------|
| `subscription_records.user_id → users(id)` | Billing records are retained; user identity is removed |
| `users.default_broker_config_id → broker_configs(id)` | User loses their default broker preference if the custom config is deleted |
| `price_snapshots.created_by_user_id → users(id)` | N/A — this FK is ON DELETE RESTRICT; manual snapshots are explicitly deleted before user is deleted |

### ON DELETE RESTRICT (prevent accidental deletion)

| FK | What it protects |
|----|-----------------|
| `portfolios.user_id → users(id)` | Cannot delete a user while their portfolio exists |
| `positions.portfolio_id → portfolios(id)` | Cannot delete a portfolio while positions exist |
| `lots.position_id → positions(id)` | Cannot delete a position while lots exist |
| `dividend_tranches.position_id → positions(id)` | Cannot delete a position while tranches exist |
| `lots.broker_config_id → broker_configs(id)` | Cannot delete a broker config while lots reference it |
| `broker_configs.created_by_user_id → users(id)` | Cannot delete a user while their custom broker configs exist |
| `price_snapshots.created_by_user_id → users(id)` | Cannot delete a user while their manual price overrides exist |
| `import_jobs.user_id → users(id)` | Cannot delete a user while import jobs are linked |
| `price_snapshots.stock_code → stocks(code)` | Cannot delete a stock while price snapshots exist |
| `positions.stock_code → stocks(code)` | Cannot delete a stock while positions reference it |

### Soft-Delete Queries

All queries on soft-deleteable tables must include the `WHERE is_deleted = false` clause unless specifically retrieving deleted records (e.g., audit export). This applies to:

- `lots`: `WHERE is_deleted = false` on all dashboard aggregates
- `positions`: `WHERE is_deleted = false` on portfolio views
- `dividend_tranches`: `WHERE is_deleted = false` on all yield calculations

---

## 7. Optimistic Locking Pattern

The `lots` and `dividend_tranches` tables use `version INTEGER NOT NULL DEFAULT 1` for optimistic concurrency control.

### Update Pattern

Every UPDATE on these tables must include the version in the WHERE clause and increment it:

```sql
-- Lot update with optimistic locking
UPDATE lots
SET
    shares           = :new_shares,
    purchase_price   = :new_purchase_price,
    initial_amount   = :new_initial_amount,
    brokerage_fee    = :new_brokerage_fee,
    clearing_fee     = :new_clearing_fee,
    stamp_duty       = :new_stamp_duty,
    all_in_cost      = :new_all_in_cost,
    broker_config_id = :new_broker_config_id,
    purchase_date    = :new_purchase_date,
    version          = version + 1,
    updated_at       = now()
WHERE
    id      = :lot_id
    AND version = :expected_version   -- must match the version the client read
    AND is_deleted = false;

-- Check rowcount: if 0, version mismatch → HTTP 409 Conflict
```

```sql
-- DividendTranche explicit user edit (the ONLY permitted update to total_amount)
UPDATE dividend_tranches
SET
    per_share_amount  = :new_per_share_amount,
    qualifying_shares = :new_qualifying_shares,
    total_amount      = :new_total_amount,    -- recalculated: new_per_share_amount × new_qualifying_shares
    payment_date      = :new_payment_date,
    ex_dividend_date  = :new_ex_dividend_date,
    year              = :new_year,
    version           = version + 1,
    updated_at        = now()
WHERE
    id      = :tranche_id
    AND version = :expected_version
    AND is_deleted = false;
```

### Conflict Response

If `UPDATE` affects 0 rows (version mismatch — another session updated the record between the client's read and this write):

```json
HTTP 409 Conflict
{
  "error": "conflict",
  "message": "This record was modified by another session. Please refresh and try again."
}
```

The client must discard its stale copy and re-fetch the current state before retrying.

### Why version Must Be in Every UPDATE

Without the version column in the WHERE clause, two concurrent sessions editing the same Lot would both succeed, with the last writer silently overwriting the first. For financial records (lot fees, dividend amounts), silent overwrites could corrupt historical data. The version check converts this into a detectable conflict.

---

## 8. PDPA Hard-Delete Order

The following sequence must execute in a single database transaction per user. If any step fails, the entire transaction is rolled back and no user data is partially deleted.

| Step | Action | SQL type | FK dependency |
|------|--------|----------|---------------|
| **1** | DELETE manual PriceSnapshots for user | Explicit DELETE | `price_snapshots.created_by_user_id REFERENCES users(id) ON DELETE RESTRICT` — must be deleted before user row |
| **2** | DELETE ImportJobs for user | Explicit DELETE | `import_jobs.user_id REFERENCES users(id) ON DELETE RESTRICT` |
| **3** | DELETE ProcessedWebhookEvents for user | Explicit DELETE (CASCADE is safety net) | `processed_webhook_events.user_id REFERENCES users(id) ON DELETE CASCADE` |
| **4** | DELETE PendingEmailNotifications for user | Explicit DELETE (CASCADE is safety net) | `pending_email_notifications.user_id REFERENCES users(id) ON DELETE CASCADE` |
| **5** | DELETE DividendTranches for user's positions | Explicit DELETE via portfolio subquery | No direct user FK; via position → portfolio → user |
| **6** | DELETE Lots for user's positions | Explicit DELETE via portfolio subquery | No direct user FK; via position → portfolio → user |
| **6a** | DELETE custom BrokerConfigs for user | Explicit DELETE | `broker_configs.created_by_user_id REFERENCES users(id) ON DELETE RESTRICT` — must occur after lots are deleted |
| **7** | DELETE Positions for user's portfolio | Explicit DELETE | `positions.portfolio_id REFERENCES portfolios(id) ON DELETE RESTRICT` |
| **8** | DELETE Portfolio for user | Explicit DELETE | `portfolios.user_id REFERENCES users(id) ON DELETE RESTRICT` |
| **9** | SET subscription_records.user_id = NULL | UPDATE (anonymise) | FK ON DELETE SET NULL enables this |
| **10** | INSERT system_deletion_log | INSERT | No FK; no PII |
| **11** | DELETE User | Explicit DELETE | Triggers CASCADE on: audit_log, pending_tokens, pending_email_notifications, processed_webhook_events |

```sql
-- Reference implementation (executed in a single transaction)
-- Step 1
DELETE FROM price_snapshots
    WHERE created_by_user_id = :user_id;

-- Step 2
DELETE FROM import_jobs
    WHERE user_id = :user_id;

-- Step 3
DELETE FROM processed_webhook_events
    WHERE user_id = :user_id;

-- Step 4
DELETE FROM pending_email_notifications
    WHERE user_id = :user_id;

-- Step 5
DELETE FROM dividend_tranches
    WHERE position_id IN (
        SELECT p.id FROM positions p
        JOIN portfolios pf ON p.portfolio_id = pf.id
        WHERE pf.user_id = :user_id
    );

-- Step 6
DELETE FROM lots
    WHERE position_id IN (
        SELECT p.id FROM positions p
        JOIN portfolios pf ON p.portfolio_id = pf.id
        WHERE pf.user_id = :user_id
    );

-- Step 6a
DELETE FROM broker_configs
    WHERE created_by_user_id = :user_id
      AND is_system = false;

-- Step 7
DELETE FROM positions
    WHERE portfolio_id IN (
        SELECT id FROM portfolios WHERE user_id = :user_id
    );

-- Step 8
DELETE FROM portfolios
    WHERE user_id = :user_id;

-- Step 9
UPDATE subscription_records
    SET user_id = NULL
    WHERE user_id = :user_id;

-- Step 10
INSERT INTO system_deletion_log (deleted_at, reason)
    VALUES (now(), 'PDPA erasure');

-- Step 11 — CASCADE removes: audit_log, pending_tokens, pending_email_notifications, processed_webhook_events
DELETE FROM users WHERE id = :user_id;
```

### Gate Condition (Pre-Deletion Check)

The PDPA deletion cron must verify the confirmation email was delivered before executing step 1:

```sql
-- Gate: abort if PDPA_DELETION_CONFIRMED email has not been sent
SELECT sent_at FROM pending_email_notifications
    WHERE user_id = :user_id
      AND type = 'PDPA_DELETION_CONFIRMED'
      AND sent_at IS NOT NULL;
-- If no row returned: skip deletion; emit Sentry CRITICAL alert
```

---

## 9. Alembic Migration Plan

### Migration Sequence

| Migration | Contents | Dependency |
|-----------|----------|------------|
| `001_create_auth_tables` | `users`, `pending_tokens`, `pending_email_notifications` | None |
| `002_create_portfolio_tables` | `broker_configs`, ALTER TABLE users (add `default_broker_config_id`), `portfolios`, `positions`, `lots`, `dividend_tranches` | 001 |
| `003_create_pricing_tables` | `stocks`, ALTER TABLE positions (add FK to stocks), `price_snapshots` | 002 |
| `004_create_admin_tables` | `system_config`, `audit_log`, `system_deletion_log` | 001 |
| `005_create_subscription_tables` | `subscription_records`, `processed_webhook_events`, `import_jobs` | 001 |
| `006_create_indexes` | All indexes | 002, 003, 004, 005 |
| `007_seed_reference_data` | BrokerConfig system rows, SystemConfig defaults | 006 |

---

### Migration 001 — Auth Tables

**upgrade():**

```sql
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
    trial_expiry_date         DATE         NOT NULL,
    subscription_start_date   DATE,
    subscription_renewal_date DATE,
    deletion_requested_date   DATE,
    permanent_deletion_date   DATE,
    created_at                TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- [DI-011] Case-insensitive email uniqueness via functional index
CREATE UNIQUE INDEX users_email_lower_unique ON users(LOWER(email));

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
);

CREATE TABLE pending_email_notifications (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type             TEXT        NOT NULL,
    recipient_email  TEXT        NOT NULL,
    attempt_count    INTEGER     NOT NULL DEFAULT 0,
    sent_at          TIMESTAMPTZ,
    next_retry_at    TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()   -- [LC-005b]
);
```

**downgrade():**

```sql
DROP INDEX users_email_lower_unique;
DROP TABLE pending_email_notifications;
DROP TABLE pending_tokens;
DROP TABLE users;
```

---

### Migration 002 — Portfolio Tables

**upgrade():**

```sql
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
    updated_at           TIMESTAMPTZ   NOT NULL DEFAULT now(),   -- [LC-005]
    CONSTRAINT broker_configs_percentage_fields_check CHECK (
        (fee_type = 'percentage' AND rate IS NOT NULL AND minimum_fee IS NOT NULL AND flat_fee IS NULL)
        OR (fee_type = 'flat' AND flat_fee IS NOT NULL AND rate IS NULL AND minimum_fee IS NULL)
    ),
    CONSTRAINT broker_configs_system_ownership_check CHECK (
        (is_system = true AND created_by_user_id IS NULL)
        OR (is_system = false AND created_by_user_id IS NOT NULL)
    )
);

ALTER TABLE users
    ADD COLUMN default_broker_config_id UUID REFERENCES broker_configs(id) ON DELETE SET NULL;

CREATE TABLE portfolios (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT portfolios_user_unique UNIQUE (user_id)
);

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
);

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
);

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
        CONSTRAINT dividend_tranches_year_range CHECK (year >= 2000 AND year <= 2100),
    payment_date     DATE          NOT NULL,
    ex_dividend_date DATE,
    version          INTEGER       NOT NULL DEFAULT 1,
    is_deleted       BOOLEAN       NOT NULL DEFAULT false,
    deleted_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);
```

**downgrade():**

```sql
DROP TABLE dividend_tranches;
DROP TABLE lots;
DROP TABLE positions;
DROP TABLE portfolios;
ALTER TABLE users DROP COLUMN default_broker_config_id;
DROP TABLE broker_configs;
```

---

### Migration 003 — Pricing Tables

**upgrade():**

```sql
CREATE TABLE stocks (
    code             TEXT        PRIMARY KEY,
    name             TEXT        NOT NULL,
    market           TEXT        NOT NULL,
    sector           TEXT,
    instrument_type  TEXT        NOT NULL DEFAULT 'equity',
    is_active        BOOLEAN     NOT NULL DEFAULT true,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()   -- [NM-004]
);

-- [MS-002] Added as NOT VALID so it can be added before the stock seeding script runs.
-- After the seed script completes, run: ALTER TABLE positions VALIDATE CONSTRAINT positions_stock_code_fk
ALTER TABLE positions
    ADD CONSTRAINT positions_stock_code_fk
    FOREIGN KEY (stock_code) REFERENCES stocks(code) ON DELETE RESTRICT NOT VALID;

CREATE TABLE price_snapshots (
    id                   UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_code           TEXT          NOT NULL REFERENCES stocks(code) ON DELETE RESTRICT,
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
);
```

**downgrade():**

```sql
DROP TABLE price_snapshots;
ALTER TABLE positions DROP CONSTRAINT positions_stock_code_fk;
DROP TABLE stocks;
```

---

### Migration 004 — Admin Tables

**upgrade():**

```sql
CREATE TABLE system_config (
    key         TEXT        PRIMARY KEY,
    value       TEXT,
    description TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID        REFERENCES users(id) ON DELETE CASCADE,
    action       TEXT        NOT NULL
        CONSTRAINT audit_log_action_check CHECK (action IN (
            'USER_REGISTERED',        'USER_LOGIN',             'PASSWORD_CHANGED',
            'LOT_CREATED',            'LOT_UPDATED',            'LOT_DELETED',
            'DIVIDEND_CREATED',       'DIVIDEND_UPDATED',       'DIVIDEND_DELETED',
            'PRICE_OVERRIDE_CREATED', 'IMPORT_COMPLETED',
            'SUBSCRIPTION_ACTIVATED', 'SUBSCRIPTION_CANCELLED',
            'DELETION_REQUESTED',     'DELETION_CANCELLED',     'ACCOUNT_DELETED',
            'CONFIG_UPDATED',         'DATA_EXPORT_DOWNLOADED'
        )),
    entity_type  TEXT
        CONSTRAINT audit_log_entity_type_check CHECK (entity_type IN (
            'User', 'Portfolio', 'Position', 'Lot', 'DividendTranche',
            'PriceSnapshot', 'SystemConfig', 'ImportJob'
        )),
    entity_id    UUID,
    metadata     JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE system_deletion_log (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    deleted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason      TEXT        NOT NULL DEFAULT 'PDPA erasure'
);
```

**downgrade():**

```sql
DROP TABLE system_deletion_log;
DROP TABLE audit_log;
DROP TABLE system_config;
```

---

### Migration 005 — Subscription Tables

**upgrade():**

```sql
CREATE TABLE subscription_records (
    id                      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID          REFERENCES users(id) ON DELETE SET NULL,
    stripe_customer_id      TEXT,
    stripe_subscription_id  TEXT,
    status                  TEXT          NOT NULL,
    plan_name               TEXT,
    amount                  NUMERIC(14,2),
    currency                TEXT          NOT NULL DEFAULT 'MYR',
    period_start            DATE,
    period_end              DATE,
    created_at              TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE processed_webhook_events (
    event_id      TEXT        PRIMARY KEY,
    user_id       UUID        REFERENCES users(id) ON DELETE CASCADE,
    processed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE import_jobs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status          TEXT        NOT NULL DEFAULT 'processing'
        CONSTRAINT import_jobs_status_check
            CHECK (status IN ('processing', 'complete', 'failed')),
    result_payload  JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),   -- [LC-007]
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**downgrade():**

```sql
DROP TABLE import_jobs;
DROP TABLE processed_webhook_events;
DROP TABLE subscription_records;
```

---

### Migration 006 — Indexes

**upgrade():**

```sql
-- Lots: dashboard aggregate queries
CREATE INDEX idx_lots_position_active
    ON lots(position_id)
    WHERE is_deleted = false;

-- DividendTranches: YTD sum per position per year
CREATE INDEX idx_dividend_tranches_position_year_active
    ON dividend_tranches(position_id, year)
    WHERE is_deleted = false;

-- PriceSnapshots: latest price lookup per stock
CREATE INDEX idx_price_snapshots_stock_date
    ON price_snapshots(stock_code, trading_date DESC);

-- AuditLog: PDPA export and deletion
CREATE INDEX idx_audit_log_user_id
    ON audit_log(user_id);

-- AuditLog: entity drill-down queries
CREATE INDEX idx_audit_log_entity
    ON audit_log(entity_type, entity_id);

-- ImportJobs: status polling per user
CREATE INDEX idx_import_jobs_user_status
    ON import_jobs(user_id, status);

-- PendingTokens: active token lookup
CREATE INDEX idx_pending_tokens_user_type_active
    ON pending_tokens(user_id, type)
    WHERE used_at IS NULL;

-- PriceSnapshots: PDPA deletion of manual overrides
CREATE INDEX idx_price_snapshots_manual_by_user
    ON price_snapshots(created_by_user_id)
    WHERE created_by_user_id IS NOT NULL;

-- Positions: uniqueness — one active position per stock per portfolio
CREATE UNIQUE INDEX idx_positions_unique_stock_per_portfolio
    ON positions(portfolio_id, stock_code)
    WHERE is_deleted = false;

-- DividendTranches: uniqueness — one active label per position per year
CREATE UNIQUE INDEX idx_dividend_tranches_unique_label_per_position_year
    ON dividend_tranches(position_id, tranche_label, year)
    WHERE is_deleted = false;

-- ImportJobs: uniqueness — one processing job per user
CREATE UNIQUE INDEX idx_import_jobs_one_processing_per_user
    ON import_jobs(user_id)
    WHERE status = 'processing';

-- Users: Stripe customer lookup
CREATE INDEX idx_users_stripe_customer_id
    ON users(stripe_customer_id)
    WHERE stripe_customer_id IS NOT NULL;

-- [PQ-003] Users: PDPA deletion cron — find expired pending_deletion accounts
CREATE INDEX idx_users_pending_deletion
    ON users(permanent_deletion_date)
    WHERE account_status = 'pending_deletion';

-- [NM-003] Column-level documentation for non-obvious invariants
COMMENT ON COLUMN users.token_version IS
    'Monotonically increasing counter; increment on logout, password change, or deletion initiation to invalidate all issued JWTs for this user.';
COMMENT ON COLUMN dividend_tranches.qualifying_shares IS
    'Share count at ex-dividend date, recorded at logging time. User may override before saving. Never updated automatically from lot changes.';
COMMENT ON COLUMN dividend_tranches.total_amount IS
    'P0 INVARIANT: stored at logging time as per_share_amount × qualifying_shares. Never recomputed from current lot shares. Only updated by an explicit user edit of this record.';
COMMENT ON COLUMN broker_configs.is_system IS
    'true = system-managed row seeded at deployment (created_by_user_id IS NULL); false = user-created custom config. System rows cannot be edited or deleted by users.';
COMMENT ON COLUMN system_config.value IS
    'Stored as TEXT regardless of logical type. Application parses to Decimal, JSON, or datetime as needed. NULL is valid (e.g., price_refresh_lock when no lock is held).';
```

**downgrade():**

```sql
DROP INDEX idx_users_pending_deletion;
DROP INDEX idx_users_stripe_customer_id;
DROP INDEX idx_import_jobs_one_processing_per_user;
DROP INDEX idx_dividend_tranches_unique_label_per_position_year;
DROP INDEX idx_positions_unique_stock_per_portfolio;
DROP INDEX idx_price_snapshots_manual_by_user;
DROP INDEX idx_pending_tokens_user_type_active;
DROP INDEX idx_import_jobs_user_status;
DROP INDEX idx_audit_log_entity;
DROP INDEX idx_audit_log_user_id;
DROP INDEX idx_price_snapshots_stock_date;
DROP INDEX idx_dividend_tranches_position_year_active;
DROP INDEX idx_lots_position_active;
```

---

### Migration 007 — Seed Reference Data

**upgrade():**

```sql
-- System BrokerConfig rows (from Architecture §10.6)
-- These are seeded once at deployment; never modified by user actions.
INSERT INTO broker_configs (id, name, fee_type, rate, minimum_fee, flat_fee, is_system, created_by_user_id)
VALUES
    (gen_random_uuid(), 'Maybank IB',    'percentage', 0.007000, 8.00,  NULL, true, NULL),
    (gen_random_uuid(), 'CIMB Clicks',   'percentage', 0.007000, 8.00,  NULL, true, NULL),
    (gen_random_uuid(), 'RHB Reflex',    'percentage', 0.007000, 8.00,  NULL, true, NULL),
    (gen_random_uuid(), 'Rakuten Trade', 'percentage', 0.007000, 7.00,  NULL, true, NULL),
    (gen_random_uuid(), 'Mirae Asset',   'percentage', 0.004200, 8.00,  NULL, true, NULL),
    (gen_random_uuid(), 'M+ Online',     'percentage', 0.006000, 8.00,  NULL, true, NULL);

-- SystemConfig operational parameters
-- stamp_duty_rate: RM1 per RM1,000 (0.10%); valid as of 2026-06-28; revisit if Budget changes rate
-- clearing_fee_rate: 0.03% of contract value; RM1,000 cap above RM3.33M contract value
-- price_deviation_max_pct: alert threshold for yfinance price anomaly detection
-- bursa_holidays: JSON array of ISO date strings; admin must update this list annually
-- price_refresh_lock: NULL = no lock held; set by refresh_prices.py during execution
INSERT INTO system_config (key, value, description)
VALUES
    ('stamp_duty_rate',         '0.001',  'RM1 per RM1,000 (0.10%); ROUNDUP semantics; configurable without code deploy; valid until 12 July 2028'),
    ('clearing_fee_rate',       '0.0003', '0.03% of contract value; no minimum; RM1,000 cap when contract value > RM3.33M'),
    ('price_deviation_max_pct', '75',     'Max price deviation (%) vs previous snapshot before marking as CORPORATE_ACTION_CANDIDATE'),
    ('bursa_holidays',          '[]',     'JSON array of ISO date strings for Bursa trading calendar non-trading days; update annually'),
    ('price_refresh_lock',      NULL,     'Process lock for refresh_prices.py; NULL = no lock held; set to ISO timestamp when lock acquired');
```

**Note on stock seeding:** The `stocks` table requires seeding with the full list of Bursa Malaysia-listed securities (MAIN Market, ACE Market). This is a large dataset and is NOT included in this migration. It should be seeded via a separate admin script (`scripts/seed_stocks.py`) that imports from a static CSV file. This script runs once after migration 007 on initial deployment and is rerun periodically (monthly cadence per §19, R-009).

**downgrade():**

```sql
DELETE FROM system_config
    WHERE key IN ('stamp_duty_rate', 'clearing_fee_rate', 'price_deviation_max_pct', 'bursa_holidays', 'price_refresh_lock');

DELETE FROM broker_configs
    WHERE is_system = true;
```

---

## 10. Risks and Open Implementation Questions

### Risk 1 — stripe_customer_id Location (OQ-001 — Decision Required Before Migration 001)

**This is open question OQ-001 from the Stage 4 schema review. It must be resolved before migration 001 runs.**

The field `users.stripe_customer_id` was added as an inference from the Stripe integration requirement (webhook → user lookup). The solution architecture (§12.1) does not explicitly place this field on the User entity. The implementation team must decide:

- **Option A (current schema):** `stripe_customer_id` on `users` — fast single-table lookup; requires the column to exist from day one of the user lifecycle.
- **Option B:** `stripe_customer_id` only on `subscription_records` — webhook processing requires a JOIN; `idx_users_stripe_customer_id` is replaced with an index on `subscription_records.stripe_customer_id`.
- **Option C:** Both — denormalized; keeps Option A's fast path but introduces a sync risk.

**Required action:** Confirm Option A, B, or C with the architect before migration 001 is finalized. If Option B is chosen, remove `stripe_customer_id` from the `users` table definition and from migration 001, and add the index to `subscription_records` in migration 005.

---

### Risk 2 — P0 Regression: PRD §14 Conflict

PRD Section 14 still describes `DividendTranche.total_amount` as "derived." Any engineer reading the PRD as their primary reference may implement triggers or computed values on `dividend_tranches`. This schema forbids any such mechanism. The mitigation:

1. PRD Section 14 must be corrected before any code is written
2. Schema comments on `dividend_tranches.total_amount` and `.qualifying_shares` explicitly state the P0 invariant
3. The mandatory P0 regression test (EC-022 from BAS Part 3) must be implemented and marked non-skippable in CI

---

### Risk 3 — PDPA Deletion Transaction Size

The PDPA hard-delete is a single transaction covering potentially hundreds of rows (all lots, dividend tranches, and audit records for a user). For a user with 50 positions × 3 lots × 8 dividend tranches × many audit events, this transaction may lock rows for a meaningful duration. At V1 scale (one PDPA deletion cron per night, few active users), this is acceptable. At scale, consider batched deletion with saga-style compensation.

---

### Risk 4 — Stock Reference Data Staleness at FK Addition

**[MS-002] Fixed in this schema.** Migration 003 adds the positions → stocks FK as `NOT VALID`, implementing the LDM-003 recommendation that was previously missing from the migration DDL.

Initial deployment requires a three-step sequence:
1. Run `alembic upgrade head` — migration 003 adds the FK `NOT VALID`; no existing rows are checked yet
2. Run `scripts/seed_stocks.py` — populates the `stocks` table with Bursa-listed securities
3. Run `ALTER TABLE positions VALIDATE CONSTRAINT positions_stock_code_fk` — scans all positions rows and enforces the FK

If a position row references a stock code absent from `stocks` after step 2, step 3 will fail with a FK violation. The seed script must include all codes present in any existing position rows. On a fresh deployment (no prior positions), step 3 succeeds immediately.

This three-step sequence must be documented in the deployment runbook and included in the CI/CD pipeline for the initial production deploy.

---

### Risk 5 — Concurrent PDPA Deletion and Active Session

If a user with `account_status = pending_deletion` makes an API request while the PDPA deletion cron is executing, the request may fail with a FK violation error (e.g., an attempt to create a lot while lots are being deleted). The application's auth middleware must check `account_status = pending_deletion` and reject all write requests with HTTP 403 before they reach the database. This is an application concern, not a schema concern — but it must be implemented to prevent race conditions at step 6.

---

### Risk 6 — Alembic Pre-Deploy and Backwards Compatibility

Render runs `alembic upgrade head` as a pre-deploy command. If the migration fails mid-way, Render aborts the new deployment and the previous application version continues running. The schema at that point is partially migrated. All migrations must be designed so that the previous application version can operate safely against a partially-migrated schema (additive-only changes: new nullable columns, new tables, new indexes are safe; existing columns and tables are untouched).

The `ALTER TABLE users ADD COLUMN default_broker_config_id` in migration 002 is safe: old application code ignores unknown columns; new code handles NULL gracefully.

---

### Risk 7 — audit_log.action CHECK Constraint Extensibility

The `audit_log.action` column has a closed CHECK constraint (18 values). Adding a new audit event type requires a migration to extend the constraint. This is a backwards-compatible additive change (new value added to the enum list), but it does require a migration deployment. The implementation team should plan for this — new features that require new audit events must coordinate with a schema migration.

---

*End of Stage 3 — Physical Schema Design*  
*This document constitutes the complete, implementation-ready database schema for BursaTrack V1.*  
*Output location:* `specs/output/2.technical-designs/database-design/`  

*Documents produced:*
- *Stage 1: BursaTrack-DB-Stage1-Domain-Model-Review.md*  
- *Stage 2: BursaTrack-DB-Stage2-Logical-Model-Decisions.md*  
- *Stage 3: BursaTrack-DB-Stage3-Physical-Schema.md (this file)*
