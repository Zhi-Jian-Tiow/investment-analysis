# BursaTrack — Architecture Decision Record (ADR) Summary

**Document version:** 1.0  
**Produced by:** Architecture Decision Workshop (Stage 2)  
**Date:** 2026-06-27  
**Status:** Final — approved by Aaron Tiow  

This ADR Summary is the authoritative input for the Solution Architecture Document. Every decision recorded here was made explicitly by the product owner. No decision was assumed or defaulted by the facilitator.

---

## Open Technical Questions — Resolution Status

| OTQ ID | Question | Status | Resolved In |
|---|---|---|---|
| OTQ-001 | Fee calculation authority | ✅ Resolved | ADR-003 |
| OTQ-002 | Session storage mechanism | ✅ Resolved | ADR-005 |
| OTQ-003 | yfinance fallback source | ✅ Resolved | ADR-007 |
| OTQ-004 | Price outage banner surfacing mechanism | ✅ Resolved | ADR-007 |
| OTQ-005 | Stamp duty rate configurability without code deploy | ✅ Resolved | ADR-012 |
| OTQ-006 | Stock code reference data strategy | ✅ Resolved | ADR-009 |
| OTQ-007 | CSV import processing model | ✅ Resolved | ADR-006 |
| OTQ-008 | Payment webhook idempotency | ✅ Resolved | ADR-007 |
| OTQ-009 | Concurrency model for lot and dividend updates | ✅ Resolved | ADR-004 |
| OTQ-010 | Position aggregate materialisation strategy | ✅ Resolved | ADR-004 |
| OTQ-011 | PDPA hard-delete scope for shared PriceSnapshot records | ✅ Resolved | ADR-009 |
| OTQ-012 | Subscription grace period duration | ⚠️ Deferred | Product decision — default to 3 days for implementation |

---

## ADR-001 — Application Architecture Style

**Problem Statement:** The overall structural pattern of the system must be chosen before domain boundaries, service interfaces, and deployment topology can be defined.

**Relevant Requirements:** Solo founder; MVP velocity; single deployable unit preferred; domain boundaries required for maintainability (portfolio, subscription, pricing, auth, admin).

**Options Considered:** Modular monolith, microservices, traditional monolith.

**Summary of Trade-offs:** Microservices add operational overhead incompatible with a solo bootstrapped MVP. A traditional monolith lacks the domain boundary enforcement needed for long-term maintainability. A modular monolith provides enforced domain separation within a single deployable, allowing the codebase to grow cleanly.

**Final Decision:** Modular monolith — single deployable unit, internally structured as distinct modules per domain.

**Rationale:** Fastest path to working software without sacrificing the code organisation needed to scale the team later. Domains can be extracted into separate services in V2 if required.

**Domain boundaries (minimum):** `portfolio` (lots, positions, dividends), `pricing` (price snapshots, yfinance integration), `subscription` (plans, billing, trial), `auth` (users, sessions), `admin` (config, audit).

**Dependencies:** All subsequent decisions.

**Outstanding Risks:** None at this stage.

**Follow-up Actions:** Define module interface contracts before implementation begins; no direct cross-module database joins (go through service layer interfaces).

---

## ADR-002 — Backend Language and Framework

**Problem Statement:** The server-side programming language and web framework must be selected before API design, ORM selection, and background processing can be specified.

**Relevant Requirements:** Developer familiarity is the primary constraint; MVP velocity.

**Options Considered:** Python / FastAPI, Node.js / Express, Go / Gin.

**Summary of Trade-offs:** FastAPI is the fastest Python framework for building REST APIs with automatic OpenAPI documentation, native async support, and Pydantic for validation. Aaron has existing Python and FastAPI experience — switching languages for MVP introduces unnecessary risk.

**Final Decision:** Python / FastAPI.

**Rationale:** Familiarity reduces implementation risk. FastAPI's Pydantic integration covers input validation automatically. Native async support aligns with async SQLAlchemy and BackgroundTasks.

**Dependencies:** ADR-001 (modular monolith).

**Outstanding Risks:** Python's GIL limits CPU-bound concurrency; not a concern for this I/O-bound application.

**Follow-up Actions:** None.

---

## ADR-003 — Frontend Framework and Fee Calculation Model

**Problem Statement:** The client-side technology stack must be chosen, and the authority model for fee calculation (client vs. server) must be established.

**Relevant Requirements:** Developer familiarity; pre-built accessible component library; TypeScript for type safety; fee calculation must be auditable and authoritative server-side (BAS v2.0 CRIT-01 correctness requirement).

**Options Considered:**
- Framework: Next.js, Vite + React, Vue.js
- Fee calculation: client-only, server-only, client-preview + server-authoritative

**Summary of Trade-offs:** Next.js + TypeScript provides SSR capability, the strongest Next.js-native tooling (Vercel), and TypeScript type safety. shadcn/ui provides accessible, unstyled components built on Radix UI that integrate natively with Tailwind CSS. Client-preview + server-authoritative fee calculation gives instant UX feedback while ensuring the server is always the single source of truth for stored values.

