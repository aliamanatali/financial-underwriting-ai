"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors,
  DragOverlay, defaultDropAnimationSideEffects,
  DragStartEvent, DragEndEvent, useDroppable,
} from "@dnd-kit/core";
import { useDraggable } from "@dnd-kit/core";
import { apiClient } from "@/lib/api";
import { DealPackage } from "@/lib/types";
import ConfirmationModal from "./ConfirmationModal";
import WarningModal from "./WarningModal";
import dynamic from "next/dynamic";

const DocumentSidePanel = dynamic(() => import("./DocumentSidePanel"), { ssr: false });
const FilePreviewModal = dynamic(() => import("./FilePreviewModal"), { ssr: false });

export interface DocumentFile {
  id: string;
  name: string;
  type: string;
  date: string;
  size: number;
}

interface FileOrganizationProps {
  packageId: string;
  initialPackage: DealPackage;
  onComplete: (files: Record<string, DocumentFile[]>) => void;
}

const CATEGORIES = [
  "Offering Memorandum", "Rent Roll", "Financials", "Tax Bills",
  "Utilities", "Leases", "Building Plans & Permits", "Disclosures", "Images",
];

const REQUIRED_CATEGORIES = ["Offering Memorandum", "Rent Roll", "Financials"];

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  "Offering Memorandum": (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" x2="8" y1="13" y2="13" /><line x1="16" x2="8" y1="17" y2="17" />
    </svg>
  ),
  "Rent Roll": (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M3 15h18M9 3v18" />
    </svg>
  ),
  "Financials": (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" x2="12" y1="1" y2="23" /><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  ),
  "Tax Bills": (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
      <polyline points="14 2 14 8 20 8" /><path d="M10 12h4M10 16h4M10 8h1" />
    </svg>
  ),
  "Utilities": (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
    </svg>
  ),
  "Leases": (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
    </svg>
  ),
  "Building Plans & Permits": (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M9 21V9" />
    </svg>
  ),
  "Disclosures": (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
  "Images": (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" />
      <polyline points="21 15 16 10 5 21" />
    </svg>
  ),
};

function getFileTypeInfo(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  if (ext === 'pdf') return { label: 'PDF', color: '#EF4444', bgColor: 'rgba(239,68,68,0.08)', borderColor: 'rgba(239,68,68,0.15)', icon: 'document' as const };
  if (['xlsx', 'xls', 'csv'].includes(ext)) return { label: ext.toUpperCase(), color: '#10B981', bgColor: 'rgba(16,185,129,0.08)', borderColor: 'rgba(16,185,129,0.15)', icon: 'spreadsheet' as const };
  if (['doc', 'docx'].includes(ext)) return { label: ext.toUpperCase(), color: '#3B82F6', bgColor: 'rgba(59,130,246,0.08)', borderColor: 'rgba(59,130,246,0.15)', icon: 'document' as const };
  if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'heif'].includes(ext)) return { label: ext.toUpperCase(), color: '#8B5CF6', bgColor: 'rgba(139,92,246,0.08)', borderColor: 'rgba(139,92,246,0.15)', icon: 'image' as const };
  if (['mov', 'mp4', 'avi', 'mkv'].includes(ext)) return { label: ext.toUpperCase(), color: '#F59E0B', bgColor: 'rgba(245,158,11,0.08)', borderColor: 'rgba(245,158,11,0.15)', icon: 'video' as const };
  return { label: ext.toUpperCase() || 'FILE', color: '#64748B', bgColor: 'rgba(100,116,139,0.08)', borderColor: 'rgba(100,116,139,0.15)', icon: 'document' as const };
}

function FileTypeIcon({ filename }: { filename: string }) {
  const info = getFileTypeInfo(filename);
  return (
    <div className="relative shrink-0">
      <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ backgroundColor: info.bgColor, border: `1px solid ${info.borderColor}` }}>
        {info.icon === 'image' ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" style={{ color: info.color }}>
            <rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" />
            <polyline points="21 15 16 10 5 21" />
          </svg>
        ) : info.icon === 'video' ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" style={{ color: info.color }}>
            <rect x="2" y="4" width="20" height="16" rx="2" />
            <polygon points="10 9 15 12 10 15" />
          </svg>
        ) : info.icon === 'spreadsheet' ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" style={{ color: info.color }}>
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="8" x2="16" y1="13" y2="13" /><line x1="8" x2="16" y1="17" y2="17" />
            <line x1="12" x2="12" y1="10" y2="20" />
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" style={{ color: info.color }}>
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" x2="8" y1="13" y2="13" /><line x1="16" x2="8" y1="17" y2="17" />
          </svg>
        )}
      </div>
      <span className="absolute -bottom-1 -right-1 text-[7px] font-bold text-white px-1 py-px rounded leading-none" style={{ backgroundColor: info.color }}>{info.label}</span>
    </div>
  );
}

