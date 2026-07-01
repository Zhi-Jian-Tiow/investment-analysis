# BursaTrack — UX Design Specification
## Part 1 of 2: Sections 1–6

> **Version:** 1.0
> **Date:** 2026-06-21
> **Author:** Senior Product Designer
> **Inputs:** BursaTrack-PRD-Final.md v2.0 · BursaTrack-BAS-Enhanced v2.0 (Parts 1–3)
> **Scope:** UX definition only — no visual designs, no wireframes, no hi-fi screens

---

# 1. UX EXECUTIVE SUMMARY

## Product Purpose

BursaTrack is a web application that replaces the manual Excel-based workflow for Malaysian dividend-focused retail investors. It automatically refreshes daily prices for Bursa-listed equities, calculates all-in transaction costs using the correct Malaysian fee stack (broker-specific brokerage, 0.03% clearing fee, RM1/RM1,000 stamp duty), logs per-tranche dividend payments, and computes a true yield using all-in cost as the denominator — the only tool in this market to do so. The core promise: the user's portfolio numbers are provably correct, every morning, without manual effort.

## Primary Users

Three personas drive V1 UX decisions:

**Ahmad (42, Methodical Dividend Accumulator)** — Desktop-primary, 5–10 min morning sessions, Maybank Investment broker, 12–18 positions, reinvests all dividends, checks every trading day. He needs speed, accuracy, and to never miss an ex-date. His primary frustration is the 15-minute manual update ritual.

**Farah (28, Emerging Income Investor)** — Mobile-primary, commute check-ins under 3 minutes, MooMoo broker, 6 positions. She wants a clean income view and to know when her next dividend arrives. Her primary frustration is that she does not trust her current numbers.

**David (35, Active Dividend Optimizer)** — Desktop-primary, deep analytical sessions, Rakuten Trade, 20+ positions. He models sell scenarios, tracks every lot and every tranche, and has already found formula bugs in his spreadsheet. He is willing to pay RM30/month for a tool that is bulletproof.

## UX Goals

1. **First value in under 10 minutes** — the user must reach a live yield calculation within one session of registration, without needing to read documentation.
2. **Trust through visible math** — every yield, cost, and fee figure must link to its constituent parts. No black-box numbers.
3. **Zero daily effort for price updates** — the dashboard must open showing current prices with no user action.
4. **Income-first hierarchy** — yield, dividend income, and payment calendar are the primary data; unrealised P&L and price movement are secondary.
5. **Graceful degradation** — price outages, stale data, and failed fetches must be visibly communicated and actionable, never silent.
6. **Mobile-ready for Farah** — every critical flow works on a 375px viewport, even if depth features are desktop-first.

## Key Design Principles

**1. Accuracy is visible, not assumed.** Every calculated number has a drill-down. The yield is not a black number — it is yield = RM[income] ÷ RM[all-in cost], always touchable.

**2. Progressive disclosure.** The dashboard is a fast summary. Depth lives one tap away. Ahmad gets his 5-minute morning check without seeing every lot and every tranche on load. David gets to every lot in two clicks.

**3. Prevent before correcting.** Smart defaults (broker pre-populated from user settings, qualifying shares defaulted to current position), inline validation, and confirmation dialogs for destructive actions. The user should not be able to accidentally corrupt data.

**4. Status at a glance.** Price freshness, trial expiry, and pending actions are communicated passively in the UI — not through modal interruptions unless action is required.

**5. Language of the dividend investor.** Labels use Malaysian investor vocabulary: "Yield," "All-In Cost," "Tranche," "Ex-Date," "Clearing Fee," "Stamp Duty." Not "ROI," "Net Asset Value," or trading terminology.

---

# 2. USER JOURNEY MAPS

---

## Persona 1: Ahmad — Methodical Dividend Accumulator

### User Goal
Migrate from Excel to BursaTrack; see correct yield calculations for all 16 positions; check portfolio every morning in under 5 minutes.

### Journey Stages

| Stage | User Goal | User Action | User Thoughts | Pain Points | UX Opportunities |
|-------|-----------|-------------|---------------|-------------|-----------------|
| **1. Discovery** | Find a better tool than Excel | Searches online, reads i3investor forum post about BursaTrack | "I wonder if this is actually better than what I built — the fee formulas need to be right" | Skepticism about accuracy claims; has been let down before | Lead with the accuracy proof: show the fee formula, not just the feature list; let him verify the calculation before signing up |
| **2. Registration** | Create an account with minimal friction | Enters email, password, selects Maybank Investment as default broker | "I just want to see the numbers — don't make me fill 10 fields" | Friction before value; email verification interrupting flow | 3-field form (email, password, broker); no mandatory email verification to access trial; Maybank Investment visible first in broker list |
| **3. Onboarding** | Enter first position; see yield | Types CIMB, 5,000 shares, RM8.38, sees all-in cost RM41,996.47 | "Wait — it automatically calculated all the fees. Let me verify this." | If the fee breakdown is hidden, trust is not built | Show fee breakdown inline as user types; animate calculation; show a tooltip linking the formula |
| **4. Portfolio Build** | Enter all 16 positions (or import CSV) | Adds remaining 15 stocks manually or uploads CSV | "This is going to take a while — I wish I could just paste from Excel" | Data entry time for power user with 16 stocks | Prominent "Import CSV" shortcut on the empty portfolio screen; Excel-to-CSV guide in import tooltip |
| **5. Daily Check** | Open dashboard; see current prices and yield | Opens browser 8:30 AM Monday; prices load automatically | "It already refreshed — I didn't have to do anything" | If prices are stale and not clearly flagged, trust breaks | "Last refreshed" timestamp prominently displayed; stale indicator immediately visible; no user action required on a good trading day |
| **6. Dividend Logging** | Log a new dividend tranche after announcement | Clicks "Add Dividend" on CIMB, enters RM0.20/share | "It asks for qualifying shares — that's more precise than my Excel. It pre-filled 5,000. Good." | Extra field (qualifying_shares) adds a step | Pre-fill qualifying shares with current total; label as "Shares qualifying for this dividend"; guidance text explains what to do if they bought more shares after ex-date |
| **7. Retention** | Continue using for 3+ months | Daily morning check, quarterly dividend logging | "This saves me 12 minutes a day. The numbers match what I know." | Subscription paywall looms at end of trial | Clear 14-day trial countdown in non-intrusive header chip; value email at day 3 showing minutes saved; frictionless subscribe on day 14 |

