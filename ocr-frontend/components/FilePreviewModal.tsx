"use client";

import React, { useState, useEffect, useMemo } from 'react';
import { apiClient } from '@/lib/api';
import { Document, Page, pdfjs } from 'react-pdf';
import * as XLSX from 'xlsx';
import mammoth from 'mammoth';
import { AgGridReact } from 'ag-grid-react';
import {
  ColDef,
  ModuleRegistry,
  ClientSideRowModelModule,
  ValidationModule,
  PaginationModule,
  CellStyleModule,
  TextFilterModule,
  NumberFilterModule,
  DateFilterModule,
  CustomFilterModule
} from 'ag-grid-community';
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";

// Register AG Grid modules
ModuleRegistry.registerModules([
  ClientSideRowModelModule,
  ValidationModule,
  PaginationModule,
  CellStyleModule,
  TextFilterModule,
  NumberFilterModule,
  DateFilterModule,
  CustomFilterModule
]);
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Setup PDF worker
if (typeof window !== 'undefined') {
  pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
}

interface FilePreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  fileId: string;
  fileName: string;
  packageId: string;
}

export default function FilePreviewModal({ isOpen, onClose, fileId, fileName, packageId }: FilePreviewModalProps) {
  const [contentUrl, setContentUrl] = useState<string | null>(null);
  const [contentType, setContentType] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Excel Data State
  const [excelData, setExcelData] = useState<any[]>([]);
  const [excelColumns, setExcelColumns] = useState<ColDef[]>([]);

  // Word Data State
  const [wordHtml, setWordHtml] = useState<string | null>(null);

  // PDF State
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState<number>(1);

  useEffect(() => {
    if (isOpen && fileId && packageId) {
      loadFile();
    }
    
    return () => {
        // Cleanup object URL if created
        if (contentUrl && contentUrl.startsWith('blob:')) {
            URL.revokeObjectURL(contentUrl);
        }
    };
  }, [isOpen, fileId, packageId]);

  const loadFile = async () => {
    setIsLoading(true);
    setError(null);
    setContentUrl(null);
    setExcelData([]);
    setWordHtml(null);
    
    try {
      // Use the API client to fetch document content
      // Note: We need to extend apiClient to support this specific call or use raw fetch
      // For now, assuming apiClient.getDocumentContentUrl returns what we need or we fetch directly
      
      const response = await apiClient.getDocumentContentUrl(packageId, fileId);
      
      if (response.signed_url) {
          const type = getContentTypeFromFilename(fileName);
          setContentType(type);
          
          if (type === 'application/pdf' || type.includes('spreadsheet') || type.includes('excel') || type.includes('csv') || type.includes('word') || type.includes('officedocument.wordprocessingml')) {
             // Check for legacy .doc first
             if (fileName.toLowerCase().endsWith('.doc')) {
                 setError("Legacy .doc files cannot be previewed. Please download the file to view it.");
                 setIsLoading(false);
                 setContentUrl(response.signed_url);
                 return;
             }

             // Use proxy to fetch file content as blob to avoid CORS and inconsistent browser behavior
             const proxyUrl = `/api/proxy-pdf?url=${encodeURIComponent(response.signed_url)}`;
             const res = await fetch(proxyUrl);
             
             if (!res.ok) {
                 throw new Error(`Failed to load file via proxy: ${res.statusText}`);
             }
             
             const blob = await res.blob();
             const blobUrl = URL.createObjectURL(blob);
             setContentUrl(blobUrl);

             // Parse based on type
             if (type.includes('spreadsheet') || type.includes('excel') || type.includes('csv')) {
                 await parseExcelFromBlob(blob);
             } else if (type.includes('word') || type.includes('officedocument.wordprocessingml')) {
                 await parseWordFromBlob(blob);
             }
             // For PDF, contentUrl (blobUrl) is enough for <Document> to render
          } else {
             // For images and others, direct link might work if CORS allows or for simple <img> tags
             // But to be safe, let's try proxy for images too if we can?
             // Images usually handle cross-origin fine for display.
             setContentUrl(response.signed_url);
          }
      } else if (response.content && response.encoding === 'base64') {
          // Convert base64 to Blob URL
          const byteCharacters = atob(response.content);
          const byteNumbers = new Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i++) {
              byteNumbers[i] = byteCharacters.charCodeAt(i);
          }
          const byteArray = new Uint8Array(byteNumbers);
          const type = response.content_type || getContentTypeFromFilename(fileName);
          const blob = new Blob([byteArray], { type });
          const url = URL.createObjectURL(blob);
          
          setContentUrl(url);
          setContentType(type);
          
          if (type.includes('spreadsheet') || type.includes('excel') || type.includes('csv') || fileName.match(/\.(xlsx|xls|csv)$/)) {
              await parseExcelFromBlob(blob);
          } else if (type.includes('word') || type.includes('officedocument.wordprocessingml') || fileName.match(/\.(docx|doc)$/)) {
               if (fileName.toLowerCase().endsWith('.doc')) {
                   setError("Legacy .doc files cannot be previewed. Please download the file to view it.");
                   setIsLoading(false);
                   return;
               }
              await parseWordFromBlob(blob);
          }
      } else {
          throw new Error("Invalid response from server");
      }
      
    } catch (err) {
      console.error("Failed to load file:", err);
      setError("Failed to load file preview.");
    } finally {
      setIsLoading(false);
    }
  };

  const getContentTypeFromFilename = (name: string) => {
      const ext = name.split('.').pop()?.toLowerCase();
      if (ext === 'pdf') return 'application/pdf';
      if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext || '')) return `image/${ext}`;
      if (['xlsx', 'xls', 'csv'].includes(ext || '')) return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
      if (ext === 'docx') return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
      if (ext === 'doc') return 'application/msword';
      return 'application/octet-stream';
  };

  const parseWordFromBlob = async (blob: Blob) => {
      try {
          const arrayBuffer = await blob.arrayBuffer();
          // Mammoth works best with .docx
          // For .doc, it might fail or we might need another strategy, but we try mammoth first
          const result = await mammoth.convertToHtml({ arrayBuffer });
          setWordHtml(result.value);
          if (result.messages.length > 0) {
              console.log("Mammoth messages:", result.messages);
          }
      } catch (err: any) {
          console.error("Error parsing Word file:", err);
          
          // Check for specific mammoth error message regarding binary files
          if (err.message && (err.message.includes("valid .docx file") || err.message.includes("find main document part"))) {
             setError("This appears to be a legacy .doc file or an invalid .docx file, which cannot be previewed. Please download it.");
          } else {
             setError("Failed to parse Word document. Please download to view.");
          }
      }
  };

  const parseExcelFromBlob = async (blob: Blob) => {
      try {
          const buffer = await blob.arrayBuffer();
          const workbook = XLSX.read(buffer, { type: 'array' });
          const sheetName = workbook.SheetNames[0];
          const worksheet = workbook.Sheets[sheetName];
          const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 }) as any[][];
          
          if (jsonData.length > 0) {
              // Calculate max columns to avoid issues with title rows or empty starting cells
              const maxCols = jsonData.reduce((max, row) => Math.max(max, row.length), 0);
              
              // Helper to generate Excel-style headers (A, B, ..., Z, AA, AB...)
              const getColumnLabel = (index: number) => {
                  let label = '';
                  let i = index;
                  while (i >= 0) {
                      label = String.fromCharCode(65 + (i % 26)) + label;
                      i = Math.floor(i / 26) - 1;
                  }
                  return label;
              };

              const columns: ColDef[] = [];
              for (let i = 0; i < maxCols; i++) {
                  columns.push({
                      field: `col_${i}`,
                      headerName: getColumnLabel(i),
                      filter: true,
                      sortable: true,
                      resizable: true,
                      minWidth: 100
                  });
              }

              // Map all rows including the first one as data
              const rowData = jsonData.map((row) => {
                  const obj: any = {};
                  for (let i = 0; i < maxCols; i++) {
                      // Use the same key generation strategy
                      obj[`col_${i}`] = row[i];
                  }
                  return obj;
              });
              
              setExcelColumns(columns);
              setExcelData(rowData);
          }
      } catch (err) {
          console.error("Error parsing Excel:", err);
          setError("Failed to parse Excel file.");
      }
  };

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-6xl h-[90vh] flex flex-col overflow-hidden" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200">
          <div className="flex items-center gap-3">
             <div className="bg-neutral-100 p-2 rounded-lg">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-neutral-600">
                    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
             </div>
             <div>
                 <h3 className="font-semibold text-gray-900 truncate max-w-lg" title={fileName}>{fileName}</h3>
                 <p className="text-xs text-gray-500 uppercase">{contentType?.split('/')[1] || 'File'}</p>
             </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-neutral-100 rounded-lg text-neutral-500 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto bg-neutral-100 p-4 flex items-center justify-center relative">
          {isLoading ? (
            <div className="flex flex-col items-center gap-3">
                <div className="w-10 h-10 border-4 border-neutral-200 border-t-neutral-800 rounded-full animate-spin"></div>
                <p className="text-neutral-500 font-medium">Loading preview...</p>
            </div>
          ) : error ? (
            <div className="text-center p-8 bg-white rounded-xl shadow-sm border border-red-100">
                <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-red-500">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="8" x2="12" y2="12"></line>
                        <line x1="12" y1="16" x2="12.01" y2="16"></line>
                    </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">Preview Unavailable</h3>
                <p className="text-gray-500 max-w-sm mb-4">{error}</p>
                {contentUrl && (
                  <a
                      href={contentUrl}
                      download={fileName}
                      className="inline-flex items-center px-4 py-2 bg-neutral-900 text-white rounded-lg hover:bg-neutral-800 transition-colors"
                  >
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
                          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                          <polyline points="7 10 12 15 17 10"></polyline>
                          <line x1="12" x2="12" y1="15" y2="3"></line>
                      </svg>
                      Download File
                  </a>
                )}
            </div>
          ) : contentUrl ? (
            <>
                {/* Image Preview */}
                {contentType?.startsWith('image/') && (
                    <img src={contentUrl} alt={fileName} className="max-w-full max-h-full object-contain shadow-lg rounded-lg bg-white" />
                )}

                {/* PDF Preview */}
                {contentType === 'application/pdf' && (
                    <div className="max-w-4xl w-full bg-white shadow-lg h-full overflow-y-auto rounded-lg">
                        <Document
                            file={contentUrl}
                            onLoadSuccess={onDocumentLoadSuccess}
                            className="flex flex-col items-center p-4 gap-4 bg-neutral-200"
                            loading={
                                <div className="flex items-center justify-center h-64 w-full">
                                    <div className="w-8 h-8 border-4 border-neutral-300 border-t-neutral-800 rounded-full animate-spin"></div>
                                </div>
                            }
                        >
                            {Array.from(new Array(numPages), (el, index) => (
                                <Page 
                                    key={`page_${index + 1}`} 
                                    pageNumber={index + 1} 
                                    width={800}
                                    renderTextLayer={false}
                                    renderAnnotationLayer={false}
                                    className="shadow-md" 
                                />
                            ))}
                        </Document>
                    </div>
                )}

                {/* Excel Preview */}
                {(contentType?.includes('spreadsheet') || contentType?.includes('excel') || contentType?.includes('csv')) && (
                    <div className="w-full h-full bg-white shadow-lg rounded-lg overflow-hidden flex flex-col">
                        <div className="ag-theme-alpine flex-1 w-full">
                            <AgGridReact
                                theme="legacy"
                                rowData={excelData}
                                columnDefs={excelColumns}
                                defaultColDef={{
                                    flex: 1,
                                    minWidth: 100,
                                    resizable: true,
                                    sortable: true,
                                    filter: true,
                                }}
                                pagination={true}
                                paginationPageSize={50}
                            />
                        </div>
                    </div>
                )}

                {/* Word Preview */}
                {(contentType?.includes('word') || contentType?.includes('officedocument.wordprocessingml')) && wordHtml && (
                    <div className="max-w-4xl w-full bg-white shadow-lg h-full overflow-y-auto rounded-lg p-8 prose prose-sm max-w-none">
                        <div dangerouslySetInnerHTML={{ __html: wordHtml }} />
                    </div>
                )}
                
                {/* Unsupported Type */}
                {!contentType?.startsWith('image/') && contentType !== 'application/pdf' && !contentType?.includes('spreadsheet') && !contentType?.includes('excel') && !contentType?.includes('csv') && !wordHtml && (
                    <div className="text-center p-8 bg-white rounded-xl shadow-sm">
                        <p className="text-gray-500 mb-4">Preview not available for this file type ({contentType}).</p>
                        <a 
                            href={contentUrl} 
                            download={fileName}
                            className="inline-flex items-center px-4 py-2 bg-neutral-900 text-white rounded-lg hover:bg-neutral-800 transition-colors"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                <polyline points="7 10 12 15 17 10"></polyline>
                                <line x1="12" x2="12" y1="15" y2="3"></line>
                            </svg>
                            Download File
                        </a>
                    </div>
                )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}