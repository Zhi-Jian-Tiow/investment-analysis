# BursaTrack PRD — Principal PM Review & Enhancements

> **Reviewer:** Principal Product Manager
> **Review Date:** 2026-06-21
> **Source Document:** BursaTrack-PRD.md (v1 Draft)
> **Purpose:** Upgrade the PRD to Business Analysis readiness; insert enhanced sections directly into the base document

---

## Executive Review Summary

### Overall Assessment

The base PRD is well-structured and grounded in real evidence — the Excel model functions as a working prototype, the identified bugs (row 28 formula, ROI denominator) are specific and actionable, and the competitive framing is honest about risks. The problem definition and PM Review sections are particularly strong; the author does not oversell the opportunity. As a Senior PM deliverable this document is above average.

However, the document stops short of Business Analysis readiness. It defines *what* the product should do at a headline level but does not give Business Analysts or engineers enough precision to begin scoping, estimating, or designing. Specifically: there are no user stories, no acceptance criteria, no NFRs, no phased delivery plan, no competitive matrix, and no domain model. The requirements section (REQ-001 to REQ-010) reads as a capability list, not a set of testable specifications. A BA picking this up today would need to schedule multiple workshops to fill in what is missing.

The enhancements below are designed to close those gaps without rewriting what already works.

---

### Top Strengths

**1. Evidence-grounded problem definition.** The row 28 formula bug, the ROI denominator flaw, and the specific fee table are primary evidence, not assertions. This gives the BA a precise starting point for data model design.

**2. Honest PM Review.** The confidence score of 4/10 with explicit reasoning is rare and valuable. It signals where pre-build validation effort should be concentrated and sets realistic expectations for stakeholders.

**3. Well-specified fee logic.** The clearing fee (0.03%), stamp duty (RM1/RM1,000 ROUNDUP), and brokerage minimum (RM8 at HLB/Maybank) are documented at implementation precision. The SST ambiguity is surfaced rather than silently assumed away.

**4. Commercially disciplined scope.** Out-of-scope decisions (real-time streaming, broker API, native apps, non-Bursa exchanges) are correct for an MVP and are explained rather than arbitrary.

**5. Risk register quality.** The risk table is unusually complete for a v1 PRD: yfinance outage, KLSE Screener competitive response, onboarding abandonment, and PDPA are all correctly identified and not minimised.

---

### Top Weaknesses

**1. No user stories or acceptance criteria.** Requirements REQ-001 to REQ-010 describe capabilities, not testable behaviours. A BA cannot derive test cases from the current format.

**2. No phased delivery plan.** "Must Have / Should Have / Nice to Have" is not a release plan. There is no MVP definition distinguishing what is needed to validate the problem from what is needed for public launch.

**3. No non-functional requirements.** Performance, availability, security, and data freshness targets are entirely absent. This is a data-sensitive financial tool — NFRs are not optional.

**4. No competitive matrix.** The competitive risk (KLSE Screener) is named but not formally compared. A BA-ready document needs a feature-level comparison to understand where BursaTrack must win.

**5. No domain model.** The data relationships between User, Portfolio, Position, Lot, Dividend, and Tranche are implied but never stated. This will cause ambiguity in BA workshops.

**6. Onboarding friction underweighted in requirements.** The PRD correctly identifies onboarding abandonment as a top risk (Section 11) but REQ-009 (CSV Import) remains a "Should Have." This is inconsistent — if onboarding abandonment is the highest probability risk, CSV Import should be a "Must Have" for V1.

---

## Recommended PRD Enhancements

---

# SECTION A: Product Vision

## What We Are Building

BursaTrack is a **dividend portfolio operating system for Malaysian retail investors** — purpose-built for Bursa Malaysia, designed around the income investor's daily workflow, and differentiated by provably accurate financial calculations that free tools do not provide.

This is not a general-purpose stock screener. It is not a trading platform. It is not a wealth management application. BursaTrack is the tool a dividend investor reaches for every morning to answer one question: *"How is my income portfolio performing, and is my money working as hard as it should?"*

## Long-Term Vision (3–5 Years)

**Year 1:** Replace the Excel spreadsheet for dividend investors in Malaysia. Become the reference tool for the serious retail investor who manages 10+ Bursa positions and cares about yield accuracy. Reach 500 paying subscribers.

**Year 2:** Expand the dividend calendar into a forward-looking income planner. Users can project their next 12 months of dividend income by position, enabling active rebalancing decisions. Add alert infrastructure (ex-date, payment received, price threshold). Reach 2,000 paying subscribers.

**Year 3:** Extend to Singapore Exchange (SGX) and the investors who hold both Bursa and SGX positions (a large and underserved segment). Add multi-currency support. Reach 10,000 paying subscribers across Malaysia and Singapore.

**Year 5:** Become the standard dividend portfolio tracker for Southeast Asian retail investors — beginning with Bursa and SGX and expanding to SET (Thailand), IDX (Indonesia), and HKEX for Malaysian diaspora investors.

## Why This Product Deserves to Exist

