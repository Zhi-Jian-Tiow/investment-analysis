# BursaTrack — UX Design Specification
## Part 3 of 3: Gap Closure Addendum

> **Version:** 1.1 — Addendum to Parts 1 & 2
> **Date:** 2026-06-21
> **Purpose:** Closes all gaps identified in BursaTrack-UX-Spec-Review.md. All content here is **additive** — Parts 1 and 2 are unchanged.
> **Closes:** Review items R-001 through R-025 and selected RISK items
> **Review items addressed:** All 10 "Must Fix Before Visual Design" (R-001–R-010) + all 15 "Should Fix Before Engineering" (R-011–R-025)

---

# SECTION 3 ADDITIONS — USER FLOWS

*Augments Part 1, Section 3. Six new flows: Flow 9–14.*

---

## Flow 9 — Edit Position / Lot

*(Closes R-006 — missing Must Fix flow)*

### Entry Point
Position Detail → Lots Tab → ••• per-row menu → "Edit Lot"; or Dashboard → ••• row menu → "Edit Position"

### Trigger
User wants to correct a data entry error on an existing lot (wrong price, wrong share count, wrong broker, wrong date)

### Happy Path
```
1. User clicks "Edit" on a specific lot row
2. Edit Lot modal opens pre-populated with the existing values:
   - Shares, purchase price, purchase date, broker, category tag (if editing position-level fields)
3. Fee calculation panel shows current stored values
4. User edits one or more fields
5. Fee calculation panel updates live to reflect the changed values
6. User clicks "Save Changes"
7. System validates updated inputs (same rules as Add Lot)
   ↓ FAIL → Inline errors; modal stays open
   ↓ PASS
8. System recalculates: brokerage, clearing, stamp duty, all-in cost for this lot
9. System updates the lot record; writes previous values to AuditLog
10. Modal closes
11. POST-SAVE LOGIC (critical):
    - If shares value was changed:
      → A notification appears on the Dividends tab (next time user navigates there):
        "Your share count was updated from [old] to [new] shares.
         Existing dividend records were not changed — they reflect the shares
         that qualified at the time each dividend was paid.
         If you need to correct a dividend amount, edit that tranche directly."
      → This notification is dismissable; shown once per lot-edit event
    - If shares value was NOT changed:
      → Standard success toast: "Lot updated. Previous values saved to audit log."
12. Lots tab updates with new values; position-level aggregates (total shares,
    total cost, blended price) recalculate immediately
```

### Alternative Paths
- User changes broker from Maybank to MooMoo: brokerage fee recalculates to flat RM3; all-in cost updates; existing dividend records unaffected
- User edits position-level field only (category tag): no fee recalculation needed; simpler save path

### Failure Paths
- Share count changed to 0 → inline: "Shares must be at least 1"
- Future purchase date entered → inline: "Purchase date cannot be in the future"
- Server error on save → toast: "Save failed. Please try again." Modal stays open with the user's edits intact

### Exit State
Lots tab shows updated lot values; position aggregates updated; audit log written; user remains on Position Detail

---

## Flow 10 — Edit Dividend Tranche

*(Closes R-007 — missing Must Fix flow)*

### Entry Point
Position Detail → Dividends Tab → ••• per-row menu on a dividend tranche row → "Edit"

### Trigger
User wants to correct a logged dividend (wrong per-share amount, wrong qualifying shares, wrong dates)

### Happy Path
```
1. User clicks "Edit" on a dividend tranche row
2. Edit Dividend modal opens pre-populated with existing values:
   - Tranche label, per_share_amount, qualifying_shares, payment_date, ex_dividend_date, year
3. Live calculation preview shows current total:
   "Total received this tranche: RM X,XXX.XX (= RM0.20 × 5,000 qualifying shares)"
4. User edits one or more fields
5. Live preview updates immediately on every keystroke:
   - Editing per_share_amount: "Total = [new per share] × [existing qualifying_shares]"
   - Editing qualifying_shares: "Total = [existing per_share] × [new qualifying_shares]"
   - If qualifying_shares now differs from current position total:
     amber note: "Using [N] qualifying shares (differs from current position total of [M])"
6. User clicks "Save Changes"
7. System validates:
   - per_share_amount > 0
   - qualifying_shares ≥ 1 AND ≤ position_total_shares at time of edit
   - year valid (1990 – current year + 1)
   - tranche label is not already used by another tranche in the same year
     (unless it IS this tranche's own label — no self-conflict)
   ↓ FAIL → Inline errors; modal stays open
   ↓ PASS
8. System stores new qualifying_shares and recalculates stored total_amount
   = updated per_share_amount × updated qualifying_shares
9. System writes previous values to AuditLog
10. Modal closes
11. Success toast: "Dividend updated — new total: RM X,XXX.XX"
12. Dividends tab updates: tranche row shows new values; yield and income totals recalculate
```

### Alternative Paths
- User changes payment_date to a different year → year field auto-updates to match; user may override year manually
- User reduces qualifying_shares from 5,000 to 3,000 (correction): total_amount decreases; income and yield recalculate downward

### Failure Paths
- qualifying_shares > current position total → inline: "Qualifying shares cannot exceed your current total ([N] shares)"
- Tranche label conflict (e.g., user changes "2nd" to "1st" when a "1st" already exists) → inline: "Tranche label '1st' is already used for CIMB in 2026"

### Exit State
Dividends tab shows corrected tranche; position yield and income YTD updated; audit log written

---

## Flow 11 — Manual Price Override

*(Closes R-011 — standalone flow for previously described sub-flow)*

### Entry Point
Dashboard → amber ⚠ icon on a stale-priced position row (or the per-row ••• menu → "Update Price Manually")

### Trigger
Automated price refresh has failed for one or more positions; user wants to enter the current price from their broker app or a financial website

### Happy Path
```
1. User sees amber ⚠ icon next to the current price in the dashboard position row
2. User clicks/taps ⚠ (or selects "Update Price Manually" from ••• menu)
3. An inline price input field appears within the position row:
   "Enter current price: RM [____]" with a [Save] button
   The stale price is shown greyed-out beside the field: "Last known: RM 8.38 (Yesterday 9:30 AM)"
4. User types the current price (e.g., 8.42)
5. [Save] button activates as soon as a valid numeric value is entered
6. User clicks [Save]
7. System creates a PriceSnapshot record (source = "manual", timestamp = now)
8. Position row updates immediately:
   - Price column shows new price (no stale indicator)
   - Market value and Unrealised P&L recalculate
   - The per-row ⚠ is removed
9. If ALL previously-stale positions have been manually overridden:
   - The top dashboard banner dismisses automatically
10. Soft note beside the manually-entered price: "Manual · [time]"
    This note persists until the next successful automated refresh supersedes it
```

### Alternative Paths
- User ignores the stale indicator: dashboard functions with last-known prices; yield and cost figures are unaffected (they use stored cost, not live price); only market value and unrealised P&L are inaccurate
- Multiple stale positions: user can enter prices inline for each, one at a time; the banner counts down: "Price data unavailable for 3 stocks" → "2 stocks" → "1 stock" → banner dismisses

### Failure Paths
- User enters 0 or a negative number → inline: "Price must be greater than zero"
- User enters a price 50% higher or lower than the last known price → soft warning: "This price is significantly different from the last known price (RM 8.38). Are you sure?" with [Confirm] and [Cancel] — does not block submission

### Recovery
- On next successful automated refresh: manual override superseded silently; "Manual · [time]" note removed; standard "Last refreshed: Today HH:MM" shown

### Exit State
Position row shows manually entered price with "Manual" provenance note; dashboard stale count decrements

---

