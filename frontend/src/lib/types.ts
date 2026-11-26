export type StudioRole = "OWNER" | "PROFESSIONAL" | "RECEPTION";
export type SubscriptionStatus = "TRIAL" | "ACTIVE" | "PAST_DUE" | "SUSPENDED";
export type PaymentMethodCode = "PIX" | "CREDIT_CARD" | "DEBIT_CARD" | "CASH";
export type LeadSource =
  | "INSTAGRAM"
  | "INDICACAO"
  | "GOOGLE"
  | "PASSANTE"
  | "OUTRO";
export type PiercingItemType = "JEWELRY" | "AFTERCARE_PRODUCT";
export type InventoryMovementType =
  | "IN_PURCHASE"
  | "OUT_SALE"
  | "RETURN_REFUND"
  | "ADJUSTMENT";

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

export interface ClientRecord {
  id: string;
  studio_id: string;
  full_name: string;
  whatsapp: string;
  email: string | null;
  birth_date: string;
  age: number;
  is_minor: boolean;
  cpf: string | null;
  lead_source: LeadSource;
  tags: string[];
  notes: string | null;
  guardian_name: string | null;
  guardian_cpf: string | null;
  guardian_whatsapp: string | null;
  guardian_relationship: string | null;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface PiercingServiceItem {
  id: string;
  studio_id: string;
  name: string;
  anatomical_site: string;
  duration_minutes: number;
  base_price: string;
  return_days_downsize: number | null;
  aftercare_instructions: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PiercingProductItem {
  id: string;
  studio_id: string;
  sku: string | null;
  name: string;
  item_type: PiercingItemType;
  category_site: string | null;
  material: string | null;
  threading_type: string | null;
  gauge_thickness: string | null;
  length_diameter: string | null;
  /** Presente exclusivamente para OWNER; omitido pela API para RECEPTION/PROFESSIONAL */
  cost_price?: string;
  sale_price: string;
  stock_quantity: number;
  min_stock_alert: number;
  is_low_stock: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface InventoryMovementItem {
  id: string;
  studio_id: string;
  product_id: string;
  movement_type: InventoryMovementType;
  quantity_delta: number;
  resulting_stock: number;
  /** Presente exclusivamente para OWNER; omitido pela API para RECEPTION/PROFESSIONAL */
  unit_cost_snapshot?: string;
  reference_sale_id: string | null;
  reason: string;
  created_by: string | null;
  created_at: string;
}
