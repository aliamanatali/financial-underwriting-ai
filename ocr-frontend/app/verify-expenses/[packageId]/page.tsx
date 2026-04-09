"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import LoadingSpinner from "@/components/LoadingSpinner";
import Sidebar from "@/components/Sidebar";
import { apiClient } from "@/lib/api";
import ExpensesVerificationWidget from "@/components/ExpensesVerificationWidget";
import { FinancialAnalysisProgress, DealPackage, NormalizedDataItem } from "@/lib/types";
import PendingExpensesWidget from "@/components/PendingExpensesWidget";
 
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

export default function VerificationPage() {
  const params = useParams();
  const router = useRouter();
  const packageId = params.packageId as string;

  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [dealPackage, setDealPackage] = useState<DealPackage | null>(null);
  const [normalizedItems, setNormalizedItems] = useState<NormalizedDataItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [normalizing, setNormalizing] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [progress, setProgress] = useState<FinancialAnalysisProgress>({ percentage: 0, message: "" });
  const [editingItem, setEditingItem] = useState<string | null>(null);
  const [editCategory, setEditCategory] = useState<string>("");
  const [commentaryExpanded, setCommentaryExpanded] = useState(false);

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
        
        const tableData = items.map(item => ({
          "Mapped Category": item.normalized_value,
          "Raw Text": item.raw_text,
          "Source": item.source_document,
          "Confidence": `${(item.confidence * 100).toFixed(1)}%`,
          "Classification": item.data_classification,
          "Extracted Amount": (item as any).amount || item.metadata?.amount || "N/A",
          "Period": (item as any).period || item.metadata?.period || "N/A"
        }));
        console.table(tableData);

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
        
        if (data.normalized_data && data.normalized_data.length > 0) {
          setNormalizedItems(data.normalized_data);
        } else {
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
  const handleVerifyItem = async (itemId: string, userCorrection?: string) => {
    try {
      const response = await fetch(
        `${baseUrl}/api/v1/multi-document/packages/${packageId}/verify-item/${itemId}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ user_correction: userCorrection }),
        }
      );

      if (!response.ok) {
        throw new Error("Failed to verify item");
      }

      setNormalizedItems((prev) =>
        prev.map((item) =>
          item.id === itemId
            ? {
                ...item,
                user_verified: true,
                user_correction: userCorrection || null,
              }
            : item
        )
      );
      setEditingItem(null);
    } catch (err) {
      console.error("Error verifying item:", err);
    }
  };

  // Handle updates from ExpensesVerificationWidget
  const handleUpdateItems = async (updatedItems: NormalizedDataItem[]) => {
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
          setNormalizedItems((prev) =>
            prev.map((i) => (i.id === item.id ? { ...item, user_verified: true } : i))
          );
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
        setNormalizedItems((prev) => [...prev, data.item]);
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
        setNormalizedItems((prev) => prev.filter((i) => i.id !== itemId));
      }
    } catch (err) {
      console.error("Error removing item:", err);
    }
  };

  // Edit item category
  const handleEditItem = (itemId: string, currentCategory: string) => {
    setEditingItem(itemId);
    setEditCategory(currentCategory);
  };

  // Save edited category
  const handleSaveEdit = (itemId: string) => {
    handleVerifyItem(itemId, editCategory);
  };

  // Verify all items using batch endpoint
  const handleVerifyAll = async () => {
    const unverifiedItems = normalizedItems.filter(item => !item.user_verified);
    
    if (unverifiedItems.length === 0) {
      return;
    }
    
    try {
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
              user_correction: null,
              payload: {
                category_group: item.category_group
              }
            }))
          ),
        }
      );
      
      if (!response.ok) {
        throw new Error("Failed to verify items");
      }
      
      setNormalizedItems((prev) =>
        prev.map((item) =>
          unverifiedItems.some(unverified => unverified.id === item.id)
            ? { ...item, user_verified: true }
            : item
        )
      );
    } catch (err) {
      console.error("Error verifying all items:", err);
    }
  };

  // Regenerate financial report with updated categories
  const handleRegenerateReport = async () => {
    setRegenerating(true);
    setError(null);
    setProgress({ percentage: 0, message: "Regenerating financial report..." });

    const eventSource = apiClient.streamFinancialAnalysisProgress(packageId, (progressUpdate) => {
      setProgress(progressUpdate);
    });

    try {
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

      router.push("/");
      
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report regeneration failed");
    } finally {
      setRegenerating(false);
      eventSource.close();
    }
  };

  // Proceed to analysis
  const handleProceedToAnalysis = () => {
    router.push(`/analysis/${packageId}`);
  };

  const groupedItems = normalizedItems.reduce((acc, item) => {
    const section = item.category_group || "Other";
    
    if (!acc[section]) {
      acc[section] = [];
    }
    acc[section].push(item);
    return acc;
  }, {} as Record<string, NormalizedDataItem[]>);

  const getConfidenceColor = (confidence: number) => {
    const percentage = confidence <= 1 ? confidence * 100 : confidence;
    if (percentage >= 95) return "bg-green-500";
    if (percentage >= 85) return "bg-amber-500";
    return "bg-red-500";
  };

  const getConfidenceTextColor = (confidence: number) => {
    const percentage = confidence <= 1 ? confidence * 100 : confidence;
    if (percentage >= 95) return "text-green-700";
    if (percentage >= 85) return "text-amber-700";
    return "text-red-700";
  };

  const formatConfidence = (confidence: number) => {
    const percentage = confidence <= 1 ? confidence * 100 : confidence;
    return Math.round(percentage);
  };

  const verifiedCount = normalizedItems.filter(item => item.user_verified).length;
  const totalCount = normalizedItems.length;
  const verificationPercentage = totalCount > 0 ? Math.round((verifiedCount / totalCount) * 100) : 0;

  const documents = dealPackage?.documents ?? {};

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (error && !dealPackage) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-600 mb-2">Error</h1>
          <p className="text-gray-600">{error}</p>
          <button
            onClick={() => router.push("/")}
            className="mt-4 px-4 py-2 bg-neutral-900 text-white rounded-md hover:bg-neutral-800"
          >
            Go Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen overflow-hidden bg-white text-neutral-900 flex">
      <Sidebar
        sidebarExpanded={sidebarExpanded}
        toggleSidebar={() => setSidebarExpanded(!sidebarExpanded)}
      />

      <div
        className={`flex flex-col flex-1 transition-all duration-300 h-screen relative z-10 bg-neutral-50/50 ${
          sidebarExpanded ? "pl-64" : "pl-[72px]"
        }`}
      >
        <header className="bg-white/80 backdrop-blur-md border-b border-neutral-200 shrink-0 sticky top-0 z-40">
          <div className="flex lg:px-8 shrink-0 bg-white/80 h-16 border-neutral-100 border-b pr-6 pl-6 top-0 backdrop-blur-md items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.push(`/analysis/${packageId}`)}
                className="text-neutral-500 hover:text-neutral-900 transition-colors cursor-pointer"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="m12 19-7-7 7-7"></path>
                  <path d="M19 12H5"></path>
                </svg>
              </button>
              <div className="h-6 w-[1px] bg-neutral-200"></div>
              <div className="flex flex-col">
                <div className="flex items-center gap-2 text-xs font-medium text-neutral-500 uppercase tracking-wider">
                  <span>Dashboard</span>
                  <span className="text-neutral-300">/</span>
                  <span>Analysis</span>
                </div>
                <div className="flex items-center gap-2">
                  <h1 className="text-sm font-semibold text-neutral-900">Verify Expenses</h1>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {normalizedItems.length > 0 && verifiedCount < totalCount && (
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium text-indigo-700 bg-indigo-50 border border-indigo-100/50">
                  <div className="relative flex h-1.5 w-1.5">
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-indigo-500"></span>
                  </div>
                  Action Required
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto relative">
          {normalizedItems.length === 0 && !normalizing ? (
            <div className="bg-white border-b border-neutral-200 pt-8 pb-0 sticky top-0 z-30 shadow-sm">
              <div className="max-w-7xl mx-auto px-6 lg:px-10 pb-6">
                <div className="flex items-end justify-between mb-1">
                  <div>
                    <h2 className="text-2xl font-semibold text-neutral-900 tracking-tight flex items-center gap-3 mb-2">
                      Verify Expenses
                    </h2>
                    <p className="text-sm text-neutral-500">Preparing verification data...</p>
                  </div>
                </div>
              </div>
            </div>
          ) : normalizing ? (
            <div className="bg-white border-b border-neutral-200 pt-8 pb-0 sticky top-0 z-30 shadow-sm">
              <div className="max-w-7xl mx-auto px-6 lg:px-10 pb-6">
                <div className="flex items-end justify-between mb-1">
                  <div>
                    <h2 className="text-2xl font-semibold text-neutral-900 tracking-tight flex items-center gap-3 mb-2">
                      Verify Expenses
                    </h2>
                    <p className="text-sm text-neutral-500">Extracting and normalizing data from your documents...</p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white border-b border-neutral-200 pt-8 pb-0 sticky top-0 z-30 shadow-sm">
              <div className="max-w-7xl mx-auto px-6 lg:px-10 pb-6">
                <div className="flex items-end justify-between mb-1">
                  <div>
                    <h2 className="text-2xl font-semibold text-neutral-900 tracking-tight flex items-center gap-3 mb-2">
                      Verify Expenses
                    </h2>
                    <p className="text-sm text-neutral-500">Review and correct expense verifications.</p>
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
            </div>
          )}

          <div className="max-w-7xl mx-auto p-6 lg:p-10 flex flex-col gap-10 pb-24">
            {(normalizing || regenerating) ? (
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
              <div className="space-y-12">
                <ExpensesVerificationWidget
                  items={normalizedItems}
                  availableCategories={AVAILABLE_CATEGORIES}
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
                 onUpdateExpenses={handleUpdateItems}
                 onAddExpense={handleAddManualExpense}
                 onRemoveExpense={handleRemoveItem}
                 onRegenerate={handleRegenerateReport}
                 documents={documents}
                 packageId={packageId}
                />
              </div>
            )}
          </div>

          {normalizedItems.length > 0 && (
            <div className="bg-white border-t border-neutral-200 py-3 px-10 flex items-center gap-6 mt-8">
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
        </main>
      </div>
    </div>
  );
}
