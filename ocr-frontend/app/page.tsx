"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import LoadingSpinner from "@/components/LoadingSpinner";
import LoginPage from "@/components/LoginPage";
import Sidebar from "@/components/Sidebar";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import {
  FireIcon,
  PaperclipIcon,
  ArrowUpIcon,
  PlusIcon,
  MoreHorizontalIcon,
  MicrophoneIcon,
  ChevronDownIcon,
} from "@/assets/icons";

// Chat Message Interface
interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// Dashboard Component
function DashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [sidebarExpanded, setSidebarExpanded] = useState(false);

  // Chat state
  const [isChatMode, setIsChatMode] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop =
        chatContainerRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  const toggleSidebar = () => {
    setSidebarExpanded(!sidebarExpanded);
  };

  // Get first name
  const getFirstName = () => {
    if (!user?.name) return "Analyst";
    return user.name.split(" ")[0];
  };

  // Handle sending a message
  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMessage = inputValue.trim();
    setInputValue("");

    const newUserMessage: ChatMessage = { role: "user", content: userMessage };
    setMessages((prev) => [...prev, newUserMessage]);

    setIsChatMode(true);
    setIsTyping(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          messages: messages,
          prompt: userMessage,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to get response");
      }

      const data = await response.json();

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: data.response,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Chat error:", error);
      const errorMessage: ChatMessage = {
        role: "assistant",
        content:
          "I apologize, but I encountered an error processing your request. Please try again.",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  // Handle key press in input
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Start new chat
  const handleNewChat = () => {
    setMessages([]);
    setIsChatMode(false);
    setInputValue("");
  };

  // Chat View
  if (isChatMode) {
    return (
      <div
        className={`min-h-screen overflow-hidden selection:bg-[#FF5E00] selection:text-white relative bg-white text-neutral-900 flex ${
          sidebarExpanded ? "has-expanded-sidebar" : ""
        }`}
      >
        {/* Sidebar */}
        <Sidebar
          sidebarExpanded={sidebarExpanded}
          toggleSidebar={toggleSidebar}
          isChatMode={isChatMode}
          messages={messages}
          onNewChat={handleNewChat}
        />

        {/* Main Chat Interface */}
        <main
          className={`flex-1 flex flex-col h-screen relative bg-white transition-all duration-400 ${
            sidebarExpanded ? "ml-64" : "ml-[72px]"
          }`}
          id="main-content"
        >
          {/* Chat Header */}
          <header className="h-14 flex items-center justify-between px-3 sticky top-0 bg-white/95 backdrop-blur-sm z-30 border-b border-neutral-100">
            <div className="flex items-center">
              <button className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-neutral-100 transition-colors text-lg text-neutral-500 font-medium group">
                <span className="text-neutral-900 font-medium tracking-tight">
                  Financial AI
                </span>
                <span className="text-neutral-400 font-normal text-sm">
                  Gemini 2.0 Flash
                </span>
                <ChevronDownIcon className="w-4 h-4 text-neutral-400 group-hover:text-neutral-600 transition-colors mt-0.5" />
              </button>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={handleNewChat}
                className="p-2 rounded-lg hover:bg-neutral-100 text-neutral-500 transition-colors"
                title="New Chat"
              >
                <PlusIcon className="w-5 h-5" />
              </button>
              <button className="p-2 rounded-lg hover:bg-neutral-100 text-neutral-500 transition-colors">
                <MoreHorizontalIcon className="w-5 h-5" />
              </button>
            </div>
          </header>

          {/* Chat Stream */}
          <div
            ref={chatContainerRef}
            className="flex-1 overflow-y-auto w-full relative z-0 pb-36"
            style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
          >
            <div className="max-w-[768px] mx-auto px-4 md:px-6 py-10 flex flex-col gap-10">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${
                    message.role === "user" ? "justify-end" : "gap-4"
                  } w-full`}
                >
                  {message.role === "user" ? (
                    <div className="bg-[#f4f4f4] text-neutral-900 px-5 py-2.5 rounded-[24px] max-w-[70%] text-base leading-relaxed">
                      {message.content}
                    </div>
                  ) : (
                    <div className="flex-1 text-base text-neutral-900 leading-7 font-normal">
                      <MarkdownRenderer content={message.content} />
                    </div>
                  )}
                </div>
              ))}

              {/* Typing indicator */}
              {isTyping && (
                <div className="flex gap-4 w-full">
                  <div className="flex items-center gap-1 text-neutral-400">
                    <div
                      className="w-2 h-2 rounded-full bg-neutral-400 animate-bounce"
                      style={{ animationDelay: "0ms" }}
                    ></div>
                    <div
                      className="w-2 h-2 rounded-full bg-neutral-400 animate-bounce"
                      style={{ animationDelay: "150ms" }}
                    ></div>
                    <div
                      className="w-2 h-2 rounded-full bg-neutral-400 animate-bounce"
                      style={{ animationDelay: "300ms" }}
                    ></div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Input Area (Fixed Bottom) */}
          <div className="absolute bottom-0 left-0 w-full bg-gradient-to-t from-white via-white to-transparent pt-10 pb-5 z-20">
            <div className="max-w-[768px] mx-auto px-4 md:px-4">
              <div className="relative flex items-center bg-[#f4f4f4] rounded-[26px] p-2 pr-2 shadow-sm border border-transparent focus-within:border-neutral-300 transition-all">
                <button className="p-2 rounded-full text-neutral-500 hover:bg-neutral-200 transition-colors">
                  <PlusIcon className="w-6 h-6" />
                </button>
                <input
                  type="text"
                  placeholder="Ask about financial underwriting..."
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  className="flex-1 bg-transparent border-none outline-none text-base text-neutral-900 placeholder:text-neutral-500 h-10 px-2 font-normal"
                />
                <div className="flex items-center gap-1">
                  <button className="p-2 text-neutral-500 hover:text-neutral-900 transition-colors">
                    <MicrophoneIcon className="w-5 h-5" />
                  </button>
                  <button
                    onClick={handleSendMessage}
                    disabled={!inputValue.trim() || isTyping}
                    className="flex hover:bg-neutral-800 transition-colors text-white bg-black w-8 h-8 rounded-full items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ArrowUpIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="text-center mt-2 mb-1">
                <p className="text-xs text-neutral-500 font-normal">
                  Financial AI can make mistakes. Verify important information.
                </p>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  // Dashboard View (Initial State)
  return (
    <div
      className={`min-h-screen overflow-x-hidden selection:bg-[#FF5E00] selection:text-white relative bg-white text-neutral-900 flex ${
        sidebarExpanded ? "has-expanded-sidebar" : ""
      }`}
    >
      {/* Background Animation */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:24px_24px]"></div>
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-white"></div>
        <div className="absolute top-[-10%] left-1/2 -translate-x-1/2 w-[1000px] h-[600px] rounded-[100%] bg-[radial-gradient(circle,rgba(255,94,0,0.05)_0%,rgba(255,255,255,0)_60%)] blur-[80px]"></div>
      </div>

      {/* Sidebar */}
      <Sidebar
        sidebarExpanded={sidebarExpanded}
        toggleSidebar={toggleSidebar}
        isChatMode={isChatMode}
        messages={messages}
        onNewChat={handleNewChat}
      />

      {/* Main Content */}
      <main
        className={`flex-1 flex flex-col min-h-screen lg:px-12 pt-8 pr-6 pb-6 pl-6 relative items-center justify-center transition-all duration-400 ${
          sidebarExpanded ? "ml-64" : "ml-[72px]"
        }`}
        id="main-content"
      >
        <div className="flex flex-col w-full max-w-4xl mr-auto ml-auto items-center">
          {/* Badge */}
          <div
            className="inline-flex gap-2.5 transition-colors cursor-default border rounded-full mb-6 pt-1.5 pr-3 pb-1.5 pl-3 backdrop-blur-md items-center cursor-pointer hover:bg-black/[0.05] border-black/10 group"
            role="button"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#FF5E00] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#FF5E00]"></span>
            </span>
            <span className="text-[11px] uppercase group-hover:text-neutral-800 transition-colors text-neutral-500 tracking-widest font-mono">
              Valiance Capital AI Hub
            </span>
          </div>

          <h1 className="md:text-4xl lg:text-5xl text-3xl font-medium text-neutral-900 tracking-tight text-center mb-3">
            Good Afternoon,
            <span className="italic text-[#FF5E00] font-serif pr-1">
              {" "}
              {getFirstName()}
            </span>
          </h1>
          <p className="md:text-2xl leading-relaxed text-xl font-light text-neutral-500 tracking-tight text-center max-w-2xl mb-8">
            How can I help with your underwriting today?
          </p>

          {/* Large Input Box with Shiny Animation */}
          <div className="w-full relative perspective-[1000px] mb-8">
            <div className="absolute -inset-4 bg-[#FF5E00] blur-3xl opacity-5 rounded-full pointer-events-none"></div>

            <div className="shiny-input-wrapper w-full p-[1px] shadow-2xl shadow-black/[0.03]">
              <div className="md:p-6 flex flex-col min-h-[140px] transition-all duration-300 bg-white/95 w-full h-full rounded-[15px] pt-4 pr-4 pb-4 pl-4 relative backdrop-blur-2xl">
                <textarea
                  className="border-none outline-none resize-none flex-grow font-light bg-transparent w-full h-full mb-4 focus:ring-0 placeholder:text-neutral-300 text-neutral-900 leading-relaxed text-sm"
                  placeholder="Ask about cap rates, NOI calculations, deal analysis, or any financial underwriting question..."
                  spellCheck="false"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                ></textarea>

                <div className="mt-auto flex flex-col sm:flex-row items-center justify-between gap-3">
                  <div className="flex items-center gap-3 w-full sm:w-auto">
                    <button className="h-8 px-3 gap-2 flex items-center justify-center rounded-lg border transition-all border-neutral-200 bg-neutral-50 hover:bg-neutral-100 text-neutral-500 hover:text-neutral-900 text-xs font-medium">
                      <PaperclipIcon className="w-3.5 h-3.5 stroke-[2]" />
                      Attach
                    </button>
                  </div>

                  <div className="flex items-center gap-4 w-full sm:w-auto justify-between sm:justify-end">
                    <button
                      onClick={handleSendMessage}
                      disabled={!inputValue.trim()}
                      className="w-8 h-8 flex items-center justify-center bg-neutral-900 text-white rounded-lg hover:bg-neutral-800 transition-colors shadow-lg shadow-black/10 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <ArrowUpIcon className="w-4 h-4 stroke-[2]" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Recent Projects / Quick Actions */}
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-700 delay-200 w-full">
            <h3 className="text-[10px] font-mono uppercase tracking-widest text-neutral-400 mb-4 ml-1">
              Recent Projects
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Card 1: Financial Underwriting */}
              <button
                onClick={() => router.push("/dashboard")}
                className="group flex flex-col justify-between text-left p-5 h-36 bg-neutral-50/50 hover:bg-white border border-neutral-100 hover:border-neutral-200 rounded-2xl hover:shadow-[0_8px_30px_rgb(0,0,0,0.04)] transition-all duration-300"
              >
                <div className="flex flex-col gap-0.5">
                  <span className="group-hover:text-neutral-900 leading-tight text-sm font-medium text-neutral-600">
                    Financial Underwriting
                  </span>
                  <span className="text-xs text-neutral-400">
                    Accelerate your deal flow.
                  </span>
                </div>
                <div className="self-start p-2 rounded-lg bg-white border border-neutral-100 text-neutral-400 group-hover:text-[#FF5E00] group-hover:border-[#FF5E00]/10 transition-colors">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="w-5 h-5 stroke-[1.5]"
                  >
                    <line x1="3" x2="21" y1="22" y2="22"></line>
                    <line x1="6" x2="6" y1="18" y2="11"></line>
                    <line x1="10" x2="10" y1="18" y2="11"></line>
                    <line x1="14" x2="14" y1="18" y2="11"></line>
                    <line x1="18" x2="18" y1="18" y2="11"></line>
                    <polygon points="12 2 20 7 4 7"></polygon>
                  </svg>
                </div>
              </button>

              {/* Card 2: Create a new app (Dummy) */}
              <button className="group flex flex-col justify-between text-left p-5 h-36 bg-transparent hover:bg-neutral-50 border border-dashed border-neutral-300 hover:border-neutral-400 rounded-2xl transition-all duration-300">
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium text-neutral-500 group-hover:text-neutral-900 leading-tight">
                    Create a new app
                  </span>
                  <span className="text-xs text-neutral-400">
                    Start a project from scratch
                  </span>
                </div>
                <div className="self-start p-2 rounded-lg bg-neutral-50 border border-neutral-200 text-neutral-400 group-hover:text-[#FF5E00] group-hover:bg-[#FF5E00]/5 group-hover:border-[#FF5E00]/20 transition-colors">
                  <PlusIcon className="w-5 h-5 stroke-[1.5]" />
                </div>
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

// Main Page Component
export default function Page() {
  const { isAuthenticated, isLoading } = useAuth();

  // Show loading spinner while checking auth state
  if (isLoading) {
    return <LoadingSpinner />;
  }

  // Show Dashboard if authenticated, Login otherwise
  return isAuthenticated ? <DashboardPage /> : <LoginPage />;
}
