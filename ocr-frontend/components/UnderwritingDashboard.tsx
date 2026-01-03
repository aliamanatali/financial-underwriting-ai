"use client";

import React from "react";
import { UnderwritingAnalysis, ExplainabilityMetadata } from "@/lib/types";

interface UnderwritingDashboardProps {
  analysis: UnderwritingAnalysis;
}

const METRIC_DEFINITIONS: Record<string, string> = {
  "T12": "Trailing 12 Months: Actual financial performance from the past year.",
  "F12": "Forward 12 Months: Projected financial performance for the upcoming year.",
  "NOI": "Net Operating Income: Total Revenue minus Operating Expenses (excludes debt service).",
  "Cap Rate": "Capitalization Rate: The rate of return (NOI divided by Asset Value).",
  "Gross Potential Rent": "Maximum possible rent if 100% occupied at market rates.",
  "Total Expenses": "All operating costs including taxes, insurance, utilities, and management.",
  "Rent Growth": "Projected annual percentage increase in rental income.",
  "Vacancy Rate": "Estimated percentage of unoccupied units.",
  "Exit Cap": "Projected Cap Rate at the time of future sale.",
  "Loan Amount": "Principal amount of the loan.",
  "Upside": "Potential increase in value or income.",
  "Occupancy": "Percentage of units currently rented.",
  "Avg Monthly Rent": "Average rental income per unit per month.",
  "Total Units": "Total number of rental units in the property."
};

function InfoTooltip({ term }: { term: string }) {
  const definition = METRIC_DEFINITIONS[term] || METRIC_DEFINITIONS[Object.keys(METRIC_DEFINITIONS).find(k => term.includes(k)) || ""] || term;
  
  return (
    <div className="group/info relative inline-block ml-1.5 align-middle">
      <div className="w-3.5 h-3.5 rounded-full border border-slate-400 text-slate-400 flex items-center justify-center text-[9px] font-serif italic cursor-help hover:border-blue-600 hover:text-blue-600 hover:bg-blue-50 transition-colors">
        i
      </div>
      <div className="absolute z-[60] bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover/info:block w-48 p-2 bg-slate-900 text-white text-xs rounded shadow-lg text-center font-normal leading-snug pointer-events-none">
        {definition}
        <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-slate-900" />
      </div>
    </div>
  );
}

