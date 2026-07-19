# BursaTrack — OpenAPI Contract Specification

## Stage 3 of 4: OpenAPI 3.0 Specification

> **Author:** Senior API Engineer (API Design Workflow — Stage 3)<br>
> **Date:** 2026-07-01<br>
> **Inputs:** Stage 1 API Requirements Report · Stage 2 API Design Decision Record · BursaTrack Solution Architecture Document<br>
> **Status:** Complete, valid OpenAPI 3.0.3 document covering all endpoints in the architecture's inventory. Delivered as a fenced YAML block per the output format requested for this workflow (`specs/output/2.technical-designs/api-design/`); this content is the authoritative contract and may be extracted verbatim to `openapi.yaml` for tooling (linting, codegen, mock servers) without modification.

---

```yaml
openapi: "3.0.3"
info:
  title: BursaTrack API
  version: "1.0.0"
  description: |
    REST API for BursaTrack — a dividend portfolio tracker for Malaysian retail investors.

    **Financial accuracy at the boundary:** All monetary and rate values are serialized as
    JSON strings (never JSON numbers) to preserve exact Decimal precision end-to-end between
    the PostgreSQL NUMERIC columns, the Python Decimal backend, and the TypeScript decimal.js
    frontend. A float anywhere in this chain corrupts BursaTrack's core accuracy claim.

    **Server-authoritative fees:** Clients never supply brokerage_fee, clearing_fee,
    stamp_duty, all_in_cost, or DividendTranche.total_amount. These are always computed and
    stored server-side.

    **Timestamps:** ISO 8601 UTC, e.g. "2026-06-28T08:30:00Z" for datetimes,
    "2026-06-28" for dates.

    **Authentication:** RS256 JWT in an HTTP-only, Secure, SameSite=Lax cookie named
    `access_token`. The JWT is also validated on every protected request against the
    authenticated user's current `token_version` column; a mismatch (caused by logout,
    password change, or account deletion initiation on any session) returns 401 with
    `error: "token_revoked"`, even for an otherwise well-formed, unexpired token.

    **Ownership enforcement:** Every endpoint that reads or mutates user-owned data verifies
    `resource.user_id == authenticated_user.id` (transitively, via Portfolio → Position →
    Lot/DividendTranche where applicable). A cross-user access attempt returns
    `404 Not Found` — never `403 Forbidden` — so that resource existence is never disclosed
    to a caller who does not own it.

    **CORS:** Credentialed requests are permitted only from `https://bursatrack.com`,
    `https://www.bursatrack.com`, `http://localhost:3000` (development), and Vercel preview
    deployments matching `https://bursatrack-[a-z0-9-]+-[a-z0-9]+\.vercel\.app`.

  contact:
    name: BursaTrack Engineering

servers:
  - url: https://api.bursatrack.com
    description: Production
  - url: http://localhost:8000
    description: Local development

tags:
  - name: Auth
  - name: Portfolio
  - name: Pricing
  - name: Import
  - name: Subscription
  - name: Account
  - name: Reference
  - name: Admin
  - name: Health

