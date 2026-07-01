# BursaTrack — Business Analysis Specification
## Part 3 of 3: Sections 10–15 (Exception Handling · Edge Cases · Assumptions · Open Questions · Testing Readiness · BA Quality Review)

---

# 10. EXCEPTION HANDLING

---

## EX-001 — Automated Price Refresh: Complete Feed Failure

**Cause:** The price data provider (yfinance) is unreachable or returns an error for all stocks.

**Expected System Behaviour:**
1. The refresh job records a failure event with a timestamp.
2. All affected PriceSnapshot records are marked source = "stale."
3. Within 5 minutes of the failure, the dashboard renders a persistent yellow status banner: "Price data unavailable — showing prices as of [last successful timestamp]. Update prices manually below."
4. Each position row shows a stale price indicator (e.g., a warning icon next to the price).
5. A manual price entry field appears inline for each position.
6. The system does not attempt another automated refresh until the next scheduled interval.

**User Message:** "Price data unavailable — showing prices as of [date/time]. Update prices manually below."

**Recovery Action:** User may enter manual price overrides per position. Next scheduled refresh will supersede manual prices on success.

---

## EX-002 — Automated Price Refresh: Partial Feed Failure

**Cause:** Some stock codes return valid prices; others return errors (e.g., a stock was recently renamed or delisted).

**Expected System Behaviour:**
1. Successfully fetched prices are updated normally.
2. Failed stocks are individually flagged as stale.
3. Status banner: "Price data unavailable for [N] stocks: [CARLSBG, LPI]. Update manually below."
4. Only the failed stocks show stale indicators and manual entry fields.

**User Message:** "Price data unavailable for [stock list]."

**Recovery Action:** Same as EX-001 per affected stock.

---

## EX-003 — CSV Import: File Validation Failure

**Cause:** Uploaded CSV has missing columns, wrong data types, or rule violations.

**Expected System Behaviour:**
1. System aborts validation on first error (fail fast) and returns a report.
2. No records are created (atomic — BR-022).
3. Error report shows: row number, column name, error description.
4. User can download the error report as a CSV.

**User Message:** "Import failed. [N] errors found. No records were imported. Download the error report, correct your file, and try again."

**Recovery Action:** User corrects the CSV and re-uploads.

---

## EX-004 — CSV Import: Atomic Transaction Failure (Database Error)

**Cause:** All rows pass validation but the database transaction fails mid-insert (e.g., server error, timeout).

**Expected System Behaviour:**
1. The transaction is fully rolled back.
2. No partial records remain in the database.
3. The user's existing portfolio is unchanged.

**User Message:** "Import could not be completed due to a system error. No records were imported. Please try again. If the problem persists, contact support."

**Recovery Action:** User retries the import. If repeated failures occur, support investigation is required.

---

## EX-005 — Login: Account Locked

**Cause:** 5 consecutive failed login attempts within a 10-minute window.

**Expected System Behaviour:**
1. The login form is disabled for 10 minutes.
2. A countdown timer is displayed.
3. No error is shown that reveals whether the account exists.

**User Message:** "Too many failed attempts. Please wait [X] minutes before trying again."

**Recovery Action:** User waits for the lockout period to expire. No email notification is sent at V1 (password reset flow is the self-service path).

---

## EX-006 — Payment Processing Failure

**Cause:** The payment processor returns a failure for a subscription purchase attempt.

**Expected System Behaviour:**
1. The subscription is not activated.
2. The account status does not change.
3. The user is returned to the subscription page with an error.

**User Message:** "Payment could not be processed. Please check your card details and try again, or use a different payment method."

**Recovery Action:** User retries with the same or a different payment method. No partial charges are applied.

---

## EX-007 — Subscription Webhook Failure (Payment Success Not Received)

**Cause:** Payment processor successfully charges the user but the webhook to BursaTrack fails or is delayed.

**Expected System Behaviour:**
1. The system does not activate the subscription until the webhook is received.
2. The payment processor retries webhook delivery for up to 72 hours.
3. If the webhook is not received within 24 hours, a support ticket is triggered automatically.

