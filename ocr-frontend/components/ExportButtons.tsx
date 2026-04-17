"use client";

import React, { useState } from "react";
import LoadingSpinner from "./LoadingSpinner";
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

  const handleExport = async (type: "excel" | "memo" | "om-proforma" | "rent-roll") => {
    setIsExporting(type as "excel" | "memo" | "om-proforma");
    setError(null); setSuccess(null);

    const exportPayload = { ...analysis };
    if (exportPayload.rent_roll) {
      exportPayload.rent_roll = exportPayload.rent_roll.map(({ stabilized_rent, ...rest }: any) => rest);
    }

    try {
      if (type === "excel") {
        await apiClient.downloadExport(exportPayload, "excel");
        if (exportPayload.om_proforma && exportPayload.om_proforma.length > 0)
          await apiClient.downloadExport(exportPayload, "om-proforma");
        setSuccess("Excel models downloaded successfully!");
      } else if (type === "om-proforma") {
        if (exportPayload.om_proforma && exportPayload.om_proforma.length > 0) {
          await apiClient.downloadExport(exportPayload, "om-proforma");
          setSuccess("OM Proforma downloaded successfully!");
        }
      } else {
        await apiClient.downloadExport(exportPayload, type);
        setSuccess("Investment memo downloaded successfully!");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setIsExporting(null);
    }
  };

  const exportOptions = [
    {
      id: "excel" as const,
      label: "Analysis Model",
      sublabel: "T12 & Pro Forma · XLSX",
      accent: "#22C55E",
      accentBg: "rgba(34,197,94,0.1)",
      accentBorder: "rgba(34,197,94,0.2)",
      hoverBorder: "rgba(34,197,94,0.4)",
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
      features: ["Standard underwriting model", "Live formulas + sensitivity"],
    },
    {
      id: "rent-roll" as const,
      label: "Rent Roll",
      sublabel: "Unit-level data · XLSX",
      accent: "#60A5FA",
      accentBg: "rgba(96,165,250,0.1)",
      accentBorder: "rgba(96,165,250,0.2)",
      hoverBorder: "rgba(96,165,250,0.4)",
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
      features: ["All units with current rents", "Vacancy + lease status"],
    },
    {
      id: "memo" as const,
      label: "Investment Memo",
      sublabel: "Executive summary · PDF",
      accent: "#F97316",
      accentBg: "rgba(249,115,22,0.1)",
      accentBorder: "rgba(249,115,22,0.2)",
      hoverBorder: "rgba(249,115,22,0.4)",
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
      features: ["AI-generated narrative", "SWOT + key risks"],
    },
  ];

  return (
    <div className="space-y-6">
      {/* Alerts */}
      {error && (
        <div className="p-4 bg-[rgba(239,68,68,0.08)] border border-[rgba(239,68,68,0.2)] rounded-xl text-[#EF4444] text-sm flex items-center gap-3">
          <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" className="shrink-0">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          {error}
        </div>
      )}
      {success && (
        <div className="p-4 bg-[rgba(34,197,94,0.08)] border border-[rgba(34,197,94,0.2)] rounded-xl text-[#22C55E] text-sm flex items-center gap-3">
          <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" className="shrink-0">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          {success}
        </div>
      )}

      {/* Export cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {exportOptions.map((opt) => {
          const loading = isExporting === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => handleExport(opt.id)}
              disabled={isExporting !== null}
              className={`group relative flex flex-col gap-4 p-6 rounded-xl border text-left transition-all duration-200 disabled:cursor-not-allowed ${
                loading
                  ? "bg-[#F1F5F9] border-[#E2E8F0] opacity-60"
                  : "bg-white border-[#E2E8F0] hover:bg-[#F1F5F9] hover:shadow-[0_4px_20px_rgba(0,0,0,0.4)]"
              }`}
              onMouseEnter={(e) => { if (!loading && isExporting === null) (e.currentTarget as HTMLButtonElement).style.borderColor = opt.hoverBorder; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.borderColor = ""; }}
            >
              {loading ? (
                <div className="flex items-center gap-3 h-full">
                  <LoadingSpinner size="sm" />
                  <span className="text-sm text-[#64748B]">Exporting…</span>
                </div>
              ) : (
                <>
                  {/* Icon */}
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center transition-transform group-hover:scale-110"
                    style={{ background: opt.accentBg, border: `1px solid ${opt.accentBorder}`, color: opt.accent }}>
                    {opt.icon}
                  </div>

                  {/* Label */}
                  <div>
                    <div className="text-sm font-bold text-[#0F172A]">{opt.label}</div>
                    <div className="text-[10px] text-[#64748B] mt-0.5">{opt.sublabel}</div>
                  </div>

                  {/* Feature list */}
                  <ul className="mt-1 space-y-1.5">
                    {opt.features.map((f) => (
                      <li key={f} className="flex items-center gap-2 text-[11px] text-[#64748B]">
                        <span style={{ color: opt.accent }}>✓</span>
                        {f}
                      </li>
                    ))}
                  </ul>

                  {/* Download arrow — appears on hover */}
                  <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: opt.accent }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                  </div>
                </>
              )}
            </button>
          );
        })}
      </div>

      {/* Package summary */}
      <div className="p-6 bg-[#F1F5F9] border border-[#E2E8F0] rounded-xl">
        <h4 className="text-[9px] font-bold text-[#64748B] uppercase tracking-widest mb-4">Included in Export Package</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-2">
          {[
            { accent: "#22C55E", text: <><span className="font-semibold text-[#0F172A]">Excel Models:</span> Standard analysis & OM data</> },
            { accent: "#22C55E", text: "Live formulas and sensitivity tables" },
            { accent: "#F97316", text: <><span className="font-semibold text-[#0F172A]">Investment Memo:</span> AI-generated executive summary</> },
            { accent: "#F97316", text: "SWOT analysis and key risks" },
          ].map(({ accent, text }, i) => (
            <div key={i} className="flex items-center gap-2 text-xs text-[#475569]">
              <span style={{ color: accent }}>✓</span>
              <span>{text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
