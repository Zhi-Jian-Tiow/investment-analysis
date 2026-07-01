# Product Requirements Document: BursaTrack

> **Author:** Senior Product Manager
> **Date:** 2026-06-21
> **Status:** Draft — For Stakeholder Review
> **Inputs:** Investment Analysis Excel Report · BursaTrack Startup Validation Report

---

# 1. EXECUTIVE SUMMARY

## Product / Feature Name

**BursaTrack** — Bursa Malaysia Dividend Portfolio Tracker

## Summary

**The problem:** Malaysian retail investors managing dividend-focused portfolios on Bursa Malaysia spend 10–15 minutes daily updating prices and calculating performance across spreadsheets that were never designed for portfolio management. These spreadsheets are error-prone (silent formula bugs have been documented), cannot reflect true all-in transaction costs accurately across different brokers, and provide no automation for live price data or dividend tracking.

**The proposed solution:** A web application that replaces the Excel-based workflow with a purpose-built portfolio tracker tailored to Bursa Malaysia — with correct Malaysian fee modelling (brokerage, clearing fee, stamp duty), per-tranche dividend logging, and automated price data — so dividend investors can assess their true cost basis, yield, and portfolio performance without manual effort.

**The expected business outcome:** Capture a paying segment of Malaysia's growing retail investor base (2.4 million active, growing at 67% YoY in new CDS accounts) who currently operate in spreadsheet friction and are underserved by free tools that lack Bursa-specific fee accuracy. The primary monetisation hypothesis is a subscription model targeting dividend-income investors who care enough about accuracy to pay a modest monthly fee.

---

# 2. PROBLEM DEFINITION

## Current State

The documented workflow for a dividend-focused Bursa Malaysia investor is:

1. Maintain a manually-updated Excel workbook with 16+ stock positions.
2. Enter market prices manually each day from a broker app or financial site.
3. Track dividend payments per payout tranche (up to 8 per stock) manually.
4. Rely on fee formulas that may not reflect the investor's actual broker rate.
5. Use a separate calculator panel in the same spreadsheet to model buy/sell scenarios.
6. Reconcile T+2 settlement timing mentally when planning liquidity.

This is a daily, repeated, high-friction process with meaningful error surface. A documented formula bug in the spreadsheet (row 28 incorrectly references dividend 1 instead of dividend 8 in the true-branch) demonstrates that silent errors can persist undetected in a complex spreadsheet for extended periods.

## User Pain Points

- **Manual price updates:** 10–15 minutes daily to update prices for 16 positions — scales poorly as the portfolio grows.
- **Silent formula errors:** Complex formulas are difficult to audit; the row 28 bug is currently dormant but would silently corrupt calculations if a per-stock share count override is ever entered.
- **Broker fee inaccuracy:** A single hard-coded brokerage rate (0.10% / RM8 minimum) overstates costs for MooMoo users (RM3 flat) and understates for Kenanga users (0.42%). True yield calculations are therefore inaccurate.
- **ROI calculation flaw:** Yield is calculated against pre-fee initial cost rather than all-in cost, slightly overstating returns.
- **No dividend history or calendar:** Dividend payment dates, ex-dates, and upcoming declarations are tracked manually with no calendar integration or alert mechanism.
- **No mobile access:** The Excel workbook is not accessible on mobile for on-the-go decision making.
- **Cognitive load:** Separate portfolio table and calculator panel must be mentally reconciled; sell scenario modelling is a manual lookup exercise.

## Business Pain Points

- **No product exists:** The creator has no monetisable asset today — value is locked in a personal spreadsheet.
- **No user base:** There are zero paying customers and no validated willingness-to-pay signal.
- **Incumbent risk:** KLSE Screener is a free, Bursa-native alternative with portfolio tracking, dividend data, and mobile apps. Any business case depends on differentiating from a free tool.
- **Price data dependency:** The proposed solution relies on the yfinance unofficial Yahoo Finance API, which has experienced outages. A data disruption on a trading day undermines the core value proposition.

## Evidence

| Source | Finding |
|--------|---------|
| Investment Analysis Excel (direct inspection) | 16-stock portfolio, daily manual price entry, documented row 28 formula bug, ROI denominator uses pre-fee cost |
| Startup Validation Report | 147,091 new CDS accounts opened in H1 2025 (67% YoY growth); ~2.4M active retail investors |
| Startup Validation Report | KLSE Screener identified as free, Bursa-native incumbent with portfolio tracking and dividend data |
| Startup Validation Report | No validated willingness-to-pay evidence for Malaysian portfolio SaaS tools |
| Startup Validation Report | yfinance API is unofficial with documented outage history |
| **Assumption** | Other Malaysian investors with 10+ Bursa positions share equivalent pain; unconfirmed by external user research |
| **Assumption** | A meaningful segment will pay RM15–30/month for accuracy and convenience not available in free tools |

