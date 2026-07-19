# BursaTrack — API Requirements Report
## Stage 1 of 4: API Requirements and Resource Analysis

> **Author:** Senior API Architect (API Design Workflow — Stage 1)<br>
> **Date:** 2026-07-01<br>
> **Inputs:** PRD v2.0 Final · BAS Enhanced v2.0 (Parts 1–3) · BursaTrack Solution Architecture Document<br>
> **Status:** Business-language requirements analysis. No HTTP paths, methods, status codes, or schemas are defined at this stage — that is Stage 3's job.

---

## 1. Executive Summary

BursaTrack's API surface serves a single web frontend (Next.js) and two non-human consumers (Stripe webhooks, Render cron scripts running server-side — not API clients). The architecture (§7.2) organises the backend into five domain modules — `auth`, `portfolio`, `pricing`, `subscription`, `admin` — plus a reference-data surface for stocks and brokers that spans `portfolio`/`admin` concerns. Mapping every business operation from the PRD and BAS against this structure yields **34 distinct business operations** (matching the "28+ endpoints" the architecture and Stage 3 prompt anticipate once auth, health, and JWKS operations are included).

**Three highest-risk areas for API design correctness**, in priority order:

1. **Server-authoritative financial calculation (P0-API-002).** Every operation that creates or edits a `Lot` must accept only the raw purchase description (shares, price, broker, date) and compute all four fee components server-side. This is BursaTrack's entire value proposition (PRD §3, Principle 1) — a design that lets the client submit `all_in_cost` would silently reintroduce the exact spreadsheet-era trust problem the product exists to solve.

2. **The `qualifying_shares` / `total_amount` invariant (P0-API-003).** BAS BR-009 documents a corrected defect: `DividendTranche.total_amount` must be **stored** at logging time from `per_share_amount × qualifying_shares`, never re-derived from the live `position_total_shares`. Every dividend-tranche create and edit operation must be designed so the client can never supply `total_amount` directly, and so that adding a new `Lot` to a position cannot retroactively alter a previously stored tranche total (BAS EC-022 is the regression scenario).

3. **Ownership isolation without existence disclosure (P0-API-004).** Every user-scoped resource (Position, Lot, DividendTranche, ImportJob, custom BrokerConfig, manual PriceSnapshot) must be reachable only by its owner, and cross-user access attempts must be indistinguishable from "resource does not exist" (HTTP 404, never 403 — architecture §14.2).

Two further structural risks recur throughout the operation inventory: **asynchronous CSV import** (the only operation that cannot complete inside a single request/response cycle) and **PDPA compliance surface area** (data export, deletion request/cancel/hard-delete), which together account for 4 of the 5 "NEW" functional requirements the BA added that were absent from the original BAS (FR-017 through FR-019).

---

## 2. Actor Inventory

### 2.1 Unauthenticated User

- **Identity:** None. Identified only by request metadata (IP address for rate limiting).
- **Permissions:** Register, log in, request password reset, complete password reset, verify email via emailed token, cancel a pending account deletion via emailed token, fetch the JWKS public key, check system health.
- **Session model:** No session. A successful login or registration establishes a session (see 2.2).
- **Security constraints:** All operations in this actor's scope are targets for enumeration and brute-force attacks. BAS EX-009 (account lockout after 5 failed logins in 10 minutes) and BAS Workflow 8 / EX-011 (password reset response must be identical whether or not the email exists) apply specifically to this actor. Architecture §14.4 confirms per-IP rate limits on `register`, `login`, and `password-reset-request`.

### 2.2 Authenticated User

