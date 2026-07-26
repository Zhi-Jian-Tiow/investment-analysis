# BursaTrack — V1 User Stories

> **Purpose:** Sprint-ready backlog for V1 implementation, derived from BursaTrack-PRD-Final.md, BursaTrack-BAS-Enhanced Parts 1–3, BursaTrack-Solution-Architecture.md, and the API/DB design artifacts.<br>
> **Format:** Each story = a Given/When/Then developer action plan + technical detail block (Acceptance Criteria, Definition of Done, Dependencies & Integrations, Technical Constraints).<br>
> **Traceability:** `FR-xxx` = PRD/BAS functional requirement, `BR-xxx` = business rule, `VR-xxx` = validation rule, `EX-xxx` = exception, `EC-xxx` = edge case, `ADR-xxx` = architecture decision. IDs let QA and engineering cross-reference the BAS/architecture docs directly.<br>
> **Open items:** Several stories below are flagged `⚠ STAKEHOLDER SIGN-OFF PENDING` where the source BAS lists an unresolved OQ (open question). These do not block starting the story but must be resolved before the story is marked done.

---

## How Epics Map to the Architecture

Epics follow the five domain modules defined in the Solution Architecture (§7.2, P-008), plus one cross-cutting Deployment/Infrastructure epic:

| Epic                                  | Architecture Module     | FRs Covered                             |
| ------------------------------------- | ----------------------- | --------------------------------------- |
| 1. Authentication & Account Lifecycle | `auth`                  | FR-001, FR-002, FR-017                  |
| 2. Portfolio — Positions & Lots       | `portfolio`             | FR-003, FR-004, FR-005, FR-006          |
| 3. Dividend Tracking                  | `portfolio`             | FR-009, FR-010, FR-013                  |
| 4. Dashboard & Sell Calculator        | `portfolio`             | FR-011, FR-012                          |
| 5. Pricing & Market Data              | `pricing`               | FR-007, FR-008                          |
| 6. CSV Import & Export                | `portfolio` / `pricing` | FR-014, FR-015                          |
| 7. Subscription & Billing             | `subscription`          | FR-016                                  |
| 8. PDPA Compliance & Admin            | `admin`                 | FR-018, FR-019, BrokerConfig/fee config |
| 9. Deployment & Infrastructure        | cross-cutting           | —                                       |

Each Epic's stories are split into **Backend**, **Frontend**, and **Deployment** stories per the module structure in Solution-Architecture §7.2.

---

# Epic 1 — Authentication & Account Lifecycle

## BE-1.1 — User Registration & Email Verification API

**FR-001 · Priority: Must Have · Status: ✅ Implemented (2026-07-25)**

**Developer Action Plan**

```gherkin
Given the auth module is scaffolded with fastapi-users and the users/portfolios tables exist
When a client POSTs to /auth/register with email, password, password_confirm, and default_broker_id
Then a User row is created with account_status="trial", trial_expiry_date = today + 14 days,
     an empty Portfolio is created and linked, a pending_tokens row (type=email_verification,
     24h expiry) is created, a verification email is queued via BackgroundTasks,
     and the response sets the JWT session cookie so the user is logged in immediately
```

**Acceptance Criteria**

- [x] `POST /auth/register` validates email (VR-001: RFC 5321, ≤254 chars, unique, lowercase-normalized), password (VR-002: 8–128 chars, ≥1 uppercase, ≥1 digit) — `password_confirm` is **not** server-validated; see Deviation 2 below
- [x] Duplicate email is rejected, not a 500 — implemented as `422 validation_failed`, not a 409; see Deviation 3 below
- [x] `broker_id` must reference an existing `BrokerConfig` — "active" concept not implemented; see Deviation 4 below
- [x] User created with `token_version=0`, `email_verified=false`
- [x] `GET /auth/verify?token=xxx` validates the token (exists, unused, not expired), marks `email_verified=true`; expired token returns "link expired" error; already-used token returns "already used" error
- [ ] User is **not** blocked from any feature during trial while unverified (EX-007) — trivially true today (no protected routes exist yet to gate), not meaningfully tested; revisit once BE-1.2/dashboard access checks exist
- [ ] **Not implemented:** "Resend verification email" capability — no such endpoint exists; see Deviation 5 below
- [x] `audit_log` entry `USER_REGISTERED` written in the same transaction as the User/Portfolio insert — written, but not directly asserted by a test
- [x] Rate limited to 3/minute per IP (architecture §14.4) — tested

**Definition of Done**

- [x] Unit tests cover: happy path, duplicate email, password mismatch (uppercase/digit/length), invalid email format, unknown broker, rate limiting, expired/used/invalid verification token — 12/12 passing (`tests/test_auth_register.py`, `tests/test_auth_verify.py`)
- [x] Registration + Portfolio creation + PendingToken + audit log insert are atomic (single DB transaction, one `commit()` in `auth/service.py::register_user`)
- [x] No plaintext password ever logged — true by code inspection (no log call references the raw password); not confirmed by an automated log-capture test
- [~] Endpoint schemas match `03-openapi-specification.md`'s `RegisterRequest`/`AuthResponse`/`UserResponse` field-for-field; FastAPI's auto-generated OpenAPI docs have not been diffed against the spec's tags/descriptions/security-scheme metadata

**Dependencies & Integrations**

- `BrokerConfig` seed data must exist first — delivered via Alembic migration `0004_seed_system_brokers`, not full Epic 9
- Resend API key configured — ✅ resolved 2026-07-25, see Deviation 5's update
- `pending_tokens` table (architecture §14.1) — delivered via migration `0001`

**Technical Constraints**

- Password hashed with bcrypt CF12, executed in a thread pool executor (MED-R-002) — must not block the async event loop
- Email verification email sent via `BackgroundTasks`, not inline in the request/response cycle
- `password_hash` and `token_version` must never appear in any response schema (PDPA / API security review PD requirement)

---

### Implementation Record — BE-1.1

**What was actually built**

- Backend scaffold at `backend/app/`, trimmed to only what this story needs (no Position/Lot/DividendTranche, no SystemConfig/SystemDeletionLog, no portfolio/admin HTTP routes) — a deliberate scope cut from the fuller scaffold originally drafted, per explicit direction to build story-by-story rather than pre-building ahead of need.
- Endpoints: `POST /auth/register`, `GET /auth/verify` (`app/auth/router.py`, `service.py`, `security.py`, `schemas.py`, `models.py`).
- Cross-module service functions (architecture P-008 — no direct cross-module table access): `app/portfolio/service.py::get_broker`/`create_portfolio`, `app/admin/service.py::record_audit_event`.
- Alembic migrations `0001`–`0004`: `users`, `pending_tokens`, `broker_configs`, `portfolios`, `audit_log`, plus system broker seed data. This is a trimmed subset of the DB design doc's migrations 001/002/004/007 — only the tables this story touches; each migration file's docstring cross-references the corresponding section of `BursaTrack-DB-Stage3-Physical-Schema.md`.
- `backend/docker-compose.yml` — local PostgreSQL 16 on host port **5433** (not 5432 — a pre-existing native Postgres service on the dev machine was already bound to 5432; discovered when `alembic upgrade head` initially failed with a password error against the wrong server).
- 12 automated tests, all passing, run against isolated in-memory SQLite per test.
- Migrations additionally verified against a live PostgreSQL 16 container (not just the SQLite test double): `upgrade head` and `downgrade base` both round-trip cleanly, and the seeded broker rows were confirmed correct via `psql`.

**Deviations from this story's spec**

1. **Auth library.** Architecture §7.2/§14.1 names `fastapi-users`. Not used. Hand-rolled instead: `bcrypt` (cost factor 12, off-loaded to a thread pool executor) + `PyJWT` (RS256) + a custom `pending_tokens` table for verification/reset tokens. Reason: `fastapi-users`' opinionated user model doesn't map cleanly onto this schema's custom fields (`trial_expiry_date`, `default_broker_config_id`, `token_version`, PDPA lifecycle columns) without fighting its abstractions. **Not yet reflected in the ADR record** — should be logged there before BE-1.2 builds more auth code on top of this choice.
2. **Request shape.** Implemented to match `03-openapi-specification.md`'s `RegisterRequest` exactly: `email`, `password`, `broker_id` only. There is no server-side `password_confirm` field (that's a client-only UX concern, owned by FE-1.1) and no `default_broker_id` field name (the OpenAPI contract calls it `broker_id`). This story's own AC text (written before the OpenAPI spec was cross-checked) still refers to the old names.
3. **Duplicate-email error shape.** Returns `422 validation_failed` with `fields: [{"field": "email", "constraint": "already registered", ...}]`, not a `409`, and not the BAS's suggested copy ("An account with this email already exists. Log in instead?"). This matches `03-openapi-specification.md`, which documents only `201`/`422`/`429` for `/auth/register` — no `409` is in the contract.
4. **Broker validation (VR-007).** Implemented as "must reference an existing `BrokerConfig`" only. The physical schema (`BursaTrack-DB-Stage3-Physical-Schema.md` §3.4, authoritative and downstream of the BAS) has no `is_active` column on `broker_configs` — the "active broker" concept from VR-007/BAS Entity 8 was dropped somewhere between the BA and DB design stages and was never carried into the table that actually exists.
5. ~~**Email delivery is not wired up.**~~ **Resolved 2026-07-25.** `app/email.py` now calls the real Resend SDK (`resend.Emails.send`, offloaded to a thread pool executor since the SDK is synchronous), with 1 retry then a structlog ERROR log on final failure (architecture §15.2's "then Sentry" half is a plain log for now — Sentry isn't wired up until Epic 9). Config additions: `resend_api_key`, `email_from_address` (defaults to Resend's no-verification-needed sandbox sender), `frontend_base_url` (verify/reset links are built from this — they won't resolve to a real page until FE-1.x exists, which is expected). A "resend verification email" endpoint still does not exist — that remains a genuine gap, just a separate one from "is email sending real."
6. **Audit log catalog is trimmed.** `AUDIT_LOG_ACTIONS`/`AUDIT_LOG_ENTITY_TYPES` in `app/admin/models.py` list only `USER_REGISTERED`, `USER_LOGIN`, `PASSWORD_CHANGED` / `User` — the three values Epic 1 stories emit — not the full ~20-value catalog from architecture §14.7. Extending this is a new migration (the DB `CHECK` constraint must be altered), flagged in a code comment at the definition site.
7. **Incidental Epic 9 scope.** This story's build delivered a sliver of DEP-9.1 (repo scaffold) and DEP-9.4 (migration baseline + a working local Postgres) as a side effect, but not those stories in full — there is still no CI pipeline, no Render/Vercel provisioning, and no Sentry/observability wiring.

**Known gaps / not yet verified**

- `audit_log` row content is written on every registration but no test queries the table to assert it — coverage is indirect (via the code path executing without error), not direct.
- "No plaintext password logged" is true by inspection, not by an automated test that captures log output and asserts the password is absent.
- No line-by-line diff has been done between our Pydantic schemas and `03-openapi-specification.md`'s field descriptions, examples, or security-scheme annotations — only the field names/types/required-ness were cross-checked while writing the code.

**Test evidence**

`uv run pytest` → **12/12 passed**. `uv run alembic upgrade head` and `downgrade base` verified against a live PostgreSQL 16 container (`docker-compose.yml`), including a `\dt` + seed-data spot check via `psql`. Two real bugs were found and fixed while doing this (not merely written and assumed correct): an invalid single-element-tuple SQL `CHECK` constraint (Python's `repr()` of a 1-tuple has a trailing comma, which is invalid SQL), and a SQLite-vs-PostgreSQL timezone-naive/aware `datetime` comparison in the token-expiry check.

---

## BE-1.2 — Login, Logout, Session Refresh & Rate Limiting

**FR-002 · Priority: Must Have · Status: ✅ Implemented (2026-07-25)**

**Developer Action Plan**

```gherkin
Given a verified or unverified user account exists
When the user POSTs correct credentials to /auth/login
Then the system sets an HTTP-only, Secure, SameSite=Lax JWT cookie (RS256, 7-day exp,
     payload includes user_id and token_version) and returns the portfolio dashboard route
```

**Acceptance Criteria**

- [x] `POST /auth/login`: on success, resets failed-attempt counter to 0; on failure, increments counter and returns a generic "Email or password is incorrect" message (no account enumeration)
- [x] BR-016: 5 failed attempts within 10 minutes from the same IP locks further attempts for 10 minutes with message "Too many failed attempts. Please wait 10 minutes before trying again." — implemented keyed strictly by **IP**, not by account; see Deviation 2 below
- [x] `POST /auth/logout` increments `token_version`, invalidating all existing JWTs for that user immediately
- [x] `POST /auth/refresh` accepts a valid non-expired JWT and issues a new 7-day JWT if `token_version` still matches; returns 401 otherwise
- [x] `GET /auth/jwks.json` publishes the RS256 public key — verified with a real cryptographic round-trip test (reconstructs the public key from the JWKS `n`/`e` and confirms it actually verifies a token signed by our private key), not just a field-presence check
- [x] Session cookie is never readable by JavaScript (`HttpOnly=true` set in code) — **not verified by an automated test**; see Known Gaps below
- [~] EX-010: an expired/revoked JWT on any authenticated request returns 401 — proven for the only two protected endpoints that exist so far (`/auth/logout`, `/auth/refresh`); the frontend redirect behaviour is explicitly FE-1.2 scope, not this story

**Definition of Done**

- [~] Security test cases from BAS §14: lockout-triggers-at-exactly-5-failures and session-invalidation are both automated and passing; the HTTP-only/Secure cookie-flag check is **not** automated (see Known Gaps)
- [x] Rate limiting via SlowAPI: 5/minute per IP on `/auth/login` (architecture §14.4) — tested, including its interaction with the separately-tracked BR-016 lockout
- [x] `token_version` mismatch correctly rejected with `token_revoked` error code (per API error catalog, ADD-002)

**Dependencies & Integrations**

- ~~`fastapi-users` JWT strategy~~ — **not used**, same deviation as BE-1.1; see Deviation 1 below
- SlowAPI middleware installed and configured per-route — reused from BE-1.1, extended to the new routes

**Technical Constraints**

- JWT expiry is 7 days (not 30 — HIGH-R-001/HIGH-R-010), with silent refresh handled client-side when `exp` is within 24 hours — client-side part is FE-1.2 scope
- No server-side **session** store — session state is still the stateless JWT + `token_version` column (P-002, no Redis). The new BR-016 lockout tracker is a separate, small piece of in-process **abuse-prevention** state (not session state) — see Deviation 3 below for its limitations

---

### Implementation Record — BE-1.2

**What was actually built**

- Endpoints: `POST /auth/login`, `POST /auth/logout`, `POST /auth/refresh`, `GET /auth/jwks.json` — all in `app/auth/router.py`.
- `app/auth/dependencies.py` (new) — `get_current_user`, a FastAPI dependency that decodes the session-cookie JWT (RS256), checks `exp`, and checks `token_version` against the DB row. This is what makes logout/refresh (and every future protected route) actually enforce revocation.
- `app/auth/lockout.py` (new) — `LoginLockoutTracker`, the in-process BR-016/EX-009 tracker (per-IP failure counting, 10-minute window, 10-minute lockout, reset on success).
- `app/auth/security.py` — restored `verify_password` (previously commented out as dead code since nothing called it before this story) and added `build_jwks`.
- `app/auth/service.py` — added `authenticate_user`, `logout_user`; refactored token issuance into a shared `issue_access_token` helper used by register, login, and refresh alike.
- `app/errors.py` — `AppError` now carries optional response `headers` (needed for `Retry-After` on the 429 lockout response); added `invalid_credentials()`, `account_locked()`, `unauthorized()` helpers.
- 14 new tests across `tests/test_auth_login.py`, `test_auth_logout.py`, `test_auth_refresh.py`, `test_auth_jwks.py` — 26/26 total passing including BE-1.1's existing suite.
- No new Alembic migration — this story works entirely off the existing `users` table from migration `0001`.
- Full happy-path smoke-tested against the real PostgreSQL 16 container (register → login → refresh → jwks → logout), not just the SQLite test suite.

**Deviations from this story's spec**

1. **Auth library, again.** Same as BE-1.1: `fastapi-users` is not used. `get_current_user` is a ~30-line hand-rolled dependency instead. This is now the second story built on the hand-rolled approach — worth formally deciding (and recording in the ADR) rather than letting it stay implicit.
2. **Lockout is keyed by IP, not by account.** The AC text ("resets failed-attempt counter... on failure, increments counter") reads ambiguously — could mean per-account or per-IP. Implemented per-IP because that's what BAS EX-009 explicitly says ("All further login attempts from the IP address are blocked"), and because BR-016's own title is "Account Lockout" but its body says "from the same IP address," which only makes sense as an IP-keyed block. Practical effect: a 6th failed attempt against a **different** account from the same IP is also blocked, and a 6th attempt against the **same** account from a **different** IP is not blocked. If the intent was actually per-account lockout, this needs to change.
3. **Lockout state is in-process, not persisted.** There is no table for this in the physical schema (confirmed against all 16 tables in `BursaTrack-DB-Stage3-Physical-Schema.md` — none of them track login attempts), so, consistent with architecture P-002, it's a plain in-memory dict, exactly like SlowAPI's own rate-limit storage. Consequence: a Render restart or a second instance (NG-008 already rules out multi-instance at V1, so this is currently only the restart case) silently clears everyone's lockout state. Same caveat the architecture doc already accepts for SlowAPI; not a new risk, but now there are two independent in-process trackers with this property instead of one.
4. **Timing-safe login added beyond the stated AC.** `authenticate_user` always runs a bcrypt check — against a precomputed dummy hash when the email doesn't exist — so the unknown-email and wrong-password paths take comparable time. Not requested by this story's AC (which only specifies message content, not timing), added because it directly serves the AC's own "no account enumeration" goal for negligible cost.
5. **`/auth/jwks.json` has no rate limit.** Consistent with `03-openapi-specification.md`, which declares no `x-ratelimit` for this endpoint (treated as public, cacheable key material) — flagged only because it's the one endpoint in this story that isn't rate-limited, which could look like an oversight without this note.

**Known gaps / not yet verified**

- **Cookie flags (`HttpOnly`, `Secure`, `SameSite=Lax`) are set in code but not asserted by any automated test.** `httpx`'s test client cookie jar exposes only name/value, not attributes, so proving this would require parsing the raw `Set-Cookie` response header directly. This is a real gap against this story's own DoD line ("cookie is HTTP-only/Secure... confirmed") — should be closed before this is relied on as a security guarantee rather than a code-review-verified one.
- EX-010's "any authenticated request returns 401" is only exercised against `/auth/logout` and `/auth/refresh` — the two protected endpoints that exist today. `get_current_user` is written generically, but there's nothing else yet to prove it against.
- No test asserts the `USER_LOGIN` audit_log row's content directly (same pattern as BE-1.1's `USER_REGISTERED` gap) — written, not directly asserted.
- **No absolute session lifetime cap (unbounded sliding renewal).** `/auth/refresh` re-signs the same `user_id`/`token_version` with a fresh 7-day `exp`, and can itself be called again before that expires — there's nothing recording when the session originally began. A token — stolen or legitimate — can therefore renew indefinitely as long as it's used at least once every 7 days; only an explicit logout or password change (both of which bump `token_version`) ever forces re-authentication. This matches the architecture doc's own documented design (§14.1) and is a deliberate simplification for V1, not an oversight — but it's the one gap worth closing (e.g. embed the original login timestamp in the JWT payload and reject refresh past a max session age, such as 30 days) before real user trust/data volume makes a stolen-and-quietly-renewed cookie a meaningful risk.

