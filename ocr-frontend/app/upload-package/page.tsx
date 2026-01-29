"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import Sidebar from "@/components/Sidebar";
import LoadingSpinner from "@/components/LoadingSpinner";
import LoginPage from "@/components/LoginPage";
import SmartFileUpload from "@/components/SmartFileUpload";

function UploadPackageContent() {
  const { user } = useAuth();
  const router = useRouter();
  const [sidebarExpanded, setSidebarExpanded] = useState(false);

  const toggleSidebar = () => {
    setSidebarExpanded(!sidebarExpanded);
  };

  const handleDownloadTemplate = () => {
    const link = document.createElement('a');
    link.href = '/template.zip';
    link.download = 'template.zip';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleUploadSuccess = (packageId: string) => {
    // Redirect to processing page
    router.push(`/processing/${packageId}`);
  };

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
                  Supported formats: PDF, Excel, CSV, Images (ZIP archive or loose files).
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

            {/* Smart Upload Component */}
            <SmartFileUpload
              onUploadSuccess={handleUploadSuccess}
            />

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
