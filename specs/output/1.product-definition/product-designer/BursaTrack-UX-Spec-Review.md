# BursaTrack — Product Design Specification Review
## Principal Product Design Reviewer

> **Version:** 1.0
> **Date:** 2026-06-21
> **Reviewer:** Principal Product Designer (15+ years — Google, Meta, Amazon, Stripe, Airbnb, Atlassian)
> **Inputs reviewed:**
> - BursaTrack-PRD-Final.md v2.0 (alignment check)
> - BursaTrack-BAS-Enhanced Parts 1–3 v2.0 (alignment check)
> - BursaTrack-UX-Spec Parts 1–2 v1.0 **(primary review target)**

---

# EXECUTIVE VERDICT

## ✅ APPROVE WITH CONDITIONS

The core product experience — portfolio dashboard, position management, dividend logging, sell calculator, and CSV import — is well-specified and ready for wireframing. The interaction model is cohesive, the trust-through-transparency principle is embedded throughout, and the three personas are genuinely served by the specified flows.

**However**, the specification has two systematic gaps that must be resolved before any visual design handoff can be considered complete:

1. **Screen Requirements are absent for 9 screens** (all auth screens, all Account Settings screens, the Welcome screen, and the Paywall screen). These screens will be built by engineers and designed by the visual designer — without requirements, both teams will be making assumptions.

2. **Five user flows are missing** (Edit Lot, Manual Price Override, Subscription failure/grace period, Email verification resend, and Custom Broker management). These are not edge cases — Edit is used daily by all personas.

The conditions for approval are itemised in the Recommended Enhancements section. They are scoped and achievable without reworking any existing content.

---

# DESIGN READINESS SCORE

## **7.5 / 10**

| Factor | Assessment |
|--------|------------|
| Core product flows (dashboard, add position, dividends, sell calculator, import) | Excellent — production-ready |
| Auth flows (registration, login, password reset) | Flows specified; screen requirements absent |
| Account management (settings, subscription, broker config) | Navigation defined; all screen requirements absent |
| Interaction design | Strong; 3 specific gaps identified |
| State coverage | Good for primary screens; incomplete for secondary screens |
| Accessibility | Comprehensive; 4 specific enhancements needed |
| Engineering handoff | Missing URL structure and routing; form submit behaviour undefined |
| Design system readiness | Component inventory implicit, not explicit |

---

# UX QUALITY SCORECARD

| Category | Score (1–10) | Comments |
|---|---|---|
| User Journey | 9 | All 3 personas have complete journey maps with emotional state, friction, and UX opportunity per stage. Minor gap: no return/lapsed-user journey. |
| User Flows | 7 | 8 flows defined thoroughly. Missing: Edit Lot/Position, Manual Price Override, Subscription Grace Period, Email Resend, Custom Broker. |
| Information Architecture | 8 | Clean 4-tab navigation; 4-level content hierarchy; well-grouped. Gap: no URL structure; Settings IA underspecified; V1.1 scalability not addressed. |
| Screen Inventory | 7 | Core screens complete. Missing requirements for 9 screens. Missing: Welcome screen, Paywall modal as standalone screen, Email Verification Success. |
| Screen Requirements | 6 | 9 of ~22 screens have requirements. Auth, onboarding, and all settings screens are absent. |
| Interaction Design | 8 | Forms, buttons, tables, and drill-downs are well-specified. Gaps: currency input formatting, session expiry mid-form, tab order in forms, table pagination. |
| State Coverage | 7 | Primary screens have comprehensive states. Auth, settings, and loading states on secondary tabs are missing. |
| Accessibility | 8 | Above-average for a UX spec. Gaps: aria-describedby for errors, skip navigation link, skeleton loader screen-reader treatment, focus after toast dismiss. |
| Edge Case Handling | 7 | 12 UX risks with mitigations. Missing: session expiry with unsaved data, last-position-deleted dashboard, decimal input on mobile, slow-network timeout state. |
| Design Scalability | 7 | V1 IA is clean. No multi-portfolio pattern defined (V1.1 risk). No URL structure = no deep-link or back-button strategy. |
| Engineering Readiness | 7 | Interaction specs are implementation-grade. Missing URL routing, API data freshness policy, browser back-button modal behaviour, form Enter key behaviour. |

---

# STRENGTHS

