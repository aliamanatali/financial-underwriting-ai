import React from "react";
import { UnderwritingAnalysis } from "@/lib/types";

interface SensitivityAnalysisWidgetProps {
  analysis: UnderwritingAnalysis;
}

export default function SensitivityAnalysisWidget({
  analysis,
}: SensitivityAnalysisWidgetProps) {
  const sensitivityData = analysis.sensitivity_analysis;

  if (!sensitivityData) {
    return null;
  }

  const { rows: exitCaps, columns: growthRates, values } = sensitivityData;

  const formatPercent = (value: number) => {
    return (value * 100).toFixed(1) + "%";
  };

  const getCellColor = (irr: number) => {
    if (irr < 0.08) return "bg-rose-50 text-rose-700";
    if (irr < 0.12) return "bg-amber-50 text-amber-700";
    if (irr < 0.15) return "bg-emerald-50 text-emerald-700";
    return "bg-emerald-100 text-emerald-800 font-bold";
  };

  return (
    <div className="bg-white rounded-xl shadow-sm p-8 border border-slate-200">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <svg
              className="w-5 h-5 text-indigo-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            Sensitivity Analysis (IRR)
          </h3>
          <p className="text-sm text-slate-500 mt-1">
            Impact of Exit Cap Rate and Rent Growth on Returns
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm text-center border-collapse">
          <thead>
            <tr>
              <th className="p-3 border-b-2 border-slate-100 text-left bg-slate-50/50">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block">
                  Exit Cap Rate ↓
                </span>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block mt-1">
                  Rent Growth →
                </span>
              </th>
              {growthRates.map((growth, idx) => (
                <th
                  key={idx}
                  className="p-3 border-b-2 border-slate-100 bg-slate-50 text-slate-700 font-semibold"
                >
                  {formatPercent(growth)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {exitCaps.map((cap, rowIdx) => (
              <tr key={rowIdx}>
                <td className="p-3 border-r border-slate-100 font-semibold text-slate-700 bg-slate-50">
                  {formatPercent(cap)}
                </td>
                {values[rowIdx]?.map((irr, colIdx) => (
                  <td
                    key={colIdx}
                    className={`p-3 border border-slate-100 transition-colors hover:brightness-95 cursor-default ${getCellColor(
                      irr
                    )}`}
                  >
                    {formatPercent(irr)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex gap-4 text-xs text-slate-500 justify-end">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-rose-50 border border-rose-200"></span>
          <span>&lt; 8% (Risky)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-amber-50 border border-amber-200"></span>
          <span>8% - 12% (Moderate)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-emerald-50 border border-emerald-200"></span>
          <span>&gt; 12% (Strong)</span>
        </div>
      </div>
    </div>
  );
}