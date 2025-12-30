"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import DocumentUpload from '@/components/DocumentUpload';
import { apiClient } from '@/lib/api';
import { UploadProgress } from '@/lib/types';

export default function UploadPage() {
  const router = useRouter();
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleUploadSuccess = (documentId: string, taskId: string) => {
    // Redirect to the analysis page on successful upload
    router.push(`/analysis/${documentId}`);
  };

  const handleUploadError = (error: string) => {
    setError(error);
  };

  return (
    <div className="container mx-auto p-8 flex flex-col items-center justify-center min-h-screen">
      <div className="w-full max-w-2xl">
        <h1 className="text-4xl font-bold text-center mb-4">Valiance Capital Underwriting AI</h1>
        <p className="text-lg text-gray-600 text-center mb-8">
          Upload a deal package (PDF) to begin the automated analysis.
        </p>
        
        <DocumentUpload
          onUploadSuccess={handleUploadSuccess}
          onUploadError={handleUploadError}
        />

        {error && (
          <div className="mt-6 p-4 bg-red-100 border border-red-300 rounded-lg text-red-800 text-center">
            <p className="font-bold">Upload Failed</p>
            <p>{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}