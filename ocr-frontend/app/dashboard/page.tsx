"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import Sidebar from "@/components/Sidebar";
import LoadingSpinner from "@/components/LoadingSpinner";
import LoginPage from "@/components/LoginPage";
import DealHistoryTable from "@/components/DealHistoryTable";

function DashboardContent() {
  const { user } = useAuth();
  const router = useRouter();
  const [sidebarExpanded, setSidebarExpanded] = useState(false);

  const getUserInitials = () => {
    if (!user?.name) return "FA";
    return user.name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase();
  };

  const toggleSidebar = () => setSidebarExpanded(!sidebarExpanded);
  const handleNewDeal = () => router.push("/upload-package");

  return (
    <div
      className={`min-h-screen overflow-hidden relative bg-[#F8FAFC] text-[#0F172A] flex ${
        sidebarExpanded ? "has-expanded-sidebar" : ""
      }`}
    >
      {/* Subtle grid overlay */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#64748b08_1px,transparent_1px),linear-gradient(to_bottom,#64748b08_1px,transparent_1px)] bg-[size:32px_32px]" />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[#F8FAFC]/0" />
      </div>

      {/* Sidebar */}
      <Sidebar
        sidebarExpanded={sidebarExpanded}
        toggleSidebar={toggleSidebar}
        isChatMode={false}
        messages={[]}
        onNewChat={() => {}}
      />

      {/* Main content */}
      <div
        className={`flex flex-col flex-1 transition-all duration-400 h-screen relative z-10 ${
          sidebarExpanded ? "ml-56" : "ml-[72px]"
        }`}
      >
        {/* ── Top Bar ────────────────────────────────────── */}
        <header className="h-14 border-b border-[#E2E8F0] bg-white flex items-center justify-between px-6 lg:px-8 shrink-0 sticky top-0 z-40">
          {/* Global search */}
          <div className="flex items-center w-full max-w-md">
            <div className="relative w-full group">
              <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-[#64748B] group-focus-within:text-[#475569] transition-colors">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
                </svg>
              </div>
              <input
                type="text"
                className="block w-full pl-9 pr-3 py-1.5 border border-[#E2E8F0] bg-[#F8FAFC] hover:bg-[#F1F5F9] focus:bg-[#F1F5F9] text-sm text-[#0F172A] rounded-lg focus:ring-1 focus:ring-[#F97316]/40 focus:border-[#F97316]/40 placeholder-[#94A3B8] transition-all outline-none"
                placeholder="Search deals, properties…"
              />
              <div className="absolute inset-y-0 right-2 flex items-center">
                <kbd className="hidden sm:inline-flex h-4 items-center gap-0.5 rounded border border-[#E2E8F0] bg-[#F1F5F9] px-1.5 font-mono text-[9px] font-medium text-[#64748B]">
                  <span className="text-[10px]">⌘</span>K
                </kbd>
              </div>
            </div>
          </div>

          {/* Right actions */}
          <div className="flex items-center gap-4">
            {/* AI status badge */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[rgba(34,197,94,0.08)] border border-[rgba(34,197,94,0.15)]">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#22C55E] opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#22C55E]" />
              </span>
              <span className="text-[9px] font-semibold text-[#22C55E] uppercase tracking-wider">
                Underwriting AI Active
              </span>
            </div>

            <div className="h-5 w-px bg-[#2A3347]" />

            {/* User */}
            <button className="flex items-center gap-2.5 hover:bg-[#F1F5F9] p-1.5 pl-2 rounded-lg transition-all">
              <div className="text-right hidden sm:block">
                <p className="text-xs font-medium text-[#0F172A] leading-tight">
                  {user?.name || "Analyst"}
                </p>
                <p className="text-[10px] text-[#64748B] leading-tight">
                  Valiance Capital
                </p>
              </div>
              <div className="w-7 h-7 rounded-full bg-[#F97316] flex items-center justify-center ring-2 ring-[rgba(249,115,22,0.2)]">
                <span className="text-white text-xs font-semibold">
                  {getUserInitials()}
                </span>
              </div>
            </button>
          </div>
        </header>

        {/* ── Main workspace ─────────────────────────────── */}
        <main className="flex-1 overflow-y-auto no-scrollbar p-6 lg:p-8">
          {/* Page header */}
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-6">
            <div>
              <h1 className="text-2xl font-semibold text-[#0F172A] tracking-tight">
                Deals Pipeline
              </h1>
              <p className="text-sm text-[#64748B] mt-1">
                Manage investment pipeline and monitor underwriting status.
              </p>
            </div>

            {/* New Deal CTA */}
            <button
              onClick={handleNewDeal}
              className="flex items-center gap-2 bg-[#F97316] hover:bg-[#EA6C0A] text-white px-4 py-2.5 rounded-lg text-sm font-semibold transition-all shadow-[0_4px_14px_rgba(249,115,22,0.35)] hover:shadow-[0_6px_20px_rgba(249,115,22,0.45)] hover:-translate-y-0.5 shrink-0"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14" /><path d="M12 5v14" />
              </svg>
              New Deal
            </button>
          </div>

          {/* Deal History Table / Card Grid */}
          <DealHistoryTable />
        </main>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <LoadingSpinner />;
  return isAuthenticated ? <DashboardContent /> : <LoginPage />;
}