**Test evidence**

`uv run pytest` → **26/26 passed** (12 from BE-1.1 + 14 new). Full endpoint set (`register`, `verify`, `login`, `logout`, `refresh`, `jwks.json`) additionally smoke-tested end-to-end against the live PostgreSQL 16 dev container with no schema changes required.

---

## BE-1.3 — Password Reset Flow

**FR-017 · Priority: Must Have · Status: ✅ Implemented (2026-07-25)** ⚠ _STAKEHOLDER SIGN-OFF PENDING (OQ-007: confirm Must Have classification, not a fast-follow)_

**Developer Action Plan**

```gherkin
Given a user has forgotten their password
When they POST their email to /auth/password-reset-request
Then the system returns the identical response ("If an account with that email exists,
     a reset link has been sent.") regardless of whether the account exists, and — only
     if the account exists — generates a single-use pending_tokens row (type=password_reset,
     1-hour expiry) and queues the reset email
```

**Acceptance Criteria**

- [~] Response body is indistinguishable between an existing and non-existing email — **true and tested**. Response *timing* is not cryptographically equalized, only practically close (see Deviation 1 below)
- [x] `POST /auth/password-reset` validates token (exists, unused, ≤1 hour old); expired → "This reset link has expired. Request a new one?"; already used → "This reset link has already been used. If you did not reset your password, contact support."
- [x] New password validated per VR-002; on success, `password_hash` updated, `token_version` incremented (invalidates **all** active sessions, per BR-019/EX-011), token marked `used_at=now()`
- [ ] EX-011: email delivery failure does not change the user-facing response — **vacuously true, not meaningfully tested**; see Deviation 2 below (same underlying gap as BE-1.1)
- [x] EC-017: resetting the password for a never-verified account also marks the email as verified
- [x] Rate limited to 3/minute per IP

**Definition of Done**

- [x] Gherkin-equivalent scenarios (happy path, expired token, already-used token, invalid token, enumeration prevention, second-request invalidates first link, complexity validation, rate limit) automated as integration tests — 11 new tests, all passing
- [x] Generating a new reset token for the same `(user_id, type)` deletes the previous pending token row (HIGH-R-011) — implemented and explicitly tested

**Dependencies & Integrations**

- Shares the `pending_tokens` table with email verification (BE-1.1) — confirmed working via the same `_consume_pending_token` code path, now shared by both flows. Deletion cancellation (BE-8.2) will be the third consumer.
- Resend for email delivery — ✅ resolved 2026-07-25, see Deviation 2's update

**Technical Constraints**

- Token is an opaque, single-use value; only its SHA-256 hash is stored (`token_hash`), never the raw token
- No behavioral branch in the code path may create a timing difference between "found" and "not found" cases — see Deviation 1 for how far this was actually taken

---

### Implementation Record — BE-1.3

**What was actually built**

- Endpoints: `POST /auth/password-reset-request`, `POST /auth/password-reset` (`app/auth/router.py`).
- `app/auth/service.py` — added `request_password_reset` and `reset_password`. Refactored the token-validation logic that BE-1.1's `verify_email` already had (not-found/already-used/expired + tzinfo normalization) into a shared `_consume_pending_token` helper, now used by both flows instead of being duplicated a third time. `verify_email` itself was rewritten to call this helper — its behavior is unchanged, only de-duplicated (re-ran BE-1.1's existing test suite to confirm no regression).
- `app/auth/schemas.py` — added `PasswordResetRequest`, `PasswordResetComplete`, `MessageResponse`. The password-complexity check (uppercase + digit, VR-002) that previously lived only inside `RegisterRequest` was extracted into a shared `_check_password_complexity` function so `PasswordResetComplete.new_password` enforces the identical rule rather than duplicating the logic.
- `app/email.py` — added `send_password_reset_email` (originally a logging stub; see Deviation 2's update — since resolved).
- No new Alembic migration — reuses `pending_tokens` from migration `0001` (the same table BE-1.1 already created, now with two token types stored in it: `email_verification` and `password_reset`).
- 11 new tests in `tests/test_auth_password_reset.py` — 37/37 total passing across the whole auth test suite.
- Full happy-path smoke-tested against the real PostgreSQL 16 container (register → request reset → complete reset → old password rejected → new password accepted).

**Deviations from this story's spec**

1. **Timing indistinguishability is "practically close," not cryptographically constant-time.** The AC's own wording ("No behavioral branch... may create a timing difference") is stricter than what's implemented. `request_password_reset` runs the same `get_user_by_email` lookup (the dominant cost) on both the found and not-found paths, but only the found path does two additional small local writes (delete old token, insert new token) and queues a BackgroundTask — a real, if small, timing difference exists between the two paths. This matches the architecture doc's own risk-acceptance language for this exact endpoint (§14.1: *"the delay introduced by... the endpoint is sufficient to prevent timing attacks at this scale"*), but it is not the byte-for-byte constant-time guarantee the AC's literal wording implies. No artificial delay/padding was added to close this gap — doing so would add latency to every legitimate request too, for a benefit that's arguably academic at this traffic scale. Flagging the gap rather than silently meeting a weaker bar than the AC states.
2. ~~**Email delivery is still not wired to Resend.**~~ **Resolved 2026-07-25**, together with BE-1.1's identical gap (see that story's Deviation 5). `send_password_reset_email` now calls the real Resend SDK via the same `_send_with_retry` helper `send_verification_email` uses (1 retry, then a structlog ERROR log — Sentry integration is still Epic 9). EX-011's "failure logged server-side" is now genuinely testable, since there's real failure-handling logic to test against instead of an unconditional stub — see `tests/test_email.py`, added specifically to exercise this (success, retry-then-succeed, exhausts-retries-without-raising), none of which existed when this story was first marked done.
3. **Token expiry is genuinely different per type, on purpose.** `PASSWORD_RESET_TOKEN_EXPIRY_HOURS = 1`, vs. `email_verification`'s 24 hours (`settings.email_verification_token_expiry_hours`). Both live in the same `pending_tokens` table and go through the same validation helper — only the expiry duration passed in at creation time differs, matching BAS FR-017/Workflow 8 exactly.

**Known gaps / not yet verified**

- No automated timing measurement exists to quantify the residual timing difference described in Deviation 1 — a flaky, low-value kind of test to automate; the mitigation is structural (identical dominant-cost lookup), not measured.
- No test asserts the `PASSWORD_CHANGED` audit_log row's content directly (same pattern as prior stories' audit-log gaps).
- `PasswordResetComplete.new_password` has no explicit test for the `maxLength: 128` boundary (only the complexity-rule rejection is tested).

**Test evidence**

`uv run pytest` → **37/37 passed** at the time this story was completed (26 from BE-1.1/BE-1.2 + 11 new). Full flow (register → request reset → complete reset → old password rejected → new password accepted) additionally smoke-tested end-to-end against the live PostgreSQL 16 dev container, no schema changes required.

**Post-story follow-up — Resend integration (2026-07-25, same day)**

Both this story's Deviation 2 and BE-1.1's Deviation 5 (the same underlying gap — email sending was a `structlog` stub, not real) were closed together as a single cross-cutting change, since fixing one without the other would have left `send_password_reset_email` and `send_verification_email` inconsistent. Summary:

- `app/email.py` rewritten to call the real Resend SDK (`resend.Emails.send`), offloaded to a thread pool executor since the SDK is synchronous (built on `requests`); 1 retry, then a structlog ERROR log on final failure (architecture §15.2 — the "then Sentry" half is deferred to Epic 9, since Sentry isn't wired up yet)
- New settings: `resend_api_key`, `email_from_address` (defaults to Resend's sandbox sender, no domain verification needed), `frontend_base_url` (verify/reset links are built from this; they 404 until FE-1.x exists, which is expected and fine)
- New `tests/test_email.py` (4 tests) exercising the real send/retry logic directly against a monkeypatched `resend.Emails.send` — success, retry-then-succeed, and exhausts-retries-without-raising
- New autouse safety-net fixture (`block_real_resend_calls` in `conftest.py`) that forces `resend.Emails.send` to fail fast in every test by default, so tests that don't explicitly mock the email functions (e.g. `test_auth_register.py`) can never make a real network call by accident — verified this actually engages (not just coincidentally passes) by running a registration test with `-s` and confirming the retry/failure log lines appear while the endpoint still returns 201
- Total suite: **41/41 passed** (37 prior + 4 new)
- Not done in this follow-up: a "resend verification email" endpoint (still doesn't exist — separate gap from "is sending real"), Jinja2 HTML templates (emails are inline HTML strings, adequate for V1 volume), and a live end-to-end send against the real Resend API (only exercised against a monkeypatched fake — worth a one-time manual smoke test before launch, using the user's real Resend API key, which was not shared with or used by this session)

---

## FE-1.1 — Registration & Onboarding UI

**FR-001 · Priority: Must Have · Status: 🟡 Implemented, manual QA in progress (2026-07-25)**

**Developer Action Plan**

```gherkin
Given a visitor is on the marketing site
When they click "Create Account" and submit email, password, password confirmation, and default broker
Then they are redirected to the dashboard with a persistent banner "Please verify your email.
     Check your inbox." and can immediately begin adding positions
```

**Acceptance Criteria**

- [x] Inline field validation matches VR-001/VR-002 error copy exactly (e.g., "Passwords do not match", "Please enter a valid email address") — `lib/validation.ts` mirrors the BAS copy verbatim
- [x] Broker dropdown is pre-populated from `GET /api/v1/brokers` (system brokers only at this stage) — endpoint didn't exist; built as part of this story (see Deviation 3). A real bug was found and fixed during manual QA: the dropdown initially displayed the broker's UUID instead of its name after selection — see Deviation 5.
- [ ] Time-to-first-value: onboarding form → dashboard → first position addable in under 10 minutes end-to-end — **not measured**; "first position addable" isn't buildable yet (Epic 2), so this AC can't be fully satisfied until then
- [x] "Resend verification email" control visible on the banner; disabled with a cooldown after use — endpoint didn't exist either; built as part of this story (see Deviation 4)
- [x] Duplicate-email error surfaces the PRD-specified copy: "An account with this email already exists. Log in instead?" with a link to `/login`

**Definition of Done**

- [ ] Component tested against all BAS US-001 Gherkin scenarios — **not automated**. No frontend test tooling (Vitest/RTL/Playwright) is set up yet; verification so far is `next build`'s type-check plus manual browser testing, which is still in progress as of this writing (see Known Gaps)
- [~] Responsive from 375px viewport — built with Tailwind's responsive utilities throughout, but no explicit test/screenshot at 375px has been done
- [x] No client-side storage of password or token in localStorage/sessionStorage — true by code inspection; all form state is `useState`, the session lives only in the HTTP-only cookie the frontend never touches directly

**Dependencies & Integrations**

- BE-1.1 registration/verification endpoints — used as-is
- `GET /api/v1/brokers` — ⚠ did **not** wait for Epic 8; built the minimal read-only version needed now (see Deviation 3), same pattern as prior stories pulling forward small necessary pieces

**Technical Constraints**

- Built with shadcn/ui + Tailwind, TypeScript strict mode — shadcn's current CLI default ("base-nova" style) is built on **Base UI** (`@base-ui/react`), not Radix UI as the architecture doc assumes (§7.1: "Radix UI primitives"). Not a choice made here — it's shadcn's own current default — but worth recording since it's a real API difference (see Deviation 5) and the architecture doc's wording is now slightly stale.
- Uses the shared `lib/api.ts` fetch wrapper with `credentials: include`

---

### Implementation Record — FE-1.1

**What was actually built**

- **Design source:** imported the user's Claude Design project (`BursaTrack.dc.html` + `support.js`, a `x-dc` prototype-runtime format, not React) via the DesignSync MCP tool. Extracted the actual palette, typography (Instrument Sans / Spline Sans Mono via Google Fonts), card/input/button geometry, and the exact register-screen copy and layout — then re-implemented it properly in React/Tailwind rather than porting the prototype DSL. Re-themed `globals.css`/`layout.tsx` from shadcn's default oklch/Geist theme to these values.
- Next.js 15 project at `frontend/` (pinned to match ADR-003 exactly — the `create-next-app` CLI defaults to 16; confirmed against the architecture doc's 3 explicit "Next.js 15" mentions before scaffolding, see Deviation 1).
- Pages: `/` (minimal landing, "Create Account" CTA), `/register` (the real FE-1.1 deliverable), `/login` (visual-only placeholder — FE-1.2 wires it up), `/dashboard` (stub redirect target — Epic 4 owns the real one).
- Components: `AuthCard` (shared logo+card shell), `RegisterForm` (the actual form logic), `PasswordStrengthMeter` (visual aid from the design, not AC-required), `VerifyBanner` (email-verification banner with working resend + cooldown).
- `lib/api.ts` (fetch wrapper, `credentials: include`), `lib/types.ts` (hand-written mirrors of the backend Pydantic schemas — no shared codegen exists), `lib/validation.ts` (VR-001/VR-002 client-side mirrors).
- `hooks/useBrokers.ts` (SWR), `hooks/useCurrentUser.ts` (bootstraps the logged-in user for the dashboard stub — see Deviation 6).

**Backend additions required to make this story actually work (not just look complete)**

1. `GET /api/v1/brokers` — didn't exist. Added `app/portfolio/router.py` + `schemas.py` (`BrokerConfigResponse`/`BrokerListResponse`, matching `03-openapi-specification.md` exactly) + `list_brokers()` in `service.py`. The OpenAPI spec documents this endpoint as requiring auth, which is unworkable for a pre-signup registration page — resolved by adding `get_current_user_optional` to `app/auth/dependencies.py` (returns `User | None` instead of 401ing), so the one endpoint serves both the anonymous case (system brokers only) and an eventual authenticated case (system + own custom brokers).
2. `POST /auth/resend-verification` — also didn't exist; the banner's resend button had nothing to call. Added `resend_verification_email()` in `app/auth/service.py`, reusing the exact HIGH-R-011 delete-then-insert token pattern BE-1.3 already established for password reset, applied to `email_verification` tokens. No-ops (doesn't send) if the account is already verified.
3. **CORS middleware didn't exist at all anywhere in the backend.** Found this while wiring the frontend up — without it, every browser request from `localhost:3000` would have been silently blocked, regardless of how correct the frontend code was. Added `cors_allowed_origins` (comma-separated) to `Settings` and wired `CORSMiddleware` in `main.py` with `allow_credentials=True` (required for the HTTP-only cookie to work cross-origin) and a concrete origin list (a wildcard is invalid together with credentials, per the CORS spec). Verified via a manual `OPTIONS` preflight request that the response headers are correct.

**Deviations from this story's spec**

1. **Next.js 16 vs. 15.** The `create-next-app` CLI's `@latest` defaults to 16. Before scaffolding, grepped every technical-design doc for "Next.js 1[56]" — all 3 hits say "Next.js 15" (architecture §1, §7.1, ADR-003 traceability table), none say 16. Confirmed with the user before proceeding; scaffolded pinned to `create-next-app@15`.
2. **shadcn is themed to the design, not left at its neutral default.** `globals.css`'s CSS variables were fully replaced with the BursaTrack palette (hex values, not oklch) and fonts swapped to Instrument Sans / Spline Sans Mono. This is a deliberate, necessary step for the design import to mean anything — undocumented as an explicit AC line item, but implied by "Built with shadcn/ui + Tailwind" plus the design import instruction.
3. **`GET /api/v1/brokers` was pulled forward from Epic 8**, same reasoning as prior stories pulling forward the minimum adjacent backend piece a frontend story hard-depends on. Only the read path was built — no `POST`/`PATCH`/`DELETE` custom-broker management, which stays Epic 8 (BE-8.3) scope.
4. **`POST /auth/resend-verification` didn't exist in any prior story's scope.** BE-1.1's Implementation Record explicitly flagged this as a gap ("no such endpoint exists") — closed here because FE-1.1's AC hard-requires a *working* resend control, not a decorative one.
5. **Base UI, not Radix — and it caused a real bug.** shadcn's current default style (`base-nova`) generates components on `@base-ui/react`, not Radix UI. This mattered concretely: Base UI's `Select.Value` does not auto-derive its displayed label from the matching `SelectItem`'s children the way Radix's does — it shows the raw `value` (the broker's UUID) unless given an explicit `children` render function. Manual QA caught this (broker dropdown showed a UUID instead of "Maybank IB" etc. after selection); fixed by passing `<SelectValue>{(value) => brokers.find(b => b.id === value)?.name ?? placeholder}</SelectValue>`. Worth remembering for every other `Select` usage in this codebase going forward.
6. **`useCurrentUser` bootstraps via `POST /auth/refresh`, not a dedicated read endpoint.** No `GET /auth/me` exists. Calling the mutating refresh endpoint unconditionally on every dashboard mount is a reasonable stand-in for a stub page, but isn't the real silent-refresh design (checking the JWT's `exp` first) — FE-1.2 should replace this rather than build alongside it.
7. **Password strength meter** — visual-only, matches the design, not requested by this story's AC (which only requires validation *messages*, not a live strength indicator). Low-cost addition, not the source of truth for whether a password is accepted.

**Known gaps / not yet verified**

- **No automated frontend tests exist.** This story's own DoD line ("component tested against all BAS US-001 Gherkin scenarios") is unmet by anything automated — only `next build`'s type-check and manual browser testing cover it.
- **Manual browser QA is in progress, not complete, as of this record.** No `chromium-cli` was available in this environment and the user declined the Chrome automation extension, so verification is being done by the user directly rather than captured as a screenshot/automated check from this session. Two issues surfaced so far: the broker-label bug above (fixed), and a `jwt.exceptions.InvalidKeyError: Could not parse the provided public key` runtime error — **this is a local environment configuration issue, not a code defect**: the user's `backend/.env` still has the literal `...` placeholder from `.env.example` in place of a real generated RSA keypair. Fix is in progress (generating a real keypair); not yet confirmed resolved at the time of this update.
- 375px-viewport responsiveness is unverified by an actual narrow-viewport check.
- "Time-to-first-value under 10 minutes" is structurally plausible (single-screen form) but not measured, and can't be fully measured until Epic 2's Add Position form exists.
- No accessibility audit has been done (focus states, ARIA labelling beyond what shadcn/Base UI provide by default).

**Test evidence**

Backend: `uv run pytest` → **46/46 passed** (10 new: `GET /api/v1/brokers` ×2, `POST /auth/resend-verification` ×3, plus the CORS/dependency changes covered indirectly by the existing suite continuing to pass). Frontend: `npm run build` compiles and type-checks cleanly across all 4 routes. Both dev servers were confirmed live in this session (`/health` 200, `localhost:3000` 200) and a manual CORS preflight (`OPTIONS /auth/register` with `Origin: http://localhost:3000`) returned the expected `access-control-allow-credentials: true` / `access-control-allow-origin: http://localhost:3000` headers. End-to-end browser verification is the user's own manual QA pass, still in progress.

---

## FE-1.2 — Login UI & Session Management

**FR-002 · Priority: Must Have · Status: 🟡 Implemented, manual QA pending (2026-07-26)**

**Developer Action Plan**

```gherkin
Given a registered user is on the login page
When they submit correct credentials
Then they land on the portfolio dashboard, and on any subsequent page load the client checks
     the JWT exp claim and silently calls /auth/refresh if expiry is within 24 hours
```

**Acceptance Criteria**

- [x] Failed login shows the generic error message; after the 5th failure within 10 minutes, the form is disabled with the lockout message and a visible countdown — countdown is driven by the backend's `Retry-After` header, now captured by `lib/api.ts`
- [x] Successful login redirects to `/dashboard`; unverified-but-active users see the persistent verification banner, not a login block
- [x] On receiving a 401 from any API call, the client redirects to `/login` with "Your session has expired. Please log in again." and returns the user to their last-viewed page after re-authentication — implemented as a global handler in `apiFetch`, with an explicit carve-out so `invalid_credentials` (a normal login-form error) never triggers it; see Deviation 2
- [x] Silent refresh is invisible to the user — no interruption to an active session within the 7-day window — implemented as a 15-minute interval check + a window-focus check while `status === "authenticated"`, not a check on every render (see Deviation 1 for why "check the exp claim" couldn't be implemented literally)

**Definition of Done**

- [ ] E2E test: session expiry mid-use triggers redirect and post-login return-to-page behavior — **not automated** (no frontend test tooling exists yet, same gap as FE-1.1); manually reasoned through but not run in a browser this session
- [x] No JWT or session data read/written via `document.cookie` — confirmed by code inspection; the only client-side session state is `AuthProvider`'s in-memory `user`/`expiresAt`, never persisted

**Dependencies & Integrations**

- BE-1.2 login/refresh endpoints — used as-is, no backend changes needed this story (first FE story where that's true)
- ~~`SubscriptionGate` component (Epic 7)~~ — built `AuthGate` instead: the auth-only half of what `SubscriptionGate` will eventually be. Epic 7 extends it with trial/subscription-status checks; doesn't replace it.

**Technical Constraints**

- All authenticated API calls go through the shared `lib/api.ts` wrapper — extended, not duplicated: the global 401 handling and `Retry-After` capture live there once, used by every caller

---

### Implementation Record — FE-1.2

**What was actually built**

- `lib/api.ts` — extended `ApiError` to capture the `Retry-After` response header (`retryAfterSeconds`), and added a global handler: any 401 whose error code is `invalid_token`/`token_expired`/`token_revoked` (i.e. the session itself is dead, not a login-form rejection) triggers `window.location.href` to `/login?redirect=<current path>&reason=session_expired`. A `suppressAuthRedirect` option lets specific calls opt out (needed for the auth bootstrap check — see Deviation 2).
- `lib/auth-context.tsx` (new) — `AuthProvider`/`useAuth()`, replacing FE-1.1's `useCurrentUser` stub hook (deleted). Holds `user`/`status` in React state and `expiresAt` in a ref; exposes `register()`, `login()`, `logout()`. Bootstraps once per full page load via `POST /auth/refresh` (suppressed redirect), then keeps the session alive via a 15-minute interval + window-focus check that silently refreshes once within 24h of the stored `expires_at`.
- `components/auth/AuthGate.tsx` (new) — auth-only route guard: shows a loading state while `status === "loading"`, redirects to `/login?redirect=...` when `unauthenticated`, renders children when `authenticated`.
- `components/auth/LoginForm.tsx` (new) — real login form: calls `useAuth().login()`, shows the generic `invalid_credentials` message inline, starts a live countdown from `retryAfterSeconds` and disables the form on `account_locked`/`rate_limit_exceeded`, redirects to the `redirect` query param (falling back to `/dashboard`) on success, and shows the "Your session has expired" banner when landed on via the global 401 handler's `reason=session_expired`.
- `app/login/page.tsx` — replaced the FE-1.1 visual placeholder with `LoginForm`, wrapped in `<Suspense>` (required by Next.js for any component calling `useSearchParams` on a statically-generated page).
- `app/dashboard/page.tsx` — replaced the ad-hoc inline auth check with `AuthGate` + `useAuth()`; added a working "Log out" action (not explicitly required by this story's AC, but there was previously no way to exercise `POST /auth/logout` from the UI at all).
- `app/layout.tsx` — wraps the app in `AuthProvider`.
- **A real bug caught and fixed before this was considered done:** `RegisterForm` originally called `apiFetch("/auth/register", ...)` directly, bypassing the new `AuthProvider` entirely. Since the root layout (and `AuthProvider` with it) doesn't remount on client-side navigation, `AuthProvider`'s one-time bootstrap check had already run *before* the user registered — so immediately after a successful registration, `router.push("/dashboard")` would land on `AuthGate` still holding a stale `unauthenticated` status from before the account existed, bouncing the freshly-registered user straight back to `/login`. Fixed by adding `register()` to `AuthProvider` (mirroring `login()`) and updating `RegisterForm` to call it, so the registration response feeds the same shared session state instead of bypassing it. This was caught by re-reasoning through the exact request/render sequence, not by running it in a browser — worth an explicit manual check.

**Deviations from this story's spec**

1. **"Checks the JWT exp claim" is not literally implementable, and isn't literally implemented.** The session cookie is HTTP-only by design (AC explicitly forbids touching `document.cookie`), so the frontend can never read the JWT's `exp` claim directly. What's actually implemented: `AuthProvider` remembers `expires_at` from the last successful login/register/refresh response (in a ref, not persisted), and a 15-minute interval plus a window-focus listener check that value against `Date.now()`, refreshing when within 24h. This satisfies the AC's intent (proactive, invisible refresh well before expiry) without being able to satisfy its literal wording.
2. **The auth bootstrap check needed an explicit escape hatch from the global 401 handler.** Without `suppressAuthRedirect`, `AuthProvider`'s very first "am I logged in?" check on every public page (landing, register, login) would 401 for any first-time visitor and immediately redirect them to `/login` — even though "not logged in yet" on a public page is completely normal, not a session-expired event. The escape hatch exists specifically so EX-010 (genuine mid-session expiry) and "never been logged in" (every anonymous visit) are handled differently, even though both are technically a 401 from the same endpoint.
3. **No dedicated `GET /auth/me` still means the bootstrap check calls the mutating `/auth/refresh` endpoint**, same stand-in noted in FE-1.1's record — now used more deliberately (once per page load, plus the interval/focus checks), but still not the endpoint the architecture doc would presumably specify if it addressed this gap directly.
4. **Logout UI was added even though not in this story's AC.** There was no way to exercise `POST /auth/logout` from the browser at all before this — added a minimal "Log out" text button to the dashboard stub so the flow is actually testable end to end, not just by API tests.

**Known gaps / not yet verified**

- **No automated tests exist for any of this** — same tooling gap as FE-1.1 (no Vitest/RTL/Playwright set up). The lockout countdown, the 401-redirect-and-return-to-page flow, and the silent-refresh interval are all reasoned through carefully but not exercised in a real browser this session.
- The "return to last page after re-authentication" mechanism only has `/dashboard` as a real protected destination to prove it against right now — the general `redirect` query-param mechanism is built to extend correctly as more protected routes exist (Epic 2+), but that's not yet demonstrated with a second route.
- `AuthGate`'s loading state is a bare "Loading…" string, not styled to the design — acceptable for a stub, worth revisiting once Epic 4's real dashboard exists.

**Test evidence**

`npm run build` compiles and type-checks cleanly across all routes, including the two new `useSearchParams`-dependent pages (`/login`, `/dashboard`) that require the `<Suspense>` boundaries Next.js enforces for static generation. No backend changes were needed for this story — BE-1.2's existing 46-test suite (unchanged) already covers the endpoints this story consumes. No live browser verification was performed this session (backend/frontend dev servers were left untouched, following the port-conflict friction earlier in this thread) — this is the user's manual QA pass to do.

---

## FE-1.3 — Forgot Password / Reset Password UI

**FR-017 · Priority: Must Have · Status: 🟡 Implemented, manual QA pending (2026-07-26)**

**Developer Action Plan**

```gherkin
Given a user has forgotten their password
When they submit their email on the "Forgot Password" page
Then they see "If an account with that email exists, a reset link has been sent." and,
     upon clicking a valid emailed link, are shown a "Set New Password" form
```

**Acceptance Criteria**

- [x] Identical confirmation message shown regardless of account existence — the frontend never branches on the backend's response at all here; whatever 200 comes back is shown as the "sent" state, matching the backend's own no-enumeration guarantee
- [x] Expired-token and already-used-token states render distinct, actionable messages — implemented as one error-card UI pattern displaying the backend's own message text directly (see Deviation 3 — the design only mocked one error variant)
- [x] On successful reset, user is redirected to `/login` with "Password updated successfully. Please log in." — no auto-login; the reset endpoint never sets a cookie, so there's nothing to accidentally auto-login with

**Definition of Done**

- [ ] All three Workflow 8 alternative flows (expired, already used, happy path) covered by component tests — **not automated**, same frontend-tooling gap as FE-1.1/1.2

**Dependencies & Integrations**

- BE-1.3 — used as-is; no backend changes needed for this story

**Technical Constraints**

- Standard form validation using the shared password rules from VR-002 — plus a new live rules checklist (`PasswordRulesChecklist`), added because the design added one to this screen specifically (not present on the register screen)

---

### Implementation Record — FE-1.3

**Design source:** the user updated the same Claude Design project used for FE-1.1 to add two new screens (`isForgot`/`isReset` state flags, not present when FE-1.1 was built) — re-fetched and read fully via DesignSync before implementing.

**What was actually built**

- `components/auth/ForgotPasswordForm.tsx` (new) — email input → `POST /auth/password-reset-request` → replaces the form with a "Reset link sent" confirmation panel (tips box, "Use a different email", "Resend email" with a cooldown). A 429 (rate-limited) response is shown as an inline amber warning using the real `Retry-After` value from `lib/api.ts` (built in FE-1.2) rather than a guessed duration.
- `components/auth/ResetPasswordForm.tsx` (new) — reads `token` from the URL; new-password + confirm fields with `PasswordStrengthMeter` (reused from FE-1.1) and the new `PasswordRulesChecklist`; three render states (form / error / done).
- `components/auth/PasswordRulesChecklist.tsx` (new) + `lib/validation.ts::passwordRuleChecks()` (new) — the live 3-row checklist the design added to this screen, using our actual VR-002 rules (see Deviation 2).
- `app/forgot-password/page.tsx`, `app/reset-password/page.tsx` (new) — the latter wrapped in `<Suspense>` for the same `useSearchParams`-on-a-static-page reason as `/login`/`/dashboard` in FE-1.2.
- `components/auth/LoginForm.tsx` — added a second, visually distinct banner (green/success, dismissible) for `?reset=success`, alongside the existing blue session-expired banner from FE-1.2 — matches the design's `loginBanner` treatment exactly.

**Deviations from the design (deliberate adaptations, not oversights)**

1. **No per-token "expired" screen shown before submission.** The design models `rpStage: 'expired'` as a state the mock can jump straight into. There is no backend endpoint to check a token's validity without consuming it — the only way to find out is to actually submit a new password and see what comes back. So the real implementation always shows the form first; the error card only appears after a real 400 from `POST /auth/password-reset`. A missing `token` query param entirely is the one case caught before submission, since that's unambiguous without calling the backend at all.
2. **Password rules checklist uses our real VR-002, not the design's rules.** The design's checklist checks "upper and lower case letters" and "a number or symbol" — neither matches what the backend (or `lib/validation.ts`) actually enforces (one uppercase letter, one digit, VR-002). Showing the design's rules verbatim would have displayed requirements that aren't real, or missed ones that are. `passwordRuleChecks()` reflects the actual three checks.
3. **One error-card pattern covers all three backend error variants, not just "expired."** The design only mocked the expired-link case. Since BE-1.3's `_consume_pending_token` returns a distinct *message* for not-found/expired/already-used but the same `invalid_token` *code* for all three, the real implementation just displays `err.message` directly inside the design's error-card visual pattern — satisfying "distinct, actionable messages" (the distinctness comes from the backend's own text) without needing three separate hand-built screens.
4. **No email address shown anywhere on the reset-password screen.** The design shows "Resetting the password for {email}" and later "Your new password is active for {email}" — but there is no endpoint that tells the frontend which account a reset token belongs to (by design — the token is opaque, and BE-1.3 deliberately never confirms account existence). Both lines were reworded to be account-agnostic ("Choose a strong new password for your account.", "Your new password is now active.").
5. **Removed the design's "a confirmation email was sent" bullet from the success screen.** BE-1.3 does not send a confirmation email after a successful reset — only an audit_log entry (`PASSWORD_CHANGED`). Keeping that line would have promised something the backend doesn't do. The "Contact support" line was kept since it's accurate regardless.
6. **The design's live "58 minutes remaining" countdown was replaced with a static statement.** There's no token-introspection endpoint to know the actual remaining time, so the info banner states the fixed 1-hour policy and the sessions-invalidated behavior (BR-019) instead of a countdown the frontend can't actually compute.
7. **The design's "Open the reset link (demo) →" button was not built.** It's a prototype-only convenience for skipping the real email step; production users get an actual email with the real link, so this has no real-app equivalent.

**Known gaps / not yet verified**

- No automated tests exist for either form (same tooling gap as every FE story so far).
- No live browser verification was performed this session — consistent with FE-1.2, no dev servers were started this time either. `npm run build` is clean across all 10 routes (2 new), and no new backend behavior was introduced (BE-1.3's existing 46-test suite already covers everything both forms call), but the actual rendered result — the live rules checklist ticking in real time, the countdown timers, the error-card copy for each of the three backend messages — is still the user's manual QA pass to do.

**Test evidence**

`npm run build` compiles and type-checks cleanly across all 10 routes including the 2 new pages. No backend changes were required or made for this story.

---

# Epic 2 — Portfolio: Positions & Lots

## BE-2.1 — Add Position (First Lot) with Server-Side Fee Calculation

**FR-003 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given an authenticated user with an active (trial or paid) account
When they POST stock_code, shares, purchase_price, purchase_date, and broker_id to
     /api/v1/portfolio/positions
Then the server calculates initial_amount, brokerage_fee, clearing_fee, stamp_duty, and
     all_in_cost using Decimal arithmetic, persists a Lot and a Position, and returns
     the position with its computed fee breakdown
```

**Acceptance Criteria**

- [x] Fee engine implements BR-001–BR-007 exactly: `brokerage = MAX(initial_amount × rate, minimum_fee)` for percentage brokers, flat fee otherwise (BR-001/002); brokerage applied per lot, not per position (BR-003); `clearing_fee = initial_amount × 0.0003`, capped at RM1,000/contract (BR-005); `stamp_duty = ROUNDUP(initial_amount / 1000, 0)`, RM1 minimum (BR-006); `all_in_cost` = sum of all four components (BR-007)
- [x] Rounding follows BR-025 exactly: each fee component individually rounded half-away-from-zero to 2dp before summing — verified against the worked boundary examples (RM12.575 → RM12.58)
- [x] Reference test cases from BAS US-003 pass numerically: Maybank Investment 5,000 CIMB @ RM8.38 → all-in RM41,996.47; MooMoo flat fee → all-in RM41,957.57; brokerage-minimum case (FM 7210, 5,000 @ RM0.60) → all-in RM3,011.90
- [x] VR-004 (shares ≥1, integer, ≤99,999,999), VR-005 (price >0, ≤4dp), VR-006 (purchase_date not future) enforced with the exact BAS error copy. VR-003's reference-list check is deferred to Epic 9 (see Implementation Record, Deviation 2) — only "required, non-empty" is enforced for now.
- [x] EC-001: adding a stock code that already exists as an active position is treated as "Add Lot", not a duplicate Position — with the notification copy from BAS
- [x] EC-002: zero-brokerage (custom broker rate=0) is valid, not an error
- [x] EC-004: purchase date on a non-trading day is accepted with a soft warning, not blocked (weekend detection only — see Implementation Record, Deviation 3)
- [x] `audit_log` entry `LOT_CREATED` written in the same transaction

**Definition of Done**

- [x] `portfolio/calculator.py` is the single authoritative fee-calculation module — every other code path (Add Lot, Edit, Sell Calculator, CSV import) calls into it, never duplicates the formula (architecture P-003, P-005, G-001)
- [x] Unit test suite covers every BR-001–BR-007 case plus the P1 test matrix from BAS §14 (brokerage min/percentage/flat, clearing fee cap, stamp duty boundary)
- [x] No `float`/`double` anywhere in the calculation path — `Decimal` only (R-003 mitigation); verified manually via grep — no mypy/ruff CI gate exists in this project yet (see Implementation Record, Known gaps)
- [x] Response schema matches `03-openapi-specification.md` `/api/v1/portfolio/positions` (all monetary fields `type: string`, per API security review FC-001–007), plus an additive `warnings` field and `stock_name` on the request (see Implementation Record, Deviations 1 and 5)

**Dependencies & Integrations**

- `BrokerConfig` and `Stock` reference tables must be seeded (Epic 9)
- `system_config` for stamp duty rate and clearing fee percentage (BR-015 configurability)

**Technical Constraints**

- All monetary columns are PostgreSQL `NUMERIC` (never `FLOAT`); `purchase_price` is `NUMERIC(12,4)`, fee/cost fields are `NUMERIC(14,2)` (architecture §12.3)
- The server is the sole source of truth for stored fee values — any client-side fee preview is display-only and must never be trusted or persisted (P-003)

---

### Implementation Record — BE-2.1

**What was actually built**

- `app/portfolio/calculator.py` (new) — the single authoritative fee engine: `compute_initial_amount`, `compute_brokerage_fee` (BR-001/BR-002/BR-003), `compute_clearing_fee` (BR-005, RM1,000 cap), `compute_stamp_duty` (BR-006, ROUNDUP-to-thousand with RM1 minimum), `calculate_lot_fees` (BR-007), `round_myr` (BR-025, half-away-from-zero to 2dp), and `is_non_trading_day` (EC-004, weekend check only — see Deviation 3). Decimal only throughout; verified by grep that no `float`/`double` appears anywhere in the module (no mypy/ruff config exists yet in this project to automate that check — see Known gaps).
- `app/portfolio/models.py` — added `Position` and `Lot` ORM models (physical schema §3.6-3.7).
- `alembic/versions/0005_create_positions_and_lots.py` (new) — creates `positions`/`lots`, and extends `audit_log`'s `action`/`entity_type` CHECK constraints to add `LOT_CREATED`/`Lot`. Verified both upgrade and downgrade against the real Postgres container.
- `app/admin/models.py` — extended `AUDIT_LOG_ACTIONS` with `LOT_CREATED`, `AUDIT_LOG_ENTITY_TYPES` with `Lot`.
- `app/portfolio/schemas.py` — `CreatePositionRequest` (with custom `field_validator`s reproducing VR-004/005/006's exact error copy), `LotResponse`, `PositionResponse`.
- `app/portfolio/service.py` — `create_position` (validates broker, computes fees, handles the EC-001 duplicate-stock redirect into an add-lot instead of a new Position, writes the `LOT_CREATED` audit entry), `get_active_position_by_stock`, `get_position_lots`, `position_aggregates` (BR-010/BR-011, computed at query time — never stored on the row, per architecture ADR-004), `get_portfolio_for_user`.
- `app/portfolio/router.py` — `POST /api/v1/portfolio/positions`, authenticated, rate-limited 60/min.
- The `create_position`/`position_aggregates` functions are written to be reused as-is by BE-2.2's dedicated Add-Lot endpoint next story (BE-2.2's DoD explicitly requires sharing `calculator.py` — this extends that sharing to the aggregate/redirect logic too).

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **`stock_name` is accepted from the client**, even though `CreatePositionRequest` in `03-openapi-specification.md` omits it. The physical schema (§3.6) documents `positions.stock_name` as "denormalised for display; entered by user at position creation," and VR-003 requires it as mandatory — the OpenAPI schema appears to simply have missed the field. Added it as a required string (max 100 chars).
2. **VR-003's "must be a valid Bursa-listed security" check is not enforced.** BE-2.1's own Dependencies section states the `Stock` reference table is seeded in Epic 9, which doesn't exist yet — so only "required, non-empty" is checked on `stock_code` for now, with no FK constraint from `positions.stock_code` to a `stocks` table. Revisit when Epic 9 lands.
3. **EC-004's non-trading-day check only detects weekends**, not Malaysian public/Bursa holidays — that requires a maintained holiday-calendar data source that doesn't exist in the schema yet. The AC's intent (soft warning, never blocking) is satisfied for the weekend case; holiday coverage is a gap, not a design choice.
4. **`system_config` (BR-015's externally-configurable stamp duty rate) doesn't exist**, so the stamp duty rate (RM1/RM1,000) and clearing-fee cap (RM1,000) are hardcoded constants in `calculator.py` with a docstring flagging them for revisit once fee-config administration is built.
5. **Added an additive `warnings: list[str]` field to `PositionResponse`**, not present in the OpenAPI spec, to carry EC-001's "added to existing position" notice and EC-004's non-trading-day notice — purely additive, doesn't remove or change any documented field.
6. **`PositionResponse` fields that depend on unbuilt epics are held at their documented-nullable/zero defaults**: `dividend_tranches: []`, `total_dividend_income_ytd: "0.00"` (Epic 3), `current_price`/`price_source`/`price_last_refreshed_at`/`current_market_value`/`unrealised_pnl: null` (the price-feed epic — all five are nullable in the spec for exactly this "no price ever retrieved" case, BAS EC-005).

**Bug caught during live verification (fixed, not just noted)**

- The first live-Postgres smoke test surfaced a real bug: `blended_purchase_price` was returned as an unrounded repeating decimal (e.g. `"8.557142857142857142857142857"`) from a plain Decimal division with no quantization. Fixed by rounding to 4dp (BR-026's price-per-share precision, matching `purchase_price`'s own column precision) in `position_aggregates`. Added a dedicated multi-lot test asserting the exact 4dp value to prevent regression.

**Test evidence**

- `uv run pytest`: 75/75 passing (46 pre-existing + 19 new calculator unit tests covering every BR-001–007/025 worked example and rounding boundary + 10 new endpoint integration tests covering the happy path, auth requirement, VR-004/005/006 validation copy, unknown-broker handling, EC-001 duplicate-stock redirect, EC-002 zero-brokerage, EC-004 weekend warning, and the `LOT_CREATED` audit log entry).
- Migration 0005 applied and rolled back cleanly against the real Postgres container (`alembic upgrade head` / `downgrade -1` / `upgrade head`).
- Live smoke test against the real backend + Postgres: registered a user, created a position, added a second lot to the same stock code (confirmed same position ID, 2 lots, aggregated totals, EC-001 notice text), triggered validation errors (zero shares, future date, 5dp price), triggered the EC-004 weekend warning, and confirmed 401 without a session cookie — all matched expectations after the `blended_purchase_price` fix above.

**Known gaps / not yet verified**

- No mypy/ruff tooling exists in this project yet to automate the DoD's "lint check flags any float" requirement — verified manually via `grep` instead. Worth adding real CI linting at some point, but out of scope for this story.
- No CSV import or Sell Calculator exist yet to exercise `calculator.py` from those other call sites (both future epics) — only Add Position exercises it so far.

---

## BE-2.2 — Add Lot to Existing Position

**FR-004 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a Position already exists for a stock in the user's portfolio
When the user POSTs a new lot to /api/v1/portfolio/positions/{id}/lots
Then the server calculates the new lot's fees independently (BR-003: brokerage per
     transaction), creates the Lot, and recalculates the position's aggregate values
     (total_shares, total_all_in_cost, blended_purchase_price) — WITHOUT touching any
     existing DividendTranche.total_amount
```

**Acceptance Criteria**

- [x] `total_shares` = SUM(shares) across non-deleted lots (BR-010); `total_all_in_cost` = SUM(all_in_cost) across non-deleted lots (BR-011); `blended_purchase_price` = total_initial_amount / total_shares
- [x] **P0 critical invariant (partial):** verified that adding a Lot never mutates any other Lot's own stored fields. The full invariant (that `DividendTranche.total_amount`/`qualifying_shares` also stay untouched) cannot be tested yet — `DividendTranche` doesn't exist until Epic 3 — see Implementation Record for the precursor test and the note to extend it in BE-3.1.
- [x] Numeric example from BAS US-004 passes: adding a 2,000-share lot at RM9.00 to an existing 5,000-share CIMB position brings total shares to 7,000, total all-in cost to RM60,037.87 (the dividend-tranche half of this AC is deferred to BE-3.1 per above)
- [x] Broker for the new lot is overridable per lot (BR-003). "Defaults to the position's existing default broker" is a frontend pre-fill concern (FE-2.2) — the backend has no notion of a position-level default broker; `broker_id` is simply required per request, same as BE-2.1.

**Definition of Done**

- [x] A precursor regression test exists now (`test_add_lot_does_not_mutate_existing_lot_ec022_precursor`); the full EC-022 test naming/scope from BAS §14 applies once `DividendTranche` exists (BE-3.1) — flagged there as P0/blocking.
- [x] Position aggregates are computed at query time, never stored redundantly on the Position row (architecture ADR-004, §12.3 HIGH-R-006) — reuses BE-2.1's `position_aggregates`.

**Dependencies & Integrations**

- Shares `portfolio/calculator.py` with BE-2.1

**Technical Constraints**

- Same Decimal/NUMERIC constraints as BE-2.1

---

### Implementation Record — BE-2.2

**What was actually built**

- `app/portfolio/service.py` — `add_lot_to_position` (the new endpoint's core logic), `get_owned_active_position` (ownership check returning 404 for missing/foreign/soft-deleted positions), `_insert_lot` and `_purchase_date_warnings` (both extracted from BE-2.1's `create_position` so the Lot-construction/audit-logging/EC-004-warning logic has exactly one implementation, now shared by both the EC-001 redirect path in BE-2.1 and this story's dedicated endpoint).
- `app/portfolio/schemas.py` — `CreateLotRequest`; refactored the VR-004/005/006 field validators out of `CreatePositionRequest` into shared module-level functions (`_check_shares`, `_check_purchase_price`, `_check_purchase_date`) so `CreateLotRequest` reuses the exact same validation, not a re-implementation. Added the same additive `warnings` field to `LotResponse` that `PositionResponse` already has.
- `app/portfolio/router.py` — `POST /api/v1/portfolio/positions/{position_id}/lots`, authenticated, rate-limited 60/min, returns `LotResponse`.

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **The P0 EC-022/BR-009 regression test cannot be fully written yet.** Its entire premise — that adding a Lot must not alter a previously-stored `DividendTranche.total_amount` — requires `DividendTranche` to exist, and it doesn't until Epic 3 (BE-3.1). Wrote a precursor test now (`test_add_lot_does_not_mutate_existing_lot_ec022_precursor`) that asserts the half of the invariant that *is* testable today (another Lot's own stored fields never change), and left an explicit note that BE-3.1 must extend this into the real, full invariant test the spec describes. This is flagged as a known gap, not silently satisfied.
2. **No GET position-detail endpoint was built.** The story's AC talks about aggregates "recalculating" after an add-lot, but the documented response for this endpoint (`03-openapi-specification.md`) is `LotResponse`, not `PositionResponse` — the new totals are only ever visible on a subsequent read. No Epic 2 backend story actually specifies a `GET /positions/{id}` endpoint (it only appears as a path-block sibling of BE-2.3's PATCH/BE-2.4's DELETE in the OpenAPI doc), so it wasn't built here to avoid scope creep. This is a real backlog gap: FE-2.2's "position detail page" and its SWR revalidation will need this endpoint to exist, so it must land before or alongside FE-2.2 — flagging that now rather than discovering it mid-frontend-story.
3. **"Broker defaults to the position's existing default broker"** has no backend equivalent — positions don't store a default broker (only individual Lots do). Implemented as a plain required `broker_id` on the request; the "defaults to" behavior is a UI pre-fill decision that belongs entirely to FE-2.2.

**Test evidence**

- `uv run pytest`: 85/85 passing (75 pre-existing + 10 new: BAS US-004 numeric match, aggregate-visible-on-next-read, per-lot broker override, auth requirement, 404 for nonexistent/foreign/soft-deleted positions, EC-004 weekend warning, `LOT_CREATED` audit entry, and the EC-022 precursor above).
- Live smoke test against the real backend + Postgres: created a position, added a lot with a *different* broker than the position's first lot (confirmed independent per-lot fee calculation), confirmed 404 for a nonexistent position and 401 unauthenticated.
- Note: this session's smoke test also surfaced an environment quirk worth recording — `uv run fastapi dev` crashed on startup with a `UnicodeEncodeError` from `rich`'s console renderer on this Windows/cp1252 terminal (unrelated to any app code); setting `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8` before the command fixed it. Not an application bug, just a note for future manual runs in this environment.

**Known gaps / not yet verified**

- `GET /api/v1/portfolio/positions/{id}` doesn't exist yet — needed before FE-2.2 can build a position detail page (see Deviation 2).
- The full EC-022/BR-009 dividend-invariant test is deferred to BE-3.1 (see Deviation 1).

---

## BE-2.3 — Edit Position / Lot with Optimistic Locking

**FR-005 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a Lot exists with version=1
When the user PATCHes shares, purchase_price, purchase_date, and/or broker_id, submitting
     version=1
Then the server recalculates all fee fields, writes the previous values to audit_log,
     increments version to 2, and returns the updated Lot — but if another session had
     already updated the Lot to version=2, the request is rejected with 409
```

**Acceptance Criteria**

- [ ] `UPDATE lots SET ..., version = version + 1 WHERE id = ? AND version = <submitted_version>`; zero rows affected → HTTP 409 `{"error": "version_conflict", "message": "This record was modified by another session. Please refresh and try again."}` (EX-008, architecture §15.4)
- [ ] Editing a lot's share count does **not** alter any existing `DividendTranche.total_amount` (EC-015) — the dashboard/API response includes a notice that dividend records were not changed
- [ ] `PATCH /api/v1/portfolio/positions/{id}` covers metadata only (category_tag, notes); lot financial fields are edited via `PATCH /api/v1/portfolio/positions/{id}/lots/{lot_id}`
- [ ] Accessing or editing a position/lot owned by another user returns 404, never 403 or a differentiated error (BAS §9 URL-level enforcement; API security review AA-001–009)
- [ ] VR-004/005/006 re-validated on edit exactly as on create
- [ ] `audit_log` entry `LOT_UPDATED` (or `POSITION_UPDATED` for metadata edits) records previous and new values

**Definition of Done**

- [ ] Concurrent-edit integration test: two simultaneous PATCH requests against the same `version` — exactly one succeeds, the other receives 409
- [ ] EC-015 regression test confirms dividend totals are untouched by a lot edit

**Dependencies & Integrations**

- BE-2.1 calculator, BE-3.x dividend endpoints (for the invariant check)

**Technical Constraints**

- `version INTEGER` column required on `Lot` (already in physical schema, architecture §8.3/§12.1)

---

## BE-2.4 — Delete Position (Cascading Soft-Delete)

**FR-006 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a Position has 2 lots and 3 dividend tranches
When the user DELETEs /api/v1/portfolio/positions/{id} after confirming
Then the Position, its Lots, and its DividendTranches are all soft-deleted
     (is_deleted=true, deleted_at=now()), and portfolio summary totals are recalculated
     to exclude them
```

**Acceptance Criteria**

- [ ] Soft-delete only — no physical row deletion at this layer (A-010); records remain for audit/PDPA export until account-level hard-delete
- [ ] Cascade covers all active Lots and DividendTranches under the Position in a single transaction
- [ ] `audit_log` entry `POSITION_DELETED` recorded (architecture §14.7)
- [ ] EC-006: attempting to log a dividend against a soft-deleted position (bypassing the UI) returns 404
- [ ] EC-001 exception path: re-adding the same stock code after a soft-delete creates a **new** Position (the old soft-deleted one is not resurrected)

**Definition of Done**

- [ ] Deletion is idempotent and fully reversible only via direct DB access (no "undo" UI at V1, consistent with BR — deletion confirmation copy is explicit that it "cannot be undone")

**Dependencies & Integrations**

- None beyond BE-2.1–2.3

**Technical Constraints**

- Soft-deleted rows must be excluded from every dashboard/aggregate query via `WHERE is_deleted = false` — missing this filter anywhere is a correctness bug, not just a display issue (it would corrupt yield/cost totals)

---

## FE-2.1 — Add Position Form with Live Fee Preview

**FR-003 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a user is on the "Add Position" form
When they enter stock, shares, price, date, and broker
Then a live, client-side fee breakdown (brokerage / clearing / stamp duty / all-in cost)
     renders instantly using decimal.js, matching what the server will compute and store
```

**Acceptance Criteria**

- [ ] Client-side preview uses `decimal.js` — never native JS floating point — to avoid a preview/actual mismatch that would undermine user trust (PRD Principle 1: Accuracy Before Features, Principle 4: Trust Through Transparency)
- [ ] Every summary number (all-in cost) has a visible drill-down to its fee components (Principle 4 — no black-box numbers)
- [ ] Stock autocomplete calls `GET /api/v1/stocks` (60-minute TTL cache per architecture §12.4) and falls back to free-text entry with server-side validation on submit (R-009 mitigation)
- [ ] Inline errors match VR-003/004/005/006 copy exactly
- [ ] EC-001 duplicate-stock flow: submitting a stock already in the portfolio shows the "added to existing position" notice instead of erroring

**Definition of Done**

- [ ] Client preview values verified against server response in an integration test — any divergence is a P0 bug given the product's core "provably accurate" positioning

**Dependencies & Integrations**

- BE-2.1, `GET /api/v1/stocks`, `GET /api/v1/brokers`

**Technical Constraints**

- Client fee preview is **display-only** — the form always submits raw inputs (shares, price, broker) and lets the server compute and persist authoritative fee values (P-003); the client must never submit its own computed `all_in_cost`

---

## FE-2.2 — Add Lot to Existing Position UI

**FR-004 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a user is viewing an existing position's detail page
When they click "Add Lot" and submit shares/price/date/broker
Then the position detail view updates to show the new blended cost basis and total
     shares, and a confirmation clarifies that historical dividend records are unaffected
```

**Acceptance Criteria**

- [ ] Broker field pre-fills to the position's existing default but is editable per lot (BR-003 — brokerage is per-transaction, so a different broker per lot is a valid scenario)
- [ ] Blended purchase price and updated all-in cost render immediately after submission (SWR revalidation)

**Definition of Done**

- [ ] Verified against BAS US-004 acceptance criteria numerically in a component/integration test

**Dependencies & Integrations**

- BE-2.2

**Technical Constraints**

- None beyond FE-2.1's shared fee-preview components

---

## FE-2.3 — Edit Position / Lot UI with Conflict Handling

**FR-005 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a user opens the edit form for a lot
When they submit changes and the server returns a 409 version conflict
Then the UI shows "This record was updated by another session. Please refresh the page
     to see the latest values before making changes." and reloads current values on refresh
```

**Acceptance Criteria**

- [ ] `version` is submitted transparently with every PATCH (not user-visible/editable)
- [ ] A dashboard/position notice appears after a share-count edit: "Position updated. Dividend records were not changed." (EC-015)
- [ ] Accessing another user's position via a crafted URL renders a generic 404 page — no information disclosure

**Definition of Done**

- [ ] EX-008 concurrent-edit scenario manually tested with two browser sessions

**Dependencies & Integrations**

- BE-2.3

**Technical Constraints**

- None additional

---

## FE-2.4 — Delete Position Confirmation Flow

**FR-006 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a user clicks "Delete Position" on a position with 2 lots and 3 dividend tranches
When the confirmation dialog appears
Then it reads "This will delete [Stock Name] and all 2 lots and 3 dividend records.
     This cannot be undone." and only proceeds on explicit confirmation
```

**Acceptance Criteria**

- [ ] Dialog dynamically interpolates the actual lot/tranche counts for the specific position
- [ ] Cancelling leaves the position untouched and returns to the dashboard
- [ ] Portfolio summary (total cost, blended yield) visibly updates immediately after confirmed deletion

**Definition of Done**

- [ ] Reusable `ConfirmDialog` component (already scoped in architecture's frontend structure, §7.2) used consistently for this and all other destructive actions (dividend delete, account delete)

**Dependencies & Integrations**

- BE-2.4

**Technical Constraints**

- None additional

---

# Epic 3 — Dividend Tracking

## BE-3.1 — Log Dividend Tranche (qualifying_shares Invariant)

**FR-009 · Priority: Must Have — P0 CRITICAL**

> This story implements the single most safety-critical business rule in the product (BR-009/BR-027, CI-001). The Excel predecessor's core defect — dividend totals silently inflating when new shares are purchased — must not be reproduced. Do not begin this story without reading BR-009 and BR-027 in full.

**Developer Action Plan**

```gherkin
Given a position has 5,000 total shares and no dividends logged
When the user POSTs tranche_label="1st", per_share_amount=0.20, payment_date, and either
     accepts the default qualifying_shares=5000 or overrides it
Then the server stores qualifying_shares and computes total_amount = per_share_amount ×
     qualifying_shares AT THIS MOMENT, and total_amount will NEVER be recomputed from a
     future position_total_shares value — only an explicit edit to this tranche changes it
```

**Acceptance Criteria**

- [ ] `qualifying_shares` defaults to current `position_total_shares` at logging time but is user-overridable, bounded `1 ≤ qualifying_shares ≤ position_total_shares` at time of entry (VR-011)
- [ ] `total_amount = per_share_amount × qualifying_shares`, rounded to 2dp (BR-025), is a **stored** column — never a computed/derived value at read time (BR-009, architecture §12.3 explicitly rules out a stored `yield_percentage` but `total_amount` on `DividendTranche` IS stored deliberately, per BR-009's fix)
- [ ] **P0 regression test (mandatory, cannot be skipped per BAS §14):** logging a 1st tranche (qualifying_shares=5000, total_amount=RM1,000 stored), then adding a new 2,000-share lot, must leave the 1st tranche's `total_amount` at exactly RM1,000.00 — this is EC-022 verbatim
- [ ] BR-014: a position may have at most 8 `DividendTranche` rows per calendar `year`; the 9th attempt is rejected with "Maximum of 8 dividend tranches per year reached for [Stock] ([Year])"
- [ ] VR-008 (per_share_amount >0, ≤6dp), VR-009 (payment_date ≤30 days future), VR-010 (ex_dividend_date ≤ payment_date if present), VR-012 (year 1990–current+1) all enforced
- [ ] Position yield recalculated as `SUM(DividendTranche.total_amount for year=current) / position_total_all_in_cost` (BR-008, BR-012) — using **all-in cost**, never the pre-fee initial amount
- [ ] Portfolio blended yield = `SUM(all positions' income) / SUM(all positions' cost)` — weighted, not an arithmetic average of individual position yields (BR-013)
- [ ] EC-023: when a user deliberately sets qualifying_shares below the current position total, the tranche detail view surfaces both numbers ("5,000 qualifying shares (current total: 7,000)") with no error — this is a valid, intentional state
- [ ] `audit_log` entry `DIVIDEND_CREATED`

**Definition of Done**

- [ ] Unit test: `total_amount` is stored and provably immutable across a subsequent lot-add operation (cross-references BE-2.2's invariant test — these two tests should assert the same fact from both directions)
- [ ] Unit test: yield calculation uses all-in cost, with the explicit negative assertion that it does NOT equal `income / pre_fee_initial_amount` (BAS US-011)
- [ ] Code review checklist item: any PR touching `DividendTranche.total_amount` must be explicitly reviewed against BR-009/BR-027 (architecture P-004)

**Dependencies & Integrations**

- Depends on Position/Lot aggregates from Epic 2 for `position_total_shares` lookup at logging time

**Technical Constraints**

- `per_share_amount` is `NUMERIC(12,6)`; `total_amount` is `NUMERIC(14,2)` (architecture §12.3)
- This is the one field in the entire schema where "derived at query time" (the architecture's general pattern, ADR-004) is deliberately **not** followed — the schema comment on this column must explain why, so a future engineer doesn't "fix" it into a derived value

---

## BE-3.2 — Edit / Delete Dividend Tranche

**FR-010 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a stored tranche has per_share_amount=0.20, qualifying_shares=5000, total_amount=1000.00
When the user PATCHes per_share_amount to 0.22 (submitting the current version)
Then total_amount recalculates to 0.22 × 5000 = 1100.00 using the EXISTING stored
     qualifying_shares — it does not re-read the live position_total_shares
```

**Acceptance Criteria**

- [ ] Editing `per_share_amount` recomputes `total_amount` using the tranche's own stored `qualifying_shares`, never the current position total (BAS US-012)
- [ ] Editing `qualifying_shares` directly recomputes `total_amount` with the new qualifying_shares × the existing `per_share_amount`; still bounded ≤ position_total_shares at time of edit (VR-011 "on edit" clause)
- [ ] Delete is a soft-delete; position/portfolio yield recalculates with the tranche excluded
- [ ] Optimistic locking via `version` column, identical conflict handling to BE-2.3 (EX-008)
- [ ] `audit_log` entries `DIVIDEND_UPDATED` / `DIVIDEND_DELETED` capture previous and new values

**Definition of Done**

- [ ] Both BAS US-012 Gherkin scenarios (edit per_share_amount, edit qualifying_shares) pass as automated tests with the exact numeric expectations

**Dependencies & Integrations**

- BE-3.1

**Technical Constraints**

- Same NUMERIC/Decimal constraints as BE-3.1

---

## BE-3.3 — Dividend Calendar Aggregation

**FR-013 · Priority: Should Have (V1)**

**Developer Action Plan**

```gherkin
Given a portfolio has dividend tranches with various ex_dividend_date and payment_date values
When the client GETs the dividend calendar view
Then entries are returned in ascending chronological order by ex_dividend_date (or
     payment_date if no ex-date), scoped to future dates plus the trailing 30 days
```

**Acceptance Criteria**

- [ ] Each entry includes stock name, tranche label, ex-date, payment date, per_share_amount, and the **stored** total_amount (not re-derived) — display must make clear this reflects the qualifying_shares basis at logging time (FR-013 step 3 fix)
- [ ] Past dates flagged "Paid"; upcoming dates within 7 days flagged for highlighting
- [ ] Empty state (no ex-dates recorded) returns a payload the frontend can render as the guidance message

**Definition of Done**

- [ ] Query correctly filters soft-deleted tranches (`is_deleted=false`)

**Dependencies & Integrations**

- BE-3.1 for the underlying data

**Technical Constraints**

- None beyond standard read-path query performance (indexed on `dividend_tranches(position_id, year, is_deleted)` per architecture §8.3)

---

## FE-3.1 — Log Dividend Tranche Form

**FR-009 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a user opens "Add Dividend" on a position with 5,000 current shares
When the form loads
Then the "Qualifying Shares" field is pre-populated with 5,000 and shows guidance text:
     "This is the number of shares you held before the ex-dividend date. Change this if
     you held fewer shares than your current total."
```

**Acceptance Criteria**

- [ ] Tranche label field suggests the next available label (1st–8th) and blocks submission once 8 are already used for the year, with the exact BAS error copy
- [ ] Qualifying-shares guidance text matches BAS Workflow 4 wording verbatim — this field is the UI's primary defense against the BR-009 class of user error
- [ ] Yield displayed immediately after submission, computed from the response (not client-recomputed) to avoid any drift from the authoritative server value

**Definition of Done**

- [ ] Manual QA pass specifically exercises EC-023 (override qualifying_shares below current total) and confirms the transparent display of both numbers

**Dependencies & Integrations**

- BE-3.1

**Technical Constraints**

- None additional

---

## FE-3.2 — Edit / Delete Dividend Tranche UI

**FR-010 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a user opens a logged tranche for editing
When they change per_share_amount or qualifying_shares
Then the recalculated total_amount and updated yield render after save, and a delete
     action requires the standard confirm-dialog ("Delete this dividend record? This
     cannot be undone.")
```

**Acceptance Criteria**

- [ ] Attempting to set qualifying_shares above the current position total shows: "Qualifying shares cannot exceed the position's current total shares ([N])"
- [ ] Uses the shared `ConfirmDialog` component (consistent with FE-2.4)

**Definition of Done**

- [ ] BAS US-012 error scenario covered

**Dependencies & Integrations**

- BE-3.2

**Technical Constraints**

- None additional

---

## FE-3.3 — Dividend Calendar View

**FR-013 · Priority: Should Have (V1)**

**Developer Action Plan**

```gherkin
Given a user has logged dividends with ex-dates across several positions
When they open the Dividend Calendar tab
Then entries render chronologically with "Paid" badges on past dates and highlighting
     on entries due within 7 days
```

**Acceptance Criteria**

- [ ] Empty state renders: "Add ex-dates when logging dividends to see your payment schedule here."
- [ ] Each entry is legible on a 375px viewport

**Definition of Done**

- [ ] Visual QA against BAS US-017 happy-path and empty-state scenarios

**Dependencies & Integrations**

- BE-3.3

**Technical Constraints**

- None additional

---

# Epic 4 — Dashboard & Sell Calculator

## BE-4.1 — Portfolio Dashboard Aggregate Endpoint

**FR-011 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given an authenticated user with 16 positions, lots, dividends, and price snapshots
When the client GETs /api/v1/portfolio/dashboard
Then the response includes a summary (total all-in cost, total YTD dividend income,
     portfolio blended yield, last price refresh timestamp) plus a per-position array
     with all derived fields, computed fresh at query time, within the 3-second NFR
```

**Acceptance Criteria**

- [ ] Per-position fields: stock name/code, category_tag, total_shares, blended_purchase_price, total_all_in_cost, current_price (with `last_refreshed_at` for staleness), current_market_value, unrealised_pnl, dividend_income_ytd, dividend_yield — matching the Position entity's "derived (runtime) aggregates" table in BAS §7
- [ ] Positions with no dividend tranches show yield as null/"—", not 0% (BAS US-013 alternate scenario)
- [ ] EC-005: positions with no price data show market value/P&L as null/"—", not RM0.00
- [ ] EC-009: zero all-in-cost positions show yield as null with a "cost basis is zero" indicator rather than throwing a division error
- [ ] EC-010: yield >100% is calculated and returned as-is, no error — the frontend may show a soft warning
- [ ] All aggregates computed at query time from stored `Lot`/`DividendTranche` rows — no denormalized/cached aggregate column on `Position` (ADR-004, HIGH-R-006)
- [ ] Response performance: <3 seconds for up to 50 positions (PRD/BAS NFR, load-tested)

**Definition of Done**

- [ ] Load test with 50 positions × 3 lots × 8 tranches confirms the 3-second budget
- [ ] Query uses the indexes specified in architecture §8.3 (`lots(position_id, is_deleted)`, `dividend_tranches(position_id, year, is_deleted)`, `price_snapshots(stock_code, trading_date)`)

**Dependencies & Integrations**

- Epic 2 (positions/lots), Epic 3 (dividends), Epic 5 (price snapshots)

**Technical Constraints**

- All computation in Python `Decimal`; response schema serializes monetary fields as strings, not JSON numbers (API security review FC-001)

---

## BE-4.2 — Sell Scenario Calculator

**FR-012 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a position has 5,000 shares, all-in buy cost RM41,996.47, broker "Maybank Investment"
When the client POSTs to /api/v1/portfolio/positions/{id}/sell-scenario with an optional
     shares_to_sell and broker override
Then the server generates scenario rows at current_price + [0.01…0.05, then 0.10…0.70 in
     0.05 steps], computes net proceeds and profit/loss per row using the same fee engine
     as buy-side, and flags the lowest break-even row
```

**Acceptance Criteria**

- [ ] Sell-side fees use identical broker rules to buy-side (BR-004): `sell_brokerage = MAX(gross × rate, min)` or flat; `sell_clearing = gross × 0.0003`; `sell_stamp_duty = ROUNDUP(gross/1000, 0)`
- [ ] Reference case from BAS US-015/016 passes numerically: CIMB @ RM8.42 → gross RM42,100, net ≈RM42,002.27, P/L ≈+RM5.80, flagged as break-even
- [ ] BR-024/EC — partial sale: buy-cost basis = `(shares_to_sell / total_shares) × total_all_in_cost` (proportional weighted average, explicitly NOT FIFO/LIFO — NG-009)
- [ ] A-006 (⚠ pending confirmation, OQ-005): default sell broker for a multi-lot position with different brokers is the most recently created active lot's broker; user can override without altering stored position data
- [ ] Response always includes the non-dismissable disclosure text: "Calculations are informational only. BursaTrack is not a financial advisor. Settlement on Bursa Malaysia is T+2..." (BR-020) and the general disclaimer (BR-021)
- [ ] EC-009: zero all-in-cost position — profit/loss = net proceeds; yield shown as "—"
- [ ] Calculator results are **not persisted** — stateless computation per request

**Definition of Done**

- [ ] Numeric test suite matches every worked example in BAS BR-004/BR-024 and US-015/016 exactly, to the cent

**Dependencies & Integrations**

- Shares `portfolio/calculator.py` with Epic 2 (BR-004 reuses the exact buy-side fee functions)

**Technical Constraints**

- Same Decimal/NUMERIC discipline as all other calculation endpoints

---

## FE-4.1 — Dashboard UI

**FR-011 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a user logs in
When the dashboard loads
Then the summary header and position table render within 3 seconds, sorted by dividend
     yield descending by default, with re-sortable columns and stale-price indicators
     where applicable
```

**Acceptance Criteria**

- [ ] Sort preference persists across the session (BAS US-014)
- [ ] Stale positions (per `last_refreshed_at` > 28h, architecture §15.1) show a stale icon and the portfolio-level banner text from EX-001/EX-002 when applicable
- [ ] Positions with null yield/market value render "—", never a misleading 0
- [ ] Loads correctly for both trial and paid accounts; trial-expired accounts render the same table in read-only mode (no add/edit/delete affordances) per the Permission Matrix (BAS §9)

**Definition of Done**

- [ ] Manual test with 50 seeded positions confirms sub-3-second perceived load and correct default sort

**Dependencies & Integrations**

- BE-4.1, `SubscriptionGate` component (Epic 7) for the read-only trial-expired state

**Technical Constraints**

- SWR with stale-while-revalidate; revalidates on window focus and after any write mutation elsewhere in the app (architecture §12.4)

---

## FE-4.2 — Sell Scenario Calculator UI

**FR-012 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a user opens the sell calculator for a position
When the scenario table renders
Then the break-even row is visually highlighted, the T+2/disclaimer text is permanently
     visible (not dismissable), and the user can enter a custom price or adjust shares-to-sell
```

**Acceptance Criteria**

- [ ] Disclosure text cannot be dismissed or hidden by the user (BR-020/BR-021 — compliance requirement, not a UX nicety)
- [ ] Custom price entry adds a row computed via the same endpoint, not a separate client-only formula
- [ ] Partial-sale slider/input updates all rows' proportional cost basis live

**Definition of Done**

- [ ] Verified the disclaimer renders on every result state, including custom-price and partial-sale variants

**Dependencies & Integrations**

- BE-4.2

**Technical Constraints**

- None additional

---

# Epic 5 — Pricing & Market Data

## BE-5.1 — Daily Automated Price Refresh Cron

**FR-007 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given it is a Bursa Malaysia trading day
When the Render cron job refresh_prices.py fires at 09:30 UTC (5:30 PM MYT)
Then the job fetches yfinance prices for every unique stock_code across active
     (non-deleted) lots, in parallel with a concurrency limit, and UPSERTs
     PriceSnapshot rows with source="automated"
```

**Acceptance Criteria**

- [ ] Trading-day check against a `system_config`-stored Bursa holiday calendar (JSON array); job exits cleanly with a Sentry check-in on non-trading days, without touching `last_refreshed_at`
- [ ] Process lock via `system_config.price_refresh_lock`: a run already in progress within the last 2 hours prevents a duplicate run (HIGH-R-004)
- [ ] Wall-clock timeout of 60 minutes wraps the entire job; on timeout, the lock clears and remaining stocks are marked stale
- [ ] Parallel fetch via `asyncio.gather` with `semaphore(10)` (HIGH-R-004) — not fully sequential, not unbounded
- [ ] Per-stock retry: 2 retries with 5s/15s exponential backoff; failures on one stock never abort others (per-stock isolation, R-001)
- [ ] Price validity guard: reject prices ≤0 or deviating >75% from the prior snapshot (configurable via `system_config.price_deviation_max_pct`, default 75 — MED-R-006, not the earlier 50% draft); rejected prices are logged as `CORPORATE_ACTION_CANDIDATE` for admin review, not silently discarded
- [ ] If >50% of stocks fail in a run, a Sentry CRITICAL alert fires
- [ ] Job reports a Sentry Cron Monitoring check-in on both success and failure paths

**Definition of Done**

- [ ] Integration test against a mocked yfinance client covers: full success, partial failure, complete outage, invalid-price rejection, holiday no-op, and lock-contention skip
- [ ] Batch timing benchmark: <30 seconds for 16 stocks (BAS §14 performance requirement)

**Dependencies & Integrations**

- `system_config` table (holiday calendar, deviation threshold, refresh lock) — Epic 9 seed data
- yfinance Python library, invoked only from this cron script, never from the request path (architecture §11.1)

**Technical Constraints**

- `PriceSnapshot` writes must be idempotent UPSERTs keyed on `(stock_code, trading_date)`
- Price fetching is isolated behind a `PriceProvider` interface in `pricing/service.py` so yfinance can be swapped later without touching calling code (R-001 mitigation, V2 evolution path)

---

## BE-5.2 — Price Outage Handling & Manual Override

**FR-008 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given the price feed fails for 2 of 16 stocks in a refresh run
When a user views their dashboard within 5 minutes of the failed refresh
Then only the 2 affected positions show a stale indicator and a manual price entry
     field; all other positions show current, unaffected prices
```

**Acceptance Criteria**

- [ ] `GET /api/v1/pricing/prices` returns price + source (`automated`/`manual`/`stale`) + `last_refreshed_at` per requested stock code
- [ ] `POST /api/v1/pricing/manual-override` creates a `PriceSnapshot` with `source="manual"`, `created_by_user_id=<user>`, current timestamp; position recalculates immediately using this price
- [ ] BR-023: the next successful automated refresh supersedes any manual override for that stock — `source` reverts to `automated`
- [ ] Manual override is blocked for trial-expired (read-only) accounts (EC-020) — same permission gate as all other write actions
- [ ] EX-001/EX-002 banner copy matches BAS exactly, including the partial-failure variant naming the specific affected stock codes

**Definition of Done**

- [ ] Full outage → manual override → next-refresh-supersedes sequence covered by an integration test (mirrors BAS Integration/Scenario Tests table)

**Dependencies & Integrations**

- BE-5.1 for the automated side of the source-transition logic

**Technical Constraints**

- `PriceSnapshot` is shared system data, not per-user — a manual override by user A is visible to user B who also holds the same stock, until the next automated refresh supersedes it (BAS §7 Entity 6 note)

---

## FE-5.1 — Stale Data Banner & Manual Price Override UI

**FR-008 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given the dashboard API response indicates 2 stocks are stale
When the page renders
Then a banner reads "Price data unavailable for 2 stocks — [Stock A], [Stock B]" and
     each affected position row exposes an inline manual-price input
```

**Acceptance Criteria**

- [ ] Complete-outage banner copy vs. partial-failure banner copy match EX-001/EX-002 exactly
- [ ] Manual entry field disappears and reverts to the automated price display once superseded (BR-023) — verified via SWR revalidation after the next scheduled refresh window
- [ ] For trial-expired accounts, the manual override field is replaced by the paywall prompt (EC-020)

**Definition of Done**

- [ ] Visual states for complete outage, partial outage, and override-in-effect all covered by component tests/screenshots

**Dependencies & Integrations**

- BE-5.2, FE-4.1 (dashboard shell)

**Technical Constraints**

- Staleness threshold (28 hours) is a shared frontend constant (`lib/constants.ts`), not hardcoded per component (architecture §7.2)

---

# Epic 6 — CSV Import & Export

## BE-6.1 — CSV Import Processing (Async Job)

**FR-014 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a user uploads a correctly formatted CSV with 16 positions and 34 dividend rows
When they POST to /import/csv
Then the file passes pre-accept validation, an ImportJob(status=processing) is created,
     a BackgroundTask performs row validation then an atomic all-or-nothing create, and
     the client polls /import/status/{job_id} until it reads status=complete
```

**Acceptance Criteria**

- [ ] Pre-accept synchronous validation (HIGH-R-009): reject >1MB with 413; require `Content-Type: text/csv`/`application/csv`; validate full UTF-8 decodability, else 400 with "File encoding error. Please save your CSV as UTF-8 before uploading." (EC-019); reject >1,000 data rows with 400
- [ ] Phase 1 (row-level validation, all rows/sheets) must fully pass before Phase 2 begins; any failing row halts the entire import with zero records created (BR-022 atomicity) and returns a row-level error report ("Row [N], Column [X]: [specific error]")
- [ ] Phase 2 is a single atomic DB transaction creating all Position/Lot/DividendTranche rows — partial failure rolls back completely (EX-005), with the generic "Import failed due to a system error... Your existing portfolio has not been affected" message
- [ ] `qualifying_shares` on imported dividend rows defaults to the matching position's imported share count if the optional CSV column is absent; if present, validated ≤ that position's total imported shares (VR-013)
- [ ] EC-007: a CSV row for a stock code already active in the portfolio is rejected at validation with the "Use 'Add Lot' instead" message (reject-only at V1 per OQ-012 — ⚠ confirm before CSV import sprint if a merge/replace mode is later required)
- [ ] EC-008: duplicate tranche label for the same stock+year within the same file is rejected at validation
- [ ] Import completes within 30 seconds for 500 rows (BAS §14 performance requirement)
- [ ] Stuck-job cleanup: any `ImportJob` left in `processing` for >1 hour (e.g., due to a Render service restart mid-task) is marked `failed` by the daily `check_trial_expiry.py` job's cleanup step (HIGH-R-005), with a re-upload CTA
- [ ] `audit_log` entry `IMPORT_COMPLETED`

**Definition of Done**

- [ ] Integration tests cover: happy path (16 positions/34 tranches), missing required column, encoding failure, row-count limit exceeded, duplicate-stock rejection, duplicate-tranche-label rejection, mid-transaction failure rollback
- [ ] Rate limited to 2/minute per authenticated user (architecture §14.4)

**Dependencies & Integrations**

- Reuses `portfolio/calculator.py` for fee computation per imported lot — must not reimplement fee logic separately
- `ImportJob` table and polling endpoint

**Technical Constraints**

- Temp file storage via `tempfile.NamedTemporaryFile`, deleted on completion or error — no imported file persists beyond job processing
- CSV injection defence (IV-008 scope note): formula-prefix characters (`=`, `+`, `-`, `@`) are only a concern for the _outbound_ template/export files (BE-6.2, BE-8.1), not inbound import parsing

---

## BE-6.2 — CSV Template Download

**FR-015 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a user is on the Import page
When they click "Download Template"
Then a static file BursaTrack_Import_Template.csv downloads, containing headers, a guide
     row, and one example row for both the Positions/Lots and Dividend Tranches sheets
```

**Acceptance Criteria**

- [ ] Served as a static frontend asset (ADD-013 decision — no dedicated API endpoint), consistent with the API design record's resolution of PD-000
- [ ] Columns match the CSV Import Template Specification exactly (BAS §7), including the optional `qualifying_shares` column on the Dividends sheet
- [ ] Any example/guide cell beginning with `=`, `+`, `-`, `@` is quoted/escaped to prevent formula injection when opened in Excel (HIGH-R-009 CSV injection defence)

**Definition of Done**

- [ ] Template file diffed against the BAS Sheet 1 / Sheet 2 column specification for exact match

**Dependencies & Integrations**

- None (static asset)

**Technical Constraints**

- Must be kept in sync with BE-6.1's validation rules — if a column is added/removed from the import validator, the template must be updated in the same PR

---

## FE-6.1 — CSV Import UI

**FR-014 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a user has uploaded a CSV file
When the server returns 202 Accepted with a job_id
Then the UI polls /import/status/{job_id} every 2 seconds and shows a progress state,
     then either a success banner ("Import complete — N positions and M dividend records
     imported") or a row-level error report
```

**Acceptance Criteria**

- [ ] Error report is scannable — each row error shown with row number, column, and message, matching BE-6.1's format
- [ ] A failed/timed-out job (per HIGH-R-005 cleanup) shows the re-upload CTA
- [ ] Uses the shared `ImportStatusPoller` component already scoped in the architecture's frontend structure (§7.2)

**Definition of Done**

- [ ] Polling stops correctly on both `complete` and `failed` terminal states (no infinite polling)

**Dependencies & Integrations**

- BE-6.1

**Technical Constraints**

- Poll interval fixed at 2 seconds per architecture §10.3 sequence diagram

---

## FE-6.2 — CSV Template Download Button

**FR-015 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a user is on the Import page
When they click "Download Template"
Then the browser downloads BursaTrack_Import_Template.csv without a network round-trip
```

**Acceptance Criteria**

- [ ] Static asset served directly, no loading state needed

**Definition of Done**

- [ ] Link verified on the Import page in both empty-portfolio and existing-portfolio states

**Dependencies & Integrations**

- BE-6.2

**Technical Constraints**

- None

---

# Epic 7 — Subscription & Billing

## BE-7.1 — Stripe Checkout & Webhook Processing

**FR-016 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a trial or trial-expired user clicks "Subscribe"
When the client POSTs to /subscription/checkout
Then the server creates a Stripe Checkout Session and returns its URL; upon payment
     completion, Stripe's checkout.session.completed webhook activates the account
     idempotently
```

**Acceptance Criteria**

- [ ] `POST /webhooks/stripe` verifies the `Stripe-Signature` header before trusting any payload (OW-010 — never trust unsigned webhook data)
- [ ] Idempotency: every webhook `event.id` is checked against `processed_webhook_events` before processing; a re-delivered event returns 200 with no side effect (OTQ-008)
- [ ] Events handled: `checkout.session.completed` → `account_status=active`, `subscription_start_date` set, `subscription_renewal_date` set from `current_period_end`; `invoice.payment_succeeded` → confirms active, refreshes `subscription_renewal_date` from `current_period_end` (not by adding a fixed interval — LOW-R-005); `invoice.payment_failed` → `account_status=grace_period`, user notified by email; `customer.subscription.deleted` → `account_status=trial_expired`
- [ ] No custom renewal cron job exists — renewal is entirely Stripe-native (`collection_method=charge_automatically`); this was a deliberate architecture correction (CRIT-R-003) to eliminate double-charge risk
- [ ] Webhook handler responds within Stripe's 30-second requirement
- [ ] Cancellation flow: `POST /subscription/cancel` (or equivalent) schedules the transition to `trial_expired` at period end without deleting any portfolio data (BR-018) — no proration/refund logic at V1 (EC-018, ⚠ OQ-010 pending Product+Legal sign-off on refund policy)
- [ ] `audit_log` entries `SUBSCRIPTION_ACTIVATED` / `SUBSCRIPTION_CANCELLED`

**Definition of Done**

- [ ] Idempotent re-delivery test: replaying the same webhook event twice produces exactly one state transition
- [ ] Stripe test-mode keys used in all non-production environments (MED-R-001) — verified in environment variable configuration, never live keys outside production

**Dependencies & Integrations**

- Stripe SDK, `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` env vars
- Resend for grace-period/failure notification emails

**Technical Constraints**

- Rate limit: `POST /webhooks/stripe` at 100/minute per IP (MED-R-008) — higher than user-facing endpoints since Stripe may burst-deliver
- Currency: MYR only; no FPX support at V1 (R-004, known gap — document, do not attempt to build)

---

## BE-7.2 — Trial Expiry & Access Gating

**FR-016 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a user's trial_expiry_date has passed
When the daily check_trial_expiry.py cron runs at 01:00 UTC
Then the account transitions to trial_expired, and subsequent write requests
     (add/edit/delete position, dividend, manual price override, CSV import) are
     rejected while GET/read requests remain available
```

**Acceptance Criteria**

- [ ] `UPDATE users SET account_status='trial_expired' WHERE account_status='trial' AND trial_expiry_date <= CURRENT_DATE` — idempotent, safe to re-run same-day
- [ ] Permission Matrix (BAS §9) enforced server-side on every write endpoint: trial-expired users get a paywall-class rejection on add/edit/delete/import/manual-override, but retain read access to dashboard, sell calculator (read-only), dividend calendar, CSV template download, PDPA export, and deletion request
- [ ] Trial length is 14 calendar days from registration (BR-017) ⚠ _STAKEHOLDER SIGN-OFF PENDING (OQ-001 — confirm 14 days is final)_

**Definition of Done**

- [ ] Every write endpoint has an explicit test asserting rejection for `trial_expired` status, not just an assumed inherited check

**Dependencies & Integrations**

- Cron infrastructure (Epic 9)

**Technical Constraints**

- Enforcement must happen at the API layer on every request — do not rely solely on frontend route guards, since API endpoints are directly reachable

---

## FE-7.1 — Paywall / Subscribe UI

**FR-016 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a user's trial has expired
When they log in
Then they see their portfolio in read-only mode with a paywall prompt, and clicking
     "Subscribe" redirects to Stripe Checkout; on return, the UI polls subscription
     status until it flips to active (or shows a "please wait" message after 30s)
```

**Acceptance Criteria**

- [ ] Matches architecture §10.4's polling pattern exactly: poll every 2s, up to 15 attempts, before falling back to "Payment processing - please wait a moment and refresh" (HIGH-R-008 — webhook may not have arrived yet when the user returns from Stripe)
- [ ] Read-only mode hides/disables all write affordances (add position, add dividend, delete, import, manual override) consistent with the Permission Matrix
- [ ] `SubscriptionGate` wraps all protected routes and redirects trial-expired write attempts to the paywall

**Definition of Done**

- [ ] Manual test of the full subscribe round-trip against Stripe test mode, including the polling fallback message

**Dependencies & Integrations**

- BE-7.1, BE-7.2

**Technical Constraints**

- None additional

---

## FE-7.2 — Subscription Management (Cancel) UI

**FR-016 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a paying subscriber with renewal on 2026-08-01
When they click "Cancel Subscription" on 2026-07-15
Then they see "Your subscription ends on 1 Aug 2026. Your data will be preserved." and
     retain full access until that date
```

**Acceptance Criteria**

- [ ] Confirmation copy matches BAS US-020 exactly, with the actual renewal date interpolated
- [ ] Billing status component shows current plan and next renewal/expiry date at all times (`BillingStatus.tsx` per architecture §7.2)

**Definition of Done**

- [ ] Verified against BAS US-020 cancel scenario

**Dependencies & Integrations**

- BE-7.1

**Technical Constraints**

- None additional

---

# Epic 8 — PDPA Compliance & Admin

## BE-8.1 — PDPA Data Export

**FR-018 · Priority: Must Have (PDPA compliance obligation)** ⚠ _STAKEHOLDER SIGN-OFF PENDING (OQ-008: legal confirmation of V1 launch requirement)_

**Developer Action Plan**

```gherkin
Given an authenticated user (any account status) clicks "Download My Data"
When the client GETs /api/v1/account/export
Then the server assembles a single JSON file containing all the user's personal and
     financial data (excluding password_hash, token_version, internal FKs, and
     soft-deleted records) and streams it as a synchronous file download
```

**Acceptance Criteria**

- [ ] Export scope matches architecture §10.7 exactly: User, Portfolio, Position, Lot, DividendTranche, custom BrokerConfig, ImportJob, AuditLog (metadata/IP excluded) — shared `PriceSnapshot` market data is explicitly excluded (it isn't personal data)
- [ ] Filename: `bursatrack-export-{date}.json`
- [ ] Synchronous, in-memory generation — no async job needed at V1 data volumes (<~400 records/user)
- [ ] Available regardless of account status, including `trial_expired` and `pending_deletion`-eligible states (per BAS Permission Matrix — export access is broader than write access)
- [ ] `audit_log` entry `DATA_EXPORT_DOWNLOADED` recorded before the response streams
- [ ] Standard 60/minute authenticated rate limit applies — no special restriction needed at V1 volumes

**Definition of Done**

- [ ] Export content diffed field-by-field against the architecture §10.7 table to confirm no PII field is missing and no excluded field (password_hash etc.) leaks
- [ ] Legal sign-off obtained per OQ-008 before this is marked "done" for launch purposes, even if code is complete earlier

**Dependencies & Integrations**

- Depends on all other domain data existing (positions, lots, dividends, broker configs, import jobs, audit log)

**Technical Constraints**

- `StreamingResponse` with `Content-Disposition: attachment` — do not buffer the entire export unnecessarily for larger accounts, but V1 volumes make this a non-issue in practice

---

## BE-8.2 — PDPA Account Deletion (30-Day Grace Period)

**FR-019 · Priority: Must Have (PDPA compliance obligation)** ⚠ _STAKEHOLDER SIGN-OFF PENDING (OQ-009: legal confirmation the 30-day window satisfies right of erasure)_

**Developer Action Plan**

```gherkin
Given a logged-in user types "DELETE" to confirm account deletion
When the client POSTs /account/delete
Then account_status becomes pending_deletion, permanent_deletion_date is set to
     today+30 days, all sessions are invalidated (token_version incremented), a
     cancellation email is sent, and the user is logged out and cannot log in again
     until either cancellation or permanent deletion
```

**Acceptance Criteria**

- [ ] Two-step confirmation UX contract: offer data export first ("Download My Data" / "Skip and Continue"), then require typing "DELETE" (BAS Workflow 9)
- [ ] `GET /account/cancel-deletion?token=xxx` (within 30 days) restores the account to its pre-deletion status and clears `permanent_deletion_date`
- [ ] `pending_deletion` accounts cannot authenticate via `/auth/login` at all (BAS Permission Matrix)
- [ ] `process_deletions.py` cron (03:00 UTC daily) hard-deletes accounts where `permanent_deletion_date <= CURRENT_DATE`:
  - [ ] **Pre-deletion gate (MED-R-005):** verifies the PDPA confirmation email was actually delivered (`pending_email_notifications` record with `sent_at IS NOT NULL`); if not, skips deletion and fires a Sentry CRITICAL for manual remediation — never silently deletes without proof of notification
  - [ ] Cancels any live Stripe subscription (`cancel_at_period_end=False`) before deleting user data (MS-002)
  - [ ] Deletes, in order, within one transaction: manual price overrides → import_jobs → processed_webhook_events → pending_email_notifications → dividend_tranches → lots → positions → portfolio → anonymises `subscription_records.user_id=NULL` (7-year accounting retention) → inserts an anonymised `system_deletion_log` row → deletes the `users` row (which CASCADEs `audit_log` automatically, per the FK design — HIGH-R-007)
  - [ ] Idempotent: safe to re-run against a partially-deleted user from a previous failed run (MED-R-007)
- [ ] Email address is freed for re-registration only after the hard-delete completes
- [ ] EC-018: deletion while a subscription is active stops future billing from the request date; no prorated refund at V1 (⚠ OQ-010 — confirm with Product+Legal before launch, document in ToS)

**Definition of Done**

- [ ] Integration test for the full lifecycle: request deletion → cancel within window → restored; and separately, request deletion → 30 days pass → hard-deleted → email re-registrable
- [ ] Test specifically asserts the pre-deletion notification gate blocks deletion when the confirmation email was never marked `sent_at`

**Dependencies & Integrations**

- Shares `pending_tokens`/cancellation-token mechanics with Epic 1
- Stripe SDK (subscription cancellation)
- `system_deletion_log` table

**Technical Constraints**

- This is the most legally sensitive job in the codebase — every deletion step must be traceable and the order matters (subscription cancellation before data deletion; deletion-log insert before the `users` row itself is removed, since some logging approaches would otherwise lose the FK target)

---

## BE-8.3 — Admin Fee Config & BrokerConfig Management

**Priority: Must Have (supports BR-015 stamp duty configurability, custom broker support)**

**Developer Action Plan**

```gherkin
Given the stamp duty rate is gazetted to change before 12 July 2028
When an operator PATCHes /admin/config/fees with the ADMIN_API_KEY header
Then the system_config value updates immediately, invalidating the in-process TTLCache,
     and all subsequent fee calculations use the new rate without a code deployment
```

**Acceptance Criteria**

- [ ] `/admin/config/fees` protected by a distinct `ADMIN_API_KEY` (not the user JWT scheme), compared in constant time
- [ ] `GET`/`PATCH /admin/config/fees` documents its TTLCache staleness explicitly (60-minute TTL, per-process on a single V1 instance) — per API security review finding OQ-000
- [ ] `GET /api/v1/brokers` lists system brokers (`is_system=true`) plus the caller's own custom configs; `POST/PATCH/DELETE /api/v1/brokers/{id}` scoped to the user's own custom configs only
- [ ] Custom broker validation per VR-014: name required/≤60 chars/unique vs. system names; percentage rate 0–2%; minimum fee RM0–100; flat fee RM0.01–100
- [ ] Deleting a custom `BrokerConfig` referenced by any `Lot` returns 409 `{"error": "in_use", "message": "This broker config is used by existing lots and cannot be deleted."}`
- [ ] System brokers (`is_system=true`) can never be modified or deleted via the API
- [ ] `audit_log` entry `CONFIG_UPDATED` on every fee-config change

**Definition of Done**

- [ ] Test confirms a `system_config` change (e.g., stamp duty rate) is reflected in a subsequent `BE-2.1` fee calculation without a redeploy, once the TTLCache expires or is invalidated
- [ ] Admin endpoint rate limit confirmed intentional (60/min keyed by API key — carried forward from API design Stage 2, per the API security review's open item #3)

**Dependencies & Integrations**

- `system_config` and `BrokerConfig` tables (Epic 9 seed data)

**Technical Constraints**

- `BrokerConfig.rate`/`minimum_fee` are fixed at config time; clearing fee % and stamp duty rate are always read from `system_config` at calculation time, not duplicated into `BrokerConfig` (architecture §10.6) — this ensures a stamp duty rate change applies uniformly across all brokers instantly

---

## FE-8.1 — Account Settings: Data Export & Delete Account UI

**FR-018, FR-019 · Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a user is in Account Settings
When they click "Delete My Account"
Then they are offered a data export first, then must type "DELETE" to confirm, and
     receive on-screen confirmation that they've been logged out and cannot log back
     in during the 30-day window
```

**Acceptance Criteria**

- [ ] "Download My Data" button triggers the BE-8.1 export directly from Account Settings, independent of the deletion flow
- [ ] Deletion flow matches BAS Workflow 9's two-step confirmation exactly, including the literal "DELETE" typed-confirmation requirement
- [ ] Cancellation-email link, when clicked (outside the app, from the user's inbox), lands on a confirmation page showing the account was restored

**Definition of Done**

- [ ] Full deletion request → cancel-within-window UI flow manually tested end to end

**Dependencies & Integrations**

- BE-8.1, BE-8.2

**Technical Constraints**

- None additional

---

## FE-8.2 — Custom Broker Config UI

**Priority: Must Have (supports FR-003/FR-004 for users on brokers outside the system list)**

**Developer Action Plan**

```gherkin
Given a user's broker isn't in the system-provided list
When they create a custom broker with a percentage or flat fee structure
Then it appears in their broker dropdown for future lots, and cannot be deleted once
     referenced by an existing lot
```

**Acceptance Criteria**

- [ ] Form validation matches VR-014 exactly (rate bounds, minimum/flat fee bounds, name uniqueness)
- [ ] Attempting to delete an in-use custom broker surfaces the 409 `in_use` message clearly, with guidance to reassign or delete the referencing lots first

**Definition of Done**

- [ ] Verified against BE-8.3's validation and conflict-handling behavior

**Dependencies & Integrations**

- BE-8.3

**Technical Constraints**

- None additional

---

# Epic 9 — Deployment & Infrastructure

## DEP-9.1 — Repository Scaffold & Local Dev Environment

**Priority: Must Have (foundational — blocks all other epics)**

**Developer Action Plan**

```gherkin
Given the repository currently contains only /specs
When a developer clones the repo and runs the local dev setup
Then docker-compose brings up FastAPI, Next.js, and PostgreSQL locally, matching the
     module structure defined in Solution-Architecture §7.2
```

**Acceptance Criteria**

- [ ] Backend scaffold matches the exact module layout: `app/{auth,portfolio,pricing,subscription,admin}/{models,schemas,router,service}.py`, plus `app/scripts/` for cron jobs
- [ ] Frontend scaffold matches the Next.js App Router layout: `(auth)` and `(app)` route groups, `components/{ui,portfolio,dividends,calculator,subscription,shared}`, `hooks/`, `lib/`
- [ ] `docker-compose.yml` runs FastAPI + Next.js + PostgreSQL with hot-reload for local development
- [ ] `.env.example` documents every required environment variable from architecture §14.5 without committing real secrets
- [ ] No cross-module direct database joins — all cross-domain access goes through service-layer interfaces (P-008), enforced by code review / import-linting from day one

**Definition of Done**

- [ ] A fresh clone + `docker-compose up` reaches a working "hello world" health check on both frontend and backend with zero manual steps beyond copying `.env.example`

**Dependencies & Integrations**

- None — this is the first story in sequence

**Technical Constraints**

- Python 3.13, FastAPI, async SQLAlchemy, Pydantic v2; Next.js 15, TypeScript strict mode, Tailwind, shadcn/ui (architecture §1 "at a glance" table)

---

## DEP-9.2 — CI Pipeline (GitHub Actions)

**Priority: Must Have**

**Developer Action Plan**

```gherkin
Given a developer opens a pull request
When GitHub Actions CI runs
Then pytest (backend), tsc --noEmit (frontend types), and eslint (frontend lint) all
     execute, and a failure in any step blocks merge and blocks deployment
```

**Acceptance Criteria**

- [ ] CI workflow file at `.github/workflows/ci.yml` runs all three checks on every PR
- [ ] Merge to `main` is gated on CI passing (architecture §18.2 flowchart)
- [ ] CI failure produces a clear, actionable log — not just a red X

**Definition of Done**

- [ ] A deliberately broken test/type-error/lint violation in a test PR is confirmed to block the pipeline

**Dependencies & Integrations**

- DEP-9.1 scaffold must exist first

**Technical Constraints**

- None additional

---

## DEP-9.3 — Hosting Setup (Vercel + Render)

**Priority: Must Have**

**Developer Action Plan**

```gherkin
Given CI passes on a merge to main
When the deployment pipeline runs
Then Vercel auto-deploys the Next.js frontend to production, Render runs
     "alembic upgrade head" as a pre-deploy command, and — only if migrations succeed —
     deploys the new FastAPI version; PR branches get automatic Vercel preview URLs
```

**Acceptance Criteria**

- [ ] Render web service, four cron job schedules (`refresh_prices.py`, `check_trial_expiry.py`, `process_deletions.py`), and managed PostgreSQL are all provisioned (note: architecture §8.4 documents that a previously-planned `process_renewals.py` cron was removed — renewal is Stripe-native, see BE-7.1; do not provision this fourth cron job)
- [ ] A failed `alembic upgrade head` aborts the deploy and leaves the previous FastAPI version running (architecture §18.2)
- [ ] Render starter plan (not free tier) is used to avoid cold starts (R-008 mitigation)
- [ ] CORS configured with the programmatic origin validator from architecture §14.3 — **not** a `"https://*.vercel.app"` wildcard (CRIT-R-001 — this was an explicitly corrected security defect; do not reintroduce the wildcard pattern)
- [ ] Rollback procedure documented and tested at least once: Vercel "redeploy previous," Render "redeploy previous deploy," `alembic downgrade -1` if needed (architecture §18.4)
- [ ] ⚠ Known risk accepted for V1 (HIGH-R-003): Vercel preview deployments point at the **production** Render API. All preview testing must use a dedicated non-real test account; never exercise delete/import/PDPA flows against real data from a preview URL. A staging Render service (~USD 7/month) is the recommended medium-term fix — provision before the first paid user, not required to block V1 launch

**Definition of Done**

- [ ] End-to-end deploy verified: a merged PR reaches production on both Vercel and Render within the expected pipeline time, with migrations applied correctly

**Dependencies & Integrations**

- DEP-9.1, DEP-9.2

**Technical Constraints**

- All secrets (DATABASE_URL, JWT_PRIVATE_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, RESEND_API_KEY, SENTRY_DSN, ADMIN_API_KEY) set as Render/Vercel environment variables only — never committed to git (architecture §14.5)
- Stripe test-mode keys in every non-production environment (MED-R-001)

---

## DEP-9.4 — Database Migration Baseline & Seed Data

**Priority: Must Have**

**Developer Action Plan**

```gherkin
Given the physical schema is fully specified in the Database Design artifacts
When the first Alembic migration is authored and applied
Then all core tables exist (users, portfolios, positions, lots, dividend_tranches,
     price_snapshots, broker_configs, stocks, system_config, audit_log, import_jobs,
     pending_tokens, pending_email_notifications, processed_webhook_events,
     subscription_records), with system brokers, an initial Bursa stock reference list,
     and stamp-duty/clearing-fee system_config values seeded
```

**Acceptance Criteria**

- [ ] Every migration is additive-only (new tables/columns); destructive changes (drops/renames) are deferred to a separate subsequent deployment (ADR-011, P-007) — this makes every deploy safely rollback-able
- [ ] Seed data includes the V1 system broker list (Maybank IB, CIMB Clicks, RHB Reflex, Rakuten Trade, Mirae Asset, M+ Online) with `is_system=true`
- [ ] `system_config` seeded with `stamp_duty_rate`, `price_deviation_max_pct` (default 75), `bursa_holidays` (current year's calendar)
- [ ] All monetary columns use `NUMERIC` with the precisions specified in architecture §12.3 — never `FLOAT`/`DOUBLE`
- [ ] Required indexes created per architecture §8.3: `lots(position_id, is_deleted)`, `dividend_tranches(position_id, year, is_deleted)`, `price_snapshots(stock_code, trading_date)`, `audit_log(user_id)`, `audit_log(entity_type, entity_id)`, `import_jobs(user_id, status)`, `processed_webhook_events(event_id)` (PK)
- [ ] `Lot` and `DividendTranche` include a `version INTEGER` column for optimistic locking from the first migration, not retrofitted later
- [ ] `users.audit_log` FK relationship is `ON DELETE CASCADE` (HIGH-R-007 — required for BE-8.2's hard-delete correctness)

**Definition of Done**

- [ ] `alembic upgrade head` and `alembic downgrade -1` both verified to work cleanly against a fresh database
- [ ] Schema reviewed against `BursaTrack-DB-Stage3-Physical-Schema.md` for exact field/type/constraint parity

**Dependencies & Integrations**

- Blocks Epics 1–8 (nothing can be built without the schema existing)

**Technical Constraints**

- PostgreSQL 16, Alembic-managed migrations only — no manual schema changes in any environment

---

## DEP-9.5 — Observability Setup

**Priority: Must Have**

**Developer Action Plan**

```gherkin
Given the application is deployed
When any request is served or any cron job runs
Then structlog emits structured JSON logs to stdout, Sentry captures unhandled
     exceptions with request context (excluding financial data and request bodies),
     each cron script reports a Sentry Cron Monitoring check-in, and BetterUptime
     polls /health every 3 minutes
```

**Acceptance Criteria**

- [ ] `GET /health` checks DB connectivity (`SELECT 1`) and returns 503 on failure — this is the sole uptime-monitoring signal (architecture §17.3)
- [ ] Sentry integrated in three contexts: FastAPI (via SDK middleware), Next.js (`@sentry/nextjs`), and each of the three cron scripts (try/except wrapping with `capture_exception` + `capture_check_in`)
- [ ] Sensitive-data exclusion verified: no request body, portfolio value, or dividend amount ever appears in a log line or Sentry payload
- [ ] Alerting matrix from architecture §17.5 wired up: new Sentry error type → email; missed cron check-in → email; >50% price refresh failure → email (+Slack if configured); `/health` unreachable → email+SMS via BetterUptime

**Definition of Done**

- [ ] A deliberately-triggered exception in a test/staging path is confirmed to appear in Sentry with the expected (sanitized) context
- [ ] A deliberately-skipped cron run is confirmed to trigger a Sentry Cron Monitoring alert

**Dependencies & Integrations**

- DEP-9.3 (hosting), all cron jobs (Epics 5, 7, 8)

**Technical Constraints**

- No custom APM/metrics beyond Render's built-in dashboard at V1 (explicitly deferred to V2 per architecture §20.2)

---

## DEP-9.6 — Security Hardening Baseline

**Priority: Must Have**

**Developer Action Plan**

```gherkin
Given the API is publicly reachable
When any request arrives
Then CORS, rate limiting, HTTPS/HSTS, and secrets handling all conform to the
     architecture's security baseline before the first real user account is created
```

**Acceptance Criteria**

- [ ] CORS uses the programmatic origin validator (static allowlist + Vercel-preview regex), never a broad wildcard, with `allow_credentials=True` (CRIT-R-001, architecture §14.3)
- [ ] SlowAPI rate limits applied exactly per architecture §14.4's table (register 3/min, login 5/min, password-reset-request 3/min, CSV import 2/min per user, Stripe webhook 100/min per IP, all other authenticated endpoints 60/min per user)
- [ ] HTTPS enforced on all endpoints; HTTP redirects to HTTPS at the platform level; HSTS headers set (architecture §14.6)
- [ ] `ADMIN_API_KEY` compared in constant time, distinct from the JWT/user auth scheme
- [ ] Every ownership-checked resource returns 404 (never 403) on cross-user access attempts — verified as a cross-cutting test across all Epic 2–8 endpoints, not just spot-checked on one
- [ ] Login response body has a `maxLength: 128` bound on the password field (defensive bound per API security review finding IV-000) even though it's unlikely exploitable
- [ ] `info.description` / equivalent internal documentation explicitly states HTTPS-only enforcement, per API security review finding SC-000

**Definition of Done**

- [ ] Security test cases from BAS §14 (accessing another user's data → 404, rate-limit lockout behavior, cookie flags, session expiry, reset-token reuse) automated and passing
- [ ] Security-review action items from `04-api-security-review.md` §4 ("Prioritised Change List") confirmed complete: the four ✅-marked items already applied, plus the four remaining LOW-priority items (422 on login, staleness note on `/admin/config/fees`, HTTPS/HSTS description sentence, `maxLength` on login password) closed out before launch

**Dependencies & Integrations**

- Cuts across every epic's endpoints — this story's tests should be written as a suite that runs against the whole API surface, not a single module

**Technical Constraints**

- No secrets in git, ever, at any point in history — verify with a pre-commit secret scanner if not already in place

---

## Summary — Traceability Checklist

Every Must-Have and Should-Have FR from the BAS is covered by at least one Backend and one Frontend story above:

| FR                           | Backend Story  | Frontend Story                   |
| ---------------------------- | -------------- | -------------------------------- |
| FR-001 Registration          | BE-1.1         | FE-1.1                           |
| FR-002 Login/Logout          | BE-1.2         | FE-1.2                           |
| FR-003 Add Position          | BE-2.1         | FE-2.1                           |
| FR-004 Add Lot               | BE-2.2         | FE-2.2                           |
| FR-005 Edit Position/Lot     | BE-2.3         | FE-2.3                           |
| FR-006 Delete Position       | BE-2.4         | FE-2.4                           |
| FR-007 Auto Price Refresh    | BE-5.1         | (dashboard reflects it — FE-4.1) |
| FR-008 Price Outage Handling | BE-5.2         | FE-5.1                           |
| FR-009 Log Dividend Tranche  | BE-3.1 (P0)    | FE-3.1                           |
| FR-010 Edit/Delete Dividend  | BE-3.2         | FE-3.2                           |
| FR-011 Portfolio Dashboard   | BE-4.1         | FE-4.1                           |
| FR-012 Sell Calculator       | BE-4.2         | FE-4.2                           |
| FR-013 Dividend Calendar     | BE-3.3         | FE-3.3                           |
| FR-014 CSV Import            | BE-6.1         | FE-6.1                           |
| FR-015 CSV Template          | BE-6.2         | FE-6.2                           |
| FR-016 Subscription          | BE-7.1, BE-7.2 | FE-7.1, FE-7.2                   |
| FR-017 Password Reset        | BE-1.3         | FE-1.3                           |
| FR-018 PDPA Export           | BE-8.1         | FE-8.1                           |
| FR-019 Account Deletion      | BE-8.2         | FE-8.1                           |

**Outstanding stakeholder sign-offs that do not block starting work, but must close before launch** (carried from BAS §13 Open Questions): OQ-001 (trial length), OQ-002 (SST on brokerage — critical, verify immediately), OQ-005 (sell-calculator default broker), OQ-007 (password reset Must-Have confirmation), OQ-008/OQ-009 (PDPA legal sign-off — critical), OQ-010 (refund policy), OQ-012 (CSV import conflict resolution).
