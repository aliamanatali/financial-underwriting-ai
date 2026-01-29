"use client";

import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api";
import WarningModal from "./WarningModal";
import { UploadProgress } from "@/lib/types";
import JSZip from "jszip";

interface SmartFileUploadProps {
  onUploadSuccess?: (packageId: string) => void;
  onUploadError?: (error: string) => void;
}

interface StagedFile {
  id: string;
  file: File;
  previewUrl?: string;
}

export default function SmartFileUpload({
  onUploadSuccess,
  onUploadError,
}: SmartFileUploadProps) {
  const router = useRouter();
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress>({ loaded: 0, total: 0, percentage: 0 });
  const [processingMessage, setProcessingMessage] = useState<string>("Initializing...");
  
  const [stagedFiles, setStagedFiles] = useState<StagedFile[]>([]);
  
  // Warning Modal State
  const [isWarningOpen, setIsWarningOpen] = useState(false);
  const [warningTitle, setWarningTitle] = useState("");
  const [warningMessage, setWarningMessage] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  const showWarning = (title: string, message: string) => {
    setWarningTitle(title);
    setWarningMessage(message);
    setIsWarningOpen(true);
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
    processAndAddFiles(files);
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      processAndAddFiles(files);
    }
    // Reset input value to allow selecting same files again if needed
    if (fileInputRef.current) {
        fileInputRef.current.value = "";
    }
  };

  const processAndAddFiles = async (files: File[]) => {
    setIsExtracting(true);
    const processedFiles: File[] = [];

    try {
      for (const file of files) {
        // If it's a ZIP file, extract it locally
        if (file.name.toLowerCase().endsWith('.zip')) {
          try {
            const zip = await JSZip.loadAsync(file);
            const extractions: Promise<void>[] = [];

            zip.forEach((relativePath, zipEntry) => {
              if (zipEntry.dir) return; // Skip directories
              // Skip macOS artifacts and hidden files
              if (zipEntry.name.includes('__MACOSX') || zipEntry.name.split('/').pop()?.startsWith('.')) return;

              const promise = zipEntry.async('blob').then((blob) => {
                // Determine mime type based on extension (simple check) or default
                const type = blob.type || 'application/octet-stream';
                const extractedFile = new File([blob], zipEntry.name, { type });
                processedFiles.push(extractedFile);
              });
              extractions.push(promise);
            });

            await Promise.all(extractions);
          } catch (err) {
            console.error("Error extracting zip:", err);
            // If extraction fails, just add the original zip
            processedFiles.push(file);
            showWarning("Zip Extraction Failed", `Could not extract ${file.name}. It will be uploaded as-is.`);
          }
        } else {
          processedFiles.push(file);
        }
      }
    } catch (error) {
      console.error("Error processing files:", error);
    } finally {
      setIsExtracting(false);
    }

    // Now add all processed files to stage
    addFiles(processedFiles);
  };

  const addFiles = (files: File[]) => {
    setStagedFiles(prev => {
      const newStagedFiles: StagedFile[] = [];
      
      files.forEach(file => {
        // Basic validation
        if (file.size === 0) return;
        
        // Check for duplicates
        if (prev.some(f => f.file.name === file.name && f.file.size === file.size)) {
            return;
        }

        const isImage = file.type.startsWith('image/') || /\.(jpg|jpeg|png|gif|webp)$/i.test(file.name);
        
        newStagedFiles.push({
          id: Math.random().toString(36).substring(7),
          file,
          previewUrl: isImage ? URL.createObjectURL(file) : undefined
        });
      });
      
      return [...prev, ...newStagedFiles];
    });
  };

  const removeFile = (id: string) => {
    setStagedFiles(prev => {
        const fileToRemove = prev.find(f => f.id === id);
        if (fileToRemove?.previewUrl) {
            URL.revokeObjectURL(fileToRemove.previewUrl);
        }
        return prev.filter(f => f.id !== id);
    });
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleUploadClick = async () => {
    if (stagedFiles.length === 0) return;

    setIsUploading(true);
    setUploadProgress({ loaded: 0, total: 0, percentage: 0 });
    setProcessingMessage("Preparing files...");

    try {
        let uploadFile: File;
        let isSmartUpload = true;

        // If single ZIP file, upload as is (but treat as smart upload if user selected it here)
        if (stagedFiles.length === 1 && stagedFiles[0].file.name.endsWith('.zip')) {
            uploadFile = stagedFiles[0].file;
            // If it's a pre-structured zip, we might still want smart upload to handle loose files inside?
            // The backend handles smart upload flag to unzip and classify.
            isSmartUpload = true; 
        } else {
            // Zip multiple files
            setProcessingMessage("Compressing files...");
            const zip = new JSZip();
            
            stagedFiles.forEach(sf => {
                zip.file(sf.file.name, sf.file);
            });
            
            const content = await zip.generateAsync({ type: "blob" });
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            const propertyName = stagedFiles.length > 0 ? stagedFiles[0].file.name.split('.')[0] + "_Package" : "Deal_Package";
            
            uploadFile = new File([content], `${propertyName}_${timestamp}.zip`, { type: "application/zip" });
        }

        setProcessingMessage("Uploading...");
        
        const dealPackage = await apiClient.uploadZipChunked(
            uploadFile, 
            (progress) => {
                setUploadProgress(progress);
            },
            (processing) => {
                setProcessingMessage(processing.message);
                // Map processing percentage to upper range if needed, or just display message
            },
            isSmartUpload
        );

        if (onUploadSuccess) {
            onUploadSuccess(dealPackage.package_id);
        }

    } catch (err) {
        console.error(err);
        const errorMessage = err instanceof Error ? err.message : "Upload failed";
        showWarning("Upload Failed", errorMessage);
        if (onUploadError) {
            onUploadError(errorMessage);
        }
    } finally {
        setIsUploading(false);
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Drop Zone */}
        <div
            className={`
            relative border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 ease-in-out flex flex-col items-center justify-center min-h-[400px]
            ${
                isDragging
                ? "border-[#FF5E00] bg-[#FFF5F0]/50 shadow-inner"
                : "border-slate-300 bg-slate-50/50 hover:bg-slate-50 hover:border-slate-400"
            }
            ${
                isUploading
                ? "pointer-events-none opacity-60"
                : "cursor-pointer"
            }
            `}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => !isUploading && fileInputRef.current?.click()}
        >
            <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={handleFileInput}
                disabled={isUploading}
            />
            
            <div className="w-20 h-20 mb-6 rounded-full bg-blue-50 flex items-center justify-center">
                <svg className="w-10 h-10 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
            </div>
            
            <h3 className="text-xl font-semibold text-gray-800 mb-2">Drop files here</h3>
            <p className="text-sm text-gray-500 mb-6 max-w-xs mx-auto">
                Support for PDF, Excel, CSV, Images, and ZIP archives.
                
            </p>
            
            <button
                className="px-6 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 transition-colors"
                disabled={isExtracting}
            >
                {isExtracting ? "Processing..." : "Select Files"}
            </button>
        </div>

        {/* Staging Area */}
        <div className="flex flex-col h-[400px] bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden relative">
            {isExtracting && (
                <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-50 flex flex-col items-center justify-center">
                    <div className="w-8 h-8 border-2 border-gray-200 border-t-[#FF5E00] rounded-full animate-spin mb-2"></div>
                    <p className="text-sm font-medium text-gray-600">Extracting files...</p>
                </div>
            )}
            
            <div className="p-4 border-b border-gray-100 bg-gray-50/50 flex justify-between items-center">
                <h3 className="font-semibold text-gray-800">Selected Files ({stagedFiles.length})</h3>
                {stagedFiles.length > 0 && (
                    <button
                        onClick={(e) => { e.stopPropagation(); setStagedFiles([]); }}
                        className="text-xs text-red-500 hover:text-red-700 font-medium"
                        disabled={isUploading || isExtracting}
                    >
                        Clear All
                    </button>
                )}
            </div>
            
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {stagedFiles.length === 0 && !isExtracting ? (
                    <div className="h-full flex flex-col items-center justify-center text-gray-400 space-y-2 opacity-60">
                        <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <p className="text-sm">No files selected yet</p>
                    </div>
                ) : (
                    stagedFiles.map((file) => (
                        <div key={file.id} className="group flex items-center p-3 bg-gray-50 rounded-lg border border-gray-100 hover:border-blue-200 transition-colors">
                            {/* File Icon/Preview */}
                            <div className="w-10 h-10 rounded bg-white border border-gray-200 flex items-center justify-center overflow-hidden flex-shrink-0 mr-3">
                                {file.previewUrl ? (
                                    <img src={file.previewUrl} alt="preview" className="w-full h-full object-cover" />
                                ) : (
                                    <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                                    </svg>
                                )}
                            </div>
                            
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-700 truncate" title={file.file.name}>{file.file.name}</p>
                                <p className="text-xs text-gray-500">{formatBytes(file.file.size)}</p>
                            </div>
                            
                            <button 
                                onClick={() => removeFile(file.id)}
                                className="p-1 text-gray-400 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
                                disabled={isUploading}
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                    ))
                )}
            </div>
            
            <div className="p-4 border-t border-gray-100 bg-gray-50">
                {isUploading ? (
                    <div className="space-y-3">
                        <div className="flex justify-between text-xs font-medium text-gray-600">
                            <span>{processingMessage}</span>
                            <span>{uploadProgress.percentage}%</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                            <div 
                                className="bg-[#FF5E00] h-2 rounded-full transition-all duration-300 ease-in-out" 
                                style={{ width: `${uploadProgress.percentage}%` }}
                            ></div>
                        </div>
                    </div>
                ) : (
                    <button
                        onClick={handleUploadClick}
                        disabled={stagedFiles.length === 0}
                        className={`
                            w-full py-3 px-4 rounded-lg font-medium text-white shadow-md transition-all
                            ${stagedFiles.length === 0 
                                ? "bg-gray-300 cursor-not-allowed" 
                                : "bg-[#FF5E00] hover:bg-[#E65400] hover:shadow-lg transform active:scale-[0.98]"
                            }
                        `}
                    >
                        Upload & Analyze {stagedFiles.length > 0 ? `(${stagedFiles.length} Files)` : ''}
                    </button>
                )}
            </div>
        </div>
      </div>

      <WarningModal
        isOpen={isWarningOpen}
        onClose={() => setIsWarningOpen(false)}
        title={warningTitle}
        message={warningMessage}
      />
    </div>
  );
}