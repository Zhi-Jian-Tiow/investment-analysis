# BursaTrack — Database Design: Stage 4 Schema Review Report

**Stage:** 4 of 4 — Schema Review and Iteration  
**Date:** 2026-06-28  
**Reviewer role:** Database reviewer acting as final quality gate before implementation  
**Schema reviewed:** Stage 3 Physical Schema Design (BursaTrack-DB-Stage3-Physical-Schema.md)  
**Input documents:**

- Stage 1 Domain Model Review Report
- Stage 2 Logical Data Modelling Decision Record
- Stage 3 Physical Schema Design
- Solution Architecture Document v1.1

---

## 1. Overall Assessment

This schema is **very close to implementation-ready** but has one HIGH finding that must be resolved before the first user registers, and four MEDIUM findings that should be resolved before launch. The P0 qualifying_shares invariant is correctly protected: `total_amount` is a plain stored column, there are no triggers, no generated columns, and no views touching `dividend_tranches`. All monetary columns use exact `NUMERIC` types with correct precision. All PDPA deletion mechanics — cascade order, anonymisation, pre-deletion gate, system_deletion_log — are correctly implemented. The Alembic migration plan is properly ordered and fully reversible.

**Risk level: LOW.** The schema is financially correct and PDPA-compliant. The outstanding findings are a case-sensitivity gap on email uniqueness (HIGH), three schema completeness gaps (MEDIUM), one migration safety gap (MEDIUM), and one open architectural question (MEDIUM). None of the findings introduce financial incorrectness or PDPA non-compliance. Zero CRITICAL findings.

**Finding count by severity:**

- CRITICAL: **0**
- HIGH: **1**
- MEDIUM: **5**
- LOW: **4**

---

## 2. Findings by Severity

### HIGH

#### [DI-011] HIGH — `users.email`

**Affected table/column:** `users.email`

**What is wrong:** `UNIQUE (email)` is a case-sensitive constraint in PostgreSQL. If any code path — a new registration route, admin script, or future OAuth integration — inserts an email without prior lowercase normalisation, a user could register as `'Aaron@Example.com'` alongside an existing `'aaron@example.com'` and the database would allow both rows. Downstream effects: Stripe webhook lookup by customer email would match the wrong account; PDPA deletion would target only one of the two records; authentication would depend on which casing the user typed. The architecture states this is an "application-layer concern" but also requires that "the unique constraint must be case-insensitive OR normalisation must be enforced." The current schema enforces neither at the database level.

**Recommendation:** Replace the column-level `UNIQUE` constraint with a functional unique index on `LOWER(email)`. In migration 001:

```sql
-- Remove from CREATE TABLE users:
CONSTRAINT users_email_unique UNIQUE (email)

-- Add after CREATE TABLE users (before CREATE TABLE pending_tokens):
CREATE UNIQUE INDEX users_email_lower_unique ON users(LOWER(email));
```

Migration 001 `downgrade()` addition:

```sql
DROP INDEX users_email_lower_unique;
```

The application still normalises to lowercase before storage (fast path), but the DB now guarantees uniqueness even if that normalisation is skipped. This does not conflict with any existing architecture decision.

---

### MEDIUM

---

#### [LC-007] MEDIUM — `import_jobs` (`created_at` missing)

**Affected table/column:** `import_jobs.created_at`

**What is wrong:** Architecture §12.1 entity model explicitly lists three separate timestamp fields on `ImportJob`: `created_at`, `started_at`, `updated_at`. The schema omits `created_at`. While `started_at DEFAULT now()` doubles as the creation time for a BackgroundTask-triggered import (where the job is inserted and processing begins in the same request cycle), the two fields have distinct semantics:

- `created_at` — when the DB row was inserted
- `started_at` — when processing actually began (used by the stuck-job cleanup query: `started_at < now() - interval '1 hour'`)

