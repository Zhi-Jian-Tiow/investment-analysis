# Stage 4 — API Security and Quality Review

## Your Role and Task

You are a senior API security reviewer acting as the final quality gate before the BursaTrack API specification is handed to engineering for implementation. Your job is to find real problems — missing authentication, authorization gaps, financial data serialization risks, PDPA exposure, input validation gaps, error response inconsistencies, and OWASP API security violations.

Review the Stage 3 OpenAPI specification as if you were the engineer who will implement it and the attacker who will probe it. Be specific. Be actionable. Prioritise by real-world impact.

---

## Documents Provided

You have been given:
- Stage 3 OpenAPI Specification (the specification to review)
- Stage 1 API Requirements Report
- Stage 2 API Design Decision Record
- Solution Architecture Document

---

## Severity Taxonomy

Grade every finding using these levels. Be accurate — over-grading dilutes trust in the review.

| Severity | Definition | Examples |
|----------|------------|---------|
| **CRITICAL** | Exploitable vulnerability, financial data corruption, PDPA non-compliance, or broken auth. Blocks implementation. | Endpoint missing auth; monetary field typed as number; ownership check absent; PII in URL |
| **HIGH** | Would cause incorrect behaviour, data exposure, or user-visible errors in production. Must be fixed before launch. | Missing rate limit; 403 returned instead of 404; missing version field for optimistic locking; incorrect status code |
| **MEDIUM** | Edge case incorrectness, operational pain, or API maintainability risk. Should be fixed before launch. | Missing field-level validation; inconsistent error schema; missing audit annotation; ambiguous nullable |
| **LOW** | Naming inconsistency, missing description, or minor style issue. Fix when convenient. | Missing example; unclear summary text; redundant query parameter |

---

## Review Checklist

Work through each category systematically. For every finding, provide:
- **Finding ID**: Category prefix + sequential number (e.g., FC-001, AA-003)
- **Severity**
- **Affected endpoint and field**
- **What is wrong**: Precise description
- **Recommendation**: Specific fix, including schema YAML if relevant

---

### Category FC — Financial Correctness

These are the highest-stakes checks. A single float escaping in an API response breaks the product's core value proposition.

- [ ] **FC-001**: Is every monetary and rate field in every response schema typed as `type: string`? Check individually: purchase_price, brokerage_fee, clearing_fee, stamp_duty, all_in_cost, per_share_amount, total_amount, price (PriceSnapshot), rate (BrokerConfig), all SellScenarioResponse fields. Zero exceptions.
- [ ] **FC-002**: Is yield percentage absent from every response schema? Yield is computed client-side and must never appear in a response body.
- [ ] **FC-003**: Do any Lot creation or update request schemas include `brokerage_fee`, `clearing_fee`, `stamp_duty`, or `all_in_cost` as accepted input fields? These must not exist in any request schema.
- [ ] **FC-004**: Does the DividendTranche creation request schema exclude `total_amount`? The server computes `total_amount = per_share_amount × qualifying_shares`. A client-supplied `total_amount` must never be accepted.
- [ ] **FC-005**: Does the DividendTranche PATCH request schema exclude `total_amount`? The server always recomputes `total_amount` when `per_share_amount` or `qualifying_shares` changes.
- [ ] **FC-006**: Are monetary fields in request schemas typed as `type: string` (not `type: number`)? The client must send decimal values as strings to preserve precision through JSON serialization.
- [ ] **FC-007**: Does the SellScenarioResponse include all computed fee components as strings? Check: projected_brokerage, projected_clearing_fee, projected_stamp_duty, projected_all_in_sell_cost, projected_net_proceeds.

### Category AA — Authentication and Authorization

- [ ] **AA-001**: Does every endpoint in the spec have a `security` field? Public endpoints must explicitly declare `security: []`. Protected endpoints must declare the correct scheme. An endpoint without a `security` field inherits the global default — if no global default is set, it is unauthenticated.
- [ ] **AA-002**: Do all portfolio, pricing, import, subscription, and account endpoints require `cookieAuth`?
- [ ] **AA-003**: Do admin endpoints (`/admin/config/fees`) require `adminApiKey`, not `cookieAuth`?
- [ ] **AA-004**: Does `POST /webhooks/stripe` require `stripeSignature`, not `cookieAuth`?
- [ ] **AA-005**: Do public endpoints (register, login, password-reset-request, health, cancel-deletion, verify, jwks.json) explicitly declare `security: []`?
- [ ] **AA-006**: Is there documentation for the `token_version` validation mechanism? The spec should note (in the cookieAuth description or in a global security description) that the JWT is also validated against the user's current `token_version`, and that a mismatch returns 401.
- [ ] **AA-007**: Does every endpoint that returns user-owned data (Position, Lot, DividendTranche, ImportJob, custom BrokerConfig, manual PriceSnapshot) document that cross-user access returns 404, not 403? Verify that 403 does not appear as a response code on these endpoints.
- [ ] **AA-008**: Does `GET /auth/verify` validate the `token` query parameter against `pending_tokens` and check `used_at IS NULL` and `expires_at > now()`? Is the spec clear that an already-used or expired token returns 400 (not 200)?
- [ ] **AA-009**: Does `GET /account/cancel-deletion` validate the deletion cancellation token before performing any state change? The spec must document that an invalid, expired, or already-used token returns 400.