**High Friction Areas:**
- Position bulk entry for 16 stocks (partially resolved by CSV import)
- Dividend tranche entry requires understanding qualifying_shares concept (resolved by smart default + explanation text)

**High Risk Areas:**
- If the calculated all-in cost does not match Ahmad's Excel value on first entry, trust collapses immediately
- If prices are not refreshed by 8:30 AM on day one, the core promise is broken

**Drop-off Risks:**
- Registration → First position: if adding a position is more than 5 fields, Ahmad will stall
- After trial → Subscription: if Ahmad has not yet seen 14 days of accurate numbers, he won't convert

---

## Persona 2: Farah — Emerging Income Investor

### User Goal
See her 6 positions and understand when her next dividend arrives, in under 3 minutes on her phone.

### Journey Stages

| Stage | User Goal | User Action | User Thoughts | Pain Points | UX Opportunities |
|-------|-----------|-------------|---------------|-------------|-----------------|
| **1. Discovery** | Find a clean mobile tool for dividend tracking | Sees Instagram post from investment influencer | "This looks clean. But is it another thing I'll never use?" | App store skepticism; previous abandoned tools | Show a short, readable dividend calendar on the landing page; she needs to see the output before committing |
| **2. Registration** | Sign up quickly | Taps sign up; enters email, password, selects MooMoo | "Easy enough. But I have to add everything manually?" | Friction from data entry expectation | Immediately surface CSV import as a "have your history from day one" path at the end of registration |
| **3. First Position** | Add MAYBANK quickly on mobile | Enters on phone: MAYBANK, 2000 shares, RM9.20, date, MooMoo auto-selected | "Oh — it calculated everything. What is clearing fee? I didn't know about that." | May be confused by fee breakdown terms | Collapsible "What is this?" tooltips on Clearing Fee and Stamp Duty; friendly label "Total you paid including fees" |
| **4. Portfolio View** | See income summary in one glance | Views dashboard on phone | "Where is the yield? I want to see all my dividends together." | If yield is buried below price data, she won't find it | Dividend yield and YTD income as the TOP row of the position table on mobile; P&L below |
| **5. Dividend Calendar** | Check when next payment arrives | Taps "Calendar" in navigation | "MAYBANK ex-date is 15 Feb. I knew that — nice to see it here." | If she hasn't entered ex-dates, calendar is empty | Prompt to add ex-date when logging dividends; "Upcoming in 7 days" highlighted badge in navigation |
| **6. Retention Check** | Quick 90-second Monday morning check | Opens app; sees 6 positions, last refreshed 9:30 AM | "All green. Nothing to do." | Nothing actionable ≠ no value | Dashboard shows "Your next dividend: CIMB, est. RM400.00, payment 15 Mar" as a prominent card |

**High Friction Areas:**
- Mobile keyboard entry of stock codes and prices requires validation to avoid typos
- No automated dividend data means she must add ex-dates herself to unlock the calendar

**High Risk Areas:**
- If the mobile dashboard is dense and hard to read, Farah abandons within one session
- Empty dividend calendar is a disappointment moment; must be handled gracefully

**Drop-off Risks:**
- After adding first position if the mobile layout is complex
- At trial expiry if she hasn't experienced the calendar or income summary as genuinely useful

---

## Persona 3: David — Active Dividend Optimizer

### User Goal
Migrate 20+ position portfolio with multiple lots; model sell scenarios; validate that the yield calculation is provably correct.

### Journey Stages