---

# 3. BUSINESS OBJECTIVES

## Primary Objective

Validate that a segment of Malaysian dividend investors will pay for a purpose-built Bursa portfolio tracker that materially reduces daily management effort and provides provably accurate cost and yield calculations.

## Secondary Objectives

- Establish BursaTrack as the reference tool for Malaysian dividend-income investors who manage 10+ positions.
- Build a defensible data moat through per-tranche dividend history and accurate cost-basis records that are time-consuming to replicate in free tools.
- Grow monthly active users (MAU) from the founder's personal use case to a paying subscriber base, validating the business model before scaling.

## Success Metrics

| Metric | Current State | Target State (12 months) |
|--------|---------------|--------------------------|
| Paying subscribers | 0 | 200 paying users at RM20/month |
| Monthly Recurring Revenue (MRR) | RM 0 | RM 4,000 |
| Daily active usage rate | 1 user (founder) | ≥ 60% of subscribers check daily |
| Portfolio onboarding completion rate | N/A | ≥ 70% of sign-ups complete full portfolio entry |
| Price data uptime | N/A | ≥ 99.5% trading-day uptime |
| Churn rate | N/A | < 5% monthly |

## Success Criteria

The initiative is considered successful if, within 12 months of public launch:

1. ≥ 200 users are paying subscribers with a monthly churn rate below 5%.
2. ≥ 3 unsolicited testimonials cite the Malaysian fee accuracy or dividend tracking as the primary reason for choosing BursaTrack over free alternatives.
3. At least one qualitative finding confirms users would not return to their previous spreadsheet workflow.

If criteria 1 is not met by month 6, the business case should be revisited; the product may be better positioned as a free open-source tool.

---

# 4. USER PERSONAS

## Persona 1: Ahmad — The Methodical Dividend Accumulator

### Description
Ahmad is 42, a mid-level government engineer in Shah Alam. He has been investing in Bursa for 8 years and holds 12–18 positions, all selected for dividend income. He is comfortable with Excel and manages his portfolio from a desktop at home each morning before work.

### Goals
- Know at a glance whether his dividend income is on track each month.
- Accurately calculate his true yield on every position including all transaction fees.
- Never miss an ex-dividend date.

### Motivations
- Financial independence through passive dividend income within 10 years.
- Precision: he wants numbers he can trust, not estimates.

### Pain Points
- Spending 15+ minutes every morning updating prices before he can make a decision.
- Unsure whether his ROI calculation is correct (he suspects it ignores fees on one side).
- No alert when an ex-date or payment is announced.

### Behaviour Patterns
- Checks portfolio Monday to Friday before 9:00 AM.
- Reinvests all dividends; tracks each tranche separately.
- Uses one broker (Maybank Investment) and has never changed.

### Usage Context
- Desktop web, morning routine, 5–10 minutes per session once the tool works correctly.

---

## Persona 2: Farah — The Emerging Income Investor

### Description
Farah is 28, a marketing executive in Kuala Lumpur. She started investing during the pandemic, holds 6 positions mostly in banking and telco stocks, and wants dividend income to supplement her salary. She is not deeply technical and finds her current Google Sheet "good enough but annoying."

### Goals
- See her dividend income in one clean view without having to calculate anything.
- Understand when her next dividend payment arrives.
- Check her portfolio from her phone on the commute.

### Motivations
- Building financial security while her salary grows.
- Simplicity: she wants a tool that "just works."

### Pain Points
- Manual updating is the biggest deterrent to checking more frequently.
- She does not fully understand the fee structure and is not confident her yield numbers are right.
- Her Google Sheet has no mobile experience worth using.

### Behaviour Patterns
- Checks portfolio 2–3 times per week, more often after announcements.
- Only uses one broker (MooMoo) because of low fees.
- Reads i3investor and KLSE Screener for market news.

### Usage Context
- Mobile-first, commute and lunch breaks, sessions under 3 minutes.

---

## Persona 3: David — The Active Dividend Optimizer

### Description
David is 35, a software developer who manages a 20+ position Bursa portfolio as a serious side project. He actively compares yield across stocks, models buy/sell scenarios before acting, and tracks every dividend tranche to calculate his true annual income. He has already identified the row 28 bug in his own spreadsheet (he thinks).

