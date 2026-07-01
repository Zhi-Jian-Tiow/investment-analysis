# Stage 2 — Logical Data Model: Decision Record

## Your Role and Task

You are a principal data architect producing the logical modelling decision record for BursaTrack. The solution architect has already made the major structural decisions. Your job in this stage is twofold:

1. **Validate** the architectural entity model against the domain model review — confirm it is complete and correct
2. **Complete** the decisions the architecture left implicit or underspecified

You are not re-opening closed architectural decisions. You are filling the gaps between the high-level entity model and the physical schema that must implement it.

---

## Documents Provided

You have been given:
- Stage 1 Domain Model Review Report
- Solution Architecture Document (entity model at §12.1, data types at §12.3, lifecycle at §12.5)
- Architecture Decision Records

---

## Decisions Already Made — Do Not Re-Open

These decisions were made by the solution architect. Treat them as constraints:

| Decision | Specification |
|----------|--------------|
| Primary keys | UUID on all tables using `gen_random_uuid()` |
| Soft delete | `is_deleted BOOLEAN DEFAULT false` + `deleted_at TIMESTAMPTZ` on Position, Lot, DividendTranche |
| Optimistic locking columns | `version INTEGER NOT NULL DEFAULT 1` on Lot and DividendTranche |
| Session invalidation column | `token_version INTEGER NOT NULL DEFAULT 0` on User |
| Monetary type | `NUMERIC` — no float anywhere in the stack |
| Yield column | Yield percentage is never stored; always computed from stored `total_amount` and `all_in_cost` values |
| Position aggregates | `total_shares`, `total_all_in_cost`, etc. are computed at query time from Lot records — not stored on Position |
| Enum style | Constrained `TEXT` columns with `CHECK` constraints (not lookup tables) |
| Multi-tenancy boundary | Single portfolio per user; all financial data scoped through `portfolio_id → user_id` |
| Audit approach | Immutable, append-only `audit_log` table; never updated or deleted except via PDPA hard-delete |
| No Redis | No caching is implemented at the schema level |

---

## Decisions to Make in This Stage

For each topic below, analyse the supplied documents and produce a decision record. Where the answer is unambiguous from the architecture or domain review, confirm it and state the constraint for Stage 3. Where the answer is genuinely open, present options with trade-offs and provide a recommendation.

---

### LDM-001 — Position Aggregate Boundary

The architecture shows Position as an aggregate root owning Lots and DividendTranches. Confirm this is correct and complete.

Specifically address:
- Are there any cross-aggregate access patterns that could create consistency problems? For example: does yield calculation require joining across Position, Lot, and DividendTranche in a single query? Is that safe under the aggregate boundary definition?
- The qualifying_shares validation rule states `qualifying_shares ≤ position_total_shares at the time of entry`. Since `position_total_shares` is derived from Lot records, this validation requires reading Lot data when creating a DividendTranche. Is this consistency requirement captured in the aggregate design?

### LDM-002 — DividendTranche total_amount Immutability

Confirm the mechanism that enforces the P0 invariant: `total_amount` is stored at logging time and never re-derived from the current position share count.

Address:
- Is application-layer enforcement sufficient, or should the schema assist? For example, is there a value in adding a database-level check (e.g., a NOT NULL constraint on `qualifying_shares` that makes the intent visible) even if the invariant itself is enforced in code?
- When the user explicitly edits a DividendTranche (changes `per_share_amount` or `qualifying_shares`), what is the correct mechanism? The application recalculates and stores the new `total_amount`. Is this the only code path that may update `total_amount`? What audit record must accompany this change?
- What does Stage 3 need to avoid? (No triggers, no generated columns, no views that compute `total_amount` from live share counts)

### LDM-003 — Stock Reference Data

The architecture includes a `stocks` table (code, name, market, sector, instrument_type, is_active). The Position entity references `stock_code`.

Decide:
- Should `Position.stock_code` be a proper foreign key to `stocks(code)`, or should it be stored as a denormalised text field with a separate validation step?
- What happens when a stock is delisted (`is_active = false`)? Should existing positions retain the link? Should new positions be blocked from referencing inactive stocks?
- The stock reference table will need periodic updates (new IPOs, delistings). The architecture describes a monthly admin-script update cadence. Does this affect the FK design?

### LDM-004 — PriceSnapshot Identity and Upsert Strategy

`PriceSnapshot` records are shared across all portfolios. The same stock code can have multiple price records over time.

Decide:
- What constitutes a unique price record for a given stock on a given trading day? Is it `(stock_code, trading_date)` with UPSERT semantics, or append-only with the latest record being the active one?
- When a manual override is superseded by an automated refresh, what happens to the manual record? Is it overwritten (UPSERT), marked with a `superseded_at` timestamp, or soft-deleted?
- The architecture states `last_refreshed_at` is used for staleness detection (>28 hours threshold). Where does this field live — on `PriceSnapshot` itself, or as a derived value from the most recent snapshot's `created_at`?

### LDM-005 — AuditLog Field Structure

The architecture defines `audit_log` with a `metadata JSONB` column but does not specify the internal structure of that JSON.

