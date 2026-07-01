# BursaTrack — Database Design: Stage 1 Domain Model Review

**Stage:** 1 of 3 — Domain Model Review  
**Date:** 2026-06-28  
**Input documents:** PRD v2.0, BAS-Enhanced Parts 1–3 v2.0, Solution Architecture v1.1, ADR-Summary v1.0  
**Output:** This Domain Model Review Report (input to Stage 2)

---

## 1. Executive Summary

### What BursaTrack Must Persist

BursaTrack is fundamentally a financial ledger. It must persist:

1. **User accounts** with a multi-state lifecycle (trial → active → grace_period → trial_expired → pending_deletion → hard-deleted)
2. **Portfolio and position records**: what stocks a user holds, in what quantities, acquired at what cost, through which broker
3. **Lot-level transaction data** with every fee component individually stored and immutable after creation (unless explicitly edited)
4. **Dividend tranche records** with `qualifying_shares` and `total_amount` stored at logging time — never re-derived from the live position share count
5. **Price snapshots**: end-of-day market prices per stock, with provenance (automated, manual, stale) and staleness timestamps
6. **Broker fee configurations**: system-seeded presets and user-created custom configurations
7. **Stock reference data**: the list of valid Bursa-listed securities for input validation
8. **Operational configuration**: externally-configurable fee rates and system parameters
9. **Audit records**: an immutable log of every sensitive data mutation, required for PDPA accountability
10. **Subscription and billing metadata**: Stripe customer/subscription IDs, webhook idempotency keys
11. **Background job state**: CSV import job status, pending email notifications, one-time tokens

### Top Three Correctness Risks

**Risk 1 — P0: Dividend total_amount re-derivation (qualifying_shares invariant)**  
The product corrects a documented defect in the original Excel model where dividend total income was derived from the live share count, causing retroactive corruption when new lots were added. The fix stores `total_amount` and `qualifying_shares` at logging time. Any code path, trigger, generated column, or view that re-derives `total_amount` from the current position share count reintroduces the defect. This is the single highest-severity correctness risk.

**Risk 2 — Floating-point monetary arithmetic**  
All monetary values must be stored with exact decimal arithmetic (NUMERIC in PostgreSQL). Use of FLOAT, REAL, or DOUBLE PRECISION for any fee component, cost basis, or dividend amount will eventually produce rounding errors that violate the product's core claim of provable accuracy.

**Risk 3 — Yield denominator using pre-fee cost**  
The product explicitly corrects a yield calculation bug where the denominator was the pre-fee initial purchase amount rather than the all-in cost (initial + brokerage + clearing + stamp duty). The schema must ensure `all_in_cost` is stored per lot and that yield is always computed from `SUM(all_in_cost)`, not from `SUM(initial_amount)`.

---

## 2. Business Entities and Value Objects

### 2.1 Entities (Own Identity and Lifecycle)

| Entity                        | Scope                      | Lifecycle management                                                     |
| ----------------------------- | -------------------------- | ------------------------------------------------------------------------ |
| **User**                      | User-scoped (is the owner) | Full: trial → active → pending_deletion → hard-deleted                   |
| **Portfolio**                 | User-scoped                | Created at registration; hard-deleted on PDPA                            |
| **Position**                  | User-scoped                | Soft-deleted by user; hard-deleted on PDPA                               |
| **Lot**                       | User-scoped                | Soft-deleted with position; hard-deleted on PDPA                         |
| **DividendTranche**           | User-scoped                | Soft-deleted with position; hard-deleted on PDPA                         |
| **PriceSnapshot** (automated) | System-shared              | Upserted daily by cron; retained permanently                             |
| **PriceSnapshot** (manual)    | Per-user                   | Created by user; hard-deleted on PDPA                                    |
| **BrokerConfig** (system)     | System-shared              | Seeded at deployment; not deletable                                      |
| **BrokerConfig** (custom)     | User-scoped                | Created by user; hard-deleted on PDPA after referencing lots are removed |
| **Stock**                     | System-shared              | Seeded; updated by admin; retained permanently                           |
| **SystemConfig**              | System-shared              | Seeded; updated by admin; retained permanently                           |
| **AuditLog**                  | User-scoped                | Append-only; CASCADE-deleted when user is hard-deleted                   |
| **ImportJob**                 | User-scoped                | Created at import start; hard-deleted on PDPA                            |
| **PendingToken**              | User-scoped                | Short-lived; CASCADE-deleted when user is hard-deleted                   |
| **PendingEmailNotification**  | User-scoped                | Retry queue for critical emails; hard-deleted on PDPA                    |
| **ProcessedWebhookEvent**     | Per-user (Stripe)          | Idempotency key; hard-deleted on PDPA                                    |
| **SubscriptionRecord**        | Per-user (billing)         | Anonymised (user_id → NULL) on PDPA; retained 7 years                    |
| **SystemDeletionLog**         | System (no PII)            | Records PDPA deletions; no user linkage; retained                        |

