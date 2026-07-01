# BursaTrack — Business Analysis Specification
## Part 2 of 3: Sections 6–9 (Process Flows · Data Requirements · Validation Rules · Permissions)

---

# 6. PROCESS FLOWS

---

## Workflow 1: New User Registration and Onboarding

**Trigger:** User visits BursaTrack and clicks "Start Free Trial."

**Main Process Flow:**

```
User lands on registration page
↓
User enters: email, password, confirm password, default broker
↓
System validates inputs (see Validation Rules §8)
  → Validation fails: display field-level errors, stay on page
↓
System checks email uniqueness
  → Email exists: "Account already exists. Log in?"
↓
System creates User record (status: "trial", trial_expiry: today + 14 days)
↓
System creates empty Portfolio linked to User
↓
System sends email verification link
↓
User is redirected to onboarding dashboard
↓
[Parallel] User begins adding positions (can proceed without email verification)
[Parallel] User receives and clicks verification email
↓
System marks email as verified
```

**Alternative Flow — CSV Import Onboarding:**
```
User is on onboarding dashboard
↓
User clicks "Import from CSV" instead of "Add Position"
↓
User downloads the CSV template
↓
User populates template with existing portfolio data
↓
User uploads CSV
↓
System validates CSV (see FR-014)
  → Validation fails: display error report, stay on import page
↓
System creates all Position, Lot, DividendTranche records atomically
↓
User is redirected to the populated dashboard
```

**Error Flow — Email verification link expired:**
```
User clicks an expired verification link (links expire after 24 hours)
↓
System displays: "This verification link has expired. Request a new one?"
↓
User clicks "Resend"
↓
System sends a new verification email
```

**Exit States:**
- Success: Verified account with portfolio data (positions entered or CSV imported).
- Partial: Account created, email unverified, portfolio empty — user may return later.
- Abandoned: User leaves before completing registration.

---

## Workflow 2: Daily Portfolio Check (Returning User)

**Trigger:** User opens BursaTrack on a trading day morning.

**Main Process Flow:**

```
User navigates to BursaTrack URL
↓
System checks session validity
  → Session expired: redirect to login page
↓
User is on dashboard
↓
System checks price refresh status for the current trading day
  → Refresh already completed today: display current prices, show "Last updated: [time]"
  → Refresh not yet run: display previous prices with "Updating prices..." spinner
  → Refresh failed: display stale price indicator and manual entry fields (see FR-008)
↓
Dashboard renders with:
  - Portfolio summary header (total cost, total income, blended yield)
  - Position table (sorted by yield descending by default)
  - Price freshness indicators
↓
[Optional] User sorts, filters, or drills into a position
↓
[Optional] User opens sell calculator for a position
↓
[Optional] User logs a new dividend tranche
↓
User exits (session persists for 30 days of inactivity)
```

**Error Flow — Subscription expired:**
```
User logs in with an expired trial account
↓
System displays paywall screen (read-only portfolio visible)
↓
User cannot add, edit, or delete any data
↓
User must subscribe to restore full access
```

---

## Workflow 3: Add Position Manual Entry

**Trigger:** User clicks "Add Position" on the dashboard.

**Main Process Flow:**

```
User clicks "Add Position"
↓
System displays the position entry form
↓
User enters: stock code/name, shares, purchase price, purchase date
  → System auto-fills broker from user default (user can override)
  → System auto-suggests category tag "Dividend" (user can change)
↓
System validates inputs in real time (inline field validation)
↓
User submits form
↓
System performs final validation
  → Validation fails: display field-level errors
↓
System calculates: initial amount, brokerage, clearing, stamp duty, all-in cost
↓
System checks: does this stock already exist as a Position in the portfolio?
  → Yes (same stock code): system adds this as a new Lot to the existing Position
  → No: system creates a new Position and a new Lot
↓
System updates all derived position values (total shares, total cost, yield)
↓
System updates portfolio summary
↓
Dashboard refreshes with the new position/lot visible
↓
System displays confirmation: "Position added. All-in cost: RM[X]"
```

**Alternative Flow — Stock not found in Bursa listed securities:**
```
User enters stock code "99999"
↓
System cannot match to a known Bursa-listed security
↓
System displays: "Stock code '99999' not found. Check the Bursa Malaysia listed securities."
↓
User corrects the entry
```

