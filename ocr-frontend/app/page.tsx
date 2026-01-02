"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import ZipUpload from "@/components/ZipUpload";
import DealHistoryTable from "@/components/DealHistoryTable";

export default function Home() {
  const router = useRouter();

  const handleUploadSuccess = (packageId: string) => {
    // Navigation is handled by ZipUpload component
    console.log(`Package ${packageId} uploaded successfully`);
  };

  const handleUploadError = (error: string) => {
    console.error("Upload error:", error);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center">
            <svg
              className="h-8 w-8 text-blue-600 mr-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Financial Underwriting AI
              </h1>
              <p className="mt-1 text-sm text-gray-600">
                Upload deal packages for automated analysis and verification
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-8">
          {/* Upload Section */}
          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Upload Deal Package
            </h2>
            <ZipUpload
              onUploadSuccess={handleUploadSuccess}
              onUploadError={handleUploadError}
            />
          </section>

          {/* History Section */}
          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Previous Analyses
            </h2>
            <DealHistoryTable />
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-sm text-gray-500">
            Financial Underwriting AI - Powered by FastAPI & Next.js
          </p>
        </div>
      </footer>
    </div>
  );
}
