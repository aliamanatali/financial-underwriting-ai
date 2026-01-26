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
    const names = user.name.split(" ");
    return names
      .map((n) => n[0])
      .join("")
      .toUpperCase();
  };

  const toggleSidebar = () => {
    setSidebarExpanded(!sidebarExpanded);
  };

  const handleNewDeal = () => {
    router.push("/upload-package");
  };

  return (
    <div
      className={`min-h-screen overflow-hidden selection:bg-neutral-900 selection:text-white relative bg-white text-neutral-900 flex ${
        sidebarExpanded ? "has-expanded-sidebar" : ""
      }`}
    >
      {/* Background */}
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

      {/* Main Content */}
      <div
        className={`flex flex-col flex-1 transition-all duration-400 h-screen relative z-10 ${
          sidebarExpanded ? "ml-64" : "ml-[72px]"
        }`}
      >
        {/* Top Bar */}
        <header className="h-16 border-b border-neutral-100 bg-white/80 backdrop-blur-md flex items-center justify-between px-6 lg:px-10 shrink-0 sticky top-0 z-40">
          {/* Global Search */}
          <div className="flex items-center w-full max-w-lg">
            <div className="relative w-full group">
              <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-neutral-400 group-focus-within:text-neutral-900 transition-colors">
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
                  <circle cx="11" cy="11" r="8"></circle>
                  <path d="m21 21-4.3-4.3"></path>
                </svg>
              </div>
              <input
                type="text"
                className="block w-full pl-10 pr-3 py-2 border-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white text-sm text-neutral-900 rounded-lg focus:ring-1 focus:ring-neutral-200 placeholder-neutral-400 transition-all outline-none"
                placeholder="Search deals, properties, or locations..."
              />
              <div className="absolute inset-y-0 right-2 flex items-center">
                <kbd className="hidden sm:inline-flex h-5 items-center gap-1 rounded border border-neutral-200 bg-neutral-50 px-1.5 font-mono text-[10px] font-medium text-neutral-500 opacity-100">
                  <span className="text-xs">⌘</span>K
                </kbd>
              </div>
            </div>
          </div>

          {/* Right Actions */}
          <div className="flex items-center gap-6">
            {/* System Status */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neutral-50 border border-neutral-100">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="text-[10px] font-medium text-neutral-600 uppercase tracking-wide">
                Underwriting AI Active
              </span>
            </div>

            <div className="h-6 w-[1px] bg-neutral-200"></div>

            {/* User Profile */}
            <button className="flex items-center gap-3 hover:bg-neutral-50 p-1.5 pl-2 rounded-full transition-all group">
              <div className="text-right hidden sm:block">
                <p className="text-xs font-medium text-neutral-900">
                  {user?.name || "Analyst"}
                </p>
                <p className="text-[10px] text-neutral-500">Valiance Capital</p>
              </div>
              <div className="w-8 h-8 rounded-full overflow-hidden ring-2 ring-neutral-100 group-hover:ring-neutral-200 transition-all">
                <div className="w-full h-full bg-[#FF5E00] flex items-center justify-center">
                  <span className="text-white text-sm font-medium">
                    {getUserInitials()}
                  </span>
                </div>
              </div>
            </button>
          </div>
        </header>

        {/* Main Workspace */}
        <main className="flex-1 overflow-y-auto p-6 lg:p-10 no-scrollbar">
          {/* Page Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
            <div>
              <h1 className="text-2xl font-semibold text-neutral-900 tracking-tight">
                Deals Dashboard
              </h1>
              <p className="text-sm text-neutral-500 mt-1">
                Manage investment pipeline and monitor underwriting status.
              </p>
            </div>
            {/* Primary Action */}
            <button
              onClick={handleNewDeal}
              className="group flex items-center gap-2 bg-neutral-900 hover:bg-neutral-800 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-all shadow-[0_2px_10px_rgba(0,0,0,0.1)] hover:shadow-[0_4px_16px_rgba(0,0,0,0.2)] hover:-translate-y-0.5"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M5 12h14"></path>
                <path d="M12 5v14"></path>
              </svg>
              <span>New Deal</span>
            </button>
          </div>

          {/* Deal History Table with New Design */}
          <div className="bg-white rounded-xl border border-neutral-200/80 shadow-sm overflow-hidden">
            <DealHistoryTable />
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

export default function DashboardPage() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return isAuthenticated ? <DashboardContent /> : <LoginPage />;
}