**1. Persona-grounded journey maps.** Each of the three personas has a distinct, realistic journey with emotional state captured at every stage. The "Ahmad checks at 8:30 AM" and "Farah checks on commute" specificity gives the visual designer concrete context for layout and information priority decisions.

**2. Trust-through-transparency pattern.** The yield drill-down tap pattern — where any displayed yield figure reveals income ÷ all-in cost with full tranche and lot decomposition — is the product's strongest UX differentiator. It is well-defined as a reusable interaction pattern and tied directly to the PRD's core positioning claim.

**3. Live fee calculation panel.** Specifying that the fee breakdown (initial amount, brokerage, clearing, stamp duty, all-in cost) animates live as the user types share count and price is exactly the right design decision for trust-building on first use. The formula annotation per fee line ("Maybank: 0.10% of RM41,900") is production-quality interaction design.

**4. Qualifying shares UX treatment.** The spec correctly anticipates that the `qualifying_shares` field (introduced to fix the critical BR-009 data defect) will confuse users. The pre-fill default, plain-English guidance text, and amber "using different from current total" note are the right layered communication approach — the concept is surfaced progressively based on relevance.

**5. Destructive action undo pattern.** The 5-second undo toast after position/lot deletion (modelled on Gmail and Slack) is the right call for a product where users may have 3 years of data in a position. This pattern is not common in portfolio trackers and will be a standout quality signal.

**6. Mobile-first thinking for Farah.** The mobile column reduction (3 of 9 columns visible by default, rest behind row-tap), 44×44px touch targets, bottom tab bar with icon+label, and full-screen modals are all correctly specified. This is a meaningful acknowledgement that Farah is a first-class persona, not an afterthought.

**7. Comprehensive accessibility foundation.** The spec goes well beyond "contrast ratios" — it specifies ARIA roles for live regions, table headers, dialog semantics, stale price indicators, and keyboard trap management in modals. This is rare at the UX spec stage and will save significant remediation effort post-build.

**8. Sell calculator fee transparency.** Specifying that each fee component (brokerage, clearing, stamp duty) is a visible column in the scenario table — not just a "Net Proceeds" black number — is the correct design for David and for the product's accuracy positioning.

---

# CRITICAL ISSUES

---

**Issue ID:** UI-001
**Severity:** High

**Problem:** Screen Requirements are absent for 9 screens: Login Form, Forgot Password Form, Reset Password Form, Welcome/Onboarding Screen, Account Settings — Profile, Account Settings — Subscription, Account Settings — Broker Settings, Account Settings — Export Data, Account Settings — Delete Account.

**Impact:** Visual designers will make independent layout, information hierarchy, and interaction decisions for these screens with no spec alignment. Engineers will implement without a clear definition of what these screens must show, what actions they must support, and under what conditions they are entered/exited. The Account Settings screens in particular contain high-stakes actions (account deletion, subscription cancellation) that require careful UX specification to prevent user error.

**Recommendation:** Add Screen Requirements (Purpose / User Goals / Key Information / Primary Actions / Secondary Actions / Entry Conditions / Exit Conditions) for all 9 screens before any visual design begins. The Login and Registration forms are simple; the settings screens require more thought, particularly the Delete Account screen's two-step confirmation pattern.

---

**Issue ID:** UI-002
**Severity:** High

**Problem:** Five user flows are missing: (1) Edit Position/Lot, (2) Manual Price Override (standalone), (3) Subscription Renewal Failure / Grace Period, (4) Email Verification Resend, (5) Custom Broker Add/Edit.

**Impact:**
- Edit is used daily by every persona — an engineer building the edit flow without a spec will make interaction decisions that may not match the UX intent (particularly the post-edit "dividend records unchanged" notification).
- The subscription renewal failure flow is a retention-critical moment: if a user's card declines and the product silently locks them out, they churn. There is currently no specified behaviour.
- Custom Broker Add/Edit is referenced in the IA and Interaction specs but has no flow definition.

**Recommendation:** Add a flow definition for each of the 5 missing flows. Edit Position/Lot is the most critical; at minimum, it needs to specify the post-edit notification for share count changes.

---

**Issue ID:** UI-003
**Severity:** High

**Problem:** No URL routing structure or routing strategy is defined. The spec defines a tabbed Position Detail screen (Lots / Dividends / Sell Calculator) but does not specify whether tabs are represented as URL routes (e.g., `/positions/[id]/dividends`) or as in-page state. Similarly, no guidance on whether modal flows (Add Position, Add Dividend) use URL parameters.