**User Message:** (If user contacts support) "Your payment was received. Your account will be activated within [timeframe]. If access is not restored in 24 hours, please contact support."

**Recovery Action:** Webhook retry mechanism; fallback: manual activation by support.

---

## EX-008 — Session Expired Mid-Session

**Cause:** User's session cookie expires after 30 days of inactivity during an active browser session.

**Expected System Behaviour:**
1. On the next authenticated request, the system returns a 401.
2. The user is redirected to the login page.
3. After successful re-login, the user is returned to the page they were attempting to access.

**User Message:** "Your session has expired. Please log in again."

**Recovery Action:** User logs in; session is re-established.

---

## EX-009 — Email Verification Link Expired

**Cause:** User clicks an email verification link more than 24 hours after it was sent.

**Expected System Behaviour:**
1. The system rejects the expired token.
2. User is shown a prompt to request a new link.

**User Message:** "This verification link has expired. Click below to request a new one."

**Recovery Action:** User requests a new verification email. Account access is not blocked pending verification during the trial period.

---

## EX-010 — Stock Code Not Found in Reference List

**Cause:** User enters a stock code that does not match any known Bursa Malaysia listed security in the system's reference data.

**Expected System Behaviour:**
1. The form is not submitted.
2. An inline error is displayed next to the stock code field.
3. If the input looks like a stock name (text, not numeric), the system attempts a name match and suggests: "Did you mean CIMB (1023)?"

**User Message:** "Stock code '[input]' was not found. Check the Bursa Malaysia listed securities."

**Recovery Action:** User corrects the stock code or selects from the suggestion.

---

# 11. EDGE CASE ANALYSIS

## Data Edge Cases

**EC-001 — Stock with zero dividend tranches**
- Description: A position (e.g., SUNWAY tagged as "Volatile") has no dividend tranches logged.
- Potential Impact: Division by zero or null in yield calculation.
- Recommended Handling: Yield displays as "—" (not 0%) when no dividends are logged. The system must explicitly handle null dividend income without dividing by zero.

**EC-002 — Position with a single share**
- Description: User holds exactly 1 share.
- Potential Impact: Stamp duty = ROUNDUP(price / 1000, 0) must be calculated correctly for very small initial amounts (e.g., 1 share at RM0.60 = RM0.60; ROUNDUP(0.0006, 0) = 1 → stamp duty = RM1).
- Recommended Handling: Confirmed by formula — minimum stamp duty is RM1 for any transaction ≥ RM0.01. No special handling required.

**EC-003 — Dividend per share with 6 decimal places**
- Description: Malaysian dividends are sometimes declared in fractions of a sen (e.g., RM0.004813/share).
- Potential Impact: Rounding errors in total_amount if the system truncates to fewer decimal places.
- Recommended Handling: Store per_share_amount to 6 decimal places. Derive total_amount at read time; round the derived total to 2 decimal places for display only.

**EC-004 — Blended price calculation with lots of very different sizes**
- Description: Lot 1: 1 share at RM1.00; Lot 2: 10,000,000 shares at RM0.01.
- Potential Impact: Blended price is dominated by the larger lot.
- Recommended Handling: Correct by design — blended price = total_initial_amount / total_shares. No special handling required.

**EC-005 — All lots deleted from a position**
- Description: User deletes all lots under a position (soft-delete).
- Potential Impact: Position still exists with total_shares = 0 and a division by zero risk in blended price calculation.
- Recommended Handling: When all lots under a position are deleted, the position is automatically soft-deleted. A position with zero lots cannot exist in an active state.

**EC-006 — CSV import with duplicate stock codes in the file**
- Description: Import file contains two rows for "CIMB 1023" with different dates (two lots).
- Potential Impact: System may create two Positions instead of two Lots under one Position.
- Recommended Handling: System must group rows by stock_code within the import file. Multiple rows for the same stock_code are treated as separate Lots under one Position.

---

## Workflow Edge Cases

**EC-007 — Dividend tranche logged before position shares are entered**
- Description: This cannot happen by design — dividend tranches are children of positions, which require at least one lot.
- Recommended Handling: The "Add Dividend" action is only available on positions that have at least one lot.

