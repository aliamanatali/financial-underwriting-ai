"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { UnderwritingAnalysis } from "@/lib/types";
import LoadingSpinner from "@/components/LoadingSpinner";
import UnderwritingDashboard from "@/components/UnderwritingDashboard";
import AuditTrailWidget from "@/components/AuditTrailWidget";
import ExportButtons from "@/components/ExportButtons";

export default function AnalysisResultPage() {
  const params = useParams();
  const id = params.id as string;
  const [analysis, setAnalysis] = useState<UnderwritingAnalysis | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"dashboard" | "audit" | "export">(
    "dashboard"
  );

  const API_BASE_URL = process.env.NEXT_PUBLIC_FINANCIAL_API_URL;

  useEffect(() => {
    if (id) {
      const fetchAnalysis = async () => {
        try {
          setIsLoading(true);
          setError(null);

          console.log(`Starting analysis for document: ${id}`);
          console.log(`API URL: ${API_BASE_URL}`);

          // First, check if this is a multi-document package
          let isPackage = false;
          try {
            const packageCheck = await fetch(`${API_BASE_URL}/api/v1/multi-document/packages/${id}`);
            if (packageCheck.ok) {
              isPackage = true;
              console.log("Detected multi-document package");
            }
          } catch (e) {
            // Not a package, continue with single-document flow
            console.log("Not a package, using single-document flow");
          }

          let response;
          if (isPackage) {
            // Use multi-document analysis endpoint
            response = await fetch(`${API_BASE_URL}/api/v1/multi-document/packages/${id}/analyze`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                growth_rate: 0.03,
                exit_cap_rate: 0.06,
                vacancy_rate: 0.03,
                loan_amount: 5000000,
                min_unit_count: 15,
                max_unit_count: 80,
                max_build_year: 1970,
              }),
            });
          } else {
            // Use single-document analysis endpoint
            response = await fetch(`${API_BASE_URL}/api/v1/analysis/${id}`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                growth_rate: 0.03,
                exit_cap_rate: 0.06,
                vacancy_rate: 0.03,
                loan_amount: 5000000,
              }),
            });
          }

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: "Unknown error" }));
            const errorMessage = errorData.detail || `HTTP ${response.status}: ${response.statusText}`;
            throw new Error(`Analysis failed: ${errorMessage}`);
          }

          const result: UnderwritingAnalysis = await response.json();
          setAnalysis(result);
          setError(null);
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : "Failed to fetch analysis results.";
          console.error("Analysis error:", errorMessage, err);
          setError(errorMessage);
        } finally {
          setIsLoading(false);
        }
      };
      fetchAnalysis();
    }
  }, [id, API_BASE_URL]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <LoadingSpinner />
          <h2 className="mt-6 text-2xl font-bold text-gray-900">Analyzing Deal...</h2>
          <p className="mt-2 text-gray-600">
            Extracting documents and performing financial calculations
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    // Determine if this is a package or single document based on the ID format or error
    const isLikelyPackage = error.includes('package') || error.includes('multi-document') || error.includes('Deal package');
    
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <div className="flex items-start">
              <svg
                className="h-6 w-6 text-red-600 mr-4 mt-0.5 flex-shrink-0"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
              <div className="flex-1">
                <h2 className="text-2xl font-bold text-red-900 mb-2">Analysis Failed</h2>
                <p className="text-red-700 mb-6 font-mono text-sm bg-red-100 p-4 rounded break-words">
                  {error}
                </p>
                <div className="bg-red-100 p-4 rounded mb-6 text-sm text-red-800">
                  <p className="font-semibold mb-2">Troubleshooting Tips:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Ensure the financial-engine backend is running on <code className="bg-red-50 px-2 py-1 rounded">{API_BASE_URL}</code></li>
                    {isLikelyPackage ? (
                      <>
                        <li>Verify the deal package was successfully uploaded via the multi-document upload page</li>
                        <li>Check that the package ID is correct: <code className="bg-red-50 px-2 py-1 rounded">{id}</code></li>
                        <li>The package may have been deleted or expired from storage</li>
                        <li>Try re-uploading your ZIP file with the deal package documents</li>
                      </>
                    ) : (
                      <>
                        <li>Verify the document was successfully processed by OCR backend</li>
                        <li>Check that the document ID is correct: <code className="bg-red-50 px-2 py-1 rounded">{id}</code></li>
                        <li>The document may have been deleted or expired from storage</li>
                        <li>Try re-uploading your document</li>
                      </>
                    )}
                    <li>Verify network connectivity and firewall settings</li>
                    <li>Check browser console (F12) for additional error details</li>
                  </ul>
                </div>
                <div className="flex gap-4">
                  <a
                    href="/"
                    className="inline-block px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
                  >
                    ← Back to Upload
                  </a>
                  <button
                    onClick={() => window.location.reload()}
                    className="inline-block px-6 py-2 bg-red-100 text-red-700 border border-red-300 rounded-lg hover:bg-red-200 transition"
                  >
                    🔄 Retry
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!analysis) {
    return <div className="text-center mt-10">No analysis data found.</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Financial Analysis</h1>
              <p className="mt-1 text-sm text-gray-600">Document ID: {id}</p>
            </div>
            <a
              href="/"
              className="inline-block px-4 py-2 text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition"
            >
              ← New Analysis
            </a>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Tabs */}
        <div className="flex gap-4 mb-8 border-b">
          {[
            { id: "dashboard", label: "📊 Underwriting Dashboard" },
            { id: "audit", label: "🔍 Audit Trail" },
            { id: "export", label: "📥 Download & Export" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-4 py-3 font-semibold border-b-2 transition ${
                activeTab === tab.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-600 hover:text-gray-900"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === "dashboard" && <UnderwritingDashboard analysis={analysis} />}

        {activeTab === "audit" && (
          <AuditTrailWidget auditTrail={(analysis.audit_trail as any) || []} />
        )}

        {activeTab === "export" && (
          <div className="space-y-6">
            <ExportButtons analysis={analysis} />

            {/* Summary Info */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h3 className="text-lg font-bold text-gray-900 mb-4">Export Summary</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="font-semibold text-gray-900 mb-3">Excel Model Includes:</h4>
                  <ul className="space-y-2 text-sm text-gray-700">
                    <li>✓ Property meta data (address, units, year built)</li>
                    <li>✓ T12 (Historical) financials with actual rents</li>
                    <li>✓ F12 (Pro Forma) projections with market rents</li>
                    <li>✓ Expense breakdown by category</li>
                    <li>✓ NOI and Cap Rate calculations</li>
                    <li>✓ Professional formatting for Investment Committee</li>
                  </ul>
                </div>
                <div>
                  <h4 className="font-semibold text-gray-900 mb-3">Investment Memo Includes:</h4>
                  <ul className="space-y-2 text-sm text-gray-700">
                    <li>✓ Executive Summary</li>
                    <li>✓ Key Questions & Answers</li>
                    <li>✓ SWOT Analysis</li>
                    <li>✓ Investment Highlights</li>
                    <li>✓ Risk Assessment & Mitigation</li>
                    <li>✓ Deal Viability Status</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
