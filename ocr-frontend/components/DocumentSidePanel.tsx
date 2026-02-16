"use client";

import React, { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';
import { Document, Page, pdfjs } from 'react-pdf';
import { DocumentFile } from './FileOrganization';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Setup PDF worker
if (typeof window !== 'undefined') {
  pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
}

interface DocumentSidePanelProps {
  file: DocumentFile | null;
  packageId: string;
  onClose: () => void;
  onDelete: (id: string, name: string) => void;
  onViewFull: (id: string, name: string) => void;
}

export default function DocumentSidePanel({ file, packageId, onClose, onDelete, onViewFull }: DocumentSidePanelProps) {
  const [contentUrl, setContentUrl] = useState<string | null>(null);
  const [contentType, setContentType] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [numPages, setNumPages] = useState<number | null>(null);

  useEffect(() => {
    if (file && packageId) {
      loadFile();
    } else {
      setContentUrl(null);
      setNumPages(null);
    }
    
    return () => {
        if (contentUrl && contentUrl.startsWith('blob:')) {
            URL.revokeObjectURL(contentUrl);
        }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file, packageId]);

  const loadFile = async () => {
    if (!file) return;
    setIsLoading(true);
    setError(null);
    setContentUrl(null);
    
    try {
      const response = await apiClient.getDocumentContentUrl(packageId, file.id);
      
      if (response.signed_url) {
          const type = getContentTypeFromFilename(file.name);
          setContentType(type);
          
          if (type === 'application/pdf') {
             const proxyUrl = `/api/proxy-pdf?url=${encodeURIComponent(response.signed_url)}`;
             const res = await fetch(proxyUrl);
             if (!res.ok) throw new Error('Failed to load PDF');
             const blob = await res.blob();
             const blobUrl = URL.createObjectURL(blob);
             setContentUrl(blobUrl);
          } else if (type.startsWith('image/')) {
             setContentUrl(response.signed_url);
          } else {
             // For other types, we might not be able to preview easily in side panel
             setContentUrl(null);
          }
      } else if (response.content && response.encoding === 'base64') {
          const byteCharacters = atob(response.content);
          const byteNumbers = new Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i++) {
              byteNumbers[i] = byteCharacters.charCodeAt(i);
          }
          const byteArray = new Uint8Array(byteNumbers);
          const type = response.content_type || getContentTypeFromFilename(file.name);
          const blob = new Blob([byteArray], { type });
          const url = URL.createObjectURL(blob);
          
          setContentUrl(url);
          setContentType(type);
      }
    } catch (err) {
      console.error("Failed to load file preview:", err);
      setError("Preview unavailable");
    } finally {
      setIsLoading(false);
    }
  };

  const getContentTypeFromFilename = (name: string) => {
      const ext = name.split('.').pop()?.toLowerCase();
      if (ext === 'pdf') return 'application/pdf';
      if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext || '')) return `image/${ext}`;
      return 'application/octet-stream';
  };

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const handleDownload = async () => {
    if (!file) return;
    try {
        const response = await apiClient.getDocumentContentUrl(packageId, file.id);
        const url = response.signed_url || (response.content ? `data:${response.content_type};base64,${response.content}` : null);
        
        if (url) {
            const a = document.createElement('a');
            a.href = url;
            a.download = file.name;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
    } catch (error) {
        console.error("Download failed", error);
    }
  };

  if (!file) return null;

  return (
    <div className="w-[350px] border-l border-neutral-200 bg-white flex flex-col h-full shrink-0 animate-in slide-in-from-right duration-300">
      <div className="p-6 h-full overflow-y-auto custom-scrollbar">
        <div className="flex items-center justify-between mb-6">
            <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Document Preview</h3>
            <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        </div>

        {/* Preview Area */}
        <div className="border border-neutral-200 rounded-lg bg-neutral-50 mb-6 overflow-hidden flex items-center justify-center min-h-[300px] max-h-[450px]">
            {isLoading ? (
                <div className="flex flex-col items-center gap-2">
                    <div className="w-6 h-6 border-2 border-neutral-300 border-t-[#FF5E00] rounded-full animate-spin"></div>
                    <span className="text-xs text-neutral-500">Loading...</span>
                </div>
            ) : error ? (
                <div className="text-center p-4">
                    <p className="text-xs text-neutral-400 mb-2">Preview not available</p>
                </div>
            ) : contentType === 'application/pdf' && contentUrl ? (
                <div
                    className="w-full h-full overflow-auto custom-scrollbar flex justify-center bg-neutral-100 cursor-pointer hover:bg-neutral-200 transition-colors"
                    onClick={() => onViewFull(file.id, file.name)}
                    title="Click to view full details"
                >
                    <Document
                        file={contentUrl}
                        onLoadSuccess={onDocumentLoadSuccess}
                        loading={
                            <div className="flex items-center justify-center h-40">
                                <div className="w-6 h-6 border-2 border-neutral-300 border-t-[#FF5E00] rounded-full animate-spin"></div>
                            </div>
                        }
                        className="flex flex-col items-center"
                    >
                        <Page
                            pageNumber={1}
                            width={250}
                            renderTextLayer={false}
                            renderAnnotationLayer={false}
                            className="shadow-sm my-4"
                        />
                    </Document>
                </div>
            ) : contentType?.startsWith('image/') && contentUrl ? (
                <img
                    src={contentUrl}
                    alt="Preview"
                    className="max-w-full max-h-full object-contain cursor-pointer hover:opacity-90 transition-opacity"
                    onClick={() => onViewFull(file.id, file.name)}
                    title="Click to view full details"
                />
            ) : (
                <div className="text-center p-4">
                    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" className="text-neutral-300 mx-auto mb-2">
                        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
                    </svg>
                    <p className="text-xs text-neutral-400">No preview available</p>
                </div>
            )}
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-3 mb-8">
            <button 
                onClick={handleDownload}
                className="w-full flex items-center justify-center gap-2 bg-[#FF5E00] hover:bg-[#E05200] text-white py-2.5 rounded-lg text-sm font-medium transition-colors"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7 10 12 15 17 10"></polyline>
                    <line x1="12" x2="12" y1="15" y2="3"></line>
                </svg>
                Download Document
            </button>
            <button 
                onClick={() => onDelete(file.id, file.name)}
                className="w-full flex items-center justify-center gap-2 bg-white border border-red-200 text-red-600 hover:bg-red-50 py-2.5 rounded-lg text-sm font-medium transition-colors"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
                Delete Document
            </button>
        </div>

        {/* Metadata */}
        <div className="mb-8">
            <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-4">Metadata</h3>
            <div className="space-y-3">
                <div className="flex justify-between items-start text-sm">
                    <span className="text-neutral-500">Filename</span>
                    <span className="text-neutral-900 font-medium text-right max-w-[200px] break-words">{file.name}</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                    <span className="text-neutral-500">Size</span>
                    <span className="text-neutral-900 font-medium">{formatFileSize(file.size)}</span>
                </div>
                {numPages && (
                    <div className="flex justify-between items-center text-sm">
                        <span className="text-neutral-500">Pages</span>
                        <span className="text-neutral-900 font-medium">{numPages}</span>
                    </div>
                )}
            </div>
        </div>

        {/* View Full Details */}
        <button 
            onClick={() => onViewFull(file.id, file.name)}
            className="w-full flex items-center justify-center gap-2 bg-white border border-neutral-300 text-neutral-700 hover:bg-neutral-50 py-2.5 rounded-lg text-sm font-medium transition-colors"
        >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                <polyline points="15 3 21 3 21 9"></polyline>
                <line x1="10" x2="21" y1="14" y2="3"></line>
            </svg>
            Preview File
        </button>
      </div>
    </div>
  );
}