## Flow 12 — Subscription Renewal Failure / Grace Period

*(Closes R-012 — retention-critical path not previously specified)*

### Entry Point
Background: scheduled billing fails on the renewal date

### Trigger
Payment processor returns a failure on the user's renewal charge

### Happy Path (payment failure → user self-recovers)
```
BACKGROUND (server-side, no user action):
1. Renewal attempt fails on renewal_date
2. System sets account status = "payment_failed"
3. Grace period begins: 7 days from renewal_date (assumption — pending stakeholder confirmation)
4. System sends email: "Your BursaTrack payment failed. Update your payment method to keep access."
   Email includes a direct link to Account Settings → Subscription

IN-APP (user's next login within grace period):
5. Dashboard loads normally with full access
6. Non-intrusive amber banner at top:
   "Payment failed on [date]. Update your payment method to avoid losing access. [Update Now →]"
   Banner is persistent (not dismissable) during the grace period
7. User clicks "Update Now"
8. Redirected to Account Settings → Subscription
9. User updates payment method via the payment processor
10. On success: payment retried immediately; if successful:
    - Status returns to "active"
    - Renewal date updated
    - Banner dismissed
    - Toast: "Payment successful. Your subscription is active."

IF GRACE PERIOD EXPIRES (7 days without payment):
11. Status changes to "trial_expired" (same as trial expiry)
12. User's next login sees the Paywall screen (read-only access)
13. User can subscribe from the paywall as if they were a new subscriber
14. All portfolio data is preserved (BR-018)
```

### Alternative Paths
- Payment succeeds on automatic retry within grace period (before user takes action): banner dismisses; no user action required; email sent: "Payment received. Your subscription continues."
- User is already on the dashboard when grace period expires: on next page interaction, the paywall banner replaces the amber banner; write actions are blocked

### Failure Paths
- User updates payment method but new charge also fails → amber banner remains; retry window extends; email sent again

### Exit State
Account status = "active" (successful payment) or "trial_expired" (grace period expired without payment)

---

## Flow 13 — Email Verification Resend

*(Closes R-013 — self-service resend not previously defined as a flow)*

### Entry Point
Dashboard → email verification banner → "Resend" link; or Account Settings → Profile → "Resend verification email" (for users who navigate away from the banner)

### Trigger
User did not receive (or deleted) the verification email and wants to re-request it

### Happy Path
```
1. User sees the persistent (non-blocking) banner:
   "Please verify your email. Check your inbox. [Resend]"
2. User clicks "Resend"
3. System checks rate limit: has a verification email been sent within the last 5 minutes?
   ↓ YES → Do not send; show: "Email already sent — please wait a moment before requesting another.
             Check your spam folder." (inline message in banner)
   ↓ NO
4. System generates a new verification token (24-hour expiry; previous token invalidated)
5. System sends verification email to the registered address
6. Banner updates inline: "Verification email sent to [email]. Didn't receive it? Check spam."
7. "Resend" link becomes temporarily disabled for 5 minutes (prevents spam-click)
```

### Alternative Path
- User has already verified their email but the banner is still showing (race condition or stale UI):
  User clicks Resend → system detects email already verified → banner dismisses; no email sent

### Failure Path
- Email delivery service fails on resend → "We couldn't send the email right now. Please try again in a few minutes."

### Exit State
User remains on Dashboard; banner either shows "sent" confirmation or rate-limit message; full app access unaffected (verification is not a gate)

---

## Flow 14 — Custom Broker Add / Edit

*(Closes R-014 — referenced in IA but flow not previously defined)*

### Entry Point
Account Settings → Broker Settings → "Add Custom Broker" button; or Edit action on an existing custom broker row

### Trigger
User's broker is not in the pre-populated list, or the user wants to update their custom broker's fee rate

### Happy Path (Add)
```
1. User navigates to Account Settings → Broker Settings
2. Page shows:
   - System brokers (read-only, greyed out): Maybank Investment, CIMB Invest,
     RHB Invest, AMBit, MooMoo, Rakuten Trade
   - User's custom brokers (editable): any previously created
   - [+ Add Custom Broker] button
3. User clicks "+ Add Custom Broker"
4. Add Custom Broker modal opens with fields:
   - Broker Name (text, required, max 60 chars, must not duplicate system broker names)
   - Fee Type: [Percentage] or [Flat Fee] (radio or toggle)
   - If Percentage:
     · Brokerage Rate (%): e.g., 0.42
     · Minimum Fee (RM): e.g., 8.00
   - If Flat Fee:
     · Flat Fee Amount (RM): e.g., 7.00
5. User fills in details
6. Live preview shows example calculation:
   "Example: 1,000 shares at RM10.00 = RM10,000
    Brokerage: RM42.00 (0.42% of RM10,000)"
7. User clicks "Save"
8. Validation (VR-014 rules apply — rates 0–2%, minimums RM0–100)
   ↓ FAIL → Inline errors
   ↓ PASS
9. Custom broker saved; appears in all broker dropdowns for new lots
   (existing lots with this broker are unaffected)
10. Modal closes; success toast: "Custom broker '[Name]' added."
```

### Happy Path (Edit)
```
1. User clicks "Edit" on a custom broker row
2. Edit modal opens pre-populated with existing values
3. User changes fields; live preview updates
4. User saves → broker updated in dropdowns; existing lots that reference this broker
   do NOT automatically recalculate (user must edit those lots separately)
5. Post-save toast: "Broker updated. Lots already using this broker are not
   automatically recalculated — edit individual lots to apply the new rate."
```

### Happy Path (Deactivate)
```
1. User clicks "Deactivate" on a custom broker row
2. Confirmation: "Deactivating this broker removes it from the broker dropdown.
   Existing lots that used this broker will retain their calculated fees."
3. User confirms → broker is marked inactive; removed from dropdown for new entries;
   existing lots display broker name with "(inactive)" label
```

### Failure Paths
- Broker name duplicates a system broker → inline: "This broker name already exists. Choose a different name."
- Rate out of range → per VR-014 error messages

### Exit State
Broker Settings page shows updated broker list; custom broker available (or removed) from all broker dropdowns

---

# SECTION 4 ADDITIONS — INFORMATION ARCHITECTURE

*Augments Part 1, Section 4. Adds URL routing structure.*

*(Closes R-005 — Must Fix for engineering handoff)*

## URL Routing Structure

### Routing Strategy
- **Tabs within Position Detail** use URL routes (not in-page state). This enables deep-linking, shareable URLs, and correct browser back-button behaviour.
- **Modal overlays** (Add Position, Add Lot, Add Dividend, Edit forms) do NOT change the URL. The underlying page URL is retained. Pressing browser back while a modal is open closes the modal — it does not navigate to the previous route. This is enforced via history manipulation (`history.pushState` on modal open; `history.back` on modal close triggers dismiss rather than navigation).
- **Settings sub-pages** use URL routes (nested under `/settings`).

### Route Map

```
/                         → Redirect to /login (unauthenticated) or /dashboard (authenticated)
/register                 → Registration Form
/login                    → Login Form
/forgot-password          → Forgot Password Form
/reset-password/:token    → Reset Password Form (token validated on load)
/verify-email/:token      → Email Verification (background action; redirect to /dashboard with banner)

/dashboard                → Dashboard (portfolio overview)

/positions/:id            → Redirect to /positions/:id/lots (default tab)
/positions/:id/lots       → Position Detail — Lots Tab
/positions/:id/dividends  → Position Detail — Dividends Tab
/positions/:id/sell       → Position Detail — Sell Calculator Tab

/calendar                 → Dividend Calendar

/import                   → Import Page
/import/result            → Import Result (success or error report; ephemeral; redirect to /import if accessed directly with no result)

/settings                 → Redirect to /settings/profile
/settings/profile         → Account Settings — Profile
/settings/subscription    → Account Settings — Subscription
/settings/brokers         → Account Settings — Broker Settings
/settings/export          → Account Settings — Export Data (PDPA)
/settings/delete-account  → Account Settings — Delete Account

/paywall                  → Paywall Screen (also rendered inline over /dashboard for trial-expired users)
```