| Stage | User Goal | User Action | User Thoughts | Pain Points | UX Opportunities |
|-------|-----------|-------------|---------------|-------------|-----------------|
| **1. Discovery** | Find a tool that handles per-broker fees and multiple lots | Reads about BursaTrack in developer investment community | "Does it support Rakuten Trade's tiered fees? Does it do multiple lots per position?" | Will check feature list before signing up; tests boundaries fast | Features page should show per-broker support explicitly; Rakuten Trade listed (even if V1 = flat RM7 with disclosure) |
| **2. Registration** | Register, select Rakuten Trade | Registers in 30 seconds | "Good — they have Rakuten Trade. Let's see if the fee maths is right." | Immediately tests the fee calculation | Show fee calculation in real time on the add position form; David will type in a trade he already knows the answer to |
| **3. Portfolio Build via CSV** | Import all 20+ positions from his existing spreadsheet | Downloads template, maps columns, uploads | "The template needs a qualifying_shares column. Is it optional?" | CSV template must be clear; column mapping mental overhead | One-page CSV guide; example row in the template; qualifying_shares clearly labelled as optional with a tooltip |
| **4. Lot-Level View** | Add second lot to CIMB | Clicks "Add Lot" on CIMB position; enters new lot details | "The blended price updates correctly. The existing dividend tranche total is unchanged. This is right." | If adding a lot changes historical dividend totals, David immediately loses trust | After adding a lot, explicitly confirm "2 existing dividend records unchanged" in the update success message |
| **5. Sell Calculator** | Model CIMB sell at RM8.60 | Opens sell calculator for CIMB | "Shows the break-even at RM8.42. Let me verify: 5000 × 8.42 = 42,100. Minus brokerage RM42.10, clearing RM12.63, stamp RM43. Net ≈ RM42,002. Profit RM5.53. Close enough." | David will manually verify the numbers | Sell calculator must show each fee component as a visible column in the scenario table, not just net proceeds |
| **6. Yield Audit** | Verify yield is calculated on all-in cost | Views CIMB yield: 5.57%. Drills down. | "Total income ÷ all-in cost. Correct." | If yield is a black number with no drill-down, David doesn't trust it | Yield figure is always tappable; drill-down shows: income = sum of tranches + per-tranche breakdown; cost = sum of lots + per-lot fee breakdown |
| **7. Daily Analytical Review** | Weekly session reviewing all positions | Saturday morning, 20-minute portfolio review | "I want to sort by yield, see which positions are underperforming, model a switch." | Dashboard needs power-user density without overwhelming Farah | Sortable columns; optional columns toggle; position detail shows historical yield trend (V1.1) |

**High Friction Areas:**
- CSV import for 20+ positions with multiple lots — template must handle multiple lots per stock clearly
- Qualifying shares override requires understanding the concept — power users like David will use it

**High Risk Areas:**
- If fee calculation for Rakuten Trade is wrong (V1 uses flat RM7, not tiered), David will notice immediately — must be disclosed in the broker selector
- If the sell calculator doesn't show fee components, David won't trust it

**Drop-off Risks:**
- If the CSV import fails on his first attempt (column mapping error), David won't retry
- If yield has no drill-down, David won't convert — he builds his own tools instead

---

# 3. USER FLOWS

---

## Flow 1 — Registration and First Position

### Entry Point
Landing page → "Start Free Trial" CTA

### Trigger
New visitor decides to try BursaTrack

### Happy Path
```
1. Land on registration form (email, password, default broker dropdown)
2. Enter details → submit
3. Account created → redirect to Welcome screen
   - Banner: "Verify your email when you have a moment. You have full access now."
4. Welcome screen offers two paths:
   - [Add your first position →] (primary CTA)
   - [Import from CSV →] (secondary CTA)
5. User clicks "Add your first position"
6. Add Position modal/page: stock code/name search, shares, price, date, broker (pre-filled with default)
7. System calculates fees inline as user types
8. User submits → position appears on dashboard
9. Dashboard: one position row; yield displayed; "Add more positions or Import from CSV" prompt visible
```

### Alternative Paths
- User chooses CSV import at step 4 → goes to Import flow (Flow 5)
- User closes Welcome screen without acting → returns to empty dashboard with "Add Position" and "Import CSV" as empty-state CTAs

### Failure Paths
- Email already registered → inline error: "This email is already registered. [Log in instead?]"
- Password too short → inline error before submission
- Invalid stock code → inline error on stock field: "Stock code not found on Bursa Malaysia"

### Exit State
User is on the dashboard with at least one position visible, or on the import page.

---

## Flow 2 — Add Position / Add Lot

### Entry Point
Dashboard → "Add Position" button; or Position detail → "Add Lot" button

### Trigger
User wants to record a new purchase

### Happy Path
```
1. User clicks "Add Position"
2. Form appears with fields:
   - Stock code / name (autocomplete search)
   - Number of shares
   - Purchase price per share (MYR)
   - Purchase date
   - Broker (defaults to user's account default; editable)
   - Category tag (Dividend / Volatile / Growth; defaults to Dividend)
3. As user types shares and price, the fee breakdown calculates live:
   - Initial Amount: RM XX,XXX.XX
   - Brokerage Fee: RM XX.XX (shows formula, e.g., "Maybank 0.10%")
   - Clearing Fee: RM XX.XX (0.03%)
   - Stamp Duty: RM XX.XX (RM1 per RM1,000)
   - ─────────────────────
   - All-In Cost: RM XX,XXX.XX
4. User submits
5. Success: position row added to dashboard; yield shows "—" until first dividend logged
```

### Add Lot Path
```
1. User opens existing CIMB position → clicks "Add Lot"
2. Same form as above (stock is pre-filled and locked)
3. After submit: success message: "Lot added. 2 existing dividend records unchanged."
   - This message is critical for David — it confirms stored dividend totals were not corrupted
4. Position row updates: total shares, total all-in cost, blended price recalculate
```

### Alternative Paths
- User selects a stock already in portfolio via "Add Position" → system detects duplicate → shows: "You already have a CIMB position. This will be added as a new lot." → user confirms or cancels

### Failure Paths
- Zero or negative shares → inline: "Shares must be at least 1"
- Price = 0 → inline: "Purchase price must be greater than zero"
- Future purchase date → inline: "Purchase date cannot be in the future"

### Exit State
Position row on dashboard updated with new lot; user returns to dashboard view.

---

## Flow 3 — Log Dividend Tranche

### Entry Point
Position row on dashboard → "Add Dividend" CTA; or Position detail → Dividends section → "Add Tranche"

### Trigger
User receives a dividend payment and wants to record it

