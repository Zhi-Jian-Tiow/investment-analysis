# BursaTrack — API Design Decision Record
## Stage 2 of 4: API Design Decision Workshop

> **Author:** Principal API Architect (API Design Workflow — Stage 2)<br>
> **Date:** 2026-07-01<br>
> **Inputs:** Stage 1 API Requirements Report · BursaTrack Solution Architecture Document<br>
> **Status:** Resolves ADD-001 through ADD-012. Does not re-open any decision listed in the architecture's "Architectural Decisions Already Made" table.

---

## ADD-001 — Response Envelope Design

**Context:** Every successful response needs a consistent shape so the Next.js client can write one response-handling layer instead of one per endpoint.

**Analysis:** The architecture is silent on envelope vs. bare object. The dashboard endpoint (§10.7 pattern, and the general aggregate-at-query-time principle in ADR-004) returns a genuinely heterogeneous, named-key structure (summary + positions array) that does not benefit from a generic `data` wrapper. The error shape the architecture *does* specify explicitly (§15.4's `{"error": "conflict", "message": "..."}` and §10.6's `{"error": "in_use", "message": "..."}`) is already a bare object, not an envelope — so an envelope on success responses would create two different top-level shapes depending on outcome, which is worse for client code than no envelope at all.

**Options:**
- Bare object (FastAPI default)
- `{"data": {...}, "meta": {...}}` envelope

**Decision: Bare object.** BursaTrack V1 has no pagination cursors, no request-tracing requirement, and no multi-resource batch responses that would benefit from a `meta` sidecar. FastAPI's default Pydantic `response_model` serialization produces bare objects with zero extra code. This is also the simpler option per the guardrail "prefer the simpler option when both are viable."

**Stage 3 Constraint:** All `2xx` response schemas are bare objects — the resource (or resource array, or computed aggregate) directly at the JSON root. No `data`/`meta` wrapper anywhere in the spec, including collection endpoints.

---

## ADD-002 — Universal Error Response Schema

**Context:** Every 4xx/5xx response across 28+ endpoints must be structurally predictable so the frontend can branch on `error` without endpoint-specific parsing.

**Analysis:** The architecture provides two concrete instances (`conflict`, `in_use`) that share the shape `{"error": string, "message": string}`. This shape generalizes cleanly. FastAPI's default 422 body (`{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`) is structurally different and would break a single universal parser if left un-normalized.

**Decision:**

Two schemas, not one, because field-level validation genuinely needs a different shape than single-cause errors:

```yaml
ErrorResponse:
  type: object
  required: [error, message]
  properties:
    error: { type: string, description: "Machine-readable error code" }
    message: { type: string, description: "Human-readable, end-user-displayable message" }
  example: { error: "version_conflict", message: "This record was modified by another session. Please refresh and try again." }

ValidationErrorResponse:
  type: object
  required: [error, message, fields]
  properties:
    error: { type: string, enum: ["validation_failed"] }
    message: { type: string }
    fields:
      type: array
      items:
        type: object
        required: [field, constraint]
        properties:
          field: { type: string }
          constraint: { type: string }
          received: { type: string, nullable: true }
  example:
    error: "validation_failed"
    message: "One or more fields failed validation."
    fields:
      - { field: "shares", constraint: "must be >= 1", received: "0" }
```

FastAPI's raw Pydantic 422 body is **normalized** to `ValidationErrorResponse` via a custom exception handler (`@app.exception_handler(RequestValidationError)`) rather than left as the framework default — this is a Stage 3/implementation constraint, not an API-visible inconsistency. The architecture's two confirmed 409 bodies (`conflict`, `in_use`) both fit `ErrorResponse` unmodified.

**Complete error code catalog:**

