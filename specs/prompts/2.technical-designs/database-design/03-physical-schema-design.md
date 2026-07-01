# Stage 3 — Physical Schema Design

## Your Role and Task

You are a senior database engineer producing the physical schema for BursaTrack — a production PostgreSQL 16 application. The entity model in the Solution Architecture Document (§12.1) provides the conceptual starting point. The Logical Data Modelling Decision Record (Stage 2) resolved the gaps. Your job is to translate both into complete, Alembic-ready DDL with all columns, types, constraints, indexes, and migration sequencing.

The schema must be correct on first implementation. This is not a prototype.

---

## Documents Provided

You have been given:
- Stage 1 Domain Model Review Report
- Stage 2 Logical Data Modelling Decision Record
- Solution Architecture Document (entity model at §12.1, data types at §12.3, index requirements at §8.3, audit events at §14.7, seeding data at §10.6)

---

## Non-Negotiable Technical Constraints

### Data Type Precision (from Architecture §12.3)

Use these types exactly. Do not substitute `FLOAT`, `REAL`, or `DOUBLE PRECISION` for any monetary or rate field.

| Field category | PostgreSQL type | Example value |
|----------------|-----------------|---------------|
| Purchase price per share | `NUMERIC(12,4)` | 8.3800 |
| Fee amounts (brokerage, clearing, stamp duty, all-in cost) | `NUMERIC(14,2)` | 41996.47 |
| Dividend per share amount | `NUMERIC(12,6)` | 0.004813 |
| DividendTranche total_amount | `NUMERIC(14,2)` | 1000.00 |
| PriceSnapshot price | `NUMERIC(12,4)` | 8.3800 |
| BrokerConfig rate | `NUMERIC(10,6)` | 0.001000 |
| Yield percentage | **Do not store** — computed at query time |

### Primary Keys

All tables use `UUID PRIMARY KEY DEFAULT gen_random_uuid()`. Do not use `SERIAL`, `BIGSERIAL`, or integer IDs.

### Alembic Migration Conventions

- Every migration must be **backwards-compatible**: additive only (new tables, new nullable columns with defaults, new indexes)
- Destructive operations (column drops, type changes, NOT NULL additions to existing tables) are applied in a separate subsequent migration, deployed after the code change is live
- All seed data is inserted via `op.execute()` statements in the initial seed migration
- Each migration file includes a `downgrade()` function that reverses the `upgrade()`

---

## Required Indexes (from Architecture §8.3)

Produce all of the following. For each, note the query pattern it supports and whether a partial index is appropriate.

| Index | Partial condition | Purpose |
|-------|-------------------|---------|
| `lots(position_id, is_deleted)` | `WHERE is_deleted = false` | Dashboard aggregate queries; position total_shares and total_all_in_cost |
| `dividend_tranches(position_id, year, is_deleted)` | `WHERE is_deleted = false` | YTD dividend sum per position |
| `price_snapshots(stock_code, trading_date)` | — | Price lookups for the dashboard |
| `audit_log(user_id)` | — | PDPA deletion job; data export |
| `audit_log(entity_type, entity_id)` | — | Drill-down audit queries |
| `import_jobs(user_id, status)` | — | Import status polling |
| `pending_tokens(user_id, type)` | `WHERE used_at IS NULL` | Active token lookup for a user |
| `price_snapshots(created_by_user_id)` | `WHERE created_by_user_id IS NOT NULL` | PDPA deletion of manual price overrides |

---

## Seeding Requirements

The following reference data must be inserted in the initial deployment via Alembic migration.

### BrokerConfig seed rows (from Architecture §10.6)

These are system-managed rows (`is_system = true`, `created_by_user_id = NULL`). Users cannot modify or delete them.

| name | fee_type | rate | minimum_fee | flat_fee | is_system |
|------|----------|------|-------------|----------|-----------|
| Maybank IB | percentage | 0.007000 | 8.00 | NULL | true |
| CIMB Clicks | percentage | 0.007000 | 8.00 | NULL | true |
| RHB Reflex | percentage | 0.007000 | 8.00 | NULL | true |
| Rakuten Trade | percentage | 0.007000 | 7.00 | NULL | true |
| Mirae Asset | percentage | 0.004200 | 8.00 | NULL | true |
| M+ Online | percentage | 0.006000 | 8.00 | NULL | true |

### SystemConfig seed rows

These operational parameters must be present at first deployment. The application reads them at startup and caches them via TTLCache.

| key | value | description |
|-----|-------|-------------|
| stamp_duty_rate | 0.001 | RM1 per RM1,000 (0.10%); configurable without code deploy (valid until 12 July 2028) |
| clearing_fee_rate | 0.0003 | 0.03% of contract value; no minimum; RM1,000 cap at >RM3.33M |
| price_deviation_max_pct | 75 | Max price deviation (%) before marking as CORPORATE_ACTION_CANDIDATE |
| bursa_holidays | [] | JSON array of ISO date strings for Bursa trading calendar holidays; admin must update annually |
| price_refresh_lock | NULL | Process lock for refresh_prices.py; NULL = no lock held |

