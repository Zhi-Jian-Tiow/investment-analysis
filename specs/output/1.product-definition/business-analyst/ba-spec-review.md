# BursaTrack — Business Analysis Quality Review

> **Reviewer Role:** Senior Business Analyst Quality Reviewer (Finance Industry)
> **Document(s) Reviewed:** BursaTrack-BAS-Part1.md, BursaTrack-BAS-Part2.md, BursaTrack-BAS-Part3.md (v1.0, Draft — For Engineering and QA Review)
> **Reference Document:** BursaTrack-PRD-Final.md (v2.0, Final)
> **Review Date:** 2026-06-21
> **Review Scope:** Functional completeness, requirement clarity, business rule quality, data model integrity, workflow coverage, acceptance criteria, edge cases, and finance-industry-specific risk (transaction integrity, calculation accuracy, auditability, security, compliance).

---

# 1. EXECUTIVE VERDICT

## APPROVE WITH CONDITIONS

The Business Analyst Specification is unusually mature for a draft document — it independently resolves five of the six "BA investigation areas" the PRD explicitly flagged (multi-lot yield method, CSV field spec, tiered broker handling, ex-date data model, dividend year-boundary ownership), and it carries forward open items transparently rather than silently assuming them away. The fee calculation, yield, and sell-calculator logic are specified to implementation precision with numeric test cases that can be directly converted into unit tests.

However, the specification cannot proceed to engineering estimation as-is. This review identifies **one critical calculation-integrity defect that the BAS itself does not recognise as a defect** (it is documented as "correct by design" when it produces incorrect historical dividend figures), **one direct contradiction between the BAS and the PRD on PDPA data-export scope**, and several auditability and authentication gaps that must be closed before a sprint can be sized with confidence. None of these require a rewrite — they require a short, focused remediation pass plus the BA kickoff workshop the document itself already calls for.

---

# 2. CONFIDENCE SCORE

## 6.5 / 10

**Reasoning:** The document's own self-assessed score of 7.5/10 is a reasonable estimate of its *breadth* of coverage but does not account for two things an independent reviewer must weigh more heavily: (1) a silent financial-calculation defect in the dividend-income model that directly contradicts the product's own "Accuracy Before Features" principle and its explicit goal of avoiding "the row 28 bug class," and (2) a scope contradiction between the BAS and the PRD on a compliance-relevant feature (PDPA data export). Both are exactly the category of defect a finance-industry BA review exists to catch before they reach engineering. The remaining gaps (password reset, account deletion detail, audit-log entity coverage) are real but lower-severity and already partially self-identified. Once the calculation defect is corrected and the PDPA scope conflict is resolved, this document is close to a 9/10.

---

# 3. SUMMARY OF FINDINGS

## Strengths

- **Fee and yield calculation logic is implementation-ready.** BR-001 through BR-008 specify brokerage, clearing fee, stamp duty, and all-in cost with numeric worked examples (RM41,900 → RM41,996.47) that match the PRD exactly and can be lifted directly into unit tests.
- **The document resolves most PRD-level open items rather than re-deferring them.** Multi-lot blended yield (BR-013), CSV template field spec (Section 7), tiered broker simplification (Broker entity notes), and ex-date placement (DividendTranche.ex_dividend_date) are all now defined to a build-ready level of detail. This is genuine BA value-add, not a restatement of the PRD.
- **Exception handling and edge-case coverage is broad.** Ten exception scenarios (EX-001–EX-010) and twenty-one edge cases (EC-001–EC-021) cover price feed failure, payment webhook failure, delisted stocks, CSV duplicate handling, and stamp-duty rate transitions — well beyond the PRD's own coverage.
- **The document is self-aware about its own gaps.** Section 15 ("BA Quality Review") candidly lists missing business rules, requirement gaps, ambiguities, and a graded BA confidence score with reasoning — a level of self-critique not common in BA drafts.
- **Atomicity and idempotency are explicitly designed**, not assumed: CSV import is all-or-nothing (BR-022), payment webhooks must be idempotent (EC-018), and audit log entries are immutable.

