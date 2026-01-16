"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import Sidebar from "@/components/Sidebar";
import LoadingSpinner from "@/components/LoadingSpinner";
import WarningModal from "@/components/WarningModal";
import LoginPage from "@/components/LoginPage";
import { apiClient } from "@/lib/api";
import { UploadProgress, DealPackage } from "@/lib/types";

function UploadPackageContent() {
  const { user } = useAuth();
  const router = useRouter();
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress>({ loaded: 0, total: 0, percentage: 0 });
  const [processingProgress, setProcessingProgress] = useState<{ percentage: number; message: string }>({ percentage: 0, message: "Initializing..." });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dealPackage, setDealPackage] = useState<DealPackage | null>(null);
  const [warningModal, setWarningModal] = useState<{ isOpen: boolean; title: string; message: string }>({
    isOpen: false,
    title: "",
    message: ""
  });
  const fileInputRef = useRef<HTMLInputElement>(null);

  const toggleSidebar = () => {
    setSidebarExpanded(!sidebarExpanded);
  };

  const validateFile = (file: File): string | null => {
    if (!file.name.endsWith('.zip')) {
      return "Only ZIP files are allowed";
    }
    // Validation limit removed
    // const maxSize = 100 * 1024 * 1024; // 100MB
    // if (file.size > maxSize) {
    //   return "File size must be less than 100MB";
    // }
    return null;
  };

  const handleUpload = async (file: File) => {
    setError(null);
    setSuccess(null);
    setDealPackage(null);

    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsUploading(true);
    setUploadProgress({ loaded: 0, total: file.size, percentage: 0 });
    setProcessingProgress({ percentage: 0, message: "Initializing..." });

    try {
      // Use chunked upload with progress tracking
      const data = await apiClient.uploadZipChunked(
        file,
        (progress) => {
          setUploadProgress(progress);
        },
        (processing) => {
          // Prevent race conditions: ignore "Initializing..." or 0% updates if we already have progress
          setProcessingProgress((prev) => {
            if (processing.message === "Initializing..." && prev.percentage > 0) {
              return prev;
            }
            if (processing.percentage > prev.percentage ||
               (processing.percentage === prev.percentage && processing.message !== "Initializing...") ||
               prev.percentage === 0) {
              return processing;
            }
            return prev;
          });
        }
      );

      // Extract property name from filename (remove .zip and _Inputs suffix)
      const propertyName = file.name
        .replace('.zip', '')
        .replace('_Inputs', '')
        .replace(/_/g, ' ');

      const documentCount = Object.values(data.documents).reduce(
        (sum, docs) => sum + docs.length,
        0
      );

      // Validation: Check for invalid folder structure (no documents found)
      if (documentCount === 0) {
        setWarningModal({
          isOpen: true,
          title: "Invalid Folder Structure",
          message: "The uploaded ZIP file does not contain the expected folder structure. Please ensure your folders are named correctly (e.g., '01 - Offering Memorandum', '02 - Rent Roll', etc.) and contain valid files."
        });
        return;
      }

      // Validation: Check for missing required folders
      // Required folders based on underwriting needs
      const requiredFolders = [
        "Offering Memorandum",
        "Rent Roll",
        "Financials"
      ];

      const missingFolders = requiredFolders.filter(folder => {
        // Check if the folder exists in documents map and has at least one file
        // The backend initializes all keys, so we check for length
        const docs = data.documents[folder];
        return !docs || docs.length === 0;
      });

      if (missingFolders.length > 0) {
        setWarningModal({
          isOpen: true,
          title: "Missing Required Folders",
          message: `The following required folders are missing or empty: ${missingFolders.join(", ")}. These documents are essential for the underwriting process. Please check your ZIP file and try again.`
        });
        return;
      }

      setDealPackage(data);
      setSuccess(
        `Successfully uploaded "${propertyName}" with ${documentCount} documents!`
      );

      // Don't redirect - let user start normalization from here
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Upload failed";
      setError(errorMessage);
    } finally {
      setIsUploading(false);
      setUploadProgress({ loaded: 0, total: 0, percentage: 0 });
    }
  };

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleUpload(files[0]);
    }
  }, [handleUpload]);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      handleUpload(file);
    }
  };

  const triggerFileInput = () => {
    if (!isUploading) {
      fileInputRef.current?.click();
    }
  };

  const handleDownloadTemplate = () => {
    // Download the template.zip file from public folder
    const link = document.createElement('a');
    link.href = '/template.zip';
    link.download = 'template.zip';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleStartNormalization = () => {
    if (!dealPackage) return;
    // Redirect to processing page which will handle normalization
    router.push(`/processing/${dealPackage.package_id}`);
  };

  return (
    <div
      className={`min-h-screen overflow-hidden selection:bg-neutral-900 selection:text-white relative bg-white text-neutral-900 flex ${
        sidebarExpanded ? "has-expanded-sidebar" : ""
      }`}
    >
      <WarningModal
        isOpen={warningModal.isOpen}
        onClose={() => setWarningModal({ ...warningModal, isOpen: false })}
        title={warningModal.title}
        message={warningModal.message}
      />
      
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
                type="button"
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
                <span className="text-xs font-medium text-neutral-500 uppercase tracking-wider">
                  Dashboard
                </span>
                <div className="flex items-center gap-2">
                  <h1 className="text-sm font-semibold text-neutral-900">
                    New Analysis
                  </h1>
                </div>
              </div>
            </div>

            {/* Right Actions */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium text-neutral-500 bg-neutral-50 border border-neutral-100 cursor-not-allowed">
                <div className="w-1.5 h-1.5 rounded-full bg-neutral-300"></div>
                Draft
              </div>
            </div>
          </div>
        </header>

        {/* Main Workspace */}
        <main className="flex-1 overflow-y-auto p-6 lg:p-10 no-scrollbar">
          <div className="max-w-5xl mx-auto flex flex-col gap-8">
            {/* Context Header */}
            <div className="flex items-end justify-between border-b border-neutral-200 pb-8">
              <div>
                <h2 className="text-2xl font-semibold text-neutral-900 tracking-tight flex items-center gap-3">
                  <div className="p-2 bg-white border border-neutral-200 rounded-lg shadow-sm text-neutral-900">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="24"
                      height="24"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M2 9V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H20a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H2"></path>
                      <path d="M12 12h8"></path>
                      <path d="m17 9 3 3-3 3"></path>
                    </svg>
                  </div>
                  Upload Deal Package
                </h2>
                <p className="text-sm text-neutral-500 mt-2 max-w-lg">
                  Supported formats: PDF, Excel within a ZIP archive.
                </p>
              </div>
              <button
                type="button"
                onClick={handleDownloadTemplate}
                className="hidden sm:flex items-center gap-2 text-sm text-neutral-500 hover:text-neutral-900 transition-colors cursor-pointer"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="7 10 12 15 17 10"></polyline>
                  <line x1="12" x2="12" y1="15" y2="3"></line>
                </svg>
                Download Template
              </button>
            </div>

            {/* Upload Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              {/* Left: Upload Zone */}
              <div className="lg:col-span-7 flex flex-col gap-4">
                <div className="bg-white p-1 rounded-xl shadow-sm border border-neutral-200">
                  <div
                    className={`upload-zone rounded-lg min-h-[320px] flex flex-col items-center justify-center p-8 text-center cursor-pointer group ${
                      isDragging ? 'bg-neutral-100 border-neutral-400' : ''
                    } ${isUploading ? 'pointer-events-none opacity-60' : ''}`}
                    onClick={triggerFileInput}
                    onDragEnter={handleDragEnter}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      className="hidden"
                      accept=".zip"
                      onChange={handleFileSelect}
                      disabled={isUploading}
                    />

                    {isUploading ? (
                      <div className="space-y-4 w-full max-w-sm px-4">
                        {uploadProgress.percentage < 100 ? (
                          <>
                             <div className="relative pt-1">
                              <div className="flex mb-2 items-center justify-between">
                                <div>
                                  <span className="text-xs font-semibold inline-block py-1 px-2 uppercase rounded-full text-neutral-600 bg-neutral-200">
                                    Uploading
                                  </span>
                                </div>
                                <div className="text-right">
                                  <span className="text-xs font-semibold inline-block text-neutral-600">
                                    {uploadProgress.percentage}%
                                  </span>
                                </div>
                              </div>
                              <div className="overflow-hidden h-2 mb-4 text-xs flex rounded bg-neutral-200">
                                <div
                                  style={{ width: `${uploadProgress.percentage}%` }}
                                  className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-neutral-900 transition-all duration-300 ease-in-out"
                                ></div>
                              </div>
                            </div>
                            <div className="space-y-1">
                              <p className="text-neutral-700 font-medium text-lg">
                                Uploading ZIP file...
                              </p>
                              <p className="text-sm text-neutral-600">
                                Please wait while we upload your documents.
                              </p>
                            </div>
                          </>
                        ) : (
                          <div className="flex flex-col items-center justify-center space-y-4 py-6">
                            <div className="w-12 h-12 border-4 border-neutral-200 border-t-emerald-500 rounded-full animate-spin"></div>
                            <div className="space-y-2 text-center">
                              <p className="text-neutral-700 font-medium text-lg">
                                Processing ZIP file...
                              </p>
                              <p className="text-sm text-neutral-600">
                                {processingProgress.message || "Extracting and categorizing documents"}
                              </p>
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <>
                        <div className="w-16 h-16 bg-neutral-50 rounded-full flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300 border border-neutral-100">
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="32"
                            height="32"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            className="text-neutral-400 group-hover:text-neutral-600 transition-colors"
                          >
                            <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"></path>
                            <path d="M12 12v9"></path>
                            <path d="m16 16-4-4-4 4"></path>
                          </svg>
                        </div>

                        <h3 className="text-lg font-semibold text-neutral-900 mb-2">
                          Select ZIP File
                        </h3>
                        <p className="text-sm text-neutral-500 mb-8 max-w-[240px]">
                          or drag and drop your deal package archive here
                        </p>

                        <button
                          type="button"
                          className="bg-neutral-900 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-neutral-800 transition-all shadow-sm flex items-center gap-2 cursor-pointer"
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <path d="m6 14 1.45-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.55 6a2 2 0 0 1-1.94 1.5H4a2 2 0 0 1-2-2V5c0-1.1.9-2 2-2h3.93a2 2 0 0 1 1.66.9l.82 1.2a2 2 0 0 0 1.66.9H18a2 2 0 0 1 2 2v2"></path>
                          </svg>
                          Browse Files
                        </button>

                        <span className="text-xs text-neutral-400 font-medium mt-6">
                          ZIP files (No Size Limit)
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Success Message with Normalization Button */}
                {success && dealPackage && (
                  <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
                    <div className="flex items-start gap-3">
                      <svg
                        className="h-5 w-5 text-emerald-600 mt-0.5 shrink-0"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                          clipRule="evenodd"
                        />
                      </svg>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-emerald-800">{success}</p>
                        <div className="mt-3 text-xs text-emerald-700">
                          <p className="font-semibold mb-1">Documents by Category:</p>
                          <ul className="space-y-0.5">
                            {Object.entries(dealPackage.documents).map(([type, docs]) => (
                              <li key={type} className="flex items-center">
                                <span className="inline-block w-1.5 h-1.5 bg-emerald-500 rounded-full mr-1.5"></span>
                                {type}: {docs.length} file{docs.length !== 1 ? 's' : ''}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div className="mt-3 pt-3 border-t border-emerald-200">
                          <button
                            type="button"
                            onClick={handleStartNormalization}
                            className="w-full px-4 py-2.5 bg-neutral-900 text-white rounded-lg text-sm font-medium hover:bg-neutral-800 transition-colors shadow-sm flex items-center justify-center gap-2 cursor-pointer"
                          >
                            <svg
                              className="w-4 h-4"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M13 10V3L4 14h7v7l9-11h-7z"
                              />
                            </svg>
                            Start Normalization
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Error Message */}
                {error && (
                  <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                    <div className="flex items-start gap-3">
                      <svg
                        className="h-5 w-5 text-red-600 mt-0.5 shrink-0"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                          clipRule="evenodd"
                        />
                      </svg>
                      <p className="text-sm text-red-800">{error}</p>
                    </div>
                  </div>
                )}

                <div className="flex items-start gap-3 p-4 bg-amber-50/50 border border-amber-100/60 rounded-lg">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="text-amber-600 shrink-0 mt-0.5"
                  >
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" x2="12" y1="8" y2="12"></line>
                    <line x1="12" x2="12.01" y1="16" y2="16"></line>
                  </svg>
                  <p className="text-xs text-amber-900/80 leading-relaxed">
                    Upload a ZIP file containing 8 document categories. Ensure
                    file naming conventions are followed for automatic
                    categorization.
                  </p>
                </div>
              </div>

              {/* Right: Instructions */}
              <div className="lg:col-span-5">
                <div className="bg-neutral-50/50 rounded-xl border border-neutral-200/60 p-6">
                  <h4 className="text-sm font-semibold text-neutral-900 uppercase tracking-wide mb-5 flex items-center gap-2">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="text-neutral-500"
                    >
                      <rect width="20" height="5" x="2" y="3" rx="1"></rect>
                      <path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"></path>
                      <path d="M10 12h4"></path>
                    </svg>
                    Expected ZIP Structure
                  </h4>

                  <div className="bg-white border border-neutral-200 rounded-lg p-4 font-mono text-xs text-neutral-600 leading-relaxed shadow-sm overflow-hidden">
                    <div className="flex items-center gap-2 text-neutral-900 font-medium mb-2">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="text-amber-600"
                      >
                        <path d="m7.5 4.27 9 5.15"></path>
                        <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"></path>
                        <path d="m3.3 7 8.7 5 8.7-5"></path>
                        <path d="M12 22v-9"></path>
                      </svg>
                      Property_Name_Inputs.zip
                    </div>
                    <div className="pl-1 space-y-1.5 border-l border-neutral-200 ml-1.5">
                      {[
                        "01 - Offering Memorandum",
                        "02 - Rent Roll",
                        "03 - Leases",
                        "04 - Financials",
                        "05 - Building Plans & Permits",
                        "06 - Disclosures",
                        "07 - Tax Bills",
                        "08 - Utilities",
                      ].map((folder) => (
                        <div key={folder} className="flex items-center gap-2 pl-3">
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            className="text-blue-500"
                          >
                            <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"></path>
                          </svg>
                          {folder}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mt-6">
                    <h4 className="text-xs font-semibold text-neutral-900 uppercase tracking-wide mb-3">
                      Supported Folder Naming
                    </h4>
                    <div className="space-y-3">
                      {[
                        {
                          name: "Offering Memorandum",
                          examples:
                            "01 - Offering Memorandum, 01-Offering Memorandum, Offering Memorandum",
                        },
                        {
                          name: "Rent Roll",
                          examples: "02 - Rent Roll, 02-Rent Roll, Rent Roll",
                        },
                        {
                          name: "Leases",
                          examples: "03 - Leases, 03-Leases, Leases",
                        },
                      ].map((item) => (
                        <div key={item.name} className="flex flex-col gap-1">
                          <span className="text-xs font-medium text-neutral-700 flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-neutral-400"></div>
                            {item.name}
                          </span>
                          <span className="text-[10px] text-neutral-500 font-mono bg-white px-1.5 py-0.5 border border-neutral-200 rounded w-fit">
                            {item.examples}
                          </span>
                        </div>
                      ))}
                    </div>
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
        .upload-zone {
          background-image: url("data:image/svg+xml,%3csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg'%3e%3crect width='100%25' height='100%25' fill='none' rx='12' ry='12' stroke='%23E5E5E5FF' stroke-width='2' stroke-dasharray='8%2c 8' stroke-dashoffset='0' stroke-linecap='square'/%3e%3c/svg%3e");
          transition: all 0.2s ease;
        }
        .upload-zone:hover {
          background-image: url("data:image/svg+xml,%3csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg'%3e%3crect width='100%25' height='100%25' fill='none' rx='12' ry='12' stroke='%23A3A3A3FF' stroke-width='2' stroke-dasharray='8%2c 8' stroke-dashoffset='0' stroke-linecap='square'/%3e%3c/svg%3e");
          background-color: #fafafa;
        }
      `}</style>
    </div>
  );
}

export default function UploadPackagePage() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return isAuthenticated ? <UploadPackageContent /> : <LoginPage />;
}
