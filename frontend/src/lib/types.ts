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
export type AppointmentStatus =
  | "AGENDADO"
  | "CONFIRMADO"
  | "EM_ATENDIMENTO"
  | "CONCLUIDO"
  | "CANCELADO"
  | "FALTOU";
export type DepositStatus =
  | "NONE"
  | "PAID"
  | "APPLIED_TO_SALE"
  | "REFUNDED"
  | "FORFEITED";

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
  unit_cost_snapshot?: string;
  reference_sale_id: string | null;
  reason: string;
  created_by: string | null;
  created_at: string;
}

export interface AppointmentItem {
  id: string;
  studio_id: string;
  client_id: string;
  client_name: string;
  client_whatsapp: string;
  client_is_minor: boolean;
  professional_id: string;
  professional_name: string;
  module: string;
  service_id: string | null;
  service_name: string | null;
  start_at: string;
  end_at: string;
  status: AppointmentStatus;
  notes: string | null;
  deposit_amount: string;
  deposit_payment_method: PaymentMethodCode | null;
  deposit_status: DepositStatus;
  deposit_paid_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AnamnesisFieldSchema {
  key: string;
  label: string;
  type: "boolean" | "boolean_with_details" | "text" | "textarea";
  required: boolean;
  placeholder?: string | null;
  details_placeholder?: string | null;
}

export interface AnamnesisTemplateItem {
  id: string;
  studio_id: string;
  module: string;
  version: number;
  title: string;
  fields_schema: AnamnesisFieldSchema[];
  consent_text: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AnamnesisRecordSummary {
  id: string;
  studio_id: string;
  client_id: string;
  client_name: string;
  appointment_id: string | null;
  template_id: string;
  template_version: number;
  module: string;
  guardian_signed_name: string | null;
  consent_accepted: boolean;
  consent_accepted_at: string | null;
  created_by: string | null;
  created_at: string;
}

export interface AnamnesisRecordDetail extends AnamnesisRecordSummary {
  template_title: string;
  fields_schema: AnamnesisFieldSchema[];
  consent_text: string;
  answers: Record<string, unknown>;
  consent_ip: string | null;
  consent_user_agent: string | null;
  signature_payload: string | null;
}

export interface PublicAnamnesisLinkCreated {
  link_id: string;
  raw_token: string;
  public_path: string;
  expires_at: string;
  client_id: string;
  client_name: string;
  client_whatsapp: string;
}

export interface PublicAnamnesisFormView {
  studio_name: string;
  client_first_name: string;
  is_minor: boolean;
  module: string;
  template_title: string;
  template_version: number;
  fields_schema: AnamnesisFieldSchema[];
  consent_text: string;
  expires_at: string;
}

export interface PiercingProcedureItem {
  id: string;
  studio_id: string;
  client_id: string;
  client_name: string;
  client_whatsapp: string;
  appointment_id: string | null;
  sale_id: string | null;
  professional_id: string;
  professional_name: string;
  service_id: string;
  service_name: string;
  jewelry_product_id: string | null;
  jewelry_name: string | null;
  anatomical_site_detail: string;
  sterilization_lot: string | null;
  healing_notes: string | null;
  performed_at: string;
  downsize_reminder_date: string | null;
  downsize_completed_at: string | null;
  is_overdue: boolean;
  days_until_due: number | null;
  created_at: string;
  updated_at: string;
}