---

## Workflow 4: Log Dividend Tranche

**Trigger:** User clicks "Add Dividend" on a position.

**Main Process Flow:**

```
User opens a position in the portfolio
↓
User clicks "Add Dividend"
↓
System displays the dividend entry form with fields:
  - Tranche label (pre-populated with next available: e.g., "2nd" if 1st already exists)
  - Dividend per share (MYR)
  - Payment date
  - Ex-dividend date (optional)
  - Year (defaults to current calendar year)
↓
System validates inputs
↓
User submits form
↓
System checks: does adding this tranche exceed the 8-per-year limit? (BR-014)
  → Limit exceeded: display error, do not create record
↓
System creates DividendTranche record with: tranche label, per-share amount, dates, year
↓
System derives: total amount = per_share × position_total_shares
↓
System recalculates position: total dividend per share, total income, yield
↓
System recalculates portfolio blended yield
↓
If ex-dividend date was entered: dividend calendar is updated
↓
Dashboard and position detail reflect updated yield immediately
```

**Alternative Flow — User enters dividend for a past year:**
```
User changes the "Year" field from 2026 to 2025
↓
System creates the tranche under year 2025
↓
System recalculates 2025 dividend income for the position
↓
Dashboard "current year" yield figure is NOT affected (2025 is a historical year)
↓
User can view 2025 dividend history in position detail
```

---

## Workflow 5: CSV Import

**Trigger:** User uploads a CSV file on the Import page.

**Main Process Flow:**

```
User navigates to Import page
↓
[Optional] User downloads CSV template
↓
User clicks "Upload File" and selects their CSV
↓
System reads the file and validates structure:
  Step 1 — File format check: is this a valid CSV? (not corrupted, not empty)
  Step 2 — Column presence check: are all required columns present? (see §8)
  Step 3 — Data type check: are all values the correct type for their column?
  Step 4 — Business rule check: do values satisfy business rules (shares > 0, price > 0, etc.)?
  Step 5 — Duplicate check: does the import create conflicting records for stocks already in portfolio?
  → Any failure: abort, return row-level error report, create NO records
↓
System displays a preview: "Ready to import: [N] positions, [M] dividend records"
User confirms import
↓
System begins atomic transaction:
  - Creates Position records for each unique stock in the import
  - Creates Lot records for each row in the positions section
  - Creates DividendTranche records for each row in the dividends section
  - Calculates all derived values (all-in cost, yield, etc.)
↓
Transaction commits successfully
↓
System redirects to dashboard with success banner
↓
[On transaction failure]: full rollback, no records created, user notified
```

**Error Flow — Import into non-empty portfolio:**
```
User already has CIMB in their portfolio
Import file also contains CIMB
↓
System detects the conflict before processing
↓
System prompts user with options for each conflicting stock:
  (a) Add as new lot(s) to existing position
  (b) Skip this stock in the import
  (c) Cancel the entire import
↓
User selects an option for each conflict
↓
Import proceeds with user's choices applied
```

---

## Workflow 6: Sell Scenario Calculator

**Trigger:** User clicks "Sell Calculator" on a position.

**Main Process Flow:**

```
User opens a position (e.g., CIMB: 5,000 shares, all-in cost RM41,996.47)
↓
User clicks "Sell Calculator"
↓
System pre-populates:
  - Stock name and code
  - Total shares (default: all shares in position)
  - All-in buy cost (total across all lots)
  - Current market price (from latest PriceSnapshot)
  - Broker (position's broker)
↓
System auto-generates price scenarios (see FR-012, Main Flow step 3)
↓
System calculates sell fees and P/L for each scenario price
↓
System highlights the break-even row
↓
System displays T+2 settlement disclosure (BR-020)
↓
[Optional] User adjusts "shares to sell" field
  → System recalculates proportional all-in cost (BR-024) and all scenarios
↓
[Optional] User adds a custom price point
  → System calculates and inserts the row in the correct sorted position
↓
Results are displayed — not saved or persisted
```

---

## Workflow 7: Subscription Management

**Trigger:** Trial expiry or user initiates subscription.

