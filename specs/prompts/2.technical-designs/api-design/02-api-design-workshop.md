# Stage 2 — API Design Decision Workshop

## Your Role and Task

You are a principal API architect producing the design decision record for BursaTrack. The solution architect has already resolved the major structural decisions (protocol, auth mechanism, framework, rate limits). The Stage 1 requirements analysis has mapped all operations. Your job is to resolve the design decisions the architecture left implicit — the ones needed to translate the operation inventory into a complete, consistent API contract.

You are not re-opening closed architectural decisions. You are filling the gaps between the architecture's high-level endpoint list and the formal OpenAPI specification that Stage 3 will produce.

---

## Documents Provided

You have been given:
- Stage 1 API Requirements Report
- Solution Architecture Document (endpoint inventory at §7.2, §10–§11; auth design at §14; rate limits at §14.4)

---

## Decisions Already Made — Do Not Re-Open

| Decision | Specification |
|----------|--------------|
| Protocol | HTTP/HTTPS only |
| Auth mechanism | RS256 JWT in HTTP-only Secure SameSite=Lax cookie |
| Session revocation | token_version INTEGER validated on every protected request |
| Ownership enforcement code | 404, never 403 |
| Rate limiting | SlowAPI in-process; rates defined per endpoint class in architecture §14.4 |
| CORS | Static allowlist + BursaTrack Vercel preview regex (architecture §14.3) |
| API URL prefix | `/api/v1/` for all resource endpoints |
| Admin auth | `ADMIN_API_KEY` header (not JWT) |
| Webhook auth | Stripe-Signature header verification |
| Async import | 202 Accepted + polling |
| Monetary type | JSON string (Python Decimal serialized as string) |
| Timestamp format | ISO 8601 UTC |

---

## Decisions to Make in This Stage

For each topic, analyse the supplied documents and produce a decision record. Where the architecture is explicit, confirm it. Where it is silent or ambiguous, analyse options and make a recommendation with rationale.

---

### ADD-001 — Response Envelope Design

The architecture describes endpoint responses but does not specify whether responses use a bare object or a wrapper envelope.

**Options:**
- **Bare object** (FastAPI default): `{"id": "...", "stock_code": "CIMB", ...}`. Simpler; no wrapper parsing.
- **Envelope wrapper**: `{"data": {...}, "meta": {"request_id": "..."}}`. Enables consistent meta attachment but adds client-side unwrapping.

**Considerations:**
- FastAPI returns bare objects by default and this is widely accepted for JSON REST APIs
- The dashboard endpoint returns aggregated data across multiple resource types — a bare object with named keys is cleaner than an envelope here
- Error responses already use a different shape (not a data/meta envelope); mixing envelopes creates inconsistency
- BursaTrack V1 has no need for request tracing IDs, pagination cursors in the envelope, or other meta fields that make envelopes valuable

Decide: bare object or envelope. If envelope, define the exact structure. Specify whether errors follow the same envelope.

### ADD-002 — Universal Error Response Schema

The architecture shows two specific 409 error bodies but no general schema. The API needs a single consistent error response structure across all error conditions.

**Required in every error response:**
- A machine-readable `error` code (e.g., `"version_conflict"`, `"in_use"`, `"validation_failed"`)
- A human-readable `message` string (displayable to end users)

**Additional considerations:**
- 422 Unprocessable Entity (FastAPI Pydantic validation) returns `{"detail": [...]}` by default with field-level errors — should this be normalized to the same schema as other errors, or left as FastAPI's default?
- Should field-level validation errors include both the field name and the violated constraint (e.g., `{"field": "shares", "constraint": "must be >= 1", "received": 0}`)?
- The architecture specifies exactly: optimistic locking returns `{"error": "conflict", "message": "..."}` and broker-in-use returns `{"error": "in_use", "message": "..."}`. Confirm these fit the general schema.

**Error catalog to define** — produce a complete list of machine-readable error codes for all error conditions:
- Auth errors (invalid_token, token_expired, token_revoked, email_not_verified)
- Validation errors (validation_failed, field-level codes as needed)
- Business rule conflicts (version_conflict, in_use, already_processing, import_limit_exceeded)
- Resource errors (not_found)
- File errors (file_too_large, invalid_format, encoding_error, row_limit_exceeded)
- Rate limit errors (rate_limit_exceeded)
- Server errors (service_unavailable)

Decide: the exact JSON schema for error responses and the complete error code catalog.

