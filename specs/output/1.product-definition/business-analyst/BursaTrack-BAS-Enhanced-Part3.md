# BursaTrack — Enhanced Business Analyst Specification
## Part 3 of 3: Sections 10–15

> **Version:** 2.0 — Enhanced
> **Date:** 2026-06-21
> **Annotation key:** `[FIXED: reason]` | `[NEW: reason]` | No annotation = KEEP
> **Continuation of Part 2 (Sections 6–9)**

---

# 10. EXCEPTION HANDLING

---

## EX-001 — Price Feed Complete Outage

**Cause:** The automated price refresh job cannot connect to the data provider (yfinance) for all stocks.

**Detection:** The refresh job records a failed response for all queried stock codes.

**System Behaviour:**
1. All PriceSnapshot records that were due for refresh are marked `source = "stale"`.
2. No existing price data is overwritten.
3. Within 5 minutes: a dashboard status banner appears: "Price data unavailable — showing prices as of [last successful refresh timestamp]. Update prices manually below."
4. Each position displays a stale indicator icon adjacent to its price.
5. Manual price override fields are activated for all positions.
6. The "Last refreshed" timestamp is NOT updated (retains the last successful refresh time).

**User-Facing Message:** "Price data is currently unavailable from our data provider. Prices shown are as of [date/time]. You can enter prices manually until the feed is restored."

**Recovery:** On the next successful automated refresh, all stale flags are cleared, manual overrides are superseded (BR-023), and the "Last refreshed" timestamp updates.

**Risk Note:** yfinance is an unofficial API. This failure mode is higher-probability than for commercial data providers. The system must be designed to handle this gracefully as a routine operational event, not an exceptional one.

---

## EX-002 — Price Feed Partial Failure

**Cause:** The automated refresh returns valid prices for some stocks but fails for others (e.g., 14 of 16 stocks successful; CARLSBG and LPI failed).

**System Behaviour:**
1. Successful stocks: PriceSnapshot updated to `source = "automated"`.
2. Failed stocks: PriceSnapshot marked `source = "stale"`.
3. Dashboard banner: "Price data unavailable for 2 stocks — CARLSBG, LPI. Showing last known prices."
4. Only the affected positions show stale indicators and manual override fields.
5. "Last refreshed" timestamp updates (reflecting the partial success).

**Recovery:** Same as EX-001 for the affected stocks.

---

## EX-003 — Price Feed Returns Clearly Invalid Data

**Cause:** The feed returns a price of RM0.00, a negative value, or a value more than 50% different from the previous day's price.

**System Behaviour:**
1. The system rejects the response as invalid and treats the stock as failed (same path as EX-002 for that stock).
2. The invalid price is NOT written to PriceSnapshot.
3. The stock is marked stale with a manual override option.

**Rationale:** A price spike of >50% in one day is highly unlikely for Bursa equities and is more likely a data error. The threshold of 50% is a configuration parameter (default: 50%).

---

## EX-004 — CSV Import Validation Failure

**Cause:** Uploaded CSV file contains one or more rows that fail validation.

**System Behaviour:**
1. Import is halted at the validation phase. No records are created (BR-022).
2. The system returns a row-level error report listing every failing row and the specific validation error.
3. User can download an error report and correct the CSV.
4. User can re-upload the corrected file.

**User-Facing Message:** "Import failed: [N] rows contain errors. Please correct the errors below and re-upload. No records have been imported."

---

## EX-005 — CSV Import Transaction Failure

**Cause:** The CSV passes validation but a database error occurs during the atomic create transaction.

**System Behaviour:**
1. The transaction is rolled back. No partial data is written.
2. User is shown a generic error: "Import failed due to a system error. Please try again. If the problem persists, contact support. Your existing portfolio has not been affected."
3. The error is logged server-side with the full stack trace and the user's email (for support purposes).

---

## EX-006 — Payment Processor Failure During Subscription

**Cause:** The payment processor returns an error or times out during the subscribe flow.

**System Behaviour:**
1. Account status is NOT changed (remains `trial`, `trial_expired`, or `active` as appropriate).
2. User is returned to the subscription page with: "Payment could not be processed. Please try again or use a different payment method."
3. No charge is applied.

**Recovery:** User can reattempt payment. The subscription page remains accessible.

---

## EX-007 — Email Delivery Failure (Registration Verification)

**Cause:** The email delivery service fails to deliver the account verification email.

**System Behaviour:**
1. The account is created and the user can log in with reduced-privilege access (dashboard accessible; email-verification reminder persisted as a banner).
2. A "Resend verification email" button is available on the dashboard.
3. The email failure is logged server-side for delivery-service monitoring.

