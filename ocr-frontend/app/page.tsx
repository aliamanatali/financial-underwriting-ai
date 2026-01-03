"use client";

import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
        {/* Navigation - Professional & Minimal */}
        <nav className="bg-white border-b border-slate-200 sticky top-0 z-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between h-16">
                    <div className="flex items-center">
                        <div className="flex-shrink-0 flex items-center">
                             <div className="h-8 w-8 bg-blue-600 rounded-lg flex items-center justify-center mr-2">
                                <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                </svg>
                             </div>
                             <span className="font-bold text-xl tracking-tight text-slate-900">Financial Underwriting <span className="text-blue-600">AI</span></span>
                        </div>
                    </div>
                    <div className="flex items-center space-x-4">
                        <a href="#how-it-works" className="text-sm font-medium text-slate-500 hover:text-slate-900">How it Works</a>
                        <Link href="/dashboard" className="text-sm font-medium text-slate-500 hover:text-slate-900">Workspace</Link>
                        <button className="bg-slate-900 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-slate-800 transition-colors">
                            Contact Sales
                        </button>
                    </div>
                </div>
            </div>
        </nav>

        {/* Hero Section */}
        <div className="relative bg-white overflow-hidden">
            <div className="max-w-7xl mx-auto">
                <div className="relative z-10 pb-8 bg-white sm:pb-16 md:pb-20 lg:max-w-2xl lg:w-full lg:pb-28 xl:pb-32">
                    <svg
                        className="hidden lg:block absolute right-0 inset-y-0 h-full w-48 text-white transform translate-x-1/2"
                        fill="currentColor"
                        viewBox="0 0 100 100"
                        preserveAspectRatio="none"
                        aria-hidden="true"
                    >
                        <polygon points="50,0 100,0 50,100 0,100" />
                    </svg>

                    <main className="mt-10 mx-auto max-w-7xl px-4 sm:mt-12 sm:px-6 md:mt-16 lg:mt-20 lg:px-8 xl:mt-28">
                        <div className="sm:text-center lg:text-left">
                            <h1 className="text-4xl tracking-tight font-extrabold text-slate-900 sm:text-5xl md:text-6xl">
                                <span className="block xl:inline">Automated Financial</span>{' '}
                                <span className="block text-blue-600 xl:inline">Underwriting</span>
                            </h1>
                            <p className="mt-3 text-base text-slate-500 sm:mt-5 sm:text-lg sm:max-w-xl sm:mx-auto md:mt-5 md:text-xl lg:mx-0">
                                Accelerate your deal flow. Upload messy OMs, Rent Rolls, and T12s. We extract, normalize, and analyze the data instantly.
                            </p>
                            <div className="mt-5 sm:mt-8 sm:flex sm:justify-center lg:justify-start">
                                <div className="rounded-md shadow">
                                    <Link
                                        href="/dashboard"
                                        className="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 md:py-4 md:text-lg"
                                    >
                                        Start Analysis
                                    </Link>
                                </div>
                                <div className="mt-3 sm:mt-0 sm:ml-3">
                                    <a
                                        href="/template.zip"
                                        download="Correct_Inputs_Template.zip"
                                        className="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-blue-700 bg-blue-100 hover:bg-blue-200 md:py-4 md:text-lg"
                                    >
                                        Download Template
                                    </a>
                                </div>
                            </div>
                        </div>
                    </main>
                </div>
            </div>
            <div className="lg:absolute lg:inset-y-0 lg:right-0 lg:w-1/2 bg-slate-50 flex items-center justify-center">
                 {/* Abstract visual or placeholder for hero image */}
                 <div className="w-full h-full object-cover flex items-center justify-center text-slate-200 bg-slate-100">
                    <svg className="w-64 h-64 opacity-20" fill="currentColor" viewBox="0 0 20 20">
                         <path fillRule="evenodd" d="M6 2a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V7.414A2 2 0 0015.414 6L12 2.586A2 2 0 0010.586 2H6zm2 10a1 1 0 10-2 0v3a1 1 0 102 0v-3zm2-3a1 1 0 011 1v5a1 1 0 11-2 0v-5a1 1 0 011-1zm4-1a1 1 0 10-2 0v7a1 1 0 102 0V8z" clipRule="evenodd" />
                    </svg>
                 </div>
            </div>
        </div>

        {/* User Journey Section */}
        <section id="how-it-works" className="py-16 bg-white border-t border-slate-100">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="text-center mb-12">
                    <h2 className="text-3xl font-extrabold text-slate-900">How It Works</h2>
                    <p className="mt-4 text-lg text-slate-500">From raw documents to actionable insights in three simple steps.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    {/* Step 1 */}
                    <div className="relative p-6 bg-slate-50 rounded-xl border border-slate-100 hover:shadow-lg transition-shadow group">
                        <div className="absolute top-0 right-0 -mt-4 -mr-4 w-12 h-12 bg-blue-600 text-white rounded-full flex items-center justify-center text-xl font-bold shadow-md group-hover:bg-blue-700 transition-colors">1</div>
                        <div className="h-12 w-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4 text-blue-600">
                             <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">Upload Package</h3>
                        <p className="text-slate-600">Simply drag and drop your deal folder containing the OM, Rent Roll, and Financial statements (T12). We support PDF and Excel formats.</p>
                    </div>

                    {/* Step 2 */}
                    <div className="relative p-6 bg-slate-50 rounded-xl border border-slate-100 hover:shadow-lg transition-shadow group">
                        <div className="absolute top-0 right-0 -mt-4 -mr-4 w-12 h-12 bg-blue-600 text-white rounded-full flex items-center justify-center text-xl font-bold shadow-md group-hover:bg-blue-700 transition-colors">2</div>
                        <div className="h-12 w-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4 text-blue-600">
                            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">AI Extraction</h3>
                        <p className="text-slate-600">Our advanced OCR and Financial Engine identify, extract, and normalize data, handling messy scans and complex tables with ease.</p>
                    </div>

                    {/* Step 3 */}
                    <div className="relative p-6 bg-slate-50 rounded-xl border border-slate-100 hover:shadow-lg transition-shadow group">
                         <div className="absolute top-0 right-0 -mt-4 -mr-4 w-12 h-12 bg-blue-600 text-white rounded-full flex items-center justify-center text-xl font-bold shadow-md group-hover:bg-blue-700 transition-colors">3</div>
                        <div className="h-12 w-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4 text-blue-600">
                             <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">Verify & Analyze</h3>
                        <p className="text-slate-600">Review the extracted data with side-by-side source verification, then generate comprehensive underwriting models instantly.</p>
                    </div>
                </div>
            </div>
        </section>

        {/* Footer */}
        <footer className="bg-white border-t border-slate-200 py-12">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between items-center">
                    <div>
                         <span className="font-bold text-xl text-slate-900">Financial Underwriting <span className="text-blue-600">AI</span></span>
                         <p className="mt-2 text-sm text-slate-500">Intelligent automation for commercial real estate.</p>
                    </div>
                    <div className="text-sm text-slate-400">
                        &copy; 2026 Financial Underwriting AI. All rights reserved.
                    </div>
                </div>
            </div>
        </footer>
    </div>
  );
}
