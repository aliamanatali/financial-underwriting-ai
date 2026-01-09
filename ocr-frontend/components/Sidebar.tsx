"use client";

import Link from "next/link";
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

  // Get user initials
  const getUserInitials = () => {
    if (!user?.name) return "FA";
    const names = user.name.split(" ");
    return names
      .map((n) => n[0])
      .join("")
      .toUpperCase();
  };

  return (
    <nav
      className={`fixed z-50 flex flex-col bg-white/80 border-neutral-100/80 border-r pt-6 pb-6 top-0 bottom-0 left-0 backdrop-blur-xl justify-between transition-all duration-400 ${
        sidebarExpanded ? "w-64" : "w-[72px]"
      }`}
      id="sidebar"
    >
      {/* Top Section: Logo & Nav Items */}
      <div className="flex flex-col items-center gap-6 w-full">
        {/* Sidebar Header (Logo + Toggle) */}
        <div
          id="sidebar-header"
          className={`flex items-center w-full min-h-[40px] relative ${
            sidebarExpanded ? "justify-between px-4" : "justify-center px-2"
          }`}
        >
          {/* Logo Wrapper (Acts as Expand Trigger when collapsed) */}
          <div
            id="logo-wrapper"
            className={`relative flex items-center justify-center w-10 h-10 shrink-0 rounded-xl ${
              !sidebarExpanded ? "cursor-pointer" : ""
            }`}
            onClick={() => !sidebarExpanded && toggleSidebar()}
          >
            {/* Logo (Blue) */}
            <div className="text-[#FF5E00]">
              <FireIcon size={24} />
            </div>

            {/* Expand Button Overlay (Visible on Hover when collapsed) */}
            {!sidebarExpanded && (
              <button
                id="expand-trigger"
                className="absolute inset-0 flex items-center justify-center rounded-xl text-neutral-400 transition-all backdrop-blur-sm opacity-0 hover:opacity-100"
              >
                <PanelLeftOpenIcon size={20} />
              </button>
            )}
          </div>

          {/* Collapse Button (Visible only when expanded) */}
          {sidebarExpanded && (
            <button
              id="collapse-trigger"
              onClick={toggleSidebar}
              className="text-neutral-400 hover:text-neutral-600 transition-colors p-1"
            >
              <PanelLeftIcon size={20} />
            </button>
          )}
        </div>

        {/* Divider */}
        <div className="w-8 h-[1px] bg-neutral-100"></div>

        {/* Nav Items */}
        <div className="flex flex-col gap-2 w-full px-2">
          {/* Chat */}
          <Link
            href="/"
            className={`sidebar-item group relative flex items-center p-2.5 rounded-lg text-[#FF5E00] bg-[#FF5E00]/10 transition-all ${
              sidebarExpanded ? "justify-start px-4" : "justify-center"
            }`}
          >
            <MessageCircleIcon className="w-5 h-5 stroke-[1.5]" />
            {sidebarExpanded ? (
              <span className="nav-label pl-3 text-sm font-medium">
                Chat
              </span>
            ) : (
              <span className="nav-label absolute left-14 px-2 py-1 bg-[#FF5E00] text-white font-normal rounded opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none z-50 shadow-lg transition-opacity duration-300 text-xs">
                Chat
              </span>
            )}
          </Link>

          {/* Financial Underwriting Dashboard */}
          <Link
            href="/dashboard"
            className={`sidebar-item group relative flex items-center p-2.5 rounded-lg text-neutral-400 hover:text-[#FF5E00] hover:bg-[#FF5E00]/10 transition-all ${
              sidebarExpanded ? "justify-start px-4" : "justify-center"
            }`}
          >
            <ChartBarIcon className="w-5 h-5 stroke-[1.5]" />
            {sidebarExpanded ? (
              <span className="nav-label pl-3 text-sm font-medium">
                Financial Underwriting
              </span>
            ) : (
              <span className="nav-label absolute left-14 px-2 py-1 bg-neutral-800 text-white font-normal rounded opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none z-50 shadow-lg transition-opacity duration-300 text-xs">
                Financial Underwriting
              </span>
            )}
          </Link>

          {/* Create App */}
          <Link
            href="/upload-package"
            className={`sidebar-item group relative flex items-center p-2.5 rounded-lg text-neutral-400 hover:text-[#FF5E00] hover:bg-[#FF5E00]/10 transition-all ${
              sidebarExpanded ? "justify-start px-4" : "justify-center"
            }`}
          >
            <SquarePlusIcon className="w-5 h-5 stroke-[1.5]" />
            {sidebarExpanded ? (
              <span className="nav-label pl-3 text-sm font-medium">
                Create App
              </span>
            ) : (
              <span className="nav-label absolute left-14 px-2 py-1 bg-neutral-800 text-white font-normal rounded opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none z-50 shadow-lg transition-opacity duration-300 text-xs">
                Create App
              </span>
            )}
          </Link>
        </div>

        {/* Chat History (Visible on Expand in Chat Mode) */}
        {sidebarExpanded && isChatMode && messages.length > 0 && (
          <div className="w-full px-4 mt-1">
            <h3 className="text-xs font-medium text-neutral-400 mb-2 mt-2 px-2">
              Current chat
            </h3>
            <div className="space-y-0.5">
              <div className="flex items-center gap-2 px-2 py-2 text-xs text-neutral-900 bg-neutral-100/80 rounded-lg">
                <span className="truncate">
                  {messages[0]?.content.substring(0, 30)}...
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Section: Logout & Profile */}
      <div
        className={`flex flex-col items-center gap-4 w-full px-2 ${
          sidebarExpanded ? "items-stretch" : ""
        }`}
        id="sidebar-bottom-actions"
      >
        {/* Logout Button */}
        <button
          onClick={logout}
          className={`sidebar-item group relative flex items-center p-2.5 rounded-lg text-neutral-400 hover:text-red-600 hover:bg-red-50 transition-all ${
            sidebarExpanded ? "justify-start px-4" : "justify-center"
          }`}
        >
          <LogOutIcon className="w-5 h-5 stroke-[1.5]" />
          {sidebarExpanded ? (
            <span className="nav-label pl-3 text-sm">Sign Out</span>
          ) : (
            <span className="nav-label absolute left-14 px-2 py-1 bg-red-600 text-white font-normal rounded opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none z-50 shadow-lg transition-opacity duration-300 text-xs">
              Sign Out
            </span>
          )}
        </button>

        {/* User Profile */}
        <div
          className={`relative mt-2 flex items-center gap-3 transition-all ${
            sidebarExpanded ? "px-4 w-full" : "justify-center"
          }`}
          id="sidebar-user-profile"
        >
          {/* Avatar with Initials */}
          <div className="w-9 h-9 rounded-full bg-[#FF5E00] flex items-center justify-center shrink-0 ring-2 ring-transparent hover:ring-[#FF5E00]/20 transition-all cursor-pointer">
            <span className="text-white text-sm font-medium">
              {getUserInitials()}
            </span>
          </div>
          {/* User Info (visible when expanded) */}
          {sidebarExpanded && (
            <div className="flex flex-col min-w-0">
              <span className="text-sm font-medium text-neutral-900 truncate">
                {user?.name || "Financial Analyst"}
              </span>
              <span className="text-xs text-neutral-400 truncate">
                {user?.email || "analyst@valiance.com"}
              </span>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
