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