**Main Process Flow:**

```
System detects trial_expiry date has passed for an account
↓
System sets account status to "trial_expired"
↓
Next time user logs in: paywall screen is displayed
  - Portfolio visible in read-only mode
  - All add/edit/delete actions are disabled
  - CTA: "Subscribe to continue"
↓
User clicks "Subscribe"
↓
User selects plan (e.g., RM20/month)
↓
System redirects to payment processor
↓
[Success] Payment processor calls webhook: subscription confirmed
  → System sets account status to "active"
  → System records subscription_start_date, billing_period, next_renewal_date
  → User is redirected to dashboard with full access restored
↓
[Failure] Payment processor returns failure
  → System stays on subscription page
  → User sees: "Payment could not be processed. Please try again or use a different card."
```

**Cancel Subscription Flow:**
```
Subscriber clicks "Cancel Subscription" in account settings
↓
System displays: "Your subscription will end on [next_renewal_date]. Your data will be preserved in read-only mode."
↓
User confirms cancellation
↓
System schedules account status change to "trial_expired" on next_renewal_date
↓
User retains full access until next_renewal_date
↓
On next_renewal_date: status changes, account becomes read-only
```

---

# 7. DATA REQUIREMENTS

---

## Entity: User

**Description:** Represents an authenticated account holder.

### Required Fields

| Field | Description | Mandatory |
|-------|-------------|-----------|
| user_id | Unique system identifier | Yes |
| email | User's email address (unique) | Yes |
| password_hash | Bcrypt-hashed password | Yes |
| email_verified | Boolean — true after verification link is clicked | Yes |
| account_status | Enum: trial / active / trial_expired / suspended | Yes |
| trial_start_date | Date account was created | Yes |
| trial_expiry_date | trial_start_date + 14 calendar days | Yes |
| subscription_start_date | Date first subscription was activated | No (null until subscribed) |
| next_renewal_date | Date current billing period ends | No (null until subscribed) |
| default_broker_id | FK to Broker; used as default when adding new positions | Yes |
| created_at | Timestamp of account creation | Yes |
| last_login_at | Timestamp of most recent successful login | Yes |

### Relationships
- One User → One Portfolio
- One User → One default Broker (FK)

### Ownership
Source of truth: BursaTrack authentication system.

---

## Entity: Portfolio

**Description:** The container for all of a user's Bursa equity positions.

### Required Fields

| Field | Description | Mandatory |
|-------|-------------|-----------|
| portfolio_id | Unique system identifier | Yes |
| user_id | FK to owning User | Yes |
| created_at | Timestamp | Yes |
| last_price_refresh_at | Timestamp of most recent successful automated price refresh | No (null until first refresh) |
| price_refresh_status | Enum: current / stale / never_refreshed | Yes |

### Derived Values (computed at read time, not stored)

| Derived Field | Calculation |
|---------------|-------------|
| total_all_in_cost | SUM of all active Position.total_all_in_cost |
| total_dividend_income_ytd | SUM of all active Position.total_dividend_income_ytd |
| blended_yield | total_dividend_income_ytd / total_all_in_cost |

### Relationships
- One Portfolio → many Positions

### Ownership
Created automatically at user registration.

---

## Entity: Position

**Description:** A specific Bursa-listed equity held in the portfolio. A Position groups one or more Lots of the same stock.

### Required Fields

| Field | Description | Mandatory |
|-------|-------------|-----------|
| position_id | Unique system identifier | Yes |
| portfolio_id | FK to parent Portfolio | Yes |
| stock_code | Bursa stock code (e.g., "1023") | Yes |
| stock_name | Stock name (e.g., "CIMB") | Yes |
| display_name | Combined display (e.g., "CIMB 1023") | Yes |
| category_tag | Enum: Dividend / Volatile / Growth | Yes (default: Dividend) |
| is_deleted | Soft delete flag | Yes (default: false) |
| created_at | Timestamp | Yes |

### Derived Values (computed at read time)