- **Identity:** RS256 JWT in an HTTP-only, Secure, SameSite=Lax cookie (architecture §14.1). The JWT payload carries `user_id` and `token_version`.
- **Permissions:** Full CRUD on their own Portfolio, Positions, Lots, DividendTranches, custom BrokerConfigs; read access to system-shared reference data (Stocks, system BrokerConfigs, PriceSnapshots); dashboard and sell-scenario computation; CSV import; subscription checkout/status/cancel; PDPA data export and account deletion request/cancellation.
- **Session model:** 7-day JWT with silent refresh (architecture §14.1 — HIGH-R-001/HIGH-R-010). The client refreshes proactively when the token is within 24 hours of expiry. `token_version` is checked on every request; it is incremented on logout, password change, and deletion initiation, immediately invalidating all other active sessions.
- **Security constraints:** Every read or write against a user-owned resource must verify `resource.user_id == authenticated_user.id` (architecture §14.2). Trial-expired accounts are a **restricted sub-state** of this actor: they retain read access to the dashboard, calculator, and dividend calendar but are blocked (paywall) from all write operations per BAS §9 Permission Matrix. `pending_deletion` accounts cannot authenticate at all — the account is fully inaccessible during the 30-day grace window (BAS Workflow 9).

### 2.3 Admin (operational, not a human user account)

- **Identity:** `ADMIN_API_KEY` environment-variable secret in a request header (architecture §14.2, §14.5). This is **not** a JWT-based identity and has no `user_id`.
- **Permissions:** Read and update system-wide fee configuration (clearing fee rate, stamp duty rate, price-deviation guard threshold, Bursa holiday calendar).
- **Session model:** None — stateless shared-secret authentication per request.
- **Security constraints:** Distinct auth scheme from all user-facing endpoints; must never accept a JWT as a substitute credential. The architecture explicitly notes there is no admin portal and no RBAC at V1 (NG-006) — this is the sole administrative surface.

### 2.4 Stripe (external system, webhook-only)

- **Identity:** `Stripe-Signature` header, verified against the `STRIPE_WEBHOOK_SECRET` (architecture §11.2, §14.5). Not a user, not JWT-based, not admin-key-based.
- **Permissions:** May only deliver subscription lifecycle events to a single webhook receiver. Cannot read or query any BursaTrack data.
- **Session model:** None — each delivery is an independent, signed, stateless callback. Idempotency is enforced via `processed_webhook_events.event_id` (architecture §11.2), not session state.
- **Security constraints:** The signature must be verified before any event payload is trusted or processed (OWASP API10 — unsafe consumption of third-party APIs). Re-delivered events must return 200 without reprocessing.

### 2.5 BursaTrack Cron Jobs (internal, not API consumers)

- **Identity:** N/A — these are standalone Python scripts (`refresh_prices.py`, `check_trial_expiry.py`, `process_deletions.py`) that connect directly to PostgreSQL using the same database credentials as the API process (architecture §13.1). They do not call the HTTP API at all.
- **Permissions:** Full read/write to `price_snapshots`, `users.account_status`, and cascading PDPA hard-deletion of all tables for a departing user.
- **Session model:** N/A.
- **Note for API design:** Because these are not API clients, they place **no direct requirements on the OpenAPI contract**. They are listed here only because their outputs (fresh `PriceSnapshot` rows, `account_status` transitions) are what several read endpoints (`GET /portfolio/dashboard`, `GET /subscription/status`) surface to the Authenticated User actor.

---

## 3. Resource Inventory