| Code | HTTP status | Used by |
|---|---|---|
| `invalid_credentials` | 401 | Login |
| `invalid_token` | 401 | Any JWT-protected endpoint (malformed/unsigned token) |
| `token_expired` | 401 | Any JWT-protected endpoint |
| `token_revoked` | 401 | Any JWT-protected endpoint (`token_version` mismatch) |
| `email_not_verified` | — *(not used to block access — BAS EX-007 explicitly states unverified users retain full trial access; this code is reserved but not wired to any 4xx response)* | — |
| `account_locked` | 429 | Login (BAS EX-009, 5 failures/10 min) |
| `validation_failed` | 422 | Any request-body-validated endpoint |
| `version_conflict` | 409 | Lot PATCH, DividendTranche PATCH |
| `in_use` | 409 | Custom BrokerConfig DELETE |
| `already_processing` | 409 | CSV import while a prior job is still processing |
| `import_limit_exceeded` | 400 | CSV import (row count > 1,000) |
| `not_found` | 404 | Any ownership-checked or existence-checked resource |
| `file_too_large` | 413 | CSV import (> 1 MB) |
| `invalid_format` | 400 | CSV import (wrong Content-Type) |
| `encoding_error` | 400 | CSV import (non-UTF-8) |
| `row_limit_exceeded` | 400 | CSV import (alias of `import_limit_exceeded` — collapsed to one code; see note below) |
| `rate_limit_exceeded` | 429 | Any rate-limited endpoint |
| `service_unavailable` | 503 | `/health` only |

**Note on `row_limit_exceeded` vs. `import_limit_exceeded`:** the Stage 2 prompt lists both terms in different sections (ADD-002's catalog request vs. ADD-010's validation-order list). These describe the same failure condition (CSV row count exceeds 1,000). **Decision: use a single code, `row_limit_exceeded`, for this condition** — carrying two codes for one failure mode would force the frontend to handle both, with no behavioural difference. `import_limit_exceeded` is dropped from the catalog.

**Stage 3 Constraint:** `components/schemas` defines `ErrorResponse` and `ValidationErrorResponse` exactly as above. Every `4xx`/`5xx` response in every path references one of these two schemas by `$ref` — no inline error schemas anywhere in the document (this also satisfies Stage 4 checklist item ER-001 in advance).

---

## ADD-003 — Pagination Strategy

**Context:** Determine which collections need server-side pagination.