| Derived Field | Calculation |
|---------------|-------------|
| total_shares | SUM(Lot.shares) where lot.is_deleted = false |
| total_initial_amount | SUM(Lot.initial_amount) where lot.is_deleted = false |
| total_all_in_cost | SUM(Lot.all_in_cost) where lot.is_deleted = false |
| blended_purchase_price | total_initial_amount / total_shares |
| total_dividend_income_ytd | SUM(DividendTranche.total_amount) for current year, is_deleted = false |
| total_dividend_per_share_ytd | SUM(DividendTranche.per_share_amount) for current year |
| dividend_yield | total_dividend_income_ytd / total_all_in_cost |
| current_price | Latest PriceSnapshot.price for stock_code |
| current_market_value | total_shares × current_price |
| unrealised_pnl | current_market_value − total_all_in_cost |

### Relationships
- One Position → many Lots (at least 1)
- One Position → many DividendTranches (0–8 per year)
- One Position → one current PriceSnapshot (via stock_code)

### Ownership
Created and managed by the owning User.

---

## Entity: Lot

**Description:** A single purchase transaction of a stock. Multiple Lots under a Position represent different entry points.

### Required Fields

| Field | Description | Mandatory |
|-------|-------------|-----------|
| lot_id | Unique system identifier | Yes |
| position_id | FK to parent Position | Yes |
| shares | Number of shares purchased (positive integer) | Yes |
| purchase_price | Price per share at time of purchase (MYR, positive decimal) | Yes |
| purchase_date | Date of purchase | Yes |
| broker_id | FK to Broker used for this transaction | Yes |
| initial_amount | shares × purchase_price | Yes (derived, stored) |
| brokerage_fee | Calculated per broker rules (BR-001 to BR-003) | Yes (derived, stored) |
| clearing_fee | initial_amount × 0.03% | Yes (derived, stored) |
| stamp_duty | ROUNDUP(initial_amount / 1000, 0) | Yes (derived, stored) |
| all_in_cost | initial_amount + brokerage_fee + clearing_fee + stamp_duty | Yes (derived, stored) |
| is_deleted | Soft delete flag | Yes (default: false) |
| created_at | Timestamp | Yes |

**Note on stored vs. derived:** Fee fields are stored at the time of creation to preserve historical accuracy. If fee rules change (e.g., stamp duty rate update), existing lots retain the fee that was correct at purchase time.

### Relationships
- Many Lots → One Position
- One Lot → One Broker

### Ownership
Created by the owning User; read-only after creation (edit creates a new version in audit log).

---

## Entity: Broker

**Description:** A brokerage firm and its fee structure for Bursa equity trades.

### Required Fields

| Field | Description | Mandatory |
|-------|-------------|-----------|
| broker_id | Unique system identifier | Yes |
| broker_name | Display name (e.g., "Maybank Investment") | Yes |
| fee_type | Enum: percentage / flat | Yes |
| fee_rate | Decimal (0.001 for 0.10%; ignored for flat type) | Yes for percentage; null for flat |
| minimum_fee | Minimum fee in MYR (e.g., 8.00) | Yes for percentage; null for flat |
| flat_fee | Fixed fee per trade in MYR (e.g., 3.00) | Yes for flat; null for percentage |
| is_active | Whether this broker is currently available for selection | Yes |
| is_custom | True for user-defined custom brokers | Yes |

**Pre-populated brokers at V1 launch (assumption):**

| Broker Name | Fee Type | Rate | Minimum |
|-------------|----------|------|---------|
| Maybank Investment | percentage | 0.10% | RM8 |
| Hong Leong (HLeBroking) | percentage | 0.10% | RM8 |
| MooMoo | flat | — | RM3 flat |
| Rakuten Trade | percentage | 0.10% | RM2.88* |
| M+ Online | percentage | 0.08% | RM8 |
| AM Equities | percentage | 0.05% | RM8 |
| Custom | user-defined | user-defined | user-defined |

*Rakuten Trade's tiered structure (RM2.88 flat under RM10K) is simplified to a single rate at V1. Full tiered support is deferred to V1.1.

### Relationships
- One Broker referenced by many Lots
- One Broker is the default for many Users

### Ownership
Pre-populated by system; Custom brokers created by users.

---

## Entity: DividendTranche

**Description:** A single dividend payment received for a Position. Up to 8 per Position per calendar year.

### Required Fields

