# Stage 3 — OpenAPI Contract Specification

## Your Role and Task

You are a senior API engineer producing the formal API contract for BursaTrack. The Stage 1 requirements analysis has mapped all business operations. The Stage 2 decision record has resolved all design decisions the architecture left implicit. Your job is to translate both into a complete, valid OpenAPI 3.0 YAML specification.

This specification is the contract between the FastAPI backend and the Next.js frontend. It must be correct and complete on first production — this is not a draft.

---

## Documents Provided

You have been given:
- Stage 1 API Requirements Report
- Stage 2 API Design Decision Record
- Solution Architecture Document (endpoint inventory at §7.2 and §10–§11, auth at §14, rate limits at §14.4, data types at §12.3)

---

## Non-Negotiable Technical Constraints

### Monetary and Rate Value Serialization

All monetary and rate fields in ALL request and response schemas must use `type: string` with a `format: decimal` annotation (not `type: number`). This applies without exception to:

| Field type | Example value in JSON |
|------------|-----------------------|
| Purchase price per share | `"8.3800"` |
| Fee amounts (brokerage, clearing, stamp duty, all-in cost) | `"41996.47"` |
| Dividend per share amount | `"0.004813"` |
| DividendTranche total_amount | `"1000.00"` |
| PriceSnapshot price | `"8.3800"` |
| BrokerConfig rate | `"0.001000"` |

Yield percentage is never in a response schema — it is computed client-side only.

### Server-Authoritative Fields — Never in Request Schemas

These fields must NOT appear in any request body schema:
- `brokerage_fee`, `clearing_fee`, `stamp_duty`, `all_in_cost` (computed by server from purchase inputs)
- `total_amount` for DividendTranche creation (computed from `per_share_amount × qualifying_shares`)
- `total_amount` for DividendTranche PATCH (server recomputes; client provides `per_share_amount` and/or `qualifying_shares`)

### Timestamp Format

All datetime fields use `type: string` with `format: date-time` (ISO 8601 UTC, e.g., `"2026-06-28T08:30:00Z"`).
Date-only fields (e.g., `purchase_date`, `ex_dividend_date`, `payment_date`) use `type: string` with `format: date` (e.g., `"2026-06-28"`).

### UUID Format

All ID fields use `type: string` with `format: uuid`.

---

## Complete Endpoint Inventory

The specification must cover all of the following endpoints. Do not add endpoints not on this list. Do not omit any endpoint on this list.

### Auth Module — No `/api/v1/` prefix

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | /auth/register | None | Create user account |
| POST | /auth/login | None | Authenticate and set JWT cookie |
| POST | /auth/logout | JWT | Invalidate session (increment token_version) |
| POST | /auth/refresh | JWT | Issue new 7-day JWT cookie |
| GET | /auth/verify | None | Verify email address via token query param |
| POST | /auth/password-reset-request | None | Initiate password reset (always 200) |
| POST | /auth/password-reset | None | Complete password reset via token |
| GET | /auth/jwks.json | None | RS256 public key (JWKS format) |

### Portfolio Module — `/api/v1/` prefix

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | /api/v1/portfolio/dashboard | JWT | Full dashboard data with computed aggregates |
| POST | /api/v1/portfolio/positions | JWT | Create position (first lot) |
| GET | /api/v1/portfolio/positions/{id} | JWT | Get position detail with all lots and tranches |
| PATCH | /api/v1/portfolio/positions/{id} | JWT | Update position metadata (category_tag, notes) |
| DELETE | /api/v1/portfolio/positions/{id} | JWT | Soft-delete position and all its lots and tranches |
| POST | /api/v1/portfolio/positions/{id}/lots | JWT | Add a lot to an existing position |
| PATCH | /api/v1/portfolio/positions/{id}/lots/{lot_id} | JWT | Update a specific lot (requires version) |
| DELETE | /api/v1/portfolio/positions/{id}/lots/{lot_id} | JWT | Soft-delete a specific lot |
| POST | /api/v1/portfolio/dividends | JWT | Log a dividend tranche |
| GET | /api/v1/portfolio/dividends | JWT | Dividend calendar view (filterable by year) |
| PATCH | /api/v1/portfolio/dividends/{id} | JWT | Update a dividend tranche (requires version) |
| DELETE | /api/v1/portfolio/dividends/{id} | JWT | Soft-delete a dividend tranche |
| GET | /api/v1/portfolio/positions/{id}/sell-scenario | JWT | Compute hypothetical sale fees and net proceeds |

