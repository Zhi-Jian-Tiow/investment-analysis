// Mirrors backend/app/auth/schemas.py and backend/app/portfolio/schemas.py.
// Kept as plain types (not generated) since there's no shared schema tooling
// yet — if the backend shapes drift, these need updating by hand.

export interface UserResponse {
  id: string;
  email: string;
  email_verified: boolean;
  account_status: "trial" | "active" | "grace_period" | "trial_expired" | "pending_deletion";
  trial_expiry_date: string;
  subscription_start_date: string | null;
  subscription_renewal_date: string | null;
  default_broker_id: string | null;
  created_at: string;
}

export interface AuthResponse {
  user: UserResponse;
  expires_at: string;
}

export interface BrokerConfigResponse {
  id: string;
  name: string;
  fee_type: "percentage" | "flat";
  rate: string | null;
  minimum_fee: string | null;
  flat_fee: string | null;
  is_system: boolean;
  created_by_user_id: string | null;
  created_at: string;
}

export interface BrokerListResponse {
  brokers: BrokerConfigResponse[];
}

export type CategoryTag = "Dividend" | "Volatile" | "Growth";

export interface CreatePositionRequest {
  stock_code: string;
  stock_name: string;
  shares: number;
  purchase_price: string;
  broker_id: string;
  purchase_date: string;
  category_tag: CategoryTag;
  notes?: string | null;
}

export interface LotResponse {
  id: string;
  position_id: string;
  shares: number;
  purchase_price: string;
  purchase_date: string;
  broker_id: string;
  initial_amount: string;
  brokerage_fee: string;
  clearing_fee: string;
  stamp_duty: string;
  all_in_cost: string;
  version: number;
  created_at: string;
  updated_at: string;
  warnings: string[];
}

export interface PositionSummaryResponse {
  id: string;
  stock_code: string;
  stock_name: string;
  category_tag: CategoryTag;
  total_shares: number;
  total_all_in_cost: string;
  blended_purchase_price: string;
  total_dividend_income_ytd: string;
  current_price: string | null;
  price_source: "automated" | "manual" | "stale" | null;
  price_last_refreshed_at: string | null;
  current_market_value: string | null;
  unrealised_pnl: string | null;
}

export type DividendTrancheLabel = "1st" | "2nd" | "3rd" | "4th" | "5th" | "6th" | "7th" | "8th";

export interface CreateDividendRequest {
  position_id: string;
  tranche_label: DividendTrancheLabel;
  per_share_amount: string;
  qualifying_shares: number;
  payment_date: string;
  ex_dividend_date?: string | null;
}

export interface DividendTrancheResponse {
  id: string;
  position_id: string;
  tranche_label: DividendTrancheLabel;
  per_share_amount: string;
  qualifying_shares: number;
  total_amount: string;
  payment_date: string;
  ex_dividend_date: string | null;
  year: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface PositionResponse extends PositionSummaryResponse {
  notes: string | null;
  lots: LotResponse[];
  dividend_tranches: DividendTrancheResponse[];
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  warnings: string[];
}

export interface DividendCalendarEntry {
  id: string;
  position_id: string;
  stock_code: string;
  stock_name: string;
  tranche_label: DividendTrancheLabel;
  per_share_amount: string;
  qualifying_shares: number;
  total_amount: string;
  payment_date: string;
  ex_dividend_date: string | null;
  year: number;
  version: number;
  created_at: string;
  updated_at: string;
  is_paid: boolean;
  is_upcoming: boolean;
}

export interface DividendCalendarResponse {
  tranches: DividendCalendarEntry[];
}

export interface PortfolioResponse {
  total_all_in_cost: string;
  total_dividend_income_ytd: string;
  last_price_refresh_at: string | null;
  positions: PositionSummaryResponse[];
}

export interface SellScenarioRow {
  price: string;
  gross_proceeds: string;
  projected_brokerage: string;
  projected_clearing_fee: string;
  projected_stamp_duty: string;
  projected_all_in_sell_cost: string;
  projected_net_proceeds: string;
  profit_loss: string;
  break_even: boolean;
}

export interface SellScenarioResponse {
  position_id: string;
  shares_to_sell: number;
  buy_cost_basis: string;
  broker_id: string;
  disclaimer_required: boolean;
  scenarios: SellScenarioRow[];
}
