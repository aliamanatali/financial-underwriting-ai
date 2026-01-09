"use client";

import React from "react";
import { AuditEntry } from "@/lib/types";

interface AuditTrailWidgetProps {
  auditTrail: AuditEntry[];
  title?: string;
}

export default function AuditTrailWidget({
  auditTrail,
  title = "Explainability - Audit Trail",
}: AuditTrailWidgetProps) {
  const getConfidenceBadgeColor = (score?: number) => {
    if (!score) return "bg-neutral-50 text-neutral-700 border-neutral-100";
    if (score >= 0.90) return "bg-emerald-50 text-emerald-700 border-emerald-100";
    return "bg-amber-50 text-amber-700 border-amber-100";
  };

  const getFieldIcon = (fieldName: string, source: string) => {
    const lowerField = fieldName.toLowerCase();
    const lowerSource = source.toLowerCase();
    
    // Viability/Gating
    if (lowerField.includes("viability") || lowerField.includes("status")) {
      return (
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <path d="m9 12 2 2 4-4"></path>
        </svg>
      );
    }
    
    // Calculated/Computed fields
    if (lowerField.includes("pro forma") || lowerSource.includes("model") || lowerSource.includes("computed") || lowerSource.includes("calculated")) {
      return (
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect width="16" height="20" x="4" y="2" rx="2"></rect>
          <line x1="8" x2="16" y1="6" y2="6"></line>
          <line x1="16" x2="16" y1="14" y2="18"></line>
          <path d="M16 10h.01"></path>
          <path d="M12 10h.01"></path>
          <path d="M8 10h.01"></path>
          <path d="M12 14h.01"></path>
          <path d="M8 14h.01"></path>
          <path d="M12 18h.01"></path>
          <path d="M8 18h.01"></path>
        </svg>
      );
    }
    
    // Rent Roll / Spreadsheet
    if (lowerSource.includes("rent") || lowerSource.includes("xlsx") || lowerSource.includes("spreadsheet")) {
      return (
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <path d="M8 13h2"></path>
          <path d="M8 17h2"></path>
          <path d="M14 13h2"></path>
          <path d="M14 17h2"></path>
        </svg>
      );
    }
    
    // Financial/Trending data
    if (lowerField.includes("expense") || lowerField.includes("irr") || lowerSource.includes("p&l") || lowerSource.includes("financial")) {
      return (
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline>
          <polyline points="16 7 22 7 22 13"></polyline>
        </svg>
      );
    }
    
    // Analytics/Charts
    if (lowerField.includes("gpr") || lowerField.includes("units") || lowerField.includes("summary")) {
      return (
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" x2="18" y1="20" y2="10"></line>
          <line x1="12" x2="12" y1="20" y2="4"></line>
          <line x1="6" x2="6" y1="20" y2="14"></line>
        </svg>
      );
    }
    
    // Default: Clipboard/Document
    return (
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect width="8" height="4" x="8" y="2" rx="1" ry="1"></rect>
        <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path>
      </svg>
    );
  };

  const getIconColor = (fieldName: string, source: string) => {
    const lowerField = fieldName.toLowerCase();
    const lowerSource = source.toLowerCase();
    
    if (lowerField.includes("viability") || lowerField.includes("status")) {
      return "bg-emerald-100 text-emerald-600 border-emerald-200";
    }
    if (lowerSource.includes("model") || lowerSource.includes("computed") || lowerSource.includes("calculated")) {
      return "bg-indigo-50 text-indigo-600 border-indigo-100";
    }
    if (lowerSource.includes("rent") || lowerSource.includes("xlsx")) {
      return "bg-purple-50 text-purple-600 border-purple-100";
    }
    if (lowerField.includes("expense") || lowerField.includes("irr")) {
      return "bg-orange-50 text-orange-600 border-orange-100";
    }
    return "bg-blue-50 text-blue-600 border-blue-100";
  };

  const getDocumentIcon = (source: string) => {
    const lowerSource = source.toLowerCase();
    
    if (lowerSource.includes("xlsx") || lowerSource.includes("spreadsheet")) {
      return (
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-500">
          <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <path d="M8 13h2"></path>
          <path d="M8 17h2"></path>
          <path d="M14 13h2"></path>
          <path d="M14 17h2"></path>
        </svg>
      );
    }
    
    if (lowerSource.includes("model") || lowerSource.includes("system")) {
      return (
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-neutral-400">
          <rect width="16" height="16" x="4" y="4" rx="2"></rect>
          <rect width="6" height="6" x="9" y="9" rx="1"></rect>
          <path d="M15 2v2"></path>
          <path d="M15 20v2"></path>
          <path d="M2 15h2"></path>
          <path d="M2 9h2"></path>
          <path d="M20 15h2"></path>
          <path d="M20 9h2"></path>
          <path d="M9 2v2"></path>
          <path d="M9 20v2"></path>
        </svg>
      );
    }
    
    return (
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-neutral-400">
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
      </svg>
    );
  };

  const formatValue = (value: unknown) => {
    if (typeof value === "object") {
      return JSON.stringify(value, null, 2);
    }
    return String(value);
  };

  const isNegativeValue = (value: unknown) => {
    const str = String(value);
    return str.includes("-") && (str.includes("$") || str.includes("%"));
  };

  const cleanFieldName = (fieldName: string) => {
    // Remove redundant "Expense:" prefix
    return fieldName.replace(/^Expense:\s*/i, "");
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Context Header */}
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-lg font-semibold text-neutral-900 flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-neutral-400">
              <circle cx="11" cy="11" r="8"></circle>
              <path d="m21 21-4.3-4.3"></path>
            </svg>
            {title}
          </h2>
          <p className="text-sm text-neutral-500 mt-1 pl-7">
            Review the source documents and extraction methods for each data point.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-xs text-neutral-400 font-medium px-3 py-1.5 rounded-full bg-white border border-neutral-100 shadow-sm flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
            High Confidence (90%+)
          </div>
          <div className="text-xs text-neutral-400 font-medium px-3 py-1.5 rounded-full bg-white border border-neutral-100 shadow-sm flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-amber-400"></div>
            Review Needed (&lt;90%)
          </div>
        </div>
      </div>

      {/* Audit List */}
      <div className="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden flex flex-col">
        {/* Column Headers */}
        <div className="grid grid-cols-12 px-6 py-3 bg-neutral-50/80 border-b border-neutral-100 text-xs font-semibold text-neutral-500 uppercase tracking-wide">
          <div className="col-span-3">Field</div>
          <div className="col-span-3">Document</div>
          <div className="col-span-2">Method</div>
          <div className="col-span-2 pl-4">Value</div>
          <div className="col-span-2 text-right">Confidence</div>
        </div>

        {/* Scrollable Area */}
        <div className="divide-y divide-neutral-100 text-sm">
          {auditTrail.map((entry, index) => (
            <div
              key={index}
              className="audit-item grid grid-cols-12 px-6 py-4 items-center hover:bg-neutral-50 cursor-default transition-colors duration-200"
            >
              {/* Field Column */}
              <div className="col-span-3 flex items-center gap-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 border ${getIconColor(entry.field_name, entry.source)}`}>
                  {getFieldIcon(entry.field_name, entry.source)}
                </div>
                <span className="font-semibold text-neutral-900">{cleanFieldName(entry.field_name)}</span>
              </div>

              {/* Document Column */}
              <div className="col-span-3 flex items-center gap-2 text-neutral-600 text-xs">
                {getDocumentIcon(entry.source)}
                {entry.source}
              </div>

              {/* Method Column */}
              <div className="col-span-2 text-neutral-500 text-xs">{entry.method}</div>

              {/* Value Column */}
              <div className="col-span-2 pl-4">
                {typeof entry.extracted_value === "object" ? (
                  <div className="bg-neutral-100 rounded-md p-2 border border-neutral-200 font-mono text-[10px] text-neutral-600 leading-relaxed overflow-x-auto whitespace-pre-wrap">
                    {formatValue(entry.extracted_value)}
                  </div>
                ) : (
                  <span className={`font-medium ${isNegativeValue(entry.extracted_value) ? "text-rose-600" : "text-neutral-900"}`}>
                    {entry.field_name.toLowerCase().includes("status") || entry.field_name.toLowerCase().includes("viability") ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-emerald-100 text-emerald-800 tracking-wide border border-emerald-200">
                        {formatValue(entry.extracted_value)}
                      </span>
                    ) : (
                      formatValue(entry.extracted_value)
                    )}
                  </span>
                )}
              </div>

              {/* Confidence Column */}
              <div className="col-span-2 flex justify-end">
                {entry.confidence_score !== undefined && (
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${getConfidenceBadgeColor(entry.confidence_score)}`}>
                    {(entry.confidence_score * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {auditTrail.length === 0 && (
        <div className="text-center py-12 bg-neutral-50 rounded-lg border-2 border-dashed border-neutral-200 text-neutral-500">
          <p>No audit trail data available</p>
        </div>
      )}
    </div>
  );
}
