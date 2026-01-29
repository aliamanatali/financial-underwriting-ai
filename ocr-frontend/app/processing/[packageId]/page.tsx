"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import Sidebar from "@/components/Sidebar";
import LoadingSpinner from "@/components/LoadingSpinner";
import LoginPage from "@/components/LoginPage";
import { apiClient } from "@/lib/api";
import { FinancialAnalysisProgress, DealPackage } from "@/lib/types";

interface DocumentCategory {
  name: string;
  count: number;
  status: 'completed' | 'processing' | 'queued';
}

function ProcessingContent() {
  const { user } = useAuth();
  const params = useParams();
  const router = useRouter();
  const packageId = params.packageId as string;
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [progress, setProgress] = useState<FinancialAnalysisProgress>({ percentage: 0, message: "Starting normalization..." });
  const [dealPackage, setDealPackage] = useState<DealPackage | null>(null);
  const [categories, setCategories] = useState<DocumentCategory[]>([]);
  const [missingDocs, setMissingDocs] = useState<string[]>([]);
  const [isUploadingMissing, setIsUploadingMissing] = useState(false);
  const missingFileInputRef = useRef<HTMLInputElement>(null);

  const toggleSidebar = () => {
    setSidebarExpanded(!sidebarExpanded);
  };

  const handleMissingFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const files = Array.from(e.target.files);
      setIsUploadingMissing(true);
      try {
        await apiClient.uploadAdditionalDocuments(packageId, files);
        // Reload page to restart processing with new files
        window.location.reload();
      } catch (err) {
        console.error("Failed to upload additional documents:", err);
        alert("Failed to upload documents. Please try again.");
        setIsUploadingMissing(false);
      }
    }
  };

  useEffect(() => {
    // Fetch package details
    const fetchPackage = async () => {
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_FINANCIAL_API_URL}/api/v1/multi-document/packages/${packageId}`
        );
        if (response.ok) {
          const data = await response.json();
          setDealPackage(data);
          
          // Build categories from documents
          const cats: DocumentCategory[] = Object.entries(data.documents).map(([type, docs]) => ({
            name: type,
            count: Array.isArray(docs) ? docs.length : 0,
            status: 'queued' as const
          }));
          setCategories(cats);
          
          // Check for missing critical documents
          const requiredDocs = ["Offering Memorandum", "Rent Roll", "Financials"];
          const missing = requiredDocs.filter(req => {
              const hasDocs = Object.entries(data.documents).some(([key, docs]) =>
                  key.includes(req) && Array.isArray(docs) && docs.length > 0
              );
              return !hasDocs;
          });
          
          if (missing.length > 0) {
              setMissingDocs(missing);
              // If missing docs, pause here (don't redirect even if completed)
              // But we should allow user to proceed if they want?
              // For now, let's block auto-redirect.
              return true; // Return true to signal "stop/handled", effectively pausing normalization loop start if we wanted
          }

          // Check if package is already normalized
          if (data.normalization_status === "completed" || data.normalization_status === "in_progress") {
            console.log("Package already normalized, redirecting to analysis page...");
            // Redirect immediately to analysis page
            router.push(`/analysis/${packageId}`);
            return true; // Signal that we're redirecting
          }
          
          return false; // Signal to continue with normalization
        }
      } catch (err) {
        console.error("Failed to fetch package:", err);
      }
      return false;
    };

    // Start normalization and progress tracking
    const startNormalization = async () => {
      // First check if already normalized
      const shouldSkip = await fetchPackage();
      if (shouldSkip) {
        return; // Don't start normalization if already done
      }
      let hasRedirected = false;
      let eventSource: EventSource | null = null;
      
      // Start progress stream
      eventSource = apiClient.streamFinancialAnalysisProgress(packageId, (progressUpdate) => {
        // Only update progress if the percentage is greater or equal to current, 
        // or if it's not the initial "Connecting..." message (which often has 0%)
        // This prevents race conditions where a late "Connecting..." message overwrites actual progress
        setProgress(prev => {
            // Ignore "Connecting..." if we already have progress
            if (progressUpdate.message === "Connecting..." && prev.percentage > 0) {
                return prev;
            }
            
            if (progressUpdate.percentage > prev.percentage || 
               (progressUpdate.percentage === prev.percentage) ||
               // Always accept if we are stuck at 0
               prev.percentage === 0
            ) {
                return progressUpdate;
            }
            return prev;
        });
        
        // Update category statuses based on progress
        if (progressUpdate.details?.document_category) {
          const currentCategory = progressUpdate.details.document_category;
          
          setCategories(prev => {
            return prev.map(cat => {
              // If this is the current category, mark as processing
              if (cat.name === currentCategory) {
                return { ...cat, status: 'processing' };
              }
              
              // If this category was previously processing but is no longer current, mark as completed
              if (cat.status === 'processing') {
                return { ...cat, status: 'completed' };
              }
              
              // Keep existing status for others (completed stay completed, queued stay queued)
              return cat;
            });
          });
        } else if (progressUpdate.details?.current_file && progressUpdate.details?.total_files) {
          // Fallback logic for legacy backend or missing category
          const fileIndex = progressUpdate.details.file_index || 0;
          const totalFiles = progressUpdate.details.total_files;
          
          setCategories(prev => {
            // Calculate how many categories should be completed based on file progress
            // Distribute files evenly across categories
            const filesPerCategory = totalFiles / prev.length;
            
            return prev.map((cat, idx) => {
              // Calculate which file range this category corresponds to
              const categoryStartFile = Math.floor(idx * filesPerCategory) + 1;
              const categoryEndFile = Math.floor((idx + 1) * filesPerCategory);
              
              // If current file is past this category's range, mark as completed
              if (fileIndex > categoryEndFile) {
                return { ...cat, status: 'completed' };
              }
              
              // If current file is within this category's range, mark as processing
              if (fileIndex >= categoryStartFile && fileIndex <= categoryEndFile) {
                return { ...cat, status: 'processing' };
              }
              
              // Otherwise, it's still queued
              return { ...cat, status: 'queued' };
            });
          });
        }
        
        // Check if processing is complete (100%)
        if (progressUpdate.percentage >= 100 && !hasRedirected) {
          hasRedirected = true;
          console.log("Processing complete, redirecting to analysis page...");
          
          // Mark all categories as completed
          setCategories(prev => prev.map(cat => ({ ...cat, status: 'completed' })));
          
          // Close event source and redirect
          setTimeout(() => {
            if (eventSource) eventSource.close();
            router.push(`/analysis/${packageId}`);
          }, 1500);
        }
      });

      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_FINANCIAL_API_URL}/api/v1/multi-document/packages/${packageId}/normalize`,
          {
            method: "POST",
          }
        );

        if (!response.ok) {
          throw new Error("Failed to normalize documents");
        }

        // The redirect will be handled by the progress update when it reaches 100%
        
      } catch (err) {
        console.error("Normalization failed:", err);
        if (eventSource) eventSource.close();
        // Redirect back to upload page on error
        setTimeout(() => {
          router.push(`/upload-package`);
        }, 2000);
      }
      
      // Return cleanup function to useEffect
      return () => {
          if (eventSource) {
              console.log("Cleaning up EventSource");
              eventSource.close();
          }
      };
    };

    // startNormalization is async, so we can't return its result directly to useEffect
    // But we can keep track of the cleanup function it generates
    let cleanupFunc: (() => void) | undefined;
    
    startNormalization().then(cleanup => {
        cleanupFunc = cleanup;
    });
    
    return () => {
        if (cleanupFunc) cleanupFunc();
    };
  }, [packageId, router]);

  return (
    <div
      className={`min-h-screen overflow-hidden selection:bg-neutral-900 selection:text-white relative bg-white text-neutral-900 flex ${
        sidebarExpanded ? "has-expanded-sidebar" : ""
      }`}
    >
      {/* Background Animation */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:24px_24px]"></div>
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-white"></div>
      </div>

      {/* Sidebar */}
      <Sidebar
        sidebarExpanded={sidebarExpanded}
        toggleSidebar={toggleSidebar}
        isChatMode={false}
        messages={[]}
        onNewChat={() => {}}
      />

      {/* Content Wrapper */}
      <div
        className={`flex flex-col flex-1 transition-all duration-300 h-screen relative z-10 bg-neutral-50/50 ${
          sidebarExpanded ? "ml-64" : "ml-[72px]"
        }`}
      >
        {/* Top Bar */}
        <header className="bg-white/80 backdrop-blur-md border-b border-neutral-200 shrink-0 sticky top-0 z-40">
          <div className="flex lg:px-8 shrink-0 sticky z-40 bg-white/80 h-16 border-neutral-100 border-b pr-6 pl-6 top-0 backdrop-blur-md items-center justify-between">
            {/* Breadcrumbs / Context */}
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.push("/dashboard")}
                className="text-neutral-500 hover:text-neutral-900 transition-colors cursor-pointer"
              >
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
                >
                  <path d="m12 19-7-7 7-7"></path>
                  <path d="M19 12H5"></path>
                </svg>
              </button>
              <div className="h-6 w-[1px] bg-neutral-200"></div>
              <div className="flex flex-col">
                <div className="flex items-center gap-2 text-xs font-medium text-neutral-500 uppercase tracking-wider">
                  <span>Dashboard</span>
                  <span className="text-neutral-300">/</span>
                  <span>Analysis</span>
                </div>
                <div className="flex items-center gap-2">
                  <h1 className="text-sm font-semibold text-neutral-900">Processing Documents</h1>
                </div>
              </div>
            </div>

            {/* Right Actions */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium text-amber-700 bg-amber-50 border border-amber-100/50">
                <div className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-amber-500"></span>
                </div>
                Processing
              </div>
            </div>
          </div>
        </header>

        {/* Main Workspace */}
        <main className="flex-1 overflow-y-auto p-6 lg:p-10 no-scrollbar">
          <div className="max-w-5xl mx-auto flex flex-col gap-8">
            
            {/* Context Header with ID */}
            <div className="flex border-neutral-200 border-b pb-6 items-end justify-between">
              <div>
                <h2 className="text-xl font-semibold text-neutral-900 tracking-tight flex items-center gap-3 mb-2">
                  Data Extraction & Categorization
                </h2>
                <p className="text-sm text-neutral-500">Extracting and categorizing information from your deal package.</p>
              </div>
              <div className="flex flex-col items-end gap-1">
                <span className="text-[10px] uppercase font-semibold text-neutral-400 tracking-wide">Package ID</span>
                <span className="text-xs font-mono text-neutral-600 bg-white border border-neutral-200 px-2 py-1 rounded select-all cursor-text">{packageId}</span>
              </div>
            </div>

            {/* Missing Documents Alert */}
            {missingDocs.length > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                  <h3 className="text-amber-800 font-semibold flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                      <line x1="12" y1="9" x2="12" y2="13"></line>
                      <line x1="12" y1="17" x2="12.01" y2="17"></line>
                    </svg>
                    Missing Required Information
                  </h3>
                  <p className="text-amber-700 text-sm mt-1">
                    To ensure accurate analysis, please upload the following documents:
                    <span className="font-semibold ml-1">{missingDocs.join(", ")}</span>
                  </p>
                </div>
                <div>
                  <input
                    type="file"
                    multiple
                    ref={missingFileInputRef}
                    className="hidden"
                    onChange={handleMissingFileSelect}
                    disabled={isUploadingMissing}
                  />
                  <button
                    onClick={() => missingFileInputRef.current?.click()}
                    disabled={isUploadingMissing}
                    className="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 transition-colors shadow-sm flex items-center gap-2"
                  >
                    {isUploadingMissing ? (
                      <>
                        <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Uploading...
                      </>
                    ) : (
                      <>
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                          <polyline points="17 8 12 3 7 8"></polyline>
                          <line x1="12" x2="12" y1="3" y2="15"></line>
                        </svg>
                        Upload Files
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              
              {/* Left: Progress Card */}
              <div className="lg:col-span-5 flex flex-col gap-6">
                <div className="bg-white p-6 rounded-xl shadow-sm border border-neutral-200 flex flex-col justify-between min-h-[240px]">
                  
                  <div>
                    <div className="flex items-end gap-2 mb-2">
                      <span className="text-5xl font-semibold text-neutral-900 tracking-tighter">{Math.round(progress.percentage)}%</span>
                      <span className="text-sm font-medium text-neutral-500 mb-1.5">complete</span>
                    </div>
                    
                    <div className="w-full bg-neutral-100 h-2 rounded-full overflow-hidden mb-6">
                      <div 
                        className="bg-neutral-900 h-full rounded-full transition-all duration-300 animate-stripe relative"
                        style={{ width: `${progress.percentage}%` }}
                      ></div>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {/* Show "Generating Financial Report" message when processing is near completion or generating analysis */}
                    {(progress.percentage >= 80 || progress.message?.toLowerCase().includes('generat') || progress.message?.toLowerCase().includes('analyz') || progress.message?.toLowerCase().includes('financial')) && progress.percentage < 100 && (
                      <div className="flex flex-col gap-1">
                        <span className="text-xs font-semibold text-neutral-900 uppercase tracking-wide">Status</span>
                        <div className="flex items-center gap-2 p-2 bg-blue-50 border border-blue-100 rounded-lg">
                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-blue-600 animate-spin">
                            <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
                          </svg>
                          <span className="text-xs font-medium text-blue-700">Generating Financial Report...</span>
                        </div>
                      </div>
                    )}
                    
                    {progress.details?.current_file && progress.details.current_file !== "All files processed" && progress.percentage < 80 && (
                      <div className="flex flex-col gap-1">
                        <span className="text-xs font-semibold text-neutral-900 uppercase tracking-wide">Currently Processing</span>
                        <div className="flex items-center gap-2 p-2 bg-neutral-50 border border-neutral-100 rounded-lg">
                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-neutral-500">
                            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                            <line x1="16" x2="8" y1="13" y2="13"></line>
                            <line x1="16" x2="8" y1="17" y2="17"></line>
                            <line x1="10" x2="8" y1="9" y2="9"></line>
                          </svg>
                          <span className="text-xs font-mono text-neutral-700 truncate">{progress.details.current_file}</span>
                        </div>
                      </div>
                    )}
                    {progress.details?.total_files && progress.details.file_index && progress.details.file_index < progress.details.total_files && (
                      <div className="flex items-center justify-between text-xs text-neutral-500 pt-2 border-t border-neutral-100">
                        <span>Total Files</span>
                        <span className="font-medium text-neutral-900">{progress.details.file_index} of {progress.details.total_files} files</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Right: Document Summary */}
              <div className="lg:col-span-7">
                <div className="bg-white rounded-xl shadow-sm border border-neutral-200 flex flex-col">
                  <div className="px-6 py-4 border-b border-neutral-100 bg-neutral-50/50 rounded-t-xl flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-neutral-900 flex items-center gap-2">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-neutral-500">
                        <path d="M15.5 2H8.6c-.4 0-.8.2-1.1.5-.3.3-.5.7-.5 1.1v12.8c0 .4.2.8.5 1.1.3.3.7.5 1.1.5h9.8c.4 0 .8-.2 1.1-.5.3-.3.5-.7.5-1.1V6.5L15.5 2z"></path>
                        <path d="M3 7.6v12.8c0 .4.2.8.5 1.1.3.3.7.5 1.1.5h9.8"></path>
                        <path d="M15 2v5h5"></path>
                      </svg>
                      Document Summary
                    </h3>
                    <span className="text-xs text-neutral-500">{categories.length} Categories Found</span>
                  </div>
                  
                  <div className="divide-y divide-neutral-100">
                    {categories.map((category, index) => (
                      <div
                        key={category.name}
                        className={`px-6 py-3.5 flex items-center justify-between group hover:bg-neutral-50 transition-colors ${
                          category.status === 'processing' ? 'bg-neutral-50/80 border-l-2 border-l-neutral-900' : ''
                        } ${category.status === 'queued' ? 'opacity-60' : ''}`}
                      >
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded flex items-center justify-center ${
                            category.status === 'completed' ? 'bg-green-50 text-green-600' :
                            category.status === 'processing' ? 'bg-white border border-neutral-200 text-neutral-900 shadow-sm' :
                            'bg-neutral-100 text-neutral-400'
                          }`}>
                            {category.status === 'completed' && category.count > 0 && (
                              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M20 6 9 17l-5-5"></path>
                              </svg>
                            )}
                            {category.status === 'completed' && category.count === 0 && (
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-amber-500">
                                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                                    <line x1="12" y1="9" x2="12" y2="13"></line>
                                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                                </svg>
                            )}
                            {category.status === 'processing' && (
                              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="animate-spin">
                                <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
                              </svg>
                            )}
                            {category.status === 'queued' && (
                              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="10"></circle>
                                <polyline points="12 6 12 12 16 14"></polyline>
                              </svg>
                            )}
                          </div>
                          <div>
                            <p className={`text-sm font-medium ${category.status === 'processing' ? 'font-semibold' : ''} text-neutral-900`}>{category.name}</p>
                            <p className="text-[10px] text-neutral-500 font-mono">{category.count} document{category.count !== 1 ? 's' : ''}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {category.status === 'completed' && category.count > 0 && (
                            <span className="inline-flex items-center px-2 py-1 rounded text-[10px] font-medium bg-green-50 text-green-700">Analyzed</span>
                          )}
                          {category.status === 'completed' && category.count === 0 && (
                            <span className="inline-flex items-center px-2 py-1 rounded text-[10px] font-medium bg-amber-50 text-amber-700">Missing</span>
                          )}
                          {category.status === 'processing' && (
                            <span className="inline-flex items-center px-2 py-1 rounded text-[10px] font-medium bg-neutral-200 text-neutral-800">Processing</span>
                          )}
                          {category.status === 'queued' && (
                            <span className="text-[10px] font-medium text-neutral-400">Queued</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

            </div>
            
            <div className="h-8"></div>
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
        @keyframes progress-stripe {
          0% { background-position: 0 0; }
          100% { background-position: 24px 24px; }
        }
        .animate-stripe {
          background-image: linear-gradient(
            45deg,
            rgba(255, 255, 255, 0.15) 25%,
            transparent 25%,
            transparent 50%,
            rgba(255, 255, 255, 0.15) 50%,
            rgba(255, 255, 255, 0.15) 75%,
            transparent 75%,
            transparent
          );
          background-size: 24px 24px;
          animation: progress-stripe 1s linear infinite;
        }
      `}</style>
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