**Impact:** Without URL routing guidance, engineers may implement tabs as pure in-page state — which means the browser back button dismisses the entire position detail view rather than returning to the previous tab, and the user cannot deep-link or share a specific position's dividend history. This is a UX regression that is much harder to fix post-build.

**Recommendation:** Define the URL structure as part of the IA section. Minimum: specify whether tabs have URLs (recommended: yes, `/positions/[id]/lots`, `/positions/[id]/dividends`, `/positions/[id]/sell`); specify that modal overlay flows do NOT change the URL (the underlying page URL remains, and closing the modal returns to the same page state); specify that browser back-button in a modal closes the modal, not navigates to the previous route.

---

**Issue ID:** UI-004
**Severity:** Medium

**Problem:** Currency input formatting during data entry is unspecified. The BAS stores purchase_price at 4dp and MYR amounts at 2dp. The UX spec does not define: (a) whether price fields show a "RM" prefix during typing, (b) whether the field auto-formats to 2 or 4 decimal places, (c) what happens if the user types "8,380" with a comma (common in Malaysian number formatting) vs. "8.38."

**Impact:** Engineers will make inconsistent format decisions across the Add Position, Add Lot, and Add Dividend forms. A user typing "8,380" (which looks correct to a Malaysian user) may get a validation error rather than an auto-corrected value, causing friction and potential abandonment.

**Recommendation:** Add a currency input spec to Section 7 (Interaction Specifications): (a) show "RM" prefix as a field prefix label, not inside the input; (b) accept both comma-decimal and dot-decimal; normalize to dot-decimal on blur; (c) display 2dp for MYR amounts, 4dp for per-share prices, after blur; (d) during typing: do not force formatting — let the user type naturally.

---

**Issue ID:** UI-005
**Severity:** Medium

**Problem:** Session expiry with unsaved form data is not handled. The spec specifies (EX-010) that session expiry returns a 401 and redirects to login, but it does not address the UX for a user who is mid-way through filling out the Add Position form or the CSV preparation when their session expires.

**Impact:** A user who has typed all their lot details into the Add Position form and hits Submit after session expiry loses all entered data. For a power user like David entering his 20th lot, this is a high-frustration event that could cause churn.

**Recommendation:** Add to the Edge Case / Interaction Spec: before the API call on form submit, check session freshness. If expired: show an inline notification "Your session has expired. [Log in to save this entry]" — if possible, preserve the form field values in sessionStorage so they are restored after re-login. Specify that on re-login, the form re-opens with preserved values. If sessionStorage preservation is out of scope for V1, explicitly document that data loss occurs and the user must re-enter — so this is a known, accepted gap.

---

**Issue ID:** UI-006
**Severity:** Medium

**Problem:** The Paywall screen (shown to trial-expired users) is described in the permission states of the Dashboard and in individual screen permission restricted states, but it is not defined as its own screen with purpose, content, and actions. It is mentioned as "paywall banner" and "paywall modal" interchangeably, without consistency.

**Impact:** The paywall is a conversion-critical moment — it is the screen that directly determines whether a user subscribes or churns. Designing it without a spec (particularly the copy, the plan comparison if applicable, and the friction level of the CTA) is a high-stakes assumption.

**Recommendation:** Add a dedicated Paywall Screen (or Paywall Modal, chosen consistently) to the Screen Inventory and Screen Requirements, with: Purpose (convert trial-expired user to paid subscriber), Key Information (what they lose by not subscribing, what they gain), Primary Action (Subscribe), Secondary Action (View my data read-only), Entry Conditions (account_status = trial_expired, any write action attempted), Exit Conditions (subscribe → full access, dismiss → read-only dashboard).

---

**Issue ID:** UI-007
**Severity:** Medium

**Problem:** The spec does not define UX behaviour when the user deletes their last position. The dashboard should revert to the empty state, but this transition is not specified. Additionally, if the user deletes a position while the Dividend Calendar has entries from that position, the Calendar must update — this side-effect is not addressed.

**Impact:** Engineers may leave orphaned calendar entries visible after position deletion, or the dashboard may remain in a "loaded" state showing zero rows rather than the empty state CTA. Both are confusing UX states.

**Recommendation:** Add to Section 8 (State Definitions) under Dashboard: a "Transition to Empty State" state — triggered when the last active position is deleted. Specify that: (a) the dashboard immediately reverts to the Empty State with the two-CTA layout, (b) the Dividend Calendar removes all entries from the deleted position on the next calendar render.

