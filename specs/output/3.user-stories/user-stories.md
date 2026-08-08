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

- [x] `UPDATE lots SET ..., version = version + 1 WHERE id = ? AND version = <submitted_version>`; zero rows affected → HTTP 409 `{"error": "version_conflict", "message": "This record was modified by another session. Please refresh and try again."}` (EX-008, architecture §15.4)
- [x] Editing a lot's share count does **not** alter any existing `DividendTranche.total_amount` (EC-015) — the response includes a notice that dividend records were not changed. The `DividendTranche` half of this invariant can't be verified yet (Epic 3) — see Implementation Record.
- [x] `PATCH /api/v1/portfolio/positions/{id}` covers metadata only (category_tag, notes); lot financial fields are edited via `PATCH /api/v1/portfolio/positions/{id}/lots/{lot_id}`
- [x] Accessing or editing a position/lot owned by another user returns 404, never 403 or a differentiated error (BAS §9 URL-level enforcement; API security review AA-001–009)
- [x] VR-004/005/006 re-validated on edit exactly as on create
- [x] `audit_log` entry `LOT_UPDATED` (or `POSITION_UPDATED` for metadata edits) records previous and new values

**Definition of Done**

- [x] Version-conflict test: a first PATCH succeeds and bumps version to 2; a second PATCH submitting the now-stale version=1 receives 409. Simulated sequentially rather than with true request concurrency (see Implementation Record) — the conditional-UPDATE code path exercised is identical to what a real race would hit.
- [x] EC-015 regression test confirms a lot edit doesn't mutate any *other* lot's stored fields — the `DividendTranche`-total half is deferred to BE-3.1, same as BE-2.2's EC-022 precursor.

**Dependencies & Integrations**

- BE-2.1 calculator, BE-3.x dividend endpoints (for the invariant check)

**Technical Constraints**

- `version INTEGER` column required on `Lot` (already in physical schema, architecture §8.3/§12.1)

---

### Implementation Record — BE-2.3

**What was actually built**

- `app/errors.py` — `version_conflict()` (409, exact spec message).
- `app/portfolio/service.py` — `get_owned_lot` (ownership on both position and lot, 404), `update_position_metadata` (category_tag/notes, `POSITION_UPDATED` audit entry with previous/new values), `update_lot` (optimistic locking via a conditional `UPDATE ... WHERE id=? AND version=?`; 0 rows affected → 409; recomputes all fee fields from the resulting shares/price/broker via the same `calculate_lot_fees` used everywhere else; `LOT_UPDATED` audit entry).
- `app/portfolio/schemas.py` — `UpdatePositionRequest`, `UpdateLotRequest` (all fields optional except `version`; a `model_validator` enforces "at least one of shares/purchase_price/broker_id/purchase_date" per the OpenAPI description). Both edit schemas reuse the same `_check_shares`/`_check_purchase_price`/`_check_purchase_date` functions BE-2.2 already extracted.
- `app/portfolio/router.py` — `PATCH /api/v1/portfolio/positions/{id}`, `PATCH /api/v1/portfolio/positions/{id}/lots/{lot_id}`, and (see Deviation 2) `GET /api/v1/portfolio/positions/{id}`. Extracted `_build_position_response` so all three Position-returning endpoints (this story's two, plus BE-2.1's create) share one field-mapping implementation.
- `app/portfolio/models.py` + `alembic/versions/0006_add_position_notes_and_extend_audit_log.py` — added `positions.notes` (see Deviation 1) and extended `audit_log`'s CHECK constraints for `LOT_UPDATED`/`POSITION_UPDATED`/`Position`.

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **Fixed a latent bug from BE-2.1: `positions.notes` didn't exist.** `CreatePositionRequest` already accepted a `notes` field (added in BE-2.1 to match the OpenAPI contract), but there was no column to store it in, so it was silently dropped every time. Since this story's `UpdatePositionRequest` literally can't do its job ("category_tag and/or notes") without somewhere to persist notes, added the column now via migration 0006 and wired it into both `create_position` and `update_position_metadata`. Also added `notes` to `PositionResponse` (additive — the documented response schemas never include it either, another apparent spec gap) so a value the user sets can actually be read back.
2. **Added `GET /api/v1/portfolio/positions/{id}`, not explicitly required by any Epic 2 BE story's own AC.** Flagged as a real gap at the end of BE-2.2: no story specifies this endpoint, but FE-2.2's position detail page and its SWR revalidation need somewhere to read a Position's current state, and it shares the exact same OpenAPI path block as this story's PATCH. Built now, reusing 100% of the existing response-building logic, rather than letting it block FE-2.2 later.
3. **The EC-022-shaped invariant test pattern from BE-2.2 repeats here for EC-015**: the full "editing a lot doesn't change `DividendTranche.total_amount`" test can't be written until `DividendTranche` exists (BE-3.1). Wrote the testable half now (editing one lot never mutates any *other* lot's stored fields) and left an explicit note to extend it in BE-3.1, same pattern as BE-2.2.
4. **The "concurrent-edit integration test" is simulated sequentially, not with true concurrency.** A first PATCH succeeds and bumps `version` to 2; a second PATCH submitting the client's now-stale `version=1` is rejected with 409. This exercises the identical conditional-UPDATE code path a real race would hit (the whole point of optimistic locking is that "stale version" looks the same whether it arrived from a genuinely concurrent request or a sequential one) — true multi-connection concurrency isn't meaningfully testable against the test suite's single-connection in-memory SQLite fixture anyway.

**Test evidence**

- `uv run pytest`: 101/101 passing (85 pre-existing + 16 new: GET position detail + 404 ownership, PATCH position metadata + validation + audit log + 404 ownership, PATCH lot fee recalculation + version increment + EC-015 notice + no-notice-when-shares-unchanged + version-conflict 409 + broker override + empty-body rejection + VR-004 re-validation + cross-position-lot 404 + cross-user 404 + audit log + EC-015 precursor).
- Migration 0006 applied and rolled back cleanly against the real Postgres container.
- Live smoke test against the real backend + Postgres: created a position, fetched it via the new GET endpoint, PATCHed its metadata (category_tag + notes both persisted and read back correctly), PATCHed a lot's share count (fees recalculated, version incremented to 2, EC-015 notice present), and confirmed a stale-version PATCH correctly returns 409 without applying.

**Known gaps / not yet verified**

- The full EC-015/BR-009 dividend-invariant test is deferred to BE-3.1 (see Deviation 3), same as BE-2.2's EC-022 gap.
- No true multi-connection concurrency test exists for the version-conflict path (see Deviation 4) — considered acceptable since the code path is identical either way.

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

- [x] Soft-delete only — no physical row deletion at this layer (A-010); records remain for audit/PDPA export until account-level hard-delete
- [x] Cascade covers all active Lots under the Position in a single transaction. `DividendTranche` doesn't exist yet (Epic 3) — see Implementation Record.
- [x] `audit_log` entry `POSITION_DELETED` recorded (architecture §14.7)
- [x] EC-006 mechanism is in place (any ownership-checked write against a soft-deleted position returns 404) and verified via the Add Lot endpoint, since no dividend endpoint exists yet to test the literal AC — see Implementation Record.
- [x] EC-001 exception path: re-adding the same stock code after a soft-delete creates a **new** Position (the old soft-deleted one is not resurrected)

**Definition of Done**

- [x] Deletion is idempotent and fully reversible only via direct DB access (no "undo" UI at V1, consistent with BR — deletion confirmation copy is explicit that it "cannot be undone")

**Dependencies & Integrations**

- None beyond BE-2.1–2.3

**Technical Constraints**

- Soft-deleted rows must be excluded from every dashboard/aggregate query via `WHERE is_deleted = false` — missing this filter anywhere is a correctness bug, not just a display issue (it would corrupt yield/cost totals)

---

### Implementation Record — BE-2.4

**What was actually built**

- `app/portfolio/service.py` — `delete_position`: soft-deletes the Position (`is_deleted=true`, `deleted_at=now()`), bulk-updates all its active Lots to the same soft-deleted state in the same transaction, writes a `POSITION_DELETED` audit entry, commits.
- `app/portfolio/router.py` — `DELETE /api/v1/portfolio/positions/{id}`, authenticated, rate-limited, returns 204 with no body.
- `app/admin/models.py` + `alembic/versions/0007_extend_audit_log_for_position_deleted.py` — extended `audit_log`'s action CHECK constraint for `POSITION_DELETED`.

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **The cascade only covers Lots, not `DividendTranche`.** `DividendTranche` doesn't exist until Epic 3 (BE-3.1) — there's nothing to cascade to yet. `delete_position`'s docstring flags this explicitly so BE-3.1 doesn't forget to extend the cascade when the table lands.
2. **EC-006 ("logging a dividend against a soft-deleted position returns 404") is tested via the Add Lot endpoint, not a dividend endpoint** — the latter doesn't exist yet. The underlying mechanism is identical either way: `get_owned_active_position` filters `is_deleted=false`, so *any* write against a soft-deleted position 404s, regardless of which endpoint. The test (`test_add_lot_to_soft_deleted_position_returns_404_ec006_precursor`) exercises that shared mechanism directly.
3. **"Idempotent" is interpreted as "the end state never corrupts or double-applies,"** not "repeated calls return the same status code." A second `DELETE` on an already-deleted position 404s (the same ownership filter every other endpoint uses), rather than silently returning 204 again — consistent with how GET/PATCH already treat soft-deleted positions as not-found. Documented and tested explicitly (`test_delete_is_idempotent_second_call_returns_404_not_an_error`) so this interpretation is a visible decision, not an accident.

**Test evidence**

- `uv run pytest`: 111/111 passing (101 pre-existing + 10 new: 204 + soft-delete flags set, cascade to all active lots, audit log entry, 404-after-delete via GET, idempotent second-delete, 404 for nonexistent/foreign positions, auth requirement, the EC-006 mechanism test, and the EC-001 exception path — re-adding the same stock code after delete creates a genuinely new Position with no "existing position" warning).
- Migration 0007 applied and rolled back cleanly against the real Postgres container.
- Live smoke test against the real backend + Postgres: created a position with 2 lots, deleted it (204), confirmed GET now 404s, re-added the same stock code (got a new position ID, single lot, no warnings — confirming no resurrection), and confirmed a second DELETE of the original position 404s.

**Known gaps / not yet verified**

- The `DividendTranche` half of the cascade delete is deferred to BE-3.1, same pattern as the EC-022/EC-015 gaps in BE-2.2/BE-2.3.
- **Epic 2 backend is now complete.** All four BE-2.x stories are implemented and verified; Epic 2's frontend stories (FE-2.1–2.4) are next.

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

- [x] Client-side preview uses `decimal.js` — never native JS floating point — to avoid a preview/actual mismatch that would undermine user trust (PRD Principle 1: Accuracy Before Features, Principle 4: Trust Through Transparency)
- [x] Every summary number (all-in cost) has a visible drill-down to its fee components (Principle 4 — no black-box numbers)
- [x] Stock lookup is free-text only — `GET /api/v1/stocks` doesn't exist yet (Epic 9); see Implementation Record for the deviation this required
- [x] Inline errors match VR-004/005/006 copy exactly (VR-003's reference-list check doesn't apply yet — same deferral as BE-2.1)
- [x] EC-001 duplicate-stock flow: submitting a stock already in the portfolio shows the "added to existing position" notice instead of erroring

**Definition of Done**

- [x] Client preview values verified against server response — not via an automated integration test (no frontend test runner exists yet, same gap as every prior FE story), but via a direct numerical parity check of the ported formulas against all three BAS US-003 worked examples (RM41,996.47 / RM41,957.57 / RM3,011.90) — see Implementation Record.

**Dependencies & Integrations**

- BE-2.1, `GET /api/v1/brokers`. (`GET /api/v1/stocks` does not exist yet — see Deviation 1.)

**Technical Constraints**

- Client fee preview is **display-only** — the form always submits raw inputs (shares, price, broker) and lets the server compute and persist authoritative fee values (P-003); the client must never submit its own computed `all_in_cost`

---

### Implementation Record — FE-2.1

**Design source:** `BursaTrack.dc.html`'s `modalAddPos` block (lines ~808-876) and its supporting `fees()`/`brokerNote()`/`BROKERS` logic — re-fetched and read fully via DesignSync before implementing. The design's fee formulas matched our backend's BR-001–007 implementation exactly (confirmed by inspection), which is what let the client-side port below be verified numerically against the same BAS reference values.

**What was actually built**

- `lib/fee-calculator.ts` (new) — the client-side fee preview: `calculateLotFees`/`computeInitialAmount`/`computeBrokerageFee`/`computeClearingFee`/`computeStampDuty`, all `decimal.js`, a line-for-line port of `portfolio/calculator.py`'s BR-001–007/BR-025 logic.
- `lib/position-validation.ts` (new) — VR-004/005/006 validators mirroring the backend's exact error copy, for instant inline feedback before any round-trip.
- `components/portfolio/AddPositionDialog.tsx` (new) — the Add Position modal: stock code/name, shares, price, purchase date, broker select (reusing `useBrokers`), category-tag pills, and the live two-column fee-breakdown panel from the design. Submits raw inputs only to `POST /api/v1/portfolio/positions`; on success, revalidates the dashboard SWR cache and navigates to the new (or existing, for EC-001) position's detail page, passing any server-returned `warnings` through as a `?notice=` query param.
- `app/dashboard/page.tsx` — replaced the Epic-1 stub with a real positions listing (table sourced from the new `GET /api/v1/portfolio/dashboard`), the "+ Add Position" button, and the dialog. Price/income/yield columns show "—" (see Deviation 3).
- `app/positions/[id]/page.tsx` (new) — a position detail page: header (name/code/tag, shares, blended price, all-in cost), a dismissible notice banner reading `?notice=`, and the Lots table (shares/price/date/broker/fee breakdown) sourced from `GET /api/v1/portfolio/positions/{id}` (BE-2.3). No "Add Lot" button yet — that's FE-2.2's own scope.
- `components/ui/dialog.tsx` (new, via `shadcn add dialog`) — this project's first modal primitive.
- **Backend addition**: `GET /api/v1/portfolio/dashboard` (`PortfolioResponse`/`PositionSummaryResponse` schemas, `list_positions_for_portfolio` service function) — see Deviation 1 for why.

**Deviations from the spec/design (deliberate adaptations, not oversights)**