If the architecture ever introduces a queued state before processing starts, or if a job is inserted and not immediately started, the single `started_at` conflates two events. Additionally, the data export (§10.7) uses `created_at` for all exported entities — `ImportJob` is included in the export and must have a `created_at` per the export field list.

Does not violate the P0 invariant.

**Recommendation:** Add to `CREATE TABLE import_jobs` in migration 005 before `started_at`:

```sql
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
```

The `downgrade()` drops `import_jobs` entirely, so no separate downgrade step is needed.

---

#### [LC-005] MEDIUM — `broker_configs` (`updated_at` missing for mutable entity)

**Affected table/column:** `broker_configs.updated_at`

**What is wrong:** Custom broker configs (`is_system = false`) are editable via `PATCH /api/v1/brokers/{id}`. The table has no `updated_at` column, making it impossible to determine when a custom config was last changed. This complicates audit queries, data exports, and debugging of fee calculation discrepancies. LC-005 requires mutable tables to have `updated_at`. The architecture §12.1 entity model does not list `updated_at` for `BrokerConfig` — making this a gap in the entity model itself that Stage 3 should have caught.

Does not violate the P0 invariant.

**Recommendation:** Add to `CREATE TABLE broker_configs` in migration 002:

```sql
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
```

Application must set `updated_at = now()` on every `PATCH`.

---

#### [PQ-003] MEDIUM — `users` (missing index for PDPA deletion cron query)

**Affected table/column:** `users.account_status`, `users.permanent_deletion_date`

**What is wrong:** The PDPA deletion cron (`process_deletions.py`) runs daily at 03:00 UTC with the query:

```sql
SELECT id FROM users
WHERE account_status = 'pending_deletion'
  AND permanent_deletion_date <= CURRENT_DATE;
```

No index exists on this column combination. At V1 scale (10,000 users) a sequential scan takes milliseconds, but as the table grows and `pending_deletion` rows accumulate, the query degrades. More critically, the cron triggers irreversible PDPA deletions — a slow scan that times out mid-batch could leave deletions in a partial state.

**Recommendation:** Add to migration 006:

```sql
CREATE INDEX idx_users_pending_deletion
    ON users(permanent_deletion_date)
    WHERE account_status = 'pending_deletion';
```

The partial condition keeps the index small — only rows actively awaiting deletion are indexed. Migration 006 `downgrade()` addition:

```sql
DROP INDEX idx_users_pending_deletion;
```

---

#### [MS-002] MEDIUM — `positions` (FK to `stocks` added as `VALID`, contradicting LDM-003 and Stage 3 Risk 4)

**Affected table/column:** `positions.stock_code`, migration 003

**What is wrong:** LDM-003 explicitly states: _"migration 003 adds the FK as NOT VALIDATED; a post-deployment validation step runs `ALTER TABLE positions VALIDATE CONSTRAINT positions_stock_code_fk` after the stock seeding script completes."_ Stage 3 Risk 4 repeats this recommendation. The actual DDL in migration 003, however, adds a fully validated FK:

```sql
ALTER TABLE positions
    ADD CONSTRAINT positions_stock_code_fk
    FOREIGN KEY (stock_code) REFERENCES stocks(code) ON DELETE RESTRICT;
```

On the very first deployment (migrations 001–007 applied to an empty database) this succeeds trivially because `positions` is empty. However, this pattern is unsafe in any non-initial deployment scenario: a staging environment restore, a developer running migrations incrementally, or any scenario where position rows exist before stocks are seeded will cause migration 003 to fail with a FK violation. The intended remedy is documented in the design decisions but not implemented in the DDL.

**Recommendation:** Change migration 003 `upgrade()` to use `NOT VALID`:

```sql
ALTER TABLE positions
    ADD CONSTRAINT positions_stock_code_fk
    FOREIGN KEY (stock_code) REFERENCES stocks(code) ON DELETE RESTRICT
    NOT VALID;
```

Add to the deployment runbook as a separate step after `scripts/seed_stocks.py` completes:

```sql
ALTER TABLE positions VALIDATE CONSTRAINT positions_stock_code_fk;
```

The `downgrade()` is unchanged (`DROP CONSTRAINT` still works). `NOT VALID` constraints are enforced on new `INSERT`/`UPDATE` but do not scan existing rows at addition time — this is backwards-compatible.

---

#### [NM-002] MEDIUM — `users.stripe_customer_id` (absent from Architecture §12.1 entity model)

**Affected table/column:** `users.stripe_customer_id`

**What is wrong:** The schema adds `stripe_customer_id TEXT UNIQUE` to the `users` table as an inference from the Stripe integration (webhook → user lookup). Architecture §12.1 entity model does not list this field on `User`. The only `stripe_customer_id` in the entity model appears on `SubscriptionRecord`. Stage 3 correctly flags this as Risk 1 ("confirm before migration 001 runs") but does not resolve it.

If `stripe_customer_id` should live only on `subscription_records`, the webhook handler must JOIN through `subscription_records` to find the user, and an index on `subscription_records(stripe_customer_id)` is required instead of the current `users(stripe_customer_id)` index. If it is correctly on `users`, §12.1 must be updated to reflect it.

This is an open architectural question, not a schema defect — but it must be resolved before migration 001 is finalised, because removing the column from `users` after launch is a destructive migration.

**Recommendation:** Confirm with the solution architect which table owns `stripe_customer_id` and update §12.1 accordingly. See Section 5 (Open Questions) for the decision options.

---

### LOW

---

#### [NM-003] LOW — All tables (`COMMENT ON COLUMN` DDL absent for non-obvious columns)

**Affected table/column:** `users.token_version`, `dividend_tranches.qualifying_shares`, `dividend_tranches.total_amount`, `broker_configs.is_system`, `system_config.value`

**What is wrong:** The schema document uses SQL inline comments (`-- ...`) throughout the `CREATE TABLE` blocks. These appear in the source files but are **not** stored in the PostgreSQL system catalog. A database administrator using `psql \d+`, pgAdmin, or any schema inspection tool will see column names and types only — the P0 invariant documentation on `qualifying_shares` and `total_amount`, the `token_version` semantics, and the `is_system` enforcement rule are invisible to any tool that reads the catalog. NM-003 specifically requires `COMMENT ON COLUMN` DDL statements for these fields.

**Recommendation:** Add to migration 006 (or a new migration `006a`):

```sql
COMMENT ON COLUMN users.token_version IS
    'Incremented on logout, password change, and deletion initiation. JWT middleware rejects tokens where jwt.token_version != user.token_version.';

COMMENT ON COLUMN dividend_tranches.qualifying_shares IS
    'P0 INVARIANT: stored at logging time. Must never be derived from current position share count. Only an explicit user edit of this tranche may change it.';

COMMENT ON COLUMN dividend_tranches.total_amount IS
    'P0 INVARIANT: stored at logging time as per_share_amount x qualifying_shares. Adding or editing lots must NOT trigger any recalculation of this value.';

COMMENT ON COLUMN broker_configs.is_system IS
    'true = system-seeded row, immutable, no user may modify or delete. false = user-created custom config. Enforcement at application layer only.';

COMMENT ON COLUMN system_config.value IS
    'Stored as TEXT regardless of semantic type. price_refresh_lock is NULL when no lock is held. bursa_holidays is a JSON array of ISO-8601 date strings.';
```

---

#### [LC-005b] LOW — `pending_email_notifications` (`updated_at` missing for mutable table)

**Affected table/column:** `pending_email_notifications.updated_at`

**What is wrong:** `pending_email_notifications` is mutated during the retry lifecycle: `attempt_count`, `sent_at`, and `next_retry_at` are all updated after creation. There is no `updated_at` column to track when the last state change occurred. Debugging stuck retry queues — including the PDPA pre-deletion gate that checks whether the confirmation email was delivered — is harder without an updated timestamp.