| Field | Description | Mandatory |
|-------|-------------|-----------|
| tranche_id | Unique system identifier | Yes |
| position_id | FK to parent Position | Yes |
| tranche_label | Enum: 1st / 2nd / 3rd / 4th / 5th / 6th / 7th / 8th | Yes |
| per_share_amount | Dividend amount per share (MYR, positive decimal) | Yes |
| payment_date | Date dividend was / will be received | Yes |
| ex_dividend_date | Ex-dividend date (for calendar; optional) | No |
| year | Calendar year this tranche belongs to (integer, e.g., 2026) | Yes |
| is_deleted | Soft delete flag | Yes (default: false) |
| created_at | Timestamp | Yes |

### Derived Values (computed at read time)

| Derived Field | Calculation |
|---------------|-------------|
| total_amount | per_share_amount × Position.total_shares |

### Relationships
- Many DividendTranches → One Position

### Ownership
Created and managed by the owning User.

---

## Entity: PriceSnapshot

**Description:** The most recently known market price for a Bursa-listed stock.

### Required Fields

| Field | Description | Mandatory |
|-------|-------------|-----------|
| snapshot_id | Unique system identifier | Yes |
| stock_code | Bursa stock code | Yes |
| price | Market price in MYR (positive decimal) | Yes |
| source | Enum: automated / manual | Yes |
| snapshot_timestamp | Timestamp when this price was recorded | Yes |
| trading_day | The Bursa trading date this price corresponds to | Yes |
| superseded_by | FK to the snapshot that replaced this one (null if active) | No |

### Relationships
- Many PriceSnapshots per stock_code (one per trading day per source)
- Referenced by Positions via stock_code (not a FK — stock codes are a lookup)

### Ownership
Created by the automated price refresh job (automated) or by the user (manual).

---

## Entity: AuditLog

**Description:** An immutable record of every change made to Lot, DividendTranche, and PriceSnapshot records.

### Required Fields

| Field | Description | Mandatory |
|-------|-------------|-----------|
| log_id | Unique system identifier | Yes |
| entity_type | Enum: Lot / DividendTranche / PriceSnapshot | Yes |
| entity_id | ID of the changed record | Yes |
| user_id | ID of the user who made the change | Yes |
| action | Enum: created / updated / deleted | Yes |
| previous_values | JSON snapshot of the record before the change | Yes for update/delete; null for create |
| new_values | JSON snapshot of the record after the change | Yes for create/update; null for delete |
| changed_at | Timestamp | Yes |

### Relationships
- One AuditLog record per change event

### Ownership
System-generated; immutable; no user can edit or delete audit log entries.

---

## CSV Import Template: Field Specification

### Positions Sheet (required columns)

| Column Name | Description | Type | Mandatory | Example |
|-------------|-------------|------|-----------|---------|
| stock_code | Bursa stock code | String | Yes | 1023 |
| stock_name | Stock display name | String | Yes | CIMB |
| shares | Number of shares purchased | Positive integer | Yes | 5000 |
| purchase_price | Price per share at purchase (MYR) | Positive decimal | Yes | 8.38 |
| purchase_date | Date of purchase | Date (YYYY-MM-DD) | Yes | 2026-01-15 |
| broker_name | Broker name matching pre-populated list | String | Yes | Maybank Investment |
| category_tag | Portfolio category | Enum | No (default: Dividend) | Dividend |

### Dividends Sheet (optional columns — can be empty)

| Column Name | Description | Type | Mandatory | Example |
|-------------|-------------|------|-----------|---------|
| stock_code | Must match a stock_code in Positions sheet | String | Yes | 1023 |
| tranche_label | Ordinal label | Enum (1st–8th) | Yes | 1st |
| per_share_amount | Dividend per share (MYR) | Positive decimal | Yes | 0.20 |
| payment_date | Payment date | Date (YYYY-MM-DD) | Yes | 2026-03-15 |
| ex_dividend_date | Ex-dividend date | Date (YYYY-MM-DD) | No | 2026-02-28 |
| year | Calendar year | Integer (4-digit) | Yes | 2026 |

---

# 8. VALIDATION RULES

---

## Field: Email Address (Registration)

