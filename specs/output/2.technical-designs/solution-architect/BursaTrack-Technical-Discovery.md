# BursaTrack — Technical Discovery Report

> **Document Type:** Technical Discovery Report
> **Version:** 1.0
> **Date:** 2026-06-27
> **Author:** Principal Software Architect
> **Inputs Reviewed:**
> - BursaTrack-PRD-Final.md v2.0
> - BursaTrack-BAS-Enhanced-Part1/2/3.md v2.0
> - BursaTrack-UX-Spec-Part1/2/3.md v1.1
> **Scope:** Pre-architecture technical discovery only. This document does not recommend technologies, design the solution, or produce architecture diagrams.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Functional Architecture Implications](#2-functional-architecture-implications)
3. [Non-Functional Requirements](#3-non-functional-requirements)
4. [Technical Constraints](#4-technical-constraints)
5. [External Dependencies](#5-external-dependencies)
6. [Data Consistency Requirements](#6-data-consistency-requirements)
7. [Long-Running Processes and Background Jobs](#7-long-running-processes-and-background-jobs)
8. [Event-Driven Behaviours](#8-event-driven-behaviours)
9. [Real-Time Communication Requirements](#9-real-time-communication-requirements)
10. [Security Concerns](#10-security-concerns)
11. [Deployment Implications](#11-deployment-implications)
12. [Data Storage Implications](#12-data-storage-implications)
13. [Potential Scalability Bottlenecks](#13-potential-scalability-bottlenecks)
14. [Risks](#14-risks)
15. [Missing Information and Ambiguous Requirements](#15-missing-information-and-ambiguous-requirements)
16. [Conflicting Requirements](#16-conflicting-requirements)
17. [Open Technical Questions](#17-open-technical-questions)
18. [Recommended Areas Requiring Architecture Decisions](#18-recommended-areas-requiring-architecture-decisions)

---

## 1. Executive Summary

BursaTrack is a web-based dividend portfolio tracker purpose-built for Malaysian retail investors on Bursa Malaysia. From an architecture standpoint, it is a calculation-intensive, multi-tenant web application with five distinct technical domains, each carrying meaningful design risk:

**1. A precision financial calculation engine.** Fee calculations, yield derivations, and sell scenarios must produce bit-identical results across all execution contexts. Any floating-point ambiguity directly undermines the product's core value proposition. This domain requires exact decimal arithmetic and exhaustive unit testing.

**2. A critical data invariant around dividend history.** The specification (BAS v2.0, CRIT-01 fix) establishes that `DividendTranche.total_amount` must be stored at logging time and must never be re-derived from the current position share count. This invariant must be enforced at the application layer, not merely documented, because a natural reading of the PRD domain model (Section 14) still implies derivation — creating a risk of regression by any engineer who reads only the PRD.

**3. An unreliable external price data dependency.** The yfinance source is an unofficial API with no contractual SLA and documented outage history. The entire daily-use value proposition depends on this feed. The architecture must treat outage as a routine operational event, not an exception, including outage detection within five minutes and graceful user-facing degradation.

**4. A subscription and lifecycle management system** requiring reliable payment webhook handling, trial expiry, billing renewal, grace periods, and PDPA-compliant account deletion with a 30-day cancellation window and irreversible hard-delete across eight entity types.

**5. A background job architecture** covering daily price refresh, trial expiry transitions, subscription renewal, and PDPA permanent deletion — all of which have strict timing, failure, and consistency requirements.

The product is scoped conservatively (one portfolio per user, Bursa only, responsive web, no native mobile), which significantly reduces architectural surface area. At the target scale of 500 concurrent users and 10,000 accounts in Year 1, the architecture does not require distributed systems, message queues, or microservices — but several design decisions made now will either enable or constrain reaching that scale cleanly.

---

## 2. Functional Architecture Implications

Each functional capability in the specification implies a distinct architectural component or responsibility. The following catalogue is derived directly from the PRD, BAS, and UX Spec.

---

### 2.1 Authentication and Session Management

The specification defines a full authentication lifecycle:

- **Registration** with email/password, default broker selection, email verification token generation, trial period initiation, and empty portfolio creation — all as a single atomic operation.
- **Login** with credential validation, failed-attempt tracking, IP-based rate limiting, lockout (5 failed attempts → 10-minute block), and session creation using HTTP-only, Secure cookies.
- **Password reset** as a distinct, security-sensitive flow: email enumeration protection (identical responses for found and not-found accounts, with identical response timing), single-use tokens with 1-hour expiry, and full invalidation of all active sessions on successful reset.
- **Session expiry** after 30 days of inactivity; graceful handling of mid-session expiry (HTTP 401 → redirect to login without data loss).
- **Account status lifecycle**: `trial` → `active` → `trial_expired` → `pending_deletion` (with cancellation path) → hard-deleted.

This implies: a session storage mechanism that supports cross-device invalidation by user ID; a rate-limiting store (per IP) with a 10-minute TTL; a token store for email verification and password reset (single-use, time-bounded); and a transactional account creation path.

---

### 2.2 Portfolio and Position Management

Positions aggregate one or more Lots. All position-level metrics (total shares, total all-in cost, blended price, dividend yield, current market value, unrealised P&L) are computed at runtime from stored Lot and DividendTranche records — they are not stored on the Position entity.

This runtime derivation is a deliberate design choice that preserves calculation correctness at the cost of query complexity. The dashboard must aggregate across potentially 50 positions × multiple lots × multiple dividend tranches for each page load. This pattern has clear implications for query design and indexing.

Soft-delete is used for Positions, Lots, and DividendTranches. Deleted records are excluded from aggregates but retained for audit and PDPA purposes. The hard-delete job must handle both active and soft-deleted records.

A duplicate-position guard is required: if the user attempts to add a stock code that already exists as an active position, the system must silently redirect the operation to Add Lot rather than creating a duplicate.

---

### 2.3 Fee Calculation Engine

The fee calculation engine is the most specification-complete component in the codebase. It must implement:

- **Brokerage:** percentage-based (rate × initial amount, floored at minimum fee) or flat fee per trade.
- **Clearing fee:** 0.03% of initial amount, capped at RM1,000.
- **Stamp duty:** `ROUNDUP(initial_amount / 1000, 0)` — ceiling function in units of RM1 per RM1,000; RM1 minimum.
- **All-in cost:** sum of all four components.
- **Rounding convention (BR-025):** each fee component rounded individually using half-away-from-zero to 2 decimal places; amounts not aggregated before rounding.
- **Stamp duty rate configurability (BR-015):** the 0.10% rate must be changeable without a code deployment; currently gazetted until 12 July 2028.

The specification explicitly states that all-in cost (not pre-fee initial amount) is the yield denominator. This is the correction of the known Excel bug and is a non-negotiable invariant. The fee engine must be callable from both the position-creation flow and the sell scenario calculator.

The UX spec requires live recalculation as the user types — implying the fee engine must either run synchronously in the browser or be accessible via a low-latency endpoint.

---

### 2.4 Dividend Tranche Management and the qualifying_shares Invariant

This is the highest-risk application-layer invariant in the specification.

When a dividend tranche is logged:
- `qualifying_shares` is captured at that moment (defaulting to current `position_total_shares`, user-overrideable).
- `total_amount` is calculated as `per_share_amount × qualifying_shares` and **stored** — it is not a derived field.

This invariant means: adding a new lot to a position after dividends have been logged must **not** alter any existing `DividendTranche.total_amount`. The calculation uses the share count from the dividend moment, not the current position total.

Architectural implication: this invariant is not enforceable at the database level through standard constraints. It must be enforced at the application layer on every write path that touches `DividendTranche.total_amount`. A natural coding path (re-derive totals on position update) would silently violate it. The invariant must be documented as an explicit application constraint at the schema definition layer, and tested as a P0 regression case.

The only circumstance in which `total_amount` changes is when the user explicitly edits the tranche (changing `per_share_amount` or `qualifying_shares`), at which point the previous values are written to the audit log before overwriting.

---

### 2.5 Daily Price Refresh

The automated price refresh is a scheduled background job (target execution: 5:30 PM MYT on Bursa Malaysia trading days). Its behaviour:

1. Determine whether today is a trading day using a configurable Bursa holiday calendar.
2. Collect unique stock codes across all active (non-deleted) portfolios.
3. Query the price data provider per stock code.
4. For each success: create or update a `PriceSnapshot` record (`source = "automated"`).
5. For each failure or invalid response (price = 0, negative, or >50% deviation from previous): mark `source = "stale"`.
6. Within 5 minutes of a failure: surface a user-facing status banner on next page load.
7. Enable manual price override for stale-flagged positions.
8. Update `last_refreshed` timestamp only for successful batch completions.

The price provider (yfinance) is an unofficial API. The failure path is architecturally first-class, not an edge case. The 50% deviation threshold for invalid data rejection is a configurable parameter.

The job must also handle: partial failures (some stocks succeed, others fail, within the same batch), complete outage (all stocks fail), and the supersession of manual overrides by the next successful automated refresh.

---

### 2.6 Sell Scenario Calculator

The sell calculator is a pure, ephemeral calculation — results are not persisted. It requires:

- Pre-population from the position's stored data (all-in buy cost, total shares, current price).
- Broker selection logic for multi-lot positions (default: most recently created active lot's broker; user-overrideable without altering stored data).
- Auto-generation of scenario rows at defined price increments (+0.01 through +0.05 in 1-cent steps; then +0.10 through +0.70 in 5-cent steps) relative to current price.
- Partial sale support: shares-to-sell input; cost basis proportional to weighted average.
- Break-even row identification: the lowest scenario price where `profit_loss ≥ 0`.
- Non-dismissable legal disclosure: "Informational only. Settlement T+2."

The UX spec requires the sell calculator to display each fee component as a column (not just net proceeds), which means the calculation payload is wider than a simple summary.

Target response time is under 100ms; the calculator must not require a server round-trip if computed client-side, but must produce identical results to the server-side fee engine.

---

### 2.7 CSV Import

CSV import is a multi-phase server-side operation:

- **Phase 1 — File validation:** format, required columns, file size limit (5 MB referenced in workflow).
- **Phase 2 — Row-level validation:** all rows across both sheets (Positions/Lots and Dividend Tranches), including: required fields, numeric ranges, stock code validity, date validity, tranche count per position per year ≤ 8, qualifying_shares ≤ position shares.
- **Phase 3 — Atomic create:** all records created in a single database transaction; no partial imports.

The operation must complete within 30 seconds for inputs up to 100 positions and 800 dividend entries. The user receives a progress indicator during processing. A row-level error report is returned on validation failure.

For each dividend tranche in the import: `qualifying_shares` defaults to the imported position share count if not specified in an optional column. The `total_amount` is stored (not derived) per the CRIT-01 fix.

The conflict resolution path for stocks already in the portfolio is reject-only at V1 (duplicate rows flagged in error report).

---

### 2.8 Subscription and Billing Lifecycle

The subscription system involves:

- **Trial:** account created with `trial_expiry_date = registration_date + 14 days`; full feature access.
- **Trial expiry:** background job sets `account_status = "trial_expired"` on expiry date; user sees read-only portfolio with paywall overlay on next login.
- **Subscribe:** redirect to payment processor; on success webhook, set `account_status = "active"` and store billing dates.
- **Renewal:** on `subscription_renewal_date`, payment is attempted; on failure, a grace period begins; after grace period without recovery, `account_status = "trial_expired"`.
- **Cancellation:** `account_status` remains `active` until end of current billing period; then transitions to `trial_expired`.
- **Data preservation invariant:** user data is never deleted due to subscription state change alone (BR-018).

Payment webhooks must be idempotent — duplicate delivery of a success webhook must not set the account to a contradictory state.

---

### 2.9 PDPA Compliance Workflows

Two mandatory PDPA workflows with distinct technical characteristics:

**FR-018 — Data Export:** User can download all their data as a collection of CSV files (minimum 6 data types: User, Portfolio, Positions, Lots, DividendTranches, AuditLog). The export is offered as a step in the account deletion flow. The export event itself is logged to the AuditLog.

**FR-019 — Account Deletion (Right of Erasure):**
- User initiates deletion; account enters `pending_deletion` state.
- 30-day grace window during which the user can cancel via a confirmation link.
- No new billing charges from deletion request date.
- On grace period expiry without cancellation: a scheduled job performs irreversible hard-delete across all 8 entity types for that user.
- Exception: shared automated `PriceSnapshot` records are retained; only manual overrides (`created_by_user_id = this user`) are removed.
- Email address is freed to allow re-registration.
- A system-level anonymised deletion log entry is written (timestamp + reason, no PII).

---

### 2.10 Audit Log

The audit log is an immutable, append-only record of all data mutations across key entities: Position, Lot, DividendTranche, User (status changes, email/password changes, deletion requests), and PriceSnapshot (manual overrides only; not automated refreshes).

Each record captures: user ID, action (CREATE/UPDATE/DELETE), entity type, entity ID, previous values (JSON), new values (JSON), server-side timestamp, and IP address.

Audit log records cannot be edited. The only deletion path is the PDPA hard-delete job for the owning user.

Architectural implication: the audit log is write-amplified (every edit to a Lot or DividendTranche creates at least one audit record) and will grow unboundedly. Its storage, indexing, and query characteristics must be considered separately from the operational data tables.

---

### 2.11 Stock Code Reference and Autocomplete

The system must maintain a reference list of valid Bursa Malaysia-listed stock codes for two purposes:
- Validation on position add and CSV import (stock code must be a valid Bursa-listed security).
- Autocomplete in the stock search field (2-character trigger; up to 8 results; displays name + code).

The specification states that at V1 a bundled list with periodic updates is acceptable. The autocomplete field falls back to free text entry if the feed is unavailable, with server-side validation on submit.

No decision has been made on whether the reference list is a static file, a database table, or queried from a live API.

---

### 2.12 Concurrency Handling

The system must handle two concurrent sessions editing the same Lot or DividendTranche simultaneously (EC-013). The specified approach is optimistic locking — either last-write-wins with a conflict notification, or check-then-update with a version field. These two options have different consistency trade-offs. The choice must be made before schema design.

Duplicate form submission (double-click on "Add Dividend") must also be protected against via idempotency at the API layer.

---

## 3. Non-Functional Requirements

### 3.1 Performance

| Requirement | Target | Source |
|---|---|---|
| Dashboard initial load | ≤ 3 seconds on 20 Mbps | PRD NFR |
| Dashboard load (returning user, cached prices) | ≤ 1.5 seconds | PRD NFR |
| All-in cost / yield calculations | < 200ms | PRD NFR |
| Sell calculator response | < 100ms | PRD NFR |
| CSV import processing | ≤ 30 seconds (up to 100 positions / 800 dividend entries) | PRD NFR |
| Price refresh batch completion | ≤ 5 minutes for all active positions | PRD NFR |
| Price outage detection and user notification | ≤ 5 minutes from failure | BAS FR-008 |

**Architectural note on dashboard performance:** position-level aggregates are computed at runtime from Lots and DividendTranches — they are not stored. For a user with 50 positions and 400 dividend tranches, the dashboard load involves significant read aggregation. The 3-second target at 500 concurrent users requires careful consideration of query design, indexing strategy, and whether partial pre-computation of aggregates is warranted.

---

### 3.2 Reliability

| Requirement | Target | Notes |
|---|---|---|
| Uptime (trading hours 8 AM–7 PM MYT) | ≥ 99.5% | < 3.65 hours downtime/year during market hours |
| Uptime (off-peak) | ≥ 99.0% | |
| Price data freshness | ≥ 99.5% of trading days with ≥ 1 successful refresh per position | Rolling 30-day window |
| Recovery Time Objective (RTO) | ≤ 4 hours | |
| Recovery Point Objective (RPO) | ≤ 24 hours | |
| Daily automated backup | Required | Point-in-time recovery strongly recommended |

---

### 3.3 Scalability

| Requirement | Target | Notes |
|---|---|---|
| Concurrent active sessions at V1 | ≥ 500 without degradation | Conservative launch target |
| Portfolio positions per user | ≥ 50 positions, ≥ 400 dividend tranches | 10× the reference Excel model |
| Daily price lookup calls | ≥ 10,000 per trading day | 500 users × 20 positions with buffer |
| User accounts (Year 1) | ≥ 10,000 | Should not require re-architecture |
| Dividend tranche records (Year 1) | ≥ 500,000 | |

---

### 3.4 Security

| Requirement | Target |
|---|---|
| Password storage | bcrypt or Argon2 with minimum cost factor 12; no plain-text storage |
| Password policy | Min 8 characters; at least one uppercase letter and one digit; strength indicator on registration |
| Session mechanism | HTTP-only, Secure cookies; 30-day inactivity expiry; explicit logout |
| Transport encryption | HTTPS all endpoints; TLS 1.2 minimum; HTTP redirects to HTTPS; HSTS header |
| Data at rest | Encrypted at rest (AES-256 or equivalent) |
| Auth rate limiting | Max 5 failed attempts per 10 minutes per IP → 10-minute lockout |
| CSRF | All state-changing requests protected by CSRF tokens |
| Sensitive data in logs | Portfolio values, dividend amounts, and PII must NOT appear in server logs |

---

### 3.5 Accessibility and Mobile

- All core features accessible and usable at ≥ 375px viewport width.
- Tap targets: minimum 44×44px on all interactive elements.
- Numeric input fields must trigger a numeric keyboard on iOS and Android.
- Screen reader support: aria-describedby for error messages, skip navigation, focus management after modal close and toast dismiss.

---

### 3.6 Auditability

- Every change to a Lot (CREATE, UPDATE, DELETE) is logged with previous and new values.
- Every change to a DividendTranche (including changes to `qualifying_shares` and `total_amount`) is logged.
- Every Position-level change (CREATE, DELETE, category_tag or stock_name edit) is logged.
- Account status changes, email/password changes, and deletion requests are logged.
- Manual price overrides are logged; automated price refreshes are not.
- Audit log records are immutable except via the PDPA hard-delete job.

---

### 3.7 Compliance

| Requirement | Details |
|---|---|
| PDPA — Data minimisation | Email, password, portfolio data only; no national ID, phone, or financial account numbers |
| PDPA — Right of access | Full data export in CSV format on user request |
| PDPA — Right of erasure | Account and all data deleted within 30-day window post-request |
| PDPA — Privacy policy | Must be live before any user accounts are created |
| Financial disclaimer | Every yield, P&L, and scenario calculation accompanied by: informational only, not financial advice |
| Stamp duty configurability | Rate configurable without code deployment |
| SC licensing | Legal opinion required before launch; sell calculator may trigger advisory classification |

---

## 4. Technical Constraints

The following constraints are explicitly stated in the project documents and must be treated as fixed inputs to the architecture.

1. **No broker API integrations:** No Malaysian broker exposes a public API for positions or transactions. All user data is entered manually or imported via CSV. This eliminates broker connectivity as an option and places the data-entry burden entirely on the user.

2. **Unofficial price data source:** yfinance (Yahoo Finance) is the only explicitly named price data source. It is an unofficial, unsupported API with no contractual SLA, rate-limit guarantee, or formal data accuracy commitment. The architecture must not assume reliable access.

3. **Stamp duty rate must be configurable without a code deployment:** The 0.10% remission expires 12 July 2028. If the rate changes, it must be updatable without a release cycle.

4. **One portfolio per user at V1:** The data model and permission checks are designed for single-portfolio accounts. Multi-portfolio support is a V1.1 consideration.

5. **No native mobile apps at V1:** The product is a responsive web application. No iOS or Android builds are in scope.

6. **No real-time price data:** Price data is end-of-day (refreshed once daily at market close). No intraday streaming is required or in scope.

7. **No automated dividend data scraping:** Dividend ex-dates and payment dates are user-entered. There is no Bursa scraping integration.

8. **Solo founder / small team:** Feature scope and operational complexity must be appropriate for a team without dedicated data engineering, infrastructure, or design resources.

9. **Bootstrapped; no external funding confirmed:** Infrastructure cost must be appropriate for a pre-revenue product. Paid institutional data APIs are out of scope until subscription revenue is established.

10. **No admin portal at V1:** Administrative actions (e.g., resending password reset emails for delivery failures) are handled out-of-band via support tooling.

11. **SST applicability unconfirmed:** If SST applies to brokerage fees for Bursa equity trades (per July 2025 Bursa FAQ), a new fee component must be added to the calculation engine. The architecture must accommodate adding a configurable SST component without schema migration.

---

## 5. External Dependencies

### 5.1 Price Data Provider (yfinance)

**Role:** Sole source of end-of-day equity prices for all Bursa-listed stocks.
**Risk level:** High.
**Nature:** Unofficial Yahoo Finance API wrapper. No contractual SLA. Documented outage history. Potential rate limiting as user base grows.
**Implications:**
- The system must never display stale prices as current; all price records carry a `source` field (`automated`, `manual`, `stale`) and a `refreshed_at` timestamp.
- The architecture must detect price feed failure within 5 minutes and surface a user-facing status indicator.
- Manual override must be available as an immediate fallback for any stale-flagged position.
- A secondary data source has not been identified. The architecture should design the price integration as an interface (not a hard dependency) to permit source substitution without application changes.

### 5.2 Payment Processor

**Role:** Subscription billing, trial-to-paid conversion, renewal, grace period, and cancellation.
**Risk level:** Low (multiple providers available; Stripe, iPay88, and Billplz are named as candidates).
**Implications:**
- The system must receive and process payment webhooks (success, failure, renewal, cancellation).
- Webhook handling must be idempotent — duplicate delivery of the same event must not cause duplicate state transitions.
- Account `status` transitions must be driven by webhook events, not by the payment redirect (the redirect may not arrive; the webhook is authoritative).
- The payment processor must support Malaysian Ringgit.

### 5.3 Email Delivery Provider

**Role:** Account verification emails, password reset emails, PDPA deletion confirmation and cancellation link emails.
**Risk level:** Low (multiple providers available).
**Implications:**
- Email delivery is asynchronous and may fail (EX-007, EX-011). Failures must not block user registration or password reset initiation.
- On registration: email failure does not prevent the user from accessing the trial; a resend option must be available.
- On password reset: email failure is logged but the response to the user is indistinguishable from a successful send (account enumeration protection).
- Volume is low at V1 scale (trial registrations, transactional emails only); no bulk marketing email capability required at launch.

### 5.4 Bursa Malaysia Trading Calendar

**Role:** Determines which days the price refresh job should run.
**Risk level:** Low.
**Implications:**
- The specification states a bundled configurable file is acceptable at V1 (not a live API call).
- The calendar must be updated periodically as Bursa announces public holidays.
- The system must check the calendar before executing the price refresh job, not rely on day-of-week alone.

### 5.5 Analytics Platform

**Role:** Product usage telemetry (event tracking for activation, retention, conversion funnels).
**Risk level:** Low.
**Implications:**
- The PRD recommends a privacy-respecting, self-hosted option (Plausible or PostHog) given the financial data sensitivity and PDPA compliance requirements.
- Analytics events must not capture portfolio values, dividend amounts, or position-level financial data.
- At V1 scale, analytics volume is minimal and does not affect system architecture.

---

## 6. Data Consistency Requirements

### 6.1 The qualifying_shares / total_amount Invariant (Critical)

`DividendTranche.total_amount` is stored at logging time as `per_share_amount × qualifying_shares`. It must remain immutable with respect to future changes to `Position.total_shares`. Adding or editing lots after a dividend has been logged must not alter any stored `total_amount`.

This invariant must be enforced at the application layer (not the database constraint layer) and verified by a dedicated regression test suite. It is classified as P0 by the BAS.

### 6.2 CSV Import Atomicity

The CSV import creates Position, Lot, and DividendTranche records atomically. Either all records in the file are created or none are. Partial imports are not permitted. This requires the entire import to succeed within a single database transaction, which has locking implications for larger import files.

### 6.3 Payment Webhook Idempotency

The payment processor may deliver the same webhook event more than once (e.g., success webhook for a subscription renewal). The system must process each distinct event exactly once. Duplicate delivery must not cause duplicate state transitions (e.g., setting `account_status = "active"` twice is harmless; but processing a cancellation event twice could cause inconsistency if the subscription end-date is also being updated).

### 6.4 Optimistic Locking for Concurrent Edits

When two sessions attempt to edit the same Lot or DividendTranche simultaneously, the second write must be rejected with a conflict notification. The specification offers two implementation approaches: last-write-wins with conflict detection, or check-then-update with a version field. The choice must be made before schema design; the version-field approach is more explicit and avoids lost updates.

### 6.5 Session Invalidation on Password Reset

On successful password reset, all active sessions for the user must be invalidated. This requires the session storage mechanism to support enumeration and deletion by user ID, not just by session token.

### 6.6 Soft-Delete Consistency

Soft-deleted records (Position, Lot, DividendTranche) must be excluded from all aggregate calculations (dashboard yield, portfolio totals, price refresh job stock list) but retained in storage for audit and PDPA purposes. Every query that aggregates over these entities must include an `is_deleted = false` filter.

### 6.7 PDPA Hard-Delete Scope

The PDPA hard-delete job must remove data across eight entity types. Shared records (automated `PriceSnapshot` records used by multiple portfolios) must not be removed — only manual override snapshots where `created_by_user_id` matches the deleted user. The hard-delete must be irreversible and must free the user's email address for re-registration.

---

## 7. Long-Running Processes and Background Jobs

The following processes run outside the synchronous web request cycle. Each has distinct requirements.

### 7.1 Daily Price Refresh Job

**Trigger:** Scheduled at 5:30 PM MYT on Bursa trading days.
**Duration:** Target ≤ 5 minutes for all active positions.
**Steps:** Trading day check → collect unique stock codes across active portfolios → query price provider per stock → write PriceSnapshot records → mark failures as stale → update last_refreshed timestamps → trigger status banners for affected users.
**Failure characteristics:** May fail partially (some stocks succeed, others fail) or completely (all stocks fail). Both paths require distinct handling. The job must not silently succeed for failed stocks.
**Isolation requirement:** Must not block web request threads. A queued or worker-based execution model is required.

### 7.2 Trial Expiry Job

**Trigger:** Daily scheduler.
**Behaviour:** Identifies accounts where `trial_expiry_date ≤ today` and `account_status = "trial"`; sets `account_status = "trial_expired"`.
**Risk:** Must be idempotent — running twice on the same day must not cause incorrect state transitions.

### 7.3 Subscription Renewal and Grace Period Job

**Trigger:** Runs on each user's `subscription_renewal_date`.
**Behaviour:** Initiates payment via processor. On success: updates `subscription_renewal_date` to the next period. On failure: initiates grace period countdown. After grace period without recovery: `account_status = "trial_expired"`.
**Complexity:** This job interacts with the payment processor and must handle webhook responses asynchronously. The payment attempt and the status update must not be conflated.

### 7.4 PDPA Hard-Delete Job

**Trigger:** Scheduled against each user's `permanent_deletion_date`.
**Behaviour:** Irreversible deletion across all eight entity types (User, Portfolio, Position, Lot, DividendTranche, PriceSnapshot (manual only), AuditLog, BrokerConfig (custom only)). Frees email address. Writes anonymised system log entry.
**Risk:** This job is irreversible. It must be guarded against premature execution (e.g., if the job runs early due to timezone confusion or scheduler drift). The 30-day window must be computed from the user's deletion request timestamp, not from a job schedule.

### 7.5 CSV Import Processing

**Trigger:** User uploads a CSV file.
**Duration:** ≤ 30 seconds for up to 100 positions / 800 dividend entries.
**Behaviour:** Three-phase: file validation → row validation → atomic create. The user receives a progress indicator during processing.
**Risk:** The atomic create phase holds a database transaction open for the duration of the import. For large files, this increases lock duration. The processing must not occur in the web request thread if the 30-second window is to be safely managed.

---

## 8. Event-Driven Behaviours

The following system behaviours are triggered by events rather than direct user actions.

| Event | Trigger | System Response |
|---|---|---|
| Payment success webhook received | Payment processor | Account status → `active`; billing dates updated |
| Payment failure webhook received | Payment processor | Grace period initiated; user notified on next login |
| Price refresh job completes with failures | Scheduler + yfinance | Stale flags set; status banner triggered for affected users within 5 minutes |
| Trial expiry date reached | Daily job | Account status → `trial_expired`; paywall shown on next login |
| Password reset link clicked | User action (email) | Token validated; session form presented; all sessions invalidated on success |
| Account deletion cancellation link clicked | User action (email) | Account status restored to previous state; deletion dates cleared; confirmation email sent |
| permanent_deletion_date reached | Scheduled job | Irreversible hard-delete of all user data |
| Session expires mid-session | Inactivity timer | Next API request returns HTTP 401; client redirects to login |
| Manual price override entered | User action | PriceSnapshot created with `source = "manual"`; P&L recalculated immediately; superseded on next successful automated refresh |
| Automated refresh supersedes manual override | Successful refresh job | PriceSnapshot updated to `source = "automated"`; stale/manual indicators cleared |

---

## 9. Real-Time Communication Requirements

The specification does not require WebSocket connections, server-sent events, or intraday price streaming.

The product is designed around a daily price refresh model — appropriate for the dividend investor workflow and explicitly chosen over real-time data. This eliminates a significant class of architectural complexity.

However, two behaviours have latency implications that approach real-time:

**Price outage detection within 5 minutes:** The specification requires that a failed price refresh results in a user-visible status banner within 5 minutes. This can be achieved through polling (the user refreshes the page and the banner is server-rendered based on the stale flag) or through client-side polling of a status endpoint. It does not require a persistent connection. The implementation approach must be chosen at architecture design time.

**Live fee recalculation as user types (UX Spec):** The Add Position and Add Dividend forms must update calculated values in real time as the user enters data. This implies the fee calculation logic must run in the browser without a server round-trip. The architecture must ensure that the browser-side fee logic and the server-side fee logic are the same implementation (or that the server re-validates all submitted values).

---

## 10. Security Concerns

### 10.1 Account Enumeration Prevention

The password reset flow must return an identical response (both message content and response timing) regardless of whether the submitted email address matches an existing account. Any observable difference — including timing differences from a database lookup — enables attackers to enumerate valid email addresses. This is a common implementation pitfall that must be explicitly addressed in the implementation.

### 10.2 Session Invalidation Completeness

On password reset, all active sessions for the user must be invalidated — not just the current session. This is a security requirement (to handle the case where the user's credentials were compromised and the attacker has an active session). The implementation must enumerate and invalidate sessions by user ID, which requires a session storage design that supports this operation efficiently.

### 10.3 Cross-User Data Access Prevention

Every data access operation — position reads, lot reads, dividend tranche reads, price manual overrides — must verify that the requested record belongs to the authenticated user. The specification calls for HTTP 404 (not HTTP 403) on cross-user access attempts, to avoid revealing the existence of the resource. This is an authorisation pattern that must be enforced at the application layer on every route.

### 10.4 Password Reset Token Single-Use Enforcement

Password reset tokens must be single-use and must be marked as used immediately on successful password submission. Reuse of a valid token (by a second browser instance or by an attacker who intercepted the email) must return an error. Token storage must support an atomic compare-and-set (check token unused → mark used) to prevent race conditions.

### 10.5 Brute Force Protection

Auth endpoint rate limiting is IP-based (5 failed attempts → 10-minute lockout). Distributed brute-force attacks across multiple IPs are not in scope at V1 given the user scale, but the rate-limiting store must support a key format that allows future enhancement (e.g., per-account rate limiting in addition to per-IP).

### 10.6 Sensitive Data in Logs

Portfolio values, dividend amounts, position details, and any user-identifiable financial data must not appear in server logs. Log sanitisation must be applied at the application layer before any structured logging or log aggregation. This is particularly relevant to error logs, where stack traces may inadvertently capture request payloads containing financial data.

### 10.7 Shared PriceSnapshot Records

PriceSnapshot records for automated refreshes are shared across portfolios — they are not user-specific. The PDPA hard-delete process must not remove shared automated snapshots. Only manual override records (`created_by_user_id = deleted_user`) are removed. This creates a distinction in the deletion logic that must be explicitly handled.

### 10.8 CSV Upload Security

CSV uploads are the only file-based input surface. Security requirements include: file size limit enforcement (5 MB referenced in the BAS), content validation before processing, and encoding detection (UTF-8 required; Windows-1252 attempted as fallback; rejection if neither works). The upload endpoint must not execute any uploaded content and must process files in an isolated context.

---

## 11. Deployment Implications

### 11.1 Background Job Infrastructure

The system requires a reliable scheduled job runner separate from the web server process for:
- Daily price refresh (5:30 PM MYT, trading days only)
- Daily trial expiry check
- Subscription renewal attempts (per-user renewal dates)
- PDPA hard-delete execution (per-user deletion dates)

These jobs have different triggers (fixed schedule vs. per-user date-based triggers) and different failure tolerances (the PDPA deletion job is highest-criticality; the trial expiry job is idempotent).

### 11.2 Background Worker Infrastructure

Long-running or async operations that must not block web request threads:
- CSV import processing (up to 30 seconds)
- Email delivery (account verification, password reset, deletion confirmation)

These can share worker infrastructure with the scheduled jobs or be separated, depending on the architectural pattern chosen.

### 11.3 HTTPS and Transport Security

All endpoints must be served over HTTPS. HTTP requests must be redirected to HTTPS. HSTS headers are required. TLS 1.2 is the minimum; TLS 1.3 is preferred. This must be enforced at the deployment boundary (load balancer or reverse proxy), not solely at the application layer.

### 11.4 Configuration Management

The stamp duty rate and the price deviation threshold (50% for invalid data rejection) must be configurable without a code deployment. The mechanism — environment variable, database configuration table, or an external config file — must be decided at architecture design time. Configuration changes must take effect without a restart.

### 11.5 Trading Day Calendar Maintenance

The Bursa Malaysia holiday calendar must be maintainable by the operator without a code deployment. This is operationally required when Bursa announces additional market holidays (common in Malaysian public holiday scheduling). The calendar storage format and update procedure must be defined.

### 11.6 Mobile Responsiveness

No separate mobile deployment is required. The application is a single responsive web application targeting ≥ 375px viewport width. The deployment model is a standard single web origin.

---

## 12. Data Storage Implications

### 12.1 Relational Data Model

The specification defines eight core entities with foreign key relationships and UUID primary keys. The entity model is clearly relational and well-suited to a relational database. Key design requirements:

- Soft-delete pattern on Position, Lot, DividendTranche (all queries filtering `is_deleted = false`).
- Position-level aggregate values are NOT stored; they are computed at query time from Lot and DividendTranche records. This is a deliberate design decision with performance implications.
- The AuditLog entity stores `previous_values` and `new_values` as JSON blobs, requiring JSON column support.

### 12.2 Decimal Precision

This is a critical storage requirement. The product's value proposition is numerical accuracy. Financial values must not be stored as floating-point types. Required precision:

| Field | Precision |
|---|---|
| `Lot.purchase_price` | Decimal, 4 decimal places |
| `Lot.initial_amount`, `brokerage_fee`, `clearing_fee`, `stamp_duty`, `all_in_cost` | Decimal, 2 decimal places |
| `DividendTranche.per_share_amount` | Decimal, 6 decimal places (e.g., 0.004813) |
| `DividendTranche.total_amount` | Decimal, 2 decimal places |
| `PriceSnapshot.price` | Decimal, 4 decimal places |
| `BrokerConfig.rate` | Decimal, 6 decimal places (e.g., 0.001000) |

Floating-point storage (FLOAT, DOUBLE) must not be used for any monetary value. Exact decimal types are required.

### 12.3 PriceSnapshot — Shared Records

PriceSnapshot records are shared across all portfolios holding the same stock code. One record per `(stock_code, trading_date)` pair. The table grows at a rate of `unique_stock_codes × trading_days`. At V1 scale (~200 unique codes, ~250 trading days/year), this is manageable but must be indexed by stock code and trading date for efficient retrieval.

Manual overrides add records with `created_by_user_id` populated; these are user-specific and must be removed on PDPA hard-delete.

### 12.4 AuditLog Growth

The audit log is append-only and grows with every mutation to auditable entities. At V1 scale, with 500 active users each making daily edits, the audit log will grow substantially over time. The table must be indexed by `(entity_type, entity_id)` for retrieval in the drill-down views, and by `user_id` for the PDPA deletion job. Consider whether the audit log belongs in the same database or a separate store.

### 12.5 Session Storage

The specification requires HTTP-only, Secure cookies for sessions. It does not prescribe server-side session storage vs. stateless tokens. The key constraint is that all sessions for a given user must be invalidatable on password reset. This requires either: server-side sessions indexed by user ID; or stateless tokens with a per-user invalidation generation counter. The choice has significant implications for session storage volume and invalidation logic.

### 12.6 Transient Sell Scenario Data

Sell scenario calculations are not persisted. They are computed on-demand and returned in the response. No storage implications.

### 12.7 CSV File Handling

Uploaded CSV files must not be stored permanently. They are processed in memory or in temporary storage and discarded after the import completes (success or failure). Error reports are generated from the validation pass and returned in the response; they do not require persistent storage.

### 12.8 BrokerConfig — Reference Data

System-provided broker configurations are semi-static reference data (small table, infrequently changed). User-created custom broker configurations are user-specific (`created_by_user_id` populated) and must be removed on PDPA hard-delete. The distinction between system brokers and custom brokers must be preserved in the data model.

---

## 13. Potential Scalability Bottlenecks

### 13.1 Price Refresh Job Fan-Out

The daily price refresh job queries yfinance for each unique stock code across all active portfolios. At 500 users with 20 positions each, this could mean up to 10,000 price lookup calls per trading day, though unique stock codes will be far fewer in practice. The bottleneck is the external API's rate limits (undocumented for yfinance) and the sequential vs. parallel query model. If requests are made sequentially, the job may exceed its 5-minute window as the user base grows.

### 13.2 Dashboard Aggregate Computation

The dashboard computes per-position metrics at runtime by aggregating Lots and DividendTranches. For a user with 50 positions, each with an average of 3 lots and 8 dividend tranches per year, a single dashboard load requires reading and aggregating approximately 550 records. At 500 concurrent users simultaneously loading their dashboards (morning trading day peak), this creates a read amplification pattern that could stress the database. Indexing strategy and whether to pre-materialise some aggregates are key architecture decisions.

### 13.3 CSV Import Transaction Lock Duration

The atomic import of 100 positions + 800 dividend tranches within a single database transaction holds locks for the duration of the operation. At concurrent import attempts, this could create contention. The import flow should be queued (one import per user serialised) and potentially executed in a lower-isolation transaction context if the atomicity requirement permits.

### 13.4 Audit Log Table Growth

The audit log is unbounded in size. Over Year 1 with 10,000 accounts and regular usage, the table could accumulate millions of rows. Without partitioning or archival, query performance on the audit log will degrade. This is not a V1 problem at 500 users, but the schema design should not preclude future partitioning by date or user.

### 13.5 Email Delivery at Scale

At V1 scale, email volume is low. However, if a price outage or account issue affects many users simultaneously and triggers batch emails, the synchronous email path could create a bottleneck. Email delivery must be asynchronous (queued) from the start.

---

## 14. Risks

### 14.1 yfinance API Reliability (High Impact, Medium Probability)

The product's primary daily-use value — eliminating manual price entry — depends entirely on an unofficial, uncontracted API. Extended outages on trading days directly undermine the core value proposition and increase churn risk. The architecture must treat yfinance outage as a first-class operational scenario (not an edge case), with full graceful degradation, user-facing status communication, and manual fallback.

**Architecture implication:** Abstract the price data provider behind an interface that permits substitution. Do not hard-code yfinance-specific behaviour into the core application.

### 14.2 Floating-Point Calculation Errors (High Impact, Medium Probability)

Any calculation error in fees, yield, or sell scenarios directly contradicts the product's claim of provable accuracy. Floating-point arithmetic is susceptible to rounding errors that would be invisible in most applications but are significant for financial calculations. The product's differentiation is built on the claim that its numbers are correct; a single discovered calculation error could destroy user trust.

**Architecture implication:** Mandate exact decimal arithmetic for all monetary calculations, both server-side and client-side. Establish a canonical server-side calculation as the authoritative result; client-side live preview may approximate but must be validated on submit.

### 14.3 qualifying_shares Invariant Regression (High Impact, Medium Probability)

The CRIT-01 fix (storing `qualifying_shares` and `total_amount` at logging time) corrects the original BAS defect. However, the PRD domain model Section 14 still describes `total_amount` as "derived" — directly contradicting the BAS v2.0 fix. An engineer reading the PRD without the BAS v2.0 context may re-implement the original defect. This risk persists until the PRD is corrected and the invariant is embedded in schema-level documentation and P0 regression tests.

### 14.4 Payment Webhook Missed or Duplicated (Medium Impact, Medium Probability)

If the payment processor fails to deliver a subscription success webhook (or delivers it after a timeout causes the system to assume failure), the user completes payment but remains in `trial_expired` state. Conversely, a duplicate webhook could trigger duplicate processing. Both paths require robust webhook idempotency and a reconciliation mechanism.

### 14.5 PDPA Non-Compliance at Launch (Medium Impact, Low Probability)

Legal opinions on the PDPA data export and deletion requirements are not yet obtained. If the legal opinion requires these to be live at launch (rather than a short post-launch gap), missing them creates compliance exposure. The account deletion workflow (Workflow 9) and data export (FR-018) are fully specified and buildable; the question is whether they are classified as launch-blockers by a legal review.

### 14.6 SC Licensing for Sell Calculator (Medium Impact, Low Probability)

The Securities Commission of Malaysia licensing requirements for financial advisory services have not been assessed against the sell scenario calculator. If the calculator is classified as financial advice rather than informational tooling, it would require an SC licence or scope change. A legal opinion is required before launch.

### 14.7 Bursa Stock Code Reference Staleness (Low Impact, Medium Probability)

The bundled Bursa stock code reference list used for validation and autocomplete will become stale as stocks are listed and delisted. A user attempting to add a newly listed stock would receive a false validation error. The update cadence for the reference list must be defined.

### 14.8 Dashboard Performance Under Load (Medium Impact, Low Probability at V1 Scale)

The runtime-aggregation approach for position metrics is correct at V1 scale but could create performance issues as user numbers grow beyond 1,000. This is not a V1 concern at 500 concurrent users, but the schema and query design must not preclude adding materialised aggregates later.

---

## 15. Missing Information and Ambiguous Requirements

### 15.1 Missing Information

| # | Missing Item | Impact |
|---|---|---|
| M-001 | No tech stack specified (intentionally deferred to architecture phase) | Blocks architecture design document; expected to be resolved in Phase 2 |
| M-002 | No admin portal specification; support tooling for password reset delivery failures (EX-011) is explicitly deferred | Support agents cannot manually resend reset tokens without ad-hoc database access at V1 |
| M-003 | No explicit CSV file size limit in the formal requirements (5 MB referenced informally in the BAS workflow but not in a validation rule) | Validation rule VR-009 or equivalent must be formalised |
| M-004 | Stock code autocomplete data source not specified (bundled file, database table, or live API) | Affects bundle size, query patterns, and staleness handling |
| M-005 | No secondary price data source identified | yfinance outage has no defined fallback beyond manual override |
| M-006 | Subscription grace period duration (days) not specified | Required to implement the renewal failure path in Workflow 7 |
| M-007 | No refund policy specified; EC-018 assumes no prorated refund at V1 but this is marked as a stakeholder decision | Terms of service and billing logic cannot be finalised without this |

### 15.2 Ambiguous Requirements

| # | Ambiguity | Impact |
|---|---|---|
| A-001 | "Dashboard loads within 3 seconds" — unclear whether this includes price data (served from stored PriceSnapshot) or if it implies a live price fetch. The BAS separately states ≤ 1.5s for returning users with "cached prices." The caching mechanism and its relationship to the 3-second SLO must be clarified. | Affects query design and whether a session-level price cache is required |
| A-002 | "Prices refreshed at least once during market hours" — the workflow specifies 5:30 PM MYT (after market close), not during market hours. A single end-of-day refresh is the intended model, but the phrasing "during market hours" in the acceptance criteria is inconsistent. | Affects the job schedule and the "last refreshed" timestamp semantics |
| A-003 | PRD NFR states fee calculations run "< 200ms client-side" — but for trust and audit purposes, the server must also calculate and store fee values. It is ambiguous whether the client-side calculation is a preview (later validated server-side) or the authoritative result. A mismatch between client and server calculations would be a product defect. | Affects whether the fee engine must be implemented in both the frontend language and the backend language, or whether the client-side preview can call a server endpoint |
| A-004 | "Optimistic locking" is described as "last-write-wins with conflict notification OR check-then-update with version field" (EX-008). These have different consistency characteristics. The spec offers both as options; a single approach must be chosen before schema design. | Affects schema (version field required for check-then-update), transaction semantics, and UI conflict resolution flow |
| A-005 | Price outage detection "within 5 minutes" and the resulting status banner — the mechanism for surfacing this to the user is unspecified (server-push, client polling, or on page refresh). The choice affects infrastructure requirements. | Affects whether the system needs server-sent events, polling endpoints, or simple page-reload behaviour |

---

## 16. Conflicting Requirements

| # | Conflict | Documents Involved | Recommended Resolution |
|---|---|---|---|
| C-001 | PRD domain model (Section 14) states: DividendTranche "total is derived. This enables recalculation if share count is edited." BAS v2.0 (BR-009 CRIT-01 fix) states: `total_amount` is STORED at logging time and must NOT be re-derived when share count changes. These are directly contradictory. | PRD-Final.md §14 vs. BAS-Enhanced-Part1/2.md §BR-009, §FR-009 | BAS v2.0 is authoritative. PRD Section 14 must be corrected before engineering begins. Any engineer who reads only the PRD will implement the wrong model. This is the highest-priority conflict to resolve. |
| C-002 | PRD NFR states "Portfolio calculation time (yield, all-in cost) < 200ms client-side." BAS data model states all position-level aggregates (total_all_in_cost, dividend_yield, etc.) are "NOT stored on the Position record" and are "calculated at runtime." These two requirements together imply that the full aggregate calculation happens in the browser — but the source data (Lots, DividendTranches) must be loaded to the client to perform the calculation, which may conflict with the 3-second dashboard load target. | PRD-Final.md §13 (Performance NFR) vs. BAS-Enhanced-Part2.md §Entity 3 | Architecture decision required: either store pre-computed aggregates on Position (violating the BAS design intent) or accept that 200ms refers only to re-calculation after a user input change (not the initial load calculation). |
| C-003 | UX Spec Part 1 (Persona 3, Stage 5) states: "After adding a lot, explicitly confirm '2 existing dividend records unchanged' in the update success message." BAS FR-004 Post-Conditions states: "All previously logged DividendTranche.total_amount values are unchanged." The BAS does not specify a user-facing confirmation message in this flow. | UX-Spec-Part1.md §2, Persona 3 vs. BAS-Enhanced-Part1.md §FR-004 | Not a functional conflict; the UX spec adds a confirmation message not specified in the BAS. Architecture implication: the Add Lot success response must include the count of unchanged dividend records. The API response must return this count. |

---

## 17. Open Technical Questions

The following questions must be answered before architecture design can be finalised. They are ordered by impact on architecture decisions.

| # | Question | Why It Blocks Architecture | Recommended Owner |
|---|---|---|---|
| OTQ-001 | **Will fee calculations run client-side, server-side, or both?** If both, how is calculation consistency enforced between the browser and the server? A discrepancy between client-rendered preview and server-stored values would be a trust failure. | Determines whether the fee engine must be implemented twice (frontend + backend), or whether the frontend calls a calculation endpoint, or whether the client shows an approximation and the server recalculates on submit. | Tech Lead + Product Owner |
| OTQ-002 | **What session storage mechanism will be used?** Server-side sessions (requiring a session store supporting user-ID-based enumeration and deletion) or stateless tokens (requiring a per-user invalidation generation counter)? This is required to implement all-session invalidation on password reset. | Determines session store technology, schema additions (e.g., session table or token blacklist), and the invalidation implementation on password reset. | Tech Lead |
| OTQ-003 | **What is the fallback when yfinance rate-limits or blocks requests?** The specification identifies manual override as the user-facing fallback, but no secondary data source is named. Is there a secondary source to be evaluated, or is manual override the only fallback? | Determines whether the price integration layer must support multiple providers and whether a switchover mechanism is required. | Tech Lead + Product Owner |
| OTQ-004 | **How will the price outage status banner be surfaced to users within 5 minutes?** Options: the banner is shown on the next page load (no push required); the client polls a `/status` endpoint; or a server-sent event is used. | Different approaches have different infrastructure requirements; polling adds server load; SSE adds connection management complexity. | Tech Lead |
| OTQ-005 | **How will the stamp duty rate (and other system-level configuration values) be made changeable without a code deployment?** Options: environment variables (requires restart); database configuration table (runtime-updatable); external config file (requires file access). | Determines schema additions, deployment procedures, and whether a config management interface is needed. | Tech Lead |
| OTQ-006 | **What is the Bursa Malaysia stock code reference data strategy?** Options: bundled static file (updated periodically), database table (updateable without deployment), or live API call (eliminates staleness but adds dependency). | Affects bundle size (if client-side autocomplete uses the bundled list), staleness risk, and update procedures. | Tech Lead |
| OTQ-007 | **How will CSV import processing be executed without blocking web request threads?** Options: synchronous in-request (risky for 30-second window), background job queue (requires queue infrastructure), or streaming with progress polling. | Determines whether a job queue is required, or whether the import can be handled synchronously with a generous request timeout. | Tech Lead |
| OTQ-008 | **How will payment webhook idempotency be enforced?** Options: store processed webhook IDs (idempotency key per event), event sourcing with deduplication, or at-most-once processing with reconciliation. | Determines schema additions (webhook log table or event store) and the consistency model for subscription state. | Tech Lead |
| OTQ-009 | **What is the concurrency model for simultaneous edits?** The specification offers "last-write-wins with conflict notification OR check-then-update with version field." One must be chosen. The version field approach requires a schema column on every editable entity. | Determines schema design (version column or not), transaction semantics, and the UI error handling pattern. | Tech Lead |
| OTQ-010 | **Should Position-level aggregate values (total_all_in_cost, dividend_yield, etc.) be pre-computed and stored, or always derived at query time?** The BAS states they are runtime-derived. The 3-second dashboard load NFR at 500 concurrent users creates pressure in the opposite direction. | This is a correctness-vs-performance trade-off. Materialising aggregates simplifies queries and improves performance but requires invalidation logic and risks the qualifying_shares invariant being violated if not carefully implemented. | Tech Lead + Product Owner |
| OTQ-011 | **How will the PDPA hard-delete job handle the shared PriceSnapshot records correctly?** The deletion must remove manual overrides (`created_by_user_id = deleted_user`) while preserving automated snapshots (shared across all portfolios). The implementation must not accidentally delete shared records. | Requires explicit deletion logic per entity type, not a simple cascade delete from the User record. | Tech Lead |
| OTQ-012 | **What is the subscription grace period duration?** Workflow 7 references a grace period after payment renewal failure but does not specify its length. This is required to implement the renewal failure state machine. | Blocks implementation of the subscription renewal failure path. | Product Owner |

---

## 18. Recommended Areas Requiring Architecture Decisions

The following areas are the most consequential decisions to be made in the architecture design phase, listed in order of criticality.

**1. Fee Calculation Engine Placement and Consistency**
Whether the fee engine runs client-side, server-side, or in both contexts — and how consistency between the two is guaranteed — is the most architecturally consequential decision. It determines the technology split between frontend and backend, the validation model for submitted data, and the risk of calculation discrepancies.

**2. Data Model Resolution for DividendTranche.total_amount**
The conflict between the PRD domain model (§14) and the BAS v2.0 (BR-009 fix) must be formally resolved and the PRD corrected before any schema is designed. The authoritative answer (total_amount is stored, not derived) must be embedded in the schema definition and enforced by application-layer constraints.

**3. Session Storage and Invalidation Strategy**
The choice between server-side sessions and stateless tokens determines the schema additions needed, the invalidation mechanism for password reset, and the operational behaviour of the 30-day inactivity expiry.

**4. Background Job and Worker Architecture**
The system requires at minimum: a daily scheduled job runner (price refresh, trial expiry, renewal), per-user date-triggered jobs (PDPA deletion), and asynchronous task processing (CSV import, email delivery). The architecture for these must be defined before implementation to avoid competing designs.

**5. Price Data Provider Abstraction**
Given the high risk of yfinance outages and the potential need for a secondary provider, the price integration must be abstracted behind a well-defined interface from day one. Embedding yfinance-specific behaviour in the application core will make future substitution expensive.

**6. Dashboard Query and Aggregation Strategy**
The decision on whether to pre-materialise position-level aggregates or compute them at query time, and the corresponding indexing strategy, is required before schema design begins. This decision has direct implications for the 3-second dashboard load target and the qualifying_shares invariant.

**7. Optimistic Locking Approach**
A single concurrency model must be chosen (version field vs. last-write-wins) before schema design, as the version field approach requires a column addition on every editable entity.

**8. Payment Webhook Idempotency Mechanism**
The mechanism for ensuring each payment event is processed exactly once must be defined before the subscription billing integration is built.

**9. PDPA Compliance Timeline**
A legal opinion on whether data export (FR-018) and account deletion (FR-019) are required at launch must be obtained before the launch scope is finalised. If required at launch, these features are on the critical path.

**10. Configuration Management Approach**
The mechanism for managing runtime-configurable values (stamp duty rate, price deviation threshold, trading calendar) without code deployments must be defined as part of the deployment design.

---

*Technical Discovery Report prepared by: Principal Software Architect*
*Audience: Engineering Lead, Solution Architect, Product Owner, QA Lead*
*Status: Complete — ready for Solution Architecture design phase*