**EC-008 — User edits share count of a position after dividends are logged**
- Description: User has 5,000 CIMB shares and has logged 3 dividend tranches. User edits lot 1 from 5,000 to 4,000 shares.
- Potential Impact: All previously logged dividend tranche totals change retroactively (because total_amount = per_share × total_shares).
- Recommended Handling: Correct by design — because per_share_amount is stored (not total_amount), the recalculation is automatic and correct. The system must display a recalculation notification: "Share count updated. [N] dividend records have been recalculated."

**EC-009 — Dividend tranche year crosses calendar boundary**
- Description: A company's financial year runs October–September. The final interim dividend may be declared in December 2025 but paid in January 2026.
- Potential Impact: If "year" is assigned by payment date, the tranche appears in 2026 yield figures instead of 2025.
- Recommended Handling: The "year" field on DividendTranche is user-entered (defaults to current calendar year but is editable). The user is responsible for assigning the correct year. The system should display the year prominently when logging dividends. (This is the BA assumption made in the absence of a stakeholder decision — confirm before build.)

**EC-010 — Sell calculator opened for a position with multiple lots at different brokers**
- Description: Lot 1 used Maybank Investment; Lot 2 used MooMoo.
- Potential Impact: Which broker rate does the sell calculator use?
- Recommended Handling: The sell calculator uses the broker of the most recently created lot (as a default). The user can override the broker for the sell calculation without changing the position data. This logic requires a stakeholder decision before implementation.

**EC-011 — Stamp duty rate changes (post-July 2028)**
- Description: The 0.10% stamp duty remission expires on 12 July 2028 and may revert to 0.15%.
- Potential Impact: If the rate is hard-coded, all post-July 2028 fee calculations will be wrong until a deployment.
- Recommended Handling: The stamp duty rate is stored in an externally configurable system setting (BR-015). When the rate changes, the setting is updated without a code deployment. Historical lots retain their original rate (stored at creation — see Lot entity notes).

---

## User Behaviour Edge Cases

**EC-012 — User imports CSV then manually adds the same stock**
- Description: User imports CIMB via CSV, then manually adds CIMB via the form.
- Potential Impact: The form detects CIMB already exists as a Position and adds the manual entry as a new Lot.
- Recommended Handling: Correct by existing flow (FR-003 Main Flow step 6). Confirm with a UI prompt: "CIMB 1023 already exists in your portfolio. Adding as a new lot."

**EC-013 — User enters a future purchase date**
- Description: User accidentally enters tomorrow's date as the purchase date.
- Potential Impact: The system should reject future dates (BR validated — see Validation Rules §8).
- Recommended Handling: Future purchase dates are rejected with an inline error.

**EC-014 — User attempts to log in from a device after session is still active on another device**
- Description: User is logged in on Desktop A. They log in on Mobile B.
- Potential Impact: Both sessions are valid simultaneously.
- Recommended Handling: Multiple concurrent sessions are permitted at V1 (no single-session enforcement). No special handling required.

**EC-015 — User cancels mid-CSV-import (closes browser)**
- Description: User begins an import, the file is being processed, and the user closes the browser tab.
- Potential Impact: If the atomic transaction is already committed, data exists. If it's mid-process, the partial transaction must roll back.
- Recommended Handling: The import is processed server-side in a single atomic transaction. Client disconnection during processing does not affect server-side transaction integrity. On reconnection, the user sees either the completed import or no change (never a partial state).

---

## Third Party Dependency Edge Cases

**EC-016 — yfinance returns a price for a delisted stock**
- Description: A stock held in a portfolio is delisted. yfinance may return a stale price, zero, or an error.
- Potential Impact: The position displays an incorrect current value and unrealised P&L.
- Recommended Handling: If yfinance returns 0 or null for a stock: treat as a price fetch failure for that stock (EX-002). Display stale indicator. Allow manual override. Do not display 0 as a valid current price.

