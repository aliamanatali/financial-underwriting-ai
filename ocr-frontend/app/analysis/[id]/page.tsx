"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { UnderwritingAnalysis, FinancialAnalysisProgress } from "@/lib/types";
import LoadingSpinner from "@/components/LoadingSpinner";
import UnderwritingDashboard from "@/components/UnderwritingDashboard";
import AuditTrailWidget from "@/components/AuditTrailWidget";
import ExportButtons from "@/components/ExportButtons";
import { apiClient } from "@/lib/api";

export default function AnalysisResultPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [analysis, setAnalysis] = useState<UnderwritingAnalysis | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<FinancialAnalysisProgress>({ percentage: 0, message: "Initializing..." });
  const [activeTab, setActiveTab] = useState<"dashboard" | "audit" | "export">(
    "dashboard"
  );

  const API_BASE_URL = process.env.NEXT_PUBLIC_FINANCIAL_API_URL;

  useEffect(() => {
    if (id) {
      const fetchAnalysis = async () => {
        try {
          setIsLoading(true);
          setError(null);
          setProgress({ percentage: 0, message: "Starting analysis..." });

          // Start progress stream
          const eventSource = apiClient.streamFinancialAnalysisProgress(id, (progressUpdate) => {
            setProgress(progressUpdate);
          });

          console.log(`Starting analysis for document: ${id}`);
          console.log(`API URL: ${API_BASE_URL}`);

          // First, check if this is a multi-document package
          // 1. Try to fetch EXISTING analysis first (Dashboard/History flow)
          // This avoids re-running the expensive LLM/Calculation if it's already done
          let existingAnalysisResponse;
          let shouldRunAnalysis = false;
          try {
            existingAnalysisResponse = await fetch(`${API_BASE_URL}/api/v1/multi-document/packages/${id}/analysis`);
            if (existingAnalysisResponse.ok) {
              const existingResult = await existingAnalysisResponse.json();
              console.log("Loaded existing analysis from history");
              setAnalysis(existingResult);
              setError(null);
              setIsLoading(false);
              eventSource.close();
              return; // EXIT EARLY - We found it!
            } else if (existingAnalysisResponse.status === 404) {
              // Check if it's "NO_ANALYSIS_YET" or package doesn't exist
              const errorData = await existingAnalysisResponse.json().catch(() => ({ detail: "" }));
              if (errorData.detail === "NO_ANALYSIS_YET") {
                console.log("Package exists but no analysis yet, will run new analysis");
                shouldRunAnalysis = true;
              } else {
                console.log("Could not load existing analysis, proceeding to check package");
                shouldRunAnalysis = true;
              }
            }
          } catch (e) {
            console.log("Could not load existing analysis, proceeding to run new analysis");
            shouldRunAnalysis = true;
          }

          // 2. If no existing analysis, determine if it's a package or single doc
          let isPackage = false;
          try {
            const packageCheck = await fetch(`${API_BASE_URL}/api/v1/multi-document/packages/${id}`);
            if (packageCheck.ok) {
              isPackage = true;
              console.log("Detected multi-document package");
            }
          } catch (e) {
            // Not a package, continue with single-document flow
            console.log("Not a package, using single-document flow");
          }

          // 3. Run NEW Analysis
          let response;
          if (isPackage) {
            // Use multi-document analysis endpoint
            response = await fetch(`${API_BASE_URL}/api/v1/multi-document/packages/${id}/analyze`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                growth_rate: 0.03,
                exit_cap_rate: 0.06,
                vacancy_rate: 0.03,
                loan_amount: 5000000,
                min_unit_count: 15,
                max_unit_count: 80,
                max_build_year: 1970,
              }),
            });
          } else {
            // Use single-document analysis endpoint
            response = await fetch(`${API_BASE_URL}/api/v1/analysis/${id}`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
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
          setError(null);
          eventSource.close();
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : "Failed to fetch analysis results.";
          console.error("Analysis error:", errorMessage, err);
          setError(errorMessage);
        } finally {
          setIsLoading(false);
        }
      };
      fetchAnalysis();
    }
  }, [id, API_BASE_URL]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white p-10 rounded-2xl shadow-xl border border-slate-100 max-w-md w-full text-center">
          <LoadingSpinner size="lg" className="mx-auto" />
          <h2 className="mt-8 text-2xl font-bold text-slate-900">Analyzing Deal...</h2>
          <p className="text-slate-500 mt-2">Processing financials and generating insights</p>
          
          <div className="mt-8 w-full bg-slate-100 rounded-full h-3 overflow-hidden">
            <div
              className="bg-blue-600 h-3 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progress.percentage}%` }}
            ></div>
          </div>
          
          <p className="mt-4 text-sm font-semibold text-blue-600 animate-pulse">
            {progress.message}
          </p>
          {progress.details?.current_file && (
            <p className="mt-1 text-xs text-slate-500">
              Processing: <span className="font-medium">{progress.details.current_file}</span>
              {progress.details.total_files && (
                <span className="ml-1">
                  ({progress.details.file_index}/{progress.details.total_files})
                </span>
              )}
            </p>
          )}
          <p className="mt-2 text-xs text-slate-400 font-medium">
            {progress.percentage}% Complete
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    // Determine if this is a package or single document based on the ID format or error
    const isLikelyPackage = error.includes('package') || error.includes('multi-document') || error.includes('Deal package');
    
    return (
      <div className="min-h-screen bg-slate-50 p-6 flex items-center justify-center">
        <div className="max-w-2xl w-full">
          <div className="bg-white border border-rose-200 rounded-2xl shadow-lg p-8">
            <div className="flex items-start">
              <div className="flex-shrink-0 w-12 h-12 bg-rose-100 rounded-full flex items-center justify-center mr-6">
                <svg
                    className="h-6 w-6 text-rose-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                >
                    <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                </svg>
              </div>
              <div className="flex-1">
                <h2 className="text-2xl font-bold text-slate-900 mb-2">Analysis Failed</h2>
                <p className="text-rose-600 mb-6 font-mono text-sm bg-rose-50 p-4 rounded-lg break-words border border-rose-100">
                  {error}
                </p>
                <div className="bg-slate-50 p-5 rounded-xl mb-8 text-sm text-slate-700 border border-slate-100">
                  <p className="font-bold text-slate-900 mb-3 uppercase tracking-wide text-xs">Troubleshooting Tips</p>
                  <ul className="list-disc list-inside space-y-2 ml-1">
                    <li>Ensure the financial-engine backend is running on <code className="bg-slate-200 px-1.5 py-0.5 rounded text-slate-800">{API_BASE_URL}</code></li>
                    {isLikelyPackage ? (
                      <>
                        <li>Verify the deal package was successfully uploaded via the multi-document upload page</li>
                        <li>Check that the package ID is correct: <code className="bg-slate-200 px-1.5 py-0.5 rounded text-slate-800">{id}</code></li>
                        <li>The package may have been deleted or expired from storage</li>
                        <li>Try re-uploading your ZIP file with the deal package documents</li>
                      </>
                    ) : (
                      <>
                        <li>Verify the document was successfully processed by OCR backend</li>
                        <li>Check that the document ID is correct: <code className="bg-slate-200 px-1.5 py-0.5 rounded text-slate-800">{id}</code></li>
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
                    className="inline-flex items-center px-6 py-3 bg-slate-800 text-white rounded-lg hover:bg-slate-900 transition-colors font-medium"
                  >
                    ← Back to Dashboard
                  </button>
                  <button
                    onClick={() => window.location.reload()}
                    className="inline-flex items-center px-6 py-3 bg-white text-slate-700 border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors font-medium"
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
        <div className="min-h-screen bg-slate-50 flex items-center justify-center">
            <div className="text-center p-10 bg-white rounded-xl shadow-sm border border-slate-200">
                <div className="text-slate-400 mb-4 text-4xl">📂</div>
                <h3 className="text-lg font-medium text-slate-900">No analysis data found</h3>
                <button 
                    onClick={() => router.push('/')}
                    className="mt-4 text-blue-600 hover:text-blue-800 font-medium"
                >
                    Return to Dashboard
                </button>
            </div>
        </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
        {/* Navigation */}
        <nav className="bg-white border-b border-slate-200 sticky top-0 z-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between h-16">
                    <div className="flex items-center">
                        <a href="/" className="flex-shrink-0 flex items-center group">
                             <div className="h-8 w-8 bg-blue-600 rounded-lg flex items-center justify-center mr-2 group-hover:bg-blue-700 transition-colors">
                                <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                </svg>
                             </div>
                             <span className="font-bold text-xl tracking-tight text-slate-900">Financial Underwriting <span className="text-blue-600">AI</span></span>
                        </a>
                    </div>
                     <div className="flex items-center space-x-4">
                        <a href="/dashboard" className="text-sm font-medium text-slate-500 hover:text-slate-900">Dashboard</a>
                        <div className="h-4 w-px bg-slate-300"></div>
                        <div className="flex items-center px-3 py-1 rounded-full bg-emerald-50 border border-emerald-100 text-emerald-700 text-sm font-medium">
                            <span className="w-2 h-2 bg-emerald-500 rounded-full mr-2"></span>
                            Analysis Complete
                        </div>
                    </div>
                </div>
            </div>
        </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
            <div>
                <h1 className="text-3xl font-bold text-slate-900">Financial Analysis</h1>
                <p className="text-slate-500 mt-1">Comprehensive underwriting report and explainability audit</p>
            </div>
            <div className="flex gap-3">
                 <button
                  onClick={() => router.push("/dashboard")}
                  className="px-4 py-2 bg-white text-slate-700 border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors font-medium text-sm"
                >
                  New Analysis
                </button>
            </div>
        </div>

        {/* Tabs */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 mb-8">
            <div className="flex border-b border-slate-100">
            {[
                { id: "dashboard", label: "📊 Underwriting Dashboard" },
                { id: "audit", label: "🔍 Audit Trail" },
                { id: "export", label: "📥 Download & Export" },
            ].map((tab) => (
                <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex-1 px-6 py-4 font-semibold text-sm transition-all relative ${
                    activeTab === tab.id
                    ? "text-blue-600 bg-blue-50/50"
                    : "text-slate-500 hover:text-slate-700 hover:bg-slate-50"
                }`}
                >
                {tab.label}
                {activeTab === tab.id && (
                    <div className="absolute bottom-0 left-0 w-full h-0.5 bg-blue-600"></div>
                )}
                </button>
            ))}
            </div>
        
            <div className="p-6 md:p-8 bg-slate-50/50">
                {/* Tab Content */}
                {activeTab === "dashboard" && <UnderwritingDashboard analysis={analysis} />}

                {activeTab === "audit" && (
                <AuditTrailWidget auditTrail={(analysis.audit_trail as any) || []} />
                )}

                {activeTab === "export" && (
                 <div className="max-w-4xl mx-auto">
                    <ExportButtons analysis={analysis} />
                 </div>
                )}
            </div>
        </div>
      </main>
    </div>
  );
}
