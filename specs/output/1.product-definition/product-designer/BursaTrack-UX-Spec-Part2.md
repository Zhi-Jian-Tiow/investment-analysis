# BursaTrack — UX Design Specification
## Part 2 of 2: Sections 7–11

> **Version:** 1.0
> **Date:** 2026-06-21
> **Continuation of Part 1 (Sections 1–6)**

---

# 7. INTERACTION SPECIFICATIONS

---

## Forms

### Add Position / Add Lot Form

**Trigger:** User clicks "Add Position" (dashboard) or "Add Lot" (position detail)

**System Response:** Modal opens with focus on the Stock Code/Name field

**User Feedback:**
- Stock code autocomplete: as user types 2+ characters, a dropdown shows matching stocks (name + code). Selecting a result populates both name and code fields.
- Fee calculation panel: updates live as shares and price are entered. Each fee line animates from blank → value. The All-In Cost line uses a slightly larger, bold font.
- Broker change: when the broker dropdown changes, brokerage fee and All-In Cost recalculate instantly. The brokerage line updates to show the new broker's formula.

**Success Behaviour:**
- Modal closes
- New position row slides into the dashboard table (animated insert)
- Toast: "CIMB position added. All-in cost: RM41,996.47." (3-second duration)
- For Add Lot: toast also reads "2 existing dividend records unchanged."

**Failure Behaviour:**
- Inline field-level errors appear below the relevant field
- The Submit button remains clickable but submission is blocked until all errors are cleared
- Errors are shown on blur (when user leaves a field) and on submit attempt
- No modal dismissal on validation failure

---

### Add / Edit Dividend Form

**Trigger:** User clicks "Add Dividend Tranche" (dividends tab)

**System Response:** Modal opens with focus on the Dividend Per Share field

**User Feedback:**
- Qualifying shares field is pre-populated with current position total — shown with a grey helper text: "Pre-filled with your current total (5,000 shares)."
- Live calculation preview updates immediately:
  - Typing RM0.20 in per share + qualifying shares = 5,000 → Total = RM1,000.00
  - Changing qualifying shares to 3,000 → Total = RM600.00
  - The preview label reads: "Total received this tranche: RM X,XXX.XX (= RM0.20 × 5,000 qualifying shares)"
- Ex-dividend date is labelled "Optional — add to track in Dividend Calendar"

**Success Behaviour:**
- Modal closes
- Dividend tranche row appears at the top of the dividend table (most recent first)
- Yield percentage in the position header animates to the new value
- "Total income YTD" in the position header updates
- Toast: "Dividend logged — RM1,000.00 (1st tranche, CIMB)"

**Failure Behaviour:**
- Same as Add Position: inline errors, no dismissal on error

---

### Edit Lot Form

**Trigger:** User clicks "Edit" on a lot row

**System Response:** Edit modal pre-populated with existing values

**User Feedback:**
- Changes cause live fee recalculation (same as Add form)
- After saving: Dashboard position row updates; a note appears on the dividends tab if share count changed: "Note: Share count updated. Existing dividend records were not changed."

**Success Behaviour:**
- Modal closes; lot row updates in place
- Toast: "Lot updated. Previous values saved to audit log."

**Failure Behaviour:**
- Inline field errors; no dismissal

---

### Password Change / Reset Forms

**Trigger:** Settings → Change Password; or Reset Password link in email

**User Feedback:**
- Password field shows a strength indicator (weak/medium/strong) based on length and character variety
- Confirm password shows a green tick when the two fields match

**Success Behaviour (reset flow):**
- Redirect to login page with: "Password updated successfully. Please log in."
- All prior sessions are invalidated server-side (user will need to log in on other devices)

**Failure Behaviour:**
- Mismatched passwords: "Passwords do not match" shown inline before submit
- Weak password: "Password must be at least 8 characters, with at least one uppercase letter and one digit"

---

## Buttons

**Primary buttons** (Add Position, Save, Import, Subscribe): full-colour fill, high contrast, full-width on mobile.