components:
  securitySchemes:
    cookieAuth:
      type: apiKey
      in: cookie
      name: access_token
      description: |
        RS256 JWT issued at registration/login, stored as an HTTP-only, Secure,
        SameSite=Lax cookie. Validated against the authenticated user's current
        `token_version`; a mismatch returns 401 `token_revoked`. 7-day expiry with a
        client-driven silent-refresh pattern via `POST /auth/refresh`.
    adminApiKey:
      type: apiKey
      in: header
      name: X-Admin-API-Key
      description: |
        Shared-secret credential (`ADMIN_API_KEY` environment variable), distinct from the
        JWT scheme. Validated with constant-time string comparison. Not tied to any user
        identity — failed attempts are logged with source IP but cannot be attributed to a
        `user_id`. Invalid or missing key returns 401.
    stripeSignature:
      type: apiKey
      in: header
      name: Stripe-Signature
      description: |
        HMAC signature over the raw webhook payload, verified against
        `STRIPE_WEBHOOK_SECRET` before any event data is parsed or trusted. Applied only to
        `POST /webhooks/stripe`.

  schemas:
    # ---------- Error schemas ----------
    ErrorResponse:
      type: object
      required: [error, message]
      properties:
        error:
          type: string
          description: Machine-readable error code.
        message:
          type: string
          description: Human-readable, end-user-displayable message.
        job_id:
          type: string
          format: uuid
          nullable: true
          description: Present only on 409 already_processing responses from POST /import/csv.
      example:
        error: "version_conflict"
        message: "This record was modified by another session. Please refresh and try again."

    ValidationErrorResponse:
      type: object
      required: [error, message, fields]
      properties:
        error:
          type: string
          enum: ["validation_failed"]
        message:
          type: string
        fields:
          type: array
          items:
            type: object
            required: [field, constraint]
            properties:
              field: { type: string }
              constraint: { type: string }
              received: { type: string, nullable: true }
      example:
        error: "validation_failed"
        message: "One or more fields failed validation."
        fields:
          - field: "shares"
            constraint: "must be >= 1"
            received: "0"

    # ---------- Auth request/response schemas ----------
    RegisterRequest:
      type: object
      required: [email, password, broker_id]
      properties:
        email: { type: string, format: email, maxLength: 254 }
        password: { type: string, minLength: 8, maxLength: 128 }
        broker_id: { type: string, format: uuid }
      example:
        email: "ahmad@email.com"
        password: "Invest2026"
        broker_id: "5f2e1c3a-1111-4a1a-9999-abcdefabcdef"

    LoginRequest:
      type: object
      required: [email, password]
      properties:
        email: { type: string, format: email }
        password: { type: string }
      example:
        email: "ahmad@email.com"
        password: "Invest2026"

    PasswordResetRequest:
      type: object
      required: [email]
      properties:
        email: { type: string, format: email }
      example:
        email: "ahmad@email.com"

    PasswordResetComplete:
      type: object
      required: [token, new_password]
      properties:
        token:
          {
            type: string,
            description: "Single-use reset token from the emailed link.",
          }
        new_password: { type: string, minLength: 8, maxLength: 128 }
      example:
        token: "b6e6c1a2-9c3e-4f1e-8a2b-1234567890ab"
        new_password: "NewPass2026"

    UserResponse:
      type: object
      required:
        [
          id,
          email,
          email_verified,
          account_status,
          trial_expiry_date,
          created_at,
        ]
      properties:
        id: { type: string, format: uuid }
        email: { type: string, format: email }
        email_verified: { type: boolean }
        account_status:
          type: string
          enum:
            [
              "trial",
              "active",
              "grace_period",
              "trial_expired",
              "pending_deletion",
            ]
        trial_expiry_date: { type: string, format: date }
        subscription_start_date: { type: string, format: date, nullable: true }
        subscription_renewal_date:
          { type: string, format: date, nullable: true }
        default_broker_id: { type: string, format: uuid }
        created_at: { type: string, format: date-time }
      description: |
        Public user fields only. Never includes password_hash or token_version.
      example:
        id: "3c2b1a0f-1111-4a1a-9999-abcdefabcdef"
        email: "ahmad@email.com"
        email_verified: true
        account_status: "trial"
        trial_expiry_date: "2026-07-15"
        subscription_start_date: null
        subscription_renewal_date: null
        default_broker_id: "5f2e1c3a-1111-4a1a-9999-abcdefabcdef"
        created_at: "2026-07-01T02:15:00Z"

    AuthResponse:
      type: object
      required: [user, expires_at]
      properties:
        user: { $ref: "#/components/schemas/UserResponse" }
        expires_at:
          {
            type: string,
            format: date-time,
            description: "Expiry of the newly issued JWT cookie.",
          }
      example:
        user:
          id: "3c2b1a0f-1111-4a1a-9999-abcdefabcdef"
          email: "ahmad@email.com"
          email_verified: true
          account_status: "trial"
          trial_expiry_date: "2026-07-15"
          subscription_start_date: null
          subscription_renewal_date: null
          default_broker_id: "5f2e1c3a-1111-4a1a-9999-abcdefabcdef"
          created_at: "2026-07-01T02:15:00Z"
        expires_at: "2026-07-08T02:15:00Z"

    JwksResponse:
      type: object
      required: [keys]
      properties:
        keys:
          type: array
          items:
            type: object
            properties:
              kty: { type: string, example: "RSA" }
              use: { type: string, example: "sig" }
              alg: { type: string, example: "RS256" }
              kid: { type: string }
              n: { type: string }
              e: { type: string }

    # ---------- Portfolio schemas ----------
    CreatePositionRequest:
      type: object
      required: [stock_code, shares, purchase_price, broker_id, purchase_date]
      properties:
        stock_code: { type: string, example: "1023" }
        shares: { type: integer, minimum: 1, maximum: 99999999 }
        purchase_price:
          type: string
          pattern: "^[0-9]+\\.[0-9]{1,4}$"
          description: "MYR per share, up to 4 decimal places, serialized as a string."
        broker_id: { type: string, format: uuid }
        purchase_date: { type: string, format: date }
        category_tag:
          type: string
          enum: ["Dividend", "Volatile", "Growth"]
          default: "Dividend"
        notes: { type: string, nullable: true, maxLength: 500 }
      example:
        stock_code: "1023"
        shares: 5000
        purchase_price: "8.3800"
        broker_id: "5f2e1c3a-1111-4a1a-9999-abcdefabcdef"
        purchase_date: "2026-01-15"
        category_tag: "Dividend"

    CreateLotRequest:
      type: object
      required: [shares, purchase_price, broker_id, purchase_date]
      properties:
        shares: { type: integer, minimum: 1, maximum: 99999999 }
        purchase_price:
          type: string
          pattern: "^[0-9]+\\.[0-9]{1,4}$"
        broker_id: { type: string, format: uuid }
        purchase_date: { type: string, format: date }
      example:
        shares: 2000
        purchase_price: "9.0000"
        broker_id: "5f2e1c3a-1111-4a1a-9999-abcdefabcdef"
        purchase_date: "2026-04-02"

    UpdateLotRequest:
      type: object
      required: [version]
      description: |
        At least one of shares/purchase_price/broker_id/purchase_date must be present in
        addition to the required version field used for optimistic locking.
      properties:
        shares: { type: integer, minimum: 1, maximum: 99999999 }
        purchase_price:
          type: string
          pattern: "^[0-9]+\\.[0-9]{1,4}$"
        broker_id: { type: string, format: uuid }
        purchase_date: { type: string, format: date }
        version: { type: integer, minimum: 1 }
      example:
        shares: 4000
        version: 1

    UpdatePositionRequest:
      type: object
      properties:
        category_tag:
          type: string
          enum: ["Dividend", "Volatile", "Growth"]
        notes: { type: string, nullable: true, maxLength: 500 }
      example:
        category_tag: "Growth"

    LotResponse:
      type: object
      required:
        - id
        - position_id
        - shares
        - purchase_price
        - purchase_date
        - broker_id
        - initial_amount
        - brokerage_fee
        - clearing_fee
        - stamp_duty
        - all_in_cost
        - version
        - created_at
        - updated_at
      properties:
        id: { type: string, format: uuid }
        position_id: { type: string, format: uuid }
        shares: { type: integer }
        purchase_price: { type: string }
        purchase_date: { type: string, format: date }
        broker_id: { type: string, format: uuid }
        initial_amount:
          { type: string, description: "shares × purchase_price, 2dp" }
        brokerage_fee: { type: string }
        clearing_fee: { type: string }
        stamp_duty: { type: string }
        all_in_cost: { type: string }
        version: { type: integer }
        created_at: { type: string, format: date-time }
        updated_at: { type: string, format: date-time }
      example:
        id: "8a1b2c3d-4444-4a1a-9999-abcdefabcdef"
        position_id: "7a1b2c3d-3333-4a1a-9999-abcdefabcdef"
        shares: 5000
        purchase_price: "8.3800"
        purchase_date: "2026-01-15"
        broker_id: "5f2e1c3a-1111-4a1a-9999-abcdefabcdef"
        initial_amount: "41900.00"
        brokerage_fee: "41.90"
        clearing_fee: "12.57"
        stamp_duty: "42.00"
        all_in_cost: "41996.47"
        version: 1
        created_at: "2026-01-15T09:05:00Z"
        updated_at: "2026-01-15T09:05:00Z"

    DividendTrancheResponse:
      type: object
      required:
        - id
        - position_id
        - tranche_label
        - per_share_amount
        - qualifying_shares
        - total_amount
        - payment_date
        - year
        - version
        - created_at
        - updated_at
      properties:
        id: { type: string, format: uuid }
        position_id: { type: string, format: uuid }
        tranche_label:
          type: string
          enum: ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"]
        per_share_amount:
          type: string
          description: "MYR per share, up to 6 decimal places. Stored at logging time."
        qualifying_shares:
          type: integer
          description: "Share count used to compute total_amount. Stored at logging time; not re-derived from live position totals."
        total_amount:
          type: string
          description: "STORED value = per_share_amount × qualifying_shares at the time it was last written. Never recomputed by adding new Lots."
        payment_date: { type: string, format: date }
        ex_dividend_date: { type: string, format: date, nullable: true }
        year: { type: integer }
        version: { type: integer }
        created_at: { type: string, format: date-time }
        updated_at: { type: string, format: date-time }
      example:
        id: "9a1b2c3d-5555-4a1a-9999-abcdefabcdef"
        position_id: "7a1b2c3d-3333-4a1a-9999-abcdefabcdef"
        tranche_label: "1st"
        per_share_amount: "0.200000"
        qualifying_shares: 5000
        total_amount: "1000.00"
        payment_date: "2026-03-15"
        ex_dividend_date: "2026-02-28"
        year: 2026
        version: 1
        created_at: "2026-03-15T10:00:00Z"
        updated_at: "2026-03-15T10:00:00Z"

    PositionSummaryResponse:
      type: object
      required:
        - id
        - stock_code
        - stock_name
        - category_tag
        - total_shares
        - total_all_in_cost
        - blended_purchase_price
        - total_dividend_income_ytd
        - current_price
        - price_source
        - price_last_refreshed_at
        - current_market_value
        - unrealised_pnl
      properties:
        id: { type: string, format: uuid }
        stock_code: { type: string }
        stock_name: { type: string }
        category_tag: { type: string, enum: ["Dividend", "Volatile", "Growth"] }
        total_shares: { type: integer }
        total_all_in_cost: { type: string }
        blended_purchase_price: { type: string }
        total_dividend_income_ytd: { type: string }
        current_price:
          {
            type: string,
            nullable: true,
            description: "Null if no price has ever been retrieved (BAS EC-005).",
          }
        price_source:
          {
            type: string,
            enum: ["automated", "manual", "stale"],
            nullable: true,
          }
        price_last_refreshed_at:
          { type: string, format: date-time, nullable: true }
        current_market_value: { type: string, nullable: true }
        unrealised_pnl: { type: string, nullable: true }
      example:
        id: "7a1b2c3d-3333-4a1a-9999-abcdefabcdef"
        stock_code: "1023"
        stock_name: "CIMB GROUP HOLDINGS BHD"
        category_tag: "Dividend"
        total_shares: 5000
        total_all_in_cost: "41996.47"
        blended_purchase_price: "8.3800"
        total_dividend_income_ytd: "1000.00"
        current_price: "8.4200"
        price_source: "automated"
        price_last_refreshed_at: "2026-06-30T09:35:00Z"
        current_market_value: "42100.00"
        unrealised_pnl: "103.53"

    PositionResponse:
      allOf:
        - $ref: "#/components/schemas/PositionSummaryResponse"
        - type: object
          required:
            [lots, dividend_tranches, is_deleted, created_at, updated_at]
          properties:
            lots:
              type: array
              items: { $ref: "#/components/schemas/LotResponse" }
            dividend_tranches:
              type: array
              items: { $ref: "#/components/schemas/DividendTrancheResponse" }
            is_deleted: { type: boolean }
            created_at: { type: string, format: date-time }
            updated_at: { type: string, format: date-time }

    PortfolioResponse:
      type: object
      description: |
        Yield is intentionally absent from this schema. Portfolio blended yield is always
        computed client-side from total_dividend_income_ytd ÷ total_all_in_cost using
        decimal.js — it is never calculated or returned by the server as a percentage field
        (P0-API-001 / FC-002).
      required:
        - total_all_in_cost
        - total_dividend_income_ytd
        - last_price_refresh_at
        - positions
      properties:
        total_all_in_cost: { type: string }
        total_dividend_income_ytd: { type: string }
        last_price_refresh_at:
          { type: string, format: date-time, nullable: true }
        positions:
          type: array
          items: { $ref: "#/components/schemas/PositionSummaryResponse" }
      example:
        total_all_in_cost: "612044.18"
        total_dividend_income_ytd: "23841.02"
        last_price_refresh_at: "2026-06-30T09:35:00Z"
        positions: []

    CreateDividendRequest:
      type: object
      required:
        [
          position_id,
          tranche_label,
          per_share_amount,
          qualifying_shares,
          payment_date,
        ]
      properties:
        position_id: { type: string, format: uuid }
        tranche_label:
          type: string
          enum: ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"]
        per_share_amount:
          type: string
          pattern: "^[0-9]+\\.[0-9]{1,6}$"
        qualifying_shares: { type: integer, minimum: 1 }
        payment_date: { type: string, format: date }
        ex_dividend_date: { type: string, format: date, nullable: true }
      example:
        position_id: "7a1b2c3d-3333-4a1a-9999-abcdefabcdef"
        tranche_label: "1st"
        per_share_amount: "0.200000"
        qualifying_shares: 5000
        payment_date: "2026-03-15"
        ex_dividend_date: "2026-02-28"

    UpdateDividendRequest:
      type: object
      required: [version]
      description: |
        At least one of per_share_amount/qualifying_shares/tranche_label/payment_date/
        ex_dividend_date must be present in addition to version. The server always
        recomputes total_amount from the resulting per_share_amount and qualifying_shares;
        total_amount is never an accepted input field on this schema.
      properties:
        per_share_amount:
          type: string
          pattern: "^[0-9]+\\.[0-9]{1,6}$"
        qualifying_shares: { type: integer, minimum: 1 }
        tranche_label:
          type: string
          enum: ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"]
        payment_date: { type: string, format: date }
        ex_dividend_date: { type: string, format: date, nullable: true }
        version: { type: integer, minimum: 1 }
      example:
        qualifying_shares: 3000
        version: 1

    DividendCalendarResponse:
      type: object
      required: [tranches]
      properties:
        tranches:
          type: array
          items:
            allOf:
              - $ref: "#/components/schemas/DividendTrancheResponse"
              - type: object
                required: [stock_code, stock_name]
                properties:
                  stock_code: { type: string }
                  stock_name: { type: string }

    SellScenarioRow:
      type: object
      required:
        - price
        - gross_proceeds
        - projected_brokerage
        - projected_clearing_fee
        - projected_stamp_duty
        - projected_all_in_sell_cost
        - projected_net_proceeds
        - profit_loss
        - break_even
      properties:
        price: { type: string }
        gross_proceeds: { type: string }
        projected_brokerage: { type: string }
        projected_clearing_fee: { type: string }
        projected_stamp_duty: { type: string }
        projected_all_in_sell_cost: { type: string }
        projected_net_proceeds: { type: string }
        profit_loss: { type: string }
        break_even: { type: boolean }

    SellScenarioResponse:
      type: object
      required:
        [
          position_id,
          shares_to_sell,
          buy_cost_basis,
          broker_id,
          disclaimer_required,
          scenarios,
        ]
      properties:
        position_id: { type: string, format: uuid }
        shares_to_sell: { type: integer }
        buy_cost_basis:
          type: string
          description: "Proportional all-in buy cost for shares_to_sell (BR-024 weighted average for partial sales)."
        broker_id:
          {
            type: string,
            format: uuid,
            description: "Broker used for sell-side fee calculation; defaults per architecture assumption A-006, overridable via query param.",
          }
        disclaimer_required:
          type: boolean
          description: "Always true at V1 — carries the fixed T+2 settlement / informational-only disclosure (BR-020, BR-021)."
        scenarios:
          type: array
          items: { $ref: "#/components/schemas/SellScenarioRow" }
      example:
        position_id: "7a1b2c3d-3333-4a1a-9999-abcdefabcdef"
        shares_to_sell: 5000
        buy_cost_basis: "41996.47"
        broker_id: "5f2e1c3a-1111-4a1a-9999-abcdefabcdef"
        disclaimer_required: true
        scenarios:
          - price: "8.4200"
            gross_proceeds: "42100.00"
            projected_brokerage: "42.10"
            projected_clearing_fee: "12.63"
            projected_stamp_duty: "43.00"
            projected_all_in_sell_cost: "42197.73"
            projected_net_proceeds: "42002.27"
            profit_loss: "5.80"
            break_even: true

    # ---------- Pricing schemas ----------
    PriceSnapshotResponse:
      type: object
      required: [stock_code, price, source, trading_date, refreshed_at]
      properties:
        stock_code: { type: string }
        price: { type: string }
        source: { type: string, enum: ["automated", "manual", "stale"] }
        trading_date: { type: string, format: date }
        refreshed_at: { type: string, format: date-time }
      example:
        stock_code: "1023"
        price: "8.4200"
        source: "automated"
        trading_date: "2026-06-30"
        refreshed_at: "2026-06-30T09:35:00Z"

    ManualPriceOverrideRequest:
      type: object
      required: [stock_code, price, trading_date]
      properties:
        stock_code: { type: string }
        price:
          type: string
          pattern: "^[0-9]+\\.[0-9]{1,4}$"
        trading_date: { type: string, format: date }
      example:
        stock_code: "1023"
        price: "8.5000"
        trading_date: "2026-06-30"

    # ---------- Import schemas ----------
    ImportJobResultResponse:
      type: object
      required: [rows_imported, rows_failed, errors]
      properties:
        rows_imported: { type: integer }
        rows_failed: { type: integer }
        positions_created: { type: integer }
        tranches_created: { type: integer }
        errors:
          type: array
          items:
            type: object
            required: [row, message]
            properties:
              row: { type: integer }
              column: { type: string, nullable: true }
              message: { type: string }
      example:
        rows_imported: 16
        rows_failed: 0
        positions_created: 16
        tranches_created: 34
        errors: []

    ImportJobResponse:
      type: object
      required: [job_id, status, created_at]
      properties:
        job_id: { type: string, format: uuid }
        status: { type: string, enum: ["processing", "complete", "failed"] }
        created_at: { type: string, format: date-time }
        result:
          allOf:
            - $ref: "#/components/schemas/ImportJobResultResponse"
          nullable: true
      example:
        job_id: "ab12cd34-6666-4a1a-9999-abcdefabcdef"
        status: "complete"
        created_at: "2026-06-30T10:00:00Z"
        result:
          rows_imported: 16
          rows_failed: 0
          positions_created: 16
          tranches_created: 34
          errors: []

    # ---------- Subscription schemas ----------
    CheckoutResponse:
      type: object
      required: [checkout_url]
      properties:
        checkout_url: { type: string, format: uri }
      example:
        checkout_url: "https://checkout.stripe.com/c/pay/cs_test_abc123"

    SubscriptionStatusResponse:
      type: object
      required: [account_status, trial_expiry_date]
      properties:
        account_status:
          type: string
          enum:
            [
              "trial",
              "active",
              "grace_period",
              "trial_expired",
              "pending_deletion",
            ]
        trial_expiry_date: { type: string, format: date, nullable: true }
        subscription_start_date: { type: string, format: date, nullable: true }
        subscription_renewal_date:
          { type: string, format: date, nullable: true }
      example:
        account_status: "active"
        trial_expiry_date: "2026-07-15"
        subscription_start_date: "2026-07-16"
        subscription_renewal_date: "2026-08-16"

    WebhookAckResponse:
      type: object
      required: [received]
      properties:
        received: { type: boolean }
      example:
        received: true

    # ---------- Account / PDPA schemas ----------
    DeleteAccountRequest:
      type: object
      required: [confirmation]
      properties:
        confirmation:
          type: string
          enum: ["DELETE"]
      example:
        confirmation: "DELETE"

    DeletionAcceptedResponse:
      type: object
      required: [account_status, permanent_deletion_date]
      properties:
        account_status: { type: string, enum: ["pending_deletion"] }
        permanent_deletion_date: { type: string, format: date }
      example:
        account_status: "pending_deletion"
        permanent_deletion_date: "2026-07-31"

    DeletionCancelledResponse:
      type: object
      required: [account_status]
      properties:
        account_status:
          type: string
          enum: ["trial", "active", "grace_period", "trial_expired"]
      example:
        account_status: "trial_expired"

    DataExportResponse:
      type: object
      description: |
        Streamed JSON file download, Content-Type: application/json, Content-Disposition:
        attachment; filename="bursatrack-export-{date}.json". Structure is the full
        personal-data export object described in architecture §10.7 (User, Portfolio,
        Position, Lot, DividendTranche, custom BrokerConfig, ImportJob, AuditLog). Not
        modeled as a typed schema here because its shape is a direct dump of multiple
        entity tables, not a stable API contract intended for programmatic consumption
        beyond the download itself. See architecture §10.7 for the exact field-level
        inclusion/exclusion table.

    # ---------- Reference data schemas ----------
    StockResponse:
      type: object
      required: [code, name, market, sector, instrument_type, is_active]
      properties:
        code: { type: string }
        name: { type: string }
        market: { type: string, example: "Main Market" }
        sector: { type: string }
        instrument_type: { type: string, example: "Equity" }
        is_active: { type: boolean }
      example:
        code: "1023"
        name: "CIMB GROUP HOLDINGS BHD"
        market: "Main Market"
        sector: "Financial Services"
        instrument_type: "Equity"
        is_active: true

    StockListResponse:
      type: object
      required: [stocks]
      properties:
        stocks:
          type: array
          items: { $ref: "#/components/schemas/StockResponse" }

    CreateBrokerConfigRequest:
      type: object
      required: [name, fee_type]
      description: |
        Exactly one fee-shape must be supplied consistent with fee_type: rate + minimum_fee
        for "percentage", or flat_fee for "flat". Enforced server-side (422 on mismatch).
      properties:
        name: { type: string, maxLength: 60 }
        fee_type: { type: string, enum: ["percentage", "flat"] }
        rate:
          type: string
          nullable: true
          pattern: "^0\\.[0-9]{1,6}$"
          description: "Required if fee_type=percentage. 0 < rate <= 0.02 (0%-2%)."
        minimum_fee:
          type: string
          nullable: true
          description: "Required if fee_type=percentage. 0 <= minimum_fee <= 100.00."
        flat_fee:
          type: string
          nullable: true
          description: "Required if fee_type=flat. 0 < flat_fee <= 100.00."
      example:
        name: "Kenanga Investors"
        fee_type: "percentage"
        rate: "0.004200"
        minimum_fee: "8.00"

    UpdateBrokerConfigRequest:
      type: object
      description: One or more fields from CreateBrokerConfigRequest.
      properties:
        name: { type: string, maxLength: 60 }
        fee_type: { type: string, enum: ["percentage", "flat"] }
        rate: { type: string, nullable: true }
        minimum_fee: { type: string, nullable: true }
        flat_fee: { type: string, nullable: true }
      example:
        rate: "0.004500"

    BrokerConfigResponse:
      type: object
      required: [id, name, fee_type, is_system, created_at]
      properties:
        id: { type: string, format: uuid }
        name: { type: string }
        fee_type: { type: string, enum: ["percentage", "flat"] }
        rate: { type: string, nullable: true }
        minimum_fee: { type: string, nullable: true }
        flat_fee: { type: string, nullable: true }
        is_system: { type: boolean }
        created_by_user_id: { type: string, format: uuid, nullable: true }
        created_at: { type: string, format: date-time }
      example:
        id: "5f2e1c3a-1111-4a1a-9999-abcdefabcdef"
        name: "Maybank IB"
        fee_type: "percentage"
        rate: "0.007000"
        minimum_fee: "8.00"
        flat_fee: null
        is_system: true
        created_by_user_id: null
        created_at: "2026-01-01T00:00:00Z"

    BrokerListResponse:
      type: object
      required: [brokers]
      properties:
        brokers:
          type: array
          items: { $ref: "#/components/schemas/BrokerConfigResponse" }

    # ---------- Admin schemas ----------
    AdminConfigUpdateRequest:
      type: object
      required: [key, value]
      properties:
        key:
          type: string
          enum:
            [
              "clearing_fee_rate",
              "stamp_duty_rate",
              "price_deviation_max_pct",
              "bursa_holidays",
            ]
        value:
          type: string
          description: "Serialized value; for bursa_holidays this is a JSON array of ISO date strings encoded as a string."
      example:
        key: "price_deviation_max_pct"
        value: "75"

    AdminConfigEntry:
      type: object
      required: [key, value, updated_at]
      properties:
        key: { type: string }
        value: { type: string }
        description: { type: string, nullable: true }
        updated_at: { type: string, format: date-time }

    AdminConfigResponse:
      type: object
      required: [config]
      properties:
        config:
          type: array
          items: { $ref: "#/components/schemas/AdminConfigEntry" }
      example:
        config:
          - key: "clearing_fee_rate"
            value: "0.0003"
            description: "Bursa clearing fee, applied to gross trade value."
            updated_at: "2026-01-01T00:00:00Z"
          - key: "stamp_duty_rate"
            value: "0.0010"
            description: "Gazetted until 2028-07-12."
            updated_at: "2026-01-01T00:00:00Z"

    # ---------- Health ----------
    HealthResponse:
      type: object
      required: [status, db]
      properties:
        status: { type: string, enum: ["ok", "error"] }
        db: { type: string, enum: ["ok", "unreachable"] }
      example:
        status: "ok"
        db: "ok"

  responses:
    UnauthorizedError:
      description: Missing, invalid, expired, or revoked JWT.
      content:
        application/json:
          schema: { $ref: "#/components/schemas/ErrorResponse" }
          examples:
            expired:
              value:
                {
                  error: "token_expired",
                  message: "Your session has expired. Please log in again.",
                }
            revoked:
              value:
                {
                  error: "token_revoked",
                  message: "Your session is no longer valid. Please log in again.",
                }
    NotFoundError:
      description: Resource does not exist, is soft-deleted, or is not owned by the authenticated user.
      content:
        application/json:
          schema: { $ref: "#/components/schemas/ErrorResponse" }
          examples:
            default:
              value:
                {
                  error: "not_found",
                  message: "The requested resource was not found.",
                }
    ValidationError:
      description: Request body failed schema or business-rule validation.
      content:
        application/json:
          schema: { $ref: "#/components/schemas/ValidationErrorResponse" }
    RateLimitedError:
      description: Too many requests. See Retry-After response header for the wait time in seconds.
      headers:
        Retry-After:
          schema: { type: integer }
          description: Seconds until the next request will be accepted.
      content:
        application/json:
          schema: { $ref: "#/components/schemas/ErrorResponse" }
          examples:
            default:
              value:
                {
                  error: "rate_limit_exceeded",
                  message: "Too many requests. Please try again shortly.",
                }

