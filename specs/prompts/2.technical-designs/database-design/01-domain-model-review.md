# Stage 1 — Domain Model Review

## Your Role and Task

You are a senior data architect performing a domain model review for BursaTrack, a web-based dividend portfolio tracker for Malaysian retail investors. The solution architect has produced a high-level architecture and entity model. The business analyst has produced a detailed functional specification. Your job is to read these documents as a domain modelling exercise — understanding what must be persisted, what must be derived, where the critical business invariants lie, and what risks the physical schema design must address.

This is not a coding task. Do not design tables, write SQL, or name columns. Focus entirely on business concepts, lifecycle, correctness requirements, and persistence concerns.

---

## Documents Provided

You have been given:
- Product Requirements Document (PRD)
- Business Analysis Specification (BAS Parts 1–3)
- Solution Architecture Document (including entity model at §12.1)
- Architecture Decision Records

---

## Required Behaviour

- Extract only what is explicitly supported by the supplied documents. Do not invent entities, business rules, or workflows.
- Distinguish clearly between: **facts** (stated in documents), **inferences** (logically implied but not stated), and **open questions** (genuinely unclear or contradictory).
- When documents contradict each other, flag it explicitly. Do not silently resolve contradictions.
- If information is missing, state it as an open question — do not guess.
- Use domain language. Avoid premature database terminology (table, column, index, foreign key).

---

## Priority Focus Areas

As you read the documents, give particular attention to these high-risk areas:

### 1. Dividend Tranche Invariant (P0 — CRITICAL)

The BAS documents a critical defect that was fixed. The original system re-derived `DividendTranche.total_amount` from the live position share count, causing retroactive corruption when new lots were added after a dividend was logged. The fix stores `total_amount` at logging time using a stored `qualifying_shares` field.

In your review, document this invariant precisely:
- What is `qualifying_shares`? What does it represent, and when is it set?
- What triggers a recalculation of `total_amount`? (Only explicit user edits to the tranche)
- What must NOT trigger a recalculation? (Adding new lots to the position)
- What is the user-visible consequence of violating this invariant?

### 2. Financial Calculation Chain

Trace the full chain from user-entered inputs through to yield output. For each calculated value in the chain, determine whether it is:
- **Stored at creation time** and never re-derived (e.g., `all_in_cost`, `total_amount`)
- **Computed at read time** from stored values (e.g., position yield, portfolio blended yield)
- The rule for when a stored value is recalculated

Pay particular attention to the Malaysian fee stack: brokerage (per-broker rules, percentage or flat), clearing fee (0.03%), and stamp duty (ROUNDUP semantics at RM1/RM1,000). Each is a distinct component.

### 3. User and Account Lifecycle

Identify all account states and valid transitions. Include:
- The trial period and what access it grants
- The `grace_period` state (Stripe renewal failure — full access retained while retrying)
- The `pending_deletion` state and the 30-day grace window
- What happens to data at each state transition
- Which transitions are user-initiated vs. system-initiated

### 4. Audit Requirements

Identify every type of state change that must produce an immutable audit record. For each:
- What changed?
- What data must the audit record capture (previous values, new values, timestamp, user)?
- Who is the responsible actor (user action vs. system action)?

The architecture lists specific audit events (§14.7). Verify the domain review is consistent with this list.

### 5. PDPA Compliance Boundaries

Identify which data is personal, which is financial, and which is system/shared:
- Which entities are strictly per-user and must be hard-deleted on PDPA erasure?
- Which entities are shared across users (e.g., PriceSnapshot for automated prices) and must be retained?
- Which entities must be anonymised rather than deleted (e.g., billing records for accounting purposes)?
- What is the deletion dependency order (which records must be deleted before others due to FK constraints)?

### 6. Price Data Provenance

The product uses an unofficial price data source (yfinance) that can fail partially or completely. The schema must support:
- Distinguishing automated prices from manual overrides from stale markers
- Recording when a price was last successfully refreshed (enabling staleness detection)
- Attributing manual overrides to the user who entered them (for PDPA deletion targeting)
- Superseding manual overrides when automated refresh succeeds

---

## Deliverable: Domain Model Review Report

### 1. Executive Summary

What does BursaTrack need to persist? What are the top three correctness risks for the data model?

### 2. Business Entities and Value Objects

For each business concept in the domain:
- Is it an entity (has its own identity and lifecycle) or a value object (defined only by its attributes)?
- Is it user-scoped (private to one user's portfolio) or system-shared (across all users)?
- Does it need its own lifecycle management (creation, update, soft-delete, hard-delete)?

### 3. Aggregate Roots and Ownership Boundaries

Identify the aggregate roots. For each:
- Which entities does it own and govern?
- What is the consistency boundary — what set of changes must be atomic?
- What invariants must hold across the aggregate?

### 4. Entity Lifecycle and State Transitions

For every entity that changes state over time:
- List all valid states
- List all valid transitions, including what triggers each
- Note what data must be recorded at each transition

Include the full User account lifecycle (trial → active → grace_period → trial_expired → pending_deletion → deleted).

### 5. Business Rules and Invariants

List all business rules that constrain what can be stored or how values must be computed. For each:
- State the rule precisely
- Note whether it applies at entity creation, on update, or at all times
- Classify it as a financial correctness rule, a validation rule, a workflow rule, or a compliance rule
- Mark the `qualifying_shares` / `total_amount` invariant as P0 CRITICAL

### 6. Stored Values vs. Derived Values

For every calculated field in the domain, state explicitly:
- **Stored**: calculated once and persisted; must not be re-derived automatically
- **Derived at read time**: always computed from stored values; must not be cached as a column
- For stored values: what event triggers a recalculation, and which user action initiates it

### 7. Transaction Boundaries and Consistency

Identify operations that must be atomic — where a partial failure would leave data in an inconsistent state. For each:
- What records are created or modified together?
- What invariants must hold across all of them?
- What is the rollback behaviour on failure?

Include: lot creation (fees must be stored atomically with the lot), dividend tranche creation (qualifying_shares and total_amount must be stored together), PDPA hard-deletion (must delete all user data in a single transaction).

### 8. Audit and Compliance Requirements

- What must be audited, and to what level of detail?
- Which audit records are user-readable (PDPA data export) vs. system-only?
- What retention requirements apply to audit records?
- What anonymisation requirements apply to billing/financial records?

### 9. Shared vs. User-Scoped Data

Explicitly categorise each entity:
- **User-scoped**: owned by a single user; not accessible to other users; PDPA-deletable
- **System-shared**: referenced by all users; not owned by any user; retained on PDPA deletion
- **Partially shared**: some records per-user (manual price overrides), some system (automated prices)

### 10. Gaps, Contradictions, and Open Questions

- Note any requirement the supplied documents do not resolve
- Flag any contradictions between documents
- List any risks the physical design team must address that are not yet answered in the architecture