**Final Decision:**
- Framework: Next.js + TypeScript + Tailwind CSS + shadcn/ui
- Fee calculation: client preview (TypeScript, for immediate UI feedback) + server authoritative (Python, for all stored values)

**Rationale:** Aaron has existing Next.js and TypeScript experience. The client-preview + server-authoritative model satisfies both the UX requirement (instant fee feedback) and the correctness requirement (server validates before any data is persisted).

**Dependencies:** ADR-002 (FastAPI backend for server-authoritative calculation).

**Outstanding Risks:** The client-side TypeScript fee formula must be kept in sync with the server-side Python formula. A divergence would show incorrect previews. Mitigate with integration tests that assert client and server return identical results for the same inputs.

**Follow-up Actions:** Write a shared test fixture that runs the fee calculation through both the TypeScript and Python implementations; assert parity.

---

## ADR-004 — Database, ORM, Migration, Concurrency, and Aggregates

**Problem Statement:** The database engine, ORM, migration toolchain, concurrency control mechanism, and position aggregate computation strategy must all be decided together due to their interdependencies.

**Relevant Requirements:** Developer familiarity with PostgreSQL and SQLAlchemy; ACID transactions required (BAS v2.0 data consistency invariants); concurrent lot editing must not produce corrupted cost basis; position aggregates must reflect all lots accurately.

**Options Considered:**
- Database: PostgreSQL, MySQL, SQLite
- ORM: SQLAlchemy, raw SQL, Peewee
- Migrations: Alembic, Django migrations
- Concurrency: optimistic locking (version field), pessimistic locking (SELECT FOR UPDATE), last-write-wins
- Aggregates: materialised, computed at query time

**Summary of Trade-offs:** PostgreSQL is the proven choice for financial data with full ACID guarantees. SQLAlchemy is the most mature Python ORM with async support. Alembic is the standard migration tool for SQLAlchemy projects. Version-field optimistic locking provides concurrency safety without locking rows, with a full audit trail. Computing position aggregates at query time avoids the sync complexity of materialised aggregates at V1 scale.

**Final Decision:**
- Database: PostgreSQL (managed, via Render)
- ORM: SQLAlchemy (async) + Alembic migrations
- Concurrency: optimistic locking — `version` field on `Lot` and `DividendTranche`; increment on every write; reject if version mismatch on update
- Position aggregates: computed at query time; `position_id` index required

**Rationale:** All choices align with Aaron's existing experience. Version-field optimistic locking was chosen over pessimistic locking specifically for its auditability and traceability properties. Query-time aggregate computation is correct and performant at V1 scale with proper indexing.

**Dependencies:** ADR-001, ADR-002.

**Outstanding Risks:**
- Position aggregate query performance degrades as the number of lots per user grows. Mitigate by adding a covering index on `(position_id, status)` and monitoring query times via Sentry performance.
- Alembic migration failures during deployment must be caught by the pre-deploy hook (ADR-011).

**Follow-up Actions:**
- Add `version` column to `Lot` and `DividendTranche` in schema design.
- Index `position_id` on all lot-related tables.
- Establish backwards-compatible migration authoring rule in engineering guidelines.

---

## ADR-005 — Authentication, Session Management, and Authorisation

**Problem Statement:** The authentication library, session token mechanism, and password hashing strategy must be decided before user management flows, PDPA deletion scope, and security hardening can be specified.

**Relevant Requirements:** Secure session management; token revocation capability (for logout, password reset, account deletion); PDPA hard-delete must invalidate sessions; developer productivity over third-party auth overhead.

**Options Considered:**
- Auth library: fastapi-users, Auth0/Clerk (third-party), custom implementation
- Session mechanism: JWT in HTTP-only cookie + token_version, Redis session store, database session table
- Password hashing: bcrypt, argon2id, scrypt

**Summary of Trade-offs:** fastapi-users provides a complete auth implementation (registration, login, password reset, email verification) with FastAPI integration, avoiding the overhead of a third-party provider setup and the complexity of a custom implementation. JWT + token_version avoids the need for a Redis session store while still enabling token revocation — invalidation is achieved by incrementing `token_version` on the User record, which causes all outstanding JWTs to fail validation.

**Final Decision:**
- Auth library: fastapi-users
- Session mechanism: JWT stored in HTTP-only, Secure, SameSite=Lax cookie; `token_version` field on `User` table; JWT must include `token_version` and is rejected if it does not match the current value
- Password hashing: bcrypt, cost factor 12

**Rationale:** fastapi-users reduces implementation time vs. both third-party integration and custom auth. JWT + token_version was chosen over a Redis session store to avoid adding Redis as an infrastructure dependency (consistent with the no-Redis architectural direction).

**Dependencies:** ADR-002 (FastAPI), ADR-004 (PostgreSQL for token_version field).

**Outstanding Risks:** fastapi-users is an open-source library with a smaller maintenance team than commercial auth providers. Monitor for security advisories.

**Follow-up Actions:**
- Add `token_version INTEGER DEFAULT 0` to User schema.
- Increment `token_version` on: logout, password change, account deletion initiation.
- Validate `token_version` match in the JWT authentication middleware.

