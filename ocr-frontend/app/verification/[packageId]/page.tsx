"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import DataVerificationTable, {
  NormalizedDataItem,
} from "@/components/DataVerificationTable";
import LoadingSpinner from "@/components/LoadingSpinner";
import { apiClient } from "@/lib/api";
import { FinancialAnalysisProgress } from "@/lib/types";

interface DocumentMetadata {
  document_id: string;
  filename: string;
  document_type: string;
}

interface DealPackage {
  package_id: string;
  property_name: string;
  created_at: string;
  documents: Record<string, DocumentMetadata[]>;
  normalization_status: string;
  verification_progress: number;
}

const EXPENSE_CATEGORIES = [
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
  "Uncategorized",
];

export default function VerificationPage() {
  const params = useParams();
  const router = useRouter();
  const packageId = params.packageId as string;

  const [dealPackage, setDealPackage] = useState<DealPackage | null>(null);
  const [normalizedItems, setNormalizedItems] = useState<NormalizedDataItem[]>(
    []
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [normalizing, setNormalizing] = useState(false);
  const [progress, setProgress] = useState<FinancialAnalysisProgress>({ percentage: 0, message: "" });

  const baseUrl =
    process.env.NEXT_PUBLIC_FINANCIAL_API_URL;

  // Fetch deal package details
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

      // Update local state
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
    } catch (err) {
      console.error("Error verifying item:", err);
    }
  };

  // Verify all items
  const handleVerifyAll = () => {
    setNormalizedItems((prev) =>
      prev.map((item) => ({ ...item, user_verified: true }))
    );
  };

  // Proceed to analysis
  const handleProceedToAnalysis = () => {
    router.push(`/analysis/${packageId}`);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" />
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
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Go Home
          </button>
        </div>
      </div>
    );
  }

  const allVerified =
    normalizedItems.length > 0 &&
    normalizedItems.every((item) => item.user_verified);

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => router.push("/")}
            className="text-blue-600 hover:text-blue-800 mb-4 flex items-center"
          >
            <svg
              className="w-5 h-5 mr-1"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
            Back to Home
          </button>

          <h1 className="text-3xl font-bold text-gray-900">
            {dealPackage?.property_name || "Deal Package"}
          </h1>
          <p className="text-gray-600 mt-2">
            Package ID: {packageId}
          </p>
        </div>

        {/* Package Summary */}
        {dealPackage && (
          <div className="bg-white rounded-lg shadow p-6 mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Document Summary
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(dealPackage.documents).map(([type, docs]) => (
                <div
                  key={type}
                  className="bg-gray-50 rounded-lg p-4 text-center"
                >
                  <div className="text-2xl font-bold text-blue-600">
                    {docs.length}
                  </div>
                  <div className="text-sm text-gray-600 mt-1">{type}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Normalization Section */}
        {normalizedItems.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <div className="max-w-md mx-auto">
              <svg
                className="mx-auto h-16 w-16 text-gray-400 mb-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">
                Ready to Normalize Data
              </h3>
              {!normalizing ? (
                <>
                  <p className="text-gray-600 mb-6">
                    Click the button below to extract and normalize data from your
                    uploaded documents. The AI will map expense categories and other
                    fields to standardized values.
                  </p>
                  <button
                    onClick={handleNormalize}
                    className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
                  >
                    Start Normalization
                  </button>
                </>
              ) : (
                <div className="w-full max-w-md mx-auto mt-6">
                  <div className="flex items-center justify-center mb-4">
                    <LoadingSpinner size="lg" />
                  </div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    {progress.message || "Normalizing..."}
                  </h3>

                  <div className="w-full bg-gray-200 rounded-full h-4 mb-2 overflow-hidden">
                    <div
                      className="bg-blue-600 h-4 rounded-full transition-all duration-300 ease-out"
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
              )}
            </div>
          </div>
        ) : (
          <>
            {/* Verification Table */}
            <DataVerificationTable
              items={normalizedItems}
              availableCategories={EXPENSE_CATEGORIES}
              onVerify={handleVerifyItem}
              onVerifyAll={handleVerifyAll}
            />

            {/* Proceed Button */}
            {allVerified && (
              <div className="mt-8 bg-white rounded-lg shadow p-6 text-center">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  All Items Verified! ✓
                </h3>
                <p className="text-gray-600 mb-4">
                  You can now proceed to financial analysis
                </p>
                <button
                  onClick={handleProceedToAnalysis}
                  className="px-6 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 font-medium"
                >
                  Proceed to Analysis →
                </button>
              </div>
            )}
          </>
        )}

        {/* Error Display */}
        {error && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}
