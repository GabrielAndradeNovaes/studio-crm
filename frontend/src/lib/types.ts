export type StudioRole = "OWNER" | "PROFESSIONAL" | "RECEPTION";
export type SubscriptionStatus = "TRIAL" | "ACTIVE" | "PAST_DUE" | "SUSPENDED";
export type PaymentMethodCode = "PIX" | "CREDIT_CARD" | "DEBIT_CARD" | "CASH";

export interface AuthenticatedUserSummary {
  id: string;
  name: string;
  email: string;
  is_superadmin: boolean;
}

export interface StudioMembershipOption {
  studio_id: string;
  studio_name: string;
  studio_slug: string;
  role: StudioRole;
  timezone: string;
  enabled_modules: string[];
  subscription_status: SubscriptionStatus;
  is_studio_active: boolean;
  is_operational: boolean;
}

export interface AuthSessionResponse {
  requires_studio_selection: boolean;
  selection_token: string | null;
  access_token: string | null;
  token_type: string;
  expires_in: number | null;
  user: AuthenticatedUserSummary;
  current_studio: StudioMembershipOption | null;
  available_studios: StudioMembershipOption[];
}

export interface StudioDetails {
  id: string;
  name: string;
  slug: string;
  document: string | null;
  phone: string | null;
  plan_tier: string;
  enabled_modules: string[];
  timezone: string;
  subscription_status: SubscriptionStatus;
  trial_ends_at: string | null;
  commission_deducts_payment_fee: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PaymentMethodConfig {
  id: string;
  studio_id: string;
  method: PaymentMethodCode;
  label: string;
  fee_percentage: string;
  fixed_fee: string;
  is_active: boolean;
}

export interface TeamMemberOwner {
  membership_id: string;
  studio_id: string;
  user_id: string;
  name: string;
  email: string;
  role: StudioRole;
  commission_service_pct: string;
  commission_product_pct: string;
  is_active: boolean;
  created_at: string;
}

export interface TeamMemberDirectory {
  membership_id: string;
  studio_id: string;
  user_id: string;
  name: string;
  email: string;
  role: StudioRole;
  is_active: boolean;
}