**Analysis:** Walking each candidate collection against BursaTrack's actual V1 data volumes:
- `GET /api/v1/stocks` — ~1,000 rows, TTLCache-backed, autocomplete use case. Full-list-then-filter or server-side `?q=` filter are both viable; neither needs page-based pagination because the *filtered* result set (not the full list) is what's returned per request.
- `GET /api/v1/portfolio/dividends` — worst case ~2,000 records across 5 years for a single power user (David persona, PRD §6). Filtered by `?year=`, which bounds any single response to at most 50 positions × 8 tranches = 400 rows — well within a single-page response.
- `GET /api/v1/brokers` — at most ~10 rows (6 system + a handful of custom) per user.
- Position list is only ever reached via the dashboard, which already returns all positions in one response (BAS FR-011 states the dashboard must load in under 3 seconds for up to 50 positions — the PRD's own performance target assumes an unpaginated full-portfolio response).

**Decision: No endpoint requires pagination at V1.** Every collection is bounded by realistic per-user data volumes that the architecture's own performance targets (§dashboard load, CSV row limits) already assume fit in a single response. This matches the guardrail "prefer the simpler option" and the Stage 3 prompt's explicit instruction not to add pagination where it isn't required.

For `GET /api/v1/stocks`: **server-side filtering with `?q=`, minimum 1 character**, not full-list-then-client-filter. Even though the TTLCache makes a full-list response cheap for the *server*, shipping ~1,000 rows to the client on every keystroke-triggered autocomplete call is wasteful bandwidth for no benefit; server-side prefix/contains matching against the cached in-process list costs nothing extra since the list is already resident in memory.

For the dividend calendar: `?year=` is **optional**, defaulting to the current calendar year. If the client wants full history, it must request specific years explicitly (no `all=true` escape hatch at V1) — this keeps every response bounded and matches BAS FR-013's calendar framing as a forward-looking/recent view, not a historical browser.

**Stage 3 Constraint:** No `page`/`per_page` parameters anywhere in the spec. `GET /api/v1/stocks` takes `?q=` (optional, `minLength: 1` when present). `GET /api/v1/portfolio/dividends` takes `?year=` (optional integer, defaults server-side to current year).

---

## ADD-004 — Soft-Delete Visibility in GET Responses

**Decision:**
- GET collection endpoints (dashboard, position list implicit in dashboard, dividend calendar, broker list) **always** silently exclude `is_deleted = true` records. No opt-in flag to include them at V1 — there is no BAS/PRD requirement for a "deleted items" view.
- `GET /api/v1/portfolio/positions/{id}` on a soft-deleted position returns **404**, identical to the ownership-mismatch case (BAS EC-006 confirms this exact behaviour for dividend logging against a deleted position, and the architecture's uniform 404-for-cross-user pattern extends naturally to soft-deleted-but-owned resources — a deleted resource is, from the client's perspective, indistinguishable from one that was never reachable).
- The PDPA data export **excludes** soft-deleted records, per architecture §10.7's explicit table note.

**Stage 3 Constraint:** No `include_deleted` query parameter on any endpoint. `404` is documented as a response on every single-resource GET/PATCH/DELETE for both "not found" and "soft-deleted" cases — the spec does not distinguish them (and must not, since distinguishing them would leak information about resource history to a user who no longer owns/sees the resource).

---

## ADD-005 — Sell Scenario Calculator Endpoint Design

**Decision:**
- **Path and method:** `GET /api/v1/portfolio/positions/{id}/sell-scenario?shares=X&price=Y` (query params). This matches the endpoint inventory the architecture already commits to (Stage 3 prompt's endpoint table lists this exact path as `GET`).
- **Resource binding:** Position-scoped, not arbitrary inputs. BAS Workflow 6 and PRD REQ-007 both describe the calculator as pre-populating from an existing position's stored data (total shares, all-in cost, current price) — it is not a free-standing "what-if I owned X shares" tool. This also gives the operation a natural ownership check (404 on cross-user access), which a resource-unbound calculator would lack entirely.
- **Response shape:** For each price point (the architecture's default increment ladder, or explicit `?price=` overrides, or both — see below), the response includes gross proceeds, sell brokerage, sell clearing, sell stamp duty, net proceeds, profit/loss, and a `break_even: boolean` flag on the qualifying row. A fixed `disclaimer_required: true` field carries BR-020's T+2 settlement notice — always `true` at V1 since there is no scenario where the disclosure is waived.
- **Multiple price points in one call:** BAS Workflow 6 requires the calculator to render a *table* of scenarios (current price +0.01 through +0.70), not one price at a time. **Decision: the endpoint returns the full default ladder by default, and accepts an optional repeated `?price=` query parameter to add custom prices to the table** (BAS Workflow 6, "User may enter custom sell price"). This is a single request returning an array of scenario rows, not one request per price point — a per-price-point design would require 10+ round trips to render one calculator view, which is both slower and inconsistent with the "read is idempotent and cacheable" rationale for choosing GET in the first place.
- **Idempotency:** GET with query params — confirmed, no alternative considered further (POST was already ruled out by the architecture's endpoint table using GET).
- **Authentication:** JWT, with ownership check on the bound position (404 on mismatch, per the universal rule).

**Stage 3 Constraint:** `sell-scenario` accepts `shares` (optional integer, defaults to the position's full active share count) and repeatable `price` (optional array of decimal-string query values). `SellScenarioResponse` contains an array of per-price rows plus the fixed `disclaimer_required` boolean.

---

## ADD-006 — Lot and DividendTranche Update URL Design

**Decision:**
- **Lots: nested.** `PATCH /api/v1/portfolio/positions/{id}/lots/{lot_id}` and `DELETE /api/v1/portfolio/positions/{id}/lots/{lot_id}` — matches the architecture's own endpoint table (Stage 3 prompt) verbatim, which already commits to the nested form. Ownership verification checks both that `position.user_id == authenticated_user.id` **and** that `lot.position_id == position.id` (a lot ID from a different position, even one the same user owns, must not resolve — this prevents a subtle cross-position IDOR where a user enumerates lot IDs across their own positions). Either check failing returns 404.
- **DividendTranches: flat.** `PATCH /api/v1/portfolio/dividends/{id}` and `DELETE /api/v1/portfolio/dividends/{id}` — also matches the architecture's endpoint table. Ownership verification checks `dividend_tranche.position.portfolio.user_id == authenticated_user.id` transitively (BAS §9 Data Ownership Rule 4). The flat form is justified because the dividend calendar (a cross-position view) is the primary context from which edits are initiated, per BAS FR-013 — nesting under `/positions/{id}/dividends/{id}` would force the client to know the position ID even when navigating from the calendar, which does not naturally carry it grouped that way in the UI flow described in BAS Workflow 4.

**Stage 3 Constraint:** Confirmed nested-for-Lot, flat-for-Dividend URL structure exactly as the architecture's endpoint table already specifies. `UpdateLotRequest` and `UpdateDividendRequest` both require a `version` field (see ADD-002/ID-001/ID-002 in the Stage 4 checklist — flagged forward here since it is a Stage 2 design commitment, not just a Stage 4 audit item).

---

## ADD-007 — Dividend Calendar Filtering and Shape

**Decision:**
- **Year filter:** Optional, defaults to the current calendar year (per ADD-003 above — this keeps the default response bounded and matches the calendar's framing as a forward-looking/recent view).
- **Response grouping:** A **flat array** of tranche objects, not grouped by year or position. BAS FR-013 step 2 specifies "ascending chronological order by ex_dividend_date... or payment_date" — a flat, sortable array satisfies this directly; grouping would require the client to flatten it right back out to render a single chronological list.
- **Fields:** tranche ID, position ID, stock code, stock name (denormalized onto the response so the client doesn't need a second lookup per row — the calendar is explicitly a cross-position view), tranche label, per_share_amount, qualifying_shares, total_amount, ex_dividend_date, payment_date, year.
- **Scope:** `?year=` is optional with a current-year default (confirmed from ADD-003); there is no `all=true` mode at V1. This is intentionally left open for OQ-003 (BAS calendar-year-vs-financial-year decision) to resolve later without an API shape change, since the parameter is just an opaque integer year regardless of which year-boundary convention is ultimately chosen.

**Stage 3 Constraint:** `GET /api/v1/portfolio/dividends?year=2026` (optional) returns `{ tranches: [DividendTrancheResponse, ...] }` — note this is the one place a named wrapper key (`tranches`) is used rather than a bare array, consistent with ADD-001's "bare object" decision (a bare top-level JSON array is avoided as a general REST practice since it cannot carry future sibling fields without a breaking change; a single named key inside a bare object achieves the same "no meta envelope" simplicity while remaining extensible).

---

## ADD-008 — Token Refresh Response Body

**Decision:** `POST /auth/refresh` returns **200 with a body**, not 204. The body is `AuthResponse`-shaped: current user's `account_status` plus `expires_at` (the new JWT's expiry timestamp). Rationale: the architecture's silent-refresh pattern (§14.1) is specifically motivated by avoiding disruptive mid-session logouts, and returning `account_status` in the same response lets the frontend detect a subscription-state change (e.g., trial expired while the tab was open, or a webhook activated the subscription) without a second round trip to `/subscription/status`. An empty body or 204 would force a second call immediately after every silent refresh purely to re-check account status, which defeats some of the point of doing the refresh proactively in the first place.

**Stage 3 Constraint:** `POST /auth/refresh` response body is `AuthResponse` (same schema as login/register responses): `{ user: UserResponse, expires_at: <date-time> }`.

---

## ADD-009 — Admin API Key Header Convention

**Decision:**
- **Header name:** `X-Admin-API-Key`. Chosen over `Authorization: ApiKey <key>` because the `Authorization` header is already semantically claimed by the cookie-based JWT scheme for user-facing endpoints (even though admin endpoints don't use cookies, reusing `Authorization` for a structurally different auth mechanism invites confusion for anyone reading request logs or writing client code against both surfaces). Chosen over generic `X-API-Key` because `X-Admin-API-Key` is self-documenting about scope, reducing the chance of accidental reuse against a non-admin endpoint.
- **Comparison:** Constant-time string comparison (`hmac.compare_digest` in Python) — this is a Stage 4/implementation-level security requirement (SC-003) that the spec documents as a description note on the `adminApiKey` security scheme, not a schema constraint.
- **Failed-attempt logging:** Every failed admin auth attempt is written to structlog (not `audit_log`, since there is no authenticated `user_id` to attribute it to) with the source IP and timestamp, for operational visibility given this is BursaTrack's single most privileged credential.
- **Response code:** **401**, not 403. A missing or invalid `X-Admin-API-Key` is an authentication failure (the caller has not proven they hold the credential), not an authorization failure (a caller who *has* proven identity but lacks permission) — 403 would imply a caller-identity concept that doesn't exist for this shared-secret scheme. This is consistent with treating `ADMIN_API_KEY` as bearer-style authentication, matching how the JWT scheme itself returns 401 (not 403) for invalid/expired/revoked tokens.

**Stage 3 Constraint:** `adminApiKey` security scheme: `type: apiKey`, `in: header`, `name: X-Admin-API-Key`. Both admin endpoints document `401` (invalid/missing key) as a response; neither documents `403`.

---

## ADD-010 — File Upload Validation Error Precedence

**Decision:** Confirmed as specified in the prompt, in this exact order (fail fast, first violation wins):

1. `Content-Length` > 1,048,576 bytes → **413**, `error: "file_too_large"`, `message: "File exceeds the 1 MB size limit."` — checked before the body is read.
2. `Content-Type` not `text/csv` or `application/csv` → **400**, `error: "invalid_format"`, `message: "File must be a CSV file (text/csv)."`
3. File cannot be decoded as UTF-8 → **400**, `error: "encoding_error"`, `message: "File encoding error. Please save your CSV as UTF-8 before uploading."` (matches BAS EC-019's user-facing copy exactly)
4. Row count > 1,000 → **400**, `error: "row_limit_exceeded"`, `message: "File exceeds the maximum of 1,000 rows."`
5. Required columns missing from the header row → **400**, `error: "validation_failed"`, `message: "Required column '<column_name>' is missing."` (uses `ValidationErrorResponse` since this is inherently a field-level condition — the "field" is the missing column name)
6. Data-level errors (invalid stock code, invalid date, duplicate tranche label, etc.) are **not** synchronous 4xx responses at all — they are discovered during the BackgroundTask and surfaced only through `GET /import/status/{job_id}`'s `result.errors` array once the job reaches `status: failed`. This is the direct consequence of the architecture's async design (§13.6): row-level validation happens inside the BackgroundTask, after the client has already received 202.

**Stage 3 Constraint:** `POST /import/csv` documents responses `202` (accepted), `400` (checks 2–5, using `ErrorResponse` for 2–4 and `ValidationErrorResponse` for 5), `409` (already processing — see ADD-012), and `413` (check 1). It does **not** document a `422` for CSV content, since content-level errors surface asynchronously, not synchronously.

---

## ADD-011 — Stock Autocomplete Response Design

**Decision:**
- **Minimum query length:** 1 character. `q` is optional; omitting it returns the first N stocks in code order (useful for a "browse" fallback) rather than an error, since there is no harm in returning *a* result set and the TTLCache makes this cheap.
- **Response fields:** code, name, market, sector, instrument_type, is_active. `is_active = false` stocks are **excluded** from every response, per the prompt's own note that inactive stocks cannot be added as new positions — filtering server-side avoids shipping dead options to the autocomplete UI.
- **Result limit:** 10 matches maximum, ranked by match quality (prefix match on `code` ranked above prefix match on `name`, both ranked above contains-match).
- **Match strategy:** prefix-or-contains on both `code` and `name` (a user typing "CIMB" should match stock name "CIMB GROUP HOLDINGS BHD"; a user typing "1023" should match the code directly) — a pure prefix-only strategy on `code` alone would fail the common case of a user searching by company name, which BAS §7 CSV template examples suggest is at least as common as searching by code.

**Stage 3 Constraint:** `GET /api/v1/stocks?q=` — `q` optional string, `minLength: 1` when present. Response: `{ stocks: [StockResponse, ...] }` (bare-object-with-named-key pattern, consistent with ADD-007), capped at 10 items, `is_active` always `true` in every returned item (the field is still present in `StockResponse` for schema completeness/reuse, but the endpoint's filtering guarantees the value).

---

## ADD-012 — Concurrent Import Handling

**Decision:** Confirmed as specified. `POST /import/csv`, when the calling user already has an `ImportJob` in `processing` status, returns **409** with `{"error": "already_processing", "message": "An import is already in progress. Please wait for it to complete or check its status.", "job_id": "<uuid>"}`. The `job_id` is included specifically so the client can redirect straight to the polling view without a separate lookup call — the alternative (omitting it and forcing the client to have already tracked the job_id from the original 202, which it may have lost on a page refresh) creates an unrecoverable dead end for a user who navigates away and back during an import.

Note this means `ErrorResponse` needs one addendum for this specific case: an optional `job_id` field. Rather than creating a third error schema for one field, **`ErrorResponse` gains an optional `job_id` property** (nullable, absent on every other error), since introducing a bespoke `AlreadyProcessingError` schema for a single endpoint's single error case would violate the "prefer the simpler option" guardrail and the ER-001 requirement that all errors share a common base shape.

**Stage 3 Constraint:** `ErrorResponse` schema gains `job_id: { type: string, format: uuid, nullable: true }`. `POST /import/csv` documents `409` referencing `ErrorResponse` with an example that populates `job_id`.

---

## ADD-013 — CSV Template Download Delivery Mechanism

**Context:** Stage 4 review finding PD-000 identified that BAS FR-015 ("CSV Template Download," User Story US-019) has no corresponding operation anywhere in the architecture's endpoint inventory, so Stage 3 correctly did not invent one. This left a BAS Must-Have requirement with no API surface at all.

**Decision:** `BursaTrack_Import_Template.csv` is served as a **static frontend asset** (e.g. a file in the Next.js `public/` directory, or an equivalent static-hosting path on Vercel), not as a versioned API endpoint. Rationale: the file is a fixed, non-personalized, non-authenticated document — identical for every user and every request — so it carries none of the characteristics (per-user data, authentication, business logic) that would justify API-layer involvement. Routing it through the API would only add latency and an unnecessary FastAPI round-trip for a file that never changes per request.

Architecture §13.6's CSV injection defence note ("on CSV template download... strip or quote cell values beginning with `=`, `+`, `-`, `@`") does not apply under this decision, since the template's column headers and example rows are fixed content authored by BursaTrack, not derived from any user-supplied or database-sourced value — there is nothing dynamic in the file for a formula-injection payload to attach to.

**Stage 3 Constraint:** No new path is added to `03-openapi-specification.md`. A note is recorded in that document's "Notes for Implementation" section so an implementer does not later conclude the template endpoint was simply forgotten.

**Escalation status:** This resolves PD-000 as an API-design decision. It does not require the solution architect to add an endpoint to the architecture's inventory, since no endpoint is being added — it only requires the frontend build to include the static file, which is outside this workflow's scope.

---

## Cross-Cutting Confirmations

Per the guardrail requiring every decision touching DividendTranche or write endpoints to confirm P0 preservation:

- **ADD-002, ADD-006, ADD-007** (all DividendTranche-touching decisions) confirm: no error schema, URL design, or response shape introduced here creates any path for a client to supply `total_amount`. `UpdateDividendRequest`'s fields are enumerated exhaustively in the Stage 3 prompt's schema list and `total_amount` is not among them; this decision record does not add it.
- **ADD-005, ADD-006** (write-endpoint-adjacent decisions — sell scenario is read-only but touches Lot-derived cost data; Lot update URL design) confirm: no fee field (`brokerage_fee`, `clearing_fee`, `stamp_duty`, `all_in_cost`) is introduced as an accepted input anywhere in this record. `UpdateLotRequest` accepts only `shares`, `purchase_price`, `broker_id`, `purchase_date`, and `version` — the server recomputes all fee fields on every update, identical to creation.

## Open Questions Carried Forward to Stage 3 / Implementation

1. Admin endpoint rate limiting (flagged in Stage 1 §10.2) remains unresolved by the architecture. **Stage 3 recommendation:** apply the same 60/minute-per-key limit used for standard authenticated endpoints, keyed by the API key value itself rather than IP (a shared admin credential may be used from a dynamic IP), pending explicit architect sign-off. This is a recommendation, not a re-opened architectural decision — the architecture did not specify *any* number, so proposing one is filling a gap, not overriding a stated constraint.
2. BAS OQ-005 (sell-calculator default broker for multi-lot positions) and OQ-003 (dividend year semantics) remain business-decision open items; both are designed around per §6/§7 above so that resolving them later requires no API contract change.