---

**Issue ID:** UI-008
**Severity:** Low

**Problem:** The spec does not specify a "skip navigation" link — the standard accessibility pattern that allows keyboard and screen reader users to bypass the navigation bar and jump directly to the main content area.

**Impact:** For Ahmad, who uses a desktop browser and may eventually use keyboard shortcuts, navigating through the full top bar on every page load is a friction tax. For screen reader users navigating daily, this is a Level AA WCAG compliance gap.

**Recommendation:** Add to Section 9 (Accessibility): a visually hidden "Skip to main content" link as the first focusable element on every page. Visible only on keyboard focus. Targets the main content `<main>` element.

---

**Issue ID:** UI-009
**Severity:** Low

**Problem:** The skeleton loader (loading state) is a visual pattern that conveys "data is coming" to sighted users. The spec does not define how screen readers are informed that the page is loading. A screen reader will announce the skeleton's HTML content (which may be empty or meaningless) and provide no indication that data is pending.

**Impact:** A screen reader user navigating the dashboard while it loads will hear silence or nonsense placeholder text, then suddenly hear the full position table announced. No audible indication of the loading state.

**Recommendation:** Add to the accessibility spec: during the loading state, apply `aria-busy="true"` to the main content container and include a visually hidden `<span role="status">Loading portfolio data...</span>`. When loading completes, remove `aria-busy` and the status span — the `aria-live="polite"` region will then announce the loaded content naturally.

---

# MISSING SCREENS

| Screen Name | Severity | Reason Required | Suggested Purpose |
|-------------|----------|-----------------|-------------------|
| Login Form — Screen Requirements | High | The login form is the second most-used screen (daily for all personas) but has no Screen Requirements section. | Define: email/password fields, error states (wrong password, locked account), "Remember me" behaviour (if applicable), entry conditions (unauthenticated user on any protected route), exit conditions (authenticated → dashboard). |
| Forgot Password Form — Screen Requirements | High | Flow 7 defines the flow but no screen spec exists. | Define: single email field, submit button, success message treatment, link to login. |
| Reset Password Form — Screen Requirements | High | Flow 7 defines the flow but no screen spec exists. | Define: new password + confirm fields, strength indicator, token-expired and token-used states, success redirect. |
| Welcome / First Session Screen | High | Referenced in Flow 1 step 3 ("Welcome screen offers two paths") but has no screen definition. This is the user's first impression after registration — a critical moment. | Define: welcome headline, two equal-weight CTAs (Add First Position, Import from CSV), dismissal behaviour, relationship to email verification banner. |
| Paywall Screen / Modal | High | Trial-expired users see this but it has no dedicated screen spec. It is the conversion screen — the single most important screen for the business. | Define: headline ("Your trial has ended"), what the user retains (read-only access), subscription CTA, plan options (if multiple), trust signals. |
| Account Settings — Profile Screen | Medium | Navigation IA lists this but no requirements exist. | Define: displayed fields (email, default broker, password change link), edit behaviour, success/error states. |
| Account Settings — Subscription Screen | Medium | Navigation IA lists this but no requirements exist. | Define: current plan display, renewal date, cancel subscription CTA, re-subscribe path for lapsed users. |
| Account Settings — Broker Settings Screen | Medium | Navigation IA lists this but no requirements exist. | Define: list of system brokers (read-only), user's custom brokers (editable), Add Custom Broker CTA, deactivate/edit per broker. |
| Account Settings — Export Data Screen | Medium | Navigation IA lists this; FR-018 is PDPA-critical. | Define: PDPA context copy, Download button, what the ZIP contains, audit log confirmation that export is recorded. |
| Account Settings — Delete Account Screen | Medium | Navigation IA lists this; FR-019 is PDPA-critical. Two-step confirmation is defined in Flow 8 but no screen requirements. | Define: two-step confirmation UX, data download offer, type-to-confirm pattern, post-submit confirmation page. |
| Email Verification Success Screen | Low | Flow 1 specifies the verification link click but no success screen. Users should land somewhere after clicking the link. | Define: "Email verified!" confirmation, CTA to return to dashboard. |
| Subscription Success Screen | Low | When a payment processor redirect returns after successful payment, there should be a dedicated success state. | Define: "You're subscribed!" headline, confirmation of plan and renewal date, CTA to dashboard with full access. |
| CSV Import — Error Report Screen | Medium | The Import Page has a failure state but the error report UX is not fully specified. Is the error table shown inline on the Import page, or as a separate result screen? | Define: error table layout, row/column/message columns, Download Error Report button, path back to Upload step. |

