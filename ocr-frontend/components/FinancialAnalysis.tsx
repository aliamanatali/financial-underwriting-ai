"use client";

import { useState } from 'react';
import { apiClient } from '@/lib/api';
import { UnderwritingAnalysis, DealParameters } from '@/lib/types';
import LoadingSpinner from './LoadingSpinner';
import UnderwritingDashboard from './UnderwritingDashboard';

interface FinancialAnalysisProps {
  documentId: string;
}

export default function FinancialAnalysis({ documentId }: FinancialAnalysisProps) {
  const [analysis, setAnalysis] = useState<UnderwritingAnalysis | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStartAnalysis = async () => {
    setIsLoading(true);
    setError(null);
    try {
      // Use the new function that sends default parameters
      const result = await apiClient.startUnderwritingAnalysis(documentId);
      setAnalysis(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start analysis');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownload = async (type: 'excel' | 'memo') => {
    if (!analysis) return;
    try {
      await apiClient.downloadExport(analysis, type);
    } catch (err) {
      alert(`Failed to download ${type}`);
    }
  };

  return (
    <div className="bg-white shadow rounded-lg p-6 mt-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-2xl font-bold text-gray-800">Underwriting Analysis</h3>
        <button
          onClick={handleStartAnalysis}
          disabled={isLoading}
          className="inline-flex items-center px-6 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
        >
          {isLoading ? <LoadingSpinner size="sm" /> : 'Run Analysis'}
        </button>
      </div>

      {error && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4" role="alert">
          <p className="font-bold">Analysis failed</p>
          <p>{error}</p>
        </div>
      )}

      {analysis ? (
        <div className="mt-6">
          <UnderwritingDashboard analysis={analysis} />
          <div className="mt-6 text-right">
            <button 
              onClick={() => handleDownload('excel')} 
              className="mr-2 px-4 py-2 bg-green-700 text-white rounded-md hover:bg-green-800"
            >
              Download Excel
            </button>
            <button 
              onClick={() => handleDownload('memo')} 
              className="px-4 py-2 bg-gray-700 text-white rounded-md hover:bg-gray-800"
            >
              Download Memo
            </button>
          </div>
        </div>
      ) : (
        <div className="text-center py-12 text-gray-500">
            <p>Click "Run Analysis" to view the underwriting dashboard.</p>
        </div>
      )}
    </div>
  );
}