**User-Facing Message (on dashboard):** "Verification email could not be sent. Click 'Resend' to try again."

**Note:** The user is NOT blocked from using BursaTrack during the trial period just because email verification has not been completed. The email verification is a security measure, not a registration gate.

---

## EX-008 — Concurrent Edit Conflict

**Cause:** Two sessions (e.g., the same user on two browsers) attempt to edit the same Lot or DividendTranche simultaneously.

**System Behaviour:**
1. The system uses optimistic locking (last-write-wins with a conflict notification, or check-then-update with a version field).
2. On conflict detection: the second write is rejected. The user is shown: "This record was updated by another session. Please refresh the page to see the latest values before making changes."

---

## EX-009 — Account Lockout (Brute Force)

**Cause:** 5 failed login attempts within 10 minutes from the same IP address (BR-016).

**System Behaviour:**
1. All further login attempts from the IP address are blocked for 10 minutes with a generic error.
2. The lockout event is logged.
3. After 10 minutes: the lockout lifts automatically. No user action required.

**User-Facing Message:** "Too many failed attempts. Please wait 10 minutes before trying again."

---

## EX-010 — Session Expiry Mid-Session

**Cause:** A user's session has expired (30 days of inactivity) while the user has the app open in a browser tab.

**System Behaviour:**
1. The next API request returns HTTP 401.
2. The app redirects the user to the login page with: "Your session has expired. Please log in again."
3. No data is lost. The user logs in and is returned to the last page they were viewing.

---

## EX-011 — Email Delivery Failure (Password Reset)

**[NEW: Email delivery failure for password reset flow was absent from the original BAS. Password reset (FR-017) is a new FR; this exception is a required companion.]**

**Cause:** The email delivery service fails to deliver the password reset email after the user submits the Forgot Password form.

**System Behaviour:**
1. The password reset token IS generated and stored server-side (so it can be retried).
2. The user sees the standard response: "If an account with that email exists, a reset link has been sent." (This message is intentionally indistinguishable from a successful send — changing it on failure would reveal whether the email exists.)
3. Internally: the failure is logged server-side with the user's email (for support monitoring).
4. **Recovery option:** If the user does not receive an email and contacts support, support can resend the token (V1 internal admin tooling requirement — logged as an open item; see Open Items).

**Note on security vs. usability trade-off:** The user has no way to distinguish a delivery failure from a "no account found" case. This is intentional — disclosing a delivery failure would confirm that an account exists for the email address, enabling enumeration attacks. Support escalation is the recovery path.

---

# 11. EDGE CASES

---

## EC-001 — Duplicate Position (Same Stock Added Twice via Add Position)

**Description:** User attempts to add a stock code that already exists as a position in their portfolio via the "Add Position" form (rather than "Add Lot").

**Behaviour:** If the stock code already exists as an active Position in the user's portfolio, the system treats the new entry as an "Add Lot" action on the existing position rather than creating a duplicate Position. The user is notified: "You already have a [Stock Name] position. This lot has been added to your existing position."

**Exception to this rule:** If the user has deleted the previous position (soft-deleted), creating a new position with the same stock code creates a fresh Position record (the soft-deleted record is retained for audit purposes but is not considered active).

---

## EC-002 — Zero-Brokerage Scenario

**Description:** User enters a trade where brokerage fee calculates to RM0.00 (e.g., a hypothetical RM0 flat-fee broker, or a custom broker with rate = 0).

**Behaviour:** System allows it. All-in cost = initial_amount + RM0 brokerage + clearing + stamp duty. No error is thrown for zero brokerage (it is valid). The system should display the RM0 brokerage component without hiding it.

---

## EC-003 — Stamp Duty Minimum (Below RM1,000 Trade)

**Description:** Trade value is below RM1,000, making ROUNDUP(amount/1000, 0) = 1 (RM1 minimum).

**Behaviour:** Stamp duty = RM1. This is the correct regulatory minimum. Verified: RM500 → ROUNDUP(0.5, 0) = 1 → RM1.

---

## EC-004 — Purchase Date on a Non-Trading Day (Weekend or Holiday)

**Description:** User enters a purchase date of a Saturday, Sunday, or Bursa public holiday.

**Behaviour:** The system accepts the date with a soft warning: "Note: [date] is not a Bursa trading day. Please verify the purchase date." The entry is not blocked — users may have off-market transactions or may be correcting historical data where they are uncertain of the exact date.

---

## EC-005 — Position with No Current Price

**Description:** A position exists but the price data provider has never returned a valid price for that stock code (e.g., a newly listed stock not yet in the feed, or a data provider limitation).