Decide:
- Should `previous_values` and `new_values` be top-level JSONB columns on `audit_log`, or nested within a single `metadata` object?
- What is the complete list of `action` values? The architecture lists 18 specific events (§14.7). Are these the complete enum, or are there additional events implied by the domain review?
- What is the complete list of `entity_type` values? Confirm the BAS-identified gap — `Position` must appear in the enum alongside `Lot`, `DividendTranche`, `User`, `SystemConfig`, `PriceSnapshot`.
- The PDPA data export must include audit log entries (§10.7). What metadata fields should be excluded from the export (e.g., raw IP addresses)?

### LDM-006 — SystemConfig Table Design

The architecture uses `SystemConfig` as a key-value store for operational settings: `stamp_duty_rate`, `clearing_fee_rate`, `bursa_holidays`, `price_deviation_max_pct`, `price_refresh_lock`.

Decide:
- Is a simple `key TEXT PRIMARY KEY / value TEXT / description TEXT / updated_at TIMESTAMPTZ` table sufficient, or does the heterogeneous value type (numeric rates, JSON arrays, timestamps, nulls) require a more structured approach?
- Who can write to `SystemConfig`? The architecture describes a separate `ADMIN_API_KEY` protecting the config endpoint. Should `SystemConfig` rows be writable only via the admin module? How is this enforced?
- Should a change to `SystemConfig` produce an `audit_log` entry? The architecture lists `CONFIG_UPDATED` as an audit event (§14.7). Confirm what fields are captured.

### LDM-007 — BrokerConfig Shared vs. Custom Ownership

System broker configs and user-created custom configs share the `broker_config` table, distinguished by `is_system BOOLEAN` and `created_by_user_id`.

Decide:
- How is it enforced that users cannot modify or delete system configs? (Application layer, database constraint, or both)
- What happens to a user's custom `BrokerConfig` when that user's account is PDPA hard-deleted? The Lot records that reference the custom config will be deleted first. After all Lots are deleted, the custom BrokerConfig is no longer referenced and can be safely deleted. Confirm this is the correct deletion order.
- Can a user's custom config have the same name as a system config? The BAS says no (VR-014). How is this enforced?

### LDM-008 — PendingToken Table Design

The architecture defines a `pending_tokens` table for password reset, email verification, and deletion cancellation tokens.

Decide:
- The architecture shows `token_hash TEXT NOT NULL UNIQUE` (SHA-256 of the raw token). Confirm: the raw token is never stored, only the hash. The expiry check is `expires_at TIMESTAMPTZ`. Single-use is enforced via `used_at TIMESTAMPTZ` (set on first use; null until used). Is this design complete?
- When a new token is generated for the same `(user_id, type)` pair, the architecture says the previous row is deleted before the new one is inserted. Is this application logic sufficient, or should a unique constraint on `(user_id, type)` enforce it at the database level?
- Token cleanup: expired and used tokens accumulate. How are they cleaned up? Is a periodic sweep in the `check_trial_expiry.py` cron job appropriate?

### LDM-009 — PDPA Deletion Cascade Order

The architecture specifies a hard-deletion order (§13.5). Confirm this order is consistent with FK relationships and that no FK constraint prevents deletions from proceeding in the stated order.

Map each deletion step to the FK relationships it depends on:
1. Lot price overrides (manual PriceSnapshot records where `created_by_user_id = user_id`)
2. ImportJob records
3. ProcessedWebhookEvent records
4. PendingEmailNotification records
5. DividendTranche records (for user's positions)
6. Lot records (for user's positions)
7. Position records (for user's portfolio)
8. Portfolio record
9. SubscriptionRecord: SET `user_id = NULL` (anonymise)
10. system_deletion_log: INSERT (before User delete)
11. User record (CASCADE removes audit_log rows automatically via ON DELETE CASCADE FK)
12. Custom BrokerConfig records (owned by user)

Identify any FK constraint that requires a different deletion order. Identify any explicit DELETE statements that can be replaced by CASCADE behaviour.

### LDM-010 — ImportJob and Background Task Lifecycle

The CSV import uses a `BackgroundTask` in FastAPI. The `import_jobs` table tracks state.

Decide:
- What are the valid `status` values for an `ImportJob`? (processing, complete, failed — are there others?)
- The architecture describes a stuck-job cleanup in `check_trial_expiry.py` that marks processing jobs older than 1 hour as failed. This introduces a dependency between two different cron jobs. Confirm this is the right approach, or whether the import job should have its own dedicated cleanup.
- When a user triggers a new CSV import while one is already `processing`, what happens? Is only one active import allowed per user at a time?

---

## Deliverable: Logical Data Modelling Decision Record

For each decision (LDM-001 through LDM-010), produce a structured record:

**Decision ID**: LDM-NNN  
**Topic**: Short descriptive title  
**Context**: Why this decision matters for BursaTrack  
**Analysis**: What the architecture and domain review say; any gaps or contradictions  
**Options** (if multiple viable approaches exist): With trade-offs  
**Decision**: The recommended approach, with rationale  
**Stage 3 Constraint**: The specific requirement this places on physical schema design  
**Open questions** (if any remain unresolved)

---

## Guardrails

- Do not re-open any decision listed under "Decisions Already Made"
- Do not write DDL or SQL — that is Stage 3
- Do not invent entities or attributes not present in the supplied documents
- Every decision that touches `DividendTranche` must explicitly address the P0 invariant
- Prefer confirming what the architecture already implies over introducing new options
