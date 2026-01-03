"use client";

import React, { useState } from "react";
import { AuditEntry } from "@/lib/types";

interface AuditTrailWidgetProps {
  auditTrail: AuditEntry[];
  title?: string;
}

export default function AuditTrailWidget({
  auditTrail,
  title = "Explainability - Audit Trail",
}: AuditTrailWidgetProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const getConfidenceBadgeColor = (score?: number) => {
    if (!score) return "bg-slate-100 text-slate-700";
    if (score >= 0.95) return "bg-emerald-100 text-emerald-700";
    if (score >= 0.85) return "bg-blue-100 text-blue-700";
    if (score >= 0.70) return "bg-amber-100 text-amber-700";
    return "bg-rose-100 text-rose-700";
  };

  const getSourceIcon = (source: string) => {
    if (!source) return "📌";
    const lowerSource = source.toLowerCase();
    if (lowerSource.includes("rent roll")) return "📊";
    if (lowerSource.includes("om") || lowerSource.includes("offering")) return "📋";
    if (lowerSource.includes("p&l") || lowerSource.includes("financial")) return "📈";
    if (lowerSource.includes("calculated")) return "🧮";
    if (lowerSource.includes("gating") || lowerSource.includes("viability")) return "✓";
    return "📌";
  };

  const formatValue = (value: any) => {
    if (typeof value === "object") {
      return JSON.stringify(value, null, 2);
    }
    return String(value);
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8">
      <h3 className="text-xl font-bold text-slate-900 mb-2 flex items-center gap-2">
        🔍 {title}
      </h3>
      <p className="text-sm text-slate-500 mb-6">
        Hover over fields to see where the data came from and how it was calculated
      </p>

      <div className="space-y-3">
        {auditTrail.map((entry, index) => (
          <div key={index} className="relative">
            {/* Main Entry Box */}
            <button
              onClick={() =>
                setExpandedIndex(expandedIndex === index ? null : index)
              }
              onMouseEnter={() => setHoveredIndex(index)}
              onMouseLeave={() => setHoveredIndex(null)}
              className={`w-full text-left p-5 rounded-lg border-2 transition-all duration-200 ${
                expandedIndex === index
                  ? "border-blue-400 bg-blue-50/50"
                  : hoveredIndex === index
                  ? "border-slate-300 bg-slate-50"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <span className="text-xl">{getSourceIcon(entry.source)}</span>
                    <div>
                      <h4 className="font-semibold text-slate-900">{entry.field_name}</h4>
                      <p className="text-xs text-slate-500 mt-1 uppercase tracking-wide">
                        Source: <strong className="text-slate-700">{entry.source}</strong>
                      </p>
                    </div>
                  </div>

                  {/* Tooltip Preview */}
                  {hoveredIndex === index && !expandedIndex && (
                    <div className="mt-3 p-3 bg-white border border-slate-200 rounded-md text-sm text-slate-600 shadow-sm animate-in fade-in">
                      <p className="font-semibold mb-1 text-slate-800">Method:</p>
                      <p className="text-xs">{entry.method}</p>
                    </div>
                  )}
                </div>

                {/* Right side: Value + Confidence */}
                <div className="text-right flex-shrink-0">
                  <p className="text-sm font-mono text-slate-900 truncate max-w-xs bg-slate-100 px-2 py-1 rounded">
                    {formatValue(entry.extracted_value).split("\n")}
                  </p>
                  {entry.confidence_score !== undefined && (
                    <div
                      className={`mt-2 inline-block px-2 py-1 rounded text-[10px] uppercase font-bold tracking-wide ${getConfidenceBadgeColor(
                        entry.confidence_score
                      )}`}
                    >
                      {(entry.confidence_score * 100).toFixed(0)}% confidence
                    </div>
                  )}
                </div>

                {/* Expand Icon */}
                <div className="text-slate-400">
                  {expandedIndex === index ? "▼" : "▶"}
                </div>
              </div>
            </button>

            {/* Expanded Details */}
            {expandedIndex === index && (
              <div className="mt-2 p-5 bg-slate-50 border border-slate-200 rounded-lg animate-in fade-in slide-in-from-top-2 shadow-inner">
                <div className="space-y-4">
                  {/* Value */}
                  <div>
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">
                      Value
                    </p>
                    <p className="mt-1 text-slate-900 font-mono text-sm whitespace-pre-wrap break-words bg-white p-2 rounded border border-slate-200">
                      {formatValue(entry.extracted_value)}
                    </p>
                  </div>

                  {/* Source */}
                  <div className="pt-4 border-t border-slate-200">
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">
                      Source Document
                    </p>
                    <p className="mt-1 text-slate-900 text-sm">{entry.source}</p>
                  </div>

                  {/* Method */}
                  <div className="pt-4 border-t border-slate-200">
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">
                      Calculation Method
                    </p>
                    <p className="mt-1 text-slate-900 text-sm">{entry.method}</p>
                  </div>

                  {/* Confidence */}
                  {entry.confidence_score !== undefined && (
                    <div className="pt-4 border-t border-slate-200">
                      <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">
                        Confidence Score
                      </p>
                      <div className="mt-2 flex items-center gap-3">
                        <div className="flex-1 bg-slate-200 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full transition-all ${
                              entry.confidence_score! >= 0.95
                                ? "bg-emerald-500"
                                : entry.confidence_score! >= 0.85
                                ? "bg-blue-500"
                                : entry.confidence_score! >= 0.70
                                ? "bg-amber-500"
                                : "bg-rose-500"
                            }`}
                            style={{ width: `${(entry.confidence_score! * 100)}%` }}
                          ></div>
                        </div>
                        <span className="text-sm font-bold text-slate-900 w-16 text-right">
                          {(entry.confidence_score! * 100).toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Gating Reasons */}
                  {entry.reasons && entry.reasons.length > 0 && (
                    <div className="pt-4 border-t border-slate-200">
                      <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">
                        Gating Concerns
                      </p>
                      <ul className="mt-2 space-y-2">
                        {entry.reasons.map((reason, idx) => (
                          <li key={idx} className="text-sm text-rose-700 bg-rose-50 p-2 rounded border border-rose-100 flex items-start gap-2">
                            <span className="text-rose-500 mt-0.5">⚠</span>
                            {reason}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Timestamp */}
                  {entry.timestamp && (
                    <div className="pt-4 border-t border-slate-200">
                      <p className="text-xs text-slate-400">
                        Extracted: {new Date(entry.timestamp).toLocaleString()}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {auditTrail.length === 0 && (
        <div className="text-center py-12 bg-slate-50 rounded-lg border-2 border-dashed border-slate-200 text-slate-500">
          <p>No audit trail data available</p>
        </div>
      )}
    </div>
  );
}
