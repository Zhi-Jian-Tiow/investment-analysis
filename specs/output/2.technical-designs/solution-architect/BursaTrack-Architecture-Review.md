# BursaTrack — Principal Architecture Review

**Review type:** Independent formal architecture review  
**Input document:** BursaTrack-Solution-Architecture.md v1.0  
**Review date:** 2026-06-28  
**Reviewer:** Independent Principal Architect  
**Status:** Complete

---

## Executive Assessment

The Solution Architecture Document is well-structured, deliberately conservative, and appropriate for a solo-founder bootstrapped MVP. The core financial logic decisions — the `qualifying_shares` invariant, mandatory decimal arithmetic, and server-authoritative calculation — are correctly specified and sufficiently defended. The modular monolith choice is sound for the target scale.

However, several issues require attention before implementation begins. Three are pre-implementation blockers, twelve are high-severity findings, and there are notable hidden assumptions and architectural smells that accumulate risk over time. The document would benefit from filling the gaps identified below before the Database Schema Design document is produced.

**Overall Readiness: Conditional — address Critical and High items before schema design begins.**

---

## Issues

### CRITICAL — Must resolve before implementation

---

**CRIT-R-001: CORS wildcard `*.vercel.app` is an overly permissive security boundary**

**Severity:** Critical  
**Section:** 14.3

**Description:** The CORS allowlist includes `"https://*.vercel.app"`. Any deployment on the Vercel platform — not only BursaTrack's preview deployments — resolves to a `*.vercel.app` subdomain. An attacker can deploy a malicious app on Vercel, obtain a legitimate `*.vercel.app` domain, and make credentialed cross-origin requests to the BursaTrack API. Because `allow_credentials=True` is set alongside this wildcard, the browser will attach the user's HTTP-only JWT cookie to requests originating from that attacker-controlled domain.

**Impact:** Full authenticated access to any logged-in user's portfolio data from an attacker-controlled page. This is a critical CSRF-equivalent attack surface.

**Recommendation:** Replace the wildcard with an enumerated list of specific preview deployment URLs, or use a pattern-matching approach that validates the hostname prefix. Vercel assigns predictable hostnames to preview deployments (`bursatrack-<branch>-<team>.vercel.app`). Configure the CORS middleware to match this specific pattern programmatically at startup rather than using a broad wildcard. For production, only `https://bursatrack.com` and `https://www.bursatrack.com` should be in the allowlist. Preview deployments should use a separate, tightly-scoped CORS configuration.

---

**CRIT-R-002: FR-018 PDPA Data Export has no architectural implementation**

**Severity:** Critical  
**Section:** Scope (§4), Audit Log (§14.7)

**Description:** FR-018 (PDPA User Data Export) is listed as Must Have in the scope table and referenced in the audit log action `DATA_EXPORT_DOWNLOADED`. However, there is no sequence diagram, no description of what data is included, no format specification, no implementation notes, and no description of how the export file is delivered to the user. For a feature that is a legal requirement under Malaysian PDPA, its complete absence from the architecture is a gap.

**Impact:** The database schema, API design, and frontend cannot be correctly implemented for FR-018 without this specification. If this feature is deferred or incorrectly implemented, it creates regulatory exposure.

**Recommendation:** Add a dedicated section describing: (1) which entities and fields are included in the export; (2) the export format (JSON or CSV); (3) the delivery mechanism (synchronous download vs. async job with email link); (4) whether the export is generated on-demand or pre-generated; (5) a sequence diagram. Given that the deletion job operates at 03:00 UTC daily, an export-on-demand approach with synchronous generation is likely acceptable at V1 scale.

---

**CRIT-R-003: Stripe renewal job conflicts with Stripe-native billing — double-charge risk**

**Severity:** Critical  
**Section:** 13.4

**Description:** Section 13.4 states: "Note: Stripe's built-in subscription renewal (automatic charge) may handle this automatically depending on the subscription configuration. The job serves as a reconciliation backup." This is architecturally undefined. If Stripe's subscription object is configured with `collection_method=charge_automatically`, Stripe will attempt renewal automatically and fire `invoice.payment_succeeded` / `invoice.payment_failed` webhooks. If `process_renewals.py` then also triggers a payment attempt for the same user on the same day, the user may be double-charged.

**Impact:** Double-charging subscribers is a financial and legal liability. It would also produce duplicate `invoice.payment_succeeded` webhook events, and depending on idempotency implementation, may corrupt subscription state.

**Recommendation:** Make a definitive architectural decision: either (A) rely entirely on Stripe's built-in subscription renewal and remove the `process_renewals.py` cron job, replacing it with proper handling of `invoice.payment_succeeded` and `invoice.payment_failed` webhooks; or (B) use Stripe with `collection_method=send_invoice` and manage the charge lifecycle manually via the renewal job. Option A is strongly preferred — it is simpler, better-supported, and eliminates the coordination risk. Document the chosen approach as a confirmed ADR.

---

### HIGH — Should resolve before launch

---

**HIGH-R-001: JWT 30-day expiry is inappropriate for a financial application**

**Severity:** High  
**Section:** 14.1

**Description:** JWT tokens have a 30-day expiry (`exp` claim). The `token_version` mechanism provides revocation on logout, password change, and deletion initiation — but not for other compromise scenarios (stolen device, browser session hijack, XSS exfiltration if Content-Security-Policy fails). A compromised token remains valid for up to 30 days unless the user explicitly logs out.

**Impact:** Extended window of unauthorized access to portfolio and financial data for compromised sessions.

**Recommendation:** Reduce JWT expiry to 1–7 days maximum. Implement a silent refresh pattern: the frontend checks the cookie's expiry and calls a `/auth/refresh` endpoint before expiry. The refresh endpoint issues a new JWT with a fresh 30-day inactivity window. This provides a seamless user experience while limiting the blast radius of token compromise. Alternatively, implement a sliding session — each authenticated API call can reset the `exp` claim — but this requires the backend to issue a new JWT cookie on every request, which has performance implications.

