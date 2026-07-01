# BursaTrack — Enhanced Business Analyst Specification
## Part 2 of 3: Sections 6–9

> **Version:** 2.0 — Enhanced
> **Date:** 2026-06-21
> **Annotation key:** `[FIXED: reason]` | `[NEW: reason]` | No annotation = KEEP
> **Continuation of Part 1 (Sections 1–5)**

---

# 6. PROCESS FLOWS / WORKFLOWS

---

## Workflow 1 — New User Registration and Email Verification

```
[User] → Opens Registration Page
         ↓
[User] → Enters: email, password, confirm password, default broker
         ↓
[System] → Validates inputs (see §8 Validation Rules)
         ↓ FAIL → Display inline field errors (no account created)
         ↓ PASS
[System] → Creates User (status: "trial")
         → Sets trial_expiry = today + 14 days
         → Creates empty Portfolio linked to User
         → Generates email verification token (24-hour expiry)
         → Sends verification email
         ↓
[System] → Redirects to Dashboard with banner:
           "Please verify your email. Check your inbox."
         ↓
[User] → Clicks verification link in email
         ↓
[System] → Validates token (exists, unused, not expired)
         ↓ EXPIRED → "Verification link expired. Request a new link?" → Resend email
         ↓ VALID
[System] → Marks email as verified
         → Redirects to Dashboard (verification banner removed)

END: User is registered, email verified, portfolio is empty and ready to use.
```

---

## Workflow 2 — Add Position with Multiple Lots

```
[User] → Navigates to Portfolio → "Add Position"
         ↓
[User] → Enters: stock code/name, shares, price, date, broker, category tag
         ↓
[System] → Validates inputs
         ↓ FAIL → Display inline errors
         ↓ PASS
[System] → Calculates: initial amount, brokerage, clearing, stamp duty, all-in cost (BR-001–007, BR-025)
         → Creates Lot record (Lot #1)
         → Creates Position record (or updates if stock already in portfolio — see EC-001)
         → Updates Portfolio summary
         ↓
[User] → Reviews position row on Dashboard
         → Clicks "Add Lot" on the position
         ↓
[User] → Enters: shares, price, date, broker (overrideable)
         ↓
[System] → Validates inputs
         → Calculates Lot #2 fees and all-in cost
         → Creates Lot #2 record linked to existing Position
         → Recalculates Position aggregates:
             · total_shares = Lot1.shares + Lot2.shares
             · total_all_in_cost = Lot1.all_in_cost + Lot2.all_in_cost
             · blended_price = (Lot1.initial_amount + Lot2.initial_amount) / total_shares
         → Updates Portfolio summary

NOTE: Existing DividendTranche.total_amount values are NOT affected by adding Lot #2.
      (See BR-009, BR-027)

END: Position updated with both lots; blended cost basis correct; historical dividends unchanged.
```

---

## Workflow 3 — Daily Price Refresh (Happy Path and Failure Paths)

```
[Scheduler] → Fires at 5:30 PM MYT on Bursa trading days (Mon–Fri, excl. holidays)
              ↓
[System] → Checks: is today a trading day? (consult configured Bursa holiday calendar)
              ↓ NO → Job exits; no action taken; "last refreshed" timestamp not updated
              ↓ YES
[System] → Collects unique stock codes across all active portfolios (non-deleted positions)
              ↓
[System] → Queries price data provider (yfinance) for each stock code
              ↓
           ┌──────────────────────┬──────────────────────────────────┐
           │ All responses valid  │ One or more responses invalid    │
           ↓                      ↓                                  ↓
[System] → Creates/updates       [System] → Creates PriceSnapshot    [System] → Also creates
           PriceSnapshot for each           for successful stocks.               PriceSnapshot
           stock (source="auto")            Marks failed stocks                  with source="stale"
           Updates Portfolio                as source="stale".                   for failed codes.
           "last_refreshed"                ↓
           timestamp.                    Within 5 minutes:
           Recalculates                  Dashboard banner:
           unrealised P&L.              "Price data unavailable for
                                         [N] stocks — last updated
                                         [timestamp]. Update manually."
                                         Manual price entry enabled
                                         for affected positions.

Manual Override Sub-flow:
[User] → Enters price manually for a stale-priced stock
[System] → Creates PriceSnapshot (source="manual", timestamp=now)
         → Recalculates unrealised P&L immediately for that position

Override Supersession:
[Scheduler] → Next successful automated refresh
[System] → Creates PriceSnapshot (source="auto") for previously-manual stocks
          → Manual override is superseded; stale/manual indicators removed

END: Portfolio always shows the most recent available price with clear provenance.
```

---

## Workflow 4 — Log Dividend Tranche

**[FIXED: Original workflow stated "System derives: total_amount = per_share × position_total_shares" — this causes retroactive corruption. Corrected to store qualifying_shares at logging time and derive/store total_amount from qualifying_shares, not from live position_total_shares.]**

