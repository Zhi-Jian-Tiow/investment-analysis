# BursaTrack — Principal BA Review: Analysis, Open Items & Readiness
## Companion to BursaTrack-BAS-Enhanced.md

> **Reviewer:** Principal Business Analyst
> **Review Date:** 2026-06-21
> **Input Documents:** BursaTrack-BAS-Part1/2/3.md · BursaTrack-PRD-Final.md v2.0
> **Output Documents:** This file (analysis) + BursaTrack-BAS-Enhanced.md (full enhanced spec)

---

# SECTION 1 — CHANGE SUMMARY

| Section / Item | Classification | Reason | MVP Discipline Note |
|---|---|---|---|
| **1. Business Analysis Summary** | KEEP | Correct, complete, well-scoped | — |
| **FR-001 to FR-002 (Auth)** | KEEP | Triggers, preconditions, flows, postconditions all present | — |
| **FR-003 to FR-006 (Position/Lot)** | KEEP | Well specified; fee logic correctly delegated to BRs | — |
| **FR-007 to FR-008 (Price refresh)** | KEEP | Outage handling and manual override fully specified | — |
| **FR-009 step 5 — dividend total derivation** | **FIX** | Total derived from live position_total_shares; triggers retroactive corruption when new lots are added post-dividend. See CRITICAL below. | — |
| **FR-009 step 6 — DividendTranche creation** | **FIX** | Must store qualifying_shares; must store total_amount at logging time, not derive at read time | — |
| **FR-010 to FR-016** | KEEP | No defects found | — |
| **FR-017 — Password Reset** | **ADD** | Standard auth requirement; explicitly flagged as missing in BA Quality Review; referenced in Open Questions | Not new scope — omission from existing auth spec |
| **FR-018 — PDPA Data Export** | **ADD** | PDPA compliance requirement; PRD NFR explicitly requires it; workflow unspecified | Not new scope — compliance obligation already in PRD |
| **FR-019 — Account Deletion** | **ADD** | PDPA compliance requirement; PRD NFR explicitly requires it; workflow unspecified | Not new scope — compliance obligation already in PRD |
| **US-001 to US-016** | KEEP | Present; traceable to personas and FRs | — |
| **US-021 — Password Reset** | **ADD** | Required to match FR-017 | — |
| **US-022 — Data Export** | **ADD** | Required to match FR-018 | — |
| **US-023 — Account Deletion** | **ADD** | Required to match FR-019 | — |
| **AC for US-005 (Edit Position)** | **ADD** | Acceptance criteria absent from original BAS | — |
| **AC for US-006 (Delete Position)** | **ADD** | Acceptance criteria absent from original BAS | — |
| **AC for US-012 (Edit Dividend Tranche)** | **ADD** | Acceptance criteria absent from original BAS | — |
| **AC for US-013 (Dashboard)** | **ADD** | Acceptance criteria absent from original BAS | — |
| **AC for US-014 (Sort by yield)** | **ADD** | Acceptance criteria absent from original BAS | — |
| **AC for US-017 (Dividend Calendar)** | **ADD** | Acceptance criteria absent from original BAS | — |
| **AC for US-019 (Template Download)** | **ADD** | Acceptance criteria absent from original BAS | — |
| **AC for US-021/022/023** | **ADD** | New stories require AC | — |
| **BR-001 to BR-008** | KEEP | Calculation rules correct; worked examples verified | — |
| **BR-009 — Dividend Total Calculation** | **FIX — CRITICAL** | See calculation-integrity finding below. Deriving total from live position_total_shares produces retroactively wrong historical dividend amounts. | — |
| **BR-010 to BR-013** | KEEP | No defects found | — |
| **BR-014** | KEEP | 8-tranche limit correctly specified | — |
| **BR-015** | KEEP | Stamp duty configurability correctly required | — |
| **BR-016 to BR-024** | KEEP | No defects found | — |
| **BR-025 — Rounding Conventions (NEW)** | **ADD** | No explicit rounding method stated anywhere in BAS; required for all fee calculations to be deterministic | — |
| **BR-026 — Currency & Precision Rules (NEW)** | **ADD** | No currency or decimal precision rules stated; required for unambiguous implementation | — |
| **BR-027 — Qualifying Shares for Dividend (NEW)** | **ADD** | Required by BR-009 fix; defines the qualifying_shares field and its semantics | — |
| **BR-005 — Clearing Fee Cap** | **FIX** | Cap of RM1,000 per contract is documented in PRD fee verification but omitted from BR; should be stated even if not currently triggered | — |
| **Workflow 4 — Log Dividend Tranche** | **FIX** | Step 5 must use qualifying_shares at time of logging, not live position_total_shares | — |
| **Workflow 8 — Password Reset (NEW)** | **ADD** | Standard auth flow; absent from existing process flows | Not new scope |
| **Workflow 9 — Account Deletion / PDPA (NEW)** | **ADD** | PDPA-required workflow; absent | Not new scope |
| **DividendTranche entity** | **FIX** | Must add qualifying_shares (stored) and change total_amount from derived to stored | — |
| **AuditLog entity — entity_type enum** | **FIX** | Enum lists Lot / DividendTranche / PriceSnapshot; omits Position — contradicts PRD NFR which requires position edit history to be logged | — |
| **Validation: Year field (Dividend Tranche)** | **ADD** | No validation rule defined for the Year field despite it being a key field on DividendTranche | — |
| **Validation: Custom broker fields** | **ADD** | No validation rules for custom broker name, rate, or minimum fee | — |
| **EX-011 — Email Delivery Failure (NEW)** | **ADD** | A registration or password-reset email may not be deliverable; no handling specified | — |
| **EC-022 — Share count increases after dividend logged** | **ADD** | Directly related to BR-009 critical fix; must be an explicit edge case | — |
| **EC-023 — Yield when qualifying_shares differ from current shares** | **ADD** | Clarifies dashboard display logic after the BR-009 fix | — |
| **Open Questions** | KEEP + additions | Existing 12 questions preserved; 3 new questions added as result of findings | — |

