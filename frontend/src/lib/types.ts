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
export type SaleStatus = "COMPLETED" | "REFUNDED";
export type SaleItemKind =
  | "PIERCING_SERVICE"
  | "PIERCING_PRODUCT"
  | "TATTOO_SESSION";
export type CommissionStatus = "PENDING" | "PAID" | "REVERSED";
export type FinancialTransactionType = "INCOME" | "EXPENSE" | "REVERSAL";
export type FinancialTransactionCategory =
  | "APPOINTMENT_DEPOSIT"
  | "SALE_PAYMENT"
  | "COMMISSION_PAYOUT"
  | "FIXED_EXPENSE"
  | "VARIABLE_EXPENSE"
  | "INVENTORY_PURCHASE"
  | "OTHER_INCOME"
  | "REFUND_OUTFLOW"
  | "MANUAL_REVERSAL";
export type CashFlowDirection = "INFLOW" | "OUTFLOW";

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

export interface SalePaymentItem {
  id: string;
  method: PaymentMethodCode;
  is_deposit: boolean;
  gross_amount: string;
  fee_percentage_snapshot: string;
  fee_amount: string;
  net_amount: string;
  paid_at: string;
}

export interface SaleItemRecord {
  id: string;
  item_kind: SaleItemKind;
  service_id: string | null;
  product_id: string | null;
  professional_id: string | null;
  description_snapshot: string;
  quantity: number;
  unit_price: string;
  discount_amount: string;
  total_item_amount: string;
  unit_cost_snapshot?: string;
}

export interface SaleRecord {
  id: string;
  studio_id: string;
  client_id: string | null;
  client_name: string | null;
  appointment_id: string | null;
  professional_id: string | null;
  professional_name: string | null;
  status: SaleStatus;
  competence_date: string;
  subtotal_amount: string;
  discount_amount: string;
  deposit_deducted_amount: string;
  total_due_amount: string;
  total_cost_snapshot?: string;
  notes: string | null;
  refunded_at: string | null;
  refund_reason: string | null;
  created_at: string;
  items: SaleItemRecord[];
  payments: SalePaymentItem[];
}

export interface CommissionItemRecord {
  id: string;
  studio_id: string;
  professional_id: string;
  professional_name: string;
  sale_id: string;
  sale_item_id: string | null;
  item_kind: SaleItemKind;
  description: string;
  base_amount: string;
  commission_pct_snapshot: string;
  commission_amount: string;
  status: CommissionStatus;
  paid_at: string | null;
  payout_transaction_id: string | null;
  created_at: string;
}

export interface MyCommissionsSummary {
  pending_total: string;
  paid_total: string;
  reversed_total: string;
  items: CommissionItemRecord[];
}

export interface CommissionPayoutResult {
  payout_transaction_id: string;
  professional_id: string;
  total_paid_amount: string;
  paid_count: number;
  paid_at: string;
}

export type ManualCategoryAllowed =
  | "FIXED_EXPENSE"
  | "VARIABLE_EXPENSE"
  | "INVENTORY_PURCHASE"
  | "OTHER_INCOME";

export interface FinancialTransactionRecord {
  id: string;
  studio_id: string;
  type: FinancialTransactionType;
  category: FinancialTransactionCategory;
  cash_flow_direction: CashFlowDirection;
  payment_method: PaymentMethodCode | null;
  description: string;
  gross_amount: string;
  fee_amount: string;
  net_amount: string;
  competence_date: string;
  paid_at: string;
  reference_sale_id: string | null;
  reference_payment_id: string | null;
  reference_appointment_id: string | null;
  reversed_transaction_id: string | null;
  created_by: string | null;
  created_at: string;
}

export interface CashflowPeriodSummary {
  total_inflows: string;
  total_outflows: string;
  net_balance: string;
  transactions: FinancialTransactionRecord[];
}

export interface PaymentMethodBreakdownItem {
  method: PaymentMethodCode;
  gross_amount: string;
  fee_amount: string;
  net_amount: string;
  count: number;
}

export interface DailyRegisterData {
  date: string;
  timezone: string;
  completed_sales_count: number;
  deposits_received_count: number;
  sales_checkout_gross: string;
  deposits_received_gross: string;
  refunds_outflow_total: string;
  net_operational_cash: string;
  by_payment_method: PaymentMethodBreakdownItem[];
  sales: SaleRecord[];
}

export interface ProfessionalPerformanceItem {
  professional_id: string;
  professional_name: string;
  items_count: number;
  gross_revenue_generated: string;
  commissions_generated: string;
}

export interface ExecutiveDashboardData {
  date_from: string;
  date_to: string;
  timezone: string;
  gross_revenue: string;
  cash_inflow_net: string;
  payment_fees_total: string;
  jewelry_cogs_total: string;
  commissions_generated_total: string;
  commissions_pending_total: string;
  operating_expenses_total: string;
  estimated_net_profit: string;
  completed_sales_count: number;
  average_ticket: string;
  by_payment_method: PaymentMethodBreakdownItem[];
  by_professional: ProfessionalPerformanceItem[];
}
