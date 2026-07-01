# BursaTrack — Database Design: Stage 2 Logical Data Modelling Decision Record

**Stage:** 2 of 3 — Logical Data Model Workshop  
**Date:** 2026-06-28  
**Input documents:** Stage 1 Domain Model Review Report; Solution Architecture v1.1 (§12.1, §12.3, §12.5, §13.5, §14.7); ADR-Summary v1.0  
**Output:** This Logical Data Modelling Decision Record (input to Stage 3)

---

## Decisions Already Made — Not Re-Opened Here

Per the orchestrator and solution architecture (ADR-004, ADR-005):

| Decision | Constraint for Stage 3 |
|----------|----------------------|
| Primary keys | UUID on all tables, `gen_random_uuid()` |
| Soft delete | `is_deleted BOOLEAN DEFAULT false` + `deleted_at TIMESTAMPTZ` on Position, Lot, DividendTranche |
| Optimistic locking | `version INTEGER NOT NULL DEFAULT 1` on Lot and DividendTranche only |
| Session invalidation | `token_version INTEGER NOT NULL DEFAULT 0` on User |
| Monetary type | `NUMERIC` exclusively — no float anywhere |
| Yield column | Never stored; computed at query time from `total_amount` and `all_in_cost` |
| Position aggregates | Computed at query time from Lot records; not stored on Position |
| Enum style | Constrained TEXT with CHECK constraints (not lookup tables) |
| Multi-tenancy | Single portfolio per user at V1; all financial data scoped through `portfolio_id → user_id` |
| Audit approach | Immutable, append-only `audit_log` table |
| No Redis | No caching schema concerns |

---

## LDM-001 — Position Aggregate Boundary

**Decision ID:** LDM-001  
**Topic:** Position as aggregate root governing Lots and DividendTranches

**Context:**  
The architecture defines Position as an aggregate root owning Lots (1:N) and DividendTranches (1:N). Dashboard aggregate queries (yield, total cost, total shares) require joining Position → Lots and Position → DividendTranches. The qualifying_shares validation rule also requires reading Lot data when creating a DividendTranche.

**Analysis:**  
The dashboard join pattern (Position → Lots → DividendTranches) is a read-across-aggregate operation performed in a single SQL query. This is safe because:
1. The consistency guarantee needed is write-consistency (Lot creation atomically stores all fee fields; DividendTranche creation atomically stores qualifying_shares and total_amount), not read-consistency between aggregates.
2. At read time, Lot and DividendTranche records are immutable snapshots — reading them together in one query is inherently consistent.

The qualifying_shares validation rule requires reading `SUM(lots.shares WHERE position_id = ? AND is_deleted = false)` before creating a DividendTranche. This read is within the same Position aggregate. The application must read the Lot sum within the same database transaction as the DividendTranche INSERT to prevent a race condition where another session adds a lot between the read and the insert (reducing the available share count). PostgreSQL's default READ COMMITTED isolation provides sufficient protection here: if a concurrent lot addition commits before the tranche INSERT, the sum read will include that lot.

**Decision:**  
The Position aggregate boundary is correct and complete. No changes needed. Write operations within the aggregate are performed in a single database transaction. Cross-aggregate read operations (e.g., joining Portfolio → Position → Lot for the dashboard) are safe at read time.

**Stage 3 Constraint:**  
- `lots.position_id` and `dividend_tranches.position_id` both reference `positions(id)` with `ON DELETE RESTRICT`
- No stored aggregate columns on positions (total_shares, total_all_in_cost, etc.)
- Dashboard queries must join lots and dividend_tranches; this is acceptable given the defined indexing strategy

---

## LDM-002 — DividendTranche total_amount Immutability (P0)

**Decision ID:** LDM-002  
**Topic:** Mechanism enforcing the qualifying_shares / total_amount invariant

**Context:**  
The P0 invariant: `total_amount` is stored at logging time as `per_share_amount × qualifying_shares` and must never be re-derived from the live position share count. The schema must not work against this invariant.