| Resource | Represents | Ownership | Lifecycle | Key relationships | Non-CRUD state? |
|---|---|---|---|---|---|
| **User** | An account holder | Private (self only) | Create (register) → Read/Update (self) → soft "pending_deletion" → hard-delete | Owns one Portfolio; referenced by every audit_log entry | Yes — `account_status` state machine (trial → active → grace_period → trial_expired → pending_deletion → gone; architecture §12.5) |
| **Portfolio** | Container for one user's holdings | User-scoped (1:1 with User at V1 — BAS Entity 2) | Created automatically at registration; never directly created/deleted by the client | Belongs to User; owns Positions | No — pure container, no independent operations |
| **Position** | A holding in one Bursa stock | User-scoped | Create (via first Lot) → Read → Update (metadata only) → soft-delete (cascades to Lots and DividendTranches) | Belongs to Portfolio; references a Stock; owns 1+ Lots and 0+ DividendTranches | No, but aggregates (total_shares, all_in_cost, yield) are computed at read time, not stored (ADR-004) |
| **Lot** | One purchase transaction within a Position | User-scoped (transitively via Position) | Create → Read (nested under Position) → Update (optimistic-locked) → soft-delete | Belongs to Position; references a BrokerConfig | No independent state machine, but every write recalculates Position-level aggregates |
| **DividendTranche** | One dividend payment received for a Position | User-scoped (transitively via Position) | Create → Read (detail + calendar) → Update (optimistic-locked) → soft-delete | Belongs to Position | The `total_amount` invariant (§1 above) makes this resource's write semantics the single most sensitive design point in the whole API |
| **PriceSnapshot** | The latest known price for a stock code | System-shared (not user-scoped) for automated entries; user-attributed for manual overrides | Upserted by the price-refresh cron; created by a user via manual override; never updated by a user directly, never deleted by a user | References a Stock; optionally references the User who entered a manual override | Yes — `source` field transitions automated → stale → manual → automated (BAS Workflow 3) |
| **BrokerConfig** | A fee structure (percentage or flat) | System-shared for the 6 pre-seeded brokers; user-owned for custom brokers | System configs: read-only, immutable. Custom configs: Create → Read → Update → Delete (blocked by FK if referenced by a Lot) | Referenced by Lot | No |
| **Stock** | A Bursa Malaysia listed security reference entry | System-shared, admin-seeded | Read-only from the API's perspective (seeded from a static CSV per ADR-009) | Referenced by Position, PriceSnapshot | No |
| **ImportJob** | The state of one CSV import attempt | User-scoped | Create (upload) → poll (Read) → terminal state (`complete` / `failed`) | Belongs to User; on success, spawns Positions/Lots/DividendTranches | Yes — this is fundamentally a state-machine resource (`processing` → `complete`/`failed`), not a CRUD resource |
| **SubscriptionRecord** | A user's Stripe subscription lineage | User-scoped; anonymised (not deleted) on PDPA erasure for 7-year accounting retention | Created on first checkout; updated by webhook events; never directly created/updated/deleted by the client | Belongs to User; referenced by Stripe subscription ID | Yes — driven entirely by Stripe webhook events, not client-initiated CRUD |
| **AuditLog** | Immutable record of a sensitive mutation | User-attributed, but not user-readable via any CRUD endpoint (only exposed inside the PDPA export) | Insert-only; hard-deleted by `ON DELETE CASCADE` when the owning User is hard-deleted | References User; polymorphic reference to any audited entity | No — append-only |
| **SystemConfig** | Fee/rate/threshold parameters (clearing fee rate, stamp duty rate, price-deviation threshold, Bursa holiday calendar) | System-wide, admin-only | Read/Update by Admin actor only | Referenced implicitly by every fee calculation | No |

---

## 4. Operation Inventory by Domain

### Auth

| Operation | Actor | Client provides | API returns | Write/Read | Sync/Async | Auth required |
|---|---|---|---|---|---|---|
| Register | Unauthenticated | email, password, password confirmation, default broker | Created user state + session established | Write | Sync | No |
| Verify email | Unauthenticated (via emailed link) | Verification token | Verified status | Write | Sync | No |
| Log in | Unauthenticated | email, password | Session established (or generic failure) | Write (session) | Sync | No |
| Log out | Authenticated | — | Session invalidated | Write | Sync | Yes |
| Refresh session | Authenticated | Existing valid session | New session with reset expiry | Write | Sync | Yes |
| Request password reset | Unauthenticated | email | Generic confirmation (identical regardless of match) | Write (token generation, conditional) | Sync | No |
| Complete password reset | Unauthenticated (via emailed link) | Reset token, new password, confirmation | Password updated; all sessions invalidated | Write | Sync | No |
| Fetch public signing key | Any | — | RS256 public key material (JWKS) | Read | Sync | No |

### Portfolio