---

## ADR-006 — Background Processing

**Problem Statement:** Scheduled jobs (price refresh, trial expiry, subscription renewal, PDPA deletion) and user-triggered async tasks (CSV import, email delivery) must be handled without blocking the web request thread or introducing unnecessary infrastructure.

**Relevant Requirements (OTQ-007):** CSV import processing must not block the HTTP request thread (up to 30-second processing window); users must receive feedback on import progress; scheduled jobs must respect the Bursa Malaysia trading calendar.

**Options Considered:**
- Scheduled jobs: APScheduler (in-process), external platform cron, Celery Beat + Redis
- Async tasks: FastAPI BackgroundTasks, ARQ + Redis, Celery + Redis

**Summary of Trade-offs:** In-process schedulers (APScheduler) create multi-worker duplication risks and compete with web request threads. Celery and ARQ require Redis, which has been deliberately avoided throughout this architecture. External platform cron (Render native cron jobs) is the simplest reliable pattern: each job is a standalone Python script, invoked by the platform scheduler, with no in-process interference.

**Final Decision:**
- Scheduled jobs: Render native cron jobs; one Python script per job type
- Async tasks: FastAPI `BackgroundTasks` for email delivery (fire-and-forget); FastAPI `BackgroundTasks` + `ImportJob` PostgreSQL table for CSV import
- CSV import flow (OTQ-007): `POST /import/csv` → validate → create `ImportJob(status="processing")` → start BackgroundTask → return `{job_id}`; client polls `GET /import/status/{job_id}` every 2 seconds; `ImportJob` updated to `complete` or `failed` with row-level result payload on completion

**Rationale:** External cron eliminates multi-worker duplication risk and separates concerns cleanly. BackgroundTasks + ImportJob table handles async task execution without Redis. Status polling via PostgreSQL is simple, correct, and requires no additional infrastructure.

**Dependencies:** ADR-002 (FastAPI BackgroundTasks), ADR-004 (ImportJob table in PostgreSQL), ADR-010 (Render for native cron).

**Outstanding Risks:**
- If the FastAPI process restarts mid-import, the BackgroundTask is lost. The `ImportJob` row remains in `"processing"` state — detectable, but the user must re-upload. Acceptable for V1.
- Cron scripts must handle the Bursa Malaysia trading calendar (price refresh skips weekends and public holidays). Must be implemented in the refresh script.

**Follow-up Actions:**
- Add `ImportJob` table to schema: `(id UUID, user_id, status, result_payload JSONB, created_at, updated_at)`.
- Implement trading calendar check in the price refresh script (maintain a list of Malaysian public holidays).

**Scheduled job inventory:**

| Job | Script | Render cron schedule |
|---|---|---|
| Daily price refresh | `scripts/refresh_prices.py` | `30 9 * * 1-5` (5:30 PM MYT = 09:30 UTC, Mon–Fri) |
| Trial expiry check | `scripts/check_trial_expiry.py` | `0 1 * * *` (1:00 AM UTC daily) |
| Subscription renewal | `scripts/process_renewals.py` | `0 2 * * *` (2:00 AM UTC daily) |
| PDPA hard-delete | `scripts/process_deletions.py` | `0 3 * * *` (3:00 AM UTC daily) |

---

## ADR-007 — External Integrations

**Problem Statement:** Market data sourcing, payment processing, and email delivery must each have a designated provider, with failure modes and idempotency strategies defined.

**Relevant Requirements (OTQ-003, OTQ-004, OTQ-008):** yfinance is an unofficial dependency with no SLA; a fallback or degradation strategy is required. Payment webhooks must be processed idempotently. Email delivery must be reliable for PDPA and subscription lifecycle events.

**Options Considered:**
- Market data: yfinance only, yfinance + Stooq fallback, yfinance + paid API fallback
- Payment: Stripe, Billplz, dual gateway
- Email: Resend, SendGrid, AWS SES

**Summary of Trade-offs:**
- yfinance: Both free fallback options (Stooq) are equally unofficial. A paid fallback adds pre-revenue cost. The correct V1 approach is honest degradation via a stale-data banner — users see last-known prices with a clear timestamp. This is also the OTQ-004 resolution.
- Stripe: Subscription management, dunning, trial handling, and webhook idempotency tooling are mature and reduce engineering effort significantly vs. Billplz. FPX support is a genuine gap but is a V2 concern.
- Resend: Free tier (3,000 emails/month) covers V1 transactional volume; excellent Python SDK; React Email templating integrates with Next.js.

**Final Decision:**
- Market data (OTQ-003 ✅): yfinance only; no fallback for V1
- Price outage surfacing (OTQ-004 ✅): `last_refreshed_at` timestamp on `PriceSnapshot`; Next.js dashboard shows per-stock stale indicator if `now() - last_refreshed_at > 28 hours`; product-level banner if majority of holdings are stale
- Payment provider: Stripe; webhook idempotency (OTQ-008 ✅) via `processed_webhook_events` table storing Stripe `event.id`; check for duplicate before processing
- Email provider: Resend

