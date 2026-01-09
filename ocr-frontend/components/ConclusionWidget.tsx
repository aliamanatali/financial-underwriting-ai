"use client";

import React, { useState } from "react";
import { UnderwritingAnalysis, DecisionImpact } from "@/lib/types";

interface ConclusionWidgetProps {
  analysis: UnderwritingAnalysis;
}

function DecisionCard({ decision }: { decision: DecisionImpact }) {
  return (
    <div className="bg-slate-50 rounded-lg p-5 border border-slate-200 hover:border-blue-300 transition-colors">
      <div className="flex justify-between items-start mb-3">
        <h4 className="font-bold text-slate-900 text-sm uppercase tracking-wide">
          {decision.metric}
        </h4>
        <span className="bg-#FFE5D9 text-blue-800 text-xs px-2 py-0.5 rounded-full font-medium">
          AI Decision
        </span>
      </div>
      
      <p className="text-lg font-bold text-slate-800 mb-3 leading-tight">
        {decision.decision}
      </p>

      <div className="space-y-3">
        <div>
          <p className="text-xs text-slate-500 font-semibold uppercase mb-1">Reasoning</p>
          <p className="text-sm text-slate-700 leading-relaxed bg-white p-2 rounded border border-slate-100">
            {decision.reasoning}
          </p>
        </div>
        
        <div>
          <p className="text-xs text-slate-500 font-semibold uppercase mb-1">Client Impact</p>
          <p className="text-sm text-slate-700 leading-relaxed bg-amber-50 p-2 rounded border border-amber-100 text-amber-900">
            {decision.impact}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function ConclusionWidget({ analysis }: ConclusionWidgetProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!analysis.conclusion) {
    return null;
  }

  const { summary, key_decisions } = analysis.conclusion;

  return (
    <div className="bg-white rounded-xl shadow-sm ring-1 ring-slate-200 border-l-4 border-indigo-600">
      {/* Header - Always Visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-8 flex items-center justify-between hover:bg-slate-50/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-100 rounded-lg">
            <svg
              className="w-6 h-6 text-indigo-700"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <h3 className="text-2xl font-bold text-slate-900">AI Underwriting Conclusion</h3>
        </div>
        
        {/* Expand/Collapse Icon */}
        <svg
          className={`w-6 h-6 text-slate-500 transition-transform duration-200 ${
            isExpanded ? "rotate-180" : ""
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Expandable Content */}
      {isExpanded && (
        <div className="px-8 pb-8">
          {analysis.analyst_commentary && (
            <div className="mb-8 bg-indigo-50/50 p-6 rounded-xl border border-indigo-100">
              <h4 className="text-sm font-bold text-indigo-900 uppercase tracking-wide mb-2">Analyst Commentary</h4>
              <div className="text-lg text-slate-800 leading-relaxed whitespace-pre-wrap">
                {analysis.analyst_commentary}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {key_decisions.map((decision, index) => (
              <DecisionCard key={index} decision={decision} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}