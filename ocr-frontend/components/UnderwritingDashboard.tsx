"use client";

import React, { useState } from "react";
import { UnderwritingAnalysis, ExplainabilityMetadata, DealParameters } from "@/lib/types";
import SensitivityAnalysisWidget from "./SensitivityAnalysisWidget";
import ConclusionWidget from "./ConclusionWidget";

interface UnderwritingDashboardProps {
  analysis: UnderwritingAnalysis;
  onReanalyze?: (params: DealParameters) => void;
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
  "Total Units": "Total number of rental units in the property.",
  "IRR": "Internal Rate of Return: The annual rate of growth that an investment is expected to generate.",
  "MOIC": "Multiple on Invested Capital: Total cash returned divided by total cash invested.",
  "Cash on Cash": "Cash-on-Cash Return: Annual pre-tax cash flow divided by actual cash invested."
};

function InfoTooltip({ term }: { term: string }) {
  const definition = METRIC_DEFINITIONS[term] || METRIC_DEFINITIONS[Object.keys(METRIC_DEFINITIONS).find(k => term.includes(k)) || ""] || term;
  
  return (
    <span className="group/info relative inline-block ml-1.5 align-middle">
      <span className="w-3.5 h-3.5 rounded-full border border-slate-400 text-slate-400 flex items-center justify-center text-[9px] font-serif italic cursor-help hover:border-blue-600 hover:text-blue-600 hover:bg-blue-50 transition-colors">
        i
      </span>
      <span className="absolute z-[60] bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover/info:block w-48 p-2 bg-slate-900 text-white text-xs rounded shadow-lg text-center font-normal leading-snug pointer-events-none">
        {definition}
        <span className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-slate-900" />
      </span>
    </span>
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
  onReanalyze,
}: UnderwritingDashboardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editParams, setEditParams] = useState<DealParameters>(
    analysis.deal_parameters || {
      growth_rate: 0.03,
      exit_cap_rate: 0.06,
      vacancy_rate: 0.05,
      loan_amount: 5000000,
    }
  );

  // New state for Property Info editing
  const [isEditingProperty, setIsEditingProperty] = useState(false);
  const [propertyEditParams, setPropertyEditParams] = useState({
    total_units: 0,
    purchase_price: 0,
    occupancy_rate: 0
  });

  // Sync state when analysis updates
  React.useEffect(() => {
    if (analysis.deal_parameters) {
      // Ensure loan_amount is preserved or defaulted to 0 if missing/null to avoid controlled/uncontrolled issues
      const syncedParams = {
        ...analysis.deal_parameters,
        loan_amount: analysis.deal_parameters.loan_amount ?? 0
      };
      setEditParams(syncedParams);
    }
    
    // Sync property params
    if (analysis.property_meta) {
      setPropertyEditParams({
        total_units: analysis.property_meta.total_units || 0,
        purchase_price: analysis.property_meta.purchase_price || 0,
        occupancy_rate: analysis.rent_roll_summary?.occupancy_rate || 0
      });
    }
  }, [analysis.deal_parameters, analysis.property_meta]);

  const handleParamChange = (key: keyof DealParameters, value: string) => {
    // Handle percentage inputs (user types 3 for 3%, we store 0.03)
    // Handle loan amount (raw number)
    let numValue = parseFloat(value);
    
    if (isNaN(numValue)) numValue = 0;

    if (key === 'growth_rate' || key === 'exit_cap_rate' || key === 'vacancy_rate') {
      numValue = numValue / 100;
    }

    setEditParams(prev => ({
      ...prev,
      [key]: numValue
    }));
  };

  const handleSave = () => {
    if (onReanalyze) {
      // Ensure loan_amount is a number and included
      // If user clears the input (0), we send 0 which allows backend to fallback to calculation
      // If user types a value, we send that value
      const cleanParams = {
        ...editParams,
        loan_amount: Number(editParams.loan_amount || 0)
      };
      console.log("Saving params:", cleanParams);
      onReanalyze(cleanParams);
      setIsEditing(false);
    }
  };

  const handlePropertySave = () => {
    if (onReanalyze) {
      const updatedParams = {
        ...editParams,
        units_override: propertyEditParams.total_units,
        purchase_price_override: propertyEditParams.purchase_price,
        occupancy_override: propertyEditParams.occupancy_rate
      };
      console.log("Saving property params:", updatedParams);
      onReanalyze(updatedParams);
      setIsEditingProperty(false);
    }
  };

  const handleCancel = () => {
    setEditParams(analysis.deal_parameters || editParams);
    setIsEditing(false);
  };

  const handlePropertyCancel = () => {
    if (analysis.property_meta) {
      setPropertyEditParams({
        total_units: analysis.property_meta.total_units || 0,
        purchase_price: analysis.property_meta.purchase_price || 0,
        occupancy_rate: analysis.rent_roll_summary?.occupancy_rate || 0
      });
    }
    setIsEditingProperty(false);
  };

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
  const occupiedUnits = Math.round(totalUnits * occupancyRate);
  const purchasePrice = analysis.property_meta.purchase_price || 0;
  const pricePerUnit = totalUnits > 0 ? purchasePrice / totalUnits : 0;

  return (
    <div className="space-y-8 font-sans">
      {/* Header with Property Info */}
      <div className="bg-white rounded-xl shadow-sm p-8 border-l-4 border-blue-600 ring-1 ring-slate-200 relative">
        <div className="flex justify-between items-start mb-6">
          <h2 className="text-3xl font-bold text-slate-900">
            {analysis.property_meta.address}
          </h2>
          {!isEditingProperty ? (
            <button
              onClick={() => setIsEditingProperty(true)}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium px-3 py-1.5 rounded-lg hover:bg-blue-50 transition-colors flex items-center gap-1"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
              </svg>
              Edit
            </button>
          ) : (
            <div className="flex gap-2">
              <button
                onClick={handlePropertyCancel}
                className="text-sm text-slate-600 hover:text-slate-800 font-medium px-3 py-1.5 rounded-lg hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handlePropertySave}
                className="text-sm bg-blue-600 text-white hover:bg-blue-700 font-medium px-3 py-1.5 rounded-lg transition-colors shadow-sm"
              >
                Save
              </button>
            </div>
          )}
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6 text-sm">
          <div className="space-y-1">
            <p className="text-slate-500 uppercase tracking-wide text-xs font-semibold">Year Built</p>
            <p className="font-bold text-lg text-slate-900">{analysis.property_meta.year_built}</p>
          </div>
          
          <div className="space-y-1">
            <p className="text-slate-500 uppercase tracking-wide text-xs font-semibold">Total Units</p>
            {isEditingProperty ? (
               <input
                  type="number"
                  className="w-full bg-slate-50 border border-slate-300 rounded px-2 py-1 text-lg font-bold text-slate-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  value={propertyEditParams.total_units}
                  onChange={(e) => setPropertyEditParams({...propertyEditParams, total_units: Number(e.target.value)})}
               />
            ) : (
              <p className="font-bold text-lg text-slate-900">{totalUnits}</p>
            )}
          </div>
          
          <div className="space-y-1">
            <p className="text-slate-500 uppercase tracking-wide text-xs font-semibold">Occupancy</p>
             {isEditingProperty ? (
               <div className="flex items-center">
                   <input
                      type="number"
                      step="0.1"
                      className="w-full bg-slate-50 border border-slate-300 rounded px-2 py-1 text-lg font-bold text-slate-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                      value={(propertyEditParams.occupancy_rate * 100).toFixed(1)}
                      onChange={(e) => setPropertyEditParams({...propertyEditParams, occupancy_rate: Number(e.target.value) / 100})}
                   />
                   <span className="ml-1 font-bold text-slate-500">%</span>
               </div>
            ) : (
                <p className="font-bold text-lg text-slate-900">{formatPercent(occupancyRate)}</p>
            )}
          </div>
          
          <div className="space-y-1">
            <p className="text-slate-500 uppercase tracking-wide text-xs font-semibold">Purchase Price</p>
            {isEditingProperty ? (
               <div className="flex items-center">
                  <span className="mr-1 font-bold text-slate-500">$</span>
                  <input
                    type="text"
                    className="w-full bg-slate-50 border border-slate-300 rounded px-2 py-1 text-lg font-bold text-slate-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                    value={propertyEditParams.purchase_price}
                    onChange={(e) => {
                        const val = e.target.value.replace(/[^0-9.]/g, '');
                        setPropertyEditParams({...propertyEditParams, purchase_price: Number(val)})
                    }}
                  />
               </div>
            ) : (
              <p className="font-bold text-lg text-slate-900">
                {formatCurrency(purchasePrice)}
              </p>
            )}
          </div>
          
          <div className="space-y-1">
            <p className="text-slate-500 uppercase tracking-wide text-xs font-semibold">Price Per Unit</p>
            <p className="font-bold text-lg text-slate-900">
              {isEditingProperty && propertyEditParams.total_units > 0
                ? formatCurrency(propertyEditParams.purchase_price / propertyEditParams.total_units)
                : formatCurrency(pricePerUnit)
              }
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

      {/* Conclusion & Decision Impact */}
      <ConclusionWidget analysis={analysis} />
      
      {/* Investment Checklist */}
      {analysis.conclusion?.investment_checklist && (
        <div className="bg-white rounded-xl shadow-sm p-8 ring-1 ring-slate-200">
             <h3 className="text-xl font-bold text-slate-900 mb-6 flex items-center gap-2">
                <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Investment Criteria Checklist
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                 {[
                    { q: "Is the property a multifamily investment?", a: analysis.conclusion.investment_checklist.is_multifamily },
                    { q: "Is it within 6 blocks of campus?", a: analysis.conclusion.investment_checklist.near_campus },
                    { q: "What is the business plan?", a: analysis.conclusion.investment_checklist.business_plan },
                    { q: "Are existing rents below market?", a: analysis.conclusion.investment_checklist.rents_below_market },
                    { q: "Is it poorly run/mismanaged?", a: analysis.conclusion.investment_checklist.is_mismanaged },
                    { q: "Diligence items remaining?", a: analysis.conclusion.investment_checklist.diligence_issues },
                    { q: "Primary Risks", a: analysis.conclusion.investment_checklist.primary_risks },
                    { q: "Price Per Unit Analysis", a: analysis.conclusion.investment_checklist.price_per_unit_analysis },
                 ].map((item, idx) => (
                    <div key={idx} className="bg-slate-50 p-4 rounded-lg border border-slate-100 flex justify-between items-center">
                        <span className="text-sm font-medium text-slate-700">{item.q}</span>
                        <span className="text-sm font-bold text-slate-900 ml-4 text-right">{item.a}</span>
                    </div>
                 ))}
            </div>
        </div>
      )}

      {/* Deal Parameters */}
      {analysis.deal_parameters && (
        <div className="bg-white rounded-xl shadow-sm p-8 ring-1 ring-slate-200">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-xl font-bold text-slate-900">Deal Parameters (Valiance Standards)</h3>
            {!isEditing ? (
              <button
                onClick={() => setIsEditing(true)}
                className="text-sm text-blue-600 hover:text-blue-800 font-medium px-3 py-1.5 rounded-lg hover:bg-blue-50 transition-colors"
              >
                Edit Parameters
              </button>
            ) : (
              <div className="flex gap-2">
                 <button
                  onClick={handleCancel}
                  className="text-sm text-slate-600 hover:text-slate-800 font-medium px-3 py-1.5 rounded-lg hover:bg-slate-100 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  className="text-sm bg-blue-600 text-white hover:bg-blue-700 font-medium px-3 py-1.5 rounded-lg transition-colors shadow-sm"
                >
                  Save & Regenerate
                </button>
              </div>
            )}
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className={`bg-slate-50 p-5 rounded-lg border ${isEditing ? 'border-blue-300 ring-2 ring-blue-100' : 'border-slate-100'}`}>
              <div className="text-sm text-slate-600 flex items-center mb-1">
                Rent Growth Rate <InfoTooltip term="Rent Growth" />
              </div>
              {isEditing ? (
                 <div className="flex items-center">
                   <input
                      type="number"
                      step="0.1"
                      className="w-full bg-white border border-slate-300 rounded px-2 py-1 text-lg font-bold text-slate-900 focus:outline-none focus:border-blue-500"
                      value={(editParams.growth_rate * 100).toFixed(1)}
                      onChange={(e) => handleParamChange('growth_rate', e.target.value)}
                   />
                   <span className="ml-1 font-bold text-slate-500">%</span>
                 </div>
              ) : (
                <p className="text-2xl font-bold text-slate-900">
                  {formatPercent(analysis.deal_parameters.growth_rate)}
                </p>
              )}
            </div>

            <div className={`bg-slate-50 p-5 rounded-lg border ${isEditing ? 'border-blue-300 ring-2 ring-blue-100' : 'border-slate-100'}`}>
              <div className="text-sm text-slate-600 flex items-center mb-1">
                Vacancy Rate <InfoTooltip term="Vacancy Rate" />
              </div>
              {isEditing ? (
                 <div className="flex items-center">
                   <input
                      type="number"
                      step="0.1"
                      className="w-full bg-white border border-slate-300 rounded px-2 py-1 text-lg font-bold text-slate-900 focus:outline-none focus:border-blue-500"
                      value={(editParams.vacancy_rate * 100).toFixed(1)}
                      onChange={(e) => handleParamChange('vacancy_rate', e.target.value)}
                   />
                   <span className="ml-1 font-bold text-slate-500">%</span>
                 </div>
              ) : (
                <p className="text-2xl font-bold text-slate-900">
                  {formatPercent(analysis.deal_parameters.vacancy_rate)}
                </p>
              )}
            </div>

            <div className={`bg-slate-50 p-5 rounded-lg border ${isEditing ? 'border-blue-300 ring-2 ring-blue-100' : 'border-slate-100'}`}>
              <div className="text-sm text-slate-600 flex items-center mb-1">
                Exit Cap Rate <InfoTooltip term="Exit Cap" />
              </div>
               {isEditing ? (
                 <div className="flex items-center">
                   <input
                      type="number"
                      step="0.1"
                      className="w-full bg-white border border-slate-300 rounded px-2 py-1 text-lg font-bold text-slate-900 focus:outline-none focus:border-blue-500"
                      value={(editParams.exit_cap_rate * 100).toFixed(1)}
                      onChange={(e) => handleParamChange('exit_cap_rate', e.target.value)}
                   />
                   <span className="ml-1 font-bold text-slate-500">%</span>
                 </div>
              ) : (
                <p className="text-2xl font-bold text-slate-900">
                  {formatPercent(analysis.deal_parameters.exit_cap_rate)}
                </p>
              )}
            </div>

            <div className={`bg-slate-50 p-5 rounded-lg border ${isEditing ? 'border-blue-300 ring-2 ring-blue-100' : 'border-slate-100'} group relative cursor-help`}>
              <div className="text-sm text-slate-600 flex items-center mb-1">
                <span className="border-b border-dashed border-slate-400">Loan Amount</span>
                <InfoTooltip term="Loan Amount" />
              </div>
              {isEditing ? (
                 <div className="flex items-center">
                   <span className="mr-1 font-bold text-slate-500">$</span>
                   <input
                      type="text"
                      className="w-full bg-white border border-slate-300 rounded px-2 py-1 text-lg font-bold text-slate-900 focus:outline-none focus:border-blue-500"
                      value={editParams.loan_amount ?? 0}
                      onChange={(e) => {
                          // Remove all non-numeric chars except decimal point
                          const val = e.target.value.replace(/[^0-9.]/g, '');
                          handleParamChange('loan_amount', val);
                      }}
                   />
                 </div>
              ) : (
                <>
                  <p className="text-2xl font-bold text-slate-900">
                    {formatCurrency(analysis.deal_parameters?.loan_amount || 0)}
                  </p>
                  <ExplanationTooltip metadata={analysis.explainability?.["Loan Amount"]} />
                </>
              )}
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

      {/* Investment Returns */}
      <div className="bg-white rounded-xl shadow-sm p-8 ring-1 ring-slate-200">
        <h3 className="text-xl font-bold text-slate-900 mb-6 flex items-center">
          <svg className="w-6 h-6 mr-2 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Investment Returns (5-Year Hold)
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-purple-50 p-5 rounded-lg border border-purple-100">
            <div className="text-sm text-purple-900 flex items-center mb-1 font-semibold">
              IRR (Levered) <InfoTooltip term="IRR" />
            </div>
            <p className="text-3xl font-bold text-purple-700">
              {formatPercent(analysis.irr || 0)}
            </p>
            <p className="text-xs text-purple-600 mt-2">
              Internal Rate of Return
            </p>
          </div>
          <div className="bg-blue-50 p-5 rounded-lg border border-blue-100">
            <div className="text-sm text-blue-900 flex items-center mb-1 font-semibold">
              MOIC <InfoTooltip term="MOIC" />
            </div>
            <p className="text-3xl font-bold text-blue-700">
              {(analysis.moic || 0).toFixed(2)}x
            </p>
             <p className="text-xs text-blue-600 mt-2">
              Multiple on Invested Capital
            </p>
          </div>
           <div className="bg-emerald-50 p-5 rounded-lg border border-emerald-100">
            <div className="text-sm text-emerald-900 flex items-center mb-1 font-semibold">
              Cash-on-Cash <InfoTooltip term="Cash on Cash" />
            </div>
            <p className="text-3xl font-bold text-emerald-700">
              {formatPercent(analysis.cash_on_cash_return || 0)}
            </p>
             <p className="text-xs text-emerald-600 mt-2">
              Avg. Annual Cash Yield
            </p>
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
            <div className="text-slate-600 text-sm mb-3 flex items-center uppercase tracking-wide font-semibold">
              NOI Upside <InfoTooltip term="Upside" />
            </div>
            <p className="text-4xl font-extrabold text-blue-600">
              {formatCurrency(noiChange)}
            </p>
            <p className="text-sm font-medium text-slate-600 mt-2">
              <span className="text-emerald-600 font-bold">{noiChangePercent > 0 ? "+" : ""}{noiChangePercent.toFixed(1)}%</span> vs Historical
            </p>
          </div>
          <div className="bg-white/60 p-6 rounded-lg backdrop-blur-sm border border-blue-100">
            <div className="text-slate-600 text-sm mb-3 flex items-center uppercase tracking-wide font-semibold">
              Cap Rate Upside <InfoTooltip term="Upside" />
            </div>
            <p className="text-4xl font-extrabold text-blue-600">
              {(capRateChange * 100).toFixed(2)}%
            </p>
            <p className="text-sm font-medium text-slate-600 mt-2">
              {historicalCapRate.toFixed(2)}% → <span className="text-emerald-600 font-bold">{proFormaCapRate.toFixed(2)}%</span>
            </p>
          </div>
        </div>
      </div>

      {/* Sensitivity Analysis */}
      <SensitivityAnalysisWidget analysis={analysis} />

      {/* Rent Roll Summary */}
      <div className="bg-white rounded-xl shadow-sm p-8 ring-1 ring-slate-200">
        <h3 className="text-xl font-bold text-slate-900 mb-6">Rent Roll Summary</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div className="bg-slate-50 p-5 rounded-lg border border-slate-100">
            <div className="text-sm text-slate-600 flex items-center mb-1">
              Total Units <InfoTooltip term="Total Units" />
            </div>
            <p className="text-3xl font-bold text-slate-900">{totalUnits}</p>
          </div>
          <div className="bg-emerald-50 p-5 rounded-lg border border-emerald-100">
            <div className="text-sm text-emerald-800 flex items-center mb-1">
              Occupied Units <InfoTooltip term="Occupancy" />
            </div>
            <p className="text-3xl font-bold text-emerald-700">{occupiedUnits}</p>
          </div>
          <div className="bg-amber-50 p-5 rounded-lg border border-amber-100">
            <div className="text-sm text-amber-800 flex items-center mb-1">
              Occupancy Rate <InfoTooltip term="Occupancy" />
            </div>
            <p className="text-3xl font-bold text-amber-700">{formatPercent(occupancyRate)}</p>
          </div>
          <div className="bg-indigo-50 p-5 rounded-lg border border-indigo-100">
            <div className="text-sm text-indigo-800 flex items-center mb-1">
              Avg Monthly Rent <InfoTooltip term="Avg Monthly Rent" />
            </div>
            <p className="text-2xl font-bold text-indigo-700">
              {formatCurrency(
                analysis.rent_roll_summary?.total_monthly_rent
                  ? analysis.rent_roll_summary.total_monthly_rent / totalUnits
                  : 0
              )}
            </p>
          </div>
        </div>
        
        {/* Unit Mix Table */}
        {analysis.unit_mix_summary && analysis.unit_mix_summary.length > 0 && (
            <div className="mt-8 overflow-x-auto">
                <h4 className="text-sm font-bold text-slate-900 uppercase tracking-wide mb-4">Unit Mix Detail</h4>
                <table className="w-full text-sm text-left">
                    <thead className="text-xs text-slate-500 uppercase bg-slate-50">
                        <tr>
                            <th className="px-4 py-3 rounded-l-lg">Unit Type</th>
                            <th className="px-4 py-3">Count</th>
                            <th className="px-4 py-3">Avg Current Rent</th>
                            <th className="px-4 py-3 rounded-r-lg">Market Rent</th>
                        </tr>
                    </thead>
                    <tbody>
                        {analysis.unit_mix_summary.map((unit, idx) => (
                            <tr key={idx} className="border-b border-slate-50 hover:bg-slate-50/50">
                                <td className="px-4 py-3 font-medium text-slate-900">{unit.unit_type}</td>
                                <td className="px-4 py-3 text-slate-600">{unit.count}</td>
                                <td className="px-4 py-3 text-slate-600">{formatCurrency(unit.avg_rent)}</td>
                                <td className="px-4 py-3 text-slate-600">{formatCurrency(unit.market_rent)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        )}
      </div>
    </div>
  );
}
