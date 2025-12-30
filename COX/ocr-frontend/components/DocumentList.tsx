"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api";
import { DocumentResponse } from "@/lib/types";
import LoadingSpinner from "./LoadingSpinner";

interface DocumentListProps {
  refreshTrigger?: number;
  onDelete?: () => void;
}

export default function DocumentList({
  refreshTrigger = 0,
  onDelete,
}: DocumentListProps) {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchDocuments = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const docs = await apiClient.listDocuments();
      setDocuments(
        docs.sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [refreshTrigger]);

  // Auto-refresh if any documents are processing (less frequent polling)
  // Individual document progress is handled by SSE in DocumentViewer
  useEffect(() => {
    const hasProcessingDocs = documents.some(
      (doc) =>
        doc.status === "pending" ||
        doc.status === "processing" ||
        doc.status === "processing_chunks"
    );

    if (hasProcessingDocs) {
      // Poll every 10 seconds (reduced from 5s since SSE handles real-time updates)
      // This is just to update the list view status
      pollingIntervalRef.current = setInterval(() => {
        fetchDocuments();
      }, 10000);
    } else {
      // Clear polling if no processing documents
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    }

    // Cleanup on unmount
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [documents]);

  // Deduplicate documents by document_id to prevent React key warnings
  const uniqueDocuments = useMemo(() => {
    // Create a Map to deduplicate by document_id (keeps the last occurrence)
    const docMap = new Map(documents.map((doc) => [doc.document_id, doc]));
    // Convert back to array
    return Array.from(docMap.values());
  }, [documents]);

  const handleDelete = async (id: string, filename: string) => {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) {
      return;
    }

    setDeletingId(id);
    try {
      await apiClient.deleteDocument(id);
      setDocuments(documents.filter((doc) => doc.document_id !== id));
      if (onDelete) {
        onDelete();
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete document");
    } finally {
      setDeletingId(null);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case "completed":
        return "bg-green-100 text-green-800";
      case "processing":
      case "processing_chunks":
        return "bg-blue-100 text-blue-800 animate-pulse";
      case "pending":
      case "extracting":
        return "bg-yellow-100 text-yellow-800";
      case "failed":
      case "error":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case "completed":
        return (
          <svg
            className="h-4 w-4 text-green-600"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
              clipRule="evenodd"
            />
          </svg>
        );
      case "processing":
      case "processing_chunks":
      case "extracting":
        return <LoadingSpinner size="sm" />;
      case "pending":
        return (
          <svg
            className="h-4 w-4 text-yellow-600"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
              clipRule="evenodd"
            />
          </svg>
        );
      case "failed":
      case "error":
        return (
          <svg
            className="h-4 w-4 text-red-600"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
              clipRule="evenodd"
            />
          </svg>
        );
      default:
        return null;
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center py-12">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
        <p className="text-red-800">{error}</p>
        <button
          onClick={fetchDocuments}
          className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
        >
          Try again
        </button>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="text-center py-12">
        <svg
          className="mx-auto h-12 w-12 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <h3 className="mt-2 text-sm font-medium text-gray-900">No documents</h3>
        <p className="mt-1 text-sm text-gray-500">
          Get started by uploading a PDF document.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold text-gray-900">
          Recent Documents ({uniqueDocuments.length})
        </h2>
        <button
          onClick={fetchDocuments}
          className="text-sm text-blue-600 hover:text-blue-800"
          aria-label="Refresh document list"
        >
          <svg
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        </button>
      </div>

      <div className="bg-white shadow overflow-hidden rounded-lg">
        <ul className="divide-y divide-gray-200">
          {uniqueDocuments.map((doc) => (
            <li
              key={doc.document_id}
              className="hover:bg-gray-50 transition-colors"
            >
              <div className="px-4 py-4 sm:px-6">
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <Link
                      href={`/documents/${doc.document_id}`}
                      className="block focus:outline-none"
                    >
                      <div className="flex items-center">
                        <svg
                          className="h-5 w-5 text-gray-400 mr-2 flex-shrink-0"
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path
                            fillRule="evenodd"
                            d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
                            clipRule="evenodd"
                          />
                        </svg>
                        <p className="text-sm font-medium text-blue-600 truncate hover:text-blue-800">
                          {doc.filename}
                        </p>
                      </div>
                      <div className="mt-2 flex items-center text-sm text-gray-500 space-x-4">
                        <span>{formatDate(doc.created_at)}</span>
                        <span>•</span>
                        <span>
                          {formatFileSize(doc.metadata?.file_size || 0)}
                        </span>
                        {doc.metadata?.page_count && (
                          <>
                            <span>•</span>
                            <span>{doc.metadata.page_count} pages</span>
                          </>
                        )}
                      </div>
                    </Link>
                  </div>
                  <div className="ml-4 flex items-center space-x-3">
                    <div className="flex items-center space-x-2">
                      {getStatusIcon(doc.status)}
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(
                          doc.status
                        )}`}
                      >
                        {doc.status.toUpperCase()}
                      </span>
                    </div>
                    <button
                      onClick={() =>
                        handleDelete(doc.document_id, doc.filename)
                      }
                      disabled={deletingId === doc.document_id}
                      className="text-red-600 hover:text-red-800 disabled:opacity-50"
                      aria-label={`Delete ${doc.filename}`}
                    >
                      {deletingId === doc.document_id ? (
                        <LoadingSpinner size="sm" />
                      ) : (
                        <svg
                          className="h-5 w-5"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                          />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
