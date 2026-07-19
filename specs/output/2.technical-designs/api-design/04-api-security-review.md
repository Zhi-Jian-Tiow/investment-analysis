# BursaTrack — API Security and Quality Review

## Stage 4 of 4: Final Quality Gate

> **Author:** Senior API Security Reviewer (API Design Workflow — Stage 4)<br>
> **Date:** 2026-07-01<br>
> **Reviewed artefact:** `03-openapi-specification.md` (as revised — `PortfolioResponse.portfolio_blended_yield` was removed during drafting, before this review; see Items Confirmed Correct §3)<br>
> **Inputs:** Stage 3 OpenAPI Specification · Stage 1 API Requirements Report · Stage 2 API Design Decision Record · BursaTrack Solution Architecture Document

---

## 1. Overall Assessment

The specification is **implementation-ready with two required fixes** before engineering begins building against it. Financial-correctness (P0-API-001/002/003), ownership enforcement (P0-API-004), and PDPA-sensitive URL/token handling are all correctly implemented across every endpoint that touches them — these were the highest-stakes categories in this review and none produced a CRITICAL finding. The two HIGH findings are both systemic omissions (rate-limit response documentation; an audit-event catalog gap inherited from the architecture) rather than exploitable vulnerabilities, and both have a mechanical fix. **0 CRITICAL, 2 HIGH, 3 MEDIUM, 4 LOW** findings.

> **Update (2026-07-19):** All 2 HIGH and 3 MEDIUM findings have been applied to `03-openapi-specification.md` (and, for OQ-001, to the Solution Architecture document). See the **Status** line under each finding below and the updated Prioritised Change List §4. The 4 LOW findings remain open — none were in scope for this fix pass.

---

## 2. Findings by Severity

### HIGH

#### [SC-001] Every rate-limited endpoint except three is missing 429 documentation

