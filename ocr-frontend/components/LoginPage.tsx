"use client";

import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { ChartBarIcon, MailIcon, LockIcon, ShieldCheckIcon } from "@/assets/icons";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!login(email, password)) setError("Invalid username or password");
  };

  return (
    <div className="relative bg-[#F8FAFC] text-[#0F172A] flex flex-col min-h-screen">
      {/* Background */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#64748b08_1px,transparent_1px),linear-gradient(to_bottom,#64748b08_1px,transparent_1px)] bg-[size:32px_32px]" />
        {/* Radial glow */}
        <div className="absolute top-[-20%] left-1/2 -translate-x-1/2 w-[800px] h-[500px] rounded-[100%] bg-[radial-gradient(circle,rgba(249,115,22,0.08)_0%,transparent_60%)] blur-[80px]" />
      </div>

      <main className="flex-1 flex flex-col min-h-screen relative items-center justify-center p-6 z-10">
        <div className="w-full max-w-md">

          {/* Brand badge */}
          <div className="flex justify-center mb-8">
            <div className="inline-flex gap-2.5 border border-[#E2E8F0] rounded-full py-1.5 px-3 bg-white items-center shadow-[var(--shadow-card)]">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#F97316] opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[#F97316]" />
              </span>
              <span className="flex items-center gap-2">
                <span className="font-serif italic text-[#F97316] text-[13px] font-medium">Valiance AI</span>
                <span className="h-3 w-px bg-[#2A3347]" />
                <span className="text-[10px] uppercase tracking-wider text-[#64748B] font-medium">Financial Intelligence</span>
              </span>
            </div>
          </div>

          {/* Login card with shiny border */}
          <div className="shiny-input-wrapper w-full p-[1px] rounded-[16px]">
            <div className="flex flex-col bg-white w-full h-full rounded-[15px] p-8 md:p-10 border border-[#E2E8F0]">

              {/* Header */}
              <div className="text-center mb-8">
                <div className="mx-auto flex items-center justify-center w-14 h-14 rounded-2xl bg-[rgba(249,115,22,0.12)] border border-[rgba(249,115,22,0.2)] mb-5 text-[#F97316]">
                  <ChartBarIcon className="w-7 h-7" />
                </div>
                <h1 className="text-2xl font-semibold text-[#0F172A] tracking-tight mb-2">Sign in</h1>
                <p className="text-sm text-[#64748B]">
                  to the{" "}
                  <span className="font-semibold text-[#0F172A]">Financial Underwriting AI</span> Hub
                </p>
              </div>

              {/* Error */}
              {error && (
                <div className="mb-4 p-3 bg-[rgba(239,68,68,0.08)] border border-[rgba(239,68,68,0.2)] rounded-lg text-[#EF4444] text-sm text-center">
                  {error}
                </div>
              )}

              {/* Form */}
              <form className="flex flex-col gap-4" onSubmit={handleLogin} action="#">
                <div className="space-y-1.5">
                  <label htmlFor="email" className="text-xs font-medium text-[#475569] ml-0.5">Username</label>
                  <div className="relative group">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#64748B] group-focus-within:text-[#475569] transition-colors">
                      <MailIcon size={16} />
                    </div>
                    <input
                      type="text" id="email" name="email" value={email} onChange={(e) => setEmail(e.target.value)}
                      className="block w-full pl-10 pr-3 py-2.5 border border-[#E2E8F0] bg-[#F8FAFC] rounded-lg text-sm text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:ring-1 focus:ring-[#F97316]/40 focus:border-[#F97316]/50 transition-all"
                      placeholder="Enter your username" required
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between ml-0.5">
                    <label htmlFor="password" className="text-xs font-medium text-[#475569]">Password</label>
                    <a href="#" className="text-xs text-[#64748B] hover:text-[#F97316] transition-colors">Forgot password?</a>
                  </div>
                  <div className="relative group">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#64748B] group-focus-within:text-[#475569] transition-colors">
                      <LockIcon size={16} />
                    </div>
                    <input
                      type="password" id="password" name="password" value={password} onChange={(e) => setPassword(e.target.value)}
                      className="block w-full pl-10 pr-3 py-2.5 border border-[#E2E8F0] bg-[#F8FAFC] rounded-lg text-sm text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:ring-1 focus:ring-[#F97316]/40 focus:border-[#F97316]/50 transition-all"
                      placeholder="••••••••" required
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  className="w-full mt-1 flex items-center justify-center py-2.5 px-4 rounded-lg bg-[#F97316] hover:bg-[#EA6C0A] text-white text-sm font-semibold transition-all shadow-[0_4px_14px_rgba(249,115,22,0.35)] hover:shadow-[0_6px_20px_rgba(249,115,22,0.45)] focus:ring-2 focus:ring-offset-2 focus:ring-[#F97316] focus:ring-offset-[#161B27]"
                >
                  Sign In
                </button>
              </form>

              <div className="relative my-7">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-[#E2E8F0]" />
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="bg-white px-2 text-[#64748B]">Or continue with</span>
                </div>
              </div>

              <button
                type="button"
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-[#F1F5F9] border border-[#E2E8F0] hover:border-[#CBD5E1] text-[#475569] hover:text-[#0F172A] text-sm font-medium transition-all"
              >
                <ShieldCheckIcon size={16} className="text-[#64748B]" />
                Single Sign-On (SSO)
              </button>
            </div>
          </div>

          <p className="text-[11px] text-[#64748B] tracking-wide text-center mt-6">
            © 2026 Valiance Capital. All rights reserved.
          </p>
        </div>
      </main>
    </div>
  );
}