### Goals
- Accurate all-in cost basis per position per lot.
- Scenario modelling: "if I sell CIMB at RM8.60, what is my net profit after fees?"
- Aggregate portfolio yield across all 20 positions in one number.

### Motivations
- Maximising yield on capital deployed; every basis point matters to him.
- He would pay RM30/month for a tool that saves him 30 minutes daily and eliminates formula risk.

### Pain Points
- Excel formulas are brittle; he finds and fixes bugs but worries about the ones he misses.
- Has to manually model every sell scenario; no integrated calculator linked to his live positions.
- No way to compare realised vs. expected yield historically.

### Behaviour Patterns
- Daily user, mornings and after market close.
- Uses Rakuten Trade; knows the fee schedule precisely.
- Would participate in a beta if invited.

### Usage Context
- Desktop, analytical, long sessions (15–20 minutes) weekly portfolio review plus quick daily checks.

---

# 5. PROPOSED SOLUTION

## Solution Overview

BursaTrack is a web application for Malaysian dividend-focused retail investors that:

1. Maintains a portfolio of Bursa-listed stocks with per-lot position tracking.
2. Automatically fetches current market prices for all holdings.
3. Calculates all-in buy costs using the correct Malaysian fee stack (brokerage at the user's actual broker rate, 0.03% clearing fee, stamp duty at RM1/RM1,000 rounded up).
4. Tracks dividend payments per stock per payout tranche, with running total and per-share calculations.
5. Computes true dividend yield against all-in cost (not pre-fee cost).
6. Provides a buy/sell scenario calculator linked to live positions.
7. Surfaces upcoming ex-dividend dates and payment schedules.

## User Value

- Eliminates daily manual price updates across 16+ positions.
- Provides provably accurate yield calculations that account for the user's actual broker fees.
- Tracks dividend history per tranche in a structured, auditable format.
- Enables sell scenario modelling without a separate calculator spreadsheet.
- Surfaces ex-dividend and payment calendar at a glance.

## Business Value

- Recurring subscription revenue from a growing segment of Malaysian retail investors.
- Strong retention driver: users who enter all their historical dividend tranches have a high switching cost.
- Differentiated positioning against free tools on fee accuracy and dividend depth, not on breadth of market coverage.

## Why This Approach

The problem is well-specified by the founder's own Excel model, which functions as a working prototype. The solution scope is narrow and achievable without requiring a full financial data platform. The Malaysian fee rules are stable regulatory inputs (clearing fee 0.03%, stamp duty 0.10% until July 2028), reducing implementation risk. The core differentiator — correct per-broker fee modelling and per-tranche dividend tracking — is not available in KLSE Screener at the level of accuracy required.

## Alternative Solutions Considered

| Alternative | Reason Not Selected |
|------------|---------------------|
| Improve the existing Excel file | No automation, no mobile, no monetisation path; scales poorly beyond 20 stocks |
| Build on top of KLSE Screener (contribute features) | No access; KLSE Screener is a third-party product with no public contribution model |
| White-label Sharesight | Sharesight does not correctly model Malaysian fee structure; pricing (AUD 32/month) is not viable for Malaysian retail market |
| Build a Google Sheets add-on | Limited automation capability; still desktop-locked; not a viable subscription product |
| Open-source personal tool (no monetisation) | Valid fallback if willingness-to-pay is not validated, but defers the business question rather than answering it |

---

# 6. SCOPE DEFINITION

## In Scope

- User account creation and authentication.
- Portfolio management: add, edit, delete positions; support multiple lots per stock.
- Per-stock share count and broker selection for accurate fee calculation.
- Automated price fetching for Bursa-listed equities (daily during market hours).
- All-in buy cost calculation: brokerage (configurable per broker), clearing fee (0.03%), stamp duty (RM1/RM1,000 rounded up).
- Dividend tracking: log individual dividend payouts per stock per tranche (up to 8 tranches), with per-share and total amounts.
- True ROI/yield calculation using all-in cost as denominator.
- Portfolio summary: total portfolio cost, total dividend income, blended yield.
- Buy/sell scenario calculator: for any stock in the portfolio, model net proceeds and profit/loss at multiple sell prices.
- Dividend calendar: display declared ex-dates and payment dates for held stocks.
- Manual price override: allow user to enter price if automated fetch fails.
- Mobile-responsive web interface.

## Out of Scope

- Real-time intraday price streaming (daily price refresh is sufficient for dividend investors).
- Coverage of non-Bursa exchanges (e.g., SGX, HKEX, NYSE).
- Social features, discussion forums, or community feeds.
- Automated dividend data scraping (dividend amounts will be user-entered, not auto-populated).
- Tax reporting or capital gains calculation (Malaysian retail equity trading does not attract CGT, but this is out of scope regardless).
- Integration with broker accounts or CDS via API (no public API access available).
- Native iOS / Android apps at launch (mobile-responsive web only).
- Warrants, ETFs, or structured products (equities only at launch).

## Future Considerations

- Push or email alerts for ex-dividend dates and declared dividends.
- Historical yield trend charts per stock and per portfolio.
- Broker API integration if Bursa or brokers open APIs.
- KLSE market screener or stock discovery features.
- Google Sheets import/export for onboarding migration.
- Native mobile apps if web MAU justifies the investment.
- SST treatment on brokerage: monitor Bursa's SST FAQ (updated July 2025) and add SST toggle if the current exemption status changes.

---

# 7. USER JOURNEY

## End-to-End Journey: First-Time Portfolio Setup and Daily Check

| Step | User Goal | User Action | Expected Outcome |
|------|-----------|-------------|-----------------|
| 1 | Discover BursaTrack | Lands on product page via search, KLSE Screener thread, or referral | Clear value proposition page; CTA to start free trial |
| 2 | Create account | Enters email and password | Account created; directed to empty portfolio dashboard |
| 3 | Configure broker settings | Selects broker from list (e.g., MooMoo, Maybank Investment, Rakuten Trade) | Brokerage rate pre-filled; user can override |
| 4 | Add first position | Enters stock code or name, number of shares, purchase price per share, purchase date | Position appears on dashboard with calculated all-in buy cost |
| 5 | Add dividend history | For the same stock, enters each historical dividend tranche (date, amount per share) | Total dividend income and yield calculated and displayed |
| 6 | Add remaining positions | Repeats steps 4–5 for all holdings | Full portfolio visible with aggregate summary |
| 7 | View portfolio dashboard | Returns next morning | Prices auto-refreshed; portfolio values, yields, and income all current without manual effort |
| 8 | Check dividend calendar | Wants to know next payment | Calendar view shows upcoming ex-dates and payment dates for held stocks |
| 9 | Model a sell scenario | Considering selling CIMB; wants to know break-even | Opens sell calculator for CIMB; enters target sell prices; sees net proceeds and profit/loss at each price |
| 10 | Log new dividend received | Carlsberg declares 3rd interim dividend | Adds new tranche entry; total income and yield update immediately |

### Entry Points
- Direct navigation (bookmarked URL).
- Search (Google: "Bursa Malaysia dividend tracker", "Malaysia stock portfolio tracker").
- Word-of-mouth / community referral (i3investor, KLSE Screener forum, Reddit r/MalaysianPF).

### Exit Points
- User completes portfolio setup and bookmarks dashboard for next-day return.
- User abandons during onboarding if data entry time exceeds ~20 minutes.

### Decision Points
- During onboarding: is the user willing to enter full historical dividend data, or only current positions?
- At subscription paywall: will the user convert from free trial to paid?
- After price data outage: will the user tolerate a manual entry day, or churn?

### Failure Points
- **Onboarding drop-off:** User with 16 positions and 3 years of dividend history estimates 45 minutes of data entry and abandons.
- **Price fetch failure:** yfinance API returns stale or missing data during market hours; dashboard shows yesterday's prices with no warning.
- **Fee confusion:** User enters wrong broker and receives inaccurate yield; discovers the error and loses trust in the tool.
- **Dividend data entry complexity:** User is unsure how many tranches to enter or what "per share" amount to use; enters aggregate instead of per-tranche.

---

# 8. HIGH-LEVEL PRODUCT REQUIREMENTS

---

## REQ-001

**Requirement Name:** Portfolio Position Management

**Description:** Users can add, edit, and delete equity positions. Each position records: stock code, stock name, number of shares, purchase price per share, purchase date, and broker. Multiple lots per stock are supported (e.g., two separate purchases of CIMB at different prices).

**User Value:** Accurately reflects real portfolio structure; supports true cost basis calculation per lot.

**Business Value:** Core retention driver — populated portfolio data creates switching cost.

**Priority:** Must Have

---

## REQ-002

**Requirement Name:** Broker-Aware Fee Calculation

**Description:** The system calculates all-in buy cost per position using the Malaysian fee stack: brokerage (configurable per broker from a pre-set list with user-override), clearing fee (0.03% of contract value), and stamp duty (RM1 per RM1,000 rounded up). The correct denominator for yield calculation is the all-in cost, not the pre-fee purchase amount.

**User Value:** Eliminates the single biggest accuracy flaw in spreadsheet-based tracking; users know their true cost basis.

**Business Value:** Core product differentiator vs. free tools. Correctly modelling per-broker fees (MooMoo RM3 flat vs. Maybank 0.10%) is a capability no free competitor currently provides at position level.

**Priority:** Must Have

---

## REQ-003

**Requirement Name:** Automated Daily Price Refresh

**Description:** Current market prices for all held Bursa-listed equities are refreshed automatically on trading days. Price data is sourced from an available market data provider. Users are informed if price data is stale or unavailable, and can enter a manual price override.

**User Value:** Eliminates the 10–15 minutes of daily manual price entry that is the primary stated pain.

**Business Value:** Without automation, the product does not deliver on its core promise; acquisition and retention both depend on this working reliably.

**Priority:** Must Have

---

## REQ-004

**Requirement Name:** Per-Tranche Dividend Logging

**Description:** For each stock, users can log individual dividend payments (up to 8 tranches per year). Each tranche records: payout number (1st, 2nd, etc.), dividend per share amount, and payment date. The system aggregates to total dividend per share and total dividend income received per position.

**User Value:** Mirrors the granularity in the Excel model; supports accurate dividend income tracking across multiple payment cycles.

**Business Value:** Dividend investors track dividends at tranche level — this depth is not available in KLSE Screener; it is a differentiating feature for the target segment.

**Priority:** Must Have

---

## REQ-005

**Requirement Name:** Yield (ROI) Calculation

**Description:** The system calculates and displays dividend yield for each position as: total dividend income ÷ all-in buy cost (inclusive of all fees). Portfolio-level blended yield is also displayed. Both per-position and portfolio yields are updated whenever a new dividend tranche is logged or a position is modified.

**User Value:** A single, accurate number that reflects true return on capital deployed, correcting the known flaw in the spreadsheet model.

**Business Value:** Accuracy here is the primary trust signal. Users who verify a correct yield calculation will have confidence in the rest of the product.

**Priority:** Must Have

---

## REQ-006

**Requirement Name:** Portfolio Summary Dashboard

**Description:** The dashboard displays: total portfolio all-in cost, total annual dividend income, portfolio blended yield, per-position breakdown (cost, income, yield, current value, unrealised P&L), and stock category tags (dividend vs. growth/volatile).

**User Value:** Replaces the spreadsheet's B-Q column view with a clean, scannable summary requiring zero manual calculation.

**Business Value:** The dashboard is the primary daily-use surface; its quality determines retention.

**Priority:** Must Have

---

## REQ-007

**Requirement Name:** Buy/Sell Scenario Calculator

**Description:** For any position in the portfolio, users can model a sell at one or more price points. The calculator outputs gross proceeds, brokerage fee, clearing fee, stamp duty, net proceeds, and profit/loss (net proceeds minus all-in buy cost). The calculator uses the position's actual broker fee rate.

**User Value:** Replicates and improves on the spreadsheet's calculator panel — linked to live position data rather than requiring manual re-entry.

**Business Value:** Retention feature for active traders who evaluate sell timing; increases session depth and daily engagement.

**Priority:** Should Have

---

## REQ-008

**Requirement Name:** Dividend Calendar

**Description:** A calendar or list view surfacing upcoming ex-dividend dates and expected payment dates for stocks held in the portfolio. Data is user-entered (no automated scraping); the system displays dates previously recorded when logging dividends.

**User Value:** Eliminates the need to track ex-dates externally; supports dividend reinvestment planning.

**Business Value:** Increases daily return visits around ex-date periods; a stickiness mechanism.

**Priority:** Should Have

---

## REQ-009

**Requirement Name:** CSV Import for Portfolio Onboarding

**Description:** Users can import historical positions and dividend records from a structured CSV template. The product provides a downloadable template and validation feedback on import errors.

**User Value:** Reduces onboarding friction from an estimated 45 minutes of manual entry to under 10 minutes for users with existing spreadsheet records.

**Business Value:** Onboarding completion rate is the primary conversion lever. CSV import is the most direct way to move users from Excel/Google Sheets to BursaTrack without abandonment.

**Priority:** Should Have

---

## REQ-010

**Requirement Name:** Mobile-Responsive Interface

**Description:** All core features (dashboard, portfolio view, dividend logging, calculator) are accessible and usable on a mobile browser at standard screen widths (≥ 375px).

**User Value:** Enables on-the-go portfolio checks; critical for users like Farah who check from a commute.

**Business Value:** Mobile responsiveness is table stakes for consumer SaaS; absence would be a hard blocker for a meaningful user segment.

**Priority:** Must Have

---

# 9. ASSUMPTIONS

| Assumption | Risk Level | Validation Needed |
|------------|------------|------------------|
| A meaningful segment of Malaysian retail investors (≥ 10,000 people) share the same daily spreadsheet friction as the founder | High | Qualitative interviews with 10–15 Bursa investors who use Excel or Google Sheets; confirm daily update pain and willingness to switch |
| Target users will pay RM15–30/month for accuracy and convenience | High | Run 10 willingness-to-pay conversations before building the subscription billing system; consider a waitlist with pricing page |
| BursaTrack's fee accuracy and dividend depth are not features KLSE Screener will ship within 6–12 months | Medium | Monitor KLSE Screener release notes; the threat is real and the timeline is unknown |
| yfinance (or an alternative data source) provides reliable Bursa data on ≥ 99.5% of trading days | High | Run a 20-day monitoring experiment on all 16 target stocks before launching; identify fallback data source |
| Bursa stamp duty remains at 0.10% through July 2028 as gazetted | Low | Already confirmed by official gazette; set a calendar reminder to review in June 2028 |
| SST on brokerage fees for Bursa equity trades remains exempt | Medium | Verify against Bursa SST FAQ updated July 2025; if SST now applies, fee calculations in product and existing Excel model are both incorrect |
| CSV import from Excel/Google Sheets is sufficient to resolve onboarding friction | Medium | Time a pilot user importing their own full transaction history using the CSV template before launch |
| Dividend investors in Malaysia have a stable, multi-year holding horizon that justifies ongoing subscription cost | Medium | Confirmed directionally by the founder's profile; unconfirmed for the broader segment |

---

# 10. CONSTRAINTS

## Business Constraints

- Solo founder / small team; feature scope must be ruthlessly prioritised to a shippable v1.
- No external funding confirmed; initial development must be bootstrappable.
- Revenue model is unvalidated; the product should reach first paying user within 90 days of development start.

## Operational Constraints

- Price data cannot be sourced from a paid institutional API at launch without subscription revenue to offset cost; solution must use a free or low-cost data source initially, with a migration plan if data reliability is unacceptable.
- No broker API integrations are available in the Malaysian market; all position and dividend data is user-entered or CSV-imported.
- Settlement cycle (T+2) must be communicated to users in the sell calculator but does not require system-level handling at v1.

## Legal / Regulatory Constraints

- BursaTrack is a personal portfolio tracking tool, not a licensed financial advisory service. The product must not provide investment recommendations, buy/sell signals, or be positioned as financial advice.
- Malaysian Securities Commission (SC) licensing requirements apply to financial advisory and fund management services; a portfolio tracking tool without advisory features does not require SC licensing, but this should be confirmed with a Malaysian legal advisor before launch.
- Personal data collected (email, portfolio holdings) is subject to Malaysia's Personal Data Protection Act (PDPA). A privacy policy and data handling policy compliant with PDPA is required at launch.
- Stamp duty remission (0.10% rate) expires 12 July 2028 unless extended; fee calculation logic must be updatable without a code deploy.
- SST exemption on brokerage must be re-verified against the July 2025 Bursa FAQ before fee calculator ships.

## Resource Constraints

- No dedicated design resource confirmed; UI should use a component library to accelerate delivery.
- No dedicated data engineering resource; price data pipeline must be maintainable by a generalist developer.

## Timeline Constraints

- Willingness-to-pay validation should be completed before committing to a paid subscription infrastructure build.
- A personal-use v0 (founder-only) should be buildable within 2–4 weeks to validate core data model and price automation before adding multi-user and subscription features.

---

# 11. RISKS

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| yfinance API outages on trading days undermine core value proposition | High | Medium | Run 20-day reliability monitoring experiment before launch; identify a secondary data source (e.g., Bursa Anywhere web scrape, a paid API at low cost); implement manual price override and clear user-facing status indicators |
| KLSE Screener ships per-tranche dividend tracking and broker fee accuracy within 12 months | High | Medium | Accelerate to market; build switching-cost moat through complete dividend history data; explore features KLSE Screener is structurally unlikely to prioritise (e.g., per-lot cost basis, broker-specific fee presets) |
| Malaysian investors refuse to pay for portfolio SaaS tools (free-tool expectation) | High | Medium | Run 10 willingness-to-pay interviews before building subscription billing; validate pricing at RM10/month as entry point before testing RM20–30; consider a permanent free tier with premium features |
| Onboarding abandonment rate is high due to manual data entry burden | High | High | Prioritise CSV import (REQ-009) for v1; build an onboarding progress tracker; consider offering a "quick start" mode with current positions only (no historical dividends) to reduce time-to-value |
| SST is now applicable on brokerage fees (July 2025 Bursa FAQ) | High | Low–Medium | Verify immediately; if SST applies at 6%, update all fee calculations in both product spec and fee logic; this would make the existing Excel model incorrect |
| Solo founder bandwidth causes scope creep and delayed launch | Medium | High | Fix v1 scope to REQ-001 through REQ-006 and REQ-010 only; defer REQ-007 (calculator) and REQ-009 (CSV import) to v1.1 if needed |
| PDPA non-compliance at launch | Medium | Low | Engage Malaysian legal advisor for a one-time compliance review before collecting user portfolio data |
| Row 28 formula bug from Excel model is replicated in product code | Low | Medium | Explicitly test the 8th dividend tranche calculation in QA; the correct formula is `shares × dividend_8` not `shares × dividend_1` |

---

# 12. DEPENDENCIES

## Internal Dependencies

- Fee calculation logic must be implemented and unit-tested before the portfolio dashboard can display accurate yield figures.
- Broker configuration (REQ-002) must be established before position creation (REQ-001), or position creation must prompt broker selection.
- Dividend tranche logging (REQ-004) must be complete before yield calculation (REQ-005) can display correct results.

## External Dependencies

- **Bursa Malaysia market data:** Reliable access to end-of-day (or intraday) prices for all Bursa-listed equities. Currently proposed via yfinance; must be validated for reliability before launch.
- **Payment processing provider:** Required to collect subscription revenue; options include Stripe (supports Malaysia), iPay88, or Billplz. Must support Malaysian ringgit and be operational before soft launch.
- **Email delivery provider:** Required for account verification, password reset, and future dividend alert notifications.

## Third Party Dependencies

| Dependency | Provider | Risk | Contingency |
|------------|----------|------|-------------|
| Market price data | yfinance (Yahoo Finance unofficial API) | High — unofficial, has experienced outages | Identify secondary source; implement manual override |
| Stamp duty rate | Bursa Malaysia / Malaysian government gazette | Low — stable until July 2028 | Build rate as configurable parameter, not hardcoded |
| SST on brokerage | Bursa Malaysia SST FAQ (July 2025) | Medium — exemption status unconfirmed | Verify before fee calculator ships |
| Payment processing | TBD (Stripe / iPay88 / Billplz) | Low | Multiple providers available |

---

# 13. OPEN QUESTIONS

| Question | Owner | Recommended Next Action |
|----------|-------|------------------------|
| Does SST now apply to brokerage fees for Bursa equity trades under the July 2025 Bursa FAQ? | Founder | Read the Bursa SST FAQ (July 2025) before any fee logic is implemented. This is a 10-minute task with a binary outcome. |
| Is KLSE Screener's dividend tracking insufficient for the target user's specific needs? | Founder | Spend 2 hours tracking all 16 portfolio positions in KLSE Screener; document exactly what it cannot do (per-tranche logging, per-broker fee accuracy, per-lot cost basis). This is the primary competitive validation task. |
| Will target users pay RM15–30/month? | Founder | Conduct 10 structured willingness-to-pay interviews with Malaysian retail investors who currently use Excel or Google Sheets. Recruit via i3investor forum, Reddit r/MalaysianPF, or personal network. |
| Is yfinance sufficiently reliable for daily production use on Bursa data? | Founder | Run automated monitoring on all 16 portfolio stocks for 20 consecutive trading days; log failures, delays, and stale prices. Do not build the price pipeline on yfinance without this data. |
| What is the correct pricing for v1 subscription? | Founder | Test RM10, RM20, and RM30 price points in willingness-to-pay interviews; consider a freemium model (up to 5 positions free, unlimited positions paid) to reduce conversion friction |
| Is a Malaysian SC licence required for BursaTrack if it includes a sell scenario calculator? | Founder + Legal Advisor | One-time consultation with a Malaysian securities lawyer; the calculator computes transaction costs, not investment advice, but confirmation is needed before launch |
| What is the minimum data entry time for a user onboarding from a 16-position Excel portfolio? | Founder | Time the complete onboarding of the founder's own portfolio (all positions, all lots, all historical dividend tranches) using a prototype or paper mock; if > 20 minutes, CSV import moves to Must Have for v1 |

---

# 14. PRODUCT MANAGER REVIEW

## Biggest Risks

**1. Free-tool expectation in Malaysia.** KLSE Screener is free, Bursa-native, mobile-first, and has a large existing user base. The validation report gives competitive landscape a score of 2/5. Until the founder has spent two hours using KLSE Screener for their own 16 positions and can articulate with specificity what is missing, the entire business case rests on an assumption that has not been stress-tested.

**2. Willingness to pay.** There is zero external evidence that Malaysian retail investors will pay RM15–30/month for a portfolio tool. MalaysiaStock.Biz's August 2024 paywall transition is the only live experiment in this market, and its outcome is unknown. This is the single most important unknown and the cheapest to validate before a line of product code is written.

**3. Price data dependency.** The yfinance API is unofficial. If it fails on a trading day, BursaTrack delivers no core value. This is not a theoretical risk — it is a documented historical one. A product that cannot be trusted to show current prices on trading days cannot compete with free alternatives.

## Weakest Assumptions

- "Malaysian retail investors share the same daily spreadsheet pain as the founder" — unverified by any external user research. The founder is the sole evidence base.
- "Users will complete full portfolio onboarding including historical dividend data" — the validation report explicitly flags high onboarding friction for anyone who is not the founder.
- "BursaTrack's differentiators are sufficient to justify a switch from KLSE Screener plus a monthly fee" — the entire business case depends on this, and it has not been tested.

## Potential Failure Scenarios

- **Scenario 1 (Most likely):** The product launches, attracts initial interest from spreadsheet users, but conversion from free trial to paid is below 20% because users find KLSE Screener adequate for their needs and are not willing to pay the price difference. MRR plateaus below RM1,000.
- **Scenario 2:** Onboarding abandonment is high (> 60% of sign-ups do not complete portfolio setup). The daily value proposition never activates for most users. Retention collapses within the first 30 days.
- **Scenario 3:** yfinance experiences a multi-day outage during a volatile market period. Users lose trust in data accuracy at exactly the moment they need it most. Churn spikes.
- **Scenario 4:** KLSE Screener adds per-tranche dividend tracking and broker fee configuration in a feature sprint, eliminating the primary differentiator before BursaTrack reaches scale.

## Recommended Improvements

1. **Validate before building.** Complete all five tests in Section 6 of the Startup Validation Report before committing to a multi-user product. The personal-use v0 is a legitimate milestone; the startup decision is a separate gate.
2. **Lead with the accuracy story.** The fee calculator accuracy (per-broker, correct denominator, correct stamp duty rate) is a more defensible differentiator than general convenience. Position BursaTrack as "the only Bursa portfolio tracker that shows your true yield" — this is specific and testable.
3. **Reduce onboarding friction aggressively.** Consider a "fast start" mode that gets users to first value in under 5 minutes: add three current positions, see live prices and estimated yield, then optionally import full history. First value in < 5 minutes is the target.
4. **Resolve the SST question immediately.** This is a binary compliance question that takes 10 minutes to answer and affects the accuracy of the product's core claim. It must be resolved before any fee logic is built.
5. **Design a fallback for price data outages.** Even if yfinance is 99.5% reliable, design the product's response to a failure: clear status message, manual price entry mode, time-to-resolution SLA communication. The user experience of a data outage is part of the product.

## Alternative Strategies

| Strategy | When to Pursue |
|----------|---------------|
| Build as free, open-source personal tool | If willingness-to-pay interviews return consistently "nothing"; still has value as a portfolio and learning project |
| Freemium model: free up to 5 positions, paid unlimited | If conversion resistance is price-sensitivity rather than lack of perceived value; lowers the commitment to try |
| B2B: sell accuracy tools to investment clubs or financial content creators | If individual willingness-to-pay is low but communities or influencers see value in branded tools |
| Partner with a broker (e.g., MooMoo Malaysia) for distribution | If the product proves its value; broker partnership could provide price data and user acquisition in exchange for co-branding |

## PM Confidence Score

**4 / 10**

**Reasoning:** The problem is real, specific, and well-documented — the Excel model is a working prototype and the founder is the ideal reference user. That earns strong marks on problem clarity. However, the score is held back by three unresolved structural risks: no external validation that others share the pain at the same intensity, no willingness-to-pay evidence in a market with a strong free-tool expectation, and an unresolved data reliability question at the core of the product's value. The competitive landscape score (2/5 in the validation report) reflects a free, embedded incumbent that the discovery documentation does not adequately confront.

This score should be revisited after the five validation tests in Section 6 of the Startup Validation Report are completed. A positive outcome on willingness-to-pay and KLSE Screener gap analysis would move this to a 7–8 without any product changes.

---

*Document prepared for stakeholder review. Intended audience: business stakeholders, business analyst, product designer. Not a technical specification.*
