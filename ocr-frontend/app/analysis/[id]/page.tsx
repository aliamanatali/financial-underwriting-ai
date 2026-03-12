"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { UnderwritingAnalysis, FinancialAnalysisProgress, DealParameters } from "@/lib/types";
import LoadingSpinner from "@/components/LoadingSpinner";
import UnderwritingDashboard from "@/components/UnderwritingDashboard";
import AuditTrailWidget from "@/components/AuditTrailWidget";
import VerificationWidget from "@/components/VerificationWidget";
import ExportButtons from "@/components/ExportButtons";
import Sidebar from "@/components/Sidebar";
import { apiClient } from "@/lib/api";
import ReportChatWidget from "@/components/ReportChatWidget";

const logInternalAuditReport = (data: UnderwritingAnalysis, packageId: string, sourceContext: string) => {
  console.log(`🔍 INTERNAL AUDIT REPORT: Analysis Data Load (${sourceContext})`);
  console.log("Time:", new Date().toISOString());
  console.log("Package ID:", packageId);

  // 1. OCR Extracted Values (Raw Mapped Data)
  const extractedValues: Record<string, any> = {};
  data.historical_expenses?.forEach((item) => {
    const source = item.audit_log?.source || "Unknown";
    const key = `[${source}] ${item.original_text}`;
    extractedValues[key] = item.amount;
  });
  console.log(`OCR Extracted Values (from ${sourceContext}):`, extractedValues);

  // 2. Categorization Report (Table)
  console.log(`📊 Historical Expenses Categorization (${data.historical_expenses?.length || 0} items)`);
  if (data.historical_expenses?.length > 0) {
    const expenseTable = data.historical_expenses.map((item) => ({
      Category: item.mapped_category,
      "Original Text": item.original_text,
      Amount: item.amount,
      Source: item.audit_log?.source || "Unknown",
      Confidence: item.confidence
    }));
    console.table(expenseTable);
  }

  // 3. Rent Roll Summary
  if (data.rent_roll_summary) {
    console.log(`🏠 Rent Roll Summary (${data.rent_roll_summary.total_units} units)`);
    console.log({
      TotalUnits: data.rent_roll_summary.total_units,
      Occupied: data.rent_roll_summary.occupied_units,
      OccupancyRate: `${(data.rent_roll_summary.occupancy_rate * 100).toFixed(1)}%`,
      AnnualRent: data.rent_roll_summary.total_annual_rent
    });
  }

  // 3.5 Trailing Periods Summary
  if (data.historical_periods && data.historical_periods.length > 0) {
    console.log(`🕒 Trailing Periods Summary:`);
    console.table(data.historical_periods);
  }

  // 4. Financial Metrics
  console.log("📈 Financial Metrics:", {
    NOI: data.pro_forma_noi,
    "Cap Rate": data.cap_rate,
    DSCR: data.dscr,
    Yield: data.debt_yield,
  });

  // 5. The Maths (Explainability)
  if (data.explainability) {
    console.log("🧮 Calculation Logic (The Maths):");
    Object.entries(data.explainability).forEach(([metric, details]) => {
      console.log(`  🔹 ${metric}:`, {
        Formula: details.calculation.formula,
        Inputs: details.calculation.inputs,
        Source: details.source
      });
    });
  }
};