```
[User] → Opens Position detail → "Add Dividend"
         ↓
[User] → Enters:
         · Tranche label (system suggests next available: 1st, 2nd, … 8th)
         · Dividend per share (MYR — up to 6 decimal places)
         · Payment date
         · Ex-dividend date (optional)
         ↓
[System] → Displays "Qualifying Shares" field pre-populated with
           current position_total_shares (e.g., 5,000)
           Guidance text: "This is the number of shares you held before the ex-dividend
           date. Change this if you held fewer shares than your current total."
         ↓
[User] → Reviews qualifying_shares (accepts default or overrides)
         ↓
[System] → Validates all inputs:
           · per_share_amount > 0
           · qualifying_shares ≥ 1 AND ≤ position_total_shares
           · tranche count for this year < 8 (BR-014)
         ↓ FAIL → Display inline validation error
         ↓ PASS
[System] → STORES:
           · qualifying_shares = value from user (default = current position_total_shares)
           · total_amount = per_share_amount × qualifying_shares [STORED, not derived]
           · Creates DividendTranche record with all fields

           ⚠ total_amount is a STORED VALUE.
             It does NOT recompute when position_total_shares changes in the future.
             It only changes if the user explicitly edits this tranche.
         ↓
[System] → Recalculates:
           · position_total_dividend_income_ytd = SUM(DividendTranche.total_amount) for year
           · position_yield = position_total_dividend_income_ytd / position_total_all_in_cost
           · portfolio_blended_yield = SUM(all positions' income) / SUM(all positions' cost)
         ↓
[System] → Updates Dashboard and Position detail view
         → Updates Dividend Calendar (if ex_dividend_date was entered)

END: Dividend recorded with immutable total. Future share purchases will not corrupt this record.
```

---

## Workflow 5 — CSV Import

```
[User] → Navigates to Import page → "Download Template"
[System] → Serves BursaTrack_Import_Template.csv

[User] → Populates template with portfolio data
       → Uploads CSV file

[System] → Phase 1: File-level validation
           · File is valid CSV format
           · Required column headers present (all required columns)
           · File size ≤ limit (e.g., 5 MB)
           ↓ FAIL → "Import failed: [specific issue]. No records imported."

         → Phase 2: Row-level validation (all rows, all sheets)
           · Required fields not empty
           · Numeric fields valid and in range
           · Stock codes valid Bursa-listed securities
           · Date fields valid dates, not in future
           · Tranche count per position per year ≤ 8
           · qualifying_shares ≤ position shares (if qualifying_shares column present)
           ↓ FAIL → Row-level error report:
                     "Row [N], Column [X]: [specific error message]"
                     All rows listed. No records imported.

         → Phase 3: Atomic create (only if all rows pass)
           · Begin transaction
           · Create all Position, Lot, DividendTranche records
           · For each DividendTranche: store qualifying_shares
             (from optional column if present; default = position shares as imported)
           · Store total_amount = per_share × qualifying_shares
           · Commit transaction
           ↓
[System] → Redirects to Dashboard with:
           "Import complete — [N] positions, [M] lots, and [K] dividend records imported."
           Yield calculations performed for all positions.

END: Full portfolio created atomically. No partial imports.
```

---

## Workflow 6 — Sell Scenario Calculator

```
[User] → Opens Position detail → "Sell Calculator"
         ↓
[System] → Pre-populates:
           · Stock name and code
           · Total shares (sum of all active lots)
           · All-in buy cost (sum of all lots' all-in costs)
           · Current price (from latest PriceSnapshot)
           · Default sell broker (broker of most recently created active lot)
         ↓
[User] → May adjust:
         · Shares to sell (default: all; partial sale available per BR-024)
         · Sell broker (override if desired)
         ↓
[System] → Generates scenario rows at:
           current_price + 0.01, +0.02, +0.03, +0.04, +0.05,
           then +0.10, +0.15, … +0.70 (in 0.05 steps)
         ↓
[System] → For each scenario price, calculates:
           · gross_proceeds = scenario_price × shares_to_sell
           · sell_brokerage = MAX(gross_proceeds × rate, min_fee) or flat_fee
           · sell_clearing = gross_proceeds × 0.0003 (capped at RM1,000; rounded per BR-025)
           · sell_stamp = ROUNDUP(gross_proceeds / 1000, 0)
           · net_proceeds = gross_proceeds − (sell_brokerage + sell_clearing + sell_stamp)
           · buy_cost_basis = (shares_to_sell / total_shares) × all_in_buy_cost [if partial]
           · profit_loss = net_proceeds − buy_cost_basis
         ↓
[System] → Highlights break-even row (lowest price where profit_loss ≥ 0)
         → Displays non-dismissable disclosure:
           "Calculations informational only. Settlement T+2." (BR-020)
           "Not financial advice." (BR-021)
         ↓
[User] → May enter custom sell price
[System] → Calculates and adds the custom price as a row

END: User has a fee-accurate break-even analysis. Calculator results are not persisted.
```

---

## Workflow 7 — Subscription Lifecycle

