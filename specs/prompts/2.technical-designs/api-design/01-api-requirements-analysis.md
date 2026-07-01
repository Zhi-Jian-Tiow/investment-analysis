# Stage 1 — API Requirements and Resource Analysis

## Your Role and Task

You are a senior API architect performing a requirements analysis for BursaTrack, a web-based dividend portfolio tracker for Malaysian retail investors. The solution architect has designed the system architecture and identified the core endpoints. The business analyst has specified all functional requirements.

Your job is to read these documents as an API design exercise — mapping every business operation to a candidate API operation, identifying the actors, resources, data requirements, and security constraints. This is NOT a contract design task. Do not define HTTP paths, methods, status codes, request schemas, or response schemas at this stage. Focus on understanding the business operations and what the API must enable.

---

## Documents Provided

You have been given:
- Product Requirements Document (PRD)
- Business Analysis Specification (BAS Parts 1–3)
- Solution Architecture Document (module structure at §7.2, endpoint references at §10–§11)

---

## Required Behaviour

- Ground every claim in the supplied documents. Do not invent operations, resources, or constraints.
- Distinguish clearly between: **facts** (stated in documents), **inferences** (logically implied), and **open questions** (genuinely unclear).
- When documents contradict each other, flag it. Do not silently resolve contradictions.
- Use business language. Avoid premature API terminology (no paths, HTTP verbs, status codes, schemas).
- If a business operation's data requirements are unclear, state it as an open question.

---

## Priority Focus Areas

Give particular attention to these high-risk areas:

### 1. Fee Calculation Authority (P0 — CRITICAL)

The architecture mandates server-authoritative fee calculation. The client sends a purchase description; the server computes all fees. This means:
- The API must capture which fields the client provides (purchase price, shares, broker choice, date)
- The API must explicitly NOT accept pre-calculated fees from the client
- Document what data flows from client → server for each trade entry operation
- Document what data flows from server → client in the response (including all computed fee components)

### 2. Dividend Tranche Invariant (P0 — CRITICAL)

`DividendTranche.total_amount` is stored at logging time. At entry, `total_amount = per_share_amount × qualifying_shares`. When a user edits a tranche, they may change `per_share_amount` and/or `qualifying_shares` — the server recomputes `total_amount`. The client must never supply `total_amount` directly.

Document:
- What fields the client provides when creating a dividend tranche
- What fields the client provides when editing a dividend tranche
- What the server computes and returns

### 3. Authentication Flows

BursaTrack has multiple distinct authentication flows. For each, document the steps (what the client does, what the server does, what is returned):
- Registration → email verification → first login
- Normal login → session management → token refresh → logout
- Password reset (request → email → reset)
- Account deletion initiation → 30-day grace → cancellation OR permanent deletion
- Stripe webhook authentication (not JWT-based)
- Admin endpoint access (not JWT-based)

### 4. Actor Classification

Identify every distinct actor type that interacts with the API:
- Unauthenticated users (registration, login, password reset, email verification, deletion cancellation)
- Authenticated users (all portfolio and account operations)
- Admin (system configuration, not a human user account — accessed via API key)
- Stripe (webhook events — external system, not a user)
- BursaTrack cron jobs (price refresh, trial expiry, PDPA deletion — internal, not API consumers)

For each actor, document what operations they can perform.

### 5. PDPA-Affected Operations

Identify every API operation that has PDPA compliance implications:
- Data export: what personal data is included and excluded?
- Deletion initiation: what happens immediately vs. after 30 days?
- Deletion cancellation: who can cancel and when?
- Token handling: are deletion cancellation tokens handled safely (not exposed in URLs)?
- Data minimisation: which API responses return more data than the client needs?

### 6. Asynchronous Operations

Identify every operation that cannot complete synchronously in a single API request:
- CSV import: why is it async? What does the client receive immediately? How does the client track progress?
- Document the polling pattern: what does the client request, what does the server return, how does the client know when to stop polling?
- Are there any other operations that should be async? (e.g., data export at large scale)

### 7. Operations Requiring Audit Trail

Identify every state-changing operation that must produce an immutable audit record. The architecture lists 18 specific audit events (§14.7). For each:
- What API operation triggers the audit event?
- What data must the audit record capture (before values, after values)?
- Who is the actor (user, admin, system)?

---

## Deliverable: API Requirements Report

### 1. Executive Summary

What is the overall API scope? How many distinct operation types exist? What are the three highest-risk areas for API design correctness?

### 2. Actor Inventory

For each actor type:
- Identity: how is the actor identified to the API?
- Permissions: what operations can they perform?
- Session model: does this actor maintain a session? How long does it last?
- Security constraints that specifically apply to this actor

### 3. Resource Inventory

For each resource that the API manages:
- Resource name and what it represents in the domain
- Ownership: user-scoped (private to one user), system-shared (all users), or admin-only
- Lifecycle: can it be created, read, updated, soft-deleted, hard-deleted?
- Relationships: what other resources is it owned by or does it reference?
- Whether it has meaningful state transitions (not just CRUD)

### 4. Operation Inventory by Domain

Group all API operations by domain module. For each operation:
- Business name (what the user or system is doing)
- Actor performing it
- Data the actor provides
- Data the API returns
- Whether it changes state (write) or reads state (read)
- Whether it is synchronous or asynchronous
- Whether it requires authentication

Domains: Auth, Portfolio, Pricing, Import, Subscription/Billing, Account/PDPA, Configuration, Stocks, Health

### 5. Non-CRUD Operations

Identify operations that do not fit the standard Create/Read/Update/Delete pattern:
- Calculation endpoints (sell scenario calculator — returns a computation, creates no resource)
- State-transition endpoints (logout, delete-request, checkout)
- Async job endpoints (CSV import — initiates a job, then polled)
- External system callbacks (Stripe webhooks — not user-initiated)
- Export endpoints (PDPA data export — reads data, creates no resource)
- Aggregate/dashboard endpoints (returns computed aggregates across multiple resources)

For each non-CRUD operation, document what makes it different from a standard CRUD endpoint and what special considerations it requires.

### 6. Data In and Data Out (Conceptual)

For each write operation, identify:
- What minimum data the client must provide
- What data the server computes and stores (never accepted from client)
- What the server returns to the client after the operation

Pay particular attention to:
- Lot creation: client provides purchase description; server computes all fee components
- DividendTranche creation: client provides per-share amount and qualifying shares; server stores total_amount
- DividendTranche edit: client provides updated per-share amount and/or qualifying shares; server recomputes total_amount

### 7. Security Requirements per Operation

For each operation, state:
- Authentication requirement: JWT, ADMIN_API_KEY, Stripe-Signature, or none
- Authorization requirement: ownership check, admin check, or none
- Rate limiting category: which rate limit class applies?
- Sensitivity: does this operation expose personal data, financial data, or system configuration?

### 8. PDPA Compliance Map

List every operation with a PDPA implication:
- What personal data does it return in the response?
- What data is included in the PDPA data export?
- What data must be excluded from the data export (and why)?
- What operations are involved in the deletion lifecycle?

### 9. Audit Trail Map

For each of the 18 audit events defined in the architecture (§14.7), identify:
- Which API operation triggers it
- What data the audit record captures
- Whether the audit write is in the same transaction as the state change (it must be)

### 10. Gaps, Contradictions, and Open Questions

- Requirements the supplied documents do not fully resolve
- Contradictions between the PRD, BAS, and architecture
- Operations implied by the business requirements that are not explicitly in the architecture
- Operations in the architecture that appear to be missing from the BAS functional requirements