Every other tool in this market — KLSE Screener, Sharesight, Excel — was built for a general investor. None were built specifically for a Malaysian dividend income investor who needs to know their true all-in cost basis, their per-broker fee impact, and their per-tranche dividend history in a single, accurate, mobile-accessible view. That investor exists in large numbers (the 2.4 million active retail investors on Bursa Malaysia skew toward income investment given Malaysia's dividend culture and EPF-influenced savings behaviour). No tool has been built for them specifically. BursaTrack is that tool.

## Strategic Positioning

BursaTrack positions against free tools not on features, but on **financial accuracy**. The single most powerful claim the product can make is: *"Every other tool shows you an approximate yield. BursaTrack shows you your actual yield, calculated the same way a professional would — including every fee, every tranche, at your specific broker's rate."* This is a claim that can be proven with a side-by-side comparison and that resonates with the target user who already suspects their spreadsheet numbers are wrong.

## Vision Statement

> **BursaTrack is the dividend investor's source of truth — the only Bursa Malaysia portfolio tracker that calculates your true yield, logs every dividend tranche, and knows your broker's fee structure. Built for Malaysian income investors who are serious about their numbers.**

---

# SECTION B: Product Principles

## Principle 1: Accuracy Before Features

**Description:** Every calculation BursaTrack produces must be verifiably correct. If the yield number, the cost basis, or the fee calculation is wrong, nothing else matters. We will not ship a feature that introduces numerical ambiguity.

**Why it matters:** The target user has already discovered (or suspects) errors in their current spreadsheet. BursaTrack wins trust by being the tool that is provably right — not the tool with the most features. A single calculation error, if discovered by a user, destroys the product's core value proposition.

**Decision test:** *If a feature introduces a tradeoff between user convenience and calculation precision, we choose precision.*

---

## Principle 2: Time-to-Value Under 10 Minutes

**Description:** A new user must be able to add their first three positions, see live prices, and receive a yield calculation within 10 minutes of creating an account. If onboarding takes longer than 10 minutes to reach first value, we have failed.

**Why it matters:** The PRD's own risk analysis identifies onboarding abandonment as the highest-probability risk. The product will never build a user base if the first experience is 45 minutes of data entry before anything useful appears.

**Decision test:** *Every onboarding design decision must be evaluated against the 10-minute clock. Features that extend onboarding time must be deferred or made optional.*

---

## Principle 3: Dividend-First, Not Price-First

**Description:** BursaTrack is designed for investors who think in terms of income, not capital gains. Portfolio views, dashboards, and default sorting should prioritise dividend yield, income received, and payment calendar — not unrealised P&L or price movement.

**Why it matters:** KLSE Screener and most portfolio trackers are designed around price movement and P&L. BursaTrack's differentiation is that it speaks the language of the dividend investor. If we build BursaTrack to look like a stock screener, we have lost the positioning battle.

**Decision test:** *When designing any new feature, ask: "Does this serve a dividend income investor or a capital gains trader?" If trader, defer.*

---

## Principle 4: Trust Through Transparency

**Description:** BursaTrack will always show users exactly how a number was calculated. Every yield figure links to its components (total dividend ÷ all-in cost). Every all-in cost shows its fee breakdown. Users should never have to take a number on faith.

**Why it matters:** The core user insight is that existing tools show numbers users cannot verify. BursaTrack's competitive advantage is not just accuracy — it is visible, auditable accuracy. A user who can trace every number to its source will not go back to a black-box tool.

**Decision test:** *No summary number is acceptable without a visible drill-down to its constituent parts.*

---

## Principle 5: Malaysia First, Then Broaden

**Description:** Every product decision at v1 and v1.1 is made in service of the Malaysian Bursa equity investor. We will not add SGX, NYSE, or other exchange support until we have proven the product for Bursa. We will not generalise the fee model to "generic" until the Bursa fee stack is rock-solid.

**Why it matters:** Breadth kills focus. The fastest path to product-market fit is extreme specificity for one well-defined user. Malaysian dividend investors are a real, growing segment. Serving them perfectly is worth more than serving everyone adequately.

**Decision test:** *If a feature requires generalising the Malaysian fee structure or expanding beyond Bursa, it belongs in the V2 backlog.*

---

## Principle 6: Reliability Is a Feature

**Description:** A portfolio tracker that shows stale prices is worse than no tracker at all — it gives users false confidence. Price data availability, system uptime, and data freshness are product features, not infrastructure footnotes. They must be designed, monitored, and communicated to users.

**Why it matters:** The yfinance dependency is the product's highest technical risk. If it fails silently, users make decisions on wrong data. If it fails visibly with a good fallback (manual entry, clear status message, last-updated timestamp), users can still function. The experience of a data failure is part of the product.

**Decision test:** *Every feature that depends on external data must have a designed failure state. "It will usually work" is not an acceptable design assumption.*

---

## Principle 7: Startup Discipline — Do Less, Better

**Description:** BursaTrack will ship fewer features than users ask for. Every feature added to v1 is a feature that delays validation of the core value proposition. We will resist scope creep, defer enhancement requests, and ship an MVP that does one thing perfectly: shows a Malaysian dividend investor their true portfolio yield, accurately, every day.

**Why it matters:** The PM Confidence Score on this product is 4/10. The biggest risk is not building the wrong features — it is spending 12 months building before discovering that willingness to pay is not validated. Speed to first paying user is the primary risk mitigation.

**Decision test:** *If a feature does not directly increase the probability of a user completing onboarding or converting to a paid subscription, it is a v1.1 feature.*

---

# SECTION C: MVP Definition

## Phased Release Plan

---

### MVP — Version 0.1 (Personal Validation Build)

**Purpose:** Validate that the core data model is correct, that automated price fetching works reliably for Bursa equities, and that the yield calculation is provably more accurate than the Excel model. Single-user only (founder). Target build time: 2–4 weeks.

**Included features:**

| Feature | Why Here | Risk Addressed |
|---------|----------|---------------|
| Single-user portfolio (no auth) | Removes authentication complexity from the validation experiment | Validates data model without user management overhead |
| Add/edit/delete positions (one lot per stock, no CSV) | Core data entry needed to test the model | Validates position structure and fee calculation logic |
| Broker-aware fee calculation (REQ-002) | The primary accuracy differentiator; must be validated against the Excel model | Confirms fee logic is correct before any other user sees it |
| True yield calculation (REQ-005) | The core metric; must be verified against known values from the Excel model | Confirms the ROI denominator bug is fixed |
| Daily price fetch from yfinance for all 16 portfolio stocks (REQ-003) | The core automation pain-point; must be proven reliable before claiming it as a feature | Validates or disconfirms the price data dependency |
| Per-tranche dividend logging, up to 8 tranches (REQ-004) | Required to verify all-in yield; cannot be deferred if the PM wants to validate the full model | Validates dividend data model completeness |
| Portfolio summary (aggregate cost, income, yield) (REQ-006, partial) | Required to compare against the Excel model's row 30/31 output | Validates end-to-end calculation chain |

**Not included in MVP:**
Authentication, multi-user, CSV import, sell calculator, dividend calendar, mobile-responsive polish, subscription billing.

**MVP Exit Criteria:** The founder can use BursaTrack for all 16 positions for 20 consecutive trading days, confirm that prices are correct on ≥ 99.5% of trading days, and verify that the yield calculation matches the expected corrected output from the Excel model.

---

### V1 — Public Launch

**Purpose:** A paywall-gated, multi-user product ready for external users. Must be good enough to convince a stranger to pay RM15–30/month. Target timeline: 8–12 weeks after MVP exit criteria are met.

**Included features:**

| Feature | Why Here | Why Not Earlier / Later |
|---------|----------|------------------------|
| User authentication (email + password) (REQ-001 dependency) | Required for multi-user | Cannot be deferred to v1.1 — without it, no paying users |
| Multi-lot position support (REQ-001) | Users who bought at multiple prices need per-lot cost basis | V0.1 validated single-lot; multi-lot extends the model minimally |
| CSV import for portfolio onboarding (REQ-009) | **Promoted from Should Have to Must Have** — onboarding abandonment is the highest-probability failure mode | Without CSV import, users with 10+ positions and 3 years of history will not complete onboarding; this is not a nice-to-have |
| Full portfolio dashboard with per-position detail (REQ-006) | Public-facing; must be complete and polished | Core retention surface |
| Mobile-responsive interface (REQ-010) | ~40% of initial users will check on mobile based on persona analysis (Farah) | Without mobile responsiveness, the product is inaccessible to a meaningful segment at launch |
| Sell scenario calculator (REQ-007) | Moved to V1 (originally Should Have) because it is directly visible in the Excel model and user personas reference it explicitly; David (Persona 3) specifically requires it | The calculator is already spec'd to near-implementation precision from the Excel model; the build cost is low and the retention value high |
| Subscription billing and trial management | Required to generate revenue | Cannot generate revenue without it |
| Dividend calendar (REQ-008) | Retains Should Have classification but included in V1 because ex-date awareness is a daily use case that drives return visits | Without it, the product is weaker than KLSE Screener on a feature users already rely on |
| Manual price override (part of REQ-003) | Already spec'd; required when yfinance fails | Must ship with price automation; a failure state without override creates user frustration |

**V1 Exit Criteria:** ≥ 10 non-founder users have completed full portfolio onboarding, at least 5 have converted to paid, and no data accuracy complaints have been filed in the first 30 days.

---

### V1.1 — Retention and Expansion

**Purpose:** Improve retention after initial conversion; address gaps identified from V1 user feedback. Target: 8–10 weeks after V1 launch.

| Feature | Why Deferred |
|---------|-------------|
| Push/email alerts for ex-dividend dates and declared dividends | High value but requires notification infrastructure; deferred to keep V1 scope tight |
| Historical yield trend charts (per position, per portfolio) | Valuable but requires time-series data accumulation; not meaningful at launch with no history |
| Google Sheets import | Less universal than CSV; lower ROI on build effort; CSV covers the primary onboarding case |
| SST toggle on brokerage fees | Deferred pending verification of July 2025 Bursa FAQ; if SST applies, promote to V1 Must Have |
| PDPA-compliant data export (user requests their data) | Required for compliance but not a user workflow feature; can be added post-launch |
| "Fast start" mode (positions-only, no dividend history at signup) | Reduces onboarding time further; validated by V1 drop-off data before building |

---

**Consistency challenge:** The base PRD lists CSV Import as "Should Have" but Section 11 identifies onboarding abandonment as "High" probability and "High" impact. These are inconsistent. The phased plan above promotes CSV Import to V1 Must Have. If the engineering estimate for CSV import is high, the recommended alternative is a "fast start" mode (positions only, no historical dividends) as the V1 onboarding path, with CSV import in V1.1. Either way, the current priority is wrong and needs a stakeholder decision.

---

# SECTION D: Competitive Analysis

## Feature Comparison Matrix

*Legend: ✅ Yes / Fully supported | ⚠️ Partial / Limited | ❌ No / Not supported | ❓ Unconfirmed (assumption marked)*

| Feature | BursaTrack (V1) | KLSE Screener | Sharesight | Google Sheets | Excel |
|---------|----------------|---------------|------------|---------------|-------|
| **Portfolio Tracking** | ✅ | ✅ | ✅ | ⚠️ Manual | ⚠️ Manual |
| **Bursa Malaysia coverage** | ✅ | ✅ | ✅ | ⚠️ Via formula | ⚠️ Via formula |
| **Automated price refresh** | ✅ (daily) | ✅ (real-time) | ✅ | ⚠️ Via GOOGLEFINANCE() | ❌ Manual |
| **Dividend tracking** | ✅ | ✅ (ex-date, amounts) | ✅ | ⚠️ Manual | ⚠️ Manual |
| **Per-tranche dividend logging (up to 8 tranches/year)** | ✅ | ❌ ❓(assumption: KLSE Screener shows totals, not individual tranches) | ⚠️ ❓ Limited tranche depth | ⚠️ Manual | ⚠️ Manual |
| **Broker-specific fee modelling** | ✅ (per-broker presets) | ❌ | ❌ | ❌ | ⚠️ Manual (single rate) |
| **Correct Malaysian fee stack (0.03% clearing, RM1/RM1,000 stamp duty)** | ✅ | ❌ ❓ | ❌ (global model) | ❌ | ⚠️ If user builds it |
| **True yield vs. all-in cost** | ✅ | ❌ ❓ | ⚠️ ❓ | ⚠️ If user builds it | ⚠️ Contains known bug |
| **Multi-lot position support** | ✅ | ❌ ❓ | ✅ | ⚠️ Manual | ⚠️ Manual |
| **Sell scenario calculator** | ✅ | ❌ | ❌ | ⚠️ Manual | ✅ (built into the model) |
| **Dividend calendar / ex-date alerts** | ✅ (V1, user-entered) | ✅ (scraped from Bursa) | ✅ | ❌ | ❌ |
| **CSV import** | ✅ (V1) | ❌ | ✅ | ✅ | ✅ |
| **Mobile experience** | ✅ (responsive web) | ✅ (native app) | ✅ (native app) | ⚠️ Limited | ❌ |
| **Offline access** | ❌ | ⚠️ App caching | ❌ | ❌ | ✅ |
| **Cost basis accuracy (all-in)** | ✅ | ❌ ❓ | ⚠️ ❓ | ⚠️ If user builds it | ⚠️ Partial (bug in row 28) |
| **Free tier** | ⚠️ Trial only | ✅ (free) | ⚠️ Free tier (limited) | ✅ (free) | ✅ (one-time cost) |
| **Pricing** | RM15–30/month (proposed) | Free | AUD 32/month | Free | One-time (Office licence) |
| **Malaysian market-specific** | ✅ | ✅ | ⚠️ Supports Bursa, not specialised | ❌ | ❌ |

> **Assumption flags:** KLSE Screener's portfolio feature set was assessed from public documentation and the startup validation report. Per-tranche dividend logging and true all-in cost basis have not been verified by hands-on testing. **The founder must spend 2 hours using KLSE Screener for their own 16 positions before V1 scope is finalised.**

---

## Competitive Advantages

**1. Broker-specific fee precision.** No competitor currently models the brokerage fee at the individual broker level (MooMoo RM3 flat vs. Maybank 0.10% vs. Rakuten Trade tiered). This is BursaTrack's only fully defensible differentiator at launch — it cannot be copied by a generic tool without a Bursa-specific product decision.

**2. Per-tranche dividend depth.** Dividend investors track individual payment tranches because they correlate them with announcement dates, yield-on-cost trends, and reinvestment decisions. If KLSE Screener shows totals only (assumption — requires verification), per-tranche logging is a meaningful gap.

**3. True all-in yield calculation.** Using all-in cost (not pre-fee initial amount) as the yield denominator is the correct calculation. KLSE Screener has not been confirmed to do this (assumption).

**4. Sell scenario calculator integrated with live positions.** The Excel model's calculator panel is a daily-use tool for active investors. No other portfolio tracker in this market integrates a sell fee calculator with live portfolio positions.

---

## Competitive Disadvantages

**1. KLSE Screener is free and has a large, loyal user base.** Any conversion from KLSE Screener requires BursaTrack to be better, not just different. "Better" means the specific capabilities listed above — if those gaps do not exist or KLSE Screener closes them, BursaTrack's business case collapses.

**2. KLSE Screener has real-time price data from Bursa; BursaTrack has daily data from an unofficial API.** For dividend investors (not traders), daily is sufficient — but it is a visible disadvantage.

**3. No native mobile app at V1.** KLSE Screener has Android and iOS apps with native UX. BursaTrack's mobile-responsive web is functional but not equivalent to a native app experience.

**4. No automated dividend data.** BursaTrack requires users to manually enter dividend amounts. KLSE Screener scrapes ex-date and dividend data from Bursa announcements. Manual entry is a friction cost that compounds as the portfolio grows.

**5. Switching cost from Excel is real.** Users with 3+ years of dividend history in Excel face a significant data migration effort. KLSE Screener requires no migration (it starts fresh).

---

## Areas Requiring Differentiation

The product must win on **accuracy** (fee calculation, yield denominator, per-tranche logging) because it cannot win on **convenience** (KLSE Screener is free and has native apps) or **data breadth** (KLSE Screener has real-time Bursa data and scraped dividends).

The marketing message must be: *"KLSE Screener tells you your portfolio is up. BursaTrack tells you whether your yield is actually what you think it is."*

---

# SECTION E: User Stories

## REQ-001 — Portfolio Position Management

- As **Ahmad** (methodical dividend accumulator), I want to add a new stock position with my purchase price and number of shares, so that I can see my true cost basis for that holding from day one.
- As **David** (active dividend optimizer), I want to record multiple lots for the same stock at different purchase prices, so that I can calculate the blended cost basis across all my entries.
- As **Farah** (emerging income investor), I want to edit a position I entered incorrectly, so that my portfolio always reflects my actual holdings without starting over.
- As **Ahmad**, I want to tag a holding as "dividend" or "growth/volatile," so that my dashboard separates income positions from capital-gain positions the same way my current spreadsheet does.

---

## REQ-002 — Broker-Aware Fee Calculation

- As **Farah**, I want to select my broker (MooMoo) when I add a position, so that my cost basis uses the correct RM3 flat fee instead of the default 0.10% rate.
- As **David**, I want to override the brokerage rate for a specific position, so that I can model the exact fee I was charged if my broker uses a non-standard rate.
- As **Ahmad**, I want to see the clearing fee (0.03%) and stamp duty (RM1/RM1,000) calculated automatically for each position, so that I don't have to verify the formula myself.
- As **David**, I want the yield calculation to use my all-in cost (including all fees) as the denominator, so that my ROI is not overstated by excluding transaction costs.

---

## REQ-003 — Automated Daily Price Refresh

- As **Ahmad**, I want my portfolio prices to be updated automatically on trading days, so that I don't spend 10–15 minutes entering prices each morning.
- As **Farah**, I want to see the last updated time for price data, so that I know whether the prices I'm looking at are from today or yesterday.
- As **David**, I want to manually enter a price override for any position, so that I can correct or supplement the data when the automated feed is unavailable.
- As any user, I want to see a clear status message when price data is stale or unavailable, so that I don't make decisions based on outdated prices without realising it.

---

## REQ-004 — Per-Tranche Dividend Logging

- As **Ahmad**, I want to log each interim dividend payment separately (1st, 2nd, 3rd tranche), so that I can track when dividends were received and which announcements they correspond to.
- As **David**, I want to log up to 8 dividend tranches per stock per year, so that I can track every payment for multi-payout stocks like CARLSBG or TIMECOM.
- As **Farah**, I want to see the total dividend per share for a stock calculated automatically from all my tranche entries, so that I don't have to manually sum them.
- As **Ahmad**, I want to record the payment date alongside each dividend tranche, so that I can reconcile with my broker's payment confirmation.

---

## REQ-005 — Yield (ROI) Calculation

- As **Ahmad**, I want to see the dividend yield for each position calculated as total dividend income divided by my all-in cost, so that I have an accurate measure of my income return on invested capital.
- As **David**, I want to see the portfolio blended yield — the sum of all dividend income divided by the total all-in portfolio cost — so that I can assess my income portfolio as a whole.
- As **Farah**, I want the yield to update automatically when I log a new dividend tranche, so that my dashboard always reflects the latest income received.
- As **David**, I want to see the yield calculation broken down (numerator: total dividend; denominator: all-in cost), so that I can verify the number is being calculated correctly.

---

## REQ-006 — Portfolio Summary Dashboard

- As **Ahmad**, I want to see all my positions in a single dashboard view with current price, all-in cost, total dividend income, and yield, so that I can assess my full portfolio in under 5 minutes.
- As **Farah**, I want to see my total dividend income for the year at the top of the dashboard, so that I can immediately see whether I'm on track for my income target.
- As **David**, I want to sort my positions by yield, so that I can identify my highest-returning holdings at a glance.
- As any user, I want the dashboard to display total portfolio all-in cost and portfolio blended yield in a summary header, so that I have the most important numbers visible without scrolling.

---

## REQ-007 — Buy/Sell Scenario Calculator

- As **David**, I want to enter a target sell price for any position and see the net proceeds after all fees (brokerage, clearing, stamp duty), so that I can calculate my actual profit before executing a trade.
- As **David**, I want to see profit/loss at multiple sell price points simultaneously (e.g., at +0.01, +0.05, +0.10 increments), so that I can assess break-even and target return at a glance.
- As **Ahmad**, I want the sell calculator to use my actual broker fee rate (not a generic rate), so that the profit/loss calculation reflects my true trading cost.
- As **Farah**, I want the sell calculator to tell me my break-even price — the minimum sell price to cover all transaction costs — so that I know my floor before deciding to sell.

---

## REQ-008 — Dividend Calendar

- As **Ahmad**, I want to see upcoming ex-dividend dates for all my holdings in a calendar view, so that I can ensure I hold the stock before the ex-date to qualify for the dividend.
- As **Farah**, I want to see expected dividend payment dates, so that I can plan my cash flow around when income arrives.
- As **David**, I want to add ex-date and payment date when logging a dividend tranche, so that my calendar reflects all historically known dates.

---

## REQ-009 — CSV Import for Portfolio Onboarding

- As **Ahmad**, I want to import my existing portfolio from a CSV file, so that I don't spend 45 minutes manually entering 16 positions and 3 years of dividend history.
- As **David**, I want to download a CSV template that matches the expected import format, so that I know exactly how to structure my data before importing.
- As any user, I want to receive clear validation feedback if my import file has errors (missing columns, incorrect formats), so that I can fix the issue without re-uploading the entire file.
- As **Farah**, I want to import positions without requiring dividend history, so that I can get to first value quickly and add dividends later.

---

## REQ-010 — Mobile-Responsive Interface

- As **Farah**, I want to check my portfolio on my phone during my commute, so that I don't have to wait until I'm at a desktop to see my latest numbers.
- As any user, I want all core features — dashboard, position view, dividend logging — to work correctly on a mobile browser at 375px width, so that I'm not blocked on desktop for any daily task.
- As **Ahmad**, I want portfolio values and yields to be readable without horizontal scrolling on mobile, so that I can scan key numbers in under 30 seconds.

---

# SECTION F: Acceptance Criteria

## REQ-001 — Portfolio Position Management

**Story: Add a new position**

```
Given I am logged in and my portfolio is open
When I add a new stock position with stock code "CIMB 1023", 5,000 shares, purchase price RM8.38, and broker "Maybank Investment"
Then the position appears in my portfolio dashboard
And the initial purchase amount is calculated as RM41,900.00 (5,000 × 8.38)
And the all-in cost is calculated as RM41,996.47 (initial amount + brokerage + clearing + stamp duty)
And the position is tagged with the selected broker
```

**Story: Add a second lot to an existing position**

```
Given I have an existing CIMB position at RM8.38 for 5,000 shares
When I add a second lot for CIMB at RM9.00 for 2,000 shares
Then both lots appear under the CIMB position
And the blended cost basis is calculated as the weighted average of both lots
And the total shares for CIMB shows 7,000
```

**Story: Edit a position**

```
Given I have an existing position with incorrect share count
When I edit the position and change the share count from 5,000 to 4,000
Then all dependent calculations (purchase amount, fees, all-in cost, dividend income, yield) recalculate immediately
And the portfolio summary totals update to reflect the change
```

**Story: Delete a position**

```
Given I have an existing position I want to remove
When I delete the position
Then the position is removed from the portfolio
And the portfolio summary totals update immediately
And all associated dividend tranche records are also removed
```

---

## REQ-002 — Broker-Aware Fee Calculation

**Story: Brokerage fee with standard broker**

```
Given I have selected "Maybank Investment" as my broker (rate: 0.10%, min RM8)
When I add a position with an initial amount of RM41,900
Then the brokerage fee is calculated as RM41.90 (RM41,900 × 0.10%)
And the clearing fee is calculated as RM12.57 (RM41,900 × 0.03%)
And the stamp duty is calculated as RM42 (ROUNDUP(41,900 / 1,000, 0))
And the all-in cost is RM41,996.47
```

**Story: Brokerage fee minimum — MooMoo**

```
Given I have selected "MooMoo" as my broker (rate: RM3 flat per trade)
When I add a position with an initial amount of RM41,900
Then the brokerage fee is calculated as RM3.00 (flat fee, not percentage)
And clearing fee and stamp duty are calculated the same as other brokers
And the all-in cost reflects the RM3.00 brokerage (lower than Maybank equivalent)
```

**Story: Brokerage minimum applies**

```
Given I have selected a percentage-based broker (0.10%, min RM8)
When I add a position with an initial amount of RM3,000 (e.g., FM at RM0.60 × 5,000 shares)
Then 0.10% of RM3,000 = RM3.00, which is below the RM8 minimum
And the brokerage fee is calculated as RM8.00 (minimum applied)
```

**Story: Stamp duty rounding**

```
Given any position
When the initial amount is RM41,900
Then stamp duty = ROUNDUP(41,900 / 1,000, 0) = ROUNDUP(41.9, 0) = 42
And the stamp duty is RM42.00
```

---

## REQ-003 — Automated Daily Price Refresh

**Story: Prices update on a trading day**

```
Given I have a portfolio with active positions
When a Bursa Malaysia trading day begins (9:00 AM MYT)
Then prices for all positions are refreshed at least once during market hours
And the dashboard displays the latest price alongside a "Last updated: [timestamp]" label
```

**Story: Price data unavailable**

```
Given the automated price feed is unavailable
When I open my dashboard
Then a visible status banner reads: "Price data unavailable — showing prices as of [last successful update]. Enter prices manually to continue."
And a manual price override field is available for each position
```

**Story: Manual price override**

```
Given a price feed failure is in progress
When I manually enter a price of RM8.50 for CIMB
Then the CIMB position immediately recalculates unrealised P&L using RM8.50
And the override is flagged visually (e.g., "Manual — [time entered]") to distinguish it from automated data
And the override is replaced by the automated feed price on the next successful refresh
```

---

## REQ-004 — Per-Tranche Dividend Logging

**Story: Log first dividend tranche**

```
Given I have a CIMB position in my portfolio
When I log the 1st dividend tranche with RM0.20 per share and payment date 2026-03-15
Then the dividend appears under CIMB as "1st Tranche: RM0.20/share — 15 Mar 2026"
And the total dividend income for CIMB updates to RM1,000 (5,000 shares × RM0.20)
And the total dividend per share for CIMB updates to RM0.20
```

**Story: Log subsequent tranche — aggregate check**

```
Given CIMB already has a 1st tranche of RM0.20/share
When I log the 2nd dividend tranche with RM0.1975 per share
Then the total dividend per share for CIMB updates to RM0.3975 (RM0.20 + RM0.1975)
And the total dividend income updates to RM1,987.50 (5,000 × RM0.3975)
And the yield recalculates immediately
```

**Story: Maximum tranche validation**

```
Given a stock already has 8 dividend tranches logged
When I attempt to add a 9th tranche
Then the system prevents the addition and displays: "Maximum of 8 dividend tranches per year reached for this stock"
```

---

## REQ-005 — Yield (ROI) Calculation

**Story: Yield calculated against all-in cost**

```
Given CIMB has an all-in buy cost of RM41,996.47 and total dividend income of RM2,337.50
When the yield is calculated
Then yield = RM2,337.50 ÷ RM41,996.47 = 5.57%
And the yield is displayed as 5.57% (not 5.58%, which would result from using pre-fee cost)
```

**Story: Portfolio blended yield**

```
Given I have 16 positions with known all-in costs and dividend income
When the portfolio summary calculates blended yield
Then blended yield = sum of all dividend income ÷ sum of all all-in costs
And individual position yields are also displayed separately
```

**Story: Yield updates on dividend log**

```
Given CIMB has a yield of 5.57%
When I log a new 3rd dividend tranche of RM0.07/share (RM350 total)
Then the total dividend income for CIMB updates to RM2,687.50
And the yield updates to RM2,687.50 ÷ RM41,996.47 = 6.40% (approximately)
And the portfolio blended yield recalculates
```

---

## REQ-006 — Portfolio Summary Dashboard

**Story: Dashboard displays key summary metrics**

```
Given I have a portfolio with at least one position and one dividend logged
When I open the portfolio dashboard
Then I see: total all-in portfolio cost, total annual dividend income, portfolio blended yield
And each position shows: stock name, shares, purchase price, all-in cost, current price, dividend income, yield
And the dashboard loads within 3 seconds on a standard broadband connection
```

**Story: Position sorting**

```
Given I am viewing the portfolio dashboard
When I click "Sort by Yield"
Then positions reorder from highest to lowest yield
And the sort order persists for my next session
```

---

## REQ-007 — Buy/Sell Scenario Calculator

**Story: Sell scenario at multiple price points**

```
Given CIMB was purchased at RM8.38 for 5,000 shares with all-in buy cost RM41,996.47
When I open the sell calculator for CIMB and request scenarios at RM8.39, RM8.40, RM8.41, RM8.42
Then the calculator shows for each price: gross proceeds, brokerage fee, clearing fee, stamp duty, net proceeds, and profit/loss
And at RM8.42: net proceeds ≈ RM42,002.27, profit/loss ≈ +RM5.80 (break-even confirmed)
And at RM8.39: profit/loss is negative (below break-even)
```

**Story: Break-even price identification**

```
Given any stock position in my portfolio
When I open the sell calculator
Then the break-even sell price is clearly highlighted (the minimum price at which profit/loss ≥ 0)
```

**Story: Sell calculator uses actual broker rate**

```
Given my broker is MooMoo (RM3 flat brokerage)
When I run a sell scenario
Then the sell brokerage fee is RM3.00 flat (not 0.10% of proceeds)
```

---

## REQ-008 — Dividend Calendar

**Story: Calendar displays upcoming ex-dates for held stocks**

```
Given I have logged dividend tranches with ex-dates for my positions
When I open the dividend calendar view
Then I see all upcoming ex-dates for my held stocks in chronological order
And past ex-dates from the current year are also visible with their payment dates
```

**Story: No ex-date data entered**

```
Given I have positions but have not entered any ex-dates
When I open the dividend calendar
Then the calendar displays an empty state with guidance: "Add ex-dates when logging dividends to see your payment schedule here"
```

---

## REQ-009 — CSV Import for Portfolio Onboarding

**Story: Successful CSV import**

```
Given I have downloaded the BursaTrack CSV template and populated it with my 16 positions and dividend history
When I upload the CSV file
Then all positions are created with correct share counts, purchase prices, and broker assignments
And all dividend tranches are created with correct per-share amounts and dates
And the dashboard immediately shows my full portfolio with calculated yields
And the import completes within 30 seconds for files up to 100 positions
```

**Story: CSV validation error**

```
Given I upload a CSV file with a missing "shares" column in row 5
When the import runs
Then the system displays: "Import error: Row 5 — 'shares' column is required but was empty. No records were imported."
And my existing portfolio is unchanged
And I can download the error report and correct the file
```

**Story: Template download**

```
Given I am on the import page
When I click "Download Template"
Then a CSV file downloads with pre-populated column headers and one example row
And the template includes a column guide explaining each field
```

---

## REQ-010 — Mobile-Responsive Interface

**Story: Dashboard usable on mobile**

```
Given I open BursaTrack on a mobile browser at 375px viewport width
When the dashboard loads
Then all key metrics (portfolio cost, total income, blended yield) are visible without horizontal scrolling
And each position row is readable with stock name, yield, and current value visible
And all interactive elements (buttons, links) have tap targets of at least 44×44px
```

**Story: Dividend logging on mobile**

```
Given I am using BursaTrack on mobile
When I navigate to add a dividend tranche for a position
Then the form is usable with a mobile keyboard
And the numeric input fields trigger a numeric keyboard on iOS and Android
And the submission button is reachable without scrolling past the form
```

---

# SECTION G: Non-Functional Requirements

## Performance

| Requirement | Target | Notes |
|-------------|--------|-------|
| Dashboard initial load time | ≤ 3 seconds on 20 Mbps connection | Measured from navigation to full portfolio render |
| Dashboard load time (returning user, cached prices) | ≤ 1.5 seconds | Cached price data should eliminate repeat API calls within a session |
| Portfolio calculation time (yield, all-in cost) | < 200ms client-side | Calculations are deterministic and should not require server round-trips |
| CSV import processing time | ≤ 30 seconds for files up to 100 positions / 800 dividend entries | Server-side; user receives progress indicator |
| Sell calculator response time | < 100ms | Synchronous calculation; no API call required |
| Price refresh cycle duration | ≤ 5 minutes to refresh all positions during trading hours | Batch refresh; user sees "prices updating" state during window |

---

## Reliability

| Requirement | Target | Notes |
|-------------|--------|-------|
| System uptime (trading days, 8 AM–7 PM MYT) | ≥ 99.5% | Equivalent to < 3.65 hours downtime per year during trading hours |
| System uptime (off-peak) | ≥ 99.0% | Lower threshold for overnight and weekend periods |
| Price data freshness on trading days | ≥ 99.5% of trading days have at least one successful refresh per position | Measured over rolling 30-day window |
| Price data outage detection time | ≤ 5 minutes | System must detect a failed price refresh and surface a warning to users within 5 minutes |
| Data backup frequency | Daily automated backup | Minimum; point-in-time recovery capability strongly recommended |
| Recovery time objective (RTO) | ≤ 4 hours | Maximum downtime before service restoration |
| Recovery point objective (RPO) | ≤ 24 hours | Maximum data loss acceptable in a worst-case failure |

---

## Security

| Requirement | Target | Notes |
|-------------|--------|-------|
| Authentication method | Email + password with bcrypt hashing (min cost factor 12) or equivalent | No plain-text password storage under any circumstances |
| Password requirements | Minimum 8 characters; must include at least one number and one letter | Display strength indicator; enforce on registration and reset |
| Session management | Sessions expire after 30 days of inactivity; provide explicit logout | HTTP-only, Secure cookies for session tokens |
| Transport encryption | HTTPS enforced across all endpoints; TLS 1.2 minimum | HTTP redirects to HTTPS; HSTS header required |
| Data encryption at rest | User portfolio data encrypted at rest | AES-256 or equivalent; particularly covers financial data |
| Rate limiting | Authentication endpoints: max 5 failed attempts per 10 minutes per IP before lockout | Prevents brute-force attacks |
| CSRF protection | All state-changing requests protected by CSRF tokens | Standard framework-level protection |
| Sensitive data in logs | Portfolio values, dividend amounts, and personal data must NOT appear in server logs | Log sanitisation required |

---

## Scalability

| Requirement | Target | Notes |
|-------------|--------|-------|
| Concurrent users at V1 launch | Support ≥ 500 concurrent active sessions without degradation | Conservative target for initial deployment |
| Portfolio size per user | Support ≥ 50 positions and ≥ 400 dividend tranche records per user | Covers 10× the reference Excel model without performance impact |
| Total price refresh load | Support ≥ 10,000 price lookup calls per trading day | Accounts for 500 users × 20 positions with buffer |
| Database growth assumption | Design for ≥ 10,000 user accounts and ≥ 500,000 dividend tranche records in Year 1 | Should not require re-architecture to achieve this |

---

## Auditability

| Requirement | Target | Notes |
|-------------|--------|-------|
| Dividend tranche edit history | Every change to a dividend tranche (amount, date) is logged with the previous value and timestamp | Required for user trust and error correction |
| Position edit history | Every change to a position (share count, price, broker) is logged | Silent correction of errors undermines trust |
| Price override log | Manual price overrides are recorded with timestamp and replaced-by value when automated data resumes | Enables users to verify that overrides were correctly superseded |
| Change attribution | All edits are attributed to the authenticated user who made them | Required for PDPA accountability |

---

## Compliance

| Requirement | Target | Notes |
|-------------|--------|-------|
| PDPA — Data minimisation | Collect only email, password, and portfolio data; no collection of national ID, phone, or financial account numbers | Not a financial institution; no reason to collect sensitive identity data |
| PDPA — Data access | Users can request a full export of their data in CSV format | Must be implemented before launch; PDPA right of access |
| PDPA — Data deletion | Users can request account and all associated data deletion; deletion completed within 30 days | PDPA right of erasure |
| PDPA — Privacy policy | A PDPA-compliant privacy policy must be in place before user accounts are created | Required by Malaysian law for any personal data processor |
| Financial disclaimer | All yield, P&L, and scenario calculations must be accompanied by a persistent disclaimer: "BursaTrack is a portfolio tracking tool and does not provide financial advice. All calculations are informational only." | Avoids regulatory risk from being characterised as a financial advisory service |
| Stamp duty rate | The stamp duty rate must be configurable without a code deployment | Required to update the rate if the 0.10% remission expires in July 2028 |

---

# SECTION H: Core Domain Model

*Conceptual business model. Not a database schema.*

---

## User

**Purpose:** Represents a registered account holder with their own private portfolio.

**Key Attributes:**
- Email address (unique, used for login)
- Password (hashed)
- Default broker (used when adding new positions; can be overridden per position)
- Account status (trial / active subscriber / cancelled)
- Trial expiry date
- Account creation date

**Relationships:**
- A User owns one Portfolio.
- A User has one default Broker setting.

---

## Portfolio

**Purpose:** The container for all of a user's Bursa equity holdings. A user has exactly one Portfolio at v1.

**Key Attributes:**
- Owner (User)
- Total all-in cost (derived: sum of all Position all-in costs)
- Total dividend income (derived: sum of all Position dividend income)
- Blended yield (derived: total dividend income ÷ total all-in cost)
- Last price refresh timestamp

**Relationships:**
- A Portfolio belongs to one User.
- A Portfolio contains one or more Positions.

---

## Position

**Purpose:** A specific stock held in the portfolio. A Position represents one security (e.g., CIMB 1023) and may contain multiple Lots (purchase tranches).

**Key Attributes:**
- Stock code (e.g., 1023)
- Stock name (e.g., CIMB)
- Category tag (Dividend / Volatile / Growth)
- Total shares (derived: sum of all Lot share counts)
- Blended purchase price per share (derived: weighted average across Lots)
- Total initial purchase amount (derived: sum of all Lot initial amounts)
- Total all-in cost (derived: sum of all Lot all-in costs)
- Total dividend income (derived: sum of all DividendTranche total amounts)
- Total dividend per share (derived: sum of all DividendTranche per-share amounts)
- Dividend yield (derived: total dividend income ÷ total all-in cost)
- Current price (from PriceSnapshot or manual override)
- Current market value (derived: total shares × current price)
- Unrealised P&L (derived: current market value − total all-in cost)

**Relationships:**
- A Position belongs to one Portfolio.
- A Position has one or more Lots.
- A Position has zero or more DividendTranches.
- A Position references one PriceSnapshot (current price).

---

## Lot

**Purpose:** A single purchase of a Position at a specific price and date. Multiple Lots under one Position represent different entry points.

**Key Attributes:**
- Parent Position
- Number of shares
- Purchase price per share
- Purchase date
- Broker (may differ from user default)
- Initial purchase amount (derived: shares × price)
- Brokerage fee (derived: per broker rate, min RM8 or flat fee)
- Clearing fee (derived: initial amount × 0.03%)
- Stamp duty (derived: ROUNDUP(initial amount / 1,000, 0))
- All-in cost (derived: initial amount + brokerage + clearing + stamp duty)

**Relationships:**
- A Lot belongs to one Position.
- A Lot references one Broker.

---

## Broker

**Purpose:** Represents a brokerage firm with its specific fee structure for Bursa Malaysia equity trades.

**Key Attributes:**
- Broker name (e.g., Maybank Investment, MooMoo, Rakuten Trade, M+ Online)
- Fee type (percentage or flat)
- Fee rate (e.g., 0.10% for percentage; RM3 for flat)
- Minimum fee (e.g., RM8 for percentage-based; N/A for flat)

**Relationships:**
- A Broker is referenced by one or more Lots.
- A Broker is the default for a User.

**Notes:** At v1, Broker is a pre-populated reference list with a small number of common Malaysian brokers, plus a "Custom" option where the user can enter their own rate.

---

## DividendTranche

**Purpose:** A single declared dividend payment for a Position. Up to 8 tranches per Position per calendar year.

**Key Attributes:**
- Parent Position
- Tranche number (1st through 8th)
- Dividend per share (MYR)
- Total dividend amount (derived: dividend per share × total shares in parent Position)
- Payment date
- Ex-dividend date (optional; used by dividend calendar)
- Year (to scope to one financial year)

**Relationships:**
- A DividendTranche belongs to one Position.

**Notes:** The "per-share" amount is stored and the total is derived. This matches the Excel model's row structure (rows 12–19 store per-share; rows 21–28 derive totals). Storing per-share enables recalculation if share count is edited.

---

## PriceSnapshot

**Purpose:** Records the most recent known price for a stock, either from automated refresh or manual override.

**Key Attributes:**
- Stock code
- Price (MYR)
- Source (automated / manual)
- Timestamp
- Trading day (the Bursa trading day the price corresponds to)

**Relationships:**
- A PriceSnapshot is referenced by one or more Positions with the same stock code.

**Notes:** A single PriceSnapshot record per stock per trading day is sufficient. Multiple Positions holding the same stock share one price record.

---

## SellScenario (Calculator)

**Purpose:** A transient calculation object — not persisted. Represents one set of sell simulation inputs and outputs for a Position.

**Key Attributes:**
- Source Position (or ad-hoc: stock + shares + all-in cost)
- Sell price
- Gross proceeds (sell price × shares)
- Sell brokerage fee
- Sell clearing fee
- Sell stamp duty
- Net proceeds (gross − fees)
- Profit/Loss (net proceeds − all-in cost)
- Break-even flag (true if profit/loss ≥ 0)

**Relationships:**
- A SellScenario references one Position (or is built ad-hoc without a portfolio position).

---

# SECTION I: Product Analytics & Success Metrics

## Acquisition

| Metric | Description | Target (Month 6) |
|--------|-------------|-----------------|
| Weekly sign-ups | New account registrations per week | 20 sign-ups/week |
| Acquisition source attribution | % of sign-ups from search / referral / community (i3investor, Reddit, KLSE Screener forum) | Track all; goal: ≥ 40% organic search by month 6 |
| Landing page conversion rate | Visitors who start account registration / total landing page visitors | ≥ 8% |
| Trial-to-registration drop-off | Users who begin registration but do not complete it | < 20% abandonment on registration form |

---

## Activation

Activation is defined as a user completing the minimum viable onboarding sequence: at least one position added with all-in cost calculated, and at least one dividend tranche logged.

| Metric | Description | Target |
|--------|-------------|--------|
| Portfolio created (first position added) | % of registered users who add at least one position | ≥ 80% within 24 hours of registration |
| Onboarding completion | % of registered users who add ≥ 3 positions AND ≥ 1 dividend tranche | ≥ 50% within 7 days of registration |
| CSV import usage | % of onboarding users who use CSV import vs. manual entry | Track; use to decide if CSV import reduces abandonment |
| Time-to-first-value | Time from account creation to first yield calculation displayed | Target median ≤ 10 minutes |
| Activation rate | % of sign-ups who reach "activated" state (3+ positions, 1+ dividend) | ≥ 50% |

---

## Engagement

| Metric | Description | Target (Month 6) |
|--------|-------------|-----------------|
| Daily Active Users (DAU) | Unique users who open the dashboard on a given trading day | 60% of paying subscribers |
| Weekly Active Users (WAU) | Unique users who interact with any feature in a 7-day window | ≥ 85% of paying subscribers |
| Monthly Active Users (MAU) | Unique users active in a 30-day window | ≥ 95% of paying subscribers |
| DAU/MAU ratio | Measure of daily engagement (stickiness) | ≥ 0.50 (indicating daily habitual use among active users) |
| Feature usage — dividend logging | % of active users who log at least one dividend per month | ≥ 70% |
| Feature usage — sell calculator | % of active users who use the calculator at least once per month | ≥ 30% |
| Session length (median) | Time spent in app per session | 3–8 minutes (reflects a healthy daily check, not excessive friction) |

---

## Retention

| Metric | Description | Target |
|--------|-------------|--------|
| D7 retention | % of registered users still active 7 days after sign-up | ≥ 50% |
| D30 retention | % of registered users still active 30 days after sign-up | ≥ 35% |
| D90 retention | % of registered users still active 90 days after sign-up | ≥ 25% |
| Monthly churn rate (paid) | % of paying subscribers who cancel in a given month | < 5% |
| Reactivation rate | % of churned users who return within 90 days | Track; no target set at v1 |
| Churn reason survey | % of cancellations with a reason captured | ≥ 60% (in-app cancellation flow with required reason field) |

**Churn early-warning signals to instrument:**
- User has not opened the dashboard in 7 consecutive trading days.
- User has not logged a dividend in 45 days (may indicate the portfolio is stale).
- User's last price refresh failed and manual override was not used within 48 hours.

---

## Revenue

| Metric | Description | Target |
|--------|-------------|--------|
| Free trial conversion rate | % of trial users who convert to a paid subscription | ≥ 25% |
| MRR (Monthly Recurring Revenue) | Total subscription revenue per month | RM 2,000 at month 6; RM 4,000 at month 12 |
| ARPU (Average Revenue Per User) | MRR ÷ paying subscribers | RM 20/month (at mid-range pricing) |
| Paying subscribers | Total active paid accounts | 100 at month 6; 200 at month 12 |
| LTV (Lifetime Value) estimate | ARPU ÷ monthly churn rate | RM 400 at 5% churn; RM 200 at 10% churn |
| Revenue by pricing tier | Breakdown if multiple tiers offered | Track from launch |

---

## Analytics Implementation Notes

**Minimum tracking stack at V1:** server-side event logging for all activation, engagement, and revenue metrics. A lightweight self-hosted or privacy-respecting analytics tool (e.g., Plausible, PostHog) is recommended over Google Analytics given the financial data sensitivity and PDPA compliance requirements.

**Events to instrument at launch:**
- `account_created`
- `first_position_added`
- `onboarding_completed` (3+ positions, 1+ dividend)
- `csv_imported`
- `dividend_logged`
- `sell_calculator_opened`
- `subscription_trial_started`
- `subscription_converted`
- `subscription_cancelled` (with reason)
- `price_refresh_failed` (system event)
- `manual_price_override_entered`

---

## Business Analysis Readiness Assessment

### Ready Areas

The following sections are sufficiently complete for BA handoff and engineering estimation without further clarification:

- **Problem Definition (Section 2):** Well-evidenced with specific formula references; BA can derive data validation requirements directly from the Excel model analysis.
- **Fee Calculation Logic (REQ-002 + Acceptance Criteria):** The brokerage (per-broker), clearing (0.03%), and stamp duty (RM1/RM1,000 ROUNDUP) are specified at implementation precision. The acceptance criteria confirm expected outputs against known values.
- **Dividend Tranche Model (REQ-004 + Domain Model):** The 8-tranche limit, per-share storage, and derived total calculation are unambiguous. The domain model clarifies why per-share values are stored rather than totals.
- **Yield Calculation (REQ-005 + Acceptance Criteria):** The denominator (all-in cost, not pre-fee amount) and the calculation method are unambiguous. The acceptance criteria include a specific numeric test case (5.57% vs. 5.58%).
- **Sell Calculator Logic (REQ-007 + Acceptance Criteria):** The calculation chain (gross proceeds → fees → net proceeds → P&L vs. buy all-in cost) is fully specified, including a numeric break-even test case.
- **Non-Functional Requirements:** Performance, reliability, security, scalability, auditability, and compliance targets are specified at measurable levels.
- **Domain Model:** Entities, key attributes, and relationships are defined at conceptual level; sufficient to begin data model design.

---

### Areas Requiring BA Investigation

The following areas need BA workshop time to resolve ambiguities before engineering estimation:

1. **Multi-lot yield calculation method.** REQ-001 accepts multiple lots per position. The yield calculation (REQ-005) must define how yield is computed for a multi-lot position. Options: (a) blended all-in cost across all lots as one denominator, (b) separate yield per lot. The PRD implies (a) but does not state it explicitly. **BA must confirm and document the calculation method.**

2. **Dividend tranche scope — per year or per stock?** The domain model defines "up to 8 tranches per calendar year" for a Position. The PRD does not specify how year boundaries are handled: does the 8-tranche limit reset on January 1, or on the stock's financial year end? **BA must define year boundary behaviour and how historical years' dividends are displayed.**

3. **CSV import field mapping.** The CSV import requirement (REQ-009) references a template but does not define the required columns, field formats, or validation rules at spec level. **BA must produce the CSV template specification including field names, data types, required vs. optional, and example values.**

4. **Broker fee type configuration.** The Broker domain entity defines "fee type: percentage or flat." The system must handle three known patterns: (a) pure flat (MooMoo: RM3), (b) pure percentage with minimum (Maybank: 0.10%, min RM8), (c) tiered (Rakuten Trade: RM2.88 flat under RM10K, then 0.10%). Tiered broker fee handling is not specified in the PRD. **BA must determine whether tiered brokers are supported at V1 or simplified to a single rate with a user override.**

5. **Trial period definition.** The PRD references a subscription billing model and a trial period but does not define the trial length (7 days, 14 days, 30 days), what features are available in trial vs. paid, or how the paywall is enforced. **BA must define the trial boundary and feature gating logic.**

6. **Dividend calendar data source.** REQ-008 states that calendar dates are user-entered (no automated scraping). The acceptance criteria confirm this. However, the user stories for ex-date entry reference "adding ex-date when logging dividends" — the BA must confirm whether ex-date is an optional field on the DividendTranche or a separate entity. **BA must define the ex-date data model and entry UX.**

---

### Stakeholder Decisions Required

The following require explicit decisions from the product owner before BA can complete requirements:

| Decision | Options | Recommendation |
|----------|---------|---------------|
| CSV Import priority | Keep as "Should Have" (V1.1) or promote to "Must Have" (V1) | Promote to V1 Must Have; onboarding abandonment is the highest-probability failure mode |
| Trial period length | 7 / 14 / 30 days | 14-day trial recommended: long enough for a dividend event to occur, short enough to drive conversion |
| Tiered broker fee support | Support Rakuten Trade tiered structure at V1, or simplify to percentage + minimum with user override | Simplify to two-rate model at V1; add tiered support in V1.1 based on user feedback |
| Free tier | No free tier (trial only) vs. permanent free tier (up to N positions) | Defer decision until willingness-to-pay interviews complete; do not build subscription billing assumptions until this is resolved |
| SST on brokerage | Exempt (current assumption) vs. 6% SST applied | Verify against July 2025 Bursa SST FAQ immediately; if SST applies, this is a V1 Must Have change |
| Portfolio count per user | One portfolio per user (V1) vs. multiple named portfolios | One portfolio per user at V1; multiple portfolios in V1.1 backlog |
| KLSE Screener gap validation | Proceed to build without hands-on KLSE Screener testing, or gate V1 scope on competitive validation | Gate V1 scope on 2-hour KLSE Screener hands-on test; competitive differentiation must be confirmed |

---

### Remaining Risks

The following risks from the base PRD remain open and are not mitigated by the enhancements in this document:

| Risk | Status | Action Required |
|------|--------|----------------|
| yfinance reliability on Bursa data | Unmitigated — no alternative data source identified | Run 20-day monitoring experiment before V1 build commences; identify fallback source (Bursa API, broker data partnership) |
| Malaysian willingness to pay | Unvalidated | Complete 10 willingness-to-pay interviews before building subscription billing |
| KLSE Screener feature gap | Unconfirmed | Complete 2-hour hands-on KLSE Screener evaluation for 16-stock dividend portfolio |
| SST on brokerage (July 2025 FAQ) | Unresolved | Read the Bursa SST FAQ immediately; binary outcome; 10-minute task |
| Onboarding abandonment | Partially mitigated by CSV Import promotion to V1 | Requires validation through pilot onboarding test with a target user |
| PDPA compliance | Partially mitigated by NFR section | Requires one-time legal review before user data is collected |

---

### Final BA Readiness Score

**6.5 / 10**

**Reasoning:** The enhanced PRD is materially more ready for BA handoff than the base document. The addition of user stories, acceptance criteria, NFRs, domain model, competitive analysis, and analytics framework closes the most significant gaps. The fee calculation, yield logic, and sell calculator are specified to a level that engineering could begin estimation.

The score does not reach 8+ for two reasons:

1. **Six areas of BA investigation remain open** (multi-lot yield method, tranche year boundaries, CSV field spec, broker tiered fee handling, trial definition, and ex-date data model). These are resolvable in a single BA workshop but must be closed before any engineering sprint can be sized.

2. **Three stakeholder decisions have not been made** that affect scope and architecture: CSV import priority, tiered broker fee support, and the free tier model. Until these are decided, the V1 scope is not final.

The document is ready for a BA kickoff workshop. It is not yet ready for engineering estimation on all features.

---

*End of Principal PM Review — BursaTrack PRD v1 Enhancement Document*
*All enhanced sections are designed for direct insertion into BursaTrack-PRD.md*