```
[Trigger] → trial_expiry date reached (background job)
[System] → Sets account status = "trial_expired"

[User] → Next login attempt
[System] → Detects trial_expired
         → Displays paywall: portfolio visible in read-only mode
         → "Your trial has ended. Subscribe to continue."
         ↓
[User] → Clicks "Subscribe" → Selects plan

[System] → Redirects to payment processor
         ↓
[Payment Processor] → Payment success callback
[System] → Account status = "active"
         → Stores: subscription_start_date, billing_period, next_renewal_date
         → Redirects to Dashboard with full access

[Renewal path]
[Scheduler] → On next_renewal_date, charges subscription
            → On success: updates next_renewal_date
            → On failure: retries for grace period → after grace period: status = "trial_expired"

[Cancellation path]
[User] → Account Settings → "Cancel Subscription"
[System] → Displays: "Your subscription ends [next_renewal_date]. Data preserved."
         → User confirms
         → Schedules status change to "trial_expired" on next_renewal_date
         → Until that date: user retains full access

END: Data always preserved; no forced deletion on subscription state change (BR-018).
```

---

## Workflow 8 — Password Reset

**[NEW: Standard auth flow; entirely absent from the original BAS. Required before engineering begins the authentication sprint.]**

```
[User] → Login page → "Forgot Password?"
         ↓
[User] → Enters email address → Submits
         ↓
[System] → Checks for account with this email (NO observable difference in response regardless of result)
         ↓
         ┌─────────────────────────────┬───────────────────────────────┐
         │ Account NOT found           │ Account found                 │
         ↓                             ↓                               │
[System] → Displays same message:    [System] → Generates reset token │
           "If an account with that             (single-use, 1-hr expiry)
            email exists, a reset link          Sends password reset email
            has been sent."                     with reset link
                                        ↓
[System] → Displays same message to both paths:
           "If an account with that email exists, a reset link has been sent."

SECURITY NOTE: The response MUST be identical for both cases (account found and not found).
               Response timing should also not vary between cases.

[User] → Clicks reset link in email
         ↓
[System] → Validates token:
           ↓ EXPIRED (> 1 hour) → "This reset link has expired. Request a new one?"
                                    → Returns user to Forgot Password page
           ↓ ALREADY USED → "This reset link has already been used.
                              If you did not reset your password, contact support."
           ↓ VALID
[System] → Presents "Set New Password" form

[User] → Enters new password and confirmation
         ↓
[System] → Validates password (see §8 Validation Rules)
         ↓ FAIL → Display inline error
         ↓ PASS
[System] → Hashes new password (same algorithm as registration)
         → Updates User.password_hash
         → Marks reset token as used
         → Invalidates ALL active sessions for this user
         → Redirects to login page:
           "Password updated successfully. Please log in."

END: User can now log in with new password. No prior sessions remain active.
```

---

## Workflow 9 — Account Deletion / PDPA Erasure

**[NEW: PDPA right of erasure workflow; entirely absent from the original BAS. Required for Malaysian PDPA compliance.]**

```
[User] → Account Settings → "Delete My Account"
         ↓
[System] → Step 1: Offers data export
           "Before deleting, would you like to download your data?"
           [Download My Data] [Skip and Continue]
         ↓
           If "Download My Data": executes FR-018 export, then returns to step 2
           If "Skip": proceeds to step 2

[System] → Step 2: Final confirmation
           "This will permanently delete your account and ALL your data in 30 days.
            To confirm, type DELETE below."
         ↓
[User] → Types "DELETE" and submits
         ↓
[System] → Sets account status = "pending_deletion"
         → Records deletion_requested_date = today
         → Calculates permanent_deletion_date = today + 30 days
         → Sends confirmation email:
           "Your deletion request is confirmed. Your data will be permanently deleted on
            [permanent_deletion_date]. To cancel, click: [cancellation link, 30-day expiry]"
         → Logs out user; invalidates all sessions
         → User cannot log in while status = "pending_deletion"

CANCELLATION PATH (within 30 days):
[User] → Clicks cancellation link in email
[System] → Validates link (within 30 days)
         → Restores account to previous status (trial_expired or active)
         → Sends cancellation confirmation: "Account deletion cancelled. You can log in again."
         → User can log in again

PERMANENT DELETION PATH (30-day window expires without cancellation):
[Scheduler] → Runs on permanent_deletion_date
[System] → Hard-deletes (irreversible):
           · User record
           · Portfolio record
           · All Position records (including soft-deleted)
           · All Lot records
           · All DividendTranche records
           · All PriceSnapshot records linked to this user's positions
           · All AuditLog entries attributed to this user
         → Email address is freed; can be re-registered
         → System records deletion completion in an anonymised system log
           (no user-identifiable data; timestamp, reason="PDPA erasure" only)

END: User's data permanently and completely erased. PDPA right of erasure satisfied.
```

---

# 7. DATA REQUIREMENTS

## Entity Model Overview

Eight core entities form the BursaTrack data model:

1. **User** — authentication, subscription, PDPA lifecycle
2. **Portfolio** — container for one user's positions
3. **Position** — an equity holding in a specific stock, aggregating one or more Lots
4. **Lot** — a single buy transaction within a Position, containing all fee components
5. **DividendTranche** — a single dividend payment received for a Position
6. **PriceSnapshot** — a daily price record for a stock code, with provenance
7. **AuditLog** — immutable record of all data changes across key entities
8. **BrokerConfig** — fee structure for each supported broker (system-managed)

