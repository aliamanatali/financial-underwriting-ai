"use client";

import { useState, useEffect, useRef } from "react";
import { apiClient } from "@/lib/api";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Set worker source
if (typeof window !== 'undefined') {
  pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
}

// Global cache for document blobs to prevent re-fetching
const blobCache = new Map<string, Blob>();
const activeFetches = new Map<string, Promise<Blob>>();

interface Bbox {
  0: number; // ymin
  1: number; // xmin
  2: number; // ymax
  3: number; // xmax
}

interface SourceDocumentViewerProps {
  documentId: string;
  filename: string;
  packageId?: string;
  pageNumber?: number;
  bbox?: number[]; // [ymin, xmin, ymax, xmax] normalized to 0-1000
  onClose: () => void;
}

export default function SourceDocumentViewer({
  documentId,
  filename,
  packageId,
  pageNumber = 1,
  bbox,
  onClose,
}: SourceDocumentViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [scale, setScale] = useState(1.2);
  const [pageWidth, setPageWidth] = useState<number>(0);
  const [pageHeight, setPageHeight] = useState<number>(0);

  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);

  // Drag and move state
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isPageLoaded, setIsPageLoaded] = useState(false);
  const [startX, setStartX] = useState(0);
  const [startY, setStartY] = useState(0);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [scrollTop, setScrollTop] = useState(0);

  // Determine file type
  const extension = filename.split('.').pop()?.toLowerCase() || '';
  const isPdf = extension === 'pdf';
  const isImage = ['jpg', 'jpeg', 'png', 'webp'].includes(extension);

  // Fetch the PDF as a blob first to handle CORS and errors better
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [loadingError, setLoadingError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;
    let objectUrlToRevoke: string | null = null;

    const loadContent = async () => {
      setLoadingError(null);
      setDownloadUrl(null);
      
      // Fast path: Check cache for PDF
      if (isPdf && blobCache.has(documentId)) {
        const blob = blobCache.get(documentId)!;
        const url = URL.createObjectURL(blob);
        objectUrlToRevoke = url;
        if (isActive) {
          setPdfBlobUrl(url);
        }
      } else {
        if (isActive) setPdfBlobUrl(null);
      }

      try {
        // 1. Get Download URL
        let url = "";
        if (packageId) {
          const baseUrl = process.env.NEXT_PUBLIC_FINANCIAL_API_URL;
          url = `${baseUrl}/api/v1/multi-document/packages/${packageId}/documents/${documentId}/download`;
        } else {
          // Fallback or direct URL construction for non-packaged documents
          const baseUrl = process.env.NEXT_PUBLIC_OCR_API_URL;
          url = `${baseUrl}/api/documents/${documentId}/content`;
        }

        if (isActive) {
          setDownloadUrl(url);
        }

        // 2. If PDF and not in cache, fetch and cache
        if (isPdf && !blobCache.has(documentId)) {
          let fetchPromise = activeFetches.get(documentId);
          
          if (!fetchPromise) {
            fetchPromise = fetch(url).then(async (res) => {
              if (!res.ok) {
                throw new Error(`Failed to fetch PDF: ${res.status} ${res.statusText}`);
              }
              return res.blob();
            });
            
            activeFetches.set(documentId, fetchPromise);
            
            // Handle caching upon resolution
            fetchPromise
              .then((blob) => {
                blobCache.set(documentId, blob);
                activeFetches.delete(documentId);
              })
              .catch(() => {
                activeFetches.delete(documentId);
              });
          }

          const blob = await fetchPromise;
          
          if (isActive) {
            const objectUrl = URL.createObjectURL(blob);
            objectUrlToRevoke = objectUrl;
            setPdfBlobUrl(objectUrl);
            setLoadingError(null);
          }
        }
      } catch (err: any) {
        console.error("Error loading document:", err);
        if (isActive && !blobCache.has(documentId)) {
          setLoadingError(err.message || "Failed to load document");
        }
      }
    };

    loadContent();

    return () => {
      isActive = false;
      if (objectUrlToRevoke) {
        URL.revokeObjectURL(objectUrlToRevoke);
      }
    };
  }, [documentId, packageId, isPdf]);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
  }

  function onDocumentLoadError(error: Error) {
    // Log meaningful error but avoid spamming console for expected 404s in dev
    if (error.message && error.message.includes('404')) {
       console.warn(`Document not found: ${filename} (${documentId})`);
    } else {
       console.error(`Error loading PDF document from ${downloadUrl}:`, error);
    }
  }

  // Reset page loaded state when scale or page changes
  useEffect(() => {
    setIsPageLoaded(false);
  }, [scale, pageNumber, documentId]);

  function onPageLoadSuccess(page: any) {
    setPageWidth(page.width);
    setPageHeight(page.height);
  }

  function onPageRenderSuccess() {
    setIsPageLoaded(true);
  }

  // Scroll to highlight automatically when selected or loaded
  useEffect(() => {
    if (isPageLoaded && highlightRef.current && scrollContainerRef.current) {
      // Use a slightly longer timeout to ensure browser layout is complete
      // especially for image-based PDFs which might take longer to compute layout
      setTimeout(() => {
        if (highlightRef.current) {
          highlightRef.current.scrollIntoView({
            behavior: 'smooth',
            block: 'center',
            inline: 'center'
          });
        }
      }, 250);
    }
  }, [bbox, isPageLoaded, scale, pageNumber]);

  // Drag to pan handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    // Only drag with left mouse button
    if (e.button !== 0 || !scrollContainerRef.current) return;
    
    // Don't drag if clicking on a button or link
    if ((e.target as HTMLElement).closest('button, a')) return;

    setIsDragging(true);
    setStartX(e.pageX - scrollContainerRef.current.offsetLeft);
    setStartY(e.pageY - scrollContainerRef.current.offsetTop);
    setScrollLeft(scrollContainerRef.current.scrollLeft);
    setScrollTop(scrollContainerRef.current.scrollTop);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging || !scrollContainerRef.current) return;
    e.preventDefault(); // Prevent text selection/native drag during active panning
    const x = e.pageX - scrollContainerRef.current.offsetLeft;
    const y = e.pageY - scrollContainerRef.current.offsetTop;
    const walkX = (x - startX) * 1.5;
    const walkY = (y - startY) * 1.5;
    scrollContainerRef.current.scrollLeft = scrollLeft - walkX;
    scrollContainerRef.current.scrollTop = scrollTop - walkY;
  };

  const handleMouseUpOrLeave = () => {
    setIsDragging(false);
  };

  // Calculate highlight box style
  const getHighlightStyle = () => {
    if (!bbox || bbox.length !== 4) return null;

    // Gemini returns bbox as [ymin, xmin, ymax, xmax] normalized to 0-1000
    // We need to convert this to PDF coordinates
    // PDF coordinates usually start from bottom-left, but react-pdf might handle it differently.
    // Let's assume standard top-left origin for CSS positioning on the rendered page.
    
    // De-normalize coordinates (0-1000 -> 0-1)
    const [ymin, xmin, ymax, xmax] = bbox.map(coord => coord / 1000);
    
    // Width and Height of the box
    const widthPct = (xmax - xmin) * 100;
    const heightPct = (ymax - ymin) * 100;
    
    // Top and Left position
    const topPct = ymin * 100;
    const leftPct = xmin * 100;

    // Add a small padding to ensure the text is fully covered (robustness improvement)
    const padding = 0.5; // 0.5% padding

    return {
      top: `${Math.max(0, topPct - padding)}%`,
      left: `${Math.max(0, leftPct - padding)}%`,
      width: `${Math.min(100, widthPct + (padding * 2))}%`,
      height: `${Math.min(100, heightPct + (padding * 2))}%`,
    };
  };

  const highlightStyle = getHighlightStyle();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-6xl h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">{filename}</h3>
            <p className="text-sm text-gray-500">
              Page {pageNumber} of {numPages || "--"}
            </p>
            <p className="text-xs text-amber-600 mt-1 italic">
              Please note: The highlighted source may be slightly misaligned but will be close to the actual written source.
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 bg-white rounded-lg border border-gray-300 p-1">
              <button
                onClick={() => setScale((s) => Math.max(0.5, s - 0.1))}
                className="p-1.5 hover:bg-gray-100 rounded text-gray-600"
                title="Zoom Out"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" x2="16.65" y1="21" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
              </button>
              <span className="text-xs font-medium w-12 text-center">
                {Math.round(scale * 100)}%
              </span>
              <button
                onClick={() => setScale((s) => Math.min(3, s + 0.1))}
                className="p-1.5 hover:bg-gray-100 rounded text-gray-600"
                title="Zoom In"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" x2="16.65" y1="21" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
              </button>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-200 rounded-full text-gray-500 transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
            </button>
          </div>
        </div>

        {/* Document Content */}
        <div
          ref={scrollContainerRef}
          className={`flex-1 overflow-auto bg-gray-100 p-4 ${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUpOrLeave}
          onMouseLeave={handleMouseUpOrLeave}
          onDragStart={(e) => e.preventDefault()} // Prevent native image dragging
        >
          <div className="w-max h-max min-w-full min-h-full flex items-center justify-center">
            <div className="relative shadow-lg bg-white min-h-[400px] min-w-[600px] flex flex-col items-center justify-center">
              {isPdf ? (
              <>
                {loadingError ? (
                   <div className="flex flex-col items-center justify-center h-96 w-[600px] bg-white p-6 text-center">
                    <p className="text-red-500 font-medium mb-2">Failed to load document.</p>
                    <p className="text-sm text-gray-500 mb-4">{loadingError}</p>
                    {downloadUrl && <a
                     href={downloadUrl}
                     download={filename}
                     className="text-indigo-600 hover:text-indigo-800 text-sm font-medium underline"
                    >
                     Try Direct Download
                    </a>}
                  </div>
                ) : !pdfBlobUrl ? (
                   <div className="flex items-center justify-center h-96 w-[600px] bg-white">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
                  </div>
                ) : (
                  <Document
                    file={pdfBlobUrl}
                    onLoadSuccess={onDocumentLoadSuccess}
                    onLoadError={onDocumentLoadError}
                    loading={
                      <div className="flex items-center justify-center h-96 w-[600px] bg-white">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
                      </div>
                    }
                    error={
                      <div className="flex flex-col items-center justify-center h-96 w-[600px] bg-white p-6 text-center">
                        <p className="text-red-500 font-medium mb-2">Failed to load document.</p>
                        <p className="text-sm text-gray-500 mb-4">The file might be missing or inaccessible.</p>
                        {downloadUrl && <a
                         href={downloadUrl}
                         download={filename}
                         className="text-indigo-600 hover:text-indigo-800 text-sm font-medium underline"
                       >
                         Try Direct Download
                       </a>}
                      </div>
                    }
                  >
                    <Page
                      pageNumber={pageNumber}
                      scale={scale}
                      onLoadSuccess={onPageLoadSuccess}
                      onRenderSuccess={onPageRenderSuccess}
                      className="bg-white shadow-md relative"
                      renderTextLayer={true}
                      renderAnnotationLayer={true}
                    >
                      {/* Highlight Overlay */}
                      {highlightStyle && (
                        <div
                          ref={highlightRef}
                          className="absolute border-2 border-yellow-500 bg-yellow-400/40 transition-all duration-300 mix-blend-multiply z-20 pointer-events-none"
                          style={highlightStyle}
                        >
                          <div className="absolute -top-7 left-0 bg-yellow-500 text-white text-[11px] px-2 py-0.5 rounded-sm shadow-sm whitespace-nowrap font-bold z-30">
                            Source Value
                          </div>
                        </div>
                      )}
                    </Page>
                  </Document>
                )}
              </>
            ) : isImage ? (
              <div className="relative" style={{ transform: `scale(${scale})`, transformOrigin: 'top center' }}>
                {downloadUrl && <img
                  src={downloadUrl}
                  alt={filename}
                  className="max-w-full h-auto"
                />}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center p-12 text-center">
                <div className="bg-gray-50 p-6 rounded-xl border border-gray-200 mb-6">
                  <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" className="text-gray-400 mx-auto mb-4"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
                  <p className="text-lg font-medium text-gray-900 mb-1">Preview not available</p>
                  <p className="text-sm text-gray-500">This file type ({extension}) cannot be previewed directly.</p>
                </div>
                {downloadUrl && <a
                  href={downloadUrl}
                  download={filename}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium shadow-sm"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                  Download File
                </a>}
              </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}