### Happy Path
```
1. User opens position (e.g., CIMB)
2. Navigates to Dividends tab/section
3. Clicks "Add Dividend Tranche"
4. Form:
   - Tranche label (auto-suggested: "1st" if no tranches exist; "2nd" if 1 exists, etc.)
   - Dividend per share (MYR — up to 6 decimal places)
   - Payment date
   - Ex-dividend date (optional)
   - Qualifying shares: [5,000] ← pre-filled with current total; with guidance text:
     "Number of shares you held before the ex-date. Change this if you bought additional shares after the ex-dividend date."
5. As user types per share and qualifying shares, live preview shows:
   - Total dividend this tranche: RM X,XXX.XX (= per share × qualifying shares)
6. User submits
7. Success:
   - Tranche row appears in dividend table
   - Position yield updates immediately
   - "Total dividend income YTD: RM X,XXX.XX" updates in position header
   - If ex-date was entered: dividend calendar updates
```

### Alternative Paths
- User overrides qualifying shares (e.g., from 7,000 to 5,000): live preview updates immediately; no error shown (this is a valid override)
- User leaves ex-dividend date blank: tranche is saved without calendar entry; a soft nudge "Add an ex-date to track this in your Dividend Calendar" appears after save

### Failure Paths
- Per share amount = 0 → inline: "Dividend per share must be greater than zero"
- Qualifying shares > current position total → inline: "Qualifying shares cannot exceed your current total (X,XXX shares)"
- 8th tranche already exists for this year → error: "You've reached the maximum of 8 tranches for CIMB in 2026"

### Exit State
Dividend table shows new tranche; position yield updated; user is on the dividends tab.

---

## Flow 4 — Dashboard Daily Check (Returning User)

### Entry Point
Bookmarked URL or browser home button

### Trigger
Morning check-in (Ahmad: 8:30 AM; Farah: commute; David: after market close)

### Happy Path
```
1. User navigates to URL
2. Authentication check → session valid → dashboard loads
3. Dashboard header shows:
   - Total All-In Cost: RM XXX,XXX.XX
   - Total Dividend Income YTD: RM XX,XXX.XX
   - Portfolio Yield: X.XX%
   - Last Refreshed: Today, 9:30 AM [green dot]
4. Position table loads with current prices, sorted by yield descending
5. User scans the table — no action needed on a good trading day
6. User closes tab or navigates away
Total time: < 60 seconds
```

### Alternative Paths — Stale Price
```
1. Dashboard loads but "Last Refreshed: Yesterday, 9:30 AM [amber dot]" appears
2. Banner at top: "Price data unavailable for X stocks — showing last known prices.
   Update prices manually below."
3. Affected positions show an amber ⚠ beside their price
4. User clicks ⚠ → inline price input appears
5. User types current price → position recalculates
```

### Alternative Paths — Trial Countdown
```
If trial expires in 3 days or fewer:
- A non-intrusive chip appears in the header: "Trial ends in 3 days — Subscribe"
- Does NOT block dashboard or interrupt the check
```

### Failure Paths
- Session expired → redirect to login → user logs in → returns to dashboard
- All prices stale → full-page banner; manual entry for each position

### Exit State
User has seen their portfolio performance; may or may not have taken action.

---

## Flow 5 — CSV Import

### Entry Point
Dashboard empty state → "Import from CSV"; or Settings → Import

### Trigger
New user with existing portfolio in Excel/Google Sheets; or returning user wanting to bulk-add positions

### Happy Path
```
1. User navigates to Import page
2. Page shows two options:
   - [Download Template] (primary action when user has no template)
   - [Upload CSV] (primary action when user has already prepared the file)
3. User downloads template
4. Template opens in Excel: two sheets (Positions & Lots; Dividend Tranches)
   - Guide row shows field format; example data row
   - Qualifying_shares column present in Dividend Tranches sheet with tooltip: "Optional. Defaults to the share total for this stock in this import."
5. User fills template; saves as CSV; uploads
6. BursaTrack validates:
   - File-level check (format, headers)
   - Row-level check (data types, ranges, stock codes)
7. If valid: success screen: "Import complete — 16 positions, 34 dividend records imported."
   - [View Portfolio →]
8. Portfolio dashboard now shows all positions with calculated fees and yields
```

### Failure Paths
```
If validation fails:
- Error table: "Row 14, Column purchase_price: Value '8,380' contains a comma. Use 8.3800 instead."
- Every error listed; import not processed
- [Download Error Report] button
- User corrects file and re-uploads; no data was created
```

### Exit State
Portfolio populated with imported data; user redirected to dashboard.

---

## Flow 6 — Sell Scenario Calculator

### Entry Point
Position row → "Sell Calculator" action; or Position detail → "Sell" tab

### Trigger
User is considering selling and wants to know their break-even and net profit at various prices

### Happy Path
```
1. User opens sell calculator for CIMB
2. Form pre-populates:
   - Stock: CIMB — 5,000 shares
   - All-In Buy Cost: RM41,996.47
   - Sell Broker: Maybank Investment (editable)
   - Shares to Sell: 5,000 (editable — for partial sale)
   - Current Price: RM8.42 (from latest PriceSnapshot)
3. Scenario table generates automatically:
   Columns: Sell Price | Gross Proceeds | Brokerage | Clearing | Stamp | Net Proceeds | P/L
   Rows: auto-generated at +0.01 steps near current price, then +0.05 steps up to +0.70
4. Break-even row is highlighted (e.g., RM8.42 row highlighted in amber)
5. Disclosure banner (non-dismissable): "Informational only. Settlement T+2."
6. User scrolls the table; optionally types a custom sell price in an input above the table
7. Table is read-only — nothing is saved
```

