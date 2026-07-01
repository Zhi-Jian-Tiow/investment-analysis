# API Design — Workflow Orchestrator

## What This Workflow Does

This is a four-stage guided workflow for designing the REST API contract for BursaTrack. It takes the approved Solution Architecture Document, BAS, and PRD as inputs and produces a complete OpenAPI 3.0 specification as output.

The Solution Architecture Document has already defined every endpoint — paths, methods, auth, and rate limits. The gaps it left implicit are the primary focus of this workflow: response envelope design, monetary serialization format, error response schema, pagination strategy, and the complete request/response schemas for all 28+ endpoints.

Work through the stages in order. Each stage's output feeds the next. Do not skip stages or jump directly to writing OpenAPI YAML.

---

## When to Use This Workflow

All of the following documents must be available before beginning:

- Solution Architecture Document (endpoint inventory at §7.2 and §10–§11, auth at §14, rate limits at §14.4)
- Architecture Decision Records (ADR-001 through ADR-015)
- Business Analysis Specification (Parts 1–3, functional requirements)
- Product Requirements Document
- Database Schema Design outputs (Stages 1–4) — the API contract must be consistent with the schema

---

## Architectural Decisions Already Made — Do Not Re-Open

The solution architect has settled the following. Every stage must treat these as constraints, not topics for discussion.

| Decision | Specification |
|----------|--------------|
| Protocol | HTTP/HTTPS only — no WebSocket, no GraphQL |
| Framework | FastAPI (Python 3.13) with async SQLAlchemy |
| Auth mechanism | RS256 JWT stored in HTTP-only, Secure, SameSite=Lax cookie |
| Session revocation | `token_version INTEGER` on User; validated on every protected request |
| Ownership violation return code | HTTP 404, never HTTP 403 |
| Rate limiting library | SlowAPI in-process; single Render instance at V1 |
| CORS | Static allowlist + BursaTrack-prefixed Vercel preview regex |
| API URL prefix | `/api/v1/` for all resource endpoints |
| Admin auth | `ADMIN_API_KEY` environment variable in request header; separate from JWT |
| Webhook auth | Stripe-Signature header verification; not JWT |
| Async import pattern | 202 Accepted + polling pattern — no WebSocket push |
| Monetary type chain | PostgreSQL `NUMERIC` → Python `Decimal` → JSON string |
| Timestamp format | ISO 8601 UTC (e.g., `"2026-06-28T08:30:00Z"`) |
| Real-time protocol | None — REST polling only at V1 |

---

## P0 Invariants — Read This Before Every Stage

These are the highest-priority correctness requirements for the API layer. Every stage must respect them, and the review stage must check them explicitly.

**P0-API-001: Monetary values are never serialized as JSON numbers.**  
Pydantic's default `Decimal` serialization can silently produce floats. Every response schema that includes a monetary or rate field must serialize it as a JSON string. A single float escaping in a response breaks BursaTrack's core accuracy claim.

**P0-API-002: Server-authoritative fee calculation — no client-supplied fees accepted.**  
The client sends `purchase_price`, `shares`, and `broker_id`. The server computes all fee components (`brokerage_fee`, `clearing_fee`, `stamp_duty`, `all_in_cost`). Any request schema that accepts pre-calculated fee amounts must be rejected in Stage 2 and blocked in the Stage 4 review.

**P0-API-003: PATCH /dividends/{id} must not accept total_amount.**  
Clients may update `per_share_amount` and/or `qualifying_shares`. The server always recomputes `total_amount = per_share_amount × qualifying_shares` and stores it. A client-supplied `total_amount` must never be persisted — include it in the request schema only if the API rejects or ignores it explicitly.

**P0-API-004: Ownership verification is universal.**  
Every endpoint that accesses user-owned data must verify `resource.user_id == authenticated_user.id`. No endpoint returns user data without this check. Violations return 404, not 403.

---

## Required Stages

