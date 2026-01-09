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
    <div className="bg-white rounded-xl border border-neutral-200 shadow-sm p-6">
      <h3 className="text-sm font-semibold text-neutral-900 mb-4">Sensitivity Analysis (IRR)</h3>
      <div className="flex flex-col h-full">
        <div className="flex justify-between items-end mb-2">
          <div className="text-[10px] text-neutral-500 font-medium uppercase tracking-wide">Exit Cap Rate ↓</div>
          <div className="text-[10px] text-neutral-500 font-medium uppercase tracking-wide">Rent Growth →</div>
        </div>
        
        <div className="flex-1 border border-neutral-100 rounded-lg overflow-hidden">
          <table className="w-full text-center h-full">
            <thead>
              <tr className="bg-neutral-50 text-[10px] text-neutral-500 border-b border-neutral-100">
                <th className="p-2 border-r border-neutral-100 bg-white"></th>
                {growthRates.map((growth, idx) => (
                  <th key={idx} className="p-2">{formatPercent(growth)}</th>
                ))}
              </tr>
            </thead>
            <tbody className="text-xs font-medium">
              {exitCaps.map((cap, rowIdx) => (
                <tr key={rowIdx}>
                  <td className="bg-neutral-50 text-neutral-500 border-r border-neutral-100 p-2">{formatPercent(cap)}</td>
                  {values[rowIdx]?.map((irr, colIdx) => {
                    const isCurrentCell = rowIdx === 1 && colIdx === 1; // Highlight current parameters
                    return (
                      <td
                        key={colIdx}
                        className={`p-2 ${getCellColor(irr)} ${isCurrentCell ? 'border border-neutral-900' : ''}`}
                      >
                        {formatPercent(irr)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex gap-4 mt-3 justify-center">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-rose-500"></div>
            <span className="text-[10px] text-neutral-500">Risky (&lt;8%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-amber-400"></div>
            <span className="text-[10px] text-neutral-500">Moderate (8-12%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
            <span className="text-[10px] text-neutral-500">Strong (&gt;12%)</span>
          </div>
        </div>
      </div>
    </div>
  );
}