### Back-Button Behaviour Rules

| Scenario | Back-Button Result |
|----------|--------------------|
| Modal open over /dashboard | Modal closes; /dashboard remains visible |
| Modal open over /positions/:id/dividends | Modal closes; dividends tab remains visible |
| /positions/:id/lots → navigate Back | Returns to /dashboard |
| /settings/profile → navigate Back | Returns to /settings/profile (or previous page in history) |
| /import/result → navigate Back | Returns to /import |
| Paywall overlay → navigate Back | If user arrived from a protected page, returns to /dashboard |

### Deep-Link Behaviour

- `/positions/:id/dividends` can be deep-linked or bookmarked; loads the dividends tab directly
- `/positions/:id/sell` can be deep-linked (useful for David bookmarking his most-traded positions)
- Import result (`/import/result`) is ephemeral and cannot be deep-linked

---

# SECTION 5 ADDITIONS — SCREEN INVENTORY

*Augments Part 1, Section 5. Adds missing screens.*

*(Closes R-002, R-003; partial R-001)*

## Additional Screens — Unauthenticated

| Screen Name | Purpose | Primary Actions | Associated Flow |
|-------------|---------|-----------------|-----------------|
| **Welcome / First Session Screen** | Bridge between registration success and first portfolio action. The user's first impression of the product's value proposition. | Add First Position, Import from CSV | Flow 1 |
| **Email Verification Success Screen** | Confirms email verification after user clicks the link | Return to Dashboard | Flow 13 |
| **Subscription Success Screen** | Confirms successful payment and subscription activation | View Portfolio (full access) | Flow 12 |

## Additional Screens — Authenticated

| Screen Name | Purpose | Primary Actions | Associated Flow |
|-------------|---------|-----------------|-----------------|
| **Paywall Screen** | Conversion screen for trial-expired users; the business's most important screen | Subscribe, View Portfolio (read-only) | Flow 12 |
| **Account Settings — Profile** | Manage email address, default broker, password change link | Edit Profile, Change Password | Flow 9 (edit broker) |
| **Account Settings — Subscription** | View and manage billing | Cancel Subscription, Update Payment Method | Flow 12 |
| **Account Settings — Broker Settings** | Manage custom brokers | Add Custom Broker, Edit, Deactivate | Flow 14 |
| **Account Settings — Export Data** | PDPA data export | Download My Data (ZIP) | FR-018 |
| **Account Settings — Delete Account** | PDPA account deletion with 30-day grace | Initiate Deletion | Flow 8 |

## Additional States

| Screen | State | Description |
|--------|-------|-------------|
| Dashboard | Payment Failed (Grace Period) | Amber banner: "Payment failed on [date]. Update your payment method to avoid losing access." Amber dot on Account nav icon. Full write access retained during grace period. |
| Account Settings — Subscription | Payment Failed State | Prominent alert at top: "Your last payment failed. [Update Payment Method →]" |

---

# SECTION 6 ADDITIONS — SCREEN REQUIREMENTS

*Augments Part 1, Section 6. Adds requirements for all previously missing screens.*

*(Closes R-001, R-002, R-003, R-004)*

---

## Screen: Login Form

### Purpose
Authenticate a returning user. The second most-visited screen in the product (daily for all personas). Must be frictionless on mobile and fast on desktop.

### User Goals
- Ahmad: log in in under 10 seconds before the trading day starts
- Farah: log in on mobile without mistyping her password

### Key Information Displayed
- Email input
- Password input (with show/hide toggle)
- "Forgot password?" link (below password field)
- "Log in" button
- "Don't have an account? Start your free trial" link
- On account lockout: amber inline notice: "Too many failed attempts. Try again in [X] minutes."

### Primary Actions
- Submit login form

### Secondary Actions
- Navigate to Forgot Password form
- Navigate to Registration

### Entry Conditions
- Unauthenticated user accesses any protected route (redirected here) OR navigates to /login directly
- User who just reset their password (arrives with "Password updated successfully" banner)

### Exit Conditions
- Successful login → /dashboard (or the originally requested protected route)
- "Forgot password?" → /forgot-password
- "Start free trial" → /register

### State Definitions
| State | Description |
|-------|-------------|
| Default | Clean form; no pre-populated values (unless browser autofill) |
| Loading (Submitting) | "Log in" button shows spinner + "Logging in…"; all fields disabled; lasts < 2 seconds typically |
| Error — Wrong Password | Inline below the password field: "Email or password is incorrect." Failed attempt counter increments. |
| Error — Account Locked | Inline amber banner: "Too many failed attempts. Please wait [N] minutes." Login button disabled until lockout expires. |
| Error — Network Failure | If the API call times out: "Something went wrong. Please check your connection and try again." Toast — not inline (the error is not field-specific). |
| Error — Account Pending Deletion | Inline: "Your account deletion is in progress. [Cancel deletion →] or [Contact support]." |

---

## Screen: Forgot Password Form

### Purpose
Allow a user to initiate password recovery. Must be usable even if the user is uncertain whether they have an account (enumeration-safe response regardless).

### User Goals
- Recover account access without contacting support

### Key Information Displayed
- Email input
- "Send Reset Link" button
- "Remember your password? Log in" link
- Post-submit confirmation message (identical for all email values): "If an account with that email exists, a reset link has been sent. Check your inbox and spam folder."
- "Didn't receive it? [Resend]" link (appears 60 seconds after submit)

### Primary Actions
- Submit email to receive reset link

### Secondary Actions
- Navigate back to Login

### Entry Conditions
- User clicks "Forgot password?" on the Login form

### Exit Conditions
- Submit → same page with confirmation message (no redirect — user waits for email)
- "Log in" link → /login

### State Definitions
| State | Description |
|-------|-------------|
| Default | Email input empty; "Send Reset Link" button |
| Loading | Button shows spinner + "Sending…"; field disabled |
| Confirmation | Form replaced by: "If an account with that email exists, a reset link has been sent." + countdown to Resend link appearance (60 seconds) |
| Resend Available | "Didn't receive it? [Resend]" link appears after 60 seconds |
| Rate Limited | If user submits multiple times: "Please wait before requesting another link." |

---

## Screen: Reset Password Form

### Purpose
Allow a user to set a new password after clicking the email link. Token-gated: the page validates the token on load before showing the form.

### User Goals
- Set a new, memorable password and regain account access

### Key Information Displayed
- New password input (with strength indicator)
- Confirm password input (with match tick)
- "Set New Password" button
- Password requirements visible below the field: "At least 8 characters, one uppercase letter, one digit"

### Primary Actions
- Submit new password

### Entry Conditions
- User arrives via the link in the password reset email (URL: `/reset-password/:token`)
- Token is validated on page load (server-side check: exists, unused, not expired)

### Exit Conditions
- Successful reset → /login with: "Password updated successfully. Please log in."
- Token expired → replace form with: "This link has expired. [Request a new link?]" → navigates to /forgot-password
- Token already used → replace form with: "This link has already been used. If you didn't reset your password, contact support."