**Behaviour:** Current market value and unrealised P&L are displayed as "—" (not RM0.00) with a tooltip: "Price not available." The position remains fully functional for dividend tracking and cost basis recording.

---

## EC-006 — Dividend Logged After Position Deletion

**Description:** User attempts to log a dividend tranche for a position they have soft-deleted.

**Behaviour:** Not permitted. The dividend form is only accessible from active positions. The soft-deleted position is not visible in the dashboard, so this can only occur via a direct API call. Server-side validation returns HTTP 404 for requests targeting deleted positions.

---

## EC-007 — Import CSV with Stock Already in Portfolio

**Description:** User uploads a CSV that includes a stock code that already exists as an active Position in their portfolio.

**Behaviour:** Two sub-cases:
1. **Conflict resolution required:** By default, the system does not allow a duplicate position to be created. If the CSV includes a stock already in the portfolio, the row is flagged in the validation error report: "Row [N]: Position for [Stock] already exists in your portfolio. Use 'Add Lot' instead, or delete the existing position before importing."
2. **Alternative path (to be confirmed):** A "replace existing" import mode could be offered. This is deferred to V1.1. At V1, the import simply rejects duplicates.

---

## EC-008 — CSV Import with Tranche Label Conflict

**Description:** CSV contains two rows for the same stock and the same tranche label (e.g., two "1st" tranches for CIMB in the same year).

**Behaviour:** The validation phase catches this: "Row [N]: Duplicate tranche label '1st' for [Stock] in [Year]. Each tranche label can only be used once per stock per year." No records are created.

---

## EC-009 — Sell Calculator: Zero All-In Cost

**Description:** A position's all-in cost calculates to RM0.00 (theoretically possible if all lots are zero-value — should not occur in practice but must not cause a division-by-zero in profit/loss calculations).

**Behaviour:** If all_in_cost = RM0.00, the sell calculator displays profit_loss = net_proceeds (since the buy basis is zero) and yield is shown as "—" with a tooltip: "Cost basis is zero; yield cannot be calculated."

---

## EC-010 — Dividend Yield > 100%

**Description:** Total dividend income for a year exceeds the all-in cost of the position (theoretical edge case for very cheap stocks paying large special dividends, or data entry errors).

**Behaviour:** The system calculates and displays the yield as-is (e.g., 134.7%). No error is thrown. A soft warning may be displayed: "This yield appears unusually high. Please verify your dividend entries." The user can dismiss or ignore the warning.

---

## EC-011 — Price Refreshed for Stocks Not Currently in Portfolio

**Description:** A user deletes their only CIMB position. The next price refresh job runs.

**Behaviour:** The price refresh job collects unique stock codes from active (non-deleted) positions only. CIMB is not included in the refresh job after its position is deleted. Existing PriceSnapshot records for CIMB are retained (they are shared across portfolios and are not user-specific).

---

## EC-012 — Trial Account Adds More Than [N] Positions

**Description:** A trial user adds a large number of positions before subscribing.

**Behaviour:** No position limit is applied to trial accounts at V1. Trial users have access to all features with the only restriction being the 14-day time limit. (Feature gating limits are a V1.1 consideration — see Open Items.)

---

## EC-013 — Concurrent Portfolio Access (Same Account, Two Sessions)

**Description:** A user is logged in on two devices simultaneously and edits data in both sessions.

**Behaviour:** See EX-008 (optimistic locking). The first write succeeds; the second write on the same record is detected as a conflict and the user is prompted to refresh.

---

## EC-014 — Lot Added with a Purchase Date Earlier Than Previous Lots

**Description:** User adds Lot #3 with a purchase date that is before Lot #1 or Lot #2 (i.e., out of chronological order).

**Behaviour:** Lots are not required to be entered in chronological order. The system accepts the new lot, recalculates position aggregates correctly (order is irrelevant for aggregate cost basis), and displays lots in the order of their purchase_date.

---

## EC-015 — User Edits a Lot After Dividends Have Been Logged

**Description:** User edits a lot's share count from 5,000 to 4,000. Three dividend tranches have already been logged for the position.

**Behaviour:**
- position_total_shares is updated to reflect the new lot share count.
- The three existing DividendTranche.total_amount values remain UNCHANGED (they were stored with qualifying_shares at the time of logging — see BR-027).
- Yield recalculates: the new (lower) all-in cost reduces the denominator, potentially increasing yield, while dividend income (based on stored total_amounts) remains the same.
- A dashboard notification appears: "Position updated. Existing dividend records were not changed. If the share count correction affects your dividend entitlements, please edit the relevant dividend tranches."