**Validation Rules:**
1. Must match standard email format (RFC 5322 basic: `local@domain.tld`)
2. Must be unique in the system
3. Maximum length: 254 characters

**Error Messages:**
- Invalid format: "Please enter a valid email address"
- Already registered: "An account with this email already exists. Log in instead?"

**Boundary Conditions:**
- 254-character email: valid
- 255-character email: invalid ("Email address is too long")

**Invalid Inputs:** `user`, `user@`, `@domain.com`, plain text with no `@`

---

## Field: Password (Registration)

**Validation Rules:**
1. Minimum 8 characters
2. Must contain at least one letter (a-z or A-Z)
3. Must contain at least one number (0-9)
4. Maximum length: 128 characters

**Error Messages:**
- Too short: "Password must be at least 8 characters"
- No letter: "Password must include at least one letter"
- No number: "Password must include at least one number"

**Special Cases:** Password field must not be logged, displayed in plain text, or included in any error response.

---

## Field: Number of Shares

**Validation Rules:**
1. Must be a positive integer (whole number greater than zero)
2. No decimals permitted
3. Maximum: 100,000,000 (100 million shares — practical upper bound)

**Error Messages:**
- Zero: "Number of shares must be greater than zero"
- Negative: "Number of shares must be greater than zero"
- Decimal (e.g., 500.5): "Number of shares must be a whole number"
- Exceeds max: "Number of shares cannot exceed 100,000,000"

---

## Field: Purchase Price (MYR)

**Validation Rules:**
1. Must be a positive decimal greater than zero
2. Maximum 4 decimal places (Malaysian shares trade in sen; 2 decimal places is standard; 4 permitted for fractional sen)
3. Maximum value: RM10,000 per share (practical upper bound for Bursa equities)

**Error Messages:**
- Zero: "Purchase price must be greater than zero"
- Negative: "Purchase price must be greater than zero"
- Exceeds max: "Purchase price cannot exceed RM10,000 per share"

---

## Field: Purchase Date

**Validation Rules:**
1. Must be a valid calendar date
2. Must not be in the future
3. Must not be before 1990-01-01 (Bursa Malaysia was established in 1990)
4. Must be a Bursa trading day (Monday–Friday; validation against a public holiday calendar is a V1.1 enhancement — at V1, weekend dates are rejected, public holidays are accepted)

**Error Messages:**
- Future date: "Purchase date cannot be in the future"
- Invalid date: "Please enter a valid date"
- Before 1990: "Purchase date must be on or after 1 Jan 1990"

---

## Field: Dividend Per Share (MYR)

**Validation Rules:**
1. Must be a positive decimal greater than zero
2. Maximum 6 decimal places (sen amounts can be fractional)
3. Maximum value: RM100 per share per tranche (practical upper bound)

**Error Messages:**
- Zero or negative: "Dividend per share must be greater than zero"
- Exceeds max: "Dividend per share cannot exceed RM100"

---

## Field: Dividend Payment Date

**Validation Rules:**
1. Must be a valid calendar date
2. Can be in the future (upcoming dividends can be pre-logged)
3. Must not be before 1990-01-01

**Error Messages:**
- Invalid date: "Please enter a valid payment date"

---

## Field: Ex-Dividend Date

**Validation Rules:**
1. Optional field — no error if blank
2. If entered: must be a valid calendar date
3. If entered: should be before the payment_date (warning if not, not blocked)

**Error Messages:**
- Invalid date: "Please enter a valid ex-dividend date"
- After payment date (warning only): "Ex-dividend date is typically before the payment date. Please verify."

---

## Field: Tranche Label

**Validation Rules:**
1. Must be one of: 1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th
2. Must not duplicate an existing tranche label for the same position and year
3. Must not exceed 8 for a given position and calendar year (BR-014)

**Error Messages:**
- Duplicate label: "A 2nd dividend tranche for [Stock Name] (2026) already exists. Edit the existing record instead."
- Exceeds 8: "Maximum of 8 dividend tranches per year reached for [Stock Name] (2026)."

---

## Field: CSV File Upload

**Validation Rules:**
1. File must have a `.csv` extension
2. File must not be empty
3. File size must not exceed 5 MB
4. File encoding must be UTF-8 or UTF-8 BOM