**EC-017 — yfinance returns prices in wrong currency (USD for a Bursa stock)**
- Description: yfinance occasionally returns USD prices for Bursa stocks that are listed on both Bursa and an overseas exchange.
- Potential Impact: Catastrophically wrong current market value and P&L figures.
- Recommended Handling: The system should validate that returned prices are within a plausible range for the stock (e.g., within 20% of the last known price). Prices outside the plausible range are flagged as suspect and treated as stale. This is a V1.1 enhancement; at V1, document the risk and implement a manual override path.

**EC-018 — Payment processor webhook arrives twice (duplicate)**
- Description: The payment processor retries a webhook that was already successfully processed.
- Potential Impact: Account status is set to "active" twice; if not idempotent, a second subscription record may be created.
- Recommended Handling: Webhook processing must be idempotent. The system must check whether the webhook event ID has already been processed before taking action.

---

## Operational Edge Cases

**EC-019 — Malaysian public holiday on a weekday**
- Description: Bursa Malaysia is closed on Malaysian public holidays. The automated price refresh must not run on these days or must handle "market closed" responses gracefully.
- Recommended Handling: Maintain a configurable list of Bursa Malaysia market closure dates. If the refresh job runs and the market is closed, treat it as a non-trading day (no prices fetched, no stale indicator, "Market closed" status displayed).

**EC-020 — New stock listed on Bursa mid-portfolio**
- Description: A user wants to add a newly listed stock that is not yet in the system's reference list.
- Recommended Handling: At V1, the reference list requires a manual update by the system operator. Newly listed stocks cannot be added until the list is updated. The error message (EX-010) directs the user to contact support if the stock is valid but not found.

**EC-021 — Database running out of disk space during import**
- Description: A large CSV import begins but the database reaches its storage limit mid-transaction.
- Recommended Handling: The transaction fails, rolls back completely, and the user receives EX-004. System health monitoring should alert operators before disk space becomes critical.

---

# 12. ASSUMPTIONS

| Assumption | Risk Level | Requires Clarification |
|------------|------------|------------------------|
| Trial period is 14 calendar days | Medium | Yes — confirm with stakeholder before registration is built |
| "Current year" for dividend yield calculation is the calendar year (Jan 1–Dec 31) | Medium | Yes — confirm before dividend tranche logic is built |
| Sell calculator uses the most recently created lot's broker when a position has multiple lots with different brokers | Medium | Yes — confirm with product owner before calculator is built |
| Soft-delete is used for all Position, Lot, and DividendTranche records | Low | No — standard practice; proceed |
| The stamp duty rate configuration is a system-level setting accessible to operations without a code deployment | Low | No — confirm with engineering that the configuration approach supports this |
| PriceSnapshot records are shared across users (one record per stock per trading day, not per user) | Low | No — this is the correct and efficient design; proceed |
| Blended cost basis for multi-lot positions uses weighted average (total_initial_amount / total_shares) | Low | No — mathematically correct; proceed |
| BursaTrack is not required to obtain an SC licence for the portfolio tracking and sell calculator features | High | Yes — legal confirmation required before launch |
| SST on brokerage fees for Bursa equity trades is exempt | Medium | Yes — verify against July 2025 Bursa SST FAQ before fee calculator is built |
| CSV import groups rows by stock_code, treating multiple rows for the same stock as separate lots | Low | No — documented as requirement; proceed |
| Multiple concurrent sessions per user are permitted (no single-session enforcement) | Low | No — standard consumer SaaS behaviour; proceed |
| Email verification is required for full access but does not block trial usage | Low | No — consistent with PRD intent; proceed |
| Tiered broker fee structures (Rakuten Trade) are simplified to a single rate at V1 | Low | No — PRD decision confirmed; proceed |
| The system maintains a configurable list of Bursa trading calendar closure dates | Low | Yes — confirm that the operations team has a process to maintain this list |

---

# 13. OPEN QUESTIONS