---

**HIGH-R-002: HS256 symmetric signing exposes all tokens if secret is leaked**

**Severity:** High  
**Section:** 14.1

**Description:** The JWT is signed with HS256 (HMAC-SHA256), a symmetric algorithm. The same `JWT_SECRET` is used to both sign and verify tokens. If this secret is exposed (via a log line, a mis-configured env var dump, or a Render credential leak), every user token ever issued can be forged. There is no way to invalidate tokens signed with a compromised key without changing `JWT_SECRET` and forcing all users to re-authenticate.

**Impact:** Full account takeover for all users in the event of secret exposure. This is a high-consequence single point of failure.

**Recommendation:** Use RS256 (RSA-SHA256) asymmetric signing. The private key signs tokens (held only by the API); the public key verifies them (can be safely distributed). Key rotation is possible without immediate session invalidation. `fastapi-users` supports RS256. Alternatively, accept the HS256 risk but document a key rotation runbook and ensure the secret rotation process is tested before launch.

---

**HIGH-R-003: Vercel preview deployments call the production API**

**Severity:** High  
**Section:** 18.3

**Description:** The environment table explicitly states that Vercel preview deployments use the production Render API. This means a developer testing a frontend change on a PR preview can create, modify, or delete real user data in production. A buggy form submission, an incorrect API call, or a developer testing an edge case will affect live data.

**Impact:** Production data corruption or accidental deletion during frontend development. This risk increases as the contributor count grows.

**Recommendation:** For a solo founder, acceptable short-term if access is strictly controlled. However, this must be documented as a known risk with a clear mitigation policy (e.g., developers must use a test account, never test against real user data). Medium-term: provide a lightweight staging environment (a second Render web service pointing to a staging PostgreSQL instance) for preview deployments. The cost is an additional ~USD 14/month. This is the most significant operational gap in the document.

---

**HIGH-R-004: Sequential yfinance fetches can exceed the cron window**

**Severity:** High  
**Section:** 13.2, 16.4

**Description:** The price refresh job fetches stocks sequentially. Each stock has a 30-second timeout and up to 2 retries (5s and 15s backoff), giving a worst-case per-stock cost of approximately 50 seconds. With 200 unique stock codes, the worst-case total is ~167 minutes. The cron is scheduled once at 09:30 UTC. No mechanism prevents overlapping cron runs or detects that the previous run is still in progress.

**Impact:** At scale, the price refresh job can run longer than 24 hours, meaning two concurrent runs can be active simultaneously, resulting in duplicate writes, elevated database load, and confusing stale-data signals.

**Recommendation:** (1) Add a distributed lock or process lock at the start of `refresh_prices.py` (a database row with a lock timestamp is sufficient — check if a run started within the last 2 hours and exit if so). (2) Plan for parallelisation of yfinance fetches with `asyncio.gather` as noted in §20.1, but move this to V1 rather than V1.1 — it's needed at lower scale than assumed. (3) Set a hard wall-clock timeout on the entire job (e.g., 60 minutes) and alert on breach via Sentry.

---

**HIGH-R-005: Stuck ImportJob state — no cleanup mechanism**

**Severity:** High  
**Section:** 8.2, 13.6

**Description:** If the Render FastAPI service crashes while a `BackgroundTask` CSV import is in progress, the `ImportJob` record remains in `status=processing` indefinitely. The document acknowledges this failure mode ("user must re-upload") but provides no mechanism to detect or clean up stuck jobs. Over time, stuck jobs accumulate in the database.

**Impact:** Users who experienced a crash during import have no way to discover why their import never completed, and the stale `processing` rows can confuse status polling. For users who retry, multiple stuck rows accumulate.

**Recommendation:** (1) Add a `started_at TIMESTAMPTZ` column to `ImportJob`. (2) Add a cleanup step to a daily cron job (or add to the existing `check_trial_expiry.py` job) that marks any `ImportJob` where `status='processing' AND started_at < now() - interval '1 hour'` as `failed` with an appropriate error message. (3) The status polling response should communicate the failure clearly with a "Please re-upload" CTA.

---

**HIGH-R-006: Yield "stored" in precision table contradicts "computed at query time" in ADR-004**

**Severity:** High  
**Section:** 12.3

**Description:** The data precision table (§12.3) includes "Yield percentage (stored)" as `NUMERIC(8,4)`. However, ADR-004 (referenced in the ADR traceability matrix) states "Position aggregates computed at query time." No `yield` or `yield_percentage` column appears in any entity in the ER diagram. The sequence diagram in §10.2 shows yield computed inline at the API layer: `yield = 1000.00 / 41996.47 = 2.38%`.

**Impact:** Schema implementers reading §12.3 will add a yield column to some table. API implementers reading ADR-004 will compute it on the fly. The inconsistency will produce a schema column that is never written to, or calculated values that diverge from a stale stored value.

**Recommendation:** Remove "Yield percentage (stored)" from the precision table. If yield is to be persisted (for performance), explicitly state which table stores it, when it is updated, and how it is kept consistent with the underlying dividend and cost data. Otherwise, confirm it is computed at query time and remove the row entirely.

---

**HIGH-R-007: `audit_log.user_id` FK constraint contradicts PDPA deletion job**

**Severity:** High  
**Section:** 13.5, 14.7