### State Definitions
| State | Description |
|-------|-------------|
| Loading (Token Validation) | Skeleton or spinner while token is validated server-side on page load |
| Valid Token — Default | Password + confirm fields rendered; form ready |
| Live Validation | Strength indicator updates on typing; confirm match tick appears when both fields match |
| Loading (Submitting) | "Set New Password" button shows spinner + "Saving…"; all fields disabled |
| Success | Redirect to /login with success banner |
| Error — Expired Token | Form replaced by expiry message + link to /forgot-password |
| Error — Used Token | Form replaced by used-token message |

---

## Screen: Welcome / First Session Screen

### Purpose
Bridge the gap between registration success and first productive action. This is the user's first impression of BursaTrack's value. The screen must communicate what to do next without requiring the user to read documentation. Shown **once**, immediately after registration.

### User Goals
- Ahmad: know he can import his 16 positions in one step
- Farah: know she can start adding positions immediately
- David: know the import CSV path is available

### Key Information Displayed
- Brief welcome headline: "Your portfolio is ready. Let's add your first holding."
- Two clear paths:
  1. **[Import from CSV →]** (primary visual weight): "Have existing positions? Import them all at once." → navigates to /import
  2. **[Add your first position →]** (secondary but prominent): "Start fresh and add positions one by one." → opens Add Position modal over /dashboard
- Small print below: "Not sure? You can do both — import your positions and add more manually anytime."
- A non-blocking email verification reminder chip at the top (if email not yet verified): "Verify your email when you get a chance. [Resend →]"

### Primary Actions
- Import from CSV → navigates to /import
- Add First Position → navigates to /dashboard and opens Add Position modal

### Entry Conditions
- User completes registration successfully (first login only — session flag `first_login = true`)
- NOT shown on subsequent logins

### Exit Conditions
- Either CTA clicked → user proceeds to chosen path
- User closes the tab / navigates away → on return, lands on /dashboard (welcome screen not shown again)
- Timeout (user leaves screen idle for 60 seconds) → no forced redirect; screen persists

### State Definitions
| State | Description |
|-------|-------------|
| Default | Two-CTA layout as described above |
| With email verification chip | Chip visible at top if email not yet verified |

---

## Screen: Paywall Screen

### Purpose
Convert a trial-expired user to a paying subscriber. This is the single most important screen for the business. It must communicate value (what they built), show what they'll lose (write access), and make subscribing as frictionless as possible. It must NOT be punitive or alarming — the user's data is safe.

### User Goals
- Understand what happened (trial ended)
- See their portfolio data is still there (reassurance)
- Subscribe quickly if motivated

### Key Information Displayed
- **Heading:** "Your free trial has ended."
- **Reassurance:** "Your portfolio is safe. All [N] positions and [M] dividend records are preserved."
- **Value summary (what they built):** portfolio yield, position count, YTD income — visible but greyed-out / read-only behind the paywall card
- **Plan card:** subscription price (e.g., RM20/month), feature list (bullet: "Unlimited positions," "Daily price refresh," "True yield calculations," "CSV import"), CTA: **[Subscribe — RM20/month →]**
- **Secondary path:** "Continue viewing in read-only mode →" (text link, low visual weight — the user can browse but not write)
- **Trial restart not available** — do not show "start another trial"

### Primary Actions
- Subscribe (redirects to payment processor)

### Secondary Actions
- Continue in read-only mode → /dashboard (paywall dismissed for this session; shown again on next write action)

### Entry Conditions
- Account status = `trial_expired` OR `payment_failed` (grace period expired)
- Reached via: login after trial expiry; or clicking any write action from a trial-expired dashboard

### Exit Conditions
- Subscribe → payment processor → return → /dashboard with full access
- Read-only → /dashboard (write actions still blocked; per-action paywall prompt replaces the full-page paywall)

### State Definitions
| State | Description |
|-------|-------------|
| Trial Expired | Standard paywall as described above |
| Payment Failed (Grace Period Expired) | Same paywall; headline: "Your subscription has lapsed." Reassurance and CTA unchanged. |
| Loading (After Payment Return) | "Activating your subscription…" spinner; account status polling |

---

## Screen: Account Settings — Profile

### Purpose
Allow a user to update their email address, default broker, and navigate to password change. The lowest-urgency settings screen — accessed infrequently.

### User Goals
- Update default broker if they switch brokerages
- Change email address (triggers reverification)

### Key Information Displayed
- Current email address (read-only display; [Change Email] link adjacent)
- Default Broker dropdown (editable; shows current value; changes apply to new lots only)
- Password section: "••••••••" (masked) with [Change Password] link → navigates to a change-password flow (similar to reset, but requires current password first)
- Account created date (read-only)
- [Save Changes] button (active only when at least one field has been modified)

### Primary Actions
- Save Profile Changes

### Secondary Actions
- Change Email → opens Change Email modal (sends verification to new address)
- Change Password → opens Change Password modal

### Entry Conditions
- Authenticated user navigates to /settings/profile

### Exit Conditions
- Save → profile updated; success toast; remains on page
- Navigate away → unsaved changes prompt: "You have unsaved changes. Leave anyway?"

### State Definitions
| State | Description |
|-------|-------------|
| Default | All fields showing current values; [Save Changes] button disabled |
| Editing | [Save Changes] button enabled as soon as any field is modified |
| Loading (Submitting) | Button spinner + "Saving…" |
| Success | Toast: "Profile updated." Page refreshes with new values. |
| Error | Inline error if email already in use or network failure |

---

## Screen: Account Settings — Subscription

### Purpose
Show the user's current plan, next renewal, and allow them to cancel or update their payment method.

### User Goals
- Know when they'll be charged next
- Cancel without feeling punished (data retained)
- Update a failing payment method quickly

### Key Information Displayed
- Current Plan: "[Plan Name] — RM[price]/month"
- Status: Active / Trial / Trial Expired / Payment Failed
- Next Renewal: [date] (or "Cancelled — access ends [date]")
- [Cancel Subscription] link (secondary, low visual weight — not a prominent button)
- [Update Payment Method] button (shown when status = payment_failed or as a secondary action otherwise)
- Billing history: last 3 invoices (date, amount, status) — "Paid" or "Failed"

### Primary Actions (Active subscription)
- Cancel Subscription → confirmation dialog: "Your subscription will end on [date]. Your portfolio data is preserved. Continue?" [Confirm Cancel] [Keep Subscription]

### Primary Actions (Trial Expired / Lapsed)
- Subscribe → /paywall or direct payment processor

### Secondary Actions
- Update Payment Method (always available)

### Entry Conditions
- Authenticated user navigates to /settings/subscription

### Exit Conditions
- Cancel confirmed → remains on page; status shows "Cancellation scheduled — access until [date]"
- Subscribe → payment flow

### State Definitions
| State | Description |
|-------|-------------|
| Active | Plan, renewal date, Cancel link, Update payment link, billing history |
| Trial Active | "Free trial — [N] days remaining." [Subscribe now] CTA |
| Trial Expired | Paywall CTA; option to subscribe |
| Cancellation Scheduled | "Subscription cancels on [date]. Access until then." [Undo Cancellation] link |
| Payment Failed | Amber alert: "Your last payment failed on [date]. [Update Payment Method →]" |

---

## Screen: Account Settings — Broker Settings

### Purpose
View system-provided brokers and manage user-created custom brokers. The entry point for Flow 14.

### User Goals
- Add a custom broker with the correct fee rate
- Deactivate a custom broker no longer in use

### Key Information Displayed
- **System Brokers section** (read-only, non-interactive):
  A table: Broker Name | Fee Type | Rate / Flat Fee | Min Fee
  All greyed out with a note: "System brokers cannot be edited."
  Includes Rakuten Trade note: "RM7 flat (V1 simplification — tier-based pricing not yet applied ⓘ)"
  — ⓘ tooltip: "Rakuten Trade uses a tiered fee structure. BursaTrack currently applies a flat RM7. Per-tier calculation will be added in a future update."