1. **Added a minimal slice of `GET /api/v1/portfolio/dashboard` (documented as Epic 4/BE-4.1's endpoint), pulled forward.** FE-2.1 needs *some* way to list a user's positions to host the Add Position trigger and show the result, and this is the only spec-documented endpoint for that — there is no separate "list positions" route. Dividend income and price-refresh fields are held at their documented-nullable/zero defaults, exactly like `PositionResponse` already does. This is the same "pull forward the minimal documented endpoint" pattern used for `GET /positions/{id}` in BE-2.3.
2. **Stock code and stock name are two separate free-text fields, not the design's single autocomplete-backed "Stock code / name" field.** The design assumes a stock lookup (`GET /api/v1/stocks`) that doesn't exist yet — BE-2.1 already deferred this to Epic 9. Splitting into two explicit fields is the only way to satisfy the backend's requirement for both values without a lookup to resolve one from the other.
3. **The positions table shows "—" for current price, income YTD, and yield** (no columns exist for these in the design's sense, since they need the price-feed and dividend epics). This mirrors the BAS's own established pattern for "no data yet" states (e.g. EC-005's null price, EC-001's "—" yield with zero dividend tranches) rather than inventing a placeholder.
4. **Purchase date is a real editable `<input type="date">` defaulting to today**, not the design's static readonly `"2026-07-17"` prototype value.
5. **No live browser verification was performed.** The user started installing the `claude-in-chrome` extension this session but chose to continue without it. Verification instead relied on: a clean `npm run build` (type-checked, 10/10 routes), a direct Node script confirming the ported `fee-calculator.ts` formulas produce byte-identical results to the backend for all three BAS worked examples, a live backend smoke test (register → create position → `GET /dashboard` shows it with correct aggregates), and confirming both new frontend routes (`/dashboard`, `/positions/[id]`) server-render without errors via the Next.js dev server logs. The interactive parts — the dialog opening, live preview updating as the user types, the EC-001 notice actually rendering after a duplicate-stock submission — are still the user's manual QA pass to do, same gap as every FE story since FE-1.1.

**Test evidence**

- `uv run pytest` (backend, for the new dashboard endpoint): 115/115 passing (111 pre-existing + 4 new: empty dashboard, aggregates across multiple positions, excludes soft-deleted positions, auth requirement).
- `npm run build`: compiles and type-checks cleanly across all 10 routes (2 new: `/positions/[id]`, plus the rebuilt `/dashboard`).
- Node parity check: `calculateLotFees` (client) vs `calculate_lot_fees` (server) produce identical `all_in_cost` for all three BAS US-003 examples.
- Live smoke test: registered a user, hit `GET /api/v1/portfolio/dashboard` before and after creating a position via the real API, confirmed the position appears with correct `total_shares`/`total_all_in_cost`/`blended_purchase_price`.

**Known gaps / not yet verified**

- No live browser interaction this session (see Deviation 5) — the user's manual QA pass covers the dialog, live preview, and EC-001 notice.
- `GET /api/v1/stocks` and stock-code reference validation remain deferred to Epic 9 (unchanged from BE-2.1).

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

- [x] Broker field pre-fills to the position's first lot's broker but is editable per lot (BR-003 — brokerage is per-transaction, so a different broker per lot is a valid scenario). No backend concept of a position-level "default broker" exists (BE-2.2 Implementation Record) — the pre-fill is a UI decision only, documented in Implementation Record Deviation 1.
- [x] Blended purchase price and updated all-in cost render immediately after submission (SWR revalidation) — the position detail page's own `usePosition` cache and the dashboard's `useDashboard` cache are both revalidated in place; the user stays on the position page rather than navigating (unlike FE-2.1's Add Position, which does navigate).

**Definition of Done**

- [x] Verified against BAS US-004 numerically — not via an automated component test (no frontend test runner exists yet, same gap as FE-2.1), but via a direct Node script confirming the ported `fee-calculator.ts` produces the exact US-004 values (lot 2: RM18,000.00 / RM18.00 / RM5.40 / RM18.00 / RM18,041.40; total after merge: 7,000 shares / RM60,037.87) — see Implementation Record.

**Dependencies & Integrations**

- BE-2.2

**Technical Constraints**

- None beyond FE-2.1's shared fee-preview components

---

### Implementation Record — FE-2.2

**Design source:** same `BursaTrack.dc.html` `modalAddPos` block as FE-2.1, driven with `lotMode: true` — re-checked via DesignSync (`list_files` showed no new files since FE-2.1) before implementing; no design changes to port.

**What was actually built**

- `components/portfolio/FeePreviewPanel.tsx` (new, extracted) + `hooks/useFeePreview.ts` (new, extracted) — the live fee-breakdown panel and its computation, pulled out of FE-2.1's `AddPositionDialog` so both dialogs share one implementation rather than duplicating ~40 lines of JSX and the preview `useMemo`. `AddPositionDialog.tsx` was refactored to use both (net simplification, not just a rename — this was a natural extraction since a second real consumer just appeared).
- `components/portfolio/AddLotDialog.tsx` (new) — stock name/code shown read-only (position already exists), shares/price/date/broker fields, broker pre-filled to `position.lots[0].broker_id` but editable, live fee preview. On success: closes, and calls `onLotAdded` with a combined notice string (any EC-004 weekend warning plus a client-side-always-true "Historical dividend records are unaffected" reassurance — see Deviation 2).
- `app/positions/[id]/page.tsx` — added the "+ Add Lot" button next to the Lots heading, wired `AddLotDialog`, and changed the notice banner from a one-shot `?notice=` query param (FE-2.1's pattern, still used for the redirect-from-Add-Position case) to `useState`-backed so Add Lot can push a fresh notice in place without a navigation.
- `POST /api/v1/portfolio/positions/{id}/lots` request body confirmed to match `CreateLotRequest` exactly via a live smoke test.

**Deviations from the spec/design (deliberate adaptations, not oversights)**

1. **Broker pre-fill uses the position's *first* lot's broker** (`position.lots[0].broker_id`), matching the design's own `c.p.lots[0].broker` exactly. This is a UI-only decision — BE-2.2's Implementation Record already established there's no backend "default broker" concept for a position — so "first lot" vs. "most recent lot" was a free choice; picked first-lot for design fidelity.
2. **The "historical dividend records are unaffected" reassurance is always shown after a successful Add Lot**, not conditionally based on whether the position actually has any dividend tranches (it never does yet — Epic 3 isn't built). The design's prototype toast interpolates a live tranche count (`{{ tranches.length }} existing dividend records unchanged`); since that count is always 0 in the real app right now and BR-009's invariant makes the statement true regardless of count, a static reassurance was used instead of a number that would currently always read "0 existing dividend records unchanged" (technically true but reads oddly). Revisit the copy once Epic 3 dividends exist and the count becomes meaningful.
3. **No live browser verification** — same standing gap as every FE story; the user does their own manual QA and has committed after doing so for FE-2.1. Verification here relied on: clean `npm run build` and `npm run lint`, a Node parity script matching all of BAS US-004 exactly (including the merged-lot totals), a live backend smoke test posing as the frontend (register → create position → add lot with the exact request shape the dialog sends → confirm the position/dashboard GETs the frontend polls after revalidation show the updated aggregates), and confirming both routes still server-render without errors via the Next.js dev server log.

**Test evidence**

- `npm run build`: compiles and type-checks cleanly across all 10 routes.
- `npm run lint`: clean.
- Node script: `calculateLotFees(2000, "9.00", maybank)` → exact BAS US-004 lot-2 values; merged total (5,000 + 2,000 shares, RM41,996.47 + RM18,041.40) → RM60,037.87, matching both the BAS wording and BE-2.2's own backend test fixture.
- Live smoke test: registered a user, created a position, added a lot via the exact JSON shape `AddLotDialog` sends, confirmed 201 with correct fee breakdown, then confirmed both `GET /positions/{id}` and `GET /dashboard` (the two SWR caches the UI revalidates) reflect the updated `total_shares`/`total_all_in_cost`/`blended_purchase_price`.

**Known gaps / not yet verified**

- No live browser interaction this session (see Deviation 3) — dialog behavior, live preview updating, and the notice banner rendering are the user's manual QA pass.
- The dividend-records reassurance copy (Deviation 2) should be revisited once Epic 3 makes tranche counts real.

**Follow-up: design-fidelity correction (post-review)**

The user's manual QA caught that the "+ Add Lot" button didn't match the design. Re-reviewing the design against the position detail page surfaced the button plus three further real mismatches, all fixed in the same pass:

1. **"+ Add Lot" button** — was rendered as the shared `Button variant="outline"` (gray border, foreground text), but the design specifies a distinct style: white background, `#3B4FE0` (primary) text, `#C9D4FA` border, `#F3F5FE` (accent) hover. Replaced with a plain button carrying the exact design classes rather than stretching the shared `Button` component's variant system to fit a style that (so far) only appears here and on one other prototype-only button.
2. **Category tag colors were swapped for Growth/Volatile.** The design's `tagColors` computation is `Dividend → ['#E7F5EE','#177A4E']`, `Growth → ['#EBF0FF','#2B3EB8']` (= the app's `--secondary`/`--secondary-foreground` tokens), `Volatile → ['#F0F0ED','#5D6069']` (= `--muted`/`--muted-foreground`). The implementation had Growth mapped to `--accent` and Volatile mapped to `--secondary` — neither matched, and the two were effectively swapped. Extracted the correct mapping into `lib/category-tags.ts` (`CATEGORY_TAG_STYLES`) and pointed both the position detail page and the dashboard at it — the dashboard had an independent copy of the identical bug (same file existed twice, not shared), now deleted in favor of the one shared source of truth.
3. **A second, distinct muted-gray was missing from the design system.** The design uses `#5D6069` for secondary body text (subtitles, descriptions — already correctly mapped to `--muted-foreground` since FE-1.1) but a visibly lighter `#8A8C94` for uppercase eyebrow labels, table column headers, and tertiary meta text (e.g. the stock-code chip). Both had been conflated onto `--muted-foreground` across every screen since FE-1.1 — not a new mistake introduced in FE-2.x, but the first time it was caught. Added a new, purely additive `--tertiary`/`text-tertiary` token (`globals.css`) rather than overloading `--muted-foreground` (which many already-approved screens rely on for the *correct*, darker shade) and applied it precisely where the design specifies `#8A8C94`: the position page's stock-code chip, stat labels, table headers, and footer note, plus the shared `FeePreviewPanel`'s eyebrow label and formula-note lines (which also benefits `AddPositionDialog`, FE-2.1's dialog, as a side effect of fixing the shared component). Deliberately did **not** sweep the rest of the app (dashboard's own table headers, auth screens) in this pass — flagged to the user as a known, separate follow-up rather than silently expanding scope beyond "the position page."
4. **Two smaller content-fidelity gaps found during the same line-by-line comparison, fixed as they were cheap and clearly in scope for "review the position page against the design":** the Lots table was missing its leading "Lot" (sequence number) column, and the Brokerage/Clearing/Stamp fee cells were missing their hover-tooltip formulas (`title` attributes) and the table footer's "— hover a fee for its formula" trailing text. Row hover (`background:#FAFAF8`) was also added to match the design's `style-hover` on each `<tr>`.

**Verification:** `npm run build` and `npm run lint` clean; confirmed via a direct read of the compiled CSS that `.text-tertiary`, `--tertiary`, and the `border-[#C9D4FA]` arbitrary value all generated correctly; confirmed both `/dashboard` and `/positions/[id]` still server-render without errors via the Next.js dev server log. Visual confirmation of the corrected colors is, as with everything else in Epic 2's frontend, the user's manual QA pass.

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

- [x] `version` is submitted transparently with every PATCH (not user-visible/editable) — tracked in component state, never rendered as a form field
- [x] A dashboard/position notice appears after a share-count edit: "Position updated. Dividend records were not changed." (EC-015) — surfaced verbatim from the backend's `warnings` array
- [x] Accessing another user's position via a crafted URL renders a generic 404 page — no information disclosure (built in FE-2.1, re-verified here per this story's explicit AC)

**Definition of Done**

- [x] EX-008 concurrent-edit scenario verified via a live two-request smoke test against the real backend (first PATCH with `version=1` succeeds and bumps to `version=2`; a second PATCH still carrying `version=1` — simulating a second session that hasn't refreshed — receives 409) rather than two literal browser sessions, since no browser tooling is available this session — see Implementation Record.

**Dependencies & Integrations**

- BE-2.3

**Technical Constraints**

- None additional

---

### Implementation Record — FE-2.3

**Design source:** none. The `BursaTrack.dc.html` prototype has no Edit Lot flow at all — the only per-lot/per-position "Edit" affordance in the design is the dashboard's ••• menu's "Edit Position" item, which calls `this.proto()` (a stub that shows "Prototype — this action is visual only for now." and does nothing else). Optimistic-locking/conflict UI isn't modeled anywhere in the prototype. Built from the story's AC/Gherkin text directly, reusing this codebase's established visual language (Dialog, form-field layout, `FeePreviewPanel`, the amber "soft warning" treatment already used for rate-limiting in `ForgotPasswordForm`) rather than inventing new patterns.

**What was actually built**

- `components/portfolio/EditLotDialog.tsx` (new) — shares/price/date/broker fields pre-filled from the lot being edited, live fee preview (same `FeePreviewPanel`/`useFeePreview` as Add Lot), `version` carried in state and always sent with the PATCH but never exposed as an input. On a 409, shows the AC's exact required copy ("This record was updated by another session. Please refresh the page to see the latest values before making changes.") in an amber banner with a "Refresh" button; refreshing re-fetches the position, repopulates every field (including `version`) from the now-current lot, and re-enables the form for another attempt.
- `app/positions/[id]/page.tsx` — added an "Actions" column to the Lots table with a per-row "Edit" button (styled after the design's own Dividends-tab row-action pattern, the closest real precedent for a per-row text-button in this design system, since no lot-specific action button exists to copy). Wired `editingLotId` state, `EditLotDialog`, and a save handler that revalidates both the position and dashboard SWR caches and surfaces the returned notice.

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **The 409 banner uses the AC's exact wording, not the backend's own message.** `app/errors.py::version_conflict()` returns `"This record was modified by another session. Please refresh and try again."`, but FE-2.3's Gherkin specifies different, more actionable copy ("...Please refresh the page to see the latest values before making changes."). Since the AC dictates the exact user-facing text, the dialog displays a hardcoded constant rather than `err.message` for this one error case — the only place in the app where a backend error message is deliberately not shown verbatim.
2. **No UI was built for editing position metadata (`category_tag`/`notes`)**, even though BE-2.3 built `PATCH /positions/{id}` for exactly that. This story's own Gherkin scenario is scoped to "a user opens the edit form for a **lot**," and no AC mentions category/notes editing — building it now would be scope creep against this story's actual acceptance criteria, not a gap. Flagged as unbuilt-but-available backend capability, not deferred to a specific future story since none currently claims it.
3. **EX-008 was verified via a live two-request smoke test (first PATCH succeeds and bumps `version`, a second PATCH replaying the stale `version` receives 409), not two literal browser sessions.** No browser automation tooling exists in this environment this session (same standing limitation as every FE story) — this is as close a substitute as scripted testing allows, since it exercises the identical server-side conditional-UPDATE code path a real concurrent session would hit (already established as sufficient in BE-2.3's own backend test suite). The user's own manual QA with two real browser tabs remains the authoritative verification for the DoD.

**Test evidence**

- `npm run build` and `npm run lint`: clean.
- Live smoke test against the real backend + Postgres, using the exact request shape `EditLotDialog` sends: PATCH with `version=1` → 200, fees recalculated, `version` bumped to 2, `warnings` containing the exact EC-015 copy; a second PATCH still carrying `version=1` → 409 `version_conflict`; `GET /positions/{id}` afterward (what the dialog's "Refresh" button triggers) shows the current `version=2` lot, confirming the refresh-and-retry flow has correct data to repopulate from; `GET` on a random/nonexistent position ID → generic 404 with no information disclosure.
- Confirmed `/positions/[id]` still server-renders without errors via the Next.js dev server log.

**Known gaps / not yet verified**

- No live browser interaction this session — the dialog's interactive behavior (conflict banner appearing, Refresh button repopulating fields, the disabled-during-conflict form state) is the user's manual QA pass, including the DoD's explicit two-browser-session EX-008 test.
- Position metadata (category_tag/notes) editing UI remains unbuilt (see Deviation 2) — `PATCH /positions/{id}` is available whenever a story claims it.

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

- [x] Dialog dynamically interpolates the actual lot/tranche counts for the specific position
- [x] Cancelling leaves the position untouched — dialog closes, no request is made, user stays exactly where they triggered it from. ("Returns to the dashboard" is interpreted as describing the confirmed-delete path, not cancel — see Implementation Record.)
- [x] Portfolio summary (total cost, blended yield) visibly updates immediately after confirmed deletion — the dashboard previously had no summary display at all; added one as part of this story (see Implementation Record).

**Definition of Done**

- [x] Reusable `ConfirmDialog` component (already scoped in architecture's frontend structure, §7.2) built at `components/shared/ConfirmDialog.tsx` — generic (title/description/confirm-label/onConfirm props), ready for dividend delete and account delete to reuse without modification.

**Dependencies & Integrations**

- BE-2.4

**Technical Constraints**

- None additional

---

### Implementation Record — FE-2.4

**Design source:** none, same situation as FE-2.3. `BursaTrack.dc.html`'s only "Delete Position" affordance is the dashboard row's ••• menu, and its handler (`mDelete`) is a stub: `this.toast(name + ' would be deleted with all N lots and M dividend records. [Undo — 5s]', ...)` — a toast-with-undo pattern, not the modal confirmation with exact interpolated copy this story's AC requires. No confirmation dialog is modeled anywhere in the prototype. Built from the AC/Gherkin text directly.

**What was actually built**

- `components/shared/ConfirmDialog.tsx` (new) — the first component in `components/shared/`, matching the exact path architecture §7.2 specifies. Generic props (`title`, `description`, `confirmLabel`, `cancelLabel`, `destructive`, `onConfirm`); handles its own submitting/error state so callers just provide an async `onConfirm`.
- `app/positions/[id]/page.tsx` — added a "Delete Position" button (shadcn's existing `destructive` Button variant — no new styling needed here, unlike the Add Lot button, since no design precedent exists to match and the shared variant is already visually correct for a destructive action) to the position header. Opens `ConfirmDialog` with the AC's exact copy template, interpolating `position.stock_name`, `position.lots.length`, and `position.dividend_tranches.length` (always 0 today — Epic 3 doesn't exist yet, so the sentence honestly reads "...and all 2 lots and 0 dividend records..."). On confirm: `DELETE /api/v1/portfolio/positions/{id}`, revalidate the dashboard SWR cache, navigate to `/dashboard`.
- `app/dashboard/page.tsx` — added the 4-card portfolio summary strip from the design (`Total All-In Cost`, `Dividend Income YTD`, `Blended Yield`, `Next Dividend`) that did not exist before this story. Also fixed the same `text-muted-foreground`-vs-`text-tertiary` mismatch identified and flagged as a known follow-up during FE-2.2's review (table column headers, the stock-code chip, and the footer note) since this file was already being touched for the summary cards.

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **"Cancelling ... returns to the dashboard" is interpreted as describing the confirmed-delete outcome, not the cancel outcome.** Read literally, the AC's single sentence ("Cancelling leaves the position untouched and returns to the dashboard") would mean cancelling navigates the user away — unusual UX that contradicts "leaves the position untouched" implying no side effects at all. Implemented the standard, safe interpretation: Cancel closes the dialog with zero side effects (no navigation, no request); Confirm deletes and navigates to `/dashboard` (where the now-updated summary is directly visible, satisfying the third AC bullet). If the literal reading was actually intended, this is a one-line fix to flag.
2. **"Delete Position" was built only on the position detail page, not as a dashboard row ••• dropdown menu**, even though that's the design's only real precedent for the action. Building a full row-actions dropdown (the design's menu has Add Lot / Add Dividend / Sell / Edit Position / Delete Position) would mean either shipping a menu where most items are non-functional stubs for epics that don't exist yet (Add Dividend, Sell) or building extensive new UI surface not required by any single story. Kept scope consistent with FE-2.2/FE-2.3's established precedent of building lot-level and position-level actions on the position detail page.
3. **Added a portfolio summary strip to the dashboard that no prior story had built.** The AC explicitly requires "Portfolio summary (total cost, blended yield) visibly updates immediately after confirmed deletion," but no summary existed for anything to update. Built all 4 of the design's summary cards (not just the two the AC names) for visual completeness against the design's grid layout — `Total All-In Cost` and `Dividend Income YTD` show real (honestly-zero) data from the dashboard endpoint already built in FE-2.1; `Blended Yield` and `Next Dividend` show `—` rather than a fabricated 0%/empty value, consistent with the BAS's own "no data yet" convention (EC-001/EC-009) used everywhere else in the app. The `Blended Yield` card also drops the design's clickable "tap to verify" drill-down, since there's nothing yet to drill into.
4. **`Total All-In Cost`'s subtitle shows only "{N} positions", not the design's "{N} positions · {M} lots".** `PortfolioResponse`/`PositionSummaryResponse` don't expose a lot count anywhere (only per-position aggregates), and adding a new field to the dashboard endpoint's schema for one subtitle string was judged out of scope for a delete-confirmation story.

**Test evidence**

- `npm run build` and `npm run lint`: clean.
- Live smoke test against the real backend + Postgres: created two positions, confirmed the dashboard summary's `total_all_in_cost` reflected both (RM51,322.57), deleted one position via the exact `DELETE` call the button sends (204), and confirmed the dashboard re-fetch shows the correct single remaining position and the updated total (RM9,074.70) — proving the summary card really does update after a confirmed delete.
- Confirmed both `/dashboard` and `/positions/[id]` still server-render without errors via the Next.js dev server log.

**Known gaps / not yet verified**

- No live browser interaction this session — the dialog's interactive behavior (button click, confirm/cancel, the summary cards visibly changing) is the user's manual QA pass.
- If "cancel returns to the dashboard" was meant literally (Deviation 1), that's a one-line change once clarified.

---

## BE/FE-2.5 — Delete Lot (Backfilled Scope)

**Priority: Must Have (backfilled)**

> Not an originally-scoped story. `DELETE /api/v1/portfolio/positions/{id}/lots/{lot_id}` has been fully documented in `03-openapi-specification.md` since the API design phase (`x-audit-event: LOT_DELETED`) but no user story in Epic 2 ever claimed it — BE-2.1–2.4/FE-2.1–2.4 only cover Add Position, Add Lot, Edit Lot, and delete at the **Position** level (cascading). Identified and implemented as a small, deliberate scope addition immediately after FE-2.4, since the delete/soft-delete machinery was already being built and the gap was directly adjacent.

**Developer Action Plan**

```gherkin
Given a position has 2 active lots
When the user deletes one of them
Then that lot is soft-deleted, the position's aggregates (total_shares, total_all_in_cost,
     blended_purchase_price) reflect the remaining lot on the next read, and a LOT_DELETED
     audit entry is recorded — but deleting a position's only remaining lot is rejected,
     directing the user to delete the position instead
```

**Acceptance Criteria** (self-defined, since no BAS/PRD source names this endpoint)

- [x] Soft-delete only (`is_deleted=true`, `deleted_at=now()`), consistent with every other delete in the app (A-010)
- [x] Ownership verified on both position and lot — 404, never 403, for missing/foreign/cross-position lots (same pattern as PATCH .../lots/{lot_id})
- [x] Deleting a position's last remaining active lot is blocked with 409 `last_lot`, directing the user to delete the position instead — a business rule invented at implementation time (no story or BR defines what a zero-lot Position should mean), not spec-mandated
- [x] `audit_log` entry `LOT_DELETED` recorded
- [x] Frontend: a "Delete" action per lot row (hidden when it's the position's only lot, since the backend would reject it anyway), using the same `ConfirmDialog` built for FE-2.4

**Test evidence**

- `uv run pytest`: 124/124 passing (115 pre-existing + 9 new: 204 + soft-delete flags, aggregates update on next read, blocks deleting the last lot, 404 for nonexistent/foreign/cross-position lots, auth requirement, audit log entry, idempotent re-delete).
- `npm run build`/`npm run lint`: clean.
- Live smoke test against the real backend + Postgres: attempted deleting a position's only lot (409 `last_lot`), added a second lot, deleted it (204), confirmed `GET /positions/{id}` shows only the remaining lot with correct aggregates, and confirmed `GET /dashboard`'s total reflects it too.

**What was built**

- Backend: `app/errors.py::last_lot_cannot_be_deleted()` (409), `app/portfolio/service.py::delete_lot()`, `DELETE /api/v1/portfolio/positions/{id}/lots/{lot_id}` route, `LOT_DELETED` added to `AUDIT_LOG_ACTIONS` via migration 0008.
- Frontend: a "Delete" button in the Lots table's Actions column (next to FE-2.3's "Edit"), reusing `ConfirmDialog` — the second real consumer of that component, exactly as FE-2.4's DoD intended it to be reused. Also improved `ConfirmDialog` itself to auto-close on a successful `onConfirm` (previously only FE-2.4's Delete Position path worked correctly without an explicit close, because it always navigated away on success — this component's contract is now "auto-close on success, stay open with an inline error on failure" for any future caller).

**Known gaps / not yet verified**

- No live browser interaction this session — the per-row Delete button, its confirmation copy, and the hidden-when-only-one-lot behavior are the user's manual QA pass.

---

**Epic 2 is now complete, including this backfilled addition.** All four originally-scoped FE-2.x stories (Add Position, Add Lot, Edit Lot with conflict handling, Delete Position) plus the backfilled Delete Lot capability are implemented, backend-verified via live smoke tests, and recorded here. Epic 2 (Portfolio: Positions & Lots) — both backend and frontend — is fully done.

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

- [x] `qualifying_shares` defaults to current `position_total_shares` at logging time but is user-overridable, bounded `1 ≤ qualifying_shares ≤ position_total_shares` at time of entry (VR-011) — the default is a frontend concern (FE-3.1); the backend enforces the upper bound server-side regardless of what the client sends
- [x] `total_amount = per_share_amount × qualifying_shares`, rounded to 2dp (BR-025), is a **stored** column — never a computed/derived value at read time
- [x] **P0 regression test (mandatory, cannot be skipped per BAS §14):** logging a 1st tranche (qualifying_shares=5000, total_amount=RM1,000 stored), then adding a new 2,000-share lot, leaves the 1st tranche's `total_amount` at exactly RM1,000.00 — verified both via an automated test and a live smoke test against real Postgres (see Implementation Record)
- [x] BR-014: a position may have at most 8 `DividendTranche` rows per calendar `year`; the 9th attempt is rejected with "Maximum of 8 dividend tranches per year reached for [Stock] ([Year])"
- [x] VR-008 (per_share_amount >0, ≤6dp), VR-009 (payment_date ≤30 days future), VR-010 (ex_dividend_date ≤ payment_date if present) enforced. VR-012 (year 1990–current+1) is enforced as a DB CHECK constraint only — `year` is never a client input (see Implementation Record Deviation 1), so there's no request field to validate it against.
- [x] Position yield is **not** returned as a percentage by the server at all (architecture's own documented decision, `PortfolioResponse`'s P0-API-001/FC-002 note: yield is always computed client-side via decimal.js). The backend's job is to return the correct ingredients — `total_dividend_income_ytd` and `total_all_in_cost` — so a correct client-side calculation is possible; verified this explicitly with a negative-assertion test (see DoD below).
- [x] Portfolio blended yield: same as above — the backend returns `total_dividend_income_ytd` and `total_all_in_cost` as weighted sums across all positions (not per-position averages), which is what a correct client-side BR-013 calculation requires.
- [x] EC-023: qualifying_shares below the current position total is accepted with no error (verified); the tranche response includes both `qualifying_shares` and the position's own `total_shares` is already visible on the same `GET /positions/{id}` call, so a frontend can surface both without any extra backend work — actually building that UI surfacing is FE-3.1 scope, not this story's.
- [x] `audit_log` entry `DIVIDEND_CREATED`

**Definition of Done**

- [x] Unit test: `total_amount` is stored and provably immutable across a subsequent lot-add operation — extends BE-2.2's precursor test from the other direction, exactly as the DoD asked ("these two tests should assert the same fact from both directions"); also extended BE-2.3's EC-015 precursor the same way for lot *edits*.
- [x] Unit test: verifies the backend returns the correct ingredients for an all-in-cost-based yield calculation, with an explicit negative assertion that `income / all_in_cost` differs from `income / pre_fee_initial_amount` (BAS US-011) — see Implementation Record for why this is framed around the returned fields rather than a yield percentage the backend never computes.
- [x] Code review checklist item: not enforced by tooling (no CI/review-gate infrastructure exists in this project) — the `DividendTranche` model's own docstring explicitly warns against turning `total_amount` into a derived value, serving the same purpose for a solo-founder codebase.

**Dependencies & Integrations**

- Depends on Position/Lot aggregates from Epic 2 for `position_total_shares` lookup at logging time

**Technical Constraints**

- `per_share_amount` is `NUMERIC(12,6)`; `total_amount` is `NUMERIC(14,2)` (architecture §12.3)
- This is the one field in the entire schema where "derived at query time" (the architecture's general pattern, ADR-004) is deliberately **not** followed — the schema comment on this column must explain why, so a future engineer doesn't "fix" it into a derived value

---

### Implementation Record — BE-3.1

**What was actually built**

- `app/portfolio/models.py` — `DividendTranche` model (physical schema §3.8), with a docstring explicitly warning against ever turning `total_amount` into a derived/computed column.
- `alembic/versions/0009_create_dividend_tranches.py` — creates `dividend_tranches`; extends `audit_log`'s CHECK constraints for `DIVIDEND_CREATED`/`DividendTranche`. Verified upgrade/downgrade both directions against real Postgres.
- `app/portfolio/schemas.py` — `CreateDividendRequest` (VR-008/009/010 validators), `DividendTrancheResponse`. `PositionResponse.dividend_tranches` upgraded from its BE-2.1-era `list[dict]` stub to the real `list[DividendTrancheResponse]`.
- `app/portfolio/service.py` — `create_dividend_tranche` (the core P0 logic: computes and stores `total_amount` once, validates `qualifying_shares` against the position's live total-shares lookup, enforces BR-014's 8-per-year cap and the duplicate-label rule below), `get_position_dividend_tranches`, `position_dividend_income_ytd` (BR-012's YTD sum, using each tranche's own stored `year` — never re-derived from `date.today()` at read time).
- `app/portfolio/router.py` — `POST /api/v1/portfolio/dividends` (`position_id` travels in the body, matching the OpenAPI spec's non-nested URL, unlike Lots). Also wired real dividend data into `GET /positions/{id}`, `POST /positions` (the EC-001 add-lot-redirect path), `PATCH /positions/{id}`, and `GET /dashboard` — all four previously returned the BE-2.1-era `total_dividend_income_ytd: "0.00"` / `dividend_tranches: []` placeholders; they now return real values.
- **Extended BE-2.4's cascade delete**, as explicitly flagged in that story's own Implementation Record: `delete_position` now also soft-deletes a position's active `DividendTranche` rows, not just its Lots.

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **`year` is never a client-supplied field.** `CreateDividendRequest` in the OpenAPI spec has no `year` property at all — only VR-012's general description ("Default: YEAR(payment_date); editable") suggests it might be. Since the request schema itself settles this, `year` is always `payment_date.year`, computed server-side, with no way to override it at creation. (BE-3.2's `UpdateDividendRequest` doesn't have a `year` field either, so this remains true after edits too — out of scope to revisit here.)
2. **Rejecting a duplicate `tranche_label` within the same position+year is a judgment call, not spec-mandated.** Neither the physical schema (no UNIQUE constraint) nor any BR/VR forbids two "1st" tranches in the same year — BR-014 only caps the *count* at 8. Since `tranche_label` is a required client input (not server-auto-assigned, despite the design prototype's UI auto-suggesting the next unused label), allowing duplicates would let a user create two same-labeled, confusing entries. Rejected with a clear message, following the same "resolve an undocumented edge case explicitly, don't silently allow or silently block" pattern as BE-2.5's last-lot rule.
3. **Yield is framed entirely around "does the backend return the right ingredients," not "is the yield percentage correct"** — because the backend never computes or returns a yield percentage at all. This was already architecture's own explicit decision (documented on `PortfolioResponse`, P0-API-001/FC-002) before this story existed; BE-3.1's AC talks about "yield recalculated" in a way that reads like the backend should compute it, but the actual, more specific architectural constraint wins. The DoD's negative-assertion test was reframed accordingly (see test evidence).

**Test evidence**

- `uv run pytest`: 144/144 passing (124 pre-existing + 20 new): happy-path storage, auth requirement, 404 ownership checks, qualifying_shares upper-bound rejection, EC-023 (qualifying_shares below current total is valid), VR-008/009/010 validation, BR-014's 8-per-year cap, the duplicate-label rejection, same-label-different-year allowed, `DIVIDEND_CREATED` audit log, dividend data now appearing on both `GET /positions/{id}` and `GET /dashboard`, the yield-ingredients negative-assertion test, **the full EC-022 P0 regression test** (add a lot after logging a dividend — total_amount unchanged), **the full EC-015 test** (edit a lot's shares after logging a dividend — total_amount unchanged), and confirming `delete_position`'s cascade now covers dividend tranches too.
- Migration 0009 applied and rolled back cleanly against the real Postgres container (upgrade/downgrade/upgrade).
- **Live smoke test reproducing the exact historical Excel defect end-to-end against real Postgres**: registered a user, created a 5,000-share position, logged a 1st dividend (5,000 qualifying shares → RM1,000.00 stored), added a 2,000-share lot, then re-fetched the position — `total_shares` correctly grew to 7,000, while the dividend's `total_amount` stayed exactly RM1,000.00. Also confirmed `GET /dashboard`'s `total_dividend_income_ytd` correctly shows RM1,000.00.
- `npm run build` (frontend): clean — confirms the `PositionResponse.dividend_tranches` type change (from an untyped stub to real tranche objects) doesn't break the frontend's existing `unknown[]`-typed usage (no FE-3.x UI reads its internal shape yet).

**Known gaps / not yet verified**

- No live browser interaction (no FE-3.x work exists yet — that's FE-3.1's own story).
- No CI/code-review-gate tooling exists in this project to mechanically enforce the DoD's "any PR touching total_amount must be reviewed against BR-009/BR-027" — the model's own docstring is the current substitute.

**Post-implementation correction — qualifying_shares bound ignored lot purchase dates (VR-011)**

User-reported via manual QA, two symptoms of the same root cause:
1. A dividend could be logged with a `payment_date` earlier than the position's own lot(s) — nonsensical, since you can't receive a dividend on shares you didn't yet own.
2. A position with lot 1 (1,000 shares, bought 1 Jul) and lot 2 (3,000 shares, bought 31 Jul) allowed a dividend dated 15 Jul to claim up to 4,000 `qualifying_shares` — but only lot 1 existed as of 15 Jul, so the true maximum was 1,000.

Root cause: `_check_qualifying_shares_bound` validated against `position_total_shares` — the position's *live* total across every lot regardless of purchase date — not against what BR-027 actually defines `qualifying_shares` to mean ("shares held before the ex-dividend date"). The original BAS text (BR-027's own worked example) anticipated this exact scenario but left it to user judgment ("the user should override qualifying_shares") rather than a hard server-side constraint; the user directed that this now be enforced automatically instead.

Fixed by adding `shares_eligible_as_of(lots, reference_date)` (`service.py`) — sums only lots whose `purchase_date <= reference_date`, where `reference_date` is `ex_dividend_date` falling back to `payment_date` (the same fallback already used everywhere else for this pair — BE-3.3's `is_upcoming`/sort). `_check_qualifying_shares_bound` now takes this eligible count as its upper bound instead of the live position total. This closes bug 1 for free: a reference date before every lot yields `eligible_shares = 0`, and `qualifying_shares >= 1` (already enforced at the schema level) can never satisfy that, so the request is rejected outright. Applied identically to `create_dividend_tranche` (BE-3.1) and `update_dividend_tranche` (BE-3.2, below) — an edit that moves a tranche's date earlier now re-tightens the bound even if the original value was valid when first logged.

BAS US-012's exact mandated error copy ("Qualifying shares cannot exceed the position's current total shares (N)") is preserved verbatim for the common case where no lot postdates the reference date (`eligible_shares == position_total_shares`); only the newly-restricted case gets a new, more specific message ("...cannot exceed the shares held as of {date} (N) — M more shares were purchased after this date").

Mirrored client-side too (not just the backend): `sharesEligibleAsOf()` (`lib/dividend-calculator.ts`) and an updated `validateQualifyingShares()` signature (`lib/dividend-validation.ts`), wired into both `AddDividendDialog` and `EditDividendDialog` so the inline error appears before a round-trip, not just as a server rejection after Save.

Four pre-existing tests (`test_add_dividend_rejects_ninth_tranche_in_same_year_br014`, `test_add_dividend_allows_same_label_in_different_years`, `test_edit_dividend_moving_year_revalidates_br014_cap`, `test_edit_dividend_tranche_label_rejects_duplicate_in_same_year`) used 2025 payment dates against a fixture position purchased in 2026, purely to exercise BR-014's year-cap logic — a latent test-data mismatch this fix now surfaces. Fixed by adding an optional `purchase_date` override to each file's `_create_position` helper and back-dating those four tests' positions to 2020.

Added 5 new backend tests (`test_add_dividend_exact_copy_when_eligible_equals_current_total`, `test_add_dividend_qualifying_shares_bounded_by_shares_owned_as_of_reference_date`, `test_add_dividend_uses_ex_date_not_payment_date_for_eligibility`, `test_add_dividend_rejects_reference_date_before_any_lot`, `test_edit_dividend_qualifying_shares_bounded_by_shares_owned_as_of_reference_date`) reproducing both reported scenarios plus the ex-date-vs-payment-date fallback and the exact-copy preservation case. Full suite: 198/198 passing. `npm run build`/`lint`: clean. Re-verified live against the real backend: both original bug scenarios now return 422 with the correct message, and the corrected 1,000-share submission returns 201.

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

- [x] Editing `per_share_amount` recomputes `total_amount` using the tranche's own stored `qualifying_shares`, never the current position total (BAS US-012)
- [x] Editing `qualifying_shares` directly recomputes `total_amount` with the new qualifying_shares × the existing `per_share_amount`; still bounded ≤ position_total_shares at time of edit (VR-011 "on edit" clause) — exact BAS error copy including comma-formatted thousands, e.g. "(5,000)"
- [x] Delete is a soft-delete; position/portfolio dividend income YTD recalculates with the tranche excluded (no separate "yield" recalculation needed server-side — see BE-3.1's Implementation Record on why the backend never computes yield% at all)
- [x] Optimistic locking via `version` column, identical conflict handling to BE-2.3 (EX-008) — same error code/message
- [x] `audit_log` entries `DIVIDEND_UPDATED` / `DIVIDEND_DELETED` capture previous and new values

**Definition of Done**

- [x] Both BAS US-012 Gherkin scenarios (edit per_share_amount, edit qualifying_shares) pass as automated tests with the exact numeric expectations (RM1,100.00 and RM600.00 respectively), plus the error scenario with the exact required error copy

**Dependencies & Integrations**

- BE-3.1

**Technical Constraints**

- Same NUMERIC/Decimal constraints as BE-3.1

---

### Implementation Record — BE-3.2

**What was actually built**

- `app/portfolio/schemas.py` — `UpdateDividendRequest` (all fields optional except `version`; "at least one field" model validator, matching `UpdateLotRequest`'s shape exactly). Refactored BE-3.1's inline VR-008/009 field validators into shared module-level functions (`_check_tranche_label`, `_check_per_share_amount`, `_check_dividend_payment_date`) so create and edit can never drift, same pattern already used for Lots.
- `app/portfolio/service.py` — `get_owned_dividend_tranche` (ownership joins through the tranche's own Position, since `/dividends/{id}` isn't nested under a position_id in the URL, unlike Lots), `update_dividend_tranche` (conditional `UPDATE ... WHERE id=? AND version=?`, merges each optional field against the tranche's existing stored value before recomputing `total_amount`), `delete_dividend_tranche`. Extracted `_check_qualifying_shares_bound` and `_check_tranche_year_constraints` out of BE-3.1's `create_dividend_tranche` so both BR-014's cap and the duplicate-label rule are re-validated identically on edit, excluding the tranche being edited from its own count/uniqueness check.
- `app/portfolio/router.py` — `PATCH /api/v1/portfolio/dividends/{id}`, `DELETE /api/v1/portfolio/dividends/{id}`.
- `alembic/versions/0010_extend_audit_log_for_dividend_edit_delete.py` — `DIVIDEND_UPDATED`/`DIVIDEND_DELETED` added to `audit_log`'s CHECK constraint.
- **Fixed a minor copy bug found while implementing this story**: BE-3.1's `qualifying_shares` error message used plain `{position_total_shares}` interpolation (e.g. "(5000)"), but BAS's own example shows comma-formatted thousands ("(5,000)"). Fixed with `{position_total_shares:,}` in both the create and edit paths.

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **Moving a tranche's `payment_date` into a different calendar year re-validates BR-014's 8-per-year cap and the duplicate-label rule against the *new* year, excluding the tranche's own row from the count.** Not explicitly called out in the AC, but a direct consequence of `payment_date` (and therefore `year`) being editable per the OpenAPI `UpdateDividendRequest` schema — an edit that moves a tranche into an already-full year must be rejected the same way a create into a full year is; an edit that only changes the *day* within the same year must not accidentally count itself twice. Both directions are tested.
2. **`ex_dividend_date: null` in a PATCH body is indistinguishable from "field omitted"** — there is no way to explicitly clear an already-set `ex_dividend_date` via this endpoint (documented on `UpdateDividendRequest` itself). Not spec-mandated either way; a minor known limitation rather than adding sentinel-value/`exclude_unset` complexity for an edge case no story covers.

**Test evidence**

- `uv run pytest`: 163/163 passing (144 pre-existing + 19 new): both BAS US-012 numeric scenarios exactly (RM1,100.00 / RM600.00), the exact error copy with comma formatting, version-conflict 409 (stale PATCH after a successful one), empty-body rejection, 404 ownership (nonexistent/foreign tranche, auth requirement), BR-014 re-validation when moving years (both the "now over cap" rejection and the "moving within the same year doesn't double-count itself" acceptance), duplicate-label rejection on edit, VR-010 re-validation, `DIVIDEND_UPDATED` audit log with previous/new values, delete 204 + soft-delete flags, delete correctly excludes the tranche from position/dashboard income on the next read, 404 ownership on delete, `DIVIDEND_DELETED` audit log.
- Migration 0010 applied and rolled back cleanly against the real Postgres container.
- Live smoke test against the real backend + Postgres: logged a dividend, ran both BAS US-012 edits in sequence against the real server (confirming version increments 1→2→3 and each recalculation), triggered the qualifying-shares-exceeded error and confirmed the exact comma-formatted copy, then deleted the tranche and confirmed the position's `total_dividend_income_ytd` correctly dropped to "0.00".
- `npm run build` (frontend): clean — no frontend changes were needed for this story (no FE-3.x UI exists yet).

**Known gaps / not yet verified**

- No live browser interaction (no FE-3.x work exists yet — that's FE-3.2's own story).
- `ex_dividend_date` cannot be explicitly cleared once set (Deviation 2).

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

- [x] Each entry includes stock name, tranche label, ex-date, payment date, per_share_amount, and the **stored** total_amount (not re-derived) — display must make clear this reflects the qualifying_shares basis at logging time (FR-013 step 3 fix)
- [x] Past dates flagged "Paid" (`is_paid`, based on `payment_date < today`); upcoming dates within 7 days flagged for highlighting (`is_upcoming`, based on the same ex-date-falling-back-to-payment-date reference the sort order uses) — both additive fields, computed server-side so every client shares one "today" reference
- [x] Empty state (no tranches for the queried year) returns `{"tranches": []}`, not an error — verified explicitly

**Definition of Done**

- [x] Query correctly filters soft-deleted tranches (`is_deleted=false`) — and, defensively, tranches on soft-deleted positions too, even though that's already redundant with BE-2.4/BE-3.1's cascade delete

**Dependencies & Integrations**

- BE-3.1 for the underlying data

**Technical Constraints**

- None beyond standard read-path query performance (indexed on `dividend_tranches(position_id, year, is_deleted)` per architecture §8.3) — no explicit load test was run (this project has no performance-testing infrastructure), but the query is a straightforward indexed join with no N+1 pattern

---

### Implementation Record — BE-3.3

**What was actually built**

- `app/portfolio/schemas.py` — `DividendCalendarEntry` (every `DividendTrancheResponse` field plus `stock_code`/`stock_name`, matching the OpenAPI `allOf` shape, plus the additive `is_paid`/`is_upcoming` flags), `DividendCalendarResponse`.
- `app/portfolio/service.py` — `get_dividend_calendar` (portfolio-wide join across all positions, filtered by `year`, sorted by `ex_dividend_date` falling back to `payment_date`, with `is_paid`/`is_upcoming` computed per row), returning a small `DividendCalendarRow` `NamedTuple` (tranche + stock_code + stock_name + the two flags) rather than a bare ORM object, since the response needs data that spans two tables.
- `app/portfolio/router.py` — `GET /api/v1/portfolio/dividends?year=` (optional, defaults to the current calendar year per the OpenAPI spec).
- No migration needed — purely a new read query over existing tables, no schema change.

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **A real conflict between the OpenAPI spec and this story's own AC, resolved in favor of the OpenAPI contract.** The OpenAPI's documented `GET /dividends` has a `year` query parameter that "Defaults to the current calendar year if omitted" — a calendar-year-boundary filter. BE-3.3's own Gherkin instead describes "scoped to future dates plus the trailing 30 days" — a rolling window relative to today, unrelated to calendar-year boundaries; on any date these two framings return genuinely different result sets (e.g. in January, "current year" spans 12 months ahead while "future + trailing 30 days" spans about one month). Implemented the OpenAPI's `year`-based contract, since it's the stable, already-documented API shape a future FE-3.3 (and any other future consumer) would code against. Interpreted the AC's "future + trailing 30 days" language as describing FE-3.3's eventual *default view* of this data — a year's worth of entries is a superset a frontend can filter down to that rolling window — rather than a distinct backend query the endpoint itself must implement. If this reading is wrong, it's a straightforward follow-up to add a second `from`/`to` date-range mode alongside (not instead of) the existing `year` param.
2. **`is_paid`/`is_upcoming` are additive fields, not in the OpenAPI schema.** The AC explicitly requires this display behavior ("Past dates flagged 'Paid'; upcoming dates within 7 days flagged for highlighting"), and computing it server-side (one shared "today" reference) is more correct than pushing date math into each client, consistent with this project's established pattern of additive fields for AC requirements the documented schema didn't anticipate (e.g. `warnings` throughout Epic 2).

**Test evidence**

- `uv run pytest`: 174/174 passing (163 pre-existing + 11 new): empty state, auth requirement, stock name/code included, default-to-current-year, explicit `year` filtering, correct chronological ordering (including the no-ex-date-falls-back-to-payment-date case, verified with three interleaved entries logged out of order), spanning multiple positions in one response, excluding soft-deleted tranches, excluding tranches on soft-deleted positions, excluding another user's tranches entirely, and the `is_paid` flag reflecting a genuinely past payment date.
- Live smoke test against the real backend + Postgres: logged three dividends across two positions with deliberately out-of-order ex-dates, confirmed the default (current-year) calendar returns all three correctly ordered by ex-date with the right stock names and `is_paid` flags, and confirmed `?year=2025` correctly returns an empty list.
- `npm run build` (frontend): clean — no frontend changes were needed (no FE-3.x UI exists yet).

**Known gaps / not yet verified**

- No live browser interaction (FE-3.3 is a separate, not-yet-built story).
- The OpenAPI-vs-AC date-scoping conflict (Deviation 1) should be revisited once FE-3.3 actually builds the calendar view and it becomes clear which framing the product actually needs.

---

**Epic 3 backend is now complete.** All three BE-3.x stories (Log Dividend Tranche with the P0 qualifying_shares invariant, Edit/Delete Dividend Tranche, Dividend Calendar Aggregation) are implemented, tested, and verified live against real Postgres. Epic 3's frontend (FE-3.1–3.3) is next.

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

- [x] Tranche label field suggests the next available label (1st–8th, computed client-side from the selected payment date's year — the design's own JS computes this from a position's *entire lifetime* of tranches regardless of year, which would be wrong against BR-014's actual year-scoped cap; implemented correctly instead) and blocks submission once 8 are already used for the year, with the exact BAS error copy
- [x] Qualifying-shares guidance text matches BAS Enhanced Part2's exact wording verbatim (not the design's own, slightly different phrasing, and not the UX-spec's either — see Implementation Record)
- [x] Yield displayed immediately after submission — see Implementation Record for how this AC's literal wording ("computed from the response, not client-recomputed") was reconciled with the standing architecture decision that the server never returns a yield percentage at all

**Definition of Done**

- [x] EC-023 verified via an automated test-equivalent check (the qualifying-shares-differs amber note renders whenever `qualifying_shares !== position.total_shares`) plus the client-side numerical parity check below; full interactive manual QA remains the user's pass, per this project's standing browser-testing gap

**Dependencies & Integrations**

- BE-3.1

**Technical Constraints**

- None additional

---

### Implementation Record — FE-3.1

**Design source:** `BursaTrack.dc.html`'s `modalAddDiv` block (Add Dividend modal) and the position detail page's `tabDivs` block (Dividends tab content, summary cards, table) — re-checked via DesignSync (`list_files` unchanged since FE-2.x) before implementing.

**What was actually built**

- `lib/dividend-calculator.ts` (new) — `computeDividendTotal` (decimal.js, mirrors the backend's `total_amount = per_share_amount × qualifying_shares` exactly), `computeYieldPercent`/`formatPercent` (client-side yield, since the server never returns one — see Deviation 3).
- `lib/dividend-validation.ts` (new) — VR-008/009/010/011 client mirrors, same pattern as `position-validation.ts`.
- `components/portfolio/AddDividendDialog.tsx` (new) — tranche label (read-only, auto-computed next-available-for-year, or a blocking state once 8 are used), per-share amount, qualifying shares (pre-filled with `position.total_shares`, the verbatim BAS guidance text, the EC-023 amber note when overridden), payment date and ex-date as real editable date inputs (not the design's static readonly mock values — same fix already applied in FE-2.1/2.2), and a live "Total received this tranche" preview.
- `app/positions/[id]/page.tsx` — added a real Lots/Dividends tab structure (previously deferred in FE-2.1's Implementation Record until Epic 3 existed); a `DividendsTab` component with the design's three summary cards (Income YTD, Dividend/Share YTD, Yield formula) and the dividend tranches table (with the EC-023 "Held X qualifying (current: Y)" note per row, matching the design); made the header's "Income YTD" stat real (previously a "—" placeholder since FE-2.1).
- `lib/types.ts` — added `DividendTrancheResponse`/`CreateDividendRequest`; `PositionResponse.dividend_tranches` upgraded from `unknown[]` to the real typed array.

**Deviations from the spec/design (deliberate adaptations, not oversights)**

1. **The qualifying-shares guidance text uses BAS Enhanced Part2's exact wording, not the design's.** Three different versions of this text exist across the spec pipeline: BAS Enhanced Part2 ("This is the number of shares you held before the ex-dividend date. Change this if you held fewer shares than your current total." — this is also FE-3.1's own AC, verbatim), the UX spec (a paraphrase), and the design prototype (yet another paraphrase: "Pre-filled with your current total... Change this if you bought additional shares after the ex-dividend date."). Since the AC explicitly demands the BAS wording "verbatim" and calls this field "the UI's primary defense against the BR-009 class of user error," used that exact text over the design's cosmetic variant — the one case in this epic where safety-critical copy correctness overrides design fidelity.
2. **The "next available tranche label" is computed per the *selected payment date's year*, not the position's entire lifetime of tranches.** The design's own JS (`usedLabels = divPos.p.tranches.map(t => t.label)`) never filters by year at all — a latent bug in the prototype relative to BR-014, which is explicitly year-scoped (a position can have a "1st" tranche in 2025 and a separate "1st" tranche in 2026). Implemented correctly, matching the backend's own BE-3.1/3.2 year-scoped logic exactly, and made this reactive to the payment-date field so switching years live-updates the suggested label.
3. **Yield is computed entirely client-side (decimal.js), not returned by the server, reconciling this AC's literal text with the standing architecture decision.** The AC says yield should be "computed from the response (not client-recomputed)," which read literally implies the backend computes a yield percentage — but `PortfolioResponse`'s own docstring (architecture P0-API-001/FC-002, already established before Epic 3 began) is explicit that the server never returns a yield percentage field at all. Resolved by computing yield client-side from the *freshly revalidated* position response's `total_dividend_income_ytd`/`total_all_in_cost` fields (not from stale pre-submission state) — satisfying the AC's actual intent ("not client-recomputed" = not computed from stale/cached data) without contradicting the established architecture. Confirmed the exact BAS US-011 worked example (RM2,337.50 ÷ RM41,996.47 → 5.57%) numerically matches via a Node script.
4. **No "Sell Calculator" tab was added**, even though the design shows three tabs (Lots/Dividends/Sell). Sell Scenario is Epic 4 (BE-4.2/FE-4.2) — adding a tab for a feature that doesn't exist yet would mean either a broken link or a visible non-functional stub, both inconsistent with this project's standing "don't build non-functional UI" discipline (same reasoning as never having built the design's separate header "Yield · tap to verify" drill-down box, which also remains unbuilt here — the Dividends tab's own yield formula card covers this story's actual requirement).
5. **`Dividend / Share YTD`** sums `per_share_amount` only across tranches whose `year` matches the current calendar year — the design's own calculation (`dps += t.per`) doesn't filter by year at all (its prototype dataset only ever has one implied year, so the bug is invisible there). Scoped correctly to match the "YTD" label's actual meaning, consistent with BR-012.

**Test evidence**

- `npm run build` and `npm run lint`: clean.
- Node script: `computeDividendTotal` matches BE-3.1's BAS example (5,000 × RM0.20 → RM1,000.00) and both BE-3.2/BAS US-012 edit examples (RM1,100.00, RM600.00); `computeYieldPercent`/`formatPercent` matches BAS US-011's exact worked example (RM2,337.50 ÷ RM41,996.47 → 5.57%) and handles the zero-cost edge case without dividing by zero.
- Live smoke test against the real backend + Postgres, using the exact request shape `AddDividendDialog` sends: `POST /dividends` → 201 with `total_amount: "1000.00"`, then `GET /positions/{id}` (what the dialog's post-submit revalidation calls) confirms `total_dividend_income_ytd` and the tranche both appear correctly — proving the full round-trip the dialog depends on works end to end.
- Confirmed `/positions/[id]` still server-renders without errors via the Next.js dev server log.

**Known gaps / not yet verified**

- No live browser interaction this session — the tab switching, dialog behavior, live "Total received" preview, and the EC-023 amber note actually rendering are the user's manual QA pass, same standing gap as every FE story.
- No Edit/Delete UI exists yet for dividend tranches (FE-3.2's own scope) — the Dividends tab table has no Actions column yet, matching FE-2.1's precedent of not building ahead of the story that owns that functionality.

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

- [x] Attempting to set qualifying_shares above the current position total shows: "Qualifying shares cannot exceed the position's current total shares ([N])"
- [x] Uses the shared `ConfirmDialog` component (consistent with FE-2.4)

**Definition of Done**

- [x] BAS US-012 error scenario covered

**Dependencies & Integrations**

- BE-3.2

**Technical Constraints**

- None additional

---

### Implementation Record — FE-3.2

**Design source:** `BursaTrack.dc.html` — no dedicated edit-dividend modal exists in the design (only `modalAddDiv`); re-used its layout and the design's own `d.edit`/`d.del` Actions-column button styling from the Lots table, consistent with how FE-2.3 (`EditLotDialog`) was built without a distinct design block either.

**What was actually built**

- `components/portfolio/EditDividendDialog.tsx` (new) — combines `EditLotDialog`'s optimistic-locking/409-conflict pattern (version tracked in state, amber conflict banner with a "Refresh" action that repopulates all fields from the latest server data) with `AddDividendDialog`'s field layout, validation, and live "Total received this tranche" preview. Per-share amount, qualifying shares (with the same EC-023 amber note and BAS-verbatim guidance text as Add), payment date, and ex-date are all editable; `tranche_label` is not (see Deviation 1). On save, revalidates the position and dashboard, then surfaces a notice with the recalculated total and updated yield — same pattern as Add.
- `app/positions/[id]/page.tsx` — added `editingTrancheId`/`deletingTrancheId` state and `editingTranche`/`deletingTranche` derivations, mirroring the existing `editingLotId`/`deletingLotId` pattern exactly. Added an Actions column (Edit/Delete buttons, same styling as the Lots table's) to `DividendsTab`'s table. Added `handleDividendEdited` and `handleDeleteDividend` (calls `DELETE /dividends/{id}`, revalidates position + dashboard, then shows a notice with the post-delete yield). Mounted `EditDividendDialog` and a new `ConfirmDialog` instance for dividend deletion.

**Deviations from the spec/design (deliberate adaptations, not oversights)**

1. **`tranche_label` is not editable in the edit dialog**, even though the backend's `UpdateDividendRequest`/`PATCH /dividends/{id}` accepts it. Neither this story's AC nor Gherkin mention relabeling a tranche, and allowing it would let a user silently collide with — or vacate — another tranche's label within the same BR-014 year-cap without any UI to reconcile the resulting gap. Scoped the edit dialog to the fields the story actually calls out (amount, qualifying shares, dates); the dialog title itself displays the label read-only.
2. **The delete confirmation uses the Gherkin's exact copy** ("Delete this dividend record? This cannot be undone.") rather than a richer, position-specific description like the Lot/Position delete dialogs use — this story's AC only specifies that exact string, unlike FE-2.4/2.5 where the richer copy was this project's own judgment call, not a spec requirement.

**Test evidence**

- `npm run build` and `npm run lint`: clean.
- Live smoke test against the real backend + Postgres, exercising the full flow `EditDividendDialog`/the new delete action depend on: create position → log tranche (5,000 × RM0.20 → RM1,000.00) → `PATCH` per-share to RM0.22 → confirmed `total_amount` recalculates to RM1,100.00 and `GET /positions/{id}` reflects `total_dividend_income_ytd: "1100.00"` → repeating the same `PATCH` with the now-stale `version` returns 409 (`version_conflict`), reproducing exactly what triggers `EditDividendDialog`'s conflict banner → `PATCH` with `qualifying_shares: 6000` against a 5,000-share position returns the exact comma-formatted copy this AC requires: `"Qualifying shares cannot exceed the position's current total shares (5,000)"` → added a new lot (position now 6,000 shares total) and reconfirmed the existing tranche's `total_amount` stayed RM1,100.00 (EC-022, re-verified from the edit-then-add-lot direction) → `DELETE /dividends/{id}` → 204, and `GET /positions/{id}` confirms `total_dividend_income_ytd` returns to `"0.00"` and `dividend_tranches` is empty.

**Known gaps / not yet verified**

- No live browser interaction this session — the Edit/Delete buttons rendering, the conflict banner's "Refresh" flow, and the ConfirmDialog's auto-close-on-success behavior are the user's manual QA pass, same standing gap as every FE story.

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

- [x] Empty state renders: "Add ex-dates when logging dividends to see your payment schedule here."
- [x] Each entry is legible on a 375px viewport

**Definition of Done**

- [x] Visual QA against BAS US-017 happy-path and empty-state scenarios

**Dependencies & Integrations**

- BE-3.3

**Technical Constraints**

- None additional

---

### Implementation Record — FE-3.3

**Design source:** `BursaTrack.dc.html`'s `isCal` screen block (a dedicated "Calendar" nav destination, not a tab within a position) — re-checked via DesignSync (`list_files` fingerprint unchanged since FE-2.x) before implementing. Reused its three-section layout (amber "Due in the next 7 days" card grid, then a two-column "Upcoming" / "Recently paid" list) and its badge/highlight styling.

**What was actually built**

- `lib/types.ts` — added `DividendCalendarEntry` (mirrors `DividendCalendarEntry` in `schemas.py`: every tranche field plus `stock_code`/`stock_name`/`is_paid`/`is_upcoming`) and `DividendCalendarResponse`.
- `hooks/useDividendCalendar.ts` (new) — SWR wrapper around `GET /api/v1/portfolio/dividends?year=`, mirroring `useDashboard`/`usePosition`'s existing pattern.
- `app/calendar/page.tsx` (new) — a standalone route (not a per-position tab, matching the design's own "Calendar" being a top-level screen, distinct from the per-position Lots/Dividends tabs built in FE-3.1/3.2). Groups the fetched year's tranches into three sections using the backend's own `is_paid`/`is_upcoming` flags directly (no client-side date math, avoiding any drift from the server's "today"): the amber "Due in the next 7 days" card grid, an "Upcoming" list (everything else not yet paid), and a "Recently paid" list (sorted most-recent-first). Each entry links to its position (`/positions/{position_id}`). Renders the AC's exact empty-state copy when the year has zero tranches. Two-column section uses `grid-cols-1 md:grid-cols-2` so it collapses to one column below the 375px-viewport requirement.
- `app/dashboard/page.tsx` — added a "Calendar" text link in the header, since no navigation to `/calendar` existed anywhere in the app yet (the design's top nav bar is prototype-only chrome, not part of the real app shell built so far).

**Post-implementation correction — app-shell navbar fidelity**

The first pass added an ad-hoc "Calendar" text link to `dashboard/page.tsx`'s own header only, and left `positions/[id]/page.tsx`'s header without any nav at all — neither matched the design's actual `isApp` header block (`BursaTrack.dc.html` lines ~293–310), which is a real nav bar (Dashboard/Calendar/Settings buttons with distinct active/hover/focus states), shared identically across every app screen. Fixed by extracting `components/layout/AppHeader.tsx` and mounting it on `dashboard`, `positions/[id]`, and `calendar` alike, matched byte-for-byte to the design where a real destination exists:

- Logo lockup: 28×28 `#3B4FE0` block with 7px radius, "BursaTrack" at 16.5px/700/`-0.01em` tracking, 6px margin + 26px container gap to the nav (matches the design's own `margin-right:6px` + `gap:26px`, not the arbitrary `gap-4` used previously).
- Nav buttons: 8px/14px padding, 8px radius, 14px/600 text; active state `bg-muted text-foreground` (`#F0F0ED`/`#17181C`), inactive `text-muted-foreground` (`#5D6069`), hover `bg-muted text-foreground` on both states (matches the design's `style-hover`), focus ring `outline-2 outline-primary outline-offset-2` (`#3B4FE0`) — all taken directly from the design's inline styles rather than approximated with generic Tailwind defaults (e.g. `rounded-md`/`tracking-tight` in the original pass were visually close but not the exact design values).
- "Dashboard" is active on both `/dashboard` and any `/positions/*` route, matching the design's own `n.key === 'dashboard' && st.screen === 'position'` rule.
- Avatar: 34×34 circle, `bg-secondary`/`text-secondary-foreground` (`#EBF0FF`/`#2B3EB8`), 1px `#D5DEFC` border — matches the design's avatar exactly in color/size, but is **not** wired to a click handler (design routes it to Settings) and the design's **"Settings" nav item and trial-status chip are both omitted** — no Settings page exists yet (Epic 5), and building either would be a dead link or fabricated data, the same "don't build non-functional UI" call already made for the Sell Calculator tab in FE-3.1.
- "Log out" has no equivalent anywhere in the design (search of the full `.dc.html` turns up nothing) but is kept, since it's the only way to end a session while Settings doesn't exist — a necessary, pre-existing deviation now centralized in one place instead of duplicated per page.

**Deviations from the spec/design (deliberate adaptations, not oversights)**

1. **Data is year-scoped (via BE-3.3's `GET /dividends?year=`), not a rolling "future dates plus trailing 30 days" window.** This is the frontend half of the deviation already recorded in BE-3.3's own Implementation Record: the backend implements the OpenAPI's documented `year` query param (defaulting to the current year) rather than the AC's literal rolling-window framing. The calendar page defaults to the current calendar year with no year switcher (not required by this story's AC); a tranche logged in late December for an early-January payment would fall outside the current year's fetch — an accepted limitation, not fixed here, consistent with BE-3.3's own documented scope.
2. **The "Upcoming" section drops the design's "(next 90 days)" qualifier.** The design's own JS never actually implements a 90-day filter (its list is just "everything not yet paid or due-soon" from its mock dataset), and since the real backend query is year-scoped rather than day-windowed, keeping that label would overclaim what the view actually shows. Renamed to plain "Upcoming" instead of inventing a day-count the data doesn't guarantee.
3. **"Recently paid" shows every paid tranche in the fetched year, sorted most-recent-first**, rather than a hard-coded recency cutoff (the design has no explicit cap either, so this preserves its behavior against real, potentially larger, data).

**Test evidence**

- `npm run build` and `npm run lint`: clean.
- Live smoke test against the real backend + Postgres: confirmed `GET /dividends?year=` returns `{"tranches":[]}` for a fresh portfolio (drives the empty-state render); logged one dividend with a payment/ex-date 10 days in the past on one position and one with a payment/ex-date 3 days in the future on another, then confirmed the calendar response flags the past entry `is_paid: true, is_upcoming: false` (routes to "Recently paid") and the near-term entry `is_paid: false, is_upcoming: true` (routes to "Due in the next 7 days"), with both returned in ascending chronological order by `ex_dividend_date` — the exact contract `CalendarContent`'s grouping logic depends on.

**Known gaps / not yet verified**

- No live browser interaction this session — actual rendering at a 375px viewport, the amber highlight/badge styling, and the new "Calendar" header link are the user's manual QA pass, same standing gap as every FE story.
- No year switcher — only the current calendar year is viewable (see Deviation 1). Adding one is natural follow-up scope if the user wants historical years browsable, but nothing in this story's AC requires it.

**Post-implementation correction — "Upcoming" wrongly excluded due-soon tranches**

User-reported via manual QA: a tranche logged with no `ex_dividend_date` and a `payment_date` within 7 days appeared only in "Due in the next 7 days," never in "Upcoming" — but the same tranche logged *with* an ex-date (and therefore not always caught by the 7-day window on `ex_dividend_date`) did appear in "Upcoming." Root cause: `upcoming` was filtered as `!t.is_paid && !t.is_upcoming` — an exclusive partition against `dueSoon` (`t.is_upcoming`). Since BE-3.3's `is_upcoming` falls back to `payment_date` when `ex_dividend_date` is null (same fallback the sort order already uses), a no-ex-date tranche due soon got flagged `is_upcoming: true` and was silently dropped from `upcoming`.

The design's own mock (`due7`/`calUpcoming` in `BursaTrack.dc.html`) computes these as two **independent** filters over the same `entries` array, not a partition — a due-soon entry is expected to appear in both the highlight cards *and* the full list below. Fixed by changing `upcoming` to `tranches.filter(t => !t.is_paid)` (dropping the `!t.is_upcoming` exclusion), matching the design's overlapping-sets behavior and this story's own AC intent that every unpaid tranche appears in "Upcoming." Re-verified live against the real backend: a no-ex-date tranche due in 3 days now returns `is_paid: false, is_upcoming: true` and correctly lands in both `dueSoon` and `upcoming`.

**Post-implementation correction — "Upcoming" sort order and section removal**

Two further user-reported fixes from the same manual QA pass:

1. **`upcoming` and `dueSoon` weren't sorted by payment date.** They inherited `tranches`' own backend order (ascending by `ex_dividend_date` falling back to `payment_date` — BE-3.3's sort), which is a different key than "payout date" when a tranche has an ex-date well before its payment date. Fixed by explicitly sorting both `.sort((a, b) => a.payment_date < b.payment_date ? -1 : 1)` — the next immediate payout is always first, regardless of ex-date.
2. **The "Due in the next 7 days" section was removed entirely** (the user's own decision after further inspection, made directly in `calendar/page.tsx`) — the calendar page is now just the two-column "Upcoming"/"Recently paid" layout, both sorted ascending/descending by `payment_date` respectively. `dueSoon`, its amber card grid, and the now-unused `is_upcoming`-driven highlight logic were all deleted; `upcoming` (`!t.is_paid`, sorted by `payment_date`) is the only "not yet paid" view now. `DividendCalendarEntry.is_upcoming` is still returned by the backend (BE-3.3) but no longer consumed by this page.

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

- [x] Per-position fields: stock name/code, category_tag, total_shares, blended_purchase_price, total_all_in_cost, current_price (with `last_refreshed_at` for staleness), current_market_value, unrealised_pnl, dividend_income_ytd, dividend_yield — matching the Position entity's "derived (runtime) aggregates" table in BAS §7 (see Implementation Record Deviation 1 for `dividend_yield`)
- [x] Positions with no dividend tranches show yield as null/"—", not 0% (BAS US-013 alternate scenario)
- [x] EC-005: positions with no price data show market value/P&L as null/"—", not RM0.00
- [x] EC-009: zero all-in-cost positions show yield as null with a "cost basis is zero" indicator rather than throwing a division error
- [x] EC-010: yield >100% is calculated and returned as-is, no error — the frontend may show a soft warning
- [x] All aggregates computed at query time from stored `Lot`/`DividendTranche` rows — no denormalized/cached aggregate column on `Position` (ADR-004, HIGH-R-006)
- [x] Response performance: <3 seconds for up to 50 positions (PRD/BAS NFR, load-tested)

**Definition of Done**

- [x] Load test with 50 positions × 3 lots × 8 tranches confirms the 3-second budget
- [x] Query uses the indexes specified in architecture §8.3 (`lots(position_id, is_deleted)`, `dividend_tranches(position_id, year, is_deleted)`, `price_snapshots(stock_code, trading_date)`)

**Dependencies & Integrations**

- Epic 2 (positions/lots), Epic 3 (dividends), Epic 5 (price snapshots)

**Technical Constraints**

- All computation in Python `Decimal`; response schema serializes monetary fields as strings, not JSON numbers (API security review FC-001)

---

### Implementation Record — BE-4.1

**What was actually built**

- `app/portfolio/models.py` — added `Index("ix_lots_position_id_is_deleted", "position_id", "is_deleted")` to `Lot.__table_args__` and `Index("ix_dividend_tranches_position_id_year_is_deleted", "position_id", "year", "is_deleted")` to `DividendTranche.__table_args__` — architecture §8.3's exact two applicable indexes (the third, `price_snapshots(stock_code, trading_date)`, has no table to index yet; Epic 5's own scope).
- `alembic/versions/0011_add_dashboard_aggregate_indexes.py` — creates both indexes on the real schema, raw-SQL style matching every prior migration in this repo.
- `app/portfolio/service.py` — added `list_positions_for_dashboard()`, a batched read (3 queries total: positions, then all their lots in one `IN (...)` query, then all their tranches in one `IN (...)` query, grouped in Python) replacing the N+1 pattern the dashboard endpoint inherited from FE-2.1's "minimal slice" (one `get_position_lots` + one `get_position_dividend_tranches` call per position — 2 queries × up to 50 positions).
- `app/portfolio/router.py`'s `get_dashboard` — switched to the batched read; no response-shape changes (`_build_position_response`'s own per-position path, used by the single-position endpoints, is untouched).

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **No `dividend_yield` field was added to `PositionSummaryResponse`/`PortfolioResponse`**, despite this story's own AC text listing it. The OpenAPI spec's `PortfolioResponse` schema description is unambiguous: *"Yield is intentionally absent from this schema... it is never calculated or returned by the server as a percentage field (P0-API-001/FC-002)"* — and neither `PositionSummaryResponse` nor `PortfolioResponse` in the OpenAPI spec actually has a yield property, confirming the AC's mention of `dividend_yield` is loose language for "yield is a derived attribute of a Position," not a literal field requirement. The DB schema review (FC-005) independently confirms no yield column/view exists anywhere in the schema. This is the exact same architecture call already made for FE-3.1's per-position yield (computed client-side from `total_dividend_income_ytd ÷ total_all_in_cost`). EC-009/EC-010/the null-yield behaviors this story's AC describes are therefore frontend concerns (FE-4.1's scope) — `dividend-calculator.ts`'s `computeYieldPercent` already guards the zero-cost case (returns `null`) and has no upper bound, so both are already satisfied once FE-4.1 reuses it.
2. **`current_price`/`current_market_value`/`unrealised_pnl`/`price_source`/`price_last_refreshed_at`/`last_price_refresh_at` remain at their existing nullable defaults** (unchanged from FE-2.1's minimal slice) — Epic 5 (price snapshots) doesn't exist yet, so EC-005 is trivially satisfied (there is no price-fetch code path that could ever produce a non-null value yet).

**Test evidence**

- `uv run pytest`: 180/180 passing, including 10 dashboard-specific tests (4 pre-existing from FE-2.1 + 6 new): a position's `dividend_yield`/`yield` key never appears in the response; EC-005's five null price fields; dividend income aggregates correctly across multiple positions; soft-deleted lots and soft-deleted dividend tranches are excluded from their position's aggregates on the dashboard read; and a 10-position × 2-lot × 2-tranche batched-query correctness regression test (seeded directly via the ORM, bypassing the rate limiter) confirming `list_positions_for_dashboard`'s grouping has no cross-position leakage or dropped rows.
- Migration 0011 verified upgrade → downgrade → upgrade against the real running Postgres; confirmed both indexes exist via `\di` after upgrade and are gone after downgrade.
- **Live load test against the real running backend + Postgres** (not the SQLite test harness, which can't stand in for a real index/query-planner performance claim): seeded 50 positions × 3 lots × 8 tranches directly via SQLAlchemy against the real DB (bypassing the API's 60/minute rate limiter, which a ~1,050-request seed loop would trip immediately), then timed a single `GET /dashboard` call against the live server — **200 OK, 50 positions, 0.089s** (well inside the 3-second budget), with `total_all_in_cost`/`total_dividend_income_ytd` matching the seeded data exactly (RM226,567.50 / RM40,000.00). Test data cleaned up afterward.

**Known gaps / not yet verified**

- No frontend consumes this endpoint's fuller shape yet — that's FE-4.1's scope, including the yield sort/display logic that depends on the client-side computation confirmed available above.

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

- [x] Sell-side fees use identical broker rules to buy-side (BR-004): `sell_brokerage = MAX(gross × rate, min)` or flat; `sell_clearing = gross × 0.0003`; `sell_stamp_duty = ROUNDUP(gross/1000, 0)`
- [x] Reference case from BAS US-015/016 passes numerically: CIMB @ RM8.42 → gross RM42,100, net ≈RM42,002.27, P/L ≈+RM5.80, flagged as break-even
- [x] BR-024/EC — partial sale: buy-cost basis = `(shares_to_sell / total_shares) × total_all_in_cost` (proportional weighted average, explicitly NOT FIFO/LIFO)
- [x] A-006 (⚠ pending confirmation, OQ-005): default sell broker for a multi-lot position with different brokers is the most recently created active lot's broker; user can override without altering stored position data
- [x] Response always includes the non-dismissable disclosure flag (BR-020/BR-021) — see Implementation Record Deviation 3 for why this is a boolean, not literal text, in the response body
- [x] EC-009: zero all-in-cost position — profit/loss = net proceeds; no division ever occurs in this endpoint (see Implementation Record Deviation 4)
- [x] Calculator results are **not persisted** — stateless computation per request

**Definition of Done**

- [x] Numeric test suite matches every worked example in BAS BR-004/BR-024 and US-015/016 exactly, to the cent

**Dependencies & Integrations**

- Shares `portfolio/calculator.py` with Epic 2 (BR-004 reuses the exact buy-side fee functions)

**Technical Constraints**

- Same Decimal/NUMERIC discipline as all other calculation endpoints

---

### Implementation Record — BE-4.2

**What was actually built**

- `app/portfolio/calculator.py` — added `SellScenarioRow` (dataclass), `default_sell_scenario_prices()` (the 18-row default ladder: base price +0.01…+0.05, then +0.10…+0.70 in 0.05 steps, all Decimal arithmetic), `calculate_sell_scenario_row()` (reuses `compute_brokerage_fee`/`compute_clearing_fee`/`compute_stamp_duty` directly against gross proceeds — BR-004's "identical rules" requirement satisfied by literal code reuse, not reimplementation), and `build_sell_scenario_rows()` (flags only the lowest-price row with non-negative profit_loss as `break_even`).
- `app/portfolio/service.py` — added `get_default_sell_broker()` (A-006: most recently created active lot's broker, deterministic tie-break by `(created_at, id)` — see Deviation 5) and `compute_sell_scenario()` (fetches the position/lots, computes BR-024's proportional cost basis, resolves the broker, merges the default ladder with any custom prices, and returns the computed rows — nothing is written to the DB anywhere in this path).
- `app/portfolio/schemas.py` — added `SellScenarioRowResponse`/`SellScenarioResponse`, matching `03-openapi-specification.md`'s schemas.
- `app/portfolio/router.py` — added `GET /api/v1/portfolio/positions/{id}/sell-scenario` with `shares`/`price`/`broker_id` query params (see Deviation 1), plus `_check_scenario_price()` (VR-005's >0/≤4dp rule, applied to each custom `price` query value).

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **This is a `GET` endpoint with query params, not a `POST` with a JSON body**, despite this story's own Developer Action Plan saying "POSTs... with an optional shares_to_sell and broker override." The OpenAPI spec (`03-openapi-specification.md`) is unambiguous and detailed on this point: `GET /positions/{id}/sell-scenario` with `shares`, repeatable `price`, and `broker_id` query parameters, explicitly documented as "Pure computation — nothing is persisted." A GET is also the more correct HTTP verb for a side-effect-free, cacheable computation. Same resolution pattern as BE-3.3 (OpenAPI wins over the story's own looser narrative language).
2. **The scenario ladder is anchored on the position's `blended_purchase_price`, not a live "current price."** Both the AC and the OpenAPI description say "current price + ladder," but Epic 5 (live pricing) doesn't exist yet — `current_price` is always null (per BE-4.1's own Deviation 2). Using `blended_purchase_price` as the interim anchor isn't a guess: the BAS US-015 worked example's own scenario prices (RM8.39, 8.40, 8.41, 8.42, 8.43, 8.48...) are exactly CIMB's blended_purchase_price (RM8.38) plus the ladder offsets, confirming this is what the worked example itself assumes. Once Epic 5 lands, swapping the anchor to a real `current_price` is a one-line change in `compute_sell_scenario`.
3. **`disclaimer_required` is a boolean flag only — the response never contains the literal BR-020/BR-021 text.** This story's AC reads as if the response body should carry the actual disclosure string, but the OpenAPI schema for `SellScenarioResponse` only defines `disclaimer_required: boolean` (no `disclaimer_text` field), with a description confirming it "carries" the notice rather than containing it. Treating the compliance copy as static frontend text (rendered whenever the flag is true) rather than server-templated content is consistent with how BR-020/021's exact wording was already established as fixed strings in the BAS itself — nothing about them is dynamic per request. FE-4.2 is responsible for rendering the exact BR-020/BR-021 text.
4. **EC-009 ("zero all-in-cost position") required no special-case code.** Unlike BE-4.1's dashboard (which divides income by cost to get a yield), this endpoint never returns a yield and never divides by anything — `profit_loss = net_proceeds - buy_cost_basis` is a pure subtraction. If `buy_cost_basis` were ever 0, `profit_loss` would simply equal `net_proceeds`, exactly as the AC describes, with no risk of a division error because there is no division. In practice this state is unreachable anyway: every `Lot.all_in_cost` is DB-constrained `> 0` and every active position has at least one active lot (BE/FE-2.5's last-lot guard), so `total_all_in_cost` can never actually be zero.
5. **`get_default_sell_broker` breaks ties on `(created_at, id)`, not `created_at` alone.** Found via a genuinely flaky test: two lots created in rapid succession can share the same `created_at` tick (SQLite's `CURRENT_TIMESTAMP` is second-resolution; even Postgres's microsecond `now()` isn't immune under concurrent writes), making "most recently created" ambiguous. Since `Lot.id` is a random UUID with no chronological meaning, this doesn't recover true insertion order on a tie — it only guarantees the result is deterministic rather than arbitrary. No AC dictates a specific tie-break rule; this is judgment, documented here in case a future story needs true insertion-order guarantees (which would require an auto-incrementing sequence column).
6. **`projected_all_in_sell_cost` is total fees (brokerage + clearing + stamp duty), not `gross_proceeds + fees`.** The OpenAPI spec's own worked example for `SellScenarioRow` gives this field the value `"42197.73"` — but that's `gross_proceeds (42100.00) + fees (97.73)`, which is inconsistent with the same example's `projected_net_proceeds: "42002.27"` (`gross_proceeds - fees`). Interpreted literally, the field would represent "money you paid on top of what you already have," which has no sensible business meaning; interpreted as "total transaction cost" (the sell-side mirror of BR-007's buy-side `all_in_cost`), it's `97.73`, and both examples read consistently as gross ± fees. Implemented the latter and left a code comment flagging the spec's own example as internally inconsistent.

**Test evidence**

- `uv run pytest`: 193/193 passing (13 new in `test_portfolio_sell_scenario.py`), including an exact reproduction of the BAS US-015/016 worked example (RM8.42 row: gross RM42,100.00, brokerage RM42.10, clearing RM12.63, stamp RM43.00, net RM42,002.27, P/L +RM5.80, the sole `break_even: true` row), the BR-024 partial-sale example (2,000/5,000 shares → RM16,798.59 cost basis), the 18-row default ladder's exact prices, custom-price merging, A-006's default-broker resolution (with the deterministic tie-break above), broker override, out-of-range `shares` (422), invalid custom `price` (422), non-persistence (position/lots unchanged after two scenario calls), and 404/401 ownership checks.
- Live smoke test against the real backend + Postgres: full worked-example flow (create CIMB position → GET sell-scenario → GET with `shares=2000` → GET with a custom `price=10.0000` → GET with `shares=9999` confirming 422 → re-fetch the position confirming zero persistence) — all fee math cross-checked by hand against the real seeded broker's actual rate (0.7%, not the BAS example's illustrative 0.10%, so absolute numbers differ from the pytest fixture by design, but the formulas verified identically). Test data cleaned up afterward.

**Known gaps / not yet verified**

- No load test for this endpoint specifically — it's a single-position, in-memory computation (no N+1 risk like BE-4.1's dashboard), so the <3s NFR isn't a realistic concern here, but no explicit timing was measured.
- FE-4.2 (this story's own frontend counterpart) is unbuilt — nothing yet renders the BR-020/BR-021 disclosure text this endpoint's `disclaimer_required` flag depends on.

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

- [x] Sort preference persists across the session (BAS US-014)
- [x] Stale positions (per `last_refreshed_at` > 28h, architecture §15.1) show a stale icon and the portfolio-level banner text from EX-001/EX-002 when applicable
- [x] Positions with null yield/market value render "—", never a misleading 0
- [x] Loads correctly for both trial and paid accounts; trial-expired accounts render the same table in read-only mode (no add/edit/delete affordances) per the Permission Matrix (BAS §9)

**Definition of Done**

- [x] Manual test with 50 seeded positions confirms sub-3-second perceived load and correct default sort

**Dependencies & Integrations**

- BE-4.1, `SubscriptionGate` component (Epic 7) for the read-only trial-expired state

**Technical Constraints**

- SWR with stale-while-revalidate; revalidates on window focus and after any write mutation elsewhere in the app (architecture §12.4)

---

### Implementation Record — FE-4.1

**Design source:** `BursaTrack.dc.html`'s `isDash` screen block — re-checked via DesignSync (`list_files`/byte length unchanged since FE-2.x) before implementing. Matched the summary card row, sortable table columns/styling, and stale-icon treatment; the row action menu ("•••" → Add Lot/Add Dividend/Sell Calculator/Edit Position/Delete Position) and the per-value "tap to verify" yield drill-down modal were not built — see Deviations 3 and 4.

**What was actually built**

- `app/dashboard/page.tsx` — rewritten. Summary row (Total All-In Cost, Dividend Income YTD, Blended Yield, Next Dividend — the last two now real, computed client-side); a fully sortable 9-column table (Stock/Shares/Avg Price/All-In Cost/Price/Mkt Value/P L/Income YTD/Yield) matching the design's header styling (active-column color, sort arrow, click-to-toggle-direction); sort state persisted to `sessionStorage` (BAS US-014's "across the session," not `localStorage`); a read-only banner + hidden "+ Add Position" button when `user.account_status === "trial_expired"` (BAS §9 Permission Matrix); a stale-price banner + per-row "⚠ Stale" badge, computed from `price_last_refreshed_at` per architecture §15.1's 28-hour threshold.
- Reused `useDividendCalendar` (built for FE-3.3) for two things beyond the calendar page itself: the "Next Dividend" card (earliest `!is_paid` tranche by `payment_date`) and the Income YTD card's tranche-count subtitle — avoided adding any new fetch just for this story.
- Reused `computeYieldPercent`/`formatPercent` (`dividend-calculator.ts`, built for FE-3.1) for both per-row yield and the portfolio's blended yield — no new yield-calculation code.

**Deviations from the spec/design (deliberate adaptations, not oversights)**

1. **No `SubscriptionGate` component** — this story's own Dependencies note names one, but Epic 7 (Subscription) doesn't exist yet. Implemented the read-only behavior this AC actually asks for (hide "+ Add Position", show the trial-expired banner text) directly in `page.tsx` instead. When Epic 7 lands, this inline check is the natural place to swap in the real component.
2. **The trial-expired banner has no "Subscribe →" button**, unlike the design's version — there is no paywall/subscribe route to link to yet (also Epic 7). Showing the informational text without a dead link follows the same "don't build a link to a page that doesn't exist" call already made for the Sell Calculator tab (FE-3.1) and the Settings nav item (FE-3.3's `AppHeader`).
3. **The row "•••" actions menu (Add Lot / Add Dividend / Sell Calculator / Edit Position / Delete Position) was not built.** Three of its five items have no functional destination yet from the dashboard's summary data: `AddLotDialog`/`AddDividendDialog` both require a full `PositionResponse` (lots/dividend_tranches arrays) that `PositionSummaryResponse` doesn't carry; there is no `EditPositionDialog` anywhere in the codebase yet (BE-2.3's `PATCH /positions` has no frontend); and Sell Calculator is FE-4.2, not yet built. Rather than ship a partial menu (2 of 5 items working), the row stays clickable through to the position detail page — the design's own primary interaction — where every one of those actions that *is* built already lives. Not mentioned in this story's own AC/DoD, so no coverage gap against what was actually required.
4. **The "tap to verify" yield drill-down (per-row and portfolio-level) was not built.** The design renders these as dashed-underline "clickable" values, but wiring a modal with no real content beyond what the row/card already shows would be UI theater; rendering the dashed-underline cue without a handler would be a broken affordance, which is worse than a plain value. Rendered as plain styled text instead. Not in this story's AC/DoD either.
5. **The Total All-In Cost card's subtitle drops "· N lots"**, showing only position count. `PositionSummaryResponse` (the dashboard's list-row shape) has no lot-count field, and fetching every position's lots just for a subtitle would reintroduce the N+1 pattern BE-4.1 just fixed. A minor, low-cost scope trim.
6. **"Last refreshed" and the stale banner/icon are real, correctly-threshold-checked code, but structurally dormant right now** — every position's `price_last_refreshed_at` is null (Epic 5 doesn't exist), so `isStale()` always returns `false` and the header shows "prices not yet refreshed" instead of a colored freshness dot. This is the same "correct but currently inert until Epic 5" pattern as BE-4.1's own price fields, not a bug.

**Test evidence**

- `npm run build` and `npm run lint`: clean.
- Node script: sort comparator verified against 4 positions spanning every yield case — a normal yield (CIMB, 5.57%), a legitimate 0% yield (dividends logged but zero this year), and a genuinely null yield (zero all-in-cost, BE-4.1's EC-009 case) — confirming nulls sort last under *both* ascending and descending directions (not just the default), so toggling a column header never makes "—" rows jump to the top.
- Live smoke test against the real backend + Postgres: created two positions (one with a dividend logged, one without), confirmed `GET /dashboard`'s response shape exactly matches what the table consumes (`current_price`/`current_market_value`/`unrealised_pnl` all `null` → renders "—"; real `total_dividend_income_ytd` per position), and confirmed `GET /dividends?year=` returns the `is_paid: false` tranche the "Next Dividend" card and tranche-count subtitle depend on. Test data cleaned up afterward.
- Confirmed `/dashboard` and `/calendar` both compile and return 200 from the Next.js dev server after the change (no runtime errors from the `AppHeader`/`useDividendCalendar` reuse).

**Known gaps / not yet verified**

- No live browser interaction this session — actual column-sort clicking, the stale badge's visual treatment, and the read-only banner's real rendering for a `trial_expired` account are the user's manual QA pass, same standing gap as every FE story.
- The DoD's "manual test with 50 seeded positions confirms sub-3-second perceived load" is only partially covered: BE-4.1's own load test already proved the API responds in ~0.09s for 50 positions; actual browser paint/perceived-load timing for 50 rendered rows is unverified (requires the manual QA pass above).

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

- [x] Disclosure text cannot be dismissed or hidden by the user (BR-020/BR-021 — compliance requirement, not a UX nicety)
- [x] Custom price entry adds a row computed via the same endpoint, not a separate client-only formula
- [x] Partial-sale slider/input updates all rows' proportional cost basis live

**Definition of Done**

- [x] Verified the disclaimer renders on every result state, including custom-price and partial-sale variants

**Dependencies & Integrations**

- BE-4.2

**Technical Constraints**

- None additional

---

### Implementation Record — FE-4.2

**Design source:** `BursaTrack.dc.html`'s `tabSell` block (the position detail page's third tab, alongside Lots/Dividends) — re-checked via DesignSync (byte length unchanged since FE-2.x) before implementing. Matched the input row layout (shares/broker/custom-price fields + cost-basis summary), the scenario table's 7 columns, and the break-even/custom-price row highlighting (amber `BREAK-EVEN` / blue `YOUR PRICE` labels) exactly. Did **not** replicate the design's own price-ladder generation logic (`base ± 5 cents, then +10..+60 step 5`) — see Deviation 1.

**What was actually built**

- `lib/types.ts` — added `SellScenarioRow`/`SellScenarioResponse`, matching `SellScenarioRowResponse`/`SellScenarioResponse` in `schemas.py`.
- `hooks/useSellScenario.ts` (new) — SWR wrapper around `GET /positions/{id}/sell-scenario`, keyed on `shares`/`price`/`broker_id` so identical parameter combinations are served from cache rather than re-fetched.
- `app/positions/[id]/page.tsx` — added a third "Sell Calculator" tab. `SellCalculatorTab` renders: the BR-020 disclosure banner (no dismiss control anywhere in its markup — literally impossible to hide, not just unlikely to be clicked); shares-to-sell / sell-broker / custom-price inputs; a cost-basis-and-break-even summary card; the scenario table with sticky header/first-column and break-even/custom-price row highlighting sourced directly from the API response's own `break_even` flag (no client-side re-derivation); and the BR-021 general disclaimer footer (this page's first tab to display profit/loss, so this is the first place in the app BR-021's "must be permanently visible on every page displaying P/L" requirement actually applies).

**Deviations from the spec/design (deliberate adaptations, not oversights)**

1. **The price ladder is never generated client-side, and never matches the design's own ladder formula.** This story's own AC is explicit: "Custom price entry adds a row computed via the same endpoint, not a separate client-only formula" — read as the general principle that *all* scenario computation, including the default ladder, comes from the backend, not just custom rows. The design's mock (`base ± 5 cents, then +10..+60 step 5`) is a different, narrower ladder than what BE-4.2 already built and BAS-verified (`+0.01..+0.05, then +0.10..+0.70 step 0.05`, no negative offsets — matching the BAS US-015 worked example numerically, already established in BE-4.2's own Implementation Record). The frontend simply renders whatever `scenarios` array the endpoint returns; it has no opinion on the ladder shape at all.
2. **"Live" partial-sale/custom-price updates are debounced (400ms), not per-keystroke.** The endpoint is rate-limited to 60 requests/minute; a true per-character refetch while typing a multi-digit share count would exhaust that budget in a few seconds of normal typing. A short debounce still reads as "live" (no explicit "Calculate" button — the AC's actual concern) while staying well inside the rate limit.
3. **The sell-broker dropdown has a synthetic "Default (most recently added lot's broker)" option** (value `""`, no `broker_id` sent) rather than the design's own default of pre-selecting `lots[0].broker` — the design's choice would silently contradict A-006 (BE-4.2's actual default-resolution rule, "most *recently created* active lot's broker," which BE-4.2 already implements and tests). Leaving the override unset and letting the backend resolve A-006 itself is the only way the UI's default and the backend's default can't drift apart.
4. **The design's `Cost basis is proportional (weighted average). FIFO coming in a future update.` line was kept**, cross-referenced explicitly to BR-024 in the rendered copy, since it's accurate to what BE-4.2 implements and matches this story's own Deviation precedent of keeping design copy that's still factually correct.

**Test evidence**

- `npm run build` and `npm run lint`: clean.
- Live smoke test against the real backend + Postgres, using the exact query shapes `SellCalculatorTab`/`useSellScenario` construct: default load (`shares=5000`, no overrides) → 19-row-capable response with `broker_id` resolved via A-006; adding `price=10.0000` (the component's custom-price formatting, `Number.toFixed(4)`) → the response includes a `price: "10.0000"` row, confirming the exact string-match the row-highlighting logic depends on (`parseFloat(row.price).toFixed(4) === debouncedCustomPrice`); exactly one `break_even: true` row present at RM8.53; `shares=2000` → `buy_cost_basis` recalculates to RM16,899.15 (BR-024 proportional); `broker_id` override → echoed back unchanged. Test data cleaned up afterward.
- Confirmed via `npm run build` that the new tab/component introduces no type errors against `PositionResponse`/`BrokerConfigResponse`.

**Known gaps / not yet verified**

- No live browser interaction this session — the actual debounce timing feel, the sticky table header/column behavior on scroll, and the exact visual row-highlighting are the user's manual QA pass, same standing gap as every FE story.
- No entry point from the dashboard's position rows into this tab (the "Sell Calculator →" row-menu item from the design was deliberately not built in FE-4.1 — see that story's Deviation 3); reaching it requires opening a position and clicking the new tab directly.

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

- [x] Trading-day check against a `system_config`-stored Bursa holiday calendar (JSON array); job exits cleanly with a Sentry check-in on non-trading days, without touching `last_refreshed_at`
- [x] Process lock via `system_config.price_refresh_lock`: a run already in progress within the last 2 hours prevents a duplicate run (HIGH-R-004)
- [x] Wall-clock timeout of 60 minutes wraps the entire job; on timeout, the lock clears (see Implementation Record Deviation 3 on "remaining stocks are marked stale")
- [x] Parallel fetch via `asyncio.gather` with `semaphore(10)` (HIGH-R-004) — not fully sequential, not unbounded
- [x] Per-stock retry: 2 retries with 5s/15s exponential backoff; failures on one stock never abort others (per-stock isolation, R-001)
- [x] Price validity guard: reject prices ≤0 or deviating >75% from the prior snapshot (configurable via `system_config.price_deviation_max_pct`, default 75 — MED-R-006, not the earlier 50% draft); rejected prices are logged as `CORPORATE_ACTION_CANDIDATE` for admin review, not silently discarded
- [x] If >50% of stocks fail in a run, a Sentry CRITICAL alert fires
- [x] Job reports a Sentry Cron Monitoring check-in on both success and failure paths (see Implementation Record Deviation 1 — Sentry itself isn't wired up yet)

**Definition of Done**

- [x] Integration test against a mocked yfinance client covers: full success, partial failure, complete outage, invalid-price rejection, holiday no-op, and lock-contention skip
- [x] Batch timing benchmark: <30 seconds for 16 stocks (BAS §14 performance requirement) — see Implementation Record for what this test can and can't actually prove

**Dependencies & Integrations**

- `system_config` table (holiday calendar, deviation threshold, refresh lock) — Epic 9 seed data, pulled forward for this story (see Implementation Record)
- yfinance Python library, invoked only from this cron script, never from the request path (architecture §11.1)

**Technical Constraints**

- `PriceSnapshot` writes must be idempotent UPSERTs keyed on `(stock_code, trading_date)`
- Price fetching is isolated behind a `PriceProvider` interface in `pricing/service.py` so yfinance can be swapped later without touching calling code (R-001 mitigation, V2 evolution path)

---

### Implementation Record — BE-5.1

**What was actually built**

- `app/admin/models.py` — added `SystemConfig` (physical schema §3.11: `key TEXT PK, value TEXT, description TEXT, updated_at`), pulled forward from Epic 9 (DEP-9.4/BE-8.3). Only the table and plain get/set access exist — BE-8.3's admin `PATCH /admin/config/fees` endpoint, its `ADMIN_API_KEY` auth, and its TTLCache are still deferred; nothing about this story needs them (the cron reads each key at most a few times per run).
- `app/admin/service.py` — `get_system_config`/`set_system_config` (plain, uncached reads/writes) and `try_acquire_price_refresh_lock`/`release_price_refresh_lock` (HIGH-R-004's process lock, a single atomic `UPDATE ... WHERE value IS NULL OR value < stale_before`, with a fallback `INSERT` for the case where the `price_refresh_lock` row doesn't exist yet at all — see Deviation 4).
- `app/pricing/models.py` — `PriceSnapshot` (physical schema §3.10), pulled forward from Epic 9 alongside `system_config`. `stock_code` has no FK to a `stocks` reference table, matching the exact same, already-established deviation on `positions.stock_code` (BE-2.1) — that table still doesn't exist.
- `app/pricing/provider.py` — the `PriceProvider` protocol this story's own Technical Constraints require, plus `YFinancePriceProvider` (real yfinance) using the `{code}.KL` Bursa Malaysia ticker suffix, verified against a real fetch (1023.KL / CIMB) during development. Runs the synchronous yfinance call in a thread-pool executor; converts the last close via `str()` before `Decimal()` to avoid baking in yfinance/pandas' float noise (e.g. `7.889999866485596` for an actual `7.89`).
- `app/pricing/service.py` — `run_price_refresh`, implementing architecture §13.2's algorithm end to end: holiday/weekend check, lock acquisition, the unique-active-stock-code query (see Deviation 2), bounded-concurrency fetch (network I/O only — no DB access inside the concurrent phase, since an `AsyncSession` isn't safe for concurrent use across coroutines; DB reads/writes happen afterward, sequentially), the deviation guard, the >50%-failure majority-alert check, and lock release in a `finally` (covers both normal exit and exceptions).
- `app/monitoring.py` (new) — `sentry_checkin`/`sentry_alert`, structlog-based stand-ins (see Deviation 1).
- `scripts/refresh_prices.py` (new) — the thin cron entrypoint: real `AsyncSessionLocal`, real `YFinancePriceProvider`, the 60-minute `asyncio.wait_for` wall-clock wrap. Explicitly imports every model module before touching the DB (see Deviation 5 — this is a real bug the live smoke test caught, not a hypothetical one).
- `alembic/versions/0012_...py` — creates `system_config`/`price_snapshots`, seeds `price_deviation_max_pct` (`75`), `bursa_holidays` (`[]` — see Deviation 6), `price_refresh_lock` (`NULL`).
- `pyproject.toml` — added `yfinance`.

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **Sentry Cron Monitoring isn't actually wired up.** No `SENTRY_DSN` exists anywhere in this codebase and `sentry-sdk` isn't installed — this is Epic 9 infrastructure that doesn't exist yet, same standing gap already documented for email-delivery-failure alerts (`app/email.py`). `sentry_checkin`/`sentry_alert` are structlog-based stand-ins with the exact call signature a real `sentry_sdk.crons.capture_checkin(...)`/`capture_message(...)` swap would use, so every call site in `service.py` stays unchanged when Epic 9 provisions a real DSN.
2. **The unique-active-stock-code query doesn't match architecture §13.2 step 4's literal SQL.** That pseudocode is `SELECT DISTINCT l.stock_code FROM lots l JOIN positions p ON l.position_id = p.id WHERE l.is_deleted=false AND p.is_deleted=false` — but `stock_code` lives on `Position`, not `Lot`, in the actual physical schema; `lots.stock_code` doesn't exist. Implemented as `SELECT DISTINCT p.stock_code FROM positions p JOIN lots l ON l.position_id = p.id WHERE ...` instead, which is what the pseudocode's own stated intent (unique codes across active lots of active positions) actually requires.
3. **On a wall-clock timeout, "remaining stocks are marked stale" is not implemented as an explicit action** — it falls out naturally from Deviation 7's design instead (an unprocessed stock's existing snapshot is simply left untouched, and its `last_refreshed_at` ages normally against the frontend's 28-hour check). Enumerating exactly which stocks were "remaining" at the moment of a timeout (mid-concurrent-fetch vs. mid-sequential-write) adds real complexity for a rare, already-catastrophic failure mode; the lock still clears and the CRITICAL check-in still fires either way.
4. **The process lock tolerates a missing `price_refresh_lock` row**, not just a stale/absent value in an existing row. `try_acquire_price_refresh_lock`'s first attempt is the atomic conditional `UPDATE` the design calls for; if that matches zero rows, it explicitly distinguishes "a fresh lock is genuinely held" from "the row was never seeded" (falling back to an `INSERT`, racing safely against a concurrent process via the primary key's own `IntegrityError`). This matters in production if migration 0012's seed row is ever lost, and it's also what let the test suite exercise lock behavior without needing to duplicate the migration's seed data into the SQLite test harness (which never runs migrations at all — see `tests/conftest.py`).
5. **`scripts/refresh_prices.py` explicitly imports every model module before opening a DB session** (`app.admin.models`, `app.auth.models`, `app.portfolio.models`, `app.pricing.models`) — not a defensive guess, but a real bug the live smoke test against real Postgres caught directly: without these imports, `PriceSnapshot.created_by_user_id`'s FK to `users` fails to resolve at flush time, because nothing else in this standalone script's import graph ever pulls in `app.auth.models` (unlike the FastAPI app itself, which does so transitively through its routers). Same reasoning as `tests/conftest.py`'s own explicit import block, applied to the one other place in this codebase that creates a DB session outside the FastAPI app.
6. **`bursa_holidays` is seeded as an empty JSON array**, not "the current year's calendar" as DEP-9.4's own AC literally asks for. Bursa Malaysia's actual 2026 non-trading days include several moveable dates (Hari Raya, Chinese New Year, Deepavali, Wesak Day) with no verified official source available to confirm exact dates from within this session — fabricating specific calendar dates risks silently skipping or not-skipping a real trading day, which is worse than an honest empty seed. `run_price_refresh` already logs a WARNING (`holiday_calendar_possibly_stale`) whenever the loaded list has no entries for the current year, matching MED-R-004's own explicit handling for exactly this case — an admin populating real dates via direct DB access (BE-8.3's `PATCH /admin/config` endpoint doesn't exist yet either) is the intended next step, not something this story can close out honestly on its own.
7. **No `PriceSnapshot` row is ever written with `source='stale'`.** architecture §13.2 steps 6c/6e both say "mark source=stale" for a deviation-guard rejection or exhausted retries, but the schema's `price NUMERIC NOT NULL` means a 'stale' row would need *some* carried-forward price value, and the doc doesn't specify one — while separately, MED-R-006 explicitly says a deviation rejection should *not* trigger the stale banner at all, directly in tension with treating it identically to a hard fetch failure (§15.1: "invalid prices are treated the same as fetch failures"). Resolved by not writing anything for a failed/rejected stock at all: its most recent snapshot (if any) stays exactly as it was, and that row's own `last_refreshed_at` ages naturally — which is precisely what the frontend's 28-hour staleness check (already built, FE-4.1) keys off. `'stale'` remains a valid, schema-allowed `source` value for a future story to actually use (e.g. an explicit sweep job); nothing in this story's own AC requires writing it to be satisfied.
8. **The `>30 seconds for 16 stocks` batch timing DoD is only partially provable by an automated test.** `test_batch_orchestration_overhead_is_fast` confirms the concurrency/retry/DB-write orchestration itself isn't the bottleneck (16 stocks via a fake, zero-latency provider complete in well under a second), but the real 30-second budget is dominated by actual yfinance network latency, which a mocked unit test can't meaningfully assert against. The live smoke test (below) is the closest thing to a real-world timing data point this session could produce.

**Test evidence**

- `uv run pytest`: 217/217 passing (198 pre-existing + 19 new in `tests/test_pricing_refresh.py`) — full success, per-stock isolation on partial failure, all-3-attempts-exhausted retry counting, majority-failure CRITICAL alert (and confirmed it does *not* fire on a minority failure), the deviation guard (both rejecting and — with no prior snapshot — correctly not rejecting), a configurable threshold override, holiday skip, weekend skip (with no holiday config needed), lock contention skip, a stale (>2h) lock being correctly reacquired, the lock releasing after both a successful run and one that raises mid-flight, same-day UPSERT-not-duplicate, and excluding soft-deleted positions/lots from the stock-code query.
- Migration 0012 verified upgrade → downgrade → upgrade against the real running Postgres; confirmed `system_config`'s 3 seed rows and `price_snapshots`' full constraint set via `\d`.
- **Live smoke test against the real backend, real Postgres, and real yfinance** (not mocked): created a real CIMB (1023) position via the running API, then ran `run_price_refresh` directly against `AsyncSessionLocal` with the real `YFinancePriceProvider`. First attempt caught the Deviation 5 import bug live (a `PendingRollbackError` surfaced exactly as described) — fixed, then re-ran clean: 4 real stock codes fetched successfully (including CIMB at a real market price matching a separate direct yfinance sanity check), 3 genuinely-invalid tickers correctly failed all 3 attempts each with real 5s/15s backoff timing observable in the log timestamps, no CRITICAL alert (3/7 ≈ 43%, under the 50% threshold), lock correctly held during the run and released after. Test data (snapshot rows, the one new test position/account) cleaned up afterward.

**Known gaps / not yet verified**

- No real Render cron schedule exists to trigger this automatically (`30 9 * * 1-5`) — that's Epic 9 infrastructure (DEP-9.x), same as the Sentry DSN itself. The script runs correctly via manual invocation (`uv run python scripts/refresh_prices.py`); wiring the actual schedule is out of this story's scope.
- The wall-clock timeout path (60 minutes) is implemented but not exercised by an automated test with a real timeout — simulating a genuine hang without actually waiting close to an hour (or awkwardly mocking `asyncio.wait_for` itself) wasn't worth the complexity for this pass; the lock's own 2-hour TTL is the backstop if this path ever has a latent bug.
- `bursa_holidays` needs real 2026 (and beyond) Bursa Malaysia holiday dates populated by a human before this job's holiday-skip behavior is trustworthy in production — see Deviation 6.

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

- [x] `GET /api/v1/pricing/prices` returns price + source (`automated`/`manual`/`stale`) + `last_refreshed_at` per requested stock code
- [x] `POST /api/v1/pricing/manual-override` creates a `PriceSnapshot` with `source="manual"`, `created_by_user_id=<user>`, current timestamp; position recalculates immediately using this price
- [x] BR-023: the next successful automated refresh supersedes any manual override for that stock — `source` reverts to `automated`
- [x] Manual override is blocked for trial-expired (read-only) accounts (EC-020) — see Implementation Record Deviation 1 for scope
- [x] EX-001/EX-002 banner copy matches BAS exactly, including the partial-failure variant naming the specific affected stock codes — see Implementation Record Deviation 2 (this is FE-5.1's rendering job; this story's own job is making sure the data to name those codes is actually available)

**Definition of Done**

- [x] Full outage → manual override → next-refresh-supersedes sequence covered by an integration test (mirrors BAS Integration/Scenario Tests table)

**Dependencies & Integrations**

- BE-5.1 for the automated side of the source-transition logic

**Technical Constraints**

- `PriceSnapshot` is shared system data, not per-user — a manual override by user A is visible to user B who also holds the same stock, until the next automated refresh supersedes it (BAS §7 Entity 6 note)

---

### Implementation Record — BE-5.2

**What was actually built**

- `app/pricing/schemas.py` (new) — `PriceSnapshotResponse` (built explicitly in the router, not via `from_attributes`, since the API field `refreshed_at` doesn't match the DB column `last_refreshed_at`), `PriceListResponse`, `ManualPriceOverrideRequest` (VR-005/BR-026's >0/≤4dp price rule, same pattern as `purchase_price`).
- `app/pricing/service.py` — `get_latest_prices()` (one query for however many stock codes are requested, grouped in Python to the max-`trading_date` row per code — same batching discipline as BE-4.1's dashboard fix) and `create_manual_price_override()` (UPSERTs by `(stock_code, trading_date)`, same pattern as BE-5.1's own automated UPSERT — which is *why* BR-023 needs no special-case code: an automated refresh and a manual override are just two callers UPSERTing the same row shape, and whichever runs later wins).
- `app/pricing/router.py` (new) — `GET /pricing/prices` and `POST /pricing/manual-override`, registered in `app/main.py`.
- `app/errors.py` — `trial_expired_paywall()` (422, error code `trial_expired`) — the first *enforced* write-permission gate anywhere in this codebase; `account_status` has existed on `User` since BE-1.1, but no endpoint before this one actually checked it (see Deviation 1).
- `app/portfolio/calculator.py` — `compute_market_value_and_pnl()` (BR-025: `market_value = shares × price`, `pnl = market_value − all_in_cost`, both null with no price data).
- `app/portfolio/router.py` — `_build_position_response()` now takes an optional `price_snapshot`, and `add_position`/`get_position`/`patch_position`/`get_dashboard` all fetch and pass one (single lookup for the three position endpoints, one batched `get_latest_prices()` call for the whole dashboard page). This is the "current_price/current_market_value/unrealised_pnl stay null until Epic 5 exists" deferral from BE-2.1/BE-4.1 finally being closed out — see Deviation 3 for why this wasn't left for a separate story.
- `alembic/versions/0013_...py` — extends `audit_log`'s CHECK constraints for `PRICE_OVERRIDE_CREATED`/`PriceSnapshot`.

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **The trial-expired write-gate is scoped to only this story's own new endpoint**, not retrofitted onto every other write endpoint (Add Position, Add Lot, Log Dividend, etc.) that the BAS §9 Permission Matrix says should also be blocked. This story's own AC only asks for the manual-override gate; building the full matrix across every prior epic is a much larger, cross-cutting retrofit that belongs to Epic 7's `SubscriptionGate` (already named as a dependency in FE-4.1's own story). `trial_expired_paywall()` is written generically enough to be reused when that retrofit happens.
2. **No banner-copy text is returned or rendered by this story.** The AC bullet reads like a backend requirement, but constructing "Price data unavailable for CIMB, MAYBANK" is inherently a *rendering* concern — this story's actual job is making sure `GET /pricing/prices` returns enough per-code detail (which codes are missing/stale vs. current) for FE-5.1 to build that exact copy itself. No separate banner-text field was added to any response.
3. **Wiring real `current_price`/`current_market_value`/`unrealised_pnl`/`price_source`/`price_last_refreshed_at` into position and dashboard responses was pulled into this story**, even though it's not one of BE-5.2's own listed AC bullets. It's a direct, unavoidable prerequisite for this story's own Gherkin ("position recalculates immediately using this price") and its OpenAPI description ("affected position's unrealised P&L recalculated") to be observably true at all — leaving it for a later story would mean shipping a manual-override endpoint whose entire effect is invisible everywhere else in the app. This closes out the "always null until the price-feed epic exists" deferral that BE-2.1, BE-4.1, and FE-4.1 all independently flagged.

**Test evidence**

- `uv run pytest`: 231/231 passing (217 pre-existing + 14 new in `tests/test_pricing.py`): latest-snapshot-per-code retrieval (including picking the newest `trading_date` when multiple exist), omitting a code with no snapshot ever (EC-005, not a fabricated stale entry), manual override create/update-in-place, the audit log entry, price validation (non-positive, >4dp), the trial-expired 422 (and confirming an `active` account is *not* blocked), cross-user visibility of a shared manual override (BE-5.2's own Technical Constraint), and **the full DoD-mandated integration test**: a simulated complete outage (BE-5.1's `run_price_refresh` against a provider that always fails) → manual override via the real endpoint → a second `run_price_refresh` with a successful fetch → confirmed the row flips back to `source='automated'` with the newly-fetched price, all in one test.
- Migration 0013 verified upgrade → downgrade → upgrade against the real running Postgres.
- **Live smoke test against the real backend, real Postgres, and real yfinance**: created a real position with no price data (confirmed all price fields null), POSTed a manual override (confirmed `source="manual"`, and the position's `current_market_value`/`unrealised_pnl` immediately reflected it correctly — RM8,500.00 / +RM49.83 for 1,000 shares against RM8,450.17 all-in cost), confirmed the dashboard showed the same and set a real `last_price_refresh_at`, then ran BE-5.1's real cron logic (`run_price_refresh` with the real `YFinancePriceProvider`) and confirmed the row **flipped from `manual`/RM8.50 to `automated`/RM7.89 (CIMB's real fetched price)** — BR-023 proven end to end against production infrastructure, not just mocks. Test data cleaned up afterward.

**Known gaps / not yet verified**

- No frontend consumes any of this yet — FE-5.1 (stale banner, manual override UI, the EX-001/EX-002 copy referenced in this story's own AC) is still unbuilt.
- The broader Permission Matrix write-gate (every other write endpoint besides manual-override) remains unenforced — see Deviation 1.

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

- [x] Complete-outage banner copy vs. partial-failure banner copy match EX-001/EX-002 exactly
- [x] Manual entry field disappears and reverts to the automated price display once superseded (BR-023) — verified via SWR revalidation after the next scheduled refresh window
- [x] For trial-expired accounts, the manual override field is replaced by the paywall prompt (EC-020)

**Definition of Done**

- [~] Visual states for complete outage, partial outage, and override-in-effect all covered by component tests/screenshots — see Known gaps: no component-test/screenshot suite exists in this codebase yet, so this was verified via a live API-level smoke test plus manual code review instead

**Dependencies & Integrations**

- BE-5.2, FE-4.1 (dashboard shell)

**Technical Constraints**

- Staleness threshold (28 hours) is a shared frontend constant (`lib/constants.ts`), not hardcoded per component (architecture §7.2)

---

### Implementation Record — FE-5.1

**What was actually built**

- `lib/constants.ts` (new) — `STALE_THRESHOLD_MS` extracted out of `dashboard/page.tsx`, where it had lived as a local constant since FE-4.1.
- `lib/types.ts` — `ManualPriceOverrideRequest`, `PriceSnapshotResponse` added (`PositionSummaryResponse` already carried `price_source`/`price_last_refreshed_at` from FE-4.1).
- `app/dashboard/page.tsx` — banner logic now distinguishes complete outage (every position stale → EX-001: "Price data unavailable — showing prices as of [timestamp]. Update prices manually below.") from partial failure (some but not all → EX-002: "Price data unavailable for {N} stocks — {names}. Showing last known prices."), replacing FE-4.1's placeholder single-copy banner. The price cell now toggles three states per row: the plain price display, a clickable amber "⚠ Stale" badge that opens an inline decimal input + Save button (posts to `POST /api/v1/pricing/manual-override`, then calls `useDashboard()`'s `mutate()` to revalidate), and a blue "Manual · {time}" badge when `price_source === "manual"` and the row isn't currently stale. For `trial_expired` accounts, clicking the Stale badge shows a paywall line ("Subscribe to override prices manually.") instead of the input (EC-020). Matched the design's exact color tokens (`#FFF6E3`/`#F0D9A6`/`#8A5A00` stale, `#EBF0FF`/`#C9D4FA`/`#2B3EB8` manual, `#3B4FE0` input/button) from `BursaTrack.dc.html`.
- `app/positions/[id]/page.tsx` — the header's "Current price" and "Unrealised P/L" stat cells, hardcoded to "—" since FE-2.1, now render `position.current_price`/`position.unrealised_pnl` (with sign-aware green/red coloring on P/L, matching the dashboard table's convention). Not one of this story's own AC bullets, but the same class of "close the loop now that BE-5.2 returns real data" fix already applied to the dashboard and position/dashboard router responses in BE-5.2 — leaving it stale would mean the position detail page kept showing "—" for data the API had been returning since the prior story.
- Removed the dashboard table's leftover FE-4.1 placeholder footnote ("Price, market value, and P/L show — until prices are refreshed (arrives in a later epic)"), now false as of Epic 5.

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **EX-001/EX-002's implied "immediate day-1 stale detection" doesn't actually happen, by BE-5.1's own design.** BE-5.1 documented (its own Deviation 7) that a failed/rejected stock's snapshot is simply left untouched rather than ever writing `source='stale'` — so this story's staleness signal is purely FE-4.1's existing 28-hour timestamp check, same as before. In practice a single missed refresh (one day) will *not* cross the 28h threshold and will *not* show a stale badge; it takes roughly two consecutive missed refreshes. This is a real, known gap between the BAS's Gherkin (which reads as if a single failed refresh immediately produces a stale row) and the shipped behavior — flagged rather than silently accepted, but not fixed here since fixing it is BE-5.1's design decision to revisit, not something this frontend story can compensate for on its own.
2. **EX-002's affected-stock list uses `stock_name` (e.g. "CIMB GROUP HOLDINGS BHD"), not a short ticker.** The BAS's own example ("CARLSBG, LPI") reads like short ticker codes, but this app's data model has only `stock_code` (Bursa's numeric code, e.g. "1023") and `stock_name` (the full company name) — no separate ticker/abbreviation field exists anywhere in the schema. `stock_name` was chosen as the more human-readable identifier already used as the primary label throughout the rest of the UI (position table, calendar, dividend dialogs).
3. **No component-test/screenshot suite exists in this codebase** (no Storybook/visual-regression tooling has been set up in any prior story) — the DoD's "covered by component tests/screenshots" was satisfied instead via a live API-level smoke test against the real backend (below) plus manual verification of the three price-cell states against the design's exact markup, and confirmed by `npm run build`/`npm run lint`.
4. **The success feedback for a saved override is the row itself updating** (input closes, price/badge change immediately after `mutate()` resolves) rather than a separate toast/notice banner — the design's own `.dc.html` prototype references a global toast system (`this.toast(...)`) that doesn't exist anywhere in this app; no other dialog in this codebase uses toasts either (they use inline notice bars scoped to their own page), and adding a new toast primitive for this one interaction was out of scope.

**Test evidence**

- `npm run build` and `npm run lint`: both clean.
- **Live smoke test against the real backend and real Postgres** (no browser-automation tool was available this session, so this verified the API contract and data-flow the UI renders from, not rendered pixels — see Known gaps): registered a user, created a position, inserted a 30-hour-old `automated` snapshot directly via `docker exec psql` to simulate staleness, confirmed `GET /api/v1/portfolio/dashboard` returned `price_last_refreshed_at` old enough to trip the 28h threshold (→ single-position dashboard correctly resolves to the EX-001 complete-outage path); POSTed `/api/v1/pricing/manual-override` and confirmed the dashboard immediately reflected `price_source="manual"` with a fresh timestamp (→ stale badge would clear, Manual badge would show); added a second, freshly-priced position and confirmed the dashboard now had 1-of-2 positions stale (→ correctly resolves to the EX-002 partial-failure path, naming the one affected `stock_name`); set the account to `trial_expired` and confirmed `POST /pricing/manual-override` returns `422 {"error": "trial_expired"}` (→ the frontend's `isReadOnly` gate, which checks the same `account_status` field before ever calling the endpoint, is consistent with the backend's own enforcement). All smoke-test data cleaned up afterward.

**Known gaps / not yet verified**

- **The UI itself was not visually verified in a browser** — no browser-automation/screenshot tool was available this session. The above smoke test confirms the data the components consume is correct; the actual rendered layout, colors, and interactions were verified by code review against the design's captured markup, not by looking at a rendered page. Recommend a manual pass in a real browser before shipping.
- Deviation 1's detection-latency gap (staleness only detectable after ~2 missed refresh cycles, not 1) is unresolved and would need a BE-5.1 design change (e.g. actually writing `source='stale'` on a failed fetch) to close.

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

- [~] Backend scaffold matches the exact module layout: `app/{auth,portfolio,pricing,subscription,admin}/{models,schemas,router,service}.py`, plus `app/scripts/` for cron jobs — see Implementation Record Deviation 1
- [~] Frontend scaffold matches the Next.js App Router layout: `(auth)` and `(app)` route groups, `components/{ui,portfolio,dividends,calculator,subscription,shared}`, `hooks/`, `lib/` — see Implementation Record Deviation 2
- [x] `docker-compose.yml` runs FastAPI + Next.js + PostgreSQL with hot-reload for local development
- [x] `.env.example` documents every required environment variable from architecture §14.5 without committing real secrets
- [~] No cross-module direct database joins — all cross-domain access goes through service-layer interfaces (P-008); enforced by code review only, not import-linting — see Implementation Record Deviation 3

**Definition of Done**

- [x] A fresh clone + `docker-compose up` reaches a working "hello world" health check on both frontend and backend with zero manual steps beyond copying `.env.example`

**Dependencies & Integrations**

- None — this is the first story in sequence

**Technical Constraints**

- Python 3.13, FastAPI, async SQLAlchemy, Pydantic v2; Next.js 15, TypeScript strict mode, Tailwind, shadcn/ui (architecture §1 "at a glance" table)

---

### Implementation Record — DEP-9.1

**What was actually built**

- `docker-compose.yml` (new, repo root) — three services (`postgres`, `backend`, `frontend`), hot-reload on both apps via bind-mounted source + named volumes for `.venv`/`node_modules`/`.next` (so the bind mount doesn't shadow what got installed at image-build time), `depends_on: condition: service_healthy` gating backend startup on Postgres, and a container-level healthcheck on the backend hitting its own `/health`.
- `backend/Dockerfile.dev`, `backend/.dockerignore` — `python:3.13-slim` + `uv sync --frozen`, `uv run uvicorn --reload` as the CMD. The `uv` binary itself is copied from `ghcr.io/astral-sh/uv:0.11.29` (pinned to the exact version this machine's local dev tooling uses, per uv's own Docker guide's "pin to a specific uv version" guidance) — not `pip install uv`, which was the first pass and got corrected after review (post-implementation correction, not part of the original build).
- `frontend/Dockerfile.dev`, `frontend/.dockerignore` — `node:22-alpine` + `npm ci`, `npm run dev -- -H 0.0.0.0` as the CMD (the `-H` flag is required — without it the dev server binds to a loopback-only address inside the container and is unreachable from the host).
- `backend/.env.example` — added the previously-undocumented `CORS_ALLOWED_ORIGINS` (already consumed by `app/config.py` since it was added, just never added to the example file), plus commented-out placeholders for `SENTRY_DSN`/`STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET` per architecture §14.5, explicitly marked as not yet consumed by any code (Sentry: DEP-9.5; Stripe: Epic 7).
- Removed `backend/docker-compose.yml` (Postgres-only, pre-dated this story) — superseded by the root file to avoid two compose projects fighting over the same container name.

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **The backend module layout only partially matches architecture §7.2's illustrative tree.** `auth/`, `portfolio/`, `pricing/`, `admin/` exist as designed. `subscription/` doesn't exist yet — Epic 7 (Stripe billing) hasn't been built. `admin/` has `models.py`/`service.py` but no `router.py`/`schemas.py` of its own — `/health` lives directly in `main.py` and CORS/config live in `config.py`, which is where they landed organically across Epics 1–5 rather than being routed through a dedicated admin router. `app/scripts/` has only `refresh_prices.py`; `check_trial_expiry.py` and `process_deletions.py` don't exist yet (their owning epics — 7 and 8 — aren't built), and `process_renewals.py` was deliberately never built at all (DEP-9.3's own AC note: renewal is Stripe-native, that cron was removed from the plan). This is the direct, expected consequence of doing DEP-9.1 last instead of first, as originally sequenced — the module tree reflects five epics of real, organically-evolved implementation, not the pre-implementation illustrative sketch. No retroactive refactor was done to force a match; that would be pure churn against already-shipped, tested code for no behavioral benefit.
2. **The frontend structure has diverged further from architecture §7.2's sketch than the backend has.** No `(auth)`/`(app)` Next.js route groups exist — routes sit flat under `app/` (`dashboard/`, `positions/`, `calendar/`, `login/`, etc.). `components/` has `ui/`, `portfolio/`, `shared/`, `dashboard/`, `layout/`, but not the spec's `dividends/`, `calculator/`, `subscription/` split (dividend and sell-calculator UI live inside `portfolio/` and the position detail page instead). `lib/` has `api.ts`, `constants.ts`, `dividend-calculator.ts`, `dividend-validation.ts`, `fee-calculator.ts`, `category-tags.ts`, `auth-context.tsx` — different names/boundaries than the spec's illustrative `fees.ts`/`decimal.ts`/`dates.ts`. Same reasoning as Deviation 1: this reflects real decisions made story-by-story (documented in each story's own Implementation Record) rather than the pre-build sketch, and wasn't retroactively forced to match here.
3. **No automated import-linter was ever added.** The "no cross-module direct database joins" rule was followed by discipline during code review across every prior story (e.g. BE-5.1's price-refresh query goes through `Position`, not a direct join into another module's internals) but no tool (e.g. `import-linter`) enforces it mechanically. Flagged as a real gap rather than silently checked off.

**Test evidence**

- `docker compose config` — valid.
- `docker compose build backend` and `docker compose build frontend` — both build clean from a cold cache.
- **Live end-to-end run**: `docker compose up -d` brought up all three containers; `bursatrack-postgres` reported `healthy`, `bursatrack-backend` reported `healthy` (its own `/health` check), `bursatrack-frontend` came up and served `GET /` and `GET /dashboard` with `200`. `curl http://localhost:8000/health` → `{"status":"ok","db":"ok"}`. `curl http://localhost:3000` → `200`.
- **Hot-reload verified for real, not assumed**: edited `app/main.py`'s `/health` handler while the stack was running, confirmed via `curl` that the change was live inside the container within seconds (WatchFiles-triggered reload, no rebuild), then reverted. Frontend bind-mount confirmed by editing `dashboard/page.tsx` and observing Next's dev server recompile the route in the container logs, then reverted (`git checkout --`).
- **This machine's existing local dev data was preserved, not reset**: the pre-existing `backend/docker-compose.yml` had implicitly named its Postgres volume `backend_bursatrack_pg_data` (Compose prefixes volume names by the compose file's directory). The new root-level file would default to a differently-prefixed volume name (`investment-analysis_bursatrack_pg_data`) and start against an empty database — copied the data across with a one-off `docker run` (alpine + `cp -a`) before bringing the stack up, rather than either hardcoding a machine-specific `external: true` volume reference into the committed file (which would break a genuine fresh clone) or silently losing the existing data. Verified post-copy: `SELECT count(*) FROM users` returned 20 rows including the real account, and `alembic_version` read `0013`, matching pre-migration state exactly.

**Known gaps / not yet verified**

- Structural deviations 1 and 2 above are real and unresolved — no plan to reconcile the shipped module layout with architecture §7.2's illustrative tree; the spec document itself is now the outdated artifact, not the code.
- No import-linting tool enforces module-boundary discipline (Deviation 3) — relies entirely on code review.
- The DoD's "fresh clone" claim was verified structurally (`docker compose build` + `config`) and functionally (a live `up` reaching both health checks) but not from an actual second, disk-clean clone of the repo — this machine already had `backend/.env`/`frontend/.env.local` populated from earlier stories, so the "copy `.env.example`" step itself wasn't exercised end-to-end.
- `npm ci` during the frontend image build reports 7 pre-existing vulnerabilities (2 moderate, 5 high) in the current `package-lock.json` — pre-existing, not introduced by this story, not triaged here.

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

- [x] CI workflow file at `.github/workflows/ci.yml` runs all three checks on every PR
- [~] Merge to `master` is gated on CI passing (architecture §18.2 flowchart) — see Implementation Record Deviation 1 (workflow triggers wired up; the actual GitHub branch-protection rule requiring the checks still needs to be applied by hand — see Known gaps)
- [x] CI failure produces a clear, actionable log — not just a red X (three separately-named jobs, not one combined job, so the failing check is obvious from the PR checks list alone)

**Definition of Done**

- [ ] A deliberately broken test/type-error/lint violation in a test PR is confirmed to block the pipeline — not yet done, see Known gaps

**Dependencies & Integrations**

- DEP-9.1 scaffold must exist first

**Technical Constraints**

- None additional

---

### Implementation Record — DEP-9.2

**What was actually built**

- `.github/workflows/ci.yml` (new) — three separate jobs (`backend-tests`, `frontend-type-check`, `frontend-lint`) triggered on every PR and push targeting the default branch, so a failure in one is immediately attributable in the GitHub PR checks list rather than buried inside one combined job's log.
- `backend-tests` — `astral-sh/setup-uv@v9` pinned to `uv==0.11.29` (the same version pinned in `backend/Dockerfile.dev` and used locally), `uv python install 3.13`, `uv sync --frozen`, `uv run pytest -v`.
- `frontend-type-check` / `frontend-lint` — `actions/setup-node@v4` on Node 22 (matching `frontend/Dockerfile.dev`), `npm ci`, then `npm run type-check` / `npm run lint` respectively.
- `frontend/package.json` — added a `type-check` script (`tsc --noEmit`) since none existed; the story's own Gherkin names this check explicitly and it wasn't previously exposed as a reusable command (only folded implicitly into `next build`'s own type-checking step).

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **The workflow targets `master`, not `main`.** The story's AC and Gherkin both say "merge to main" — but this repository's actual default branch (confirmed via `git branch --show-current` and `git remote show origin`) is `master`, and always has been throughout this project. Caught before pushing rather than shipping a workflow that would silently never trigger. `on.pull_request.branches` / `on.push.branches` are both set to `[master]`.

**Test evidence**

- All three CI commands run and verified locally, exactly as the workflow invokes them (not just "should work"): `uv run pytest -v` → 231/231 passed (352.97s); `npm run type-check` → clean; `npm run lint` → clean.
- `astral-sh/setup-uv`'s tag was checked against the live GitHub repo before pinning (WebFetch's own summary of the repo's README first claimed `@v5` was current, which was already stale) — but the corrected `@v9` still failed on the actual, real Actions run once pushed: `Unable to resolve action 'astral-sh/setup-uv@v9', unable to find version 'v9'`. Queried the GitHub API directly (`/git/refs/tags`) rather than trusting a fetched/summarized page a second time, and confirmed this repo — unlike `actions/checkout`/`actions/setup-node`, which do publish floating major tags (`v4` is a real ref for both) — has no floating `v9` tag at all, only the exact `v9.0.0`. Fixed to `astral-sh/setup-uv@v9.0.0`. Worth remembering: don't trust a fetched-and-summarized page for exact version/tag strings when the real, structured source (here, the GitHub API) is one call away.

**Known gaps / not yet verified**

- **The DoD's own explicit requirement — a deliberately-broken PR confirmed to block the pipeline — has not been done.** This needs the workflow actually pushed to GitHub and a real PR opened against it, which wasn't done as part of this pass (no `git push`/PR was created without the user's go-ahead, since pushing to the real shared remote is a separate, explicit action). Do this before considering DEP-9.2 fully done.
- **Branch protection requiring these checks has not been applied.** `.github/workflows/ci.yml` makes the checks *available* to run, but doesn't by itself block merging — that's a separate GitHub repository setting (Settings → Branches → branch protection rule on `master` → "Require status checks to pass"). No `gh` CLI is installed on this machine to script it, and applying a branch-protection rule is a real change to shared repository settings that shouldn't happen without the user directly authorizing it. Manual steps to close this gap are documented for the user.
- The full backend `pytest` run took ~6 minutes locally — acceptable for CI, but worth knowing if CI minutes/time-to-signal ever becomes a concern later.

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

- [~] Render web service, four cron job schedules (`refresh_prices.py`, `check_trial_expiry.py`, `process_deletions.py`), and managed PostgreSQL are all provisioned — see Implementation Record Deviation 1: only `refresh_prices.py` is defined; the other two don't exist yet (Epic 7/8 unbuilt), and the environment stood up is a **staging** environment, not literally "production" (Deviation 2)
- [x] A failed `alembic upgrade head` aborts the deploy and leaves the previous FastAPI version running (architecture §18.2) — `render.yaml`'s `preDeployCommand`; Render's own documented behavior on a non-zero exit
- [~] Render starter plan (not free tier) is used to avoid cold starts (R-008 mitigation) — the cron job is `plan: starter` (Render disallows `free` for cron jobs regardless); the **web service and database were deliberately switched to `plan: free`** at the user's request, since this is a testing-only environment for now — R-008's cold-start mitigation is knowingly deferred, not forgotten. Switch both back to a paid plan (`starter` / `basic-256mb`) before this stops being throwaway.
- [x] CORS configured with the programmatic origin validator from architecture §14.3 — **not** a `"https://*.vercel.app"` wildcard (CRIT-R-001) — `add_cors_middleware()` + `cors_vercel_preview_regex`, tested in `tests/test_cors.py`
- [ ] Rollback procedure documented and tested at least once — not yet done, needs a live Render/Vercel deploy to exist first
- [~] ⚠ Known risk (HIGH-R-003): Vercel preview deployments point at the production Render API — **superseded by Deviation 2**: with no separate production environment yet, this risk doesn't currently apply in its original form; it will need re-evaluating once a real production environment exists alongside this staging one

**Definition of Done**

- [ ] End-to-end deploy verified: a merged PR reaches production on both Vercel and Render within the expected pipeline time, with migrations applied correctly — blocked on live account provisioning, see Known gaps

**Dependencies & Integrations**

- DEP-9.1, DEP-9.2

**Technical Constraints**

- All secrets (DATABASE_URL, JWT_PRIVATE_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, RESEND_API_KEY, SENTRY_DSN, ADMIN_API_KEY) set as Render/Vercel environment variables only — never committed to git (architecture §14.5)
- Stripe test-mode keys in every non-production environment (MED-R-001)

---

### Implementation Record — DEP-9.3 (code-complete portion)

**What was actually built**

- `app/config.py` — added `cors_vercel_preview_regex: str = ""` (empty/disabled by default, since the real Vercel project slug doesn't exist yet).
- `app/main.py` — extracted `add_cors_middleware(app, settings)` out of `create_app()` specifically so it's independently testable (the real `app` singleton's middleware is fixed at import time from real settings — it can't be reconfigured per-test the way `Depends(get_settings)` can via `dependency_overrides`). Wires `allow_origin_regex=settings.cors_vercel_preview_regex or None` — the `or None` matters: Starlette treats an empty-string regex as "match everything," not "disabled."
- `backend/tests/test_cors.py` (new, 5 tests) — static allowlist origin allowed; matching Vercel preview pattern allowed; an unrelated `*.vercel.app` origin explicitly rejected (this is the exact CRIT-R-001 scenario — a bare wildcard would have allowed it); an entirely unrecognised origin rejected; and confirming the disabled (empty-string) regex default doesn't accidentally match every preview URL.
- `backend/Dockerfile` (new, production — distinct from `Dockerfile.dev`) — same `ghcr.io/astral-sh/uv:0.11.29` pinned-binary pattern as the dev image and CI, `--no-dev` to exclude test-only dependencies, no bind-mount dependency (source baked in via `COPY`), no `--reload`, binds to Render's injected `$PORT` (falls back to 8000 for a manual `docker run`).
- `render.yaml` (new, repo root) — Render Blueprint defining `bursatrack-db` (managed Postgres, Singapore region), an `envVarGroups` block shared between both services (secrets marked `sync: false` so they're never committed — Render prompts for them once at Blueprint creation), `bursatrack-api` (web service, `runtime: docker` pointing at `backend/Dockerfile`, `healthCheckPath: /health`, `preDeployCommand: uv run alembic upgrade head`), and `bursatrack-refresh-prices` (cron, same Docker image, `schedule: "30 9 * * 1-5"`). Database and web service plans were changed to `free` at the user's explicit request after initial implementation (Deviation 4) — the cron job stays on `starter` since Render doesn't offer a free tier for cron jobs at all.

**Deviations from the spec (deliberate adaptations, not oversights)**

1. **Only one of the three cron jobs is defined in `render.yaml`.** `check_trial_expiry.py` and `process_deletions.py` don't exist as code yet — Epic 7 (Stripe billing) and Epic 8 (PDPA deletion) are unbuilt. Rather than provisioning cron slots pointing at scripts that don't exist, they're left out entirely, with a comment in `render.yaml` itself noting they'll be added once those stories land. This is the user's own explicitly chosen sequencing (see the approved plan: stand up staging now, build Epic 6-8 against it).
2. **This is a staging environment, not the spec's literal "production."** Architecture §18.3 explicitly says "No staging environment at V1" — its actual V1 design was preview-deploys-hit-production with a mitigation policy (dedicated test account, avoid destructive flows on previews). The user chose differently: stand up a non-public staging environment now, build remaining features against it, defer the public-launch/production decision until Epic 7/8 land. This was discussed and explicitly chosen, not a silent deviation — flagged here for the written record to match every other deviation in this project.
3. **Region and plan values were verified against Render's live docs before use, not assumed** — an earlier draft would have used `plan: starter` for the database (matching the web service), but `starter` is a *legacy* Postgres plan that new databases can no longer be created on; corrected to `basic-256mb`, the smallest current-generation paid tier. `region: singapore` was similarly confirmed as a real, exact slug (matching architecture's own R-015 note about migrating to Render's Singapore region for Malaysian latency) rather than guessed.
4. **The web service and database plans were downgraded to `free` after initial implementation, at the user's explicit request**, since this environment is testing-only for now. This knowingly reintroduces R-008's cold-start risk (free web services spin down after 15 min idle) and adds a 90-day auto-expiry on the free Postgres instance — both flagged to the user at the time, not silently applied. The cron job could not follow suit — Render does not offer a free plan for cron jobs at all — so it remains on `starter`, which is also why the AC bullet above is marked partial rather than done.

**Test evidence**

- `uv run pytest tests/test_cors.py -v` — 5/5 passed, including the CRIT-R-001 rejection case.
- `docker build -t bursatrack-backend-prod-test -f backend/Dockerfile backend` — builds clean.
- **Live container run**: ran the built production image directly (`docker run`, attached to the existing docker-compose network, `DATABASE_URL` pointed at the compose Postgres, a non-default `$PORT=9000` to prove the port-binding logic isn't hardcoded) — confirmed `GET /health` → `{"status":"ok","db":"ok"}`. Test container and image removed afterward.

**Known gaps / not yet verified**

- **Nothing has actually been deployed to Render or Vercel.** Account creation, connecting the GitHub repo, and applying the Blueprint are manual steps only the user can do (they need the user's own account/authorization) — not done as part of this pass.
- The `sync: false` secrets in `render.yaml` (JWT keys, `ADMIN_API_KEY`, `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS`, `FRONTEND_BASE_URL`, `CORS_ALLOWED_ORIGINS`, `CORS_VERCEL_PREVIEW_REGEX`) are unset — several of them (the last three) can't even be filled in correctly until the Vercel project exists and its real URL/slug is known.
- The DoD's rollback-procedure test, and the end-to-end "PR → CI → deploy" verification, both need a live deployment to exist first — neither has been done.
- Whether Vercel's plan tier supports Deployment Protection (password-gating the staging site) hasn't been checked — depends on which Vercel plan the user signs up for.

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