**Rationale:** All three decisions optimise for V1 cost and implementation speed. yfinance degradation is the honest approach for a pre-revenue product. Stripe's subscription infrastructure saves weeks of engineering time vs. Billplz for recurring billing.

**Dependencies:** ADR-004 (PostgreSQL for idempotency table and PriceSnapshot), ADR-006 (BackgroundTasks for email delivery).

**Outstanding Risks:**
- yfinance can break without warning when Yahoo Finance changes its scraping surface. No automated recovery; requires manual intervention and Sentry alert.
- Stripe does not support FPX (Malaysian online banking transfer). This is a meaningful gap for the Malaysian market — address in V2.
- SST applicability on subscription fees remains an open product/legal question (flagged in BAS). Stripe's tax configuration must be set correctly before launch.

**Follow-up Actions:**
- Verify SST applicability before launch and configure Stripe Tax accordingly.
- Add `processed_webhook_events(event_id TEXT PRIMARY KEY, processed_at TIMESTAMPTZ)` to schema.
- Implement FPX support via Billplz in V2.

---

## ADR-008 — Caching Strategy

**Problem Statement:** A caching strategy must balance dashboard performance with operational simplicity, consistency with the no-Redis architectural direction, and V1 user volumes.

**Relevant Requirements:** Dashboard load times must feel responsive; stock reference list must not be re-queried on every autocomplete keystroke; no Redis.

**Options Considered:** No cache layer, in-process `lru_cache`, Redis distributed cache, frontend SWR.

**Summary of Trade-offs:** Portfolio data is user-specific and cannot be efficiently shared across a cache. Price data is already persisted in PostgreSQL after the daily refresh — the database is the cache. The only data that benefits from in-process caching is the stock reference list (infrequently changing, shared across all users). SWR on the frontend provides stale-while-revalidate semantics that make the dashboard feel instant without requiring backend caching infrastructure.

**Final Decision:**
- Backend: `cachetools.TTLCache` (1-hour TTL) on the stock reference endpoint in the FastAPI service layer; `Cache-Control: max-age=3600` HTTP header on `/stocks` response
- Frontend: SWR with window-focus revalidation on all dashboard data fetching
- No Redis; no distributed cache

**Rationale:** In-process TTLCache requires zero infrastructure. SWR is included in the Next.js ecosystem. Together they cover all V1 caching needs.

**Dependencies:** ADR-002 (FastAPI), ADR-003 (Next.js + SWR), ADR-004 (PostgreSQL as primary data store).

**Outstanding Risks:** None at V1 scale.

**Follow-up Actions:** None.

---

## ADR-009 — Data Storage

**Problem Statement:** Reference data (stock codes), file handling (CSV uploads), PDPA deletion scope, and backup strategy must be defined.

**Relevant Requirements (OTQ-006, OTQ-011):** Stock reference list must be queryable and maintainable without code deployment. PDPA hard-delete must not corrupt other users' historical P&L data via `PriceSnapshot` deletion.

**Options Considered:**
- Stock reference: PostgreSQL table, bundled JSON file, external scraper
- CSV handling: transient temp file, object storage (S3/R2)
- PDPA scope: delete all user data including PriceSnapshot vs. retain shared market data
- Backup: managed provider backups, custom backup scripts

**Summary of Trade-offs:** A PostgreSQL `stocks` table can be updated via admin script without a code deployment, supports relational queries (filter by sector/market), and integrates with the existing database. Bundled JSON files require a code deployment for updates. Object storage adds cost and complexity for CSV files that have no retention requirement. `PriceSnapshot` records are market data (no PII) shared across all users — deleting them on user deletion would corrupt other users' data and is not required by PDPA.

**Final Decision:**
- Stock reference data (OTQ-006 ✅): PostgreSQL `stocks` table; seeded from a static CSV of all Bursa-listed securities at initial deployment; updated via admin script for IPOs/delistings
- PDPA hard-delete scope (OTQ-011 ✅):
  - **Delete:** `users`, `lots`, `dividend_tranches`, `import_jobs`, `processed_webhook_events` for that user
  - **Retain:** `price_snapshots`, `stocks` (market/reference data; no PII)
  - **Anonymise (not delete):** subscription billing records (set `user_id = NULL`; retain for accounting — Malaysian tax law requires 7 years)
- CSV upload handling: write to Python `tempfile.NamedTemporaryFile`; delete after BackgroundTask completes; no persistent file storage
- Database backup: rely on Render managed PostgreSQL automated daily snapshots; no custom backup scripts for V1

**Rationale:** All decisions favour operational simplicity. The anonymise-not-delete approach for billing records is the legally safe choice under Malaysian tax record-keeping obligations.

**Dependencies:** ADR-004 (PostgreSQL), ADR-010 (Render managed PostgreSQL for backups).

**Outstanding Risks:** Anonymising billing records rather than deleting them must be reviewed against PDPA requirements — confirm with legal counsel before launch.