- **Custom Brokers section**:
  Table: Broker Name | Fee Type | Rate/Fee | Status (Active/Inactive) | Actions (Edit / Deactivate)
  [+ Add Custom Broker] button at bottom of the section

### Primary Actions
- Add Custom Broker → opens Add Custom Broker modal (Flow 14)

### Secondary Actions
- Edit custom broker row
- Deactivate custom broker row (with confirmation)

### Entry Conditions
- Authenticated user navigates to /settings/brokers

### Exit Conditions
- Back/navigate → /settings/profile or previous page

### State Definitions
| State | Description |
|-------|-------------|
| No Custom Brokers | Empty state below custom section: "No custom brokers yet. Add one if your broker isn't listed." |
| Default (has custom brokers) | List of custom brokers with edit/deactivate actions |
| Success after add | Toast: "Custom broker added." |
| Success after deactivate | Toast: "Broker deactivated. Existing lots are unchanged." |

---

## Screen: Account Settings — Export Data (PDPA)

### Purpose
Allow a user to download all their personal and portfolio data in compliance with the Malaysian PDPA right of access. Simple, reassuring, functional.

### User Goals
- Download all data BursaTrack holds about them

### Key Information Displayed
- Heading: "Download Your Data"
- Brief PDPA context: "Under the Malaysian Personal Data Protection Act (PDPA), you can request a copy of all data we hold about you."
- What's included (list): account details, all positions, all lots with fee breakdowns, all dividend records (including qualifying shares), all manual price overrides, audit log of all changes
- File format: "ZIP archive containing CSV files, one per data type"
- Estimated size note: "Typically 1–5 KB for most portfolios"
- [Download My Data] button
- Last export note (if applicable): "Last exported: [date]"

### Primary Actions
- Download My Data → generates ZIP and initiates browser download

### Entry Conditions
- Any authenticated user (including trial-expired and pending-deletion)

### Exit Conditions
- After download: success toast: "Your data export has started. Check your Downloads folder." Remains on page.

### State Definitions
| State | Description |
|-------|-------------|
| Default | Page as described; [Download] button active |
| Loading (Generating) | Button shows spinner + "Preparing your data…"; typically < 5 seconds |
| Success | Toast: "Export ready. Check your Downloads folder." Button resets to default. "Last exported: [date/time]" appears below button. |
| Error | Toast: "Export failed. Please try again." |

---

## Screen: Account Settings — Delete Account

### Purpose
Allow a user to initiate permanent account deletion per PDPA right of erasure. The two-step confirmation flow (Flow 8) is defined here as screen requirements. The design must be serious without being alarming — the 30-day grace period gives the user complete safety.

### User Goals
- Know exactly what will be deleted
- Have a clear cancellation path if they change their mind
- Download their data before deleting (the pre-delete export prompt)

### Key Information Displayed
- **Danger Zone visual separation** (distinct border, warning colour band)
- Heading: "Delete Your Account"
- Explanation: "Permanently delete your account and all associated data. This process has a 30-day cancellation window."
- [Delete My Account] button (destructive style — red outlined, not filled)

**On click — Step 1 (Data Export Offer):**
- "Before you go — would you like to download your data?" (non-full-screen overlay or inline step)
- [Download My Data] → executes FR-018 export; on completion, Step 2 becomes available
- [Skip and Continue →] → proceeds to Step 2

**On Step 2 (Type-to-Confirm):**
- "This will permanently delete your account and all data in 30 days. You can cancel within 30 days by clicking the link in the confirmation email."
- Confirmation input: "Type DELETE to confirm:"
- [Confirm Deletion] button — disabled until the user has typed "DELETE" exactly
- [Cancel] text link (abandons the deletion flow; returns to Settings)

### Primary Actions
- Confirm Deletion (only after typing DELETE)

### Secondary Actions
- Download My Data (step 1 optional)
- Cancel / abandon (any time before confirming)

### Entry Conditions
- Authenticated user navigates to /settings/delete-account

### Exit Conditions
- Deletion confirmed → dedicated confirmation page: "Account deletion requested. Your data will be deleted on [date + 30 days]. A confirmation email has been sent with a cancellation link." → session ends; user logged out.
- Cancelled at any step → returns to /settings

### State Definitions
| State | Description |
|-------|-------------|
| Default | [Delete My Account] button in danger zone section |
| Step 1 Overlay | Data export offer with two paths |
| Step 2 — Type to Confirm | Confirmation input; [Confirm Deletion] disabled until "DELETE" typed |
| Typing | [Confirm Deletion] enables as user types "DELETE" exactly (case-sensitive) |
| Loading (Submitting) | Button spinner + "Processing…" |
| Confirmed | Redirect to confirmation screen; user logged out |

---

# SECTION 7 ADDITIONS — INTERACTION SPECIFICATIONS

*Augments Part 2, Section 7. Closes R-008, R-021, R-023, R-024, R-025.*

---

## Currency Input Formatting

*(Closes R-008 — Must Fix)*

**Specification for all price and MYR amount input fields** (purchase price, flat fee, minimum fee, dividend per share, manual price override):

| Behaviour | Specification |
|-----------|---------------|
| Field prefix | "RM" displayed as a static prefix label *outside* the input (not inside). The user types a number only; "RM" is decorative/contextual and must not be part of the input value. |
| Decimal separator | Accept both `.` (dot) and `,` (comma) during typing. On blur (when user leaves the field), normalize to dot-decimal. |
| Example: user types "8,38" | On blur: normalizes to "8.38" |
| Example: user types "8,380" | Ambiguous — treated as a Malaysian-style thousands separator: "8,380.00" would be the normalized result. Implementation decision: on blur, if the comma-separated value ≥ 1000, treat the comma as a thousands separator; if < 1000, treat as decimal. |
| Display precision during typing | No forced precision while the user is typing (do not auto-insert ".00" on every keystroke) |
| Display precision on blur | **Purchase price:** round to 4dp display (e.g., "8.3800"). **MYR amounts (fees, flat fees, minimums):** round to 2dp display (e.g., "8.00"). **Dividend per share:** round to 4dp display; up to 6dp accepted and stored. |
| Invalid characters | Non-numeric characters (letters, special chars except `.` and `,`) are rejected on input |
| Negative values | Blocked; do not allow `-` character in price/amount fields |
| Zero | Accepted during typing (user may type "0" then continue); blocked on blur if zero is not valid for the field (field shows inline error) |
| Max value warning | If value exceeds a soft threshold (e.g., purchase price > RM99,999), show a soft warning on blur: "This price seems unusually high. Please verify." — does not block submission |

---

## Tranche Label Assignment

*(Closes R-021 — Should Fix)*

**Clarification for the Add/Edit Dividend Form tranche label field:**

- The tranche label is a **user-editable dropdown** containing all unused labels from: 1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th.
- The system **suggests** the next sequential unused label (e.g., if 1st and 2nd exist, the dropdown defaults to "3rd").
- The user **may select any unused label** from the dropdown — they are not locked to the next sequential label. This handles the case where a user deleted the "1st" tranche and wants to re-add a replacement labelled "1st."
- Already-used labels for this position in this year are shown in the dropdown as **greyed-out and unselectable**, with a note: "Already logged."
- **Edit mode:** The tranche's own current label is always available in the dropdown (it is not greyed out — a tranche can be re-saved with the same label it already has).

---

## Sell Calculator Table — Scroll and Density

*(Closes R-023 — Should Fix)*