**Recommendation:** Add to `CREATE TABLE pending_email_notifications` in migration 001:

```sql
updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

Application must set `updated_at = now()` on every retry attempt and on final delivery confirmation.

---

#### [NM-001] LOW — `system_config`, `audit_log`, `system_deletion_log` (singular table names)

**Affected table/column:** Table names `system_config`, `audit_log`, `system_deletion_log`

**What is wrong:** NM-001 requires all table names to be `snake_case` plural. These three tables use singular names, inconsistent with all other tables in the schema (`users`, `lots`, `positions`, `dividend_tranches`, etc.). These names are inherited directly from Architecture §12.1 and Stage 2 decisions, so the inconsistency originates in the architecture documents rather than Stage 3.

**Recommendation:** If naming consistency is desired, rename at initial deployment before any application code is written:

| Current name          | Plural name            |
| --------------------- | ---------------------- |
| `system_config`       | `system_configs`       |
| `audit_log`           | `audit_logs`           |
| `system_deletion_log` | `system_deletion_logs` |

This requires updating the architecture documents and all application model references. Given that the names are architecture-specified and the fix is disruptive to upstream documents, this finding may be accepted as-is.

---

#### [NM-004] LOW — `stocks` (`updated_at` absent for admin-maintained table)

**Affected table/column:** `stocks.updated_at`

**What is wrong:** The `stocks` table is updated monthly by an admin script as new IPOs are listed and delistings occur. There is no `updated_at` column to record when a stock record was last modified. The architecture §12.1 entity model does not list `updated_at` for `Stock`, making this consistent with the spec. However, when debugging why a user's stock code fails validation (recently delisted? not yet seeded?), the absence of `updated_at` makes the admin script's history unverifiable from the DB catalog.

**Recommendation:** Add to `CREATE TABLE stocks` in migration 003:

```sql
updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

The admin import script should set `updated_at = now()` on each upsert.

---

## 3. Items Confirmed Correct

The following checklist items were reviewed and found to be correctly implemented. The engineering team can treat these as stable.

### FC — Financial Correctness (all items pass)

- **FC-001 — NUMERIC types:** Every monetary and rate column uses the exact `NUMERIC` precision specified in Architecture §12.3. Verified individually: `lots.purchase_price NUMERIC(12,4)`, `lots.brokerage_fee/clearing_fee/stamp_duty/all_in_cost/initial_amount NUMERIC(14,2)`, `dividend_tranches.per_share_amount NUMERIC(12,6)`, `dividend_tranches.total_amount NUMERIC(14,2)`, `price_snapshots.price NUMERIC(12,4)`, `broker_configs.rate NUMERIC(10,6)`, `broker_configs.minimum_fee/flat_fee NUMERIC(14,2)`, `subscription_records.amount NUMERIC(14,2)`. No `FLOAT`, `REAL`, or `DOUBLE PRECISION` found anywhere in the schema.

- **FC-002 — DividendTranche.total_amount immutability (P0):** `total_amount` is defined as `NUMERIC(14,2) NOT NULL` — a plain stored column. There are zero triggers, zero generated column definitions, and zero views anywhere in the schema document. The P0 invariant is fully protected by the schema. Any recalculation of `total_amount` from `lots.shares` would be an application-layer defect, not a schema defect.

- **FC-003 — qualifying_shares integrity:** `qualifying_shares INTEGER NOT NULL CONSTRAINT dividend_tranches_qualifying_shares_positive CHECK (qualifying_shares >= 1)` is correct and present. Supports the P0 invariant by ensuring the stored share count is always valid.

- **FC-004 — All four fee components stored individually:** `brokerage_fee`, `clearing_fee`, `stamp_duty`, and `all_in_cost` are all `NUMERIC(14,2) NOT NULL` stored columns on `lots`. None are generated columns. `all_in_cost` is stored independently and cannot be recomputed by the DB without an explicit application write.