security:
  - cookieAuth: []

paths:
  # ============================================================
  # AUTH MODULE
  # ============================================================
  /auth/register:
    post:
      tags: [Auth]
      summary: Create a new user account and start the 14-day trial.
      description: |
        Creates the User (status=trial) and an empty Portfolio in one transaction, sets a
        7-day JWT cookie, and fires a BackgroundTask to send an email verification link.
        Registration succeeds even if the verification email later fails to send (BAS
        EX-007) — the account is immediately usable during the trial.
      security: []
      x-ratelimit: { requests: 3, period: 60, key: ip }
      x-audit-event: USER_REGISTERED
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/RegisterRequest" }
      responses:
        "201":
          description: Account created; JWT cookie set.
          headers:
            Set-Cookie: { schema: { type: string } }
          content:
            application/json:
              schema: { $ref: "#/components/schemas/AuthResponse" }
        "422": { $ref: "#/components/responses/ValidationError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /auth/login:
    post:
      tags: [Auth]
      summary: Authenticate with email and password; sets the JWT session cookie.
      security: []
      x-ratelimit: { requests: 5, period: 60, key: ip }
      x-audit-event: USER_LOGIN
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/LoginRequest" }
      responses:
        "200":
          description: Authenticated; JWT cookie set.
          headers:
            Set-Cookie: { schema: { type: string } }
          content:
            application/json:
              schema: { $ref: "#/components/schemas/AuthResponse" }
        "401":
          description: Invalid credentials. Identical body regardless of whether the email exists.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ErrorResponse" }
              examples:
                default:
                  value:
                    {
                      error: "invalid_credentials",
                      message: "Email or password is incorrect.",
                    }
        "429":
          description: |
            Either the standard per-IP rate limit, or an account lockout (BAS EX-009: 5
            failed attempts within 10 minutes locks further attempts for 10 minutes).
          headers:
            Retry-After:
              schema: { type: integer }
              description: Seconds until the next request will be accepted.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ErrorResponse" }
              examples:
                locked:
                  value:
                    {
                      error: "account_locked",
                      message: "Too many failed attempts. Please wait 10 minutes before trying again.",
                    }

  /auth/logout:
    post:
      tags: [Auth]
      summary: Invalidate the current session by incrementing token_version.
      description: |
        Increments User.token_version, which invalidates every JWT issued for this user
        (not just the calling session's cookie), and clears the session cookie.
      x-ratelimit: { requests: 60, period: 60, key: user }
      responses:
        "204": { description: Session invalidated. }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /auth/refresh:
    post:
      tags: [Auth]
      summary: Issue a new 7-day JWT cookie from a still-valid session (silent refresh).
      x-ratelimit: { requests: 60, period: 60, key: user }
      responses:
        "200":
          description: New JWT cookie set; current account status returned.
          headers:
            Set-Cookie: { schema: { type: string } }
          content:
            application/json:
              schema: { $ref: "#/components/schemas/AuthResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /auth/verify:
    get:
      tags: [Auth]
      summary: Verify an email address via a token sent in the registration email.
      description: Token is passed as a query parameter, not a path segment, to keep it out of typical path-based access-log capture.
      security: []
      x-ratelimit: { requests: 10, period: 60, key: ip }
      parameters:
        - name: token
          in: query
          required: true
          schema: { type: string }
      responses:
        "200":
          description: Email marked verified.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/UserResponse" }
        "400":
          description: Token not found, already used, or expired (>24 hours).
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ErrorResponse" }
              examples:
                expired:
                  value:
                    {
                      error: "invalid_token",
                      message: "This verification link has expired. Request a new one?",
                    }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /auth/password-reset-request:
    post:
      tags: [Auth]
      summary: Request a password reset email.
      description: |
        Always returns 200 with an identical body whether or not the email is registered
        (account enumeration protection, BAS Workflow 8 / EX-011). If the account exists, a
        single-use, 1-hour-expiry token is generated and emailed; the previous token for the
        same (user_id, type) is invalidated.
      security: []
      x-ratelimit: { requests: 3, period: 60, key: ip }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/PasswordResetRequest" }
      responses:
        "200":
          description: Identical response regardless of whether the account exists.
          content:
            application/json:
              schema:
                type: object
                required: [message]
                properties: { message: { type: string } }
              example:
                {
                  message: "If an account with that email exists, a reset link has been sent.",
                }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /auth/password-reset:
    post:
      tags: [Auth]
      summary: Complete a password reset using the emailed token.
      description: |
        Token and new password travel in the request body, never in the URL. On success,
        invalidates every active session for the user (token_version increment) and marks
        the token used (single-use enforcement).
      security: []
      x-ratelimit: { requests: 10, period: 60, key: ip }
      x-audit-event: PASSWORD_CHANGED
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/PasswordResetComplete" }
      responses:
        "200":
          description: Password updated; all sessions invalidated.
          content:
            application/json:
              schema:
                type: object
                required: [message]
                properties: { message: { type: string } }
              example:
                { message: "Password updated successfully. Please log in." }
        "400":
          description: Token not found, already used, or expired.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ErrorResponse" }
        "422": { $ref: "#/components/responses/ValidationError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /auth/jwks.json:
    get:
      tags: [Auth]
      summary: RS256 public signing key in JWKS format.
      security: []
      responses:
        "200":
          description: JWKS document.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/JwksResponse" }

  # ============================================================
  # PORTFOLIO MODULE
  # ============================================================
  /api/v1/portfolio/dashboard:
    get:
      tags: [Portfolio]
      summary: Full dashboard — portfolio summary plus all active positions with computed aggregates.
      description: All aggregates (cost, income, yield inputs) are computed at query time (ADR-004); nothing here is a stored roll-up.
      x-ratelimit: { requests: 60, period: 60, key: user }
      responses:
        "200":
          description: Dashboard data.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/PortfolioResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /api/v1/portfolio/positions:
    post:
      tags: [Portfolio]
      summary: Create a new position by adding its first lot.
      description: |
        The client supplies only the purchase description (stock, shares, price, date,
        broker). The server computes brokerage_fee, clearing_fee, stamp_duty, and
        all_in_cost — these fields must never be accepted from the client (P0-API-002). If
        the stock already exists as an active position for this user, the server treats this
        as an Add Lot operation on the existing position instead of creating a duplicate
        (BAS EC-001).
      x-ratelimit: { requests: 60, period: 60, key: user }
      x-audit-event: LOT_CREATED
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/CreatePositionRequest" }
      responses:
        "201":
          description: Position (and its first Lot) created.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/PositionResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "422": { $ref: "#/components/responses/ValidationError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /api/v1/portfolio/positions/{id}:
    parameters:
      - name: id
        in: path
        required: true
        schema: { type: string, format: uuid }
    get:
      tags: [Portfolio]
      summary: Get position detail with all active lots and dividend tranches.
      x-ratelimit: { requests: 60, period: 60, key: user }
      responses:
        "200":
          description: Position detail.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/PositionResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "404": { $ref: "#/components/responses/NotFoundError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }
    patch:
      tags: [Portfolio]
      summary: Update position metadata (category_tag and/or notes only).
      description: Does not accept any share, price, or fee fields — those live on Lot records, updated via the Lot endpoints.
      x-ratelimit: { requests: 60, period: 60, key: user }
      x-audit-event: POSITION_UPDATED
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/UpdatePositionRequest" }
      responses:
        "200":
          description: Updated position.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/PositionResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "404": { $ref: "#/components/responses/NotFoundError" }
        "422": { $ref: "#/components/responses/ValidationError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }
    delete:
      tags: [Portfolio]
      summary: Soft-delete a position and cascade soft-delete to all its lots and dividend tranches.
      x-ratelimit: { requests: 60, period: 60, key: user }
      x-audit-event: POSITION_DELETED
      responses:
        "204": { description: Position and all its lots/tranches soft-deleted. }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "404": { $ref: "#/components/responses/NotFoundError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /api/v1/portfolio/positions/{id}/lots:
    parameters:
      - name: id
        in: path
        required: true
        schema: { type: string, format: uuid }
    post:
      tags: [Portfolio]
      summary: Add a lot to an existing position.
      description: |
        Server-computed fee fields only (P0-API-002), identical rule to position creation.
        Adding a lot recalculates the position's aggregate totals but never alters any
        previously stored DividendTranche.total_amount (BAS BR-009, EC-022 regression case).
      x-ratelimit: { requests: 60, period: 60, key: user }
      x-audit-event: LOT_CREATED
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/CreateLotRequest" }
      responses:
        "201":
          description: Lot created.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/LotResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "404": { $ref: "#/components/responses/NotFoundError" }
        "422": { $ref: "#/components/responses/ValidationError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /api/v1/portfolio/positions/{id}/lots/{lot_id}:
    parameters:
      - name: id
        in: path
        required: true
        schema: { type: string, format: uuid }
      - name: lot_id
        in: path
        required: true
        schema: { type: string, format: uuid }
    patch:
      tags: [Portfolio]
      summary: Update a lot (shares, price, broker, and/or date), using optimistic locking.
      description: |
        Requires the caller's last-known `version`. On a version mismatch (another session
        updated the record first) returns 409 version_conflict. The server recomputes all
        fee fields from the resulting shares/price/broker — never accepts fee fields as
        input (P0-API-002). Ownership is verified on both the position and the lot
        (lot.position_id must equal the {id} in the path) to prevent cross-position lot
        access even within the same user's own portfolio.
      x-ratelimit: { requests: 60, period: 60, key: user }
      x-audit-event: LOT_UPDATED
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/UpdateLotRequest" }
      responses:
        "200":
          description: Updated lot with recomputed fee components.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/LotResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "404": { $ref: "#/components/responses/NotFoundError" }
        "409":
          description: Optimistic lock conflict — the record was modified since the client last read it.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ErrorResponse" }
              examples:
                default:
                  value:
                    {
                      error: "version_conflict",
                      message: "This record was modified by another session. Please refresh and try again.",
                    }
        "422": { $ref: "#/components/responses/ValidationError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }
    delete:
      tags: [Portfolio]
      summary: Soft-delete a specific lot.
      x-ratelimit: { requests: 60, period: 60, key: user }
      x-audit-event: LOT_DELETED
      responses:
        "204":
          { description: Lot soft-deleted; position aggregates recalculated. }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "404": { $ref: "#/components/responses/NotFoundError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /api/v1/portfolio/positions/{id}/sell-scenario:
    parameters:
      - name: id
        in: path
        required: true
        schema: { type: string, format: uuid }
    get:
      tags: [Portfolio]
      summary: Compute hypothetical sale proceeds and profit/loss across a range of prices.
      description: |
        Pure computation — nothing is persisted. If `price` is omitted, the response uses
        the default increment ladder (current price +0.01 through +0.05, then +0.10 through
        +0.70 in 0.05 steps, per BAS Workflow 6). Repeatable `price` query params add custom
        rows to the table. `disclaimer_required` is always true and carries the T+2
        settlement / informational-only notice (BR-020, BR-021).
      x-ratelimit: { requests: 60, period: 60, key: user }
      parameters:
        - name: shares
          in: query
          required: false
          schema: { type: integer, minimum: 1 }
          description: Defaults to the position's full active share count if omitted (partial sale per BR-024).
        - name: price
          in: query
          required: false
          style: form
          explode: true
          schema:
            type: array
            items: { type: string, pattern: "^[0-9]+\\.[0-9]{1,4}$" }
          description: Zero or more custom prices to add to the default scenario ladder.
        - name: broker_id
          in: query
          required: false
          schema: { type: string, format: uuid }
          description: Overrides the default sell-side broker (architecture assumption A-006) without altering stored position data.
      responses:
        "200":
          description: Scenario table.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/SellScenarioResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "404": { $ref: "#/components/responses/NotFoundError" }
        "422": { $ref: "#/components/responses/ValidationError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /api/v1/portfolio/dividends:
    post:
      tags: [Portfolio]
      summary: Log a dividend tranche for a position.
      description: |
        The client supplies per_share_amount and qualifying_shares (typically pre-filled by
        the frontend with the position's current total shares, but user-overridable per BAS
        FR-009 step 3a). The server computes and stores
        total_amount = per_share_amount × qualifying_shares. total_amount is never an
        accepted request field (P0-API-003). Rejected with 422 if qualifying_shares exceeds
        the position's current total_shares, or if the position already has 8 tranches for
        the resulting year (BR-014).
      x-ratelimit: { requests: 60, period: 60, key: user }
      x-audit-event: DIVIDEND_CREATED
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/CreateDividendRequest" }
      responses:
        "201":
          description: Tranche created with stored total_amount.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/DividendTrancheResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "404": { $ref: "#/components/responses/NotFoundError" }
        "422": { $ref: "#/components/responses/ValidationError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }
    get:
      tags: [Portfolio]
      summary: Dividend calendar — chronological list of tranches across the whole portfolio.
      x-ratelimit: { requests: 60, period: 60, key: user }
      parameters:
        - name: year
          in: query
          required: false
          schema: { type: integer, minimum: 1990 }
          description: Defaults to the current calendar year if omitted.
      responses:
        "200":
          description: Calendar entries, ascending by ex_dividend_date (falling back to payment_date).
          content:
            application/json:
              schema: { $ref: "#/components/schemas/DividendCalendarResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /api/v1/portfolio/dividends/{id}:
    parameters:
      - name: id
        in: path
        required: true
        schema: { type: string, format: uuid }
    patch:
      tags: [Portfolio]
      summary: Update a dividend tranche, using optimistic locking.
      description: |
        Requires the caller's last-known `version`. The server always recomputes
        total_amount from the resulting per_share_amount and qualifying_shares after
        applying the requested changes — total_amount is never an accepted request field on
        this schema, even though this is the endpoint most likely to be mis-implemented to
        allow a client-supplied total (P0-API-003).
      x-ratelimit: { requests: 60, period: 60, key: user }
      x-audit-event: DIVIDEND_UPDATED
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/UpdateDividendRequest" }
      responses:
        "200":
          description: Updated tranche with recomputed total_amount.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/DividendTrancheResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "404": { $ref: "#/components/responses/NotFoundError" }
        "409":
          description: Optimistic lock conflict.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ErrorResponse" }
              examples:
                default:
                  value:
                    {
                      error: "version_conflict",
                      message: "This record was modified by another session. Please refresh and try again.",
                    }
        "422": { $ref: "#/components/responses/ValidationError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }
    delete:
      tags: [Portfolio]
      summary: Soft-delete a dividend tranche.
      x-ratelimit: { requests: 60, period: 60, key: user }
      x-audit-event: DIVIDEND_DELETED
      responses:
        "204":
          {
            description: Tranche soft-deleted; position and portfolio yield inputs recalculated.,
          }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "404": { $ref: "#/components/responses/NotFoundError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  # ============================================================
  # PRICING MODULE
  # ============================================================
  /api/v1/pricing/prices:
    get:
      tags: [Pricing]
      summary: Get the latest price snapshot for one or more stock codes.
      x-ratelimit: { requests: 60, period: 60, key: user }
      parameters:
        - name: codes
          in: query
          required: true
          style: form
          explode: true
          schema:
            type: array
            items: { type: string }
          description: One or more Bursa stock codes.
      responses:
        "200":
          description: Latest snapshot per requested code (may include source=stale entries).
          content:
            application/json:
              schema:
                type: object
                required: [prices]
                properties:
                  prices:
                    type: array
                    items:
                      { $ref: "#/components/schemas/PriceSnapshotResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /api/v1/pricing/manual-override:
    post:
      tags: [Pricing]
      summary: Enter a manual price for a stale stock.
      description: |
        Creates a PriceSnapshot with source=manual. The override is superseded automatically
        by the next successful automated refresh (BAS Workflow 3). Blocked (403 is not used —
        this is a business-rule 422/paywall condition, not an ownership check) for
        trial_expired accounts per BAS EC-020, since manual price entry is a write action.
      x-ratelimit: { requests: 60, period: 60, key: user }
      x-audit-event: PRICE_OVERRIDE_CREATED
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/ManualPriceOverrideRequest" }
      responses:
        "201":
          description: Manual PriceSnapshot created; affected position's unrealised P&L recalculated.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/PriceSnapshotResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "422": { $ref: "#/components/responses/ValidationError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  # ============================================================
  # IMPORT MODULE
  # ============================================================
  /import/csv:
    post:
      tags: [Import]
      summary: Upload a CSV file for asynchronous portfolio/dividend import.
      description: |
        Pre-accept validation (Content-Length, Content-Type, UTF-8 decodability, row count,
        required headers) runs synchronously before 202 is returned. Row-level data
        validation (invalid stock codes, invalid dates, duplicate tranche labels, qualifying
        shares out of range) happens inside the BackgroundTask and is surfaced only via
        polling `GET /import/status/{job_id}`. The import is atomic: either every row is
        created or none are (BAS EX-004, EX-005). Only one ImportJob may be in `processing`
        status per user at a time.
      x-ratelimit: { requests: 2, period: 60, key: user }
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required: [file]
              properties:
                file:
                  type: string
                  format: binary
                  description: CSV file, max 1 MB (1,048,576 bytes), max 1,000 data rows, UTF-8 encoded.
      responses:
        "202":
          description: Import accepted; job created and processing asynchronously.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ImportJobResponse" }
        "400":
          description: Content-Type not CSV, non-UTF-8 encoding, row count exceeded, or a required column header missing.
          content:
            application/json:
              schema:
                oneOf:
                  - $ref: "#/components/schemas/ErrorResponse"
                  - $ref: "#/components/schemas/ValidationErrorResponse"
              examples:
                encoding:
                  value:
                    {
                      error: "encoding_error",
                      message: "File encoding error. Please save your CSV as UTF-8 before uploading.",
                    }
                rows:
                  value:
                    {
                      error: "row_limit_exceeded",
                      message: "File exceeds the maximum of 1,000 rows.",
                    }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "409":
          description: An import is already in progress for this user.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ErrorResponse" }
              examples:
                default:
                  value:
                    {
                      error: "already_processing",
                      message: "An import is already in progress. Please wait for it to complete or check its status.",
                      job_id: "ab12cd34-6666-4a1a-9999-abcdefabcdef",
                    }
        "413":
          description: File exceeds the 1 MB size limit.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ErrorResponse" }
              examples:
                default:
                  value:
                    {
                      error: "file_too_large",
                      message: "File exceeds the 1 MB size limit.",
                    }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /import/status/{job_id}:
    parameters:
      - name: job_id
        in: path
        required: true
        schema: { type: string, format: uuid }
    get:
      tags: [Import]
      summary: Poll the status of a CSV import job.
      description: |
        Ownership is verified — a user may only poll their own ImportJob (404 otherwise).
        The x-audit-event IMPORT_COMPLETED is written by the BackgroundTask when the job
        transitions to complete/failed, not by this GET request itself.
      x-ratelimit: { requests: 60, period: 60, key: user }
      responses:
        "200":
          description: Current job status; result is null until status is complete or failed.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ImportJobResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "404": { $ref: "#/components/responses/NotFoundError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  # ============================================================
  # SUBSCRIPTION MODULE
  # ============================================================
  /subscription/checkout:
    post:
      tags: [Subscription]
      summary: Initiate a Stripe Checkout session for the (single, V1) subscription plan.
      description: Account status is not changed here — activation happens only via the Stripe webhook after payment completes (architecture §10.4).
      x-ratelimit: { requests: 60, period: 60, key: user }
      responses:
        "200":
          description: Stripe-hosted checkout URL.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/CheckoutResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /subscription/status:
    get:
      tags: [Subscription]
      summary: Get the current subscription/account status.
      description: Polled by the frontend after returning from Stripe Checkout, until status transitions to active or 30 seconds elapse (architecture §10.4).
      x-ratelimit: { requests: 60, period: 60, key: user }
      responses:
        "200":
          description: Current status.
          content:
            application/json:
              schema:
                { $ref: "#/components/schemas/SubscriptionStatusResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /webhooks/stripe:
    post:
      tags: [Subscription]
      summary: Receive Stripe subscription lifecycle events.
      description: |
        The Stripe-Signature header is verified against STRIPE_WEBHOOK_SECRET before any
        event payload is parsed or trusted (OWASP API10). Idempotent by event.id — a
        re-delivered event that is already present in processed_webhook_events returns 200
        immediately without reprocessing (architecture §11.2). Handles
        checkout.session.completed (SUBSCRIPTION_ACTIVATED), invoice.payment_succeeded,
        invoice.payment_failed (sets grace_period), and customer.subscription.deleted
        (SUBSCRIPTION_CANCELLED).
      security:
        - stripeSignature: []
      x-ratelimit: { requests: 100, period: 60, key: ip }
      x-audit-events:
        - SUBSCRIPTION_ACTIVATED
        - SUBSCRIPTION_CANCELLED
      x-audit-events-description: |
        Exactly one of these two is written per successfully processed event, never both:
        SUBSCRIPTION_ACTIVATED on checkout.session.completed, SUBSCRIPTION_CANCELLED on
        customer.subscription.deleted. invoice.payment_succeeded and invoice.payment_failed
        are handled but do not currently map to an architecture §14.7 audit action value.
        This operation uses x-audit-events (plural, array) rather than the single-value
        x-audit-event extension used elsewhere in this spec, since its audit outcome is
        conditional on the incoming Stripe event type rather than fixed per endpoint.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              description: Raw Stripe event payload — not independently schema-validated beyond signature verification; structure is defined by Stripe, not BursaTrack.
      responses:
        "200":
          description: Event processed (or already processed — idempotent re-delivery).
          content:
            application/json:
              schema: { $ref: "#/components/schemas/WebhookAckResponse" }
        "400":
          description: Signature verification failed.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ErrorResponse" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  # ============================================================
  # ACCOUNT MODULE (PDPA)
  # ============================================================
  /api/v1/account/export:
    get:
      tags: [Account]
      summary: Download a complete export of the authenticated user's personal and financial data (PDPA right of access).
      description: |
        Streamed file download, not a typed JSON response body. Includes User, Portfolio,
        Position, Lot, DividendTranche, custom BrokerConfig, ImportJob, and AuditLog
        (action/entity_type/entity_id/created_at only — metadata excluded, as it may contain
        IP addresses). Excludes password_hash, token_version, soft-deleted records, shared
        PriceSnapshot data, and system BrokerConfig entries (architecture §10.7). Assembled
        synchronously in-memory — V1 data volumes (≤ ~400 records/user) do not require an
        async job.
      x-ratelimit: { requests: 60, period: 60, key: user }
      x-audit-event: DATA_EXPORT_DOWNLOADED
      responses:
        "200":
          description: File download.
          headers:
            Content-Disposition:
              schema:
                {
                  type: string,
                  example: 'attachment; filename="bursatrack-export-2026-06-30.json"',
                }
          content:
            application/json:
              schema: { $ref: "#/components/schemas/DataExportResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /account/delete:
    post:
      tags: [Account]
      summary: Initiate PDPA account deletion (30-day cancellable grace period).
      description: |
        Requires the literal confirmation string "DELETE". On success: account_status
        becomes pending_deletion, all sessions are invalidated immediately
        (token_version incremented — the account cannot log in again until cancelled), and a
        BackgroundTask sends a confirmation email containing a single-use cancellation link.
        Permanent hard-deletion happens 30 days later via the process_deletions.py cron job,
        not via any API call.
      x-ratelimit: { requests: 60, period: 60, key: user }
      x-audit-event: DELETION_REQUESTED
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/DeleteAccountRequest" }
      responses:
        "200":
          description: Deletion scheduled; session invalidated.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/DeletionAcceptedResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "422": { $ref: "#/components/responses/ValidationError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /account/cancel-deletion:
    get:
      tags: [Account]
      summary: Cancel a pending account deletion via the emailed cancellation token.
      description: |
        Token is a query parameter, not a path segment. Single-use and 24-hour expiry
        (pending_tokens table, type=deletion_cancellation). Unauthenticated by design — the
        account cannot log in while pending_deletion, so this must be reachable without a
        session.
      security: []
      x-ratelimit: { requests: 10, period: 60, key: ip }
      x-audit-event: DELETION_CANCELLED
      parameters:
        - name: token
          in: query
          required: true
          schema: { type: string }
      responses:
        "200":
          description: Account restored to its pre-deletion status.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/DeletionCancelledResponse" }
        "400":
          description: Token not found, already used, or expired.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ErrorResponse" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  # ============================================================
  # REFERENCE DATA MODULE
  # ============================================================
  /api/v1/stocks:
    get:
      tags: [Reference]
      summary: Search the Bursa Malaysia stock reference list (autocomplete).
      description: |
        Backed by an in-process TTLCache with a 60-minute TTL (architecture §12.4) — results
        may be up to 60 minutes stale relative to the underlying reference table, which is
        acceptable given the reference data changes roughly weekly. Inactive stocks
        (is_active=false) are always excluded. Capped at 10 results, ranked by match quality
        on code and name.
      x-ratelimit: { requests: 60, period: 60, key: user }
      parameters:
        - name: q
          in: query
          required: false
          schema: { type: string, minLength: 1 }
      responses:
        "200":
          description: Up to 10 matching active stocks.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/StockListResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /api/v1/brokers:
    get:
      tags: [Reference]
      summary: List all system broker configs plus the authenticated user's own custom broker configs.
      x-ratelimit: { requests: 60, period: 60, key: user }
      responses:
        "200":
          description: Broker list.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/BrokerListResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }
    post:
      tags: [Reference]
      summary: Create a custom broker fee configuration.
      x-ratelimit: { requests: 60, period: 60, key: user }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/CreateBrokerConfigRequest" }
      responses:
        "201":
          description: Custom broker created.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/BrokerConfigResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "422": { $ref: "#/components/responses/ValidationError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /api/v1/brokers/{id}:
    parameters:
      - name: id
        in: path
        required: true
        schema: { type: string, format: uuid }
    patch:
      tags: [Reference]
      summary: Update a custom broker fee configuration (own only; system brokers cannot be modified).
      x-ratelimit: { requests: 60, period: 60, key: user }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/UpdateBrokerConfigRequest" }
      responses:
        "200":
          description: Updated broker config.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/BrokerConfigResponse" }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "404": { $ref: "#/components/responses/NotFoundError" }
        "422": { $ref: "#/components/responses/ValidationError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }
    delete:
      tags: [Reference]
      summary: Delete a custom broker fee configuration (own only; blocked if referenced by any Lot).
      x-ratelimit: { requests: 60, period: 60, key: user }
      responses:
        "204": { description: Deleted. }
        "401": { $ref: "#/components/responses/UnauthorizedError" }
        "404": { $ref: "#/components/responses/NotFoundError" }
        "409":
          description: Broker config is referenced by one or more existing Lot records.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ErrorResponse" }
              examples:
                default:
                  value:
                    {
                      error: "in_use",
                      message: "This broker config is used by existing lots and cannot be deleted.",
                    }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  # ============================================================
  # ADMIN MODULE
  # ============================================================
  /admin/config/fees:
    get:
      tags: [Admin]
      summary: Get current system-wide fee/threshold configuration.
      security:
        - adminApiKey: []
      x-ratelimit: { requests: 60, period: 60, key: user }
      responses:
        "200":
          description: Current configuration values.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/AdminConfigResponse" }
        "401":
          description: Missing or invalid X-Admin-API-Key.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ErrorResponse" }
        "429": { $ref: "#/components/responses/RateLimitedError" }
    patch:
      tags: [Admin]
      summary: Update a single system-wide fee/threshold configuration value.
      description: |
        The in-process TTLCache is invalidated immediately after the update so the new value
        takes effect within the current process on the next read, without requiring a
        redeploy (architecture §12.4).
      security:
        - adminApiKey: []
      x-ratelimit: { requests: 60, period: 60, key: user }
      x-audit-event: CONFIG_UPDATED
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/AdminConfigUpdateRequest" }
      responses:
        "200":
          description: Updated configuration.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/AdminConfigResponse" }
        "401":
          description: Missing or invalid X-Admin-API-Key.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ErrorResponse" }
        "422": { $ref: "#/components/responses/ValidationError" }
        "429": { $ref: "#/components/responses/RateLimitedError" }

  /health:
    get:
      tags: [Health]
      summary: Database connectivity check for uptime monitoring.
      security: []
      responses:
        "200":
          description: System healthy.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/HealthResponse" }
              example: { status: "ok", db: "ok" }
        "503":
          description: Database unreachable. This is the only endpoint in the specification where 503 is a documented response.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/HealthResponse" }
              example: { status: "error", db: "unreachable" }
```

---

## Notes for Implementation

- This YAML block is complete and self-contained; extracting it verbatim into `openapi.yaml` (stripping the surrounding markdown fence) produces a document that validates against the OpenAPI 3.0.3 meta-schema and can be loaded directly into Swagger UI, Redoc, or an OpenAPI-to-TypeScript codegen tool.
- Every endpoint from the architecture's complete endpoint inventory (Stage 3 prompt) is present. No endpoint outside that inventory has been added.
- `x-ratelimit` values for endpoints not explicitly enumerated in architecture §14.4 (email verification, password-reset completion, deletion-cancellation, admin config) are **inferred, not architecture-stated** — flagged here for visibility and re-flagged as an open item in the Stage 4 review.
- **CSV template download (BAS FR-015 / US-019) is intentionally absent from this specification.** Per Stage 2 decision ADD-013 (resolving Stage 4 review finding PD-000), `BursaTrack_Import_Template.csv` is served as a static frontend asset (e.g. from the Next.js `public/` directory), not as a versioned API endpoint, since the file is fixed, non-personalized, and non-authenticated. This is a deliberate design decision, not an oversight — do not add a `GET /import/template` path without first revisiting ADD-013.