---

# CRITICAL FINDING — Calculation Integrity (Section B)

## FINDING CI-001: BR-009 — Retroactive Dividend Corruption (CRITICAL SEVERITY)

**What the original BAS says:**

> "The system stores dividend_per_share on each DividendTranche record. The total dividend amount for a tranche is derived at read time: total = dividend_per_share × position_total_shares."

**Why this is a defect, not a design choice:**

`position_total_shares` changes whenever a new Lot is added to a Position. This means the total_amount for every historically logged dividend tranche changes retroactively whenever the user buys more shares — regardless of whether those shares were held at the time the dividend was declared.

**Worked example of the defect:**

1. User holds 5,000 CIMB shares. On 15 March 2026 they receive the 1st dividend of RM0.20/share.
2. User logs 1st tranche: per_share = RM0.20. Derived total = 5,000 × RM0.20 = **RM1,000.00**. Correct.
3. On 1 June 2026 the user buys 2,000 more CIMB shares (these shares did NOT qualify for the March dividend — they did not exist before the ex-date).
4. Next time the dashboard loads: derived total for the 1st tranche = 7,000 × RM0.20 = **RM1,400.00**.
5. The user's historical dividend income has silently increased by RM400 that was never received.
6. Portfolio yield and blended portfolio yield are now incorrect.

This is precisely the class of retroactive-computation bug the BAS correctly documents in the Excel model's row 28 issue — yet the BAS then introduces the same class of bug in its own data model.

**The fix requires two changes:**

1. Add a `qualifying_shares` field to the DividendTranche entity, defaulting to `position_total_shares` at the moment the tranche is logged. This value is **stored and immutable** after creation (it can only be changed by an explicit user edit, which is audit-logged).
2. Change `total_amount` on DividendTranche from **derived** to **stored**: `total_amount = per_share_amount × qualifying_shares`, calculated and stored at the time of creation. It does NOT update when position_total_shares changes.

