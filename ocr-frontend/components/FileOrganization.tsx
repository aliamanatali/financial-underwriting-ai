"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragOverlay,
  defaultDropAnimationSideEffects,
  DragStartEvent,
  DragOverEvent,
  DragEndEvent,
  useDroppable,
} from "@dnd-kit/core";
import { useDraggable } from "@dnd-kit/core";
import { apiClient } from "@/lib/api";
import { DealPackage } from "@/lib/types";
import ConfirmationModal from "./ConfirmationModal";
import WarningModal from "./WarningModal";
import dynamic from 'next/dynamic';

const DocumentSidePanel = dynamic(() => import("./DocumentSidePanel"), {
  ssr: false,
});

const FilePreviewModal = dynamic(() => import("./FilePreviewModal"), {
  ssr: false,
});

// --- Types ---

export interface DocumentFile {
  id: string; // document_id
  name: string; // filename
  type: string; // document_type
  date: string;
  size: number;
}

interface FileOrganizationProps {
  packageId: string;
  initialPackage: DealPackage;
  onComplete: (files: Record<string, DocumentFile[]>) => void;
}

// Available Categories (Document Types)
const CATEGORIES = [
  "Offering Memorandum",
  "Rent Roll",
  "Financials",
  "Tax Bills",
  "Utilities",
  "Leases",
  "Building Plans & Permits",
  "Disclosures",
  "Images"
];

// --- Components ---

function FileIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-red-500">
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
      <polyline points="14 2 14 8 20 8"></polyline>
    </svg>
  );
}

function FolderIcon({ active }: { active?: boolean }) {
  return (
    <svg 
      xmlns="http://www.w3.org/2000/svg" 
      width="18" 
      height="18" 
      viewBox="0 0 24 24" 
      fill={active ? "#FF5E00" : "none"} 
      stroke={active ? "#FF5E00" : "currentColor"} 
      strokeWidth="2" 
      strokeLinecap="round" 
      strokeLinejoin="round"
      className={active ? "text-[#FF5E00]" : "text-neutral-400"}
    >
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
    </svg>
  );
}

// Sidebar Folder Droppable
interface SidebarFolderProps {
  id: string;
  title: string;
  count: number;
  isActive: boolean;
  onClick: () => void;
}

function SidebarFolder({ id, title, count, isActive, onClick }: SidebarFolderProps) {
  const { setNodeRef, isOver } = useDroppable({
    id: id,
    data: { type: "folder", category: id },
  });

  return (
    <div
      ref={setNodeRef}
      onClick={onClick}
      className={`
        flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm mb-1
        ${isActive ? "bg-orange-50 text-[#FF5E00] font-medium" : "text-neutral-600 hover:bg-neutral-50"}
        ${isOver ? "bg-orange-100 border border-orange-200" : ""}
      `}
    >
      <div className="flex items-center gap-2">
        <FolderIcon active={isActive} />
        <span className="truncate max-w-[140px]" title={title}>{title}</span>
      </div>
      <span className={`text-xs px-2 py-0.5 rounded-full ${isActive ? "bg-orange-100 text-[#FF5E00]" : "bg-neutral-100 text-neutral-500"}`}>
        {count}
      </span>
    </div>
  );
}

// Draggable File Row
interface DraggableFileRowProps {
  file: DocumentFile;
  packageId: string;
  onDelete: (id: string, name: string) => void;
  onPreview: (id: string, name: string) => void;
  isDragDisabled?: boolean;
}

function DraggableFileRow({ file, packageId, onDelete, onPreview, isDragDisabled }: DraggableFileRowProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: file.id,
    data: { type: "file", file },
    disabled: isDragDisabled
  });

  const formatDate = (dateStr: string) => {
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch (e) {
        return dateStr;
    }
  };

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
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
        } else {
            alert('Could not generate download link');
        }
    } catch (error) {
        console.error("Download failed", error);
        alert('Download failed');
    }
  };

  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className={`
        flex items-center py-3 px-4 bg-white border-b border-neutral-100 hover:bg-neutral-50 transition-colors group cursor-pointer
        ${isDragging ? "opacity-40" : ""}
      `}
      onClick={() => onPreview(file.id, file.name)}
    >
      {/* File Icon & Name */}
      <div className="flex-1 flex items-center gap-3 min-w-0">
        <div className="p-2 bg-white border border-neutral-100 rounded-lg shrink-0 text-red-500">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" x2="8" y1="13" y2="13"></line>
                <line x1="16" x2="8" y1="17" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium text-neutral-900 truncate pr-4" title={file.name}>
            {file.name}
          </p>
          <p className="text-xs text-neutral-400 truncate">
             {file.type}/{file.name.split('/').pop()}
          </p>
        </div>
      </div>

      {/* Date */}
      <div className="w-32 text-xs text-neutral-500 hidden sm:block text-right mr-8">
        {file.date ? formatDate(file.date) : "-"}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={handleDownload}
          className="p-1.5 text-neutral-400 hover:text-neutral-600 hover:bg-neutral-100 rounded transition-colors"
          title="Download"
          onPointerDown={(e) => e.stopPropagation()}
        >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" x2="12" y1="15" y2="3"></line>
            </svg>
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(file.id, file.name); }}
          className="p-1.5 text-neutral-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
          title="Delete"
          onPointerDown={(e) => e.stopPropagation()}
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      </div>
    </div>
  );
}