interface SidebarFolderProps {
  id: string; title: string; count: number; isActive: boolean; onClick: () => void; isRequired?: boolean;
}

function SidebarFolder({ id, title, count, isActive, onClick, isRequired }: SidebarFolderProps) {
  const { setNodeRef, isOver } = useDroppable({ id, data: { type: "folder", category: id } });
  const isEmpty = count === 0;
  const showWarning = isRequired && isEmpty;

  return (
    <div
      ref={setNodeRef}
      onClick={onClick}
      className={`group flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-all text-xs mb-0.5 ${
        isActive
          ? "bg-[rgba(249,115,22,0.1)] text-[#F97316]"
          : "text-[#64748B] hover:bg-white hover:text-[#0F172A] hover:shadow-sm"
      } ${isOver ? "bg-[rgba(249,115,22,0.08)] ring-1 ring-[rgba(249,115,22,0.3)]" : ""}`}
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <span className={`shrink-0 transition-colors ${isActive ? "text-[#F97316]" : showWarning ? "text-amber-400" : "text-[#94A3B8] group-hover:text-[#64748B]"}`}>
          {CATEGORY_ICONS[title] || (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
          )}
        </span>
        <span className="truncate font-medium" title={title}>{title}</span>
        {isRequired && (
          <span className="shrink-0 text-[8px] font-semibold text-[#94A3B8] uppercase tracking-wide">req</span>
        )}
      </div>
      <div className="flex items-center gap-1.5 shrink-0 ml-2">
        {showWarning && (
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
        )}
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold tabular-nums ${
          isActive
            ? "bg-[rgba(249,115,22,0.15)] text-[#F97316]"
            : count > 0
            ? "bg-[#F1F5F9] text-[#475569]"
            : "bg-[#F8FAFC] text-[#CBD5E1]"
        }`}>
          {count}
        </span>
      </div>
    </div>
  );
}

interface DraggableFileRowProps {
  file: DocumentFile; packageId: string;
  onDelete: (id: string, name: string) => void;
  onPreview: (id: string, name: string) => void;
  isDragDisabled?: boolean;
}

function DraggableFileRow({ file, packageId, onDelete, onPreview, isDragDisabled }: DraggableFileRowProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: file.id, data: { type: "file", file }, disabled: isDragDisabled,
  });

  const formatDate = (dateStr: string) => {
    try { return new Date(dateStr).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }); }
    catch { return dateStr; }
  };

  const formatSize = (bytes: number) => {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const response = await apiClient.getDocumentContentUrl(packageId, file.id);
      const url = response.signed_url || (response.content ? `data:${response.content_type};base64,${response.content}` : null);
      if (url) { const a = document.createElement("a"); a.href = url; a.download = file.name; document.body.appendChild(a); a.click(); document.body.removeChild(a); }
      else alert("Could not generate download link");
    } catch { alert("Download failed"); }
  };

  return (
    <div
      ref={setNodeRef} {...attributes} {...listeners}
      onClick={() => onPreview(file.id, file.name)}
      className={`flex items-center gap-4 py-3.5 px-5 border-b border-[#F1F5F9] hover:bg-[#FAFBFD] transition-colors group cursor-pointer relative ${isDragging ? "opacity-30" : ""}`}
    >
      {/* Drag handle */}
      {!isDragDisabled && (
        <div className="absolute left-1.5 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-40 transition-opacity">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" className="text-[#94A3B8]">
            <circle cx="9" cy="5" r="1.5"/><circle cx="15" cy="5" r="1.5"/>
            <circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/>
            <circle cx="9" cy="19" r="1.5"/><circle cx="15" cy="19" r="1.5"/>
          </svg>
        </div>
      )}

      <FileTypeIcon filename={file.name} />

      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-[#0F172A] truncate" title={file.name}>
          {file.name}
        </p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[10px] px-1.5 py-px rounded bg-[#F1F5F9] text-[#64748B] font-medium border border-[#E2E8F0]">
            {file.type || "Document"}
          </span>
          {file.size > 0 && (
            <span className="text-[10px] text-[#94A3B8]">{formatSize(file.size)}</span>
          )}
        </div>
      </div>

      <div className="text-[10px] text-[#94A3B8] tabular-nums hidden sm:block shrink-0">
        {file.date ? formatDate(file.date) : "—"}
      </div>

      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        <button
          onClick={handleDownload}
          onPointerDown={(e) => e.stopPropagation()}
          className="p-1.5 text-[#94A3B8] hover:text-[#475569] hover:bg-[#F1F5F9] rounded-lg transition-colors"
          title="Download"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" x2="12" y1="15" y2="3" />
          </svg>
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(file.id, file.name); }}
          onPointerDown={(e) => e.stopPropagation()}
          className="p-1.5 text-[#94A3B8] hover:text-[#EF4444] hover:bg-[rgba(239,68,68,0.08)] rounded-lg transition-colors"
          title="Delete"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </button>
      </div>
    </div>
  );
}

export default function FileOrganization({ packageId, initialPackage, onComplete }: FileOrganizationProps) {
  const [filesByCategory, setFilesByCategory] = useState<Record<string, DocumentFile[]>>({});
  const [activeCategory, setActiveCategory] = useState<string>("All Documents");
  const [selectedFile, setSelectedFile] = useState<DocumentFile | null>(null);
  const [activeDragFile, setActiveDragFile] = useState<DocumentFile | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [warningModal, setWarningModal] = useState<{ isOpen: boolean; title: string; message: string }>({ isOpen: false, title: "", message: "" });
  const [confirmModal, setConfirmModal] = useState<{ isOpen: boolean; title: string; message: string; onConfirm: () => void; isDangerous?: boolean; confirmLabel?: string }>({ isOpen: false, title: "", message: "", onConfirm: () => {} });
  const [previewModal, setPreviewModal] = useState<{ isOpen: boolean; fileId: string; fileName: string }>({ isOpen: false, fileId: "", fileName: "" });

  const parsePackageToMap = (pkg: DealPackage) => {
    const map: Record<string, DocumentFile[]> = {};
    CATEGORIES.forEach((cat) => (map[cat] = []));
    if (pkg?.documents) {
      Object.entries(pkg.documents).forEach(([type, docs]) => {
        if (!map[type]) map[type] = [];
        if (Array.isArray(docs)) {
          docs.forEach((doc) => {
            const lower = doc.filename.toLowerCase();
            if (!lower.endsWith("thumbs.db") && !lower.endsWith("desktop.ini") && !lower.endsWith(".ds_store") && !doc.filename.startsWith(".") && !doc.filename.includes("__MACOSX")) {
              map[type].push({ id: doc.document_id, name: doc.filename, type: doc.document_type, date: doc.upload_timestamp, size: doc.file_size });
            }
          });
        }
      });
    }
    return map;
  };

  useEffect(() => { setFilesByCategory(parsePackageToMap(initialPackage)); }, [initialPackage]);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }), useSensor(KeyboardSensor));

  const handleDragStart = (event: DragStartEvent) => {
    const { file } = (event.active.data.current as { file: DocumentFile }) || {};
    setActiveDragFile(file);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    const { file } = (active.data.current as { file: DocumentFile }) || {};
    setActiveDragFile(null);
    if (!over || !file) return;
    const targetCategory = over.id as string;
    let currentCategory = "";
    Object.entries(filesByCategory).forEach(([cat, files]) => { if (files.find((f) => f.id === file.id)) currentCategory = cat; });
    if (currentCategory && targetCategory && currentCategory !== targetCategory && CATEGORIES.includes(targetCategory)) {
      const fileToMove = filesByCategory[currentCategory].find((f) => f.id === file.id);
      if (!fileToMove) return;
      const updatedFile = { ...fileToMove, type: targetCategory };
      setFilesByCategory((prev) => ({ ...prev, [currentCategory]: prev[currentCategory].filter((f) => f.id !== file.id), [targetCategory]: [...prev[targetCategory], updatedFile] }));
      setIsUpdating(true);
      try {
        await apiClient.updateDocumentCategory(packageId, file.id, targetCategory);
      } catch {
        setFilesByCategory((prev) => ({ ...prev, [targetCategory]: prev[targetCategory].filter((f) => f.id !== file.id), [currentCategory]: [...prev[currentCategory], fileToMove] }));
        setWarningModal({ isOpen: true, title: "Move Failed", message: "Failed to move file. Please try again." });
      } finally { setIsUpdating(false); }
    }
  };

  const handleDeleteRequest = (fileId: string, fileName: string) => {
    setConfirmModal({ isOpen: true, title: "Delete File", message: `Are you sure you want to delete "${fileName}"? This action cannot be undone.`, isDangerous: true, confirmLabel: "Delete", onConfirm: () => executeDeleteFile(fileId) });
  };

  const executeDeleteFile = async (fileId: string) => {
    setIsUpdating(true);
    try {
      await apiClient.deleteDocumentFromPackage(packageId, fileId);
      setFilesByCategory((prev) => { const n = { ...prev }; Object.keys(n).forEach((k) => { n[k] = n[k].filter((f) => f.id !== fileId); }); return n; });
      if (selectedFile?.id === fileId) setSelectedFile(null);
    } catch {
      setWarningModal({ isOpen: true, title: "Delete Failed", message: "Failed to delete file. Please try again." });
    } finally { setIsUpdating(false); }
  };

  const handleUploadFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const files = Array.from(e.target.files);
    setIsUploading(true);
    try {
      const updatedPackage = await apiClient.uploadAdditionalDocuments(packageId, files);
      setFilesByCategory(parsePackageToMap(updatedPackage));
      setWarningModal({ isOpen: true, title: "Upload Successful", message: `Successfully uploaded ${files.length} file(s).` });
    } catch {
      setWarningModal({ isOpen: true, title: "Upload Failed", message: "Failed to upload files. Please try again." });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleContinue = () => {
    const missing = REQUIRED_CATEGORIES.filter((d) => !filesByCategory[d]?.length);
    if (missing.length > 0) {
      setConfirmModal({
        isOpen: true, title: "Missing Documents",
        message: `You are missing critical documents:\n\n${missing.map((d) => `• ${d}`).join("\n")}\n\nAnalysis quality may be reduced. Continue anyway?`,
        confirmLabel: "Continue Anyway", onConfirm: () => onComplete(filesByCategory),
      });
      return;
    }
    onComplete(filesByCategory);
  };

  const displayFiles = activeCategory === "All Documents"
    ? Object.values(filesByCategory).flat().sort((a, b) => (a.type || "").localeCompare(b.type || ""))
    : filesByCategory[activeCategory] || [];
  const totalFilesCount = Object.values(filesByCategory).flat().length;
  const requiredFilled = REQUIRED_CATEGORIES.filter((c) => (filesByCategory[c]?.length || 0) > 0).length;

  return (
    <div className="flex flex-col h-[calc(100vh-180px)] min-h-[600px] bg-white rounded-2xl border border-[#E2E8F0] overflow-hidden shadow-[0_8px_40px_rgba(0,0,0,0.08)]">

      {/* ── Header ─────────────────────────────────────── */}
      <div className="shrink-0 flex items-center justify-between px-6 py-4 border-b border-[#E2E8F0] bg-white">
        <div className="flex items-center gap-4">
          <div className="w-9 h-9 bg-[rgba(249,115,22,0.1)] rounded-xl flex items-center justify-center shrink-0">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#F97316" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-bold text-[#0F172A] leading-tight">Review &amp; Organize Files</h2>
            <p className="text-[11px] text-[#94A3B8] mt-px">Drag files into folders · click a file to preview</p>
          </div>
          {/* Coverage pill */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-[11px] font-semibold ml-2 ${
            requiredFilled === REQUIRED_CATEGORIES.length
              ? "bg-[rgba(34,197,94,0.08)] border-[rgba(34,197,94,0.2)] text-[#22C55E]"
              : "bg-[rgba(245,158,11,0.08)] border-[rgba(245,158,11,0.2)] text-amber-600"
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${requiredFilled === REQUIRED_CATEGORIES.length ? "bg-[#22C55E]" : "bg-amber-400 animate-pulse"}`} />
            {requiredFilled}/{REQUIRED_CATEGORIES.length} required docs
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <input type="file" multiple className="hidden" ref={fileInputRef} onChange={handleUploadFiles} />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-[#E2E8F0] hover:border-[#CBD5E1] hover:bg-[#F8FAFC] text-[#475569] hover:text-[#0F172A] rounded-xl text-xs font-semibold transition-all disabled:opacity-50"
          >
            {isUploading ? (
              <>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin">
                  <path d="M21 12a9 9 0 1 1-2.5-6.2" /><path d="M21 6v6h-6" />
                </svg>
                Uploading…
              </>
            ) : (
              <>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" x2="12" y1="3" y2="15" />
                </svg>
                Upload Files
              </>
            )}
          </button>
          <button
            onClick={handleContinue}
            disabled={isUploading || isUpdating}
            className="flex items-center gap-2 px-5 py-2 bg-[#F97316] hover:bg-[#EA6C0A] text-white rounded-xl text-xs font-bold transition-all shadow-[0_4px_14px_rgba(249,115,22,0.35)] hover:shadow-[0_6px_20px_rgba(249,115,22,0.4)] disabled:opacity-50"
          >
            {isUpdating ? (
              <>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin">
                  <path d="M21 12a9 9 0 1 1-2.5-6.2" /><path d="M21 6v6h-6" />
                </svg>
                Updating…
              </>
            ) : (
              <>
                Confirm &amp; Start Analysis
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </>
            )}
          </button>
        </div>
      </div>

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
        <div className="flex flex-1 overflow-hidden">

          {/* ── Sidebar ──────────────────────────────────── */}
          <div className="w-60 shrink-0 bg-[#F8FAFC] border-r border-[#E2E8F0] flex flex-col overflow-y-auto no-scrollbar">
            <div className="px-4 pt-4 pb-2">
              <p className="text-[9px] font-bold text-[#94A3B8] uppercase tracking-widest px-1 mb-2">Directories</p>

              {/* All Documents */}
              <div
                onClick={() => setActiveCategory("All Documents")}
                className={`flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-all text-xs mb-0.5 ${
                  activeCategory === "All Documents"
                    ? "bg-[rgba(249,115,22,0.1)] text-[#F97316] font-semibold"
                    : "text-[#64748B] hover:bg-white hover:text-[#0F172A] hover:shadow-sm"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                    className={activeCategory === "All Documents" ? "text-[#F97316]" : "text-[#94A3B8]"}>
                    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" x2="8" y1="13" y2="13" /><line x1="16" x2="8" y1="17" y2="17" /><polyline points="10 9 9 9 8 9" />
                  </svg>
                  <span className="font-semibold">All Documents</span>
                </div>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold tabular-nums ${
                  activeCategory === "All Documents" ? "bg-[rgba(249,115,22,0.15)] text-[#F97316]" : "bg-[#F1F5F9] text-[#64748B]"
                }`}>
                  {totalFilesCount}
                </span>
              </div>

              <div className="my-2 h-px bg-[#E2E8F0]" />
            </div>

            <div className="px-4 pb-4 flex-1">
              {CATEGORIES.map((cat) => (
                <SidebarFolder
                  key={cat}
                  id={cat}
                  title={cat}
                  count={filesByCategory[cat]?.length || 0}
                  isActive={activeCategory === cat}
                  onClick={() => setActiveCategory(cat)}
                  isRequired={REQUIRED_CATEGORIES.includes(cat)}
                />
              ))}
            </div>

            {/* Bottom legend */}
            <div className="px-5 py-3 border-t border-[#E2E8F0] flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
              <span className="text-[10px] text-[#94A3B8]">Required, empty</span>
            </div>
          </div>

          {/* ── Main content ──────────────────────────────── */}
          <div className="flex-1 min-w-0 bg-white flex flex-col overflow-hidden">

            {/* Content header */}
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#F1F5F9] bg-white">
              <div className="flex items-center gap-2.5">
                <span className={`text-[#F97316] ${activeCategory !== "All Documents" ? "" : "hidden"}`}>
                  {CATEGORY_ICONS[activeCategory]}
                </span>
                {activeCategory === "All Documents" && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#F97316" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                )}
                <h3 className="text-sm font-bold text-[#0F172A]">{activeCategory}</h3>
                <span className="text-[10px] px-2 py-0.5 bg-[#F1F5F9] text-[#64748B] rounded-full font-semibold">
                  {displayFiles.length} {displayFiles.length === 1 ? "file" : "files"}
                </span>
              </div>
              {activeCategory !== "All Documents" && (
                <p className="text-[10px] text-[#94A3B8]">Drag files here to categorize</p>
              )}
            </div>

            {/* Column labels */}
            {displayFiles.length > 0 && (
              <div className="px-5 py-2 bg-[#F8FAFC] border-b border-[#F1F5F9] flex items-center gap-4 text-[9px] font-bold text-[#94A3B8] uppercase tracking-widest">
                <div className="w-9 shrink-0" />
                <div className="flex-1">File Name</div>
                <div className="text-right hidden sm:block w-28">Uploaded</div>
                <div className="w-16" />
              </div>
            )}

            {/* File list */}
            <div className="flex-1 overflow-y-auto min-h-0 no-scrollbar">
              {displayFiles.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full py-16 text-center px-8">
                  <div className="w-16 h-16 bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl flex items-center justify-center mb-4">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-[#CBD5E1]">
                      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                    </svg>
                  </div>
                  <p className="text-sm font-semibold text-[#0F172A] mb-1">
                    {activeCategory === "All Documents" ? "No files uploaded yet" : `No files in ${activeCategory}`}
                  </p>
                  <p className="text-xs text-[#94A3B8] max-w-[220px] leading-relaxed">
                    {activeCategory === "All Documents"
                      ? "Upload documents using the button above to get started."
                      : "Drag a file from another folder and drop it here to categorize it."}
                  </p>
                  {activeCategory === "All Documents" && (
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="mt-5 flex items-center gap-2 px-4 py-2 bg-[#F97316] hover:bg-[#EA6C0A] text-white rounded-xl text-xs font-bold transition-all shadow-[0_4px_14px_rgba(249,115,22,0.3)]"
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" x2="12" y1="3" y2="15" />
                      </svg>
                      Upload Files
                    </button>
                  )}
                </div>
              ) : (
                displayFiles.map((file) => (
                  <DraggableFileRow
                    key={file.id}
                    file={file}
                    packageId={packageId}
                    onDelete={handleDeleteRequest}
                    onPreview={() => setSelectedFile(file)}
                    isDragDisabled={activeCategory === "All Documents"}
                  />
                ))
              )}
            </div>
          </div>

          {selectedFile && (
            <DocumentSidePanel
              file={selectedFile}
              packageId={packageId}
              onClose={() => setSelectedFile(null)}
              onDelete={handleDeleteRequest}
              onViewFull={(id, name) => setPreviewModal({ isOpen: true, fileId: id, fileName: name })}
            />
          )}
        </div>

        <DragOverlay dropAnimation={{ sideEffects: defaultDropAnimationSideEffects({ styles: { active: { opacity: "0.5" } } }) }}>
          {activeDragFile ? (
            <div className="flex items-center gap-3 px-4 py-3 bg-white border border-[#F97316] rounded-xl shadow-[0_12px_40px_rgba(0,0,0,0.15)] w-72">
              <FileTypeIcon filename={activeDragFile.name} />
              <p className="text-xs font-semibold text-[#0F172A] truncate">{activeDragFile.name}</p>
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      <ConfirmationModal isOpen={confirmModal.isOpen} onClose={() => setConfirmModal({ ...confirmModal, isOpen: false })} onConfirm={confirmModal.onConfirm} title={confirmModal.title} message={confirmModal.message} confirmLabel={confirmModal.confirmLabel} isDangerous={confirmModal.isDangerous} />
      <WarningModal isOpen={warningModal.isOpen} onClose={() => setWarningModal({ ...warningModal, isOpen: false })} title={warningModal.title} message={warningModal.message} />
      <FilePreviewModal isOpen={previewModal.isOpen} onClose={() => setPreviewModal({ ...previewModal, isOpen: false })} fileId={previewModal.fileId} fileName={previewModal.fileName} packageId={packageId} />
    </div>
  );
}
