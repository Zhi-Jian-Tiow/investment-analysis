# Product Requirements Document: BursaTrack
## Bursa Malaysia Dividend Portfolio Tracker

> **Version:** 2.0 — Final
> **Status:** Business Analysis Ready (Pending Stakeholder Decisions)
> **Date:** 2026-06-21
> **Author:** Principal Product Manager
> **Inputs:** Investment Analysis Excel Report · BursaTrack Startup Validation Report · PRD v1 · Principal PM Review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Product Vision](#2-product-vision)
3. [Product Principles](#3-product-principles)
4. [Problem Definition](#4-problem-definition)
5. [Business Objectives](#5-business-objectives)
6. [User Personas](#6-user-personas)
7. [Proposed Solution](#7-proposed-solution)
8. [Competitive Analysis](#8-competitive-analysis)
9. [Scope Definition](#9-scope-definition)
10. [MVP Definition — Phased Release Plan](#10-mvp-definition--phased-release-plan)
11. [User Journey](#11-user-journey)
12. [High-Level Product Requirements](#12-high-level-product-requirements)
13. [Non-Functional Requirements](#13-non-functional-requirements)
14. [Core Domain Model](#14-core-domain-model)
15. [Product Analytics & Success Metrics](#15-product-analytics--success-metrics)
16. [Assumptions](#16-assumptions)
17. [Constraints](#17-constraints)
18. [Risks](#18-risks)
19. [Dependencies](#19-dependencies)
20. [Open Questions](#20-open-questions)
21. [Business Analysis Readiness Assessment](#21-business-analysis-readiness-assessment)
22. [Product Manager Review](#22-product-manager-review)

---

# 1. Executive Summary

## Product / Feature Name

**BursaTrack** — Bursa Malaysia Dividend Portfolio Tracker

## Summary

**The problem:** Malaysian retail investors managing dividend-focused portfolios on Bursa Malaysia spend 10–15 minutes daily updating prices and calculating performance across spreadsheets that were never designed for portfolio management. These spreadsheets are error-prone (silent formula bugs have been documented), cannot reflect true all-in transaction costs accurately across different brokers, and provide no automation for live price data or dividend tracking.

**The proposed solution:** A web application that replaces the Excel-based workflow with a purpose-built portfolio tracker tailored to Bursa Malaysia — with correct Malaysian fee modelling (brokerage at the user's actual broker rate, clearing fee, stamp duty), per-tranche dividend logging, and automated daily price data — so dividend investors can assess their true cost basis, yield, and portfolio performance without manual effort.

**The expected business outcome:** Capture a paying segment of Malaysia's growing retail investor base (2.4 million active, growing at 67% YoY in new CDS accounts) who currently operate in spreadsheet friction and are underserved by free tools that lack Bursa-specific fee accuracy. The primary monetisation hypothesis is a subscription model targeting dividend-income investors who care enough about accuracy to pay a modest monthly fee.

---

# 2. Product Vision

## What We Are Building

BursaTrack is a **dividend portfolio operating system for Malaysian retail investors** — purpose-built for Bursa Malaysia, designed around the income investor's daily workflow, and differentiated by provably accurate financial calculations that free tools do not provide.

This is not a general-purpose stock screener. It is not a trading platform. It is not a wealth management application. BursaTrack is the tool a dividend investor reaches for every morning to answer one question: *"How is my income portfolio performing, and is my money working as hard as it should?"*

## Long-Term Vision (3–5 Years)

**Year 1:** Replace the Excel spreadsheet for dividend investors in Malaysia. Become the reference tool for the serious retail investor who manages 10+ Bursa positions and cares about yield accuracy. Reach 500 paying subscribers.

**Year 2:** Expand the dividend calendar into a forward-looking income planner. Users can project their next 12 months of dividend income by position, enabling active rebalancing decisions. Add alert infrastructure (ex-date, payment received, price threshold). Reach 2,000 paying subscribers.

**Year 3:** Extend to Singapore Exchange (SGX) and investors who hold both Bursa and SGX positions — a large, underserved segment. Add multi-currency support. Reach 10,000 paying subscribers across Malaysia and Singapore.

**Year 5:** Become the standard dividend portfolio tracker for Southeast Asian retail investors — beginning with Bursa and SGX and expanding to SET (Thailand), IDX (Indonesia), and HKEX for Malaysian diaspora investors.

## Why This Product Deserves to Exist

Every other tool in this market — KLSE Screener, Sharesight, Excel — was built for a general investor. None were built specifically for a Malaysian dividend income investor who needs to know their true all-in cost basis, their per-broker fee impact, and their per-tranche dividend history in a single, accurate, mobile-accessible view. That investor exists in large numbers, given Malaysia's dividend culture and EPF-influenced savings behaviour. No tool has been built for them specifically. BursaTrack is that tool.

## Strategic Positioning

BursaTrack positions against free tools not on features, but on **financial accuracy**. The single most powerful claim the product can make is: *"Every other tool shows you an approximate yield. BursaTrack shows you your actual yield, calculated the same way a professional would — including every fee, every tranche, at your specific broker's rate."* This is a claim that can be proven with a side-by-side comparison and that resonates with the target user who already suspects their spreadsheet numbers are wrong.

## Vision Statement

> **BursaTrack is the dividend investor's source of truth — the only Bursa Malaysia portfolio tracker that calculates your true yield, logs every dividend tranche, and knows your broker's fee structure. Built for Malaysian income investors who are serious about their numbers.**

---

# 3. Product Principles

## Principle 1: Accuracy Before Features

**Description:** Every calculation BursaTrack produces must be verifiably correct. If the yield number, the cost basis, or the fee calculation is wrong, nothing else matters. We will not ship a feature that introduces numerical ambiguity.

**Why it matters:** The target user has already discovered (or suspects) errors in their current spreadsheet. BursaTrack wins trust by being the tool that is provably right — not the tool with the most features. A single calculation error, if discovered by a user, destroys the product's core value proposition.

**Decision test:** If a feature introduces a tradeoff between user convenience and calculation precision, choose precision.

---

## Principle 2: Time-to-Value Under 10 Minutes

**Description:** A new user must be able to add their first three positions, see live prices, and receive a yield calculation within 10 minutes of creating an account. If onboarding takes longer than 10 minutes to reach first value, we have failed.

**Why it matters:** Onboarding abandonment is the highest-probability failure mode. The product will never build a user base if the first experience is 45 minutes of data entry before anything useful appears.

**Decision test:** Every onboarding design decision must be evaluated against the 10-minute clock. Features that extend onboarding time must be deferred or made optional.

---

## Principle 3: Dividend-First, Not Price-First

**Description:** BursaTrack is designed for investors who think in terms of income, not capital gains. Portfolio views, dashboards, and default sorting should prioritise dividend yield, income received, and payment calendar — not unrealised P&L or price movement.

**Why it matters:** KLSE Screener and most portfolio trackers are designed around price movement and P&L. BursaTrack's differentiation is that it speaks the language of the dividend investor. If we build BursaTrack to look like a stock screener, we have lost the positioning battle.

**Decision test:** When designing any new feature, ask: "Does this serve a dividend income investor or a capital gains trader?" If trader, defer.

---

## Principle 4: Trust Through Transparency

**Description:** BursaTrack will always show users exactly how a number was calculated. Every yield figure links to its components (total dividend ÷ all-in cost). Every all-in cost shows its fee breakdown. Users should never have to take a number on faith.

**Why it matters:** The core user insight is that existing tools show numbers users cannot verify. BursaTrack's competitive advantage is not just accuracy — it is visible, auditable accuracy. A user who can trace every number to its source will not go back to a black-box tool.

**Decision test:** No summary number is acceptable without a visible drill-down to its constituent parts.

---

## Principle 5: Malaysia First, Then Broaden

**Description:** Every product decision at v1 and v1.1 is made in service of the Malaysian Bursa equity investor. We will not add SGX, NYSE, or other exchange support until we have proven the product for Bursa. We will not generalise the fee model to "generic" until the Bursa fee stack is rock-solid.

**Why it matters:** Breadth kills focus. The fastest path to product-market fit is extreme specificity for one well-defined user. Malaysian dividend investors are a real, growing segment. Serving them perfectly is worth more than serving everyone adequately.

**Decision test:** If a feature requires generalising the Malaysian fee structure or expanding beyond Bursa, it belongs in the V2 backlog.

---

## Principle 6: Reliability Is a Feature

**Description:** A portfolio tracker that shows stale prices is worse than no tracker at all — it gives users false confidence. Price data availability, system uptime, and data freshness are product features, not infrastructure footnotes. They must be designed, monitored, and communicated to users.

**Why it matters:** The yfinance dependency is the product's highest technical risk. If it fails silently, users make decisions on wrong data. If it fails visibly with a good fallback (manual entry, clear status message, last-updated timestamp), users can still function. The experience of a data failure is part of the product.

**Decision test:** Every feature that depends on external data must have a designed failure state. "It will usually work" is not an acceptable design assumption.

---

## Principle 7: Startup Discipline — Do Less, Better

**Description:** BursaTrack will ship fewer features than users ask for. Every feature added to v1 is a feature that delays validation of the core value proposition. We will resist scope creep, defer enhancement requests, and ship an MVP that does one thing perfectly: shows a Malaysian dividend investor their true portfolio yield, accurately, every day.

**Why it matters:** The PM Confidence Score on this product is 4/10. The biggest risk is spending 12 months building before discovering that willingness to pay is not validated. Speed to first paying user is the primary risk mitigation.

**Decision test:** If a feature does not directly increase the probability of a user completing onboarding or converting to a paid subscription, it is a v1.1 feature.

---

# 4. Problem Definition

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
- **Silent formula errors:** Complex formulas are difficult to audit; the row 28 bug is currently dormant but would silently corrupt calculations if a per-stock share count override were ever entered.
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

# 5. Business Objectives

## Primary Objective

Validate that a segment of Malaysian dividend investors will pay for a purpose-built Bursa portfolio tracker that materially reduces daily management effort and provides provably accurate cost and yield calculations.

## Secondary Objectives

- Establish BursaTrack as the reference tool for Malaysian dividend-income investors who manage 10+ positions.
- Build a defensible data moat through per-tranche dividend history and accurate cost-basis records that are time-consuming to replicate in free tools.
- Grow monthly active users (MAU) from the founder's personal use case to a paying subscriber base, validating the business model before scaling.

## Success Metrics

| Metric | Current State | Target (Month 6) | Target (Month 12) |
|--------|---------------|-----------------|-------------------|
| Paying subscribers | 0 | 100 | 200 |
| Monthly Recurring Revenue (MRR) | RM 0 | RM 2,000 | RM 4,000 |
| Daily active usage rate | 1 user (founder) | ≥ 60% of paying subscribers | ≥ 60% of paying subscribers |
| Portfolio onboarding completion rate | N/A | ≥ 50% of sign-ups | ≥ 70% of sign-ups |
| Price data uptime (trading days) | N/A | ≥ 99.5% | ≥ 99.5% |
| Monthly churn rate | N/A | < 7% | < 5% |

## Success Criteria

The initiative is considered successful if, within 12 months of public launch:

1. ≥ 200 users are paying subscribers with a monthly churn rate below 5%.
2. ≥ 3 unsolicited testimonials cite the Malaysian fee accuracy or dividend tracking as the primary reason for choosing BursaTrack over free alternatives.
3. At least one qualitative finding confirms users would not return to their previous spreadsheet workflow.

If criterion 1 is not met by month 6, the business case should be revisited; the product may be better positioned as a free open-source tool.

---

# 6. User Personas

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
David is 35, a software developer who manages a 20+ position Bursa portfolio as a serious side project. He actively compares yield across stocks, models buy/sell scenarios before acting, and tracks every dividend tranche to calculate his true annual income. He has already identified a formula bug similar to the row 28 issue in his own spreadsheet.

### Goals
- Accurate all-in cost basis per position per lot.
- Scenario modelling: "if I sell CIMB at RM8.60, what is my net profit after fees?"
- Aggregate portfolio yield across all 20 positions in one number.

### Motivations
- Maximising yield on capital deployed; every basis point matters to him.
- He would pay RM30/month for a tool that saves him 30 minutes daily and eliminates formula risk.

### Pain Points
- Excel formulas are brittle; he finds and fixes bugs but worries about the ones he misses.
- Has to manually model every sell scenario; no integrated calculator linked to live positions.
- No way to compare realised vs. expected yield historically.

### Behaviour Patterns
- Daily user, mornings and after market close.
- Uses Rakuten Trade; knows the fee schedule precisely.
- Would participate in a beta if invited.

### Usage Context
- Desktop, analytical, long sessions (15–20 minutes) weekly portfolio review plus quick daily checks.

---

# 7. Proposed Solution

## Solution Overview

BursaTrack is a web application for Malaysian dividend-focused retail investors that:

1. Maintains a portfolio of Bursa-listed stocks with per-lot position tracking.
2. Automatically fetches current market prices for all holdings on a daily basis.
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
| Build on top of KLSE Screener | No access; third-party product with no public contribution model |
| White-label Sharesight | Does not correctly model Malaysian fee structure; AUD 32/month pricing not viable for Malaysian retail market |
| Build a Google Sheets add-on | Limited automation capability; still desktop-locked; not a viable subscription product |
| Open-source personal tool (no monetisation) | Valid fallback if willingness-to-pay is not validated, but defers the business question rather than answering it |

---

# 8. Competitive Analysis

## Feature Comparison Matrix

*Legend: ✅ Yes / Fully supported | ⚠️ Partial / Limited | ❌ No / Not supported | ❓ Unconfirmed — assumption marked*

| Feature | BursaTrack (V1) | KLSE Screener | Sharesight | Google Sheets | Excel |
|---------|----------------|---------------|------------|---------------|-------|
| **Portfolio tracking** | ✅ | ✅ | ✅ | ⚠️ Manual | ⚠️ Manual |
| **Bursa Malaysia coverage** | ✅ | ✅ | ✅ | ⚠️ Via formula | ⚠️ Via formula |
| **Automated price refresh** | ✅ Daily | ✅ Real-time | ✅ | ⚠️ GOOGLEFINANCE() | ❌ Manual |
| **Dividend tracking** | ✅ | ✅ Ex-date + amounts | ✅ | ⚠️ Manual | ⚠️ Manual |
| **Per-tranche dividend logging (up to 8/year)** | ✅ | ❌ ❓ | ⚠️ ❓ Limited depth | ⚠️ Manual | ⚠️ Manual |
| **Broker-specific fee modelling** | ✅ Per-broker presets | ❌ | ❌ | ❌ | ⚠️ Single hard-coded rate |
| **Correct Malaysian fee stack** | ✅ 0.03% clearing + RM1/RM1,000 stamp duty | ❌ ❓ | ❌ Global model | ❌ | ⚠️ If user builds it |
| **True yield vs. all-in cost** | ✅ | ❌ ❓ | ⚠️ ❓ | ⚠️ If user builds it | ⚠️ Known ROI denominator bug |
| **Multi-lot position support** | ✅ | ❌ ❓ | ✅ | ⚠️ Manual | ⚠️ Manual |
| **Sell scenario calculator** | ✅ | ❌ | ❌ | ⚠️ Manual | ✅ Built into reference model |
| **Dividend calendar / ex-date alerts** | ✅ User-entered | ✅ Scraped from Bursa | ✅ | ❌ | ❌ |
| **CSV import** | ✅ V1 | ❌ | ✅ | ✅ | ✅ |
| **Mobile experience** | ✅ Responsive web | ✅ Native app | ✅ Native app | ⚠️ Limited | ❌ |
| **Offline access** | ❌ | ⚠️ App caching | ❌ | ❌ | ✅ |
| **Cost basis accuracy (all-in)** | ✅ | ❌ ❓ | ⚠️ ❓ | ⚠️ Manual | ⚠️ Partial — bug in row 28 |
| **Free tier** | ⚠️ Trial only | ✅ Free | ⚠️ Limited free tier | ✅ Free | ✅ One-time cost |
| **Pricing** | RM15–30/month (proposed) | Free | AUD 32/month | Free | One-time licence |
| **Malaysian market-specific** | ✅ | ✅ | ⚠️ Supports Bursa, not specialised | ❌ | ❌ |

> **❓ Assumption flags:** KLSE Screener's per-tranche dividend logging, true all-in cost basis, and per-broker fee modelling have not been verified by hands-on testing. **The founder must spend 2 hours using KLSE Screener for their own 16 positions before V1 scope is finalised.** If KLSE Screener already covers these features adequately, the business case must be revisited.

## Competitive Advantages

**1. Broker-specific fee precision.** No competitor currently models the brokerage fee at the individual broker level (MooMoo RM3 flat vs. Maybank 0.10% vs. Rakuten Trade tiered). This is BursaTrack's only fully defensible differentiator at launch.

**2. Per-tranche dividend depth.** If KLSE Screener shows totals only (assumption — requires verification), per-tranche logging is a meaningful gap for serious dividend investors.

**3. True all-in yield calculation.** Using all-in cost (not pre-fee initial amount) as the yield denominator is the correct calculation. KLSE Screener has not been confirmed to do this.

**4. Sell scenario calculator integrated with live positions.** No other portfolio tracker in this market integrates a sell fee calculator with live portfolio positions.

## Competitive Disadvantages

**1. KLSE Screener is free with a large, loyal user base.** Any conversion requires BursaTrack to be meaningfully better in specific, demonstrable ways.

**2. KLSE Screener has real-time data; BursaTrack has daily data from an unofficial API.** For dividend investors, daily is sufficient — but it is a visible disadvantage.

**3. No native mobile app at V1.** KLSE Screener and Sharesight have native apps with better mobile UX than a responsive web app.

**4. No automated dividend data.** KLSE Screener scrapes ex-date and dividend data from Bursa. BursaTrack requires manual entry — friction that compounds as the portfolio grows.

**5. Real switching cost from Excel.** Users with 3+ years of history face significant data migration effort. KLSE Screener requires no migration.

## Strategic Positioning Statement

BursaTrack must win on **accuracy** because it cannot win on **convenience** or **data breadth**. The marketing message: *"KLSE Screener tells you your portfolio is up. BursaTrack tells you whether your yield is actually what you think it is."*

---

# 9. Scope Definition

## In Scope

- User account creation and authentication.
- Portfolio management: add, edit, delete positions; support multiple lots per stock.
- Per-stock share count and broker selection for accurate fee calculation.
- Automated price fetching for Bursa-listed equities (daily during market hours).
- All-in buy cost calculation: brokerage (configurable per broker), clearing fee (0.03%), stamp duty (RM1/RM1,000 rounded up).
- Dividend tracking: log individual dividend payouts per stock per tranche (up to 8 per year), with per-share and total amounts.
- True ROI/yield calculation using all-in cost as denominator.
- Portfolio summary: total portfolio cost, total dividend income, blended yield.
- Highest-to-lowest yield sorting on the dashboard.
- Buy/sell scenario calculator linked to live positions.
- Dividend calendar: display ex-dates and payment dates for held stocks (user-entered).
- Manual price override: allow user to enter price if automated fetch fails.
- Price data freshness indicator (last-updated timestamp and outage status banner).
- CSV import for portfolio and dividend history onboarding.
- Mobile-responsive web interface (≥ 375px viewport).
- Subscription billing and trial management.
- PDPA-compliant privacy policy and user data export.

## Out of Scope

- Real-time intraday price streaming (daily price refresh is sufficient for dividend investors).
- Coverage of non-Bursa exchanges (SGX, HKEX, NYSE, etc.) at v1.
- Automated dividend amount scraping from Bursa announcements.
- Social features, discussion forums, or community feeds.
- Tax reporting or capital gains calculation.
- Integration with broker accounts or CDS via API (no public API access available).
- Native iOS / Android apps at launch (mobile-responsive web only).
- Warrants, ETFs, or structured products (equities only at launch).
- Multiple portfolios per user (one portfolio per account at v1).
- Push notifications / email alerts (deferred to v1.1).

## Future Considerations

- Push / email alerts for ex-dividend dates and declared dividends.
- Historical yield trend charts per stock and per portfolio.
- Broker API integration if Bursa or brokers open APIs.
- Google Sheets / other format import.
- KLSE market screener or stock discovery features.
- Native mobile apps if web MAU justifies the investment.
- SGX and other exchange support (Year 3 vision).
- SST toggle on brokerage fees — monitor Bursa's SST FAQ; if exemption status changes, promote to next release.

---

# 10. MVP Definition — Phased Release Plan

## MVP — Version 0.1 (Personal Validation Build)

**Purpose:** Validate that the core data model is correct, that automated price fetching works reliably for Bursa equities, and that the yield calculation is provably more accurate than the Excel model. Single-user only (founder). Target build time: 2–4 weeks.

| Feature | Why Here | Risk Addressed |
|---------|----------|---------------|
| Single-user portfolio (no auth) | Removes authentication complexity from the validation experiment | Validates data model without user management overhead |
| Add/edit/delete positions (one lot per stock) | Core data entry to test the model | Validates position structure and fee calculation logic |
| Broker-aware fee calculation (REQ-002) | Primary accuracy differentiator; must be validated against the Excel model | Confirms fee logic is correct before any other user sees it |
| True yield calculation (REQ-005) | Core metric; must be verified against known Excel values | Confirms the ROI denominator bug is fixed |
| Daily price fetch via yfinance for all 16 stocks (REQ-003) | Core automation claim; must be proven reliable before marketing it | Validates or disconfirms the price data dependency risk |
| Per-tranche dividend logging, up to 8 tranches (REQ-004) | Required to verify all-in yield; cannot be deferred | Validates dividend data model completeness |
| Portfolio summary: aggregate cost, income, yield (REQ-006, partial) | Required to compare against Excel model output | Validates end-to-end calculation chain |

**Not included in MVP:** Authentication, multi-user, CSV import, sell calculator, dividend calendar, mobile polish, subscription billing.

**MVP Exit Criteria:** The founder can use BursaTrack for all 16 positions for 20 consecutive trading days, confirm prices are correct on ≥ 99.5% of trading days, and verify that yield calculations match the corrected Excel model output.

---

## V1 — Public Launch

**Purpose:** Multi-user, paywall-gated, publicly launchable product. Must be compelling enough to convince a stranger to pay RM15–30/month. Target: 8–12 weeks after MVP exit criteria are met.

| Feature | Priority | Why Here | Why Not Moved |
|---------|----------|----------|--------------|
| User authentication | Must Have | Required for multi-user | Cannot be deferred — no paying users without it |
| Multi-lot position support (REQ-001) | Must Have | Users with multiple entry points need per-lot cost basis | V0.1 validated single-lot; multi-lot extends the model minimally |
| CSV import (REQ-009) | **Must Have ⬆️** | **Promoted from Should Have** — onboarding abandonment is the highest-probability failure mode; users with 10+ positions will not complete manual entry | Without this, most target users will abandon onboarding |
| Full portfolio dashboard (REQ-006) | Must Have | Public-facing core retention surface | N/A |
| Automated price refresh + manual override + status indicator (REQ-003) | Must Have | Core daily-use value proposition | N/A |
| Broker-aware fee calculation (REQ-002) | Must Have | Core accuracy differentiator | N/A |
| Per-tranche dividend logging (REQ-004) | Must Have | Core dividend-investor feature | N/A |
| True yield calculation (REQ-005) | Must Have | Core accuracy claim | N/A |
| Mobile-responsive interface (REQ-010) | Must Have | ~40% of target users will check on mobile (Farah persona) | Absence is a hard blocker for a meaningful user segment |
| Sell scenario calculator (REQ-007) | Must Have | Already spec'd to near-implementation precision from the Excel model; David persona explicitly requires it; build cost is low, retention value is high | Promoted from Should Have given low build cost and high persona alignment |
| Dividend calendar (REQ-008) | Should Have | Ex-date awareness is a daily use case driving return visits; without it the product is weaker than KLSE Screener on a feature users already rely on | Included in V1 given its role in daily engagement |
| Subscription billing and trial management | Must Have | Required to generate revenue | N/A |

**V1 Exit Criteria:** ≥ 10 non-founder users have completed full portfolio onboarding, at least 5 have converted to paid, and no data accuracy complaints have been filed in the first 30 days.

---

## V1.1 — Retention and Expansion

**Purpose:** Improve retention after initial conversion; address gaps identified from V1 user feedback. Target: 8–10 weeks after V1 launch.

| Feature | Why Deferred |
|---------|-------------|
| Push / email alerts for ex-dates and declared dividends | High value but requires notification infrastructure; deferred to keep V1 scope tight |
| Historical yield trend charts | Requires time-series data accumulation; not meaningful at launch with no history |
| Google Sheets import | Less universal than CSV; lower ROI on build effort; CSV covers the primary onboarding case |
| SST toggle on brokerage fees | Deferred pending verification of July 2025 Bursa SST FAQ; if SST applies, promote to V1 Must Have |
| PDPA-compliant data export (user data download) | Required for compliance but not a primary user workflow; can be added post-launch |
| "Fast start" mode (positions-only, no historical dividends at signup) | Reduces onboarding time further; validate from V1 drop-off data before building |
| Tiered broker fee support (Rakuten Trade model) | Simplified to two-rate model at V1; add tiered structure based on user demand |
| Multiple portfolios per user | One portfolio per account is sufficient for V1; add if users with multiple brokers or strategies request it |

> **⚠️ Priority Note:** The base PRD listed CSV Import as "Should Have." This has been promoted to **V1 Must Have** because onboarding abandonment is identified as the highest-probability failure mode (High impact, High probability in the risk register). A Should Have designation was inconsistent with the stated risk level. This decision requires stakeholder sign-off.

---

# 11. User Journey

## End-to-End Journey: First-Time Portfolio Setup and Daily Check

| Step | User Goal | User Action | Expected Outcome |
|------|-----------|-------------|-----------------|
| 1 | Discover BursaTrack | Lands on product page via search, KLSE Screener forum, or referral | Clear value proposition page; CTA to start free trial |
| 2 | Create account | Enters email and password | Account created; directed to empty portfolio dashboard |
| 3 | Configure broker settings | Selects broker from list (e.g., MooMoo, Maybank Investment, Rakuten Trade) | Brokerage rate pre-filled; user can override |
| 4 | Add first position (or import CSV) | Enters stock code, number of shares, purchase price, purchase date — or uploads CSV | Position(s) appear on dashboard with calculated all-in buy cost |
| 5 | Add dividend history | For each stock, enters historical dividend tranches (date, amount per share) | Total dividend income and yield calculated and displayed |
| 6 | Complete portfolio setup | All holdings entered | Full portfolio visible with aggregate summary and blended yield |
| 7 | Daily morning check | Returns next day | Prices auto-refreshed; all portfolio values, yields, and income current without manual effort |
| 8 | Check dividend calendar | Wants to know next payment | Calendar view shows upcoming ex-dates and payment dates for held stocks |
| 9 | Model a sell scenario | Considering selling; wants net profit at target price | Opens sell calculator; enters target sell prices; sees net proceeds and profit/loss at each price |
| 10 | Log new dividend received | Stock declares interim dividend | Adds new tranche entry; total income and yield update immediately |

### Entry Points
- Direct navigation (bookmarked URL, daily morning habit).
- Organic search: "Bursa Malaysia dividend tracker," "Malaysia stock portfolio tracker."
- Community referral: i3investor forum, KLSE Screener community, Reddit r/MalaysianPF.

### Exit Points
- User completes portfolio setup and bookmarks dashboard for daily return.
- User abandons during onboarding if data entry time exceeds 10–20 minutes (mitigated by CSV import).

### Decision Points
- During onboarding: manual entry vs. CSV import.
- At subscription paywall: will the user convert from free trial to paid?
- After price data outage: will the user use manual override, or churn?

### Failure Points
- **Onboarding drop-off:** User with 16 positions and 3 years of dividend history abandons before completing setup (mitigated by CSV import in V1).
- **Price fetch failure:** yfinance API returns stale or missing data during market hours (mitigated by status banner and manual override).
- **Fee confusion:** User selects wrong broker, receives inaccurate yield, loses trust.
- **Dividend entry complexity:** User unsure about per-share vs. aggregate amount; enters wrong value.

---

# 12. High-Level Product Requirements

---

## REQ-001 — Portfolio Position Management

**Description:** Users can add, edit, and delete equity positions. Each position records: stock code, stock name, number of shares, purchase price per share, purchase date, and broker. Multiple lots per stock are supported (e.g., two separate purchases of CIMB at different prices). Category tags (Dividend / Volatile / Growth) can be assigned to each position.

**User Value:** Accurately reflects real portfolio structure; supports true cost basis calculation per lot.

**Business Value:** Core retention driver — populated portfolio data creates switching cost.

**Priority:** Must Have

### User Stories

- As **Ahmad**, I want to add a new stock position with my purchase price and number of shares, so that I can see my true cost basis for that holding from day one.
- As **David**, I want to record multiple lots for the same stock at different purchase prices, so that I can calculate the blended cost basis across all my entries.
- As **Farah**, I want to edit a position I entered incorrectly, so that my portfolio always reflects my actual holdings without starting over.
- As **Ahmad**, I want to tag a holding as "Dividend" or "Volatile/Growth," so that my dashboard separates income positions from capital-gain positions the way my current spreadsheet does.

### Acceptance Criteria

**Add a new position**
```
Given I am logged in and my portfolio is open
When I add a new stock position: "CIMB 1023", 5,000 shares, purchase price RM8.38, broker "Maybank Investment"
Then the position appears in my portfolio dashboard
And the initial purchase amount is RM41,900.00 (5,000 × 8.38)
And the all-in cost is RM41,996.47 (initial amount + brokerage + clearing + stamp duty)
And the position is tagged with the selected broker
```

**Add a second lot to an existing position**
```
Given I have an existing CIMB position at RM8.38 for 5,000 shares
When I add a second lot for CIMB at RM9.00 for 2,000 shares
Then both lots appear under the CIMB position
And the blended cost basis is the weighted average of both lots
And total CIMB shares shows 7,000
```

**Edit a position**
```
Given I have an existing position with an incorrect share count
When I edit the share count from 5,000 to 4,000
Then all dependent calculations (all-in cost, dividend income, yield) recalculate immediately
And the portfolio summary totals update to reflect the change
```

**Delete a position**
```
Given I have an existing position I want to remove
When I delete the position
Then the position is removed from the portfolio
And all associated dividend tranche records are also removed
And portfolio summary totals update immediately
```

---

## REQ-002 — Broker-Aware Fee Calculation

**Description:** The system calculates all-in buy cost per position using the Malaysian fee stack: brokerage (configurable per broker from a pre-set list with user-override), clearing fee (0.03% of contract value), and stamp duty (RM1 per RM1,000 rounded up, per the Bursa Malaysia gazette in force until 12 July 2028). The correct denominator for yield calculation is the all-in cost, not the pre-fee purchase amount.

**User Value:** Eliminates the single biggest accuracy flaw in spreadsheet-based tracking; users know their true cost basis.

**Business Value:** Core product differentiator vs. free tools. Correctly modelling per-broker fees (MooMoo RM3 flat vs. Maybank 0.10%) is a capability no free competitor currently provides at position level.

**Priority:** Must Have

### User Stories

- As **Farah**, I want to select my broker (MooMoo) when adding a position, so that my cost basis uses the correct RM3 flat fee instead of the default 0.10% rate.
- As **David**, I want to override the brokerage rate for a specific position, so that I can model the exact fee charged if my broker uses a non-standard rate.
- As **Ahmad**, I want clearing fee (0.03%) and stamp duty (RM1/RM1,000) calculated automatically, so that I don't have to verify the formula myself.
- As **David**, I want the yield calculation to use my all-in cost as the denominator, so that my ROI is not overstated by excluding transaction costs.

### Acceptance Criteria

**Standard percentage broker (Maybank Investment)**
```
Given I have selected "Maybank Investment" (rate: 0.10%, min RM8)
When I add a position with initial amount RM41,900
Then brokerage fee = RM41.90 (RM41,900 × 0.10%)
And clearing fee = RM12.57 (RM41,900 × 0.03%)
And stamp duty = RM42.00 (ROUNDUP(41,900 / 1,000, 0))
And all-in cost = RM41,996.47
```

**Flat-fee broker (MooMoo)**
```
Given I have selected "MooMoo" (rate: RM3 flat per trade)
When I add a position with initial amount RM41,900
Then brokerage fee = RM3.00 (flat fee)
And clearing fee and stamp duty are calculated identically to other brokers
And all-in cost reflects the lower RM3.00 brokerage
```

**Brokerage minimum applied**
```
Given a percentage-based broker (0.10%, min RM8)
When I add a position with initial amount RM3,000 (e.g., FM at RM0.60 × 5,000 shares)
Then 0.10% of RM3,000 = RM3.00, which is below the RM8 minimum
And brokerage fee = RM8.00 (minimum applied)
```

**Stamp duty rounding**
```
Given any position with initial amount RM41,900
Then stamp duty = ROUNDUP(41,900 / 1,000, 0) = ROUNDUP(41.9, 0) = 42
And stamp duty = RM42.00
```

---

## REQ-003 — Automated Daily Price Refresh

**Description:** Current market prices for all held Bursa-listed equities are refreshed automatically on trading days. Price data is sourced from an available market data provider. Users are clearly informed if price data is stale or unavailable, and can enter a manual price override per position.

**User Value:** Eliminates the 10–15 minutes of daily manual price entry that is the primary stated pain.

**Business Value:** Without automation, the product does not deliver on its core promise; acquisition and retention both depend on this working reliably.

**Priority:** Must Have

### User Stories

- As **Ahmad**, I want my portfolio prices updated automatically on trading days, so that I don't spend 10–15 minutes entering prices each morning.
- As **Farah**, I want to see when prices were last updated, so that I know whether I'm looking at today's or yesterday's data.
- As **David**, I want to manually enter a price override for any position, so that I can correct the data when the automated feed is unavailable.
- As any user, I want a clear status message when price data is stale or unavailable, so that I don't make decisions based on outdated prices without realising it.

### Acceptance Criteria

**Prices update on a trading day**
```
Given I have a portfolio with active positions
When a Bursa Malaysia trading day begins
Then prices for all positions are refreshed at least once during market hours
And the dashboard displays a "Last updated: [timestamp]" label per price
```

**Price data unavailable**
```
Given the automated price feed is unavailable
When I open my dashboard
Then a visible status banner reads: "Price data unavailable — showing prices as of [last successful update]. Enter prices manually to continue."
And a manual price override field is available for each position
```

**Manual price override**
```
Given a price feed failure is in progress
When I manually enter RM8.50 for CIMB
Then the CIMB position recalculates unrealised P&L using RM8.50
And the override is flagged visually (e.g., "Manual — [time entered]")
And the override is replaced by the automated price on the next successful refresh
```

---

## REQ-004 — Per-Tranche Dividend Logging

**Description:** For each stock, users can log individual dividend payments (up to 8 tranches per year). Each tranche records: payout label (1st–8th), dividend per share (MYR), payment date, and optionally ex-dividend date. The system aggregates to total dividend per share and total dividend income per position.

**User Value:** Mirrors the granularity in the Excel model; supports accurate dividend income tracking across multiple payment cycles.

**Business Value:** Dividend investors track dividends at tranche level — this depth is not confirmed to be available in KLSE Screener; it is a primary differentiating feature for the target segment.

**Priority:** Must Have

### User Stories

- As **Ahmad**, I want to log each interim dividend payment separately (1st, 2nd, 3rd), so that I can track when dividends were received and which announcements they correspond to.
- As **David**, I want to log up to 8 dividend tranches per stock per year, so that I can track every payment for multi-payout stocks like CARLSBG or TIMECOM.
- As **Farah**, I want the total dividend per share calculated automatically from all my tranche entries, so that I don't have to manually sum them.
- As **Ahmad**, I want to record the payment date alongside each tranche, so that I can reconcile with my broker's payment confirmation.

### Acceptance Criteria

**Log first dividend tranche**
```
Given I have a CIMB position (5,000 shares) in my portfolio
When I log the 1st tranche: RM0.20/share, payment date 2026-03-15
Then the tranche appears as "1st Tranche: RM0.20/share — 15 Mar 2026"
And total dividend income for CIMB = RM1,000 (5,000 × RM0.20)
And total dividend per share for CIMB = RM0.20
```

**Log subsequent tranche — aggregate check**
```
Given CIMB already has a 1st tranche of RM0.20/share
When I log the 2nd tranche at RM0.1975/share
Then total dividend per share for CIMB = RM0.3975
And total dividend income = RM1,987.50 (5,000 × RM0.3975)
And yield recalculates immediately
```

**Maximum tranche limit**
```
Given a stock already has 8 dividend tranches logged
When I attempt to add a 9th tranche
Then the system prevents the addition and displays: "Maximum of 8 dividend tranches per year reached for this stock"
```

---

## REQ-005 — Yield (ROI) Calculation

**Description:** The system calculates and displays dividend yield for each position as: total dividend income ÷ all-in buy cost (inclusive of all fees). Portfolio-level blended yield is also displayed. Both per-position and portfolio yields update whenever a new dividend tranche is logged or a position is modified.

**User Value:** A single, accurate number that reflects true return on capital deployed, correcting the known flaw in the spreadsheet model.

**Business Value:** Accuracy here is the primary trust signal. Users who verify a correct yield calculation will have confidence in the rest of the product.

**Priority:** Must Have

### User Stories

- As **Ahmad**, I want dividend yield calculated as total dividend income divided by my all-in cost, so that I have an accurate measure of my income return on invested capital.
- As **David**, I want to see the portfolio blended yield — sum of all dividend income divided by total all-in cost — so that I can assess my income portfolio as a whole.
- As **Farah**, I want the yield to update automatically when I log a new dividend tranche, so that my dashboard always reflects the latest income received.
- As **David**, I want to see the yield calculation broken down (total dividend ÷ all-in cost), so that I can verify the number is being calculated correctly.

### Acceptance Criteria

**Yield calculated against all-in cost**
```
Given CIMB has an all-in buy cost of RM41,996.47 and total dividend income of RM2,337.50
When the yield is calculated
Then yield = RM2,337.50 ÷ RM41,996.47 = 5.57%
And the yield is NOT 5.58% (which would result from using pre-fee cost of RM41,900)
```

**Portfolio blended yield**
```
Given I have 16 positions with known all-in costs and dividend income
When the portfolio summary displays blended yield
Then blended yield = sum of all dividend income ÷ sum of all all-in costs
And individual position yields are displayed separately
```

**Yield updates on dividend log**
```
Given CIMB has a yield of 5.57%
When I log a new 3rd tranche of RM0.07/share (RM350 total income added)
Then total dividend income for CIMB = RM2,687.50
And yield updates immediately (≈ 6.40%)
And portfolio blended yield recalculates
```

---

## REQ-006 — Portfolio Summary Dashboard

**Description:** The dashboard displays: total portfolio all-in cost, total annual dividend income, portfolio blended yield, and per-position breakdown (cost, income, yield, current value, unrealised P&L). Category tags (Dividend / Volatile) are displayed. Positions can be sorted by yield. The dashboard loads within 3 seconds.

**User Value:** Replaces the spreadsheet's multi-column view with a clean, scannable summary requiring zero manual calculation.

**Business Value:** The dashboard is the primary daily-use surface; its quality determines retention.

**Priority:** Must Have

### User Stories

- As **Ahmad**, I want to see all my positions in a single dashboard view with current price, all-in cost, total dividend income, and yield, so that I can assess my full portfolio in under 5 minutes.
- As **Farah**, I want to see my total dividend income for the year at the top of the dashboard, so that I can immediately see whether I'm on track for my income target.
- As **David**, I want to sort positions by yield, so that I can identify my highest-returning holdings at a glance.
- As any user, I want total portfolio all-in cost and blended yield visible in a summary header without scrolling, so that I see the most important numbers immediately.

### Acceptance Criteria

**Dashboard summary header**
```
Given I have a portfolio with at least one position and one dividend logged
When I open the portfolio dashboard
Then I see in the header: total all-in portfolio cost, total annual dividend income, portfolio blended yield
And the dashboard loads within 3 seconds on a standard broadband connection
```

**Position sorting**
```
Given I am viewing the portfolio dashboard
When I click "Sort by Yield"
Then positions reorder from highest to lowest yield
And the sort preference persists for my next session
```

---

## REQ-007 — Buy/Sell Scenario Calculator

**Description:** For any position in the portfolio, users can model a sell at one or more price points. The calculator outputs gross proceeds, brokerage fee, clearing fee, stamp duty, net proceeds, and profit/loss (net proceeds minus all-in buy cost). The calculator uses the position's actual broker fee rate. Break-even price is highlighted.

**User Value:** Replicates and improves on the spreadsheet's calculator panel — linked to live position data rather than requiring manual re-entry.

**Business Value:** Retention feature for active investors who evaluate sell timing; increases session depth and daily engagement.

**Priority:** Must Have

### User Stories

- As **David**, I want to enter a target sell price for any position and see net proceeds after all fees, so that I can calculate my actual profit before executing a trade.
- As **David**, I want to see profit/loss at multiple sell price points simultaneously (at +0.01, +0.05, +0.10 increments), so that I can assess break-even and target return at a glance.
- As **Ahmad**, I want the sell calculator to use my actual broker fee rate, so that the profit/loss calculation reflects my true trading cost.
- As **Farah**, I want the sell calculator to highlight my break-even price, so that I know my floor before deciding to sell.

### Acceptance Criteria

**Sell scenario at multiple price points**
```
Given CIMB was purchased at RM8.38 for 5,000 shares with all-in buy cost RM41,996.47
When I open the sell calculator and request scenarios at RM8.39, RM8.40, RM8.41, RM8.42
Then at RM8.42: net proceeds ≈ RM42,002.27, profit/loss ≈ +RM5.80 (break-even)
And at RM8.39: profit/loss is negative
And at RM8.42 the row is highlighted as break-even
```

**Sell calculator uses actual broker rate**
```
Given my broker is MooMoo (RM3 flat brokerage)
When I run a sell scenario
Then the sell brokerage fee = RM3.00 flat (not 0.10% of gross proceeds)
```

---

## REQ-008 — Dividend Calendar

**Description:** A calendar or chronological list view surfacing upcoming ex-dividend dates and expected payment dates for stocks held in the portfolio. Data is user-entered (no automated scraping). Dates are captured when logging dividend tranches.

**User Value:** Eliminates the need to track ex-dates externally; supports dividend reinvestment planning.

**Business Value:** Increases daily return visits around ex-date periods; a stickiness mechanism.

**Priority:** Should Have (V1)

### User Stories

- As **Ahmad**, I want to see upcoming ex-dividend dates for all my holdings in order, so that I can ensure I hold the stock before the ex-date to qualify for the dividend.
- As **Farah**, I want to see expected dividend payment dates, so that I can plan my cash flow around when income arrives.
- As **David**, I want to add ex-date and payment date when logging a dividend tranche, so that my calendar reflects all historically known dates.

### Acceptance Criteria

**Calendar with data**
```
Given I have logged dividend tranches with ex-dates for my positions
When I open the dividend calendar
Then I see upcoming ex-dates for my held stocks in chronological order
And past ex-dates from the current year are also visible with payment dates
```

**Empty state**
```
Given I have positions but have not entered any ex-dates
When I open the dividend calendar
Then the calendar displays: "Add ex-dates when logging dividends to see your payment schedule here"
```

---

## REQ-009 — CSV Import for Portfolio Onboarding

**Description:** Users can import historical positions and dividend records from a structured CSV template. The product provides a downloadable template and validation feedback on import errors. Positions can be imported without dividend history for a "fast start." Import completes within 30 seconds for files up to 100 positions.

**User Value:** Reduces onboarding from an estimated 45 minutes of manual entry to under 10 minutes for users migrating from Excel or Google Sheets.

**Business Value:** Onboarding completion rate is the primary conversion lever. CSV import is the most direct way to move users from spreadsheets to BursaTrack without abandonment.

**Priority:** Must Have *(Promoted from Should Have — onboarding abandonment is the highest-probability, highest-impact risk. This decision requires stakeholder sign-off.)*

### User Stories

- As **Ahmad**, I want to import my existing portfolio from a CSV file, so that I don't spend 45 minutes manually entering 16 positions and 3 years of dividend history.
- As **David**, I want to download a CSV template that matches the expected import format, so that I know exactly how to structure my data before importing.
- As any user, I want clear validation feedback if my import file has errors, so that I can fix the issue without re-uploading the entire file.
- As **Farah**, I want to import positions without requiring dividend history, so that I can get to first value quickly and add dividends later.

### Acceptance Criteria

**Successful import**
```
Given I have populated the BursaTrack CSV template with 16 positions and dividend history
When I upload the file
Then all positions are created with correct share counts, purchase prices, and broker assignments
And all dividend tranches are created with correct per-share amounts and dates
And the dashboard immediately shows my full portfolio with calculated yields
And the import completes within 30 seconds
```

**Validation error**
```
Given I upload a CSV file with a missing "shares" column value in row 5
When the import runs
Then the system displays: "Import error: Row 5 — 'shares' column is required but was empty. No records were imported."
And my existing portfolio is unchanged
```

**Template download**
```
Given I am on the import page
When I click "Download Template"
Then a CSV file downloads with pre-populated column headers and one example row
And the template includes a column guide explaining each field
```

---

## REQ-010 — Mobile-Responsive Interface

**Description:** All core features (dashboard, portfolio view, dividend logging, sell calculator, dividend calendar) are accessible and usable on a mobile browser at standard screen widths (≥ 375px). Interactive elements have tap targets of at least 44×44px. Numeric input fields trigger a numeric keyboard on iOS and Android.

**User Value:** Enables on-the-go portfolio checks; critical for users like Farah who check from a commute.

**Business Value:** Mobile responsiveness is table stakes for consumer SaaS; absence would be a hard blocker for a meaningful user segment.

**Priority:** Must Have

### User Stories

- As **Farah**, I want to check my portfolio on my phone during my commute, so that I don't have to wait until I'm at a desktop to see my latest numbers.
- As any user, I want all core features to work correctly on a mobile browser at 375px width, so that I'm not blocked on desktop for any daily task.
- As **Ahmad**, I want portfolio values and yields readable without horizontal scrolling on mobile, so that I can scan key numbers in under 30 seconds.

### Acceptance Criteria

**Dashboard usable on mobile**
```
Given I open BursaTrack on a mobile browser at 375px viewport width
When the dashboard loads
Then all key metrics (portfolio cost, total income, blended yield) are visible without horizontal scrolling
And each position row is readable with stock name, yield, and current value visible
And all interactive elements have tap targets of at least 44×44px
```

**Dividend logging on mobile**
```
Given I am using BursaTrack on mobile
When I navigate to add a dividend tranche
Then the form is usable with a mobile keyboard
And numeric input fields trigger a numeric keyboard on iOS and Android
And the submission button is reachable without scrolling past the form
```

---

# 13. Non-Functional Requirements

## Performance

| Requirement | Target | Notes |
|-------------|--------|-------|
| Dashboard initial load time | ≤ 3 seconds on 20 Mbps connection | From navigation to full portfolio render |
| Dashboard load time (returning user, cached prices) | ≤ 1.5 seconds | Cached price data eliminates repeat API calls within a session |
| Portfolio calculation time (yield, all-in cost) | < 200ms client-side | Deterministic calculations; no server round-trips |
| CSV import processing time | ≤ 30 seconds for files up to 100 positions / 800 dividend entries | Server-side; user receives progress indicator |
| Sell calculator response time | < 100ms | Synchronous calculation; no API call required |
| Price refresh cycle duration | ≤ 5 minutes to refresh all positions during trading hours | User sees "prices updating" state during window |

## Reliability

| Requirement | Target | Notes |
|-------------|--------|-------|
| System uptime (trading days, 8 AM–7 PM MYT) | ≥ 99.5% | < 3.65 hours downtime per year during trading hours |
| System uptime (off-peak) | ≥ 99.0% | Lower threshold for overnight / weekend periods |
| Price data freshness on trading days | ≥ 99.5% of trading days have at least one successful refresh per position | Measured over rolling 30-day window |
| Price data outage detection time | ≤ 5 minutes | System detects failed refresh and surfaces a user-facing warning |
| Data backup frequency | Daily automated backup | Point-in-time recovery strongly recommended |
| Recovery Time Objective (RTO) | ≤ 4 hours | Maximum downtime before service restoration |
| Recovery Point Objective (RPO) | ≤ 24 hours | Maximum data loss acceptable in a worst-case failure |

## Security

| Requirement | Target | Notes |
|-------------|--------|-------|
| Authentication method | Email + password with bcrypt hashing (min cost factor 12) or equivalent | No plain-text password storage |
| Password requirements | Minimum 8 characters; at least one number and one letter | Display strength indicator; enforce on registration and reset |
| Session management | Sessions expire after 30 days of inactivity; explicit logout available | HTTP-only, Secure cookies for session tokens |
| Transport encryption | HTTPS enforced across all endpoints; TLS 1.2 minimum | HTTP redirects to HTTPS; HSTS header required |
| Data encryption at rest | User portfolio data encrypted at rest | AES-256 or equivalent |
| Rate limiting | Auth endpoints: max 5 failed attempts per 10 minutes per IP before lockout | Prevents brute-force attacks |
| CSRF protection | All state-changing requests protected by CSRF tokens | Standard framework-level protection |
| Sensitive data in logs | Portfolio values, dividend amounts, and personal data must NOT appear in server logs | Log sanitisation required |

## Scalability

| Requirement | Target | Notes |
|-------------|--------|-------|
| Concurrent users at V1 launch | Support ≥ 500 concurrent active sessions without degradation | Conservative target for initial deployment |
| Portfolio size per user | Support ≥ 50 positions and ≥ 400 dividend tranche records per user | 10× the reference Excel model |
| Total price refresh load | Support ≥ 10,000 price lookup calls per trading day | 500 users × 20 positions with buffer |
| Database growth | Design for ≥ 10,000 user accounts and ≥ 500,000 dividend tranche records in Year 1 | Should not require re-architecture to achieve |

## Auditability

| Requirement | Target | Notes |
|-------------|--------|-------|
| Dividend tranche edit history | Every change to a tranche (amount, date) is logged with previous value and timestamp | Required for user trust and error correction |
| Position edit history | Every change to a position (share count, price, broker) is logged | Silent correction of errors undermines trust |
| Price override log | Manual overrides recorded with timestamp and replaced-by value when automated data resumes | Enables verification that overrides were superseded |
| Change attribution | All edits attributed to the authenticated user who made them | Required for PDPA accountability |

## Compliance

| Requirement | Target | Notes |
|-------------|--------|-------|
| PDPA — Data minimisation | Collect only email, password, and portfolio data; no national ID, phone, or financial account numbers | Not a financial institution |
| PDPA — Data access | Users can request a full export of their data in CSV format | PDPA right of access |
| PDPA — Data deletion | Users can request account and all associated data deletion; completed within 30 days | PDPA right of erasure |
| PDPA — Privacy policy | A PDPA-compliant privacy policy must be live before user accounts are created | Required by Malaysian law |
| Financial disclaimer | All yield, P&L, and scenario calculations accompanied by: "BursaTrack is a portfolio tracking tool and does not provide financial advice. All calculations are informational only." | Avoids regulatory characterisation as a financial advisory service |
| Stamp duty rate configurability | The stamp duty rate must be configurable without a code deployment | Required to update if the 0.10% remission expires July 2028 |

---

# 14. Core Domain Model

*Conceptual business model. Not a database schema.*

---

## User

**Purpose:** A registered account holder with their own private portfolio.

**Key Attributes:** Email address (unique), password (hashed), default broker, account status (trial / active / cancelled), trial expiry date, account creation date.

**Relationships:** A User owns one Portfolio. A User has one default Broker setting.

---

## Portfolio

**Purpose:** The container for all of a user's Bursa equity holdings. One Portfolio per user at V1.

**Key Attributes:** Owner (User), total all-in cost (derived), total dividend income (derived), blended yield (derived), last price refresh timestamp.

**Relationships:** A Portfolio belongs to one User. A Portfolio contains one or more Positions.

---

## Position

**Purpose:** A specific stock held in the portfolio. Represents one security (e.g., CIMB 1023) and may contain multiple Lots.

**Key Attributes:** Stock code, stock name, category tag (Dividend / Volatile / Growth), total shares (derived), blended purchase price per share (derived), total initial purchase amount (derived), total all-in cost (derived), total dividend income (derived), total dividend per share (derived), dividend yield (derived), current price (from PriceSnapshot or manual override), current market value (derived), unrealised P&L (derived).

**Relationships:** A Position belongs to one Portfolio. A Position has one or more Lots. A Position has zero or more DividendTranches. A Position references one PriceSnapshot (current price).

---

## Lot

**Purpose:** A single purchase of a Position at a specific price and date. Multiple Lots represent different entry points.

**Key Attributes:** Parent Position, number of shares, purchase price per share, purchase date, broker, initial purchase amount (derived), brokerage fee (derived), clearing fee (derived), stamp duty (derived), all-in cost (derived).

**Relationships:** A Lot belongs to one Position. A Lot references one Broker.

---

## Broker

**Purpose:** A brokerage firm with its specific fee structure for Bursa Malaysia equity trades.

**Key Attributes:** Broker name, fee type (percentage or flat), fee rate, minimum fee.

**Relationships:** A Broker is referenced by one or more Lots. A Broker is the default for a User.

**Notes:** Pre-populated reference list of common Malaysian brokers (Maybank Investment, MooMoo, Rakuten Trade, M+ Online, Hong Leong) plus a "Custom" option. V1 simplifies tiered brokers (e.g., Rakuten Trade) to a single rate with user override; tiered support added in V1.1.

---

## DividendTranche

**Purpose:** A single declared dividend payment for a Position. Up to 8 tranches per Position per calendar year.

**Key Attributes:** Parent Position, tranche number (1st–8th), dividend per share (MYR), total dividend amount (derived: per share × total shares), payment date, ex-dividend date (optional), year.

**Relationships:** A DividendTranche belongs to one Position.

**Notes:** Per-share amount is stored; total is derived. This enables recalculation if share count is edited — and avoids the row 28 formula class of bug where a derived total is stored and becomes stale.

---

## PriceSnapshot

**Purpose:** The most recent known price for a stock, from automated refresh or manual override.

**Key Attributes:** Stock code, price (MYR), source (automated / manual), timestamp, trading day.

**Relationships:** A PriceSnapshot is referenced by one or more Positions with the same stock code.

**Notes:** One PriceSnapshot per stock per trading day. Multiple Positions holding the same stock share one price record.

---

## SellScenario (Transient — Not Persisted)

**Purpose:** A transient calculation object for one sell simulation at a given price point.

**Key Attributes:** Source Position, sell price, gross proceeds (derived), sell brokerage fee (derived), sell clearing fee (derived), sell stamp duty (derived), net proceeds (derived), profit/loss (derived: net proceeds − all-in buy cost), break-even flag.

**Relationships:** References one Position (or built ad-hoc without a portfolio position).

---

# 15. Product Analytics & Success Metrics

## Acquisition

| Metric | Description | Target (Month 6) |
|--------|-------------|-----------------|
| Weekly sign-ups | New account registrations per week | 20 sign-ups/week |
| Source attribution | % of sign-ups from search / referral / community | ≥ 40% organic search by month 6 |
| Landing page conversion rate | Registrations started / total visitors | ≥ 8% |
| Registration drop-off | Users who begin but do not complete registration | < 20% |

## Activation

Activation = at least one position added with all-in cost calculated + at least one dividend tranche logged.

| Metric | Description | Target |
|--------|-------------|--------|
| First position added | % of registered users who add ≥ 1 position | ≥ 80% within 24 hours |
| Onboarding completion | % who add ≥ 3 positions AND ≥ 1 dividend tranche | ≥ 50% within 7 days |
| CSV import usage | % of onboarding users using CSV vs. manual entry | Track; use to inform V1.1 onboarding investment |
| Time-to-first-value | Time from account creation to first yield calculation displayed | Median ≤ 10 minutes |
| Activation rate | % of sign-ups reaching "activated" state | ≥ 50% |

## Engagement

| Metric | Description | Target (Month 6) |
|--------|-------------|-----------------|
| Daily Active Users (DAU) | Unique users opening the dashboard on a trading day | 60% of paying subscribers |
| Weekly Active Users (WAU) | Unique users active in a 7-day window | ≥ 85% of paying subscribers |
| Monthly Active Users (MAU) | Unique users active in a 30-day window | ≥ 95% of paying subscribers |
| DAU/MAU ratio | Daily stickiness indicator | ≥ 0.50 |
| Dividend logging rate | % of active users logging ≥ 1 dividend per month | ≥ 70% |
| Sell calculator usage | % of active users using the calculator ≥ once per month | ≥ 30% |
| Median session length | Time spent per session | 3–8 minutes |

## Retention

| Metric | Description | Target |
|--------|-------------|--------|
| D7 retention | % still active 7 days after sign-up | ≥ 50% |
| D30 retention | % still active 30 days after sign-up | ≥ 35% |
| D90 retention | % still active 90 days after sign-up | ≥ 25% |
| Monthly churn rate (paid) | % of paying subscribers who cancel per month | < 5% at month 12 |
| Churn reason capture | % of cancellations with reason recorded | ≥ 60% |

**Churn early-warning signals to instrument:**
- User has not opened the dashboard in 7 consecutive trading days.
- User has not logged a dividend in 45 days (portfolio may be stale).
- User's last price refresh failed and manual override was not used within 48 hours.

## Revenue

| Metric | Description | Target |
|--------|-------------|--------|
| Trial conversion rate | % of trial users converting to paid | ≥ 25% |
| MRR | Total subscription revenue per month | RM 2,000 (month 6); RM 4,000 (month 12) |
| ARPU | MRR ÷ paying subscribers | RM 20/month |
| Paying subscribers | Total active paid accounts | 100 (month 6); 200 (month 12) |
| LTV estimate | ARPU ÷ monthly churn rate | RM 400 at 5% churn |

## Analytics Implementation Notes

Recommended: a privacy-respecting, self-hosted analytics tool (e.g., Plausible, PostHog) over Google Analytics, given financial data sensitivity and PDPA compliance requirements.

**Key events to instrument at launch:**
`account_created` · `first_position_added` · `onboarding_completed` · `csv_imported` · `dividend_logged` · `sell_calculator_opened` · `subscription_trial_started` · `subscription_converted` · `subscription_cancelled` (with reason) · `price_refresh_failed` · `manual_price_override_entered`

---

# 16. Assumptions

| Assumption | Risk Level | Validation Needed |
|------------|------------|------------------|
| A meaningful segment of Malaysian retail investors (≥ 10,000 people) share the same daily spreadsheet friction as the founder | High | Qualitative interviews with 10–15 Bursa investors who use Excel or Google Sheets; confirm daily update pain and willingness to switch |
| Target users will pay RM15–30/month for accuracy and convenience | High | Run 10 willingness-to-pay conversations before building subscription billing; consider a waitlist with pricing page |
| BursaTrack's fee accuracy and dividend depth are not features KLSE Screener will ship within 6–12 months | Medium | Monitor KLSE Screener release notes; also complete hands-on evaluation to confirm the gap exists today |
| yfinance (or an alternative data source) provides reliable Bursa data on ≥ 99.5% of trading days | High | Run a 20-day monitoring experiment on all 16 target stocks before launching |
| Bursa stamp duty remains at 0.10% through July 2028 as gazetted | Low | Already confirmed by official gazette; set a calendar reminder for June 2028 |
| SST on brokerage fees for Bursa equity trades remains exempt | Medium | Verify against Bursa SST FAQ updated July 2025 before fee calculator ships |
| CSV import is sufficient to resolve onboarding friction | Medium | Time a pilot user importing their own transaction history using the CSV template before launch |
| Dividend investors in Malaysia have a stable, multi-year holding horizon justifying ongoing subscription cost | Medium | Directionally confirmed by founder's profile; unconfirmed for the broader segment |

---

# 17. Constraints

## Business Constraints

- Solo founder / small team; feature scope must be ruthlessly prioritised to a shippable V1.
- No external funding confirmed; initial development must be bootstrappable.
- Revenue model is unvalidated; the product should reach first paying user within 90 days of development start.

## Operational Constraints

- Price data cannot be sourced from a paid institutional API at launch without subscription revenue to offset cost; solution must use a free or low-cost data source initially, with a migration plan if reliability is unacceptable.
- No broker API integrations are available in the Malaysian market; all position and dividend data is user-entered or CSV-imported.
- Settlement cycle (T+2) must be communicated to users in the sell calculator but does not require system-level handling at V1.

## Legal / Regulatory Constraints

- BursaTrack is a personal portfolio tracking tool, not a licensed financial advisory service. The product must not provide investment recommendations, buy/sell signals, or be positioned as financial advice.
- Malaysian Securities Commission (SC) licensing requirements apply to financial advisory and fund management services; confirm with a Malaysian legal advisor that a portfolio tracking tool without advisory features does not require SC licensing.
- Personal data is subject to Malaysia's Personal Data Protection Act (PDPA). A compliant privacy policy and data handling policy are required at launch.
- Stamp duty remission (0.10% rate) expires 12 July 2028 unless extended; fee calculation logic must be configurable without a code deployment.
- SST exemption on brokerage must be re-verified against the July 2025 Bursa FAQ before the fee calculator ships.

## Resource Constraints

- No dedicated design resource confirmed; UI should use a component library to accelerate delivery.
- No dedicated data engineering resource; price data pipeline must be maintainable by a generalist developer.

## Timeline Constraints

- Willingness-to-pay validation should be completed before committing to subscription infrastructure build.
- A personal-use V0.1 (founder-only) should be buildable within 2–4 weeks to validate core data model and price automation before adding multi-user and subscription features.

---

# 18. Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| yfinance API outages on trading days undermine core value proposition | High | Medium | Run 20-day reliability monitoring experiment before launch; identify secondary data source; implement manual override and clear status indicators |
| KLSE Screener ships per-tranche dividend tracking and broker fee accuracy within 12 months | High | Medium | Accelerate to market; build switching-cost moat through complete dividend history data; explore features KLSE Screener is structurally unlikely to prioritise |
| Malaysian investors refuse to pay for portfolio SaaS tools | High | Medium | Run 10 willingness-to-pay interviews before building subscription billing; validate pricing at RM10/month as entry point; consider permanent free tier |
| Onboarding abandonment rate is high due to manual data entry burden | High | High | CSV import promoted to V1 Must Have; build a "fast start" mode (current positions only, no historical dividends) as fallback |
| SST now applies to brokerage fees (July 2025 Bursa FAQ) | High | Low–Medium | Verify immediately; if SST applies at 6%, update all fee calculations in product spec and fee logic; the existing Excel model would also be incorrect |
| Solo founder bandwidth causes scope creep and delayed launch | Medium | High | Fix V1 scope to REQ-001 through REQ-010; enforce startup discipline principle |
| PDPA non-compliance at launch | Medium | Low | Engage Malaysian legal advisor for one-time compliance review before collecting user portfolio data |
| Row 28 formula bug replicated in product code | Low | Medium | Explicitly test the 8th dividend tranche calculation in QA; correct formula is shares × dividend_tranche_8, not shares × dividend_tranche_1 |

---

# 19. Dependencies

## Internal Dependencies

- Fee calculation logic (REQ-002) must be implemented and unit-tested before the portfolio dashboard can display accurate yield figures.
- Broker configuration (REQ-002) must be established before or during position creation (REQ-001).
- Dividend tranche logging (REQ-004) must be complete before yield calculation (REQ-005) can display correct results.

## External Dependencies

- **Bursa Malaysia market data:** Reliable access to end-of-day (or intraday) prices for all Bursa-listed equities. Currently proposed via yfinance; must be validated for reliability before launch.
- **Payment processing provider:** Required to collect subscription revenue. Options include Stripe (supports Malaysia), iPay88, or Billplz. Must support Malaysian ringgit and be operational before soft launch.
- **Email delivery provider:** Required for account verification, password reset, and future dividend alert notifications.

## Third Party Dependencies

| Dependency | Provider | Risk | Contingency |
|------------|----------|------|-------------|
| Market price data | yfinance (Yahoo Finance unofficial API) | High — unofficial, has experienced outages | Identify secondary source; implement manual override |
| Stamp duty rate | Bursa Malaysia / Malaysian government gazette | Low — stable until July 2028 | Build rate as configurable parameter |
| SST on brokerage | Bursa Malaysia SST FAQ (July 2025) | Medium — exemption status unconfirmed | Verify before fee calculator ships |
| Payment processing | TBD (Stripe / iPay88 / Billplz) | Low | Multiple providers available |

---

# 20. Open Questions

| Question | Owner | Recommended Next Action |
|----------|-------|------------------------|
| Does SST now apply to brokerage fees for Bursa equity trades under the July 2025 Bursa FAQ? | Founder | Read the Bursa SST FAQ (July 2025) before any fee logic is implemented. Binary outcome; 10-minute task. |
| Is KLSE Screener's dividend tracking insufficient for the target user's specific needs? | Founder | Spend 2 hours tracking all 16 portfolio positions in KLSE Screener; document exactly what it cannot do. Primary competitive validation task. |
| Will target users pay RM15–30/month? | Founder | Conduct 10 structured willingness-to-pay interviews with Malaysian retail investors who currently use Excel or Google Sheets. |
| Is yfinance sufficiently reliable for daily production use on Bursa data? | Founder | Run automated monitoring on all 16 portfolio stocks for 20 consecutive trading days before building the price pipeline. |
| What is the correct V1 subscription pricing? | Founder | Test RM10, RM20, and RM30 in willingness-to-pay interviews; consider a freemium model (up to 5 positions free, unlimited positions paid). |
| Is a Malaysian SC licence required for BursaTrack if it includes a sell scenario calculator? | Founder + Legal Advisor | One-time consultation with a Malaysian securities lawyer before launch. |
| How should multi-lot yield be calculated — blended all-in cost as one denominator, or separate yield per lot? | BA / Product Owner | Confirm calculation method in BA kickoff; document in data model. |
| How are dividend tranche year boundaries handled — calendar year or stock financial year? | BA / Product Owner | Define year boundary behaviour and historical year display in BA workshop. |
| What are the required CSV import fields, formats, and validation rules? | BA | Produce CSV template specification including field names, data types, required vs. optional, and example values. |
| Are tiered broker fee structures (Rakuten Trade) supported at V1 or simplified? | Product Owner | Decision: simplify to two-rate model at V1 (recommended) or build tiered support; must be resolved before broker feature is scoped. |
| What is the trial period length and feature gating model? | Product Owner | Decision: recommend 14-day trial with full feature access; confirm before subscription billing is built. |
| What is the minimum data entry time for a user onboarding from a 16-position Excel portfolio? | Founder | Time the complete onboarding of the founder's own portfolio using a prototype; if > 20 minutes without CSV, CSV import must be in V1. |

---

# 21. Business Analysis Readiness Assessment

## Ready Areas

The following sections are sufficiently complete for BA handoff and engineering estimation:

- **Problem Definition:** Well-evidenced with specific formula references; BA can derive data validation requirements directly from the Excel model analysis.
- **Fee Calculation Logic (REQ-002 + Acceptance Criteria):** Brokerage, clearing fee, and stamp duty are specified at implementation precision with numeric test cases.
- **Dividend Tranche Model (REQ-004 + Domain Model):** The 8-tranche limit, per-share storage, and derived total calculation are unambiguous.
- **Yield Calculation (REQ-005 + Acceptance Criteria):** The denominator (all-in cost), calculation method, and a specific numeric test case (5.57% vs. 5.58%) are unambiguous.
- **Sell Calculator Logic (REQ-007 + Acceptance Criteria):** The full calculation chain is specified with a numeric break-even test case.
- **Non-Functional Requirements:** Performance, reliability, security, scalability, auditability, and compliance targets are measurable.
- **Domain Model:** Entities, attributes, and relationships are defined at conceptual level; sufficient to begin data model design.
- **User Stories + Acceptance Criteria (REQ-001 to REQ-010):** Testable and traceable to personas and business objectives.

## Areas Requiring BA Investigation

| Area | Issue | Recommended Action |
|------|-------|-------------------|
| Multi-lot yield calculation method | PRD implies blended all-in cost as denominator but does not state it explicitly | Define and document in first BA workshop |
| Dividend tranche year boundary | "Up to 8 per calendar year" — behaviour at year boundaries is undefined | Define year boundary logic and how historical years are displayed |
| CSV import field specification | REQ-009 references a template but does not define required columns, data types, or validation rules | BA to produce full CSV template spec before engineering estimation |
| Tiered broker fee handling | Rakuten Trade has a tiered structure not handled by the current two-rate model | Resolve pending stakeholder decision on V1 scope |
| Trial period definition | Trial length, feature gating, and paywall enforcement logic are not specified | Define trial boundary and gating in BA workshop |
| Ex-date / dividend calendar data model | Whether ex-date is a field on DividendTranche or a separate entity is not specified | Clarify and document in domain model |

## Stakeholder Decisions Required

| Decision | Options | Recommendation |
|----------|---------|---------------|
| CSV Import priority | V1 Must Have vs. V1.1 Should Have | **V1 Must Have** — onboarding abandonment is highest-probability, highest-impact risk |
| Trial period length | 7 / 14 / 30 days | 14-day trial — long enough for a dividend event; short enough to drive conversion |
| Tiered broker fee support | Support Rakuten Trade tiered structure at V1, or simplify | Simplify to two-rate model at V1; add tiered support in V1.1 |
| Free tier | No free tier (trial only) vs. permanent free tier (up to N positions) | Defer until willingness-to-pay interviews complete |
| SST on brokerage | Exempt (current assumption) vs. 6% SST applied | Verify against July 2025 Bursa SST FAQ immediately |
| KLSE Screener gap validation | Proceed to build vs. gate V1 scope on competitive validation | Gate — competitive differentiation must be confirmed before V1 spec is finalised |

## Remaining Open Risks

| Risk | Status |
|------|--------|
| yfinance reliability | Unmitigated; 20-day monitoring experiment not yet run |
| Malaysian willingness to pay | Unvalidated; no interviews conducted |
| KLSE Screener feature gap | Unconfirmed; hands-on evaluation not yet completed |
| SST on brokerage | Unresolved; July 2025 Bursa FAQ not yet read |
| Onboarding completion rate | Partially mitigated by CSV import promotion; requires pilot test |
| PDPA compliance | Partially mitigated by NFR section; legal review not yet completed |

## BA Readiness Score

**6.5 / 10**

The document is ready for a BA kickoff workshop. It is not yet ready for full engineering estimation. The six BA investigation areas and six stakeholder decisions above must be closed — resolvable in one or two structured BA workshops — before the V1 sprint can be sized with confidence. The score rises to 8.5+ once those items are resolved.

---

# 22. Product Manager Review

## Biggest Risks

**1. Free-tool expectation in Malaysia.** KLSE Screener is free, Bursa-native, mobile-first, and has a large existing user base. Until the founder has spent two hours using KLSE Screener for their own 16 positions and can articulate with specificity what is missing, the entire business case rests on an assumption that has not been stress-tested.

**2. Willingness to pay.** There is zero external evidence that Malaysian retail investors will pay RM15–30/month for a portfolio tool. MalaysiaStock.Biz's August 2024 paywall transition is the only live experiment in this market, and its outcome is unknown. This is the single most important unknown and the cheapest to validate before a line of product code is written.

**3. Price data dependency.** The yfinance API is unofficial and has experienced outages. If it fails on a trading day, BursaTrack delivers no core value. This is not a theoretical risk — it is a documented historical one. A product that cannot be trusted to show current prices on trading days cannot compete with free alternatives.

## Weakest Assumptions

- "Malaysian retail investors share the same daily spreadsheet pain as the founder" — unverified by any external user research. The founder is the sole evidence base.
- "Users will complete full portfolio onboarding including historical dividend data" — high onboarding friction for anyone who is not the founder. Mitigated by CSV import promotion to V1 Must Have, but not eliminated.
- "BursaTrack's differentiators are sufficient to justify a switch from KLSE Screener plus a monthly fee" — the entire business case depends on this, and it has not been tested.

## Potential Failure Scenarios

- **Scenario 1 (Most likely):** The product launches, attracts initial interest, but conversion from free trial to paid is below 20% because users find KLSE Screener adequate for their needs. MRR plateaus below RM1,000.
- **Scenario 2:** Onboarding abandonment is high (> 60% of sign-ups do not complete portfolio setup). The daily value proposition never activates for most users. Retention collapses within 30 days.
- **Scenario 3:** yfinance experiences a multi-day outage during a volatile market period. Users lose trust at exactly the moment they need the tool most. Churn spikes.
- **Scenario 4:** KLSE Screener adds per-tranche dividend tracking and broker fee configuration in a feature sprint, eliminating the primary differentiator before BursaTrack reaches scale.

## Recommended Improvements

1. **Validate before building.** Complete all five tests in Section 6 of the Startup Validation Report before committing to a multi-user product. The personal-use V0.1 is a legitimate milestone; the startup decision is a separate gate.
2. **Lead with the accuracy story.** The fee calculator accuracy (per-broker, correct denominator, correct stamp duty rate) is a more defensible differentiator than general convenience. Position BursaTrack as "the only Bursa portfolio tracker that shows your true yield."
3. **Resolve the SST question immediately.** This is a binary compliance question that takes 10 minutes to answer and affects the accuracy of the product's core claim.
4. **Design a fallback for price data outages.** Clear status message, manual price entry mode, time-to-resolution communication. The user experience of a data outage is part of the product.
5. **Test onboarding time before launch.** Time a pilot user importing their own 16-position portfolio using the CSV template. If it takes more than 10 minutes, re-examine the template design.

## Alternative Strategies

| Strategy | When to Pursue |
|----------|---------------|
| Build as free, open-source personal tool | If willingness-to-pay interviews return consistently "nothing"; still has value as a portfolio and learning project |
| Freemium model: free up to 5 positions, paid unlimited | If conversion resistance is price-sensitivity rather than lack of perceived value |
| B2B: sell accuracy tools to investment clubs or financial content creators | If individual willingness-to-pay is low but communities or influencers see value in branded tools |
| Partner with a broker for distribution | If the product proves its value; broker partnership could provide price data and user acquisition in exchange for co-branding |

## PM Confidence Score

**4 / 10**

The problem is real, specific, and well-documented — the Excel model is a working prototype and the founder is the ideal reference user. However, the score is held back by three unresolved structural risks: no external validation that others share the pain at the same intensity, no willingness-to-pay evidence in a market with a strong free-tool expectation, and an unresolved data reliability question at the core of the product's value. The competitive landscape score (2/5 in the Startup Validation Report) reflects a free, embedded incumbent that the discovery documentation does not adequately confront.

This score should be revisited after the five validation tests in Section 6 of the Startup Validation Report are completed. A positive outcome on willingness-to-pay and KLSE Screener gap analysis would move this to 7–8 without any product changes.

---

*BursaTrack PRD v2.0 — Final*
*Prepared for stakeholder review and Business Analysis handoff*
*Audience: Business stakeholders · Business Analysts · Product Designers · Engineering Leads*
