import { DocumentResponse, UnderwritingAnalysis, UploadResponse, DealParameters, ProcessingProgress, ExtractedText, DealPackage } from "./types";

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

    return new Promise((resolve, reject) => {
      xhr.addEventListener('load', () => {
        if (xhr.status === 200) {
          try {
            const response = JSON.parse(xhr.responseText);
            resolve(response as UploadResponse);
          } catch (e) {
            reject(new Error('Failed to parse upload response'));
          }
        } else {
          try {
            const error = JSON.parse(xhr.responseText);
            reject(new Error(error.detail || `Upload failed with status ${xhr.status}`));
          } catch (e) {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        }
      });

      xhr.addEventListener('error', () => {
        reject(new Error('Upload request failed'));
      });

      const formData = new FormData();
      formData.append('file', file);

      xhr.open('POST', `${OCR_API_URL}/api/documents/upload`);
      xhr.send(formData);
    });
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

  // --- Financial Engine Methods ---

  async startAnalysis(documentId: string, params: DealParameters): Promise<UnderwritingAnalysis> {
    const response = await fetch(`${FIN_API_URL}/api/v1/analysis/${documentId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    return this.handleResponse<UnderwritingAnalysis>(response);
  }

  async getDealPackages(): Promise<DealPackage[]> {
    const response = await fetch(`${FIN_API_URL}/api/v1/multi-document/packages`);
    return this.handleResponse<DealPackage[]>(response);
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

  async downloadExport(analysisData: UnderwritingAnalysis, type: 'excel' | 'memo'): Promise<void> {
    const endpoint = type === 'excel' ? 'export/excel' : 'export/memo';
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
    a.download = type === 'excel' ? `financial_analysis_${analysisData.document_id}.xlsx` : `investment_memo_${analysisData.document_id}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  }
}

export const apiClient = new ApiClient();