### Category ID — Idempotency

- [ ] **ID-001**: Does the `UpdateLotRequest` schema include a required `version INTEGER` field? PATCH on a lot without a version field cannot use optimistic locking.
- [ ] **ID-002**: Does the `UpdateDividendRequest` schema include a required `version INTEGER` field? Same requirement.
- [ ] **ID-003**: Are the optimistic locking 409 responses documented on every PATCH endpoint for Lot and DividendTranche? The 409 response body must use the `ErrorResponse` schema with `error: "version_conflict"`.
- [ ] **ID-004**: Does `POST /webhooks/stripe` document idempotent re-delivery behaviour? The spec must state that re-delivery of an already-processed event returns 200 immediately.
- [ ] **ID-005**: Does `POST /import/csv` document the 409 response when an import is already in progress? The `error: "already_processing"` response should include the existing `job_id`.
- [ ] **ID-006**: Is `POST /auth/password-reset-request` documented to always return 200 regardless of whether the email exists? The spec must note that this is intentional (account enumeration protection) and the response body is identical for both cases.

### Category IV — Input Validation

- [ ] **IV-001**: Is `shares` (Lot creation) constrained with `minimum: 1`? An integer with no minimum allows `shares: 0` or negative values.
- [ ] **IV-002**: Is `qualifying_shares` constrained with `minimum: 1`?
- [ ] **IV-003**: Is `tranche_label` constrained to the enum `["1st","2nd","3rd","4th","5th","6th","7th","8th"]`?
- [ ] **IV-004**: Is `category_tag` constrained to the enum `["Dividend","Volatile","Growth"]`?
- [ ] **IV-005**: Is `fee_type` (BrokerConfig) constrained to `["percentage","flat"]`?
- [ ] **IV-006**: Is `confirmation` (DeleteAccountRequest) constrained to `enum: ["DELETE"]`? This prevents accidental deletions.
- [ ] **IV-007**: Is the CSV file upload documented with: max Content-Length of 1 MB (1,048,576 bytes); accepted Content-Type of `text/csv` or `application/csv`; max row count of 1,000? Are 413 and 400 response codes documented for these violations?
- [ ] **IV-008**: Does the spec document CSV injection defence? (Cells starting with `=`, `+`, `-`, `@` are stripped or quoted.) This is an application behaviour note, not a schema constraint, but it must appear in the endpoint description.
- [ ] **IV-009**: Is the `purchase_price` string field documented with a format constraint (up to 4 decimal places)? A free-format string allows arbitrary non-numeric input that the server would reject but the spec should constrain.
- [ ] **IV-010**: Is the `per_share_amount` string field documented with a format constraint (up to 6 decimal places, as per BAS BR-026)?
- [ ] **IV-011**: Are email fields validated with `format: email` in schema definitions?
- [ ] **IV-012**: Is the password field constrained with `minLength`? (Minimum 8 characters is industry standard; confirm against BAS validation rules.)
- [ ] **IV-013**: Does `GET /api/v1/stocks?q=` document minimum query length if a minimum was decided in ADD-011?

### Category PD — PDPA Compliance

PDPA violations are CRITICAL findings.

- [ ] **PD-001**: Does `GET /api/v1/account/export` return a streaming file download, not a JSON object? The spec must define the response as `application/octet-stream` or `application/json` with `Content-Disposition: attachment` — not a schema of field names, since the client receives a file, not an API response body.
- [ ] **PD-002**: Does the data export response description explicitly state what is included (User fields, Portfolio, Position, Lot, DividendTranche, custom BrokerConfig, ImportJob, AuditLog) and excluded (password_hash, token_version, soft-deleted records, shared PriceSnapshot, system BrokerConfig)?
- [ ] **PD-003**: Does `GET /account/cancel-deletion` use a query parameter for the token (`?token=xxx`), NOT a path parameter (`/cancel-deletion/{token}`)? Path parameters appear in server access logs. Query parameters in HTTPS requests are encrypted but may still appear in logs — document that the token is single-use and expires after 24 hours.
- [ ] **PD-004**: Does `GET /auth/verify` use a query parameter for the token (`?token=xxx`), NOT a path parameter?
- [ ] **PD-005**: Does `POST /auth/password-reset` use the token in the request body, NOT in the URL?
- [ ] **PD-006**: Does the deletion initiation endpoint (`POST /account/delete`) document: (a) the session is invalidated immediately, (b) the 30-day grace period before permanent deletion, (c) the confirmation email with cancellation link?
- [ ] **PD-007**: Do response schemas for UserResponse and any other schemas that include user data exclude `password_hash` and `token_version`? These must never appear in any API response.
- [ ] **PD-008**: Do error response schemas avoid including PII? Error messages must not include email addresses, user IDs, or other identifying information that could be exposed through error leakage.
- [ ] **PD-009**: Does `POST /account/delete` produce an audit_log entry (`DELETION_REQUESTED`) documented in the spec? Is the audit event annotation present?

