"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { UnderwritingAnalysis, FinancialAnalysisProgress, DealParameters } from "@/lib/types";
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
  const [activeTab, setActiveTab] = useState<"dashboard" | "audit" | "export">("dashboard");
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  
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
  }, [id, API_BASE_URL]);

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
                    className="inline-flex items-center px-6 py-3 bg-neutral-800 text-white rounded-lg hover:bg-neutral-900 transition-colors font-medium"
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

      {/* Left Sidebar */}
      <nav 
        className={`fixed z-50 flex flex-col bg-white/80 border-neutral-100/80 border-r pt-6 pb-6 top-0 bottom-0 left-0 backdrop-blur-xl justify-between transition-all duration-400 ${
          sidebarExpanded ? 'w-64' : 'w-[72px]'
        }`}
      >
        <div className="flex flex-col items-center gap-6 w-full">
          <div className={`flex items-center w-full px-2 min-h-[40px] relative ${sidebarExpanded ? 'justify-between px-4' : 'justify-center'}`}>
            <div 
              className="relative flex items-center justify-center w-10 h-10 shrink-0 rounded-xl cursor-pointer"
              onClick={() => !sidebarExpanded && setSidebarExpanded(true)}
            >
              <div className="text-neutral-900">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"></path>
                  <path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"></path>
                  <path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"></path>
                  <path d="M10 6h4"></path>
                  <path d="M10 10h4"></path>
                  <path d="M10 14h4"></path>
                  <path d="M10 18h4"></path>
                </svg>
              </div>
            </div>
            {sidebarExpanded && (
              <button 
                onClick={() => setSidebarExpanded(false)}
                className="text-neutral-400 hover:text-neutral-600 transition-colors p-1"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <rect width="18" height="18" x="3" y="3" rx="2" ry="2"></rect>
                  <path d="M9 3v18"></path>
                </svg>
              </button>
            )}
          </div>

          <div className="w-8 h-[1px] bg-neutral-100"></div>

          <div className="flex flex-col gap-2 w-full px-2">
            <a 
              href="/dashboard" 
              className={`group relative flex items-center p-2.5 rounded-lg text-neutral-900 bg-neutral-100 transition-all ${
                sidebarExpanded ? 'justify-start px-4' : 'justify-center'
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 stroke-[1.5]">
                <rect width="7" height="7" x="3" y="3" rx="1"></rect>
                <rect width="7" height="7" x="14" y="3" rx="1"></rect>
                <rect width="7" height="7" x="14" y="14" rx="1"></rect>
                <rect width="7" height="7" x="3" y="14" rx="1"></rect>
              </svg>
              {sidebarExpanded && <span className="ml-3 font-normal text-sm">Deals</span>}
            </a>
          </div>
        </div>

        <div className="flex flex-col items-center gap-4 w-full px-2">
          <button className={`group relative flex items-center p-2.5 rounded-lg text-neutral-400 hover:text-neutral-900 hover:bg-neutral-50 transition-all ${
            sidebarExpanded ? 'justify-start px-4 w-full' : 'justify-center'
          }`}>
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 stroke-[1.5]">
              <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.72l-.15.1a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.38a2 2 0 0 0-.73-2.73l-.15-.1a2 2 0 0 1-1-1.72v-.51a2 2 0 0 1 1-1.72l.15-.1a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"></path>
              <circle cx="12" cy="12" r="3"></circle>
            </svg>
            {sidebarExpanded && <span className="ml-3 font-normal text-sm">Settings</span>}
          </button>
        </div>
      </nav>

      {/* Content Wrapper */}
      <div className={`flex flex-col flex-1 transition-all duration-300 h-screen relative z-10 bg-neutral-50/50 ${
        sidebarExpanded ? 'pl-64' : 'pl-[72px]'
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
              className="text-neutral-500 hover:text-neutral-900 transition-colors"
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
              onClick={() => router.push(`/verification/${id}`)}
              className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium text-neutral-600 hover:bg-neutral-100 transition-all border border-transparent hover:border-neutral-200"
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
              />
            )}

            {activeTab === "audit" && (
              <AuditTrailWidget auditTrail={analysis.audit_trail || []} />
            )}

            {activeTab === "export" && (
              <div className="bg-white rounded-xl border border-neutral-200 shadow-sm p-6">
                <ExportButtons analysis={analysis} />
              </div>
            )}
          </div>
        </main>
      </div>

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