---

## EC-016 — User Enters a Dividend for a Past Calendar Year

**Description:** User logs a dividend for CIMB with payment_date in 2024 and year = 2024.

**Behaviour:** System accepts this. The dividend is counted toward 2024's tranche total (not 2025 or 2026). The "YTD" dividend income displayed on the dashboard uses `year = current calendar year` — so a 2024 dividend does NOT appear in the current-year dashboard total. It is visible in a per-position historical view. (This behaviour should be confirmed with the Product Owner — see Open Items regarding calendar year vs. stock financial year.)

---

## EC-017 — User Requests Password Reset for Unverified Email Account

**Description:** A user registered but never verified their email, and then tries to reset their password.

**Behaviour:** The password reset flow proceeds normally. The system sends a reset email to the unverified address. On successful password reset, the email is also considered verified (since the user has demonstrated control of the email address by clicking the reset link).

---

## EC-018 — Account Deletion Requested While Subscription Is Active

**Description:** User requests account deletion (FR-019) while they have an active paid subscription.

**Behaviour:**
1. The deletion request is accepted. Account enters `pending_deletion` state.
2. No further billing charges are made from the deletion request date.
3. If the user cancels the deletion within 30 days, the subscription is reinstated at its last state. If the billing period passed during the 30-day window, the subscription is treated as having been cancelled (does not auto-renew).
4. The system does NOT issue a prorated refund at V1. Refund policy is a stakeholder decision — see Open Items.

---

## EC-019 — Import File Encoding Issues

**Description:** User uploads a CSV file that contains non-UTF-8 characters (e.g., special Malaysian stock names with non-ASCII characters).

**Behaviour:** The system attempts to detect encoding (UTF-8, then Windows-1252). If the file cannot be decoded, the user is shown: "File encoding error. Please save your CSV as UTF-8 before uploading." The import is not attempted.

---

## EC-020 — Manual Price Override After Subscription Expiry

**Description:** A trial-expired (read-only) user's portfolio shows stale prices. The user cannot enter manual prices because write actions are blocked.

**Behaviour:** Manual price entry is a write action and is blocked for trial-expired accounts (see Permission Matrix, §9). The user sees the paywall prompt when they attempt to use the manual override field. The stale indicator remains visible.

---

## EC-021 — Delete Account That Has Already Been Verified and Subscribed

**Description:** A paid subscriber with verified email and active portfolio requests account deletion.

**Behaviour:** Standard FR-019 flow applies. All data enters the 30-day pending deletion period regardless of subscription status. See EC-018 for subscription billing treatment.

---

## EC-022 — Share Count Increases After Dividend Has Been Logged

**[NEW: This edge case was not in the original BAS. It is the core scenario addressed by the BR-009 qualifying_shares fix. Required to ensure QA explicitly tests the corrected invariant.]**

**Description:** User holds 5,000 CIMB shares. They log the 1st dividend tranche (RM0.20/share, qualifying_shares = 5,000, total_amount = RM1,000 stored). They then add 2,000 more CIMB shares (a new Lot).

**Behaviour:**
1. After adding the new Lot, CIMB position_total_shares = 7,000.
2. The existing 1st dividend tranche is **not recalculated**. qualifying_shares remains 5,000. total_amount remains RM1,000.
3. The dashboard shows CIMB total dividend income YTD = RM1,000 (not RM1,400).
4. CIMB yield = RM1,000 / new total all-in cost (denominator increases; yield decreases).

**Regression test:** This case must be in QA's automated regression suite. The wrong behaviour (total_amount inflating to RM1,400) is the original BR-009 defect.

---

## EC-023 — Yield Display When Qualifying Shares Differ From Current Position Total

**[NEW: New edge case arising from the qualifying_shares field. Covers the scenario where the user consciously logged a dividend with fewer qualifying_shares than their current position total — the system must display this transparently.]**

**Description:** User holds 7,000 CIMB shares. They log the 1st dividend tranche with qualifying_shares manually set to 5,000 (because they only held 5,000 at the ex-date). total_amount stored = RM0.20 × 5,000 = RM1,000.

