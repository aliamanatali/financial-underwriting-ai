import { DocumentResponse, UnderwritingAnalysis, UploadResponse, DealParameters, ProcessingProgress, ExtractedText, DealPackage, FinancialAnalysisProgress } from "./types";

const OCR_API_URL = process.env.NEXT_PUBLIC_OCR_API_URL;
const FIN_API_URL = process.env.NEXT_PUBLIC_FINANCIAL_API_URL;

class ApiClient {
  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "An unknown error occurred." }));
      const detail = error.detail || `HTTP ${response.status}: ${response.statusText}`;
      throw new Error(detail);
    }
    return response.json();
  }

  // --- Health Check Methods ---

  async checkOCRBackend(): Promise<boolean> {
    try {
      const response = await fetch(`${OCR_API_URL}/health`, { method: 'GET' });
      return response.ok;
    } catch (err) {
      console.error("OCR backend health check failed:", err);
      return false;
    }
  }

  async checkFinancialBackend(): Promise<boolean> {
    try {
      const response = await fetch(`${FIN_API_URL}/health`, { method: 'GET' });
      return response.ok;
    } catch (err) {
      console.error("Financial backend health check failed:", err);
      return false;
    }
  }

  // --- OCR Backend Methods ---

  async uploadDocument(
    file: File,
    onProgress?: (progress: { loaded: number; total: number; percentage: number }) => void
  ): Promise<UploadResponse> {
    try {
      // Use fallback mime type if empty
      const mimeType = file.type || 'application/pdf';

      // 1. Get Signed URL
      const urlResponse = await fetch(`${OCR_API_URL}/api/documents/upload-url?filename=${encodeURIComponent(file.name)}&mime_type=${encodeURIComponent(mimeType)}`, {
        method: 'POST',
      });
      
      if (!urlResponse.ok) {
        throw new Error('Failed to get upload URL');
      }
      
      const { upload_url, document_id, storage_path } = await urlResponse.json();
      
      // 2. Upload directly to GCP using XMLHttpRequest for progress tracking
      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        
        if (onProgress) {
          xhr.upload.addEventListener('progress', (e: ProgressEvent) => {
            if (e.lengthComputable) {
              const percentComplete = (e.loaded / e.total) * 100;
              onProgress({
                loaded: e.loaded,
                total: e.total,
                percentage: percentComplete,
              });
            }
          });
        }
        
        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        });
        
        xhr.addEventListener('error', () => {
          reject(new Error('Network error during upload'));
        });
        
        xhr.open('PUT', upload_url);
        xhr.setRequestHeader('Content-Type', mimeType);
        xhr.send(file);
      });
      
      // 3. Confirm upload and trigger processing
      const confirmResponse = await fetch(`${OCR_API_URL}/api/documents/upload-confirm`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          document_id,
          storage_path,
          filename: file.name,
          mime_type: mimeType
        }),
      });
      
      if (!confirmResponse.ok) {
        const error = await confirmResponse.json().catch(() => ({ detail: "Confirmation failed" }));
        throw new Error(error.detail || 'Failed to confirm upload');
      }
      
      return await confirmResponse.json();
      
    } catch (error) {
      console.error("Upload error:", error);
      throw error;
    }
  }

  streamDocumentProgress(documentId: string, onProgress: (progress: ProcessingProgress) => void): EventSource {
    const eventSource = new EventSource(`${OCR_API_URL}/api/documents/${documentId}/progress/stream`);
    eventSource.onmessage = (event) => {
      const progress = JSON.parse(event.data);
      onProgress(progress);
    };
    eventSource.onerror = (err) => {
      console.error("EventSource failed:", err);
      eventSource.close();
    };
    return eventSource;
  }

  streamFinancialAnalysisProgress(documentId: string, onProgress: (progress: FinancialAnalysisProgress) => void): EventSource {
    console.log(`[SSE] Connecting to progress stream for ${documentId}...`);
    const eventSource = new EventSource(`${FIN_API_URL}/api/v1/progress/${documentId}`);
    
    eventSource.onopen = () => {
      console.log(`[SSE] Connection opened for ${documentId}`);
    };

    eventSource.onmessage = (event) => {
      try {
        const progress = JSON.parse(event.data);
        console.log(`[SSE] Progress update for ${documentId}:`, progress);
        onProgress(progress);
      } catch (e) {
        console.error(`[SSE] Error parsing message for ${documentId}:`, e);
      }
    };

    eventSource.onerror = (err) => {
      // It's normal for the connection to close when finished or on error,
      // the caller should handle closing explicitly or we can let it auto-retry if needed.
      console.log(`[SSE] Connection error/closed for ${documentId}:`, err);
    };
    
    return eventSource;
  }

  async listDocuments(): Promise<DocumentResponse[]> {
    const response = await fetch(`${OCR_API_URL}/api/documents`);
    const data = await this.handleResponse<{ documents: DocumentResponse[] }>(response);
    return data.documents;
  }

  async getDocument(documentId: string): Promise<DocumentResponse> {
    const response = await fetch(`${OCR_API_URL}/api/documents/${documentId}`);
    return this.handleResponse<DocumentResponse>(response);
  }

  async getDocumentText(documentId: string): Promise<ExtractedText> {
    const response = await fetch(`${OCR_API_URL}/api/documents/${documentId}/text`);
    return this.handleResponse<ExtractedText>(response);
  }

  async deleteDocument(documentId: string): Promise<void> {
    const response = await fetch(`${OCR_API_URL}/api/documents/${documentId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "An unknown error occurred." }));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
    // No content expected on successful deletion
  }

  async getDocumentContentUrl(packageId: string, documentId: string): Promise<{
    signed_url?: string,
    content?: string,
    encoding?: string,
    content_type?: string,
    filename?: string
  }> {
    const response = await fetch(`${FIN_API_URL}/api/v1/multi-document/packages/${packageId}/documents/${documentId}/content`);
    return this.handleResponse(response);
  }

  // --- Financial Engine Methods ---

  async startAnalysis(documentId: string, params: DealParameters): Promise<UnderwritingAnalysis> {
    const response = await fetch(`${FIN_API_URL}/api/v1/analysis/${documentId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    return this.handleResponse<UnderwritingAnalysis>(response);
  }

  async updateAnalysis(documentId: string, analysisData: UnderwritingAnalysis): Promise<void> {
    const response = await fetch(`${FIN_API_URL}/api/v1/analysis/${documentId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(analysisData),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "An unknown error occurred." }));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
  }

  async getDealPackages(limit: number = 5, offset: number = 0): Promise<{
    packages: DealPackage[];
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  }> {
    const response = await fetch(`${FIN_API_URL}/api/v1/multi-document/packages?limit=${limit}&offset=${offset}`);
    return this.handleResponse<{
      packages: DealPackage[];
      total: number;
      limit: number;
      offset: number;
      has_more: boolean;
    }>(response);
  }

  async renameDealPackage(packageId: string, newName: string): Promise<void> {
    const response = await fetch(`${FIN_API_URL}/api/v1/multi-document/packages/${packageId}/rename?new_name=${encodeURIComponent(newName)}`, {
      method: 'PATCH',
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "An unknown error occurred." }));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
  }

  async deleteDealPackage(packageId: string): Promise<void> {
    const response = await fetch(`${FIN_API_URL}/api/v1/multi-document/packages/${packageId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "An unknown error occurred." }));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
  }

  async updateManualOverrides(packageId: string, overrides: Record<string, any>): Promise<void> {
    const response = await fetch(`${FIN_API_URL}/api/v1/multi-document/packages/${packageId}/manual-overrides`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(overrides),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "An unknown error occurred." }));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
  }

  async updateDocumentCategory(packageId: string, documentId: string, newCategory: string): Promise<void> {
    const response = await fetch(`${FIN_API_URL}/api/v1/multi-document/packages/${packageId}/documents/${documentId}/category?new_category=${encodeURIComponent(newCategory)}`, {
      method: 'PUT',
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "An unknown error occurred." }));
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
  }

  async deleteDocumentFromPackage(packageId: string, documentId: string): Promise<void> {
    const response = await fetch(`${FIN_API_URL}/api/v1/multi-document/packages/${packageId}/documents/${documentId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "An unknown error occurred." }));
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
  }

  async uploadZipChunked(
    file: File,
    onProgress?: (progress: { loaded: number; total: number; percentage: number }) => void,
    onProcessingProgress?: (progress: { percentage: number; message: string }) => void,
    isSmartUpload: boolean = false
  ): Promise<DealPackage> {
    const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB chunks
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
    const fileName = file.name;

    // 1. Initialize upload
    const initFormData = new FormData();
    initFormData.append("filename", fileName);
    initFormData.append("total_chunks", totalChunks.toString());

    const initResponse = await fetch(`${FIN_API_URL}/api/v1/multi-document/packages/upload-chunk/init`, {
      method: "POST",
      body: initFormData,
    });

    if (!initResponse.ok) {
      throw new Error("Failed to initialize upload");
    }

    const { upload_id } = await initResponse.json();

    // 2. Upload chunks
    for (let i = 0; i < totalChunks; i++) {
      const start = i * CHUNK_SIZE;
      const end = Math.min(start + CHUNK_SIZE, file.size);
      const chunk = file.slice(start, end);

      const chunkFormData = new FormData();
      chunkFormData.append("upload_id", upload_id);
      chunkFormData.append("chunk_index", i.toString());
      chunkFormData.append("chunk", chunk);

      const chunkResponse = await fetch(`${FIN_API_URL}/api/v1/multi-document/packages/upload-chunk`, {
        method: "POST",
        body: chunkFormData,
      });

      if (!chunkResponse.ok) {
        throw new Error(`Failed to upload chunk ${i + 1}/${totalChunks}`);
      }

      if (onProgress) {
        const loaded = Math.min((i + 1) * CHUNK_SIZE, file.size);
        const percentage = Math.round((loaded / file.size) * 100);
        onProgress({
          loaded,
          total: file.size,
          percentage
        });
      }
    }

    // 3. Complete upload
    const completeFormData = new FormData();
    completeFormData.append("upload_id", upload_id);
    completeFormData.append("original_filename", fileName);
    
    if (isSmartUpload) {
      completeFormData.append("is_smart_upload", "true");
    }

    // Extract property name from filename (remove .zip and _Inputs suffix)
    const propertyName = fileName
      .replace('.zip', '')
      .replace('_Inputs', '')
      .replace(/_/g, ' ');
    completeFormData.append("property_name", propertyName);

    // Start listening for processing progress before calling complete
    let eventSource: EventSource | null = null;
    if (onProcessingProgress) {
        try {
            // Using the progress/stream endpoint with the upload_id as task_id
            eventSource = new EventSource(`${FIN_API_URL}/api/v1/progress/${upload_id}`);
            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.percentage !== undefined) {
                        onProcessingProgress({
                            percentage: data.percentage,
                            message: data.message || "Processing..."
                        });
                    }
                } catch (e) {
                    console.error("Error parsing progress event:", e);
                }
            };
            eventSource.onerror = (err) => {
                // Connection might close normally when task finishes or on error
                // We don't want to log heavy errors here as it might just be the stream ending
                // console.log("Progress stream closed/error", err);
                if (eventSource) {
                    eventSource.close();
                }
            };
        } catch (e) {
            console.error("Failed to setup progress stream:", e);
        }
    }

    try {
        const completeResponse = await fetch(`${FIN_API_URL}/api/v1/multi-document/packages/upload-chunk/complete`, {
          method: "POST",
          body: completeFormData,
        });

        if (!completeResponse.ok) {
          const errorData = await completeResponse.json().catch(() => ({ detail: "Upload completion failed" }));
          throw new Error(errorData.detail || "Upload completion failed");
        }

        return completeResponse.json();
    } finally {
        // Cleanup event source
        if (eventSource) {
            eventSource.close();
        }
    }
  }

  async uploadAdditionalDocuments(packageId: string, files: File[]): Promise<DealPackage> {
    const formData = new FormData();
    files.forEach((file) => {
        formData.append('files', file);
    });

    const response = await fetch(`${FIN_API_URL}/api/v1/multi-document/packages/${packageId}/documents`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(error.detail || "Upload failed");
    }

    return response.json();
  }

  async startUnderwritingAnalysis(documentId: string): Promise<UnderwritingAnalysis> {
    // Create default deal parameters
    const params: DealParameters = {
      growth_rate: 0.03,
      exit_cap_rate: 0.06,
      vacancy_rate: 0.03,
      loan_amount: 5000000,
      min_unit_count: 15,
      max_unit_count: 80,
      max_build_year: 1970,
    };

    // Call the original startAnalysis function with the default parameters
    return this.startAnalysis(documentId, params);
  }

  async downloadExport(analysisData: UnderwritingAnalysis, type: 'excel' | 'memo' | 'om-proforma' | 'rent-roll'): Promise<void> {
    let endpoint = '';
    let filename = '';

    switch (type) {
        case 'excel':
            endpoint = 'export/excel';
            filename = `financial_analysis_${analysisData.document_id}.xlsx`;
            break;
        case 'memo':
            endpoint = 'export/memo';
            filename = `investment_memo_${analysisData.document_id}.pdf`;
            break;
        case 'om-proforma':
            endpoint = 'export/om-proforma';
            filename = `om_proforma_${analysisData.document_id}.xlsx`;
            break;
        case 'rent-roll':
            endpoint = 'export/rent-roll';
            filename = `rent_roll_detail_${analysisData.document_id}.xlsx`;
            break;
    }

    if (!endpoint) {
        throw new Error(`Invalid export type: ${type}`);
    }

    const response = await fetch(`${FIN_API_URL}/api/v1/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(analysisData),
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "An unknown error occurred." }));
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  }

  async getRentRollPreview(analysisData: UnderwritingAnalysis): Promise<{
    columns: any[],
    rows: any[],
    summary_columns?: any[],
    summary_rows?: any[],
    stabilized_columns?: any[],
    stabilized_rows?: any[]
  }> {
    const response = await fetch(`${FIN_API_URL}/api/v1/export/rent-roll/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(analysisData),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "An unknown error occurred." }));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }

    return response.json();
  }
  async chatWithReport(documentId: string, messages: { role: string; content: string }[]): Promise<{ response: string }> {
    const response = await fetch(`${FIN_API_URL}/api/v1/analysis/${documentId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "An unknown error occurred." }));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  async *chatWithReportStream(documentId: string, messages: { role: string; content: string }[]): AsyncGenerator<string, void, unknown> {
    const response = await fetch(`${FIN_API_URL}/api/v1/analysis/${documentId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "An unknown error occurred." }));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }

    if (!response.body) throw new Error("No response body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.token) yield data.token;
            if (data.error) throw new Error(data.error);
          } catch (e) {
            console.error('Error parsing stream data:', e);
          }
        }
      }
    }
  }
}

export const apiClient = new ApiClient();
