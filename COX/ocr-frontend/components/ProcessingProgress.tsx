"use client";

import { ProcessingProgress, ChunkProgress, ChunkStatus } from "@/lib/types";
import LoadingSpinner from "./LoadingSpinner";

interface ProcessingProgressProps {
  progress: ProcessingProgress;
}

export default function ProcessingProgressComponent({
  progress,
}: ProcessingProgressProps) {
  const getChunkStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <svg
            className="h-5 w-5 text-green-500"
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
        return <LoadingSpinner size="sm" />;
      case "failed":
        return (
          <svg
            className="h-5 w-5 text-red-500"
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
      case "pending":
        return (
          <svg
            className="h-5 w-5 text-gray-400"
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
      default:
        return null;
    }
  };

  const getChunkStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-green-50 border-green-200";
      case "processing":
        return "bg-blue-50 border-blue-200";
      case "failed":
        return "bg-red-50 border-red-200";
      case "pending":
        return "bg-gray-50 border-gray-200";
      default:
        return "bg-gray-50 border-gray-200";
    }
  };

  // Calculate current processing chunk from chunk_index or find processing chunks
  const getCurrentChunkDisplay = () => {
    // If chunk_index is provided in the event, use it (1-based)
    if (progress.chunk_index !== undefined && progress.chunk_index !== null) {
      return `Processing chunk ${progress.chunk_index + 1} of ${
        progress.total_chunks
      }`;
    }

    // Otherwise, try to find processing chunks from chunks object
    if (progress.chunks) {
      const chunksObj = Array.isArray(progress.chunks)
        ? progress.chunks
        : Object.entries(progress.chunks).map(([index, chunk]) => ({
            chunk_index: parseInt(index),
            status: chunk.status,
            pages: "",
            error: chunk.error,
          }));

      const processingChunks = chunksObj
        .filter((chunk) => chunk.status === "processing")
        .map((chunk) => chunk.chunk_index + 1);

      if (processingChunks.length > 0) {
        return `Processing chunk${
          processingChunks.length > 1 ? "s" : ""
        } ${processingChunks.join(", ")} of ${progress.total_chunks}`;
      }
    }

    // Fallback based on status
    if (progress.status === "completed") {
      return "Processing completed!";
    } else if (progress.status === "failed") {
      return "Processing failed";
    } else if (progress.processing_chunks && progress.processing_chunks > 0) {
      return `Processing ${progress.processing_chunks} chunk${
        progress.processing_chunks > 1 ? "s" : ""
      }...`;
    }

    return "Waiting to start...";
  };

  const progressPercentage =
    progress.overall_progress ?? progress.progress_percentage ?? 0;

  return (
    <div className="space-y-6">
      {/* Overall Progress */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">
            Processing Progress
          </h3>
          <span className="text-2xl font-bold text-blue-600">
            {Math.round(progressPercentage)}%
          </span>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-gray-200 rounded-full h-4 mb-4">
          <div
            className="bg-blue-600 h-4 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${progressPercentage}%` }}
          />
        </div>

        {/* Status Message */}
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center space-x-2">
            {progress.status === "processing" && <LoadingSpinner size="sm" />}
            <span className="text-gray-700">{getCurrentChunkDisplay()}</span>
          </div>
          <span className="text-gray-600">
            {progress.completed_chunks} / {progress.total_chunks} chunks
            completed
          </span>
        </div>

        {/* Failed Chunks Warning */}
        {progress.failed_chunks > 0 && (
          <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
            <div className="flex items-center">
              <svg
                className="h-5 w-5 text-yellow-600 mr-2"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="text-sm text-yellow-800">
                {progress.failed_chunks} chunk
                {progress.failed_chunks > 1 ? "s" : ""} failed
              </span>
            </div>
          </div>
        )}

        {/* Error Message */}
        {progress.error_message && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-start">
              <svg
                className="h-5 w-5 text-red-600 mr-2 mt-0.5"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
              <div className="flex-1">
                <p className="text-sm font-medium text-red-800">Error</p>
                <p className="text-sm text-red-700 mt-1">
                  {progress.error_message}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Chunk Details */}
      {progress.chunks && (
        <div className="bg-white shadow rounded-lg p-6">
          <h4 className="text-md font-semibold text-gray-900 mb-4">
            Chunk Status Details
          </h4>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {(() => {
              // Convert chunks to array format
              const chunksArray: ChunkProgress[] = Array.isArray(
                progress.chunks
              )
                ? progress.chunks
                : Object.entries(progress.chunks).map(([index, chunk]) => ({
                    chunk_index: parseInt(index),
                    status: chunk.status as ChunkStatus,
                    pages: "",
                    error: chunk.error,
                  }));

              return chunksArray.length > 0
                ? chunksArray.map((chunk) => (
                    <div
                      key={chunk.chunk_index}
                      className={`flex items-center justify-between p-3 border rounded-lg ${getChunkStatusColor(
                        chunk.status
                      )}`}
                    >
                      <div className="flex items-center space-x-3">
                        {getChunkStatusIcon(chunk.status)}
                        <div>
                          <p className="text-sm font-medium text-gray-900">
                            Chunk {chunk.chunk_index + 1}
                          </p>
                          {chunk.pages && (
                            <p className="text-xs text-gray-600">
                              Pages: {chunk.pages}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span
                          className={`px-2 py-1 text-xs font-medium rounded-full ${
                            chunk.status === "completed"
                              ? "bg-green-100 text-green-800"
                              : chunk.status === "processing"
                              ? "bg-blue-100 text-blue-800"
                              : chunk.status === "failed"
                              ? "bg-red-100 text-red-800"
                              : "bg-gray-100 text-gray-800"
                          }`}
                        >
                          {chunk.status.toUpperCase()}
                        </span>
                      </div>
                      {chunk.error && (
                        <div className="mt-2 text-xs text-red-600">
                          Error: {chunk.error}
                        </div>
                      )}
                    </div>
                  ))
                : null;
            })()}
          </div>
        </div>
      )}
    </div>
  );
}
