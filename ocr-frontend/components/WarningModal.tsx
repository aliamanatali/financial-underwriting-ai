import React from "react";

interface WarningModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  message: string;
}

export default function WarningModal({ isOpen, onClose, title, message }: WarningModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/20 backdrop-blur-sm">
      <div className="bg-white border border-[#E2E8F0] rounded-2xl shadow-[0_8px_30px_rgba(0,0,0,0.12)] max-w-md w-full p-8 animate-in fade-in zoom-in-95 duration-200">
        <div className="flex flex-col items-center text-center">
          <div className="w-14 h-14 bg-[rgba(245,158,11,0.12)] border border-[rgba(245,158,11,0.2)] rounded-full flex items-center justify-center mb-5">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[#F59E0B]">
              <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>

          <h3 className="text-lg font-bold text-[#0F172A] mb-2">{title}</h3>

          <p className="text-sm text-[#475569] mb-8 leading-relaxed whitespace-pre-line">{message}</p>

          <button
            onClick={onClose}
            className="w-full sm:w-auto min-w-[120px] px-6 py-2.5 bg-[#F97316] hover:bg-[#EA6C0A] text-white text-sm font-semibold rounded-lg transition-colors shadow-[0_4px_14px_rgba(249,115,22,0.3)]"
          >
            Okay
          </button>
        </div>
      </div>
    </div>
  );
}