| Question | Impact if Unresolved | Recommended Owner |
|----------|---------------------|------------------|
| What is the trial period duration? (14 days assumed) | Registration logic, subscription paywall timing | Product Owner |
| Is "current year" for dividend yield the calendar year or the stock's financial year? | Dividend tranche year assignment, yield calculation scope | Product Owner |
| Which broker rate does the sell calculator use when a position has lots from different brokers? | Sell calculator P&L accuracy | Product Owner |
| Is SST now applicable to brokerage fees for Bursa equity trades (July 2025 FAQ)? | All fee calculations in the product will be incorrect if SST applies at 6% | Founder — read the July 2025 Bursa SST FAQ (10-minute task) |
| Is a Malaysian SC licence required for BursaTrack given it includes a sell scenario calculator? | Legal compliance before launch | Founder + Malaysian securities lawyer |
| How should conflicting stocks be handled during CSV import into a non-empty portfolio? (add as lot / skip / cancel) | CSV import UX and business logic | Product Owner |
| What is the full list of pre-populated brokers at V1 launch, and are the stated fee rates confirmed? | Accuracy of all-in cost calculations from day one | Founder — verify rates directly with each broker |
| Should the system validate that a purchase date is a Bursa trading day (not just a weekday)? If yes, V1 or V1.1? | Validation complexity — requires a holiday calendar | Product Owner |
| What happens to a position's yield in the dashboard if the all-in cost is zero (data corruption scenario)? | Division-by-zero guard required | Engineering |
| Who maintains the Bursa trading calendar closure list, and what is the update process? | Price refresh accuracy on public holidays | Operations / Product Owner |
| What is the maximum number of positions a user can hold at V1? (50 stated in PRD NFRs — confirm as hard limit or soft recommendation) | System performance and UX | Engineering |
| Does the dividend calendar show future planned tranches (pre-logged), or only past-paid tranches? | Calendar display logic | Product Owner |

---

# 14. TESTING READINESS REVIEW

## Areas Ready for Testing

**Fee Calculation Logic (FR-003, FR-004, FR-012; BR-001 to BR-007):**
- All calculation rules are fully specified with numeric test cases.
- Test cases can be directly derived from the acceptance criteria.
- The reference Excel model provides a validated set of expected outputs for all 16 stocks.
- The row 28 formula class of bug is documented — a specific regression test must be written: "Editing lot share count does NOT use per_share_amount from tranche 1 when calculating tranche 8 total."

**Yield Denominator Correctness (FR-009, BR-008):**
- Test case: CIMB yield must be 5.57% (all-in denominator), not 5.58% (pre-fee denominator).
- Boundary test: portfolio with one position and one tranche.
- Boundary test: portfolio with 16 positions and blended yield calculation.

**Validation Rules (§8):**
- All field-level validations have defined error messages and boundary conditions. QA can begin writing negative test cases immediately.

**Authentication (FR-001, FR-002; BR-016, BR-017, BR-019):**
- Registration happy path, email conflict, password rules, lockout (5 attempts), session expiry (30 days) are all specified.

**CSV Import (FR-014, FR-015; BR-022):**
- Atomicity test: valid file creates all records; file with one error creates zero records.
- Row-level error test: error report includes row number and column name.
- Duplicate stock test: two rows for the same stock_code create two lots under one position.

**Access Control (§9):**
- All role-based permission rules are specified with explicit allowed/denied action tables.
- Expired trial user cannot write data — must be tested at the application layer, not just the UI.

---

## Missing Information (Blocks QA Planning)

| Missing Item | Impact on Testing |
|-------------|------------------|
| Trial period duration (14 days assumed) | Cannot write subscription expiry test cases until confirmed |
| CSV import field specification (full column list not yet finalised) | Cannot write CSV validation test cases until the template spec is signed off |
| Sell calculator broker selection logic for multi-lot positions | Cannot write sell calculator accuracy tests for multi-broker positions |
| Bursa trading calendar closure list format | Cannot write public holiday price refresh tests |
| Conflict resolution UX for CSV import into non-empty portfolio (add/skip/cancel options) | Cannot write merge import test cases |
| Subscription payment processor selection | Cannot write payment success/failure/webhook tests until provider is confirmed |

---

## Potential Testing Risks

1. **yfinance reliability during test execution:** Automated price refresh tests that depend on live data will be flaky. Recommend: mock the price data provider in test environments; use a fixed set of known stock prices for all integration tests.