**Follow-up Actions:**
- Source the initial Bursa Malaysia securities list and prepare the seed CSV before first deployment.
- Add `stocks(code TEXT PK, name TEXT, market TEXT, sector TEXT, instrument_type TEXT, is_active BOOLEAN)` to schema.
- Implement anonymisation (null `user_id`) rather than deletion for billing records in the PDPA deletion script.

---

## ADR-010 — Infrastructure and Hosting

**Problem Statement:** Cloud provider, hosting platform, containerisation strategy, and the deployment topology for all BursaTrack components must be decided.

**Relevant Requirements:** Solo founder; operational simplicity; Render native cron job support (required by ADR-006); Next.js hosting with preview deployments; managed PostgreSQL with automated backups.

**Options Considered:**
- Hosting: Vercel + Render, Railway, Fly.io, AWS
- Containerisation: Docker everywhere, Docker Compose for local dev only, no Docker

**Summary of Trade-offs:** Vercel is purpose-built for Next.js (same company); its free tier covers V1 completely and provides automatic preview deployments on every PR branch. Render provides managed PostgreSQL, FastAPI web service hosting, and native cron job support — all required capabilities — on a single platform with a generous free/starter tier. Railway is simpler (one platform) but less specialised for Next.js and has a less generous free tier. AWS is too operationally expensive for a solo founder at MVP stage. Docker Compose for local dev provides environment consistency without adding Dockerfile maintenance for production.

**Final Decision:**
- Next.js frontend: Vercel (free tier)
- FastAPI backend + cron jobs: Render web service + Render cron jobs
- PostgreSQL: Render managed PostgreSQL
- Local development: Docker Compose (`docker-compose.yml` running FastAPI + Next.js + PostgreSQL)
- Production deployment: native PaaS (no Dockerfiles required for production)

**Estimated V1 cost:** USD 0–14/month (Render free tier for PostgreSQL has 90-day expiry; USD 7/month for persistent managed PostgreSQL; USD 7/month for always-on FastAPI service).

**Rationale:** Vercel + Render is the lowest-cost, highest-productivity combination for a Next.js + FastAPI stack. Both platforms deploy from git push. Render's native cron eliminates any need for a separate scheduler process.

**Dependencies:** ADR-001 through ADR-009.

**Outstanding Risks:**
- Render's default region is US. For Malaysian users, latency to the FastAPI API will be higher than a Singapore region deployment. Render has a Singapore region (`Singapore (Southeast Asia)`) available on paid plans — migrate when paying users are present and latency becomes a concern.
- Render free tier spins down web services after 15 minutes of inactivity (cold start ~30 seconds). Upgrade to starter plan (USD 7/month) at launch to eliminate cold starts.

**Follow-up Actions:**
- Write `docker-compose.yml` for local development before first implementation sprint.
- Migrate to Render Singapore region when first paying Malaysian users are present.

---

## ADR-011 — Deployment Strategy

**Problem Statement:** How code moves from a developer's machine to production, how database migrations are applied safely, and how rollback is executed must be defined before implementation begins.

**Relevant Requirements:** Solo founder; git-push deployment preferred; Alembic migrations must run before new FastAPI code takes traffic; regressions in financial calculation logic must be caught before production.

**Options Considered:**
- CI/CD: GitHub Actions + platform auto-deploy, platform-native auto-deploy only
- Environments: local + production, local + staging + production
- Migration: Render pre-deploy command, manual migration, migration on startup
- Rollback: platform dashboard, manual git revert

**Summary of Trade-offs:** GitHub Actions CI catches regressions in fee calculation and dividend math before they reach production — the cost of 15 minutes of setup is justified by the criticality of the financial logic. A staging environment doubles hosting cost and operational overhead; Vercel's automatic preview deployments cover frontend review without an additional Render instance. Render's pre-deploy command is the correct mechanism for safe Alembic migrations — the deploy is aborted if the migration fails, keeping the old version running.

**Final Decision:**
- CI/CD: GitHub Actions workflow on every PR and push to `main`; runs `pytest` (FastAPI), `tsc --noEmit` (Next.js type check), `eslint` (Next.js linting); Render and Vercel deploy only after checks pass
- Environments: local + production; Vercel preview deployments used for frontend branch review
- Database migration: Render pre-deploy command `alembic upgrade head`; migration must succeed before new FastAPI version starts
- Migration authoring rule: all migrations must be backwards-compatible (additive only: new columns, new tables); destructive changes (drops, renames) applied in a separate subsequent deployment
- Rollback: Vercel one-click rollback from deployment history; Render one-click redeploy of previous build; `alembic downgrade -1` for database rollback if needed

**Rationale:** The backwards-compatible migration rule is the most important engineering practice to establish — it makes every deployment safe to roll back.

**Dependencies:** ADR-010 (Render + Vercel).

**Outstanding Risks:** If a migration runs successfully but the new FastAPI version has a runtime bug, rollback requires both a Render redeploy and an `alembic downgrade -1`. Document this procedure before first production deployment.