### Alternative Paths
- User changes "Shares to Sell" to 2,000 → table recalculates using proportional cost basis
- User changes sell broker → table recalculates with new fee rate

### Failure Paths
- No current price available (stale) → warning above table: "Using last known price (yesterday). Update price first for accurate scenarios."

### Exit State
Calculator results displayed; user navigates back to dashboard or position detail.

---

## Flow 7 — Password Reset

### Entry Point
Login page → "Forgot password?"

### Happy Path
```
1. User clicks "Forgot password?"
2. Form: "Enter your email address" → submit
3. Response (identical regardless of whether email exists): "If an account with that email exists, a reset link has been sent."
4. User receives email → clicks link (valid for 1 hour)
5. New password form: password + confirm password
6. Submit → "Password updated successfully. Please log in."
7. User redirected to login; all prior sessions invalidated
```

### Failure Paths
- Link expired → "This link has expired. [Request a new link?]"
- Link already used → "This link has already been used. If you didn't reset your password, contact support."

### Exit State
User is on the login page with a fresh password.

---

## Flow 8 — Account Deletion (PDPA)

### Entry Point
Account Settings → "Delete my account"

### Happy Path
```
1. User clicks "Delete my account"
2. Step 1 prompt: "Before we go — would you like to download your data first?"
   - [Download My Data] → runs FR-018 export, then returns to step 3
   - [Skip and continue]
3. Step 2 confirmation: "This will permanently delete your account and all data in 30 days. Type DELETE to confirm."
4. User types DELETE → submit
5. Confirmation screen: "Deletion requested. Your data will be permanently deleted on [date+30 days]. Check your email for details."
6. Session ends → user logged out
7. Cancellation email sent with 30-day valid link
```

### Failure Paths
- User types something other than DELETE → button remains disabled; inline hint: "Type DELETE exactly to confirm"
- Cancellation link clicked within 30 days → "Deletion cancelled. You can log in again."

### Exit State
Account pending deletion (user logged out); or deletion cancelled (user returned to account).

---

# 4. INFORMATION ARCHITECTURE

## Navigation Structure

BursaTrack has a single-tier primary navigation with four top-level destinations. Navigation is persistent on all authenticated screens.

```
ROOT (authenticated)
│
├── 🏠 Dashboard              [default landing screen]
│   ├── Portfolio Summary Header (cost / income / yield / freshness)
│   ├── Position Table (sortable; default: yield descending)
│   │   └── Per-Position Row → Position Detail (drill-down)
│   │       ├── Lots Tab (per-lot fee breakdown)
│   │       ├── Dividends Tab (per-tranche dividend table + Add Dividend)
│   │       └── Sell Calculator Tab
│   └── "Add Position" floating action button / top-bar button
│
├── 📅 Dividend Calendar       [upcoming ex-dates + payment dates]
│   ├── Upcoming (next 90 days, chronological)
│   ├── Past (last 30 days, with "Paid" badge)
│   └── Empty State (prompt to add ex-dates when logging dividends)
│
├── 📥 Import / Export         [data management]
│   ├── Import CSV (template download + file upload)
│   └── Export My Data (PDPA — FR-018)
│
└── ⚙️ Account Settings        [profile + subscription + data]
    ├── Profile (email, default broker, password change)
    ├── Subscription (plan, renewal, cancel)
    ├── Broker Settings (custom brokers)
    └── Danger Zone (Delete Account — FR-019)
```

**Unauthenticated routes:**
```
/login
/register
/forgot-password
/reset-password/[token]
```

## Content Hierarchy

### Level 1 — Portfolio (global aggregate)
Total all-in cost · Total dividend income (YTD) · Portfolio blended yield · Last refreshed

### Level 2 — Position (per stock)
Stock name/code · Category tag · Total shares · Blended price · Total all-in cost · Current price · Market value · Unrealised P&L · YTD income · Yield

### Level 3 — Lot (per purchase transaction)
Shares · Purchase price · Purchase date · Broker · Initial amount · Brokerage fee · Clearing fee · Stamp duty · All-in cost

### Level 3 — Dividend Tranche (per payout)
Tranche label · Per-share amount · Qualifying shares · Total amount · Payment date · Ex-dividend date

## Parent/Child Relationships

```
Portfolio (1)
└── Position (1..N, one per stock)
    ├── Lot (1..N, one per buy transaction)
    └── DividendTranche (0..8 per calendar year)
```

## Grouping Logic

**Dashboard grouping:** All positions in a flat table; no visual grouping by sector or category in V1 (category tag is a filter/label, not a navigation-level grouping).

**Dividend Calendar grouping:** Chronological by ex-dividend date (primary), payment date (secondary). Two sub-views: Upcoming (≥ today) and Past (< today, last 30 days).

**Position detail grouping:** Tabbed: Lots | Dividends | Sell Calculator. The three concerns are related to the same position but serve different analytical modes — keeping them in tabs prevents cognitive overload.

**Settings grouping:** Functional: Profile · Subscription · Broker Settings · Data / Danger Zone. Danger zone (account deletion) is visually separated with a border and a warning colour.

---

# 5. SCREEN INVENTORY

## Core Authenticated Screens