---

## Entity 1 — User

| Field | Type | Mandatory | Derived | Notes |
|-------|------|-----------|---------|-------|
| user_id | UUID | Yes | No | Primary key |
| email | String | Yes | No | Unique; max 254 chars; lowercase-normalized |
| password_hash | String | Yes | No | bcrypt or Argon2; never stored in plaintext |
| email_verified | Boolean | Yes | No | Default: false at registration |
| account_status | Enum | Yes | No | Values: trial, active, trial_expired, pending_deletion, suspended |
| trial_start_date | Date | Yes | No | Set at registration |
| trial_expiry_date | Date | Yes | No | = trial_start_date + 14 days (BR-017) |
| subscription_start_date | Date | No | No | Set when first paid subscription begins |
| subscription_renewal_date | Date | No | No | Next billing date |
| deletion_requested_date | Date | No | No | Set when account deletion is initiated |
| permanent_deletion_date | Date | No | No | = deletion_requested_date + 30 days |
| default_broker_id | FK → BrokerConfig | Yes | No | User's default broker for new positions |
| created_at | Timestamp | Yes | No | UTC |
| updated_at | Timestamp | Yes | Yes | Updated on any field change |

**Lifecycle:** Created at registration. Status transitions: trial → active → trial_expired (or suspended). Deletion path: pending_deletion → hard-deleted after 30 days. Email address freed on hard-delete.

---

## Entity 2 — Portfolio

| Field | Type | Mandatory | Derived | Notes |
|-------|------|-----------|---------|-------|
| portfolio_id | UUID | Yes | No | Primary key |
| user_id | FK → User | Yes | No | One Portfolio per User at V1 |
| created_at | Timestamp | Yes | No | UTC |

**Note:** Portfolio is a container entity. All aggregate metrics (total all-in cost, total dividend income, blended yield) are calculated at runtime from the Portfolio's Positions.

---

## Entity 3 — Position

| Field | Type | Mandatory | Derived | Notes |
|-------|------|-----------|---------|-------|
| position_id | UUID | Yes | No | Primary key |
| portfolio_id | FK → Portfolio | Yes | No | |
| stock_code | String | Yes | No | e.g., "1023" (Bursa code) |
| stock_name | String | Yes | No | e.g., "CIMB GROUP HOLDINGS BHD" |
| category_tag | Enum | Yes | No | Values: Dividend, Volatile, Growth; default: Dividend |
| is_deleted | Boolean | Yes | No | Default: false; soft-delete flag |
| deleted_at | Timestamp | No | No | Set on soft-delete |
| created_at | Timestamp | Yes | No | UTC |
| updated_at | Timestamp | Yes | Yes | Updated on any direct field change |

**Derived (runtime) aggregates — NOT stored on the Position record:**

| Aggregate | Calculation |
|-----------|-------------|
| total_shares | SUM(Lot.shares) for non-deleted Lots |
| total_initial_amount | SUM(Lot.initial_amount) for non-deleted Lots |
| total_all_in_cost | SUM(Lot.all_in_cost) for non-deleted Lots |
| blended_purchase_price | total_initial_amount / total_shares |
| total_dividend_income_ytd | SUM(DividendTranche.total_amount) where year = current year, non-deleted |
| dividend_yield | total_dividend_income_ytd / total_all_in_cost |
| current_market_value | total_shares × current_price (from latest PriceSnapshot) |
| unrealised_pnl | current_market_value − total_all_in_cost |

---

## Entity 4 — Lot

| Field | Type | Mandatory | Derived | Notes |
|-------|------|-----------|---------|-------|
| lot_id | UUID | Yes | No | Primary key |
| position_id | FK → Position | Yes | No | |
| shares | Integer | Yes | No | ≥ 1 |
| purchase_price | Decimal(10,4) | Yes | No | MYR per share; 4dp stored |
| purchase_date | Date | Yes | No | Must not be in the future |
| broker_id | FK → BrokerConfig | Yes | No | Broker for this specific lot |
| initial_amount | Decimal(12,2) | Yes | No | shares × purchase_price, rounded to 2dp |
| brokerage_fee | Decimal(10,2) | Yes | No | Calculated per BR-001–004 and BR-025 |
| clearing_fee | Decimal(10,2) | Yes | No | initial_amount × 0.0003, rounded per BR-025 |
| stamp_duty | Decimal(10,2) | Yes | No | ROUNDUP(initial_amount/1000, 0) |
| all_in_cost | Decimal(12,2) | Yes | No | initial_amount + brokerage + clearing + stamp_duty |
| is_deleted | Boolean | Yes | No | Default: false |
| deleted_at | Timestamp | No | No | Set on soft-delete |
| created_at | Timestamp | Yes | No | UTC |
| updated_at | Timestamp | Yes | Yes | |

