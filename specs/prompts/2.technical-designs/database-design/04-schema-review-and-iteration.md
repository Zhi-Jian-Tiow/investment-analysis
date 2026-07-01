# Stage 4 — Schema Review and Iteration

## Your Role and Task

You are an experienced database reviewer acting as the final quality gate before the BursaTrack schema reaches implementation. Your job is to find real problems — missing constraints, incorrect lifecycle handling, financial calculation risks, PDPA compliance gaps, and migration hazards — and produce actionable findings. This is a quality gate, not a rubber stamp.

Review the proposed schema as if you were the engineer who will maintain it in production and fix bugs caused by design flaws. Be specific. Be constructive. Prioritise.

---

## Documents Provided

You have been given:
- Stage 3 Physical Schema Design (the schema to review)
- Stage 1 Domain Model Review Report
- Stage 2 Logical Data Modelling Decision Record
- Solution Architecture Document

---

## Severity Taxonomy

Grade every finding using these levels. Be accurate — over-grading dilutes trust in the review.

| Severity | Definition | Examples |
|----------|------------|---------|
| **CRITICAL** | Data integrity failure, financial incorrectness, or PDPA non-compliance. Blocks implementation. | `total_amount` re-derived from live share count; float type on monetary column; missing PDPA deletion step |
| **HIGH** | Will cause incorrect behaviour or visible data errors in production, but does not corrupt existing data. Must be fixed before launch. | Missing index causing dashboard timeouts; missing version column blocking optimistic locking; missing CHECK constraint allowing invalid account status |
| **MEDIUM** | Edge case incorrectness, operational pain, or schema maintenance risk. Should be fixed before launch. | Missing column comment on non-obvious field; partial index absent where it would materially help; stuck-job cleanup gap |
| **LOW** | Naming inconsistency, minor style issue, or improvement opportunity. Fix when convenient. | Column named `created` instead of `created_at`; table name not plural; redundant constraint |

---

## Review Checklist

Work through each category systematically. For every finding, provide:
- **Finding ID**: Category prefix + sequential number (e.g., FC-001, DI-003)
- **Severity**
- **Affected table and column**
- **What is wrong**: Precise description
- **Recommendation**: Specific fix, including DDL if relevant

### Category FC — Financial Correctness

These are the highest-stakes checks. A single error here breaks BursaTrack's core value proposition.

- [ ] **FC-001**: Are all monetary and rate columns using `NUMERIC` with the precision specified in Architecture §12.3? Check every column individually — no `FLOAT`, `REAL`, or `DOUBLE PRECISION` anywhere.
- [ ] **FC-002**: Is `DividendTranche.total_amount` defined as a stored column, not a generated/computed column? Is there any trigger, generated column definition, or view that would re-derive `total_amount` from the current position share count?
- [ ] **FC-003**: Is `qualifying_shares` a stored `INTEGER NOT NULL` column on `DividendTranche`? Is it constrained with `CHECK (qualifying_shares >= 1)`?
- [ ] **FC-004**: Are all four fee components (`brokerage_fee`, `clearing_fee`, `stamp_duty`, `all_in_cost`) stored as individual columns on `Lot`? Is `all_in_cost` stored (not a generated column deriving from the others)?
- [ ] **FC-005**: Is yield percentage absent from every table definition? Yield must be computed at query time only.
- [ ] **FC-006**: Is `DividendTranche.per_share_amount` typed as `NUMERIC(12,6)` (6 decimal places for sub-cent dividend amounts such as RM0.004813)?
- [ ] **FC-007**: Is `Lot.purchase_price` typed as `NUMERIC(12,4)` (4 decimal places for prices such as RM8.3800)?
- [ ] **FC-008**: Does the schema design support the ROUNDUP stamp duty calculation? (This is application-layer arithmetic, but confirm no schema element would force rounding at storage time that conflicts with ROUNDUP semantics.)

### Category DI — Data Integrity Constraints

