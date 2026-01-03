"use client";

import { useState } from "react";
import ZipUpload from "@/components/ZipUpload";
import DealHistoryTable from "@/components/DealHistoryTable";

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<'upload' | 'history'>('upload');

  const handleUploadSuccess = (packageId: string) => {
    console.log(`Package ${packageId} uploaded successfully`);
  };

  const handleUploadError = (error: string) => {
    console.error("Upload error:", error);
  };

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
      {/* Navigation */}
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16">
                <div className="flex items-center">
                    <a href="/" className="flex-shrink-0 flex items-center group">
                            <div className="h-8 w-8 bg-blue-600 rounded-lg flex items-center justify-center mr-2 group-hover:bg-blue-700 transition-colors">
                            <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                            </svg>
                            </div>
                            <span className="font-bold text-xl tracking-tight text-slate-900">Financial Underwriting <span className="text-blue-600">AI</span></span>
                    </a>
                </div>
                    <div className="flex items-center space-x-4">
                    <a href="/" className="text-sm font-medium text-slate-500 hover:text-slate-900">Home</a>
                    <span className="text-slate-300">/</span>
                    <span className="text-sm font-medium text-blue-600">Dashboard</span>
                </div>
            </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="text-center mb-10">
            <h1 className="text-3xl font-bold text-slate-900">Analysis Workspace</h1>
            <p className="mt-2 text-slate-500">Manage your deals, start new analyses, or download templates.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl mx-auto mb-10">
                <div
                onClick={() => setActiveTab('upload')}
                className={`cursor-pointer px-4 py-3 rounded-xl border transition-all group flex flex-col items-center text-center hover:scale-[1.01] duration-200 ${
                    activeTab === 'upload'
                    ? 'border-blue-600 bg-blue-50/60 shadow-md ring-1 ring-blue-600'
                    : 'border-slate-200 bg-white hover:border-blue-400 hover:shadow-lg hover:bg-slate-50'
                }`}
                >
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center mb-2 transition-colors shadow-sm ${
                        activeTab === 'upload' ? 'bg-blue-600 text-white' : 'bg-white border border-slate-200 text-slate-500 group-hover:text-blue-600 group-hover:border-blue-200'
                }`}>
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                </div>
                <h3 className={`text-sm font-bold mb-0.5 ${activeTab === 'upload' ? 'text-blue-900' : 'text-slate-700'}`}>New Analysis</h3>
                <p className="text-xs text-slate-500 line-clamp-1 px-2">Upload a new deal package (ZIP) to extract & analyze.</p>
                </div>

                <div
                onClick={() => setActiveTab('history')}
                className={`cursor-pointer px-4 py-3 rounded-xl border transition-all group flex flex-col items-center text-center hover:scale-[1.01] duration-200 ${
                    activeTab === 'history'
                    ? 'border-blue-600 bg-blue-50/60 shadow-md ring-1 ring-blue-600'
                    : 'border-slate-200 bg-white hover:border-blue-400 hover:shadow-lg hover:bg-slate-50'
                }`}
                >
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center mb-2 transition-colors shadow-sm ${
                        activeTab === 'history' ? 'bg-blue-600 text-white' : 'bg-white border border-slate-200 text-slate-500 group-hover:text-blue-600 group-hover:border-blue-200'
                }`}>
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                </div>
                <h3 className={`text-sm font-bold mb-0.5 ${activeTab === 'history' ? 'text-blue-900' : 'text-slate-700'}`}>Deal History</h3>
                <p className="text-xs text-slate-500 line-clamp-1 px-2">View past analyses, continue pending verifications, or export.</p>
                </div>
        </div>

        {/* Dynamic Content Area */}
        <div className="bg-slate-50 rounded-3xl border border-slate-200 overflow-hidden min-h-[500px] shadow-inner">
            {activeTab === 'upload' && (
                <div className="p-8 lg:p-12 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="max-w-4xl mx-auto">
                        <div className="flex justify-between items-center mb-8">
                            <div>
                                <h3 className="text-2xl font-bold text-slate-900">Upload Deal Package</h3>
                                <p className="text-slate-500">Supported formats: PDF, Excel within a ZIP archive.</p>
                            </div>
                            <a
                                href="/template.zip"
                                download="Correct_Inputs_Template.zip"
                                className="inline-flex items-center px-4 py-2 bg-white border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 hover:text-blue-600 transition-colors"
                            >
                                <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                                Download Template
                            </a>
                        </div>
                        <ZipUpload 
                            onUploadSuccess={handleUploadSuccess}
                            onUploadError={handleUploadError}
                        />
                    </div>
                </div>
            )}

            {activeTab === 'history' && (
                <div className="p-8 lg:p-12 animate-in fade-in slide-in-from-bottom-4 duration-500">
                        <div className="flex justify-between items-center mb-8">
                        <div>
                            <h3 className="text-2xl font-bold text-slate-900">Recent Deals</h3>
                            <p className="text-slate-500">Track the status of your underwriting pipeline.</p>
                        </div>
                        <button onClick={() => setActiveTab('upload')} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors shadow-sm">
                            + New Deal
                        </button>
                        </div>
                    <DealHistoryTable />
                </div>
            )}
        </div>
      </main>
    </div>
  );
}