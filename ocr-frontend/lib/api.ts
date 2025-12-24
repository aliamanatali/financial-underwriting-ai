// API client for FastAPI backend integration

import {
  DocumentResponse,
  UploadResponse,
  ExtractedText,
  ApiError,
  UploadProgress,
  ProcessingStatus,
  ProcessingProgress,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * Handle API errors
   */
  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        detail: `HTTP error! status: ${response.status}`,
        status: response.status,
      }));
      throw new Error(error.detail || "An error occurred");
    }
    return response.json();
  }

  /**
   * Upload a PDF document to the backend
   */
  async uploadDocument(
    file: File,
    onProgress?: (progress: UploadProgress) => void
  ): Promise<UploadResponse> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      // Track upload progress
      if (onProgress) {
        xhr.upload.addEventListener("progress", (e) => {
          if (e.lengthComputable) {
            const progress: UploadProgress = {
              loaded: e.loaded,
              total: e.total,
              percentage: Math.round((e.loaded / e.total) * 100),
            };
            onProgress(progress);
          }
        });
      }

      // Handle completion
      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            resolve(response);
          } catch (error) {
            reject(new Error("Failed to parse response"));
          }
        } else {
          try {
            const error = JSON.parse(xhr.responseText);
            reject(new Error(error.detail || `Upload failed: ${xhr.status}`));
          } catch {
            reject(new Error(`Upload failed: ${xhr.status}`));
          }
        }
      });

      // Handle errors
      xhr.addEventListener("error", () => {
        reject(new Error("Network error occurred"));
      });

      xhr.addEventListener("abort", () => {
        reject(new Error("Upload aborted"));
      });

      // Prepare and send request
      const formData = new FormData();
      formData.append("file", file);

      xhr.open("POST", `${this.baseUrl}/api/documents/upload`);
      xhr.send(formData);
    });
  }

  /**
   * Get document details by ID
   */
  async getDocument(id: string): Promise<DocumentResponse> {
    const response = await fetch(`${this.baseUrl}/api/documents/${id}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });
    return this.handleResponse<DocumentResponse>(response);
  }

  /**
   * Get extracted text from a document
   */
  async getDocumentText(id: string): Promise<ExtractedText> {
    const response = await fetch(`${this.baseUrl}/api/documents/${id}/text`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });
    return this.handleResponse<ExtractedText>(response);
  }

  /**
   * Get list of all documents
   */
  async listDocuments(): Promise<DocumentResponse[]> {
    const response = await fetch(`${this.baseUrl}/api/documents`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });
    const data = await this.handleResponse<{
      documents: DocumentResponse[];
      total: number;
    }>(response);
    return data.documents;
  }

  /**
   * Delete a document by ID
   */
  async deleteDocument(id: string): Promise<{ message: string }> {
    const response = await fetch(`${this.baseUrl}/api/documents/${id}`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
    });
    return this.handleResponse<{ message: string }>(response);
  }

  /**
   * Get processing status for a document
   */
  async getDocumentStatus(id: string): Promise<ProcessingStatus> {
    const response = await fetch(`${this.baseUrl}/api/documents/${id}/status`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });
    return this.handleResponse<ProcessingStatus>(response);
  }

  /**
   * Get detailed processing progress for a document
   */
  async getDocumentProgress(id: string): Promise<ProcessingProgress> {
    const response = await fetch(
      `${this.baseUrl}/api/documents/${id}/progress`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      }
    );
    return this.handleResponse<ProcessingProgress>(response);
  }

  /**
   * Check backend health
   */
  async healthCheck(): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/health`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });
    return this.handleResponse<{ status: string }>(response);
  }
}

// Export singleton instance
export const apiClient = new ApiClient();

// Export class for testing
export default ApiClient;
