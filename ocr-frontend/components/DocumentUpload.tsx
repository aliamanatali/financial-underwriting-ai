"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api";
import { UploadProgress } from "@/lib/types";
import LoadingSpinner from "./LoadingSpinner";

interface DocumentUploadProps {
  onUploadSuccess?: (documentId: string, taskId: string) => void;
  onUploadError?: (error: string) => void;
}

export default function DocumentUpload({
  onUploadSuccess,
  onUploadError,
}: DocumentUploadProps) {
  const router = useRouter();
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const validateFile = (file: File): string | null => {
    // Check file type
    if (file.type !== "application/pdf") {
      return "Only PDF files are allowed";
    }

    // Check file size (max 50MB)
    const maxSize = 50 * 1024 * 1024; // 50MB
    if (file.size > maxSize) {
      return "File size must be less than 50MB";
    }

    return null;
  };

  const handleUpload = async (file: File) => {
    setError(null);
    setSuccess(null);

    // Validate file
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      if (onUploadError) {
        onUploadError(validationError);
      }
      return;
    }

    setIsUploading(true);
    setUploadProgress({ loaded: 0, total: file.size, percentage: 0 });

    try {
      const response = await apiClient.uploadDocument(file, (progress) => {
        setUploadProgress(progress);
      });

      setSuccess(
        `File "${file.name}" uploaded successfully! Processing in background...`
      );
      setUploadProgress(null);

      if (onUploadSuccess) {
        onUploadSuccess(response.document_id, response.task_id);
      }

      // Redirect to document detail page after 1 second
      setTimeout(() => {
        router.push(`/documents/${response.document_id}`);
      }, 1000);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Upload failed";
      setError(errorMessage);
      setUploadProgress(null);

      if (onUploadError) {
        onUploadError(errorMessage);
      }
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleUpload(files[0]);
    }
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleUpload(files[0]);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div
        className={`
          relative border-2 border-dashed rounded-lg p-8 text-center transition-colors
          ${
            isDragging
              ? "border-blue-500 bg-blue-50"
              : "border-gray-300 bg-white"
          }
          ${
            isUploading
              ? "pointer-events-none opacity-60"
              : "hover:border-blue-400"
          }
        `}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {isUploading ? (
          <div className="space-y-4">
            <LoadingSpinner size="lg" className="mx-auto" />
            <div className="space-y-2">
              <p className="text-gray-700 font-medium">Uploading...</p>
              {uploadProgress && (
                <>
                  <div className="w-full bg-gray-200 rounded-full h-2.5">
                    <div
                      className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                      style={{ width: `${uploadProgress.percentage}%` }}
                    />
                  </div>
                  <p className="text-sm text-gray-600">
                    {uploadProgress.percentage}% (
                    {Math.round(uploadProgress.loaded / 1024)} KB /{" "}
                    {Math.round(uploadProgress.total / 1024)} KB)
                  </p>
                </>
              )}
            </div>
          </div>
        ) : (
          <>
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              stroke="currentColor"
              fill="none"
              viewBox="0 0 48 48"
              aria-hidden="true"
            >
              <path
                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <div className="mt-4">
              <label
                htmlFor="file-upload"
                className="cursor-pointer inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                <span>Choose a PDF file</span>
                <input
                  id="file-upload"
                  name="file-upload"
                  type="file"
                  className="sr-only"
                  accept=".pdf,application/pdf"
                  onChange={handleFileInput}
                  disabled={isUploading}
                />
              </label>
            </div>
            <p className="mt-2 text-sm text-gray-600">or drag and drop</p>
            <p className="mt-1 text-xs text-gray-500">PDF files up to 50MB</p>
          </>
        )}
      </div>

      {/* Success Message */}
      {success && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-center">
            <svg
              className="h-5 w-5 text-green-400 mr-2"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            <p className="text-sm text-green-800">{success}</p>
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
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
            <p className="text-sm text-red-800">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}
