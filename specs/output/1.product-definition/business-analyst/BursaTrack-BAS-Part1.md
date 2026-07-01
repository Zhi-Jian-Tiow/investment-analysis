# BursaTrack — Business Analysis Specification
## Part 1 of 3: Sections 1–5 (Summary · Functional Requirements · User Stories · Acceptance Criteria · Business Rules)

> **Version:** 1.0
> **Date:** 2026-06-21
> **Analyst:** Senior Business Analyst
> **Input Document:** BursaTrack-PRD-Final.md v2.0
> **Status:** Draft — For Engineering and QA Review

---

# 1. BUSINESS ANALYSIS SUMMARY

## Overview

**Product Purpose:** BursaTrack is a web-based dividend portfolio tracker purpose-built for Malaysian retail investors on Bursa Malaysia. It automates daily price retrieval, calculates all-in transaction costs using the correct Malaysian fee stack (brokerage at the user's actual broker rate, 0.03% clearing fee, RM1/RM1,000 stamp duty), logs per-tranche dividend payments, and produces a true yield figure using all-in cost as the denominator.

**Business Context:** The product replaces a manually-maintained Excel workbook as the primary workflow tool for a dividend-income investor. The Excel model has a documented formula bug (row 28 references dividend tranche 1 instead of tranche 8 in the true-branch of an IF statement) and a yield denominator error (divides by pre-fee cost rather than all-in cost). BursaTrack must correct both issues and provide automated price retrieval to eliminate the 10–15 minute daily manual update cycle.

**Scope of This Analysis:** All ten functional requirements defined in PRD v2.0 (REQ-001 through REQ-010), plus authentication and subscription management which are implicit dependencies. This analysis covers system behaviour, business rules, process flows, data requirements, validation rules, exception handling, and edge cases. It does not cover infrastructure architecture, database schema design, API design, or UI layout.

---

## Key Observations

**Well-defined areas:**
- Malaysian fee stack is specified to implementation precision: brokerage rate per broker, clearing fee 0.03%, stamp duty ROUNDUP(amount/1000, 0) with RM1 minimum.
- Yield denominator is unambiguous: all-in cost (initial amount + brokerage + clearing + stamp duty), not pre-fee initial amount.
- Dividend tranche model is clear: up to 8 tranches per position per calendar year; per-share amount stored, total derived.
- Sell calculator logic is fully specified with a numeric break-even test case (CIMB: buy RM8.38 → break-even RM8.42).
- Row 28 bug from the Excel model is documented; product must not replicate it.

**Areas requiring clarification (carried forward from PRD):**
- Multi-lot yield calculation method: blended all-in cost as single denominator vs. per-lot yield — PRD implies blended but does not state it explicitly.
- Dividend tranche year boundary: calendar year vs. stock financial year; behaviour when a stock pays across December/January is undefined.
- Broker tiered fee handling: Rakuten Trade has a tiered structure (RM2.88 flat under RM10K, 0.10% above); PRD defers to V1.1 but the Broker entity must accommodate it.
- Trial period length and feature gating are not specified in the PRD.
- CSV import field mapping, required/optional columns, and validation rules are not defined.
- Ex-dividend date: unclear whether it is a field on DividendTranche or a separate entity.
- SST on brokerage: whether the July 2025 Bursa FAQ changes the SST exemption is unresolved.

**Potential implementation risks:**
- The yfinance price data source is unofficial. The system must be designed to degrade gracefully on outage rather than silently display stale data.
- The stamp duty rate (0.10%) is configured by law until 12 July 2028. The rate must be externally configurable without a code deployment.
- The brokerage fee minimum (RM8) applies per trade, not per share. The system must apply it per lot transaction, not per position.
- T+2 settlement: the sell calculator shows profit/loss but does not reflect the 2-trading-day delay before cash is received. A disclosure is required.

---

# 2. FUNCTIONAL REQUIREMENTS

---

## FR-001 — User Registration

**Description:** A new user creates a BursaTrack account by providing their email address, a password, and selecting their default broker. The system validates inputs, creates the account, sends an email verification link, and initiates a free trial period.

**Trigger:** User clicks "Create Account" on the registration page.

**Preconditions:**
- The email address has not been previously registered.
- The system's email delivery service is operational.
- The trial period configuration is active.

**Main Flow:**
1. User enters email address, password, and password confirmation.
2. User selects default broker from the pre-populated broker list.
3. System validates all fields (see Validation Rules, Section 8).
4. System creates the user account with status "trial."
5. System records the trial start date and calculates trial expiry date.
6. System creates an empty Portfolio associated with the new account.
7. System sends an email verification link to the provided email address.
8. System redirects the user to the onboarding dashboard with a banner: "Please verify your email. Check your inbox."
9. User clicks the email verification link.
10. System marks the email as verified and activates the account.

**Post Conditions:**
- A User record exists with status "trial," verified email, and a linked empty Portfolio.
- Trial expiry date is set to registration date + 14 days (assumption — pending stakeholder decision).
- User can immediately begin adding positions without waiting for email verification.

**User Value:** Establishes a secure, private account to hold portfolio data.

**Priority:** Must Have

---

## FR-002 — User Authentication (Login and Logout)

**Description:** A registered user authenticates with their email and password to access their portfolio. Failed attempts are rate-limited. Sessions expire after 30 days of inactivity.

**Trigger:** User submits the login form.

**Preconditions:**
- The user account exists and is not suspended.

**Main Flow:**
1. User enters email and password.
2. System checks for rate-limit lockout (see BR-016).
3. System validates credentials against the stored hashed password.
4. On success: system creates a session (HTTP-only, Secure cookie), increments the failed-attempt counter to zero, and redirects to the portfolio dashboard.
5. On failure: system increments the failed-attempt counter, returns a generic error ("Email or password is incorrect"), and if the counter reaches 5, locks the account for 10 minutes.

**Post Conditions (success):** User is authenticated; session token is active; portfolio dashboard is displayed.

**Post Conditions (failure):** Failed-attempt counter is incremented; lockout is applied if threshold reached.

**User Value:** Secure access to private portfolio data.

**Priority:** Must Have

---

## FR-003 — Add Position (Single Lot)

**Description:** An authenticated user adds a new equity position to their portfolio by specifying the stock, number of shares, purchase price, purchase date, and broker. The system calculates all-in buy cost and updates the portfolio summary.

**Trigger:** User submits the "Add Position" form.

**Preconditions:**
- User is authenticated with an active account (trial or paid).
- The stock code or name entered is a valid Bursa Malaysia listed security (see validation).

**Main Flow:**
1. User selects or enters the stock code / stock name (e.g., "CIMB 1023").
2. User enters: number of shares, purchase price per share (MYR), purchase date, broker (defaults to user's default broker).
3. User optionally selects a category tag (Dividend / Volatile / Growth; defaults to "Dividend").
4. System validates all inputs.
5. System calculates:
   - Initial purchase amount = shares × price
   - Brokerage fee = per broker rule (see BR-001 to BR-004)
   - Clearing fee = initial amount × 0.03% (see BR-005)
   - Stamp duty = ROUNDUP(initial amount / 1000, 0) (see BR-006)
   - All-in cost = initial amount + brokerage + clearing + stamp duty
6. System creates a Lot record and links it to the Position (creating a new Position if this is the first lot for this stock in the portfolio).
7. System updates the portfolio summary (total cost, blended yield).
8. System displays the new position in the dashboard with all calculated values.

**Post Conditions:**
- A Lot record exists with all fee components and all-in cost.
- A Position record exists (new or updated) with derived aggregate values.
- Portfolio summary totals are updated.

**User Value:** Accurate record of what the investor actually paid, including all transaction costs.

**Priority:** Must Have

---

## FR-004 — Add Lot to Existing Position

**Description:** A user adds a subsequent purchase lot to a position that already exists in the portfolio (e.g., they bought more CIMB shares at a different price). The system calculates the new lot's all-in cost and updates the position's blended cost basis.

**Trigger:** User clicks "Add Lot" on an existing position.

**Preconditions:**
- The position already exists in the portfolio.
- User is authenticated with an active account.

**Main Flow:**
1. User opens an existing position and clicks "Add Lot."
2. User enters: number of shares, purchase price per share, purchase date, broker (inherits position default, can be overridden).
3. System validates inputs.
4. System calculates the new lot's fees and all-in cost (same rules as FR-003).
5. System creates a new Lot record linked to the existing Position.
6. System recalculates position-level derived values:
   - Total shares = sum of all lots' share counts
   - Total all-in cost = sum of all lots' all-in costs
   - Blended purchase price = total initial amount / total shares
   - Dividend yield = total dividend income / total all-in cost (recalculated)
7. Portfolio summary totals are updated.

**Post Conditions:**
- New Lot record exists.
- Position aggregate values (total shares, total cost, blended price, yield) reflect all lots.

**User Value:** Accurate blended cost basis for positions built up over multiple purchases.

**Priority:** Must Have

---

## FR-005 — Edit Position / Lot

**Description:** A user corrects a previously entered position or lot (e.g., wrong share count, wrong price, wrong broker). The system recalculates all derived values and records the change in the audit log.

**Trigger:** User clicks "Edit" on a position or lot.

**Preconditions:**
- The position/lot exists and belongs to the authenticated user.

**Main Flow:**
1. User opens the edit form for a position or a specific lot.
2. User modifies one or more fields.
3. System validates the updated inputs.
4. System recalculates all affected derived values (fees, all-in cost, yield, portfolio totals).
5. System writes the previous values to the audit log with a timestamp.
6. System saves the updated record.
7. Dashboard reflects updated values immediately.

**Post Conditions:**
- Lot / Position record updated with new values.
- Previous values stored in audit log.
- All downstream derived values (position yield, portfolio blended yield) recalculated.

**User Value:** Ability to correct data entry errors without losing the position.

**Priority:** Must Have

---

## FR-006 — Delete Position

**Description:** A user removes a position and all its associated lots and dividend tranches from the portfolio.

**Trigger:** User clicks "Delete Position" and confirms the deletion.

**Preconditions:**
- The position belongs to the authenticated user.

**Main Flow:**
1. User clicks "Delete Position."
2. System displays a confirmation prompt: "This will delete [Stock Name] and all [N] lots and [M] dividend records. This cannot be undone."
3. User confirms.
4. System soft-deletes the Position record and all associated Lots and DividendTranches.
5. Portfolio summary totals are updated.

**Post Conditions:**
- Position, Lots, and DividendTranches are removed from the active portfolio view.
- Portfolio summary recalculated.

**Assumption:** Soft-delete is used (records are marked deleted, not physically removed) to support potential future audit or recovery features.

**User Value:** Keeps the portfolio accurate when a position is closed or entered in error.

**Priority:** Must Have

---

## FR-007 — Automated Daily Price Refresh

**Description:** On each Bursa Malaysia trading day, the system automatically retrieves the latest market price for every stock held across all active portfolios and updates the PriceSnapshot records. If the price feed is unavailable, the system surfaces a data-quality warning to affected users and does not display the previous price as current.

**Trigger:** Scheduled job fires on each Bursa Malaysia trading day (Monday–Friday, excluding public holidays).

**Preconditions:**
- At least one portfolio has active positions.
- The price data provider is reachable.

**Main Flow:**
1. Scheduled job collects the list of unique stock codes across all active portfolios.
2. System queries the price data provider for each stock code.
3. For each successful response: system creates or updates a PriceSnapshot record (stock code, price, source = "automated," timestamp, trading day).
4. System marks the portfolio's price refresh status as "current" with the refresh timestamp.
5. Dashboard price column updates to reflect the new prices.

**Post Conditions:**
- PriceSnapshot records for all actively held stocks reflect the trading day's price.
- Portfolio's "last refreshed" timestamp is updated.
- Unrealised P&L values on the dashboard are recalculated.

**User Value:** Eliminates 10–15 minutes of daily manual price entry.

**Priority:** Must Have

---

## FR-008 — Price Data Outage Handling

**Description:** When the automated price refresh fails for one or more stocks, the system detects the failure within 5 minutes, surfaces a clear status warning to the user, and enables manual price override per position.

**Trigger:** Price refresh job fails to obtain a valid price for one or more stocks.

**Preconditions:** The automated refresh has been attempted and returned an error or no data for at least one stock.

**Main Flow:**
1. Refresh job records a failed fetch for one or more stock codes.
2. System marks the affected PriceSnapshot records with source = "stale."
3. Within 5 minutes of the failure, the dashboard surfaces a status banner: "Price data unavailable for [N] stocks — showing prices as of [last successful timestamp]. Update prices manually below."
4. Each affected position displays a "stale" indicator and a manual price entry field.
5. User enters a price manually for one or more positions.
6. System creates a PriceSnapshot record with source = "manual" and the current timestamp.
7. Position calculations update immediately using the manual price.
8. On the next successful automated refresh, the manual override is superseded.

**Post Conditions:**
- Stale prices are visually distinguished from current prices.
- Manual override prices are stored and applied until superseded.
- No position displays a stale price as if it were current.

**User Value:** Users can continue working with accurate data even when the automated feed fails.

**Priority:** Must Have

---

## FR-009 — Log Dividend Tranche

**Description:** A user records an individual dividend payment received for a position. The system stores the per-share amount, derives the total received, and recalculates the position's yield and the portfolio's blended yield.

**Trigger:** User submits the "Add Dividend" form for a position.

**Preconditions:**
- The position exists and belongs to the authenticated user.
- The position has fewer than 8 logged dividend tranches for the relevant calendar year.

**Main Flow:**
1. User opens the dividend section of a position.
2. User selects the tranche label (1st–8th; system suggests the next available label).
3. User enters: dividend per share (MYR), payment date, ex-dividend date (optional).
4. System validates inputs.
5. System derives: total dividend amount = dividend per share × total shares (sum of all lots).
6. System creates a DividendTranche record.
7. System recalculates:
   - Position total dividend per share = sum of all tranches' per-share amounts for the year.
   - Position total dividend income = sum of all tranches' total amounts for the year.
   - Position yield = total dividend income / total all-in cost.
   - Portfolio blended yield = sum of all positions' dividend income / sum of all positions' all-in cost.
8. Dashboard and position detail update immediately.

**Post Conditions:**
- DividendTranche record exists.
- Position and portfolio yield figures updated.
- Dividend calendar updated if ex-dividend date was entered.

**User Value:** Accurate, per-tranche dividend record that drives the true yield calculation.

**Priority:** Must Have

---

## FR-010 — Edit / Delete Dividend Tranche

**Description:** A user corrects or removes a previously logged dividend tranche. All downstream yield calculations recalculate immediately. The change is recorded in the audit log.

**Trigger:** User clicks "Edit" or "Delete" on a dividend tranche record.

**Preconditions:** The tranche belongs to the authenticated user's position.

**Main Flow (Edit):**
1. User opens the edit form for the tranche.
2. User modifies the dividend per share, payment date, or ex-dividend date.
3. System validates updated values.
4. System writes previous values to audit log.
5. System saves the update and recalculates position and portfolio yield.

**Main Flow (Delete):**
1. User clicks "Delete."
2. System displays: "Delete this dividend record? This cannot be undone."
3. User confirms.
4. System soft-deletes the tranche record.
5. System recalculates position and portfolio yield with the tranche removed.

**Post Conditions:**
- Tranche updated or removed.
- Position and portfolio yield recalculated.
- Audit log records the change.

**Priority:** Must Have

---

## FR-011 — Portfolio Dashboard

**Description:** The authenticated user's primary view. Displays portfolio summary metrics and a per-position breakdown. Supports sorting by yield. All values derived in real time from stored position, lot, dividend, and price data. Loads within 3 seconds.

**Trigger:** User navigates to the dashboard (home screen after login).

**Preconditions:** User is authenticated with an active account (trial or paid).

**Main Flow:**
1. System retrieves all positions, lots, dividend tranches, and current price snapshots for the user's portfolio.
2. System calculates and renders the summary header:
   - Total portfolio all-in cost
   - Total annual dividend income (current calendar year)
   - Portfolio blended yield (%)
   - Last price refresh timestamp
3. System renders the position table with per-position columns:
   - Stock name and code
   - Category tag
   - Total shares
   - Blended purchase price
   - Total all-in cost
   - Current price (with stale indicator if applicable)
   - Current market value
   - Unrealised P&L (current market value − total all-in cost)
   - Total dividend income (current year)
   - Dividend yield (%)
4. Default sort: by dividend yield descending.
5. User can re-sort by any column.

**Post Conditions:** Dashboard is rendered with all current values; sort preference saved to user session.

**Priority:** Must Have

---

## FR-012 — Sell Scenario Calculator

**Description:** For any position in the portfolio, the user can model the net proceeds and profit/loss from selling at one or more target prices. The calculator uses the position's actual broker fee rate for the sell-side fees and compares net proceeds against the position's all-in buy cost.

**Trigger:** User opens the sell calculator for a specific position.

**Preconditions:**
- The position exists in the user's portfolio with at least one lot.
- The position has a valid all-in buy cost.

**Main Flow:**
1. User opens the sell calculator for a position (e.g., CIMB with 5,000 shares, all-in cost RM41,996.47).
2. System pre-populates: stock name, total shares, all-in buy cost, current price.
3. System auto-generates price scenarios at the following increments above the current price:
   - +0.01, +0.02, +0.03, +0.04, +0.05 (fine-grained near current price)
   - +0.10, +0.15, +0.20 … +0.70 (broad view in 0.05 steps)
4. For each scenario price, the system calculates:
   - Gross sell proceeds = scenario price × total shares
   - Sell brokerage fee = per broker rule on gross proceeds (same rules as buy-side, BR-001 to BR-004)
   - Sell clearing fee = gross proceeds × 0.03%
   - Sell stamp duty = ROUNDUP(gross proceeds / 1000, 0)
   - Net sell proceeds = gross proceeds − (sell brokerage + sell clearing + sell stamp duty)
   - Profit/Loss = net sell proceeds − all-in buy cost
5. System highlights the break-even row (lowest scenario price where profit/loss ≥ 0).
6. System displays a disclosure: "Calculations are informational only. Settlement occurs T+2 (two trading days after sale)."
7. User can enter a custom sell price not in the auto-generated list.
8. User can adjust the number of shares to sell (partial sale simulation).

**Post Conditions:** Calculator results displayed; not persisted.

**User Value:** Eliminates the manual sell scenario spreadsheet; linked to live position data.

**Priority:** Must Have

---

## FR-013 — Dividend Calendar

**Description:** A calendar or chronological list view that displays upcoming ex-dividend dates and expected payment dates for all stocks held in the portfolio. Data is sourced from ex-dates and payment dates entered by the user when logging dividend tranches.

**Trigger:** User navigates to the Dividend Calendar tab.

**Preconditions:** User is authenticated.

**Main Flow:**
1. System retrieves all DividendTranche records for the user's portfolio where ex-dividend date or payment date is in the future (or within the past 30 days).
2. System renders entries in ascending chronological order by ex-dividend date (if present) or payment date.
3. Each entry shows: stock name, tranche label, ex-dividend date, payment date, dividend per share, estimated total payment.
4. Dates that have passed are displayed with a "Paid" badge.
5. Upcoming dates within the next 7 days are highlighted.
6. If no dates are recorded, the system displays: "Add ex-dates when logging dividends to see your payment schedule here."

**Post Conditions:** Calendar view rendered from stored dividend data.

**Priority:** Should Have (V1)

---

## FR-014 — CSV Import

**Description:** A user imports their portfolio positions and optionally their dividend history from a CSV file, using the BursaTrack-provided template. The system validates the file, reports errors with row-level detail, and on a clean import creates all positions, lots, and dividend tranche records. Import is atomic — either all records are created or none.

**Trigger:** User uploads a CSV file on the Import page.

**Preconditions:**
- User is authenticated with an active account.
- User has either an empty portfolio or has chosen to merge with existing data (see edge cases).

**Main Flow:**
1. User downloads the CSV template from the Import page.
2. User populates the template with their portfolio data.
3. User uploads the completed CSV file.
4. System validates the file format, column presence, and row-level data (see Validation Rules, Section 8).
5. If validation passes: system creates all Position, Lot, and DividendTranche records in a single atomic transaction.
6. System redirects the user to the dashboard with a success message: "Import complete — [N] positions and [M] dividend records imported."
7. If validation fails: system displays a row-level error report. No records are created. User can correct the file and re-upload.

**Post Conditions (success):**
- All records created.
- Dashboard populated with imported data.
- All yield calculations computed from imported data.

**Post Conditions (failure):**
- No records created.
- User receives actionable error messages.

**Priority:** Must Have

---

## FR-015 — CSV Template Download

**Description:** The user downloads a pre-formatted CSV template with column headers, a guide row, and one example row. The template defines the exact field names and formats required for a successful import.

**Trigger:** User clicks "Download Template" on the Import page.

**Preconditions:** User is authenticated.

**Main Flow:**
1. System serves a CSV file containing:
   - Row 1: Column headers (defined in Data Requirements, Section 7)
   - Row 2: Column guide (description of each field in the header row)
   - Row 3: Example data row
2. File downloads with the name `BursaTrack_Import_Template.csv`.

**Post Conditions:** Template file is available for download.

**Priority:** Must Have

---

## FR-016 — Subscription Management

**Description:** At the end of the trial period, the user is prompted to subscribe. A paying subscriber has unlimited access. An expired trial user can view their portfolio (read-only) but cannot add or edit data until they subscribe. A subscriber can cancel at any time; access continues until the end of the billing period.

**Trigger:** Trial expiry date passes; or user clicks "Subscribe."

**Preconditions:** User account exists.

**Main Flow (trial expiry):**
1. On the day the trial expires, the system marks the account as "trial_expired."
2. On next login, the system displays a paywall screen: "Your 14-day trial has ended. Subscribe to continue."
3. The user's portfolio data is preserved and visible in read-only mode.
4. User cannot add, edit, or delete positions or dividends until they subscribe.

**Main Flow (subscribe):**
1. User selects a subscription plan.
2. User is redirected to the payment processor.
3. On payment success: account status changes to "active," access is restored.
4. System stores the subscription start date, billing period, and next renewal date.

**Main Flow (cancel):**
1. User clicks "Cancel Subscription."
2. System confirms: "Your subscription will end on [date]. Your portfolio data will be preserved."
3. User confirms.
4. Account is scheduled to become "trial_expired" at the end of the current billing period.
5. User retains full access until that date.

**Post Conditions:**
- Account status reflects current subscription state.
- Portfolio data preserved through all state transitions.

**Priority:** Must Have

---

# 3. USER STORIES

| Story ID | Description | Linked FR | Priority |
|----------|-------------|-----------|----------|
| US-001 | As a new investor, I want to register with my email and default broker, so that I can start a free trial and set up my portfolio | FR-001 | Must Have |
| US-002 | As a registered user, I want to log in securely, so that only I can access my portfolio data | FR-002 | Must Have |
| US-003 | As Ahmad, I want to add a stock position with my purchase price, share count, and broker, so that the system calculates my true all-in cost including all fees | FR-003 | Must Have |
| US-004 | As David, I want to add multiple lots to the same stock position at different prices, so that I have an accurate blended cost basis | FR-004 | Must Have |
| US-005 | As Farah, I want to edit a position I entered incorrectly, so that my portfolio always reflects my actual holdings | FR-005 | Must Have |
| US-006 | As any user, I want to delete a position I no longer hold, so that my portfolio stays accurate | FR-006 | Must Have |
| US-007 | As Ahmad, I want prices to refresh automatically on trading days, so that I don't spend 10–15 minutes updating prices manually | FR-007 | Must Have |
| US-008 | As any user, I want to see a clear warning when price data is unavailable, so that I don't make decisions based on stale data | FR-008 | Must Have |
| US-009 | As any user, I want to enter prices manually when the automated feed fails, so that I can continue using the portfolio even during outages | FR-008 | Must Have |
| US-010 | As Ahmad, I want to log individual dividend payment tranches (1st, 2nd, 3rd) separately, so that I have an accurate record of when each payment was received | FR-009 | Must Have |
| US-011 | As David, I want the total dividend yield calculated using my all-in cost as the denominator, so that my ROI figure is accurate and not overstated | FR-009 | Must Have |
| US-012 | As any user, I want to edit a dividend tranche I entered incorrectly, so that my income figures are correct | FR-010 | Must Have |
| US-013 | As any user, I want to see all my positions in a single dashboard with yield, income, and current value, so that I can assess my portfolio in under 5 minutes | FR-011 | Must Have |
| US-014 | As David, I want to sort positions by yield, so that I can identify my highest-returning holdings at a glance | FR-011 | Must Have |
| US-015 | As David, I want to model a sell at multiple price points and see net proceeds after all fees, so that I know my break-even and profit before executing a trade | FR-012 | Must Have |
| US-016 | As Farah, I want the sell calculator to highlight the break-even price, so that I know my floor before deciding to sell | FR-012 | Must Have |
| US-017 | As Ahmad, I want to see upcoming ex-dividend dates for all my holdings in order, so that I never miss an ex-date | FR-013 | Should Have |
| US-018 | As Ahmad, I want to import my 16-position portfolio from a CSV file, so that I don't spend 45 minutes on manual data entry | FR-014 | Must Have |
| US-019 | As any user, I want a CSV template to download, so that I know the exact format required for import | FR-015 | Must Have |
| US-020 | As any user on trial expiry, I want to subscribe to continue managing my portfolio, so that I don't lose access to my data | FR-016 | Must Have |

---

# 4. ACCEPTANCE CRITERIA

## US-001 / FR-001 — Registration

**Happy Path**
```gherkin
Given I am on the registration page
When I enter a valid email "ahmad@email.com", password "Invest2026", confirm password "Invest2026", and select broker "Maybank Investment"
Then my account is created with status "trial"
And the trial expiry date is set to 14 days from today
And an empty Portfolio is created and linked to my account
And I am redirected to the onboarding dashboard
And I see a banner: "Please verify your email. Check your inbox."
And I receive a verification email at "ahmad@email.com"
```

**Alternate: email already registered**
```gherkin
Given the email "ahmad@email.com" is already registered
When I attempt to register with "ahmad@email.com"
Then I see the error: "An account with this email already exists. Log in instead?"
And no new account is created
```

**Error: password mismatch**
```gherkin
Given I enter password "Invest2026" and confirm password "invest2026"
When I submit the registration form
Then I see the error: "Passwords do not match"
And no account is created
```

**Error: invalid email format**
```gherkin
Given I enter email "not-an-email"
When I submit the registration form
Then I see the error: "Please enter a valid email address"
```

---

## US-002 / FR-002 — Login

**Happy Path**
```gherkin
Given I have a verified account with email "ahmad@email.com" and password "Invest2026"
When I enter correct credentials and click "Log In"
Then I am redirected to my portfolio dashboard
And a secure session is established
```

**Error: wrong password (below lockout threshold)**
```gherkin
Given I have entered the wrong password 3 times
When I enter the wrong password a 4th time
Then I see: "Email or password is incorrect" (generic message)
And the failed attempt counter increments to 4
```

**Error: account locked**
```gherkin
Given I have failed login 5 times in the last 10 minutes
When I attempt to log in again
Then I see: "Too many failed attempts. Please wait 10 minutes before trying again."
And the login form is disabled
```

**Permission: unverified email**
```gherkin
Given my email has not been verified
When I log in
Then I am taken to the dashboard but see a persistent banner: "Please verify your email to ensure you don't lose access."
And I retain full access during the trial period
```

---

## US-003 / FR-003 — Add Position

**Happy Path**
```gherkin
Given I am logged in with broker "Maybank Investment" (0.10%, min RM8)
When I add stock "CIMB 1023", 5000 shares, price RM8.38, date 2026-01-15, broker "Maybank Investment"
Then the position appears in my portfolio
And initial amount = RM41,900.00
And brokerage fee = RM41.90
And clearing fee = RM12.57
And stamp duty = RM42.00
And all-in cost = RM41,996.47
```

**Alternate: MooMoo flat-fee broker**
```gherkin
Given I select broker "MooMoo" (RM3 flat)
When I add stock "CIMB 1023", 5000 shares, price RM8.38
Then brokerage fee = RM3.00
And all-in cost = RM41,957.57 (RM41,900 + RM3.00 + RM12.57 + RM42.00)
```

**Alternate: brokerage minimum applies**
```gherkin
Given I select broker "Maybank Investment" (0.10%, min RM8)
When I add stock "FM 7210", 5000 shares, price RM0.60
Then initial amount = RM3,000.00
And 0.10% of RM3,000 = RM3.00, which is below the RM8 minimum
And brokerage fee = RM8.00
And clearing fee = RM0.90
And stamp duty = RM3.00
And all-in cost = RM3,011.90
```

**Error: share count zero or negative**
```gherkin
Given I enter share count "0"
When I submit the form
Then I see: "Number of shares must be greater than zero"
```

**Error: price zero or negative**
```gherkin
Given I enter purchase price "0"
When I submit the form
Then I see: "Purchase price must be greater than zero"
```

---

## US-004 / FR-004 — Add Lot to Existing Position

**Happy Path**
```gherkin
Given I have an existing CIMB position with 5,000 shares at RM8.38 (all-in RM41,996.47)
When I add a second lot: 2,000 shares at RM9.00, broker "Maybank Investment"
Then the CIMB position shows total shares = 7,000
And total initial amount = RM41,900 + RM18,000 = RM59,900
And second lot all-in cost = RM18,000 + RM18.00 + RM5.40 + RM18.00 = RM18,041.40
And position total all-in cost = RM41,996.47 + RM18,041.40 = RM60,037.87
And blended purchase price = RM59,900 / 7,000 = RM8.557 (approx.)
```

---

## US-007 / FR-007 — Automated Price Refresh

**Happy Path**
```gherkin
Given it is a Bursa Malaysia trading day and the price feed is available
When the scheduled price refresh job runs
Then PriceSnapshot records are created/updated for all stocks in active portfolios
And each position on the dashboard shows the latest price with "Last updated: [timestamp]"
And unrealised P&L is recalculated for all positions
```

**Alternate: weekend / public holiday**
```gherkin
Given today is a Saturday or Malaysian public holiday
When the scheduled time for price refresh arrives
Then the job does not run
And no PriceSnapshot records are created
And the dashboard shows the most recent trading day's prices
And the "Last updated" timestamp reflects the last trading day
```

---

## US-008–009 / FR-008 — Price Data Outage

**Error: complete feed failure**
```gherkin
Given the price data provider is unavailable
When the scheduled refresh job runs
Then no PriceSnapshot records are updated
And within 5 minutes, the dashboard displays: "Price data unavailable — showing prices as of [last timestamp]. Update prices manually below."
And each affected position shows a stale price indicator
And a manual price entry field appears for each position
```

**Alternate: partial failure (some stocks fail)**
```gherkin
Given the feed returns prices for 14 of 16 stocks but fails for CARLSBG and LPI
When the refresh job runs
Then CARLSBG and LPI show stale indicators and manual entry fields
And the remaining 14 positions display updated prices normally
And the status banner reads: "Price data unavailable for 2 stocks — CARLSBG, LPI"
```

**Happy Path: manual override superseded**
```gherkin
Given I entered a manual price of RM8.50 for CIMB during an outage
When the next automated refresh succeeds and returns RM8.42 for CIMB
Then the CIMB price updates to RM8.42
And the stale indicator and manual flag are removed
And the "Manual" label is replaced by "Last updated: [refresh timestamp]"
```

---

## US-010 / FR-009 — Log Dividend Tranche

**Happy Path**
```gherkin
Given I have a CIMB position with 5,000 shares and no dividends logged yet
When I log: 1st tranche, RM0.20/share, payment date 2026-03-15, ex-date 2026-02-28
Then a DividendTranche record is created
And total dividend per share = RM0.20
And total dividend income = RM1,000.00 (5,000 × RM0.20)
And position yield = RM1,000.00 / RM41,996.47 = 2.38%
And the dividend calendar shows ex-date 28 Feb 2026 and payment 15 Mar 2026
```

**Alternate: second tranche**
```gherkin
Given CIMB already has a 1st tranche of RM0.20/share
When I log: 2nd tranche, RM0.1975/share, payment date 2026-06-20
Then total dividend per share = RM0.3975
And total dividend income = RM1,987.50
And position yield = RM1,987.50 / RM41,996.47 = 4.73%
```

**Error: exceeds 8 tranches**
```gherkin
Given CIMB already has 8 dividend tranches logged for calendar year 2026
When I attempt to add a 9th tranche for 2026
Then I see: "Maximum of 8 dividend tranches per year reached for CIMB (2026). Start a new year or edit an existing tranche."
And no record is created
```

**Error: dividend per share is zero or negative**
```gherkin
Given I enter dividend per share as "0"
When I submit the form
Then I see: "Dividend per share must be greater than zero"
```

---

## US-011 / FR-009 — Yield Denominator Correctness

**Happy Path**
```gherkin
Given CIMB has total dividend income RM2,337.50 and all-in cost RM41,996.47
When the system calculates yield
Then yield = RM2,337.50 / RM41,996.47 = 5.5660...% displayed as 5.57%
And yield is NOT calculated as RM2,337.50 / RM41,900 = 5.5789...% (pre-fee cost)
```

---

## US-015–016 / FR-012 — Sell Calculator

**Happy Path**
```gherkin
Given CIMB position: 5,000 shares, all-in buy cost RM41,996.47, broker "Maybank Investment"
When I open the sell calculator
Then the system generates scenarios at RM8.39, RM8.40, RM8.41, RM8.42, RM8.43 (and further steps)
And at RM8.39: gross = RM41,950; sell broker fee = RM41.95; clearing = RM12.585; stamp = RM42; net = RM41,853.47; P/L = -RM143.00
And at RM8.42: net proceeds ≈ RM42,002.27; P/L ≈ +RM5.80
And the RM8.42 row is highlighted as "Break-even"
And a disclosure is visible: "Calculations are informational only. Settlement T+2."
```

**Alternate: MooMoo broker (flat RM3 sell fee)**
```gherkin
Given my CIMB position uses broker "MooMoo" (RM3 flat)
When I open the sell calculator
Then sell brokerage fee = RM3.00 for all price scenarios (not 0.10% of proceeds)
```

**Alternate: partial sale**
```gherkin
Given I have 5,000 CIMB shares
When I change the "shares to sell" field to 2,000
Then all scenario calculations use 2,000 shares
And all-in buy cost used for P/L = proportional cost of 2,000 shares = (2,000/5,000) × RM41,996.47 = RM16,798.59
```

---

## US-018 / FR-014 — CSV Import

**Happy Path**
```gherkin
Given I have a correctly formatted CSV file with 16 positions and 34 dividend tranche records
When I upload the file
Then all 16 positions are created with correct share counts, prices, brokers, and all-in costs
And all 34 dividend tranches are created with correct per-share amounts and dates
And the dashboard displays the full portfolio with calculated yields
And a success banner reads: "Import complete — 16 positions and 34 dividend records imported"
And the import completes within 30 seconds
```

**Error: missing required column**
```gherkin
Given I upload a CSV where the "purchase_price" column header is missing
When the system validates the file
Then I see: "Import failed: Required column 'purchase_price' is missing. No records were imported."
And my existing portfolio is unchanged
```

**Error: invalid data in a row**
```gherkin
Given row 7 has share count "abc" (non-numeric)
When the system validates the file
Then I see: "Import failed: Row 7 — 'shares' must be a positive whole number. Found: 'abc'. No records were imported."
And I can download an error report
```

**Error: duplicate position on import into non-empty portfolio**
```gherkin
Given I already have a CIMB position in my portfolio
And my import file also contains a CIMB position
When I upload the file
Then the system prompts: "CIMB 1023 already exists in your portfolio. Choose: (a) Add as a new lot, (b) Skip, (c) Cancel import"
```

---

## US-020 / FR-016 — Subscription

**Happy Path**
```gherkin
Given my 14-day trial has expired
When I log in
Then I see the paywall screen with a subscribe CTA
And my portfolio data is visible in read-only mode
And I cannot add, edit, or delete positions or dividends
```

**Happy Path: subscribe**
```gherkin
Given I am on the paywall screen
When I click "Subscribe", complete payment, and return to the app
Then my account status changes to "active"
And I have full access to all features
And a receipt confirmation is displayed
```

**Happy Path: cancel**
```gherkin
Given I am a paying subscriber with renewal on 2026-08-01
When I cancel my subscription on 2026-07-15
Then I see: "Your subscription ends on 1 Aug 2026. Your data will be preserved."
And I retain full access until 2026-08-01
And on 2026-08-02 my account becomes read-only (trial_expired)
```

---

# 5. BUSINESS RULES

---

## BR-001 — Percentage-Based Brokerage Fee

**Rule Name:** Percentage Brokerage Calculation

**Description:** For brokers with a percentage-based fee, brokerage = MAX(initial_amount × rate, minimum_fee). The fee is calculated on the initial purchase amount (shares × price), not on the all-in cost.

**Rule Type:** Calculation Rule

**Example:**
- Broker: Maybank Investment (0.10%, min RM8)
- Initial amount: RM41,900
- 0.10% of RM41,900 = RM41.90 → RM41.90 > RM8 → brokerage = RM41.90
- Initial amount: RM3,000 → 0.10% = RM3.00 → RM3.00 < RM8 → brokerage = RM8.00

---

## BR-002 — Flat-Fee Brokerage

**Rule Name:** Flat Brokerage Calculation

**Description:** For brokers with a flat fee per trade, brokerage = flat_fee regardless of trade size. No minimum applies because the flat fee is itself the minimum and maximum.

**Rule Type:** Calculation Rule

**Example:**
- Broker: MooMoo (RM3 flat)
- Trade size: any amount
- Brokerage = RM3.00

---

## BR-003 — Brokerage Applied Per Lot

**Rule Name:** Brokerage is Per Transaction

**Description:** The brokerage fee is applied once per lot transaction (one purchase). If a user buys CIMB on three separate dates, brokerage is charged three times — once per lot.

**Rule Type:** Calculation Rule

**Example:**
- Lot 1: 5,000 shares at RM8.38 → brokerage on RM41,900
- Lot 2: 2,000 shares at RM9.00 → brokerage on RM18,000
- Total brokerage ≠ brokerage on combined RM59,900

---

## BR-004 — Sell-Side Brokerage

**Rule Name:** Sell Brokerage Uses Same Rules as Buy

**Description:** The sell calculator applies the same brokerage rules (same broker, same rate, same minimum) to the gross sell proceeds. Brokerage fee on sale = MAX(gross_proceeds × rate, minimum) for percentage brokers; flat_fee for flat-fee brokers.

**Rule Type:** Calculation Rule

**Example:**
- Sell price: RM8.42, shares: 5,000 → gross proceeds: RM42,100
- Broker: Maybank (0.10%, min RM8) → sell brokerage = RM42.10

---

## BR-005 — Clearing Fee

**Rule Name:** Clearing Fee Calculation

**Description:** Clearing fee = initial_amount × 0.03% on BUY, or gross_proceeds × 0.03% on SELL. No minimum. No cap applies for the position sizes in scope (the RM1,000 regulatory cap is not relevant below RM3.33M per transaction).

**Rule Type:** Calculation Rule

**Example:**
- Initial amount: RM41,900 → clearing fee = RM41,900 × 0.0003 = RM12.57

---

## BR-006 — Stamp Duty

**Rule Name:** Stamp Duty Calculation

**Description:** Stamp duty = ROUNDUP(initial_amount / 1000, 0) on BUY, or ROUNDUP(gross_proceeds / 1000, 0) on SELL. Minimum RM1 (enforced by the ROUNDUP formula for any positive amount ≥ RM1). Rate is 0.10% (RM1 per RM1,000), gazetted until 12 July 2028.

**Rule Type:** Calculation Rule

**Example:**
- Initial amount: RM41,900 → ROUNDUP(41.9, 0) = 42 → stamp duty = RM42.00
- Initial amount: RM3,000 → ROUNDUP(3.0, 0) = 3 → stamp duty = RM3.00
- Initial amount: RM500 → ROUNDUP(0.5, 0) = 1 → stamp duty = RM1.00

---

## BR-007 — All-In Cost Composition

**Rule Name:** All-In Cost Definition

**Description:** All-in cost per lot = initial_amount + brokerage_fee + clearing_fee + stamp_duty. This is the true cost of acquiring the lot and is the correct basis for yield calculation.

**Rule Type:** Calculation Rule

**Example:**
- CIMB: RM41,900 + RM41.90 + RM12.57 + RM42.00 = RM41,996.47

---

## BR-008 — Yield Denominator

**Rule Name:** Yield Uses All-In Cost

**Description:** Dividend yield = total_dividend_income / total_all_in_cost. The denominator must be the all-in cost (BR-007), not the pre-fee initial amount. Using the pre-fee amount overstates yield.

**Rule Type:** Calculation Rule

**Example:**
- CIMB: RM2,337.50 / RM41,996.47 = 5.57% (correct)
- NOT: RM2,337.50 / RM41,900 = 5.58% (incorrect — pre-fee denominator)

---

## BR-009 — Dividend Per Share Stored, Total Derived

**Rule Name:** Store Per-Share, Derive Total

**Description:** The system stores dividend_per_share on each DividendTranche record. The total dividend amount for a tranche is derived at read time: total = dividend_per_share × position_total_shares. This prevents stale totals if the share count is edited, and is the correct design that avoids the row 28 formula class of bug.

**Rule Type:** Calculation Rule

**Example:**
- Tranche: RM0.20/share, position: 5,000 shares → derived total = RM1,000
- If share count is later corrected to 4,000 → derived total auto-corrects to RM800

---

## BR-010 — Position Total Shares

**Rule Name:** Total Shares Is Sum of All Lots

**Description:** position_total_shares = SUM(shares) across all non-deleted lots for that position.

**Rule Type:** Calculation Rule

**Example:**
- Lot 1: 5,000 shares; Lot 2: 2,000 shares → position total = 7,000 shares

---

## BR-011 — Position All-In Cost

**Rule Name:** Position All-In Cost Is Sum of All Lots

**Description:** position_total_all_in_cost = SUM(all_in_cost) across all non-deleted lots for that position.

**Rule Type:** Calculation Rule

---

## BR-012 — Position Dividend Income

**Rule Name:** Position Dividend Income Is Sum of All Tranches (Current Year)

**Description:** position_total_dividend_income = SUM(dividend_per_share × position_total_shares) across all non-deleted DividendTranche records for the position in the current calendar year.

**Rule Type:** Calculation Rule

**Assumption:** "Current year" means the calendar year of the dashboard view date (January 1 – December 31). Tranches from prior years are visible in history but excluded from the current yield calculation. This assumption requires stakeholder confirmation.

---

## BR-013 — Portfolio Blended Yield

**Rule Name:** Portfolio Yield Is Aggregate Income / Aggregate Cost

**Description:** portfolio_blended_yield = SUM(all positions' dividend_income) / SUM(all positions' all_in_cost). This is a portfolio-weighted average yield, not an arithmetic average of individual position yields.

**Rule Type:** Calculation Rule

**Example:**
- CIMB: income RM2,337.50, cost RM41,996.47
- MAYBANK: income RM3,100, cost RM59,837.61
- Blended yield = (RM2,337.50 + RM3,100) / (RM41,996.47 + RM59,837.61) = 5.34%

---

## BR-014 — Dividend Tranche Limit

**Rule Name:** Maximum 8 Dividend Tranches Per Position Per Calendar Year

**Description:** A position may have at most 8 DividendTranche records with the same calendar year value. Attempting to add a 9th is blocked with an error message.

**Rule Type:** Validation Rule

---

## BR-015 — Stamp Duty Rate Configurability

**Rule Name:** Stamp Duty Rate Is Externally Configurable

**Description:** The stamp duty rate (currently RM1/RM1,000, i.e., 0.10%) must be stored in a configurable system setting, not hard-coded. This allows the rate to be updated without a code deployment when the gazette changes (next review date: 12 July 2028).

**Rule Type:** Compliance Rule

---

## BR-016 — Login Rate Limiting

**Rule Name:** Account Lockout After 5 Failed Login Attempts

**Description:** If a user fails to authenticate 5 times within a 10-minute window from the same IP address, the account is locked for 10 minutes. The error message is generic: "Too many failed attempts. Please wait 10 minutes before trying again." The counter resets on successful login.

**Rule Type:** Permission Rule / Compliance Rule

---

## BR-017 — Trial Period Duration

**Rule Name:** Free Trial Is 14 Calendar Days

**Description:** The trial period begins at the moment of account creation and expires exactly 14 calendar days later (at midnight MYT on day 14). During the trial, all features are accessible. After expiry, the account is read-only until a subscription is activated.

**Rule Type:** Workflow Rule

**Assumption:** 14-day duration is assumed pending stakeholder decision. This must be confirmed before registration is built.

---

## BR-018 — Portfolio Data Preservation

**Rule Name:** Portfolio Data Persists Through All Account State Changes

**Description:** Portfolio data (positions, lots, dividend tranches) is never deleted due to trial expiry or subscription cancellation. Data is preserved in read-only state until explicitly deleted by the user.

**Rule Type:** Workflow Rule

---

## BR-019 — Session Expiry

**Rule Name:** Sessions Expire After 30 Days of Inactivity

**Description:** A user session expires if no authenticated request is made within 30 consecutive calendar days. On session expiry, the user must log in again. Session tokens are HTTP-only, Secure, and SameSite cookies.

**Rule Type:** Compliance Rule / Permission Rule

---

## BR-020 — T+2 Settlement Disclosure

**Rule Name:** Sell Calculator Must Display T+2 Settlement Notice

**Description:** The sell scenario calculator must display the following disclosure on every result page: "Calculations are informational only. BursaTrack is not a financial advisor. Settlement on Bursa Malaysia is T+2 — cash from a sale is available two trading days after the trade date." This disclosure is non-dismissable.

**Rule Type:** Compliance Rule

---

## BR-021 — Financial Disclaimer

**Rule Name:** Financial Disclaimer on All Calculated Outputs

**Description:** All pages displaying yield, profit/loss, or scenario calculations must include: "BursaTrack is a portfolio tracking tool and does not provide financial advice. All calculations are informational only." This disclaimer must be permanently visible, not dismissed by the user.

**Rule Type:** Compliance Rule

---

## BR-022 — CSV Import Atomicity

**Rule Name:** CSV Import Is All-or-Nothing

**Description:** A CSV import either creates all records successfully or creates none. If any row fails validation, the entire import is rolled back and no records are created. The user receives a row-level error report.

**Rule Type:** Workflow Rule

---

## BR-023 — Price Override Supersession

**Rule Name:** Manual Price Overrides Are Superseded by Automated Refresh

**Description:** When the automated price refresh successfully returns a price for a stock that has a manual override, the automated price replaces the manual override. The manual price is stored in the audit log but is no longer the active price.

**Rule Type:** Workflow Rule

---

## BR-024 — Proportional Cost for Partial Sell

**Rule Name:** Partial Sale All-In Cost Is Proportional

**Description:** In the sell calculator, when the user enters fewer shares than the total position, the all-in buy cost used for profit/loss calculation = (shares_to_sell / total_position_shares) × position_total_all_in_cost.

**Rule Type:** Calculation Rule

**Example:**
- CIMB: 5,000 shares, total all-in cost RM41,996.47
- Sell 2,000 shares → proportional cost = (2,000 / 5,000) × RM41,996.47 = RM16,798.59

---

*End of Part 1. Continue in BursaTrack-BAS-Part2.md (Process Flows · Data Requirements · Validation Rules · Permissions) and BursaTrack-BAS-Part3.md (Exception Handling · Edge Cases · Assumptions · Open Questions · Testing Readiness · BA Quality Review).*
