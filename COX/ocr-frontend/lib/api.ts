import { UnderwritingAnalysis, UploadResponse, DealParameters, ProcessingProgress } from "./types";

const OCR_API_URL = process.env.NEXT_PUBLIC_OCR_API_URL || "http://localhost:8001";
const FIN_API_URL = process.env.NEXT_PUBLIC_FINANCIAL_API_URL || "http://localhost:8000";

class ApiClient {
  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "An unknown error occurred." }));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
    return response.json();
  }

  // --- OCR Backend Methods ---

  async uploadDocument(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${OCR_API_URL}/api/documents/upload`, {
      method: 'POST',
      body: formData,
    });
    return this.handleResponse<UploadResponse>(response);
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

  // --- Financial Engine Methods ---

  async startAnalysis(documentId: string, params: DealParameters): Promise<UnderwritingAnalysis> {
    const response = await fetch(`${FIN_API_URL}/api/v1/analysis/${documentId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    return this.handleResponse<UnderwritingAnalysis>(response);
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