export default function AnalysisResultPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const id = params.id as string;
  const [analysis, setAnalysis] = useState<UnderwritingAnalysis | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<FinancialAnalysisProgress>({ percentage: 0, message: "Initializing..." });
  const [activeTab, setActiveTab] = useState<"dashboard" | "audit" | "export" | "verification">("dashboard");
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [initialRentRollTab, setInitialRentRollTab] = useState<"details" | "omExport" | "unitBreakdown" | "unitBreakdownStabilized">("details");
  const [initialRentRollEditMode, setInitialRentRollEditMode] = useState(false);
  const [validationTrigger, setValidationTrigger] = useState<number>(0);

  useEffect(() => {
    const tab = searchParams.get("tab");
    const rentRollTab = searchParams.get("rentRollTab");
    const rentRollEditMode = searchParams.get("rentRollEditMode");
    const trigger = searchParams.get("validationTrigger");

    if (tab === "export") {
      setActiveTab("export");
    } else if (tab === "dashboard") {
      setActiveTab("dashboard");
    } else if (tab === "verification") {
      setActiveTab("verification");
    }
    
    if (rentRollTab) {
        setInitialRentRollTab(rentRollTab as any);
    }
    
    if (rentRollEditMode === "true") {
        setInitialRentRollEditMode(true);
    }

    if (trigger) {
        setValidationTrigger(Number(trigger));
    }
  }, [searchParams]);
  
  const eventSourceRef = useRef<EventSource | null>(null);
  const API_BASE_URL = process.env.NEXT_PUBLIC_FINANCIAL_API_URL;

  const closeEventSource = () => {
    if (eventSourceRef.current) {
      console.log("Closing existing EventSource");
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  };

  const handleReanalyze = async (newParams: DealParameters) => {
    console.log("🔄 handleReanalyze called in parent component");
    console.log("📊 Re-analyzing with params:", newParams);
    console.log("🆔 Package ID:", id);
    console.log("🌐 API Base URL:", API_BASE_URL);
    
    setIsLoading(true);
    setError(null);
    setProgress({ percentage: 0, message: "Restarting analysis..." });
    setAnalysis(null);

    closeEventSource();
    eventSourceRef.current = apiClient.streamFinancialAnalysisProgress(id, (progressUpdate) => {
      setProgress(progressUpdate);
    });

    try {
      const apiUrl = `${API_BASE_URL}/api/v1/multi-document/packages/${id}/analyze`;
      console.log("📡 Making POST request to:", apiUrl);
      console.log("📦 Request body:", JSON.stringify(newParams, null, 2));
      
      const response = await fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newParams),
      });

      console.log("📥 Response status:", response.status, response.statusText);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Unknown error" }));
        const errorMessage = errorData.detail || `HTTP ${response.status}: ${response.statusText}`;
        console.error("❌ Analysis failed:", errorMessage);
        throw new Error(`Analysis failed: ${errorMessage}`);
      }

      const result: UnderwritingAnalysis = await response.json();
      console.log("✅ Analysis completed successfully");
      setAnalysis(result);
      logInternalAuditReport(result, id, "Analysis");
      setError(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch analysis results.";
      console.error("❌ Analysis error:", errorMessage, err);
      setError(errorMessage);
    } finally {
      closeEventSource();
      setIsLoading(false);
      console.log("🏁 handleReanalyze completed");
    }
  };

  useEffect(() => {
    if (id) {
      const fetchAnalysis = async () => {
        try {
          // Prevent unnecessary re-fetches if data is already loaded and valid for this ID
          if (analysis && analysis.document_id === id && !isLoading) {
             return;
          }

          setIsLoading(true);
          setError(null);
          setProgress({ percentage: 0, message: "Starting analysis..." });
          
          closeEventSource();
          eventSourceRef.current = apiClient.streamFinancialAnalysisProgress(id, (progressUpdate) => {
            setProgress(progressUpdate);
          });

          console.log(`Starting analysis for document: ${id}`);
          console.log(`API URL: ${API_BASE_URL}`);

          let existingAnalysisResponse;
          try {
            existingAnalysisResponse = await fetch(`${API_BASE_URL}/api/v1/multi-document/packages/${id}/analysis`);
            if (existingAnalysisResponse.ok) {
              const existingResult = await existingAnalysisResponse.json();
              console.log("Loaded existing analysis from history");
              setAnalysis(existingResult);
              logInternalAuditReport(existingResult, id, "History");
              setError(null);
              setIsLoading(false);
              closeEventSource();
              return;
            }
          } catch (e) {
            console.log("Could not load existing analysis, proceeding to run new analysis");
          }

          let isPackage = false;
          try {
            const packageCheck = await fetch(`${API_BASE_URL}/api/v1/multi-document/packages/${id}`);
            if (packageCheck.ok) {
              isPackage = true;
              console.log("Detected multi-document package");
            }
          } catch (e) {
            console.log("Not a package, using single-document flow");
          }

          let response;
          if (isPackage) {
            const defaultParams: DealParameters = {
                growth_rate: 0.03,
                exit_cap_rate: 0.06,
                vacancy_rate: 0.03,
                loan_amount: 5000000,
                min_unit_count: 15,
                max_unit_count: 80,
                max_build_year: 1970,
            };

            response = await fetch(`${API_BASE_URL}/api/v1/multi-document/packages/${id}/analyze`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(defaultParams),
            });
          } else {
            response = await fetch(`${API_BASE_URL}/api/v1/analysis/${id}`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                growth_rate: 0.03,
                exit_cap_rate: 0.06,
                vacancy_rate: 0.03,
                loan_amount: 5000000,
              }),
            });
          }

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: "Unknown error" }));
            const errorMessage = errorData.detail || `HTTP ${response.status}: ${response.statusText}`;
            throw new Error(`Analysis failed: ${errorMessage}`);
          }

          const result: UnderwritingAnalysis = await response.json();
          setAnalysis(result);
          logInternalAuditReport(result, id, "Analysis");
          setError(null);
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : "Failed to fetch analysis results.";
          console.error("Analysis error:", errorMessage, err);
          setError(errorMessage);
        } finally {
          setIsLoading(false);
          closeEventSource();
        }
      };
      
      fetchAnalysis();
    }

    return () => {
        closeEventSource();
    };
  }, [id]); // Removed API_BASE_URL from dependencies to prevent re-runs on env var ref changes

  if (isLoading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center p-4">
        <div className="bg-white p-10 rounded-2xl shadow-xl border border-neutral-100 max-w-md w-full text-center">
          <div className="mx-auto"><LoadingSpinner /></div>
          <h2 className="mt-8 text-2xl font-bold text-neutral-900">Analyzing Deal...</h2>
          <p className="text-neutral-500 mt-2">Processing financials and generating insights</p>
          
          <div className="mt-8 w-full bg-neutral-100 rounded-full h-3 overflow-hidden">
            <div
              className="bg-neutral-900 h-3 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progress.percentage}%` }}
            ></div>
          </div>
          
          <p className="mt-4 text-sm font-semibold text-neutral-900 animate-pulse">
            {progress.message}
          </p>
          {progress.details?.current_file && (
            <p className="mt-1 text-xs text-neutral-500">
              Processing: <span className="font-medium">{progress.details.current_file}</span>
              {progress.details.total_files && (
                <span className="ml-1">
                  ({progress.details.file_index}/{progress.details.total_files})
                </span>
              )}
            </p>
          )}
          <p className="mt-2 text-xs text-neutral-400 font-medium">
            {progress.percentage}% Complete
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    const isLikelyPackage = error.includes('package') || error.includes('multi-document') || error.includes('Deal package');
    
    return (
      <div className="min-h-screen bg-neutral-50 p-6 flex items-center justify-center">
        <div className="max-w-2xl w-full">
          <div className="bg-white border border-rose-200 rounded-2xl shadow-lg p-8">
            <div className="flex items-start">
              <div className="flex-shrink-0 w-12 h-12 bg-rose-100 rounded-full flex items-center justify-center mr-6">
                <svg className="h-6 w-6 text-rose-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div className="flex-1">
                <h2 className="text-2xl font-bold text-neutral-900 mb-2">Analysis Failed</h2>
                <p className="text-rose-600 mb-6 font-mono text-sm bg-rose-50 p-4 rounded-lg break-words border border-rose-100">
                  {error}
                </p>
                <div className="bg-neutral-50 p-5 rounded-xl mb-8 text-sm text-neutral-700 border border-neutral-100">
                  <p className="font-bold text-neutral-900 mb-3 uppercase tracking-wide text-xs">Troubleshooting Tips</p>
                  <ul className="list-disc list-inside space-y-2 ml-1">
                    <li>Ensure the financial-engine backend is running on <code className="bg-neutral-200 px-1.5 py-0.5 rounded text-neutral-800">{API_BASE_URL}</code></li>
                    {isLikelyPackage ? (
                      <>
                        <li>Verify the deal package was successfully uploaded via the multi-document upload page</li>
                        <li>Check that the package ID is correct: <code className="bg-neutral-200 px-1.5 py-0.5 rounded text-neutral-800">{id}</code></li>
                        <li>The package may have been deleted or expired from storage</li>
                        <li>Try re-uploading your ZIP file with the deal package documents</li>
                      </>
                    ) : (
                      <>
                        <li>Verify the document was successfully processed by OCR backend</li>
                        <li>Check that the document ID is correct: <code className="bg-neutral-200 px-1.5 py-0.5 rounded text-neutral-800">{id}</code></li>
                        <li>The document may have been deleted or expired from storage</li>
                        <li>Try re-uploading your document</li>
                      </>
                    )}
                    <li>Verify network connectivity and firewall settings</li>
                  </ul>
                </div>
                <div className="flex gap-4">
                  <button
                    onClick={() => router.push("/")}
                    className="inline-flex items-center px-6 py-3 bg-neutral-800 text-white rounded-lg hover:bg-neutral-900 transition-colors font-medium cursor-pointer"
                  >
                    ← Back to Dashboard
                  </button>
                  <button
                    onClick={() => window.location.reload()}
                    className="inline-flex items-center px-6 py-3 bg-white text-neutral-700 border border-neutral-300 rounded-lg hover:bg-neutral-50 transition-colors font-medium"
                  >
                    🔄 Retry Analysis
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
        <div className="min-h-screen bg-neutral-50 flex items-center justify-center">
            <div className="text-center p-10 bg-white rounded-xl shadow-sm border border-neutral-200">
                <div className="text-neutral-400 mb-4 text-4xl">📂</div>
                <h3 className="text-lg font-medium text-neutral-900">No analysis data found</h3>
                <button 
                    onClick={() => router.push('/')}
                    className="mt-4 text-neutral-900 hover:text-neutral-700 font-medium"
                >
                    Return to Dashboard
                </button>
            </div>
        </div>
    );
  }

  const getStatusDisplay = (status: string) => {
    if (status === "PASS") {
      return {
        text: "CRITERIA MET",
        color: "bg-emerald-50 text-emerald-700 border-emerald-100",
      };
    } else {
      return {
        text: "CRITERIA NOT MET",
        color: "bg-rose-50 text-rose-700 border-rose-100",
      };
    }
  };

  return (
    <div className="min-h-screen overflow-hidden bg-white text-neutral-900 flex relative">
      {/* Background Animation */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:24px_24px]"></div>
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-white"></div>
      </div>

      {/* Sidebar */}
      <Sidebar
        sidebarExpanded={sidebarExpanded}
        toggleSidebar={() => setSidebarExpanded(!sidebarExpanded)}
        isChatMode={false}
        messages={[]}
        onNewChat={() => {}}
      />

      {/* Content Wrapper */}
      <div className={`flex flex-col flex-1 transition-all duration-300 h-screen relative z-10 bg-neutral-50/50 ${
        sidebarExpanded ? 'ml-64' : 'ml-[72px]'
      }`}>
        {/* Top Bar */}
        <header className="h-16 border-b border-neutral-100 bg-white/80 backdrop-blur-md flex items-center justify-between px-6 lg:px-8 shrink-0 sticky top-0 z-40">
          <div className="flex items-center gap-4">
            <button
              onClick={() => {
                if (activeTab !== 'dashboard') {
                  setActiveTab('dashboard');
                } else {
                  router.push('/dashboard');
                }
              }}
              className="text-neutral-500 hover:text-neutral-900 transition-colors cursor-pointer"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m12 19-7-7 7-7"></path>
                <path d="M19 12H5"></path>
              </svg>
            </button>
            <div className="h-6 w-[1px] bg-neutral-200"></div>
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <h1 className="text-sm font-semibold text-neutral-900">
                  {analysis.property_meta?.address || 'Financial Analysis'}
                </h1>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${getStatusDisplay(analysis.pass_fail_status).color}`}>
                  {getStatusDisplay(analysis.pass_fail_status).text}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setActiveTab('verification')}
              className={`hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all border border-transparent hover:border-neutral-200 ${
                activeTab === 'verification' ? 'text-neutral-900 bg-neutral-100' : 'text-neutral-600 hover:bg-neutral-100'
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 11l3 3L22 4"></path>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
              </svg>
              Verify Data
            </button>
            <button
              onClick={() => setActiveTab('audit')}
              className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium text-neutral-600 hover:bg-neutral-100 transition-all border border-transparent hover:border-neutral-200"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 12a9 9 0 1 0 9-9 9.76 9.76 0 0 0-4.7 8.5"></path>
                <path d="M3 12h9"></path>
                <path d="M3 12v9"></path>
              </svg>
              Audit Trail
            </button>
            <button 
              onClick={() => setActiveTab('export')}
              className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium text-neutral-600 hover:bg-neutral-100 transition-all border border-transparent hover:border-neutral-200"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" x2="12" y1="15" y2="3"></line>
              </svg>
              Export
            </button>
            <button 
              onClick={() => router.push('/dashboard')}
              className="flex items-center gap-2 bg-neutral-900 hover:bg-neutral-800 text-white px-3 py-1.5 rounded-md text-xs font-medium transition-all shadow-sm"
            >
              New Analysis
            </button>
          </div>
        </header>

        {/* Main Workspace */}
        <main className="flex-1 overflow-y-auto p-6 lg:p-8 no-scrollbar">
          <div className="max-w-7xl mx-auto flex flex-col gap-6">
            {activeTab === "dashboard" && (
              <UnderwritingDashboard
                analysis={analysis}
                onReanalyze={handleReanalyze}
                initialRentRollTab={initialRentRollTab}
                initialRentRollEditMode={initialRentRollEditMode}
                validationTrigger={validationTrigger}
              />
            )}

            {activeTab === "verification" && (
              <VerificationWidget
                packageId={id}
                view="both"
                onAnalysisUpdate={(newAnalysis) => {
                    console.log("Updating analysis state from verification", newAnalysis);
                    setAnalysis(newAnalysis);
                    setActiveTab("dashboard");
                }}
              />
            )}

            {activeTab === "audit" && (
              <AuditTrailWidget auditTrail={analysis.audit_trail || []} packageId={id} />
            )}

            {activeTab === "export" && (
              <div className="bg-white rounded-xl border border-neutral-200 shadow-sm p-6">
                <ExportButtons
                  analysis={analysis}
                  onAnalysisUpdate={(newAnalysis) => {
                    console.log("Updating analysis state in parent page", newAnalysis);
                    setAnalysis(newAnalysis);
                  }}
                />
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Chat Widget */}
      <ReportChatWidget documentId={id} />

      <style jsx global>{`
        .no-scrollbar::-webkit-scrollbar {
          display: none;
        }
        .no-scrollbar {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
      `}</style>
    </div>
  );
}
