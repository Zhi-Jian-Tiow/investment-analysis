# BursaTrack — Enhanced Business Analyst Specification
## Part 1 of 3: Sections 1–5

> **Version:** 2.0 — Enhanced
> **Date:** 2026-06-21
> **Basis:** BursaTrack-BAS-Part1/2/3.md v1.0 + Principal BA Review
> **Annotation key:** `[FIXED: reason]` = corrected content | `[NEW: reason]` = added content | No annotation = KEEP (unchanged, verified correct)
> **Companion document:** BursaTrack-BAS-Enhanced-Analysis.md (Change Summary · Open Items · Scope Check · Readiness)

---

# 1. BUSINESS ANALYSIS SUMMARY

## Overview

**Product Purpose:** BursaTrack is a web-based dividend portfolio tracker purpose-built for Malaysian retail investors on Bursa Malaysia. It automates daily price retrieval, calculates all-in transaction costs using the correct Malaysian fee stack (brokerage at the user's actual broker rate, 0.03% clearing fee, RM1/RM1,000 stamp duty), logs per-tranche dividend payments, and produces a true yield figure using all-in cost as the denominator.

**Business Context:** The product replaces a manually-maintained Excel workbook as the primary workflow tool for a dividend-income investor. The Excel model has a documented formula bug (row 28 references dividend tranche 1 instead of tranche 8 in the true-branch of an IF statement) and a yield denominator error (divides by pre-fee cost rather than all-in cost). BursaTrack must correct both issues and provide automated price retrieval to eliminate the 10–15 minute daily manual update cycle.

**Scope of This Analysis:** All ten functional requirements defined in PRD v2.0 (REQ-001 through REQ-010), plus authentication, subscription management, password reset, and PDPA compliance workflows which are implicit dependencies. This analysis covers system behaviour, business rules, process flows, data requirements, validation rules, exception handling, and edge cases. It does not cover infrastructure architecture, database schema design, API design, or UI layout.

## Key Observations

**Well-defined areas:**
- Malaysian fee stack is specified to implementation precision: brokerage rate per broker, clearing fee 0.03%, stamp duty ROUNDUP(amount/1000, 0) with RM1 minimum.
- Yield denominator is unambiguous: all-in cost (initial amount + brokerage + clearing + stamp duty), not pre-fee initial amount.
- Sell calculator logic is fully specified with a numeric break-even test case (CIMB: buy RM8.38 → break-even RM8.42).

**[FIXED: BR-009 critical defect surfaced — original stated dividend total was derived from live position_total_shares; this causes retroactive corruption when new lots are added post-dividend]**
- Dividend tranche model is now corrected: per_share_amount and qualifying_shares are stored at logging time; total_amount is stored (not derived). See BR-009 and BR-027.

**Areas requiring clarification (ESCALATE items — see companion document):**
- Multi-lot yield calculation method: blended all-in cost as single denominator vs. per-lot yield — confirmed as blended.
- Dividend tranche year boundary: calendar year vs. stock financial year; stakeholder decision required.
- Broker tiered fee handling: Rakuten Trade tiered structure deferred to V1.1.
- Trial period length and feature gating: 14-day assumption requires confirmation.
- Sell calculator broker for multi-lot positions with different brokers: stakeholder decision required.
- SST on brokerage (July 2025 Bursa FAQ): must be verified immediately.

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
- Trial expiry date is set to registration date + 14 days (assumption — pending stakeholder decision; see Open Items).
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
   - All monetary amounts rounded per BR-025.
6. System creates a Lot record and links it to the Position (creating a new Position if this is the first lot for this stock in the portfolio).
7. System updates the portfolio summary (total cost, blended yield).
8. System displays the new position in the dashboard with all calculated values.

**Post Conditions:**
- A Lot record exists with all fee components and all-in cost stored.
- A Position record exists (new or updated) with derived aggregate values.
- Portfolio summary totals are updated.

**User Value:** Accurate record of what the investor actually paid, including all transaction costs.

**Priority:** Must Have

---

## FR-004 — Add Lot to Existing Position

**Description:** A user adds a subsequent purchase lot to a position that already exists in the portfolio. The system calculates the new lot's all-in cost and updates the position's blended cost basis.

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

**[FIXED: Original step 6 said "Dividend yield = total dividend income / total all-in cost (recalculated)" without clarifying that dividend income uses stored total_amounts — NOT re-derived from the new share count. This was ambiguous and could lead to retroactive corruption if misread alongside old BR-009.]**

   - Dividend yield = total dividend income / total all-in cost, where total dividend income is the sum of DividendTranche.total_amount fields (stored at logging time — see BR-027). Adding a new lot does NOT change any previously stored DividendTranche.total_amount.

7. Portfolio summary totals are updated.

**Post Conditions:**
- New Lot record exists.
- Position aggregate values (total shares, total cost, blended price, yield) reflect all lots.
- All previously logged DividendTranche.total_amount values are unchanged.

**User Value:** Accurate blended cost basis for positions built up over multiple purchases.

**Priority:** Must Have

---

## FR-005 — Edit Position / Lot

**Description:** A user corrects a previously entered position or lot. The system recalculates all derived values and records the change in the audit log.

**Trigger:** User clicks "Edit" on a position or lot.

**Preconditions:**
- The position/lot exists and belongs to the authenticated user.

**Main Flow:**
1. User opens the edit form for a position or a specific lot.
2. User modifies one or more fields.
3. System validates the updated inputs.
4. System recalculates all affected derived values (fees, all-in cost, yield, portfolio totals).
5. System writes the previous values to the audit log with a timestamp and user attribution.
6. System saves the updated record.
7. Dashboard reflects updated values immediately.

**[NEW: Clarify that editing a lot's share count does NOT retroactively change stored DividendTranche.total_amount values — they are fixed at the qualifying_shares recorded at dividend logging time. See BR-027.]**

**Note:** Editing a lot's share count changes position_total_shares (the current share count used for new dividend calculations), but does NOT alter any existing DividendTranche.total_amount. If the user believes historical dividend totals are also wrong, they must edit each DividendTranche separately.

**Post Conditions:**
- Lot / Position record updated with new values.
- Previous values stored in audit log.
- All downstream derived values (position yield, portfolio blended yield) recalculated using stored DividendTranche.total_amount values.

**User Value:** Ability to correct data entry errors without losing the position.

**Priority:** Must Have

---

## FR-006 — Delete Position

**Description:** A user removes a position and all its associated lots and dividend tranches from the portfolio.

**Trigger:** User clicks "Delete Position" and confirms the deletion.

**Preconditions:** The position belongs to the authenticated user.

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

**Priority:** Must Have

---

## FR-007 — Automated Daily Price Refresh

**Description:** On each Bursa Malaysia trading day, the system automatically retrieves the latest market price for every stock held across all active portfolios and updates the PriceSnapshot records.

**Trigger:** Scheduled job fires on each Bursa Malaysia trading day (Monday–Friday, excluding public holidays per the configurable trading calendar).

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

**Priority:** Must Have

---

## FR-009 — Log Dividend Tranche

**[FIXED: Step 5 originally said "System derives: total amount = dividend per share × position_total_shares" — this causes retroactive corruption when new lots are added after the dividend is logged. Fixed to store qualifying_shares and total_amount at logging time. See CI-001 in analysis document.]**

**Description:** A user records an individual dividend payment received for a position. The system stores the per-share amount and qualifying share count at the time of logging, computes and stores the total received, and recalculates the position's yield and the portfolio's blended yield.

**Trigger:** User submits the "Add Dividend" form for a position.

**Preconditions:**
- The position exists and belongs to the authenticated user.
- The position has fewer than 8 logged dividend tranches for the relevant calendar year.

**Main Flow:**
1. User opens the dividend section of a position.
2. User selects the tranche label (1st–8th; system suggests the next available label).
3. User enters: dividend per share (MYR), payment date, ex-dividend date (optional).

**[FIXED: New step 3a — qualifying_shares field]**

3a. System displays a "Qualifying Shares" field pre-populated with position_total_shares at this moment. User may override this value if they know the actual share count that qualified for this dividend (e.g., they held fewer shares before the ex-date than they hold today). The qualifying_shares value must be ≥ 1 and ≤ position_total_shares at the time of logging.

4. System validates all inputs.

**[FIXED: Step 5 — now stores qualifying_shares and total_amount; does not derive from live share count]**

5. System stores:
   - qualifying_shares = the value from step 3a (defaults to current position_total_shares)
   - total_amount = per_share_amount × qualifying_shares (stored at this moment; will NOT change if the position's share count later changes)

6. System creates a DividendTranche record with: tranche label, per_share_amount, qualifying_shares, total_amount (stored), payment_date, ex_dividend_date (if entered), year.
7. System recalculates:
   - Position total dividend per share (YTD) = sum of all tranches' per_share_amount for the year.
   - Position total dividend income (YTD) = sum of all tranches' stored total_amount for the year.
   - Position yield = position total dividend income / position total all-in cost.
   - Portfolio blended yield = sum of all positions' total dividend income / sum of all positions' all-in cost.
8. Dashboard and position detail update immediately.

**Post Conditions:**
- DividendTranche record exists with qualifying_shares and total_amount both stored.
- Position and portfolio yield figures updated.
- Dividend calendar updated if ex-dividend date was entered.

**User Value:** Accurate, per-tranche dividend record that drives the true yield calculation, immune to retroactive corruption from future share purchases.

**Priority:** Must Have

---

## FR-010 — Edit / Delete Dividend Tranche

**[FIXED: Edit flow must clarify that recalculation uses stored qualifying_shares — it does NOT re-derive from current position_total_shares. Also clarifies that editing per_share_amount recomputes total_amount using the existing stored qualifying_shares.]**

**Description:** A user corrects or removes a previously logged dividend tranche. All downstream yield calculations recalculate immediately. The change is recorded in the audit log.

**Trigger:** User clicks "Edit" or "Delete" on a dividend tranche record.

**Preconditions:** The tranche belongs to the authenticated user's position.

**Main Flow (Edit):**
1. User opens the edit form for the tranche.
2. User may modify: per_share_amount, qualifying_shares, payment_date, or ex_dividend_date.
3. System validates updated values (qualifying_shares must be ≥ 1 and ≤ position_total_shares at the time of editing).
4. System recalculates stored total_amount = updated per_share_amount × updated qualifying_shares.
5. System writes previous values to audit log.
6. System saves the update and recalculates position and portfolio yield using the new stored total_amount.

**Main Flow (Delete):**
1. User clicks "Delete."
2. System displays: "Delete this dividend record? This cannot be undone."
3. User confirms.
4. System soft-deletes the tranche record.
5. System recalculates position and portfolio yield with the tranche removed.

**Post Conditions:**
- Tranche updated or removed.
- Stored total_amount reflects the edited values (not re-derived from live share count).
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
   - Total annual dividend income (current calendar year — sum of stored DividendTranche.total_amount)
   - Portfolio blended yield (%)
   - Last price refresh timestamp
3. System renders the position table with per-position columns:
   - Stock name and code
   - Category tag
   - Total shares (current — sum of all active lots)
   - Blended purchase price
   - Total all-in cost
   - Current price (with stale indicator if applicable)
   - Current market value
   - Unrealised P&L (current market value − total all-in cost)
   - Total dividend income (current year — sum of stored DividendTranche.total_amount)
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

**[NEW: Broker selection for multi-lot positions — see Open Item in companion document]**

3. System selects the broker for sell-side fee calculation: when a position has multiple lots using different brokers, the system defaults to the broker of the most recently created active lot. The user may override the broker for the sell calculation without altering the position's stored data. This default is an assumption pending stakeholder confirmation.

4. System auto-generates price scenarios at the following increments above the current price:
   - +0.01, +0.02, +0.03, +0.04, +0.05 (fine-grained near current price)
   - +0.10, +0.15, +0.20 … +0.70 (broad view in 0.05 steps)
5. For each scenario price, the system calculates:
   - Gross sell proceeds = scenario price × total shares
   - Sell brokerage fee = per broker rule on gross proceeds (BR-001 to BR-004)
   - Sell clearing fee = gross proceeds × 0.03% (rounded per BR-025)
   - Sell stamp duty = ROUNDUP(gross proceeds / 1000, 0)
   - Net sell proceeds = gross proceeds − (sell brokerage + sell clearing + sell stamp duty)
   - Profit/Loss = net sell proceeds − all-in buy cost
6. System highlights the break-even row (lowest scenario price where profit/loss ≥ 0).
7. System displays a disclosure: "Calculations are informational only. Settlement occurs T+2 (two trading days after sale)." (BR-020)
8. User can enter a custom sell price not in the auto-generated list.
9. User can adjust the number of shares to sell (partial sale — see BR-024).

**Post Conditions:** Calculator results displayed; not persisted.

**Priority:** Must Have

---

## FR-013 — Dividend Calendar

**Description:** A calendar or chronological list view that displays upcoming ex-dividend dates and expected payment dates for all stocks held in the portfolio. Data is sourced from ex-dates and payment dates entered by the user when logging dividend tranches.

**Trigger:** User navigates to the Dividend Calendar tab.

**Preconditions:** User is authenticated.

**Main Flow:**
1. System retrieves all DividendTranche records for the user's portfolio where ex_dividend_date or payment_date is in the future (or within the past 30 days).
2. System renders entries in ascending chronological order by ex_dividend_date (if present) or payment_date.
3. Each entry shows: stock name, tranche label, ex_dividend_date, payment_date, per_share_amount, stored total_amount (based on qualifying_shares at time of logging).
4. Dates that have passed are displayed with a "Paid" badge.
5. Upcoming dates within the next 7 days are highlighted.
6. If no dates are recorded: "Add ex-dates when logging dividends to see your payment schedule here."

**Post Conditions:** Calendar view rendered from stored dividend data.

**Priority:** Should Have (V1)

---

## FR-014 — CSV Import

**Description:** A user imports their portfolio positions and optionally their dividend history from a CSV file, using the BursaTrack-provided template. Atomic import — either all records are created or none.

**Trigger:** User uploads a CSV file on the Import page.

**Preconditions:**
- User is authenticated with an active account.
- User has either an empty portfolio or has chosen a conflict resolution option for stocks already in the portfolio.

**Main Flow:**
1. User downloads the CSV template from the Import page.
2. User populates the template with their portfolio data.
3. User uploads the completed CSV file.
4. System validates the file format, column presence, and row-level data (see Validation Rules, Section 8).
5. If validation passes: system creates all Position, Lot, and DividendTranche records in a single atomic transaction.

**[NEW: Clarify qualifying_shares on CSV import]**

For each DividendTranche row in the import file, qualifying_shares defaults to the share count of the matching position as imported. If the user wishes to specify a different qualifying share count, they may include an optional `qualifying_shares` column in the Dividends sheet.

6. System redirects the user to the dashboard with a success message: "Import complete — [N] positions and [M] dividend records imported."
7. If validation fails: system displays a row-level error report. No records are created.

**Post Conditions (success):** All records created; dashboard populated; all yield calculations computed.
**Post Conditions (failure):** No records created; user receives actionable error messages.

**Priority:** Must Have

---

## FR-015 — CSV Template Download

**Description:** The user downloads a pre-formatted CSV template with column headers, a guide row, and one example row.

**Trigger:** User clicks "Download Template" on the Import page.

**Preconditions:** User is authenticated.

**Main Flow:**
1. System serves a CSV file containing: column headers, guide row, example data row.
2. File downloads as `BursaTrack_Import_Template.csv`.

**Post Conditions:** Template file available for download.

**Priority:** Must Have

---

## FR-016 — Subscription Management

**Description:** At the end of the trial period, the user is prompted to subscribe. An expired trial user can view their portfolio (read-only) but cannot add or edit data.

**Trigger:** Trial expiry date passes; or user clicks "Subscribe."

**Preconditions:** User account exists.

**Main Flow (trial expiry):**
1. On the day the trial expires, the system marks the account as "trial_expired."
2. On next login, the system displays a paywall screen with portfolio visible in read-only mode.
3. User cannot add, edit, or delete positions or dividends until they subscribe.

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

**Post Conditions:** Account status reflects current subscription state; portfolio data preserved.

**Priority:** Must Have

---

## FR-017 — Password Reset

**[NEW: Standard auth requirement; flagged as missing in BA Quality Review; required before auth sprint can be considered complete.]**

**Description:** A registered user who has forgotten their password initiates a password reset by entering their email. The system sends a time-limited reset link. The user clicks the link, enters a new password, and the system updates the stored password hash and invalidates all existing sessions.

**Trigger:** User clicks "Forgot Password" on the login page.

**Preconditions:** None required (the email may or may not belong to a registered account — the system does not reveal which).

**Main Flow:**
1. User enters their email address and clicks "Send Reset Link."
2. System searches for an account with the provided email.
3. **Regardless of whether the account exists**, the system displays: "If an account with that email exists, a reset link has been sent." (Prevents account enumeration.)
4. If the account exists: system generates a secure, single-use reset token with a 1-hour expiry. System sends an email containing the reset link.
5. User clicks the reset link within 1 hour.
6. System validates the token (exists, unused, not expired).
7. System presents a "Set New Password" form.
8. User enters a new password and confirmation.
9. System validates the new password (see Validation Rules §8).
10. System hashes the new password and updates the User record.
11. System marks the reset token as used.
12. System invalidates all active sessions for this user.
13. System redirects the user to the login page with: "Password updated successfully. Please log in."

**Post Conditions:**
- User's password_hash updated.
- All prior sessions invalidated.
- Reset token marked as used (cannot be reused).

**Alternative Flow — Token expired:**
1. User clicks a reset link that has expired (> 1 hour).
2. System displays: "This reset link has expired. Request a new one?"
3. User can request a new link (restarts from step 1).

**Alternative Flow — Token already used:**
1. User clicks a link that was already used.
2. System displays: "This reset link has already been used. If you did not reset your password, contact support."

**User Value:** Self-service account recovery without support intervention.

**Priority:** Must Have `[REQUIRES STAKEHOLDER SIGN-OFF on Must Have classification — cannot be deferred from V1 without explicit acceptance of the support burden and security risk of having no self-service recovery path]`

---

## FR-018 — PDPA User Data Export

**[NEW: PDPA compliance requirement. PRD NFR §13 explicitly states "Users can request a full export of their data in CSV format." Workflow was absent from the original BAS.]**

**Description:** An authenticated user can download a complete export of all their personal and portfolio data in CSV format, satisfying the Malaysian Personal Data Protection Act (PDPA) right of access.

**Trigger:** User navigates to Account Settings and clicks "Download My Data."

**Preconditions:** User is authenticated (any account status, including trial_expired).

**Main Flow:**
1. User clicks "Download My Data" in Account Settings.
2. System confirms: "Preparing your data export. This may take a few seconds."
3. System compiles the following into a ZIP file containing multiple CSVs:
   - `account.csv`: email, account status, registration date, trial expiry, subscription dates.
   - `positions.csv`: all positions (including soft-deleted, with deletion date).
   - `lots.csv`: all lots with all fee fields.
   - `dividend_tranches.csv`: all dividend tranches with qualifying_shares, total_amount, dates.
   - `price_overrides.csv`: all manual price overrides entered by the user.
   - `audit_log.csv`: all audit log entries attributed to this user.
4. System serves the ZIP file for download as `BursaTrack_DataExport_[YYYY-MM-DD].zip`.
5. System records that a data export was performed (timestamp) in the audit log.

**Post Conditions:**
- Data export ZIP file downloaded by user.
- Export event recorded in audit log.

**User Value:** Compliance with PDPA right of access; user can migrate their data or verify what is stored.

**Priority:** Must Have (PDPA compliance obligation) `[REQUIRES STAKEHOLDER SIGN-OFF on V1 inclusion — legal risk of launching without this in Malaysia must be assessed]`

---

## FR-019 — Account Deletion (PDPA)

**[NEW: PDPA compliance requirement. PRD NFR §13 states "Users can request account and all associated data deletion; deletion completed within 30 days." Workflow was absent from the original BAS.]**

**Description:** An authenticated user can request the deletion of their account and all associated personal and portfolio data. A 30-day grace period applies before permanent deletion, during which the user may cancel the request. The user is offered a data export before deletion is confirmed.

**Trigger:** User navigates to Account Settings and clicks "Delete My Account."

**Preconditions:** User is authenticated.

**Main Flow:**
1. User clicks "Delete My Account."
2. System displays a two-step confirmation:
   - Step 1: "Before deleting, would you like to download your data? [Download My Data] [Skip and Continue]"
   - Step 2: "This will permanently delete your account and all data in 30 days. Type DELETE to confirm."
3. User types "DELETE" and confirms.
4. System sets account status to "pending_deletion" and records the deletion_requested_date.
5. System sends a confirmation email: "Your account deletion request has been received. Your data will be permanently deleted on [deletion_requested_date + 30 days]. To cancel, click here."
6. System logs the user out and invalidates all sessions.
7. User cannot log in during the pending_deletion period (account is inaccessible).
8. If the user clicks "Cancel deletion" in the email within 30 days: system restores the account to its previous status (trial_expired or active); user can log in again.
9. After 30 days: system permanently hard-deletes all user data (User, Portfolio, Positions, Lots, DividendTranches, PriceSnapshots linked to this user, AuditLog entries). The deletion is irreversible.

**Post Conditions (deletion confirmed after 30 days):**
- All user data permanently deleted.
- The email address is freed and can be used to register a new account.

**Post Conditions (deletion cancelled within 30 days):**
- Account restored to previous status.
- No data deleted.

**User Value / Compliance:** Satisfies PDPA right of erasure; gives users control over their personal data.

**Priority:** Must Have (PDPA compliance obligation) `[REQUIRES STAKEHOLDER SIGN-OFF on V1 inclusion]`

---

# 3. USER STORIES

| Story ID | Description | Linked FR | Priority |
|----------|-------------|-----------|----------|
| US-001 | As a new investor, I want to register with my email and default broker, so that I can start a free trial | FR-001 | Must Have |
| US-002 | As a registered user, I want to log in securely, so that only I can access my portfolio | FR-002 | Must Have |
| US-003 | As Ahmad, I want to add a stock position with purchase price, shares, and broker, so that the system calculates my true all-in cost | FR-003 | Must Have |
| US-004 | As David, I want to add multiple lots to the same stock at different prices, so that I have an accurate blended cost basis | FR-004 | Must Have |
| US-005 | As Farah, I want to edit a position I entered incorrectly, so that my portfolio reflects my actual holdings | FR-005 | Must Have |
| US-006 | As any user, I want to delete a position I no longer hold, so that my portfolio stays accurate | FR-006 | Must Have |
| US-007 | As Ahmad, I want prices to refresh automatically on trading days, so that I don't spend 10–15 minutes updating manually | FR-007 | Must Have |
| US-008 | As any user, I want a clear warning when price data is unavailable, so that I don't make decisions on stale data | FR-008 | Must Have |
| US-009 | As any user, I want to enter prices manually when the automated feed fails, so that I can continue using the portfolio during outages | FR-008 | Must Have |
| US-010 | As Ahmad, I want to log individual dividend tranches separately, so that I have an accurate record of each payment received | FR-009 | Must Have |
| US-011 | As David, I want yield calculated using my all-in cost as denominator, so that my ROI is accurate | FR-009 | Must Have |
| US-012 | As any user, I want to edit a dividend tranche I entered incorrectly, so that my income figures are correct | FR-010 | Must Have |
| US-013 | As any user, I want to see all positions in a single dashboard with yield, income, and current value, so that I can assess my portfolio in under 5 minutes | FR-011 | Must Have |
| US-014 | As David, I want to sort positions by yield, so that I can identify my highest-returning holdings | FR-011 | Must Have |
| US-015 | As David, I want to model a sell at multiple price points and see net proceeds after all fees, so that I know my break-even before executing a trade | FR-012 | Must Have |
| US-016 | As Farah, I want the sell calculator to highlight the break-even price, so that I know my floor before deciding to sell | FR-012 | Must Have |
| US-017 | As Ahmad, I want to see upcoming ex-dividend dates for all my holdings, so that I never miss an ex-date | FR-013 | Should Have |
| US-018 | As Ahmad, I want to import my portfolio from a CSV file, so that I don't spend 45 minutes on manual entry | FR-014 | Must Have |
| US-019 | As any user, I want to download a CSV template, so that I know the exact format required | FR-015 | Must Have |
| US-020 | As any user on trial expiry, I want to subscribe, so that I don't lose access to my portfolio | FR-016 | Must Have |
| US-021 | As a user who has forgotten their password, I want to reset it via email, so that I can regain access to my account without contacting support | FR-017 | Must Have |
| US-022 | As any user, I want to download all my data in CSV format, so that I can verify what BursaTrack stores about me and migrate it if needed | FR-018 | Must Have |
| US-023 | As any user, I want to permanently delete my account and all my data, so that my personal information is not retained after I stop using the service | FR-019 | Must Have |

---

# 4. ACCEPTANCE CRITERIA

## US-001 / FR-001 — Registration

**Happy Path**
```gherkin
Given I am on the registration page
When I enter valid email "ahmad@email.com", password "Invest2026", confirm "Invest2026", broker "Maybank Investment"
Then my account is created with status "trial"
And trial expiry = registration date + 14 days
And an empty Portfolio is linked to my account
And I am redirected to the onboarding dashboard
And I see: "Please verify your email. Check your inbox."
And I receive a verification email at "ahmad@email.com"
```

**Alternate: email already registered**
```gherkin
Given "ahmad@email.com" is already registered
When I attempt to register with "ahmad@email.com"
Then I see: "An account with this email already exists. Log in instead?"
And no new account is created
```

**Error: password mismatch**
```gherkin
Given password "Invest2026" and confirm "invest2026"
When I submit registration
Then I see: "Passwords do not match"
And no account is created
```

**Error: invalid email format**
```gherkin
Given email "not-an-email"
When I submit registration
Then I see: "Please enter a valid email address"
```

---

## US-002 / FR-002 — Login

**Happy Path**
```gherkin
Given verified account with email "ahmad@email.com" and password "Invest2026"
When I enter correct credentials
Then I am redirected to my portfolio dashboard
And a secure session is established
```

**Error: wrong password (below lockout)**
```gherkin
Given I have failed login 4 times already
When I enter the wrong password a 5th time
Then I see: "Too many failed attempts. Please wait 10 minutes before trying again."
And the login form is disabled for 10 minutes
```

**Permission: unverified email**
```gherkin
Given my email has not been verified
When I log in
Then I am taken to the dashboard with a persistent banner: "Please verify your email to ensure you don't lose access."
And I retain full access during the trial period
```

---

## US-003 / FR-003 — Add Position

**Happy Path: Maybank Investment**
```gherkin
Given I am logged in with default broker "Maybank Investment" (0.10%, min RM8)
When I add stock "CIMB 1023", 5000 shares, price RM8.38, date 2026-01-15
Then initial amount = RM41,900.00
And brokerage fee = RM41.90 (RM41,900 × 0.001, rounded to 2dp)
And clearing fee = RM12.57 (RM41,900 × 0.0003, rounded to 2dp)
And stamp duty = RM42.00 (ROUNDUP(41.9, 0))
And all-in cost = RM41,996.47
```

**Alternate: MooMoo flat-fee**
```gherkin
Given I select broker "MooMoo" (RM3 flat)
When I add "CIMB 1023", 5000 shares, price RM8.38
Then brokerage fee = RM3.00
And all-in cost = RM41,957.57 (41,900 + 3.00 + 12.57 + 42.00)
```

**Alternate: brokerage minimum applied**
```gherkin
Given broker "Maybank Investment" (0.10%, min RM8)
When I add "FM 7210", 5000 shares, price RM0.60
Then initial amount = RM3,000.00
And 0.10% of RM3,000 = RM3.00 < RM8 minimum
And brokerage fee = RM8.00
And clearing fee = RM0.90
And stamp duty = RM3.00
And all-in cost = RM3,011.90
```

**Error: share count zero**
```gherkin
Given share count "0"
When I submit the form
Then I see: "Number of shares must be greater than zero"
```

---

## US-004 / FR-004 — Add Lot to Existing Position

**Happy Path**
```gherkin
Given CIMB position: 5,000 shares, all-in RM41,996.47, one 1st dividend tranche stored (RM0.20/share, qualifying_shares=5000, total_amount=RM1,000 stored)
When I add second lot: 2,000 shares at RM9.00, broker "Maybank Investment"
Then lot 2 initial amount = RM18,000.00
And lot 2 brokerage = RM18.00, clearing = RM5.40, stamp duty = RM18.00
And lot 2 all-in cost = RM18,041.40
And CIMB total shares = 7,000
And CIMB total all-in cost = RM60,037.87
And blended purchase price = RM59,900 / 7,000 = RM8.557 (approx)
And the 1st dividend tranche total_amount remains RM1,000.00 (stored value is unchanged)
```

---

## US-005 / FR-005 — Edit Position / Lot

**[NEW: Acceptance criteria were absent from the original BAS.]**

**Happy Path: edit lot share count**
```gherkin
Given I have a CIMB lot with 5,000 shares at RM8.38 (all-in RM41,996.47)
And I have a stored dividend tranche: qualifying_shares=5000, total_amount=RM1,000.00
When I edit the lot share count from 5,000 to 4,000
Then lot initial amount recalculates to RM33,520.00
And lot brokerage = RM33.52, clearing = RM10.056 → RM10.06, stamp duty = RM34.00
And lot all-in cost = RM33,597.58
And the existing dividend tranche total_amount remains RM1,000.00 (qualifying_shares=5000 unchanged)
And the dashboard shows a recalculation notice: "Position updated. Dividend records were not changed."
```

**Happy Path: edit lot broker**
```gherkin
Given CIMB lot with broker "Maybank Investment" (all-in RM41,996.47)
When I change the broker to "MooMoo" (RM3 flat)
Then brokerage recalculates to RM3.00
And new all-in cost = RM41,900 + RM3.00 + RM12.57 + RM42.00 = RM41,957.57
And the change is recorded in the audit log
```

**Error: invalid share count on edit**
```gherkin
Given I am editing a lot
When I change share count to "-100"
Then I see: "Number of shares must be greater than zero"
And the change is not saved
```

**Permission: edit position owned by another user**
```gherkin
Given position_id "XYZ" belongs to a different user
When I attempt to access the edit form for "XYZ" directly by URL
Then I receive a 404 response
And no data is revealed about whether the position exists
```

---

## US-006 / FR-006 — Delete Position

**[NEW: Acceptance criteria were absent from the original BAS.]**

**Happy Path**
```gherkin
Given I have a CIMB position with 2 lots and 3 dividend tranches
When I click "Delete Position" and confirm
Then CIMB no longer appears in my portfolio
And all 2 lots are soft-deleted
And all 3 dividend tranches are soft-deleted
And total portfolio all-in cost decreases by the CIMB position's all-in cost
And portfolio blended yield recalculates without CIMB
```

**Error: confirmation dialog dismissed**
```gherkin
Given the delete confirmation dialog is shown
When I click "Cancel"
Then the position is not deleted
And I am returned to the dashboard
```

---

## US-007 / FR-007 — Automated Price Refresh

**Happy Path**
```gherkin
Given it is a Bursa trading day and the price feed is available
When the scheduled refresh job runs
Then PriceSnapshot records are created/updated for all stocks in active portfolios
And each position shows the latest price with "Last updated: [timestamp]"
And unrealised P&L is recalculated
```

**Alternate: weekend / public holiday**
```gherkin
Given today is a Saturday or a day in the configured Bursa holiday calendar
When the scheduled refresh time arrives
Then the job does not run
And the dashboard shows the most recent trading day's prices
And "Last updated" reflects the last trading day
```

---

## US-008–009 / FR-008 — Price Data Outage

**Error: complete feed failure**
```gherkin
Given the price feed is unavailable
When the scheduled refresh runs
Then within 5 minutes the dashboard shows: "Price data unavailable — showing prices as of [last timestamp]. Update prices manually below."
And each affected position shows a stale price indicator
And a manual price entry field is available for each position
```

**Alternate: partial failure**
```gherkin
Given the feed returns prices for 14 of 16 stocks but fails for CARLSBG and LPI
When the refresh runs
Then only CARLSBG and LPI show stale indicators and manual entry fields
And the status banner reads: "Price data unavailable for 2 stocks — CARLSBG, LPI"
```

**Happy Path: override superseded**
```gherkin
Given I entered manual price RM8.50 for CIMB during an outage
When the next automated refresh succeeds and returns RM8.42 for CIMB
Then CIMB price updates to RM8.42
And the stale/manual indicator is removed
And "Last updated: [refresh timestamp]" is shown
```

---

## US-010 / FR-009 — Log Dividend Tranche

**Happy Path**
```gherkin
Given I have a CIMB position with 5,000 shares (no dividends logged)
When I log: 1st tranche, RM0.20/share, payment 2026-03-15, ex-date 2026-02-28
And qualifying_shares defaults to 5,000 (I do not override it)
Then qualifying_shares = 5,000 is stored on the tranche
And total_amount = RM0.20 × 5,000 = RM1,000.00 is stored on the tranche
And position total dividend per share YTD = RM0.20
And position total dividend income YTD = RM1,000.00
And position yield = RM1,000.00 / RM41,996.47 = 2.38%
And the dividend calendar shows ex-date 28 Feb and payment 15 Mar
```

**[NEW: Test that total_amount does NOT change when a new lot is added later]**

**Critical regression test: new lot does not corrupt historical dividend**
```gherkin
Given CIMB has a stored 1st tranche (qualifying_shares=5000, total_amount=RM1,000.00)
When I add a second lot of 2,000 CIMB shares
Then CIMB total shares becomes 7,000
And the 1st tranche qualifying_shares remains 5,000
And the 1st tranche total_amount remains RM1,000.00
And CIMB total dividend income YTD remains RM1,000.00
And CIMB yield recalculates only due to the new all-in cost (denominator increases)
```

**Error: exceeds 8 tranches**
```gherkin
Given CIMB already has 8 dividend tranches for calendar year 2026
When I attempt to add a 9th tranche for 2026
Then I see: "Maximum of 8 dividend tranches per year reached for CIMB (2026)."
And no record is created
```

---

## US-011 / FR-009 — Yield Denominator Correctness

**Happy Path**
```gherkin
Given CIMB: total dividend income RM2,337.50 (from stored total_amounts), all-in cost RM41,996.47
When the system calculates yield
Then yield = RM2,337.50 / RM41,996.47 = 5.5660...% displayed as 5.57%
And yield is NOT RM2,337.50 / RM41,900 = 5.58% (pre-fee cost)
```

---

## US-012 / FR-010 — Edit Dividend Tranche

**[NEW: Acceptance criteria were absent from the original BAS.]**

**Happy Path: edit per_share_amount**
```gherkin
Given CIMB 1st tranche: per_share=RM0.20, qualifying_shares=5000, total_amount=RM1,000.00 (stored)
When I edit per_share_amount to RM0.22
Then total_amount recalculates to RM0.22 × 5,000 = RM1,100.00 (using stored qualifying_shares=5000)
And position total dividend income YTD increases by RM100
And yield recalculates
And the change is recorded in the audit log
```

**Happy Path: edit qualifying_shares**
```gherkin
Given CIMB 1st tranche: per_share=RM0.20, qualifying_shares=5000, total_amount=RM1,000.00
When I realise I only held 3,000 shares at the ex-date and edit qualifying_shares to 3,000
Then total_amount recalculates to RM0.20 × 3,000 = RM600.00
And position total dividend income YTD decreases by RM400
And the change is recorded in the audit log
```

**Error: qualifying_shares exceeds current position total**
```gherkin
Given CIMB position has 5,000 total shares
When I attempt to set qualifying_shares to 6,000
Then I see: "Qualifying shares cannot exceed the position's current total shares (5,000)"
```

---

## US-013 / FR-011 — Portfolio Dashboard

**[NEW: Acceptance criteria were absent from the original BAS.]**

**Happy Path**
```gherkin
Given I have a portfolio with 16 positions, all lots and dividends entered
When I open the portfolio dashboard
Then the summary header shows: total all-in cost, total YTD dividend income, portfolio blended yield, last price refresh timestamp
And each position row shows: stock name/code, category tag, total shares, blended price, all-in cost, current price, current market value, unrealised P&L, YTD dividend income, yield
And the page loads within 3 seconds
And positions are sorted by yield descending by default
```

**Alternate: position with no dividends**
```gherkin
Given SUNWAY position has no dividend tranches logged
When I view the dashboard
Then SUNWAY shows yield as "—" (not 0%)
And SUNWAY dividend income shows RM0.00 or "—"
```

**Alternate: price data stale**
```gherkin
Given price data for CARLSBG is stale (last refreshed yesterday)
When I view the dashboard
Then CARLSBG shows its current price with a stale indicator icon
And the portfolio banner shows the stale warning for CARLSBG
```

---

## US-014 / FR-011 — Sort by Yield

**[NEW: Acceptance criteria were absent from the original BAS.]**

**Happy Path**
```gherkin
Given I am viewing the dashboard sorted by default (yield descending)
When I click the "Yield" column header
Then positions reorder ascending by yield (lowest first)
When I click "Yield" again
Then positions reorder descending (highest first)
And the sort preference is saved for my next session
```

---

## US-015–016 / FR-012 — Sell Scenario Calculator

**Happy Path**
```gherkin
Given CIMB: 5,000 shares, all-in buy cost RM41,996.47, broker "Maybank Investment"
When I open the sell calculator
Then scenarios are generated at RM8.39, RM8.40, RM8.41, RM8.42, RM8.43, RM8.48...
And at RM8.42: gross=RM42,100; broker fee=RM42.10; clearing=RM12.63; stamp=RM43; net≈RM42,002.27; P/L≈+RM5.80
And the RM8.42 row is highlighted as "Break-even"
And the disclaimer "Calculations informational only. Settlement T+2." is visible
```

**Alternate: partial sale**
```gherkin
Given CIMB: 5,000 shares, total all-in cost RM41,996.47
When I set "shares to sell" to 2,000
Then proportional all-in cost = (2,000/5,000) × RM41,996.47 = RM16,798.59
And all scenarios use 2,000 shares and RM16,798.59 as the buy cost basis
```

---

## US-017 / FR-013 — Dividend Calendar

**[NEW: Acceptance criteria were absent from the original BAS.]**

**Happy Path**
```gherkin
Given I have logged dividend tranches with ex-dates for multiple positions
When I open the dividend calendar
Then entries appear in chronological order by ex_dividend_date
And entries within the next 7 days are highlighted
And past entries show a "Paid" badge
And each entry shows: stock name, tranche label, ex-date, payment date, per_share_amount, total_amount (qualifying_shares basis)
```

**Empty state**
```gherkin
Given I have positions but no ex-dates entered
When I open the dividend calendar
Then I see: "Add ex-dates when logging dividends to see your payment schedule here"
```

---

## US-018 / FR-014 — CSV Import

**Happy Path**
```gherkin
Given a correctly formatted CSV with 16 positions and 34 dividend tranche records
When I upload the file
Then all 16 positions are created with correct share counts, prices, brokers, and all-in costs
And all 34 tranches are created with correct per_share_amount, qualifying_shares, and total_amount
And the dashboard shows the full portfolio with calculated yields
And a banner reads: "Import complete — 16 positions and 34 dividend records imported"
And the import completes within 30 seconds
```

**Error: missing required column**
```gherkin
Given the CSV is missing the "purchase_price" column header
When the system validates the file
Then I see: "Import failed: Required column 'purchase_price' is missing. No records were imported."
And my existing portfolio is unchanged
```

---

## US-019 / FR-015 — CSV Template Download

**[NEW: Acceptance criteria were absent from the original BAS.]**

**Happy Path**
```gherkin
Given I am on the Import page
When I click "Download Template"
Then a file named "BursaTrack_Import_Template.csv" downloads
And it contains: a header row with all required column names, a guide row describing each field, one example data row
And the Dividends sheet columns include "qualifying_shares" (optional)
```

---

## US-020 / FR-016 — Subscription

**Happy Path: subscribe**
```gherkin
Given my 14-day trial has expired
When I log in
Then I see the paywall screen with portfolio visible in read-only mode
When I click "Subscribe", complete payment, and return
Then my account status changes to "active"
And I have full access to all features
```

**Happy Path: cancel**
```gherkin
Given I am a paying subscriber with renewal on 2026-08-01
When I cancel on 2026-07-15
Then I see: "Your subscription ends on 1 Aug 2026. Your data will be preserved."
And I retain full access until 2026-08-01
And on 2026-08-02 my account becomes read-only
```

---

## US-021 / FR-017 — Password Reset

**[NEW: User story and AC for new FR-017.]**

**Happy Path**
```gherkin
Given a registered user with email "ahmad@email.com"
When they enter "ahmad@email.com" on the Forgot Password page and submit
Then they see: "If an account with that email exists, a reset link has been sent."
And they receive an email with a reset link valid for 1 hour
When they click the link within 1 hour and enter new password "NewPass2026" (confirmed)
Then their password is updated
And all their existing sessions are invalidated
And they are redirected to the login page with: "Password updated successfully. Please log in."
```

**Error: expired token**
```gherkin
Given a reset link that was generated more than 1 hour ago
When the user clicks the link
Then they see: "This reset link has expired. Request a new one?"
```

**Security: account enumeration prevention**
```gherkin
Given email "nonexistent@email.com" is not registered
When a user submits this email on the Forgot Password page
Then they see the identical message: "If an account with that email exists, a reset link has been sent."
And no email is sent
And there is no observable difference in response time between registered and unregistered emails
```

---

## US-022 / FR-018 — PDPA Data Export

**[NEW: User story and AC for new FR-018.]**

**Happy Path**
```gherkin
Given I am logged in (any account status)
When I navigate to Account Settings and click "Download My Data"
Then a ZIP file named "BursaTrack_DataExport_[YYYY-MM-DD].zip" downloads
And the ZIP contains: account.csv, positions.csv, lots.csv, dividend_tranches.csv, price_overrides.csv, audit_log.csv
And the export event is recorded in my audit log
```

---

## US-023 / FR-019 — Account Deletion

**[NEW: User story and AC for new FR-019.]**

**Happy Path**
```gherkin
Given I am logged in
When I navigate to Account Settings, click "Delete My Account", skip the data download, type "DELETE", and confirm
Then my account status becomes "pending_deletion"
And I receive a confirmation email with a cancellation link valid for 30 days
And I am logged out immediately
And I cannot log in during the 30-day period
When 30 days pass without cancellation
Then all my data is permanently deleted
And my email address is freed for re-registration
```

**Alternate: cancel deletion within 30 days**
```gherkin
Given my account is in "pending_deletion" status
When I click the cancellation link in the confirmation email within 30 days
Then my account is restored to its previous status
And I can log in again with no data lost
```

---

# 5. BUSINESS RULES

---

## BR-001 — Percentage-Based Brokerage Fee

**Rule Name:** Percentage Brokerage Calculation

**Description:** For brokers with a percentage-based fee: brokerage = MAX(initial_amount × rate, minimum_fee). Applied per lot transaction, not per position (see BR-003).

**Rule Type:** Calculation Rule

**Example:**
- Maybank Investment (0.10%, min RM8): RM41,900 × 0.001 = RM41.90 → MAX(41.90, 8) = RM41.90
- Maybank Investment (0.10%, min RM8): RM3,000 × 0.001 = RM3.00 → MAX(3.00, 8) = RM8.00 (minimum applied)

---

## BR-002 — Flat-Fee Brokerage

**Rule Name:** Flat Brokerage Calculation

**Description:** For brokers with a flat fee per trade: brokerage = flat_fee, regardless of trade size.

**Rule Type:** Calculation Rule

**Example:**
- MooMoo (RM3 flat): any trade size → brokerage = RM3.00

---

## BR-003 — Brokerage Applied Per Lot

**Rule Name:** Brokerage is Per Transaction (Per Lot)

**Description:** The brokerage fee is applied once per lot transaction. If a user buys CIMB on three separate dates (three lots), brokerage is charged three times — once per lot.

**Rule Type:** Calculation Rule

**Example:**
- Lot 1: 5,000 shares at RM8.38 → brokerage on RM41,900
- Lot 2: 2,000 shares at RM9.00 → brokerage on RM18,000
- Total brokerage ≠ brokerage on combined RM59,900

---

## BR-004 — Sell-Side Brokerage

**Rule Name:** Sell Brokerage Uses Same Rules as Buy

**Description:** The sell calculator applies the same brokerage rules to gross sell proceeds. Brokerage fee on sale = MAX(gross_proceeds × rate, minimum) for percentage brokers; flat_fee for flat-fee brokers.

**Rule Type:** Calculation Rule

**Example:**
- Sell RM42,100 with Maybank (0.10%, min RM8) → RM42.10

---

## BR-005 — Clearing Fee

**[FIXED: Original BR-005 stated the RM1,000 cap was "not relevant" and did not document it. The cap is a real regulatory rule and must be documented even if not triggered at current portfolio sizes.]**

**Rule Name:** Clearing Fee Calculation

**Description:** Clearing fee = initial_amount × 0.03% on BUY, or gross_proceeds × 0.03% on SELL. No minimum. Regulatory cap: RM1,000 per contract (triggered at contract values ≥ RM3,333,333). At current portfolio sizes (max RM89,200 for CARLSBG), the cap is not triggered. The cap is documented here for completeness — the system should validate that calculated clearing fee does not exceed RM1,000 for any single lot.

**Rule Type:** Calculation Rule

**Example:**
- RM41,900 × 0.0003 = RM12.57 (rounded per BR-025) → well below the RM1,000 cap

---

## BR-006 — Stamp Duty

**Rule Name:** Stamp Duty Calculation

**Description:** Stamp duty = ROUNDUP(initial_amount / 1000, 0) on BUY, or ROUNDUP(gross_proceeds / 1000, 0) on SELL. Minimum RM1. Rate is 0.10% (RM1 per RM1,000), gazetted until 12 July 2028. The rate is stored in a configurable system setting (see BR-015).

**Rule Type:** Calculation Rule

**Example:**
- RM41,900 → ROUNDUP(41.9, 0) = 42 → RM42.00
- RM3,000 → ROUNDUP(3.0, 0) = 3 → RM3.00
- RM500 → ROUNDUP(0.5, 0) = 1 → RM1.00 (minimum)

---

## BR-007 — All-In Cost Composition

**Rule Name:** All-In Cost Definition

**Description:** All-in cost per lot = initial_amount + brokerage_fee + clearing_fee + stamp_duty. All components are individually rounded before summing (see BR-025). This is the true cost of acquiring the lot and is the correct basis for yield calculation.

**Rule Type:** Calculation Rule

**Example:**
- CIMB: RM41,900.00 + RM41.90 + RM12.57 + RM42.00 = RM41,996.47

---

## BR-008 — Yield Denominator

**Rule Name:** Yield Uses All-In Cost

**Description:** Dividend yield = total_dividend_income / total_all_in_cost. The denominator must be the all-in cost (BR-007), not the pre-fee initial amount. Using the pre-fee amount overstates yield.

**Rule Type:** Calculation Rule

**Example:**
- CIMB: RM2,337.50 / RM41,996.47 = 5.57% (correct)
- NOT: RM2,337.50 / RM41,900 = 5.58% (incorrect — pre-fee denominator)

---

## BR-009 — Dividend Total Amount: Stored at Logging Time

**[FIXED — CRITICAL: Original BR-009 said total_amount was derived at read time from position_total_shares. This causes retroactive corruption when new lots are added after a dividend is logged. A user holding 5,000 shares who later adds 2,000 more would see their historical dividend total inflate from RM1,000 to RM1,400 — income they never received. The fix stores total_amount at logging time using qualifying_shares. See CI-001 in the companion analysis document for the full defect description and worked example.]**

**Rule Name:** Dividend Total Amount Is Stored at Logging Time, Using Qualifying Shares

**Description:** When a DividendTranche is created, the system stores:
1. `per_share_amount` — the declared dividend per share (MYR, up to 6 decimal places)
2. `qualifying_shares` — the number of shares that entitled the user to this dividend (defaults to position_total_shares at the moment of logging; user may override — see BR-027)
3. `total_amount` — calculated as `per_share_amount × qualifying_shares` and **stored** at this moment

`total_amount` is a stored value, not a derived value. It does NOT recompute when position_total_shares changes. It only changes when the user explicitly edits the tranche (which is audit-logged).

**Rule Type:** Calculation Rule

**Example (the defect scenario, now handled correctly):**
- 15 Jan 2026: User holds 5,000 CIMB shares. Logs 1st dividend: per_share=RM0.20, qualifying_shares=5,000, total_amount = RM0.20 × 5,000 = **RM1,000.00** (stored).
- 1 Jun 2026: User buys 2,000 more CIMB shares. Position total_shares becomes 7,000.
- Dashboard: 1st tranche total_amount remains **RM1,000.00** (the stored value). The RM1,000 income correctly reflects what the user actually received.

---

## BR-010 — Position Total Shares

**Rule Name:** Total Shares Is Sum of All Active Lots

**Description:** position_total_shares = SUM(shares) across all non-deleted lots for that position.

**Rule Type:** Calculation Rule

---

## BR-011 — Position All-In Cost

**Rule Name:** Position All-In Cost Is Sum of All Active Lots

**Description:** position_total_all_in_cost = SUM(all_in_cost) across all non-deleted lots for that position.

**Rule Type:** Calculation Rule

---

## BR-012 — Position Dividend Income

**[FIXED: Original used "SUM(dividend_per_share × position_total_shares)" which would be wrong with the BR-009 fix. Updated to use stored total_amount.]**

**Rule Name:** Position Dividend Income Is Sum of Stored Tranche total_amounts (Current Year)

**Description:** position_total_dividend_income = SUM(DividendTranche.total_amount) across all non-deleted DividendTranche records for the position where year = current calendar year.

**Rule Type:** Calculation Rule

**Example:**
- CIMB 1st tranche: total_amount = RM1,000.00 (stored)
- CIMB 2nd tranche: total_amount = RM987.50 (stored)
- CIMB 3rd tranche: total_amount = RM350.00 (stored)
- Position total dividend income YTD = RM1,000 + RM987.50 + RM350 = RM2,337.50

---

## BR-013 — Portfolio Blended Yield

**Rule Name:** Portfolio Yield Is Aggregate Income / Aggregate Cost

**Description:** portfolio_blended_yield = SUM(all positions' dividend_income_ytd) / SUM(all positions' all_in_cost). Portfolio-weighted, not arithmetic average of individual yields.

**Rule Type:** Calculation Rule

**Example:**
- CIMB: income RM2,337.50, cost RM41,996.47
- MAYBANK: income RM3,100.00, cost RM59,837.61
- Blended yield = RM5,437.50 / RM101,834.08 = 5.34%

---

## BR-014 — Dividend Tranche Limit

**Rule Name:** Maximum 8 Dividend Tranches Per Position Per Calendar Year

**Description:** A position may have at most 8 DividendTranche records with the same year value. Attempting to add a 9th is blocked with an error message.

**Rule Type:** Validation Rule

---

## BR-015 — Stamp Duty Rate Configurability

**Rule Name:** Stamp Duty Rate Is Externally Configurable

**Description:** The stamp duty rate (currently RM1/RM1,000, i.e., 0.10%) is stored in a configurable system setting, not hard-coded. This allows the rate to be updated without a code deployment when the gazette changes (next review date: 12 July 2028).

**Rule Type:** Compliance Rule

---

## BR-016 — Login Rate Limiting

**Rule Name:** Account Lockout After 5 Failed Login Attempts

**Description:** 5 failed login attempts within a 10-minute window from the same IP address locks the account for 10 minutes. Error message is generic. Counter resets on successful login.

**Rule Type:** Permission Rule

---

## BR-017 — Trial Period Duration

**Rule Name:** Free Trial Is 14 Calendar Days

**Description:** Trial begins at account creation and expires exactly 14 calendar days later (at midnight MYT on day 14). All features accessible during trial.

**Rule Type:** Workflow Rule

**Assumption:** 14-day duration is assumed pending stakeholder confirmation. See Open Items.

---

## BR-018 — Portfolio Data Preservation

**Rule Name:** Portfolio Data Persists Through All Account State Changes

**Description:** Portfolio data is never deleted due to trial expiry or subscription cancellation. Data is preserved in read-only state until explicitly deleted by the user (FR-019).

**Rule Type:** Workflow Rule

---

## BR-019 — Session Expiry

**Rule Name:** Sessions Expire After 30 Days of Inactivity

**Description:** A user session expires if no authenticated request is made within 30 consecutive calendar days. Session tokens are HTTP-only, Secure, and SameSite cookies.

**Rule Type:** Compliance Rule

---

## BR-020 — T+2 Settlement Disclosure

**Rule Name:** Sell Calculator Must Display T+2 Settlement Notice

**Description:** The sell scenario calculator must display on every result page: "Calculations are informational only. BursaTrack is not a financial advisor. Settlement on Bursa Malaysia is T+2 — cash from a sale is available two trading days after the trade date." This disclosure is non-dismissable.

**Rule Type:** Compliance Rule

---

## BR-021 — Financial Disclaimer

**Rule Name:** Financial Disclaimer on All Calculated Outputs

**Description:** All pages displaying yield, profit/loss, or scenario calculations must include: "BursaTrack is a portfolio tracking tool and does not provide financial advice. All calculations are informational only." This disclaimer must be permanently visible.

**Rule Type:** Compliance Rule

---

## BR-022 — CSV Import Atomicity

**Rule Name:** CSV Import Is All-or-Nothing

**Description:** A CSV import either creates all records successfully or creates none. If any row fails validation, the entire import is rolled back.

**Rule Type:** Workflow Rule

---

## BR-023 — Price Override Supersession

**Rule Name:** Manual Price Overrides Are Superseded by Automated Refresh

**Description:** When automated refresh successfully returns a price for a stock with a manual override, the automated price replaces the manual override. The manual price is stored in audit log but is no longer the active price.

**Rule Type:** Workflow Rule

---

## BR-024 — Proportional Cost for Partial Sell

**Rule Name:** Partial Sale All-In Cost Is Proportional (Weighted Average)

**Description:** In the sell calculator, when selling fewer shares than the total position, the all-in buy cost basis = (shares_to_sell / total_position_shares) × position_total_all_in_cost. This is a weighted average approach — FIFO or LIFO lot-level accounting is NOT implemented at V1.

**Rule Type:** Calculation Rule

**Example:**
- CIMB: 5,000 shares, total all-in cost RM41,996.47
- Sell 2,000 shares → (2,000/5,000) × RM41,996.47 = RM16,798.59

---

## BR-025 — MYR Amount Rounding Convention

**[NEW: No rounding convention was defined anywhere in the original BAS. Required for deterministic fee calculations across all implementations.]**

**Rule Name:** All MYR Amounts Rounded Half Away From Zero to 2 Decimal Places

**Description:**
- All MYR monetary amounts are stored with exactly 2 decimal places.
- Rounding method: **round half away from zero** (i.e., RM12.565 → RM12.57; RM12.564 → RM12.56).
- Each fee component (brokerage, clearing, stamp duty) is individually rounded to 2dp before being summed into all-in cost. The sum is not rounded separately — it is already in 2dp by composition of 2dp components.
- Stamp duty (BR-006) uses ROUNDUP, which always produces a whole number — no further rounding needed.
- total_amount on DividendTranche = per_share_amount × qualifying_shares, rounded to 2dp.
- Unrealised P&L = current_market_value − total_all_in_cost, where current_market_value = total_shares × current_price, rounded to 2dp.

**Rule Type:** Calculation Rule

**Worked example (rounding boundary):**
- Clearing fee for a RM41,666.67 lot: RM41,666.67 × 0.0003 = RM12.50001 → rounded to **RM12.50**
- Clearing fee for a RM41,833.33 lot: RM41,833.33 × 0.0003 = RM12.55 → stored as **RM12.55**
- Clearing fee for a RM41,916.67 lot: RM41,916.67 × 0.0003 = RM12.575 → rounded to **RM12.58** (half away from zero)

---

## BR-026 — Currency and Field Precision Rules

**[NEW: No currency or precision rules were stated in the original BAS. Required for unambiguous data model and API design.]**

**Rule Name:** All Amounts Are MYR; Precision Rules by Field Type

**Description:**

| Field Type | Storage Precision | Display Precision | Notes |
|------------|------------------|-------------------|-------|
| MYR monetary amounts (fees, costs, dividends) | 2 decimal places | 2 decimal places | e.g., RM41,996.47 |
| MYR price per share | 4 decimal places | 2 decimal places (with 4dp available on hover) | e.g., stored RM8.3800, displayed RM8.38 |
| Dividend per share | 6 decimal places | 4 decimal places | e.g., RM0.004813 stored; RM0.0048 displayed |
| Yield percentage | 4 decimal places | 2 decimal places | e.g., stored 5.5660, displayed 5.57% |
| Share count | Integer (no decimals) | Integer | — |
| Qualifying shares | Integer (no decimals) | Integer | — |

**Currency:** All amounts are Malaysian Ringgit (MYR). No multi-currency support at V1.

**Rule Type:** Calculation Rule

---

## BR-027 — Qualifying Shares Semantics

**[NEW: Required by the BR-009 fix. Defines qualifying_shares field, its default value, its immutability after creation, and its relationship to total_amount.]**

**Rule Name:** Qualifying Shares Represents the Share Count Entitled to a Specific Dividend

**Description:**
- `qualifying_shares` on a DividendTranche record represents the number of shares the user held before the ex-dividend date and therefore qualified to receive this specific dividend.
- **Default value:** position_total_shares at the exact moment the tranche is logged. This is the most common case (user logs the dividend while holding all their shares).
- **User override:** The user may edit the qualifying_shares field at logging time or later (e.g., if they know they held fewer shares before the ex-date than they hold today). The field must be ≥ 1 and ≤ position_total_shares at the time of the entry.
- **Immutability of total_amount:** After creation, total_amount does NOT change unless the user explicitly edits the tranche. Adding new lots to the position does NOT change any existing tranche's total_amount.
- **Audit:** Any change to qualifying_shares or total_amount is audit-logged with the previous values, new values, and the user's ID.

**Rule Type:** Calculation Rule

**Example:**
- User holds 5,000 CIMB on 1 Mar 2026. On 15 Jun 2026 they buy 2,000 more. They log the 1st dividend on 20 Jun 2026.
- At logging time, position_total_shares = 7,000. Default qualifying_shares = 7,000.
- **However**, if the ex-date was 28 Feb 2026 (before the additional 2,000 shares were purchased), only 5,000 shares qualified.
- The user should override qualifying_shares to 5,000 at logging time.
- If they don't, total_amount = RM0.20 × 7,000 = RM1,400 (overstated by RM400).
- The system provides a qualifying_shares field and guidance, but cannot automatically verify the ex-date share count without historical lot dates.

---

*End of Part 1 (Sections 1–5). Continue in BursaTrack-BAS-Enhanced-Part2.md.*