**Analysis:**  
Application-layer enforcement is the designated mechanism (ADR-004). The schema assists by:
1. Making both `qualifying_shares` and `total_amount` NOT NULL — the record cannot exist without these values
2. Adding a `CHECK (qualifying_shares >= 1)` constraint
3. Maintaining no triggers, generated columns, or views that touch these fields

The only code path that may update `total_amount` is the explicit user edit endpoint (`PUT /api/v1/positions/{id}/dividends/{id}`), which:
1. Reads the existing record (bumps version expectation)
2. Validates new qualifying_shares ≤ current position_total_shares
3. Recalculates: `new_total_amount = new_per_share_amount × new_qualifying_shares`
4. Writes: old qualifying_shares, old per_share_amount, old total_amount to audit_log as `previous_values`
5. Updates: dividend_tranche with new values and incremented version

What must NOT trigger total_amount recalculation:
- Adding a new Lot to the same Position
- Editing Lot shares or purchase price
- Any database-level mechanism (no triggers, no generated columns)

**Decision:**  
Application-layer enforcement is sufficient and required. Schema assistance: NOT NULL on `qualifying_shares` and `total_amount`; CHECK `qualifying_shares >= 1`. No triggers, generated columns, or views on `dividend_tranches` that touch these columns.

**Stage 3 Constraint:**  
- `dividend_tranches.qualifying_shares INTEGER NOT NULL CHECK (qualifying_shares >= 1)`
- `dividend_tranches.total_amount NUMERIC(14,2) NOT NULL`
- `dividend_tranches.per_share_amount NUMERIC(12,6) NOT NULL`
- Zero triggers on the `dividend_tranches` table
- Zero generated columns on `dividend_tranches`
- No database view that computes `total_amount` from `lots.shares`

---

## LDM-003 — Stock Reference Data (FK vs. Denormalised Text)

**Decision ID:** LDM-003  
**Topic:** Whether `positions.stock_code` carries a proper FK to `stocks(code)`

**Context:**  
The architecture includes a `stocks` table with `code TEXT PRIMARY KEY`. Positions reference `stock_code`. The question is whether this reference should be enforced at the database level.

**Analysis:**  
A proper FK (`positions.stock_code REFERENCES stocks(code)`) provides:
- Database-level referential integrity: no position can reference a non-existent stock code
- Clean validation at data load time (CSV import, API)

Stock delisting (`is_active = false`): existing positions must retain the FK reference (historical data integrity). The FK does not break on delistings because the stock row remains — only `is_active` changes. New lot creation against an inactive stock is blocked at the application layer (validation check: `stocks.is_active = true` before creating a new position or lot).

Monthly admin-script updates (new IPOs, delistings) add or update stock rows without disrupting existing FK relationships.

**Decision:**  
Use a proper FK. `positions.stock_code TEXT REFERENCES stocks(code) ON DELETE RESTRICT`. The `ON DELETE RESTRICT` prevents a stock row from being removed while positions exist (which would only happen by error; stock rows should never be hard-deleted).

**Complication — migration ordering:**  
The Stage 3 recommended migration plan places `portfolios`, `positions`, `lots`, `dividend_tranches` in migration 002 and `stocks` in migration 003. This creates a dependency conflict: `positions.stock_code` cannot reference `stocks(code)` if `stocks` is not yet created.

**Resolution:**  
Move `stocks` to migration 002 (before `positions`), or create `positions` without the FK in migration 002 and add the FK constraint via `ALTER TABLE` in migration 003. The additive ALTER TABLE approach is backwards-compatible and preferred to avoid restructuring the migration plan's module groupings.

**Stage 3 Constraint:**  
- `stocks` table created in migration 003 (pricing tables)
- `positions.stock_code TEXT NOT NULL` in migration 002 (no FK yet)
- `ALTER TABLE positions ADD CONSTRAINT positions_stock_code_fk FOREIGN KEY (stock_code) REFERENCES stocks(code) ON DELETE RESTRICT` in migration 003
- `stocks.code TEXT PRIMARY KEY` (natural key, not UUID — Bursa stock codes are the authoritative identifier)
- Application layer validates `stocks.is_active = true` before creating new positions or lots

