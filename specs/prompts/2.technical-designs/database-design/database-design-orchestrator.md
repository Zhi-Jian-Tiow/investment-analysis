# Database Schema Design — Workflow Orchestrator

## What This Workflow Does

This is a four-stage guided workflow for designing the PostgreSQL database schema for BursaTrack. It takes the approved solution architecture and product documents as inputs and produces Alembic-ready DDL as output.

Work through the stages in order. Each stage's output feeds the next. Do not skip stages or jump directly to SQL.

---

## When to Use This Workflow

All of the following documents must be available before beginning:

- Solution Architecture Document (entity model at §12, precision rules at §12.3, index requirements at §8.3)
- Architecture Decision Records (ADR-001 through ADR-015)
- Business Analysis Specification (Parts 1–3)
- Product Requirements Document

---

## Architectural Decisions Already Made — Do Not Re-Open

The solution architect has settled the following. Every stage must treat these as constraints, not starting points for discussion.

| Area                | Decision                                                                                        |
| ------------------- | ----------------------------------------------------------------------------------------------- |
| Database engine     | PostgreSQL 16, managed on Render                                                                |
| ORM and migrations  | async SQLAlchemy + Alembic; backwards-compatible migrations only                                |
| Primary key type    | UUID everywhere (`gen_random_uuid()`)                                                           |
| Monetary storage    | `NUMERIC` only — no `FLOAT`, `REAL`, or `DOUBLE PRECISION`                                      |
| Soft delete pattern | `is_deleted BOOLEAN DEFAULT false` + `deleted_at TIMESTAMPTZ` on Position, Lot, DividendTranche |
| Optimistic locking  | `version INTEGER NOT NULL DEFAULT 1` on Lot and DividendTranche                                 |
| Session revocation  | `token_version INTEGER NOT NULL DEFAULT 0` on User                                              |
| Yield percentage    | Computed at query time — never stored as a column                                               |
| Position aggregates | Computed at query time — not stored on Position                                                 |
| Multi-tenancy       | Single portfolio per user at V1; all data scoped through portfolio_id                           |
| Caching             | In-process TTLCache in FastAPI — not a schema concern                                           |
| Redis               | Not used at any layer                                                                           |
| Enum persistence    | Constrained `TEXT` columns with `CHECK` constraints — not lookup tables                         |

---

## P0 Invariant — Read This Before Every Stage

This is the most critical correctness requirement in the entire schema. It must be preserved at every design decision.

**`DividendTranche.total_amount` is stored at logging time and must never be re-derived from the current position share count.**

At logging time:

- `qualifying_shares` = the share count the user held at the ex-dividend date (defaults to current position total; user may override)
- `total_amount` = `per_share_amount × qualifying_shares`, calculated and stored immediately

After creation:

- `total_amount` changes only when the user explicitly edits the tranche record
- Adding new Lots to the parent Position must never trigger any recalculation of `total_amount`

The schema must not contain any trigger, generated column, or view that derives or updates `total_amount` from the current position share count. Enforcement is at the application layer; the schema must not work against it.

---

## Required Stages

### Stage 1 — Domain Model Review

**Prompt:** `01-domain-model-review.md`  
**Inputs:** All product and architecture documents  
**Output:** Domain Model Review Report  
**Goal:** Understand what must be persisted, what must be derived, and where the business rules and correctness invariants lie. No table design at this stage.

### Stage 2 — Logical Data Model Workshop

**Prompt:** `02-logical-data-model-workshop.md`  
**Inputs:** Stage 1 output + Solution Architecture Document  
**Output:** Logical Data Modelling Decision Record  
**Goal:** Make explicit decisions on modelling patterns the architecture left implicit. Validate the architectural entity model against the domain review. No DDL at this stage.

### Stage 3 — Physical Schema Design

**Prompt:** `03-physical-schema-design.md`  
**Inputs:** Stage 1 and Stage 2 outputs + Solution Architecture Document  
**Output:** Physical Schema Design with Alembic-ready DDL  
**Goal:** Produce a complete, implementation-ready PostgreSQL schema.

---

## BursaTrack-Specific Priorities

All stages must protect the following:

1. **Financial correctness**: Every fee component (brokerage, clearing fee, stamp duty) is stored individually at the Lot level. The all-in cost is the sum of those stored components. No fee value is a computed column.

2. **The qualifying_shares invariant (P0)**: Described above. Any design decision that touches `DividendTranche` must be evaluated against this invariant.

3. **Malaysian fee stack accuracy**: Brokerage uses `NUMERIC(10,6)` rate and `NUMERIC(14,2)` minimum. Clearing fee is always `NUMERIC(14,2)`. Stamp duty uses ROUNDUP semantics — never float.

4. **Auditability**: Lot edits, DividendTranche edits, password changes, subscription changes, and PDPA actions produce immutable audit_log entries with previous and new values in JSONB.

5. **PDPA compliance**: The schema must support full data export (FR-018) and a hard-deletion in the specific order defined in the architecture (§13.5). `SubscriptionRecord` is anonymised (user_id set to NULL), not deleted.

6. **Stale price provenance**: `PriceSnapshot.source` is `automated`, `manual`, or `stale`. `last_refreshed_at` enables staleness detection (>28 hours threshold used by the frontend).

7. **Operational simplicity**: This is an MVP for a solo founder. Do not introduce complexity that the product does not yet require.

---

## Guardrails for All Stages

The AI must not:

- Skip to SQL generation before Stage 1 and Stage 2 are complete
- Re-open any decision listed under "Architectural Decisions Already Made"
- Invent entities, relationships, or business rules not present in the supplied documents
- Use floating-point types for any monetary value
- Create triggers, generated columns, or views that derive `DividendTranche.total_amount` from position share counts
- Design for theoretical scale the product does not need

---

## Invocation

Provide the AI with all documents listed under "When to Use This Workflow." At each stage, share the prior stage's output alongside the next stage's prompt. Confirm stage outputs with a human reviewer before proceeding.