### Category SC — Security Hardening

- [ ] **SC-001**: Is the CORS policy documented in the spec's `info.description` or server annotations? Reviewers and integrators need to know which origins are allowed.
- [ ] **SC-002**: Are JWT cookie security attributes (`HttpOnly`, `Secure`, `SameSite=Lax`) documented in the `cookieAuth` security scheme description?
- [ ] **SC-003**: Does the spec document that `ADMIN_API_KEY` validation uses constant-time string comparison? This is a description note — not a schema constraint — but it must be in the spec for the implementing engineer.
- [ ] **SC-004**: Does `POST /webhooks/stripe` document that the `Stripe-Signature` header is verified using the Stripe webhook secret before any event data is processed or trusted?
- [ ] **SC-005**: Does `POST /auth/password-reset-request` document that it returns 200 with an identical response body regardless of whether the email exists (account enumeration protection)?
- [ ] **SC-006**: Are rate limits documented for all endpoint groups? The 429 response with `Retry-After` header must be documented on every rate-limited endpoint.
- [ ] **SC-007**: Does the spec document that all responses with user-owned data perform an ownership check that returns 404 for cross-user access? This should appear in the `cookieAuth` scheme description or as a global note.

### Category ER — Error Response Consistency

- [ ] **ER-001**: Do all 4xx and 5xx responses reference the `ErrorResponse` or `ValidationErrorResponse` schema from components? No inline error schemas — all must be refs.
- [ ] **ER-002**: Is 422 Unprocessable Entity documented consistently across all POST and PATCH endpoints? 422 is FastAPI's default for Pydantic validation failures and must be documented everywhere input validation can fail.
- [ ] **ER-003**: Is 401 Unauthorized documented on every JWT-protected endpoint?
- [ ] **ER-004**: Is 429 Too Many Requests documented on every rate-limited endpoint, with a note about `Retry-After`?
- [ ] **ER-005**: Is 503 Service Unavailable limited to `GET /health`? It should not appear as a possible response on other endpoints (database failures will manifest as 500, not 503, from the client's perspective).
- [ ] **ER-006**: Are 409 Conflict responses accompanied by a schema that includes an `error` code distinguishing the conflict type? (`version_conflict` vs `in_use` vs `already_processing` must be distinguishable in the response body so clients can handle them differently.)
- [ ] **ER-007**: Is the error response body for the 413 Payload Too Large documented (or does the spec rely on the platform/proxy returning a non-JSON body)? If the CSV upload size check happens in FastAPI, the response body must be an `ErrorResponse`.
- [ ] **ER-008**: Do all error responses include the `error` machine-readable code (not just `message`)? The frontend must be able to distinguish error types programmatically.

### Category OQ — Operational Quality

- [ ] **OQ-001**: Does every state-changing endpoint have an `x-audit-event` annotation matching an event from architecture §14.7? Check: POST /positions (LOT_CREATED), PATCH /positions/{id}/lots/{lot_id} (LOT_UPDATED), DELETE /positions/{id}/lots/{lot_id} (LOT_DELETED), POST /dividends (DIVIDEND_CREATED), PATCH /dividends/{id} (DIVIDEND_UPDATED), DELETE /dividends/{id} (DIVIDEND_DELETED), POST /pricing/manual-override (PRICE_OVERRIDE_CREATED), POST /import/csv (not an audit event — IMPORT_COMPLETED fires when job completes), POST /subscription/checkout (SUBSCRIPTION_ACTIVATED fires via webhook), POST /account/delete (DELETION_REQUESTED), GET /account/export (DATA_EXPORT_DOWNLOADED), PATCH /admin/config/fees (CONFIG_UPDATED).
- [ ] **OQ-002**: Is `GET /health` documented as unauthenticated (`security: []`) and returning `{"status": "ok", "db": "ok"}` on 200 and `{"status": "error", "db": "unreachable"}` on 503?
- [ ] **OQ-003**: Does `GET /import/status/{job_id}` document ownership verification? A user must not be able to poll another user's import job status.
- [ ] **OQ-004**: Is the TTLCache behaviour documented for `GET /api/v1/stocks` and `GET /admin/config/fees`? Consumers should know responses may be up to 60 minutes stale.
- [ ] **OQ-005**: Does `DELETE /api/v1/portfolio/positions/{id}` document the cascade behaviour — that soft-deleting a position also soft-deletes all its lots and all associated dividend tranches?
- [ ] **OQ-006**: Does `PATCH /admin/config/fees` document that the TTLCache is invalidated immediately after the update (so the next GET returns the new value within the current process)?

### Category OW — OWASP API Security Top 10

Check each OWASP API Top 10 item against the specification:

- [ ] **OW-001 Broken Object Level Authorization (BOLA/IDOR)**: Does the spec consistently document 404 (not 403) for cross-user resource access on every user-scoped endpoint? Is there any endpoint where a user ID can be substituted in the URL to access another user's data?
- [ ] **OW-002 Broken Authentication**: Is the JWT cookie authentication documented with all security flags? Is token_version revocation documented? Are token expiry and silent refresh documented?
- [ ] **OW-003 Broken Object Property Level Authorization**: Do response schemas expose any fields that should not be returned to the authenticated user? (Check: password_hash, token_version, other users' data in shared resources.) Do write request schemas accept any fields the server should own? (Check: fee fields, total_amount, is_system.)
- [ ] **OW-004 Unrestricted Resource Consumption**: Are all rate limits documented? Is the CSV upload size limit documented? Is the row count limit documented? Is there any endpoint where a user could trigger disproportionate server work without a rate limit?
- [ ] **OW-005 Broken Function Level Authorization**: Are all admin endpoints behind `adminApiKey`? Is there any endpoint that performs privileged actions without appropriate authentication?
- [ ] **OW-006 Unrestricted Access to Sensitive Business Flows**: Is there rate limiting on account registration to prevent account farming? Is there rate limiting on the subscription checkout to prevent payment flow abuse? Is there protection against a user looping through delete/cancel to harvest deletion confirmation emails?
- [ ] **OW-007 Server-Side Request Forgery (SSRF)**: Does any endpoint accept a URL as input and make a server-side HTTP request to it? (No SSRF risk apparent in BursaTrack, but confirm.)
- [ ] **OW-008 Security Misconfiguration**: Is CORS documented correctly (no wildcard allowed with credentials)? Are JWT cookies documented with all three security flags? Is there any endpoint missing TLS documentation (all traffic is HTTPS only)?
- [ ] **OW-009 Improper Inventory Management**: Are all 28+ endpoints in the spec? Is there any endpoint in the architecture (§7.2, §10-§11) not in the spec, or any endpoint in the spec not in the architecture?
- [ ] **OW-010 Unsafe Consumption of APIs**: Does the Stripe webhook endpoint validate the Stripe-Signature before processing any event? Is there documentation that the webhook payload is not trusted until signature verification succeeds?

---

## Deliverable: API Security and Quality Review Report

### 1. Overall Assessment

One paragraph: Is this specification ready for implementation? What is the overall risk level? How many CRITICAL and HIGH findings were identified?

### 2. Findings by Severity

List all findings, ordered CRITICAL → HIGH → MEDIUM → LOW. For each:

```
[FC-001] CRITICAL — LotResponse.brokerage_fee
Problem: Field is typed `type: number` in the response schema. JSON number
         serialization of Python Decimal will produce floating-point imprecision
         (e.g., 41996.469999... instead of 41996.47), breaking financial accuracy.
Fix:     Change to `type: string, format: decimal` in the LotResponse schema.
         Configure FastAPI's Pydantic model with json_encoders={Decimal: str}.
```

### 3. Items Confirmed Correct

List what you checked and found correctly implemented. This gives the engineering team confidence about what does not need to change.

### 4. Prioritised Change List

A numbered list of all required changes before implementation, ordered by severity. Include the specific schema YAML change for CRITICAL and HIGH findings.

### 5. Open Questions

Any items requiring a stakeholder or architect decision before implementation can begin. Do not block on LOW findings.

---

## Guardrails

- Be specific. "Ensure the endpoint is secure" is not a finding. "The `GET /api/v1/portfolio/positions/{id}` endpoint documents `200 OK` and `404 Not Found` but not `401 Unauthorized`. An unauthenticated request to this endpoint will return 401, but the spec does not document this, leaving frontend developers to discover it through testing." is a finding.
- Grade accurately. Reserve CRITICAL for exploitable vulnerabilities, financial data corruption, and PDPA non-compliance.
- Every finding about DividendTranche must state whether it violates P0-API-003 (total_amount write protection).
- Every finding about Lot creation must state whether it violates P0-API-002 (server-authoritative fees).
- Every finding about monetary fields must state whether it violates P0-API-001 (decimal serialization).