---

## LDM-004 — PriceSnapshot Identity and Upsert Strategy

**Decision ID:** LDM-004  
**Topic:** Unique identity of a PriceSnapshot and UPSERT semantics

**Context:**  
Price snapshots are shared across all portfolios. The same stock has one price per trading day. The architecture describes UPSERT semantics for automated refreshes and manual overrides.

**Analysis:**  
The natural identity of a PriceSnapshot is `(stock_code, trading_date)`. This is confirmed by:
- The price refresh cron upserts on this pair
- Manual overrides target today's trading date
- The dashboard queries the most recent snapshot by `trading_date DESC`

Automated supersession of manual overrides: when the next trading day's cron runs successfully, it creates a new row for the new `trading_date`. The manual override for the previous day remains (it has a different `trading_date`) but is no longer the "current" price because it is not the latest by date. The UI always reads the most recent row. No `superseded_at` flag or soft-delete is required — the date ordering is the supersession mechanism.

Same-day UPSERT: if the cron runs and then a user enters a manual override on the same trading day, the manual override UPSERTs the same row (source changes to 'manual'). If the cron then runs again successfully on the same day (unlikely but possible), it would UPSERT back to 'automated'. The `ON CONFLICT` clause handles both directions.

`last_refreshed_at` lives on the PriceSnapshot row itself. It is updated on every UPSERT. The frontend's staleness check: `now() - last_refreshed_at > 28 hours`.

The architecture also mentions per-stock `last_refreshed_at` as the staleness signal. This is on the most recently UPSERTED row for that stock, found by querying `ORDER BY trading_date DESC LIMIT 1`.

**Decision:**  
UNIQUE constraint on `(stock_code, trading_date)`. UPSERT semantics for all writes (both automated and manual). `last_refreshed_at TIMESTAMPTZ NOT NULL DEFAULT now()` on the PriceSnapshot row, updated on every UPSERT. No `superseded_at` flag — date ordering is the supersession mechanism.

**Stage 3 Constraint:**  
- `UNIQUE (stock_code, trading_date)` on `price_snapshots` table
- `last_refreshed_at TIMESTAMPTZ NOT NULL DEFAULT now()` on `price_snapshots`
- Application uses `INSERT ... ON CONFLICT (stock_code, trading_date) DO UPDATE SET price = excluded.price, source = excluded.source, last_refreshed_at = excluded.last_refreshed_at, created_by_user_id = excluded.created_by_user_id`
- Dashboard query: `SELECT ... FROM price_snapshots WHERE stock_code = ? ORDER BY trading_date DESC LIMIT 1`

---

## LDM-005 — AuditLog Field Structure

**Decision ID:** LDM-005  
**Topic:** Internal structure of the `audit_log` table's metadata columns

**Context:**  
The architecture defines `audit_log` with a single `metadata JSONB` column containing `{previous_values: {...}, new_values: {...}, ip: "..."}`. The Stage 2 prompt asks whether `previous_values` and `new_values` should be separate top-level columns.

**Analysis:**  
The architecture's DDL snippet (§14.7) explicitly defines `metadata JSONB` as a single column with nested structure. This is the architectural specification. Re-opening this to split into separate columns would contradict the architecture doc.

Keeping as single `metadata JSONB`:
- Consistent with the architectural spec
- The PDPA data export must exclude IP addresses — this is handled at the application layer by excluding the `ip` field when building the export response, not by separate column

Action enum completeness: the architecture lists 18 specific audit events (§14.7). These are the complete enum for V1. No additional events are implied by the domain review beyond those listed.

Entity type completeness: the architecture shows `entity_type TEXT` with examples. From the domain review, the complete set of entity_type values required is: `User`, `Portfolio`, `Position`, `Lot`, `DividendTranche`, `PriceSnapshot`, `SystemConfig`, `ImportJob`. A CHECK constraint will enforce this.

**Decision:**  
Single `metadata JSONB` column per the architectural spec. A CHECK constraint on `action` enforces the 18-event enum. A CHECK constraint on `entity_type` enforces the known entity types. IP addresses in metadata are excluded from PDPA exports at the application layer.

