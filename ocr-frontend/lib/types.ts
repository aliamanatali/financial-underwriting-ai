// TypeScript types for OCR API integration

export type DocumentStatus =
  | "pending"
  | "processing"
  | "processing_chunks"
  | "extracting"
  | "completed"
  | "failed"
  | "error";
export type TaskStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
export type ChunkStatus = "pending" | "processing" | "completed" | "failed";

export interface Document {
  id: string;
  filename: string;
  upload_date: string;
  status: DocumentStatus;
  file_size?: number;
  page_count?: number;
  extraction_confidence?: number;
}

export interface DocumentResponse {
  document_id: string;
  filename: string;
  status: DocumentStatus;
  created_at: string;
  updated_at: string;
  progress_percentage?: number;
  error_message?: string | null;
  metadata?: {
    page_count?: number;
    file_size?: number;
  } | null;
}

export interface DocumentDetailsResponse extends DocumentResponse {
  extracted_text?: string | null;
  metadata?: {
    page_count?: number;
    has_handwriting?: boolean;
    quality?: string;
    file_size?: number;
    mime_type?: string;
    extraction_notes?: string | null;
  } | null;
  processing_time_seconds?: number | null;
  error_message?: string | null;
}

export interface UploadResponse {
  document_id: string;
  task_id: string;
  filename: string;
  status: DocumentStatus;
  message: string;
}

export interface ProcessingStatus {
  status: DocumentStatus;
  task_status: TaskStatus;
  progress_percentage: number;
  message: string;
}

export interface ChunkProgress {
  chunk_index: number;
  status: ChunkStatus;
  pages: string;
  error?: string;
}

export interface ProcessingProgress {
  document_id: string;
  status: DocumentStatus;
  progress_percentage?: number;
  total_chunks: number;
  completed_chunks: number;
  failed_chunks: number;
  processing_chunks?: number;
  current_chunk?: number | null; // Deprecated, use chunk_index from events
  chunk_index?: number; // Current chunk being processed (from SSE events)
  chunks?: ChunkProgress[] | Record<string, { status: string; error?: string }>;
  overall_progress?: number;
  error_message?: string;
  event?: string;
}

export interface FinancialAnalysisProgress {
  percentage: number;
  message: string;
  details?: {
    current_file?: string;
    file_index?: number;
    total_files?: number;
    file_type?: string;
    [key: string]: any;
  };
}

export interface ExtractedText {
  document_id: string;
  text: string;
  page_count: number;
  confidence?: number;
  metadata?: {
    extraction_method?: string;
    processing_time?: number;
    [key: string]: unknown;
  };
}

export interface ApiError {
  detail: string;
  status?: number;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}

// Financial Analysis Types
export interface PropertyMeta {
  address: string;
  year_built: number;
  purchase_price: number;
  total_units: number;
  current_loan_balance?: number;
}

export interface RentRollItem {
  unit_number: string;
  unit_size: number;
  unit_type: string;
  tenant_name: string;
  current_rent: number;
  stabilized_rent: number;
  market_rent: number;
  move_in_date: string;
  lease_start: string;
  lease_end: string;
  deposit?: number;
  parking?: string;
  comments?: string;
  source_file?: string;
}

export interface RentRollSummary {
  total_units: number;
  occupied_units: number;
  occupancy_rate: number;
  avg_unit_size: number;
  total_monthly_rent: number;
  total_annual_rent: number;
  total_stabilized_rent: number;
  total_market_rent: number;
  avg_rent_per_unit: number;
  avg_rent_per_sf: number;
  avg_stabilized_per_unit: number;
  avg_stabilized_per_sf: number;
  avg_market_per_unit: number;
  avg_market_per_sf: number;
}

export interface StandardizedExpense {
  original_text: string;
  mapped_category: string;
  amount: number;
  confidence: number;
  audit_log: AuditEntry;
  user_verified: boolean;
  user_corrected_category?: string;
}

export interface FinancialLineItem {
  category: string;
  value: number;
  period: string;
  type: string;
}

export interface DealParameters {
  growth_rate: number;
  exit_cap_rate: number;
  vacancy_rate: number;
  loan_amount?: number;
  min_unit_count?: number;
  max_unit_count?: number;
  max_build_year?: number;
  treasury_rate_5yr?: number;
  perm_spread?: number;
  units_override?: number;
  purchase_price_override?: number;
  occupancy_override?: number;
}

export interface UnitTypeSummary {
  unit_type: string;
  count: number;
  avg_rent: number;
  market_rent: number;
}