**Follow-up Actions:**
- Create `.github/workflows/ci.yml` before first feature implementation.
- Document the rollback procedure in the project README or engineering wiki.
- Enforce the backwards-compatible migration authoring rule in PR review checklist.

---

## ADR-012 — Configuration Management

**Problem Statement:** Application secrets must be stored securely and injected at runtime. Business-configurable parameters — specifically Malaysian fee rates — must be changeable without a code deployment.

**Relevant Requirements (OTQ-005):** Stamp duty rate (RM1 per RM1,000, ROUNDUP) and clearing fee rate (0.03%) must be updatable without a code deployment, as government budget announcements can change these rates. The frontend fee preview must use the same rates as the server authoritative calculation.

**Options Considered:**
- Secrets: platform env vars, AWS Secrets Manager, HashiCorp Vault
- Fee parameters (OTQ-005): hardcoded constants, environment variables (requires redeploy), database `system_config` table

**Summary of Trade-offs:** Platform environment variables (Render + Vercel) are the appropriate secrets mechanism for V1 — encrypted at rest, never in git, editable in the dashboard. Environment variables for fee parameters are insufficient because: (1) they require a redeploy to change, and (2) the frontend cannot reliably fetch them for display without an additional API endpoint backed by a database value. A `system_config` PostgreSQL table provides a single source of truth accessible to both backend calculation and frontend display, is auditable via `updated_at`, and is truly zero-deployment-change.

**Final Decision:**
- Secrets (API keys, DB credentials, JWT signing key, Stripe webhook secret, Resend API key): Render and Vercel platform environment variables; read in Python via Pydantic `BaseSettings`; local development via `.env` file (git-ignored)
- Fee parameters (OTQ-005 ✅): `system_config` PostgreSQL table with key-value schema; admin FastAPI endpoint (protected) for updates; backed by 1-hour in-process `TTLCache`; exposed via `GET /config/fees` for frontend consumption
- Application settings (trial period, grace period): also stored in `system_config` table

**`system_config` initial seed values:**

| Key | Value | Description |
|---|---|---|
| `stamp_duty_rate_per_thousand` | `1.00` | Stamp duty in RM per RM1,000 (ROUNDUP to nearest RM1) |
| `clearing_fee_rate` | `0.0003` | Clearing fee as decimal fraction (0.03%) |
| `trial_period_days` | `14` | Trial period duration in days (assumed; confirm with product) |
| `subscription_grace_period_days` | `3` | Grace period after payment failure before access is suspended |

**Rationale:** The database table is the only approach that satisfies all three constraints simultaneously: zero-deployment-change, frontend-readable, and auditable.

**Dependencies:** ADR-004 (PostgreSQL), ADR-008 (TTLCache for in-process caching of config values).

**Outstanding Risks:** The admin endpoint that updates `system_config` must be secured (admin-only FastAPI dependency or API key). An accidental update to `stamp_duty_rate_per_thousand` would corrupt all subsequent fee calculations until corrected.

**Follow-up Actions:**
- Add `system_config(key TEXT PK, value TEXT, description TEXT, updated_at TIMESTAMPTZ)` to schema.
- Add `audit_log` entry on every `system_config` update (see ADR-014).
- Implement `GET /config/fees` endpoint; cache with 1-hour TTL.
- Confirm trial period duration (14 days assumed) before first user registration.

---

## ADR-013 — Observability

**Problem Statement:** The monitoring, logging, error tracking, and alerting stack must be defined. For a solo founder, the stack must provide actionable signal without operational overhead.

**Relevant Requirements:** Silent failures in background jobs (PDPA deletion, price refresh) are unacceptable. Sentry must capture cron job failures. Uptime monitoring must alert before users notice downtime.

**Options Considered:**
- Logging: structlog (structured JSON), standard Python logging, Datadog Logs
- Error tracking: Sentry, Rollbar, no tooling
- Uptime: BetterUptime, UptimeRobot, Pingdom
- APM: Datadog, New Relic, none

**Summary of Trade-offs:** Sentry's free tier (5,000 errors/month) is the highest-value observability investment for a solo founder — it catches exceptions that would otherwise only surface via user complaints, including silent cron job failures. External uptime monitoring (BetterUptime/UptimeRobot) catches network-level outages that Render's internal health checks cannot detect. Full APM is not warranted at V1 user volumes; Render's built-in CPU/memory metrics are sufficient.

**Final Decision:**
- Application logging: `structlog` emitting structured JSON to stdout; Render captures and displays logs in dashboard
- Next.js logging: Vercel function logs dashboard
- Error tracking: Sentry (Python SDK for FastAPI; `@sentry/nextjs` for Next.js; `sentry_sdk.capture_exception` in all cron scripts); Sentry Cron Monitoring to detect missed job executions
- Uptime monitoring: BetterUptime or UptimeRobot (free tier); monitor `GET /health` endpoint every 3 minutes; email + SMS alert on failure
- Metrics: Render platform dashboard (CPU, memory, request count); no custom metrics for V1
- APM/tracing: none for V1