| Screen Name | Purpose | Primary Actions | Associated Workflow |
|-------------|---------|-----------------|---------------------|
| Dashboard | Portfolio overview — all positions, summary metrics, live prices | View positions, Add Position, click into position detail | Flow 4 (Daily Check) |
| Position Detail — Lots Tab | Show all lots for a stock with full fee breakdown | Add Lot, Edit Lot, Delete Lot | Flow 2 |
| Position Detail — Dividends Tab | Show all dividend tranches for a stock | Add Dividend Tranche, Edit Tranche, Delete Tranche | Flow 3 |
| Position Detail — Sell Calculator Tab | Model sell scenarios at multiple price points | Adjust shares to sell, adjust sell broker, enter custom price | Flow 6 |
| Add Position Form | Add a new stock to portfolio | Submit position | Flow 2 |
| Add Lot Form | Add a new purchase lot to an existing position | Submit lot | Flow 2 |
| Add Dividend Form | Log a new dividend tranche | Submit tranche | Flow 3 |
| Edit Position / Lot Form | Correct a previously entered lot | Submit edit | Flow 2 |
| Edit Dividend Form | Correct a previously entered tranche | Submit edit | Flow 3 |
| Dividend Calendar | See upcoming and past ex-dates / payment dates | View only (V1 — no direct edit from here) | Flow 4 |
| Import Page | Bulk-import portfolio from CSV | Download template, upload CSV | Flow 5 |
| Import Result Screen | Show success or error report after import | View portfolio (success) or download error report (failure) | Flow 5 |
| Account Settings — Profile | Manage email, default broker, password | Edit profile, change password | Flow 7 (change pwd) |
| Account Settings — Subscription | View plan, manage billing | Subscribe, cancel subscription | — |
| Account Settings — Broker Settings | Add / edit custom brokers | Add custom broker, deactivate broker | — |
| Account Settings — Export Data | PDPA data export | Download ZIP | FR-018 |
| Account Settings — Delete Account | PDPA account deletion | Initiate deletion | Flow 8 |

## Unauthenticated Screens

| Screen Name | Purpose | Primary Actions | Associated Workflow |
|-------------|---------|-----------------|---------------------|
| Landing / Marketing Page | Convert visitors | Register, Log in | — |
| Registration Form | Create account | Submit registration | Flow 1 |
| Login Form | Authenticate | Log in, Forgot password | — |
| Forgot Password Form | Initiate password reset | Submit email | Flow 7 |
| Reset Password Form | Set new password | Submit new password | Flow 7 |

## Modal / Overlay Screens

| Screen Name | Purpose | Primary Actions |
|-------------|---------|-----------------|
| Add Position Modal | Inline position creation from dashboard | Submit |
| Add Lot Modal | Inline lot addition from position detail | Submit |
| Add Dividend Modal | Inline dividend logging from position detail | Submit |
| Edit Lot Modal | Inline lot correction | Submit |
| Edit Dividend Modal | Inline dividend correction | Submit |
| Delete Confirmation Dialog | Confirm irreversible deletions | Confirm / Cancel |
| Fee Breakdown Tooltip/Sheet | Show formula behind all-in cost | Read-only |
| Yield Breakdown Tooltip/Sheet | Show income ÷ cost drill-down | Read-only |

## Empty States

| Screen | Empty State Trigger | Message |
|--------|-------------------|---------|
| Dashboard | No positions added | "Welcome to BursaTrack. Add your first position or import from CSV to get started." |
| Dividend Calendar | No ex-dates entered | "Add ex-dividend dates when logging dividends to see your payment schedule here." |
| Position Lots Tab | Should never be empty (position requires ≥ 1 lot) | N/A |
| Position Dividends Tab | No dividends logged | "No dividends logged for this year. Track your first payment above." |

## Error States

| Screen | Error Trigger | Error State Content |
|--------|--------------|---------------------|
| Dashboard | Price data all stale | Full-page amber banner + stale indicators per position |
| Dashboard | Partial stale prices | Per-position amber ⚠ + partial banner |
| Import Page | Validation failure | Row-level error table; "No records imported. Correct errors and re-upload." |
| Add / Edit Forms | Validation error | Inline field-level error messages |
| Sell Calculator | No current price | Warning: "Using last known price. Update price first." |
| Reset Password | Expired token | "This link has expired. [Request new link?]" |
| Reset Password | Used token | "This link has already been used." |

## Permission / State Screens

| Screen | Condition | Behaviour |
|--------|-----------|-----------|
| Dashboard | Trial expired | Read-only view; paywall banner: "Your trial has ended. Subscribe to continue." |
| Any write action | Trial expired | Blocked; paywall modal appears instead |
| Login | Account pending deletion | "Your account deletion is pending. [Cancel deletion] or [Contact support]." |

## Success States

| Action | Success Treatment |
|--------|------------------|
| Position added | Position row animates into dashboard table |
| Lot added | Success toast: "Lot added. X existing dividend records unchanged." |
| Dividend logged | Yield in position header updates immediately; success toast |
| CSV import complete | Full success screen: "Import complete — N positions, M dividend records." |
| Password reset complete | Redirect to login with: "Password updated. Please log in." |
| Account deletion initiated | Dedicated confirmation page (not just a toast) |
| Subscription activated | Success banner: "Welcome to BursaTrack! Full access is now active." |

---

# 6. SCREEN REQUIREMENTS

---

## Screen: Dashboard

### Purpose
The primary daily view for all three personas. Displays a portfolio health summary and a sortable position table. Must load fast and require zero actions for a good-data trading day.

### User Goals
- Ahmad: confirm all 16 prices have refreshed; check overall yield in < 60 seconds
- Farah: see income total and yield at a glance; check on mobile in < 3 minutes
- David: scan positions by yield; identify any that need attention; access position detail