**Behaviour:**
1. Dashboard shows CIMB 1st tranche total = RM1,000.
2. On the dividend tranche detail: the display shows "5,000 qualifying shares (current total: 7,000)" to make the discrepancy visible.
3. No warning or error is displayed — this is an intentional, valid override.
4. Yield = RM1,000 / CIMB total all-in cost (using 7,000-share position's full cost).

**Rationale:** The system must not conflate "qualifying_shares at ex-date" with "current position total." This edge case tests that the UI correctly surfaces the qualifying_shares annotation for QA and audit review.

---

# 12. ASSUMPTIONS

The following assumptions have been made during the analysis. If any assumption is invalidated, the dependent requirements and rules must be reviewed.

| # | Assumption | Impact if Wrong | Owner |
|---|------------|-----------------|-------|
| A-001 | Trial period is 14 calendar days | BR-017, FR-001, FR-016, US-001 AC would need updating | Product Owner |
| A-002 | All monetary amounts are MYR only; no multi-currency support at V1 | If multi-currency required, data model, fee calculations, and yield calculations all need rework | Product Owner |
| A-003 | Dividend tranche year is calendar year (Jan–Dec), not the stock's financial year | If financial-year bucketing is required, the year field, tranche limit (BR-014), and dashboard YTD total all need redesign | Product Owner |
| A-004 | Portfolio yield is blended (total income / total cost), not a simple average of individual yields | If the user wants per-position yield averaging, BR-013 and portfolio summary calculations change | Product Owner |
| A-005 | Partial sale all-in cost uses weighted average (BR-024), not FIFO or LIFO lot tracking | If FIFO/LIFO is required, the sell calculator needs per-lot fee attribution — a significant complexity increase | Product Owner |
| A-006 | The sell calculator default broker for multi-lot positions is the most recently added active lot's broker | If a different default logic is preferred (e.g., primary broker, or force user selection), FR-012 workflow step 3 changes | Product Owner |
| A-007 | SST (Sales and Retail Tax) is NOT applied to brokerage fees for BursaTrack transactions at V1 | If SST applies, a new fee component must be added to all-in cost calculations and the fee stack | Legal / Product Owner |
| A-008 | yfinance is the V1 price data source; no SLA or rate limit is contractually guaranteed | If a different data source is used, FR-007 (refresh schedule), FR-008 (failure handling), and EX-001–003 must be reviewed | Tech Lead |
| A-009 | The Bursa Malaysia trading calendar is maintained as a configurable system file (not a real-time API call) | If a real-time calendar API is used, the scheduling integration changes | Tech Lead |
| A-010 | Soft-delete is used for all user-created records (Position, Lot, DividendTranche) | If hard-delete is used, audit log and PDPA deletion flow designs change | Tech Lead |
| A-011 | PDPA account deletion provides a 30-day grace/cancellation period before permanent deletion | If the required PDPA deletion window is different, FR-019 and Workflow 9 must be updated | Legal |
| A-012 | Custom broker fee structures allow any percentage rate 0–2% and any minimum fee RM0–100 | If regulatory or product constraints impose different bounds, VR-014 must be updated | Product Owner |
| A-013 | Password reset tokens expire after 1 hour | If a longer or shorter expiry is preferred, FR-017 AC must be updated | Product Owner |
| A-014 | All price refresh jobs run at 5:30 PM MYT (after Bursa market close at 5:00 PM) | If a different refresh time is required, Workflow 3 schedule changes | Tech Lead / Product Owner |
| A-015 | No admin portal is required at V1; admin actions (e.g., resending reset emails, viewing delivery failures) are handled via support tooling outside the main application | If an admin portal is required, a third role (Admin) and its permission matrix must be specified | Product Owner |

---

# 13. OPEN QUESTIONS

The following items require a stakeholder decision and CANNOT be resolved by the BA alone. They are extracted from the ESCALATE findings and are the primary blockers to reaching a 9–10 readiness score.

| # | Question | Why It Can't Be Resolved by the BA | Recommended Owner | Recommended Next Action | Priority |
|---|----------|------------------------------------|-------------------|------------------------|---------|
| OQ-001 | **Trial period duration** — Is 14 calendar days correct? | Pricing/marketing decision | Product Owner | Confirm or adjust; update BR-017 and FR-001 | High |
| OQ-002 | **SST on brokerage** — Does the July 2025 Bursa FAQ confirm SST is exempt for retail brokerage fees on equity trades? | Legal / regulatory interpretation | Legal / Finance | Read the July 2025 Bursa FAQ immediately; if SST applies, add SST component to all-in cost formula | Critical |
| OQ-003 | **Dividend tranche year** — Calendar year (Jan–Dec) or stock's financial year? | Product decision affecting data model | Product Owner | Decide before dividend data model is implemented | High |
| OQ-004 | **Multi-lot yield method** — Confirmed as blended (total income / total cost). No further action needed. | _(Resolved — blended confirmed)_ | — | — | Closed |
| OQ-005 | **Sell calculator broker for multi-lot positions** — When a position has lots from different brokers, which broker's rate applies to the sell calculation? (Assumption A-006: most recent lot's broker.) | Product decision | Product Owner | Confirm default logic or require explicit user selection on the sell form | Medium |
| OQ-006 | **Rakuten Trade tiered fee structure** — Is V1 acceptable with a flat RM7 (ignoring the tier) or should tiered logic be in V1? | Product / engineering complexity trade-off | Product Owner + Tech Lead | Confirm V1 scope; document the simplification in the UI if flat is used | Medium |
| OQ-007 | **FR-017 Password Reset priority** — Is Must Have appropriate, or acceptable to defer to a fast-follow? | Product priority decision; auth-sprint scope | Product Owner | Formally sign off on Must Have or defer with explicit acceptance of the support burden | High |
| OQ-008 | **FR-018 PDPA Data Export V1 inclusion** — Is V1 the correct milestone, or is there a legal opinion that allows a short post-launch gap? | Legal compliance threshold decision | Legal + Product Owner | Get legal opinion on PDPA launch requirement timeline | Critical |
| OQ-009 | **FR-019 Account Deletion V1 inclusion** — Same as OQ-008 | Legal compliance threshold decision | Legal + Product Owner | Get legal opinion; confirm if 30-day grace period satisfies PDPA right of erasure | Critical |
| OQ-010 | **Subscription refund policy on account deletion (EC-018)** — No prorated refund at V1 is assumed. Is this the intended policy? | Pricing / terms-of-service decision | Product Owner + Legal | Define refund policy in T&C before launch; update EC-018 | Medium |
| OQ-011 | **Support tooling for password reset delivery failures (EX-011)** — Admin tooling to resend reset tokens: in-scope or out-of-scope for V1? | Product / engineering scope decision | Product Owner | If out-of-scope, document support escalation procedure | Low |
| OQ-012 | **CSV import conflict resolution** — When importing a stock already in the portfolio, should the system reject the row (current assumption) or offer a "merge" or "replace" mode? | Product UX decision | Product Owner | Decide before import sprint; EC-007 currently assumes reject-only at V1 | Medium |