**Destructive buttons** (Delete Position, Delete Account, Cancel Subscription): outlined red or muted secondary style until clicked; confirmation dialog required before any destructive action executes.

**State transitions:**
- Default → Hover: subtle elevation/colour shift
- Hover → Loading (after click): button text replaced with a spinner + "Saving…" text; button is disabled during the async operation
- Loading → Success: button re-enables; toast shown
- Loading → Error: button re-enables; inline error shown

**Disabled state:** buttons that require an active subscription are shown in a disabled state with a tooltip: "Subscribe to enable this feature."

---

## Search / Autocomplete (Stock Code Field)

**Trigger:** User begins typing in the Stock Code / Name field

**System Response:**
- After 2 characters: dropdown appears showing up to 8 matching Bursa-listed stocks
- Matching characters are bolded in the dropdown results
- Results show: stock name + stock code (e.g., "CIMB Group Holdings Bhd — 1023")

**User Feedback:**
- Keyboard navigation: arrow keys scroll through dropdown; Enter selects
- Mouse: click selects
- After selection: both name and code fields populate; focus moves to Shares field

**Failure Behaviour:**
- No matches found: "No Bursa-listed stock found for '[query]'. Check the stock code or name."
- Feed unavailable: field accepts free text entry; server-side validation applies on submit

---

## Sorting (Dashboard Table)

**Trigger:** User clicks a column header on the dashboard position table

**System Response:**
- Table re-sorts by that column (ascending first click; descending second click)
- Sorted column shows a sort direction arrow
- Sort preference is saved to the user's session (persists on next login)

**Default sort:** Dividend Yield, descending (highest yield first)

**User Feedback:**
- Table sort animates smoothly (rows slide to new positions)
- Current sort column header is visually highlighted

---

## Price Stale Indicator

**Trigger:** One or more PriceSnapshot records have source = "stale"

**System Response:**
- Dashboard header: amber dot next to "Last Refreshed" + amber banner: "Price data unavailable for [N] stocks — showing prices as of [last timestamp]. Update prices manually below."
- Affected position rows: amber ⚠ icon next to the price cell

**User Feedback (manual override):**
- Clicking ⚠ on a position row expands an inline price input field: "Enter current price: RM [___]"
- Typing a price → All-In calculations update live in the row
- Pressing Enter or clicking Save → PriceSnapshot created with source="manual"; stale indicator removed for that position

**Recovery:**
- On next successful automated refresh, stale/manual indicators disappear automatically; banner dismissed

---

## Tables (Position Table, Dividend Table, Scenario Table)

### Position Table
- Default: sortable columns; row click navigates to Position Detail
- Mobile: condensed to 3 columns (Stock, Yield, Income); remaining data via row tap
- Long position names truncated with ellipsis; full name on hover tooltip

### Dividend Tranche Table
- Sorted by payment_date descending (most recent first)
- If qualifying_shares ≠ current position total: amber note in that row: "Held [N] qualifying shares (current total: [M])"
- Edit/Delete actions via ••• per-row menu on desktop; swipe-left on mobile

### Sell Scenario Table
- Break-even row highlighted in amber with a label: "Break-even"
- Rows above break-even (loss) shown in a muted/light style
- Rows below break-even with significant profit shown with a subtle green tint
- All amounts shown with 2 decimal places (MYR)
- Custom price row, if entered, shown at the top of the table

---

## Navigation

**Primary navigation** (desktop): horizontal top bar with four items — Dashboard, Calendar, Import, Account (avatar/initials).

**Primary navigation** (mobile): bottom tab bar with the same four items using icons + labels.

**Back navigation:** "← Back to [Screen]" text link at the top-left of all secondary screens (position detail, settings sub-pages, import result).

**Drill-down from yield figure:** Any displayed yield percentage is tappable → opens a non-modal overlay panel showing:
```
Yield: 5.57%
= Total Dividend Income ÷ Total All-In Cost
= RM 2,337.50 ÷ RM 41,996.47

Income breakdown:
  1st tranche:   RM 1,000.00  (5,000 shares × RM0.20)
  2nd tranche:   RM  987.50   (5,000 shares × RM0.1975)
  3rd tranche:   RM  350.00   (5,000 shares × RM0.07)

Cost breakdown:
  Lot 1 (5,000 shares):  RM 41,996.47
    Initial:     RM 41,900.00
    Brokerage:   RM     41.90
    Clearing:    RM     12.57
    Stamp Duty:  RM     42.00
```
This is the "Trust Through Transparency" principle in action. Every number should be explainable in one tap.