export interface AuditEntry {
  field_name: string;
  extracted_value: any;
  source: string;
  method: string;
  confidence_score?: number;
  timestamp?: string;
  reasons?: string[];
  document_id?: string;
  page_number?: number;
  bbox?: number[];
}

export interface ExplanationSource {
  document: string;
  fields_used: string[];
  data_type: string;
}

export interface ExplanationCalculation {
  formula: string;
  inputs: Record<string, number | string>;
}

export interface ExplainabilityMetadata {
  metric: string;
  value: number | string | null;
  source: ExplanationSource;
  calculation: ExplanationCalculation;
  adjustments: string[];
  classification: string;
}

export interface DecisionImpact {
  metric: string;
  decision: string;
  reasoning: string;
  impact: string;
}

export interface InvestmentChecklist {
    is_multifamily: string;
    is_multifamily_source?: string;
    
    near_campus: string;
    near_campus_source?: string;
    
    business_plan: string;
    business_plan_source?: string;
    
    rents_below_market: string;
    rents_below_market_source?: string;
    
    is_mismanaged: string;
    is_mismanaged_source?: string;
    
    diligence_issues: string;
    diligence_issues_source?: string;
    
    primary_risks: string;
    primary_risks_source?: string;
    
    price_per_unit_analysis: string;
    price_per_unit_source?: string;
}

export interface UnitTypeConfig {
    unit_type: string;
    bed_count: number;
    occupancy_type: "Single" | "Double" | "Mixed"; // Default "Single"
    unit_config_label: string; // e.g. "Single"

    // Advanced Configuration
    beds_single?: number;
    beds_double?: number;
    market_rent_single?: number;
    market_rent_double?: number;
}

export interface StudentHousingConfig {
    unit_type_configs: UnitTypeConfig[];
}

export interface Conclusion {
  summary: string;
  key_decisions: DecisionImpact[];
  investment_checklist?: InvestmentChecklist;
}

export interface UnderwritingAnalysis {
  document_id: string;
  pass_fail_status: string;
  gating_reasons: string[];
  property_meta: PropertyMeta;
  rent_roll: RentRollItem[];
  rent_roll_summary: RentRollSummary;
  unit_mix_summary?: UnitTypeSummary[];
  historical_expenses: StandardizedExpense[];
  deal_parameters?: DealParameters;
  audit_trail?: AuditEntry[];
  pro_forma_noi?: number;
  cap_rate?: number;
  historical_noi?: number;
  historical_cap_rate?: number;
  historical_total_expenses?: number;
  pro_forma_expenses?: number;
  irr?: number;
  moic?: number;
  cash_on_cash_return?: number;
  dscr?: number;
  debt_yield?: number;
  annual_debt_service?: number;
  explainability?: Record<string, ExplainabilityMetadata>;
  sensitivity_analysis?: {
    rows: number[];
    columns: number[];
    values: number[][];
  };
  conclusion?: Conclusion;
  analyst_commentary?: string;
  om_proforma?: OMProformaTable[];
  student_housing_config?: StudentHousingConfig;
}

export interface OMProformaRow {
  row_name: string;
  annual?: number;
  monthly?: number;
  per_unit?: number;
  percentage?: number;
}

export interface OMProformaTable {
  scenario_name: string;
  rows: OMProformaRow[];
  purchase_price?: number;
  cap_rate?: number;
  grm?: number;
}

export interface DocumentMetadata {
  document_id: string;
  filename: string;
  document_type: string;
  upload_timestamp: string;
  file_size: number;
  extraction_status: string;
}

export type DataClassification = "Sourced" | "Assumption" | "Recommendation";

export type CategoryGroup =
  | "Revenue"
  | "Operating Expense"
  | "Capital Expenditure"
  | "Property Info"
  | "Debt"
  | "Tax & Insurance"
  | "Other";

export interface NormalizedDataItem {
  id: string;
  raw_text: string;
  normalized_value: string;
  field_type: string;
  category_group: CategoryGroup;
  data_classification: DataClassification;
  confidence: number;
  user_verified: boolean;
  user_correction?: string | null;
  source_document: string;
  metadata?: Record<string, any>;
}

export interface DealPackage {
  package_id: string;
  property_name: string;
  created_at: string;
  updated_at: string;
  documents: Record<string, DocumentMetadata[]>;
  normalization_status: string;
  verification_progress: number;
  normalized_data?: NormalizedDataItem[];
  manual_overrides?: {
    total_units?: number;
    gross_potential_rent?: number;
    purchase_price?: number;
    year_built?: number;
    [key: string]: any;
  };
}