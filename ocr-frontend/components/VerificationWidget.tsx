"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import LoadingSpinner from "@/components/LoadingSpinner";
import { apiClient } from "@/lib/api";
import DataVerificationTable from "@/components/DataVerificationTable";
import PendingExpensesWidget from "@/components/PendingExpensesWidget";

const ExpensesVerificationWidget = dynamic(() => import("@/components/ExpensesVerificationWidget"), { ssr: false });

import { FinancialAnalysisProgress, DealPackage, NormalizedDataItem } from "@/lib/types";

const AVAILABLE_CATEGORIES = [
  "Gross Potential Rent", "Other Income", "Reimbursements",
  "Real Estate Taxes", "Insurance", "Repairs & Maintenance",
  "General & Administrative", "Payroll", "Utilities", "Management Fees",
  "Contract Services", "Other Operating Expenses", "Capital Reserves",
  "Advertising & Marketing", "Leasing Fees",
  "Property Characteristic", "Physical Condition",
  "Purchase Price", "Price per Unit", "Total Units", "Year Built",
  "Current Loan Balance", "Uncategorized",
];

interface VerificationWidgetProps {
  packageId: string;
  view?: "data" | "expenses" | "both";
  onAnalysisUpdate?: (analysis: any) => void;
  onDataChange?: () => void;
}