### ADD-003 — Pagination Strategy

The architecture does not define a pagination strategy. Some endpoints return collections that could grow large.

**Collections that need pagination analysis:**
- `GET /api/v1/stocks` — Bursa Malaysia has ~1,000 listed securities. The autocomplete use case requires fast partial-match results, not full-list pagination. The stock reference table is cached in FastAPI TTLCache.
- `GET /api/v1/portfolio/dividends` — A user who has tracked 5 years × 50 positions × 8 tranches = 2,000 records. The calendar view is filtered by year (implied), not paginated across all years.
- Audit log in PDPA export — included in the export file, not an API-browsable collection.
- `GET /api/v1/brokers` — Small collection (6 system + user's custom). No pagination needed.

**For `GET /api/v1/stocks` autocomplete:**
- Should return all stocks (full list for initial load, then client-side filter), OR
- Should filter server-side with `?q=` and require minimum 1–2 characters before querying
- The TTLCache suggests full-list-then-filter is viable; the 60-minute cache means the list rarely hits the database

**For dividend calendar:**
- The `?year=` query parameter is mentioned but not specified. What is the default? (current year)
- What happens if no `year` is supplied? Return current year, or all years grouped by year?

Decide: which collections require server-side pagination, the exact pagination parameters (`?page=1&per_page=50` offset-based), and whether paginated responses use a wrapper or include a `Link` header.

### ADD-004 — Soft-Delete Visibility in GET Responses

Soft-deleted records (`is_deleted = true`) should not appear in normal API responses. But the architecture doesn't explicitly address edge cases.

Decide:
- Do GET collection endpoints (e.g., GET /portfolio/positions) always silently exclude soft-deleted records? (yes, almost certainly)
- Is there ever a reason to expose soft-deleted records to the client? (e.g., a "deleted positions" history view — not in scope for V1 based on PRD)
- If a client requests a specific soft-deleted resource by ID (GET /positions/{id}), does it return 404? (yes — consistent with ownership enforcement pattern)
- Does the PDPA data export include soft-deleted records? (no — architecture §10.7 explicitly excludes them)

### ADD-005 — Sell Scenario Calculator Endpoint Design

The PRD references a sell scenario calculator that computes projected fees and net proceeds for a hypothetical sale. The architecture mentions it but doesn't specify the endpoint shape.

Decide:
- **Path and method**: `GET /api/v1/portfolio/positions/{id}/sell-scenario?shares=X&price=Y` (query params for read-only computation) OR `POST /api/v1/portfolio/calculator` (request body with position context)
- **Resource binding**: Should the calculator require a valid position ID (scoped to user's position), or accept arbitrary inputs (stock code, shares, price) without resource binding?
- **Response shape**: What does the response contain? At minimum: computed fee components (brokerage, clearing, stamp duty), total all-in cost to sell, net proceeds, and the T+2 disclaimer flag.
- **Idempotency**: GET with query params is idempotent and cacheable; POST with body is not. GET is preferred for pure calculations.
- **Authentication**: Must be authenticated (ownership check on position ID if position-bound)

### ADD-006 — Lot and DividendTranche Update URL Design

The architecture references updating Lots and DividendTranches but the exact URL patterns are not fully specified.

For Lots:
- The architecture shows `POST /api/v1/portfolio/positions/{id}/lots` for adding a lot to a position. But updating or deleting a specific lot requires addressing the lot directly.
- Options: `PATCH /api/v1/portfolio/positions/{id}/lots/{lot_id}` (nested) vs `PATCH /api/v1/portfolio/lots/{lot_id}` (flat)
- The nested pattern is more RESTful (a lot belongs to a position) but requires the position ID in the URL even if only the lot is being updated

For DividendTranches:
- `PATCH /api/v1/portfolio/dividends/{id}` is stated in the architecture. Is this always addressed at the top level (not nested under position)?
- A user may have dividend tranches for multiple positions — flat addressing (`/dividends/{id}`) is simpler for the calendar view

Decide: the complete URL patterns for Lot CRUD and DividendTranche CRUD, with the ownership verification strategy for each.

### ADD-007 — Dividend Calendar Filtering and Shape

`GET /api/v1/portfolio/dividends` serves a calendar view of all dividend tranches for the user's portfolio.

Decide:
- **Year filter**: Is `?year=2026` a required query parameter, or optional with a default (current year)?
- **Response grouping**: Does the response return a flat array of dividend tranche objects, or grouped by year or by position?
- **Fields**: The calendar view likely shows different fields than the detail view. What does the calendar response include? At minimum: tranche ID, position ID, stock code, tranche label, per_share_amount, qualifying_shares, total_amount, ex_dividend_date, payment_date, year.
- **Scope**: Does this endpoint return all years of dividend history (with year as optional filter), or does year become required once the user has >1 year of history?

### ADD-008 — Token Refresh Response Body

`POST /auth/refresh` returns a new JWT cookie. The architecture states it returns `200 OK` but doesn't specify the response body.

Decide:
- Does the refresh response include a body? If so, what?
- Options: empty body `{}`, user state `{account_status, token_expiry}`, or no body with 204 No Content
- The frontend needs to know when the next refresh is due — does it decode the JWT for the expiry, or does the API return `expires_at`?
- Should the refresh response return the current account status? This would allow the frontend to detect subscription status changes between sessions without a separate call.

### ADD-009 — Admin API Key Header Convention

The architecture states that admin endpoints are protected by `ADMIN_API_KEY` but doesn't specify the request header name or format.

Decide:
- Header name: `X-Admin-API-Key`, `Authorization: ApiKey <key>`, or `X-API-Key`?
- Is the header validated with constant-time string comparison (to prevent timing attacks)?
- How are failed admin auth attempts logged?
- Should the admin endpoint return 401 (treated like auth failure) or 403 (auth succeeded but permission denied)?

### ADD-010 — File Upload Validation Error Precedence

`POST /import/csv` has multiple validation checks (size, content type, encoding, row count, header format). When multiple validations fail simultaneously, the response must prioritize them clearly.

Decide the validation order (reject on first failure):
1. Content-Length > 1 MB → 413 Payload Too Large (before reading the body)
2. Content-Type is not text/csv or application/csv → 400 Bad Request
3. File cannot be decoded as UTF-8 → 400 Bad Request
4. Row count > 1,000 → 400 Bad Request
5. Required columns missing from header row → 400 Bad Request
6. Data-level errors (invalid stock code, invalid date) → discovered during BackgroundTask processing → reflected in ImportJob result

Confirm this ordering or adjust. Specify the exact `error` code and `message` for each validation failure.

### ADD-011 — Stock Autocomplete Response Design

`GET /api/v1/stocks?q=search_term` serves an autocomplete component in the portfolio entry form.

Decide:
- **Minimum query length**: must `q` have at least 1 character? 2 characters? Is `q` optional (returns all)?
- **Response fields**: what fields are returned per stock? (code, name, market, sector, instrument_type, is_active — but is_active=false stocks should probably be excluded)
- **Result limit**: is there a maximum number of results? (e.g., top 10 matches)
- **Match strategy**: prefix match on code OR contains match on code OR code OR name?
- **Inactive stocks**: should stocks with `is_active = false` appear? (no — they cannot be added as new positions)

### ADD-012 — Concurrent Import Handling

The architecture says one active import per user at a time. But the exact API behaviour when a second import is requested while one is already running is not specified.

Decide:
- When `POST /import/csv` is called and the user already has an ImportJob in `processing` state: return 409 Conflict with `{"error": "already_processing", "message": "An import is already in progress. Please wait for it to complete or check its status."}` and optionally include the `job_id` of the existing job?
- Should the existing `job_id` be returned in the 409 response so the client can redirect to the status polling endpoint?

---

## Deliverable: API Design Decision Record

For each decision (ADD-001 through ADD-012), produce a structured record:

**Decision ID**: ADD-NNN  
**Topic**: Short descriptive title  
**Context**: Why this decision matters for BursaTrack's API design  
**Analysis**: What the architecture says; what the Stage 1 analysis implies; any constraints  
**Options** (if multiple viable approaches exist): With trade-offs  
**Decision**: The recommended approach with rationale  
**Stage 3 Constraint**: The specific requirement this places on the OpenAPI specification  
**Open questions** (if any remain unresolved)

---

## Guardrails

- Do not re-open any decision listed under "Decisions Already Made"
- Do not write OpenAPI YAML — that is Stage 3
- Every decision that touches DividendTranche must confirm it preserves P0-API-003 (no client-supplied total_amount)
- Every decision that touches a write endpoint must confirm it preserves P0-API-002 (no client-supplied fees)
- Do not invent endpoints or operations not grounded in the Stage 1 requirements analysis
- Prefer the simpler option when both options are viable — BursaTrack is an MVP, not a platform