**Error Messages:**
- Wrong file type: "Please upload a .csv file"
- Empty file: "The uploaded file is empty"
- Too large: "File size cannot exceed 5 MB"

---

## Field: Stock Code (Position Entry)

**Validation Rules:**
1. Must be a non-empty string
2. Must match a known Bursa Malaysia stock code from the system's reference list
3. Maximum length: 10 characters

**Error Messages:**
- Not found: "Stock code '[input]' was not found in the Bursa Malaysia listed securities. Check the code and try again."

**Special Cases:** If user enters the stock name instead of the code (e.g., "CIMB" instead of "1023"), the system should attempt a name lookup and suggest the matching code.

---

## Field: Broker Selection

**Validation Rules:**
1. Must be selected from the pre-populated broker list or be a Custom broker with a defined rate
2. Cannot be blank
3. Custom broker must have a valid fee_type, fee_rate (if percentage), and minimum_fee / flat_fee

**Error Messages:**
- No selection: "Please select a broker"

---

# 9. PERMISSIONS & ACCESS CONTROL

## User Roles

At V1, BursaTrack has two roles:

| Role | Description |
|------|-------------|
| **Authenticated User (Trial)** | Has a registered account within the 14-day trial window. Full access to all features. |
| **Authenticated User (Paid)** | Has an active paid subscription. Full access to all features. |
| **Authenticated User (Expired Trial)** | Trial has ended, no active subscription. Read-only access to portfolio data. |
| **Unauthenticated Visitor** | Not logged in. Access limited to registration, login, and marketing pages only. |

---

## Allowed Actions by Role

| Action | Trial | Paid | Expired Trial | Unauthenticated |
|--------|-------|------|---------------|-----------------|
| View registration / login page | ✅ | ✅ | ✅ | ✅ |
| Register new account | ✅ | ✅ | ✅ | ✅ |
| Log in | ✅ | ✅ | ✅ | ❌ |
| View portfolio dashboard | ✅ | ✅ | ✅ (read-only) | ❌ |
| Add / edit / delete position | ✅ | ✅ | ❌ | ❌ |
| Add / edit / delete lot | ✅ | ✅ | ❌ | ❌ |
| Add / edit / delete dividend tranche | ✅ | ✅ | ❌ | ❌ |
| Import CSV | ✅ | ✅ | ❌ | ❌ |
| Use sell calculator | ✅ | ✅ | ✅ (read-only) | ❌ |
| View dividend calendar | ✅ | ✅ | ✅ (read-only) | ❌ |
| Subscribe / manage subscription | ✅ | ✅ | ✅ | ❌ |
| Cancel subscription | N/A | ✅ | N/A | ❌ |
| Export portfolio data (PDPA) | ✅ | ✅ | ✅ | ❌ |
| Delete account | ✅ | ✅ | ✅ | ❌ |

---

## Restricted Actions

- **No user can access another user's portfolio.** Portfolio data is scoped to the authenticated user_id. Attempting to access a portfolio by direct URL with another user's ID must return a 404 (not a 403, to prevent enumeration).
- **No user can modify the system Broker list.** Users can add Custom brokers for their own use only; they cannot edit or delete system-defined brokers.
- **No user can modify audit log entries.** The AuditLog is write-once and cannot be edited or deleted by any user role.
- **Expired trial users cannot write any data.** All add, edit, delete, and import actions are disabled at the application layer (not just the UI).

---

## Data Visibility Rules

- A user can only see their own portfolio, positions, lots, dividend tranches, and price overrides.
- PriceSnapshot records sourced from the automated feed are shared across all users (one record per stock per trading day). Manual price overrides are user-scoped.
- The system broker list is visible to all authenticated users. Custom brokers are visible only to their creating user.

---

## Ownership Rules

- All data created by a user (positions, lots, dividend tranches, custom brokers) is owned by that user.
- Ownership transfers do not exist at V1 (no portfolio sharing, no team accounts).
- On account deletion: all user-owned data is soft-deleted with a 30-day grace period before permanent deletion (PDPA compliance — user can request data export before deletion is finalised).

---

*End of Part 2. Continue in BursaTrack-BAS-Part3.md.*