---

# MISSING USER FLOWS

| Flow Name | Severity | Why Missing | What to Specify |
|-----------|----------|-------------|-----------------|
| Edit Position / Lot | High | Edit is a daily action for all personas. Referenced in FR-005 and Screen Requirements but no flow exists. | Entry (Edit button on lot row) → pre-populated form → validation → save → post-edit notification ("2 existing dividend records unchanged" if share count changed) → return to Lots tab. |
| Manual Price Override | Medium | Mentioned as a sub-flow within Flow 4 (Daily Check) but deserves its own flow definition as it is a complete, distinct user action. | Entry (amber ⚠ tap on stale position) → inline price input appears → user enters price → save → position recalculates → stale indicator removed. |
| Subscription Renewal Failure / Grace Period | High | Not specified anywhere. What happens if the user's payment fails on renewal? This is a retention-critical path. | Payment fails → email notification → grace period begins (e.g., 7 days) → app shows "Payment failed" banner → user can update payment method → after grace period: trial_expired status. |
| Email Verification Resend | Medium | The registration flow and EX-007 mention "Resend verification email" but no flow defines the trigger, the feedback, and the rate-limiting behaviour. | User clicks "Resend" on verification banner → system sends email → toast: "Verification email sent" → if sent within 5 minutes of last send: "Please wait before requesting another." |
| Custom Broker Add / Edit | Medium | Referenced in Settings IA and Interaction Specs but no flow exists. | Entry (Broker Settings → Add Custom Broker) → form: name, fee type, rate/minimum or flat fee → validation → save → broker appears in all broker dropdowns. Edit path from same screen. |
| Subscription Management (Cancel → Lapse → Re-subscribe) | Medium | FR-016 and Workflow 7 in the BAS define the system behaviour but the UX flow for these transitions is not specified. | Cancel → confirmation with end date → lapse → read-only dashboard → re-subscribe from paywall → payment → full access restored. |
| Edit Dividend Tranche | Medium | FR-010 defines this but no UX flow exists. Edit dividend has a unique post-edit behaviour (qualifying_shares can be changed, which recalculates total_amount). | Entry (Edit on tranche row) → pre-populated form → changes qualifying_shares: live preview updates total → save → dividend table updates; yield recalculates. |

---

# MISSING STATES

| Screen | Missing State | Why It Matters |
|--------|--------------|----------------|
| Login Form | Loading state (during submit) | Without a loading state, the submit button may appear to do nothing during slow network. Engineers need to know to disable the button and show a spinner. |
| Login Form | Network error state | If the login API call fails with a 500 or timeout, the user needs feedback distinct from "wrong password." |
| Position Detail — Lots Tab | Loading state | If the position has many lots and the API is slow, the tab content area needs a skeleton state. |
| Position Detail — Lots Tab | Error state | If the lots API call fails, the user needs an error message with a retry option, not a blank tab. |
| Position Detail — Dividends Tab | Loading state | Same reasoning as Lots Tab. |
| Position Detail — Dividends Tab | Error state | Same reasoning as Lots Tab. |
| Sell Calculator Tab | Loading state | The sell calculator pre-populates from position data; if that fetch is async, a loading state is needed. |
| Dashboard | "Last position deleted" → Empty State transition | The spec defines empty state and loaded state separately but not the transition between them (triggered by deleting the last position). |
| Dashboard | Session expiry mid-view | If the user has the dashboard open for 30+ days and the session expires, the next interaction should trigger a graceful session-expired notification, not a silent 401. |
| Import Page — Upload in Progress | Progress/feedback state | "Spinner or progress bar" is mentioned but not formally specified as a state. For large CSV files, a percentage progress indicator is meaningful. |
| Account Settings — All screens | All states | None of the settings screens have any state definitions. Profile edit (success/error), subscription cancellation (confirmation), broker deletion (confirmation) all need states. |
| Paywall Screen | When accessed from different entry points | The paywall is reached from multiple triggers (login after trial expiry, clicking a write action). The state should reflect context: "Your trial has ended" vs. "Subscribe to add positions." |
| Password Reset | Loading state (on submit of new password form) | The password reset form submission is an async action. The button needs a loading state. |
| Add Lot Modal | After successful add — with dividend records unchanged message | This is a success state variant, but the specific "X dividend records unchanged" content is conditional. The state specification should clarify the logic: "If position has ≥ 1 existing dividend tranche, show count in toast." |