- [ ] **DI-001**: Do all FK relationships have an explicit `ON DELETE` clause? No implicit `NO ACTION` left undefined where the intent is `CASCADE`, `RESTRICT`, or `SET NULL`.
- [ ] **DI-002**: Is `users.account_status` constrained to `CHECK (account_status IN ('trial', 'active', 'grace_period', 'trial_expired', 'pending_deletion'))`? Does this match the lifecycle state diagram in Architecture §12.5 exactly?
- [ ] **DI-003**: Is `price_snapshots.source` constrained to `CHECK (source IN ('automated', 'manual', 'stale'))`?
- [ ] **DI-004**: Is `broker_configs.fee_type` constrained to `CHECK (fee_type IN ('percentage', 'flat'))`?
- [ ] **DI-005**: Is `dividend_tranches.tranche_label` constrained to `CHECK (tranche_label IN ('1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th'))`?
- [ ] **DI-006**: Is `lots.shares` constrained with `CHECK (shares >= 1)` and `lots.purchase_price` with `CHECK (purchase_price > 0)`?
- [ ] **DI-007**: Is `pending_tokens.type` constrained to `CHECK (type IN ('email_verification', 'password_reset', 'deletion_cancellation'))`?
- [ ] **DI-008**: Is `import_jobs.status` constrained to `CHECK (status IN ('processing', 'complete', 'failed'))`?
- [ ] **DI-009**: Is `positions.category_tag` constrained to `CHECK (category_tag IN ('Dividend', 'Volatile', 'Growth'))`?
- [ ] **DI-010**: Is `processed_webhook_events.event_id` the primary key (not just a unique index)? This is the idempotency mechanism for Stripe webhooks.
- [ ] **DI-011**: Is `users.email` unique? Is it normalised to lowercase before storage (application-layer concern, but the unique constraint must be case-insensitive or normalisation must be enforced)?
- [ ] **DI-012**: Is `broker_configs` protected against users modifying or deleting system rows? (The `is_system` flag must be present. Application-layer enforcement is stated in the architecture; confirm the column is non-nullable with a default.)
- [ ] **DI-013**: Is `pending_tokens` single-use? Is `used_at TIMESTAMPTZ` present and nullable (NULL = not yet used)?

### Category LC — Lifecycle and State Management

- [ ] **LC-001**: Does `users.account_status` include `grace_period`? This state is required by the Stripe billing model (Architecture §12.5 and §13.4) and is absent from the original BAS enum.
- [ ] **LC-002**: Are `permanent_deletion_date` and `deletion_requested_date` both present as nullable `DATE` columns on `users`? Both are required for the PDPA deletion workflow.
- [ ] **LC-003**: Is `token_version INTEGER NOT NULL DEFAULT 0` present on `users`? This is the session invalidation mechanism (Architecture §14.1).
- [ ] **LC-004**: Is `version INTEGER NOT NULL DEFAULT 1` present on both `lots` and `dividend_tranches`? This is the optimistic locking mechanism.
- [ ] **LC-005**: Do all tables that change state over time have `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`? Do mutable tables also have `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`?
- [ ] **LC-006**: Do soft-deleted tables (`positions`, `lots`, `dividend_tranches`) have both `is_deleted BOOLEAN NOT NULL DEFAULT false` and `deleted_at TIMESTAMPTZ` (nullable — set on soft-delete, null otherwise)?
- [ ] **LC-007**: Is `import_jobs` tracking `started_at`, `created_at`, and `updated_at` separately? The architecture needs `started_at` to identify stuck jobs (>1 hour in `processing` state).

### Category PD — PDPA Compliance

PDPA non-compliance is a CRITICAL finding. Every gap here must be fixed before the first user registers.

- [ ] **PD-001**: Is `subscription_records.user_id` nullable with `ON DELETE SET NULL`? This enables anonymisation (not deletion) during PDPA hard-delete, required for 7-year accounting record retention.
- [ ] **PD-002**: Is there a `system_deletion_log` table (or equivalent) for recording account hard-deletions with no PII? Architecture §13.5 requires an INSERT into this table before the user row is deleted.
- [ ] **PD-003**: Is `price_snapshots.created_by_user_id` a nullable FK to `users`? Manual price overrides must be attributed to the user for targeted PDPA deletion. Automated snapshots have `created_by_user_id = NULL`.
- [ ] **PD-004**: Does `audit_log` use `ON DELETE CASCADE` from `users`? The architecture explicitly states this (§14.7) — when a user is deleted, their audit_log rows are cascade-deleted atomically. `ON DELETE SET NULL` would leave orphaned audit records that are neither deleted nor attributed, violating PDPA.
- [ ] **PD-005**: Is `pending_email_notifications` present with a `sent_at` column? The PDPA deletion pre-gate (Architecture §13.5) checks that the PDPA confirmation email was successfully delivered before proceeding with permanent deletion. Without `sent_at`, this gate cannot function.
- [ ] **PD-006**: Does the FK deletion order in the schema support the Architecture §13.5 deletion sequence without FK constraint violations? Specifically: do Lot and DividendTranche records have FKs to Position (not directly to Portfolio or User), allowing them to be deleted before Position?
- [ ] **PD-007**: Is `import_jobs` linked to `user_id` with explicit deletion handling during PDPA hard-delete?

