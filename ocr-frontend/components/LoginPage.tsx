"use client";

import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import {
  ChartBarIcon,
  MailIcon,
  LockIcon,
  ShieldCheckIcon,
} from "@/assets/icons";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();

    const success = login(email, password);
    if (!success) {
      setError("Invalid username or password");
    }
  };

  return (
    <div className="relative bg-white text-neutral-900 flex flex-col min-h-screen">
      {/* Background Animation */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        {/* Minimalist Grid Pattern */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:24px_24px]"></div>
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-white"></div>

        {/* Soft Blue Ambient Glows */}
        <div className="absolute top-[-20%] left-1/2 -translate-x-1/2 w-[1000px] h-[600px] rounded-[100%] bg-[radial-gradient(circle,rgba(255,94,0,0.06)_0%,rgba(255,255,255,0)_60%)] blur-[80px]"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[500px] h-[500px] rounded-[100%] bg-[radial-gradient(circle,rgba(255,94,0,0.03)_0%,rgba(255,255,255,0)_60%)] blur-[80px]"></div>
      </div>

      {/* Main Content (Login) */}
      <main className="flex-1 flex flex-col min-h-screen relative items-center justify-center p-6 z-10">
        {/* Login Container */}
        <div className="w-full max-w-md relative">
          {/* Badge */}
          <div className="flex justify-center mb-8 animate-in fade-in slide-in-from-bottom-2 duration-700">
            <div className="inline-flex gap-2.5 transition-colors cursor-default border rounded-full pt-1.5 pr-3 pb-1.5 pl-3 backdrop-blur-md items-center bg-white/50 border-neutral-200/60 shadow-sm">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#FF5E00] opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[#FF5E00]"></span>
              </span>
              <span className="flex items-center gap-2 ml-0.5">
                <span className="font-serif italic text-[#FF5E00] text-[13px] font-medium">
                  Valiance AI
                </span>
                <span className="h-3 w-px bg-neutral-300"></span>
                <span className="text-[10px] uppercase tracking-wider text-neutral-500 font-medium">
                  Financial Intelligence
                </span>
              </span>
            </div>
          </div>

          {/* The Card with Shiny Border Animation */}
          <div className="shiny-input-wrapper w-full p-[1px] shadow-2xl shadow-black/[0.04] animate-in fade-in zoom-in-95 duration-700">
            <div className="flex flex-col bg-white/95 w-full h-full rounded-[15px] p-8 md:p-10 relative backdrop-blur-2xl">
              {/* Header */}
              <div className="text-center mb-10">
                <div className="mx-auto flex items-center justify-center w-14 h-14 rounded-2xl bg-white border border-neutral-100 mb-6 text-[#FF5E00] shadow-[0_2px_12px_rgba(255,94,0,0.1)] ring-1 ring-neutral-200/50">
                  <ChartBarIcon className="w-7 h-7" />
                </div>
                <h1 className="text-2xl font-medium text-neutral-900 tracking-tight mb-3">
                  Sign in
                </h1>
                <p className="text-sm text-neutral-500 font-normal flex items-center justify-center gap-1.5 flex-wrap">
                  to the{" "}
                  <span className="font-semibold text-neutral-900 text-base tracking-wide">
                    Financial Underwriting AI
                  </span>{" "}
                  Hub
                </p>
              </div>

              {/* Error Message */}
              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm text-center">
                  {error}
                </div>
              )}

              {/* Form */}
              <form className="flex flex-col gap-5" onSubmit={handleLogin} action="#">
                {/* Email/Username Input */}
                <div className="space-y-1.5">
                  <label
                    htmlFor="email"
                    className="text-xs font-medium text-neutral-700 ml-1"
                  >
                    Username
                  </label>
                  <div className="relative group">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-400 group-focus-within:text-neutral-900 transition-colors">
                      <MailIcon size={16} />
                    </div>
                    <input
                      type="text"
                      id="email"
                      name="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="block w-full pl-10 pr-3 py-2.5 border border-neutral-200 rounded-lg text-sm text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-[#FF5E00]/10 focus:border-[#FF5E00]/50 transition-all bg-white"
                      placeholder="Enter your username"
                      required
                    />
                  </div>
                </div>

                {/* Password Input */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between ml-1">
                    <label
                      htmlFor="password"
                      className="text-xs font-medium text-neutral-700"
                    >
                      Password
                    </label>
                    <a
                      href="#"
                      className="text-xs text-neutral-500 hover:text-[#FF5E00] transition-colors"
                    >
                      Forgot password?
                    </a>
                  </div>
                  <div className="relative group">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-400 group-focus-within:text-neutral-900 transition-colors">
                      <LockIcon size={16} />
                    </div>
                    <input
                      type="password"
                      id="password"
                      name="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="block w-full pl-10 pr-3 py-2.5 border border-neutral-200 rounded-lg text-sm text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-[#FF5E00]/10 focus:border-[#FF5E00]/50 transition-all bg-white"
                      placeholder="••••••••"
                      required
                    />
                  </div>
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  className="w-full mt-2 flex items-center justify-center py-2.5 px-4 rounded-lg bg-[#FF5E00] hover:bg-[#E65400] text-white text-sm font-medium transition-all shadow-[0_2px_10px_rgba(255,94,0,0.15)] hover:shadow-[0_4px_20px_rgba(255,94,0,0.25)] focus:ring-2 focus:ring-offset-2 focus:ring-[#FF5E00]"
                >
                  Sign In
                </button>
              </form>

              {/* Divider */}
              <div className="relative my-8">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-neutral-100"></div>
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="bg-white px-2 text-neutral-400">
                    Or continue with
                  </span>
                </div>
              </div>

              {/* SSO Button */}
              <button
                type="button"
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-white border border-neutral-200 hover:bg-neutral-50 text-neutral-700 text-sm font-medium transition-all group"
              >
                <ShieldCheckIcon
                  size={16}
                  className="text-neutral-400 group-hover:text-neutral-600 transition-colors"
                />
                Single Sign-On (SSO)
              </button>
            </div>
          </div>

          {/* Footer */}
          <p className="text-[11px] text-neutral-400 tracking-wide text-center mt-8">
            © 2026 Valiance Capital. All rights reserved.
          </p>
        </div>
      </main>
    </div>
  );
}