**Ripple effects of this fix (all addressed in the enhanced spec):**
- FR-009 step 5: "store qualifying_shares = current position_total_shares; store total_amount = per_share × qualifying_shares"
- FR-010 (Edit Dividend Tranche): editing per_share_amount recalculates and stores a new total_amount using the stored qualifying_shares (not current shares)
- FR-004 step 6: the note "Dividend yield = total dividend income / total all-in cost (recalculated)" must clarify that total dividend income uses stored total_amounts — it does NOT re-derive from the new share count
- Workflow 4 step 5: must use qualifying_shares
- DividendTranche entity: qualifying_shares added as stored field; total_amount changed from derived to stored
- BR-009: fundamentally rewritten
- New BR-027: defines qualifying_shares semantics

**Severity: CRITICAL** — This strikes at the accuracy of the core product output (dividend income and yield figures). It must be resolved before any engineering sprint begins on the dividend tranche or yield calculation features.

---

## FINDING CI-002: Rounding Convention — Missing

**The BAS never states how MYR amounts are rounded.** This is required for deterministic implementation — two engineers implementing "RM41,900 × 0.03%" could produce RM12.57 (round half up) or RM12.57 (round half to even / banker's rounding) — which happens to agree here — but could disagree on values like RM12.575.

**Required additions:**
- Explicit rounding rule for all fee calculations (BR-025)
- Decimal precision for stored vs. displayed values (BR-026)

---

## FINDING CI-003: AuditLog entity_type Enum Missing "Position"

**PRD NFR states:** "Position edit history: every change to a position (share count, price, broker) is logged."
**BAS AuditLog entity states:** entity_type = "Enum: Lot / DividendTranche / PriceSnapshot"

Position is not in the enum. This means position-level edits (category tag, stock name corrections) would not be logged under the spec as written. FIX: Add "Position" to the enum. 

Note: In the data model, most position-level changes route through Lot edits (share count, price, broker all live on Lot). The Position entity itself stores stock_code, stock_name, display_name, and category_tag. Category tag changes should be logged. The FIX adds "Position" to the enum and clarifies which Position fields trigger an audit entry.

---

## FINDING CI-004: BR-005 Clearing Fee Cap Not Documented

**PRD Fee Verification states:** RM1,000 cap per contract. **BAS BR-005 says:** "No cap. The RM1,000 regulatory cap is not relevant below RM3.33M per transaction."

The cap is real and regulatory. Dismissing it as "not relevant" for a spec that will be used long-term is risky — the cap should be documented as part of the rule. FIX: Add the cap to BR-005 with the calculation breakeven (RM3,333,333 contract value triggers the cap).

---

# SECTION 3 — OPEN ITEMS REQUIRING STAKEHOLDER DECISION

| Item | Why It Cannot Be Resolved by BA Alone | Recommended Owner | Recommended Next Action |
|------|---------------------------------------|------------------|------------------------|
| **Trial period duration (14 days assumed)** | Business/pricing decision — affects conversion optimisation and UX | Product Owner | Decide before registration sprint begins; 14 days is the documented assumption |
| **Sell calculator broker for multi-lot, multi-broker positions** | Product positioning decision — FIFO, LIFO, or user-selectable lot matching affect P&L accuracy; wrong choice creates user complaints | Product Owner | Decision needed before sell calculator sprint; enhanced spec documents "most recent lot's broker" as the V1 assumption but flags it for explicit confirmation |
| **Is SST applicable on brokerage fees (July 2025 Bursa FAQ)?** | Legal/regulatory determination — if SST at 6% applies, all brokerage calculations are wrong | Founder — read July 2025 Bursa SST FAQ (10-minute task) | Must be resolved before any fee calculation logic is built |
| **SC licence: does the sell scenario calculator require a securities services licence under Malaysian law?** | Legal interpretation — cannot be answered by a BA | Founder + Malaysian securities lawyer | One-time legal consultation; must precede public launch |
| **Free tier model: trial-only vs. permanent freemium (up to N positions)** | Revenue model and product strategy decision | Product Owner | Resolve in parallel with subscription billing sprint; does not block auth or portfolio features |
| **"Current year" dividend income scope: calendar year or rolling 12 months?** | Product design decision with direct user-facing impact; affects dashboard metric definition | Product Owner | Decision needed before dashboard sprint; calendar year (Jan 1–Dec 31) is the documented assumption |
| **Position share count after a user sells shares: purchase records only vs. current holding?** | Fundamental product design decision — BursaTrack at V1 tracks purchase cost, not sell transactions; position total_shares reflects all purchases regardless of sells | Product Owner | Must be explicitly documented before engineering begins; current assumption (purchase records only) must be confirmed |
| **Qualifying shares for dividends: default to current total_shares at logging time OR require user to enter the ex-date share count explicitly?** | User experience trade-off — defaulting to current shares is simpler but less accurate for users who bought shares after the ex-date; requiring explicit entry is more accurate but adds friction | Product Owner | The enhanced spec defaults qualifying_shares to position_total_shares at logging time; if this assumption is wrong, the data model changes |
| **CSV conflict resolution UI for non-empty portfolio (add as lot / skip / cancel)** | UX design decision | Product Owner + Product Designer | Decide before CSV import sprint; enhanced spec documents the three options |
| **Subscription receipt / invoice: sent by BursaTrack or payment processor?** | Business operations decision | Product Owner | Should be decided before subscription billing is built |
| **Price refresh schedule: what time(s) during the trading day?** | Product decision with data cost implications | Product Owner | Enhanced spec recommends single end-of-day refresh (4:30 PM MYT) as V1 default; confirm |
| **Stamp duty rate post-July 2028: who owns the update process?** | Operations responsibility assignment | Founder / Ops | Assign before launch; the rate is configurable per BR-015, but someone must own the update |

---

# SECTION 4 — SCOPE DISCIPLINE CHECK

## ADD Items Classified as Pure Ambiguity Closure (not new scope)

The following ADD items close gaps that were already implicitly required by the PRD or the BAS itself (either stated in the BA Quality Review as missing, or referenced in compliance sections):

| ADD Item | Minimum Viable Closure Written | What Was Deliberately Left Out | Reason Left Out |
|----------|-------------------------------|-------------------------------|-----------------|
| FR-017 Password Reset | Standard email-link reset, 1-hour expiry, 6-character minimum token | Multi-factor auth, recovery codes, admin-initiated reset | Not in PRD scope; adds complexity without addressing V1 user needs |
| FR-018 PDPA Data Export | CSV export of all user portfolio data, available on request from account settings | Real-time export API, encrypted SFTP delivery, audit trail of export events | Not in PRD scope; CSV download is the minimum viable compliance path |
| FR-019 Account Deletion | Soft delete with 30-day grace period, data export offered before deletion | Immediate hard delete, automated deletion on extended inactivity | PRD specifies 30-day retention; hard delete introduces recovery risk |
| BR-025 Rounding Convention | Round half away from zero, 2dp for MYR, 4dp for yield storage | Banker's rounding analysis, alternative precision levels | Minimum needed to make fee calculations deterministic |
| BR-026 Currency & Precision | MYR, stored precision per field type | Multi-currency, exchange rate handling | Out of scope at V1 (Bursa MYR only) |
| BR-027 Qualifying Shares | Defines qualifying_shares field and its immutability | FIFO lot-level sell accounting, ex-date automatic calculation | Not in PRD scope; the fix is the minimum needed to prevent retroactive corruption |
| Missing Acceptance Criteria (7 user stories) | Happy path + key error path per story | Full combinatorial edge case coverage | Full coverage is QA's responsibility; BA specifies the contractual scenarios |
| EX-011 Email Delivery Failure | System behaviour on send failure, user message, retry recommendation | Automatic retry logic, delivery status tracking, alternative channels | Not in PRD scope; minimum is a user-facing message and a resend option |

## No Priority Escalations Made Without Explicit Flag

The enhanced specification does not upgrade any "Should Have" or "Could Have" to "Must Have" without an explicit stakeholder flag. Specifically:

- REQ-009 / FR-014 (CSV Import) was already promoted to **Must Have** in the PRD Final v2.0 by the PM, with an explicit stakeholder sign-off flag. The BAS reflects that decision — this is not a BA escalation.
- FR-017 (Password Reset), FR-018 (Data Export), FR-019 (Account Deletion) are classified as **Must Have** because they are PDPA compliance obligations (deletion, export) and a standard auth requirement (password reset) that cannot be deferred without a deliberate and documented legal risk decision. They are flagged `[REQUIRES STAKEHOLDER SIGN-OFF]` on the "Must Have" classification itself.

**Explicit confirmation: No requirement was upgraded in priority without an explicit stakeholder flag.**

---

# SECTION 5 — READINESS STATEMENT

## Enhanced Document Confidence Score: **8.5 / 10**

**Reasoning:** The original BAS had one critical calculation defect (BR-009) and several missing sections (password reset, PDPA flows, acceptance criteria for 7 user stories, rounding conventions). The enhanced document closes all of these. What keeps the score from 9–10:

- Three ESCALATE items directly affect engineering sprint planning (trial period duration, sell calculator broker selection for multi-lot positions, SST on brokerage fees). Until these are resolved, two sprints cannot be fully estimated.
- The qualifying_shares fix (BR-009) changes the DividendTranche data model; the exact UX for entering qualifying_shares vs. defaulting to current shares is a stakeholder decision that affects the dividend logging UX wireframes.

## KEEP / FIX / ADD / ESCALATE Summary

| Classification | Count |
|---|---|
| KEEP | 52 items |
| FIX | 9 items (1 CRITICAL, 8 standard) |
| ADD | 23 items |
| ESCALATE | 12 items |

## Downstream Readiness

| Team | Status | Reason |
|------|--------|--------|
| **Product Design** | Ready with Conditions | Can wireframe all core flows. Blocked on: (1) qualifying_shares UX decision (how does user enter or confirm ex-date share count when logging a dividend), (2) sell calculator broker selector for multi-lot positions, (3) paywall/trial duration |
| **Solution Architecture** | Ready with Conditions | Can model data entities and integration points. Blocked on: (1) DividendTranche qualifying_shares field confirmed, (2) price data provider selection confirmed (yfinance vs. paid alternative), (3) payment processor selection |
| **Engineering** | Ready with Conditions | Can estimate and build auth, position management, fee calculation, sell calculator, and dashboard sprints immediately. Blocked on: (1) dividend tranche sprint requires qualifying_shares stakeholder decision, (2) subscription billing sprint requires trial duration and payment processor decisions, (3) SST must be confirmed before any fee calculation logic is deployed |
| **QA** | Ready | Can begin test plan and write test cases for all specified flows. The reference Excel model (16 stocks) provides a canonical numeric fixture for all fee and yield calculations. Three items are noted as needing mock/fixture strategy (yfinance, payment webhook, session expiry timing). |

## What Would Move This to 9–10

1. SST on brokerage confirmed by reading the July 2025 Bursa FAQ (10-minute task — the single highest-leverage action available right now).
2. Qualifying shares UX decision made (default to current shares vs. user-entered; recommendation: default to current shares with a user-overridable field).
3. Trial period duration confirmed (14 days recommended; must be a stakeholder decision).
4. Sell calculator broker selection for multi-lot positions confirmed.

All four items are resolvable in a single 2-hour stakeholder session.