**Note:** All fee components are individually calculated and stored at the time of Lot creation. If a user later edits the lot (shares, price, broker), fees are recalculated and the previous values are written to AuditLog before overwriting.

---

## Entity 5 — DividendTranche

**[FIXED: Added qualifying_shares field (the core of the BR-009 defect fix). Changed total_amount from "derived" to "stored." Added is_deleted, deleted_at fields which were omitted from the original entity definition. Corrected year field description.]**

| Field | Type | Mandatory | Derived | Notes |
|-------|------|-----------|---------|-------|
| tranche_id | UUID | Yes | No | Primary key |
| position_id | FK → Position | Yes | No | |
| tranche_label | Enum | Yes | No | Values: 1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th |
| per_share_amount | Decimal(10,6) | Yes | No | MYR per share; 6dp stored (e.g., 0.004813) |
| qualifying_shares | Integer | Yes | No | **STORED at logging time** — defaults to position_total_shares; user may override (≥ 1, ≤ position_total_shares at time of entry) |
| total_amount | Decimal(12,2) | Yes | **STORED** | **= per_share_amount × qualifying_shares, stored at logging time. NOT re-derived from live position_total_shares. Only changes if user explicitly edits this tranche.** |
| payment_date | Date | Yes | No | Date dividend was paid to the user |
| ex_dividend_date | Date | No | No | Ex-date from the company announcement; optional |
| year | Integer | Yes | No | Calendar year (default: YEAR(payment_date)). Used for tranche count limit (BR-014) and YTD income calculation |
| is_deleted | Boolean | Yes | No | Default: false |
| deleted_at | Timestamp | No | No | Set on soft-delete |
| created_at | Timestamp | Yes | No | UTC |
| updated_at | Timestamp | Yes | Yes | |

**Lifecycle:** Created when user logs a dividend. Editing per_share_amount or qualifying_shares triggers recalculation of total_amount and an AuditLog entry. Soft-deleted when user deletes the record. Hard-deleted on PDPA account deletion.

**Critical invariant:** After creation, `total_amount` changes ONLY when the user explicitly edits this tranche record. Adding new Lots to the parent Position does NOT change `total_amount`. This invariant must be enforced at the application layer.

---

## Entity 6 — PriceSnapshot

| Field | Type | Mandatory | Derived | Notes |
|-------|------|-----------|---------|-------|
| snapshot_id | UUID | Yes | No | Primary key |
| stock_code | String | Yes | No | Bursa stock code |
| price | Decimal(10,4) | Yes | No | MYR per share; 4dp stored |
| trading_date | Date | Yes | No | The trading day this price is for |
| source | Enum | Yes | No | Values: automated, manual, stale |
| refreshed_at | Timestamp | Yes | No | UTC timestamp of when this snapshot was created |
| created_by_user_id | FK → User | No | No | Populated only when source = "manual"; null for automated |

**Retention:** Price snapshots are not linked to individual users (they are shared across all portfolios that hold the same stock). On PDPA account deletion, only manual overrides created by the deleted user (via created_by_user_id) are removed; automated snapshots are retained.

---

## Entity 7 — AuditLog

**[FIXED: entity_type enum was missing "Position" — this contradicts the PRD NFR requirement that position edit history be logged. Added "Position" to the entity_type enum. Also added password_reset_token and session as entity types for Workflow 8.]**

| Field | Type | Mandatory | Derived | Notes |
|-------|------|-----------|---------|-------|
| audit_id | UUID | Yes | No | Primary key |
| user_id | FK → User | Yes | No | The user who performed the action |
| action | Enum | Yes | No | Values: CREATE, UPDATE, DELETE |
| entity_type | Enum | Yes | No | Values: **Position** `[FIXED]`, Lot, DividendTranche, Portfolio, PriceSnapshot, User |
| entity_id | UUID | Yes | No | ID of the affected record |
| previous_values | JSON | No | No | Snapshot of the record before the change (null for CREATE) |
| new_values | JSON | No | No | Snapshot of the record after the change (null for DELETE) |
| changed_at | Timestamp | Yes | No | UTC; server-side timestamp |
| ip_address | String | No | No | For security audit purposes |

**What must be audited:**
- Lot: every CREATE, UPDATE, DELETE
- DividendTranche: every CREATE, UPDATE, DELETE (including qualifying_shares and total_amount changes)
- Position: every CREATE, DELETE; UPDATE to category_tag or stock_name
- User: account status changes, email changes, password changes, deletion requests
- PriceSnapshot: manual overrides (source="manual") only; not automated refreshes

**AuditLog records are immutable** — they may not be edited or deleted except by the PDPA hard-deletion process for the owning user.

---

## Entity 8 — BrokerConfig