## Weaknesses

- **A core calculation rule produces financially incorrect historical figures and is misclassified as correct.** This is the most serious finding in this review (see CRIT-01).
- **The BAS and PRD disagree on whether PDPA data export is in V1 scope or deferred to V1.1**, and the BAS's own Permissions table assumes it is built at V1 without flagging the conflict.
- **Audit log entity coverage is narrower than the PRD's NFR requires.** The PRD explicitly requires "Position edit history... every change to a position... is logged," but the AuditLog entity_type enum only covers Lot, DividendTranche, and PriceSnapshot.
- **Standard authentication workflows (password reset, email change) are acknowledged as missing but not specified**, only assumed at a one-line level.
- **Concurrency and duplicate-submission edge cases are absent.** No rule addresses two simultaneous edits to the same position/lot, or duplicate form submission (e.g., double-click on "Add Dividend").
- Several blockers the BAS itself flags (SST applicability, trial period length, sell-calculator broker selection for multi-lot/multi-broker positions) are correctly identified but remain unresolved — meaning the document is *transparently* incomplete rather than *falsely* complete in these areas, which is good practice but still blocks estimation.

## Overall Assessment

This is a high-quality first-pass BA specification with genuine engineering value in its calculation logic, data model, and exception/edge-case catalogue. It is not yet safe to hand to engineering for full estimation because it contains one undetected calculation defect that strikes directly at the product's core value proposition (provable accuracy) and one scope contradiction with the PRD on a compliance feature. With a focused remediation pass — not a rewrite — this document can reach a 9/10 readiness level.

---

# 4. CRITICAL ISSUES

---

**Issue ID:** CRIT-01

**Severity:** Critical