### Key Information Displayed

**Header Summary Row (always visible, above the fold on desktop and mobile):**
- Total All-In Cost: RM [amount]
- Total Dividend Income YTD: RM [amount]
- Portfolio Blended Yield: [X.XX%]
- Last Refreshed: [Today, HH:MM] with a green dot (current) or amber dot (stale)

**Position Table Columns (default order):**
1. Stock Name & Code (with category tag chip)
2. Total Shares
3. Blended Purchase Price
4. Total All-In Cost
5. Current Price (with stale indicator if applicable)
6. Market Value
7. Unrealised P&L (colour: green if positive, red if negative)
8. Dividend Income YTD
9. Yield % (bold; this is the primary sort column)
10. Actions menu (•••) → Edit / Add Lot / Add Dividend / Sell Calculator / Delete

**Mobile layout:** Columns 1, 9 (yield), 8 (income) are visible by default. All other columns accessible via row tap → Position Detail.

### Primary Actions
- Add Position (floating action button on mobile; button in top bar on desktop)
- Sort by any column header

### Secondary Actions
- Import from CSV (empty state or via navigation)
- Per-row actions via ••• menu

### Entry Conditions
- User is authenticated with any active account status
- Trial expired: same view but all write actions disabled; paywall banner shown

### Exit Conditions
- User navigates to Calendar, Import, Settings, or Position Detail
- Session expires → login

---

## Screen: Position Detail — Lots Tab

### Purpose
Show the per-lot breakdown for a stock, including each lot's individual fee components and all-in cost. The transparency layer that makes Ahmad and David trust the numbers.

### User Goals
- Verify that each lot's fees were calculated correctly
- Add a new lot (bought more shares)
- Edit a lot (entered wrong price or date)

### Key Information Displayed

**Position header (persistent across tabs):**
- Stock name / code / category
- Total shares · Blended purchase price · Total all-in cost
- YTD dividend income · Yield

**Lots Table:**
| Lot # | Shares | Purchase Price | Date | Broker | Initial Amount | Brokerage | Clearing | Stamp Duty | All-In Cost | Actions |
Each row is expandable to show the fee formula tooltip (e.g., "Clearing = RM41,900 × 0.03% = RM12.57").

### Primary Actions
- Add Lot
- Edit Lot (per row)
- Delete Lot (per row, with confirmation dialog)

### Secondary Actions
- View Lots tab → navigate to Dividends tab or Sell Calculator tab

### Entry Conditions
- User navigated from position row on Dashboard

### Exit Conditions
- User clicks Back → Dashboard
- User navigates to another tab (Dividends, Sell Calculator)
- User submits Add/Edit/Delete → remains on Lots Tab with updated data

---

## Screen: Position Detail — Dividends Tab

### Purpose
Show all dividend tranches for the current position and allow logging, editing, and deleting tranches. The qualifying_shares field and stored total_amount must be clearly presented to build trust.

### User Goals
- See all dividends received for this stock, this year and historically
- Log a new dividend tranche
- Verify that a previously logged tranche has the correct qualifying shares and total

### Key Information Displayed

**Dividend Summary (above table):**
- Total dividend income YTD: RM [amount] (sum of stored total_amounts, current year)
- Dividend per share YTD: RM [amount] (sum of per_share_amounts, current year)
- Yield: [X.XX%] = RM [income] ÷ RM [all-in cost] ← tappable to show the full formula

**Dividend Tranches Table:**
| Tranche | Per Share | Qualifying Shares | Total Received | Payment Date | Ex-Date | Actions |
- If qualifying_shares ≠ current position total_shares: show a note: "Held [N] qualifying shares (current total: [M])"
- Rows sorted by payment_date descending (most recent first)

### Primary Actions
- Add Dividend Tranche (CTA above table)

### Secondary Actions
- Edit Tranche (per row)
- Delete Tranche (per row, with confirmation)
- Tap on yield figure → Yield drill-down modal

### Entry Conditions
- User navigated to Dividends tab from Lots tab or directly from position row

### Exit Conditions
Same as Lots Tab.

---

## Screen: Position Detail — Sell Calculator Tab

### Purpose
Fee-accurate sell scenario modelling for a specific position. Not saved to the portfolio.

### User Goals
- David: see break-even at multiple price points with full fee transparency
- Any user: know "if I sell today, what do I net?"

### Key Information Displayed

**Input row (above table):**
- Shares to sell: [5,000] (editable)
- Sell broker: [Maybank Investment] (editable dropdown)
- Buy cost basis: RM41,996.47 (read-only; proportional if partial sale)
- Current price: RM8.42 (from latest PriceSnapshot; shows stale warning if applicable)

**Scenario Table:**
| Sell Price | Gross Proceeds | Brokerage | Clearing | Stamp Duty | Net Proceeds | P/L |
Auto-generated at incremental steps; break-even row highlighted in amber.
Custom price input at top: "Enter a specific price" → adds a row and scrolls to it.

**Non-dismissable disclosure banner:**
"Calculations are informational only. Settlement occurs T+2 (two trading days after sale). BursaTrack is not a financial advisor."

### Primary Actions
- None (read-only calculator)

### Secondary Actions
- Edit shares to sell
- Change sell broker
- Enter custom price

### Entry Conditions
- User navigated to Sell tab from position detail

### Exit Conditions
- User navigates to other tabs or Back → Dashboard

---

## Screen: Add Position / Add Lot Form (Modal)

### Purpose
Record a new purchase with full fee calculation visible in real time. The first place the user verifies BursaTrack's accuracy.