### Stage 1 — API Requirements and Resource Analysis
**Prompt:** `01-api-requirements-analysis.md`  
**Inputs:** PRD, BAS Parts 1–3, Solution Architecture Document  
**Output:** API Requirements Report  
**Goal:** Map every business operation to a candidate API operation. Identify actors, resources, data in/out, and security requirements conceptually. No HTTP paths, methods, or schemas at this stage.

### Stage 2 — API Design Decision Workshop
**Prompt:** `02-api-design-workshop.md`  
**Inputs:** Stage 1 output + Solution Architecture Document  
**Output:** API Design Decision Record  
**Goal:** Resolve every design decision the architecture left implicit. Confirm what is settled; fill the gaps.

### Stage 3 — OpenAPI Contract Specification
**Prompt:** `03-openapi-specification.md`  
**Inputs:** Stage 1 and Stage 2 outputs + Solution Architecture Document  
**Output:** Complete OpenAPI 3.0 YAML specification  
**Goal:** Produce the formal, machine-readable API contract covering all 28+ endpoints.

### Stage 4 — API Security and Quality Review
**Prompt:** `04-api-security-review.md`  
**Inputs:** Stage 3 OpenAPI spec + all prior stage outputs  
**Output:** Security and Quality Review Report with severity-graded findings  
**Goal:** Final quality gate before implementation. Find auth gaps, authorization gaps, financial data risks, PDPA exposure, input validation gaps, and response inconsistencies.

---

## BursaTrack-Specific API Priorities

All stages must protect the following:

1. **Financial accuracy at the API boundary**: Monetary values (prices, fees, dividend amounts, total amounts) must be strings in all request and response bodies. The API is the boundary between the `Decimal` world (Python backend) and the consumer (TypeScript frontend using `decimal.js`). A float at this boundary corrupts the calculation chain end-to-end.

2. **Server-authoritative fee calculation**: The API contract must make it impossible for a client to supply fee amounts. The `POST /portfolio/positions` and `POST /portfolio/positions/{id}/lots` request schemas must only accept `purchase_price`, `shares`, `broker_id`, and `purchase_date`. The API must not accept `brokerage_fee`, `clearing_fee`, `stamp_duty`, or `all_in_cost` from any client.

3. **Ownership enforcement without privilege escalation**: The API must be designed such that an authenticated user can never read, modify, or delete another user's data — not through direct access, not through parameter manipulation, not through batch operations. Returns 404 to prevent resource existence enumeration.

4. **PDPA compliance at the API surface**: The data export endpoint must include exactly the personal data defined in the architecture (§10.7). The deletion flow must not expose PII in URLs. Token-based flows (email verification, password reset, deletion cancellation) must use query parameters, not path segments, to keep tokens out of server access logs.

5. **Idempotency and conflict handling**: The API contract must document the optimistic locking mechanism for Lot and DividendTranche PATCH operations, the Stripe webhook idempotency mechanism, and the single-active-import-per-user rule. Clients must be able to detect and recover from 409 conflicts.

6. **Audit trail completeness**: Every state-changing operation must produce an audit_log entry in the same database transaction. The API contract must document which operations trigger audit events and what data they capture.

---

## Guardrails for All Stages

The AI must not:

- Re-open any decision listed under "Architectural Decisions Already Made"
- Skip to OpenAPI YAML generation before Stages 1 and 2 are complete
- Design endpoints that accept fee amounts from the client
- Serialize monetary values as JSON numbers in any response schema
- Design endpoints that accept `total_amount` for DividendTranche updates
- Return HTTP 403 for cross-user resource access — always 404
- Invent endpoints, resources, or operations not present in the supplied documents
- Introduce GraphQL, WebSocket, or server-sent event endpoints

---

## Invocation

Provide the AI with all documents listed under "When to Use This Workflow." At each stage, share the prior stage's output alongside the next stage's prompt. Confirm stage outputs with a human reviewer before proceeding to the next stage.
