"use client";

import React, { useState } from "react";
import LoadingSpinner from "./LoadingSpinner";
import RentRollExportModal from "./RentRollExportModal";

import { UnderwritingAnalysis } from "@/lib/types";
import { apiClient } from "@/lib/api";

interface ExportButtonsProps {
  analysis: UnderwritingAnalysis;
  onAnalysisUpdate?: (newAnalysis: UnderwritingAnalysis) => void;
}

export default function ExportButtons({ analysis, onAnalysisUpdate }: ExportButtonsProps) {
  const [isExporting, setIsExporting] = useState<"excel" | "memo" | "om-proforma" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isRentRollModalOpen, setIsRentRollModalOpen] = useState(false);

  const handleExport = async (type: "excel" | "memo" | "om-proforma" | "rent-roll") => {
    // If it's rent-roll export, open the modal instead of direct export
    if (type === "rent-roll") {
        setIsRentRollModalOpen(true);
        return;
    }

    setIsExporting(type as "excel" | "memo" | "om-proforma");
    setError(null);
    setSuccess(null);

    try {
      if (type === "excel") {
        // Download Standard Underwriting Model
        await apiClient.downloadExport(analysis, "excel");
        
        // Also download OM Proforma if available
        if (analysis.om_proforma && analysis.om_proforma.length > 0) {
            await apiClient.downloadExport(analysis, "om-proforma");
        }
        
        setSuccess("Excel models downloaded successfully!");
      } else if (type === "om-proforma") {
         // Deprecated standalone button logic - kept for type safety but unreachable via UI
         if (analysis.om_proforma && analysis.om_proforma.length > 0) {
          await apiClient.downloadExport(analysis, "om-proforma");
          setSuccess("OM Proforma extracted data downloaded successfully!");
        }
      } else {
        await apiClient.downloadExport(analysis, type);
        setSuccess("Investment memo downloaded successfully!");
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Download failed";
      setError(errorMessage);
    } finally {
      setIsExporting(null);
    }
  };

  return (
    <div className="space-y-6 font-sans">
      <RentRollExportModal
        isOpen={isRentRollModalOpen}
        onClose={() => setIsRentRollModalOpen(false)}
        analysis={analysis}
        onAnalysisUpdate={onAnalysisUpdate}
      />

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-sm flex items-center">
          <svg className="w-5 h-5 mr-2 text-rose-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          {error}
        </div>
      )}

      {success && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-700 text-sm flex items-center">
          <svg className="w-5 h-5 mr-2 text-emerald-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          {success}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Excel Export */}
        <button
          onClick={() => handleExport("excel")}
          disabled={isExporting !== null}
          className={`group flex items-center justify-center gap-4 px-6 py-6 rounded-xl font-semibold transition-all border shadow-sm hover:shadow-md ${
            isExporting === "excel"
              ? "bg-slate-50 border-slate-200 text-slate-400 cursor-not-allowed"
              : "bg-white border-slate-200 text-slate-700 hover:border-emerald-500 hover:text-emerald-700 hover:bg-emerald-50/50"
          }`}
        >
          {isExporting === "excel" ? (
            <>
              <LoadingSpinner size="sm" />
              Excel...
            </>
          ) : (
            <>
              <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center text-emerald-600 group-hover:bg-emerald-200 group-hover:scale-110 transition-transform">
                 <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                 </svg>
              </div>
              <div className="text-left">
                  <div className="text-sm font-bold">Analysis Model</div>
                  <div className="text-[10px] text-slate-500 font-normal mt-0.5">T12 & Pro Forma</div>
              </div>
            </>
          )}
        </button>

        {/* Rent Roll Export (With Modal) */}
        <button
          onClick={() => handleExport("rent-roll")}
          className={`group flex items-center justify-center gap-4 px-6 py-6 rounded-xl font-semibold transition-all border shadow-sm hover:shadow-md bg-white border-slate-200 text-slate-700 hover:border-blue-500 hover:text-blue-700 hover:bg-blue-50/50`}
        >
          <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600 group-hover:bg-blue-200 group-hover:scale-110 transition-transform">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
          </div>
          <div className="text-left">
              <div className="text-sm font-bold">Rent Roll</div>
              <div className="text-[10px] text-slate-500 font-normal mt-0.5">Edit & Export</div>
          </div>
        </button>

        {/* Memo Export */}
        <button
          onClick={() => handleExport("memo")}
          disabled={isExporting !== null}
          className={`group flex items-center justify-center gap-4 px-6 py-6 rounded-xl font-semibold transition-all border shadow-sm hover:shadow-md ${
            isExporting === "memo"
              ? "bg-slate-50 border-slate-200 text-slate-400 cursor-not-allowed"
              : "bg-white border-slate-200 text-slate-700 hover:border-[#FF5E00] hover:text-[#FF5E00] hover:bg-[#FFF5F0]/50"
          }`}
        >
          {isExporting === "memo" ? (
            <>
              <LoadingSpinner size="sm" />
              Memo...
            </>
          ) : (
            <>
               <div className="w-10 h-10 bg-[#FFE5D9] rounded-lg flex items-center justify-center text-[#FF5E00] group-hover:bg-[#FFCBB3] group-hover:scale-110 transition-transform">
                 <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                 </svg>
              </div>
              <div className="text-left">
                  <div className="text-sm font-bold">Investment Memo</div>
                  <div className="text-[10px] text-slate-500 font-normal mt-0.5">Word Document</div>
              </div>
            </>
          )}
        </button>
      </div>

      <div className="p-6 bg-slate-50 border border-slate-200 rounded-xl">
        <h4 className="font-bold text-slate-900 mb-3 text-sm uppercase tracking-wide">Included in Export Package</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
             <ul className="space-y-2 text-sm text-slate-600">
                <li className="flex items-center gap-2">
                    <span className="text-emerald-500">✓</span>
                    <strong>Excel Models:</strong> Standard Analysis & OM Data
                </li>
                <li className="flex items-center gap-2">
                    <span className="text-emerald-500">✓</span>
                    Live formulas and sensitivity tables
                </li>
            </ul>
            <ul className="space-y-2 text-sm text-slate-600">
                <li className="flex items-center gap-2">
                    <span className="text-#FFF5F00">✓</span>
                    <strong>Investment Memo:</strong> AI-generated executive summary
                </li>
                <li className="flex items-center gap-2">
                    <span className="text-#FFF5F00">✓</span>
                    SWOT analysis and key risks
                </li>
            </ul>
        </div>
      </div>
    </div>
  );
}
