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

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    if (id) {
      const fetchAnalysis = async () => {
        try {
          setIsLoading(true);

          // Trigger the analysis endpoint
          const response = await fetch(`${API_BASE_URL}/api/v1/analysis/${id}`, {
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

          if (!response.ok) {
            throw new Error(`Analysis failed: ${response.statusText}`);
          }

          const result: UnderwritingAnalysis = await response.json();
          setAnalysis(result);
          setError(null);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Failed to fetch analysis results.");
          console.error(err);
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
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <h2 className="text-2xl font-bold text-red-900 mb-2">❌ Analysis Failed</h2>
            <p className="text-red-700 mb-4">{error}</p>
            <a
              href="/"
              className="inline-block px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
            >
              ← Back to Upload
            </a>
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