**Stage 3 Constraint:**  
```
audit_log.action CHECK (action IN (
    'USER_REGISTERED', 'USER_LOGIN', 'PASSWORD_CHANGED',
    'LOT_CREATED', 'LOT_UPDATED', 'LOT_DELETED',
    'DIVIDEND_CREATED', 'DIVIDEND_UPDATED', 'DIVIDEND_DELETED',
    'PRICE_OVERRIDE_CREATED', 'IMPORT_COMPLETED',
    'SUBSCRIPTION_ACTIVATED', 'SUBSCRIPTION_CANCELLED',
    'DELETION_REQUESTED', 'DELETION_CANCELLED', 'ACCOUNT_DELETED',
    'CONFIG_UPDATED', 'DATA_EXPORT_DOWNLOADED'
))
audit_log.entity_type CHECK (entity_type IN (
    'User', 'Portfolio', 'Position', 'Lot', 'DividendTranche',
    'PriceSnapshot', 'SystemConfig', 'ImportJob'
))
```

---

## LDM-006 — SystemConfig Table Design

**Decision ID:** LDM-006  
**Topic:** Structure of the `system_config` key-value table

**Context:**  
The architecture uses `system_config` as a key-value store for operational settings: `stamp_duty_rate`, `clearing_fee_rate`, `price_deviation_max_pct`, `bursa_holidays`, `price_refresh_lock`. Values are heterogeneous: numeric rates (as decimal strings), JSON arrays, integers, and NULLs.

**Analysis:**  
A simple `key TEXT PRIMARY KEY / value TEXT / description TEXT / updated_at TIMESTAMPTZ` structure is sufficient. Rationale:
- All values can be stored as text strings and parsed by the application: numeric rates as `"0.001"`, JSON arrays as `"[]"`, NULL as SQL NULL
- The TTLCache in FastAPI caches parsed values in memory; the DB storage format is a serialisation detail
- Adding typed columns (rate NUMERIC, json_value JSONB) would complicate the schema for no benefit at V1

Write access: the admin config endpoint (`POST /admin/config`) is protected by `ADMIN_API_KEY`. This is enforced at the application layer, not at the database level. No database-level row security is required.

CONFIG_UPDATED audit event captures: `entity_type = 'SystemConfig'`, `entity_id = NULL` (no UUID PK), `metadata = {key: "stamp_duty_rate", previous_values: {"value": "0.001"}, new_values: {"value": "0.0012"}}`.

**Decision:**  
Simple key-value table with `key TEXT PRIMARY KEY`, `value TEXT`, `description TEXT`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Application parses values as needed. Write access enforced at application layer via ADMIN_API_KEY.

**Stage 3 Constraint:**  
- `system_config (key TEXT PRIMARY KEY, value TEXT, description TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT now())`
- `key TEXT PRIMARY KEY` — natural key, not UUID (system_config is the exception to the UUID PK rule alongside `stocks` and `processed_webhook_events`)
- Seed rows inserted in migration 007 via `op.execute()`

---

## LDM-007 — BrokerConfig Shared vs. Custom Ownership

**Decision ID:** LDM-007  
**Topic:** How system and custom broker configurations share one table and coexist under PDPA deletion

**Context:**  
The `broker_configs` table contains both system-seeded configs (`is_system = true`, `created_by_user_id = NULL`) and user-created custom configs (`is_system = false`, `created_by_user_id = user.id`). Users cannot modify or delete system configs.

**Analysis:**  
**Enforcement of system config immutability:** Application layer. Every PATCH/DELETE on a broker config checks `is_system = true` and rejects with HTTP 403. No database-level constraint can efficiently enforce this without a trigger (which the design avoids). Application layer is sufficient for V1.