// --- Main Component ---

export default function FileOrganization({ packageId, initialPackage, onComplete }: FileOrganizationProps) {
  // Map: CategoryName -> List of DocumentFile
  const [filesByCategory, setFilesByCategory] = useState<Record<string, DocumentFile[]>>({});
  const [activeCategory, setActiveCategory] = useState<string>("All Documents");
  const [selectedFile, setSelectedFile] = useState<DocumentFile | null>(null);
  
  const [activeDragId, setActiveDragId] = useState<string | null>(null);
  const [activeDragFile, setActiveDragFile] = useState<DocumentFile | null>(null);

  const [isUploading, setIsUploading] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Modals
  const [warningModal, setWarningModal] = useState<{ isOpen: boolean; title: string; message: string }>({
    isOpen: false, title: "", message: ""
  });
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean; title: string; message: string; onConfirm: () => void; isDangerous?: boolean; confirmLabel?: string;
  }>({
    isOpen: false, title: "", message: "", onConfirm: () => {}
  });
  const [previewModal, setPreviewModal] = useState<{ isOpen: boolean; fileId: string; fileName: string; }>({
      isOpen: false, fileId: "", fileName: ""
  });

  // Helpers
  const parsePackageToMap = (pkg: DealPackage) => {
      const map: Record<string, DocumentFile[]> = {};
      CATEGORIES.forEach(cat => map[cat] = []);
      
      if (pkg && pkg.documents) {
        Object.entries(pkg.documents).forEach(([type, docs]) => {
            if (!map[type]) map[type] = [];
            if (Array.isArray(docs)) {
                docs.forEach(doc => {
                    const lowerName = doc.filename.toLowerCase();
                    const isSystemFile = lowerName.endsWith('thumbs.db') ||
                                       lowerName.endsWith('desktop.ini') ||
                                       lowerName.endsWith('.ds_store') ||
                                       doc.filename.startsWith('.') ||
                                       doc.filename.includes('__MACOSX');
                    
                    if (!isSystemFile) {
                        map[type].push({
                            id: doc.document_id,
                            name: doc.filename,
                            type: doc.document_type,
                            date: doc.upload_timestamp,
                            size: doc.file_size
                        });
                    }
                });
            }
        });
      }
      return map;
  };

  useEffect(() => {
    setFilesByCategory(parsePackageToMap(initialPackage));
  }, [initialPackage]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor)
  );

  // --- Drag Handlers ---

  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event;
    const { file } = active.data.current as { file: DocumentFile } || {};
    setActiveDragId(active.id as string);
    setActiveDragFile(file);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    const { file } = active.data.current as { file: DocumentFile } || {};

    setActiveDragId(null);
    setActiveDragFile(null);

    if (!over || !file) return;

    // Identified target folder
    const targetCategory = over.id as string;
    
    // Check if moving to a different category
    // We need to find the current category of the file
    let currentCategory = "";
    Object.entries(filesByCategory).forEach(([cat, files]) => {
        if (files.find(f => f.id === file.id)) {
            currentCategory = cat;
        }
    });

    if (currentCategory && targetCategory && currentCategory !== targetCategory && CATEGORIES.includes(targetCategory)) {
        // Optimistic UI Update
        const fileToMove = filesByCategory[currentCategory].find(f => f.id === file.id);
        if (!fileToMove) return;

        const updatedFile = { ...fileToMove, type: targetCategory };

        setFilesByCategory(prev => {
            const sourceList = prev[currentCategory].filter(f => f.id !== file.id);
            const targetList = [...prev[targetCategory], updatedFile];
            return {
                ...prev,
                [currentCategory]: sourceList,
                [targetCategory]: targetList
            };
        });

        // Backend Update
        setIsUpdating(true);
        try {
            console.log(`Moving document ${file.id} from ${currentCategory} to ${targetCategory}`);
            await apiClient.updateDocumentCategory(packageId, file.id, targetCategory);
        } catch (error) {
            console.error("Failed to update category:", error);
            // Revert on failure
            setFilesByCategory(prev => {
                const targetList = prev[targetCategory].filter(f => f.id !== file.id);
                const sourceList = [...prev[currentCategory], fileToMove];
                return {
                    ...prev,
                    [currentCategory]: sourceList,
                    [targetCategory]: targetList
                };
            });
            setWarningModal({
                isOpen: true,
                title: "Move Failed",
                message: "Failed to move file. Please try again."
            });
        } finally {
            setIsUpdating(false);
        }
    }
  };

  // --- Actions ---

  const handleDeleteRequest = (fileId: string, fileName: string) => {
      setConfirmModal({
          isOpen: true,
          title: "Delete File",
          message: `Are you sure you want to delete "${fileName}"? This action cannot be undone.`,
          isDangerous: true,
          confirmLabel: "Delete",
          onConfirm: () => executeDeleteFile(fileId)
      });
  };

  const handleFileSelect = (file: DocumentFile) => {
      setSelectedFile(file);
  };

  const executeDeleteFile = async (fileId: string) => {
      setIsUpdating(true);
      try {
          await apiClient.deleteDocumentFromPackage(packageId, fileId);
          // Remove from local state
          setFilesByCategory(prev => {
              const newState = { ...prev };
              Object.keys(newState).forEach(key => {
                  newState[key] = newState[key].filter(f => f.id !== fileId);
              });
              return newState;
          });
          if (selectedFile?.id === fileId) {
              setSelectedFile(null);
          }
      } catch (err) {
          console.error("Failed to delete file:", err);
          setWarningModal({
              isOpen: true,
              title: "Delete Failed",
              message: "Failed to delete file. Please try again."
          });
      } finally {
          setIsUpdating(false);
      }
  };

  const handleUploadFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!e.target.files || e.target.files.length === 0) return;
      const files = Array.from(e.target.files);
      setIsUploading(true);
      try {
          const updatedPackage = await apiClient.uploadAdditionalDocuments(packageId, files);
          setFilesByCategory(parsePackageToMap(updatedPackage));
          setWarningModal({
              isOpen: true,
              title: "Upload Successful",
              message: `Successfully uploaded ${files.length} file(s).`
          });
      } catch (err) {
          console.error("Failed to upload files:", err);
          setWarningModal({
              isOpen: true,
              title: "Upload Failed",
              message: "Failed to upload files. Please try again."
          });
      } finally {
          setIsUploading(false);
          if (fileInputRef.current) fileInputRef.current.value = "";
      }
  };

  const handleContinue = () => {
    const missingCritical = [];
    if (filesByCategory["Offering Memorandum"]?.length === 0) missingCritical.push("Offering Memorandum");
    if (filesByCategory["Rent Roll"]?.length === 0) missingCritical.push("Rent Roll");
    if (filesByCategory["Financials"]?.length === 0) missingCritical.push("Financials");

    if (missingCritical.length > 0) {
        setConfirmModal({
            isOpen: true,
            title: "Missing Documents",
            message: `You are missing critical documents:\n\n${missingCritical.map(d => `• ${d}`).join('\n')}\n\nAnalysis quality may be significantly reduced. Are you sure you want to continue?`,
            confirmLabel: "Continue Anyway",
            onConfirm: () => onComplete(filesByCategory)
        });
        return;
    }
    onComplete(filesByCategory);
  };

  // --- Render ---

  // Flatten files if "All Documents" is selected
  const displayFiles = activeCategory === "All Documents" 
    ? Object.values(filesByCategory).flat().sort((a,b) => (a.type || "").localeCompare(b.type || "")) 
    : filesByCategory[activeCategory] || [];
  
  const totalFilesCount = Object.values(filesByCategory).flat().length;

  return (
    <div className="flex flex-col h-[calc(100vh-180px)] min-h-[600px] bg-white rounded-xl shadow-sm border border-neutral-200 overflow-hidden">
        {/* Header Section */}
        <div className="flex items-center justify-between p-6 border-b border-neutral-100 bg-white">
            <div>
                <h2 className="text-xl font-semibold text-neutral-900">Review & Organize Files</h2>
                <p className="text-sm text-neutral-400 mt-1">Files can be organized by dragging them into the desired folders.</p>
            </div>
            <div className="flex items-center gap-3">
                 <input
                    type="file"
                    multiple
                    className="hidden"
                    ref={fileInputRef}
                    onChange={handleUploadFiles}
                />
                <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploading}
                    className="px-4 py-2 bg-white border border-neutral-300 text-neutral-700 rounded-lg text-sm font-medium hover:bg-neutral-50 transition-colors shadow-sm flex items-center gap-2"
                >
                    {isUploading ? "Uploading..." : "Upload Files"}
                </button>
                <button
                    onClick={handleContinue}
                    disabled={isUploading || isUpdating}
                    className="px-6 py-2 bg-[#FF5E00] text-white rounded-lg text-sm font-medium hover:bg-[#E05200] transition-colors shadow-sm disabled:opacity-50"
                >
                    {isUpdating ? "Updating..." : "Confirm & Start Analysis"}
                </button>
            </div>
        </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="flex flex-1 overflow-hidden">
            {/* Sidebar */}
            <div className="w-72 shrink-0 bg-white border-r border-neutral-100 flex flex-col p-4 overflow-y-auto custom-scrollbar">
                <div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-4 px-3">
                    Directories
                </div>

                {/* All Documents Option */}
                <div
                    onClick={() => setActiveCategory("All Documents")}
                    className={`
                        flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm mb-1
                        ${activeCategory === "All Documents" ? "bg-orange-50 text-[#FF5E00] font-medium" : "text-neutral-600 hover:bg-neutral-50"}
                    `}
                >
                    <div className="flex items-center gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={activeCategory === "All Documents" ? "text-[#FF5E00]" : "text-neutral-400"}>
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                            <line x1="16" x2="8" y1="13" y2="13"></line>
                            <line x1="16" x2="8" y1="17" y2="17"></line>
                            <polyline points="10 9 9 9 8 9"></polyline>
                        </svg>
                        <span>All Documents</span>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${activeCategory === "All Documents" ? "bg-orange-100 text-[#FF5E00]" : "bg-neutral-100 text-neutral-500"}`}>
                        {totalFilesCount}
                    </span>
                </div>

                <div className="my-2 border-b border-neutral-100"></div>

                {/* Category Folders */}
                {CATEGORIES.map(category => (
                    <SidebarFolder
                        key={category}
                        id={category}
                        title={category}
                        count={filesByCategory[category]?.length || 0}
                        isActive={activeCategory === category}
                        onClick={() => setActiveCategory(category)}
                    />
                ))}
            </div>

            {/* Main Content Area */}
            <div className="flex-1 min-w-0 bg-white flex flex-col overflow-hidden">
                {/* Header */}
                <div className="px-6 py-4 border-b border-neutral-100 flex items-center justify-between">
                    <h3 className="font-semibold text-neutral-900">{activeCategory}</h3>
                </div>

                {/* Table Header */}
                <div className="px-6 py-2 bg-neutral-50 border-b border-neutral-100 flex items-center text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                    <div className="flex-1">File Name</div>
                    <div className="w-32 text-right mr-16">Date</div>
                </div>

                {/* File List */}
                <div className="flex-1 overflow-y-auto p-2 min-h-0 custom-scrollbar">
                    {displayFiles.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-64 text-neutral-400">
                            <p className="mb-2">No files in this folder</p>
                            <p className="text-sm">Drag files here from other folders or upload new ones</p>
                        </div>
                    ) : (
                        displayFiles.map(file => (
                            <DraggableFileRow
                                key={file.id}
                                file={file}
                                packageId={packageId}
                                onDelete={handleDeleteRequest}
                                onPreview={() => handleFileSelect(file)}
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

        <DragOverlay dropAnimation={{ sideEffects: defaultDropAnimationSideEffects({ styles: { active: { opacity: '0.5' } } }) }}>
           {activeDragFile ? (
             <div className="flex items-center gap-3 p-3 bg-white border border-[#FF5E00] rounded-lg shadow-xl w-80">
                <div className="p-2 bg-red-50 rounded-lg shrink-0">
                    <FileIcon />
                </div>
                <div className="flex-1 min-w-0">
                   <p className="text-sm font-medium text-neutral-900 truncate">{activeDragFile.name}</p>
                </div>
             </div>
           ) : null}
        </DragOverlay>

      </DndContext>

      <ConfirmationModal
        isOpen={confirmModal.isOpen}
        onClose={() => setConfirmModal({ ...confirmModal, isOpen: false })}
        onConfirm={confirmModal.onConfirm}
        title={confirmModal.title}
        message={confirmModal.message}
        confirmLabel={confirmModal.confirmLabel}
        isDangerous={confirmModal.isDangerous}
      />

      <WarningModal
        isOpen={warningModal.isOpen}
        onClose={() => setWarningModal({ ...warningModal, isOpen: false })}
        title={warningModal.title}
        message={warningModal.message}
      />

      <FilePreviewModal
        isOpen={previewModal.isOpen}
        onClose={() => setPreviewModal({ ...previewModal, isOpen: false })}
        fileId={previewModal.fileId}
        fileName={previewModal.fileName}
        packageId={packageId}
      />
    </div>
  );
}
