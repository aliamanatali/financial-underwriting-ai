"use client";

import React, { useState, useEffect } from "react";
import { UnderwritingAnalysis, ExplainabilityMetadata, DealParameters } from "@/lib/types";
import SensitivityAnalysisWidget from "./SensitivityAnalysisWidget";
import RentRollWidget from "./RentRollWidget";
import MarkdownRenderer from "./MarkdownRenderer";

const LogicErrorItem = ({ errorMsg, analysis }: { errorMsg: string, analysis: any }) => {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);

  const fetchExplanation = async () => {
    if (explanation || loading) return;
    setLoading(true);
    try {
      const contextData = {
        gross_potential_rent: analysis?.rent_roll_summary?.total_annual_rent,
        net_operating_income: analysis?.pro_forma_noi,
        operating_expenses: analysis?.pro_forma_expenses,
        occupancy_rate: analysis?.rent_roll_summary?.occupancy_rate,
        purchase_price: analysis?.property_meta?.purchase_price,
        cap_rate: analysis?.cap_rate
      };

      const prompt = `Please analyze this specific data logic error from our commercial real estate underwriting system: "${errorMsg}".

Here is the current relevant data for this property:
${JSON.stringify(contextData, null, 2)}

Based on this specific data:
1. Provide insights into exactly which numbers are causing this error and why.
2. Suggest a concrete fix or adjustment to the inputs to resolve this error.
Explain in a concise, professional manner. IMPORTANT: Do NOT include conversational filler, greetings, or introductory statements. Start directly with the analysis.`;
      
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, messages: [] }),
      });
      
      const data = await response.json();
      if (data.response) {
        setExplanation(data.response);
      } else {
        setExplanation("Failed to get explanation from Gemini.");
      }
    } catch (e) {
      setExplanation("Error fetching explanation.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExplanation();
  }, [errorMsg, analysis]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <li className="mb-2 list-none">
      <div
        className="cursor-pointer hover:text-rose-900 flex items-start gap-1 font-medium transition-colors"
        onClick={() => {
          setExpanded(!expanded);
        }}
      >
        <span className="mt-0.5 shrink-0 text-rose-500">
          <svg className={`w-3.5 h-3.5 transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
          </svg>
        </span>
        <span className="flex-1">{errorMsg}</span>
      </div>
      
      {expanded && (
        <div className="mt-2 ml-4 mb-3 p-3 bg-white/80 border border-rose-200/60 rounded-lg text-rose-900/90 text-xs leading-relaxed shadow-sm">
          {loading ? (
             <div className="flex items-center gap-2 text-rose-600 font-medium">
               <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24">
                 <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                 <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
               </svg>
               Analyzing logic error ...
             </div>
          ) : (
            <div className="prose prose-sm prose-rose max-w-none text-[11px] prose-p:my-1 prose-headings:my-2">
              <MarkdownRenderer content={explanation || ""} />
            </div>
          )}
        </div>
      )}
    </li>
  );
};
import CombinedRentRollTable from "./CombinedRentRollTable";
import ExpenseRevenueList from "./ExpenseRevenueList";
import WidgetTooltip from "./WidgetTooltip";

interface UnderwritingDashboardProps {
  analysis: UnderwritingAnalysis;
  onReanalyze?: (params: DealParameters) => Promise<void> | void;
  initialRentRollTab?: "details" | "omExport" | "unitBreakdown" | "unitBreakdownStabilized";
  initialRentRollEditMode?: boolean;
  validationTrigger?: number;
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
      <span className="w-3.5 h-3.5 rounded-full border border-slate-400 text-slate-400 flex items-center justify-center text-[9px] font-serif italic cursor-help hover:border-[#FF5E00] hover:text-[#FF5E00] hover:bg-#FFF5F0 transition-colors">
        i
      </span>
      <span className="absolute z-[60] bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover/info:block w-48 p-2 bg-slate-900 text-white text-xs rounded shadow-lg text-center font-normal leading-snug pointer-events-none">
        {definition}
        <span className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-slate-900" />
      </span>
    </span>
  );
}

function SourceTooltip({ source }: { source?: string }) {
  if (!source) return null;

  return (
    <div className="absolute z-50 bottom-full right-0 mb-2 hidden group-hover/source:block w-64 p-2 bg-slate-900 text-white text-xs rounded shadow-lg text-left font-normal leading-snug pointer-events-none">
      <span className="font-semibold text-slate-300">Source:</span> {source}
      <div className="absolute top-full right-4 -mt-1 border-4 border-transparent border-t-slate-900" />
    </div>
  );
}

function ExplanationTooltip({ metadata, analysis, selectedPeriod = "T12" }: { metadata?: ExplainabilityMetadata, analysis: UnderwritingAnalysis, selectedPeriod?: string }) {
  if (!metadata) return null;

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
    }).format(value);
  };

  const periodMultiplier = selectedPeriod === "T3" ? 0.25 :
                           selectedPeriod === "T6" ? 0.5 :
                           selectedPeriod === "T9" ? 0.75 : 1.0;

  const isHistorical = metadata.metric.toLowerCase().includes("historical") ||
                       metadata.metric.toLowerCase().includes("t12");

  // Update strings runtime
  const forwardPeriod = selectedPeriod.replace("T", "F");
  const displayMetric = metadata.metric.replace("T12", selectedPeriod).replace("F12", forwardPeriod).replace("Historical ", "");
  const displaySourceDoc = metadata.source.document.replace("T12", selectedPeriod).replace("F12", forwardPeriod);
  const displayFieldsUsed = metadata.source.fields_used.map(f => f.replace("T12", selectedPeriod).replace("F12", forwardPeriod));

  return (
    <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover/explanation:block w-96 p-4 bg-white border border-slate-200 rounded-lg shadow-xl text-left text-sm font-normal normal-case">
      <div className="flex justify-between items-start mb-2 border-b pb-2">
        <h4 className="font-bold text-slate-900">{displayMetric}</h4>
        <span className={`px-2 py-0.5 text-xs rounded-full ${
          metadata.classification.includes("Assumptions")
            ? "bg-amber-100 text-amber-800"
            : "bg-[#FFE5D9] text-blue-800"
        }`}>
          {metadata.classification}
        </span>
      </div>
      
      <div className="space-y-3">
        <div>
          <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider">Source</p>
          <p className="text-slate-700">
            <span className="font-medium">{displaySourceDoc}</span>
            {displayFieldsUsed.length > 0 && (
              <span className="text-slate-500"> ({displayFieldsUsed.join(", ")})</span>
            )}
          </p>
        </div>

        <div>
          <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider">Calculation</p>
          <code className="block bg-slate-50 p-1.5 rounded text-xs text-slate-800 font-mono mt-1 border">
            {metadata.calculation.formula.replace("12", selectedPeriod.replace("T", "").replace("F", ""))}
          </code>
          <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            {Object.entries(metadata.calculation.inputs).map(([key, val]) => {
              // Only scale dollar amounts, not unit counts or percentages
              const isUnitCount = key.toLowerCase().includes("units") || key.toLowerCase().includes("count");
              const isPercentage = key.toLowerCase().includes("%") || key.toLowerCase().includes("rate") || key.toLowerCase().includes("ratio");
              
              const shouldScale = typeof val === 'number' && !isUnitCount && !isPercentage;
              const displayVal = shouldScale ? val * periodMultiplier : val;
              const displayKey = key.replace("T12", selectedPeriod).replace("F12", forwardPeriod);
              return (
                <div key={key} className="flex justify-between">
                  <span className="text-slate-500">{displayKey}:</span>
                  <span className="font-medium text-slate-900">
                    {typeof displayVal === 'number'
                      ? (isUnitCount ? displayVal.toLocaleString() : (isPercentage ? (displayVal < 1 ? (displayVal * 100).toFixed(1) + "%" : displayVal + "%") : formatCurrency(displayVal)))
                      : displayVal}
                  </span>
                </div>
              );
            })}
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
  initialRentRollTab,
  initialRentRollEditMode,
  validationTrigger,
}: UnderwritingDashboardProps) {
  const [isEditingPropertyDetails, setIsEditingPropertyDetails] = useState(false);
  const [isCommentaryExpanded, setIsCommentaryExpanded] = useState(true);
  const [selectedPeriod, setSelectedPeriod] = useState<string>("T12");
  const [editParams, setEditParams] = useState<DealParameters>({
    growth_rate: 0.03,
    exit_cap_rate: 0.06,
    vacancy_rate: 0.05,
    ...(analysis.deal_parameters || {}),
    // Use the backend-calculated loan_amount (from LTV) when no user override exists
    loan_amount: analysis.deal_parameters?.loan_amount ?? analysis.loan_amount ?? undefined,
  });
  const [editPropertyDetails, setEditPropertyDetails] = useState({
    year_built: analysis.property_meta?.year_built || 0,
    total_units: analysis.property_meta?.total_units || 0,
    purchase_price: analysis.property_meta?.purchase_price || 0,
    current_loan_balance: analysis.property_meta?.current_loan_balance || 0,
    building_size: analysis.property_meta?.building_size || 0,
  });
  const [isSavingProperty, setIsSavingProperty] = useState(false);

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

  const [isSavingParams, setIsSavingParams] = useState(false);
  const handleSave = async () => {
    console.log("handleSave called with params:", editParams);
    console.log("onReanalyze function exists:", !!onReanalyze);
    if (onReanalyze) {
      console.log("Calling onReanalyze with params:", editParams);
      setIsSavingParams(true);
      try {
        await onReanalyze(editParams);
      } finally {
        setIsSavingParams(false);
      }
    } else {
      console.error("onReanalyze callback is not defined!");
    }
  };

  const handleCancel = () => {
    setEditParams(analysis.deal_parameters || editParams);
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

  // Get data for selected historical period
  const periodMultiplier = selectedPeriod === "T3" ? 0.25 :
                           selectedPeriod === "T6" ? 0.5 :
                           selectedPeriod === "T9" ? 0.75 : 1.0;

  const selectedPeriodData = analysis.historical_periods?.find(p => p.period === selectedPeriod) || {
    period: selectedPeriod,
    total_expenses: (analysis.historical_total_expenses || 0) * periodMultiplier,
    noi: (analysis.historical_noi || 0) * periodMultiplier,
    cap_rate: analysis.historical_cap_rate || 0
  };

  const historicalNOI = selectedPeriodData.noi;
  const historicalTotalExpenses = selectedPeriodData.total_expenses;
  const historicalCapRate = selectedPeriodData.cap_rate;
  
  const proFormaNOI = analysis.pro_forma_noi || 0;
  
  // Adjusted Pro Forma values for the selected period
  const adjustedProFormaNOI = proFormaNOI * periodMultiplier;
  const adjustedProFormaExpenses = (analysis.pro_forma_expenses || 0) * periodMultiplier;
  const adjustedProFormaGPR = (analysis.rent_roll.reduce((sum, item) => sum + item.market_rent * 12, 0)) * periodMultiplier;
  
  const noiChange = adjustedProFormaNOI - historicalNOI;
  const noiChangePercent = historicalNOI > 0 ? (noiChange / historicalNOI) * 100 : 0;

  const proFormaCapRate = analysis.cap_rate || 0;
  const capRateChange = proFormaCapRate - historicalCapRate;

  const occupancyRate = analysis.rent_roll_summary?.occupancy_rate || 0;
  const totalUnits = analysis.property_meta?.total_units || 0;
  const occupiedUnits = analysis.rent_roll_summary?.occupied_units || 0;
  const purchasePrice = analysis.property_meta.purchase_price || 0;
  
  // Calculate price per unit - use edited values if in edit mode, otherwise use analysis values
  const displayTotalUnits = isEditingPropertyDetails ? editPropertyDetails.total_units : totalUnits;
  const displayPurchasePrice = isEditingPropertyDetails ? editPropertyDetails.purchase_price : purchasePrice;
  const pricePerUnit = displayTotalUnits > 0 ? displayPurchasePrice / displayTotalUnits : 0;

  const handlePropertyDetailChange = (key: string, value: string) => {
    const numValue = parseFloat(value) || 0;
    setEditPropertyDetails(prev => ({
      ...prev,
      [key]: numValue
    }));
  };

  const handleSavePropertyDetails = async () => {
    console.log("Saving property details and triggering re-analysis:", editPropertyDetails);
    setIsSavingProperty(true);
    
    const API_BASE_URL = process.env.NEXT_PUBLIC_FINANCIAL_API_URL;
    const packageId = analysis.document_id;
    
    try {
      // First, update manual overrides in the backend
      const response = await fetch(`${API_BASE_URL}/api/v1/multi-document/packages/${packageId}/manual-overrides`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          year_built: editPropertyDetails.year_built,
          total_units: editPropertyDetails.total_units,
          purchase_price: editPropertyDetails.purchase_price,
          current_loan_balance: editPropertyDetails.current_loan_balance,
          building_size: editPropertyDetails.building_size,
        }),
      });
      
      if (response.ok) {
        console.log("Property details updated successfully in backend");
        
        // Now trigger re-analysis with current deal parameters
        if (onReanalyze) {
          console.log("Triggering re-analysis with updated property details");
          onReanalyze(editParams);
        }
      } else {
        console.error("Failed to update property details in backend");
      }
    } catch (error) {
      console.error("Error updating property details:", error);
    } finally {
      setIsSavingProperty(false);
      setIsEditingPropertyDetails(false);
    }
  };

  const handleCancelPropertyDetails = () => {
    setEditPropertyDetails({
      year_built: analysis.property_meta?.year_built || 0,
      total_units: analysis.property_meta?.total_units || 0,
      purchase_price: analysis.property_meta?.purchase_price || 0,
      current_loan_balance: analysis.property_meta?.current_loan_balance || 0,
      building_size: analysis.property_meta?.building_size || 0,
    });
    setIsEditingPropertyDetails(false);
  };

  const checkMissingValues = () => {
    const missing = [];
    if (!analysis.property_meta?.purchase_price) missing.push("Purchase Price");
    if (!analysis.property_meta?.total_units) missing.push("Total Units");
    if (!analysis.rent_roll_summary?.total_annual_rent) missing.push("Gross Potential Rent");
    if (!analysis.historical_total_expenses && (!analysis.historical_expenses || analysis.historical_expenses.length === 0)) missing.push("Operating Expenses");
    return missing;
  };

  const checkLogicErrors = () => {
    const errors = [];
    
    // Logic Error: NOI should not be greater than Gross Potential Rent
    if (analysis.pro_forma_noi && analysis.rent_roll_summary?.total_annual_rent && analysis.pro_forma_noi > analysis.rent_roll_summary.total_annual_rent) {
      errors.push("Net Operating Income (NOI) cannot exceed Gross Potential Rent.");
    }

    // Logic Error: Expenses should be positive
    if (analysis.pro_forma_expenses && analysis.pro_forma_expenses < 0) {
      errors.push("Operating Expenses cannot be negative.");
    }

    // Logic Error: Occupancy cannot exceed 100% (with small buffer for floating point)
    if (analysis.rent_roll_summary?.occupancy_rate && analysis.rent_roll_summary.occupancy_rate > 1.01) {
      errors.push("Occupancy Rate cannot exceed 100%.");
    }

    // Logic Error: Purchase Price must be positive
    if (analysis.property_meta?.purchase_price && analysis.property_meta.purchase_price <= 0) {
      errors.push("Purchase Price must be greater than zero.");
    }
    
    // Logic Error: Cap Rate shouldn't be negative (unless deep distress, but usually indicates data error here)
    if (analysis.cap_rate && analysis.cap_rate < 0) {
      errors.push("Cap Rate is negative, indicating potential data error.");
    }

    return errors;
  };

  const missingValues = checkMissingValues();
  const logicErrors = checkLogicErrors();
  const hasCriticalIssues = missingValues.length > 0 || logicErrors.length > 0;

  return (
    <>
    <div className="space-y-6 font-sans">
      {/* Critical Issues Banner (Missing Values or Logic Errors) */}
      {hasCriticalIssues && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 flex items-start gap-3 shadow-sm">
          <div className="p-1.5 bg-rose-100 rounded-full text-rose-600 shrink-0 mt-0.5">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" x2="12" y1="8" y2="12"></line>
              <line x1="12" x2="12.01" y1="16" y2="16"></line>
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-bold text-rose-800">Report Inaccurate: Critical Data Issues</h3>
            
            {missingValues.length > 0 && (
              <div className="mt-1">
                 <p className="text-xs text-rose-700 font-semibold mb-0.5">Missing Crucial Values:</p>
                 <ul className="list-disc list-inside text-xs text-rose-700 ml-1">
                   {missingValues.map(val => <li key={val}>{val}</li>)}
                 </ul>
              </div>
            )}

            {logicErrors.length > 0 && (
              <div className="mt-2">
                 <p className="text-xs text-rose-700 font-semibold mb-1 flex items-center gap-1.5">
                   <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                     <circle cx="12" cy="12" r="10"></circle>
                     <line x1="12" y1="8" x2="12" y2="12"></line>
                     <line x1="12" y1="16" x2="12.01" y2="16"></line>
                   </svg>
                   Data Logic Errors (Click to analyze):
                 </p>
                 <ul className="text-xs text-rose-700 ml-1">
                   {logicErrors.map(err => <LogicErrorItem key={err} errorMsg={err} analysis={analysis} />)}
                 </ul>
              </div>
            )}

         
          </div>
        </div>
      )}

      {/* Quick Stats Row */}
      <div className="bg-white rounded-xl border border-neutral-200 shadow-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-neutral-900">Property Details</h3>
          {!isEditingPropertyDetails ? (
            <button
              onClick={() => setIsEditingPropertyDetails(true)}
              className="text-[10px] font-medium text-neutral-500 hover:text-neutral-900 border border-neutral-200 px-2 py-1 rounded bg-neutral-50 hover:bg-white transition-all"
            >
              Edit Details
            </button>
          ) : (
            <div className="flex gap-2">
              <button
                onClick={handleCancelPropertyDetails}
                className="text-[10px] font-medium text-neutral-500 hover:text-neutral-900 border border-neutral-200 px-2 py-1 rounded bg-neutral-50 hover:bg-white transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleSavePropertyDetails}
                disabled={isSavingProperty}
                className="text-[10px] font-medium bg-neutral-900 text-white px-2 py-1 rounded hover:bg-neutral-800 transition-all disabled:opacity-50 flex items-center gap-1"
              >
                {isSavingProperty ? (
                    <>
                        <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Saving...
                    </>
                ) : "Save Changes"}
              </button>
            </div>
          )}
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-px bg-neutral-200 rounded-lg overflow-hidden border border-neutral-200">
          <div className="bg-white p-4 flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wide text-neutral-500 font-medium">Year Built</span>
            {isEditingPropertyDetails ? (
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                className="text-sm font-semibold text-neutral-900 bg-white border border-neutral-300 rounded px-2 py-1 focus:outline-none focus:border-neutral-900"
                value={editPropertyDetails.year_built}
                onChange={(e) => handlePropertyDetailChange('year_built', e.target.value)}
              />
            ) : (
              <span className="text-sm font-semibold text-neutral-900">{analysis.property_meta.year_built || "-"}</span>
            )}
          </div>
          <div className={`bg-white p-4 flex flex-col gap-1 ${(!totalUnits && missingValues.includes("Total Units")) ? "ring-2 ring-rose-200 bg-rose-50" : ""}`}>
            <span className={`text-[10px] uppercase tracking-wide font-medium ${(!totalUnits && missingValues.includes("Total Units")) ? "text-rose-500" : "text-neutral-500"}`}>
              Total Units {(!totalUnits && missingValues.includes("Total Units")) && "(Missing)"}
            </span>
            {isEditingPropertyDetails ? (
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                className="text-sm font-semibold text-neutral-900 bg-white border border-neutral-300 rounded px-2 py-1 focus:outline-none focus:border-neutral-900"
                value={editPropertyDetails.total_units}
                onChange={(e) => handlePropertyDetailChange('total_units', e.target.value)}
              />
            ) : (
              <span className="text-sm font-semibold text-neutral-900">{totalUnits || "-"}</span>
            )}
          </div>
          <div className={`bg-white p-4 flex flex-col gap-1 ${(occupancyRate > 1.01) ? "ring-2 ring-rose-200 bg-rose-50" : ""}`}>
            <span className={`text-[10px] uppercase tracking-wide font-medium ${(occupancyRate > 1.01) ? "text-rose-500" : "text-neutral-500"}`}>
              Occupancy {(occupancyRate > 1.01) && "(Invalid)"}
            </span>
            <span className="text-sm font-semibold text-neutral-900">{formatPercent(occupancyRate)}</span>
          </div>
          <div className={`bg-white p-4 flex flex-col gap-1 ${(!purchasePrice && missingValues.includes("Purchase Price")) || purchasePrice <= 0 ? "ring-2 ring-rose-200 bg-rose-50" : ""}`}>
            <span className={`text-[10px] uppercase tracking-wide font-medium ${(!purchasePrice && missingValues.includes("Purchase Price")) || purchasePrice <= 0 ? "text-rose-500" : "text-neutral-500"}`}>
              Purchase Price {(!purchasePrice && missingValues.includes("Purchase Price")) ? "(Missing)" : purchasePrice <= 0 ? "(Invalid)" : ""}
            </span>
            {isEditingPropertyDetails ? (
              <input
                type="text"
                inputMode="decimal"
                pattern="[0-9]*"
                className="text-sm font-semibold text-neutral-900 bg-white border border-neutral-300 rounded px-2 py-1 focus:outline-none focus:border-neutral-900"
                value={editPropertyDetails.purchase_price}
                onChange={(e) => handlePropertyDetailChange('purchase_price', e.target.value)}
              />
            ) : (
              <span className="text-sm font-semibold text-neutral-900">{formatCurrency(purchasePrice)}</span>
            )}
          </div>
          <div className="bg-white p-4 flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wide text-neutral-500 font-medium">Price Per Unit</span>
            <span className="text-sm font-semibold text-neutral-900">{formatCurrency(pricePerUnit)}</span>
          </div>
          <div className="bg-white p-4 flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wide text-neutral-500 font-medium flex items-center">
              Gross Sq Ft
              <WidgetTooltip
                title="Gross Square Footage (GSF)"
                description="Total building area extracted from the Offering Memorandum or property overview."
                formulas={[{ label: "Source", formula: "Extracted from document headers (PropertyMeta)" }]}
                className="text-neutral-400 ml-1 hover:text-neutral-700"
              />
            </span>
            {isEditingPropertyDetails ? (
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                className="text-sm font-semibold text-neutral-900 bg-white border border-neutral-300 rounded px-2 py-1 focus:outline-none focus:border-neutral-900"
                value={editPropertyDetails.building_size || ''}
                onChange={(e) => handlePropertyDetailChange('building_size', e.target.value)}
              />
            ) : (
              <span className="text-sm font-semibold text-neutral-900">
                {analysis.property_meta?.building_size ? analysis.property_meta.building_size.toLocaleString() : "-"}
              </span>
            )}
          </div>
          <div className="bg-white p-4 flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wide text-neutral-500 font-medium flex items-center">
              Net Rentable Sq Ft
              <WidgetTooltip
                title="Net Rentable Square Footage (NRSF)"
                description="Total livable or leasable space, calculated directly from the rent roll."
                formulas={[{ label: "Calculation", formula: "Sum of unit_size for all extracted Rent Roll units" }]}
                className="text-neutral-400 ml-1 hover:text-neutral-700"
              />
            </span>
            <span className="text-sm font-semibold text-neutral-900">
              {(analysis.rent_roll || []).reduce((acc, item) => acc + (Number(item.unit_size) || 0), 0).toLocaleString()}
            </span>
          </div>
        </div>
      </div>

      {/* Rent Roll Section - Editable */}
      <RentRollWidget
        rentRoll={analysis.rent_roll || []}
        summary={analysis.rent_roll_summary}
        packageId={analysis.document_id}
        studentHousingConfig={analysis.student_housing_config}
        onUpdate={() => onReanalyze && onReanalyze(editParams)}
        initialTab={initialRentRollTab}
        initialEditMode={initialRentRollEditMode}
        validationTrigger={validationTrigger}
        fullAnalysis={analysis} // Pass full analysis for export purposes
      />

      {/* Combined Rent Roll Table (Read-Only Aggregated View) - HIDDEN
      <CombinedRentRollTable
        rentRoll={(analysis.rent_roll || []).filter(item => {
          const isNonOMFlow = !analysis.om_proforma || analysis.om_proforma.length === 0;
          if (!isNonOMFlow) return true;
          const sizeStr = String(item.unit_size).toLowerCase().trim();
          return !(
            !item.unit_size ||
            item.unit_size === 0 ||
            sizeStr === "-" ||
            sizeStr === "unknown" ||
            sizeStr === "unkown"
          );
        })}
        formatCurrency={formatCurrency}
      />
      */}

      {/* Expense & Revenue List (Historical Financials) - HIDDEN
      <ExpenseRevenueList
        expenses={analysis.historical_expenses || []}
        formatCurrency={formatCurrency}
      />
      */}

      {/* AI Underwriting Section */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* AI Conclusion Card */}
        <div className="lg:col-span-8 bg-white rounded-xl border border-neutral-200 shadow-sm p-6 relative overflow-hidden min-h-[300px]">
          
          {/* Verdict Suspended Overlay */}
          {hasCriticalIssues && (
            <div className="absolute inset-0 bg-white/90 backdrop-blur-sm z-30 flex flex-col items-center justify-center text-center p-6">
              <div className="w-12 h-12 bg-amber-100 rounded-full flex items-center justify-center text-amber-600 mb-3">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                  <line x1="12" y1="9" x2="12" y2="13"></line>
                  <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
              </div>
              <h3 className="text-lg font-bold text-neutral-900 mb-1">Verdict Suspended</h3>
              <p className="text-sm text-neutral-600 max-w-xs mb-6">
                We cannot determine if this deal passes investment criteria until critical data issues are resolved.
              </p>
            </div>
          )}

          <div className={hasCriticalIssues ? "opacity-20 blur-[1px] pointer-events-none select-none" : ""}>
            <div className="flex items-start justify-between mb-6">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-500">
                  <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275Z"></path>
                </svg>
                <h2 className="text-sm font-semibold text-neutral-900 uppercase tracking-wide">AI Underwriting Conclusion</h2>
              </div>
              <p className="text-xs text-neutral-500">Analysis based on Offering Memorandum and Rent Roll.</p>
            </div>
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border ${getStatusDisplay(analysis.pass_fail_status).color}`}>
              <div className={`w-1.5 h-1.5 rounded-full ${analysis.pass_fail_status === 'PASS' ? 'bg-emerald-500' : 'bg-rose-500'}`}></div>
              <span className="text-[11px] font-semibold uppercase tracking-wide">Qualification Status: {getStatusDisplay(analysis.pass_fail_status).text}</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Checklist */}
            <div className="space-y-4">
              <h3 className="text-xs font-semibold text-neutral-900 pb-2 border-b border-neutral-100">Investment Criteria Checklist</h3>
              <div className="space-y-3">
                {analysis.conclusion?.investment_checklist && (
                  <>
                    <div className="flex items-start justify-between gap-4">
                      <span className="text-xs text-neutral-600 shrink-0">Is it within 6 blocks of campus?</span>
                      <div className="relative group/source flex-1 text-right">
                        <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-neutral-100 text-neutral-600 inline-block text-left cursor-help">{analysis.conclusion.investment_checklist.near_campus}</span>
                        <SourceTooltip source={analysis.conclusion.investment_checklist.near_campus_source} />
                      </div>
                    </div>
                    <div className="flex items-start justify-between gap-4">
                      <span className="text-xs text-neutral-600">Are existing rents below market?</span>
                      <div className="relative group/source inline-block">
                        <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-rose-50 text-rose-700 whitespace-nowrap cursor-help">{analysis.conclusion.investment_checklist.rents_below_market}</span>
                        <SourceTooltip source={analysis.conclusion.investment_checklist.rents_below_market_source} />
                      </div>
                    </div>
                    <div className="flex items-start justify-between gap-4">
                      <span className="text-xs text-neutral-600">Is it poorly run/mismanaged?</span>
                      <div className="relative group/source inline-block">
                        <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-700 whitespace-nowrap cursor-help">{analysis.conclusion.investment_checklist.is_mismanaged}</span>
                        <SourceTooltip source={analysis.conclusion.investment_checklist.is_mismanaged_source} />
                      </div>
                    </div>
                  </>
                )}
                {analysis.gating_reasons.length > 0 && analysis.gating_reasons.map((reason, idx) => (
                  <div key={idx} className="flex items-start justify-between gap-4">
                    <span className="text-xs text-neutral-600">{reason}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-rose-50 text-rose-700 whitespace-nowrap">Issue</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Narrative */}
            <div className="space-y-4">
              <h3 className="text-xs font-semibold text-neutral-900 pb-2 border-b border-neutral-100">Business Plan & Risks</h3>
              <div className="space-y-3">
                {analysis.conclusion?.investment_checklist?.business_plan && (
                  <div className="group/source relative">
                    <span className="text-[10px] text-neutral-400 uppercase tracking-wide font-medium flex items-center gap-1 w-fit">
                        Strategy
                    </span>
                    <p className="text-xs text-neutral-700 mt-1 leading-relaxed cursor-help inline-block">
                      {analysis.conclusion.investment_checklist.business_plan}
                    </p>
                    <SourceTooltip source={analysis.conclusion.investment_checklist.business_plan_source} />
                  </div>
                )}
                {analysis.conclusion?.investment_checklist?.primary_risks && (
                  <div className="group/source relative">
                    <span className="text-[10px] text-neutral-400 uppercase tracking-wide font-medium flex items-center gap-1 w-fit">
                        Primary Risks
                        <SourceTooltip source={analysis.conclusion.investment_checklist.primary_risks_source} />
                    </span>
                    <div className="flex gap-2 mt-1 flex-wrap">
                      <span className="inline-flex items-center gap-1 px-2 py-1 rounded border border-orange-200 bg-orange-50 text-orange-700 text-[10px] font-medium">
                        <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path>
                          <line x1="12" x2="12" y1="9" y2="13"></line>
                          <line x1="12" x2="12.01" y1="17" y2="17"></line>
                        </svg>
                        {analysis.conclusion.investment_checklist.primary_risks}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>
            </div>
          </div>
        </div>

        {/* Investment Returns (Key Metrics) */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          <div className="bg-neutral-900 rounded-xl shadow-lg p-6 text-white flex flex-col justify-between h-full relative group">
            <div className="absolute inset-0 bg-neutral-900 overflow-hidden rounded-xl">
              <div className="absolute -top-24 -right-24 w-80 h-80 bg-orange-500/20 rounded-full blur-3xl pointer-events-none"></div>
              <div className="absolute -bottom-12 -left-12 w-40 h-40 bg-white/5 rounded-full blur-2xl pointer-events-none"></div>
              <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff08_1px,transparent_1px),linear-gradient(to_bottom,#ffffff08_1px,transparent_1px)] bg-[size:24px_24px]"></div>
              <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-neutral-900/50"></div>
            </div>

            <div className="relative z-10">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-sm font-medium text-white flex items-center">
                  Investment Returns (5-Year)
                  <WidgetTooltip
                    title="Investment Returns"
                    description="Projected returns over a 5-year hold period based on the Deal Parameters."
                    formulas={[
                      { label: "IRR", formula: "Internal Rate of Return on cash flows & sale" },
                      { label: "MOIC", formula: "(Total Cash Distributions + Net Sale Proceeds) / Initial Equity" },
                      { label: "Cash-on-Cash", formula: "Annual Pre-Tax Cash Flow / Initial Equity Invested" }
                    ]}
                    className="text-white"
                  />
                </h3>
                <span className="p-1.5 rounded bg-white/10 text-neutral-400">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline>
                    <polyline points="16 7 22 7 22 13"></polyline>
                  </svg>
                </span>
              </div>

              <div className="grid grid-cols-2 gap-y-6">
                <div>
                  <p className="text-xs text-white/70 mb-1">IRR (Levered)</p>
                  <div className={`text-2xl font-medium tracking-tight ${(analysis.irr || 0) < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                    {formatPercent(analysis.irr || 0)}
                  </div>
                </div>
                <div>
                  <p className="text-xs text-white/70 mb-1">MOIC</p>
                  <div className="text-2xl font-medium tracking-tight text-white">{(analysis.moic || 0).toFixed(2)}x</div>
                </div>
                <div className="col-span-2 pt-4 border-t border-white/10">
                  <p className="text-xs text-white/70 mb-1">Cash-on-Cash</p>
                  <div className={`text-2xl font-medium tracking-tight ${(analysis.cash_on_cash_return || 0) < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                    {formatPercent(analysis.cash_on_cash_return || 0)}
                  </div>
                  <p className="text-[10px] text-white/70 mt-1">Avg. Annual Cash Yield</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>


      {/* Financial Analysis Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: Parameters */}
        <div className="lg:col-span-4 bg-white rounded-xl border border-neutral-200 shadow-sm p-6 h-full">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-sm font-semibold text-neutral-900 flex items-center">
              Deal Parameters
              <WidgetTooltip
                title="Deal Parameters"
                description="Adjustable assumptions used to calculate financial projections and returns."
                formulas={[
                  { label: "Rent Growth", formula: "Annual % increase in market rent" },
                  { label: "Vacancy Rate", formula: "% of GPR lost to vacancy" },
                  { label: "Exit Cap", formula: "Cap rate applied to Year 6 NOI for sale price" },
                  { label: "Loan Amount", formula: "Total debt principal (affects equity & DSCR)" }
                ]}
              />
            </h3>
            <div className="flex gap-2">
              <button
                onClick={handleCancel}
                className="text-[10px] font-medium text-neutral-500 hover:text-neutral-900 border border-neutral-200 px-2 py-1 rounded bg-neutral-50 hover:bg-white transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={isSavingParams}
                className="text-[10px] font-medium bg-neutral-900 text-white px-2 py-1 rounded hover:bg-neutral-800 transition-all disabled:opacity-50 flex items-center gap-1"
              >
                {isSavingParams ? (
                    <>
                        <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Saving...
                    </>
                ) : "Save & Regenerate"}
              </button>
            </div>
          </div>
          
          <div className="space-y-6">
            {/* Rent Growth Rate Panel */}
            <div className="group">
              <div className="flex justify-between items-baseline mb-2">
                <label className="text-xs font-medium text-neutral-600">Rent Growth Rate</label>
                <span className="text-sm font-semibold text-neutral-900">{(editParams.growth_rate * 100).toFixed(1)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="10"
                step="0.1"
                value={editParams.growth_rate * 100}
                onChange={(e) => handleParamChange('growth_rate', e.target.value)}
                className="w-full h-1.5 bg-neutral-100 rounded-full appearance-none cursor-pointer slider-thumb"
                style={{
                  background: `linear-gradient(to right, #171717 0%, #171717 ${(editParams.growth_rate * 100) * 10}%, #f5f5f5 ${(editParams.growth_rate * 100) * 10}%, #f5f5f5 100%)`
                }}
              />
              <div className="flex justify-between text-[9px] text-neutral-400 mt-1.5">
                <span>0%</span>
                <span>10%</span>
              </div>
            </div>

            {/* Vacancy Rate Panel */}
            <div className="group">
              <div className="flex justify-between items-baseline mb-2">
                <label className="text-xs font-medium text-neutral-600">Vacancy Rate</label>
                <span className="text-sm font-semibold text-neutral-900">{(editParams.vacancy_rate * 100).toFixed(1)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="20"
                step="0.1"
                value={editParams.vacancy_rate * 100}
                onChange={(e) => handleParamChange('vacancy_rate', e.target.value)}
                className="w-full h-1.5 bg-neutral-100 rounded-full appearance-none cursor-pointer slider-thumb"
                style={{
                  background: `linear-gradient(to right, #171717 0%, #171717 ${(editParams.vacancy_rate * 100) * 5}%, #f5f5f5 ${(editParams.vacancy_rate * 100) * 5}%, #f5f5f5 100%)`
                }}
              />
              <div className="flex justify-between text-[9px] text-neutral-400 mt-1.5">
                <span>0%</span>
                <span>20%</span>
              </div>
            </div>

            {/* Exit Cap Rate Panel */}
            <div className="group">
              <div className="flex justify-between items-baseline mb-2">
                <label className="text-xs font-medium text-neutral-600">Exit Cap Rate</label>
                <span className="text-sm font-semibold text-neutral-900">{(editParams.exit_cap_rate * 100).toFixed(1)}%</span>
              </div>
              <input
                type="range"
                min="3"
                max="10"
                step="0.1"
                value={editParams.exit_cap_rate * 100}
                onChange={(e) => handleParamChange('exit_cap_rate', e.target.value)}
                className="w-full h-1.5 bg-neutral-100 rounded-full appearance-none cursor-pointer slider-thumb"
                style={{
                  background: `linear-gradient(to right, #171717 0%, #171717 ${((editParams.exit_cap_rate * 100) - 3) * 14.28}%, #f5f5f5 ${((editParams.exit_cap_rate * 100) - 3) * 14.28}%, #f5f5f5 100%)`
                }}
              />
              <div className="flex justify-between text-[9px] text-neutral-400 mt-1.5">
                <span>3%</span>
                <span>10%</span>
              </div>
            </div>

            {/* Loan Amount Panel */}
            <div className="group pt-2 border-t border-neutral-100">
              <div className="flex justify-between items-baseline mb-2">
                <label className="text-xs font-medium text-neutral-600">Loan Amount</label>
                <span className="text-sm font-semibold text-neutral-900">{formatCurrency(editParams.loan_amount ?? analysis.loan_amount ?? 0)}</span>
              </div>
              <input
                type="range"
                min="0"
                max="10000000"
                step="50000"
                value={editParams.loan_amount ?? analysis.loan_amount ?? 0}
                onChange={(e) => handleParamChange('loan_amount', e.target.value)}
                className="w-full h-1.5 bg-neutral-100 rounded-full appearance-none cursor-pointer slider-thumb"
                style={{
                  background: `linear-gradient(to right, #171717 0%, #171717 ${((editParams.loan_amount ?? analysis.loan_amount ?? 0) / 10000000) * 100}%, #f5f5f5 ${((editParams.loan_amount ?? analysis.loan_amount ?? 0) / 10000000) * 100}%, #f5f5f5 100%)`
                }}
              />
              <div className="flex justify-between text-[9px] text-neutral-400 mt-1.5">
                <span>$0</span>
                <span>$10M</span>
              </div>
            </div>

              {/* Upside Summary */}
              <div className="bg-neutral-50 rounded-lg p-3 space-y-2 border border-neutral-100 mt-4">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-neutral-500">NOI Upside</span>
                  <span className="text-emerald-600 font-medium">{formatCurrency(noiChange)}</span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-neutral-500">Cap Rate Upside</span>
                  <span className="text-neutral-900 font-medium">{(capRateChange * 100).toFixed(2)}%</span>
                </div>
              </div>
            </div>
        </div>

        {/* Center: Operating Data & Sensitivity */}
        <div className="lg:col-span-8 flex flex-col gap-6">
          <div className="bg-white rounded-xl border border-neutral-200 shadow-sm flex flex-col">
            <div className="px-6 py-4 border-b border-neutral-100 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <h3 className="text-sm font-semibold text-neutral-900">Operating Analysis</h3>
                <select
                  value={selectedPeriod}
                  onChange={(e) => setSelectedPeriod(e.target.value)}
                  className="text-[10px] font-medium border border-neutral-200 rounded px-2 py-1 bg-neutral-50 hover:bg-white transition-all cursor-pointer outline-none focus:ring-1 focus:ring-neutral-400"
                >
                  <option value="T12">T12 (Trailing 12m)</option>
                  <option value="T9">T9 (Trailing 9m)</option>
                  <option value="T6">T6 (Trailing 6m)</option>
                  <option value="T3">T3 (Trailing 3m)</option>
                </select>
              </div>
              <div className="flex gap-2">
                <span className="flex items-center gap-1 text-[10px] text-neutral-500">
                  <span className="w-2 h-2 rounded-full bg-neutral-300"></span> Historical ({selectedPeriod})
                </span>
                <span className="flex items-center gap-1 text-[10px] text-neutral-500">
                  <span className="w-2 h-2 rounded-full bg-neutral-900"></span> Pro Forma ({selectedPeriod.replace("T", "F")})
                </span>
              </div>
            </div>
            
            <div className="p-0 relative">
            {hasCriticalIssues ? (
              <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-10 flex flex-col items-center justify-center text-center p-6 border-b border-neutral-100 rounded-b-xl">
                <div className="w-12 h-12 bg-rose-100 rounded-full flex items-center justify-center text-rose-500 mb-3">
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                    <line x1="12" y1="9" x2="12" y2="13"></line>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                  </svg>
                </div>
                <h4 className="text-neutral-900 font-semibold mb-2">Analysis Paused</h4>
                <p className="text-sm text-neutral-600 max-w-sm mb-4">
                  We cannot populate the Operating Analysis table due to critical data issues:
                </p>
                <div className="text-left inline-block mb-6">
                  {missingValues.length > 0 && (
                     <ul className="text-sm text-rose-600 font-medium mb-2">
                       {missingValues.map((val) => <li key={val}>• Missing: {val}</li>)}
                     </ul>
                  )}
                  {/* {logicErrors.length > 0 && (
                     <div className="mt-2">
                       <p className="text-sm text-rose-600 font-bold mb-2">Data Logic Errors:</p>
                       <ul className="text-sm text-rose-600 font-medium bg-rose-50/50 p-3 rounded-lg border border-rose-100">
                         {logicErrors.map((err) => <LogicErrorItem key={err} errorMsg={err} analysis={analysis} />)}
                       </ul>
                     </div>
                  )} */}
                </div>
                
              </div>
            ) : null}
            
            <table className={`w-full text-left text-sm ${hasCriticalIssues ? 'opacity-20 pointer-events-none' : ''}`}>
              <thead>
                <tr className="bg-neutral-50/50 border-b border-neutral-100 text-xs text-neutral-500 font-medium">
                  <th className="px-6 py-3 font-medium">Item</th>
                  <th className="px-6 py-3 font-medium text-right">{selectedPeriod} (Historical)</th>
                  <th className="px-6 py-3 font-medium text-right">{selectedPeriod.replace("T", "F")} (Pro Forma)</th>
                  <th className="px-6 py-3 font-medium text-right w-24">Var %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                <tr className="group hover:bg-neutral-50 transition-colors">
                  <td className="px-6 py-3.5 text-neutral-600 font-medium group/explanation relative cursor-help">
                    Gross Potential Rent
                    <ExplanationTooltip metadata={analysis.explainability?.["Gross Potential Rent"]} analysis={analysis} selectedPeriod={selectedPeriod} />
                  </td>
                  <td className="px-6 py-3.5 text-right text-neutral-900 font-medium">
                    <span className="relative group/explanation cursor-help inline-block">
                      {formatCurrency((analysis.rent_roll_summary?.total_annual_rent || 0) * periodMultiplier)}
                      <ExplanationTooltip metadata={analysis.explainability?.["Historical Gross Potential Rent"]} analysis={analysis} selectedPeriod={selectedPeriod} />
                    </span>
                  </td>
                  <td className="px-6 py-3.5 text-right text-neutral-900 font-medium">
                    <span className="relative group/explanation cursor-help inline-block">
                      {formatCurrency(adjustedProFormaGPR)}
                      <ExplanationTooltip metadata={analysis.explainability?.["Gross Potential Rent"]} analysis={analysis} selectedPeriod={selectedPeriod} />
                    </span>
                  </td>
                  <td className="px-6 py-3.5 text-right text-emerald-600 text-xs">
                    {((adjustedProFormaGPR - ((analysis.rent_roll_summary?.total_annual_rent || 0) * periodMultiplier)) / (((analysis.rent_roll_summary?.total_annual_rent || 0) * periodMultiplier) || 1) * 100).toFixed(1)}%
                  </td>
                </tr>
                {/* EGI Waterfall: Loss to Lease */}
                {(analysis.loss_to_lease || 0) > 0 && (
                  <tr className="group hover:bg-neutral-50/50 transition-colors">
                    <td className="pl-10 pr-6 py-2.5 text-xs text-neutral-500">
                      Less: Loss to Lease
                    </td>
                    <td className="px-6 py-2.5 text-right text-xs text-neutral-500">—</td>
                    <td className="px-6 py-2.5 text-right text-xs text-neutral-500">
                      ({formatCurrency((analysis.loss_to_lease || 0) * periodMultiplier)})
                    </td>
                    <td className="px-6 py-2.5" />
                  </tr>
                )}
                {/* EGI Waterfall: Vacancy Loss */}
                {(analysis.vacancy_loss || 0) > 0 && (
                  <tr className="group hover:bg-neutral-50/50 transition-colors">
                    <td className="pl-10 pr-6 py-2.5 text-xs text-neutral-500">
                      Less: Vacancy Loss
                    </td>
                    <td className="px-6 py-2.5 text-right text-xs text-neutral-500">—</td>
                    <td className="px-6 py-2.5 text-right text-xs text-neutral-500">
                      ({formatCurrency((analysis.vacancy_loss || 0) * periodMultiplier)})
                    </td>
                    <td className="px-6 py-2.5" />
                  </tr>
                )}
                {/* EGI Waterfall: Other Income */}
                {(analysis.other_income || 0) > 0 && (
                  <tr className="group hover:bg-neutral-50/50 transition-colors">
                    <td className="pl-10 pr-6 py-2.5 text-xs text-neutral-500">
                      Plus: Other Income
                    </td>
                    <td className="px-6 py-2.5 text-right text-xs text-neutral-500">—</td>
                    <td className="px-6 py-2.5 text-right text-xs text-neutral-500">
                      {formatCurrency((analysis.other_income || 0) * periodMultiplier)}
                    </td>
                    <td className="px-6 py-2.5" />
                  </tr>
                )}
                {/* EGI Subtotal */}
                {(analysis.effective_gross_income || 0) > 0 && (
                  <tr className="group hover:bg-neutral-50 transition-colors border-t border-neutral-100">
                    <td className="px-6 py-3 text-sm text-neutral-700 font-medium">
                      Effective Gross Income
                    </td>
                    <td className="px-6 py-3 text-right text-sm text-neutral-700 font-medium">
                      {formatCurrency(historicalNOI + historicalTotalExpenses)}
                    </td>
                    <td className="px-6 py-3 text-right text-sm text-neutral-700 font-medium">
                      {formatCurrency((analysis.effective_gross_income || 0) * periodMultiplier)}
                    </td>
                    <td className="px-6 py-3" />
                  </tr>
                )}
                <tr className="group hover:bg-neutral-50 transition-colors">
                  <td className="px-6 py-3.5 text-neutral-600 font-medium group/explanation relative cursor-help">
                    Total Expenses
                    <ExplanationTooltip metadata={analysis.explainability?.["Total Operating Expenses"]} analysis={analysis} selectedPeriod={selectedPeriod} />
                  </td>
                  <td className="px-6 py-3.5 text-right text-neutral-900">
                    <span className="relative group/explanation cursor-help inline-flex flex-col items-end">
                      <span>({formatCurrency(historicalTotalExpenses)})</span>
                      <span className="text-[10px] text-neutral-400 font-normal mt-0.5">
                        {((historicalTotalExpenses / (((analysis.rent_roll_summary?.total_annual_rent || 0) * periodMultiplier) || 1)) * 100).toFixed(1)}% of GPR
                      </span>
                      <ExplanationTooltip metadata={analysis.explainability?.["Historical Total Operating Expenses"]} analysis={analysis} selectedPeriod={selectedPeriod} />
                    </span>
                  </td>
                  <td className="px-6 py-3.5 text-right text-neutral-900">
                    <span className="relative group/explanation cursor-help inline-flex flex-col items-end">
                      <span>({formatCurrency(adjustedProFormaExpenses)})</span>
                      <span className="text-[10px] text-neutral-400 font-normal mt-0.5">
                        {((adjustedProFormaExpenses / (adjustedProFormaGPR || 1)) * 100).toFixed(1)}% of GPR
                      </span>
                      <ExplanationTooltip metadata={analysis.explainability?.["Total Operating Expenses"]} analysis={analysis} selectedPeriod={selectedPeriod} />
                    </span>
                  </td>
                  <td className="px-6 py-3.5 text-right text-emerald-600 text-xs">
                    {((historicalTotalExpenses - adjustedProFormaExpenses) / (historicalTotalExpenses || 1) * 100).toFixed(1)}%
                  </td>
                </tr>
                <tr className="bg-neutral-50/30 font-semibold border-t border-neutral-200">
                  <td className="px-6 py-4 text-neutral-900 group/explanation relative cursor-help">
                    Net Operating Income
                    <ExplanationTooltip metadata={analysis.explainability?.["Net Operating Income (NOI)"]} analysis={analysis} selectedPeriod={selectedPeriod} />
                  </td>
                  <td className="px-6 py-4 text-right text-rose-600">
                    <span className="relative group/explanation cursor-help inline-block">
                      {formatCurrency(historicalNOI)}
                      <ExplanationTooltip metadata={analysis.explainability?.["Historical Net Operating Income (NOI)"]} analysis={analysis} selectedPeriod={selectedPeriod} />
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right text-rose-600">
                    <span className="relative group/explanation cursor-help inline-block">
                      {formatCurrency(adjustedProFormaNOI)}
                      <ExplanationTooltip metadata={analysis.explainability?.["Net Operating Income (NOI)"]} analysis={analysis} selectedPeriod={selectedPeriod} />
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right text-emerald-600 text-xs">{noiChangePercent.toFixed(1)}%</td>
                </tr>
                <tr className="group hover:bg-neutral-50 transition-colors">
                  <td className="px-6 py-3.5 text-neutral-600 font-medium group/explanation relative cursor-help">
                    Cap Rate
                    <ExplanationTooltip metadata={analysis.explainability?.["Entry Cap Rate"]} analysis={analysis} selectedPeriod={selectedPeriod} />
                  </td>
                  <td className="px-6 py-3.5 text-right text-rose-600 font-medium">
                    <span className="relative group/explanation cursor-help inline-block">
                      {formatPercent(historicalCapRate)}
                      <ExplanationTooltip metadata={analysis.explainability?.["Historical Cap Rate"]} analysis={analysis} selectedPeriod={selectedPeriod} />
                    </span>
                  </td>
                  <td className="px-6 py-3.5 text-right text-rose-600 font-medium">
                    <span className="relative group/explanation cursor-help inline-block">
                      {formatPercent(proFormaCapRate)}
                      <ExplanationTooltip metadata={analysis.explainability?.["Entry Cap Rate"]} analysis={analysis} selectedPeriod={selectedPeriod} />
                    </span>
                  </td>
                  <td className="px-6 py-3.5 text-right"></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        
        <SensitivityAnalysisWidget analysis={analysis} />
      </div>
    </div>


      {/* Additional Detailed Sections with Neutral Design */}
      



      {/* Upside Potential */}
      <div className="bg-gradient-to-br from-slate-50 via-neutral-50 to-stone-50 rounded-xl border border-slate-200 shadow-sm p-6">
        <h3 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2">
          <svg className="w-4 h-4 text-[#FF5E00]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
          Upside Potential Analysis
        </h3>
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
            <div className="text-slate-700 text-xs mb-2 flex items-center uppercase tracking-wide font-semibold">
              NOI Upside <InfoTooltip term="Upside" />
            </div>
            <p className={`text-3xl font-extrabold ${noiChange >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
              {formatCurrency(noiChange)}
            </p>
            <p className="text-xs font-medium text-neutral-600 mt-1">
              <span className={`font-bold ${noiChangePercent >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>{noiChangePercent > 0 ? "+" : ""}{noiChangePercent.toFixed(1)}%</span> vs Historical
            </p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
            <div className="text-slate-700 text-xs mb-2 flex items-center uppercase tracking-wide font-semibold">
              Cap Rate Upside <InfoTooltip term="Upside" />
            </div>
            <p className={`text-3xl font-extrabold ${capRateChange >= 0 ? 'text-[#FF5E00]' : 'text-rose-600'}`}>
              {(capRateChange * 100).toFixed(2)}%
            </p>
            <p className="text-xs font-medium text-neutral-600 mt-1">
              <span className="text-neutral-700">{(historicalCapRate * 100).toFixed(2)}%</span> → <span className={`font-bold ${capRateChange >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>{(proFormaCapRate * 100).toFixed(2)}%</span>
            </p>
          </div>
        </div>
      </div>

      {/* Analyst Commentary Section - Collapsible */}
      {analysis.analyst_commentary && (
        <div className="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden">
          <button
            onClick={() => setIsCommentaryExpanded(!isCommentaryExpanded)}
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-neutral-50 transition-colors">
            <div className="flex items-center gap-3">
              <div className="flex-shrink-0 w-8 h-8 bg-slate-700 rounded-lg flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
              </div>
              <div className="text-left">
                <h3 className="text-sm font-semibold text-neutral-900">Analyst Commentary</h3>
                <p className="text-xs text-neutral-500 mt-0.5">Professional insights and detailed analysis</p>
              </div>
            </div>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className={`text-neutral-400 transition-transform duration-200 ${isCommentaryExpanded ? 'rotate-180' : ''}`}
            >
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>

          {isCommentaryExpanded && (
            <div className="px-6 pb-6 pt-2 bg-gradient-to-br from-slate-50/30 to-neutral-50/30 border-t border-neutral-100 relative min-h-[300px]">
              
              {/* Critical Issues Overlay for Analyst Commentary */}
              {hasCriticalIssues && (
                <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-20 flex flex-col items-center justify-center text-center p-6 rounded-b-xl">
                  <div className="w-12 h-12 bg-rose-100 rounded-full flex items-center justify-center text-rose-500 mb-3">
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                      <line x1="12" y1="9" x2="12" y2="13"></line>
                      <line x1="12" y1="17" x2="12.01" y2="17"></line>
                    </svg>
                  </div>
                  <h4 className="text-neutral-900 font-semibold mb-2">Commentary Suspended</h4>
                  <p className="text-sm text-neutral-600 max-w-sm mb-6">
                    Professional commentary and final verdict cannot be generated while critical data is missing or invalid.
                  </p>
                </div>
              )}

              <div className={hasCriticalIssues ? "opacity-20 blur-[1px] pointer-events-none select-none" : ""}>
                {/* 3-Paragraph Summary */}
                <div className="bg-white rounded-lg p-5 border border-neutral-200 shadow-sm space-y-4 mb-6">
                  {analysis.analyst_commentary.split('\n\n').filter(p => p.trim()).map((paragraph, idx) => (
                    <p key={idx} className="text-sm text-neutral-800 leading-relaxed">
                      {paragraph.trim()}
                    </p>
                  ))}
                </div>

                {/* Detailed Analysis Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Deal Viability */}
                <div className="bg-white rounded-lg p-4 border border-neutral-200 shadow-sm">
                  <h4 className="text-xs font-bold text-neutral-900 mb-3 uppercase tracking-wide">Deal Viability</h4>
                  <div className="space-y-3">
                    <div>
                      <span className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">AI Decision</span>
                      <p className={`text-xs font-semibold mt-1 ${analysis.pass_fail_status === 'PASS' ? 'text-emerald-700' : 'text-rose-700'}`}>
                        {analysis.pass_fail_status === 'PASS' ? 'Approved' : 'Declined / Requires Waiver'}
                      </p>
                    </div>
                    <div>
                      <span className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">Reasoning</span>
                      <p className="text-xs text-neutral-700 mt-1 leading-relaxed">
                        {analysis.gating_reasons && analysis.gating_reasons.length > 0
                          ? `The deal failed to meet the required gating criteria. Specifically: ${analysis.gating_reasons.join('; ')}. This indicates that fundamental investment parameters are not currently satisfied based on the provided financials.`
                          : 'The property meets all preliminary investment criteria and financial thresholds. The provided documentation and current pro forma projections align with the strategic investment mandate.'}
                      </p>
                    </div>
                    <div>
                      <span className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">Client Impact</span>
                      <p className="text-xs text-neutral-700 mt-1 leading-relaxed">
                        {analysis.pass_fail_status === 'PASS'
                          ? 'The deal has been cleared to proceed to the formal underwriting and comprehensive due diligence phase. Teams can allocate resources to verify property condition, finalize debt structuring, and prepare investment committee memos.'
                          : 'The transaction is flagged for immediate rejection. Deal teams must halt further resource allocation unless formal waivers are obtained or structural changes (e.g., price reduction, equity injection) are negotiated to mitigate the identified risks.'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Operational Efficiency (NOI) */}
                <div className="bg-white rounded-lg p-4 border border-neutral-200 shadow-sm">
                  <h4 className="text-xs font-bold text-neutral-900 mb-3 uppercase tracking-wide">Operational Efficiency (NOI)</h4>
                  <div className="space-y-3">
                    <div>
                      <span className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">AI Decision</span>
                      <p className={`text-xs font-semibold mt-1 ${noiChange >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
                        Projected NOI {noiChange >= 0 ? 'increased' : 'decreased'} by {formatCurrency(Math.abs(noiChange))}
                      </p>
                    </div>
                    <div>
                      <span className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">Reasoning</span>
                      <p className="text-xs text-neutral-700 mt-1 leading-relaxed">
                        Pro forma NOI diverges from T-12 historicals due to automated normalization adjustments. The AI engine recalibrated projected revenues based on current market rents and stabilized vacancy assumptions, while simultaneously standardizing operating expenses (such as property taxes, insurance, and management fees) to reflect institutional operational standards.
                      </p>
                    </div>
                    <div>
                      <span className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">Client Impact</span>
                      <p className="text-xs text-neutral-700 mt-1 leading-relaxed">
                        {noiChange >= 0 ? 'An increased pro forma NOI enhances the underlying asset valuation, potentially allowing for maximum leverage and more favorable loan sizing. This provides a stronger foundation for target yield metrics.' : 'A decreased pro forma NOI directly reduces the capitalized valuation of the asset and compresses the maximum allowable loan amount sizing. Investors may need to renegotiate the purchase price or inject additional equity to maintain target leverage ratios.'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Debt Service Coverage */}
                <div className="bg-white rounded-lg p-4 border border-neutral-200 shadow-sm">
                  <h4 className="text-xs font-bold text-neutral-900 mb-3 uppercase tracking-wide">Debt Service Coverage</h4>
                  <div className="space-y-3">
                    <div>
                      <span className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">AI Decision</span>
                      <p className={`text-xs font-semibold mt-1 ${(analysis.dscr || 0) >= 1.25 ? 'text-emerald-700' : 'text-rose-700'}`}>
                        {(analysis.dscr || 0) >= 1.25 ? 'Adequate' : 'Low'} DSCR of {(analysis.dscr || 0).toFixed(2)}x
                      </p>
                    </div>
                    <div>
                      <span className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">Reasoning</span>
                      <p className="text-xs text-neutral-700 mt-1 leading-relaxed">
                        {(analysis.dscr || 0) >= 1.25
                          ? 'The projected stabilized Net Operating Income (NOI) provides a sufficient buffer to comfortably cover the proposed annualized debt service obligations, meeting or exceeding standard lender underwriting minimums (typically 1.20x - 1.25x).'
                          : 'The projected stabilized Net Operating Income (NOI) falls below the minimum threshold required to safely service the proposed debt load. This indicates that operational cash flow is currently insufficient to meet periodic principal and interest payments without significant risk of shortfall.'}
                      </p>
                    </div>
                    <div>
                      <span className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">Client Impact</span>
                      <p className="text-xs text-neutral-700 mt-1 leading-relaxed">
                        {(analysis.dscr || 0) >= 1.25
                          ? 'The property presents an acceptable risk profile for debt financing. The healthy cash flow buffer supports favorable loan terms, protects investor distributions, and ensures compliance with standard debt yield and DSCR covenants.'
                          : 'The severe default risk will likely trigger loan rejection under current terms. To proceed, the sponsor must structurally de-risk the deal by either negotiating a lower purchase price, significantly reducing the requested loan amount, securing lower interest rates, or injecting additional upfront equity.'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Valuation (Cap Rate) */}
                <div className="bg-white rounded-lg p-4 border border-neutral-200 shadow-sm">
                  <h4 className="text-xs font-bold text-neutral-900 mb-3 uppercase tracking-wide">Valuation (Cap Rate)</h4>
                  <div className="space-y-3">
                    <div>
                      <span className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">AI Decision</span>
                      <p className="text-xs font-semibold text-neutral-900 mt-1">
                        Entry Cap Rate at {formatPercent(proFormaCapRate)}
                      </p>
                    </div>
                    <div>
                      <span className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">Reasoning</span>
                      <p className="text-xs text-neutral-700 mt-1 leading-relaxed">
                        The Entry Cap Rate is derived by dividing the stabilized Pro Forma Net Operating Income (NOI) by the stated purchase price of {formatCurrency(purchasePrice)}. This metric isolates the asset's unleveraged initial rate of return based purely on its expected operational cash generation capabilities.
                      </p>
                    </div>
                    <div>
                      <span className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">Client Impact</span>
                      <p className="text-xs text-neutral-700 mt-1 leading-relaxed">
                        This yield reflects the upfront market pricing relative to current operational performance. Investors should compare this entry yield against the established market exit benchmark of {formatPercent(analysis.deal_parameters?.exit_cap_rate || 0.06)} to gauge potential cap rate compression or expansion risk, which directly drives the terminal asset value and overall IRR viability.
                      </p>
                    </div>
                  </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

    </div>
    </>
  );
}