**Specification for the scenario table in the Sell Calculator Tab:**

- The table is **long-scroll** (no pagination). Typical auto-generated row count is approximately 30–35 rows (5 fine-grained + 28 broad steps). This is manageable as a single scrollable table.
- The table is not virtualized for V1 (maximum rows is bounded and predictable).
- **Desktop:** full table visible; the break-even row is auto-scrolled into the visible viewport on initial render (using `scrollIntoView` with smooth behaviour).
- **Mobile:** the table container is horizontally scrollable with the **"Sell Price" column pinned** (position: sticky, left: 0). Remaining columns (Gross Proceeds, Brokerage, Clearing, Stamp, Net Proceeds, P/L) scroll horizontally. Column headers are also sticky vertically.
- **Custom price row:** when the user enters a custom price, a new row is prepended at the top of the table and the table scrolls to it.
- **Row limit:** a maximum of 50 rows (auto-generated + custom) is enforced. If the auto-generation range would exceed 50 rows, the step size is automatically increased to keep within the limit.

---

## Form Submit on Enter Key

*(Closes R-024 — Should Fix)*

**Specification for keyboard Enter key behaviour in forms:**

| Form | Enter Key Behaviour |
|------|---------------------|
| Login Form | Enter on either field submits the form |
| Registration Form | Enter on any field submits the form (after all fields are filled) |
| Forgot Password Form | Enter submits the form |
| Reset Password Form | Enter on either field submits if both are filled and valid |
| Add Position / Add Lot Modal | Enter does NOT auto-submit. The form has multiple fields and an autocomplete dropdown that uses Enter for selection. Auto-submit on Enter is disabled to prevent accidental submission mid-form. The [Save Position] button must be clicked explicitly. |
| Add / Edit Dividend Modal | Same as Add Position — Enter is disabled for form submit; used for autocomplete only. |
| Custom Broker Modal | Enter does NOT auto-submit (fee type toggle could be Enter-activated incorrectly). |
| Manual Price Override (inline) | Enter submits the price override immediately (single-field entry — Enter-to-submit is expected behaviour). |
| Edit Lot / Edit Dividend Modal | Same policy as Add Position — no Enter-to-submit. |
| Confirmation Dialogs (type DELETE) | Enter submits if the field contains exactly "DELETE." |
| Settings — Profile | Enter on any single field does NOT submit. Explicit [Save Changes] button click required. |

---

## Mobile Numeric Keyboard Triggers

*(Closes R-025 — Should Fix)*

**All price, amount, share count, and numeric fields must trigger the numeric keyboard on mobile devices** by applying the correct HTML attribute:

| Field Type | Attribute to Use | Result |
|------------|-----------------|--------|
| Purchase price, dividend per share, brokerage rate, flat fee, minimum fee, manual override price | `inputmode="decimal"` | Numeric keyboard with decimal point on iOS and Android |
| Share count, qualifying shares | `inputmode="numeric"` | Numeric keyboard without decimal (integers only) |
| Year field | `inputmode="numeric"` | Numeric keyboard |
| Email field | `type="email"` | Email-optimised keyboard (@ key visible) |
| Password field | `type="password"` | Standard keyboard (masked) |

**Note:** Do NOT use `type="number"` for price fields. This type introduces browser-native spin buttons (increment/decrement arrows) and removes leading zeros, which creates inconsistent UX across browsers. Use `type="text"` with `inputmode="decimal"` instead.

---

# SECTION 8 ADDITIONS — STATE DEFINITIONS

*Augments Part 2, Section 8. Closes R-010, R-016, R-020.*

---

## Position Detail — Lots Tab: Missing States

*(Closes R-010 — Must Fix)*

### Loading State
- Triggered when the Lots tab is first navigated to and the position's lot data is being fetched
- Display: a skeleton loader showing 2–3 placeholder rows (shimmer animation) in the lots table area
- The Position header (stock name, total shares, all-in cost) is shown from cached position data during load; only the per-lot table shows the skeleton
- `aria-busy="true"` applied to the lots table container; visually hidden text: "Loading lot details..."

### Error State
- Triggered if the lot data API call fails (network error, 5xx)
- Display: inline error banner within the Lots tab area: "Unable to load lots. [Retry →]"
- [Retry] link re-triggers the API call without reloading the page
- The Position header remains visible (showing cached aggregate data)
- The [Add Lot] button is disabled during the error state

---

## Position Detail — Dividends Tab: Missing States

*(Closes R-010 — Must Fix)*

### Loading State
- Same pattern as Lots Tab: skeleton rows in the tranche table; position header visible from cache
- `aria-busy="true"` on the dividends table container; visually hidden: "Loading dividend records..."

### Error State
- Inline banner: "Unable to load dividend records. [Retry →]"
- [Add Dividend Tranche] button disabled during error
- Yield summary (shown in the position header) may display the last-known cached value with a stale indicator: "Yield may be outdated — [Refresh →]"

---

## Login Form: Missing States

*(Closes R-020 — Should Fix)*

### Loading State (Submitting)
- Triggered immediately when user clicks "Log in" and the API call is in flight
- "Log in" button text replaced with spinner + "Logging in…"
- Both input fields disabled
- Duration: typically < 1 second; if it takes > 3 seconds, show: "Taking longer than usual…" below the button (does not cancel the request)

