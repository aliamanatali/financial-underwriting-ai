"use client";

import { useState, useEffect, useRef } from "react";
import { apiClient } from "@/lib/api";
import {
  DocumentResponse,
  ExtractedText,
  ProcessingProgress,
} from "@/lib/types";
import LoadingSpinner from "./LoadingSpinner";
import ProcessingProgressComponent from "./ProcessingProgress";
import { useDocumentProgress } from "@/hooks/useDocumentProgress";

interface DocumentViewerProps {
  documentId: string;
}

export default function DocumentViewer({ documentId }: DocumentViewerProps) {
  const [document, setDocument] = useState<DocumentResponse | null>(null);
  const [extractedText, setExtractedText] = useState<ExtractedText | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Use SSE for real-time progress updates (only for processing_chunks status)
  const shouldUseSSE =
    document?.status === "processing_chunks" ||
    document?.status === "processing";
  const {
    progress,
    isConnected,
    error: sseError,
  } = useDocumentProgress(shouldUseSSE ? documentId : null);

  const fetchDocument = async () => {
    try {
      const docData = await apiClient.getDocument(documentId);
      setDocument(docData);
      return docData;
    } catch (err) {
      throw err;
    }
  };

  const fetchExtractedText = async () => {
    try {
      const textData = await apiClient.getDocumentText(documentId);
      setExtractedText(textData);
    } catch (err) {
      console.error("Failed to fetch extracted text:", err);
    }
  };

  useEffect(() => {
    const initializeData = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const docData = await fetchDocument();

        // If completed, fetch extracted text
        if (docData.status === "completed") {
          await fetchExtractedText();
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load document"
        );
      } finally {
        setIsLoading(false);
      }
    };

    initializeData();
  }, [documentId]);

  // Monitor SSE progress updates and refresh document when completed
  useEffect(() => {
    if (!progress) return;

    // Check if processing completed via SSE
    if (progress.status === "completed") {
      console.log(`Document ${documentId} completed via SSE, updating UI...`);

      // Immediately update the document state to show completed status
      setDocument((prev) =>
        prev
          ? {
              ...prev,
              status: "completed",
            }
          : null
      );

      // Refresh document data and fetch extracted text
      fetchDocument().then((docData) => {
        if (docData.status === "completed") {
          fetchExtractedText();
        }
      });
    } else if (progress.status === "failed") {
      // Immediately update the document state to show failed status
      setDocument((prev) =>
        prev
          ? {
              ...prev,
              status: "failed",
              error_message: progress.error_message,
            }
          : null
      );

      // Refresh document to get error details
      fetchDocument();
    }
  }, [progress?.status, documentId]);

  // Display SSE errors
  useEffect(() => {
    if (sseError) {
      console.error("SSE Error:", sseError);
    }
  }, [sseError]);

  const handleCopyText = async () => {
    if (!extractedText?.text) return;

    try {
      await navigator.clipboard.writeText(extractedText.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      alert("Failed to copy text to clipboard");
    }
  };

  const handleDownloadText = () => {
    if (!extractedText?.text || !document) return;

    const blob = new Blob([extractedText.text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement("a");
    a.href = url;
    a.download = `${document.filename.replace(".pdf", "")}_extracted.txt`;
    window.document.body.appendChild(a);
    a.click();
    window.document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatProcessingTime = (seconds: number) => {
    if (seconds < 60) {
      return `${seconds.toFixed(1)}s`;
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = Math.floor(seconds % 60);
      return `${minutes}m ${remainingSeconds}s`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return `${hours}h ${minutes}m`;
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <LoadingSpinner size="lg" />
        <p className="mt-4 text-gray-600">Loading document...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
        <div className="flex items-center">
          <svg
            className="h-5 w-5 text-red-400 mr-2"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
              clipRule="evenodd"
            />
          </svg>
          <p className="text-red-800">{error}</p>
        </div>
      </div>
    );
  }

  if (!document) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600">Document not found</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Document Metadata */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">
          {document.filename}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div>
            <span className="font-medium text-gray-700">Upload Date:</span>
            <span className="ml-2 text-gray-600">
              {formatDate(document.created_at)}
            </span>
          </div>
          <div>
            <span className="font-medium text-gray-700">Status:</span>
            <span
              className={`ml-2 px-2 py-1 text-xs font-medium rounded-full ${
                document.status === "completed"
                  ? "bg-green-100 text-green-800"
                  : document.status === "processing"
                  ? "bg-blue-100 text-blue-800"
                  : document.status === "failed"
                  ? "bg-red-100 text-red-800"
                  : "bg-yellow-100 text-yellow-800"
              }`}
            >
              {document.status.toUpperCase()}
            </span>
          </div>
          <div>
            <span className="font-medium text-gray-700">File Size:</span>
            <span className="ml-2 text-gray-600">
              {document.metadata?.file_size
                ? (document.metadata.file_size / 1024 / 1024).toFixed(2) + " MB"
                : "N/A"}
            </span>
          </div>
          {document.metadata?.page_count && (
            <div>
              <span className="font-medium text-gray-700">Pages:</span>
              <span className="ml-2 text-gray-600">
                {document.metadata.page_count}
              </span>
            </div>
          )}
          {document.processing_time_seconds !== null &&
            document.processing_time_seconds !== undefined && (
              <div>
                <span className="font-medium text-gray-700">
                  Processing Time:
                </span>
                <span className="ml-2 text-gray-600">
                  {formatProcessingTime(document.processing_time_seconds)}
                </span>
              </div>
            )}
        </div>
      </div>

      {/* Processing Progress */}
      {(document.status === "processing_chunks" ||
        document.status === "processing" ||
        document.status === "pending") && (
        <>
          {progress && <ProcessingProgressComponent progress={progress} />}
          {isConnected && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="flex items-center text-sm text-blue-700">
                <div className="animate-pulse mr-2">
                  <div className="h-2 w-2 bg-blue-500 rounded-full"></div>
                </div>
                <span>Real-time updates active</span>
              </div>
            </div>
          )}
        </>
      )}

      {/* Failed Status */}
      {document.status === "failed" && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-start">
            <svg
              className="h-6 w-6 text-red-600 mr-3 mt-0.5"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            <div>
              <h3 className="text-lg font-semibold text-red-900">
                Processing Failed
              </h3>
              <p className="mt-2 text-sm text-red-700">
                {document.error_message ||
                  "An error occurred while processing this document."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Extracted Text (only show when completed) */}
      {document.status === "completed" && extractedText && (
        <>
          {/* Action Buttons */}
          <div className="flex flex-wrap gap-3">
            <button
              onClick={handleCopyText}
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              {copied ? (
                <>
                  <svg
                    className="h-5 w-5 mr-2 text-green-500"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                  Copied!
                </>
              ) : (
                <>
                  <svg
                    className="h-5 w-5 mr-2"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                    />
                  </svg>
                  Copy Text
                </>
              )}
            </button>

            <button
              onClick={handleDownloadText}
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              <svg
                className="h-5 w-5 mr-2"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
              Download Text
            </button>
          </div>

          {/* Extracted Text */}
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Extracted Text
            </h3>
            <div className="bg-gray-50 rounded-lg p-4 max-h-[600px] overflow-y-auto">
              <pre className="whitespace-pre-wrap text-sm text-gray-800 font-mono leading-relaxed">
                {extractedText.text || "No text extracted"}
              </pre>
            </div>
            <div className="mt-4 text-sm text-gray-500">
              {extractedText.text.length.toLocaleString()} characters
            </div>
          </div>
        </>
      )}
    </div>
  );
}
