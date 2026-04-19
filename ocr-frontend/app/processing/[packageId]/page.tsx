"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import Sidebar from "@/components/Sidebar";
import LoadingSpinner from "@/components/LoadingSpinner";
import LoginPage from "@/components/LoginPage";
import FileOrganization, { DocumentFile } from "@/components/FileOrganization";
import { apiClient } from "@/lib/api";
import { FinancialAnalysisProgress, DealPackage } from "@/lib/types";

interface DocumentCategory {
  name: string;
  count: number;
  completedCount: number;
  status: 'completed' | 'processing' | 'queued';
  fileNames: string[];
  categoryProgress?: number; // 0-100 per-category percentage from backend
}

function ProcessingContent() {
  const { user } = useAuth();
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const packageId = params.packageId as string;
  const reanalyzeLevel = searchParams.get("reanalyze") ? parseInt(searchParams.get("reanalyze")!, 10) as 1 | 2 | 3 | 4 : null;
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [progress, setProgress] = useState<FinancialAnalysisProgress>({ percentage: 0, message: reanalyzeLevel ? `Re-analyzing (level ${reanalyzeLevel})...` : "Starting normalization..." });
  const [dealPackage, setDealPackage] = useState<DealPackage | null>(null);
  const [categories, setCategories] = useState<DocumentCategory[]>([]);
  const [activeFiles, setActiveFiles] = useState<string[]>([]);
  const [isReviewing, setIsReviewing] = useState(!reanalyzeLevel);
  const [startProcessing, setStartProcessing] = useState(false);
  // "attach_only" means we connect to SSE but don't POST /normalize (resuming in-progress work)
  const [attachOnly, setAttachOnly] = useState(false);
  const [processingFailed, setProcessingFailed] = useState(false);
  const [failedMessage, setFailedMessage] = useState("");

  const toggleSidebar = () => {
    setSidebarExpanded(!sidebarExpanded);
  };

  // Build categories from package documents data
  const buildCategories = (documents: Record<string, any[]>): DocumentCategory[] => {
    return Object.entries(documents).map(([type, docs]) => {
      let docArray = Array.isArray(docs) ? docs : [];

      // Filter out system files and unsupported types that won't be processed
      docArray = docArray.filter((d: any) => {
         const lowerName = d.filename.toLowerCase();
         return !lowerName.endsWith('thumbs.db') &&
                !lowerName.endsWith('desktop.ini') &&
                !lowerName.endsWith('.ds_store') &&
                !d.filename.startsWith('.') &&
                !d.filename.includes('__MACOSX');
      });

      return {
        name: type,
        count: docArray.length,
        completedCount: 0,
        status: 'queued' as const,
        fileNames: docArray.map((d: any) => d.filename)
      };
    });
  };

  // Fetch package details and determine what screen to show
  const fetchPackage = useCallback(async () => {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_FINANCIAL_API_URL}/api/v1/multi-document/packages/${packageId}?t=${Date.now()}`,
        { cache: 'no-store' }
      );
      if (response.ok) {
        const data = await response.json();
        console.log("Fetched package data for processing:", data);
        setDealPackage(data);
        setCategories(buildCategories(data.documents));

        const status = data.normalization_status;

        // Explicit handling for every possible normalization_status.
        // When a re-analyze was just triggered, the backend flips status to
        // "in_progress" synchronously before returning — but there's still a
        // brief window where the MongoDB read races the flip. Skip the
        // completed-redirect in that case so we don't bounce the user back.
        if (status === "completed" && !reanalyzeLevel) {
          console.log("Package already completed, redirecting to analysis page...");
          router.push(`/analysis/${packageId}`);
          return true;
        }

        if (status === "in_progress") {
          console.log("Package in progress, attaching to existing SSE stream...");
          // Fetch current progress from Redis to initialize state before SSE connects
          try {
            const currentProgress = await apiClient.getCurrentProgress(packageId);
            if (currentProgress && currentProgress.percentage > 0) {
              setProgress(currentProgress);
              console.log(`Resuming at ${currentProgress.percentage}%: ${currentProgress.message}`);
            } else {
              setProgress({ percentage: 0, message: "Resuming..." });
            }
          } catch {
            setProgress({ percentage: 0, message: "Resuming..." });
          }
          setIsReviewing(false);
          setAttachOnly(true);
          setStartProcessing(true);
          return false;
        }

        if (status === "failed") {
          console.log("Package processing previously failed.");
          setProcessingFailed(true);
          setFailedMessage("Previous processing attempt failed. You can retry.");
          setIsReviewing(false);
          return false;
        }

        if (reanalyzeLevel) {
          // Re-analyze was triggered by the analysis page — just attach to SSE
          // (the background task may not have updated the status yet)
          setIsReviewing(false);
          setAttachOnly(true);
          setStartProcessing(true);
        } else if (!startProcessing) {
          // status === "pending" (or any unknown value) → show review screen
          setIsReviewing(true);
        }

        return false;
      }
    } catch (err) {
      console.error("Failed to fetch package:", err);
    }
    return false;
  }, [packageId, router, startProcessing, reanalyzeLevel]);

  useEffect(() => {
    if (!dealPackage) {
        fetchPackage();
    }
  }, [dealPackage, fetchPackage]);

  // Retry handler for failed state
  const handleRetry = async () => {
    setProcessingFailed(false);
    setFailedMessage("");
    // Reset status to pending in backend so dedup guard allows re-run
    try {
      await fetch(
        `${process.env.NEXT_PUBLIC_FINANCIAL_API_URL}/api/v1/multi-document/packages/${packageId}/reset-status`,
        { method: "POST" }
      );
    } catch {
      // If reset endpoint doesn't exist, the normalize endpoint will handle it
    }
    setProgress({ percentage: 0, message: "Starting normalization..." });
    setAttachOnly(false);
    // Toggle off then on to ensure the useEffect re-fires even if startProcessing was already true
    setStartProcessing(false);
    setTimeout(() => setStartProcessing(true), 0);
  };

  const handleReviewComplete = async (updatedFiles?: Record<string, DocumentFile[]>) => {
      // Force refresh of package data before starting
      await fetchPackage();

      // If we have updated files from the review component, update categories to reflect user's changes
      if (updatedFiles) {
          console.log("Using locally updated files for categories summary");
          const cats: DocumentCategory[] = Object.entries(updatedFiles).map(([type, docs]) => {
              return {
                  name: type,
                  count: docs.length,
                  completedCount: 0,
                  status: 'queued' as const,
                  fileNames: docs.map(d => d.name)
              };
          });
          setCategories(cats);
      }

      setIsReviewing(false);
      setAttachOnly(false);
      setStartProcessing(true);
  };

  // SSE progress handler — extracted so both "new" and "attach" paths use the same logic
  const createProgressHandler = (eventSourceRef: { current: EventSource | null }) => {
    let hasRedirected = false;

    return (progressUpdate: FinancialAnalysisProgress) => {
      setProgress(prev => {
        if (progressUpdate.message === "Connecting..." && prev.percentage > 0) {
          return prev;
        }
        if (progressUpdate.percentage > prev.percentage || prev.percentage === 0 || progressUpdate.percentage === prev.percentage) {
          return progressUpdate;
        }
        return prev;
      });

      // Update active files and categories
      if (progressUpdate.details) {
        const active = (progressUpdate.details.active_files as string[]) || [];
        const completed = (progressUpdate.details.completed_files as string[]) || [];

        // Merge active files rather than replacing — only remove files that
        // have moved to completed, and add any new ones.  This prevents
        // flickering when rapid SSE updates briefly report an empty active list
        // between file transitions.
        setActiveFiles(prev => {
          const completedSet = new Set(completed);
          // Keep previously active files that haven't completed yet, add new ones
          const merged = new Set([...prev.filter(f => !completedSet.has(f)), ...active]);
          const next = Array.from(merged);
          if (JSON.stringify([...prev].sort()) !== JSON.stringify(next.sort())) {
            return next;
          }
          return prev;
        });

        setCategories(prevCats => {
          return prevCats.map(cat => {
            const catCompletedCount = cat.fileNames.filter(f => completed.includes(f)).length;
            const isProcessing = cat.fileNames.some(f => active.includes(f));

            // Never regress status: completed stays completed, processing never goes back to queued
            let newStatus = cat.status;
            if (cat.status === 'completed') {
              // Once completed, never regress (subsequent extraction steps may
              // send progress updates that don't include this category's files)
              newStatus = 'completed';
            } else if (catCompletedCount === cat.count && cat.count > 0) {
              newStatus = 'completed';
            } else if (isProcessing || catCompletedCount > 0) {
              newStatus = 'processing';
            } else if (cat.status !== 'processing') {
              newStatus = 'queued';
            }

            // Compute per-category percentage from this category's own
            // completed/total counts instead of using the shared backend key,
            // which lumps multiple categories (e.g. all non-OM docs) together.
            let categoryPct: number | undefined;
            if (newStatus === 'processing' && cat.count > 0) {
              categoryPct = Math.round((catCompletedCount / cat.count) * 100);
            }

            return {
              ...cat,
              completedCount: catCompletedCount,
              status: newStatus,
              categoryProgress: categoryPct,
            };
          });
        });
      }

      // Check if processing failed (negative percentage from background task)
      if (progressUpdate.percentage < 0) {
        if (eventSourceRef.current) eventSourceRef.current.close();
        setProcessingFailed(true);
        setFailedMessage(progressUpdate.message || "Processing failed");
        return;
      }

      // Check if processing is complete (100%)
      if (progressUpdate.percentage >= 100 && !hasRedirected) {
        hasRedirected = true;
        console.log("Processing complete, redirecting to analysis page...");

        setCategories(prev => prev.map(cat => ({ ...cat, status: 'completed', completedCount: cat.count })));
        setActiveFiles([]);

        setTimeout(() => {
          if (eventSourceRef.current) eventSourceRef.current.close();
          router.push(`/analysis/${packageId}`);
        }, 1500);
      }
    };
  };

  useEffect(() => {
    if (!startProcessing) return;

    const eventSourceRef: { current: EventSource | null } = { current: null };
    const progressHandler = createProgressHandler(eventSourceRef);

    // Always connect to SSE stream
    eventSourceRef.current = apiClient.streamFinancialAnalysisProgress(packageId, progressHandler);

    // Fire the backend call — only for normal flow (re-analyze is triggered by the analysis page)
    if (!attachOnly && !reanalyzeLevel) {
      // Normal flow: POST /normalize for new processing runs
      (async () => {
        try {
          const response = await fetch(
            `${process.env.NEXT_PUBLIC_FINANCIAL_API_URL}/api/v1/multi-document/packages/${packageId}/normalize`,
            { method: "POST" }
          );

          if (response.status === 409) {
            // Already in progress — SSE will pick up current state, nothing to do
            console.log("Normalization already in progress (409), attached to SSE stream.");
            return;
          }

          if (!response.ok) {
            throw new Error("Failed to normalize documents");
          }
        } catch (err) {
          console.error("Normalization failed:", err);
          if (eventSourceRef.current) eventSourceRef.current.close();
          setProcessingFailed(true);
          setFailedMessage(String(err));
        }
      })();
    }

    return () => {
      if (eventSourceRef.current) {
        console.log("Cleaning up EventSource");
        eventSourceRef.current.close();
      }
    };
  }, [packageId, router, startProcessing, attachOnly, reanalyzeLevel]);

  return (
    <div className={`min-h-screen overflow-hidden relative bg-[#F8FAFC] text-[#0F172A] flex ${sidebarExpanded ? "has-expanded-sidebar" : ""}`}>
      {/* Subtle grid */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#64748b08_1px,transparent_1px),linear-gradient(to_bottom,#64748b08_1px,transparent_1px)] bg-[size:32px_32px]" />
      </div>

      <Sidebar sidebarExpanded={sidebarExpanded} toggleSidebar={toggleSidebar} isChatMode={false} messages={[]} onNewChat={() => {}} />

      <div className={`flex flex-col flex-1 min-w-0 transition-all duration-300 h-screen relative z-10 ${sidebarExpanded ? "ml-56" : "ml-[72px]"}`}>

        {/* Top Bar */}
        <header className="h-14 border-b border-[#E2E8F0] bg-white shrink-0 sticky top-0 z-40 flex items-center px-6 lg:px-8 justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => router.push("/dashboard")} className="text-[#64748B] hover:text-[#475569] transition-colors" aria-label="Go back">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m12 19-7-7 7-7" /><path d="M19 12H5" />
              </svg>
            </button>
            <div className="h-4 w-px bg-[#2A3347]" />
            <nav className="flex items-center gap-1.5 text-xs text-[#64748B]">
              <span className="hover:text-[#475569] cursor-pointer" onClick={() => router.push("/dashboard")}>Deals</span>
              <span>/</span>
              <span className="text-[#0F172A] font-medium">
                {isReviewing ? "Organize Files" : reanalyzeLevel ? "Re-Analyzing" : "Processing Documents"}
              </span>
            </nav>
          </div>

          <div className="flex items-center gap-2">
            {!isReviewing && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[rgba(245,158,11,0.08)] border border-[rgba(245,158,11,0.2)]">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#F59E0B] opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#F59E0B]" />
                </span>
                <span className="text-[9px] font-semibold text-[#F59E0B] uppercase tracking-wider">Processing</span>
              </div>
            )}
          </div>
        </header>

        {/* Main Workspace */}
        <main className="flex-1 overflow-y-auto no-scrollbar p-6 lg:p-8 min-w-0">
          <div className={`mx-auto flex flex-col gap-6 ${isReviewing ? "max-w-[95%]" : "max-w-5xl"}`}>

            {processingFailed ? (
              <div className="max-w-xl mx-auto flex flex-col items-center gap-6 py-16">
                <div className="w-14 h-14 rounded-full bg-[rgba(239,68,68,0.12)] flex items-center justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[#EF4444]">
                    <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
                  </svg>
                </div>
                <div className="text-center">
                  <h2 className="text-xl font-semibold text-[#0F172A] mb-2">Processing Failed</h2>
                  <p className="text-sm text-[#64748B]">{failedMessage || "An error occurred during document processing."}</p>
                </div>
                <button
                  onClick={handleRetry}
                  className="px-5 py-2.5 rounded-lg bg-[#0F172A] text-white text-sm font-medium hover:bg-[#1E293B] transition-colors"
                >
                  Retry Processing
                </button>
              </div>
            ) : isReviewing && dealPackage ? (
              <FileOrganization
                packageId={packageId}
                initialPackage={dealPackage}
                onComplete={handleReviewComplete}
              />
            ) : (
              <>
                {/* Page title */}
                <div className="flex pb-5 border-b border-[#E2E8F0] items-end justify-between">
                  <div>
                    <h2 className="text-xl font-semibold text-[#0F172A] tracking-tight mb-1">
                      Data Extraction &amp; Categorization
                    </h2>
                    <p className="text-sm text-[#64748B]">Extracting and categorizing information from your deal package in parallel.</p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span className="text-[9px] uppercase font-semibold text-[#64748B] tracking-widest">Package ID</span>
                    <span className="text-xs font-mono text-[#475569] bg-[#F1F5F9] border border-[#E2E8F0] px-2 py-1 rounded select-all cursor-text">{packageId}</span>
                  </div>
                </div>

                {/* Content Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">

                  {/* Left: Progress Card */}
                  <div className="lg:col-span-5 flex flex-col gap-5">
                    <div className="bg-white p-6 rounded-xl border border-[#E2E8F0] shadow-[var(--shadow-card)] flex flex-col justify-between min-h-[240px]">
                      <div>
                        <div className="flex items-end gap-2 mb-3">
                          <span className="text-5xl font-semibold text-[#0F172A] tracking-tighter font-mono">{Math.round(progress.percentage)}%</span>
                          <span className="text-sm font-medium text-[#64748B] mb-1.5">complete</span>
                        </div>
                        <div className="w-full bg-[#F1F5F9] h-1.5 rounded-full overflow-hidden mb-5">
                          <div
                            className="bg-[#F97316] h-full rounded-full transition-all duration-300 shadow-[0_0_8px_rgba(249,115,22,0.5)]"
                            style={{ width: `${progress.percentage}%` }}
                          />
                        </div>
                      </div>

                      <div className="space-y-3">
                        {progress.percentage > 0 && progress.percentage < 100 && activeFiles.length === 0 && (
                          <div className={`flex items-center gap-2 p-2.5 rounded-lg ${
                            progress.percentage >= 80
                              ? "bg-[rgba(16,185,129,0.08)] border border-[rgba(16,185,129,0.15)]"
                              : progress.percentage >= 60
                              ? "bg-[rgba(59,130,246,0.08)] border border-[rgba(59,130,246,0.15)]"
                              : "bg-[rgba(249,115,22,0.08)] border border-[rgba(249,115,22,0.15)]"
                          }`}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={`shrink-0 animate-spin ${
                              progress.percentage >= 80 ? "text-[#10B981]" : progress.percentage >= 60 ? "text-[#60A5FA]" : "text-[#F97316]"
                            }`}>
                              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                            </svg>
                            <span className={`text-xs font-medium ${
                              progress.percentage >= 80 ? "text-[#10B981]" : progress.percentage >= 60 ? "text-[#60A5FA]" : "text-[#F97316]"
                            }`}>
                              {progress.percentage >= 60
                                ? progress.message
                                : progress.percentage >= 40 ? "Normalizing Extracted Data…"
                                : progress.percentage >= 15 ? "Extracting Data from Documents…"
                                : progress.message || "Preparing Documents…"}
                            </span>
                          </div>
                        )}
                        {progress.percentage >= 100 && (
                          <div className="flex items-center gap-2 p-2.5 bg-[rgba(16,185,129,0.08)] border border-[rgba(16,185,129,0.15)] rounded-lg">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[#10B981] shrink-0">
                              <path d="M20 6 9 17l-5-5" />
                            </svg>
                            <span className="text-xs font-medium text-[#10B981]">Analysis complete — redirecting…</span>
                          </div>
                        )}

                        {activeFiles.length > 0 && progress.percentage < 90 && (
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center justify-between">
                              <span className="text-[10px] font-semibold text-[#64748B] uppercase tracking-widest">Queue ({activeFiles.length})</span>
                              <span className="text-[10px] text-[#64748B] flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B] animate-pulse" />Live
                              </span>
                            </div>
                            <div className="flex flex-col gap-1.5 max-h-40 overflow-y-auto custom-scrollbar pr-1">
                              {activeFiles.map((file, idx) => (
                                <div key={idx} className="flex items-center gap-2.5 p-2 bg-[#F1F5F9] border border-[#E2E8F0] rounded-lg">
                                  <div className="shrink-0 w-7 h-7 rounded bg-[#2A3347] flex items-center justify-center">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[#F59E0B] animate-spin">
                                      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                                    </svg>
                                  </div>
                                  <div className="flex flex-col min-w-0">
                                    <span className="text-xs font-medium text-[#0F172A] truncate">{file}</span>
                                    <span className="text-[10px] text-[#64748B]">Extracting data…</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {progress.details?.total_files && (
                          <div className="flex items-center justify-between text-xs text-[#64748B] pt-3 border-t border-[#E2E8F0]">
                            <span>Overall Progress</span>
                            <span className="font-medium text-[#475569]">{progress.details.file_index || 0} of {progress.details.total_files} files</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Right: Document Summary */}
                  <div className="lg:col-span-7">
                    <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-[var(--shadow-card)] overflow-hidden">
                      <div className="px-5 py-3.5 border-b border-[#E2E8F0] bg-[#F1F5F9] flex items-center justify-between">
                        <h3 className="text-sm font-semibold text-[#0F172A] flex items-center gap-2">
                          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-[#64748B]">
                            <path d="M15.5 2H8.6c-.4 0-.8.2-1.1.5-.3.3-.5.7-.5 1.1v12.8c0 .4.2.8.5 1.1.3.3.7.5 1.1.5h9.8c.4 0 .8-.2 1.1-.5.3-.3.5-.7.5-1.1V6.5L15.5 2z" />
                            <path d="M3 7.6v12.8c0 .4.2.8.5 1.1.3.3.7.5 1.1.5h9.8" /><path d="M15 2v5h5" />
                          </svg>
                          Document Summary
                        </h3>
                        <span className="text-[10px] text-[#64748B]">{categories.length} categories</span>
                      </div>

                      <div className="divide-y divide-[#E2E8F0]">
                        {categories.map((category) => (
                          <div
                            key={category.name}
                            title={category.fileNames.join("\n")}
                            className={`px-5 py-3 flex items-center justify-between cursor-help transition-colors hover:bg-[#F1F5F9] ${
                              category.status === "processing" ? "border-l-2 border-l-[#F97316]" : "border-l-2 border-l-transparent"
                            } ${category.status === "queued" ? "opacity-50" : ""}`}
                          >
                            <div className="flex items-center gap-3">
                              <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                                category.status === "completed" ? "bg-[rgba(34,197,94,0.12)] text-[#22C55E]" :
                                category.status === "processing" ? "bg-[rgba(249,115,22,0.12)] text-[#F97316]" :
                                "bg-[#F1F5F9] text-[#64748B]"
                              }`}>
                                {category.status === "completed" && category.count > 0 && <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M20 6 9 17l-5-5" /></svg>}
                                {category.status === "completed" && category.count === 0 && <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[#F59E0B]"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>}
                                {category.status === "processing" && <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin"><path d="M21 12a9 9 0 1 1-6.219-8.56" /></svg>}
                                {category.status === "queued" && <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>}
                              </div>
                              <div>
                                <p className="text-sm font-medium text-[#0F172A]">{category.name}</p>
                                <p className="text-[10px] text-[#64748B] font-mono">
                                  {category.completedCount} / {category.count} processed
                                  {category.status === 'processing' && category.categoryProgress != null && category.categoryProgress < 100 && (
                                    <span className="ml-1.5 text-[#F97316]">&middot; {Math.round(category.categoryProgress)}%</span>
                                  )}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              {category.status === "completed" && category.count > 0 && <span className="px-2 py-0.5 rounded-full text-[9px] font-semibold bg-[rgba(34,197,94,0.12)] text-[#22C55E] border border-[rgba(34,197,94,0.2)]">Analyzed</span>}
                              {category.status === "completed" && category.count === 0 && <span className="px-2 py-0.5 rounded-full text-[9px] font-semibold bg-[rgba(245,158,11,0.12)] text-[#F59E0B] border border-[rgba(245,158,11,0.2)]">Missing</span>}
                              {category.status === "processing" && <span className="px-2 py-0.5 rounded-full text-[9px] font-semibold bg-[rgba(249,115,22,0.12)] text-[#F97316] border border-[rgba(249,115,22,0.2)]">Processing</span>}
                              {category.status === "queued" && <span className="text-[9px] font-medium text-[#64748B]">Queued</span>}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </>
            )}

            <div className="h-8" />
          </div>
        </main>
      </div>

    </div>
  );
}

export default function ProcessingPage() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return isAuthenticated ? <ProcessingContent /> : <LoginPage />;
}
