"use client";

import { useState, useRef, useEffect } from "react";
import { MessageCircleIcon, XIcon, SendIcon, SparklesIcon, ChevronDownIcon, ChevronUpIcon } from "@/assets/icons";
import { apiClient } from "@/lib/api";
import MarkdownRenderer from "./MarkdownRenderer";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface ReportChatWidgetProps {
  documentId: string;
  isExpanded?: boolean;
}

export default function ReportChatWidget({ documentId, isExpanded = false }: ReportChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(isExpanded);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessage: ChatMessage = { role: "user", content: inputValue.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setIsLoading(true);

    try {
      const response = await apiClient.chatWithReport(documentId, [...messages, userMessage]);
      const assistantMessage: ChatMessage = { role: "assistant", content: response.response };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Chat error:", error);
      const errorMessage: ChatMessage = {
        role: "assistant",
        content: "I apologize, but I encountered an error processing your request. Please try again.",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={`fixed bottom-6 right-6 z-50 flex flex-col items-end transition-all duration-300 ${isOpen ? 'w-[400px]' : 'w-auto'}`}>
      
      {/* Chat Window */}
      {isOpen && (
        <div className="w-full h-[600px] bg-white rounded-2xl shadow-2xl border border-neutral-200 flex flex-col overflow-hidden animate-in slide-in-from-bottom-10 fade-in duration-300 mb-4">
          {/* Header */}
          <div className="h-14 bg-neutral-900 flex items-center justify-between px-4 shrink-0">
            <div className="flex items-center gap-2 text-white">
              <SparklesIcon className="w-5 h-5 text-amber-400" />
              <h3 className="font-medium">Financial Assistant</h3>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setIsOpen(false)}
                className="p-1.5 text-neutral-400 hover:text-white hover:bg-neutral-800 rounded-lg transition-colors"
              >
                <ChevronDownIcon className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-neutral-50/50">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-neutral-500">
                <div className="w-12 h-12 bg-amber-100 rounded-full flex items-center justify-center mb-3">
                  <SparklesIcon className="w-6 h-6 text-amber-600" />
                </div>
                <p className="text-sm font-medium text-neutral-900 mb-1">
                  How can I help with this report?
                </p>
                <p className="text-xs text-neutral-400 max-w-[200px]">
                  Ask about key metrics, risks, or get a summary of the deal.
                </p>
                <div className="mt-6 grid grid-cols-1 gap-2 w-full">
                  <button 
                    onClick={() => {
                        setInputValue("Summarize the key risks in this deal");
                    }}
                    className="text-xs bg-white border border-neutral-200 p-2 rounded-lg hover:border-amber-400 hover:text-amber-700 transition-colors text-left"
                  >
                    "Summarize the key risks"
                  </button>
                  <button 
                     onClick={() => {
                        setInputValue("Explain the pro forma assumptions");
                    }}
                    className="text-xs bg-white border border-neutral-200 p-2 rounded-lg hover:border-amber-400 hover:text-amber-700 transition-colors text-left"
                  >
                    "Explain pro forma assumptions"
                  </button>
                </div>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${
                    msg.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                      msg.role === "user"
                        ? "bg-neutral-900 text-white rounded-tr-none"
                        : "bg-white border border-neutral-200 text-neutral-800 shadow-sm rounded-tl-none"
                    }`}
                  >
                    {msg.role === "assistant" ? (
                      <MarkdownRenderer content={msg.content} />
                    ) : (
                      msg.content
                    )}
                  </div>
                </div>
              ))
            )}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-white border border-neutral-200 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm">
                  <div className="flex items-center gap-1.5">
                    <div className="w-2 h-2 bg-neutral-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                    <div className="w-2 h-2 bg-neutral-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                    <div className="w-2 h-2 bg-neutral-400 rounded-full animate-bounce"></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="p-4 bg-white border-t border-neutral-100">
            <form onSubmit={handleSubmit} className="relative">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Ask about this report..."
                className="w-full pl-4 pr-12 py-3 bg-neutral-50 border border-neutral-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-neutral-900/10 focus:border-neutral-900 transition-all text-sm"
              />
              <button
                type="submit"
                disabled={!inputValue.trim() || isLoading}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 bg-neutral-900 text-white rounded-lg hover:bg-neutral-800 disabled:opacity-50 disabled:hover:bg-neutral-900 transition-colors"
              >
                <SendIcon className="w-4 h-4" />
              </button>
            </form>
            <div className="text-[10px] text-center text-neutral-400 mt-2">
                AI can make mistakes. Verify important financial data.
            </div>
          </div>
        </div>
      )}

      {/* Floating Button (Visible when closed) */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="flex items-center gap-2 px-4 py-3 bg-neutral-900 text-white rounded-full shadow-xl hover:bg-neutral-800 transition-all hover:scale-105 active:scale-95 group"
        >
          <SparklesIcon className="w-5 h-5 text-amber-400" />
          <span className="font-medium pr-1">Ask AI Assistant</span>
          <ChevronUpIcon className="w-4 h-4 text-neutral-400 group-hover:text-white transition-colors" />
        </button>
      )}
    </div>
  );
}