---

# UX RISKS

## User Adoption Risks

**RISK-A01: Time-to-first-value depends on the Empty State CTAs working.**
If a new user lands on the empty dashboard and the "Add Position" and "Import from CSV" CTAs are visually weak (small, low contrast, unclear), they will not know what to do next. The spec defines these CTAs but does not specify their visual weight hierarchy. Without explicit "this is the hero action" guidance, a designer may de-prioritise them.

**Recommendation:** Explicitly mark the empty-state CTAs as high-emphasis primary buttons in the screen requirement. The spec says "two equal-weight CTAs" — verify this is intentional. For Ahmad, Add Position is primary; for David, Import CSV is primary. Consider hero CTA (Import) + secondary CTA (Add manually).

**RISK-A02: The CSV Import template preparation is an unsupported off-app task.**
The user downloads a template, fills it in Excel or Google Sheets (off-app), and uploads. The spec does not define any in-app support for this step. A user who makes a column-mapping error may fail 2–3 import attempts before succeeding, causing abandonment.

**Recommendation:** Add an in-app "Import Guide" accessible from the Import page — a simple step-by-step explanation of the multi-lot pattern and the optional columns. This does not require a new screen, just a collapsible panel or modal trigger from the Import page.

---

## User Error Risks

**RISK-E01: Incorrect qualifying_shares entered cannot easily be identified after the fact.**
If a user logs a dividend with the wrong qualifying_shares (e.g., 7,000 instead of 5,000), the stored total_amount is wrong. The spec defines editing the tranche but does not specify any mechanism for the user to audit their dividend entries for qualifying_shares accuracy.

**Recommendation:** On the Position Detail — Dividends tab, add a subtle visual signal when any tranche has qualifying_shares ≠ current position total (the spec mentions this). This signal is well-specified. Ensure it persists visibly, not just on hover.

**RISK-E02: Tranche label assignment is not enforced after deletion.**
If a user has 1st and 2nd tranches, deletes the 1st, and then adds a new one — the system will suggest "2nd" as the next label. But the user may intend to replace the deleted "1st." The spec does not define whether tranche labels are user-editable or system-assigned. If system-assigned (always incremental), this creates label gaps.

**Recommendation:** Clarify in the Add Dividend Form spec: tranche label is a user-editable dropdown (1st…8th), not auto-incremented. The system suggests the next unused label, but the user can select any unused label from the dropdown.

---

## Discoverability Risks

**RISK-D01: The Sell Calculator is a tab within Position Detail — many users will never find it.**
The spec acknowledges this (UX Risk 5) and recommends a "Sell Calculator →" item in the per-row ••• menu on the dashboard. This mitigation should be elevated from "risk recommendation" to a required spec item — it is the difference between the sell calculator being a discovered feature and a hidden one.

**Recommendation:** Add "Sell Calculator →" as a named item in the ••• row action menu in the Dashboard Screen Requirements. This is a spec change, not a visual design decision.

**RISK-D02: The PDPA Data Export is deeply nested (Account Settings → Export Data).**
For a user who needs their data urgently, or who is offboarding, this path requires 2–3 navigation steps. The spec doesn't address whether this action should also be surfaced in the Delete Account confirmation flow (which it does — Flow 8 Step 1 offers the export download before confirmation). This is correct.

**Recommendation:** Verify in the Delete Account screen requirements that the data export offer in step 1 is prominently designed — it is the last chance for the user to save their data and should not be a small "Skip" link.

---

## Accessibility Risks

