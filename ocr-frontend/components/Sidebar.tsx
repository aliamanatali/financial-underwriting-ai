"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import {
  FireIcon,
  MessageCircleIcon,
  ChartBarIcon,
  SquarePlusIcon,
  LogOutIcon,
  PanelLeftOpenIcon,
  PanelLeftIcon,
} from "@/assets/icons";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface SidebarProps {
  sidebarExpanded: boolean;
  toggleSidebar: () => void;
  isChatMode?: boolean;
  messages?: ChatMessage[];
  onNewChat?: () => void;
}

export default function Sidebar({
  sidebarExpanded,
  toggleSidebar,
  isChatMode = false,
  messages = [],
  onNewChat,
}: SidebarProps) {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  const isChatActive = pathname === "/home" || isChatMode;
  const isFinancialActive = pathname === "/dashboard";

  const getUserInitials = () => {
    if (!user?.name) return "FA";
    return user.name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase();
  };

  const navItemBase =
    "sidebar-item group relative flex items-center p-2.5 rounded-lg transition-all duration-150";
  const navItemActive =
    "text-[#F97316] bg-[rgba(249,115,22,0.12)] border-l-2 border-[#F97316]";
  const navItemInactive =
    "text-[#475569] hover:text-[#F97316] hover:bg-[rgba(249,115,22,0.08)] border-l-2 border-transparent";
  const expandedAlign = sidebarExpanded ? "justify-start px-[calc(1rem-2px)]" : "justify-center";

  return (
    <nav
      id="sidebar"
      className={`fixed z-50 flex flex-col bg-white border-r border-[#E2E8F0] pt-5 pb-5 top-0 bottom-0 left-0 justify-between transition-all duration-400 ${
        sidebarExpanded ? "w-56" : "w-[72px]"
      }`}
    >
      {/* ── Top: Logo + Nav ───────────────────────────────── */}
      <div className="flex flex-col items-center gap-5 w-full">

        {/* Header: Logo + toggle */}
        <div
          id="sidebar-header"
          className={`flex items-center w-full min-h-[40px] relative ${
            sidebarExpanded ? "justify-between px-4" : "justify-center px-2"
          }`}
        >
          <div
            id="logo-wrapper"
            className="group/logo relative flex items-center justify-center w-10 h-10 shrink-0 rounded-xl cursor-pointer"
            onClick={toggleSidebar}
          >
            {/* Brand icon */}
            <div className="text-[#F97316] transition-opacity group-hover/logo:opacity-0">
              <FireIcon size={24} />
            </div>
            {/* Toggle overlay */}
            <div
              id="sidebar-toggle-overlay"
              className="absolute inset-0 flex items-center justify-center rounded-xl text-[#475569] hover:text-[#F97316] transition-all opacity-0 group-hover/logo:opacity-100"
            >
              {!sidebarExpanded ? (
                <PanelLeftOpenIcon size={20} />
              ) : (
                <PanelLeftIcon size={20} />
              )}
            </div>
          </div>

          {/* AI-active badge — shown when expanded */}
          {sidebarExpanded && (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-[rgba(34,197,94,0.1)] border border-[rgba(34,197,94,0.2)]">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#22C55E] opacity-75"></span>
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#22C55E]"></span>
              </span>
              <span className="text-[9px] font-semibold text-[#22C55E] uppercase tracking-wider whitespace-nowrap">
                AI Active
              </span>
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="w-8 h-px bg-[#2A3347]" />

        {/* Nav items */}
        <div className="flex flex-col gap-1.5 w-full px-2">

          {/* Chat */}
          <Link
            href="/home"
            className={`${navItemBase} ${isChatActive ? navItemActive : navItemInactive} ${expandedAlign}`}
          >
            <MessageCircleIcon className="w-5 h-5 stroke-[1.5] shrink-0" />
            {sidebarExpanded ? (
              <span className="nav-label pl-3 text-sm font-medium">Chat</span>
            ) : (
              <span className="nav-label absolute left-[68px] px-2.5 py-1.5 bg-[#F1F5F9] border border-[#E2E8F0] text-[#0F172A] font-medium rounded-md opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none z-50 shadow-[0_10px_40px_rgba(0,0,0,0.5)] transition-opacity duration-200 text-xs">
                Chat
              </span>
            )}
          </Link>

          {/* Financial Underwriting */}
          <Link
            href="/dashboard"
            className={`${navItemBase} ${isFinancialActive ? navItemActive : navItemInactive} ${expandedAlign}`}
          >
            <ChartBarIcon className="w-5 h-5 stroke-[1.5] shrink-0" />
            {sidebarExpanded ? (
              <span className="nav-label pl-3 text-sm font-medium">Deals</span>
            ) : (
              <span className="nav-label absolute left-[68px] px-2.5 py-1.5 bg-[#F1F5F9] border border-[#E2E8F0] text-[#0F172A] font-medium rounded-md opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none z-50 shadow-[0_10px_40px_rgba(0,0,0,0.5)] transition-opacity duration-200 text-xs">
                Deals
              </span>
            )}
          </Link>

          {/* New Deal */}
          <Link
            href="/upload-package"
            className={`${navItemBase} ${
              pathname === "/upload-package" ? navItemActive : navItemInactive
            } ${expandedAlign}`}
          >
            <SquarePlusIcon className="w-5 h-5 stroke-[1.5] shrink-0" />
            {sidebarExpanded ? (
              <span className="nav-label pl-3 text-sm font-medium">New Deal</span>
            ) : (
              <span className="nav-label absolute left-[68px] px-2.5 py-1.5 bg-[#F1F5F9] border border-[#E2E8F0] text-[#0F172A] font-medium rounded-md opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none z-50 shadow-[0_10px_40px_rgba(0,0,0,0.5)] transition-opacity duration-200 text-xs">
                New Deal
              </span>
            )}
          </Link>
        </div>

        {/* Chat history when expanded */}
        {sidebarExpanded && isChatMode && messages.length > 0 && (
          <div className="w-full px-4 mt-1">
            <h3 className="text-[10px] font-semibold text-[#64748B] uppercase tracking-widest mb-2 px-2">
              Current Chat
            </h3>
            <div className="space-y-0.5">
              <div className="flex items-center gap-2 px-2 py-2 text-xs text-[#0F172A] bg-[#F1F5F9] rounded-lg">
                <span className="truncate text-[#475569]">
                  {messages[0]?.content.substring(0, 32)}…
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Bottom: Logout + Profile ──────────────────────── */}
      <div
        id="sidebar-bottom-actions"
        className={`flex flex-col items-center gap-3 w-full px-2 ${
          sidebarExpanded ? "items-stretch" : ""
        }`}
      >
        {/* Divider */}
        <div className="w-8 h-px bg-[#2A3347] self-center" />

        {/* Logout */}
        <button
          onClick={logout}
          className={`sidebar-item group relative flex items-center p-2.5 rounded-lg text-[#475569] hover:text-[#EF4444] hover:bg-[rgba(239,68,68,0.08)] transition-all duration-150 border-l-2 border-transparent ${
            sidebarExpanded ? "justify-start px-[calc(1rem-2px)]" : "justify-center"
          }`}
          aria-label="Sign out"
        >
          <LogOutIcon className="w-5 h-5 stroke-[1.5] shrink-0" />
          {sidebarExpanded ? (
            <span className="nav-label pl-3 text-sm">Sign Out</span>
          ) : (
            <span className="nav-label absolute left-[68px] px-2.5 py-1.5 bg-[#F1F5F9] border border-[#E2E8F0] text-[#EF4444] font-medium rounded-md opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none z-50 shadow-[0_10px_40px_rgba(0,0,0,0.5)] transition-opacity duration-200 text-xs">
              Sign Out
            </span>
          )}
        </button>

        {/* User profile */}
        <div
          id="sidebar-user-profile"
          className={`relative flex items-center gap-3 transition-all ${
            sidebarExpanded ? "px-3 w-full" : "justify-center"
          }`}
        >
          {/* Avatar */}
          <div className="w-8 h-8 rounded-full bg-[#F97316] flex items-center justify-center shrink-0 ring-2 ring-[rgba(249,115,22,0.2)]">
            <span className="text-white text-xs font-semibold">
              {getUserInitials()}
            </span>
          </div>
          {/* User info (expanded only) */}
          {sidebarExpanded && (
            <div className="flex flex-col min-w-0">
              <span className="text-sm font-medium text-[#0F172A] truncate leading-tight">
                {user?.name || "Financial Analyst"}
              </span>
              <span className="text-[10px] text-[#64748B] truncate leading-tight mt-0.5">
                Valiance Capital
              </span>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