---

# 14. TESTING READINESS

## Testing Approach

BursaTrack's calculation-heavy domain requires that every calculated output have a deterministic, numeric test case. The following test categories must be covered.

---

## Unit Test Requirements (Business Logic)

| Test Area | Key Test Cases | Priority |
|-----------|---------------|----------|
| Brokerage calculation | Percentage + minimum applied; flat fee; minimum not applied (large trade) | P1 |
| Clearing fee | Standard calculation; RM1,000 cap not triggered; cap trigger case | P1 |
| Stamp duty | Standard ROUNDUP; minimum RM1 case; exact RM1,000 boundary | P1 |
| All-in cost composition | All four components; correct sum | P1 |
| **Dividend total_amount (critical)** | Stored at logging; NOT recomputed when new lot added | **P0 — regression required** |
| Qualifying_shares default | Defaults to current position_total_shares | P1 |
| Qualifying_shares override | User override accepted; out-of-range rejected | P1 |
| Yield denominator | Uses all-in cost; does NOT use pre-fee initial amount | P1 |
| Portfolio blended yield | Weighted aggregate; not arithmetic average | P1 |
| Partial sale cost basis | Proportional weighted average | P1 |
| Sell break-even detection | Correct row highlighted; RM8.42 CIMB test case | P1 |
| Stamp duty configurability | Rate change takes effect without code deploy | P1 |
| Rounding convention | Half away from zero; each component rounded individually | P1 |

---

## Integration / Scenario Tests

| Scenario | Expected Outcome |
|----------|-----------------|
| Add lot → verify dividend total unchanged | EC-022: adding 2,000 CIMB shares does not change 1st tranche RM1,000 stored value |
| Edit lot shares → verify dividend total unchanged | EC-015: reducing shares from 5,000 to 4,000 does not change stored dividend total_amounts |
| CSV import with qualifying_shares column | Correct qualifying_shares stored; total_amount = per_share × qualifying_shares |
| CSV import without qualifying_shares column | Default qualifying_shares = position total shares |
| Stale price → manual override → automated refresh supersedes | Correct source transitions; manual price replaced by auto |
| Trial expiry → paywall → subscribe → full access | Account status transitions; no data loss |
| Password reset happy path | Token used, sessions invalidated, new password works |
| Password reset expired token | Error displayed; user can request new link |
| Account deletion → 30-day window → permanent deletion | All user data hard-deleted; email address freed |
| Account deletion → cancellation within 30 days | Account restored; no data deleted |
| PDPA data export | ZIP contains all 6 CSVs; audit log records the export |

---

## Security Test Cases