- **FC-005 — Yield percentage absent:** No `yield_percentage`, `dividend_yield`, or equivalent column exists on any table. Yield is correctly deferred to query-time computation.

- **FC-006 — per_share_amount precision:** `NUMERIC(12,6)` correctly accommodates sub-cent dividend amounts such as RM0.004813.

- **FC-007 — purchase_price precision:** `NUMERIC(12,4)` correctly accommodates share prices such as RM8.3800.

- **FC-008 — ROUNDUP stamp duty compatibility:** `stamp_duty NUMERIC(14,2)` stores values computed by ROUNDUP to 0 decimal places (result is always a whole-RM multiple of the rate), then stored to 2 decimal places. No schema element forces rounding at storage time that would conflict with ROUNDUP semantics.

### DI — Data Integrity Constraints (all items pass except DI-011)

- **DI-001 — FK ON DELETE clauses:** Every foreign key in the schema has an explicit `ON DELETE` clause. No implicit `NO ACTION` was left undefined. Verified: `pending_tokens` (CASCADE), `pending_email_notifications` (CASCADE), `broker_configs.created_by_user_id` (RESTRICT), `portfolios` (RESTRICT), `positions.portfolio_id` (RESTRICT), `lots.position_id` (RESTRICT), `lots.broker_config_id` (RESTRICT), `dividend_tranches.position_id` (RESTRICT), stocks FK on positions (RESTRICT, added migration 003), `price_snapshots.stock_code` (RESTRICT), `price_snapshots.created_by_user_id` (RESTRICT), `audit_log` (CASCADE), `subscription_records` (SET NULL), `processed_webhook_events` (CASCADE), `import_jobs` (RESTRICT), `users.default_broker_config_id` (SET NULL).

- **DI-002 — users.account_status constraint:** `CHECK (account_status IN ('trial', 'active', 'grace_period', 'trial_expired', 'pending_deletion'))` matches the Architecture §12.5 state diagram exactly. All five states present; no extra or missing states.

- **DI-003 — price_snapshots.source:** `CHECK (source IN ('automated', 'manual', 'stale'))` correctly constrained.

- **DI-004 — broker_configs.fee_type:** `CHECK (fee_type IN ('percentage', 'flat'))` correctly constrained.

- **DI-005 — dividend_tranches.tranche_label:** `CHECK (tranche_label IN ('1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th'))` correctly constrained to 8 values.

- **DI-006 — lots share/price constraints:** `CHECK (shares >= 1)` and `CHECK (purchase_price > 0)` are both present.

- **DI-007 — pending_tokens.type:** `CHECK (type IN ('email_verification', 'password_reset', 'deletion_cancellation'))` correctly constrained.

- **DI-008 — import_jobs.status:** `CHECK (status IN ('processing', 'complete', 'failed'))` correctly constrained.

- **DI-009 — positions.category_tag:** `CHECK (category_tag IN ('Dividend', 'Volatile', 'Growth'))` correctly constrained.

- **DI-010 — processed_webhook_events.event_id as PK:** `event_id TEXT PRIMARY KEY` is the primary key, ensuring idempotency via the PK unique index (not just a secondary unique index).

- **DI-012 — broker_configs.is_system:** `is_system BOOLEAN NOT NULL DEFAULT false` — non-nullable with a safe default. Paired with the `broker_configs_system_ownership_check` constraint that enforces `(is_system = true AND created_by_user_id IS NULL) OR (is_system = false AND created_by_user_id IS NOT NULL)`.

- **DI-013 — pending_tokens single-use:** `used_at TIMESTAMPTZ` is nullable (no default, NULL = not yet used). The schema correctly represents unused vs. used state.

### LC — Lifecycle and State Management (all items pass except LC-007 and LC-005)

- **LC-001 — grace_period in account_status:** `grace_period` is present in the CHECK constraint, satisfying the Stripe billing model requirement.

- **LC-002 — PDPA deletion date columns:** `deletion_requested_date DATE` and `permanent_deletion_date DATE` are both present and nullable on `users`.