function ExplanationTooltip({ metadata }: { metadata?: ExplainabilityMetadata }) {
  if (!metadata) return null;

  return (
    <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block w-96 p-4 bg-white border border-slate-200 rounded-lg shadow-xl text-left text-sm font-normal normal-case">
      <div className="flex justify-between items-start mb-2 border-b pb-2">
        <h4 className="font-bold text-slate-900">{metadata.metric}</h4>
        <span className={`px-2 py-0.5 text-xs rounded-full ${
          metadata.classification.includes("Assumptions")
            ? "bg-amber-100 text-amber-800"
            : "bg-blue-100 text-blue-800"
        }`}>
          {metadata.classification}
        </span>
      </div>
      
      <div className="space-y-3">
        <div>
          <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider">Source</p>
          <p className="text-slate-700">
            <span className="font-medium">{metadata.source.document}</span>
            {metadata.source.fields_used.length > 0 && (
              <span className="text-slate-500"> ({metadata.source.fields_used.join(", ")})</span>
            )}
          </p>
        </div>

        <div>
          <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider">Calculation</p>
          <code className="block bg-slate-50 p-1.5 rounded text-xs text-slate-800 font-mono mt-1 border">
            {metadata.calculation.formula}
          </code>
          <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            {Object.entries(metadata.calculation.inputs).map(([key, val]) => (
              <div key={key} className="flex justify-between">
                <span className="text-slate-500">{key}:</span>
                <span className="font-medium text-slate-900">
                  {typeof val === 'number'
                    ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val)
                    : val}
                </span>
              </div>
            ))}
          </div>
        </div>

        {metadata.adjustments.length > 0 && (
          <div>
            <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider">Adjustments</p>
            <ul className="list-disc list-inside text-xs text-slate-700 mt-1">
              {metadata.adjustments.map((adj, i) => (
                <li key={i}>{adj}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      
      {/* Arrow */}
      <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-white" />
    </div>
  );
}

export default function UnderwritingDashboard({
  analysis,
}: UnderwritingDashboardProps) {
  const getStatusDisplay = (status: string) => {
    if (status === "PASS") {
      return {
        text: "CRITERIA MET",
        color: "bg-emerald-50 text-emerald-800 border-emerald-200",
        icon: "✓",
      };
    } else {
      return {
        text: "CRITERIA NOT MET",
        color: "bg-rose-50 text-rose-800 border-rose-200",
        icon: "✗",
      };
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return (value * 100).toFixed(2) + "%";
  };

  const historicalNOI = analysis.historical_noi || 0;
  const proFormaNOI = analysis.pro_forma_noi || 0;
  const noiChange = proFormaNOI - historicalNOI;
  const noiChangePercent = historicalNOI > 0 ? (noiChange / historicalNOI) * 100 : 0;

  const historicalCapRate = analysis.historical_cap_rate || 0;
  const proFormaCapRate = analysis.cap_rate || 0;
  const capRateChange = proFormaCapRate - historicalCapRate;

  const occupancyRate = analysis.rent_roll_summary?.occupancy_rate || 0;
  const totalUnits = analysis.property_meta?.total_units || 0;
  const occupiedUnits = analysis.rent_roll_summary?.occupied_units || 0;

  return (
    <div className="space-y-8 font-sans">
      {/* Header with Property Info */}
      <div className="bg-white rounded-xl shadow-sm p-8 border-l-4 border-blue-600 ring-1 ring-slate-200">
        <h2 className="text-3xl font-bold text-slate-900 mb-6">
          {analysis.property_meta.address}
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-sm">
          <div className="space-y-1">
            <p className="text-slate-500 uppercase tracking-wide text-xs font-semibold">Year Built</p>
            <p className="font-bold text-lg text-slate-900">{analysis.property_meta.year_built}</p>
          </div>
          <div className="space-y-1">
            <p className="text-slate-500 uppercase tracking-wide text-xs font-semibold">Total Units</p>
            <p className="font-bold text-lg text-slate-900">{totalUnits}</p>
          </div>
          <div className="space-y-1">
            <p className="text-slate-500 uppercase tracking-wide text-xs font-semibold">Occupancy</p>
            <p className="font-bold text-lg text-slate-900">{formatPercent(occupancyRate)}</p>
          </div>
          <div className="space-y-1">
            <p className="text-slate-500 uppercase tracking-wide text-xs font-semibold">Purchase Price</p>
            <p className="font-bold text-lg text-slate-900">
              {formatCurrency(analysis.property_meta.purchase_price)}
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-slate-500 uppercase tracking-wide text-xs font-semibold">Existing Loan</p>
            <p className="font-bold text-lg text-slate-900">
              {formatCurrency(analysis.property_meta.current_loan_balance || 0)}
            </p>
          </div>
        </div>
      </div>

      {/* Pass/Fail Status Badge */}
      <div className={`rounded-xl border p-6 ${getStatusDisplay(analysis.pass_fail_status).color} shadow-sm`}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold flex items-center gap-3 tracking-tight">
              <span className="text-2xl w-8 h-8 flex items-center justify-center rounded-full bg-white/50">{getStatusDisplay(analysis.pass_fail_status).icon}</span>
              Qualification Status: {getStatusDisplay(analysis.pass_fail_status).text}
            </h3>
            {analysis.gating_reasons.length > 0 && (
              <div className="mt-4 pl-11 space-y-2">
                {analysis.gating_reasons.map((reason, idx) => (
                  <p key={idx} className="text-sm font-medium">
                    • {reason}
                  </p>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Deal Parameters */}
      {analysis.deal_parameters && (
        <div className="bg-white rounded-xl shadow-sm p-8 ring-1 ring-slate-200">
          <h3 className="text-xl font-bold text-slate-900 mb-6">Deal Parameters (Valiance Standards)</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="bg-slate-50 p-5 rounded-lg border border-slate-100">
              <p className="text-sm text-slate-600 flex items-center mb-1">
                Rent Growth Rate <InfoTooltip term="Rent Growth" />
              </p>
              <p className="text-2xl font-bold text-slate-900">
                {formatPercent(analysis.deal_parameters.growth_rate)}
              </p>
            </div>
            <div className="bg-slate-50 p-5 rounded-lg border border-slate-100">
              <p className="text-sm text-slate-600 flex items-center mb-1">
                Vacancy Rate <InfoTooltip term="Vacancy Rate" />
              </p>
              <p className="text-2xl font-bold text-slate-900">
                {formatPercent(analysis.deal_parameters.vacancy_rate)}
              </p>
            </div>
            <div className="bg-slate-50 p-5 rounded-lg border border-slate-100">
              <p className="text-sm text-slate-600 flex items-center mb-1">
                Exit Cap Rate <InfoTooltip term="Exit Cap" />
              </p>
              <p className="text-2xl font-bold text-slate-900">
                {formatPercent(analysis.deal_parameters.exit_cap_rate)}
              </p>
            </div>
            <div className="bg-slate-50 p-5 rounded-lg border border-slate-100 group relative cursor-help">
              <p className="text-sm text-slate-600 flex items-center mb-1">
                <span className="border-b border-dashed border-slate-400">Loan Amount</span>
                <InfoTooltip term="Loan Amount" />
              </p>
              <p className="text-2xl font-bold text-slate-900">
                {formatCurrency(analysis.deal_parameters?.loan_amount || 0)}
              </p>
              <ExplanationTooltip metadata={analysis.explainability?.["Loan Amount"]} />
            </div>
          </div>
        </div>
      )}

      {/* Financial Summary - Side by Side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* T12 (Historical) */}
        <div className="bg-white rounded-xl shadow-sm p-8 border-t-4 border-orange-500 ring-1 ring-slate-200">
          <h3 className="text-xl font-bold text-slate-900 mb-6 flex items-center">
            <span className="text-orange-600 mr-2">●</span> T12 (Historical) <InfoTooltip term="T12" />
          </h3>
          <div className="space-y-4">
            <div className="flex justify-between pb-3 border-b border-slate-100">
              <span className="text-slate-600 flex items-center">
                Gross Potential Rent <InfoTooltip term="Gross Potential Rent" />
              </span>
              <span className="font-semibold text-slate-900">
                {formatCurrency(analysis.rent_roll_summary?.total_annual_rent || 0)}
              </span>
            </div>
            <div className="flex justify-between pb-3 border-b border-slate-100">
              <span className="text-slate-600 flex items-center">
                Total Expenses <InfoTooltip term="Total Expenses" />
              </span>
              <span className="font-semibold text-rose-600">
                -{formatCurrency(
                  analysis.historical_total_expenses ||
                  analysis.historical_expenses?.reduce((sum, e) => sum + e.amount, 0) ||
                  0
                )}
              </span>
            </div>
            <div className="flex justify-between bg-orange-50 p-4 rounded-lg font-bold text-lg border border-orange-100">
              <span className="flex items-center text-orange-900">
                Net Operating Income <InfoTooltip term="NOI" />
              </span>
              <span className="text-orange-700">{formatCurrency(historicalNOI)}</span>
            </div>
            <div className="flex justify-between pt-2 text-lg font-bold px-2">
              <span className="flex items-center text-slate-700">
                Cap Rate <InfoTooltip term="Cap Rate" />
              </span>
              <span className="text-slate-900">{formatPercent(historicalCapRate)}</span>
            </div>
          </div>
        </div>

        {/* F12 (Pro Forma) */}
        <div className="bg-white rounded-xl shadow-sm p-8 border-t-4 border-emerald-500 ring-1 ring-slate-200">
          <h3 className="text-xl font-bold text-slate-900 mb-6 flex items-center">
            <span className="text-emerald-600 mr-2">●</span> F12 (Pro Forma) <InfoTooltip term="F12" />
          </h3>
          <div className="space-y-4">
            <div className="flex justify-between pb-3 border-b border-slate-100 group relative cursor-help">
              <div className="flex items-center gap-1">
                <span className="text-slate-600 border-b border-dashed border-slate-400">Gross Potential Rent</span>
                <InfoTooltip term="Gross Potential Rent" />
              </div>
              <span className="font-semibold text-slate-900">
                {formatCurrency(
                  analysis.rent_roll.reduce((sum, item) => sum + item.market_rent * 12, 0)
                )}
              </span>
              <ExplanationTooltip metadata={analysis.explainability?.["Gross Potential Rent"]} />
            </div>
            <div className="flex justify-between pb-3 border-b border-slate-100 group relative cursor-help">
              <div className="flex items-center gap-1">
                <span className="text-slate-600 border-b border-dashed border-slate-400">Total Expenses</span>
                <InfoTooltip term="Total Expenses" />
              </div>
              <span className="font-semibold text-rose-600">
                -{formatCurrency(analysis.pro_forma_expenses || 0)}
              </span>
              <ExplanationTooltip metadata={analysis.explainability?.["Total Operating Expenses"]} />
            </div>
            <div className="flex justify-between bg-emerald-50 p-4 rounded-lg font-bold text-lg border border-emerald-100 group relative cursor-help">
              <div className="flex items-center gap-1 text-emerald-900">
                <span className="border-b border-dashed border-emerald-700/50">Net Operating Income</span>
                <InfoTooltip term="NOI" />
              </div>
              <span className="text-emerald-700">{formatCurrency(proFormaNOI)}</span>
              <ExplanationTooltip metadata={analysis.explainability?.["Net Operating Income (NOI)"]} />
            </div>
            <div className="flex justify-between pt-2 text-lg font-bold px-2 group relative cursor-help">
              <div className="flex items-center gap-1 text-slate-700">
                <span className="border-b border-dashed border-slate-400">Cap Rate</span>
                <InfoTooltip term="Cap Rate" />
              </div>
              <span className="text-slate-900">{formatPercent(proFormaCapRate)}</span>
              <ExplanationTooltip metadata={analysis.explainability?.["Entry Cap Rate"]} />
            </div>
          </div>
        </div>
      </div>

      {/* Upside Potential */}
      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl shadow-sm p-8 border border-blue-100">
        <h3 className="text-xl font-bold text-blue-900 mb-6 flex items-center">
            <svg className="w-6 h-6 mr-2 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
            Upside Potential
        </h3>
        <div className="grid grid-cols-2 gap-8">
          <div className="bg-white/60 p-6 rounded-lg backdrop-blur-sm border border-blue-100">
            <p className="text-slate-600 text-sm mb-3 flex items-center uppercase tracking-wide font-semibold">
              NOI Upside <InfoTooltip term="Upside" />
            </p>
            <p className="text-4xl font-extrabold text-blue-600">
              {formatCurrency(noiChange)}
            </p>
            <p className="text-sm font-medium text-slate-600 mt-2">
              <span className="text-emerald-600 font-bold">{noiChangePercent > 0 ? "+" : ""}{noiChangePercent.toFixed(1)}%</span> vs Historical
            </p>
          </div>
          <div className="bg-white/60 p-6 rounded-lg backdrop-blur-sm border border-blue-100">
            <p className="text-slate-600 text-sm mb-3 flex items-center uppercase tracking-wide font-semibold">
              Cap Rate Upside <InfoTooltip term="Upside" />
            </p>
            <p className="text-4xl font-extrabold text-blue-600">
              {(capRateChange * 100).toFixed(2)}%
            </p>
            <p className="text-sm font-medium text-slate-600 mt-2">
              {historicalCapRate.toFixed(2)}% → <span className="text-emerald-600 font-bold">{proFormaCapRate.toFixed(2)}%</span>
            </p>
          </div>
        </div>
      </div>

      {/* Rent Roll Summary */}
      <div className="bg-white rounded-xl shadow-sm p-8 ring-1 ring-slate-200">
        <h3 className="text-xl font-bold text-slate-900 mb-6">Rent Roll Summary</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div className="bg-slate-50 p-5 rounded-lg border border-slate-100">
            <p className="text-sm text-slate-600 flex items-center mb-1">
              Total Units <InfoTooltip term="Total Units" />
            </p>
            <p className="text-3xl font-bold text-slate-900">{totalUnits}</p>
          </div>
          <div className="bg-emerald-50 p-5 rounded-lg border border-emerald-100">
            <p className="text-sm text-emerald-800 flex items-center mb-1">
              Occupied Units <InfoTooltip term="Occupancy" />
            </p>
            <p className="text-3xl font-bold text-emerald-700">{occupiedUnits}</p>
          </div>
          <div className="bg-amber-50 p-5 rounded-lg border border-amber-100">
            <p className="text-sm text-amber-800 flex items-center mb-1">
              Occupancy Rate <InfoTooltip term="Occupancy" />
            </p>
            <p className="text-3xl font-bold text-amber-700">{formatPercent(occupancyRate)}</p>
          </div>
          <div className="bg-indigo-50 p-5 rounded-lg border border-indigo-100">
            <p className="text-sm text-indigo-800 flex items-center mb-1">
              Avg Monthly Rent <InfoTooltip term="Avg Monthly Rent" />
            </p>
            <p className="text-2xl font-bold text-indigo-700">
              {formatCurrency(
                analysis.rent_roll_summary?.total_monthly_rent
                  ? analysis.rent_roll_summary.total_monthly_rent / totalUnits
                  : 0
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
