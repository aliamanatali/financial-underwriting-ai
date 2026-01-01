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
  unit_type: string;
  tenant_name: string;
  current_rent: number;
  market_rent: number;
  lease_start: string;
  lease_end: string;
}

export interface RentRollSummary {
  total_units: number;
  occupied_units: number;
  occupancy_rate: number;
  total_monthly_rent: number;
  total_annual_rent: number;
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
}

export interface AuditEntry {
  field: string;
  value: any;
  source: string;
  method: string;
  confidence_score?: number;
  timestamp?: string;
  reasons?: string[];
}

export interface UnderwritingAnalysis {
  document_id: string;
  pass_fail_status: string;
  gating_reasons: string[];
  property_meta: PropertyMeta;
  rent_roll: RentRollItem[];
  rent_roll_summary: RentRollSummary;
  historical_expenses: FinancialLineItem[];
  deal_parameters?: DealParameters;
  audit_trail?: AuditEntry[];
  pro_forma_noi?: number;
  cap_rate?: number;
  historical_noi?: number;
  historical_cap_rate?: number;
}