**PDPA deletion order:** Stage 1 identified that the PDPA deletion order in §13.5 omits custom BrokerConfig deletion. The correct order:
1. Delete manual PriceSnapshots (step 1 in §13.5)
2. Delete ImportJobs (step 2)
3. Delete ProcessedWebhookEvents (step 3)
4. Delete PendingEmailNotifications (step 4)
5. Delete DividendTranches for user's positions (step 5)
6. Delete Lots for user's positions (step 6)
7. **[Gap resolved]** Delete custom BrokerConfigs for user (new step after Lots are removed)
8. Delete Positions for user's portfolio (step 7)
9. Delete Portfolio (step 8)
10. Anonymise SubscriptionRecord (step 9)
11. Insert system_deletion_log (step 10)
12. Delete User (triggers CASCADE on audit_log, pending_tokens) (step 11)

This order is safe because: Lots reference BrokerConfig (`lot.broker_config_id FK`). By the time we delete custom BrokerConfigs (step 7), all Lots for this user have already been hard-deleted (step 6). The `ON DELETE RESTRICT` on `lots.broker_config_id` is satisfied.

**Name uniqueness:** VR-014 states custom broker names must not duplicate system broker names. Enforced at application layer (query system broker names at validation time). No DB-level unique constraint across all broker names because two different users' custom configs may legitimately share a name.

**Decision:**  
`is_system BOOLEAN NOT NULL DEFAULT false` distinguishes the two types. `created_by_user_id UUID REFERENCES users(id) ON DELETE RESTRICT` links custom configs to their creator. System config protection enforced at application layer. PDPA deletion sequence adds custom BrokerConfig deletion after Lots are removed. Name uniqueness enforced at application layer.

**Stage 3 Constraint:**  
- `broker_configs.created_by_user_id REFERENCES users(id) ON DELETE RESTRICT`
- CHECK: `(is_system = true AND created_by_user_id IS NULL) OR (is_system = false AND created_by_user_id IS NOT NULL)`
- PDPA deletion: explicit `DELETE FROM broker_configs WHERE created_by_user_id = :user_id` after all lots are removed
- `lots.broker_config_id REFERENCES broker_configs(id) ON DELETE RESTRICT`

---

## LDM-008 — PendingToken Table Design

**Decision ID:** LDM-008  
**Topic:** Completeness of the pending_tokens design and cleanup strategy

**Context:**  
The architecture defines pending_tokens with `token_hash TEXT UNIQUE`, `type TEXT`, `user_id UUID`, `expires_at TIMESTAMPTZ`, `used_at TIMESTAMPTZ`. The question is whether a `UNIQUE (user_id, type)` constraint should be added at the database level.

**Analysis:**  
**UNIQUE (user_id, type) constraint:** Yes, this should be a database-level constraint. Reason: the application logic that deletes the old token before inserting a new one is not atomic by default — there is a race window where two concurrent requests (e.g., double-click) could both attempt to generate a token for the same user+type. The UNIQUE constraint causes the second INSERT to fail, which the application catches and retries or treats as a noop. This is a safety guard against a rare but possible race condition.

Implementation note: the application must DELETE the old token and INSERT the new one in a single transaction (or use `INSERT ... ON CONFLICT (user_id, type) DO UPDATE`). The UNIQUE constraint makes this work correctly.

**Raw token storage:** The raw token is NEVER stored. Only the SHA-256 hash is stored in `token_hash`. The raw token is sent to the user via email and discarded. This is confirmed by the architectural spec.

**Token expiry:** `expires_at TIMESTAMPTZ NOT NULL`. Check at validation time: `expires_at > now()`.

**Single-use:** `used_at TIMESTAMPTZ NULL`. Set to now() on first valid use. Subsequent uses rejected if `used_at IS NOT NULL`.

**Cleanup:** Include token cleanup in the `check_trial_expiry.py` cron (which already runs nightly at 01:00 UTC). Cleanup SQL: `DELETE FROM pending_tokens WHERE used_at IS NOT NULL OR expires_at < now() - INTERVAL '7 days'`. The 7-day buffer beyond expiry prevents any timing edge cases.

**Decision:**  
Design is complete with the addition of `UNIQUE (user_id, type)` as a database-level constraint. Token cleanup in the nightly cron. No other changes to the existing design.