---

## Deliverable: Physical Schema Design Document

### 1. Schema Summary

Brief overview of the schema structure. Include:
- Total table count and module ownership
- Key design decisions carried forward from Stage 2
- Migration deployment plan summary

### 2. Table Inventory

For each table:
- Purpose and module ownership (auth / portfolio / pricing / subscription / admin)
- Lifecycle: append-only, updateable, soft-deleted, or hard-deleted on PDPA erasure

### 3. Complete Table Definitions

For every table, produce the full DDL in PostgreSQL 16 syntax:
- Column name, data type, nullability, default value
- Primary key, unique constraints, foreign keys with explicit `ON DELETE` behaviour
- `CHECK` constraints for all enum-like columns
- `CHECK` constraints for domain rules where appropriate (e.g., `qualifying_shares >= 1`)
- Column comments for non-obvious fields

Include every table from the entity model at Architecture §12.1, plus any additional tables identified in Stage 2 decisions.

### 4. CHECK Constraints Reference

List all `CHECK` constraints and their business rule source:

Required at minimum:
- `users.account_status IN ('trial', 'active', 'grace_period', 'trial_expired', 'pending_deletion')`
- `price_snapshots.source IN ('automated', 'manual', 'stale')`
- `broker_configs.fee_type IN ('percentage', 'flat')`
- `dividend_tranches.tranche_label IN ('1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th')`
- `dividend_tranches.qualifying_shares >= 1`
- `lots.shares >= 1`
- `lots.purchase_price > 0`
- `pending_tokens.type IN ('email_verification', 'password_reset', 'deletion_cancellation')`
- `import_jobs.status IN ('processing', 'complete', 'failed')`
- `positions.category_tag IN ('Dividend', 'Volatile', 'Growth')`

### 5. Index Strategy

For each required index, produce:
- The `CREATE INDEX` statement with partial condition if applicable
- The specific query it supports
- Rationale for the partial condition if used

### 6. FK Cascade and Lifecycle Behaviour

Document every FK relationship, specifying:
- `ON DELETE CASCADE`: which relationships cascade (e.g., `audit_log.user_id REFERENCES users(id) ON DELETE CASCADE`)
- `ON DELETE SET NULL`: where nullification is correct (e.g., `subscription_records.user_id` on PDPA anonymisation)
- `ON DELETE RESTRICT`: where deletion must be blocked (e.g., deleting a BrokerConfig that is referenced by active Lots)
- Soft-delete semantics: which queries must include `WHERE is_deleted = false`

### 7. Optimistic Locking Pattern

Document the check-and-increment pattern for `Lot` and `DividendTranche`:
- The SQL pattern for the conditional UPDATE
- The response when a version conflict is detected (HTTP 409)
- Why `version` must be included in every UPDATE statement for these tables

### 8. PDPA Hard-Delete Order

Reproduce the deletion order from Architecture §13.5, annotated with:
- Which steps use explicit `DELETE WHERE`
- Which steps rely on `ON DELETE CASCADE` from the User deletion
- The Alembic-level implications (ensuring CASCADE FKs are in place before the cron job runs)
- The `SubscriptionRecord` anonymisation step (SET `user_id = NULL`)

### 9. Alembic Migration Plan

Provide the recommended migration sequence for V1 initial deployment:

| Migration | Contents | Dependency |
|-----------|----------|------------|
| 001_create_auth_tables | `users`, `pending_tokens`, `pending_email_notifications` | None |
| 002_create_portfolio_tables | `portfolios`, `positions`, `lots`, `dividend_tranches`, `broker_configs` | 001 |
| 003_create_pricing_tables | `stocks`, `price_snapshots` | 002 |
| 004_create_admin_tables | `system_config`, `audit_log` | 001 |
| 005_create_subscription_tables | `subscription_records`, `processed_webhook_events`, `import_jobs` | 001 |
| 006_create_indexes | All indexes listed in §4 | 002, 003, 004, 005 |
| 007_seed_reference_data | BrokerConfig system rows, SystemConfig defaults | 006 |

For each migration, include the `downgrade()` reversal.

### 10. Risks and Open Implementation Questions

Note any ambiguities, assumptions made in the physical design, and risks that require engineering review before implementation begins.

---

## Guardrails

Do not:
- Use `FLOAT`, `DOUBLE PRECISION`, or `REAL` for any monetary value
- Store yield percentage as a column
- Create triggers, generated columns, or views that derive `DividendTranche.total_amount` from position share counts
- Use `SERIAL` or `BIGSERIAL` for any primary key — UUID only
- Add tables, columns, or indexes not grounded in the entity model or Stage 2 decisions
- Write non-backwards-compatible migrations (no column drops, no NOT NULL additions without defaults)
- Include materialised views, partitions, or other complexity the product does not yet require