### Pricing Module — `/api/v1/` prefix

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | /api/v1/pricing/prices | JWT | Get latest price snapshots for given stock codes |
| POST | /api/v1/pricing/manual-override | JWT | Enter manual price for a stale stock |

### Import Module — No `/api/v1/` prefix

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | /import/csv | JWT | Upload CSV file; returns 202 + job_id |
| GET | /import/status/{job_id} | JWT | Poll import job status |

### Subscription Module — No `/api/v1/` prefix

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | /subscription/checkout | JWT | Initiate Stripe checkout; returns checkout_url |
| GET | /subscription/status | JWT | Get current subscription/account status |
| POST | /webhooks/stripe | Stripe-Signature | Receive Stripe lifecycle events |

### Account Module — No `/api/v1/` prefix

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | /api/v1/account/export | JWT | PDPA data export (JSON file download) |
| POST | /account/delete | JWT | Initiate PDPA account deletion (30-day pending) |
| GET | /account/cancel-deletion | None | Cancel pending deletion via email token |

### Reference Data Module — `/api/v1/` prefix

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | /api/v1/stocks | JWT | Stock reference list (optionally filtered by ?q=) |
| GET | /api/v1/brokers | JWT | Broker configs (system + user's custom) |
| POST | /api/v1/brokers | JWT | Create custom broker config |
| PATCH | /api/v1/brokers/{id} | JWT | Update custom broker config |
| DELETE | /api/v1/brokers/{id} | JWT | Delete custom broker config |

### Admin Module — No `/api/v1/` prefix

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | /admin/config/fees | ADMIN_API_KEY | Get system configuration |
| PATCH | /admin/config/fees | ADMIN_API_KEY | Update system configuration |
| GET | /health | None | Database connectivity check |

---

## Required Security Schemes

Define three security schemes in `components/securitySchemes`:

1. **`cookieAuth`**: `type: apiKey`, `in: cookie`, `name: access_token`. Applied to all JWT-protected endpoints.
2. **`adminApiKey`**: `type: apiKey`, `in: header`, `name: X-Admin-API-Key` (or as decided in ADD-009). Applied only to admin endpoints.
3. **`stripeSignature`**: `type: apiKey`, `in: header`, `name: Stripe-Signature`. Applied only to `POST /webhooks/stripe`.

---

## Required Component Schemas

Define all reusable schemas under `components/schemas`. At minimum:

### Error Schemas
- `ErrorResponse`: universal error body (from ADD-002 decision)
- `ValidationErrorResponse`: field-level 422 error body (from ADD-002 decision)

### Request Schemas (no server-authoritative fields)
- `RegisterRequest`: email, password, broker_id
- `LoginRequest`: email, password
- `PasswordResetRequest`: email
- `PasswordResetComplete`: token, new_password
- `CreatePositionRequest`: stock_code, shares, purchase_price, broker_id, purchase_date, notes (optional)
- `CreateLotRequest`: shares, purchase_price, broker_id, purchase_date
- `UpdateLotRequest`: one or more of (shares, purchase_price, broker_id, purchase_date), plus `version`
- `UpdatePositionRequest`: category_tag (optional), notes (optional)
- `CreateDividendRequest`: position_id, per_share_amount, qualifying_shares, tranche_label, ex_dividend_date, payment_date (optional)
- `UpdateDividendRequest`: one or more of (per_share_amount, qualifying_shares, tranche_label, ex_dividend_date, payment_date), plus `version`
- `ManualPriceOverrideRequest`: stock_code, price, trading_date
- `CreateBrokerConfigRequest`: name, fee_type, rate or flat_fee, minimum_fee (optional)
- `UpdateBrokerConfigRequest`: one or more fields from CreateBrokerConfigRequest
- `AdminConfigUpdateRequest`: key, value
- `DeleteAccountRequest`: `confirmation` field (must equal string `"DELETE"`)

### Response Schemas
- `UserResponse`: user public fields (no password_hash, no token_version)
- `AuthResponse`: user fields + `expires_at` timestamp
- `PortfolioResponse`: dashboard aggregate structure
- `PositionResponse`: position with computed aggregates (total_shares, total_all_in_cost) and nested lots and dividend_tranches
- `PositionSummaryResponse`: position without lots/tranches (for list contexts)
- `LotResponse`: lot with all fee components (all as strings)
- `DividendTrancheResponse`: tranche with total_amount, qualifying_shares, per_share_amount (all as strings)
- `PriceSnapshotResponse`: price (as string), source, last_refreshed_at, stock_code
- `SellScenarioResponse`: projected_brokerage, projected_clearing, projected_stamp_duty, projected_all_in_sell_cost, projected_net_proceeds, disclaimer_required (boolean)
- `ImportJobResponse`: job_id, status, created_at, result (nullable until complete)
- `ImportJobResultResponse`: rows_imported, rows_failed, errors (array of row-level error objects)
- `SubscriptionStatusResponse`: account_status, trial_expiry_date, subscription_start_date, renewal_date
- `BrokerConfigResponse`: all fields including is_system, created_by_user_id
- `AdminConfigResponse`: array of {key, value, description, updated_at}
- `DataExportResponse`: stream (documented as binary download, not JSON)
- `HealthResponse`: status, db fields
- `StockResponse`: code, name, market, sector, instrument_type, is_active

---

## Validation Rules in Schemas

Embed these constraints directly in schema definitions using OpenAPI `minimum`, `maximum`, `pattern`, `enum`, `minLength`, `maxLength`:

| Field | Constraint |
|-------|-----------|
| `shares` (Lot creation) | `minimum: 1`, integer |
| `purchase_price` | string pattern `"^[0-9]+\.[0-9]{1,4}$"`, value > 0 (enforced in server) |
| `qualifying_shares` | `minimum: 1`, integer |
| `per_share_amount` | string pattern for up to 6 decimal places |
| `tranche_label` | `enum: ["1st","2nd","3rd","4th","5th","6th","7th","8th"]` |
| `category_tag` | `enum: ["Dividend","Volatile","Growth"]` |
| `broker_id` | format uuid |
| `confirmation` (delete) | `enum: ["DELETE"]` |
| `fee_type` (broker config) | `enum: ["percentage","flat"]` |
| `account_status` | `enum: ["trial","active","grace_period","trial_expired","pending_deletion"]` |
| CSV file | `maxLength` in multipart field description; content-type constrained |

---

## Rate Limit Documentation

For each endpoint or endpoint group, document rate limits using the `x-ratelimit` extension:

```yaml
x-ratelimit:
  requests: 3
  period: 60
  key: ip
```

Fields: `requests` (integer), `period` (seconds), `key` (`ip` or `user`).

---

## Audit Trail Annotation

For every endpoint that produces an audit_log entry, annotate with:

```yaml
x-audit-event: LOT_CREATED
```

Use the exact action values from architecture §14.7.

---

## Deliverable: OpenAPI 3.0 YAML Specification

Produce a complete, valid OpenAPI 3.0 YAML document. Structure:

```yaml
openapi: "3.0.3"
info:
  title: BursaTrack API
  version: "1.0.0"
  description: |
    REST API for BursaTrack — a dividend portfolio tracker for Malaysian retail investors.
    All monetary values are serialized as strings to preserve exact Decimal precision.
    Timestamps are ISO 8601 UTC. Authentication uses HTTP-only cookies.

servers:
  - url: https://api.bursatrack.com
    description: Production
  - url: http://localhost:8000
    description: Local development

components:
  securitySchemes: ...
  schemas: ...

paths:
  /auth/register: ...
  # ... all 28+ paths
```

Each path entry must include:
- `summary` (one sentence)
- `description` (when the summary alone is insufficient)
- `security` (the applicable security scheme, or `[]` for public)
- `parameters` (path params, query params with type, required, description)
- `requestBody` (for POST/PATCH; schema ref + example)
- `responses` (all applicable status codes with schema refs and examples)
- `x-ratelimit` (rate limit annotation)
- `x-audit-event` (for state-changing endpoints that produce audit logs)

---

## Guardrails

Do not:
- Use `type: number` or `type: integer` for any monetary or rate field
- Include `total_amount` in DividendTranche request schemas as an accepted input field
- Include fee components in Lot creation or update request schemas as accepted inputs
- Add endpoints not present in the endpoint inventory above
- Return `403 Forbidden` for cross-user resource access — the schema must document `404`
- Use `type: string` without format for UUID, datetime, or date fields — always include the format annotation
- Omit examples from response schemas — examples are required for each schema
- Add pagination to endpoints that do not require it (most endpoints are single-user data at V1 scale and do not need pagination)