- **LC-003 — token_version:** `token_version INTEGER NOT NULL DEFAULT 0` is present on `users`. Session invalidation mechanism is in place.

- **LC-004 — version columns for optimistic locking:** `version INTEGER NOT NULL DEFAULT 1` is present on both `lots` and `dividend_tranches`. No other tables have this column (correct — only these two need optimistic locking per the architecture).

- **LC-006 — Soft-delete consistency:** `is_deleted BOOLEAN NOT NULL DEFAULT false` and `deleted_at TIMESTAMPTZ` (nullable) are consistently applied to all three soft-deletable tables: `positions`, `lots`, `dividend_tranches`. No deviations.

### PD — PDPA Compliance (all items pass)

- **PD-001 — subscription_records.user_id:** `UUID REFERENCES users(id) ON DELETE SET NULL` — nullable with SET NULL, enabling anonymisation while retaining the record for 7-year accounting retention.

- **PD-002 — system_deletion_log:** Present with `id UUID PK`, `deleted_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `reason TEXT NOT NULL DEFAULT 'PDPA erasure'`. No user PII columns. Architecture gap from Stage 1 has been resolved.

- **PD-003 — price_snapshots.created_by_user_id:** Nullable FK `REFERENCES users(id) ON DELETE RESTRICT`. NULL for automated/stale records; non-NULL for manual overrides. PDPA deletion correctly targets only manual overrides.

- **PD-004 — audit_log ON DELETE CASCADE:** `user_id UUID REFERENCES users(id) ON DELETE CASCADE` — cascade deletion is confirmed. The architecture §14.7 DDL snippet is matched exactly. Orphaned audit records with null `user_id` are correctly avoided.

- **PD-005 — pending_email_notifications.sent_at:** `sent_at TIMESTAMPTZ` (nullable) is present. The PDPA pre-deletion gate correctly queries `WHERE type='PDPA_DELETION_CONFIRMED' AND sent_at IS NOT NULL` to confirm email delivery before permanent deletion proceeds.

- **PD-006 — FK deletion order:** The FK structure correctly supports the 11-step PDPA deletion sequence from Architecture §13.5 without constraint violations. `DividendTranche` and `Lot` records reference `Position` (not `Portfolio` or `User` directly), enabling child deletion before parent in steps 5–6. Step 6a (custom `BrokerConfig` deletion) correctly follows step 6 (`Lot` deletion), satisfying the `lots.broker_config_id ON DELETE RESTRICT` constraint.

- **PD-007 — import_jobs.user_id:** `UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT` — explicit deletion in PDPA step 2, before the user row is removed.

### PQ — Performance and Query Correctness (all items pass except PQ-003)

- **PQ-001 — All §8.3 indexes present:** Every index required by Architecture §8.3 is present in migration 006. Verified individually: `idx_lots_position_active`, `idx_dividend_tranches_position_year_active`, `idx_price_snapshots_stock_date`, `idx_audit_log_user_id`, `idx_audit_log_entity`, `idx_import_jobs_user_status`, `idx_pending_tokens_user_type_active`, `idx_price_snapshots_manual_by_user`.

- **PQ-002 — Partial indexes on lots and dividend_tranches:** Both indexes use `WHERE is_deleted = false`, ensuring the index only covers active records. Dashboard aggregate queries filtered to non-deleted records will use these indexes without scanning soft-deleted rows.

- **PQ-004 — Price staleness query:** `idx_price_snapshots_stock_date ON price_snapshots(stock_code, trading_date DESC)` serves the dashboard query `SELECT ... FROM price_snapshots WHERE stock_code = ? ORDER BY trading_date DESC LIMIT 1` efficiently.

- **PQ-005 — stocks.code indexed:** `code TEXT PRIMARY KEY` creates an implicit unique B-tree index on `stocks(code)`, serving FK lookups from `positions` and `price_snapshots`.

### MS — Migration Safety (all items pass except MS-002)

- **MS-001 — FK dependency order:** Migration sequence is correct: `001 → users` (no deps); `002 → broker_configs → ALTER users → portfolios → positions → lots → dividend_tranches` (depends on 001); `003 → stocks → ALTER positions → price_snapshots` (depends on 002); `004 → system_config, audit_log, system_deletion_log` (depends on 001); `005 → subscription_records, processed_webhook_events, import_jobs` (depends on 001); `006 → indexes`; `007 → seed data`. No FK can be violated by this ordering.

- **MS-003 — BrokerConfig seed data:** Migration 007 contains all six system broker config rows (Maybank IB, CIMB Clicks, RHB Reflex, Rakuten Trade, Mirae Asset, M+ Online) with correct values matching Architecture §10.6.

- **MS-004 — SystemConfig seed data:** Migration 007 contains all five system config rows (`stamp_duty_rate`, `clearing_fee_rate`, `price_deviation_max_pct`, `bursa_holidays`, `price_refresh_lock`) with correct values.

- **MS-005 — Downgrade functions:** All seven migrations include `downgrade()` functions. Verified that each downgrade reverses exactly what the upgrade applied, in reverse order (e.g., migration 002 downgrade drops tables in reverse dependency order before dropping `broker_configs`, then drops the `default_broker_config_id` column from `users`).

- **MS-006 — pending_tokens.type constraint placement:** The CHECK constraint on `pending_tokens.type` is defined inline within the `CREATE TABLE` statement in migration 001, not as a deferred `ALTER TABLE`. Correct.

### NM — Naming and Maintainability (all items pass except NM-001, NM-002, NM-003)

- **NM-004 — is_deleted / deleted_at consistency:** `is_deleted BOOLEAN NOT NULL DEFAULT false` and `deleted_at TIMESTAMPTZ` (nullable, set on soft-delete, null otherwise) are applied consistently and identically across all three soft-deletable tables: `positions`, `lots`, `dividend_tranches`. No deviation in column name, type, or nullability.

---

## 4. Prioritised Change List

Changes required before implementation can proceed, ordered by severity.

### Must fix before launch

**1. [DI-011] HIGH — Replace case-sensitive email UNIQUE constraint with functional index**

Migration 001 change:

```sql
-- Remove from CREATE TABLE users:
CONSTRAINT users_email_unique UNIQUE (email)