| Field | Type | Mandatory | Derived | Notes |
|-------|------|-----------|---------|-------|
| broker_id | UUID | Yes | No | Primary key |
| broker_name | String | Yes | No | e.g., "Maybank Investment" |
| fee_type | Enum | Yes | No | Values: percentage, flat |
| rate | Decimal(8,6) | No | No | For fee_type = "percentage" (e.g., 0.001000 = 0.10%) |
| minimum_fee | Decimal(10,2) | No | No | For fee_type = "percentage" (e.g., 8.00 = RM8) |
| flat_fee | Decimal(10,2) | No | No | For fee_type = "flat" (e.g., 3.00 = RM3) |
| is_active | Boolean | Yes | No | Inactive brokers hidden from new dropdowns but retained for existing lots |
| is_custom | Boolean | Yes | No | True if created by the user (custom broker); false for system-provided |
| created_by_user_id | FK → User | No | No | Populated for custom brokers; null for system brokers |
| created_at | Timestamp | Yes | No | UTC |

**V1 system brokers (pre-populated):**

| Broker Name | Fee Type | Rate | Min Fee | Flat Fee |
|-------------|----------|------|---------|----------|
| Maybank Investment | percentage | 0.10% | RM8 | — |
| CIMB Invest | percentage | 0.10% | RM8 | — |
| RHB Invest | percentage | 0.10% | RM8 | — |
| AMBit | percentage | 0.10% | RM8 | — |
| MooMoo | flat | — | — | RM3 |
| Rakuten Trade | flat | — | — | RM7 (tiered structure deferred to V1.1) |
| Custom | — | user-defined | user-defined | user-defined |

**Stamp Duty System Config (not a BrokerConfig entity — separate system setting):**

| Setting | Value | Notes |
|---------|-------|-------|
| stamp_duty_rate | RM1 per RM1,000 (0.10%) | Gazetted until 12 July 2028; externally configurable without code deployment (BR-015) |

---

## CSV Import Template Specification

The import file has two worksheets/sections:

### Sheet 1 — Positions & Lots

| Column | Mandatory | Format | Example |
|--------|-----------|--------|---------|
| stock_code | Yes | Bursa code (4 chars, numeric) | 1023 |
| stock_name | Yes | String, max 100 chars | CIMB GROUP HOLDINGS BHD |
| category_tag | No | Dividend / Volatile / Growth | Dividend |
| lot_number | Yes | Integer ≥ 1 | 1 |
| shares | Yes | Integer ≥ 1 | 5000 |
| purchase_price | Yes | Decimal, 4dp | 8.3800 |
| purchase_date | Yes | YYYY-MM-DD | 2026-01-15 |
| broker_name | Yes | Must match a BrokerConfig.broker_name exactly (or "Custom") | Maybank Investment |
| custom_broker_rate | Conditional | Decimal if broker_name = "Custom" | 0.001 |
| custom_broker_min_fee | Conditional | Decimal if broker_name = "Custom" | 8.00 |
| custom_flat_fee | Conditional | Decimal if broker_name = "Custom" and flat fee | — |

### Sheet 2 — Dividend Tranches

| Column | Mandatory | Format | Example |
|--------|-----------|--------|---------|
| stock_code | Yes | Must match a stock_code from Sheet 1 | 1023 |
| tranche_label | Yes | 1st / 2nd / … / 8th | 1st |
| per_share_amount | Yes | Decimal, up to 6dp | 0.200000 |
| qualifying_shares | No | Integer; defaults to total shares for this stock in Sheet 1 | 5000 |
| payment_date | Yes | YYYY-MM-DD | 2026-03-15 |
| ex_dividend_date | No | YYYY-MM-DD | 2026-02-28 |
| year | No | YYYY; defaults to YEAR(payment_date) | 2026 |

---

# 8. VALIDATION RULES

---

## VR-001 — Email Address

| Field | Rule | Error Message |
|-------|------|---------------|
| email | Required | "Email address is required" |
| email | Valid format (RFC 5321) | "Please enter a valid email address" |
| email | Max 254 characters | "Email address must be under 254 characters" |
| email | Unique (on registration) | "An account with this email already exists. Log in instead?" |
| email | Normalized to lowercase before storage | _(no visible error; silent normalization)_ |

---

## VR-002 — Password

| Field | Rule | Error Message |
|-------|------|---------------|
| password | Required | "Password is required" |
| password | Min 8 characters | "Password must be at least 8 characters" |
| password | Max 128 characters | "Password must be under 128 characters" |
| password | Must contain at least one uppercase letter | "Password must contain at least one uppercase letter" |
| password | Must contain at least one digit | "Password must contain at least one digit" |
| password_confirm | Must match password | "Passwords do not match" |

---

## VR-003 — Stock Code and Name

| Field | Rule | Error Message |
|-------|------|---------------|
| stock_code | Required | "Stock code is required" |
| stock_code | Must be a valid Bursa Malaysia listed security | "This stock code is not recognized as a Bursa Malaysia listed security" |
| stock_name | Required | "Stock name is required" |
| stock_name | Max 100 characters | "Stock name must be under 100 characters" |

**Note:** The system must maintain a reference list of valid Bursa stock codes. This list may be bundled (updated periodically) or validated against a live API. At V1, bundled with periodic update is acceptable. Invalid-code validation must not block position creation during price feed outages — the stale-data path (FR-008) applies to price only, not to stock-code validation.

---

## VR-004 — Shares

