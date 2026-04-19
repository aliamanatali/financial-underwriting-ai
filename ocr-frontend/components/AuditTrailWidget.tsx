"use client";

import React, { useState } from "react";
import dynamic from "next/dynamic";
import { AuditEntry } from "@/lib/types";

const SourceDocumentViewer = dynamic(() => import("./SourceDocumentViewer"), {
  ssr: false,
});

interface AuditTrailWidgetProps {
  auditTrail: AuditEntry[];
  title?: string;
  packageId?: string;
}

export default function AuditTrailWidget({
  auditTrail,
  title = "Explainability — Audit Trail",
  packageId,
}: AuditTrailWidgetProps) {
  const [viewingItem, setViewingItem] = useState<AuditEntry | null>(null);

  const getConfidenceBadge = (score?: number) => {
    if (score === undefined) return null;
    const pct = (score * 100).toFixed(0);
    if (score >= 0.9) return <span className="badge-high">{pct}%</span>;
    if (score >= 0.7) return <span className="badge-medium">{pct}%</span>;
    return <span className="badge-low">{pct}%</span>;
  };

  const getFieldIcon = (fieldName: string, source: string) => {
    const lf = fieldName.toLowerCase();
    const ls = source.toLowerCase();

    if (lf.includes("viability") || lf.includes("status")) {
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" /><path d="m9 12 2 2 4-4" />
        </svg>
      );
    }
    if (ls.includes("model") || ls.includes("computed") || ls.includes("calculated") || lf.includes("pro forma")) {
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect width="16" height="20" x="4" y="2" rx="2" /><line x1="8" x2="16" y1="6" y2="6" />
          <line x1="16" x2="16" y1="14" y2="18" /><path d="M16 10h.01" /><path d="M12 10h.01" />
          <path d="M8 10h.01" /><path d="M12 14h.01" /><path d="M8 14h.01" />
          <path d="M12 18h.01" /><path d="M8 18h.01" />
        </svg>
      );
    }
    if (ls.includes("rent") || ls.includes("xlsx") || ls.includes("spreadsheet")) {
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
          <polyline points="14 2 14 8 20 8" /><path d="M8 13h2" /><path d="M8 17h2" />
          <path d="M14 13h2" /><path d="M14 17h2" />
        </svg>
      );
    }
    if (lf.includes("expense") || lf.includes("irr") || ls.includes("p&l") || ls.includes("financial")) {
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" /><polyline points="16 7 22 7 22 13" />
        </svg>
      );
    }
    if (lf.includes("gpr") || lf.includes("units") || lf.includes("summary")) {
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" x2="18" y1="20" y2="10" /><line x1="12" x2="12" y1="20" y2="4" /><line x1="6" x2="6" y1="20" y2="14" />
        </svg>
      );
    }
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect width="8" height="4" x="8" y="2" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      </svg>
    );
  };

  const getIconStyle = (fieldName: string, source: string): string => {
    const lf = fieldName.toLowerCase();
    const ls = source.toLowerCase();
    if (lf.includes("viability") || lf.includes("status"))
      return "bg-[rgba(34,197,94,0.1)] text-[#22C55E] border-[rgba(34,197,94,0.2)]";
    if (ls.includes("model") || ls.includes("computed") || ls.includes("calculated"))
      return "bg-[rgba(99,102,241,0.1)] text-[#818CF8] border-[rgba(99,102,241,0.2)]";
    if (ls.includes("rent") || ls.includes("xlsx"))
      return "bg-[rgba(168,85,247,0.1)] text-[#C084FC] border-[rgba(168,85,247,0.2)]";
    if (lf.includes("expense") || lf.includes("irr"))
      return "bg-[rgba(249,115,22,0.1)] text-[#F97316] border-[rgba(249,115,22,0.2)]";
    return "bg-[rgba(59,130,246,0.1)] text-[#60A5FA] border-[rgba(59,130,246,0.2)]";
  };

  const getDocumentIcon = (source: string) => {
    const ls = source.toLowerCase();
    if (ls.includes("xlsx") || ls.includes("spreadsheet")) {
      return (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[#22C55E] shrink-0">
          <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
          <polyline points="14 2 14 8 20 8" /><path d="M8 13h2" /><path d="M8 17h2" /><path d="M14 13h2" /><path d="M14 17h2" />
        </svg>
      );
    }
    if (ls.includes("model") || ls.includes("system")) {
      return (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[#64748B] shrink-0">
          <rect width="16" height="16" x="4" y="4" rx="2" /><rect width="6" height="6" x="9" y="9" rx="1" />
          <path d="M15 2v2" /><path d="M15 20v2" /><path d="M2 15h2" /><path d="M2 9h2" />
          <path d="M20 15h2" /><path d="M20 9h2" /><path d="M9 2v2" /><path d="M9 20v2" />
        </svg>
      );
    }
    return (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[#64748B] shrink-0">
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
        <polyline points="14 2 14 8 20 8" />
      </svg>
    );
  };

  const formatValue = (value: unknown) => {
    if (typeof value === "object") return JSON.stringify(value, null, 2);
    return String(value);
  };

  const isNegative = (value: unknown) => {
    const s = String(value);
    return s.includes("-") && (s.includes("$") || s.includes("%"));
  };

  const cleanFieldName = (name: string) => name.replace(/^Expense:\s*/i, "");

  return (
    <div className="flex flex-col gap-6">

      {/* Header row */}
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[#0F172A] flex items-center gap-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[#64748B]">
              <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
            </svg>
            {title}
          </h2>
          <p className="text-sm text-[#64748B] mt-1 pl-7">
            Review source documents and extraction methods for each data point.
          </p>
        </div>

        {/* Legend chips */}
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-[10px] font-medium text-[#475569] px-3 py-1.5 rounded-full bg-white border border-[#E2E8F0]">
            <span className="w-2 h-2 rounded-full bg-[#22C55E]" />
            High Confidence (90%+)
          </span>
          <span className="flex items-center gap-1.5 text-[10px] font-medium text-[#475569] px-3 py-1.5 rounded-full bg-white border border-[#E2E8F0]">
            <span className="w-2 h-2 rounded-full bg-[#F59E0B]" />
            Review Needed (&lt;90%)
          </span>
        </div>
      </div>

      {/* Table card */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] overflow-hidden shadow-[var(--shadow-card)]">

        {/* Column headers */}
        <div className="grid grid-cols-12 px-6 py-3 bg-[#F1F5F9] border-b border-[#E2E8F0] text-[10px] font-semibold text-[#64748B] uppercase tracking-widest">
          <div className="col-span-3">Field</div>
          <div className="col-span-3">Document</div>
          <div className="col-span-2">Method</div>
          <div className="col-span-2 pl-4">Value</div>
          <div className="col-span-2 text-right">Confidence</div>
        </div>

        {/* Rows */}
        <div className="divide-y divide-[#F1F5F9] text-sm">
          {auditTrail.map((entry, i) => (
            <div
              key={i}
              className="grid grid-cols-12 px-6 py-4 items-center hover:bg-[#F1F5F9] cursor-default transition-colors duration-150"
            >
              {/* Field */}
              <div className="col-span-3 flex items-center gap-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 border ${getIconStyle(entry.field_name, entry.source)}`}>
                  {getFieldIcon(entry.field_name, entry.source)}
                </div>
                <span className="font-semibold text-[#0F172A] text-xs truncate">
                  {cleanFieldName(entry.field_name)}
                </span>
              </div>

              {/* Document */}
              <div className="col-span-3 flex items-center gap-2 text-[#475569] text-xs">
                {getDocumentIcon(entry.source)}
                <span className="truncate max-w-[110px]" title={entry.source}>{entry.source}</span>
                {entry.document_id && (
                  <button
                    onClick={() => setViewingItem(entry)}
                    className="p-1 text-[#64748B] hover:text-[#F97316] hover:bg-[rgba(249,115,22,0.08)] rounded transition-colors shrink-0"
                    title="View Source Document"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" />
                    </svg>
                  </button>
                )}
              </div>

              {/* Method */}
              <div className="col-span-2 text-[#64748B] text-xs">{entry.method}</div>

              {/* Value */}
              <div className="col-span-2 pl-4">
                {typeof entry.extracted_value === "object" ? (
                  entry.field_name === "Rent Roll Summary" ? (
                    <div className="flex flex-col gap-1 text-xs">
                      {(["Units", "Occupancy", "Ann. Rent"] as const).map((label) => {
                        const keyMap: Record<string, string> = { "Units": "total_units", "Occupancy": "occupancy_rate", "Ann. Rent": "total_annual_rent" };
                        const val = (entry.extracted_value as Record<string, unknown>)?.[keyMap[label]];
                        return (
                          <div key={label} className="flex justify-between items-center gap-2">
                            <span className="text-[#64748B]">{label}:</span>
                            <span className="font-medium text-[#0F172A] font-mono">{String(val ?? "—")}</span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="bg-[#F8FAFC] rounded-md p-2 border border-[#E2E8F0] font-mono text-[10px] text-[#475569] leading-relaxed overflow-x-auto whitespace-pre-wrap">
                      {formatValue(entry.extracted_value)}
                    </div>
                  )
                ) : (
                  entry.field_name.toLowerCase().includes("status") || entry.field_name.toLowerCase().includes("viability") ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-[rgba(34,197,94,0.12)] text-[#22C55E] tracking-wide border border-[rgba(34,197,94,0.2)]">
                      {formatValue(entry.extracted_value)}
                    </span>
                  ) : (
                    <span className={`font-mono text-xs font-medium ${isNegative(entry.extracted_value) ? "text-[#EF4444]" : "text-[#0F172A]"}`}>
                      {formatValue(entry.extracted_value)}
                    </span>
                  )
                )}
              </div>

              {/* Confidence */}
              <div className="col-span-2 flex justify-end">
                {getConfidenceBadge(entry.confidence_score)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Empty state */}
      {auditTrail.length === 0 && (
        <div className="text-center py-12 bg-white rounded-xl border-2 border-dashed border-[#E2E8F0]">
          <p className="text-[#64748B] text-sm">No audit trail data available</p>
        </div>
      )}

      {/* Source document viewer modal */}
      {viewingItem && viewingItem.document_id && (
        <SourceDocumentViewer
          documentId={viewingItem.document_id}
          packageId={packageId}
          filename={viewingItem.source || "Document"}
          pageNumber={viewingItem.page_number}
          bbox={viewingItem.bbox}
          onClose={() => setViewingItem(null)}
        />
      )}
    </div>
  );
}