**Health check endpoint:** `GET /health` returns `{"status": "ok", "db": "ok"}` (HTTP 200) or `{"status": "error", "db": "unreachable"}` (HTTP 503); performs `SELECT 1` against PostgreSQL.

**Total observability cost for V1:** RM 0 (all free tiers).

**Dependencies:** ADR-002 (FastAPI), ADR-003 (Next.js), ADR-006 (cron scripts), ADR-010 (Render + Vercel).

**Outstanding Risks:** Sentry free tier is capped at 5,000 errors/month. A bug causing repeated errors could exhaust the quota. Set up a Sentry rate limit per issue type to prevent quota exhaustion from a single recurring bug.

**Follow-up Actions:**
- Add Sentry SDK to FastAPI application startup.
- Add `@sentry/nextjs` to Next.js configuration.
- Wrap every cron script entry point in try/except with `sentry_sdk.capture_exception`.
- Implement `GET /health` endpoint before first deployment.

---

## ADR-014 — Security

**Problem Statement:** Beyond the security decisions already made in authentication (ADR-005), HTTPS (ADR-010), and input validation (ADR-002), the remaining security concerns — CORS policy, CSRF mitigation, rate limiting, and audit logging — must be defined.

**Relevant Requirements:** PDPA compliance requires an audit trail of deletion requests and their execution. Financial data requires rate limiting on authentication endpoints to prevent brute-force. Vercel preview deployments must be able to call the FastAPI API.

**Options Considered:**
- CORS: wildcard, strict allowlist
- CSRF: SameSite=Strict, SameSite=Lax, CSRF token
- Rate limiting: SlowAPI (in-process), Redis-backed rate limiter, Render network-level DDoS protection only
- Audit logging: PostgreSQL table, external audit log service, no audit logging

**Summary of Trade-offs:** `SameSite=Strict` on the JWT cookie prevents cross-site request forgery but breaks cookie transmission on top-level navigation from external links (e.g., clicking a Stripe receipt link that redirects to the app). `SameSite=Lax` blocks cross-site form submissions and XHR (the actual CSRF attack vectors) while allowing top-level GET navigations — the correct production default. SlowAPI in-process rate limiting adds no infrastructure, is sufficient for V1 volumes, and protects the most sensitive endpoints.

**Final Decision:**
- CORS: strict allowlist via FastAPI `CORSMiddleware`; allow production domain, `www` subdomain, and `*.vercel.app` (for preview deployments); local `http://localhost:3000`; no wildcard
- CSRF: JWT stored with `SameSite=Lax`, `HttpOnly`, `Secure` attributes; no additional CSRF token required
- Rate limiting: SlowAPI in-process; applied per-IP to auth endpoints (5 req/min on login, register, password reset); per-user on import endpoint (2 req/min); all authenticated endpoints (60 req/min)
- Audit logging: `audit_log` PostgreSQL table; log: PDPA deletion request, PDPA deletion execution, password changed, subscription activated/cancelled, `system_config` fee parameter updated, CSV import completed

**`audit_log` schema:**
```
audit_log(
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  entity_type TEXT,
  entity_id UUID,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
)
```

**Rationale:** SameSite=Lax is the industry standard default for cookie-based auth. SlowAPI is zero-infrastructure and protects the endpoints that matter most. The audit_log table is a lightweight PDPA compliance mechanism with negligible storage overhead.

**Dependencies:** ADR-002 (FastAPI), ADR-004 (PostgreSQL), ADR-005 (JWT cookie).

**Outstanding Risks:** SlowAPI rate limits are per-process and not shared across multiple Render instances. At V1 (single instance), this is not a concern.

**Follow-up Actions:**
- Add `audit_log` table to schema.
- Implement a `log_audit_event()` helper function in the `admin` module; call it at every auditable event site.
- Configure CORS allowlist in FastAPI startup.

---

## ADR-015 — Scalability and Reliability

**Problem Statement:** The failure behaviour of the system's most critical external dependency (yfinance), the retry strategy for async tasks, database connection management, and the V1 scaling posture must be defined.

**Relevant Requirements:** yfinance failure for one stock must not prevent other stocks from updating (BAS data consistency). Email delivery failures for PDPA confirmation emails must be detectable. The system must be stateless enough to scale horizontally when required.

**Options Considered:**
- yfinance retry: per-stock isolation + backoff, whole-batch retry, no retry
- Email retry: no retry, in-task retry, queued retry
- DB connections: SQLAlchemy default pool, PgBouncer, connection-per-request
- Scaling: single instance, horizontal scaling from day 1, vertical scaling

**Summary of Trade-offs:** Per-stock failure isolation is the only approach that prevents a single stock's fetch failure from leaving all holdings without a price update. In-task email retry with Sentry capture is the simplest mechanism that still provides observability on failures. PgBouncer is available on Render as a one-checkbox option — enabling it when connection exhaustion is observed is preferable to configuring it upfront. The architecture is inherently stateless (JWT tokens in cookies, no server-side session), making horizontal scaling a single Render configuration change when required.

