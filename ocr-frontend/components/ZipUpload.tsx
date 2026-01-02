"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import LoadingSpinner from "./LoadingSpinner";

interface ZipUploadProps {
  onUploadSuccess?: (packageId: string) => void;
  onUploadError?: (error: string) => void;
}

interface DocumentMetadata {
  document_id: string;
  filename: string;
  document_type: string;
  upload_timestamp: string;
  file_size: number;
}

interface DealPackage {
  package_id: string;
  property_name: string;
  created_at: string;
  documents: Record<string, DocumentMetadata[]>;
}

interface DocumentTypeInfo {
  type: string;
  folder_examples: string[];
}

export default function ZipUpload({
  onUploadSuccess,
  onUploadError,
}: ZipUploadProps) {
  const router = useRouter();
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dealPackage, setDealPackage] = useState<DealPackage | null>(null);
  const [documentTypes, setDocumentTypes] = useState<DocumentTypeInfo[]>([]);
  const [isLoadingTypes, setIsLoadingTypes] = useState(true);

  // Fetch document types from backend on component mount
  useEffect(() => {
    const fetchDocumentTypes = async () => {
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_FINANCIAL_ENGINE_URL || 'http://localhost:8001'}/api/v1/multi-document/document-types`
        );
        
        if (response.ok) {
          const data: DocumentTypeInfo[] = await response.json();
          setDocumentTypes(data);
        } else {
          console.error("Failed to fetch document types");
        }
      } catch (err) {
        console.error("Error fetching document types:", err);
      } finally {
        setIsLoadingTypes(false);
      }
    };

    fetchDocumentTypes();
  }, []);

  const validateFile = (file: File): string | null => {
    // Check file type
    if (!file.name.endsWith('.zip')) {
      return "Only ZIP files are allowed";
    }

    // Check file size (max 100MB for ZIP)
    const maxSize = 100 * 1024 * 1024; // 100MB
    if (file.size > maxSize) {
      return "File size must be less than 100MB";
    }

    return null;
  };

  const handleUpload = async (file: File) => {
    setError(null);
    setSuccess(null);
    setDealPackage(null);

    // Validate file
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      if (onUploadError) {
        onUploadError(validationError);
      }
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append("file", file);
      
      // Extract property name from filename (remove .zip and _Inputs suffix)
      const propertyName = file.name
        .replace('.zip', '')
        .replace('_Inputs', '')
        .replace(/_/g, ' ');
      formData.append("property_name", propertyName);

      // Upload to backend
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_FINANCIAL_ENGINE_URL || 'http://localhost:8001'}/api/v1/multi-document/packages/upload-zip`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Upload failed");
      }

      const data: DealPackage = await response.json();
      setDealPackage(data);
      
      const documentCount = Object.values(data.documents).reduce(
        (sum, docs) => sum + docs.length,
        0
      );

      setSuccess(
        `Successfully uploaded "${propertyName}" with ${documentCount} documents across ${Object.keys(data.documents).length} categories!`
      );

      if (onUploadSuccess) {
        onUploadSuccess(data.package_id);
      }

      // Redirect to verification page after 2 seconds
      setTimeout(() => {
        router.push(`/verification/${data.package_id}`);
      }, 2000);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Upload failed";
      setError(errorMessage);

      if (onUploadError) {
        onUploadError(errorMessage);
      }
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleUpload(files[0]);
    }
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleUpload(files[0]);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto">
      <div
        className={`
          relative border-2 border-dashed rounded-lg p-12 text-center transition-colors
          ${
            isDragging
              ? "border-blue-500 bg-blue-50"
              : "border-gray-300 bg-white"
          }
          ${
            isUploading
              ? "pointer-events-none opacity-60"
              : "hover:border-blue-400"
          }
        `}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {isUploading ? (
          <div className="space-y-4">
            <LoadingSpinner size="lg" className="mx-auto" />
            <div className="space-y-2">
              <p className="text-gray-700 font-medium text-lg">
                Processing ZIP file...
              </p>
              <p className="text-sm text-gray-600">
                Extracting and categorizing documents
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="mx-auto w-24 h-24 mb-4">
              <svg
                className="w-full h-full text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
            </div>
            <div className="space-y-4">
            <div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">
                Upload Deal Package
              </h3>
              <p className="text-sm text-gray-600 mb-4">
                {isLoadingTypes
                  ? "Upload a ZIP file with organized document folders"
                  : documentTypes.length > 0
                  ? `Upload a ZIP file containing ${documentTypes.length} document categories`
                  : "Upload a ZIP file with organized document folders"
                }
              </p>
            </div>
              
              <label
                htmlFor="zip-upload"
                className="cursor-pointer inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
              >
                <svg
                  className="w-5 h-5 mr-2"
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
                Choose Deal Package ZIP
                <input
                  id="zip-upload"
                  name="zip-upload"
                  type="file"
                  className="sr-only"
                  accept=".zip,application/zip"
                  onChange={handleFileInput}
                  disabled={isUploading}
                />
              </label>
              
              <p className="text-sm text-gray-600">or drag and drop</p>
              <p className="text-xs text-gray-500">ZIP files up to 100MB</p>
            </div>

            {/* Expected Structure Info - Dynamic */}
            <div className="mt-8 bg-gray-50 rounded-lg p-4 text-left">
              <h4 className="text-sm font-semibold text-gray-700 mb-2">
                Expected ZIP Structure:
              </h4>
              {isLoadingTypes ? (
                <div className="flex items-center justify-center py-4">
                  <LoadingSpinner size="sm" />
                  <span className="ml-2 text-xs text-gray-500">Loading structure...</span>
                </div>
              ) : documentTypes.length > 0 ? (
                <div className="text-xs text-gray-600 font-mono space-y-1">
                  <div>📦 Property_Name_Inputs.zip</div>
                  {documentTypes.map((docType, index) => (
                    <div key={docType.type} className="ml-4">
                      📂 {docType.folder_examples[0] || docType.type}
                    </div>
                  ))}
                  <div className="mt-3 text-xs text-gray-500 font-sans">
                    <p className="font-semibold mb-1">Supported folder naming:</p>
                    <ul className="space-y-1">
                      {documentTypes.slice(0, 3).map((docType) => (
                        <li key={docType.type}>
                          • {docType.type}: {docType.folder_examples.join(", ")}
                        </li>
                      ))}
                      {documentTypes.length > 3 && (
                        <li className="text-gray-400">...and more</li>
                      )}
                    </ul>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-gray-600 font-mono space-y-1">
                  <div>📦 Property_Name_Inputs.zip</div>
                  <div className="ml-4">📂 Multi-folder structure supported</div>
                  <div className="ml-4 text-gray-500 font-sans mt-2">
                    Upload a ZIP file with organized document folders
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Success Message with Package Details */}
      {success && dealPackage && (
        <div className="mt-4 p-6 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-start">
            <svg
              className="h-6 w-6 text-green-400 mr-3 mt-0.5"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            <div className="flex-1">
              <p className="text-sm font-medium text-green-800">{success}</p>
              <div className="mt-3 text-sm text-green-700">
                <p className="font-semibold mb-2">Documents by Category:</p>
                <ul className="space-y-1">
                  {Object.entries(dealPackage.documents).map(([type, docs]) => (
                    <li key={type} className="flex items-center">
                      <span className="inline-block w-2 h-2 bg-green-500 rounded-full mr-2"></span>
                      {type}: {docs.length} file{docs.length !== 1 ? 's' : ''}
                    </li>
                  ))}
                </ul>
              </div>
              <p className="mt-3 text-xs text-green-600">
                Redirecting to verification page...
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center">
            <svg
              className="h-5 w-5 text-red-400 mr-2"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            <p className="text-sm text-red-800">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}
