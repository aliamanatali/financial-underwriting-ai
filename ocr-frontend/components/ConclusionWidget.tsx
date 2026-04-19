"use client";

import React, { useState } from "react";
import { UnderwritingAnalysis, DecisionImpact } from "@/lib/types";

interface ConclusionWidgetProps {
  analysis: UnderwritingAnalysis;
}

function DecisionCard({ decision }: { decision: DecisionImpact }) {
  return (
    <div className="bg-[#F1F5F9] rounded-xl p-5 border border-[#E2E8F0] hover:border-[#CBD5E1] transition-all duration-150">
      <div className="flex justify-between items-start mb-3">
        <h4 className="font-bold text-[#0F172A] text-xs uppercase tracking-widest">
          {decision.metric}
        </h4>
        <span className="bg-[rgba(249,115,22,0.12)] text-[#F97316] text-[9px] px-2 py-0.5 rounded-full font-semibold border border-[rgba(249,115,22,0.2)] uppercase tracking-wide">
          AI Decision
        </span>
      </div>

      <p className="text-base font-semibold text-[#0F172A] mb-4 leading-snug">
        {decision.decision}
      </p>

      <div className="space-y-3">
        <div>
          <p className="text-[9px] text-[#64748B] font-semibold uppercase tracking-widest mb-1.5">Reasoning</p>
          <p className="text-xs text-[#475569] leading-relaxed bg-[#F8FAFC] p-3 rounded-lg border border-[#E2E8F0]">
            {decision.reasoning}
          </p>
        </div>
        <div>
          <p className="text-[9px] text-[#64748B] font-semibold uppercase tracking-widest mb-1.5">Client Impact</p>
          <p className="text-xs leading-relaxed bg-[rgba(245,158,11,0.06)] p-3 rounded-lg border border-[rgba(245,158,11,0.15)] text-[#F59E0B]">
            {decision.impact}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function ConclusionWidget({ analysis }: ConclusionWidgetProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!analysis.conclusion) return null;

  const { summary, key_decisions } = analysis.conclusion;
  const isPassing = analysis.pass_fail_status === "PASS";

  return (
    <div className="rounded-xl border border-[#E2E8F0] bg-white overflow-hidden shadow-[var(--shadow-card)]" style={{ borderTop: "3px solid #F97316" }}>

      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-7 py-6 flex items-center justify-between hover:bg-[#F1F5F9] transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          {/* Sparkle icon */}
          <div className="p-2 bg-[rgba(249,115,22,0.12)] rounded-lg border border-[rgba(249,115,22,0.2)]">
            <svg className="w-5 h-5 text-[#F97316]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 3l1.5 1.5M19 3l-1.5 1.5M12 2v2M3 12h2M19 12h2M5 21l1.5-1.5M19 21l-1.5-1.5M12 22v-2M12 6a6 6 0 100 12 6 6 0 000-12z" />
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-[#0F172A] uppercase tracking-wide">
                ✦ AI Underwriting Conclusion
              </h3>
              <span className="text-[9px] font-semibold text-[#64748B] uppercase tracking-widest bg-[#F1F5F9] border border-[#E2E8F0] px-2 py-0.5 rounded-full">
                AI Generated
              </span>
            </div>
            <p className="text-xs text-[#64748B] mt-0.5">
              Qualification Status:&nbsp;
              <span className={`font-semibold ${isPassing ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
                {isPassing ? "CRITERIA MET" : "CRITERIA NOT MET"}
              </span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wide ${
            isPassing
              ? "bg-[rgba(34,197,94,0.12)] text-[#22C55E] border border-[rgba(34,197,94,0.2)]"
              : "bg-[rgba(239,68,68,0.12)] text-[#EF4444] border border-[rgba(239,68,68,0.2)]"
          }`}>
            <span className={`w-2 h-2 rounded-full ${isPassing ? "bg-[#22C55E]" : "bg-[#EF4444] animate-pulse"}`} />
            {isPassing ? "PASS" : "CRITERIA NOT MET"}
          </span>
          <svg className={`w-5 h-5 text-[#64748B] transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Summary always visible when expanded */}
      {summary && isExpanded && (
        <div className="px-7 pb-2">
          <p className="text-sm text-[#475569] leading-relaxed">{summary}</p>
        </div>
      )}

      {/* Expandable content */}
      {isExpanded && (
        <div className="px-7 pb-7 pt-4 space-y-6">

          {/* Analyst Commentary */}
          {analysis.analyst_commentary && (
            <div className="relative bg-[#F1F5F9] p-6 rounded-xl border border-[#E2E8F0]">
              {/* Gradient left accent */}
              <div className="absolute left-0 top-4 bottom-4 w-0.5 bg-gradient-to-b from-[#F97316] via-[#F97316]/50 to-transparent rounded-full" />
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-[9px] font-bold text-[#64748B] uppercase tracking-widest pl-3">Analyst Commentary</h4>
                <span className="text-[9px] font-semibold text-[#64748B] uppercase tracking-widest bg-[rgba(249,115,22,0.08)] border border-[rgba(249,115,22,0.15)] px-2 py-0.5 rounded-full">
                  AI Generated
                </span>
              </div>
              <p className="text-sm text-[#475569] leading-[1.7] whitespace-pre-wrap pl-3 max-w-[70ch]">
                {analysis.analyst_commentary}
              </p>
            </div>
          )}

          {/* Key decisions grid */}
          {key_decisions && key_decisions.length > 0 && (
            <div>
              <h4 className="text-[9px] font-bold text-[#64748B] uppercase tracking-widest mb-3">Investment Criteria</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {key_decisions.map((decision, i) => (
                  <DecisionCard key={i} decision={decision} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
