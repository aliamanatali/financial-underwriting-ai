"use client";

import ZipUpload from "@/components/ZipUpload";

export default function UploadPackagePage() {
  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Upload Deal Package
          </h1>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Upload a ZIP file containing all 8 document categories for automated
            extraction, normalization, and financial analysis.
          </p>
        </div>

        {/* Upload Component */}
        <ZipUpload />

        {/* Information Section */}
        <div className="mt-16 grid md:grid-cols-3 gap-8">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
              <svg
                className="w-6 h-6 text-blue-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              1. Upload ZIP
            </h3>
            <p className="text-gray-600 text-sm">
              Upload a ZIP file with the 8-folder structure containing all deal
              documents (OM, Rent Roll, Financials, etc.)
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mb-4">
              <svg
                className="w-6 h-6 text-green-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              2. Verify Data
            </h3>
            <p className="text-gray-600 text-sm">
              Review AI-extracted data in a split-screen view. Correct any
              misclassified expense categories or other fields.
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mb-4">
              <svg
                className="w-6 h-6 text-purple-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              3. Analyze
            </h3>
            <p className="text-gray-600 text-sm">
              Get comprehensive financial analysis including NOI, Cap Rate, and
              pass/fail recommendations based on your criteria.
            </p>
          </div>
        </div>

        {/* Document Types Reference */}
        <div className="mt-12 bg-white rounded-lg shadow p-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">
            Required Document Categories
          </h2>
          <div className="grid md:grid-cols-2 gap-4">
            {[
              {
                number: "01",
                name: "Offering Memorandum",
                description: "Property marketing deck and overview",
              },
              {
                number: "02",
                name: "Rent Roll",
                description: "Current tenant and rent information",
              },
              {
                number: "03",
                name: "Leases",
                description: "Individual tenant lease agreements",
              },
              {
                number: "04",
                name: "Financials",
                description: "T12, P&L statements, income statements",
              },
              {
                number: "05",
                name: "Building Plans & Permits",
                description: "Floor plans, seismic reports, permits",
              },
              {
                number: "06",
                name: "Disclosures",
                description: "Property condition reports and disclosures",
              },
              {
                number: "07",
                name: "Tax Bills",
                description: "Property tax bills and assessments",
              },
              {
                number: "08",
                name: "Utilities",
                description: "Utility bills (electric, water, gas, etc.)",
              },
            ].map((category) => (
              <div
                key={category.number}
                className="flex items-start p-4 bg-gray-50 rounded-lg"
              >
                <div className="flex-shrink-0 w-10 h-10 bg-blue-600 text-white rounded-lg flex items-center justify-center font-bold mr-4">
                  {category.number}
                </div>
                <div>
                  <h4 className="font-semibold text-gray-900">
                    {category.name}
                  </h4>
                  <p className="text-sm text-gray-600 mt-1">
                    {category.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