| Operation | Actor | Client provides | API returns | Write/Read | Sync/Async | Auth required |
|---|---|---|---|---|---|---|
| View dashboard | Authenticated | — | Portfolio summary + all positions with computed aggregates | Read | Sync | Yes |
| Add position (first lot) | Authenticated | Stock, shares, purchase price, purchase date, broker, category tag (optional) | Created Position + Lot with all computed fee components | Write | Sync | Yes |
| View position detail | Authenticated | Position identifier | Position + all lots + all dividend tranches, with aggregates | Read | Sync | Yes |
| Edit position metadata | Authenticated | Category tag and/or notes | Updated position | Write | Sync | Yes |
| Delete position | Authenticated | Position identifier + confirmation | Position and all lots/tranches soft-deleted | Write | Sync | Yes |
| Add lot to existing position | Authenticated | Shares, purchase price, purchase date, broker | Created Lot with computed fee components; updated position aggregates | Write | Sync | Yes |
| Edit lot | Authenticated | One or more of (shares, price, date, broker) + expected version | Updated lot with recomputed fees; updated position aggregates | Write | Sync | Yes |
| Delete lot | Authenticated | Lot identifier | Lot soft-deleted; updated position aggregates | Write | Sync | Yes |
| Log dividend tranche | Authenticated | Position, tranche label, per-share amount, qualifying shares (defaulted, overridable), payment date, ex-dividend date (optional) | Created tranche with stored total_amount; updated position/portfolio yield | Write | Sync | Yes |
| View dividend calendar | Authenticated | Optional year filter | Chronological list of tranches across the portfolio | Read | Sync | Yes |
| Edit dividend tranche | Authenticated | One or more of (per-share amount, qualifying shares, label, dates) + expected version | Updated tranche with recomputed total_amount; updated yield | Write | Sync | Yes |
| Delete dividend tranche | Authenticated | Tranche identifier | Tranche soft-deleted; updated yield | Write | Sync | Yes |
| Compute sell scenario | Authenticated | Position, shares to sell (optional, defaults to all), one or more target prices | Fee-accurate projected proceeds/profit at each price, break-even flag | Read (pure computation; nothing persisted) | Sync | Yes |

### Pricing

| Operation | Actor | Client provides | API returns | Write/Read | Sync/Async | Auth required |
|---|---|---|---|---|---|---|
| Get latest prices | Authenticated | One or more stock codes | Latest PriceSnapshot per code, with staleness provenance | Read | Sync | Yes |
| Manual price override | Authenticated | Stock code, price, trading date | Created manual PriceSnapshot; immediately recalculates affected position's unrealised P&L | Write | Sync | Yes |

### Import

| Operation | Actor | Client provides | API returns | Write/Read | Sync/Async | Auth required |
|---|---|---|---|---|---|---|
| Upload CSV | Authenticated | CSV file (positions + optional dividend tranches) | Accepted job identifier (immediately) | Write (job creation) | **Async** — job runs after acceptance | Yes |
| Poll import status | Authenticated | Job identifier | Job status; on completion, row-level result (created counts or per-row errors) | Read | Sync (client polls repeatedly) | Yes |

### Subscription / Billing

