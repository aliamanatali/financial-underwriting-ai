"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import LoadingSpinner from "@/components/LoadingSpinner";
import LoginPage from "@/components/LoginPage";
import Sidebar from "@/components/Sidebar";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import {
  PaperclipIcon,
  ArrowUpIcon,
  PlusIcon,
  MoreHorizontalIcon,
  MicrophoneIcon,
  ChevronDownIcon,
} from "@/assets/icons";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

function DashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [isChatMode, setIsChatMode] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatContainerRef.current) chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
  }, [messages, isTyping]);

  const getFirstName = () => (user?.name ? user.name.split(" ")[0] : "Analyst");

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;
    const userMessage = inputValue.trim();
    setInputValue("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsChatMode(true);
    setIsTyping(true);
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages, prompt: userMessage }),
      });
      if (!response.ok) throw new Error("Failed to get response");
      const data = await response.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.response }]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "I apologize — I encountered an error. Please try again." }]);
    } finally { setIsTyping(false); }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSendMessage(); }
  };

  const handleNewChat = () => { setMessages([]); setIsChatMode(false); setInputValue(""); };
  const toggleSidebar = () => setSidebarExpanded(!sidebarExpanded);

  // Chat View
  if (isChatMode) {
    return (
      <div className={`min-h-screen overflow-hidden bg-[#F8FAFC] text-[#0F172A] flex ${sidebarExpanded ? "has-expanded-sidebar" : ""}`}>
        <Sidebar sidebarExpanded={sidebarExpanded} toggleSidebar={toggleSidebar} isChatMode={isChatMode} messages={messages} onNewChat={handleNewChat} />

        <main className={`flex-1 flex flex-col h-screen relative bg-[#F8FAFC] transition-all duration-300 ${sidebarExpanded ? "ml-56" : "ml-[72px]"}`}>
          {/* Header */}
          <header className="h-14 flex items-center justify-between px-4 sticky top-0 bg-white/95 backdrop-blur-sm z-30 border-b border-[#E2E8F0]">
            <button className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-[#F1F5F9] transition-colors group">
              <span className="text-[#0F172A] font-medium text-sm tracking-tight">Financial AI</span>
              <span className="text-[#64748B] font-normal text-xs">Gemini 2.0 Flash</span>
              <ChevronDownIcon className="w-4 h-4 text-[#64748B] group-hover:text-[#475569] transition-colors" />
            </button>
            <div className="flex items-center gap-1">
              <button onClick={handleNewChat} className="p-2 rounded-lg hover:bg-[#F1F5F9] text-[#64748B] hover:text-[#0F172A] transition-colors" title="New Chat">
                <PlusIcon className="w-5 h-5" />
              </button>
              <button className="p-2 rounded-lg hover:bg-[#F1F5F9] text-[#64748B] hover:text-[#0F172A] transition-colors">
                <MoreHorizontalIcon className="w-5 h-5" />
              </button>
            </div>
          </header>

          {/* Messages */}
          <div ref={chatContainerRef} className="flex-1 overflow-y-auto w-full no-scrollbar pb-36">
            <div className="max-w-[768px] mx-auto px-4 md:px-6 py-10 flex flex-col gap-8">
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "gap-4"} w-full`}>
                  {msg.role === "user" ? (
                    <div className="bg-[rgba(249,115,22,0.1)] text-[#0F172A] border border-[rgba(249,115,22,0.15)] px-5 py-3 rounded-2xl rounded-tr-sm max-w-[70%] text-sm leading-relaxed">
                      {msg.content}
                    </div>
                  ) : (
                    <div className="flex-1 text-sm text-[#475569] leading-7">
                      <MarkdownRenderer content={msg.content} />
                    </div>
                  )}
                </div>
              ))}
              {isTyping && (
                <div className="flex gap-4 w-full">
                  <div className="flex items-center gap-1.5">
                    {[0, 150, 300].map((delay) => (
                      <div key={delay} className="w-2 h-2 rounded-full bg-[#CBD5E1] animate-bounce" style={{ animationDelay: `${delay}ms` }} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Input */}
          <div className="absolute bottom-0 left-0 w-full bg-gradient-to-t from-[#F8FAFC] via-[#F8FAFC] to-transparent pt-10 pb-5 z-20">
            <div className="max-w-[768px] mx-auto px-4">
              <div className="relative flex items-center bg-white border border-[#E2E8F0] rounded-2xl p-2 pr-2 focus-within:border-[#F97316]/40 transition-all">
                <button className="p-2 rounded-full text-[#64748B] hover:text-[#475569] hover:bg-[#F1F5F9] transition-colors">
                  <PlusIcon className="w-5 h-5" />
                </button>
                <input type="text" placeholder="Ask about financial underwriting…" value={inputValue} onChange={(e) => setInputValue(e.target.value)} onKeyDown={handleKeyPress}
                  className="flex-1 bg-transparent border-none outline-none text-sm text-[#0F172A] placeholder:text-[#64748B] h-10 px-2" />
                <div className="flex items-center gap-1">
                  <button className="p-2 text-[#64748B] hover:text-[#475569] transition-colors"><MicrophoneIcon className="w-4 h-4" /></button>
                  <button onClick={handleSendMessage} disabled={!inputValue.trim() || isTyping}
                    className="w-8 h-8 flex items-center justify-center bg-[#F97316] hover:bg-[#EA6C0A] text-white rounded-xl transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
                    <ArrowUpIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <p className="text-center mt-2 text-[10px] text-[#64748B]">Financial AI can make mistakes. Verify important information.</p>
            </div>
          </div>
        </main>
      </div>
    );
  }

  // Home View
  return (
    <div className={`min-h-screen overflow-x-hidden bg-[#F8FAFC] text-[#0F172A] flex ${sidebarExpanded ? "has-expanded-sidebar" : ""}`}>
      {/* Background */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#64748b08_1px,transparent_1px),linear-gradient(to_bottom,#64748b08_1px,transparent_1px)] bg-[size:32px_32px]" />
        <div className="absolute top-[-10%] left-1/2 -translate-x-1/2 w-[1000px] h-[600px] rounded-[100%] bg-[radial-gradient(circle,rgba(249,115,22,0.06)_0%,transparent_60%)] blur-[80px]" />
      </div>

      <Sidebar sidebarExpanded={sidebarExpanded} toggleSidebar={toggleSidebar} isChatMode={isChatMode} messages={messages} onNewChat={handleNewChat} />

      <main className={`flex-1 flex flex-col min-h-screen px-6 lg:px-12 pt-8 pb-6 relative items-center justify-center transition-all duration-300 ${sidebarExpanded ? "ml-56" : "ml-[72px]"}`}>
        <div className="flex flex-col w-full max-w-3xl mx-auto items-center">

          {/* Brand badge */}
          <div className="inline-flex gap-2.5 border border-[#E2E8F0] rounded-full mb-7 py-1.5 px-3 bg-white items-center cursor-default">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#F97316] opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#F97316]" />
            </span>
            <span className="text-[10px] uppercase tracking-widest text-[#64748B] font-medium">Valiance Capital AI Hub</span>
          </div>

          {/* Headline */}
          <h1 className="text-3xl md:text-4xl lg:text-5xl font-medium text-[#0F172A] tracking-tight text-center mb-3">
            Good Afternoon,
            <span className="italic text-[#F97316] font-serif"> {getFirstName()}</span>
          </h1>
          <p className="text-lg md:text-xl font-light text-[#64748B] tracking-tight text-center max-w-xl mb-9">
            How can I help with your underwriting today?
          </p>

          {/* Input box */}
          <div className="w-full relative mb-8">
            <div className="shiny-input-wrapper w-full p-[1px]">
              <div className="flex flex-col min-h-[140px] bg-white w-full h-full rounded-[15px] p-5 border border-[#E2E8F0]">
                <textarea
                  className="border-none outline-none resize-none flex-grow bg-transparent w-full h-full mb-4 placeholder:text-[#64748B] text-[#0F172A] leading-relaxed text-sm"
                  placeholder="Ask about cap rates, NOI calculations, deal analysis, or any financial underwriting question…"
                  spellCheck={false}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } }}
                />
                <div className="flex items-center justify-between gap-3">
                  <button className="h-8 px-3 gap-2 flex items-center justify-center rounded-lg border border-[#E2E8F0] bg-[#F1F5F9] hover:bg-[#F1F5F9] text-[#64748B] hover:text-[#475569] text-xs font-medium transition-colors">
                    <PaperclipIcon className="w-3.5 h-3.5" />
                    Attach
                  </button>
                  <button onClick={handleSendMessage} disabled={!inputValue.trim()}
                    className="w-8 h-8 flex items-center justify-center bg-[#F97316] hover:bg-[#EA6C0A] text-white rounded-lg transition-colors shadow-[0_4px_14px_rgba(249,115,22,0.3)] disabled:opacity-30 disabled:cursor-not-allowed">
                    <ArrowUpIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Quick action cards */}
          <div className="w-full">
            <p className="text-[10px] font-mono uppercase tracking-widest text-[#64748B] mb-4 ml-1">Recent Projects</p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <button onClick={() => router.push("/dashboard")}
                className="group flex flex-col justify-between text-left p-5 h-36 bg-white hover:bg-[#F1F5F9] border border-[#E2E8F0] hover:border-[#CBD5E1] rounded-2xl transition-all duration-200">
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium text-[#0F172A] leading-tight">Financial Underwriting</span>
                  <span className="text-xs text-[#64748B]">Accelerate your deal flow.</span>
                </div>
                <div className="self-start p-2 rounded-lg bg-[#F1F5F9] border border-[#E2E8F0] text-[#64748B] group-hover:text-[#F97316] group-hover:border-[rgba(249,115,22,0.2)] group-hover:bg-[rgba(249,115,22,0.06)] transition-colors">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="3" x2="21" y1="22" y2="22" /><line x1="6" x2="6" y1="18" y2="11" />
                    <line x1="10" x2="10" y1="18" y2="11" /><line x1="14" x2="14" y1="18" y2="11" />
                    <line x1="18" x2="18" y1="18" y2="11" /><polygon points="12 2 20 7 4 7" />
                  </svg>
                </div>
              </button>
              <button className="group flex flex-col justify-between text-left p-5 h-36 bg-transparent hover:bg-white border border-dashed border-[#E2E8F0] hover:border-[#CBD5E1] rounded-2xl transition-all duration-200">
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium text-[#475569] group-hover:text-[#0F172A] leading-tight">Create a new app</span>
                  <span className="text-xs text-[#64748B]">Start a project from scratch</span>
                </div>
                <div className="self-start p-2 rounded-lg bg-white border border-[#E2E8F0] text-[#64748B] group-hover:text-[#F97316] group-hover:border-[rgba(249,115,22,0.2)] transition-colors">
                  <PlusIcon className="w-[18px] h-[18px]" />
                </div>
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default function Page() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <LoadingSpinner />;
  return isAuthenticated ? <DashboardPage /> : <LoginPage />;
}