**Description:** The `audit_log` DDL (§14.7) defines `user_id UUID REFERENCES users(id) ON DELETE SET NULL`. This means the database will automatically null the `user_id` foreign key when a `users` row is deleted. However, the PDPA hard-delete job (§13.5) explicitly deletes `audit_log WHERE user_id = ?` before deleting the `users` row. These two mechanisms conflict: if the FK constraint is `ON DELETE SET NULL`, the explicit deletion is redundant (and if it runs before the user delete, the FK doesn't fire). If the deletion job were to fail or skip the audit_log step, the FK would null the reference rather than deleting the rows — leaving orphaned audit records in the database that are not deleted and not associated with any user.

**Impact:** Undefined PDPA deletion behaviour depending on execution order. Potential for orphaned audit_log rows that cannot be associated with a user for PDPA compliance purposes.

**Recommendation:** Choose one mechanism and apply it consistently. Recommended: change the FK to `ON DELETE CASCADE` to let the database handle audit_log row deletion automatically when the user is deleted. Remove the explicit `DELETE audit_log` step from the deletion job. Then `system_deletion_log` is inserted before the user delete, and the cascade handles the rest. This is simpler and less error-prone.

---

**HIGH-R-008: Stripe checkout return race condition — webhook may not arrive before user returns**

**Severity:** High  
**Section:** 10.4

**Description:** The subscription lifecycle sequence shows: user completes Stripe Checkout → Stripe sends webhook → user is redirected back to the app → frontend calls `GET /subscription/status`. In practice, Stripe webhook delivery typically occurs seconds after the checkout completes, but there is no guarantee it arrives before the user's browser loads the return page. If the user returns before the webhook is processed, `GET /subscription/status` returns `trial` (old status), and the user sees a broken "not subscribed" state despite having paid.

**Impact:** Payment success followed by a confusing "you are not subscribed" experience. Users may attempt to re-subscribe, contact support, or abandon.

**Recommendation:** After Stripe Checkout redirects back to the app, the frontend should poll `GET /subscription/status` with a brief retry loop (e.g., poll every 2 seconds for up to 30 seconds) until the status transitions to `active`, or show a "Processing your payment…" loading state. Alternatively, Stripe provides a `session_id` query parameter on the return URL that the frontend can pass to a backend endpoint that synchronously retrieves the checkout session from Stripe's API to confirm payment before the webhook arrives.

---

**HIGH-R-009: No file size or content validation documented for CSV import**

**Severity:** High  
**Section:** 13.6, 10.3

**Description:** The CSV import workflow describes row-level validation in Phase 1, but does not specify: (1) a maximum file size limit; (2) a maximum row count limit; (3) defence against CSV injection (cells beginning with `=`, `+`, `-`, `@` that could execute in Excel when the template is opened); (4) character encoding validation (BOM, UTF-8 vs. Windows-1252). The `slowapi` rate limiter restricts imports to 2/minute per user, but a single request could contain an arbitrarily large CSV file.

**Impact:** Memory exhaustion from large CSV files processed in-memory as BackgroundTasks. Denial of service against the 512 MB Render instance. CSV injection affecting users who re-open their template in Excel.

**Recommendation:** (1) Enforce a maximum upload size at the API layer (`Content-Length` check) and at the Render service level. 1 MB is a reasonable ceiling for the expected data volume. (2) Enforce a maximum row count (e.g., 1,000 rows). (3) Strip or escape cell values beginning with formula-injection characters before generating any CSV output (template download and data export). (4) Validate that uploaded files are valid UTF-8 and reject on encoding error.

---

**HIGH-R-010: No token refresh mechanism for 30-day JWT sessions**

**Severity:** High  
**Section:** 14.1

**Description:** The 30-day JWT expiry is set via the `exp` claim. There is no `/auth/refresh` endpoint or token renewal mechanism described. When a JWT expires mid-session (the user has had the app open for 30 days, or returns after 30 days of inactivity), the next API call returns HTTP 401 and the Next.js client redirects to login. This is a hard session termination. Combined with the recommendation to reduce JWT expiry to 1–7 days (HIGH-R-001), the absence of a refresh mechanism means users will be logged out after each expiry interval.

**Impact:** Disruptive user experience for active users. Likely to generate support requests. In the worst case, interrupts a user mid-workflow (e.g., mid-form during dividend logging).

**Recommendation:** Implement a token refresh endpoint (`POST /auth/refresh`) that accepts a valid non-expired JWT and returns a new JWT with a reset expiry. The Next.js client checks token expiry before each SWR fetch and silently refreshes if the token is within 24 hours of expiry. This is a standard pattern and requires minimal code.

---

**HIGH-R-011: Password reset and email verification token mechanics unspecified**

**Severity:** High  
**Section:** 10.1, 14.1

**Description:** The registration sequence diagram references email verification tokens (`GET /auth/verify?token=xxx`) and the password reset feature (FR-017) is in scope, but the architecture does not specify: (1) token generation mechanism (JWT or opaque database-stored token); (2) token expiry duration; (3) single-use enforcement (must be invalidated after first use); (4) account enumeration protection for password reset (same response regardless of whether email exists); (5) what happens when the verification link expires (resend flow).

**Impact:** Without these specifications, the implementation could use long-lived or reusable tokens, enabling account takeover via link interception. Account enumeration via password reset response timing is a known attack.

**Recommendation:** Specify: (a) use short-lived (24-hour), single-use, opaque random tokens stored in a `pending_tokens` table with `(token_hash, type, user_id, expires_at, used_at)`; (b) delete or mark as used immediately on first use; (c) password reset response is always the same message regardless of email existence; (d) verification link re-send regenerates a new token and invalidates the old one.

---

**HIGH-R-012: BrokerConfig CRUD is absent from all workflows and API descriptions**

**Severity:** High  
**Section:** 8.1, 8.2, 10.0

**Description:** `BrokerConfig` is a first-class entity in the data model with `fee_type`, `rate`, `minimum_fee`, and `flat_fee` fields. It has a foreign key relationship from `Lot`. The "Add Position" workflow shows `{broker}` as a request field. However, there is no workflow, sequence diagram, or API description for: (1) how system broker configs are seeded; (2) how a user creates a custom broker config; (3) how the admin updates fee parameters that differ from system configs; (4) how broker config deletion is handled when lots reference it. The relationship between `BrokerConfig` and `SystemConfig` (which stores fee parameters via `TTLCache`) is also unclear.

**Impact:** Schema and API implementers will make independent decisions about BrokerConfig CRUD. Without a specified workflow, the "authoritative server-side calculation" guarantee (G-001) cannot be validated.

**Recommendation:** Add a section describing: (a) the seeded set of system `BrokerConfig` records at deployment (e.g., Maybank IB, CIMBClick, Rakuten Trade); (b) the API endpoints for managing custom broker configs; (c) the relationship between `BrokerConfig.rate`/`minimum_fee` and the `system_config` fee parameters (are they duplicated? derived?); (d) the FK constraint behaviour when a user deletes a custom broker config that is referenced by existing lots (probably prevent deletion with a 409 response).

---

### MEDIUM — Address before or shortly after launch

---

**MED-R-001: No staging environment for a financial application accepting real payments**

**Severity:** Medium  
**Section:** 18.3

**Description:** The document explicitly states "No staging environment at V1." For a solo founder, this is a cost and complexity trade-off. However, the combination of (a) Vercel preview deployments pointing to production, (b) real Stripe payment flows, (c) PDPA deletion running against real user data, and (d) no staging PostgreSQL makes any infrastructure or data model change a production risk.

**Impact:** A failed database migration or a cron job bug discovered after deployment will affect real users and real financial data. Rollback requires Render dashboard access and `alembic downgrade`, which are manual operations.

**Recommendation:** At minimum, use Stripe's test mode keys in development and only switch to live keys in production. Ensure the local Docker Compose environment is comprehensive enough to test all payment flows. If possible, stand up a lightweight staging Render service (~USD 7/month) pointed to a separate PostgreSQL instance for pre-launch migration testing. Document the go/no-go checklist for each production deployment explicitly.

---

**MED-R-002: bcrypt cost factor 12 on a 0.5 CPU shared instance — latency risk**

**Severity:** Medium  
**Section:** 14.1

**Description:** bcrypt at cost factor 12 on a 0.5 CPU Render starter instance typically takes 300–600ms per hash. For registration and login, this is acceptable as a one-time operation. However, during password reset, email re-verification, or high-traffic registration bursts, multiple concurrent bcrypt operations will saturate the CPU core, causing queue buildup and elevated latency across all concurrent requests.

**Impact:** Registration and login latency degrades under concurrent load. A burst of 10 simultaneous registrations can block the event loop for 3–6 seconds on a 0.5 CPU instance.

**Recommendation:** FastAPI with async SQLAlchemy is async-first, but bcrypt is CPU-bound and blocks the event loop unless run in a thread pool executor. Verify that `fastapi-users`'s bcrypt integration runs in `asyncio.get_event_loop().run_in_executor()` to avoid blocking. If not, wrap the bcrypt call explicitly. Alternatively, reduce cost factor to 10 (still secure; bcrypt cost 12 is recommended for dedicated servers, not 0.5-vCPU shared containers).

---

**MED-R-003: In-process `TTLCache` is lost on every deployment and service restart**

**Severity:** Medium  
**Section:** 12.4

**Description:** The `TTLCache` for stock reference data and fee configuration has a 60-minute TTL. On every Render deployment (which restarts the process), the cache is cold and all concurrent requests hit the database for stock reference and fee config data. If a deployment occurs during a usage peak (e.g., post-market hours when users check their portfolios), there will be a burst of database queries immediately after the new process starts.

**Impact:** Elevated database load for up to 60 minutes after each deployment. Not a correctness issue, but a reliability concern under concurrent load.

**Recommendation:** This is acceptable at V1 scale. Document it as a known behaviour. As a low-cost mitigation, warm the cache proactively at startup (`@app.on_event("startup")` or `lifespan` context manager) by loading stock reference data and fee config into the TTLCache before the first request is served.

---

**MED-R-004: Bursa holiday calendar maintenance is unspecified**

**Severity:** Medium  
**Section:** 13.2

**Description:** The price refresh job loads the Bursa Malaysia holiday calendar from `system_config` as a JSON list to determine whether today is a trading day. There is no specification for: (1) who maintains this calendar; (2) how it is updated (the admin module has a `/config/fees` endpoint, but no holiday calendar endpoint); (3) what happens if the calendar is not updated before a new calendar year; (4) what happens on special market closures (e.g., unscheduled closures for public events or disasters).

**Impact:** If the holiday calendar is not updated before a new year begins, the price refresh job will attempt to fetch prices on market holidays (harmless but wasteful), or worse, skip trading days if the wrong holiday is in the list. For 2026/2027, this will materialise if the calendar is not refreshed.

**Recommendation:** (1) Add a `PATCH /admin/config/holidays` endpoint with a description in the admin module. (2) Document the annual maintenance procedure (update the `system_config.holidays` value before each new calendar year). (3) Consider storing holiday dates as a structured list by year in `system_config` so multi-year data can coexist. (4) Log a WARNING if today is a weekday but not in the calendar's current year, alerting the admin that the calendar may need updating.

---

**MED-R-005: Resend email delivery is fire-and-forget with one retry — insufficient for PDPA-required notifications**

**Severity:** Medium  
**Section:** 11.3, 15.2

**Description:** Email delivery uses `FastAPI BackgroundTasks` with one retry and a Sentry alert on final failure. For PDPA deletion confirmation (a legally required notification under Malaysian PDPA), a fire-and-forget mechanism with one retry is the thinnest possible reliability guarantee. If Resend has an outage lasting longer than the retry window, the user will not receive their legally required confirmation email, and the deletion will still proceed.

**Impact:** Regulatory exposure if PDPA-required notifications are not delivered. Sentry will alert, but a solo founder may not respond in time to manually resend before the deletion window opens.

**Recommendation:** For the PDPA deletion confirmation email specifically, implement a persistent retry mechanism. Options: (a) store a `pending_email_notifications` table row and have a cron job retry any unsent notifications up to 5 times over 24 hours; (b) use Resend's scheduled email feature; (c) before hard-deleting, verify that the deletion confirmation email was sent (check the `sent_at` column on the notification record) and abort the deletion with a Sentry CRITICAL alert if it was not. Option (c) is the strongest guarantee for the PDPA scenario.

---

**MED-R-006: Price deviation threshold of 50% will reject valid corporate action prices**

**Severity:** Medium  
**Section:** 13.2, 15.1

**Description:** The price validation logic rejects prices that deviate more than 50% from the previous snapshot. This threshold is designed to catch yfinance data errors. However, Bursa-listed stocks regularly experience legitimate price movements exceeding 50% due to: rights issues, bonus shares, capital reductions, suspension and resumption, privatisation offers, and circuit-breaker resumptions. A stock that has been suspended for several trading days and resumes with a large gap will fail the price guard and be marked as `stale` — even though the fetched price is correct.

**Impact:** Incorrectly marking valid prices as stale. Users with holdings in recently resumed or corporate-action-affected stocks will see stale indicators for valid prices, with no automated resolution.

**Recommendation:** (1) Increase the threshold to a configurable value (currently in `system_config` — confirm this) and default it to 75% or 100% rather than 50%. (2) When a price is rejected by the deviation guard, log the specific reason (price value, previous value, deviation %) to structlog so it can be investigated. (3) Consider flagging the rejection as `CORPORATE_ACTION_CANDIDATE` and surfacing it differently from a true fetch failure, so a manual review is possible without triggering the stale-data banner for all users.

---

**MED-R-007: `process_deletions.py` runs deletions per-user without isolation — a per-user failure can leave partial state**

**Severity:** Medium  
**Section:** 13.5

**Description:** The PDPA deletion job processes multiple users in a loop. Section 13.5 states: "Capture any per-user exceptions to Sentry without aborting other deletions." This is correct for user isolation. However, if a per-user transaction commits partially (e.g., lots are deleted but the user row is not yet deleted when a database error occurs), the user is in an indeterminate state: data deleted, account still present, `account_status` still `pending_deletion`. The next cron run at 03:00 UTC will re-attempt the deletion — but the cascading deletes for already-deleted data will either fail with FK errors or silently no-op.

**Impact:** Users who experience a partial deletion may have their account stuck in `pending_deletion` state with partial data. The daily re-run should be idempotent, but this property is not documented or tested.

**Recommendation:** Document the idempotency requirement explicitly for `process_deletions.py`: the deletion job must be safe to re-run for a user who has been partially deleted. Verify that all delete steps within the transaction use `DELETE ... WHERE ... IF EXISTS` semantics or handle `NOT FOUND` gracefully. Add a test that simulates a mid-transaction failure and verifies the re-run completes cleanly.

---

**MED-R-008: No application-level rate limiting on Stripe webhook endpoint**

**Severity:** Medium  
**Section:** 14.4, 11.2

**Description:** The Stripe webhook endpoint (`POST /webhooks/stripe`) is not included in the rate limiting table. Stripe signature verification (`Stripe-Signature` header) prevents unauthorised webhook processing, but the endpoint is still publicly accessible. A volumetric attack flooding this endpoint with garbage requests (with or without valid signatures) will trigger repeated database idempotency checks (`SELECT processed_webhook_events`) and potentially exhaust the connection pool.

**Impact:** Webhook endpoint DoS as an attack vector against the database connection pool, causing collateral API degradation.

**Recommendation:** Apply a separate rate limit to `POST /webhooks/stripe` — e.g., 100/minute per IP. Stripe delivers webhooks from a small set of documented IP ranges; consider allowlisting these IPs at the platform level (Render firewall rules) rather than in-application.

---

### LOW — Address over time

---

**LOW-R-001: No API error response standard specified**

**Severity:** Low  
**Section:** 8.2

**Description:** The document describes individual error responses (HTTP 409 for optimistic lock conflicts, HTTP 503 for database down, HTTP 401 for auth failure) but does not specify a standard error response envelope format. FastAPI's default error responses for `HTTPException` and Pydantic validation errors (`RequestValidationError`) differ in structure, creating inconsistent error handling on the client.

**Recommendation:** Specify a standard error response format and register a custom exception handler that normalises both `HTTPException` and `RequestValidationError` into the same envelope (e.g., `{"error": "string", "message": "string", "details": [...]}`). Document this in the architecture.

---

**LOW-R-002: `Stock` reference table has no deactivation workflow for newly-listed or delisted stocks**

**Severity:** Low  
**Section:** Risk R-009

**Description:** R-009 acknowledges the stock reference staleness risk and mentions "Admin script to add/update stock records without deployment." However, there is no specification for what happens to a `Position` that references a delisted stock (where `Stock.is_active = false`). The dashboard still shows it; the price refresh job still tries to fetch it; the all-in cost is still calculated normally. The user cannot add more lots to a delisted stock (hopefully) but their existing position is in limbo.

**Recommendation:** Define the behaviour for positions holding delisted stocks: (a) should the dashboard mark these positions differently? (b) should the price refresh job skip `is_active=false` stock codes? (c) can the user still log dividends for delisted stocks that paid a final dividend? These edge cases should be specified before schema design.

---

**LOW-R-003: Optimistic locking not applied to `Position` entity**

**Severity:** Low  
**Section:** 15.4

**Description:** Optimistic locking (`version INTEGER`) is applied to `Lot` and `DividendTranche` but not to `Position`. The `Position` entity has mutable fields (`stock_name`, `category_tag`, `is_deleted`) that can be edited. If two browser tabs open the same position and submit edits concurrently, the second write silently wins.

**Recommendation:** Either apply the `version` column to `Position` for consistency, or document the explicit rationale for why `Position`-level conflicts are acceptable (e.g., because the only mutable fields are `stock_name` and `category_tag`, both of which are user-supplied labels without financial implications).

---

**LOW-R-004: Missing: API versioning strategy for `/api/v2/` transition**

**Severity:** Low  
**Section:** 8.2

**Description:** All endpoints are under `/api/v1/`. There is no description of how a v2 API would be introduced (new prefix alongside v1, or full cutover with deprecation period). Given the planned V1.1 and V2 features (multi-portfolio, FPX), some of these will require breaking API changes.

**Recommendation:** Add a brief note on the API versioning strategy: either URL-path versioning (`/api/v1/`, `/api/v2/`) with a documented deprecation policy, or a single versioned API with backwards-compatible additive changes. A solo founder MVP can defer this, but it should be a conscious decision.

---

**LOW-R-005: `subscription_renewal_date` on `User` can drift from Stripe's subscription state**

**Severity:** Low  
**Section:** 12.1, 13.4

**Description:** `User.subscription_renewal_date` is set by the webhook handler when a subscription is activated. If Stripe changes the next billing date (e.g., due to a payment retry, proration, or manual adjustment in the Stripe dashboard), the webhook handler must update this field from the `invoice.payment_succeeded` event. If a webhook event is missed or processed out of order, `subscription_renewal_date` can drift from Stripe's actual next billing date. The renewal job then targets the wrong date.

**Recommendation:** On every `invoice.payment_succeeded` webhook, explicitly retrieve `subscription.current_period_end` from the Stripe event payload and update `subscription_renewal_date` from this value (not by adding 30 days to `subscription_start`). Document this as a requirement in the Stripe webhook handler specification.

---

## Hidden Assumptions

**HA-001: yfinance provides complete coverage of Bursa Malaysia tickers.**
The document assumes yfinance supports all Bursa-listed stocks via `.KL` suffix tickers. In practice, some counters (ETFs, warrants, REITs structured as listed entities) may have inconsistent ticker support. This has not been validated. If a stock code is in the user's portfolio but unsupported by yfinance, the stock will permanently show stale — with no differentiation from a temporary outage.

**HA-002: Render's managed PostgreSQL connection limits accommodate the application pool plus cron scripts.**
The connection pool is configured at 5 + 10 overflow = 15 connections. Four cron scripts each independently open a connection to the database. At 09:30 UTC, the price refresh cron runs simultaneously with active web traffic. On Render's free PostgreSQL tier, the connection limit is 25 connections. On the starter tier, it is higher. The exact limit for the chosen Render PostgreSQL tier must be confirmed against the total possible concurrent connections (FastAPI pool + 4 cron scripts).

**HA-003: Stripe supports MYR subscription billing for a Malaysian merchant account.**
Section 11.2 states currency is MYR. Stripe's support for MYR depends on the merchant's Stripe account country. Stripe does not have a Malaysia entity; Malaysian merchants typically onboard via Stripe's global or Singapore entity. Stripe's MYR support must be confirmed before any payment infrastructure is built.

**HA-004: 500 concurrent users will generate fewer than ~100 unique stock codes across all portfolios.**
The price refresh sequential fetch assumption is implicitly based on a small number of unique tickers. At 500 active users, if each holds 10 unique stocks and 20% overlap exists, this could be 400 unique tickers. At 50s worst-case per ticker, this is 333 minutes — far exceeding the daily window. The estimate in §16.2 ("10,000 price API calls per trading day") appears to use 10,000 accounts × 1 call, not unique stock codes. The actual number of unique tickers at V1 scale must be estimated and used to size the fetch window.

**HA-005: FastAPI BackgroundTasks are reliable enough for CSV import processing.**
BackgroundTasks run in the same process as the web server. They are not durable — a process crash loses in-flight tasks. For CSV import, the document accepts this and says "user must re-upload." This is a product decision, not a bug, but it must be communicated to users with a clear error state (which requires the stuck ImportJob cleanup described in HIGH-R-005).

**HA-006: `SameSite=Lax` provides sufficient CSRF protection without a CSRF token.**
Lax prevents cross-site POST requests, which covers the primary CSRF attack surface. However, this assumes all state-changing operations use POST/PUT/PATCH/DELETE HTTP methods — never GET. This must be enforced as a coding convention.

---

## Architectural Smells

**AS-001: NG-006 "Administrative actions via direct database access" is high-risk production hygiene.**
Running ad-hoc SQL against a production database without an admin interface is a well-known source of production incidents (wrong-table updates, missing WHERE clauses, accidental fee config corruption). Even a minimal set of admin CLI scripts with guarded operations (confirm before execute) is significantly safer than raw SQL. The `system_config` update and stock reference seeding paths are particularly high-risk. The `admin` module exists — add basic admin endpoints or CLI commands before launch.

**AS-002: Resend templates live in Next.js but are invoked from FastAPI BackgroundTasks.**
Section 11.3 states "React Email templates (co-located in Next.js app, rendered server-side)." If email templates are in the Next.js codebase, how does the FastAPI BackgroundTask render them? This implies either a network call from FastAPI to the Next.js server to render the template, or the templates are duplicated/shared. The mechanism is not explained and is architecturally unclear.

**AS-003: `process_renewals.py` calls Stripe to "initiate payment" without a clear outcome path.**
The renewal job calls `stripe.invoice.create` or `stripe.subscription.retrieve` and then waits for a webhook. The outcome of the cron job (success/failure in initiating the payment) is separate from the outcome of the payment itself (which arrives via webhook). This two-phase, asynchronous process with an intermediate "initiated" state is not reflected in the subscription state machine, the `User` account status, or the `SubscriptionRecord`. If CRIT-R-003 is resolved by removing this cron job in favour of Stripe-native renewal, this smell is eliminated.

**AS-004: Audit log is deleted as part of PDPA hard-delete — potential conflict with financial record retention.**
Malaysian financial regulations (Capital Markets and Services Act, Bursa rules) may require retention of transaction records for 7 years. The audit log captures `LOT_CREATED`, `LOT_UPDATED`, `LOT_DELETED`, `DIVIDEND_CREATED` events. Deleting these on PDPA request may conflict with financial record-keeping obligations. The `SubscriptionRecord` is retained and anonymised (correctly), but the audit trail of financial transactions is not. A legal opinion on this specific intersection is recommended before the PDPA deletion workflow is implemented.

---

## Overengineering

**OE-001: Optimistic locking for V1 concurrent user volumes.**
At 500 concurrent users with an average of 50 positions, the probability that two separate sessions edit the same `Lot` record simultaneously is extremely low. The `version INTEGER` column and associated HTTP 409 conflict handling add code complexity to every UPDATE path. This is correct enterprise practice, but for a bootstrapped MVP it may be deferred to V1.1. The decision to include it is defensible if the V2 multi-portfolio or multi-user sharing scenarios are anticipated.

**OE-002: Five strict module boundaries for a solo-founder MVP.**
The modular monolith with five domain modules and "no direct cross-module database joins" adds significant structural overhead for a team of one. A simpler two-layer structure (routes + service) without strict domain isolation would be easier to navigate. The isolation is valuable if team size grows, but the cost is non-trivial ceremony at MVP scale. This is a judgment call — the document's rationale (preparing for service extraction at V3+) is legitimate but distant.

---

## Underengineering

**UE-001: No staging environment (addressed in MED-R-001).**

**UE-002: Single retry for legally required PDPA notifications (addressed in MED-R-005).**

**UE-003: No file size or content limits on CSV import (addressed in HIGH-R-009).**

**UE-004: No integration test specification for P0 financial invariants.**
The document mandates "a mandatory P0 regression test that cannot be skipped" for the qualifying_shares invariant (R-002). However, the CI pipeline (§18.2) is described only as "pytest + tsc + eslint" with no further detail. There is no specification for: which tests are P0, what the test coverage requirements are, whether integration tests run against a real PostgreSQL instance in CI, or how the CI database is provisioned. For a product whose core value proposition is financial accuracy, the test strategy deserves a dedicated section.

**UE-005: No admin tooling or runbook for operational tasks.**
Beyond Sentry and BetterUptime alerts, there is no description of how the solo founder responds to an alert. When the PDPA deletion confirmation email fails (Sentry alert fires), what is the remediation procedure? When a cron job fails, how is it re-triggered manually? When a user reports a wrong price, what is the manual override procedure? These runbooks should be at least briefly documented before launch.

---

## Diagram Quality

**DQ-001: Component diagram (§7.1) — missing the React Email / Resend template rendering path.**
The component diagram shows `FastAPI → BackgroundTask → Resend` but does not show how email templates (stated to be in Next.js) are accessed. If there is a server-to-server call, it should be visible. This is the same as AS-002.

**DQ-002: Data flow diagram for price refresh (§9.3) — cron schedule label says "Mon/Fri" but should say "Mon–Fri".**
Minor: the flowchart node reads `"Render Cron: 09:30 UTC Mon/Fri"`. The cron expression `30 9 * * 1-5` means Monday through Friday. The label should read "Mon–Fri" to be unambiguous.

**DQ-003: ER diagram (§12.1) — `BrokerConfig.created_by_user_id` has no FK relationship drawn.**
`BrokerConfig` has a `created_by_user_id` field, implying a relationship to `User`. The ER diagram does not draw this relationship, making it unclear whether custom `BrokerConfig` is user-scoped or system-scoped. The `is_system` flag suggests both, but the ownership model is not visually represented.

**DQ-004: Subscription lifecycle state diagram (§12.5) — missing `grace_period` state.**
Section 15.2 describes a "grace period on renewal failure" and §11.2 Stripe integration mentions "invoice.payment_failed (grace period)." However, the subscription state diagram does not include a `grace_period` state between `active` and `trial_expired`. The current diagram implies `active → trial_expired` directly on payment failure. A `grace_period` intermediate state (where the user retains access for N days while payment is retried) should be modelled explicitly if it exists.

**DQ-005: Deployment diagram (§18.1) — pre-deploy migration arrow direction is ambiguous.**
The arrow `RWeb → (Pre-deploy: alembic upgrade head) → RPG` uses the same edge style as runtime database connections. A note or different style would clarify that this is a pre-deploy hook, not a runtime data path.

---

## Missing Scenarios

**MS-001: User cancels subscription mid-cycle.**
The Stripe integration section lists `customer.subscription.deleted` as a handled event. However, the subscription lifecycle description does not specify: does the user retain access until the end of the paid period (Stripe's default for cancellations at period end) or is access revoked immediately? This affects how `subscription_renewal_date` is used and whether a `cancelled_pending_expiry` state is needed.

**MS-002: User requests PDPA deletion while subscription is active.**
The PDPA deletion workflow (§10.5) shows the user initiating deletion. There is no mention of cancelling the active Stripe subscription at deletion time. If the subscription is not cancelled, Stripe will attempt renewal after the user has been hard-deleted, producing a payment against a non-existent customer record.

**MS-003: Multiple failed login attempts — account lockout policy.**
Rate limiting (`5/minute per IP`) is applied to login. However, a distributed attack from multiple IPs targeting a single account is not covered. There is no account lockout policy after N consecutive failed login attempts. This is a standard security control for financial applications.

**MS-004: User changes email address.**
There is no workflow for changing a registered email address. Email change requires: (1) new email verification before the change is committed; (2) audit logging; (3) token_version increment to invalidate existing sessions; (4) a grace period or notification to the old email. The absence of this feature should be explicitly listed as a Non-Goal if not planned for V1.

**MS-005: CSV import with duplicate stock codes across rows.**
The CSV import Phase 1 validation is described but does not specify how duplicate rows are handled. If a user uploads a CSV with the same stock code and purchase date appearing twice, should this create two lots, one lot, or a validation error?

**MS-006: yfinance ticker format mismatch for Bursa-listed stocks.**
Bursa Malaysia stocks use the `.KL` suffix in yfinance (e.g., `1155.KL` for Maybank). The `stocks` table stores `stock_code` (e.g., `1155`). The price refresh script must map between these formats. There is no description of this mapping logic or its failure cases (e.g., what if a stock code has no `.KL` equivalent in yfinance, or yfinance returns a different ticker format for warrants and REITs).

---

## Missing Failure Cases

**MFC-001: Alembic migration succeeds on Render, but the new FastAPI code crashes on startup.**
The deployment sequence shows the Render pre-deploy command runs `alembic upgrade head`, and if it succeeds, the new FastAPI version is deployed. If the new FastAPI version crashes at startup (e.g., due to an import error or a missing environment variable), Render will attempt to restart it, but the schema migration has already been applied. Rolling back requires reverting the migration manually via `alembic downgrade`. This failure mode is acknowledged in §18.4 but the procedure is a manual one-liner — it should be explicitly tested before launch.

**MFC-002: yfinance returns a valid price for the wrong date.**
yfinance may return the most recently available price even if the requested date is not a trading day (e.g., requesting today's price when the market was closed unexpectedly). The price validation guard (>0, <50% deviation) would accept this stale price as valid and update `last_refreshed_at` to today, hiding the staleness. The stale-data banner would not fire. Users would see a recent price but not know whether it reflects today's trading session.

**MFC-003: Resend permanently rejects the domain (account suspension or billing lapse).**
The failure handling for Resend covers per-email API errors. If the Resend account is suspended (billing lapse, spam complaints, domain verification expiry), all email delivery will fail silently beyond the one retry. There is no monitoring for cumulative email delivery failure rates, and the solo founder may not notice until users start reporting that they are not receiving emails.

**MFC-004: Render PostgreSQL snapshot restore takes longer than 4 hours (RTO target).**
The RTO target is ≤ 4 hours, but this assumes Render's restore operation completes within that window. For a larger database with many `audit_log` and `price_snapshot` rows, restore from snapshot may take longer. The 4-hour RTO has not been validated against Render's actual restore performance.

**MFC-005: User submits CSV with a stock code that exists in the `stocks` table but has `is_active = false`.**
Phase 1 validation checks `SELECT stocks WHERE code IN (imported codes)`. If the query returns a result for a delisted stock code (because the row exists with `is_active = false`), the import will proceed to Phase 2 and create a position for a delisted stock. The expected behaviour (reject, warn, or accept) is unspecified.

---

## Summary of Findings

| ID | Severity | Area | One-line description |
|---|---|---|---|
| CRIT-R-001 | Critical | Security | `*.vercel.app` CORS wildcard allows any Vercel app to make credentialed requests |
| CRIT-R-002 | Critical | Completeness | FR-018 PDPA Data Export has no implementation in the architecture |
| CRIT-R-003 | Critical | Correctness | Stripe renewal cron conflicts with Stripe-native billing — double-charge risk |
| HIGH-R-001 | High | Security | 30-day JWT expiry too long for a financial application |
| HIGH-R-002 | High | Security | HS256 symmetric signing — all tokens compromised if secret leaks |
| HIGH-R-003 | High | Operational | Preview deployments target production API — production data mutation risk |
| HIGH-R-004 | High | Reliability | Sequential yfinance fetches can exceed the 24-hour cron window at scale |
| HIGH-R-005 | High | Reliability | No cleanup mechanism for stuck ImportJob records after service crash |
| HIGH-R-006 | High | Consistency | Yield "stored" in precision table contradicts "computed at query time" in ADR-004 |
| HIGH-R-007 | High | Correctness | `audit_log` FK `ON DELETE SET NULL` conflicts with explicit PDPA deletion job |
| HIGH-R-008 | High | Correctness | Stripe webhook race condition — user returns to app before webhook is delivered |
| HIGH-R-009 | High | Security | No file size, row count, or CSV injection limits on import endpoint |
| HIGH-R-010 | High | Completeness | No token refresh mechanism for expiring JWTs |
| HIGH-R-011 | High | Security | Password reset and verification token mechanics are unspecified |
| HIGH-R-012 | High | Completeness | BrokerConfig CRUD workflow absent from all architecture sections |
| MED-R-001 | Medium | Operations | No staging environment for financial application with real payments |
| MED-R-002 | Medium | Performance | bcrypt CF12 on 0.5 vCPU may block event loop under concurrent auth load |
| MED-R-003 | Medium | Performance | TTLCache cold on every restart — database burst post-deployment |
| MED-R-004 | Medium | Operations | Bursa holiday calendar update procedure unspecified |
| MED-R-005 | Medium | Reliability | One email retry insufficient for PDPA-legally-required notifications |
| MED-R-006 | Medium | Correctness | 50% price deviation threshold rejects valid corporate-action prices |
| MED-R-007 | Medium | Reliability | Per-user PDPA deletion idempotency under partial failure not proven |
| MED-R-008 | Medium | Security | Stripe webhook endpoint unprotected from volumetric abuse |
| LOW-R-001 | Low | Completeness | No standard API error response envelope specified |
| LOW-R-002 | Low | Completeness | Delisted stock behaviour on existing positions unspecified |
| LOW-R-003 | Low | Consistency | Optimistic locking not applied to `Position` entity |
| LOW-R-004 | Low | Extensibility | No API versioning strategy described |
| LOW-R-005 | Low | Consistency | `subscription_renewal_date` can drift from Stripe's actual billing date |

---

_Architecture review prepared by: Independent Principal Architect_  
_Input: BursaTrack-Solution-Architecture.md v1.0_  
_Review date: 2026-06-28_