| Operation | Actor | Client provides | API returns | Write/Read | Sync/Async | Auth required |
|---|---|---|---|---|---|---|
| Initiate checkout | Authenticated | Selected plan (implicit — one plan at V1 per PRD scope) | A redirect URL to Stripe-hosted checkout | Write (session creation with Stripe, not local state) | Sync | Yes |
| Get subscription status | Authenticated | — | Current account status, trial/renewal dates | Read | Sync | Yes |
| Receive Stripe webhook | Stripe (external) | Signed event payload | Acknowledgement only | Write (account status transitions) | Sync (must respond within Stripe's timeout), but the effect is asynchronous relative to the user's checkout flow — the frontend polls subscription status until the webhook lands (architecture §10.4) | Stripe-Signature, not JWT |

### Account / PDPA

| Operation | Actor | Client provides | API returns | Write/Read | Sync/Async | Auth required |
|---|---|---|---|---|---|---|
| Export personal data | Authenticated | — | A downloadable file containing all personal/financial data | Read (with a side-effecting audit log write) | Sync (in-memory assembly; volumes are small enough at V1 — architecture §10.7) | Yes |
| Request account deletion | Authenticated | Confirmation phrase | Account moved to pending_deletion; all sessions invalidated | Write | Sync | Yes |
| Cancel pending deletion | Unauthenticated (via emailed link — the account cannot log in during this state) | Cancellation token | Account restored to its prior status | Write | Sync | No |

### Configuration (Admin)

| Operation | Actor | Client provides | API returns | Write/Read | Sync/Async | Auth required |
|---|---|---|---|---|---|---|
| Get fee configuration | Admin | — | Current system-wide fee/threshold parameters | Read | Sync | ADMIN_API_KEY |
| Update fee configuration | Admin | Parameter key and new value | Updated configuration | Write | Sync | ADMIN_API_KEY |

### Stocks / Brokers (Reference Data)

| Operation | Actor | Client provides | API returns | Write/Read | Sync/Async | Auth required |
|---|---|---|---|---|---|---|
| Search/list stocks | Authenticated | Optional search term | Matching active Bursa securities | Read (cached) | Sync | Yes |
| List brokers | Authenticated | — | System brokers + the user's own custom brokers | Read | Sync | Yes |
| Create custom broker | Authenticated | Name, fee type, rate/flat fee, minimum fee | Created custom BrokerConfig | Write | Sync | Yes |
| Update custom broker | Authenticated | One or more fields + identifier | Updated custom BrokerConfig | Write | Sync | Yes |
| Delete custom broker | Authenticated | Identifier | Deleted, or rejected if referenced by an existing Lot | Write | Sync | Yes |

### Health

| Operation | Actor | Client provides | API returns | Write/Read | Sync/Async | Auth required |
|---|---|---|---|---|---|---|
| Health check | Any (uptime monitor) | — | Database connectivity status | Read | Sync | No |

---

## 5. Non-CRUD Operations

| Operation | Why it is not standard CRUD | Special considerations |
|---|---|---|
| **Sell scenario computation** | Reads position data but persists nothing; the output is a pure derived computation across a range of hypothetical prices | Must be idempotent and safe to call repeatedly (no side effects); must be scoped to the requesting user's own position; the T+2 settlement disclosure (BR-020) is a fixed response field, not a computed one |
| **Logout / session invalidation** | A state-transition on the User resource (`token_version` incremented), not a resource deletion | Must invalidate *only* the calling session's line of trust — in practice this invalidates all sessions for that user, since `token_version` is a single counter, which is the intended behaviour per architecture §14.1 |
| **Password reset request/complete** | A two-step state transition across an ephemeral `pending_tokens` resource that is never exposed as a queryable resource | The "request" step must not leak whether the account exists (BAS Workflow 8, EX-011) |
| **Account deletion initiation / cancellation** | A state-transition on User.account_status with a 30-day deferred side effect (the hard-delete cron job), not an immediate delete | Initiation must be irrevocable-looking to the user (session killed immediately) while remaining reversible via the emailed token for 30 days (BAS Workflow 9) |
| **CSV import** | Initiates an asynchronous job; the creation response and the eventual result are two separate reads | Requires a polling contract: what the client receives at 202, what it polls, and how it detects terminal state (BAS Workflow 5; architecture §13.6) |
| **Stripe webhook receiver** | Not user-initiated at all — an external system pushes state changes | Must be idempotent per delivery (`processed_webhook_events`) and must never trust the payload before signature verification |
| **PDPA data export** | Reads across nearly every resource type owned by the user and assembles them into a single downloadable artefact; also writes an audit log entry as a side effect of a "read" | Must exclude fields never meant to leave the system (`password_hash`, `token_version`, soft-deleted records, other users' shared reference data) per architecture §10.7 |
| **Dashboard** | Aggregates data across Position, Lot, DividendTranche, and PriceSnapshot in a single computed response; no dedicated dashboard resource exists in the data model | All aggregate figures (total cost, total income, blended yield) are computed at read time (ADR-004) — there is no dashboard "row" to fetch |
| **Fee/config admin update** | A configuration mutation with system-wide effect rather than a change to a single owned resource | Must invalidate the in-process `TTLCache` immediately so the change takes effect without a redeploy (architecture §12.4) |

---

## 6. Data In and Data Out (Conceptual)

### Lot creation (Add Position / Add Lot)
- **Client provides (minimum):** stock identification (for the first lot in a position), number of shares, purchase price per share, purchase date, broker selection, category tag (optional, first lot only).
- **Server computes and stores, never accepted from client:** brokerage fee, clearing fee, stamp duty, all-in cost (BAS §7 Entity 4; PRD REQ-002). This is the direct implementation of P0-API-002.
- **Server returns:** the created Lot with every fee component broken out individually (Product Principle 4 — Trust Through Transparency requires the user to see the calculation, not just the total), plus the recalculated Position-level aggregates (total shares, total all-in cost, blended purchase price).

### DividendTranche creation
- **Client provides:** position identifier, tranche label, dividend per share, qualifying shares (pre-populated with the position's current total shares by the frontend, but the *value ultimately submitted* is client-controlled — the user may override it per BAS FR-009 step 3a), payment date, ex-dividend date (optional).
- **Server computes and stores, never accepted from client:** `total_amount`. This is the direct implementation of P0-API-003 / BR-009.
- **Server returns:** the created tranche including the stored `qualifying_shares` and `total_amount`, plus recalculated position and portfolio yield figures.

### DividendTranche edit
- **Client provides:** one or more of (per-share amount, qualifying shares, tranche label, dates), plus the expected `version` for optimistic-locking (architecture §15.4).
- **Server computes and stores:** a **recomputed** `total_amount = updated per_share_amount × updated qualifying_shares`, using whichever of the two values changed and whichever remained the same as previously stored (BAS FR-010). The server must never accept a client-supplied `total_amount` on edit either — this is the case most likely to be miscoded, since a naive PATCH handler might allow partial-field passthrough of a `total_amount` field if present in the request body.
- **Server returns:** the updated tranche and recalculated yield figures.

### Sell scenario computation
- **Client provides:** position identifier, optional shares-to-sell (defaults to all active shares), one or more target prices (or none, to receive the architecture's default price-increment ladder).
- **Server computes:** gross proceeds, sell-side brokerage/clearing/stamp duty, net proceeds, profit/loss against the position's stored all-in cost, and the break-even row.
- **Server returns:** the full scenario table; nothing is persisted.

---

## 7. Security Requirements per Operation

| Operation group | Authentication | Authorization | Rate-limit class (architecture §14.4) | Sensitivity |
|---|---|---|---|---|
| Register, Login, Password-reset-request | None | None | Per-IP, strict (3–5/min) | High — brute-force / enumeration target |
| Email verify, Password-reset-complete, Deletion-cancel | None (token-based) | Token validity check (exists, unused, unexpired) | Standard authenticated rate (n/a — unauthenticated but token-gated) | High — bearer-token-style access; token must be single-use |
| Logout, Refresh, JWKS | JWT (logout/refresh) / none (JWKS) | Self only | Standard | Low |
| All Portfolio, Pricing, Import, Account-export, Subscription-status/checkout endpoints | JWT (cookie) | Ownership check (404 on mismatch) | Standard authenticated (60/min), except Import (2/min) | High — personal financial data |
| Sell scenario | JWT | Ownership check on the bound position | Standard | Medium — no persistence, but reveals cost basis |
| Stripe webhook | Stripe-Signature | Signature verification, not user-based | Elevated (100/min per IP, architecture §14.4 MED-R-008) | High — controls billing state |
| Admin config get/update | ADMIN_API_KEY | Shared-secret only, no per-resource ownership | Not explicitly rate-limited in architecture — open question, see §10 | Critical — controls fee calculation for all users |
| Health | None | None | Not rate-limited | Low |

---

## 8. PDPA Compliance Map

| Operation | Personal data in response | Included in data export? | Deletion-lifecycle role |
|---|---|---|---|
| Dashboard, Position detail, Lot, DividendTranche reads | Financial holdings data tied to the authenticated user | Yes (Position, Lot, DividendTranche per architecture §10.7 table) | N/A |
| PDPA data export | Full personal + financial profile assembled into one file | — (this *is* the export) | Satisfies PDPA right of access (Malaysian PDPA §30) |
| Account deletion request | None beyond confirmation | N/A | Initiates 30-day grace period; immediately invalidates all sessions; triggers confirmation email with cancellation token |
| Account deletion cancellation | None | N/A | Restores prior `account_status`; must validate the token has not expired or been used |
| Hard-delete (cron, not an API operation) | N/A — not client-facing | N/A | Permanently removes all rows per architecture §13.5; frees the email address for re-registration |
| Manual price override | Stock code, price — indirectly tied to the user who entered it via `created_by_user_id` | Excluded — PriceSnapshot is system-shared, not personal data (architecture §10.7 explicit exclusion) | N/A |
| Custom BrokerConfig | Fee structure the user defined | Included (custom only; system brokers excluded — they aren't personal data) | N/A |

**Fields that must never appear in any response body, per architecture §10.7 and §14.7:** `password_hash`, `token_version`, internal foreign keys not meaningful to the user, soft-delete markers on exported records (soft-deleted records themselves are excluded entirely), and `AuditLog.metadata` (may contain IP addresses — excluded from the export per the architecture's explicit note, though `action`/`entity_type`/`entity_id`/`created_at` are included).

**Token handling requirement (from the API prompt library's BursaTrack-Specific API Priorities §4):** email verification, password reset, and deletion-cancellation tokens must travel as query parameters, not path segments, to avoid tokens landing in server access logs at the URL-routing layer. (Both are technically loggable, but path segments are more commonly captured by default logging middleware and CDN/proxy access logs; query-parameter placement is the documented mitigation and matches the pattern already used for `GET /auth/verify?token=xxx` in architecture §10.1.)

---

## 9. Audit Trail Map

Cross-referencing the 18 audit events defined in architecture §14.7 against the operation inventory in §4:

| Audit event (`action` value) | Triggering operation | Data the audit record must capture | Same-transaction requirement |
|---|---|---|---|
| `USER_REGISTERED` | Register | New user_id, email (in metadata) | Yes — architecture §10.1 shows this inside the registration transaction |
| `USER_LOGIN` | Log in | user_id, timestamp, IP | Not shown as transactional in the architecture's sequence diagrams; treated as a fire-and-forget write — **flagged as an open question in §10** |
| `PASSWORD_CHANGED` | Complete password reset | user_id, timestamp | Yes |
| `LOT_CREATED` | Add position / Add lot | New lot_id, all computed fee fields | Yes |
| `LOT_UPDATED` | Edit lot | lot_id, previous_values, new_values | Yes |
| `LOT_DELETED` | Delete lot | lot_id | Yes |
| `DIVIDEND_CREATED` | Log dividend tranche | tranche_id, qualifying_shares, total_amount | Yes — architecture §10.2 shows this explicitly inside the same transaction |
| `DIVIDEND_UPDATED` | Edit dividend tranche | tranche_id, previous_values, new_values | Yes |
| `DIVIDEND_DELETED` | Delete dividend tranche | tranche_id | Yes |
| `PRICE_OVERRIDE_CREATED` | Manual price override | stock_code, price, user_id | Yes |
| `IMPORT_COMPLETED` | CSV import (fires when the BackgroundTask finishes, not when the upload is accepted) | job_id, positions/lots/tranches created counts | Yes, within the BackgroundTask's own transaction — not the original request's transaction, since import is async |
| `SUBSCRIPTION_ACTIVATED` | Stripe webhook (`checkout.session.completed`) | user_id, stripe event_id | Yes — architecture §10.4 shows this inside the webhook handler's transaction |
| `SUBSCRIPTION_CANCELLED` | Stripe webhook (`customer.subscription.deleted`) | user_id | Presumed yes, by symmetry with `SUBSCRIPTION_ACTIVATED` — not explicitly diagrammed |
| `DELETION_REQUESTED` | Request account deletion | user_id, deletion_requested_date | Yes — architecture §10.5 |
| `DELETION_CANCELLED` | Cancel pending deletion | user_id | Yes — architecture §10.5 |
| `ACCOUNT_DELETED` | Hard-delete (cron, not an API operation) | Anonymised, in `system_deletion_log` rather than `audit_log` (the user row and its audit_log rows are cascade-deleted together) | N/A — not an API-triggered event |
| `CONFIG_UPDATED` | Update fee configuration (Admin) | key, previous value, new value | Presumed yes — not explicitly diagrammed in the architecture but implied by the general audit rule (P-010) |
| `DATA_EXPORT_DOWNLOADED` | PDPA data export | user_id, timestamp | Yes — architecture §10.7 shows this explicitly before the response streams |

---

## 10. Gaps, Contradictions, and Open Questions

These items are genuinely unresolved by the supplied documents and are flagged here rather than silently resolved. Stage 2 must either treat them as constraints to design around or explicitly note them as still-open in the decision record.

1. **`USER_LOGIN` and `SUBSCRIPTION_CANCELLED` transactional guarantee is not explicitly diagrammed.** Architecture §14.7 lists them as required audit events, but only `USER_REGISTERED`, `DIVIDEND_CREATED`, `SUBSCRIPTION_ACTIVATED`, `DELETION_REQUESTED`/`DELETION_CANCELLED`, and `DATA_EXPORT_DOWNLOADED` appear inside explicit sequence diagrams. Stage 2/3 should assume the same same-transaction rule applies uniformly (per architecture P-010, "audit everything sensitive") rather than treating the absence of a diagram as license for a weaker guarantee.

2. **Admin endpoint rate limiting is unspecified.** Architecture §14.4's rate-limit table does not include `/admin/config/fees`. Given this endpoint controls fee calculation for every user, an unlimited-rate shared-secret endpoint is a plausible brute-force target for the `ADMIN_API_KEY` itself. This is an open question for Stage 2 (ADD-009 discusses the header format but not a rate limit).

3. **BAS Open Question OQ-005 (sell-calculator broker for multi-lot positions) is unresolved by BA analysis and directly affects this operation's request shape.** BAS §13 states the default is "most recently created active lot's broker," pending stakeholder confirmation, with user override. Stage 2/3 must design the sell-scenario operation to accept an optional broker override without waiting on this stakeholder decision, since a request-shape decision (does the client always have the *option* to override?) does not require the default-logic decision to be finalized.

4. **BAS OQ-003 (dividend tranche year: calendar year vs. stock financial year) affects the dividend calendar filtering contract.** The BAS explicitly defers this to a stakeholder decision. The API's `?year=` filter semantics (§7 of the design workshop, ADD-007) cannot be fully finalized until this is resolved; Stage 2 should design the filter parameter to be year-boundary-agnostic (an opaque integer year) so the resolution of OQ-003 does not require an API contract change, only a change to which `year` value the server assigns at write time.

5. **Contradiction check — PRD vs. architecture on Stripe plan selection:** The PRD (§10, V1 scope) does not describe multiple pricing tiers, and architecture §10.4's checkout sequence shows no plan parameter in `POST /subscription/checkout`. Confirmed as **no contradiction** — V1 has exactly one plan, so the checkout operation requires no client-supplied plan identifier. Flagged here only to make explicit that this was checked, not assumed.

6. **Operation implied by BAS but not explicit in the architecture's endpoint references:** BAS VR-014 (custom broker validation) and BAS §10.6 in the architecture both independently confirm custom BrokerConfig CRUD, so this is resolved — not a gap. No operations were found in the BAS/PRD that lack a corresponding architecture endpoint, and no architecture endpoint (per the complete inventory in the Stage 3 prompt) lacks a corresponding business justification in the BAS/PRD. The inventories are consistent.

7. **`GET /api/v1/portfolio/positions/{id}/sell-scenario` computation scope:** BAS Workflow 6 and PRD REQ-007 describe the calculator as always bound to an existing position (it pre-populates from stored position data). The architecture's endpoint inventory (Stage 3 prompt) confirms this as a path-scoped operation, not a free-standing calculator accepting arbitrary stock/price/shares inputs. This resolves what might otherwise look like an ambiguity between "position-bound" and "arbitrary input" calculator designs — the documents agree it is position-bound.