**Status:** ✅ Fixed. `RateLimitedError` now carries a `Retry-After` response header; all 37 operations that declare `x-ratelimit` (including `POST /auth/login`'s custom 429, which kept its account-lockout body and gained the same header) now document a 429 response. Verified 1:1 — 37 `x-ratelimit` annotations, 37 `"429"` response entries.

**Problem:** `x-ratelimit` is annotated on all ~35 operations, but only `POST /auth/register`, `POST /auth/login`, and `POST /auth/password-reset-request` document a 429 response. The other ~32 rate-limited endpoints (all of Portfolio, Pricing, Import, Subscription, Account, Reference, and Admin) have no 429 in their `responses` block, and no operation anywhere declares a `Retry-After` response header. A client integrating strictly against this contract has no documented way to know what a throttled response looks like outside the three auth endpoints, and cannot discover the `Retry-After` header without reading the architecture document separately. This is exactly the gap Stage 4 checklist items SC-006 and ER-004 exist to catch.

**Fix:** Add to `components/responses`:

```yaml
RateLimitedError:
  description: Too many requests.
  headers:
    Retry-After:
      schema: { type: integer }
      description: Seconds until the next request will be accepted.
  content:
    application/json:
      schema: { $ref: "#/components/schemas/ErrorResponse" }
```

The schema already exists in `components/responses` without the `headers` block — add the `headers` block, then add `"429": { $ref: "#/components/responses/RateLimitedError" }` to every operation that carries an `x-ratelimit` annotation.

---

#### [OQ-001] No audit action value exists for Position update or delete

**Status:** ✅ Fixed. Per explicit user decision, both the architecture and the spec were updated: `POSITION_UPDATED` and `POSITION_DELETED` were added to the Solution Architecture document's §14.7 action-value table (with a note explaining the reconciliation), and `PATCH`/`DELETE /api/v1/portfolio/positions/{id}` in `03-openapi-specification.md` now carry the corresponding `x-audit-event` annotations.

**Problem:** `PATCH /api/v1/portfolio/positions/{id}` and `DELETE /api/v1/portfolio/positions/{id}` carry no `x-audit-event` annotation. This is not a Stage 3 oversight — architecture §14.7's 18-event catalog defines `LOT_CREATED`, `LOT_UPDATED`, `LOT_DELETED`, `DIVIDEND_CREATED`/`UPDATED`/`DELETED`, but no `POSITION_CREATED`/`UPDATED`/`DELETED` action value, so Stage 3 correctly declined to invent one per the guardrail "use the exact action values from architecture §14.7."

However, BAS Enhanced Part 2 §7 (AuditLog `entity_type` enum) explicitly lists "Position" and states this was a `[FIXED]` correction specifically because "this contradicts the PRD NFR requirement that position edit history be logged" (BA Quality Review, Change Summary Table, entry "AuditLog entity_type enum"). The BAS "What must be audited" list is explicit: "Position: every CREATE, DELETE; UPDATE to `category_tag` or `stock_name`." Position CREATE is covered indirectly (`LOT_CREATED` fires when the first lot creates a position), but Position UPDATE and Position DELETE (which cascades to soft-deleting every Lot and DividendTranche under it — itself a significant, currently-unaudited bulk mutation) have no corresponding architecture action value at all. This is a genuine contradiction between the architecture and the BAS that the API layer cannot resolve on its own.

**Fix:** This requires an architecture-level decision, not just a spec edit: add `POSITION_UPDATED` and `POSITION_DELETED` to architecture §14.7's action-value table, then annotate the two operations:

```yaml
# PATCH /api/v1/portfolio/positions/{id}
x-audit-event: POSITION_UPDATED
# DELETE /api/v1/portfolio/positions/{id}
x-audit-event: POSITION_DELETED
```

Flagged to the solution architect as a required architecture update, not applied unilaterally in this spec, since inventing an action value not present in §14.7 would itself violate the Stage 3 guardrail.

### MEDIUM

#### [OQ-002] `POST /webhooks/stripe` has no `x-audit-event` annotation for its two conditional outcomes

**Status:** ✅ Fixed, using recommended option (a). `POST /webhooks/stripe` now carries `x-audit-events: [SUBSCRIPTION_ACTIVATED, SUBSCRIPTION_CANCELLED]` plus an `x-audit-events-description` explaining the branching condition and why this operation uses the plural extension instead of `x-audit-event`.

**Problem:** The Stage 4 checklist (OQ-001 in the audit-annotation review) frames `SUBSCRIPTION_ACTIVATED` as firing "via webhook," and architecture §14.7 lists `SUBSCRIPTION_ACTIVATED` and `SUBSCRIPTION_CANCELLED` as required events, both produced by this single endpoint depending on which Stripe event type is delivered (`checkout.session.completed` vs. `customer.subscription.deleted`). The OpenAPI `x-audit-event` extension as used elsewhere in this spec carries exactly one value per operation, which cannot represent "one of two events depending on payload content" without a documented convention.

**Fix:** Either (a) split the audit annotation into a structured extension — `x-audit-events: [SUBSCRIPTION_ACTIVATED, SUBSCRIPTION_CANCELLED]` — with a description explaining the branching condition, or (b) document the mapping in the operation `description` field only (already partially done — the description names both events) and treat `x-audit-event` as reserved for single-outcome operations. Recommend (a) for machine-readability if the audit annotation is ever programmatically extracted for a compliance audit tool.

---

#### [FC-000] `DataExportResponse` content-type/schema-type mismatch

**Status:** ✅ Fixed. `DataExportResponse` is now `type: object` (no `format: binary`), with a description explaining the payload structure and pointing to architecture §10.7; the operation's `content` block already used `application/json`, so the two are now internally consistent.

**Problem:** `GET /api/v1/account/export`'s 200 response declares `content: application/json: schema: $ref DataExportResponse`, where `DataExportResponse` is `type: string, format: binary`. `format: binary` is the OpenAPI convention for `application/octet-stream` payloads (arbitrary binary data); pairing it with the `application/json` media type is internally inconsistent and would confuse codegen tooling that respects the `format` keyword (some generators will produce a `Blob`/`ArrayBuffer` return type for a `format: binary` schema regardless of the declared media type, which happens to be harmless here but is not guaranteed for every generator). This does not affect the actual streamed download the FastAPI backend produces — it is a documentation-fidelity issue, not a runtime one — but it is worth resolving since PD-001 (Stage 4 checklist) exists specifically to make this unambiguous for implementers.

**Fix:**

```yaml
responses:
  "200":
    description: |
      Streamed JSON file download. Content-Type: application/json;
      Content-Disposition: attachment.
    headers:
      Content-Disposition:
        schema: { type: string, example: 'attachment; filename="bursatrack-export-2026-06-30.json"' }
    content:
      application/json:
        schema:
          type: object
          description: |
            Structure is the full personal-data export object described in
            architecture §10.7. Not modeled as a typed schema here because its
            shape is a direct dump of multiple entity tables, not a stable API
            contract intended for programmatic consumption beyond the download
            itself.
```

Drop `format: binary`; keep the media type as `application/json` since that is what architecture §10.7 explicitly specifies the backend sends.

---

#### [PD-000] CSV template download (BAS FR-015) has no corresponding endpoint

**Status:** ✅ Fixed. Per explicit user decision, resolved as **static frontend asset**, not an API endpoint — recorded as Stage 2 decision ADD-013 in `02-api-design-decision-record.md`, with a corresponding note added to `03-openapi-specification.md`'s "Notes for Implementation" section so the omission reads as deliberate rather than forgotten.

**Problem:** BAS FR-015 ("CSV Template Download") and the PRD's CSV import scope both describe a dedicated template-download operation ("Download Template" button, serving `BursaTrack_Import_Template.csv`). The Stage 3 prompt's "Complete Endpoint Inventory" — which Stage 3 was instructed not to add endpoints beyond — does not include this operation anywhere in the Import Module table. This spec correctly did not invent an endpoint outside that inventory (per guardrail), so the omission is not a Stage 3 defect, but it means a BAS Must-Have requirement (FR-015, User Story US-019, with full acceptance criteria) currently has no API surface at all. Architecture §13.6's CSV injection defence note ("on CSV template download... strip or quote cell values beginning with `=`, `+`, `-`, `@`") also has nothing to attach to.

**Fix:** Not a spec-level fix — requires the solution architect to add the missing endpoint to the architecture's endpoint inventory (e.g., `GET /import/template`, unauthenticated or JWT-protected, serving a static file), after which Stage 3 can add the corresponding OpenAPI path. Flagged as an open item rather than CRITICAL because a static template file can currently be served outside the versioned API (e.g., as a public static asset on the frontend) as a stopgap, but that decision should be made explicitly rather than by default.

### LOW

#### [ER-000] `POST /auth/login` has no 422 response documented

**Problem:** The endpoint accepts a JSON body (`LoginRequest`) that FastAPI/Pydantic will reject with 422 on malformed input (e.g., missing `password` field, non-string `email`), consistent with every other JSON-body endpoint in the spec. This one endpoint's `responses` block only documents 200, 401, and 429.

**Fix:** Add `"422": { $ref: "#/components/responses/ValidationError" }` to `POST /auth/login`.

---

#### [OQ-000] `GET /admin/config/fees` does not document TTLCache staleness

**Problem:** `GET /api/v1/stocks` explicitly documents "results may be up to 60 minutes stale" (per architecture §12.4's TTLCache table), matching Stage 4 checklist item OQ-004. `GET /admin/config/fees` reads from the same TTLCache mechanism per architecture §12.4 but has no `description` field at all — only a `summary`. An admin operator reading this response with no staleness note might reasonably assume it reflects the database state at the instant of the request, immediately after another admin has just called PATCH on a different process/instance.

**Fix:** Add a `description` to the GET operation: "Backed by the same 60-minute TTLCache as `/api/v1/stocks` (architecture §12.4). A PATCH from a different process invalidates only that process's cache — in a future multi-instance deployment, other instances may serve a stale value for up to 60 minutes. Single-instance at V1 (architecture §14.4), so this is not currently observable, but documenting it now avoids a silent surprise if the single-Render-instance constraint (NG-008) is ever relaxed."

---

#### [SC-000] No explicit HTTPS/TLS enforcement statement in `info.description`

**Problem:** `info.description` documents CORS policy and JWT cookie flags but does not state that all traffic is HTTPS-only, even though architecture §14.6 is explicit ("HTTPS enforced on all endpoints... HTTP redirects to HTTPS via hosting platform configuration. HSTS headers set."). OW-008 (Stage 4 checklist) asks reviewers to confirm this is documented somewhere in the contract for integrators who read only the OpenAPI spec, not the full architecture document.

**Fix:** Add one sentence to `info.description`: "All traffic is HTTPS-only; HTTP requests are redirected by the hosting platform (Render/Vercel) and HSTS is enforced. `servers[0].url` (`https://api.bursatrack.com`) never accepts plaintext HTTP in production."

---

#### [IV-000] `LoginRequest.password` has no `maxLength` constraint

**Problem:** `RegisterRequest.password` and `PasswordResetComplete.new_password` both constrain `minLength: 8, maxLength: 128` (matching BAS VR-002). `LoginRequest.password` has no constraint at all. This is very unlikely to be exploitable — the value is compared against a bcrypt hash, not used to construct a query or fed to an unbounded operation — but an unconstrained string field on a public, rate-limited-but-not-infinitely-so endpoint is worth bounding defensively (a multi-megabyte `password` value in a login POST body costs the bcrypt-hashing code a wasted comparison attempt and is free amplification for an attacker versus the cost of a normal request).

**Fix:** Add `maxLength: 128` to `LoginRequest.password` (no `minLength`, since a legacy account could theoretically predate a minimum-length policy change and must still be able to log in with whatever password it has).

---

## 3. Items Confirmed Correct

The following were checked against the full Stage 4 checklist and found correctly implemented — listed so the engineering team knows what does **not** need further attention.

**Financial Correctness (all of FC-001 through FC-007):**

- Every monetary/rate field in every response and request schema is `type: string` with a decimal-pattern or descriptive annotation — verified individually for `purchase_price`, `brokerage_fee`, `clearing_fee`, `stamp_duty`, `all_in_cost`, `per_share_amount`, `total_amount`, `PriceSnapshot.price`, `BrokerConfig.rate`, and all seven `SellScenarioRow` monetary fields. Zero `type: number` occurrences on any financial field in the document.
- `PortfolioResponse.portfolio_blended_yield` was identified as a genuine FC-002 violation during drafting and was removed before this review — yield is now absent from every response schema in the document, with an explicit note in `PortfolioResponse`'s description explaining why (computed client-side only). This is called out explicitly here rather than silently, since it demonstrates the exact class of defect this review exists to catch, and confirms none of the same pattern survived elsewhere (`SellScenarioResponse`, `PositionSummaryResponse`, and `DividendCalendarResponse` were all re-checked specifically for a reintroduced yield field and are clean).
- No `Lot` or `DividendTranche` request schema accepts a fee/total field. `CreatePositionRequest`, `CreateLotRequest`, `UpdateLotRequest` accept only `stock_code`/`shares`/`purchase_price`/`broker_id`/`purchase_date`/`category_tag`/`notes`/`version` — never `brokerage_fee`, `clearing_fee`, `stamp_duty`, or `all_in_cost`. `CreateDividendRequest` and `UpdateDividendRequest` accept only `per_share_amount`/`qualifying_shares`/`tranche_label`/dates/`version` — never `total_amount`, on either creation or edit. This is the single most safety-critical check in the whole review (P0-API-002 and P0-API-003) and both pass cleanly.

**Authentication and Authorization (AA-001 through AA-009):**

- Every operation declares `security` explicitly or correctly inherits the documented global default (`cookieAuth`); all nine public/token-gated/webhook/admin operations override it explicitly (`security: []`, `stripeSignature`, or `adminApiKey` as appropriate).
- `403` does not appear anywhere in the document. Every ownership-checked resource documents `404` consistently for both "does not exist" and "not owned by caller" (and, per ADD-004, "soft-deleted").
- `token_version` revocation semantics are documented in both `info.description` and the `cookieAuth` security-scheme description.
- `GET /auth/verify` and `GET /account/cancel-deletion` both document token validity checks (existence, single-use, expiry) resolving to 400 on failure, never a silent 200.

**Idempotency (ID-001 through ID-006):** `version` is a required field on both `UpdateLotRequest` and `UpdateDividendRequest`; both PATCH operations document 409 `version_conflict` using the shared `ErrorResponse` schema; the Stripe webhook's idempotent-redelivery behaviour and the CSV import's `already_processing` 409 (with `job_id` echoed back, per ADD-012) are both documented; `POST /auth/password-reset-request`'s enumeration-safe 200 is explicit.

**Input Validation (IV-001 through IV-013, except IV-000 above):** All BAS-derived numeric minimums, enums, and decimal-place patterns are present and correctly scoped to the fields BAS specifies them for (`shares`, `qualifying_shares`, `tranche_label`, `category_tag`, `fee_type`, `confirmation`, CSV size/type/row limits, `purchase_price`, `per_share_amount`, email format). IV-008 (CSV injection defence) was checked and found **not applicable** to any endpoint in this spec — the architecture's injection-defence note (§13.6) applies to CSV template download and CSV-formatted export, and this spec correctly has neither (template download has no endpoint per PD-000 above; the PDPA export is JSON per architecture §10.7, not CSV).

**PDPA Compliance (PD-001 through PD-009, except PD-000/FC-000 above):** `/account/export`'s description explicitly enumerates included and excluded entities/fields matching architecture §10.7 verbatim; `/account/cancel-deletion` and `/auth/verify` both use query parameters, never path segments, for tokens; `/auth/password-reset` takes the token in the request body; `/account/delete`'s description covers immediate session invalidation, the 30-day grace period, and the confirmation email; `UserResponse` excludes `password_hash` and `token_version`; no error message anywhere interpolates an email address, user ID, or other PII into the `message` string.

**Security Hardening (SC-001 through SC-007, except SC-000 above):** CORS policy, cookie security flags (`HttpOnly`, `Secure`, `SameSite=Lax`), admin-key constant-time comparison, Stripe signature-before-trust, and the enumeration-safe password-reset response are all documented in `info.description` and/or the relevant security-scheme descriptions.

**Error Response Consistency (ER-001 through ER-008, except ER-000/SC-001 above):** Every error response references `ErrorResponse` or `ValidationErrorResponse` by `$ref` — zero inline error schemas. `503` appears only on `/health`. All three confirmed 409 conflict types (`version_conflict`, `in_use`, `already_processing`) carry distinguishable `error` codes.

**Operational Quality (OQ-002 through OQ-006, except OQ-001/OQ-002/OQ-000 above):** `GET /health` is unauthenticated with the exact response bodies specified; `GET /import/status/{job_id}` documents ownership verification; `DELETE /api/v1/portfolio/positions/{id}` documents the lot/tranche cascade; `PATCH /admin/config/fees` documents immediate TTLCache invalidation.

**OWASP API Security Top 10 (OW-001 through OW-010):** BOLA (OW-001) is structurally prevented by the universal 404 pattern; broken authentication (OW-002) and broken object property authorization (OW-003) are both clean per the checks above; resource consumption limits (OW-004) are documented for CSV upload even though the 429/Retry-After gap (SC-001 finding above) weakens this category overall; function-level authorization (OW-005) is correctly scoped to `adminApiKey`; SSRF (OW-007) — confirmed no endpoint accepts a URL for server-side fetch, no risk present; security misconfiguration (OW-008) is mostly clean aside from the TLS-statement gap (SC-000); inventory management (OW-009) — **confirmed exact match**, every endpoint in the architecture's Stage 3 inventory is present in the spec and no additional endpoint was invented; unsafe API consumption (OW-010) — Stripe payload is never trusted before signature verification, documented explicitly.

---

## 4. Prioritised Change List

1. **[HIGH — SC-001]** ✅ Done — `RateLimitedError` gained a `headers.Retry-After` block; all 37 `x-ratelimit`-annotated operations now document `429`.
2. **[HIGH — OQ-001]** ✅ Done — `POSITION_UPDATED`/`POSITION_DELETED` added to architecture §14.7 and annotated on `PATCH`/`DELETE /api/v1/portfolio/positions/{id}`.
3. **[MEDIUM — OQ-002]** ✅ Done — `POST /webhooks/stripe` now carries `x-audit-events: [SUBSCRIPTION_ACTIVATED, SUBSCRIPTION_CANCELLED]`.
4. **[MEDIUM — FC-000]** ✅ Done — `DataExportResponse` is now `type: object`, `format: binary` removed.
5. **[MEDIUM — PD-000]** ✅ Done — resolved as a static frontend asset (Stage 2 decision ADD-013); no new endpoint added.
6. **[LOW — ER-000]** Not yet applied — add `422` to `POST /auth/login`.
7. **[LOW — OQ-000]** Not yet applied — add a staleness-note `description` to `GET /admin/config/fees`.
8. **[LOW — SC-000]** Not yet applied — add one sentence on HTTPS/HSTS enforcement to `info.description`.
9. **[LOW — IV-000]** Not yet applied — add `maxLength: 128` to `LoginRequest.password`.

---

## 5. Open Questions

These require a stakeholder or architect decision before implementation can proceed on the affected surface — none should block starting implementation on the rest of the API.

1. ~~**POSITION_UPDATED / POSITION_DELETED audit action values (from finding OQ-001).**~~ **Resolved 2026-07-19** — added to architecture §14.7 and annotated in the spec (see §2 Status line above).
2. ~~**CSV template download endpoint (from finding PD-000).**~~ **Resolved 2026-07-19** — decided as a static frontend asset (ADD-013); no API endpoint added.
3. **Admin endpoint rate limiting** (carried forward from Stage 2's open questions): this review's recommendation (60/min keyed by API key value) was not independently re-litigated here since it is a Stage 2 design decision, not a Stage 3 spec defect, but it remains unconfirmed by the solution architect and is called out again here because the SC-001 fix (adding 429 documentation everywhere) will make this endpoint's rate limit externally visible/testable for the first time — worth confirming the number is intentional before that happens.
4. **BAS OQ-003 and OQ-005** (dividend year semantics; sell-calculator default broker) remain unresolved business decisions carried forward unchanged from Stage 1/Stage 2 — neither blocks implementation, since both were deliberately designed (§ADD-005, §ADD-007 in the Stage 2 record) to require no API contract change once resolved.
