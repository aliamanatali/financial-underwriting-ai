"use client";

import { useState, useRef, useEffect } from "react";
import { SparklesIcon, ChevronDownIcon, ChevronUpIcon, SendIcon } from "@/assets/icons";
import { apiClient } from "@/lib/api";
import MarkdownRenderer from "./MarkdownRenderer";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface ReportChatWidgetProps {
  documentId: string;
  isExpanded?: boolean;
  onOpenChange?: (isOpen: boolean) => void;
}

export default function ReportChatWidget({ documentId, isExpanded = false, onOpenChange }: ReportChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(isExpanded);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });

  useEffect(() => { scrollToBottom(); }, [messages, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessage: ChatMessage = { role: "user", content: inputValue.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setIsLoading(true);

    try {
      const stream = apiClient.chatWithReportStream(documentId, [...messages, userMessage]);
      let fullResponse = "";
      let isFirstChunk = true;

      for await (const chunk of stream) {
        fullResponse += chunk;
        if (isFirstChunk) {
          isFirstChunk = false;
          setIsLoading(false);
          setMessages((prev) => [...prev, { role: "assistant", content: fullResponse }]);
        } else {
          setMessages((prev) => {
            const newMessages = [...prev];
            const last = newMessages[newMessages.length - 1];
            if (last.role === "assistant") last.content = fullResponse;
            return newMessages;
          });
        }
      }
    } catch {
      setMessages((prev) => {
        const newMessages = [...prev];
        const last = newMessages[newMessages.length - 1];
        if (last.role === "assistant" && !last.content)
          last.content = "I apologize — I encountered an error. Please try again.";
        return newMessages;
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={`fixed bottom-6 right-6 z-50 flex flex-col items-end transition-all duration-300 ${isOpen ? "w-[400px]" : "w-auto"}`}>

      {/* Chat Window */}
      {isOpen && (
        <div className="w-full h-[600px] bg-white rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.6)] border border-[#E2E8F0] flex flex-col overflow-hidden mb-4">

          {/* Header */}
          <div className="h-14 bg-[#F1F5F9] border-b border-[#E2E8F0] flex items-center justify-between px-4 shrink-0">
            <div className="flex items-center gap-2">
              <div className="p-1.5 bg-[rgba(249,115,22,0.12)] rounded-lg">
                <SparklesIcon className="w-4 h-4 text-[#F97316]" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[#0F172A] leading-tight">Financial Assistant</h3>
                <p className="text-[9px] text-[#64748B] uppercase tracking-widest">AI Powered</p>
              </div>
            </div>
            <button
              onClick={() => { setIsOpen(false); onOpenChange?.(false); }}
              className="p-1.5 text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] rounded-lg transition-colors"
              aria-label="Collapse chat"
            >
              <ChevronDownIcon className="w-5 h-5" />
            </button>
          </div>

          {/* Messages area */}
          <div className="flex-1 overflow-y-auto no-scrollbar p-4 space-y-3 bg-[#F8FAFC]">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6">
                <div className="w-12 h-12 bg-[rgba(249,115,22,0.12)] rounded-full flex items-center justify-center mb-3 border border-[rgba(249,115,22,0.2)]">
                  <SparklesIcon className="w-6 h-6 text-[#F97316]" />
                </div>
                <p className="text-xs font-semibold text-[#0F172A] mb-1">How can I help with this report?</p>
                <p className="text-xs text-[#64748B] max-w-[200px] leading-relaxed">
                  Ask about key metrics, risks, or get a deal summary.
                </p>
                <div className="mt-5 flex flex-col gap-2 w-full">
                  {["Summarize the key risks in this deal", "Explain the pro forma assumptions", "What is the IRR and why?"].map((q) => (
                    <button
                      key={q}
                      onClick={() => setInputValue(q)}
                      className="text-xs bg-white border border-[#E2E8F0] hover:border-[#F97316]/40 hover:text-[#F97316] p-2.5 rounded-lg transition-colors text-left text-[#475569]"
                    >
                      &ldquo;{q}&rdquo;
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[88%] rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                    msg.role === "user"
                      ? "bg-[rgba(249,115,22,0.12)] text-[#0F172A] border border-[rgba(249,115,22,0.2)] rounded-tr-none"
                      : "bg-[#F1F5F9] text-[#475569] border border-[#E2E8F0] rounded-tl-none"
                  }`}>
                    {msg.role === "assistant" ? (
                      <MarkdownRenderer content={msg.content} />
                    ) : (
                      msg.content
                    )}
                  </div>
                </div>
              ))
            )}

            {/* Typing indicator */}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-[#F1F5F9] border border-[#E2E8F0] rounded-2xl rounded-tl-none px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 bg-[#CBD5E1] rounded-full animate-bounce [animation-delay:-0.3s]" />
                    <span className="w-1.5 h-1.5 bg-[#CBD5E1] rounded-full animate-bounce [animation-delay:-0.15s]" />
                    <span className="w-1.5 h-1.5 bg-[#CBD5E1] rounded-full animate-bounce" />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input area */}
          <div className="p-3 bg-white border-t border-[#E2E8F0]">
            <form onSubmit={handleSubmit} className="relative">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Ask about this report…"
                className="w-full pl-4 pr-12 py-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-xs text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:ring-1 focus:ring-[#F97316]/40 focus:border-[#F97316]/40 transition-all"
              />
              <button
                type="submit"
                disabled={!inputValue.trim() || isLoading}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 bg-[#F97316] hover:bg-[#EA6C0A] text-white rounded-lg disabled:opacity-30 disabled:pointer-events-none transition-all"
                aria-label="Send message"
              >
                <SendIcon className="w-4 h-4" />
              </button>
            </form>
            <p className="text-[9px] text-center text-[#64748B] mt-2">
              AI can make mistakes. Always verify financial data.
            </p>
          </div>
        </div>
      )}

      {/* Floating toggle button */}
      {!isOpen && (
        <button
          onClick={() => { setIsOpen(true); onOpenChange?.(true); }}
          className="flex items-center gap-2 pl-3.5 pr-4 py-2.5 bg-[#0F172A] hover:bg-[#1E293B] text-white rounded-full shadow-[0_4px_20px_rgba(0,0,0,0.3)] hover:shadow-[0_6px_24px_rgba(0,0,0,0.35)] transition-all hover:scale-105 active:scale-95"
        >
          <div className="w-6 h-6 bg-white/15 rounded-full flex items-center justify-center shrink-0">
            <SparklesIcon className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="font-semibold text-sm">Ask AI Assistant</span>
          <ChevronUpIcon className="w-4 h-4 text-white/60" />
        </button>
      )}
    </div>
  );
}