export default function VerificationWidget({ packageId, view = "both", onAnalysisUpdate, onDataChange }: VerificationWidgetProps) {
  const [dealPackage, setDealPackage] = useState<DealPackage | null>(null);
  const [normalizedItems, setNormalizedItems] = useState<NormalizedDataItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [normalizing, setNormalizing] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [progress, setProgress] = useState<FinancialAnalysisProgress>({ percentage: 0, message: "" });
  const [globalFilter, setGlobalFilter] = useState<"All" | "Handwritten" | "Duplicates">("All");
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  const baseUrl = process.env.NEXT_PUBLIC_FINANCIAL_API_URL;

  useEffect(() => {
    if (normalizedItems.length > 0) {
      console.group("🔍 INTERNAL AUDIT REPORT: OCR & Categorization Analysis");
      console.log(`Generated at: ${new Date().toISOString()}`);
      console.log(`Package ID: ${packageId}`);
      console.log(`Total Items: ${normalizedItems.length}`);
      const auditGroups = normalizedItems.reduce((acc, item) => {
        const group = item.category_group || "Uncategorized";
        if (!acc[group]) acc[group] = [];
        acc[group].push(item);
        return acc;
      }, {} as Record<string, NormalizedDataItem[]>);
      Object.entries(auditGroups).forEach(([group, items]) => {
        console.groupCollapsed(`📂 ${group} (${items.length})`);
        console.table(items.map(i => ({ "Category": i.normalized_value, "Raw": i.raw_text, "Source": i.source_document, "Confidence": `${(i.confidence * 100).toFixed(1)}%` })));
        console.groupEnd();
      });
      console.groupEnd();
    }
  }, [normalizedItems, packageId]);

  useEffect(() => {
    const fetchPackage = async () => {
      try {
        const response = await fetch(`${baseUrl}/api/v1/multi-document/packages/${packageId}`);
        if (!response.ok) throw new Error("Failed to fetch deal package");
        const data = await response.json();
        setDealPackage(data);
        if (data.normalized_data && data.normalized_data.length > 0) setNormalizedItems(data.normalized_data);
        else handleNormalize();
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred");
      } finally {
        setLoading(false);
      }
    };
    if (packageId) fetchPackage();
  }, [packageId, baseUrl]);

  const handleNormalize = async () => {
    setNormalizing(true); setError(null);
    setProgress({ percentage: 0, message: "Starting normalization..." });
    const eventSource = apiClient.streamFinancialAnalysisProgress(packageId, (p) => setProgress(p));
    try {
      const response = await fetch(`${baseUrl}/api/v1/multi-document/packages/${packageId}/normalize`, { method: "POST" });
      if (!response.ok) throw new Error("Failed to normalize documents");
      const data = await response.json();
      setNormalizedItems(data.normalized_items);
      const pkgRes = await fetch(`${baseUrl}/api/v1/multi-document/packages/${packageId}`);
      if (pkgRes.ok) setDealPackage(await pkgRes.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Normalization failed");
    } finally {
      setNormalizing(false); eventSource.close();
    }
  };

  const handleVerifyItem = async (itemId: string, userCorrection?: string, userRawText?: string) => {
    try {
      const payload: any = {};
      if (userRawText !== undefined) payload.raw_text = userRawText;
      const response = await fetch(`${baseUrl}/api/v1/multi-document/packages/${packageId}/verify-item/${itemId}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_correction: userCorrection, payload: Object.keys(payload).length > 0 ? payload : undefined }),
      });
      if (!response.ok) throw new Error("Failed to verify item");
      setNormalizedItems((prev) => prev.map((item) => {
        if (item.id !== itemId) return item;
        const updated = { ...item, user_verified: true, user_correction: userCorrection !== undefined ? userCorrection : item.user_correction };
        if (userRawText !== undefined) {
          updated.raw_text = userRawText;
          const amounts = userRawText.match(/\$?([\d,]+\.?\d*)/g);
          if (amounts) { const p = parseFloat(amounts[amounts.length - 1].replace(/,/g, "").replace("$", "")); if (!isNaN(p)) updated.metadata = { ...updated.metadata, amount: p }; }
        }
        return updated;
      }));
      setHasUnsavedChanges(true);
      if (onDataChange) onDataChange();
    } catch (err) { console.error("Error verifying item:", err); }
  };

  const handleUpdateItems = async (updatedItems: NormalizedDataItem[]) => {
    for (const item of updatedItems) {
      try {
        const response = await fetch(`${baseUrl}/api/v1/multi-document/packages/${packageId}/verify-item/${item.id}`, {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_correction: item.user_correction || item.normalized_value, payload: { amount: item.metadata?.amount, raw_text: item.raw_text, category_group: item.category_group } }),
        });
        if (response.ok) { setNormalizedItems((prev) => prev.map((i) => (i.id === item.id ? { ...item, user_verified: true } : i))); setHasUnsavedChanges(true); if (onDataChange) onDataChange(); }
      } catch (err) { console.error("Error updating item:", err); }
    }
  };

  const handleAddManualExpense = async (newItem: Partial<NormalizedDataItem>) => {
    try {
      const response = await fetch(`${baseUrl}/api/v1/multi-document/packages/${packageId}/add-normalized-item`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(newItem),
      });
      if (response.ok) { const data = await response.json(); setNormalizedItems((prev) => [...prev, data.item]); setHasUnsavedChanges(true); if (onDataChange) onDataChange(); }
    } catch (err) { console.error("Error adding expense:", err); }
  };

  const handleRemoveItem = async (itemId: string) => {
    try {
      const response = await fetch(`${baseUrl}/api/v1/multi-document/packages/${packageId}/remove-normalized-item/${itemId}`, { method: "DELETE" });
      if (response.ok) { setNormalizedItems((prev) => prev.filter((i) => i.id !== itemId)); setHasUnsavedChanges(true); if (onDataChange) onDataChange(); }
    } catch (err) { console.error("Error removing item:", err); }
  };

  const handleVerifyAll = async () => {
    const unverified = normalizedItems.filter((i) => !i.user_verified);
    if (unverified.length === 0) return;
    try {
      const response = await fetch(`${baseUrl}/api/v1/multi-document/packages/${packageId}/verify-items-batch`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(unverified.map((i) => ({ item_id: i.id, user_correction: null }))),
      });
      if (!response.ok) throw new Error("Failed to verify items");
      setNormalizedItems((prev) => prev.map((i) => unverified.some((u) => u.id === i.id) ? { ...i, user_verified: true } : i));
      setHasUnsavedChanges(true); if (onDataChange) onDataChange();
    } catch (err) { console.error("Error verifying all:", err); }
  };

  const handleRegenerateReport = async () => {
    setRegenerating(true); setError(null);
    setProgress({ percentage: 0, message: "Regenerating financial report..." });
    const eventSource = apiClient.streamFinancialAnalysisProgress(packageId, (p) => setProgress(p));
    try {
      const response = await fetch(`${baseUrl}/api/v1/multi-document/packages/${packageId}/analyze`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ growth_rate: 0.03, exit_cap_rate: 0.06, vacancy_rate: 0.03, min_unit_count: 15, max_unit_count: 80, max_build_year: 1970, management_fee_rate: 0.04, tax_rate: 0.012, ltv: 0.65, sofr_rate: 0.05, bridge_spread: 0.02, closing_costs: 0.0, renovation_budget: 0.0 }),
      });
      if (!response.ok) throw new Error("Failed to regenerate report");
      const newAnalysis = await response.json();
      if (onAnalysisUpdate) onAnalysisUpdate(newAnalysis);
      setHasUnsavedChanges(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report regeneration failed");
    } finally { setRegenerating(false); eventSource.close(); }
  };

  const verifiedCount = normalizedItems.filter((i) => i.user_verified).length;
  const totalCount = normalizedItems.length;
  const verificationPct = totalCount > 0 ? Math.round((verifiedCount / totalCount) * 100) : 0;
  const documents = dealPackage?.documents ?? {};

  if (loading) return <div className="flex items-center justify-center py-20"><LoadingSpinner /></div>;

  if (error && !dealPackage) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <h1 className="text-xl font-bold text-[#EF4444] mb-2">Error</h1>
          <p className="text-[#64748B] text-sm">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header card */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-[var(--shadow-card)] p-6">
        <div className="flex items-end justify-between flex-wrap gap-6">
          <div>
            <h2 className="text-base font-semibold text-[#0F172A] flex items-center gap-2">
              {view === "expenses" ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[#64748B]">
                  <line x1="12" y1="1" x2="12" y2="23" /><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[#64748B]">
                  <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                </svg>
              )}
              {view === "expenses" ? "Verify Expenses" : "Verify Data"}
            </h2>
            <p className="text-xs text-[#64748B] mt-1 pl-6">
              {view === "expenses" ? "Review and correct expense categorizations." : "Review and correct AI-mapped categories from your documents."}
            </p>
          </div>

          <div className="flex items-center gap-5">
            {/* Progress indicator */}
            <div className="flex flex-col items-end gap-1.5">
              <div className="flex items-baseline gap-2">
                <span className="text-xs font-medium text-[#475569]">
                  Verified: <span className="font-mono text-[#0F172A]">{verifiedCount} / {totalCount}</span>
                </span>
                <span className="text-[10px] text-[#64748B]">{verificationPct}%</span>
              </div>
              <div className="w-40 h-1.5 bg-[#F1F5F9] rounded-full overflow-hidden">
                <div className="h-full bg-[#F97316] rounded-full transition-all duration-300" style={{ width: `${verificationPct}%` }} />
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-3">
              <button onClick={handleVerifyAll}
                className="flex items-center gap-2 px-4 py-2 bg-[#F1F5F9] hover:bg-[#F1F5F9] text-[#475569] hover:text-[#0F172A] text-xs font-medium rounded-lg transition-colors border border-[#E2E8F0] hover:border-[#CBD5E1]">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 6 7 17l-5-5" /><path d="m22 10-7.5 7.5L13 16" />
                </svg>
                Verify All
              </button>
              <button onClick={handleRegenerateReport} disabled={regenerating}
                className="flex items-center gap-2 px-4 py-2 bg-[#F97316] hover:bg-[#EA6C0A] text-white text-xs font-semibold rounded-lg transition-colors shadow-[0_4px_14px_rgba(249,115,22,0.3)] disabled:opacity-50 disabled:cursor-not-allowed">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={regenerating ? "animate-spin" : ""}>
                  <path d="M21 12a9 9 0 1 1-2.5-6.2" /><path d="M21 6v6h-6" />
                </svg>
                {regenerating ? "Regenerating..." : "Save & Regenerate"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {(normalizing || regenerating) ? (
        /* Progress state */
        <div className="bg-white rounded-xl border border-[#E2E8F0] p-12 text-center shadow-[var(--shadow-card)]">
          <div className="max-w-sm mx-auto">
            <div className="flex items-center justify-center mb-6">
              <div className="relative w-12 h-12">
                <div className="w-12 h-12 rounded-full border-2 border-[#E2E8F0] animate-[spin_3s_linear_infinite]">
                  <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-[#F97316]" />
                </div>
              </div>
            </div>
            <h3 className="text-base font-semibold text-[#0F172A] mb-5">
              {progress.message || (regenerating ? "Regenerating Report…" : "Normalizing Documents…")}
            </h3>
            <div className="w-full bg-[#F1F5F9] rounded-full h-2 mb-2 overflow-hidden">
              <div className="bg-gradient-to-r from-[#F97316]/70 via-[#F97316] to-[#F97316]/70 h-2 rounded-full transition-all duration-300" style={{ width: `${progress.percentage}%` }} />
            </div>
            <div className="flex justify-between text-xs text-[#64748B] mb-4">
              <span>{progress.percentage}%</span>
            </div>
            {progress.details?.current_file && (
              <div className="p-4 bg-[#F1F5F9] rounded-xl border border-[#E2E8F0] text-left">
                <p className="text-[9px] text-[#64748B] uppercase tracking-widest font-semibold mb-1.5">Processing File</p>
                <p className="text-sm font-medium text-[#0F172A] truncate" title={progress.details.current_file}>{progress.details.current_file}</p>
                {progress.details.total_files && (
                  <p className="text-xs text-[#64748B] mt-1">{progress.details.file_index} of {progress.details.total_files} files</p>
                )}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {/* Filter tabs */}
          <div className="flex gap-1 p-1 bg-white border border-[#E2E8F0] rounded-lg w-fit">
            {(["All", "Handwritten", "Duplicates"] as const).map((tab) => (
              <button key={tab} onClick={() => setGlobalFilter(tab)}
                className={`px-4 py-2 text-xs font-medium rounded-md transition-colors ${
                  globalFilter === tab ? "bg-[#F97316] text-white shadow-sm" : "text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9]"
                }`}>
                {tab}
              </button>
            ))}
          </div>

          <div className="space-y-10">
            {(view === "expenses" || view === "both") && (
              <>
                <ExpensesVerificationWidget items={normalizedItems} availableCategories={AVAILABLE_CATEGORIES} globalFilter={globalFilter} onUpdateExpenses={handleUpdateItems} onAddExpense={handleAddManualExpense} onRemoveExpense={handleRemoveItem} onRegenerate={handleRegenerateReport} documents={documents} packageId={packageId} />
                <PendingExpensesWidget items={normalizedItems} availableCategories={AVAILABLE_CATEGORIES.filter((c) => c !== "Uncategorized")} globalFilter={globalFilter} onUpdateExpenses={handleUpdateItems} onAddExpense={handleAddManualExpense} onRemoveExpense={handleRemoveItem} onRegenerate={handleRegenerateReport} documents={documents} packageId={packageId} />
              </>
            )}
            {(view === "data" || view === "both") && (
              <DataVerificationTable items={normalizedItems} availableCategories={AVAILABLE_CATEGORIES} documents={documents} packageId={packageId} globalFilter={globalFilter} onVerify={handleVerifyItem} onVerifyAll={handleVerifyAll} />
            )}
          </div>
        </div>
      )}

      {/* Footer legend */}
      {normalizedItems.length > 0 && !normalizing && !regenerating && (
        <div className="bg-white border border-[#E2E8F0] rounded-xl py-3 px-6 flex items-center gap-5 flex-wrap">
          <span className="text-[9px] font-semibold text-[#64748B] uppercase tracking-widest">Confidence Legend</span>
          <div className="flex items-center gap-4">
            {[
              { cls: "badge-high", label: "High (≥95%)" },
              { cls: "badge-medium", label: "Medium (85–94%)" },
              { cls: "badge-low", label: "Low (<85%)" },
            ].map(({ cls, label }) => (
              <div key={cls} className="flex items-center gap-2">
                <span className={cls}>90%</span>
                <span className="text-xs text-[#64748B]">{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