2. **Fee rounding precision:** Clearing fee (0.03%) and stamp duty (ROUNDUP) can produce floating-point precision issues depending on implementation language. All fee calculations must be tested to 2 decimal places using controlled inputs. Use the 16-stock reference dataset from the Excel model as the canonical test fixture.

3. **Atomic CSV import rollback:** Testing that a failed import creates zero records requires a database-level assertion, not just a UI assertion. QA must have access to a test database query to verify no partial records exist after a failed import.

4. **Session expiry:** Testing a 30-day session expiry in automated tests is impractical in real time. Recommend: make the session expiry duration configurable in the test environment and set it to 30 seconds for automated tests.

5. **Stamp duty rate configurability:** If the rate is stored in a system setting, QA must test that changing the setting affects new lot calculations but NOT retroactively changes the stored fees on existing lots.

---

## Recommended Next Actions

1. **Resolve 12 open questions** before engineering estimation begins. The most critical are: trial period duration, SST on brokerage (binary compliance question), sell calculator broker selection for multi-lot positions, and the SC licence question.
2. **Produce the CSV import template specification** (a BA work product — required before FR-014 engineering estimation).
3. **Establish a test data fixture** from the Excel model: all 16 stocks with known purchase prices, fees, dividend tranches, and expected yields. This fixture becomes the canonical regression test dataset.
4. **Confirm the Bursa stock reference list source** and the process for keeping it current (new listings, delistings).
5. **Confirm the payment processor** so that subscription workflow tests can be scoped.

---

# 15. BUSINESS ANALYST QUALITY REVIEW

## Missing Business Rules

The following business rules are required but were not explicitly stated in the PRD and have been documented here for the first time:

- **BR-003 (Brokerage per lot, not per position):** The PRD describes brokerage per position; the correct interpretation is per lot (per transaction). This is a meaningful distinction for multi-lot positions.
- **BR-009 (Store per-share, derive total):** The PRD mentions avoiding the row 28 bug but does not explicitly state the rule that prevents it. This rule must be confirmed with engineering before the data model is designed.
- **BR-024 (Proportional cost for partial sell):** The PRD's sell calculator acceptance criteria only cover full position sells. The partial sell rule is an edge case that must be handled.
- **BR-020 / BR-021 (T+2 disclosure and financial disclaimer):** The PRD mentions these as compliance requirements but does not define the exact text or placement rules. The exact required text is now documented.

---

## Potential Requirement Gaps

1. **Password reset flow:** The PRD and this specification cover registration and login but do not define the "Forgot Password" workflow. This is a standard auth requirement that must be specified before engineering estimation. Assumption: standard email-based reset link, expires 1 hour.

2. **Email change flow:** A user who wants to change their email address has no defined workflow. This should be scoped (even if deferred to V1.1) to avoid it being built ad hoc.

3. **Account deletion (PDPA):** The PDPA compliance section of the PRD mentions data deletion as a user right but the workflow is not specified. This must be defined before launch (30-day grace period, data export before deletion, soft-delete confirmation).

4. **Subscription invoice / receipt delivery:** No specification for whether BursaTrack sends a subscription receipt email. This is a standard expectation and a tax documentation requirement for business subscribers.

5. **Stock reference data maintenance:** The process for adding newly listed stocks, handling delistings, and handling stock code changes (mergers, name changes) is not defined. Without it, the system will silently fail to find valid stocks over time.

6. **Price refresh job scheduling:** The exact schedule (time of day, frequency during market hours) is not defined. For dividend investors, end-of-day (4:30 PM MYT) is sufficient; intraday refresh at 12:30 PM MYT is a nice-to-have.

---

## Ambiguous Areas

1. **"Current year" dividend income:** The dashboard shows "total annual dividend income (current calendar year)" but the PRD does not define what happens at year-end. Does January 2027 data reset the dashboard? Is there a historical view? This must be defined before the dividend yield calculation is built.

2. **Position "total shares" after a partial sell:** If a user sells 2,000 of their 5,000 CIMB shares, does the position reflect 5,000 (purchase records only) or 3,000 (current holding)? At V1, BursaTrack tracks purchase cost and dividend income — it does not track sell transactions. The sell calculator is for modelling only. The position's lot records remain unchanged after a sale. This is a fundamental product design decision that should be documented explicitly in the PRD.