### 2.2 Value Objects (Defined by Attributes, No Own Identity)

| Concept                                                          | Where it lives                 | Why not a standalone entity                                        |
| ---------------------------------------------------------------- | ------------------------------ | ------------------------------------------------------------------ |
| **Fee breakdown** (brokerage, clearing, stamp duty, all_in_cost) | Columns on `Lot`               | Inseparable from the lot transaction; no independent lifecycle     |
| **Qualifying shares** and **total amount** on DividendTranche    | Columns on `DividendTranche`   | Part of the tranche record; they don't exist independently         |
| **Account status transition**                                    | State on `User.account_status` | A state transition, not a persistent entity at V1                  |
| **Position aggregates** (total_shares, blended_price, yield)     | Derived at read time           | Never stored; always computed from Lot and DividendTranche records |

---

## 3. Aggregate Roots and Ownership Boundaries

### 3.1 User Aggregate

**Root:** `User`  
**Owns:** `Portfolio` (1:1), `PendingToken` (1:N), `PendingEmailNotification` (1:N), custom `BrokerConfig` (1:N)

**Consistency boundary:**  
Account status transitions must be atomic with their audit log entries. Password changes must atomically update `password_hash` and increment `token_version`.

**Invariants:**

- At most one active `Portfolio` per User at V1
- `token_version` incremented on: logout, password change, deletion initiation
- `trial_expiry_date = trial_start_date + 14 days` (set at registration, not recomputed)

---

### 3.2 Position Aggregate

**Root:** `Position`  
**Owns:** `Lot` (1:N), `DividendTranche` (1:N)

**Consistency boundary:**

- Creating a Lot: initial amount, all fee components, and all_in_cost must be stored atomically with the Lot record. There is no valid intermediate state where a Lot exists without its fee data.
- Creating a DividendTranche: `qualifying_shares` and `total_amount` must be stored atomically. The validation that `qualifying_shares ≤ position_total_shares` requires reading the Lot records (computing `SUM(lots.shares WHERE is_deleted=false)`). This read is within the same aggregate boundary.
- Soft-deleting a Position must soft-delete all child Lots and DividendTranches atomically.

**Invariants:**

- **P0 CRITICAL**: `DividendTranche.total_amount` is stored at logging time as `per_share_amount × qualifying_shares`. It MUST NOT be recomputed when Lot records change. Only an explicit user edit of the tranche may change it.
- Maximum 8 active DividendTranches per `(position_id, year)` combination.
- `qualifying_shares ≥ 1` on every DividendTranche.
- `Lot.shares ≥ 1` on every Lot.

---

### 3.3 Pricing Aggregate (System-Shared)

**Root:** `PriceSnapshot`  
**Owns:** Nothing (standalone record per stock per trading day)

**Consistency boundary:**  
The price refresh cron upserts one `PriceSnapshot` per `(stock_code, trading_date)`. The `(stock_code, trading_date)` pair is the identity key for upsert semantics.

**Invariants:**

