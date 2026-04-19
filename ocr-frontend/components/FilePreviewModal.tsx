"use client";

import React, { useState, useEffect, useRef, useCallback } from 'react';
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

ModuleRegistry.registerModules([
  ClientSideRowModelModule, ValidationModule, PaginationModule,
  CellStyleModule, TextFilterModule, NumberFilterModule, DateFilterModule, CustomFilterModule
]);
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

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

function getFileType(name: string) {
  const ext = name.split('.').pop()?.toLowerCase() || '';
  if (ext === 'pdf') return { label: 'PDF', color: 'bg-rose-500 text-white', contentType: 'application/pdf' };
  if (['xlsx', 'xls'].includes(ext)) return { label: 'Excel', color: 'bg-emerald-600 text-white', contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' };
  if (ext === 'csv') return { label: 'CSV', color: 'bg-teal-600 text-white', contentType: 'text/csv' };
  if (ext === 'docx') return { label: 'DOCX', color: 'bg-blue-600 text-white', contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' };
  if (ext === 'doc') return { label: 'DOC', color: 'bg-blue-700 text-white', contentType: 'application/msword' };
  if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) return { label: ext.toUpperCase(), color: 'bg-violet-600 text-white', contentType: `image/${ext}` };
  return { label: ext.toUpperCase() || 'FILE', color: 'bg-[#475569] text-white', contentType: 'application/octet-stream' };
}

const ZOOM_LEVELS = [0.5, 0.75, 1, 1.25, 1.5, 2];

function DocumentSkeleton() {
  return (
    <div className="flex flex-col items-center gap-5 py-10 px-6 w-full">
      {[1, 2].map((page) => (
        <div key={page} className="w-full max-w-[700px] bg-white rounded-xl shadow-[0_2px_16px_rgba(0,0,0,0.10)] overflow-hidden">
          <div className="h-1 bg-gradient-to-r from-[#F97316]/30 via-[#F97316]/10 to-transparent" />
          <div className="p-10 space-y-4">
            <div className="h-5 w-2/3 rounded-md bg-[#F1F5F9] shimmer" />
            <div className="h-3 w-1/3 rounded-md bg-[#F1F5F9] shimmer" />
            <div className="pt-2 space-y-2.5">
              {[100, 92, 88, 95, 72, 85, 90, 60, 78, 88, 70, 94].map((w, i) => (
                <div key={i} className="h-2.5 rounded-md bg-[#F1F5F9] shimmer" style={{ width: `${w}%`, animationDelay: `${i * 55}ms` }} />
              ))}
            </div>
            <div className="pt-4 grid grid-cols-2 gap-4">
              {[78, 65, 88, 55, 70, 80].map((w, i) => (
                <div key={i} className="h-2.5 rounded-md bg-[#F1F5F9] shimmer" style={{ width: `${w}%`, animationDelay: `${i * 75}ms` }} />
              ))}
            </div>
          </div>
          <div className="flex justify-center pb-4">
            <div className="h-2 w-8 rounded-md bg-[#F1F5F9] shimmer" />
          </div>
        </div>
      ))}
      <div className="flex items-center gap-2 text-[#94A3B8] text-xs font-medium mt-1">
        <svg className="w-3.5 h-3.5 animate-spin text-[#F97316]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Loading document…
      </div>
    </div>
  );
}

export default function FilePreviewModal({ isOpen, onClose, fileId, fileName, packageId }: FilePreviewModalProps) {
  const [contentUrl, setContentUrl] = useState<string | null>(null);
  const [contentType, setContentType] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [excelData, setExcelData] = useState<any[]>([]);
  const [excelColumns, setExcelColumns] = useState<ColDef[]>([]);
  const [wordHtml, setWordHtml] = useState<string | null>(null);
  const [numPages, setNumPages] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [zoomIndex, setZoomIndex] = useState<number>(2); // default = 1 (100%)
  const contentRef = useRef<HTMLDivElement>(null);

  const fileInfo = getFileType(fileName);
  const zoom = ZOOM_LEVELS[zoomIndex];
  const zoomPct = Math.round(zoom * 100);

  useEffect(() => {
    if (isOpen && fileId && packageId) {
      setCurrentPage(1);
      setZoomIndex(2);
      loadFile();
    }
    return () => {
      if (contentUrl && contentUrl.startsWith('blob:')) URL.revokeObjectURL(contentUrl);
    };
  }, [isOpen, fileId, packageId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  const loadFile = async () => {
    setIsLoading(true);
    setError(null);
    setContentUrl(null);
    setExcelData([]);
    setWordHtml(null);
    try {
      const response = await apiClient.getDocumentContentUrl(packageId, fileId);
      if (response.signed_url) {
        const type = fileInfo.contentType;
        setContentType(type);
        if (fileName.toLowerCase().endsWith('.doc')) {
          setError("Legacy .doc files cannot be previewed. Please download to view.");
          setIsLoading(false);
          setContentUrl(response.signed_url);
          return;
        }
        if (type === 'application/pdf' || type.includes('spreadsheet') || type.includes('excel') || type.includes('csv') || type.includes('word')) {
          const proxyUrl = `/api/proxy-pdf?url=${encodeURIComponent(response.signed_url)}`;
          const res = await fetch(proxyUrl);
          if (!res.ok) throw new Error(`Failed to load: ${res.statusText}`);
          const blob = await res.blob();
          const blobUrl = URL.createObjectURL(blob);
          setContentUrl(blobUrl);
          if (type.includes('spreadsheet') || type.includes('excel') || type.includes('csv')) await parseExcelFromBlob(blob);
          else if (type.includes('word')) await parseWordFromBlob(blob);
        } else {
          setContentUrl(response.signed_url);
        }
      } else if (response.content && response.encoding === 'base64') {
        const byteCharacters = atob(response.content);
        const byteArray = new Uint8Array([...byteCharacters].map(c => c.charCodeAt(0)));
        const type = response.content_type || fileInfo.contentType;
        const blob = new Blob([byteArray], { type });
        const url = URL.createObjectURL(blob);
        setContentUrl(url);
        setContentType(type);
        if (type.includes('spreadsheet') || type.includes('excel') || type.includes('csv')) await parseExcelFromBlob(blob);
        else if (type.includes('word')) await parseWordFromBlob(blob);
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

  const parseWordFromBlob = async (blob: Blob) => {
    try {
      const result = await mammoth.convertToHtml({ arrayBuffer: await blob.arrayBuffer() });
      setWordHtml(result.value);
    } catch (err: any) {
      setError(err.message?.includes("valid .docx") ? "Legacy .doc file — please download to view." : "Failed to parse Word document.");
    }
  };

  const parseExcelFromBlob = async (blob: Blob) => {
    try {
      const workbook = XLSX.read(await blob.arrayBuffer(), { type: 'array' });
      const worksheet = workbook.Sheets[workbook.SheetNames[0]];
      const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 }) as any[][];
      if (jsonData.length > 0) {
        const maxCols = jsonData.reduce((max, row) => Math.max(max, row.length), 0);
        const getLabel = (i: number) => { let l = '', idx = i; while (idx >= 0) { l = String.fromCharCode(65 + (idx % 26)) + l; idx = Math.floor(idx / 26) - 1; } return l; };
        const columns: ColDef[] = Array.from({ length: maxCols }, (_, i) => ({ field: `col_${i}`, headerName: getLabel(i), filter: true, sortable: true, resizable: true, minWidth: 100 }));
        const rowData = jsonData.map(row => Object.fromEntries(Array.from({ length: maxCols }, (_, i) => [`col_${i}`, row[i]])));
        setExcelColumns(columns);
        setExcelData(rowData);
      }
    } catch { setError("Failed to parse spreadsheet."); }
  };

  const handleDownload = async () => {
    if (!contentUrl) return;
    const a = document.createElement('a');
    a.href = contentUrl;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const goToPage = useCallback((page: number) => {
    const clamped = Math.min(Math.max(page, 1), numPages);
    setCurrentPage(clamped);
    const pages = contentRef.current?.querySelectorAll('.react-pdf__Page');
    pages?.[clamped - 1]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [numPages]);

  const isPdf = contentType === 'application/pdf';
  const isExcel = contentType?.includes('spreadsheet') || contentType?.includes('excel') || contentType?.includes('csv');
  const isWord = (contentType?.includes('word') || contentType?.includes('officedocument.wordprocessingml')) && !!wordHtml;
  const isImage = contentType?.startsWith('image/');

  const pdfWidth = typeof window !== 'undefined'
    ? Math.min(window.innerWidth * 0.7, 820) * zoom
    : 760 * zoom;

  if (!isOpen) return null;

  return (
    <>
      <style>{`
        @keyframes shimmer {
          0% { background-position: -700px 0; }
          100% { background-position: 700px 0; }
        }
        .shimmer {
          background: linear-gradient(90deg, #F1F5F9 25%, #E8ECF0 50%, #F1F5F9 75%);
          background-size: 700px 100%;
          animation: shimmer 1.8s infinite linear;
        }
      `}</style>

      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/60 backdrop-blur-[3px]"
        onClick={onClose}
      >
        <div
          className="flex flex-col w-full max-w-5xl h-[92vh] bg-white rounded-2xl shadow-[0_32px_80px_rgba(0,0,0,0.30)] overflow-hidden border border-[#E2E8F0]"
          onClick={e => e.stopPropagation()}
        >

          {/* ── Header ─────────────────────────────────────── */}
          <div className="shrink-0 flex items-center gap-3 px-4 py-3 bg-white border-b border-[#E2E8F0]">

            {/* Close */}
            <button
              onClick={onClose}
              className="shrink-0 w-7 h-7 flex items-center justify-center rounded-lg text-[#94A3B8] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-colors"
              aria-label="Close"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>

            <div className="w-px h-4 bg-[#E2E8F0] shrink-0" />

            {/* File type badge */}
            <span className={`shrink-0 text-[9px] font-bold px-2 py-0.5 rounded tracking-widest uppercase ${fileInfo.color}`}>
              {fileInfo.label}
            </span>

            {/* Filename */}
            <p className="flex-1 text-[13px] font-medium text-[#0F172A] truncate min-w-0" title={fileName}>
              {fileName}
            </p>

            {/* ── PDF controls ── */}
            {isPdf && numPages > 0 && !isLoading && (
              <>
                {/* Page navigation */}
                <div className="shrink-0 flex items-center gap-1 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg px-1 py-0.5">
                  <button
                    onClick={() => goToPage(currentPage - 1)}
                    disabled={currentPage <= 1}
                    className="w-6 h-6 flex items-center justify-center rounded-md text-[#64748B] hover:text-[#0F172A] hover:bg-[#E2E8F0] disabled:opacity-30 disabled:pointer-events-none transition-colors"
                  >
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
                  </button>
                  <span className="text-[11px] font-medium text-[#0F172A] tabular-nums px-1.5 min-w-[52px] text-center">
                    {currentPage} <span className="text-[#94A3B8] font-normal">/ {numPages}</span>
                  </span>
                  <button
                    onClick={() => goToPage(currentPage + 1)}
                    disabled={currentPage >= numPages}
                    className="w-6 h-6 flex items-center justify-center rounded-md text-[#64748B] hover:text-[#0F172A] hover:bg-[#E2E8F0] disabled:opacity-30 disabled:pointer-events-none transition-colors"
                  >
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
                  </button>
                </div>

                <div className="w-px h-4 bg-[#E2E8F0] shrink-0" />

                {/* Zoom */}
                <div className="shrink-0 flex items-center gap-1 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg px-1 py-0.5">
                  <button
                    onClick={() => setZoomIndex(i => Math.max(0, i - 1))}
                    disabled={zoomIndex === 0}
                    className="w-6 h-6 flex items-center justify-center rounded-md text-[#64748B] hover:text-[#0F172A] hover:bg-[#E2E8F0] disabled:opacity-30 disabled:pointer-events-none transition-colors"
                    aria-label="Zoom out"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" /><path strokeLinecap="round" d="M8 11h6" /></svg>
                  </button>
                  <button
                    onClick={() => setZoomIndex(2)}
                    className="text-[11px] font-medium text-[#475569] hover:text-[#0F172A] tabular-nums px-1 min-w-[38px] text-center transition-colors"
                    title="Reset to 100%"
                  >
                    {zoomPct}%
                  </button>
                  <button
                    onClick={() => setZoomIndex(i => Math.min(ZOOM_LEVELS.length - 1, i + 1))}
                    disabled={zoomIndex === ZOOM_LEVELS.length - 1}
                    className="w-6 h-6 flex items-center justify-center rounded-md text-[#64748B] hover:text-[#0F172A] hover:bg-[#E2E8F0] disabled:opacity-30 disabled:pointer-events-none transition-colors"
                    aria-label="Zoom in"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" /><path strokeLinecap="round" d="M11 8v6M8 11h6" /></svg>
                  </button>
                </div>

                <div className="w-px h-4 bg-[#E2E8F0] shrink-0" />
              </>
            )}

            {/* Download */}
            {contentUrl && (
              <button
                onClick={handleDownload}
                className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#F1F5F9] hover:bg-[#E2E8F0] text-[#475569] hover:text-[#0F172A] text-[11px] font-medium transition-colors border border-[#E2E8F0]"
                title="Download"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" x2="12" y1="15" y2="3" />
                </svg>
                Download
              </button>
            )}
          </div>

          {/* ── Content area ───────────────────────────────── */}
          <div
            ref={contentRef}
            className="flex-1 overflow-y-auto overflow-x-auto no-scrollbar relative"
            style={{ background: '#E8ECEF' }}
            onScroll={() => {
              if (isPdf && contentRef.current && numPages > 0) {
                const pages = contentRef.current.querySelectorAll('.react-pdf__Page');
                let closestPage = 1;
                let closestDist = Infinity;
                pages.forEach((el, i) => {
                  const rect = el.getBoundingClientRect();
                  const dist = Math.abs(rect.top);
                  if (dist < closestDist) { closestDist = dist; closestPage = i + 1; }
                });
                setCurrentPage(closestPage);
              }
            }}
          >
            {isLoading ? (
              <DocumentSkeleton />
            ) : error ? (
              <div className="flex flex-col items-center justify-center h-full py-16 text-center px-6">
                <div className="w-14 h-14 bg-white border border-[rgba(239,68,68,0.2)] rounded-2xl flex items-center justify-center mb-4 shadow-sm">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#EF4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                </div>
                <h3 className="text-sm font-semibold text-[#0F172A] mb-1">Preview Unavailable</h3>
                <p className="text-xs text-[#64748B] max-w-xs leading-relaxed mb-5">{error}</p>
                {contentUrl && (
                  <button
                    onClick={handleDownload}
                    className="flex items-center gap-2 px-4 py-2 bg-[#0F172A] hover:bg-[#1E293B] text-white rounded-xl text-xs font-semibold shadow-sm transition-all"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" x2="12" y1="15" y2="3" />
                    </svg>
                    Download File
                  </button>
                )}
              </div>
            ) : contentUrl ? (
              <>
                {/* Image */}
                {isImage && (
                  <div className="flex items-center justify-center h-full p-8">
                    <img src={contentUrl} alt={fileName} className="max-w-full max-h-full object-contain rounded-xl shadow-[0_8px_32px_rgba(0,0,0,0.2)]" />
                  </div>
                )}

                {/* PDF */}
                {isPdf && (
                  <div className="flex justify-center">
                    <Document
                      file={contentUrl}
                      onLoadSuccess={({ numPages: n }) => setNumPages(n)}
                      className="flex flex-col items-center gap-4 py-6 px-4"
                      loading={<DocumentSkeleton />}
                    >
                      {Array.from({ length: numPages }, (_, i) => (
                        <Page
                          key={`page_${i + 1}`}
                          pageNumber={i + 1}
                          width={pdfWidth}
                          renderTextLayer={false}
                          renderAnnotationLayer={false}
                          className="rounded-lg shadow-[0_2px_16px_rgba(0,0,0,0.15)]"
                        />
                      ))}
                    </Document>
                  </div>
                )}

                {/* Excel / CSV */}
                {isExcel && (
                  <div className="w-full h-full p-4">
                    <div className="ag-theme-alpine w-full h-full rounded-xl overflow-hidden border border-[#E2E8F0] shadow-sm">
                      <AgGridReact
                        theme="legacy"
                        rowData={excelData}
                        columnDefs={excelColumns}
                        defaultColDef={{ flex: 1, minWidth: 100, resizable: true, sortable: true, filter: true }}
                        pagination={true}
                        paginationPageSize={50}
                      />
                    </div>
                  </div>
                )}

                {/* Word */}
                {isWord && (
                  <div className="flex justify-center p-8">
                    <div className="w-full max-w-3xl bg-white rounded-xl shadow-[0_2px_16px_rgba(0,0,0,0.10)] p-10 prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: wordHtml! }} />
                  </div>
                )}

                {/* Unsupported */}
                {!isImage && !isPdf && !isExcel && !isWord && (
                  <div className="flex flex-col items-center justify-center h-full py-16 text-center">
                    <div className="w-14 h-14 bg-white border border-[#E2E8F0] rounded-2xl flex items-center justify-center mb-4 shadow-sm">
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" /><polyline points="14 2 14 8 20 8" />
                      </svg>
                    </div>
                    <p className="text-sm text-[#64748B] mb-4">Preview not available for <span className="text-[#0F172A] font-semibold">{fileInfo.label}</span> files</p>
                    <button
                      onClick={handleDownload}
                      className="flex items-center gap-2 px-4 py-2 bg-[#0F172A] hover:bg-[#1E293B] text-white rounded-xl text-xs font-semibold shadow-sm transition-all"
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" x2="12" y1="15" y2="3" />
                      </svg>
                      Download File
                    </button>
                  </div>
                )}
              </>
            ) : null}
          </div>

        </div>
      </div>
    </>
  );
}