| Field | Rule | Error Message |
|-------|------|---------------|
| shares | Required | "Number of shares is required" |
| shares | Must be a positive integer (≥ 1) | "Number of shares must be greater than zero" |
| shares | Must be a whole number | "Number of shares must be a whole number" |
| shares | Max 99,999,999 | "Number of shares cannot exceed 99,999,999" |

---

## VR-005 — Purchase Price

| Field | Rule | Error Message |
|-------|------|---------------|
| purchase_price | Required | "Purchase price is required" |
| purchase_price | Must be > 0 | "Purchase price must be greater than zero" |
| purchase_price | Max 4 decimal places | "Purchase price can have at most 4 decimal places" |
| purchase_price | Max RM99,999.9999 | "Purchase price seems unusually high. Please verify." (warning, not block) |

---

## VR-006 — Purchase Date

| Field | Rule | Error Message |
|-------|------|---------------|
| purchase_date | Required | "Purchase date is required" |
| purchase_date | Valid date format (YYYY-MM-DD) | "Please enter a valid date (YYYY-MM-DD)" |
| purchase_date | Must not be in the future | "Purchase date cannot be in the future" |
| purchase_date | Must not be before 1990-01-01 | "Purchase date seems too far in the past. Please verify." (warning, not block) |

---

## VR-007 — Broker

| Field | Rule | Error Message |
|-------|------|---------------|
| broker_id | Required | "Please select a broker" |
| broker_id | Must reference an active BrokerConfig | "The selected broker is not available" |

---

## VR-008 — Dividend Per Share Amount

| Field | Rule | Error Message |
|-------|------|---------------|
| per_share_amount | Required | "Dividend per share is required" |
| per_share_amount | Must be > 0 | "Dividend per share must be greater than zero" |
| per_share_amount | Max 6 decimal places | "Dividend per share can have at most 6 decimal places" |
| per_share_amount | Max RM999.999999 | "Dividend per share seems unusually high. Please verify." (warning, not block) |

---

## VR-009 — Dividend Payment Date

| Field | Rule | Error Message |
|-------|------|---------------|
| payment_date | Required | "Payment date is required" |
| payment_date | Valid date format | "Please enter a valid date (YYYY-MM-DD)" |
| payment_date | Must not be more than 30 days in the future | "Payment date cannot be more than 30 days in the future" |

**Rationale for 30-day future allowance:** Users may log dividends just before receipt (e.g., they know the payment is coming). Blocking future dates would cause friction with no quality benefit.

---

## VR-010 — Ex-Dividend Date

| Field | Rule | Error Message |
|-------|------|---------------|
| ex_dividend_date | Optional | _(no error if empty)_ |
| ex_dividend_date | If provided: valid date format | "Please enter a valid date (YYYY-MM-DD)" |
| ex_dividend_date | If provided: must be before or equal to payment_date | "Ex-dividend date must be before or on the payment date" |
| ex_dividend_date | If provided: must not be more than 1 year before payment_date | "Ex-dividend date seems too far before the payment date. Please verify." (warning) |

---

## VR-011 — Qualifying Shares

**[NEW: Validation rules for qualifying_shares were entirely absent from the original BAS. Required by the BR-009 fix.]**

| Field | Rule | Error Message |
|-------|------|---------------|
| qualifying_shares | Required (auto-populated; user can override) | "Qualifying shares is required" |
| qualifying_shares | Must be a positive integer (≥ 1) | "Qualifying shares must be at least 1" |
| qualifying_shares | Must be ≤ position_total_shares at the time of entry | "Qualifying shares cannot exceed the position's current total shares ([N])" |
| qualifying_shares | Must be a whole number | "Qualifying shares must be a whole number" |

**On edit:** Must be ≤ position_total_shares at the time of editing (which may be different from creation time if new lots have been added since).

---

## VR-012 — Dividend Year

**[NEW: No validation existed for the year field; required because the tranche limit (BR-014) is enforced per-year.]**

| Field | Rule | Error Message |
|-------|------|---------------|
| year | Default: YEAR(payment_date); editable | _(auto-populated)_ |
| year | Must be a valid 4-digit calendar year | "Please enter a valid year (YYYY)" |
| year | Must be between 1990 and current year + 1 | "Year must be between 1990 and [current year + 1]" |
| year | Tranche count for this position + year must be < 8 | "Maximum of 8 dividend tranches per year reached for [Stock] ([Year])" |

---

## VR-013 — CSV Import File

| Field | Rule | Error Message |
|-------|------|---------------|
| file | Required | "Please select a file to upload" |
| file | Must be .csv extension | "File must be a CSV file (.csv)" |
| file | Max file size: 5 MB | "File is too large (max 5 MB)" |
| file | All required column headers must be present | "Import failed: Required column '[column_name]' is missing" |
| stock_code (CSV) | Must match a valid Bursa stock code | "Row [N]: Stock code '[value]' is not a valid Bursa-listed security" |
| tranche_label (CSV) | Must be one of: 1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th | "Row [N]: Tranche label must be one of: 1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th" |
| qualifying_shares (CSV, if provided) | Must be ≤ sum of lot shares for that stock_code in the same import | "Row [N]: qualifying_shares ([value]) exceeds total shares for [stock_code] in this import ([N])" |

