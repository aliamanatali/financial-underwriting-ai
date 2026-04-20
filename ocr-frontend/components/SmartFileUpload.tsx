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

function getFileTypeColor(filename: string): { bg: string; icon: string; ext: string } {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  if (["pdf"].includes(ext)) return { bg: "bg-[rgba(239,68,68,0.12)]", icon: "text-[#EF4444]", ext: "PDF" };
  if (["xlsx", "xls", "csv"].includes(ext)) return { bg: "bg-[rgba(34,197,94,0.12)]", icon: "text-[#22C55E]", ext: ext.toUpperCase() };
  if (["jpg", "jpeg", "png", "gif", "webp"].includes(ext)) return { bg: "bg-[rgba(59,130,246,0.12)]", icon: "text-[#60A5FA]", ext: ext.toUpperCase() };
  if (["doc", "docx"].includes(ext)) return { bg: "bg-[rgba(99,102,241,0.12)]", icon: "text-[#818CF8]", ext: "DOC" };
  return { bg: "bg-[#F1F5F9]", icon: "text-[#475569]", ext: ext.toUpperCase() || "FILE" };
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

  const [isWarningOpen, setIsWarningOpen] = useState(false);
  const [warningTitle, setWarningTitle] = useState("");
  const [warningMessage, setWarningMessage] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  const showWarning = (title: string, message: string) => {
    setWarningTitle(title); setWarningMessage(message); setIsWarningOpen(true);
  };

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation(); setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation(); setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation(); setIsDragging(false);
    processAndAddFiles(Array.from(e.dataTransfer.files));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) processAndAddFiles(Array.from(e.target.files));
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const processAndAddFiles = async (files: File[]) => {
    setIsExtracting(true);
    const processedFiles: File[] = [];
    try {
      for (const file of files) {
        if (file.name.toLowerCase().endsWith(".zip")) {
          try {
            const zip = await JSZip.loadAsync(file);
            const extractions: Promise<void>[] = [];
            zip.forEach((relativePath, zipEntry) => {
              if (zipEntry.dir) return;
              if (zipEntry.name.includes("__MACOSX") || zipEntry.name.split("/").pop()?.startsWith(".")) return;
              extractions.push(
                zipEntry.async("blob").then((blob) => {
                  processedFiles.push(new File([blob], zipEntry.name, { type: blob.type || "application/octet-stream" }));
                })
              );
            });
            await Promise.all(extractions);
          } catch {
            processedFiles.push(file);
            showWarning("Zip Extraction Failed", `Could not extract ${file.name}. It will be uploaded as-is.`);
          }
        } else {
          processedFiles.push(file);
        }
      }
    } finally {
      setIsExtracting(false);
    }
    addFiles(processedFiles);
  };

  const addFiles = (files: File[]) => {
    setStagedFiles((prev) => {
      const newFiles: StagedFile[] = [];
      files.forEach((file) => {
        if (file.size === 0) return;
        if (prev.some((f) => f.file.name === file.name && f.file.size === file.size)) return;
        const isImage = file.type.startsWith("image/") || /\.(jpg|jpeg|png|gif|webp)$/i.test(file.name);
        newFiles.push({
          id: Math.random().toString(36).substring(7),
          file,
          previewUrl: isImage ? URL.createObjectURL(file) : undefined,
        });
      });
      return [...prev, ...newFiles];
    });
  };

  const removeFile = (id: string) => {
    setStagedFiles((prev) => {
      const f = prev.find((f) => f.id === id);
      if (f?.previewUrl) URL.revokeObjectURL(f.previewUrl);
      return prev.filter((f) => f.id !== id);
    });
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  const handleUploadClick = async () => {
    if (stagedFiles.length === 0) return;
    setIsUploading(true);
    setUploadProgress({ loaded: 0, total: 0, percentage: 0 });
    setProcessingMessage("Preparing files…");
    try {
      let uploadFile: File;
      if (stagedFiles.length === 1 && stagedFiles[0].file.name.endsWith(".zip")) {
        uploadFile = stagedFiles[0].file;
      } else {
        setProcessingMessage("Compressing files…");
        const zip = new JSZip();
        stagedFiles.forEach((sf) => zip.file(sf.file.name, sf.file));
        const content = await zip.generateAsync({ type: "blob" });
        const ts = new Date().toISOString().replace(/[:.]/g, "-");
        const name = (stagedFiles[0].file.name.split(".")[0] + "_Package") || "Deal_Package";
        uploadFile = new File([content], `${name}_${ts}.zip`, { type: "application/zip" });
      }
      setProcessingMessage("Uploading…");
      const dealPackage = await apiClient.uploadZipChunked(
        uploadFile,
        (progress) => {
          setUploadProgress(progress);
          if (progress.percentage === 100) setProcessingMessage("Finalizing & starting analysis…");
        },
        (processing) => {
          setProcessingMessage(processing.message);
          setUploadProgress((prev) => ({ ...prev, percentage: processing.percentage }));
        },
        true
      );
      onUploadSuccess?.(dealPackage.package_id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      showWarning("Upload Failed", msg);
      onUploadError?.(msg);
    } finally {
      setIsUploading(false);
    }
  };

  const canUpload = stagedFiles.length > 0 && !isUploading && !isExtracting;

  return (
    <div className="w-full">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* ── Drop Zone ─────────────────────────────────── */}
        <div
          className={`relative border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center min-h-[360px] transition-all duration-200 ${
            isDragging
              ? "border-[#F97316] bg-[rgba(249,115,22,0.06)] shadow-[0_0_0_4px_rgba(249,115,22,0.12)] cursor-copy"
              : "border-[#E2E8F0] bg-white hover:border-[#CBD5E1] hover:bg-[#F1F5F9] cursor-pointer"
          } ${isUploading ? "pointer-events-none opacity-50" : ""}`}
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !isUploading && fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && !isUploading && fileInputRef.current?.click()}
          aria-label="File drop zone"
        >
          <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileInput} disabled={isUploading} />

          {/* Icon */}
          <div className={`w-20 h-20 mb-5 rounded-full flex items-center justify-center transition-all duration-200 ${
            isDragging ? "bg-[rgba(249,115,22,0.15)] scale-110" : "bg-[#F1F5F9]"
          }`}>
            <svg className={`w-10 h-10 transition-colors ${isDragging ? "text-[#F97316]" : "text-[#64748B]"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d={isDragging
                  ? "M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  : "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                }
              />
            </svg>
          </div>

          <h3 className="text-base font-semibold text-[#0F172A] mb-1.5">
            {isDragging ? "Release to drop files" : "Drop files here"}
          </h3>
          <p className="text-xs text-[#64748B] mb-6 text-center max-w-xs leading-relaxed">
            PDF, Excel, CSV, Images, or ZIP archives.<br />Loose files are automatically packaged.
          </p>

          <button
            type="button"
            className="px-5 py-2 bg-[#F1F5F9] border border-[#CBD5E1] rounded-lg text-sm font-medium text-[#475569] hover:text-[#0F172A] hover:border-[#F97316]/50 transition-all"
            disabled={isExtracting}
            onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
          >
            {isExtracting ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-3.5 w-3.5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Processing…
              </span>
            ) : "Browse Files"}
          </button>

          {/* Supported format pills */}
          <div className="flex gap-1.5 mt-5 flex-wrap justify-center">
            {["PDF", "XLSX", "CSV", "JPG", "ZIP"].map((fmt) => (
              <span key={fmt} className="px-2 py-0.5 rounded text-[9px] font-semibold bg-[#F8FAFC] border border-[#E2E8F0] text-[#64748B] uppercase tracking-wide">
                {fmt}
              </span>
            ))}
          </div>
        </div>

        {/* ── Staging Area ──────────────────────────────── */}
        <div className="flex flex-col rounded-xl border border-[#E2E8F0] bg-white overflow-hidden relative min-h-[360px] max-h-[480px]">

          {/* Extracting overlay */}
          {isExtracting && (
            <div className="absolute inset-0 bg-[#F8FAFC]/70 backdrop-blur-sm z-20 flex flex-col items-center justify-center gap-3">
              <div className="w-8 h-8 border-2 border-[#E2E8F0] border-t-[#F97316] rounded-full animate-spin" />
              <p className="text-sm font-medium text-[#475569]">Extracting files…</p>
            </div>
          )}

          {/* Header */}
          <div className="px-4 py-3 border-b border-[#E2E8F0] bg-[#F1F5F9] flex items-center justify-between">
            <h3 className="text-sm font-semibold text-[#0F172A]">
              Selected Files
              <span className="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-[#E2E8F0] text-[10px] font-bold text-[#475569]">
                {stagedFiles.length}
              </span>
            </h3>
            {stagedFiles.length > 0 && (
              <button
                onClick={(e) => { e.stopPropagation(); setStagedFiles([]); }}
                className="text-xs text-[#EF4444] hover:text-[#F87171] font-medium transition-colors"
                disabled={isUploading || isExtracting}
              >
                Clear All
              </button>
            )}
          </div>

          {/* File list */}
          <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-2">
            {stagedFiles.length === 0 && !isExtracting ? (
              <div className="h-full flex flex-col items-center justify-center gap-3 opacity-40 py-8">
                <svg className="w-10 h-10 text-[#64748B]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-xs text-[#64748B]">No files selected yet</p>
              </div>
            ) : (
              stagedFiles.map((sf) => {
                const { bg, icon, ext } = getFileTypeColor(sf.file.name);
                return (
                  <div
                    key={sf.id}
                    className="group flex items-center gap-3 p-2.5 bg-[#F1F5F9] rounded-lg border border-[#E2E8F0] hover:border-[#CBD5E1] transition-all"
                  >
                    {/* File icon / preview */}
                    <div className={`w-9 h-9 rounded-lg ${bg} flex items-center justify-center overflow-hidden shrink-0`}>
                      {sf.previewUrl ? (
                        <img src={sf.previewUrl} alt="preview" className="w-full h-full object-cover rounded-lg" />
                      ) : (
                        <span className={`text-[9px] font-bold ${icon}`}>{ext}</span>
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-[#0F172A] truncate" title={sf.file.name}>
                        {sf.file.name}
                      </p>
                      <p className="text-[10px] text-[#64748B]">{formatBytes(sf.file.size)}</p>
                    </div>

                    <button
                      onClick={() => removeFile(sf.id)}
                      className="p-1 text-[#64748B] hover:text-[#EF4444] transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100 shrink-0"
                      disabled={isUploading}
                      aria-label={`Remove ${sf.file.name}`}
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer: progress or upload button */}
          <div className="p-4 border-t border-[#E2E8F0] bg-white">
            {isUploading ? (
              <div className="space-y-2.5">
                <div className="flex justify-between text-xs text-[#475569]">
                  <span className="truncate">{processingMessage}</span>
                  <span className="font-semibold text-[#F97316] ml-2 shrink-0">{uploadProgress.percentage}%</span>
                </div>
                <div className="w-full bg-[#F1F5F9] rounded-full h-1.5 overflow-hidden border border-[#E2E8F0]">
                  <div
                    className="bg-[#F97316] h-full rounded-full transition-all duration-300 ease-in-out shadow-[0_0_8px_rgba(249,115,22,0.5)]"
                    style={{ width: `${uploadProgress.percentage}%` }}
                  />
                </div>
              </div>
            ) : (
              <button
                onClick={handleUploadClick}
                disabled={!canUpload}
                className={`w-full py-2.5 px-4 rounded-lg font-semibold text-sm transition-all flex items-center justify-center gap-2 ${
                  canUpload
                    ? "bg-[#F97316] hover:bg-[#EA6C0A] text-white shadow-[0_4px_14px_rgba(249,115,22,0.35)] hover:shadow-[0_6px_20px_rgba(249,115,22,0.45)] hover:-translate-y-0.5"
                    : "bg-[#F1F5F9] text-[#64748B] border border-[#E2E8F0] cursor-not-allowed"
                }`}
              >
                {canUpload ? (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    Upload &amp; Analyze ({stagedFiles.length} {stagedFiles.length === 1 ? "file" : "files"})
                  </>
                ) : (
                  "Select files to upload"
                )}
              </button>
            )}
          </div>
        </div>
      </div>

      <WarningModal isOpen={isWarningOpen} onClose={() => setIsWarningOpen(false)} title={warningTitle} message={warningMessage} />
    </div>
  );
}