**Final Decision:**
- yfinance retry: per-stock failure isolation; up to 2 retries per stock with exponential backoff (5s, 15s); log failures to Sentry at `WARNING` level per stock; Sentry `CRITICAL` alert if >50% of stocks fail in a single run; stale-data banner shown for holdings with `now() - last_refreshed_at > 28 hours`
- Email delivery retry: 1 in-task retry; `sentry_sdk.capture_exception` on final failure; UI "Resend" button for critical flows (email verification, password reset)
- Database connections: SQLAlchemy default pool (5 connections, 10 max overflow) for V1; enable Render PgBouncer (transaction mode) if connection exhaustion is observed; no proactive configuration required
- Horizontal scaling: single Render instance for V1; architecture is stateless — horizontal scaling is a Render dashboard configuration change; first lever is vertical scaling (upgrade Render instance tier)
- Circuit breakers: not required for V1 (no external dependency is in the synchronous API request path)

**Rationale:** All decisions are calibrated to V1 scale. The yfinance per-stock isolation pattern is the most important reliability decision — a whole-batch failure behaviour would make the product non-functional for users whenever any single stock has a data issue.

**Dependencies:** ADR-006 (cron scripts for price refresh), ADR-007 (yfinance, Resend), ADR-010 (Render single instance), ADR-013 (Sentry for alerting).

**Outstanding Risks:**
- yfinance is an unofficial scraper with no SLA. If Yahoo Finance breaks the scraping interface (has occurred historically), the price refresh fails entirely until the yfinance library is updated. No automated mitigation for V1 — requires manual intervention.
- Email delivery failures for PDPA deletion confirmations (legally required notifications) are captured in Sentry but not automatically retried beyond the first in-task retry. If Resend has an extended outage, PDPA confirmation emails may not be delivered. Monitor Resend status page.

**Follow-up Actions:**
- Subscribe to Resend status page for outage notifications.
- Monitor yfinance GitHub issues for Yahoo Finance breaking changes before they affect production.
- Document the yfinance manual recovery procedure (update library version, redeploy).

---

## Summary of All Decisions

| ADR | Topic | Key Decision |
|---|---|---|
| ADR-001 | Application Architecture | Modular monolith |
| ADR-002 | Backend | Python / FastAPI |
| ADR-003 | Frontend + Fee Calculation | Next.js + TypeScript + Tailwind + shadcn/ui; client preview + server authoritative fees |
| ADR-004 | Database | PostgreSQL + SQLAlchemy + Alembic; version-field optimistic locking; query-time aggregates |
| ADR-005 | Authentication | fastapi-users; JWT + token_version in HTTP-only Lax cookie; bcrypt CF12 |
| ADR-006 | Background Processing | Render cron jobs; FastAPI BackgroundTasks + ImportJob table; polling for CSV import |
| ADR-007 | External Integrations | yfinance only + stale banner; Stripe; Resend |
| ADR-008 | Caching | In-process TTLCache (stock reference); SWR (frontend); no Redis |
| ADR-009 | Data Storage | PostgreSQL stocks table; PDPA retain PriceSnapshot + anonymise billing; transient CSV tempfile; managed backups |
| ADR-010 | Infrastructure | Vercel (Next.js) + Render (FastAPI + PostgreSQL + Cron); Docker Compose local dev |
| ADR-011 | Deployment | GitHub Actions CI; local + production; Render pre-deploy Alembic; backwards-compatible migrations |
| ADR-012 | Configuration | Render + Vercel env vars for secrets; system_config table for fee parameters; TTLCache |
| ADR-013 | Observability | structlog + Sentry + Sentry Cron Monitoring + BetterUptime; no APM |
| ADR-014 | Security | Strict CORS; SameSite=Lax; SlowAPI rate limiting; audit_log table |
| ADR-015 | Scalability + Reliability | Per-stock yfinance isolation; in-task email retry; SQLAlchemy default pool; single instance V1 |

---

## Open Items for Pre-Implementation Resolution

The following items remain open and must be resolved before schema design and implementation begin:

| # | Item | Owner | Priority |
|---|---|---|---|
| 1 | Confirm trial period duration (14 days assumed; in system_config) | Aaron | High — affects user onboarding flow |
| 2 | Confirm subscription grace period (3 days in system_config) | Aaron | High — affects subscription state machine |
| 3 | Verify SST applicability on subscription fees; configure Stripe Tax | Aaron (legal/tax advice) | High — must be correct before first payment |
| 4 | Correct PRD Section 14 (DividendTranche.total_amount described as "derived" — must say "stored") | Aaron | Critical — C-001 conflict from Technical Discovery Report |
| 5 | Source initial Bursa Malaysia securities list for stocks table seed | Aaron | High — required for stock reference data |
| 6 | Confirm dividend year boundary (calendar year vs. financial year) | Aaron | Medium — affects dividend income reporting |
| 7 | Confirm sell-calculator broker selection for multi-lot/multi-broker positions | Aaron | Medium — affects sell workflow UX and fee calculation |

---

*This ADR Summary serves as the sole authoritative input for the Solution Architecture Document. No architectural decisions should be made in the Solution Architecture Document that are not grounded in this record.*
