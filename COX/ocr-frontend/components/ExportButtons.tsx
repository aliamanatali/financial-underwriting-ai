"use client";

import React, { useState } from "react";
import LoadingSpinner from "./LoadingSpinner";

import { UnderwritingAnalysis } from "@/lib/types";
import { apiClient } from "@/lib/api";

interface ExportButtonsProps {
  analysis: UnderwritingAnalysis;
}

export default function ExportButtons({ analysis }: ExportButtonsProps) {
  const [isExporting, setIsExporting] = useState<"excel" | "memo" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleExport = async (type: "excel" | "memo") => {
    setIsExporting(type);
    setError(null);
    setSuccess(null);

    try {
      await apiClient.downloadExport(analysis, type);
      setSuccess(`${type === "excel" ? "Excel model" : "Investment memo"} downloaded successfully!`);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Download failed";
      setError(errorMessage);
    } finally {
      setIsExporting(null);
    }
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          ❌ {error}
        </div>
      )}

      {success && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
          ✓ {success}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Excel Export */}
        <button
          onClick={() => handleExport("excel")}
          disabled={isExporting !== null}
          className={`flex items-center justify-center gap-3 px-6 py-4 rounded-lg font-semibold transition-all ${
            isExporting === "excel"
              ? "bg-blue-100 text-blue-700 cursor-not-allowed"
              : "bg-blue-600 text-white hover:bg-blue-700 active:scale-95"
          }`}
        >
          {isExporting === "excel" ? (
            <>
              <LoadingSpinner size="sm" />
              Generating Excel...
            </>
          ) : (
            <>
              <span className="text-xl">📊</span>
              Export Excel Model
            </>
          )}
        </button>

        {/* Memo Export */}
        <button
          onClick={() => handleExport("memo")}
          disabled={isExporting !== null}
          className={`flex items-center justify-center gap-3 px-6 py-4 rounded-lg font-semibold transition-all ${
            isExporting === "memo"
              ? "bg-green-100 text-green-700 cursor-not-allowed"
              : "bg-green-600 text-white hover:bg-green-700 active:scale-95"
          }`}
        >
          {isExporting === "memo" ? (
            <>
              <LoadingSpinner size="sm" />
              Generating Memo...
            </>
          ) : (
            <>
              <span className="text-xl">📝</span>
              Export Investment Memo
            </>
          )}
        </button>
      </div>

      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm text-gray-700">
        <p className="font-semibold mb-2">📌 What you're exporting:</p>
        <ul className="space-y-1 text-xs">
          <li>✓ <strong>Excel Model:</strong> Professional T12 vs F12 side-by-side analysis with all calculations</li>
          <li>✓ <strong>Investment Memo:</strong> AI-generated executive summary with SWOT, key questions, and recommendations</li>
        </ul>
      </div>
    </div>
  );
}