---

## Notifications / Toasts

**Toast system:** non-blocking, bottom-right on desktop, bottom-centre on mobile. 3-second auto-dismiss for success; persistent (manual dismiss) for errors and warnings.

| Type | Colour | Usage |
|------|--------|-------|
| Success | Green | Position added, lot added, dividend saved, import complete, password updated |
| Warning | Amber | Price stale, trial ending soon (last 3 days) |
| Error | Red | Save failed, import failed row-count, network error |
| Info | Blue | Email verification reminder |

**Non-dismissable banners** (embedded in page, not floating):
- Price data stale → amber banner in dashboard header
- Trial expired → paywall banner in dashboard header
- T+2 settlement disclosure → always-visible in sell calculator

---

# 8. STATE DEFINITIONS

---

## Dashboard Screen States

### Default State
- Portfolio header shows: Total All-In Cost · Total YTD Income · Blended Yield · Last Refreshed (green dot, today's time)
- Position table shows all active positions sorted by yield descending
- All prices current; no warning indicators
- "Add Position" CTA visible

### Empty State
- No positions have been added
- Hero empty state: "Welcome to BursaTrack" with two equal-weight CTAs: [Add your first position] and [Import from CSV]
- Portfolio summary header shows RM0.00 for all values (or hidden until first position)

### Loading State
- Dashboard skeleton loader: header row placeholder + 3–5 placeholder position rows with shimmer animation
- Appears for the first render or after navigating back from a different screen
- Skeleton resolves in < 3 seconds (PRD NFR)

### Success State (after add/edit)
- New position row slides in; or updated row flashes briefly to indicate the change
- Toast confirmation visible bottom-right

### Error State — Partial Stale Prices
- Amber dot on "Last Refreshed" chip
- Amber banner at top: "Price data unavailable for [N] stocks. Showing last known prices."
- Affected rows: amber ⚠ + inline price input option

### Error State — All Prices Stale
- Full-width amber banner: "Price data unavailable — all positions show last known prices as of [date/time]. Update prices manually."
- No green indicators; all positions show amber ⚠

### Permission Restricted State (Trial Expired)
- Dashboard visible in read-only mode
- Full-width blue banner: "Your free trial has ended. Subscribe to continue adding positions and logging dividends."
- All write actions (Add Position, Add Lot, Add Dividend, Edit, Delete, Import) show the paywall modal instead of executing
- Sell Calculator and Calendar remain viewable (read-only)

---

## Add Position / Add Lot Modal States

### Default State
- Form rendered with all fields empty except Broker (pre-filled with account default)
- Fee calculation panel shows placeholder dashes: "—"

### Live Calculation State
- As shares and price are entered, the fee panel populates in real time
- All-In Cost line renders in bold once both shares and price have valid values

### Loading State (on submit)
- Submit button shows spinner + "Saving…"
- All form fields disabled
- Lasts < 1 second for typical network conditions

### Success State
- Modal closes; position row animates onto dashboard; toast shown

### Error State
- Inline errors appear under affected fields
- Submit button re-enables after all errors are resolved
- Modal remains open

---

## Add Dividend Modal States

### Default State
- Tranche label auto-suggested (e.g., "2nd")
- Qualifying shares pre-filled with current position total
- Total preview shows "—" until per share amount is entered

### Live Preview State
- As per_share_amount and qualifying_shares are typed: "Total received this tranche: RM X,XXX.XX" updates in real time
- If qualifying_shares is edited away from the default: amber note appears: "Using [N] qualifying shares (not your current total of [M])"

### Success State
- Modal closes; tranche row appears at top of dividend table; yield updates

### Error State
- Inline errors; modal stays open

---

## Dividend Calendar States

### Default State
- "Upcoming (next 90 days)" section followed by "Past (last 30 days)" section
- "Due in next 7 days" shown as highlighted cards at the top

### Empty State
- No ex-dates entered by the user
- "Add ex-dividend dates when logging dividends to see your payment schedule here."
- Link: "View my positions →"

### Loading State
- Skeleton cards for the upcoming section

---

## Sell Calculator States

### Default State
- Form pre-populated with position data
- Scenario table auto-generated from current price

### Stale Price Warning State
- Warning above table: "Current price is from [yesterday, HH:MM]. For accurate scenarios, update the price manually on the dashboard first."
- Table still shows (using stale price) — does not block use

### No Price Available State
- "No price data available for this position. Add a price manually on the dashboard to use the sell calculator."
- Table is not rendered

---

## Import Page States

### Default State
- Two-step guide with Download Template and Upload CSV

### Upload In Progress State
- File upload progress bar or spinner
- "Validating your data…"

### Validation Error State
- Error table rendered
- "Import failed: [N] rows have errors. No records were imported."
- [Download Error Report] button

### Success State
- "Import complete — N positions and M dividend records imported."
- [View Portfolio →] CTA (primary); brief summary of what was created

---

# 9. ACCESSIBILITY REQUIREMENTS

---

## Keyboard Navigation

All interactive elements must be reachable and operable by keyboard alone:

- **Tab order:** follows reading order (left-to-right, top-to-bottom). Modal dialogs trap focus within the modal until closed.
- **Navigation:** top navigation tabs are reachable by Tab; activated by Enter or Space.
- **Position table rows:** each row is focusable via Tab; Enter navigates to position detail; arrow keys navigate rows.
- **Dropdown menus (broker, tranche label):** keyboard-navigable; arrow keys move through options; Enter selects.
- **Stock code autocomplete:** Down arrow opens dropdown after typing; arrow keys navigate suggestions; Enter selects; Escape dismisses.
- **Modal dialogs:** opened via Enter on trigger; Escape closes the modal and returns focus to the trigger element.
- **Sell calculator:** all inputs and the custom price field are keyboard-accessible; Tab navigates scenario table rows.
- **Destructive confirmation dialogs:** default focus on "Cancel" (not "Confirm") to prevent accidental data loss by pressing Enter rapidly.

---

## Focus States

- Every focusable element must have a visible focus indicator: a 2px offset outline in the product's primary colour (not relying on default browser outlines, which are often invisible).
- Focus ring must be visible on all backgrounds — dark and light.
- Focus must never be trapped in a non-modal context (e.g., a tooltip or popover should not hold focus captive).

---

## Screen Reader Considerations

- **Page title:** `<title>` tag must describe the current screen (e.g., "Dashboard — BursaTrack", "CIMB Position Detail — BursaTrack").
- **Tables:** all data tables use `<thead>`, `<tbody>`, `<th scope="col">` and `<th scope="row">` correctly. Screen readers must be able to announce "Yield, 5.57%, CIMB row."
- **Live fee calculation panel:** uses `aria-live="polite"` so that screen readers announce the All-In Cost when it updates, without interrupting user typing.
- **Toast notifications:** use `role="status"` and `aria-live="polite"` for success toasts; `role="alert"` and `aria-live="assertive"` for error toasts.
- **Icons:** all icons used alone (without visible label) have an `aria-label` or are wrapped in a `<button>` with `aria-label`.
- **Stale price indicator (⚠):** `aria-label="Stale price for CIMB. Click to enter price manually."` on the icon button.
- **Yield drill-down:** the tappable yield figure has `role="button"` and `aria-label="View yield breakdown for CIMB"`.
- **Confirmation dialogs:** `role="dialog"`, `aria-modal="true"`, `aria-labelledby` pointing to the dialog heading.

---

## Contrast Requirements

- **Normal text (< 18px):** minimum 4.5:1 contrast ratio against background (WCAG AA)
- **Large text (≥ 18px or ≥ 14px bold):** minimum 3:1 contrast ratio
- **UI components (buttons, inputs, focus rings):** minimum 3:1 against adjacent colour
- **Stale price indicator (amber ⚠):** amber on white background — designer must verify this passes 3:1 against the table row background. If it fails, use a darker amber or add a text label alongside the icon.
- **Green/red for P&L:** do not rely on colour alone — the P&L column must also use a "+" or "−" prefix, and optionally an arrow icon, so that colour-blind users are not disadvantaged.
- **Error messages:** red error text must be accompanied by an error icon; do not rely on red colour alone.

---

## Mobile Accessibility Considerations

- **Touch targets:** all interactive elements have a minimum 44×44px touch target (Apple HIG and Google Material guidance). Small icons in table rows must use a larger invisible tap area.
- **Viewport meta tag:** `<meta name="viewport" content="width=device-width, initial-scale=1">` required. No `user-scalable=no` — users must be able to zoom.
- **Font size:** minimum 16px for body text on mobile to prevent browser zoom override.
- **Bottom tab bar:** tab items have labels in addition to icons (never icon-only for primary navigation).
- **Modals on mobile:** full-screen or near-full-screen on small viewports; scrollable if content exceeds screen height; no fixed-height modals that clip content on small phones.
- **Sell calculator table on mobile:** horizontally scrollable with pinned Sell Price column; column names visible on scroll.

---

# 10. UX RISK REVIEW

---

## Confusing Workflows

### Risk 1: Qualifying Shares — User Does Not Understand the Field

**Description:** The `qualifying_shares` field on the Add Dividend form is not a concept users encounter in other tools. A new user may be confused about why it exists and what to do if their share count has changed since the ex-date.

**Impact:** User enters the wrong qualifying shares (too many → overstated income; too few → understated income). More likely: user is confused and abandons the dividend logging flow.

**Recommendation:**
- Label the field "Shares qualifying for this dividend (pre-filled with your current total)"
- Add a single, plain-English help tooltip: "If you bought more shares after the ex-dividend date for this payment, update this to the number you held before that date."
- Default is always current total — the correct value for the vast majority of cases (user bought before ex-date and hasn't changed their holding)
- For Farah, the default will almost always be correct; the field only needs user attention if they actively added shares after an ex-date they haven't yet logged

### Risk 2: Multi-Lot CSV Import — Multiple Rows per Stock

**Description:** The CSV template requires multiple rows for a stock with multiple lots (Lot 1, Lot 2, Lot 3 on separate rows with the same stock_code). This is not obvious to users who think of a "position" as one row.

**Impact:** Users who don't read the guide create only one lot per stock, losing cost basis accuracy.

**Recommendation:**
- Template includes 2 example rows for the same stock (CIMB Lot 1 + CIMB Lot 2) to demonstrate the pattern
- Guide text above the upload area: "Each purchase on a different date should be a separate row, even for the same stock."
- Consider a column order guide graphic (in-app, not a PDF) showing the multi-lot pattern

### Risk 3: Sell Calculator — Partial Sale Cost Basis Method Not Explained

**Description:** When a user sells fewer shares than their total position, the calculator uses proportional (weighted average) cost. Users who expect FIFO may be confused why the numbers are different.

**Impact:** David or Ahmad may dispute the calculator's result, reducing trust.

**Recommendation:**
- Below "Shares to Sell" input, add grey label text: "Cost basis is calculated as a proportional share of your total all-in cost (weighted average). FIFO tracking coming in a future update."
- This is honest, sets expectations, and signals forward momentum

---

## Cognitive Overload Risks

### Risk 4: Dashboard Density for New Users

**Description:** The position table has 9 columns plus an actions menu. For a new user seeing their first positions, this can feel overwhelming — particularly on desktop where all columns are visible.

**Impact:** Farah may feel the product is "too complicated" and return to her Google Sheet.

**Recommendation:**
- On first login with 1–3 positions: show a reduced column set by default (Stock, Shares, Yield, Income, Current Price). The remaining columns accessible via a "More columns" toggle.
- After 14 days or 5+ positions: switch to full column view automatically (user has learned the product)
- Progressive disclosure protects Farah without compromising David

### Risk 5: Position Detail Tabs — Users May Not Discover Sell Calculator

**Description:** The Sell Calculator is on a tab within Position Detail. Users who don't navigate to position detail (e.g., Farah, who uses mobile dashboard view) may not discover it.

**Impact:** Sell Calculator is a V1 Must Have feature; low discoverability reduces its value.

**Recommendation:**
- Add "Sell Calculator →" as a secondary action on each position row's ••• menu, directly visible on the dashboard without requiring position detail navigation
- This is not new scope — it's a navigation path, not a feature

---

## User Error Risks

### Risk 6: Accidental Position or Tranche Deletion

**Description:** Soft-delete is used, but users can delete a position with 20+ lots and dividend tranches through a single confirmation dialog.

**Impact:** Data loss (feels like loss even though soft-deleted) causes major trust damage. David especially would be furious.

**Recommendation:**
- Confirmation dialog shows the scope of what will be deleted: "This will delete CIMB and all 3 lots and 8 dividend records."
- Add a 5-second undo window after deletion (a "Undo" toast: "CIMB deleted. [Undo — 5s]") — if clicked, the soft-delete is reversed immediately
- This is a well-established pattern (Gmail, Slack) and dramatically reduces irreversible error risk

### Risk 7: Edit Lot Share Count After Dividends Logged — User Confusion

**Description:** If a user edits a lot's share count, the dividend totals do NOT change (by design, per BR-027). The user may be confused: "I changed my shares but my income didn't update."

**Impact:** User may think the system is broken; or they may manually re-enter their dividends to "fix" the income, creating duplicate records.

**Recommendation:**
- After any lot edit that changes share count, show a post-save notification on the Dividends tab: "Your share count was updated. Existing dividend records were not changed — they reflect the shares that qualified at the time each dividend was paid. If you need to correct a dividend amount, edit that tranche directly."
- Link "edit that tranche" to the specific tranche in question if possible

---

## Data Loss Risks

### Risk 8: CSV Import Failure After Long Data Preparation

**Description:** User spends 30 minutes preparing a 20+ position CSV, uploads it, gets a validation error, and must correct and re-upload. The entire import is rejected (atomic import by design).

**Impact:** High-effort path feels punishing on failure; could cause abandonment before onboarding completion.

**Recommendation:**
- The error report must be specific, actionable, and downloadable — users should be able to open the report alongside their CSV and fix in parallel
- Error messages reference the exact column name and example correct value, not just "invalid data"
- Consider a "preview mode" (V1.1): show what would be imported before committing — reduces the surprise of failure. Flag for V1.1 backlog.

### Risk 9: Password Reset Email Delivery Failure

**Description:** If the reset email fails to deliver (EX-011), the user sees the same confirmation message as a success. They may wait 30 minutes for an email that never arrives.

**Impact:** User locked out; goes to support or abandons the product.

**Recommendation:**
- Add a "Didn't receive the email? Resend" link that appears on the confirmation screen 60 seconds after submit
- This provides self-service recovery without revealing account existence (the resend link is shown to everyone who submits the form)

---

## Accessibility Risks

### Risk 10: Amber Colour for Stale Price Warning

**Description:** The amber ⚠ stale indicator relies on colour contrast to communicate urgency. Amber on white may fail WCAG 3:1 for UI components.

**Recommendation:**
- Use amber icon + "Stale" text label alongside the icon in the price cell (not icon-only)
- Alternatively: a darker amber shade with explicit contrast-ratio testing in the design phase

### Risk 11: Green/Red P&L Colour-Only Indication

**Description:** Unrealised P&L uses colour (green = positive, red = negative) to communicate direction. ~8% of males have red-green colour blindness.

**Recommendation:**
- Always prefix P&L values with "+" or "−" (mandatory)
- Optionally: add ▲ and ▼ arrows alongside colour for dual-coding
- Do not remove colour — it is useful for the majority; just do not rely on it exclusively

### Risk 12: Mobile Modal Overflow on Small Screens

**Description:** The Add Position modal with the live fee calculation panel may exceed the viewport height on a 375px iPhone SE screen, clipping the All-In Cost line.

**Recommendation:**
- Modal must be scrollable on mobile; the fee panel should scroll with the form rather than being fixed
- The most critical output (All-In Cost) should be a sticky footer within the modal so it remains visible during scroll
- Test on 375×667px (iPhone SE) before design sign-off

---

# 11. DESIGNER READINESS REVIEW

---

## Missing UX Information

The following items are deferred to the designer's first round of questions or require stakeholder input before visual design can be finalised:

1. **Brand identity not yet defined.** Colour palette, typography, logo, and tone-of-voice guide are not part of this spec. The designer will need these before producing any screens. Recommendation: define brand before first wireframe review — even a minimal brand guide (1 primary colour, 1 typeface, logo mark) is sufficient to begin.

2. **Email templates not specified.** Verification email, password reset email, deletion confirmation email, and trial-expiry reminder email require design treatment. These are out of scope for this UX spec but are required before engineering delivers authentication and subscription features.

3. **Subscription plan pricing page not specced.** The subscription flow (FR-016) directs users to a payment processor but the pricing selection screen before that redirect has not been designed. The plans, pricing tiers, and comparison language are pending business decisions. The designer will need plan names and price points before this screen can be wireframed.

4. **Error illustrations / empty-state artwork.** The spec describes empty-state copy; the visual treatment (illustration, icon, or text-only) is a design decision. Recommendation: simple iconographic treatment — no full-page illustrations at V1 (reduces design and illustration scope).

5. **Mobile breakpoints below 375px.** The spec targets 375px as the minimum viewport. If the product team decides to target 320px (very old devices), several layouts (fee breakdown panel, sell calculator table, position table) will need additional responsive logic.

6. **Rakuten Trade V1 flat-fee disclosure treatment.** The spec states Rakuten Trade is listed as flat RM7 (not tiered) with a disclosure. The exact copy and visual treatment of that disclosure in the broker dropdown has not been designed. Recommendation: a small info icon ⓘ next to "Rakuten Trade (RM7 flat, tier not applied)" with a tooltip explaining the simplification.

---

## Open Questions

| # | Question | Impact on Design | Recommended Owner |
|---|----------|-----------------|-------------------|
| OQ-D01 | Is the subscription pricing page a simple one-plan page or a multi-tier comparison table? | Single plan = simple card; multi-tier = comparison layout | Product Owner |
| OQ-D02 | Should the Dividend Calendar be a true calendar grid view (with weeks/months) or a chronological list view? | Calendar grid is more visual but harder to build on mobile; list is simpler and sufficient for V1 | Product Owner |
| OQ-D03 | Should position history (historical yield trend) be visible in V1 Position Detail, or is that V1.1? | If V1: needs a chart component; if V1.1: position detail is simpler | Product Owner |
| OQ-D04 | Is there a "notification centre" or in-app notification pattern, or are all alerts email-only until V1.1? | If in-app: notification bell in header; if email-only: no nav element needed | Product Owner |
| OQ-D05 | Is the trial expiry chip in the header shown from day 1, or only in the final 3 days? | Day 1 = full trial countdown; final 3 days only = minimal urgency pattern | Product Owner |
| OQ-D06 | What is the visual treatment for the "Trust Through Transparency" yield drill-down — a tooltip, a slide-in panel, or a modal? | Tooltip: compact but may be awkward on mobile; panel: better for the level of data | Design decision |
| OQ-D07 | Should custom broker creation be a full settings page or an inline "+ Add custom broker" option at the bottom of the broker dropdown? | Inline is lower friction for onboarding; settings page is more discoverable | Design decision |
| OQ-D08 | Is there a "Welcome" or onboarding tour for new users, or do they land directly on the empty dashboard? | Onboarding tour adds time-to-first-value risk; empty-state CTAs may be sufficient | Product Owner |

---

## Recommendations

1. **Prioritise the mobile Add Position form.** Farah's drop-off risk is highest at the moment she tries to add a position on mobile. The live fee calculation panel and the qualifying_shares field must work beautifully on a 375px screen. Build mobile-first for these two forms.

2. **Ship the Yield Drill-Down on day one.** This single interaction — tapping a yield percentage and seeing the full math — is the product's most powerful trust-building moment. It is not a "nice to have." It directly supports the core positioning claim: "provably accurate yield." Design this interaction to be delightful.

3. **Design the "Lot added — dividend records unchanged" success toast carefully.** This toast exists for one reason: to prevent David from losing trust. The copy must be specific ("2 existing dividend records unchanged") not generic ("Lot added successfully"). The first time David adds a second lot and sees this message, he will know the system understands the problem it is solving.

4. **Test the CSV import error table with real data before engineering sprint.** The error table is the most likely abandonment point in the onboarding flow. Write real example error messages in the design file — not placeholder "Error: invalid data" text. Real messages reduce cognitive load at the highest-friction moment.

5. **Do not add an onboarding tour for V1.** The 10-minute time-to-value principle means that an onboarding wizard adds risk, not value. The empty dashboard with two clear CTAs (Add Position, Import CSV) is sufficient. Defer an interactive tour to V1.1 once you have qualitative data on where users actually get stuck.

---

## UX Confidence Score: 8 / 10

### Reasoning

**What is solid (pushes the score up):**
- All 8 major user flows are fully specified (entry point → happy path → failures → exit state)
- Screen inventory is complete: 20+ screens, all states, empty states, error states, permission states
- Interaction specifications cover every major input type and feedback pattern
- The "Trust Through Transparency" yield drill-down pattern is clearly defined and tied to a specific interaction
- The qualifying_shares UX treatment is thoughtfully designed (default to current total, plain-English guidance, no technical jargon)
- Accessibility requirements are comprehensive and go beyond the minimum (dual-coding for P&L, live-region annotations for fee calculator)
- UX risk review identifies the 12 most likely failure points with concrete, actionable mitigations

**What holds the score back (2 points deducted):**
- No brand identity defined yet (OQ-D01 gap) — this will affect every screen during visual design
- Three high-priority stakeholder decisions (subscription pricing page, calendar view type, notification pattern) are open — the designer may need to produce two versions of several screens pending those answers
- The mobile breakpoint strategy (375px vs. 320px) is unresolved and affects the sell calculator table and fee panel layouts specifically

### What Would Take This to 9–10

1. Brand identity (colour palette, typography) confirmed — allows design to begin immediately
2. OQ-D01 (pricing page layout), OQ-D02 (calendar format), OQ-D05 (trial countdown trigger) resolved
3. One usability test session with one Ahmad-type user (any Malaysian investor with 10+ Bursa positions and an Excel portfolio) to validate that the fee breakdown panel builds trust rather than adding confusion

---

## Downstream Readiness

| Team | Status | Condition |
|------|--------|-----------|
| **Visual Designer** | Ready with Conditions | Can begin wireframing Dashboard, Add Position, and Dividend flows immediately. Pricing page and calendar format require stakeholder decisions first. Brand identity needed before any hi-fi work. |
| **Frontend Engineer** | Ready with Conditions | Interaction specifications and state definitions are complete enough to begin component library planning. Component states (loading, error, success, empty, permission-restricted) are fully specified. Sell calculator table responsive behaviour on mobile needs design mock before implementation. |
| **Product Manager** | Ready | Open design questions (OQ-D01 to OQ-D08) are clearly framed as low-cost decisions that should be batched into a single stakeholder session. |
| **QA / Test Lead** | Ready | Screen inventory, state definitions, and interaction specs provide a complete test surface. Happy path + failure path + state transition tests can be written directly from this spec. |

---

*End of Part 2 (Sections 7–11).*
*BursaTrack UX Spec v1.0 is complete across two files:*
*— Part 1: Sections 1–6 (Executive Summary, User Journey Maps, User Flows, Information Architecture, Screen Inventory, Screen Requirements)*
*— Part 2: Sections 7–11 (Interaction Specifications, State Definitions, Accessibility, UX Risk Review, Designer Readiness Review)*