-- Add after CREATE TABLE users (before CREATE TABLE pending_tokens):
CREATE UNIQUE INDEX users_email_lower_unique ON users(LOWER(email));
```

Migration 001 `downgrade()` addition:

```sql
DROP INDEX users_email_lower_unique;
```

**2. [LC-007] MEDIUM — Add `created_at` to `import_jobs`**

Migration 005 change — add to `CREATE TABLE import_jobs` before `started_at`:

```sql
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
```

**3. [LC-005] MEDIUM — Add `updated_at` to `broker_configs`**

Migration 002 change — add to `CREATE TABLE broker_configs` before the CHECK constraints:

```sql
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
```

**4. [PQ-003] MEDIUM — Add PDPA deletion cron index**

Migration 006 addition:

```sql
CREATE INDEX idx_users_pending_deletion
    ON users(permanent_deletion_date)
    WHERE account_status = 'pending_deletion';
```

Migration 006 `downgrade()` addition:

```sql
DROP INDEX idx_users_pending_deletion;
```

**5. [MS-002] MEDIUM — Change positions FK in migration 003 to `NOT VALID`**

Migration 003 change:

```sql
-- Change to:
ALTER TABLE positions
    ADD CONSTRAINT positions_stock_code_fk
    FOREIGN KEY (stock_code) REFERENCES stocks(code) ON DELETE RESTRICT
    NOT VALID;
