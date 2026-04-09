"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import LoadingSpinner from "@/components/LoadingSpinner";
import { apiClient } from "@/lib/api";
import DataVerificationTable from "@/components/DataVerificationTable";
import PendingExpensesWidget from "@/components/PendingExpensesWidget";

const ExpensesVerificationWidget = dynamic(() => import("@/components/ExpensesVerificationWidget"), {
  ssr: false,
});

import { FinancialAnalysisProgress, DealPackage, NormalizedDataItem } from "@/lib/types";

const AVAILABLE_CATEGORIES = [
  // Revenue
  "Gross Potential Rent",
  "Other Income",
  "Reimbursements",
  // Expenses
  "Real Estate Taxes",
  "Insurance",
  "Repairs & Maintenance",
  "General & Administrative",
  "Payroll",
  "Utilities",
  "Management Fees",
  "Contract Services",
  "Other Operating Expenses",
  "Capital Reserves",
  "Advertising & Marketing",
  "Leasing Fees",
  // Property Info
  "Property Characteristic",
  "Physical Condition",
  
  // Explicit Major Variables
  "Purchase Price",
  "Price per Unit",
  "Total Units",
  "Year Built",
  "Current Loan Balance",

  "Uncategorized",
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
  const [editingItem, setEditingItem] = useState<string | null>(null);
  const [editCategory, setEditCategory] = useState<string>("");
  const [globalFilter, setGlobalFilter] = useState<"All" | "Handwritten" | "Duplicates">("All");
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  const baseUrl = process.env.NEXT_PUBLIC_FINANCIAL_API_URL;

  // Internal Audit Log for Verification
  useEffect(() => {
    if (normalizedItems.length > 0) {
      console.group("🔍 INTERNAL AUDIT REPORT: OCR & Categorization Analysis");
      console.log(`Generated at: ${new Date().toISOString()}`);
      console.log(`Package ID: ${packageId}`);
      console.log(`Total Items: ${normalizedItems.length}`);

      // Group items for clear reporting
      const auditGroups = normalizedItems.reduce((acc, item) => {
        const group = item.category_group || "Uncategorized";
        if (!acc[group]) acc[group] = [];
        acc[group].push(item);
        return acc;
      }, {} as Record<string, NormalizedDataItem[]>);

      Object.entries(auditGroups).forEach(([group, items]) => {
        console.groupCollapsed(`📂 Category Group: ${group} (${items.length} items)`);
        
        // Create a tabular view for high-level scan
        const tableData = items.map(item => ({
          "Mapped Category": item.normalized_value,
          "Raw Text": item.raw_text,
          "Source": item.source_document,
          "Confidence": `${(item.confidence * 100).toFixed(1)}%`,
          "Classification": item.data_classification,
          // Cast to any to check for direct properties that might be sent by backend but not in type definition
          "Extracted Amount": (item as any).amount || item.metadata?.amount || "N/A",
          "Period": (item as any).period || item.metadata?.period || "N/A"
        }));
        console.table(tableData);

        // Detailed view for "Maths" and specific metadata
        console.log("📝 Detailed Item Breakdown (Maths & Metadata):");
        items.forEach(item => {
            console.groupCollapsed(`Item: ${item.normalized_value || "Unknown"} (from ${item.source_document})`);
            console.log("Raw OCR Text:", item.raw_text);
            console.log("Categorization:", {
                group: item.category_group,
                mapped_value: item.normalized_value,
                confidence: item.confidence
            });
            console.log("Maths/Values:", {
                amount: (item as any).amount || item.metadata?.amount,
                period: (item as any).period || item.metadata?.period,
                ...item.metadata
            });
            console.log("Full Object:", item);
            console.groupEnd();
        });

        console.groupEnd();
      });

      console.groupEnd();
    }
  }, [normalizedItems, packageId]);

  // Fetch deal package details and auto-start normalization if needed
  useEffect(() => {
    const fetchPackage = async () => {
      try {
        const response = await fetch(
          `${baseUrl}/api/v1/multi-document/packages/${packageId}`
        );

        if (!response.ok) {
          throw new Error("Failed to fetch deal package");
        }

        const data = await response.json();
        setDealPackage(data);
        
        // If normalized data is persisted in package, load it
        if (data.normalized_data && data.normalized_data.length > 0) {
          setNormalizedItems(data.normalized_data);
        } else {
          // Auto-start normalization if no normalized data exists
          handleNormalize();
        }
        
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred");
      } finally {
        setLoading(false);
      }
    };

    if (packageId) {
      fetchPackage();
    }
  }, [packageId, baseUrl]);

  // Trigger normalization
  const handleNormalize = async () => {
    setNormalizing(true);
    setError(null);
    setProgress({ percentage: 0, message: "Starting normalization..." });

    // Start progress stream
    const eventSource = apiClient.streamFinancialAnalysisProgress(packageId, (progressUpdate) => {
      setProgress(progressUpdate);
    });

    try {
      const response = await fetch(
        `${baseUrl}/api/v1/multi-document/packages/${packageId}/normalize`,
        {
          method: "POST",
        }
      );

      if (!response.ok) {
        throw new Error("Failed to normalize documents");
      }

      const data = await response.json();
      setNormalizedItems(data.normalized_items);
      
      // Also refresh deal package to get updated status
      const pkgResponse = await fetch(`${baseUrl}/api/v1/multi-document/packages/${packageId}`);
      if (pkgResponse.ok) {
        const pkgData = await pkgResponse.json();
        setDealPackage(pkgData);
      }
      
    } catch (err) {
      setError(err instanceof Error ? err.message : "Normalization failed");
    } finally {
      setNormalizing(false);
      eventSource.close();
    }
  };

  // Verify a single item
  const handleVerifyItem = async (itemId: string, userCorrection?: string, userRawText?: string) => {
    try {
      const payload: any = {};
      if (userRawText !== undefined) {
        payload.raw_text = userRawText;
      }
      
      const response = await fetch(
        `${baseUrl}/api/v1/multi-document/packages/${packageId}/verify-item/${itemId}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            user_correction: userCorrection,
            payload: Object.keys(payload).length > 0 ? payload : undefined
          }),
        }
      );

      if (!response.ok) {
        throw new Error("Failed to verify item");
      }

      // Update local state
      setNormalizedItems((prev) =>
        prev.map((item) => {
          if (item.id === itemId) {
            const updatedItem = {
              ...item,
              user_verified: true,
              user_correction: userCorrection !== undefined ? userCorrection : item.user_correction,
            };
            if (userRawText !== undefined) {
              updatedItem.raw_text = userRawText;
              // Extract numeric amount locally for immediate UI update
              const amounts = userRawText.match(/\$?([\d,]+\.?\d*)/g);
              if (amounts) {
                const parsed = parseFloat(amounts[amounts.length - 1].replace(/,/g, '').replace('$', ''));
                if (!isNaN(parsed)) {
                  updatedItem.metadata = { ...updatedItem.metadata, amount: parsed };
                }
              }
            }
            return updatedItem;
          }
          return item;
        })
      );
      setEditingItem(null);
      setHasUnsavedChanges(true);
      if (onDataChange) onDataChange();
    } catch (err) {
      console.error("Error verifying item:", err);
    }
  };

  // Handle updates from ExpensesVerificationWidget
  const handleUpdateItems = async (updatedItems: NormalizedDataItem[]) => {
    // For now, we update them one by one, but we could add a batch endpoint
    for (const item of updatedItems) {
      try {
        const response = await fetch(
          `${baseUrl}/api/v1/multi-document/packages/${packageId}/verify-item/${item.id}`,
          {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              user_correction: item.user_correction || item.normalized_value,
              payload: {
                amount: item.metadata?.amount,
                raw_text: item.raw_text,
                category_group: item.category_group
              }
            }),
          }
        );

        if (response.ok) {
          // Update local state
          setNormalizedItems((prev) =>
            prev.map((i) => (i.id === item.id ? { ...item, user_verified: true } : i))
          );
          setHasUnsavedChanges(true);
          if (onDataChange) onDataChange();
        }
      } catch (err) {
        console.error("Error updating item:", err);
      }
    }
  };

  // Handle adding a manual expense
  const handleAddManualExpense = async (newItem: Partial<NormalizedDataItem>) => {
    try {
      const response = await fetch(
        `${baseUrl}/api/v1/multi-document/packages/${packageId}/add-normalized-item`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(newItem),
        }
      );

      if (response.ok) {
        const data = await response.json();
        // Add to local state
        setNormalizedItems((prev) => [...prev, data.item]);
        setHasUnsavedChanges(true);
        if (onDataChange) onDataChange();
      }
    } catch (err) {
      console.error("Error adding manual expense:", err);
    }
  };

  // Handle removing an item
  const handleRemoveItem = async (itemId: string) => {
    try {
      const response = await fetch(
        `${baseUrl}/api/v1/multi-document/packages/${packageId}/remove-normalized-item/${itemId}`,
        {
          method: "DELETE",
        }
      );

      if (response.ok) {
        // Remove from local state
        setNormalizedItems((prev) => prev.filter((i) => i.id !== itemId));
        setHasUnsavedChanges(true);
        if (onDataChange) onDataChange();
      }
    } catch (err) {
      console.error("Error removing item:", err);
    }
  };

  // Verify all items using batch endpoint
  const handleVerifyAll = async () => {
    const unverifiedItems = normalizedItems.filter(item => !item.user_verified);
    
    if (unverifiedItems.length === 0) {
      return;
    }
    
    try {
      // Use the new batch verification endpoint
      const response = await fetch(
        `${baseUrl}/api/v1/multi-document/packages/${packageId}/verify-items-batch`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(
            unverifiedItems.map(item => ({
              item_id: item.id,
              user_correction: null
            }))
          ),
        }
      );
      
      if (!response.ok) {
        throw new Error("Failed to verify items");
      }
      
      // Update all items in local state at once
      setNormalizedItems((prev) =>
        prev.map((item) =>
          unverifiedItems.some(unverified => unverified.id === item.id)
            ? { ...item, user_verified: true }
            : item
        )
      );
      setHasUnsavedChanges(true);
      if (onDataChange) onDataChange();
    } catch (err) {
      console.error("Error verifying all items:", err);
    }
  };

  // Regenerate financial report with updated categories
  const handleRegenerateReport = async () => {
    setRegenerating(true);
    setError(null);
    setProgress({ percentage: 0, message: "Regenerating financial report..." });

    // Start progress stream
    const eventSource = apiClient.streamFinancialAnalysisProgress(packageId, (progressUpdate) => {
      setProgress(progressUpdate);
    });

    try {
      // Use default deal parameters for regeneration
      const defaultParams = {
        growth_rate: 0.03,
        exit_cap_rate: 0.06,
        vacancy_rate: 0.03,
        min_unit_count: 15,
        max_unit_count: 80,
        max_build_year: 1970,
        management_fee_rate: 0.04,
        tax_rate: 0.012,
        ltv: 0.65,
        sofr_rate: 0.05,
        bridge_spread: 0.02,
        closing_costs: 0.0,
        renovation_budget: 0.0
      };

      const response = await fetch(
        `${baseUrl}/api/v1/multi-document/packages/${packageId}/analyze`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(defaultParams),
        }
      );

      if (!response.ok) {
        throw new Error("Failed to regenerate financial report");
      }

      const newAnalysis = await response.json();
      if (onAnalysisUpdate) {
        onAnalysisUpdate(newAnalysis);
      }
      setHasUnsavedChanges(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report regeneration failed");
    } finally {
      setRegenerating(false);
      eventSource.close();
    }
  };

  const verifiedCount = normalizedItems.filter(item => item.user_verified).length;
  const totalCount = normalizedItems.length;
  const verificationPercentage = totalCount > 0 ? Math.round((verifiedCount / totalCount) * 100) : 0;

  // Pass the full documents object to the verification table
  const documents = dealPackage?.documents ?? {};

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <LoadingSpinner />
      </div>
    );
  }

  if (error && !dealPackage) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-600 mb-2">Error</h1>
          <p className="text-gray-600">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header & Sticky Progress - Adapted for Widget */}
      <div className="bg-white rounded-xl border border-neutral-200 shadow-sm p-6">
        <div className="flex items-end justify-between mb-1">
          <div>
            <h2 className="text-lg font-semibold text-neutral-900 flex items-center gap-2">
              {view === "expenses" ? (
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-neutral-400">
                  <line x1="12" y1="1" x2="12" y2="23"></line>
                  <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-neutral-400">
                  <path d="M9 11l3 3L22 4"></path>
                  <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
                </svg>
              )}
              {view === "expenses" ? "Verify Expenses" : "Verify Data"}
            </h2>
            <p className="text-sm text-neutral-500 mt-1">
              {view === "expenses" ? "Review and correct expense verifications." : "Review and correct AI-mapped categories from your documents."}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex flex-col items-end mr-4">
              <div className="flex items-baseline gap-2 mb-1">
                <span className="text-sm font-medium text-neutral-900">
                  Verified: <span className="font-mono">{verifiedCount} / {totalCount}</span>
                </span>
                <span className="text-xs text-neutral-400">{verificationPercentage}%</span>
              </div>
              <div className="w-48 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-neutral-900 rounded-full transition-all duration-300"
                  style={{ width: `${verificationPercentage}%` }}
                ></div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleVerifyAll}
                className="flex items-center gap-2 px-4 py-2 bg-white hover:bg-neutral-50 text-neutral-900 text-sm font-medium rounded-lg transition-colors shadow-sm border border-neutral-200"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 6 7 17l-5-5"></path>
                  <path d="m22 10-7.5 7.5L13 16"></path>
                </svg>
                Verify All
              </button>
              <button
                onClick={handleRegenerateReport}
                disabled={regenerating}
                className="flex items-center gap-2 px-4 py-2 bg-neutral-900 hover:bg-neutral-800 text-white text-sm font-medium rounded-lg transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={regenerating ? "animate-spin" : ""}>
                  <path d="M21 12a9 9 0 1 1-2.5-6.2"></path>
                  <path d="M21 6v6h-6"></path>
                </svg>
                {regenerating ? "Regenerating..." : "Save and Regenerate"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {(normalizing || regenerating) ? (
        // Normalization Progress
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <div className="max-w-md mx-auto">
            <div className="w-full max-w-md mx-auto mt-6">
                <div className="flex items-center justify-center mb-4">
                  <div className="relative">
                    <div className="w-12 h-12 rounded-full border-2 border-neutral-200 animate-spin">
                      <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-neutral-900"></div>
                    </div>
                  </div>
                </div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  {progress.message || (regenerating ? "Regenerating Report..." : "Normalizing...")}
                </h3>

                <div className="w-full bg-gray-200 rounded-full h-4 mb-2 overflow-hidden">
                  <div
                    className="bg-neutral-900 h-4 rounded-full transition-all duration-300 ease-out"
                    style={{ width: `${progress.percentage}%` }}
                  ></div>
                </div>

                <div className="flex justify-between text-sm text-gray-600">
                  <span>{progress.percentage}%</span>
                </div>

                {progress.details?.current_file && (
                  <div className="mt-4 p-4 bg-slate-50 rounded-lg border border-slate-200 text-left shadow-sm">
                    <div className="flex items-start">
                      <div className="flex-shrink-0 mr-3">
                        <svg className="h-5 w-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-slate-500 uppercase tracking-wide font-semibold mb-1">
                          Processing File
                        </p>
                        <p className="text-sm font-medium text-slate-900 truncate" title={progress.details.current_file}>
                          {progress.details.current_file}
                        </p>
                        {progress.details.total_files && (
                          <p className="text-xs text-slate-500 mt-1">
                            {progress.details.file_index} of {progress.details.total_files} files
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {/* Global Tabs */}
          <div className="flex space-x-1 bg-white p-1 rounded-lg border border-slate-200 shadow-sm w-fit">
            {(["All", "Handwritten", "Duplicates"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setGlobalFilter(tab)}
                className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                  globalFilter === tab
                    ? "bg-slate-100 text-slate-900 shadow-sm"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Data Tables by Section */}
          <div className="space-y-12">
            {(view === "expenses" || view === "both") && (
              <>
                <ExpensesVerificationWidget
                  items={normalizedItems}
                  availableCategories={AVAILABLE_CATEGORIES}
                  globalFilter={globalFilter}
                  onUpdateExpenses={handleUpdateItems}
                  onAddExpense={handleAddManualExpense}
                  onRemoveExpense={handleRemoveItem}
                  onRegenerate={handleRegenerateReport}
                  documents={documents}
                  packageId={packageId}
                />
                <PendingExpensesWidget
                  items={normalizedItems}
                  availableCategories={AVAILABLE_CATEGORIES.filter(c => c !== "Uncategorized")}
                  globalFilter={globalFilter}
                  onUpdateExpenses={handleUpdateItems}
                  onAddExpense={handleAddManualExpense}
                  onRemoveExpense={handleRemoveItem}
                  onRegenerate={handleRegenerateReport}
                  documents={documents}
                  packageId={packageId}
                />
            </>
          )}

          {(view === "data" || view === "both") && (
            <DataVerificationTable
              items={normalizedItems}
              availableCategories={AVAILABLE_CATEGORIES}
              documents={documents}
              packageId={packageId}
              globalFilter={globalFilter}
              onVerify={handleVerifyItem}
              onVerifyAll={handleVerifyAll}
            />
          )}
          </div>
        </div>
      )}

      {/* Footer Legend */}
      {normalizedItems.length > 0 && !normalizing && !regenerating && (
        <div className="bg-white border-t border-neutral-200 py-3 px-10 flex items-center gap-6 rounded-b-xl">
          <span className="text-xs font-medium text-neutral-500 uppercase tracking-wider">Confidence Score Legend</span>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500"></span>
              <span className="text-xs text-neutral-600">High Confidence (≥95%)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-500"></span>
              <span className="text-xs text-neutral-600">Medium Confidence (85-94%)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-500"></span>
              <span className="text-xs text-neutral-600">Low Confidence ({`<85%`})</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}