- One active PriceSnapshot per stock per trading day.
- `source` values: `automated` (cron refresh), `manual` (user override), `stale` (refresh attempted but failed).
- `last_refreshed_at` records when the snapshot was last written; used by the frontend for staleness detection (> 28 hours threshold).

---

## 4. Entity Lifecycle and State Transitions

### 4.1 User Account Lifecycle

```
[Registration]
     │
     ▼
  trial ──────────────────────────────────────────────────────┐
     │                                                        │
     │  checkout.session.completed (Stripe webhook)           │  trial_expiry_date <= CURRENT_DATE
     ▼                                                        │  (check_trial_expiry.py cron, 01:00 UTC)
  active                                                      ▼
     │  ◄──── invoice.payment_succeeded (Stripe)       trial_expired
     │                                                        │
     │  invoice.payment_failed (Stripe)                       │  User subscribes
     ▼                                                        │  (checkout.session.completed)
grace_period ──► trial_expired                                │
     │           (customer.subscription.deleted)              │
     │                                                        │
     │  All states (except pending_deletion) ─────────────────┘
     │
     │  User initiates deletion (from any active state)
     ▼
pending_deletion
     │
     │  User clicks cancellation link within 30 days
     ├──────────────────────────────► restored to previous status
     │
     │  30-day window expires
     ▼
[HARD DELETED] — all user data permanently removed
```

**Data recorded at each transition:**

| Transition                   | Data recorded                                                                                                                                                                                                 |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Registration                 | User row created; Portfolio row created; audit_log (USER_REGISTERED); verification token created                                                                                                              |
| trial → active               | account_status updated; subscription_start_date, subscription_renewal_date set; audit_log (SUBSCRIPTION_ACTIVATED)                                                                                            |
| active → grace_period        | account_status updated; Sentry alert; email notification sent                                                                                                                                                 |
| grace_period → active        | account_status updated; subscription_renewal_date updated from Stripe `current_period_end`                                                                                                                    |
| Any → trial_expired          | account_status updated                                                                                                                                                                                        |
| Any → pending_deletion       | account_status updated; deletion_requested_date, permanent_deletion_date set; token_version incremented; audit_log (DELETION_REQUESTED); PDPA deletion confirmation email sent to pending_email_notifications |
| pending_deletion → restored  | account_status restored to previous; permanent_deletion_date cleared; audit_log (DELETION_CANCELLED)                                                                                                          |
| pending_deletion → [deleted] | Full PDPA hard-delete; audit_log (ACCOUNT_DELETED) inserted before user row removed                                                                                                                           |

---

### 4.2 Position / Lot Lifecycle

| Event                              | Data recorded                                                                                                                |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Position created (first lot added) | Position row created; Lot row with all fee components; audit_log (LOT_CREATED)                                               |
| Lot added to existing position     | Lot row with all fee components; audit_log (LOT_CREATED)                                                                     |
| Lot edited                         | Previous values in audit_log (LOT_UPDATED); version incremented; Lot updated with recalculated fees                          |
| Position soft-deleted              | is_deleted=true, deleted_at=now() on Position; same on all child Lots and DividendTranches; audit_log (LOT_DELETED for each) |
| PDPA erasure                       | All Positions, Lots, DividendTranches for user hard-deleted (explicit DELETE statements)                                     |

---

### 4.3 DividendTranche Lifecycle

| Event                             | Data recorded                                                                                                                                              |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tranche created                   | qualifying_shares and total_amount STORED atomically; audit_log (DIVIDEND_CREATED)                                                                         |
| Tranche explicitly edited by user | Previous qualifying_shares, per_share_amount, total_amount in audit_log (DIVIDEND_UPDATED); total_amount recalculated from new inputs; version incremented |
| New Lot added to same position    | **No change to any DividendTranche** — this is the P0 invariant                                                                                            |
| Lot share count edited            | **No change to any DividendTranche** — existing total_amounts reflect qualifying_shares at logging time                                                    |
| Tranche soft-deleted              | is_deleted=true, deleted_at=now(); audit_log (DIVIDEND_DELETED)                                                                                            |
| PDPA erasure                      | Hard-deleted with parent position                                                                                                                          |