**Problem:** The dividend-income calculation model recalculates *historical* dividend totals using the *current* total share count of a position, not the share count that was actually held when each tranche was paid. BR-009 stores `dividend_per_share` and derives `total_amount = per_share_amount × Position.total_shares` at read time (confirmed in Part 1 BR-009/BR-012 and in Part 2's DividendTranche derived-values table). Edge case EC-008 explicitly walks through this: if a user later edits or adds a lot that changes `total_shares`, "all previously logged dividend tranche totals change retroactively," and the BAS labels this **"Correct by design."**

It is not correct. If a user holds 5,000 CIMB shares, receives a tranche of RM0.20/share (correctly RM1,000 at the time), and *later* buys 2,000 more CIMB shares (a new Lot, raising `total_shares` to 7,000), the system will retroactively restate that already-paid historical dividend as RM1,400 — income the user never actually received, because the extra 2,000 shares were not held on the dividend's record date. The same error occurs in reverse if shares are later sold or a lot is corrected downward.

**Impact:** This is functionally the same defect class the product was explicitly built to eliminate (the Excel "row 28" bug, where a derived total silently used the wrong reference). It directly contradicts Product Principle 1 ("Accuracy Before Features") and Principle 4 ("Trust Through Transparency" — "every all-in cost shows its fee breakdown... users should never have to take a number on faith"). Because dividend income feeds directly into the yield calculation (BR-008, REQ-005), this defect will silently inflate or deflate the yield figure — the single number the entire competitive positioning ("BursaTrack shows your *actual* yield") depends on. If discovered by a user post-launch, per Product Principle 1's own stated logic, it "destroys the product's core value proposition."

**Recommended Fix:** Store `total_amount` on the DividendTranche record at creation time, calculated against the share count actually held at that point in time (not derived from the position's current total shares). Re-derivation should only be triggered explicitly when a user corrects a *prior* lot's share count for an error (EC-008's stated scenario), and even then, only the shares held as of the tranche's payment date should be used — not the position's all-time total. This requires the domain model to track a point-in-time share count (e.g., snapshotting `shares_held_at_tranche` on the DividendTranche, or deriving it from the sum of Lots with `purchase_date <= tranche.payment_date`). This decision should be escalated to the BA kickoff workshop as a blocker, not treated as resolved.

---

**Issue ID:** CRIT-02

**Severity:** High

**Problem:** The PRD Scope Definition (Section 9, "In Scope") lists "PDPA-compliant privacy policy **and user data export**" as in-scope for V1. The PRD's own V1.1 phased release plan (Section 10) simultaneously lists "PDPA-compliant data export (user data download)" as **deferred to V1.1** ("Required for compliance but not a primary user workflow; can be added post-launch") — an unresolved contradiction within the PRD itself. The BAS does not surface this contradiction. Instead, its Permissions & Access Control table (Part 2, Section 9) lists "Export portfolio data (PDPA)" as an allowed action for Trial, Paid, and Expired Trial users with no V1/V1.1 qualifier and no functional requirement (FR-xxx) ever defines the export workflow, format, or trigger.

**Impact:** Engineering cannot estimate this feature because it is unclear whether it must ship at V1 (compliance-relevant — PDPA right of access) or V1.1. If V1.1 is the actual intent, the Permissions table is presenting an inaccurate access model to downstream teams. If V1 is the actual intent, there is no functional requirement, workflow, or acceptance criteria for it anywhere in the BAS — a true requirement gap.

**Recommended Fix:** Escalate the PRD-level contradiction to the Product Owner for a single binary decision (V1 Must Have vs. V1.1), then either (a) write a full FR for data export (trigger, format — CSV per the PDPA right of access stated in the PRD NFR table —, file contents, delivery mechanism) with acceptance criteria, or (b) update the Permissions table to remove "Export portfolio data" from V1 role capabilities and note it as a V1.1 item.

---

**Issue ID:** HIGH-01

**Severity:** High

**Problem:** The PRD's Auditability NFR explicitly requires: "Position edit history — every change to a position (share count, price, broker) is logged." The BAS's AuditLog entity (Part 2, Section 7) restricts `entity_type` to an enum of `Lot / DividendTranche / PriceSnapshot` — Position is not a covered entity type, despite FR-005 ("Edit Position / Lot") describing edits to position-level fields (category tag, stock name corrections) as a single combined workflow.

**Impact:** As written, an edit to a Position-level field (e.g., correcting a category tag, or a stock name/display name correction) has no defined audit trail, which is a direct gap against the PRD's stated compliance requirement and against PDPA accountability ("All edits attributed to the authenticated user who made them").

**Recommended Fix:** Add `Position` to the AuditLog `entity_type` enum, and clarify in FR-005 which Position-level fields are independently editable (separate from Lot-level edits) so the audit trail design is complete.

---

**Issue ID:** HIGH-02

**Severity:** Medium-High

**Problem:** Password reset ("Forgot Password") and email-change workflows are acknowledged by the BAS itself (Part 3, Section 15, "Potential Requirement Gaps" #1 and #2) as undefined, with only a one-line assumption ("standard email-based reset link, expires 1 hour"). No FR, acceptance criteria, validation rules, or rate-limiting rule exists for either flow, despite BR-016 establishing rate-limiting discipline for login.

**Impact:** Password reset is a day-one launch requirement (a user will need it within the first week of any real user base), not a deferrable nice-to-have. Without a specified flow, engineering will build it ad hoc, and QA has no acceptance criteria to test against — including security-relevant behaviour like reset-link expiry, single-use tokens, and rate-limiting reset requests (which is itself a common abuse vector the current spec does not address for any endpoint other than login).

**Recommended Fix:** Write a full FR for password reset (trigger, token generation/expiry, single-use enforcement, rate limiting on reset requests per BR-016's pattern) before engineering estimation. Email change can reasonably be deferred to V1.1, but should be explicitly scoped out rather than left silent.

---

# 5. REQUIREMENT QUALITY SCORECARD


| Category                | Score (1-10) | Comments                                                                                                                                                                                                                                                                                                                                               |
| ----------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Functional Requirements | 8            | FR-001–FR-016 are well-structured with clear triggers, preconditions, main flow, and postconditions. Comprehensive coverage of all ten PRD requirements plus implicit auth/subscription dependencies.                                                                                                                                                  |
| Business Rules          | 6            | Fee/stamp-duty/clearing-fee rules (BR-001–BR-007) are excellent. The dividend-income aggregation rule (BR-009/BR-012) contains the critical defect described in CRIT-01, which pulls this category down significantly given its centrality to the product's value proposition.                                                                         |
| User Stories            | 8            | Clearly traceable to personas and FRs; appropriately scoped, no overly technical phrasing.                                                                                                                                                                                                                                                             |
| Acceptance Criteria     | 8            | Strong use of Gherkin-style Given/When/Then with real numeric values matching the PRD's reference figures (RM41,996.47, 5.57% yield). Good coverage of happy path, alternates, and errors for most FRs — though REQ-008/FR-013 (dividend calendar) and FR-010 (edit dividend tranche) have thinner acceptance criteria than the calculation-heavy FRs. |
| Workflows               | 8            | Seven end-to-end process flows with alternative and error branches; good coverage of registration, onboarding, daily use, import, and subscription lifecycle.                                                                                                                                                                                          |
| Data Requirements       | 7            | Entities, fields, and derived values are clearly specified, including a thoughtful note on storing fees at creation time to handle future rate changes. Reduced by the AuditLog entity_type gap (HIGH-01) and the unresolved "current year" dividend scope ambiguity.                                                                                  |
| Edge Cases              | 7            | Twenty-one edge cases is a strong catalogue, covering data, workflow, user-behaviour, and operational categories. Missing: concurrent edit handling and duplicate/double-submission protection (see Section 8).                                                                                                                                        |
| Exception Handling      | 8            | Ten exception scenarios with clear cause, system behaviour, user message, and recovery action — a genuinely usable QA reference.                                                                                                                                                                                                                       |
| Security                | 7            | Rate limiting, session expiry, CSRF, and password complexity rules are specified and consistent with the PRD NFRs. Reduced for the missing password-reset and abuse-prevention rules on non-login endpoints (HIGH-02).                                                                                                                                 |
| Auditability            | 6            | Strong design intent (immutable, attributed, previous/new value snapshots) undermined by incomplete entity coverage (HIGH-01) and by CRIT-01, which means the audit trail can faithfully record an *incorrect* calculation without any mechanism flagging that the recorded historical total has silently changed.                                     |


---

# 6. MISSING REQUIREMENTS

---

**Requirement Area:** Point-in-time dividend share count

**Missing Detail:** No field or rule captures the number of shares actually held at the time a dividend tranche was paid, independent of the position's current total share count.

**Why It Matters:** Without this, the dividend-income total for any historical tranche silently changes whenever the position's share count changes for any reason (new lot, edit, future sell tracking). See CRIT-01.

**Suggested Addition:** Add a stored `shares_held_at_payment` (or equivalent) value to DividendTranche, populated at creation time from the position's total shares as of `payment_date`, and used as the multiplier for `total_amount` instead of the live `Position.total_shares`.

---

**Requirement Area:** Password reset workflow

**Missing Detail:** No FR, acceptance criteria, or business rule for "Forgot Password."

**Why It Matters:** This is a standard, near-immediate-need authentication workflow; building it without a spec risks inconsistent security behaviour (token expiry, single-use, rate limiting).

**Suggested Addition:** A full FR covering: reset request trigger, token generation and expiry (1 hour, per the BAS's own stated assumption), single-use token enforcement, rate limiting on reset requests, and the email content/format.

---

**Requirement Area:** PDPA data export — functional specification

**Missing Detail:** No FR defines what "export portfolio data" actually produces (file format, contents, trigger, delivery method, V1 vs. V1.1 status).

**Why It Matters:** Listed as an allowed user action in the Permissions table with no underlying requirement; also conflicts with the PRD's own internal V1/V1.1 inconsistency. See CRIT-02.

**Suggested Addition:** A full FR (trigger: user-initiated request; format: CSV per PDPA right of access; contents: positions, lots, dividend tranches, account metadata; delivery: immediate download or async email link) once V1/V1.1 placement is confirmed.

---

**Requirement Area:** Account deletion workflow detail

**Missing Detail:** The BAS notes (Section 9, Ownership Rules) a 30-day soft-delete grace period exists, and Section 15 flags the workflow as undefined, but no FR specifies the user-facing confirmation flow, what happens to active subscriptions on deletion request, or the export-before-deletion prompt.

**Why It Matters:** This is a PDPA right-of-erasure obligation explicitly named in the PRD's Compliance NFR table; an incomplete spec here is a launch-blocking compliance gap, not a nice-to-have.

**Suggested Addition:** A full FR covering: deletion request trigger, mandatory export offer before deletion, handling of an active paid subscription at time of deletion request, 30-day grace period behaviour, and final purge confirmation.

---

**Requirement Area:** Concurrency / duplicate-submission handling

**Missing Detail:** No rule addresses two simultaneous edits to the same Position/Lot (e.g., two open browser tabs) or duplicate form submissions (e.g., a double-click on "Add Dividend" creating two identical tranches).

**Why It Matters:** This is a standard finance-system data-integrity concern (the system prompt's own review criteria explicitly call out "concurrent actions" and "duplicate actions" as required edge-case categories); without a stated rule, behaviour is undefined and likely inconsistent across implementations.

**Suggested Addition:** Define a last-write-wins or optimistic-locking rule for concurrent Position/Lot edits, and an idempotency rule (e.g., disable submit button + server-side debounce) for dividend/position creation forms.

---

# 7. AMBIGUITY REVIEW

---

**Current Statement:** BR-012 — "position_total_dividend_income = SUM(dividend_per_share × position_total_shares) across all non-deleted DividendTranche records for the position in the current calendar year."

**Why Ambiguous:** "position_total_shares" is not qualified as a point-in-time value, which is exactly what produces the CRIT-01 defect. The rule reads as internally consistent but is financially incorrect when share count changes over time.

**Recommended Clarification:** Restate as: "position_total_dividend_income = SUM(tranche.total_amount) where each tranche.total_amount was fixed at creation time using the shares held as of that tranche's payment date." This should be paired with an explicit numeric example showing a lot added *after* a dividend was logged, to make the correct behaviour unambiguous to engineering.

---

**Current Statement:** "Current year" dividend income / yield scope (referenced throughout, e.g., BR-012, the dashboard spec, and explicitly flagged as ambiguous by the BAS itself in Part 3, Section 15).

**Why Ambiguous:** It is unclear whether the dashboard's headline yield figure is a current-calendar-year figure that resets every January 1, an all-time figure, or both displayed separately. This affects user-facing behaviour at every year boundary and is a recurring theme across BR-012, EC-009, and the Open Questions list — the BAS correctly flags it as unresolved but it remains a true blocker, not a documented assumption.

**Recommended Clarification:** The BA kickoff workshop should produce a definitive answer: does the dashboard show (a) current calendar year only, (b) all-time only, or (c) both, with the "yield" figure used for the core product claim clearly defined as one specific number. Given the product's positioning around "true yield," an all-time all-in-cost yield (not reset annually) is likely the more defensible default — but this is a product decision, not a BA assumption to make unilaterally.

---

**Current Statement:** EC-010 — "The sell calculator uses the broker of the most recently created lot (as a default)... This logic requires a stakeholder decision before implementation."

**Why Ambiguous:** The BAS itself flags this as undecided, but BR-004 ("Sell-Side Brokerage") is stated as if the rule were settled, without the multi-lot/multi-broker caveat. A reader of BR-004 in isolation would not know this edge case exists.

**Recommended Clarification:** Cross-reference BR-004 explicitly to EC-010 so the two are not read as contradictory, and prioritise resolving the underlying stakeholder decision — it directly affects acceptance-criteria correctness for any multi-lot position with mixed brokers.

---

**Current Statement:** Fee rounding convention (implicit throughout BR-001, BR-005, BR-006 — e.g., "brokerage fee = RM41.90," "clearing fee = RM12.57").

**Why Ambiguous:** All worked examples round to 2 decimal places, but no rule explicitly states the rounding method (round-half-up vs. round-half-to-even / banker's rounding) for brokerage and clearing fee calculations, which can matter for cent-level reconciliation against the Excel reference model and could produce off-by-one-cent disagreements with QA's expected values.

**Recommended Clarification:** Add an explicit rounding rule (e.g., "round half up to the nearest cent") applicable to brokerage fee and clearing fee calculations, consistent with how stamp duty's ROUNDUP behaviour is already explicitly defined.

---

# 8. RISK REVIEW

## Business Risks

- The dividend-income defect (CRIT-01), if it reaches production, directly undermines the product's central marketing claim ("BursaTrack shows your actual yield") — the exact failure mode the PRD's Product Manager Review already identifies as the highest-stakes trust risk for this product.
- The PRD/BAS PDPA scope contradiction (CRIT-02) creates risk of either shipping a compliance gap (if V1 is the real intent and it's not built) or presenting users/auditors with an inaccurate permissions model (if V1.1 is the real intent and the Permissions table is wrong).

## Operational Risks

- The BAS's own Operational Risk list (yfinance outage on ex-date days, CSV template versioning, stamp duty rate transition) is well-reasoned and does not need rework. One addition: no rule addresses what happens if the price refresh job itself fails mid-run for a subset of users versus all users at the infrastructure level (partial job failure vs. partial data-source failure are conflated in EX-002).

## Technical Delivery Risks

- The CRIT-01 fix likely requires a data-model change (a point-in-time share count on DividendTranche) rather than a logic-only fix. If this is discovered after engineering has already built against the current BR-009/BR-012 model, it will require a migration, not a patch — this should be resolved before estimation, not during sprint 1.
- Concurrency handling (Section 6, missing requirement) is absent from both the PRD and BAS; if not addressed at design time, it is the kind of gap that surfaces expensively post-launch under real concurrent usage (e.g., a user with the app open on both phone and desktop).

## Compliance Risks

- PDPA right-of-erasure (account deletion) and right-of-access (data export) workflows are both incompletely specified (Section 6), which is a compliance-relevant gap, not merely a UX one, under the PRD's own stated Malaysian PDPA constraints. *This is not legal advice; it is a flag that these PRD-stated compliance obligations are not yet specified to a buildable level.*
- The SC licensing question (sell scenario calculator) and the SST-on-brokerage question are correctly carried forward by the BAS as open items requiring legal/regulatory confirmation, consistent with the PRD. No new compliance risk identified beyond what the PRD already names — this review confirms the BAS has not introduced new compliance exposure here, but has also not advanced resolution of it.

---

# 9. DOWNSTREAM IMPACT

## Product Designer

**Ready / Not Ready:** Ready with conditions

**Reason:** Workflows, screens implied by FRs, and exception/error messaging are detailed enough to begin wireframing the core dashboard, position management, dividend logging, and sell calculator screens. Password reset and account deletion screens cannot be designed yet pending their missing specifications.

## Solution Architect

**Ready / Not Ready:** Not Ready

**Reason:** The domain model is conceptually sound, but the CRIT-01 fix likely changes the DividendTranche schema (point-in-time share count), and the AuditLog entity_type enum needs to be extended (HIGH-01) before a schema can be finalised. Designing against the current model risks a costly migration.

## Engineering Team

**Ready / Not Ready:** Not Ready

**Reason:** The fee/yield/sell-calculator calculation modules could begin today in isolation. However, full V1 estimation is blocked by: the CRIT-01 calculation-model decision, the CRIT-02 PDPA scope conflict, the password reset and account deletion specs, and the BAS's own already-identified blockers (SST applicability, trial period duration, sell-calculator multi-broker logic).

## QA Team

**Ready / Not Ready:** Not Ready

**Reason:** Test cases for fee calculation, yield denominator correctness, authentication happy/error paths, and CSV import atomicity can be written today and are high quality. A complete test plan cannot be produced until: the dividend-income recalculation behaviour is corrected and re-specified (CRIT-01 — otherwise QA would be certifying incorrect behaviour as correct), the "current year" yield scope is resolved, and the missing password-reset/account-deletion flows are specified.

---

# 10. REQUIRED ACTIONS BEFORE NEXT STEP

☐ Resolve CRIT-01 — redesign dividend-income calculation to use a point-in-time share count rather than the position's current total shares; update BR-009, BR-012, and the DividendTranche data model accordingly.

☐ Resolve CRIT-02 — get a binary Product Owner decision on PDPA data export V1 vs. V1.1 placement, then either write the missing FR or correct the Permissions table.

☐ Add `Position` to the AuditLog `entity_type` enum and clarify which Position-level fields are independently auditable (HIGH-01).

☐ Write a full FR for password reset, including token expiry, single-use enforcement, and rate limiting (HIGH-02).

☐ Write a full FR for account deletion (PDPA right of erasure), including the export-before-deletion prompt and active-subscription handling.

☐ Define a concurrency rule for simultaneous edits and a duplicate-submission/idempotency rule for position and dividend creation.

☐ Resolve the "current year" vs. "all-time" dividend yield display scope as a definitive product decision, not a carried-forward assumption.

☐ Resolve the sell calculator's broker-selection logic for multi-lot, multi-broker positions (already flagged by the BAS; escalate as a true blocker).

☐ Confirm trial period duration (14 days assumed) and SST applicability on brokerage fees (binary, 10-minute verification per the PRD) — both already flagged by the BAS and PRD; treat as non-negotiable before subscription billing and fee logic are built.

☐ State an explicit rounding convention for brokerage and clearing fee calculations.

---

# FINAL RECOMMENDATION

**Decision:** APPROVE WITH CONDITIONS

**Reason:** This BAS is a strong piece of analytical work — its calculation logic, workflow coverage, and exception/edge-case catalogue are well above the bar typically seen at this stage, and it independently resolved most of the PRD's own flagged investigation areas rather than simply restating them. It should not, however, proceed to full engineering estimation in its current form. The dividend-income recalculation defect (CRIT-01) is a genuine, undetected calculation-accuracy bug in a product whose entire value proposition rests on calculation accuracy, and it must be corrected — not merely re-documented — before the data model is finalised. The PDPA scope contradiction with the PRD (CRIT-02) and the audit-log entity gap (HIGH-01) are compliance-adjacent issues that should not be allowed to drift into a later sprint. The remaining items (password reset, account deletion, concurrency handling) are conventional gaps that a focused two-to-three-hour remediation and BA workshop session — already anticipated by the document's own "Recommended Next Actions" — should be able to close. Once CRIT-01 and CRIT-02 are resolved and the checklist in Section 10 is satisfied, this document is ready for Solution Architecture and full engineering estimation.

---

*BA Quality Review prepared per the Senior Business Analyst Quality Reviewer (Finance Industry) review framework.*
*Audience: Product Owner · Business Analyst · Engineering Lead · QA Lead*