| Test | Requirement |
|------|-------------|
| Accessing another user's position by ID | Returns HTTP 404 |
| Accessing a deleted position by direct URL | Returns HTTP 404 |
| Rate limiting: 5 failed logins | Account locked for 10 min after 5th failure |
| Password reset: account enumeration | Identical response for found and not-found email |
| Session: cookie is HTTP-only and Secure | No JavaScript access to session token |
| Session: expiry after 30 days inactive | 401 returned; user redirected to login |
| Reset token reuse | Second use returns "already used" error |

---

## Performance Requirements (from PRD NFRs)

| Metric | Target | Test Method |
|--------|--------|-------------|
| Dashboard load time | < 3 seconds for up to 50 positions | Load test with 50 positions |
| CSV import | < 30 seconds for 500 rows | Benchmark test |
| Price refresh per stock | < 5 seconds per stock | Integration test against yfinance |
| Price refresh batch (16 stocks) | < 30 seconds total | End-to-end batch timing |

---

# 15. BA QUALITY REVIEW — ENHANCED DOCUMENT

## Self-Assessment: Enhanced Specification v2.0

**Confidence Score: 8.5 / 10**

**Summary counts:**
- KEEP: 52 items (unchanged; verified correct)
- FIX: 9 items (including 1 Critical — BR-009 retroactive dividend corruption)
- ADD: 23 items (missing requirements, workflows, AC, business rules, validation rules, exception handling, edge cases)
- ESCALATE: 12 items (11 genuine open questions + 1 closed as resolved)

---

## Change Summary Table

| Section/Item | Classification | Reason | MVP Note |
|---|---|---|---|
| FR-001 to FR-012 (all) | KEEP | Triggers, preconditions, flows, postconditions all correct and complete | — |
| FR-003 — Add Position (calculation steps) | KEEP | Fee formula correct; all components present | — |
| FR-004 — Add Lot (step 6 dividend note) | FIX | Ambiguous clause could be misread as re-deriving dividend totals from new share count | Critical correctness |
| FR-005 — Edit Position (new lot note) | NEW | Explicit clarification that editing lot share count does not change stored DividendTranche.total_amount | Ambiguity closure |
| FR-009 — Log Dividend (step 3a, 5) | FIX (CRITICAL) | Steps derived total_amount from live position_total_shares — retroactive corruption defect | CI-001 in analysis |
| FR-010 — Edit Dividend (edit flow steps 3–5) | FIX | Editing must use stored qualifying_shares, not re-derive from current share count | BR-009 ripple |
| FR-013 — Dividend Calendar (step 3) | FIX | Display of total_amount should note it is based on qualifying_shares | Consistency |
| FR-017 — Password Reset | NEW | Entire FR absent from original BAS; standard auth requirement | Must Have (requires SO) |
| FR-018 — PDPA Data Export | NEW | Entire FR absent; PRD NFR explicitly required it | PDPA compliance |
| FR-019 — Account Deletion | NEW | Entire FR absent; PRD NFR explicitly required it | PDPA compliance |
| US-021, US-022, US-023 | NEW | User stories for new FRs 017–019 | Required companions |
| AC for US-005 | NEW | Missing from original | QA completeness |
| AC for US-006 | NEW | Missing from original | QA completeness |
| AC for US-012 | NEW | Missing from original | QA completeness |
| AC for US-013 | NEW | Missing from original | QA completeness |
| AC for US-014 | NEW | Missing from original | QA completeness |
| AC for US-017 | NEW | Missing from original | QA completeness |
| AC for US-019 | NEW | Missing from original | QA completeness |
| AC for US-010 — critical regression test | NEW | Explicitly tests that new lot does not corrupt stored dividend total | P0 regression |
| BR-005 — Clearing fee cap | FIX | RM1,000 cap documented in PRD but omitted from BAS | Compliance completeness |
| BR-009 — Dividend total_amount | FIX (CRITICAL) | Derived from live share count → retroactive corruption; fixed to stored | CI-001 |
| BR-012 — Position dividend income | FIX | Formula updated to use stored total_amount, not per_share × live shares | BR-009 ripple |
| BR-025 — MYR rounding convention | NEW | No rounding rule existed; required for deterministic calculations | Calculation integrity |
| BR-026 — Currency and precision rules | NEW | No precision table existed; required for data model and API design | Calculation integrity |
| BR-027 — Qualifying shares semantics | NEW | New field requires its own business rule documenting semantics and invariant | BR-009 complement |
| Workflow 4 — Log Dividend | FIX (CRITICAL) | Step 5 corrected to store qualifying_shares and total_amount; not derive from live shares | CI-001 ripple |
| Workflow 8 — Password Reset | NEW | Entire workflow absent; required for FR-017 | Standard auth |
| Workflow 9 — Account Deletion | NEW | Entire workflow absent; required for FR-019 / PDPA | PDPA compliance |
| DividendTranche entity | FIX | Added qualifying_shares field; changed total_amount from derived to stored; added is_deleted, deleted_at | BR-009 fix |
| AuditLog entity_type enum | FIX | "Position" missing from enum — contradicts PRD NFR for position edit history | CI-003 in analysis |
| VR-011 — Qualifying shares validation | NEW | No validation for qualifying_shares existed | Required by new field |
| VR-012 — Dividend year validation | NEW | No validation for year field; required for tranche limit enforcement | Calculation integrity |
| VR-014 — Custom broker validation | NEW | No validation for user-defined broker fields | Security / data quality |
| EX-011 — Password reset email delivery failure | NEW | Companion exception for new FR-017 | Auth completeness |
| EC-022 — Share count increases after dividend logged | NEW | Core regression test scenario for BR-009 fix | P0 regression |
| EC-023 — Qualifying shares differ from current total | NEW | New display behaviour for qualifying_shares override | UX correctness |
| EC-015 — Lot edit doesn't change dividend totals | FIX | Clarified that editing lot shares does not alter stored DividendTranche.total_amount | BR-009 consistency |
| FR-014 — CSV Import (qualifying_shares column) | NEW | qualifying_shares handling in import was unspecified | Import completeness |
| CSV template spec (Sheet 2) | NEW | qualifying_shares column added as optional | Import completeness |
| Assumption A-007 — SST | — | SST assumption flagged; confirmation required from Legal | ESCALATE |
| Open Items OQ-002, OQ-008, OQ-009 | — | Critical legal/compliance questions; cannot be BA-resolved | ESCALATE |