**Stage 3 Constraint:**  
- `UNIQUE (user_id, type)` on `pending_tokens`
- `token_hash TEXT NOT NULL UNIQUE` (secondary unique constraint for lookup by hash)
- `expires_at TIMESTAMPTZ NOT NULL`
- `used_at TIMESTAMPTZ` (nullable; NULL = not yet used)
- Application uses DELETE + INSERT in a single transaction when issuing a new token for an existing (user_id, type)

---

## LDM-009 — PDPA Deletion Cascade Order

**Decision ID:** LDM-009  
**Topic:** Confirming the FK-correct PDPA hard-deletion order

**Context:**  
Architecture §13.5 specifies a deletion sequence for PDPA hard-delete. This decision maps each step to its FK relationships and confirms no constraint prevents the sequence.

**Analysis:**

The corrected and complete deletion order, with FK dependency notes:

| Step | Action | FK dependency |
|------|--------|---------------|
| 1 | DELETE manual PriceSnapshots WHERE created_by_user_id = user_id | `price_snapshots.created_by_user_id REFERENCES users(id) ON DELETE RESTRICT` — explicit DELETE required |
| 2 | DELETE ImportJobs WHERE user_id = user_id | `import_jobs.user_id REFERENCES users(id) ON DELETE RESTRICT` — explicit DELETE required |
| 3 | DELETE ProcessedWebhookEvents WHERE user_id = user_id | `processed_webhook_events.user_id REFERENCES users(id) ON DELETE CASCADE` — explicit DELETE or let CASCADE handle it |
| 4 | DELETE PendingEmailNotifications WHERE user_id = user_id | `pending_email_notifications.user_id REFERENCES users(id) ON DELETE CASCADE` — explicit DELETE or CASCADE |
| 5 | DELETE DividendTranches WHERE position_id IN (SELECT id FROM positions WHERE portfolio_id = user_portfolio_id) | FK: DividendTranche → Position → Portfolio; no direct cascade; explicit DELETE |
| 6 | DELETE Lots WHERE position_id IN (same subquery) | FK: Lot → Position → Portfolio; explicit DELETE; must occur before custom BrokerConfig deletion |
| 6a | DELETE custom BrokerConfigs WHERE created_by_user_id = user_id | `broker_configs.created_by_user_id REFERENCES users(id) ON DELETE RESTRICT` — explicit DELETE; safe only after step 6 |
| 7 | DELETE Positions WHERE portfolio_id = user_portfolio_id | FK: Position → Portfolio; explicit DELETE |
| 8 | DELETE Portfolio WHERE user_id = user_id | FK: Portfolio → User ON DELETE RESTRICT; explicit DELETE |
| 9 | SET subscription_records.user_id = NULL WHERE user_id = user_id | Anonymise, not delete; FK: ON DELETE SET NULL |
| 10 | INSERT INTO system_deletion_log (deleted_at, reason) VALUES (now(), 'PDPA erasure') | No FK (no PII); safe at any point after user data is removed |
| 11 | DELETE User WHERE id = user_id | Triggers CASCADE: audit_log (ON DELETE CASCADE), pending_tokens (ON DELETE CASCADE), pending_email_notifications (ON DELETE CASCADE), processed_webhook_events (ON DELETE CASCADE) |

**CASCADE opportunities:**  
The following FKs can use ON DELETE CASCADE (automatically cleaned up on user deletion):
- `audit_log.user_id REFERENCES users(id) ON DELETE CASCADE` — confirmed by architecture §14.7
- `pending_tokens.user_id REFERENCES users(id) ON DELETE CASCADE` — confirmed by architecture §14.1

The following cannot use CASCADE (require explicit DELETE before user deletion):
- `price_snapshots.created_by_user_id REFERENCES users(id) ON DELETE RESTRICT` — PDPA REQUIRES deletion; CASCADE to 'stale' automated records would be incorrect; explicit DELETE is mandatory
- `import_jobs.user_id REFERENCES users(id) ON DELETE RESTRICT` — must be explicitly deleted (step 2)
- `broker_configs.created_by_user_id REFERENCES users(id) ON DELETE RESTRICT` — must be explicitly deleted after lots are gone (step 6a)
- `lots.broker_config_id REFERENCES broker_configs(id) ON DELETE RESTRICT` — must be explicitly deleted before broker config deletion
- `positions.portfolio_id REFERENCES portfolios(id) ON DELETE RESTRICT` — explicit
- `portfolios.user_id REFERENCES users(id) ON DELETE RESTRICT` — explicit