### Network Error State
- Triggered if the authentication API call times out or returns a 5xx error (distinct from a 401 wrong-password response)
- The error is NOT shown inline with the password field (it is not the user's fault)
- A toast notification: "Connection problem. Please check your internet and try again."
- The "Log in" button re-enables; the user may retry
- The form fields retain the user's typed values (do not clear on network error)

---

## Dashboard: Last Position Deleted → Empty State Transition

*(Closes R-016 — Should Fix)*

### Specification
When the user deletes their last active position:

1. The 5-second undo toast appears (standard behaviour for all deletions): "[Stock name] deleted. [Undo — 5s]"
2. While the undo window is open: the position row fades out but the portfolio summary header remains (showing RM0 values)
3. If the user does NOT click Undo within 5 seconds: the dashboard transitions to the **Empty State**:
   - Portfolio summary header: hidden (or shows dashes for all values — designer decision, flagged as open question OQ-D09)
   - Position table area: replaced by the standard Empty State layout ("Welcome back. Add your first position or import from CSV.")
   - The Empty State uses the same copy as the first-session empty state, but without the "Welcome" header — the user is a returning user, not a new one
4. If the user clicks Undo within 5 seconds: the position row reappears; the portfolio summary recalculates; dashboard returns to the loaded state

**Dividend Calendar side-effect:** When the last position is deleted, the Dividend Calendar transitions to its empty state on the next render. Calendar entries from the deleted position are removed. This does not require a separate notification.

---

## Session Expiry Mid-View (Enhancement)

*(Closes R-015 — Should Fix — supplements existing EX-010 spec in Part 2)*

### Session Expiry With Unsaved Form Data

**When the session expires while a form modal is open:**

1. The user's next form submission (clicking Save) returns a 401 from the server
2. The modal does NOT close
3. A banner appears within the modal: "Your session has expired. [Log in to save →]"
4. The form field values are preserved in the modal (the user has not lost their typed data — it is still visible)
5. Clicking "Log in to save →":
   - Opens the login form in a new tab OR triggers a login overlay (implementation decision — flagged as open question OQ-D10)
   - After successful re-authentication, the user is returned to the original tab/page
   - The modal is re-opened if the session token was refreshed (page has not reloaded)
6. If the page must reload after re-login: **the form data is lost**. This is the accepted V1 behaviour for this edge case. The notification must warn: "After logging in, you'll need to re-enter your data."

**Field-level sessionStorage preservation (V1.1 aspiration):** Preserving draft form data in `sessionStorage` before the modal opens is a V1.1 enhancement. At V1, the user is warned of potential data loss and must re-enter if the page reloads.

---

# SECTION 9 ADDITIONS — ACCESSIBILITY REQUIREMENTS

*Augments Part 2, Section 9. Closes R-017, R-018, R-019 and RISK-AC02.*

---

## Error Message Association (aria-describedby)

*(Closes R-017 — Should Fix)*

All inline form field errors must be associated with their input via `aria-describedby` so that screen readers announce both the field label and the error message when the field receives focus.

**Implementation pattern:**
```html
<!-- Field with error -->
<label for="shares">Number of shares</label>
<input
  id="shares"
  type="text"
  inputmode="numeric"
  aria-describedby="shares-error"
  aria-invalid="true"
/>
<span id="shares-error" role="alert">
  Number of shares must be greater than zero
</span>
```

**Rules:**
- `aria-invalid="true"` must be set on the input when the field is in an error state; removed when the error clears
- The error `<span>` should use `role="alert"` to announce immediately when injected into the DOM
- Error IDs follow the pattern: `[field-id]-error`
- When multiple errors exist simultaneously (on form submit), each field's error is independently associated — do not combine all errors into one region
- Success state: `aria-invalid` removed; `aria-describedby` may be removed or pointed to a helper text `<span>` if one exists

---

## Skip Navigation Link

*(Closes R-018 — Should Fix)*

A "Skip to main content" link must be the **first focusable element on every page** of the authenticated application. It is visually hidden until it receives keyboard focus, at which point it becomes visible.

**Implementation pattern:**
```html
<a href="#main-content" class="skip-link">Skip to main content</a>
<!-- ... header navigation ... -->
<main id="main-content" tabindex="-1">
  <!-- page content -->
</main>
```

**Visual treatment when focused:** The skip link appears as a high-contrast button at the top-left of the viewport (background: product primary colour; text: white; padding 12px 16px). It disappears on blur.

**What "main content" means per screen:**
- Dashboard: the portfolio summary header (`#main-content` placed before the summary row)
- Position Detail: the tab strip (`#main-content` placed before the tab list)
- Import Page: the step-by-step import guide (`#main-content` placed before "Step 1")
- Settings pages: the first settings section heading

---

## Screen Reader Loading State Announcements

*(Closes R-019 — Should Fix)*

Skeleton loaders are purely visual. Without additional markup, screen readers receive no information during loading states.

**Implementation for all loading states:**

1. Add `aria-busy="true"` to the container element when loading begins; remove when content is ready
2. Include a visually hidden live region that announces loading status:

```html
<div aria-live="polite" aria-atomic="true" class="sr-only">
  <!-- Populated dynamically: "Loading portfolio data..." on start; empty string when done -->
</div>
```

3. When loading completes, the live region text is cleared (set to empty string) — the content itself is then announced naturally by the screen reader as the user navigates

**Screen-specific announcements:**

| Screen | Loading Announcement | Completion |
|--------|---------------------|------------|
| Dashboard (initial load) | "Loading portfolio data…" | Clear (table is announced on navigation) |
| Position Detail — Lots Tab | "Loading lot details…" | Clear |
| Position Detail — Dividends Tab | "Loading dividend records…" | Clear |
| Import Page (validation) | "Validating your data…" | "Validation complete. [N] errors found." or "Validation successful." |
| CSV export (generating) | "Preparing your data export…" | "Export ready." |

---

## ARIA Tab Roles for Position Detail Tab Strip

*(Closes RISK-AC02 — Should Fix)*

The Position Detail tab strip (Lots / Dividends / Sell Calculator) must use the ARIA tab pattern to be keyboard-navigable and screen-reader-accessible.

**Required markup pattern:**
```html
<div role="tablist" aria-label="Position detail sections">
  <button
    role="tab"
    id="tab-lots"
    aria-selected="true"
    aria-controls="panel-lots"
  >Lots</button>
  <button
    role="tab"
    id="tab-dividends"
    aria-selected="false"
    aria-controls="panel-dividends"
    tabindex="-1"
  >Dividends</button>
  <button
    role="tab"
    id="tab-sell"
    aria-selected="false"
    aria-controls="panel-sell"
    tabindex="-1"
  >Sell Calculator</button>
</div>

<div role="tabpanel" id="panel-lots" aria-labelledby="tab-lots">
  <!-- Lots content -->
</div>
<!-- Other panels hidden via aria-hidden or display:none -->
```

**Keyboard navigation within the tab strip:**
- Tab key: moves focus to the tab strip (first selected tab)
- Arrow Left / Arrow Right: moves focus between tabs within the strip (roving tabindex pattern)
- Enter or Space: activates the focused tab
- Tab from within the tab strip: moves focus into the active tab panel content

**DOM order requirement:** The tab strip must appear before the tab panel in DOM order — both visually and in the accessibility tree. This ensures keyboard and screen reader users encounter the navigation before the content.

---

## Focus Management After Toast Dismiss

*(Closes remaining accessibility gap identified in review)*

When a toast notification is dismissed (either by timeout or by user clicking the close/dismiss button on a persistent toast):

- **Auto-dismissed toasts** (3-second success toasts): focus does not move. The toast disappears from the DOM; focus remains on whatever element the user was interacting with.
- **User-dismissed persistent toasts** (error or warning toasts with a close button): when the user presses the close button, focus returns to the element that triggered the action which produced the toast (e.g., the "Save" button that caused the error). If that element is no longer in the DOM (e.g., the modal was closed), focus moves to the nearest logical container (the page `<main>` element).
- **Undo toast** (position deletion 5-second undo): the Undo button within the toast is focusable. After the 5-second window expires and the toast auto-dismisses, focus returns to the dashboard position table (or the empty state CTA if the last position was deleted).

---

# SECTION 10 — FINTECH DATA DISPLAY SUPPLEMENT

*New section. Closes data display gaps identified in the review.*

---

## Large Number Display Format

Portfolio totals can reach RM1,000,000+ for users with large portfolios. The following thresholds and formats apply:

| Value Range | Display Format | Example |
|-------------|---------------|---------|
| < RM1,000 | Full 2dp | RM 842.50 |
| RM1,000 – RM999,999 | Full 2dp with comma thousands separator | RM 41,996.47 |
| RM1,000,000 – RM9,999,999 | Full 2dp with comma separators | RM 1,234,567.89 |
| ≥ RM10,000,000 | Not expected at V1; use full format (no abbreviation) | RM 12,345,678.90 |

**No abbreviation (RM1.2M) is used at V1.** Abbreviations introduce rounding that conflicts with the product's accuracy positioning. A dividend investor who holds RM1,234,567.89 in positions cares about the RM567.89.

**Negative values** (unrealised P&L in loss): display as "−RM 4,320.15" with a leading minus sign, NOT parentheses notation.

---

## Rounding Display vs. Storage Disclosure

The BAS specifies that yield is stored to 4dp and displayed to 2dp (e.g., stored 5.5660%, displayed 5.57%). This rounding can cause displayed column totals not to add up precisely:

**Example:** 5 positions with stored yields 5.5660%, 4.2312%, 7.1108%, 3.9845%, 6.0031% display as 5.57%, 4.23%, 7.11%, 3.98%, 6.00%. The displayed blended yield of 5.37% (2dp) may not equal the arithmetic average of the 5 displayed values.

**UX specification:** This discrepancy is **expected and correct** (blended yield is weighted, not arithmetic average). No special treatment is required. However, the Yield Drill-Down overlay (tapping the yield figure) must show the full stored precision value in the calculation: "5.57% (5.5660% stored)" — this allows power users like David to verify the math with full precision.

---

# SECTION 11 — DESIGN SYSTEM COMPONENT VOCABULARY

*New section. Closes R-022 — Should Fix.*

---

## Required Component Definitions

The following reusable components are referenced throughout the spec. Each must be designed as a single consistent component, not reimplemented per screen.

### Component 1: Fee Breakdown Panel

**Used in:** Add Position/Lot modal (live), Lots Tab (per-row expandable), Sell Calculator Tab (per-row columns)

**Anatomy:**
```
Label:                   Value:          Formula (grey subtext):
Initial Amount           RM 41,900.00
Brokerage Fee            RM    41.90    Maybank Investment: 0.10% of RM 41,900
Clearing Fee             RM    12.57    0.03% of RM 41,900
Stamp Duty               RM    42.00    RM1 per RM 1,000 (ROUNDUP)
────────────────────────────────────
All-In Cost              RM 41,996.47   [bold, larger font size]
```

**States:** Live (values updating as user types) / Static (fixed values on display screens)
**Behaviour:** In live state, the "All-In Cost" row animates a brief highlight when its value changes

---

### Component 2: Yield Drill-Down Overlay

**Used in:** Dashboard position row (tap yield %), Position Detail Dividends tab (tap yield %), Portfolio header (tap blended yield %)

**Trigger:** Any rendered yield percentage is tappable / has `role="button"`
**Presentation:** On desktop: a popover panel anchored to the tapped yield element. On mobile: a bottom sheet (slides up from bottom of viewport, overlaying up to 70% of screen height).
**Content structure:** [Yield formula] → [Income breakdown: per-tranche rows] → [Cost breakdown: per-lot rows]
**Dismiss:** Click/tap outside the popover (desktop); swipe down or tap the drag handle (mobile); Escape key (desktop)
**Accessibility:** `role="dialog"`, `aria-modal="true"`, `aria-labelledby` → heading "Yield Breakdown — CIMB"

---

### Component 3: Status Chip / Badge

**Used throughout:** Category tags (Dividend/Volatile/Growth), Stale price indicator, "Paid" badge on calendar, Trial countdown, Payment failed indicator, "Manual" price provenance tag

**Variants by role:**
| Variant | Colour token | Use case |
|---------|-------------|---------|
| Neutral | Grey | Category tags |
| Success | Green | "Paid" badge; subscription active |
| Warning | Amber | Stale price; trial ending; payment failed |
| Info | Blue | "Manual" price provenance; email verification reminder |
| Destructive | Red | (reserved — not used in V1 as a chip) |

**Anatomy:** [Optional icon] + [Label text] in a rounded-pill shape, small font (12–13px), padding 4px 8px

---

### Component 4: Confirmation Dialog

**Used in:** Delete Position, Delete Lot, Delete Dividend Tranche, Cancel Subscription, Deactivate Broker

**Anatomy:**
- Heading: destructive action name (e.g., "Delete CIMB position?")
- Body: scope of what will be deleted/affected: "This will delete CIMB and all 3 lots and 8 dividend records."
- Two buttons: [Cancel] (left, neutral style, default focus) and [Confirm / Delete] (right, destructive style)
- Default focus is on Cancel to prevent accidental confirmation via Enter

**Keyboard:** Escape = Cancel; Tab between Cancel and Confirm; Enter on focused button activates it

---

### Component 5: Data Entry Form Layout

**Used in:** All modal forms (Add Position, Add Lot, Add Dividend, Edit forms, Custom Broker, Registration, Password forms)

**Layout pattern:** Single-column, full-width fields. Label above field (not inline/placeholder-only). Error text below field. Grouped sections separated by a subtle horizontal rule if the form has > 6 fields. On mobile: full-screen modal with sticky [Save] button pinned to bottom of viewport.

**Field spacing:** 16px between fields; 24px between field groups.

**Required field indicator:** An asterisk (*) after the label, with a legend at the top of the form: "* Required fields"

---

### Component 6: Empty State

**Used in:** Dashboard (no positions), Dividend Calendar (no dates), Position Dividends Tab (no tranches)

**Anatomy:** [Icon or illustration — designer choice, small] + [Heading] + [Body copy] + [Primary CTA button]

**Tone:** Welcoming, not apologetic. "Add your first position to get started" — not "No data found."

---

# DOCUMENT AMENDMENTS

*Corrections to existing content in Parts 1 and 2.*

---

## Amendment 1 — Dashboard Screen Requirements: Add Sell Calculator to ••• Menu

*(Closes R-009 — Must Fix)*

**In Part 1, Section 6, Screen: Dashboard — Secondary Actions**, amend the ••• per-row menu to include "Sell Calculator →" as an explicit named item:

**••• Per-row action menu items (in order):**
1. Add Lot
2. Add Dividend
3. **Sell Calculator →** *(navigates to /positions/:id/sell)*
4. Edit Position
5. Delete Position

This ensures the Sell Calculator is discoverable directly from the dashboard without requiring navigation to Position Detail first.

---

## Amendment 2 — Dashboard Screen Requirements: Trial Countdown Timing

**In Part 1, Section 6, Screen: Dashboard — Key Information Displayed**, amend the trial countdown chip specification:

The trial countdown chip is shown **from day 1 of the trial** (not only in the final 3 days). It shows: "Trial: [N] days remaining." On days 1–11 it is a neutral info chip (blue, low urgency). From day 12–14 it changes to an amber warning chip. On day 14 (the last day), the chip reads "Trial ends today."

The chip is placed in the top navigation bar (right side, before the Account avatar), not in the content area. It is non-intrusive and does not interrupt any workflow.

---

## Amendment 3 — Part 2, Section 8: Add Note on Missing Import Page Upload State

**Formal state definition for Import Page — Upload in Progress:**

| State | Description |
|-------|-------------|
| Upload In Progress | After the user selects and submits a file: a progress indicator replaces the upload zone. For files < 1MB: a spinner + "Validating your data…" is sufficient. For files ≥ 1MB: a percentage progress bar if the upload is streaming; otherwise spinner. The [Download Template] and [Upload File] buttons are disabled during validation. Cancel is not available (atomic import means there is nothing to cancel mid-validation). |

---

# OPEN QUESTIONS (NEW — FROM ADDENDUM)

*Two new questions added to the existing Open Questions table (Part 1, Section 11 via the BAS).*

| ID | Question | Impact | Recommended Owner |
|----|----------|--------|------------------|
| OQ-D09 | When the last position is deleted and the dashboard transitions to empty state, should the portfolio summary header show RM0.00 values or be hidden entirely? | Visual treatment decision; either is correct. RM0 values maintain layout stability; hidden simplifies the empty state. | Design |
| OQ-D10 | When session expires mid-modal, should re-authentication open in a new browser tab or as an overlay modal above the existing form? | New tab loses the in-progress form context on some browsers; overlay is more seamless but complex to implement. V1 recommendation: new tab with a warning. | Engineering + Design |

---

*End of Part 3 (Gap Closure Addendum).*
*BursaTrack UX Spec v1.1 is now complete across three files:*
*— Part 1: Sections 1–6 (Executive Summary, Journey Maps, User Flows, IA, Screen Inventory, Screen Requirements — core product)*
*— Part 2: Sections 7–11 (Interaction Specs, State Definitions, Accessibility, UX Risk Review, Designer Readiness)*
*— Part 3: This addendum — all review gaps closed; R-001 through R-025 addressed*

*Projected post-addendum Design Readiness Score: 9 / 10*
*Projected post-addendum Verdict: APPROVE*
