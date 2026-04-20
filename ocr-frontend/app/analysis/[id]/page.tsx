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
  const extractedValues: Record<string, unknown> = {};
  data.historical_expenses?.forEach((item) => {
    const source = item.audit_log?.source || "Unknown";
    extractedValues[`[${source}] ${item.original_text}`] = item.amount;
  });
  console.log(`OCR Extracted Values (from ${sourceContext}):`, extractedValues);
  console.log(`📊 Historical Expenses Categorization (${data.historical_expenses?.length || 0} items)`);
  if (data.historical_expenses?.length > 0) {
    console.table(
      data.historical_expenses.map((item) => ({
        Category: item.mapped_category,
        "Original Text": item.original_text,
        Amount: item.amount,
        Source: item.audit_log?.source || "Unknown",
        Confidence: item.confidence,
      }))
    );
  }
  if (data.rent_roll_summary) {
    console.log(`🏠 Rent Roll Summary (${data.rent_roll_summary.total_units} units)`, {
      TotalUnits: data.rent_roll_summary.total_units,
      Occupied: data.rent_roll_summary.occupied_units,
      OccupancyRate: `${(data.rent_roll_summary.occupancy_rate * 100).toFixed(1)}%`,
      AnnualRent: data.rent_roll_summary.total_annual_rent,
    });
  }
  if ((data.historical_periods?.length ?? 0) > 0) {
    console.log(`🕒 Trailing Periods:`); console.table(data.historical_periods);
  }
  console.log("📈 Financial Metrics:", { NOI: data.pro_forma_noi, "Cap Rate": data.cap_rate, DSCR: data.dscr, Yield: data.debt_yield });
  if (data.explainability) {
    console.log("🧮 Calculation Logic:");
    Object.entries(data.explainability).forEach(([metric, details]) => {
      console.log(`  🔹 ${metric}:`, { Formula: details.calculation.formula, Inputs: details.calculation.inputs, Source: details.source });
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
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [isReanalyzing, setIsReanalyzing] = useState(false);
  const devReanalyzeEnabled = process.env.NEXT_PUBLIC_ENABLE_REANALYZE === "true";

  useEffect(() => {
    const tab = searchParams.get("tab");
    const rentRollTab = searchParams.get("rentRollTab");
    const rentRollEditMode = searchParams.get("rentRollEditMode");
    const trigger = searchParams.get("validationTrigger");
    if (tab === "export") setActiveTab("export");
    else if (tab === "dashboard") setActiveTab("dashboard");
    else if (tab === "verification") setActiveTab("verification");
    if (rentRollTab) setInitialRentRollTab(rentRollTab as "details" | "omExport" | "unitBreakdown" | "unitBreakdownStabilized");
    if (rentRollEditMode === "true") setInitialRentRollEditMode(true);
    if (trigger) setValidationTrigger(Number(trigger));
  }, [searchParams]);

  const eventSourceRef = useRef<EventSource | null>(null);
  const API_BASE_URL = process.env.NEXT_PUBLIC_FINANCIAL_API_URL;

  const closeEventSource = () => {
    if (eventSourceRef.current) { eventSourceRef.current.close(); eventSourceRef.current = null; }
  };

  const handleDevReanalyze = async () => {
    if (isReanalyzing) return;
    setIsReanalyzing(true);
    try {
      // Fire a full re-extraction (level 4). Returns instantly — work runs in background.
      await apiClient.devReanalyze(id, 4);
    } catch (err) {
      console.error("Failed to start re-analyze:", err);
      setIsReanalyzing(false);
      return;
    }
    // Redirect to processing page to show progress via SSE
    router.push(`/processing/${id}?reanalyze=4`);
  };

  const handleReanalyze = async (newParams: DealParameters) => {
    setIsLoading(true); setError(null);
    setProgress({ percentage: 0, message: "Restarting analysis..." });
    setAnalysis(null);
    closeEventSource();
    eventSourceRef.current = apiClient.streamFinancialAnalysisProgress(id, setProgress);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/multi-document/packages/${id}/analyze`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(newParams),
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(`Analysis failed: ${errorData.detail || `HTTP ${response.status}`}`);
      }
      const result: UnderwritingAnalysis = await response.json();
      setAnalysis(result); logInternalAuditReport(result, id, "Analysis"); setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch analysis results.");
    } finally { closeEventSource(); setIsLoading(false); }
  };

  useEffect(() => {
    if (!id) return;
    const fetchAnalysis = async () => {
      if (analysis && analysis.document_id === id && !isLoading) return;
      setIsLoading(true); setError(null);
      setProgress({ percentage: 0, message: "Starting analysis..." });
      closeEventSource();
      eventSourceRef.current = apiClient.streamFinancialAnalysisProgress(id, setProgress);
      try {
        const existingResp = await fetch(`${API_BASE_URL}/api/v1/multi-document/packages/${id}/analysis`);
        if (existingResp.ok) {
          const result = await existingResp.json();
          setAnalysis(result); logInternalAuditReport(result, id, "History");
          setError(null); setIsLoading(false); closeEventSource(); return;
        }
      } catch { /* proceed to run new analysis */ }
      try {
        let isPackage = false;
        try { const chk = await fetch(`${API_BASE_URL}/api/v1/multi-document/packages/${id}`); if (chk.ok) isPackage = true; } catch { /* */ }
        const defaultParams: DealParameters = { growth_rate: 0.03, exit_cap_rate: 0.06, vacancy_rate: 0.03, min_unit_count: 15, max_unit_count: 80, max_build_year: 1970 };
        const response = isPackage
          ? await fetch(`${API_BASE_URL}/api/v1/multi-document/packages/${id}/analyze`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(defaultParams) })
          : await fetch(`${API_BASE_URL}/api/v1/analysis/${id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ growth_rate: 0.03, exit_cap_rate: 0.06, vacancy_rate: 0.03 }) });
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: "Unknown error" }));
          throw new Error(`Analysis failed: ${errorData.detail || `HTTP ${response.status}`}`);
        }
        const result: UnderwritingAnalysis = await response.json();
        setAnalysis(result); logInternalAuditReport(result, id, "Analysis"); setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch analysis results.");
      } finally { setIsLoading(false); closeEventSource(); }
    };
    fetchAnalysis();
    return () => closeEventSource();
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Loading state ───────────────────────────────────────
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center p-4">
        <div className="bg-white border border-[#E2E8F0] p-10 rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.5)] max-w-md w-full text-center">
          <div className="mx-auto"><LoadingSpinner /></div>
          <h2 className="mt-6 text-xl font-bold text-[#0F172A]">Analyzing Deal…</h2>
          <p className="text-[#64748B] mt-1 text-sm">Processing financials and generating insights</p>
          <div className="mt-6 w-full bg-[#F1F5F9] rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-[#F97316] h-full rounded-full transition-all duration-500 ease-out shadow-[0_0_8px_rgba(249,115,22,0.5)]"
              style={{ width: `${progress.percentage}%` }}
            />
          </div>
          <p className="mt-3 text-sm font-semibold text-[#F97316] animate-pulse">{progress.message}</p>
          {progress.details?.current_file && (
            <p className="mt-1 text-xs text-[#64748B]">
              Processing: <span className="font-medium text-[#475569]">{progress.details.current_file}</span>
              {progress.details.total_files && <span className="ml-1">({progress.details.file_index}/{progress.details.total_files})</span>}
            </p>
          )}
          <p className="mt-1 text-xs text-[#64748B]">{progress.percentage}% complete</p>
        </div>
      </div>
    );
  }

  // ── Error state ─────────────────────────────────────────
  if (error) {
    const isLikelyPackage = error.includes("package") || error.includes("multi-document") || error.includes("Deal package");
    return (
      <div className="min-h-screen bg-[#F8FAFC] p-6 flex items-center justify-center">
        <div className="max-w-2xl w-full bg-white border border-[rgba(239,68,68,0.2)] rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.5)] p-8">
          <div className="flex items-start gap-5">
            <div className="w-12 h-12 bg-[rgba(239,68,68,0.12)] rounded-full flex items-center justify-center shrink-0">
              <svg className="h-6 w-6 text-[#EF4444]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-bold text-[#0F172A] mb-2">Analysis Failed</h2>
              <p className="text-[#EF4444] mb-5 font-mono text-xs bg-[rgba(239,68,68,0.06)] p-3 rounded-lg break-words border border-[rgba(239,68,68,0.15)]">{error}</p>
              <div className="bg-[#F1F5F9] border border-[#E2E8F0] p-4 rounded-xl mb-6 text-sm text-[#475569]">
                <p className="font-semibold text-[#64748B] mb-2 uppercase tracking-wide text-[10px]">Troubleshooting</p>
                <ul className="list-disc list-inside space-y-1.5 ml-1 text-xs">
                  <li>Ensure the financial-engine backend is running on <code className="bg-[#F1F5F9] px-1.5 py-0.5 rounded text-[#475569] border border-[#E2E8F0]">{API_BASE_URL}</code></li>
                  {isLikelyPackage ? (
                    <>
                      <li>Verify the deal package was successfully uploaded</li>
                      <li>Check the package ID: <code className="bg-[#F1F5F9] px-1.5 py-0.5 rounded text-[#475569] border border-[#E2E8F0]">{id}</code></li>
                    </>
                  ) : (
                    <>
                      <li>Verify the document was processed by the OCR backend</li>
                      <li>Check the document ID: <code className="bg-[#F1F5F9] px-1.5 py-0.5 rounded text-[#475569] border border-[#E2E8F0]">{id}</code></li>
                    </>
                  )}
                  <li>Verify network connectivity and firewall settings</li>
                </ul>
              </div>
              <div className="flex gap-3">
                <button onClick={() => router.push("/dashboard")} className="flex items-center gap-2 px-4 py-2.5 bg-[#F1F5F9] border border-[#E2E8F0] text-[#0F172A] rounded-lg hover:border-[#CBD5E1] transition-all text-sm font-medium">
                  ← Back to Deals
                </button>
                <button onClick={() => window.location.reload()} className="flex items-center gap-2 px-4 py-2.5 bg-[#F97316] hover:bg-[#EA6C0A] text-white rounded-lg transition-all text-sm font-medium shadow-[0_4px_14px_rgba(249,115,22,0.35)]">
                  Retry Analysis
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center">
        <div className="text-center p-10 bg-white border border-[#E2E8F0] rounded-xl">
          <p className="text-4xl mb-4">📂</p>
          <h3 className="text-base font-medium text-[#0F172A]">No analysis data found</h3>
          <button onClick={() => router.push("/dashboard")} className="mt-4 text-[#F97316] hover:underline text-sm font-medium">
            Return to Deals
          </button>
        </div>
      </div>
    );
  }

  const getStatusDisplay = (commentary?: string) => {
    const isRejected = commentary && /(reject|fail)/i.test(commentary);
    if (!isRejected) {
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
  const isPassing = getStatusDisplay(analysis.analyst_commentary).text === "CRITERIA MET";

  return (
    <div className={`min-h-screen overflow-hidden bg-[#F8FAFC] text-[#0F172A] flex relative ${sidebarExpanded ? "has-expanded-sidebar" : ""}`}>
      {/* Subtle grid */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#64748b08_1px,transparent_1px),linear-gradient(to_bottom,#64748b08_1px,transparent_1px)] bg-[size:32px_32px]" />
      </div>

      <Sidebar sidebarExpanded={sidebarExpanded} toggleSidebar={() => setSidebarExpanded(!sidebarExpanded)} isChatMode={false} messages={[]} onNewChat={() => {}} />

      <div className={`flex flex-col flex-1 transition-all duration-300 h-screen relative z-10 ${sidebarExpanded ? "ml-56" : "ml-[72px]"}`}>

        {/* ── Top Bar ──────────────────────────────────── */}
        <header className="shrink-0 sticky top-0 z-40 bg-white border-b border-[#E2E8F0]">
          {/* Main header row */}
          <div className="h-14 flex items-center justify-between px-6 lg:px-8">
            <div className="flex items-center gap-3 min-w-0">
              <button
                onClick={() => activeTab !== "dashboard" ? setActiveTab("dashboard") : router.push("/dashboard")}
                className="text-[#64748B] hover:text-[#475569] transition-colors shrink-0"
                aria-label="Go back"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="m12 19-7-7 7-7" /><path d="M19 12H5" />
                </svg>
              </button>

              <div className="h-4 w-px bg-[#E2E8F0] shrink-0" />

              <div className="flex items-center gap-2.5 min-w-0">
                <h1 className="text-sm font-semibold text-[#0F172A] truncate">
                  {analysis.property_meta?.address || "Financial Analysis"}
                </h1>
                {/* Status badge */}
                <span className={`shrink-0 inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide ${
                  isPassing
                    ? "bg-[rgba(34,197,94,0.12)] text-[#22C55E] border border-[rgba(34,197,94,0.2)]"
                    : "bg-[rgba(239,68,68,0.12)] text-[#EF4444] border border-[rgba(239,68,68,0.2)]"
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${isPassing ? "bg-[#22C55E]" : "bg-[#EF4444] animate-pulse"}`} />
                  {isPassing ? "CRITERIA MET" : "CRITERIA NOT MET"}
                </span>
              </div>
            </div>

            {/* Right actions */}
            <div className="flex items-center gap-2 shrink-0">
              {/* Ghost action buttons */}
              {(["verification", "audit", "export"] as const).map((tab) => {
                const labels: Record<string, string> = { verification: "Verify Data", audit: "Audit Trail", export: "Export" };
                const icons: Record<string, React.ReactNode> = {
                  verification: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 11l3 3L22 4M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />,
                  audit: <><path strokeLinecap="round" strokeLinejoin="round" d="M3 12a9 9 0 109-9 9.76 9.76 0 00-4.7 8.5M3 12h9m-9 0v9" /></>,
                  export: <><path strokeLinecap="round" strokeLinejoin="round" d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" x2="12" y1="15" y2="3" /></>,
                };
                return (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border ${
                      activeTab === tab
                        ? "bg-[#F97316] text-white border-transparent shadow-[0_2px_8px_rgba(249,115,22,0.35)]"
                        : "text-[#475569] border-[#E2E8F0] hover:border-[#CBD5E1] hover:text-[#0F172A] hover:bg-[#F1F5F9]"
                    }`}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">{icons[tab]}</svg>
                    {labels[tab]}
                  </button>
                );
              })}

              {devReanalyzeEnabled && (
                <button
                  onClick={handleDevReanalyze}
                  disabled={isReanalyzing}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border border-[#7C3AED] text-[#7C3AED] hover:bg-[rgba(124,58,237,0.08)] disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {isReanalyzing ? (
                    <>
                      <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="animate-spin">
                        <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                      </svg>
                      Starting…
                    </>
                  ) : (
                    <>
                      <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2v6h-6" /><path d="M3 12a9 9 0 0 1 15-6.7L21 8" /><path d="M3 22v-6h6" /><path d="M21 12a9 9 0 0 1-15 6.7L3 16" /></svg>
                      Re-Analyze
                    </>
                  )}
                </button>
              )}

              <button
                onClick={() => router.push("/upload-package")}
                className="flex items-center gap-1.5 bg-[#F97316] hover:bg-[#EA6C0A] text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition-all shadow-[0_2px_8px_rgba(249,115,22,0.35)]"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14" /><path d="M12 5v14" />
                </svg>
                New Analysis
              </button>
            </div>
          </div>

          {/* Breadcrumb row */}
          <div className="px-6 lg:px-8 pb-2 flex items-center gap-1.5 text-[10px] text-[#94A3B8]">
            <span className="hover:text-[#475569] cursor-pointer transition-colors" onClick={() => router.push("/dashboard")}>Deals</span>
            <span>/</span>
            <span className="text-[#64748B]">Analysis</span>
          </div>
        </header>

        {/* ── Main workspace ──────────────────────────── */}
        <main className="flex-1 overflow-y-auto no-scrollbar p-4 lg:p-6">
          <div className="max-w-[1280px] mx-auto flex flex-col gap-6">

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
                  setAnalysis(newAnalysis);
                  setHasUnsavedChanges(false);
                  setActiveTab("dashboard");
                }}
                onDataChange={() => setHasUnsavedChanges(true)}
              />
            )}

            {activeTab === "audit" && (
              <AuditTrailWidget auditTrail={analysis.audit_trail || []} packageId={id} />
            )}

            {activeTab === "export" && (
              <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-[var(--shadow-card)] p-6">
                <ExportButtons
                  analysis={analysis}
                  onAnalysisUpdate={(newAnalysis) => setAnalysis(newAnalysis)}
                />
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Unsaved changes toast */}
      {activeTab === "verification" && hasUnsavedChanges && (
        <div className={`fixed right-6 z-[60] bg-white border border-[#E2E8F0] text-[#0F172A] px-4 py-3 rounded-xl shadow-[0_10px_40px_rgba(0,0,0,0.5)] max-w-sm text-xs font-medium transition-all duration-300 ${isChatOpen ? "bottom-[660px]" : "bottom-[84px]"}`}>
          <div className="flex gap-2 items-start">
            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 mt-0.5 text-[#F97316]">
              <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <p className="leading-relaxed text-[#475569]">
              Changes made. Scroll to top and click <span className="text-[#F97316] font-semibold">&apos;Save and Regenerate&apos;</span> to update the report.
            </p>
          </div>
        </div>
      )}

      <ReportChatWidget documentId={id} onOpenChange={setIsChatOpen} />
    </div>
  );
}