**Decision:**  
Deletion order is confirmed as 11 steps (with step 6a added for custom BrokerConfigs). The CASCADE FKs on audit_log and pending_tokens handle cleanup automatically at step 11. All other deletions are explicit. The subscription_records anonymisation (step 9) uses `ON DELETE SET NULL` for the FK so it can be done as a regular UPDATE.

**Stage 3 Constraint:**  
- `audit_log.user_id REFERENCES users(id) ON DELETE CASCADE`
- `pending_tokens.user_id REFERENCES users(id) ON DELETE CASCADE`
- `pending_email_notifications.user_id REFERENCES users(id) ON DELETE CASCADE` (explicit DELETE in step 4, CASCADE as safety net)
- `processed_webhook_events.user_id REFERENCES users(id) ON DELETE CASCADE` (explicit DELETE in step 3, CASCADE as safety net)
- `subscription_records.user_id REFERENCES users(id) ON DELETE SET NULL`
- `price_snapshots.created_by_user_id REFERENCES users(id) ON DELETE RESTRICT`
- `import_jobs.user_id REFERENCES users(id) ON DELETE RESTRICT`
- `broker_configs.created_by_user_id REFERENCES users(id) ON DELETE RESTRICT`
- PDPA deletion procedure must be a single database transaction; full rollback on failure

---

## LDM-010 — ImportJob and Background Task Lifecycle

**Decision ID:** LDM-010  
**Topic:** ImportJob status values, stuck-job cleanup, and concurrent import policy

**Context:**  
The CSV import uses FastAPI BackgroundTasks with an `import_jobs` table for state tracking.

**Analysis:**  
**Status values:** Three states are sufficient: `processing`, `complete`, `failed`. No additional states are needed at V1. A `queued` state is unnecessary because the BackgroundTask starts immediately on request acceptance — there is no queue.

**Stuck-job cleanup:** Including cleanup in `check_trial_expiry.py` is acceptable for V1. The cleanup SQL: `UPDATE import_jobs SET status = 'failed', result_payload = '{"error": "timeout"}' WHERE status = 'processing' AND started_at < now() - INTERVAL '1 hour'`. Both cleanup steps are lightweight SQL — combining them in one cron job is operationally simpler than a dedicated cron for import cleanup.

**Concurrent import limit:** Only one active ImportJob (status='processing') per user at a time. The application should check for an existing processing job before creating a new one. If one exists: return the existing `job_id` with status='processing'. The DB should enforce this with a partial unique index: `UNIQUE (user_id) WHERE status = 'processing'`. This prevents a race condition where two concurrent upload requests both succeed in creating a processing job.

**result_payload:** JSONB column storing the outcome: success counts, error messages, or failure details. NULL while processing.

**Decision:**  
Status values: `processing`, `complete`, `failed`. Stuck-job cleanup in `check_trial_expiry.py` cron. Concurrent import limit enforced by partial unique index `UNIQUE (user_id) WHERE status = 'processing'` — application layer and DB both guard this.