---

## Downstream Readiness Assessment

| Team | Status | Condition |
|------|--------|-----------|
| **Product Design** | Ready with Conditions | Can wireframe all flows. Open items OQ-001 (trial duration), OQ-005 (sell calculator broker default), and OQ-012 (CSV conflict resolution) affect specific UI decisions but don't block wireframe starts. |
| **Solution Architecture** | Ready with Conditions | Can design data model. qualifying_shares fix is fully specified. Architecture must confirm DividendTranche.total_amount immutability is enforced at the application layer (not just the DB layer). OQ-003 (year semantics) must be resolved before dividend querying is finalised. |
| **Engineering** | Ready with Conditions | Can begin auth and portfolio management sprints. PDPA sprints (FR-018, FR-019) require legal sign-off (OQ-008, OQ-009) before sprint commitment. SST (OQ-002) must be resolved before fee calculation implementation. Password reset (FR-017) should be in V1 sprint given Must Have classification. |
| **QA** | Ready | Can write a complete test plan including P0 regression test for EC-022 (BR-009 fix) and all new acceptance criteria. The critical test invariant (adding a lot does NOT change stored DividendTranche.total_amount) is fully specified with worked examples. |

---

## What Would Take This Document to a 9–10 Score

The following ESCALATE items, if resolved, would close the remaining gaps:

1. **OQ-002 resolved** (SST on brokerage): If SST applies, add SST as a new fee component. If exempt, confirm in writing and update A-007.
2. **OQ-003 resolved** (dividend tranche year semantics): Confirm calendar year vs. stock financial year; small data model impact but prevents ambiguous dividend queries.
3. **OQ-008 and OQ-009 resolved** (PDPA V1 obligation): Legal sign-off confirms FR-018 and FR-019 are V1 requirements. Removes the `[REQUIRES STAKEHOLDER SIGN-OFF]` flags from those FRs.
4. **OQ-007 resolved** (FR-017 password reset priority): Sign-off converts it from a flagged Must Have to a confirmed sprint commitment.
5. **OQ-001 resolved** (trial period duration): A single confirmed number removes the assumption from BR-017 and FR-001 AC.

All five items are stakeholder/legal decisions, not BA analysis gaps. The document is complete to the limit of what BA analysis can produce unilaterally.

---

*End of Part 3 (Sections 10–15).*
*BursaTrack-BAS-Enhanced v2.0 is complete across three files:*
*— Part 1: Sections 1–5 (Business Summary, FRs, User Stories, Acceptance Criteria, Business Rules)*
*— Part 2: Sections 6–9 (Process Flows, Data Requirements, Validation Rules, Permissions)*
*— Part 3: Sections 10–15 (Exception Handling, Edge Cases, Assumptions, Open Questions, Testing Readiness, BA Quality Review)*