### Category PQ — Performance and Query Correctness

- [ ] **PQ-001**: Are all required indexes from Architecture §8.3 present? Check each one individually against the index list in Stage 3.
- [ ] **PQ-002**: Are indexes on `lots` and `dividend_tranches` partial (`WHERE is_deleted = false`)? Without the partial condition, indexes will scan deleted records on every dashboard query.
- [ ] **PQ-003**: Is there an index supporting the PDPA deletion job's query `SELECT id FROM users WHERE account_status = 'pending_deletion' AND permanent_deletion_date <= CURRENT_DATE`?
- [ ] **PQ-004**: Is there an index supporting the price staleness query? The dashboard computes staleness from `price_snapshots(stock_code, trading_date)` — confirm this index serves that lookup efficiently.
- [ ] **PQ-005**: Is the `stocks` table indexed on `code` (the natural key and FK target)? Is `code` the primary key, or is there a surrogate UUID PK with a separate unique index on `code`?

### Category MS — Migration Safety

- [ ] **MS-001**: Is the migration sequence ordered to respect FK dependency? Specifically: `users` must exist before `portfolios`; `portfolios` before `positions`; `positions` before `lots` and `dividend_tranches`; `broker_configs` before `lots`.
- [ ] **MS-002**: Are all V1 migrations additive only? No `ALTER TABLE ... NOT NULL` without a `DEFAULT`, no column drops, no type changes.
- [ ] **MS-003**: Is BrokerConfig seed data included in the migration sequence? System broker rows must be present before any user can create a portfolio.
- [ ] **MS-004**: Is SystemConfig seed data included in the migration sequence? The `stamp_duty_rate` and `clearing_fee_rate` rows must exist before any Lot can be created (they are read by the fee calculator).
- [ ] **MS-005**: Does every migration include a correct `downgrade()` function? A downgrade must undo exactly what the upgrade did, in reverse order.
- [ ] **MS-006**: Is the `pending_tokens.type` constraint applied correctly? If using a CHECK constraint, ensure the migration includes it as part of the `CREATE TABLE`, not as a deferred `ALTER TABLE` step.

### Category NM — Naming and Maintainability

- [ ] **NM-001**: Are all table names in `snake_case` plural (e.g., `dividend_tranches`, not `dividend_tranche` or `DividendTranches`)?
- [ ] **NM-002**: Are column names consistent with the entity model in Architecture §12.1? Flag any deviations.
- [ ] **NM-003**: Do non-obvious columns have `COMMENT ON COLUMN` statements? Specifically: `token_version`, `qualifying_shares`, `total_amount`, `is_system`, `price_refresh_lock`.
- [ ] **NM-004**: Is the distinction between `is_deleted` (soft-delete flag) and `deleted_at` (soft-delete timestamp) used consistently across all soft-deleted tables?

---

## Deliverable: Schema Review Report

### 1. Overall Assessment

One paragraph: Is this schema ready for implementation? What is the overall risk level? How many CRITICAL and HIGH findings were found?

### 2. Findings by Severity

List all findings, ordered CRITICAL → HIGH → MEDIUM → LOW. For each:

```
[FC-001] CRITICAL — lots.clearing_fee
Problem: Column is typed FLOAT(8) instead of NUMERIC(14,2). Float storage will
         produce rounding errors in fee calculations, breaking the product's core
         accuracy claim.
Fix:     ALTER TABLE lots ALTER COLUMN clearing_fee TYPE NUMERIC(14,2);
         (In a new migration; this is a type change requiring a backwards-incompatible
         migration with a downtime window.)
```

### 3. Items Confirmed Correct

List what you checked and found to be correctly implemented. This gives the engineering team confidence about what does not need to change.

### 4. Prioritised Change List

A numbered list of all changes required before implementation can proceed, ordered by severity. For CRITICAL and HIGH findings, include the specific DDL change.

### 5. Open Questions

List any items that require a stakeholder or architect decision before the schema can be finalised. Do not block on LOW findings — call them out but do not include them in the open questions list.

---

## Guardrails

- Be specific. "Consider adding an index" is not a finding. "The `dividend_tranches` table has no index on `(position_id, year, is_deleted)`. Dashboard queries that sum YTD dividend income for a user will perform a full table scan, violating the 3-second load time NFR for portfolios with large dividend histories." is a finding.
- Grade accurately. Not every issue is CRITICAL. Reserve CRITICAL for genuine data integrity failures, financial calculation errors, and PDPA non-compliance.
- Do not approve the schema just because it is technically plausible. It must match the documented requirements.
- Every finding about `DividendTranche` must explicitly state whether it violates the P0 invariant.