3. **Dividend income shown on dashboard — year-to-date or all-time?** The PRD states "total annual dividend income (current calendar year)" in the dashboard spec but does not address whether a historical view (total all-time income) is also displayed. QA cannot write comprehensive dashboard tests without this being defined.

4. **Unrealised P&L when current price is manual:** Should unrealised P&L be displayed when the current price is a manual override? The answer should be yes (with a visual indicator that it uses a manual price), but this is not stated.

---

## Operational Risks

1. **yfinance outage coincides with a major market event (e.g., dividend ex-date):** On the day a major stock goes ex-dividend, investors are most likely to check their portfolio. If the price feed fails on that day, the user experience is at maximum friction at a maximum-attention moment. The manual override fallback is essential and must be easy to use, not buried in settings.

2. **CSV template changes between versions:** If the CSV template is updated in V1.1 (new columns, changed field names), users who saved the V1 template will receive validation errors. Versioning the template (e.g., `BursaTrack_Import_Template_v1.csv`) and maintaining backward compatibility is a planned V1.1 consideration.

3. **Stamp duty rate change in July 2028:** If the rate reverts to 0.15%, existing users' historical lot calculations must NOT be changed (stored fees are correct at the time of purchase). Only new lots added after the rate change use the new rate. The Lot entity is designed to store fees at creation time specifically for this reason.

4. **Dividend per share vs. total amount data entry error:** Users familiar with Bursa announcements may enter the total dividend income they received (e.g., RM1,000) rather than the per-share amount (RM0.20). If the per-share field expects RM0.20 and the user enters RM1,000, the derived total becomes RM5,000,000 (for 5,000 shares). The system needs an input plausibility check: if `per_share_amount × position_total_shares` would exceed RM1,000,000, display a confirmation prompt.

---

## Recommended Clarifications

Before any sprint begins, the following items must be closed in a single BA kickoff session (estimated: 2 hours):

| Priority | Item |
|----------|------|
| 1 — Blocker | SST on brokerage: read July 2025 Bursa FAQ (10 minutes; binary outcome) |
| 2 — Blocker | Trial period duration (14 days assumed) |
| 3 — Blocker | Password reset workflow specification |
| 4 — Blocker | CSV import template column specification |
| 5 — High | "Current year" yield scope and year-end reset behaviour |
| 6 — High | Sell calculator broker selection for multi-lot, multi-broker positions |
| 7 — High | Position share count after a user sells shares (purchase records only vs. current holding) |
| 8 — Medium | Account deletion workflow (PDPA) |
| 9 — Medium | Stock reference data maintenance process |
| 10 — Medium | Price refresh schedule (time of day, frequency) |

---

## BA Confidence Score

**7.5 / 10**

**Reasoning:**

This specification is ready for engineering estimation on the core calculation engine (fee logic, yield, sell calculator) and the data model. These areas are defined to implementation precision with numeric test cases and explicit business rules. An engineering team can begin building and testing the fee calculation, dividend tranche, and yield modules immediately from this document.

The score does not reach 9+ for the following reasons:

- **Three open questions are blockers for specific features:** SST on brokerage (fee calculator), trial period duration (subscription logic), and sell calculator broker selection for multi-lot positions. Each blocks a distinct feature from being estimated.
- **Three requirement gaps are unspecified:** Password reset, account deletion, and the "position shares after a sell" decision are standard requirements that will surface in sprint planning if not addressed now.
- **Two ambiguities are significant:** "Current year" dividend income scope and the partial sell position model must be resolved before QA can write a complete test plan.

A score of 9 is achievable after a single two-hour BA kickoff session that resolves the 10 items in the table above.

---

*End of Part 3.*
*Full Business Analysis Specification: BursaTrack-BAS-Part1.md + BursaTrack-BAS-Part2.md + BursaTrack-BAS-Part3.md*
*Intended audience: Engineering Leads · QA Team · Product Designer · Product Owner*