```

Add to deployment runbook (run after `scripts/seed_stocks.py` completes):

```sql
ALTER TABLE positions VALIDATE CONSTRAINT positions_stock_code_fk;
```

**6. [NM-002] MEDIUM — Confirm placement of `stripe_customer_id` before finalising migration 001**

Decision required before migration 001 is run. See Section 5.

### Fix when convenient

**7. [NM-003] LOW — Add `COMMENT ON COLUMN` DDL**

Add to migration 006 (or new migration `006a`):

```sql
COMMENT ON COLUMN users.token_version IS
    'Incremented on logout, password change, and deletion initiation. JWT middleware rejects tokens where jwt.token_version != user.token_version.';

COMMENT ON COLUMN dividend_tranches.qualifying_shares IS
    'P0 INVARIANT: stored at logging time. Must never be derived from current position share count. Only an explicit user edit of this tranche may change it.';

COMMENT ON COLUMN dividend_tranches.total_amount IS
    'P0 INVARIANT: stored at logging time as per_share_amount x qualifying_shares. Adding or editing lots must NOT trigger any recalculation of this value.';

COMMENT ON COLUMN broker_configs.is_system IS
    'true = system-seeded row, immutable, no user may modify or delete. false = user-created custom config. Enforcement at application layer only.';

COMMENT ON COLUMN system_config.value IS
    'Stored as TEXT regardless of semantic type. price_refresh_lock is NULL when no lock is held. bursa_holidays is a JSON array of ISO-8601 date strings.';
```

**8. [LC-005b] LOW — Add `updated_at` to `pending_email_notifications`**

Migration 001 change — add to `CREATE TABLE pending_email_notifications`:

```sql
updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

**9. [NM-004] LOW — Add `updated_at` to `stocks`**

Migration 003 change — add to `CREATE TABLE stocks`:

```sql
updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

The admin seed script should set `updated_at = now()` on each upsert.

**10. [NM-001] LOW — Table naming inconsistency (optional)**

If naming consistency is required, rename `system_config → system_configs`, `audit_log → audit_logs`, `system_deletion_log → system_deletion_logs` in migrations 001/004. Requires updating all application model references. Accept as-is if architecture-specified names are to be preserved.

---

## 5. Open Questions

**OQ-001 [NM-002] — Where does `stripe_customer_id` live?**

`users.stripe_customer_id TEXT UNIQUE` is present in the schema but absent from Architecture §12.1 entity model. Stage 3 correctly flags this as Risk 1 but leaves it unresolved. The decision options are:

**Option A — Keep on `users`:** Simplest webhook handler (single `SELECT` on users by `stripe_customer_id`). Requires updating §12.1 to list this field. The current schema is correct as-is.

**Option B — Move to `subscription_records`:** Matches the entity model. Webhook handler must JOIN through `subscription_records`. Requires adding:

```sql
CREATE INDEX idx_subscription_records_stripe_customer
    ON subscription_records(stripe_customer_id)
    WHERE stripe_customer_id IS NOT NULL;
```

and removing `stripe_customer_id` from `users`.

**Decision required before migration 001 is finalised.** Removing `stripe_customer_id` from `users` after launch is a destructive migration.

---

**OQ-002 — Stock seeding and FK validation sequencing in the deployment runbook**

Finding MS-002 changes migration 003 to add the positions FK as `NOT VALID`. The deployment runbook must document a three-step initial deployment sequence:

```
Step 1: alembic upgrade head        (runs migrations 001–007)
Step 2: python scripts/seed_stocks.py
Step 3: psql -c "ALTER TABLE positions VALIDATE CONSTRAINT positions_stock_code_fk;"
```

Confirm whether the Render pre-deploy command can be extended to include steps 2 and 3, or whether a post-deploy hook executes them separately.

---

_End of Stage 4 — Schema Review Report_  
_Review by: Database reviewer (Stage 4 quality gate)_  
_Date: 2026-06-28_  
_Schema cleared for implementation subject to: 1 HIGH fix, 4 MEDIUM fixes, OQ-001 stakeholder decision_