---

## VR-014 — Custom Broker

**[NEW: No validation rules existed for custom broker fields; required because users can define their own broker fee structures.]**

| Field | Rule | Error Message |
|-------|------|---------------|
| broker_name (custom) | Required | "Broker name is required" |
| broker_name (custom) | Max 60 characters | "Broker name must be under 60 characters" |
| broker_name (custom) | Must not duplicate an existing system broker name | "This broker name already exists. Choose a different name." |
| fee_type | Required: one of "percentage" or "flat" | "Please select a fee type" |
| rate (percentage) | Required if fee_type = percentage | "Brokerage rate is required" |
| rate (percentage) | 0 < rate ≤ 0.02 (0% to 2%) | "Brokerage rate must be between 0% and 2%" |
| minimum_fee (percentage) | Required if fee_type = percentage | "Minimum fee is required" |
| minimum_fee (percentage) | ≥ 0, ≤ RM100 | "Minimum fee must be between RM0 and RM100" |
| flat_fee (flat) | Required if fee_type = flat | "Flat fee amount is required" |
| flat_fee (flat) | 0 < flat_fee ≤ RM100 | "Flat fee must be between RM0.01 and RM100" |

---

# 9. PERMISSIONS AND ACCESS CONTROL

## Role Model

BursaTrack has two roles at V1:

| Role | Description |
|------|-------------|
| **User** | Authenticated account owner. Has access to their own data only. |
| **System** | Backend/automated processes (scheduler, batch jobs). No user-facing login. |

A third role (Admin) is deferred to V2.

---

## Permission Matrix

| Action | Unauthenticated | Trial User | Paid User | Trial-Expired User | Pending-Deletion User | System |
|--------|-----------------|------------|-----------|-------------------|-----------------------|--------|
| Register | ✓ | — | — | — | — | — |
| Log in | ✓ | ✓ | ✓ | ✓ | ✗ | — |
| Log out | — | ✓ | ✓ | ✓ | ✗ | — |
| Reset password | ✓ | ✓ | ✓ | ✓ | ✗ | — |
| View portfolio (dashboard) | ✗ | ✓ | ✓ | Read-only | ✗ | — |
| Add position / lot | ✗ | ✓ | ✓ | ✗ (paywall) | ✗ | — |
| Edit position / lot | ✗ | ✓ | ✓ | ✗ (paywall) | ✗ | — |
| Delete position | ✗ | ✓ | ✓ | ✗ (paywall) | ✗ | — |
| Log dividend tranche | ✗ | ✓ | ✓ | ✗ (paywall) | ✗ | — |
| Edit / delete dividend | ✗ | ✓ | ✓ | ✗ (paywall) | ✗ | — |
| View sell calculator | ✗ | ✓ | ✓ | Read-only | ✗ | — |
| View dividend calendar | ✗ | ✓ | ✓ | Read-only | ✗ | — |
| CSV import | ✗ | ✓ | ✓ | ✗ (paywall) | ✗ | — |
| Download CSV template | ✗ | ✓ | ✓ | ✓ | ✗ | — |
| Manual price override | ✗ | ✓ | ✓ | ✗ (paywall) | ✗ | — |
| Download my data (PDPA) | ✗ | ✓ | ✓ | ✓ | ✗ | — |
| Request account deletion | ✗ | ✓ | ✓ | ✓ | ✗ | — |
| Cancel deletion request | ✗ | — | — | — | ✓ (email link) | — |
| Subscribe | ✗ | ✓ | ✓ | ✓ | ✗ | — |
| Cancel subscription | ✗ | — | ✓ | — | ✗ | — |
| Automated price refresh | — | — | — | — | — | ✓ |
| Permanent data deletion | — | — | — | — | — | ✓ (after 30 days) |

---

## Data Ownership Rules

1. **Portfolio-scoped isolation:** A User may only access data that is linked to their own portfolio_id. No cross-portfolio reads are permitted.
2. **Position ownership:** A User may only view, edit, or delete positions where position.portfolio_id → portfolio.user_id = authenticated user's user_id.
3. **Lot ownership:** Access controlled transitively via position_id → portfolio_id → user_id.
4. **DividendTranche ownership:** Access controlled transitively via position_id.
5. **PriceSnapshots:** Shared across portfolios (stock code–level, not user-level). Users may read any PriceSnapshot but may only create PriceSnapshots via the manual override flow.
6. **BrokerConfig (system):** Readable by all authenticated users. Not editable by users.
7. **BrokerConfig (custom):** Readable and editable only by the user who created them (created_by_user_id matches authenticated user).

## URL-level Enforcement

All resource endpoints that accept a resource ID in the URL (e.g., `/positions/{position_id}`) must validate ownership server-side on every request. Ownership check failure returns HTTP 404 (not 403) to avoid information disclosure about whether the resource exists.

---

*End of Part 2 (Sections 6–9). Continue in BursaTrack-BAS-Enhanced-Part3.md.*