**RISK-AC01: The amber stale price indicator may fail WCAG 3:1 for UI components.**
Specified in the spec (UX Risk 10) but not fully resolved. The spec says "use amber icon + 'Stale' text label" — this is the correct direction but the exact colour token is not defined. If the designer uses a standard amber (#FFA500) on white (#FFFFFF), it passes 3:1. If they use a lighter amber (#FFD700), it fails.

**Recommendation:** Specify in Section 9 that the stale indicator must use a minimum contrast amber — recommend at least #B45309 (warm amber) for the text label on white backgrounds, or test the chosen token explicitly before visual design sign-off.

**RISK-AC02: Focus order on the Position Detail tabs may be non-intuitive.**
When navigating by keyboard, the tab bar (Lots / Dividends / Sell Calculator) should receive focus before the table content within the selected tab. If the tab strip is rendered after the content in DOM order, keyboard users will navigate through the entire table before reaching the tab strip.

**Recommendation:** Add to Section 9: Position Detail tab strip must appear before the tab panel content in both visual and DOM order. Use `role="tablist"`, `role="tab"`, and `role="tabpanel"` with `aria-selected` and `aria-controls` per ARIA Authoring Practices.

---

## Scalability Risks

**RISK-S01: The 4-tab navigation has no room for V1.1 features.**
The PRD's V1.1 roadmap mentions alerts, historical yield trend charts, and potentially a notification centre. The current navigation (Dashboard, Calendar, Import, Account) is full. Adding a 5th top-level tab or a notification bell creates an unspecified design problem.

**Recommendation:** Note in the IA section: bottom tab navigation is designed for V1 with exactly 4 tabs. V1.1 scope expansion should be evaluated against a navigation restructure before implementation begins (e.g., merging Import into Account Settings to free a slot for Alerts).

**RISK-S02: No multi-portfolio pattern in the IA.**
The PRD describes "one portfolio per account at V1" but the 3-Year Vision includes SGX expansion. If the IA does not accommodate a portfolio switcher as a design pattern from the start, adding multi-portfolio in Year 2 requires a navigation restructure.

**Recommendation:** Add a forward-looking note in the IA: the portfolio is currently implicit (the entire app IS the portfolio). When multi-portfolio is introduced, a portfolio selector will need to be added above or within the primary navigation. The current IA can accommodate this by adding a portfolio switcher in the header without changing the 4-tab structure.

---

# RECOMMENDED ENHANCEMENTS

---

## 1. Must Fix Before Visual Design

| # | Enhancement | Effort | Priority |
|---|-------------|--------|----------|
| R-001 | Add Screen Requirements for Login Form, Forgot Password, Reset Password | Low (simple forms) | Must Fix |
| R-002 | Add Screen Requirements for Welcome / First Session Screen | Low | Must Fix |
| R-003 | Add Screen Requirements for Paywall Screen (dedicated, not just a state) | Medium | Must Fix |
| R-004 | Add Screen Requirements for all 5 Account Settings screens | Medium | Must Fix |
| R-005 | Define URL routing structure (tab URLs, modal URL behaviour, browser back-button strategy) | Low (design decision only) | Must Fix |
| R-006 | Add Edit Position / Lot user flow | Low | Must Fix |
| R-007 | Add Edit Dividend Tranche user flow | Low | Must Fix |
| R-008 | Specify currency input formatting behaviour (RM prefix, comma vs. dot, decimal places on blur) | Low | Must Fix |
| R-009 | Add "Sell Calculator →" as a named ••• menu item in Dashboard Screen Requirements | Low | Must Fix |
| R-010 | Add Loading and Error states for Position Detail — Lots Tab and Dividends Tab | Low | Must Fix |

---

## 2. Should Fix Before Engineering

| # | Enhancement | Effort | Priority |
|---|-------------|--------|----------|
| R-011 | Add Manual Price Override standalone flow | Low | Should Fix |
| R-012 | Add Subscription Renewal Failure / Grace Period flow | Medium | Should Fix |
| R-013 | Add Email Verification Resend flow | Low | Should Fix |
| R-014 | Add Custom Broker Add/Edit flow | Low | Should Fix |
| R-015 | Specify session expiry with unsaved form data behaviour (sessionStorage preservation or explicit data-loss acceptance) | Medium | Should Fix |
| R-016 | Specify Dashboard → Empty State transition when last position is deleted | Low | Should Fix |
| R-017 | Add `aria-describedby` linkage for form field errors to accessibility spec | Low | Should Fix |
| R-018 | Add Skip Navigation link to accessibility spec | Low | Should Fix |
| R-019 | Add `aria-busy` + visually-hidden loading announcement for skeleton loader | Low | Should Fix |
| R-020 | Add Login Form loading state and network error state | Low | Should Fix |
| R-021 | Clarify tranche label assignment: user-editable dropdown, not auto-incremented | Low | Should Fix |
| R-022 | Define component vocabulary: Chip, Fee Breakdown Panel, Drill-Down Overlay, Form Layout | Medium | Should Fix |
| R-023 | Specify whether the sell calculator table is paginated, virtualized, or long-scroll for 40+ rows | Low | Should Fix |
| R-024 | Specify form submit on Enter key vs. button-click-only behaviour | Low | Should Fix |
| R-025 | Specify `inputmode="decimal"` on all price/amount fields (triggers numeric keyboard on mobile) | Low | Should Fix |

---

## 3. Nice to Have Improvements

| # | Enhancement | Effort |
|---|-------------|--------|
| R-026 | Add V1.1 navigation scalability note (5th tab strategy) | Low |
| R-027 | Specify CSV Import — in-app Import Guide (collapsible panel, not a new screen) | Low |
| R-028 | Add ARIA tab role spec for Position Detail tab strip (tablist/tab/tabpanel/aria-selected) | Low |
| R-029 | Add forward-looking multi-portfolio IA note | Low |
| R-030 | Specify large number display format (RM1,234,567.89 vs. RM1.2M threshold) | Low |
| R-031 | Add keyboard shortcut spec for "Add Position" (e.g., Cmd/Ctrl+N) — for power users like David | Medium |
| R-032 | Add the slow-network timeout state (load > 5s): retry button + "Taking longer than expected" message | Low |

---

# CLAUDE DESIGN READINESS

## User Flow Generation

**Ready** — with conditions.

The 8 specified flows are complete enough for flow diagram generation. The 5 missing flows (Edit, Manual Override, Subscription Failure, Email Resend, Custom Broker) should be added before a complete flow diagram set is generated. Generating without them produces an incomplete flow map that misleads engineers about the product's full interaction surface.

## Wireframe Generation

**Ready with Conditions** — for core product screens only.

The Dashboard, Position Detail (all 3 tabs), Add Position/Add Lot, Add Dividend, Dividend Calendar, Import Page, and Registration Form have sufficient screen requirements for wireframe generation. The auth screens (Login, Forgot Password, Reset Password), all Account Settings screens, the Welcome screen, and the Paywall screen do NOT have requirements and cannot be wireframed without assumptions.

**Recommended approach:** Generate wireframes for the 9 fully-specified screens now; generate auth and settings wireframes after R-001 through R-004 are resolved.

## Screen Generation

**Not Ready** — for the full screen set.

Screen generation requires complete screen requirements, state definitions, and interaction specs for each screen. Currently, 9 of ~22 screens have full requirements. Screen generation attempted on the remaining 13 screens would produce outputs misaligned with the product's design intent. Wait for R-001 through R-010 to be resolved.

## Responsive Design Generation

**Ready** — for specified breakpoints.

The spec defines mobile-first behaviour for the dashboard (3-column condensed view), forms (full-screen modals), navigation (bottom tab bar), and sell calculator (horizontally scrollable table with pinned first column). These are sufficient for responsive design generation at 375px and 1440px. The gap: the 768px tablet breakpoint is not specified at all. A full responsive design generation will need a tablet layout decision (particularly for the fee breakdown panel and position table).

---

# FINAL RECOMMENDATION

**Decision: APPROVE WITH CONDITIONS**

**Reasoning:**

BursaTrack's UX Specification v1.0 is a well-structured, thoughtfully designed document that demonstrates a strong understanding of the product's positioning, its three personas, and the unique UX challenges of a calculation-heavy fintech product. The core product flows — portfolio management, dividend logging, sell calculator, CSV import — are ready for wireframing today.

The specification is held back from a full APPROVE by two systematic gaps that are real risks for the visual design and engineering phases:

First, nearly half the application's screens (all auth, onboarding, and settings screens) lack Screen Requirements. The visual designer will encounter these screens on day two of wireframing. Without requirements, they will either block waiting for spec or make assumptions that require rework. Given the high stakes of some of these screens (the Paywall, the Delete Account confirmation, the Subscription screen), assumption-driven design is not acceptable.

Second, five user flows — including the most-used daily action (Edit Lot) — are absent. Edit interactions in particular have product-critical post-save behaviour (the "dividend records unchanged" notification) that will be lost if engineers build the edit flow without a spec.

The conditions are achievable. Items R-001 through R-010 from the "Must Fix Before Visual Design" list represent roughly 2–3 hours of specification work. Resolving them would push this document to a clean 9/10 and a full APPROVE. The specification's foundation is excellent — the completion work is additive, not corrective.

**Revised readiness projection:** After resolving R-001 through R-010, this specification would score **9 / 10** and receive a full APPROVE for visual design handoff.
