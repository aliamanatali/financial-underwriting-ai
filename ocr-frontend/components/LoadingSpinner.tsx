"use client";

import { FireIcon } from "@/assets/icons";

interface LoadingSpinnerProps {
  size?: "sm" | "lg";
  className?: string;
  message?: string;
  subMessage?: string;
}

export default function LoadingSpinner({ size, className = "", message, subMessage }: LoadingSpinnerProps = {}) {
  if (size === "sm") {
    return (
      <div className={`inline-flex items-center justify-center ${className}`}>
        <div className="relative w-4 h-4">
          <div className="w-4 h-4 rounded-full border border-[#E2E8F0] animate-spin">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-1 rounded-full bg-[#F97316]" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`fixed inset-0 z-[100] flex items-center justify-center bg-white/95 backdrop-blur-xl ${className}`}>
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#64748b08_1px,transparent_1px),linear-gradient(to_bottom,#64748b08_1px,transparent_1px)] bg-[size:32px_32px]" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-[radial-gradient(circle,rgba(249,115,22,0.08)_0%,transparent_60%)]" />
      </div>

      <div className="relative flex flex-col items-center gap-7">
        <div className="relative">
          <div className="w-20 h-20 rounded-full border-2 border-[#E2E8F0] animate-[spin_3s_linear_infinite]">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-[#F97316]" />
          </div>
          <div className="absolute inset-2 rounded-full border-2 border-[#E2E8F0] animate-[spin_2s_linear_infinite_reverse]">
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 w-1.5 h-1.5 rounded-full bg-[rgba(249,115,22,0.6)]" />
          </div>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-[#F97316] animate-pulse">
              <FireIcon size={28} />
            </div>
          </div>
        </div>

        <div className="flex flex-col items-center gap-2">
          <span className="text-lg font-medium text-[#0F172A]">{message || "Loading"}</span>
          {subMessage && (
            <p className="text-sm text-[#64748B] text-center max-w-md">{subMessage}</p>
          )}
          <div className="flex gap-1 mt-1">
            <div className="w-1.5 h-1.5 rounded-full bg-[#F97316] animate-bounce [animation-delay:0s]" />
            <div className="w-1.5 h-1.5 rounded-full bg-[#F97316] animate-bounce [animation-delay:0.1s]" />
            <div className="w-1.5 h-1.5 rounded-full bg-[#F97316] animate-bounce [animation-delay:0.2s]" />
          </div>
        </div>

        <div className="w-48 h-1 bg-[#F1F5F9] rounded-full overflow-hidden">
          <div className="h-full bg-gradient-to-r from-[#F97316]/50 via-[#F97316] to-[#F97316]/50 rounded-full animate-[shimmer_1.5s_ease-in-out_infinite]" />
        </div>
      </div>
    </div>
  );
}