**Stage 3 Constraint:**  
- `import_jobs.status TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'complete', 'failed'))`
- `import_jobs.result_payload JSONB` (nullable; set on completion or failure)
- `import_jobs.started_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- Partial unique index: `CREATE UNIQUE INDEX idx_import_jobs_one_processing_per_user ON import_jobs(user_id) WHERE status = 'processing'`

---

## Additional Resolution: system_deletion_log Table

**Context:** Stage 1 Gap 1 identified that `system_deletion_log` is referenced in §13.5 but not defined in §12.1.

**Decision:**  
Create `system_deletion_log` as a new table with no user PII. This is a compliance record, not a data record.

**Stage 3 Constraint:**  
```
CREATE TABLE system_deletion_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deleted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason TEXT NOT NULL DEFAULT 'PDPA erasure'
    -- No user_id, no email, no personal data
);
```

---

## Additional Resolution: processed_webhook_events.user_id

**Context:** Stage 1 Gap 2 identified that `processed_webhook_events` has no `user_id`, making PDPA deletion impossible without a JOIN.

**Decision:**  
Add `user_id UUID REFERENCES users(id) ON DELETE CASCADE` to `processed_webhook_events`. This enables direct PDPA deletion by user_id and is consistent with the architecture's intent (step 3 in §13.5 deletes these "for user").

**Stage 3 Constraint:**  
- `processed_webhook_events.user_id UUID REFERENCES users(id) ON DELETE CASCADE`
- Insert `user_id` when processing a webhook event (sourced from the Stripe customer lookup)

---

## Additional Resolution: Circular FK Between users and broker_configs

**Context:** Users have a `default_broker_config_id` FK to `broker_configs`. BrokerConfigs have `created_by_user_id` FK to `users`. This is a circular dependency that cannot be resolved in a single migration.

**Decision:**  
Two-phase migration:  
1. Migration 001: Create `users` WITHOUT the `default_broker_config_id` column  
2. Migration 002: Create `broker_configs` WITH `created_by_user_id REFERENCES users(id)`, then `ALTER TABLE users ADD COLUMN default_broker_config_id UUID REFERENCES broker_configs(id) ON DELETE SET NULL`

Both operations in migration 002 must succeed together. The downgrade reverses both.

**Stage 3 Constraint:**  
- Migration 001: `users` has no `default_broker_config_id`
- Migration 002: `broker_configs` created first; then `ALTER TABLE users ADD COLUMN default_broker_config_id UUID REFERENCES broker_configs(id) ON DELETE SET NULL`

---

## Additional Resolution: DividendTranche Tranche Label Uniqueness

**Context:** VR-007 (from Stage 1) states tranche_label must be unique per (position_id, year) for non-deleted tranches.

**Decision:**  
Enforce with a partial unique index (not a table constraint, since partial index is required for the WHERE clause):

```sql
CREATE UNIQUE INDEX idx_dividend_tranches_unique_label_per_position_year
    ON dividend_tranches(position_id, tranche_label, year)
    WHERE is_deleted = false;
```

This allows the same (position_id, tranche_label, year) combination to be reused if the original was soft-deleted (edge case: a user deletes a '3rd' tranche and re-enters it).

**Stage 3 Constraint:**  
This partial unique index is required in the indexes migration.

---

## Decisions Summary for Stage 3

| Decision | Outcome |
|----------|---------|
| LDM-001 | Position aggregate boundary confirmed; no changes |
| LDM-002 | Application-layer enforcement; schema assists with NOT NULL + CHECK; zero triggers |
| LDM-003 | FK to stocks; added via ALTER TABLE in migration 003; stocks uses TEXT PK |
| LDM-004 | UNIQUE (stock_code, trading_date); UPSERT semantics; last_refreshed_at on row |
| LDM-005 | Single metadata JSONB per architecture spec; action and entity_type CHECK constraints added |
| LDM-006 | Simple key TEXT PRIMARY KEY / value TEXT table; application parses |
| LDM-007 | Application layer guards system config; PDPA deletion adds step 6a for custom configs |
| LDM-008 | UNIQUE (user_id, type) added; token cleanup in nightly cron |
| LDM-009 | 11-step deletion order confirmed; CASCADE on audit_log and pending_tokens |
| LDM-010 | Three status values; partial unique index for concurrent import guard |
| Gap 1 | system_deletion_log table added (no PII) |
| Gap 2 | processed_webhook_events.user_id added |
| Circular FK | Two-phase migration for users ↔ broker_configs |
| Label uniqueness | Partial unique index on (position_id, tranche_label, year) WHERE is_deleted = false |

---

*End of Stage 2 — Logical Data Modelling Decision Record*  
*Proceed to Stage 3 — Physical Schema Design using this record and the Stage 1 Domain Model Review.*