---

### 4.4 PriceSnapshot Lifecycle

| Event                            | Behaviour                                                                                                   |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Daily cron (automated) — success | UPSERT on (stock_code, trading_date): price, source='automated', last_refreshed_at=now()                    |
| Daily cron (automated) — failure | UPSERT on (stock_code, trading_date): source='stale' (price unchanged from last known)                      |
| User manual override             | UPSERT on (stock_code, today's trading_date): price, source='manual', created_by_user_id=user_id            |
| Next day's cron — success        | New UPSERT for next trading_date; previous day's manual record remains but is no longer the "current" price |
| PDPA user deletion               | DELETE WHERE created_by_user_id = deleted_user_id (manual overrides only; automated records retained)       |

---

### 4.5 ImportJob Lifecycle

| Status       | Meaning                                | Next state                    |
| ------------ | -------------------------------------- | ----------------------------- |
| `processing` | BackgroundTask running                 | → `complete` or `failed`      |
| `complete`   | All records created successfully       | Terminal                      |
| `failed`     | Validation failed or transaction error | Terminal; user must re-upload |

Stuck jobs (status='processing' for > 1 hour) are transitioned to 'failed' by the `check_trial_expiry.py` cron cleanup step.

---

### 4.6 PendingToken Lifecycle

| Event                                   | Behaviour                                                                                   |
| --------------------------------------- | ------------------------------------------------------------------------------------------- |
| New token generated for (user_id, type) | Previous row for same (user_id, type) deleted; new row inserted with token_hash, expires_at |
| User uses token                         | used_at set to now(); reuse rejected                                                        |
| Token expires                           | expires_at < now(); rejected on validation                                                  |
| Cleanup (cron)                          | DELETE WHERE expires_at < now() - 7 days OR used_at IS NOT NULL                             |
| User hard-deleted                       | CASCADE deletes all pending_tokens for user                                                 |

---

## 5. Business Rules and Invariants

### Financial Correctness Rules

| Rule ID        | Rule                                                                                                                                                        | Applies when                   | Classification        |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | --------------------- |
| **FCR-001**    | brokerage = MAX(initial_amount × rate, minimum_fee) for percentage brokers                                                                                  | Lot creation or edit           | Financial correctness |
| **FCR-002**    | brokerage = flat_fee for flat-fee brokers                                                                                                                   | Lot creation or edit           | Financial correctness |
| **FCR-003**    | Brokerage applied once per lot transaction, not per position                                                                                                | Lot creation or edit           | Financial correctness |
| **FCR-004**    | clearing_fee = initial_amount × 0.0003; capped at RM1,000 per lot                                                                                           | Lot creation or edit           | Financial correctness |
| **FCR-005**    | stamp_duty = ROUNDUP(initial_amount / 1000, 0) × RM1; minimum RM1                                                                                           | Lot creation or edit           | Financial correctness |
| **FCR-006**    | all_in_cost = initial_amount + brokerage_fee + clearing_fee + stamp_duty                                                                                    | Lot creation or edit           | Financial correctness |
| **FCR-007**    | All MYR amounts rounded half-away-from-zero to 2dp; each fee component rounded before summing                                                               | All monetary calculations      | Financial correctness |
| **FCR-008**    | Stamp duty rate is read from system_config, not hard-coded                                                                                                  | Fee calculation                | Compliance            |
| **P0-CRIT-01** | DividendTranche.total_amount = per_share_amount × qualifying_shares, stored at logging time; never recomputed from live share count                         | Tranche creation and existence | **P0 CRITICAL**       |
| **FCR-009**    | qualifying_shares stored at logging time; may be overridden by user at logging time; defaults to position_total_shares at the moment of logging             | Tranche creation               | Financial correctness |
| **FCR-010**    | yield = SUM(DividendTranche.total_amount WHERE is_deleted=false AND year=current_year) / SUM(Lot.all_in_cost WHERE is_deleted=false); computed at read time | Dashboard query                | Financial correctness |

### Validation Rules

| Rule ID    | Rule                                                                              | Scope                             |
| ---------- | --------------------------------------------------------------------------------- | --------------------------------- |
| **VR-001** | qualifying_shares ≥ 1                                                             | DividendTranche creation and edit |
| **VR-002** | qualifying_shares ≤ position_total_shares at time of entry                        | DividendTranche creation and edit |
| **VR-003** | lot.shares ≥ 1, must be integer                                                   | Lot creation and edit             |
| **VR-004** | lot.purchase_price > 0                                                            | Lot creation and edit             |
| **VR-005** | Maximum 8 DividendTranches per (position_id, year) where is_deleted=false         | Tranche creation                  |
| **VR-006** | tranche_label must be in ('1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th') | Tranche creation                  |
| **VR-007** | tranche_label unique per (position_id, year) where is_deleted=false               | Tranche creation                  |
| **VR-008** | stock_code must reference an active stock in the stocks reference table           | Position creation                 |
| **VR-009** | DividendTranche.per_share_amount > 0                                              | Tranche creation and edit         |

### Workflow Rules

| Rule ID    | Rule                                                                                          |
| ---------- | --------------------------------------------------------------------------------------------- |
| **WR-001** | Soft-delete: Position, Lot, DividendTranche use is_deleted + deleted_at                       |
| **WR-002** | Soft-deleting a Position must soft-delete all child Lots and DividendTranches atomically      |
| **WR-003** | One portfolio per user at V1                                                                  |
| **WR-004** | CSV import is atomic: all records succeed or none are created                                 |
| **WR-005** | Optimistic locking on Lot and DividendTranche via version column (reject on version mismatch) |
| **WR-006** | Only one active ImportJob (status='processing') per user at a time                            |
| **WR-007** | Manual price override superseded when next automated refresh succeeds for that trading day    |

### Compliance Rules

| Rule ID    | Rule                                                                                                      |
| ---------- | --------------------------------------------------------------------------------------------------------- |
| **CR-001** | Stamp duty rate configurable via system_config without code deployment                                    |
| **CR-002** | PDPA: full data export must be possible for any user on request                                           |
| **CR-003** | PDPA: hard-delete all user personal and financial data within 30 days of deletion request                 |
| **CR-004** | PDPA: subscription billing records anonymised (user_id → NULL), not deleted (7-year accounting retention) |
| **CR-005** | Audit records retained for lifetime of user account; deleted on PDPA erasure                              |
| **CR-006** | T+2 settlement disclosure on sell calculator (application layer concern, not schema)                      |

---

## 6. Stored Values vs. Derived Values

### Stored at Creation Time (Never Re-derived Automatically)

| Value                                                   | Entity          | Event that may change it                                                                       |
| ------------------------------------------------------- | --------------- | ---------------------------------------------------------------------------------------------- |
| `initial_amount` (shares × purchase_price)              | Lot             | Only on explicit user edit of the lot; recalculated and stored; old value written to audit_log |
| `brokerage_fee`                                         | Lot             | Only on explicit user edit                                                                     |
| `clearing_fee`                                          | Lot             | Only on explicit user edit                                                                     |
| `stamp_duty`                                            | Lot             | Only on explicit user edit                                                                     |
| `all_in_cost`                                           | Lot             | Only on explicit user edit                                                                     |
| `qualifying_shares`                                     | DividendTranche | Only on explicit user edit of the tranche                                                      |
| `total_amount` (= per_share_amount × qualifying_shares) | DividendTranche | **Only on explicit user edit of the tranche — P0 invariant**                                   |
| `per_share_amount`                                      | DividendTranche | Only on explicit user edit                                                                     |
| `year`                                                  | DividendTranche | Set at creation from payment_date; editable                                                    |
| `trial_expiry_date`                                     | User            | Set at registration; not recomputed                                                            |

### Derived at Read Time (Never Stored as a Column)

| Derived value                         | Computed from                                                                                              |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `position_total_shares`               | `SUM(lots.shares WHERE position_id = ? AND is_deleted = false)`                                            |
| `position_total_initial_amount`       | `SUM(lots.initial_amount WHERE position_id = ? AND is_deleted = false)`                                    |
| `position_total_all_in_cost`          | `SUM(lots.all_in_cost WHERE position_id = ? AND is_deleted = false)`                                       |
| `position_blended_purchase_price`     | `total_initial_amount / total_shares`                                                                      |
| `position_total_dividend_income_ytd`  | `SUM(dividend_tranches.total_amount WHERE position_id = ? AND year = current_year AND is_deleted = false)` |
| `position_dividend_yield`             | `total_dividend_income_ytd / total_all_in_cost`                                                            |
| `position_current_market_value`       | `total_shares × PriceSnapshot.price` (from most recent snapshot)                                           |
| `position_unrealised_pnl`             | `current_market_value - total_all_in_cost`                                                                 |
| `portfolio_total_all_in_cost`         | Sum of all positions' `total_all_in_cost`                                                                  |
| `portfolio_total_dividend_income_ytd` | Sum of all positions' `total_dividend_income_ytd`                                                          |
| `portfolio_blended_yield`             | `portfolio_total_dividend_income_ytd / portfolio_total_all_in_cost`                                        |
| `staleness_flag`                      | `now() - PriceSnapshot.last_refreshed_at > 28 hours`                                                       |

---

## 7. Transaction Boundaries and Consistency

| Operation                     | What must be atomic                                                                                                 | Rollback behaviour                                                   |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| **Lot creation**              | INSERT lot (all fee fields) + CREATE position (if new) + INSERT audit_log                                           | Full rollback; no partial lot                                        |
| **Lot edit**                  | UPDATE lot (version++) + INSERT audit_log (previous + new values)                                                   | Full rollback; version mismatch → HTTP 409, no write                 |
| **Lot soft-delete**           | UPDATE lot (is_deleted=true) + INSERT audit_log                                                                     | Full rollback                                                        |
| **Position soft-delete**      | UPDATE position + UPDATE all child lots + UPDATE all child dividend_tranches + INSERT audit_log entries             | Full rollback                                                        |
| **DividendTranche creation**  | Validate qualifying_shares (read lots) + INSERT tranche (qualifying_shares, total_amount stored) + INSERT audit_log | Full rollback; no partial tranche                                    |
| **DividendTranche edit**      | UPDATE tranche (total_amount recalculated, version++) + INSERT audit_log                                            | Full rollback; version mismatch → HTTP 409                           |
| **CSV import**                | Phase 1 validation (no writes) → Phase 2: all INSERTs (positions, lots, tranches, audit_log) in one transaction     | Full rollback on any row failure; ImportJob updated to 'failed'      |
| **Stripe webhook processing** | SELECT idempotency check + INSERT processed_webhook_events + UPDATE user status + INSERT audit_log                  | Full rollback if any step fails; HTTP 500 to Stripe (triggers retry) |
| **PDPA hard-delete**          | Ordered DELETEs + SET NULL on subscription_records + INSERT system_deletion_log + DELETE user (cascade)             | Per-user rollback; other users' deletions unaffected                 |
| **User registration**         | INSERT user + INSERT portfolio + INSERT audit_log                                                                   | Full rollback; email reported as undelivered                         |
| **Password change**           | UPDATE password_hash + INCREMENT token_version + INSERT audit_log                                                   | Full rollback; old sessions invalidated only on full success         |

---

## 8. Audit and Compliance Requirements

### What Must Be Audited

Every audit entry must capture: action, entity_type, entity_id, user_id, timestamp, previous_values (where applicable), new_values (where applicable).

| Event                       | Actor                   | previous_values captured                          | new_values captured                                          |
| --------------------------- | ----------------------- | ------------------------------------------------- | ------------------------------------------------------------ |
| User registration           | User                    | None                                              | Email, account_status                                        |
| User login                  | User                    | None                                              | Timestamp                                                    |
| Password change             | User                    | None (no hash captured)                           | token_version incremented                                    |
| Lot created                 | User                    | None                                              | All lot fields including all fee components                  |
| Lot updated                 | User                    | All lot fields before edit                        | All lot fields after edit                                    |
| Lot deleted                 | User                    | All lot fields                                    | None                                                         |
| DividendTranche created     | User                    | None                                              | All tranche fields including qualifying_shares, total_amount |
| DividendTranche updated     | User                    | qualifying_shares, per_share_amount, total_amount | Updated values                                               |
| DividendTranche deleted     | User                    | All tranche fields                                | None                                                         |
| Manual price override       | User                    | Previous price (if any)                           | Manual price                                                 |
| CSV import completed        | User                    | None                                              | Row counts                                                   |
| Subscription activated      | System (Stripe webhook) | None                                              | subscription_start_date                                      |
| Subscription cancelled      | System (Stripe webhook) | None                                              | cancellation date                                            |
| Deletion requested          | User                    | Previous account_status                           | pending_deletion, deletion dates                             |
| Deletion cancelled          | User                    | pending_deletion                                  | Restored status                                              |
| Account hard-deleted        | System (cron)           | None                                              | Timestamp (record survives only in system_deletion_log)      |
| SystemConfig updated        | Admin                   | Previous value                                    | New value                                                    |
| PDPA data export downloaded | User                    | None                                              | Timestamp                                                    |

### PDPA Data Export: Audit Log Inclusion

Audit log entries ARE included in the PDPA data export. The `metadata` JSONB field may contain IP addresses, which must be excluded from the export. Export format: audit entries without IP fields.

### Retention Requirements

| Data                      | Retention                                                                       |
| ------------------------- | ------------------------------------------------------------------------------- |
| AuditLog                  | Lifetime of user account; CASCADE-deleted on PDPA hard-delete                   |
| SubscriptionRecord        | 7 years minimum (Malaysian accounting law); anonymised (user_id → NULL) on PDPA |
| SystemDeletionLog         | Permanent; no user PII                                                          |
| PriceSnapshot (automated) | Permanent (shared market data)                                                  |
| PriceSnapshot (manual)    | Until PDPA deletion of creating user                                            |

---

## 9. Shared vs. User-Scoped Data

### User-Scoped (PDPA-Deletable, Owned by One User)

- `User`, `Portfolio`, `Position`, `Lot`, `DividendTranche`
- `AuditLog` (CASCADE-deleted when User is deleted)
- `ImportJob`
- `PendingToken` (CASCADE-deleted when User is deleted)
- `PendingEmailNotification`
- `ProcessedWebhookEvent` (for that user's Stripe events)
- Custom `BrokerConfig` (where `is_system = false` and `created_by_user_id = user.id`)
- Manual `PriceSnapshot` (where `created_by_user_id = user.id`)

### System-Shared (Retained on PDPA Deletion, No User Owner)

- `Stock` (Bursa reference data)
- `SystemConfig` (operational parameters)
- System `BrokerConfig` (where `is_system = true`)
- Automated and stale `PriceSnapshot` (where `created_by_user_id IS NULL`)
- `SystemDeletionLog` (no PII)

### Partially Shared (Anonymised, Not Deleted)

- `SubscriptionRecord` — retained for accounting; `user_id` set to NULL on PDPA erasure

---

## 10. Gaps, Contradictions, and Open Questions

### Gap 1: system_deletion_log Table Undefined

The solution architecture references inserting into `system_deletion_log` during the PDPA hard-delete procedure (§13.5) but does not define this table in the entity model (§12.1). The physical design must create this table. It must store: `id UUID`, `deleted_at TIMESTAMPTZ`, `reason TEXT` — with no user PII.

**Impact:** Stage 3 must add this table. No entity model entry exists to reference.

---

### Gap 2: processed_webhook_events Has No user_id in Entity Model

The entity model (§12.1) shows `ProcessedWebhookEvent` with only `event_id TEXT PK` and `processed_at`. The PDPA deletion procedure (§13.5, step 3) says "Delete: processed_webhook_events (for user)". Without a `user_id` column, deletion by user is impossible without a JOIN through `subscription_records.stripe_customer_id`.

**Inference:** A `user_id` column should be added to `processed_webhook_events`. This resolves the PDPA deletion dependency without a complex join.

**Impact:** Stage 3 must add `user_id UUID REFERENCES users(id) ON DELETE CASCADE` to `processed_webhook_events`.

---

### Gap 3: Custom BrokerConfig Deletion in PDPA Order

The PDPA deletion order in §13.5 does not include deletion of custom `BrokerConfig` records. Since `Lot` records (step 6) reference `BrokerConfig` via FK, and Lots are deleted before the User row, custom BrokerConfig records can be safely deleted after Lots are removed. The deletion order is incomplete.

**Inference:** Custom BrokerConfig records should be deleted after Lots (step 6) and before Positions are deleted (step 7), or in any order after Lots are removed.

**Impact:** Stage 3 must add custom BrokerConfig deletion to the PDPA deletion sequence. The FK from `Lot.broker_config_id → broker_configs(id)` must be `ON DELETE RESTRICT` to prevent accidental deletion of a broker config while lots still reference it.

---

### Contradiction 1: PRD §14 vs. BAS v2.0 on DividendTranche.total_amount

PRD Section 14 (Core Domain Model) states: "total dividend amount (derived: per share × total shares)" — implying `total_amount` is derived from the live position share count. This directly contradicts BAS v2.0 CRIT-01 (BR-009, FR-009, EC-022) and Solution Architecture P-004, which mandate that `total_amount` is STORED at logging time and must never be re-derived from live share count.

**Impact:** This is a pre-implementation blocker identified in the architecture as R-002. The Solution Architecture document (§19, R-002) flags this and states "Do not begin schema design until PRD Section 14 is corrected." The BAS v2.0 and Solution Architecture v1.1 are the authoritative sources. The physical design must follow BAS v2.0: `total_amount` is stored, not derived.

---

### Open Question 1: DividendTranche Tranche Label Uniqueness

The BAS states no duplicate tranche labels per position per year (VR from EC-008). The physical design should enforce a unique constraint on `(position_id, tranche_label, year)` where `is_deleted = false`. This requires a partial unique index in PostgreSQL.

**Impact:** Stage 3 must create this partial unique index.

---

### Open Question 2: PriceSnapshot — Is it One Row Per Day or Latest Wins?

The architecture describes UPSERT semantics on `(stock_code, trading_date)`. This implies one active record per stock per trading day. Manual overrides for the same day would update the existing row (source → 'manual'). Next day's automated refresh creates a new row for the new date. This means "supersession" is a date-based concept (the next day's row is the current price), not a flag on the existing row.

**Confirmed interpretation:** One PriceSnapshot per `(stock_code, trading_date)`. UNIQUE constraint on this pair enables UPSERT semantics. Staleness detection uses `last_refreshed_at` on the most recent row (by trading_date DESC).

---

### Open Question 3: position.stock_name — Denormalised or Reference?

Position stores `stock_name TEXT`. The `stocks` table also has `name TEXT`. The BAS entity model includes `stock_name` directly on Position. The architecture shows Position referencing `stock_code` (FK to stocks). This design denormalises the stock name onto Position.

**Inference:** Denormalisation is intentional — the user may have entered a name at position creation time, and the stocks table name may differ. The FK on `stock_code` is for validation; `stock_name` on Position is for display. Both should exist.

---

_End of Stage 1 — Domain Model Review Report_  
_Proceed to Stage 2 — Logical Data Model Workshop using this report and the Solution Architecture Document._