### User Goals
- Enter a new stock purchase
- See the fee calculation happen live (builds trust on first use)

### Key Information Displayed

**Input fields:**
- Stock code / name (autocomplete: type "CIMB" or "1023")
- Number of shares
- Purchase price per share (MYR)
- Purchase date
- Broker (dropdown; defaults to account default)
- Category tag (Dividend / Volatile / Growth)

**Live fee calculation panel (updates as user types):**
```
Initial Amount:    RM 41,900.00
Brokerage Fee:     RM     41.90   (Maybank: 0.10% of RM41,900)
Clearing Fee:      RM     12.57   (0.03% of RM41,900)
Stamp Duty:        RM     42.00   (RM1 per RM1,000)
──────────────────────────────────
All-In Cost:       RM 41,996.47
```
Each line shows its formula in grey text. Brokerage line shows the broker name and rate dynamically.

### Primary Actions
- Save Position (submit)

### Secondary Actions
- Cancel (close modal without saving)

### Entry Conditions
- User clicked "Add Position" on dashboard (new position) or "Add Lot" on position detail (new lot)

### Exit Conditions
- Successful save → position appears on dashboard or lot tab; success toast shown
- Cancel → returns to previous screen with no changes

---

## Screen: Add / Edit Dividend Form (Modal)

### Purpose
Log a new dividend tranche with the qualifying_shares concept made understandable to non-technical users.

### User Goals
- Record a dividend payment
- Confirm the total they received is correctly calculated

### Key Information Displayed

**Input fields:**
- Tranche label (auto-suggested; editable dropdown: 1st…8th)
- Dividend per share (MYR)
- Payment date
- Ex-dividend date (optional; with explainer: "The last date you needed to hold shares to receive this dividend")
- Qualifying shares: [5,000] with guidance text:
  "The number of shares you held before the ex-dividend date. Pre-filled with your current total (5,000). Update this if you bought additional shares after the ex-date."

**Live calculation preview:**
```
Total received this tranche:  RM 1,000.00
(= RM0.20 × 5,000 qualifying shares)
```
This preview updates immediately when either per_share or qualifying_shares changes.

### Primary Actions
- Save Dividend

### Secondary Actions
- Cancel

### Entry Conditions
- "Add Dividend Tranche" clicked from Dividends tab

### Exit Conditions
- Successful save → tranche row appears; yield and income totals update
- Cancel → no change

---

## Screen: Dividend Calendar

### Purpose
Chronological view of upcoming and past ex-dates and payment dates for all held positions. Helps Farah know when her next payment arrives.

### User Goals
- See upcoming ex-dates and payment dates
- Identify payments arriving in the next 7 days

### Key Information Displayed

**Highlighted upcoming section:**
"Due in the next 7 days" — up to 3 entries shown as cards with stock name, tranche label, ex-date, payment date, and total amount (based on qualifying_shares).

**Full chronological list:**
| Stock | Tranche | Ex-Date | Payment Date | Per Share | Total Amount | Status |
- Status: "Upcoming" (future payments), "Paid" (past payments within 30 days)
- Total amount shown with note if qualifying_shares differs from current total

**Empty state:** "Add ex-dividend dates when logging dividends to see your payment schedule here. [Go to portfolio →]"

### Primary Actions
- None — read-only in V1

### Secondary Actions
- Tap position name → navigates to Position Detail (Dividends tab)

### Entry Conditions
- User taps/clicks Calendar in navigation

### Exit Conditions
- Navigation to another section

---

## Screen: Import Page

### Purpose
Guide the user through CSV bulk import with clear template, validation, and atomic error reporting.

### User Goals
- Migrate existing portfolio from Excel/Google Sheets in one session
- Know exactly what went wrong if the import fails

### Key Information Displayed

**Step-by-step layout:**
1. "Step 1: Download the template" — [Download Template] button with note: "Two sheets: Positions & Lots, and Dividend Tranches."
2. "Step 2: Fill in your data" — link to a 2-minute guide (in-app or expandable)
3. "Step 3: Upload" — drag-and-drop area or [Browse Files]
4. After upload: validation in progress indicator

**On success:**
"Import complete — 16 positions, 34 dividend records imported. [View Portfolio →]"

**On failure:**
Error table: Row | Column | Error Description
[Download Error Report] button
"No records were imported. Correct the errors and re-upload."

### Primary Actions
- Download Template
- Upload File

### Entry Conditions
- User navigates from dashboard empty state or main navigation

### Exit Conditions
- Successful import → Portfolio Dashboard
- Failed import → remains on Import page with error table visible

---

## Screen: Registration Form

### Purpose
Get the user to their first experience as fast as possible. 3 required fields; no friction before value.

### User Goals
- Create an account in under 60 seconds

### Key Information Displayed

**Fields:**
- Email address
- Password (with strength indicator)
- Confirm password
- Default broker (dropdown; Maybank Investment, CIMB Invest, RHB Invest, AMBit, MooMoo, Rakuten Trade, Custom)

**Trust signal below form:** "Your data is stored securely. Cancel anytime during your 14-day free trial."

**Post-submit:** Redirect to Dashboard with email verification banner (non-blocking).

### Primary Actions
- Create Account (submit)

### Secondary Actions
- Log in (link: "Already have an account?")

### Entry Conditions
- Unauthenticated visitor on /register

### Exit Conditions
- Successful registration → Welcome screen → Dashboard
- Error → inline validation; remains on form

---

*End of Part 1 (Sections 1–6). Continue in BursaTrack-UX-Spec-Part2.md.*
