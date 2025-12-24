// TypeScript types for OCR API integration

export type DocumentStatus = "pending" | "processing" | "completed" | "failed";
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
  status: string;
  extracted_text?: string | null;
  metadata?: {
    page_count?: number;
    has_handwriting?: boolean;
    quality?: string;
    file_size?: number;
    mime_type?: string;
    extraction_notes?: string | null;
  } | null;
  created_at: string;
  updated_at: string;
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
