"use client";

import { FireIcon } from "@/assets/icons";

interface LoadingSpinnerProps {
  size?: "sm" | "lg";
  className?: string;
  message?: string;
  subMessage?: string;
}

export default function LoadingSpinner({ size, className = "", message, subMessage }: LoadingSpinnerProps = {}) {
  // Small spinner for inline use
  if (size === "sm") {
    return (
      <div className={`inline-flex items-center justify-center ${className}`}>
        <div className="relative w-4 h-4">
          <div className="w-4 h-4 rounded-full border border-neutral-300 animate-spin">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-1 rounded-full bg-[#FF5E00]"></div>
          </div>
        </div>
      </div>
    );
  }

  // Full-screen spinner (default) or large spinner
  return (
    <div className={`fixed inset-0 z-[100] flex items-center justify-center bg-white/95 backdrop-blur-xl ${className}`}>
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:24px_24px] animate-pulse"></div>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-[radial-gradient(circle,rgba(255,94,0,0.15)_0%,rgba(255,255,255,0)_70%)] animate-[pulse_2s_ease-in-out_infinite]"></div>
      </div>

      <div className="relative flex flex-col items-center gap-8">
        <div className="relative">
          <div className="w-20 h-20 rounded-full border-2 border-neutral-100 animate-[spin_3s_linear_infinite]">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-[#FF5E00]"></div>
          </div>
          <div className="absolute inset-2 rounded-full border-2 border-neutral-100 animate-[spin_2s_linear_infinite_reverse]">
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 w-1.5 h-1.5 rounded-full bg-[#FF5E00]/60"></div>
          </div>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-[#FF5E00] animate-pulse">
              <FireIcon size={28} />
            </div>
          </div>
        </div>

        <div className="flex flex-col items-center gap-2">
          <div className="flex items-center gap-2">
            <span className="text-lg font-medium text-neutral-900">
              {message || "Loading"}
            </span>
          </div>

          {subMessage && (
            <p className="text-sm text-neutral-500 text-center max-w-md">
              {subMessage}
            </p>
          )}

          <div className="flex gap-1 mt-1">
            <div className="w-1.5 h-1.5 rounded-full bg-[#FF5E00] animate-[bounce_1s_ease-in-out_infinite]"></div>
            <div
              className="w-1.5 h-1.5 rounded-full bg-[#FF5E00] animate-[bounce_1s_ease-in-out_infinite_0.1s]"
              style={{ animationDelay: "0.1s" }}
            ></div>
            <div
              className="w-1.5 h-1.5 rounded-full bg-[#FF5E00] animate-[bounce_1s_ease-in-out_infinite_0.2s]"
              style={{ animationDelay: "0.2s" }}
            ></div>
          </div>
        </div>

        <div className="w-48 h-1 bg-neutral-100 rounded-full overflow-hidden">
          <div className="h-full bg-gradient-to-r from-#FF5E00/50 via-#FF5E00 to-#FF5E00/50 rounded-full animate-[shimmer_1.5s_ease-in-out_infinite]"></div>
        </div>
      </div>
    </div>
  );
}
