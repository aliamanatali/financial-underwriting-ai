"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import Sidebar from "@/components/Sidebar";
import LoadingSpinner from "@/components/LoadingSpinner";
import LoginPage from "@/components/LoginPage";
import SmartFileUpload from "@/components/SmartFileUpload";

const STEPS = [
  { id: 1, label: "Upload" },
  { id: 2, label: "Organize" },
  { id: 3, label: "Analyze" },
];

function UploadPackageContent() {
  const { user } = useAuth();
  const router = useRouter();
  const [sidebarExpanded, setSidebarExpanded] = useState(false);

  const toggleSidebar = () => setSidebarExpanded(!sidebarExpanded);

  const handleDownloadTemplate = () => {
    const link = document.createElement("a");
    link.href = "/template.zip";
    link.download = "template.zip";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleUploadSuccess = (packageId: string) => {
    router.push(`/processing/${packageId}`);
  };

  return (
    <div
      className={`min-h-screen overflow-hidden relative bg-[#F8FAFC] text-[#0F172A] flex ${
        sidebarExpanded ? "has-expanded-sidebar" : ""
      }`}
    >
      {/* Subtle grid */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#64748b08_1px,transparent_1px),linear-gradient(to_bottom,#64748b08_1px,transparent_1px)] bg-[size:32px_32px]" />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[#F8FAFC]/0" />
      </div>

      <Sidebar sidebarExpanded={sidebarExpanded} toggleSidebar={toggleSidebar} isChatMode={false} messages={[]} onNewChat={() => {}} />

      <div
        className={`flex flex-col flex-1 transition-all duration-300 h-screen relative z-10 ${
          sidebarExpanded ? "ml-56" : "ml-[72px]"
        }`}
      >
        {/* Top Bar */}
        <header className="h-14 border-b border-[#E2E8F0] bg-white shrink-0 sticky top-0 z-40 flex items-center px-6 lg:px-8 justify-between">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => router.push("/dashboard")}
              className="text-[#64748B] hover:text-[#475569] transition-colors"
              aria-label="Go back"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m12 19-7-7 7-7" /><path d="M19 12H5" />
              </svg>
            </button>
            <div className="h-4 w-px bg-[#2A3347]" />
            {/* Breadcrumb */}
            <nav className="flex items-center gap-1.5 text-xs text-[#64748B]">
              <span className="hover:text-[#475569] cursor-pointer" onClick={() => router.push("/dashboard")}>Deals</span>
              <span>/</span>
              <span className="text-[#0F172A] font-medium">New Deal</span>
            </nav>
          </div>

          {/* Step indicator */}
          <div className="hidden md:flex items-center gap-1">
            {STEPS.map((step, idx) => (
              <div key={step.id} className="flex items-center gap-1">
                <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-all ${
                  step.id === 1
                    ? "bg-[#F97316] text-white shadow-[0_2px_8px_rgba(249,115,22,0.35)]"
                    : "bg-[#F1F5F9] text-[#94A3B8] border border-[#E2E8F0]"
                }`}>
                  <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold ${
                    step.id === 1 ? "bg-white/20 text-white" : "bg-[#E2E8F0] text-[#64748B]"
                  }`}>{step.id}</span>
                  {step.label}
                </div>
                {idx < STEPS.length - 1 && (
                  <div className="w-6 h-px bg-[#E2E8F0]" />
                )}
              </div>
            ))}
          </div>

          <button
            type="button"
            onClick={handleDownloadTemplate}
            className="hidden sm:flex items-center gap-2 text-xs text-[#64748B] hover:text-[#475569] transition-colors border border-[#E2E8F0] hover:border-[#CBD5E1] px-3 py-1.5 rounded-lg"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" x2="12" y1="15" y2="3" />
            </svg>
            Template
          </button>
        </header>

        {/* Main */}
        <main className="flex-1 overflow-y-auto no-scrollbar p-6 lg:p-10">
          <div className="max-w-5xl mx-auto flex flex-col gap-8">
            {/* Page header */}
            <div className="flex items-center justify-between pb-6 border-b border-[#E2E8F0]">
              <div>
                <h2 className="text-2xl font-semibold text-[#0F172A] tracking-tight flex items-center gap-3">
                  <div className="p-2 bg-[#F1F5F9] border border-[#E2E8F0] rounded-lg text-[#F97316]">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M2 9V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H20a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H2" />
                      <path d="M12 12h8" /><path d="m17 9 3 3-3 3" />
                    </svg>
                  </div>
                  Upload Deal Package
                </h2>
                <p className="text-sm text-[#64748B] mt-2 max-w-lg">
                  Supported formats: PDF, Excel, CSV, Images (ZIP archive or loose files).
                </p>
              </div>
            </div>

            {/* Smart Upload Component */}
            <SmartFileUpload onUploadSuccess={handleUploadSuccess} />

            <div className="h-8" />
          </div>
        </main>
      </div>
    </div>
  );
}

export default function UploadPackagePage() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <LoadingSpinner />;
  return isAuthenticated ? <UploadPackageContent /> : <LoginPage />;
}
