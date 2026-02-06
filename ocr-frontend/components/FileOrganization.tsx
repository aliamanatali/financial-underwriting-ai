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
} from "@dnd-kit/core";
import { 
  arrayMove, 
  SortableContext, 
  sortableKeyboardCoordinates, 
  verticalListSortingStrategy,
  useSortable
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { apiClient } from "@/lib/api";
import { DealPackage } from "@/lib/types";
import ConfirmationModal from "./ConfirmationModal";
import WarningModal from "./WarningModal";
import dynamic from 'next/dynamic';

const FilePreviewModal = dynamic(() => import("./FilePreviewModal"), {
  ssr: false,
});

// --- Types ---

interface DocumentFile {
  id: string; // document_id
  name: string; // filename
  type: string; // document_type
}

interface FileOrganizationProps {
  packageId: string;
  initialPackage: DealPackage;
  onComplete: () => void;
}

// --- Draggable File Component ---

interface SortableFileProps {
  id: string;
  file: DocumentFile;
  onDelete?: (fileId: string, fileName: string) => void;
  onPreview?: (fileId: string, fileName: string) => void;
}

function SortableFile({ id, file, onDelete, onPreview }: SortableFileProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: id, data: { type: "file", file } });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent drag start
    if (onDelete) {
      onDelete(id, file.name);
    }
  };

  const handlePreview = (e: React.MouseEvent) => {
      // If user is not dragging, trigger preview
      // Note: isDragging prop in this component is about the item being dragged, not detecting drag intent
      // We can use a simple onClick here, dnd-kit should prevent onClick if it's a drag operation usually
      if (onPreview) {
          onPreview(id, file.name);
      }
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      title={file.name}
      className="flex items-center gap-3 p-3 bg-white border border-neutral-200 rounded-lg shadow-sm mb-2 group hover:border-neutral-300 transition-colors relative"
    >
        {/* Drag Handle Area */}
        <div
            {...attributes}
            {...listeners}
            onClick={handlePreview}
            className="flex-1 flex items-center gap-3 min-w-0 cursor-pointer"
        >
            <div className="w-8 h-8 flex-shrink-0 bg-neutral-100 rounded flex items-center justify-center text-neutral-400">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
            </div>
            <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-neutral-900 truncate hover:underline text-left" title={file.name}>
                {file.name}
                </p>
            </div>
        </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {onDelete && (
            <button
                onClick={handleDelete}
                className="p-1 text-neutral-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                title="Delete file"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 6h18"></path>
                    <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                    <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                </svg>
            </button>
        )}
        <div {...attributes} {...listeners} className="text-neutral-300 cursor-grab active:cursor-grabbing">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="9" cy="12" r="1"></circle>
                <circle cx="9" cy="5" r="1"></circle>
                <circle cx="9" cy="19" r="1"></circle>
                <circle cx="15" cy="12" r="1"></circle>
                <circle cx="15" cy="5" r="1"></circle>
                <circle cx="15" cy="19" r="1"></circle>
            </svg>
        </div>
      </div>
    </div>
  );
}

// --- Droppable Folder Component ---

interface FolderProps {
  id: string; // This is the category name (DocumentType)
  title: string;
  files: DocumentFile[];
  onDeleteFile: (fileId: string, fileName: string) => void;
  onPreviewFile: (fileId: string, fileName: string) => void;
}

function Folder({ id, title, files, onDeleteFile, onPreviewFile }: FolderProps) {
  const { setNodeRef, isOver } = useSortable({
    id: id,
    data: { type: "folder", category: id },
    disabled: true // Folders themselves are not draggable, just droppable via SortableContext logic
  });

  return (
    <div 
      ref={setNodeRef}
      className={`bg-neutral-50 rounded-xl border-2 transition-colors h-full flex flex-col ${
        isOver ? "border-amber-500 bg-amber-50" : "border-transparent"
      }`}
    >
      <div className="p-4 border-b border-neutral-200 flex items-center justify-between bg-white rounded-t-xl">
        <h3 className="font-semibold text-neutral-900 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-neutral-400"></span>
            {title}
        </h3>
        <span className="text-xs font-medium text-neutral-500 bg-neutral-100 px-2 py-1 rounded-full">
          {files.length}
        </span>
      </div>
      <div className="p-4 flex-1 overflow-y-auto min-h-[120px] max-h-[400px]">
        <SortableContext
            id={id}
            items={files.map(f => f.id)}
            strategy={verticalListSortingStrategy}
        >
          {files.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-neutral-400 py-8 border-2 border-dashed border-neutral-200 rounded-lg">
              <p className="text-sm">Empty Folder</p>
              <p className="text-xs">Drop files here</p>
            </div>
          ) : (
            files.map((file) => (
              <SortableFile key={file.id} id={file.id} file={file} onDelete={onDeleteFile} onPreview={onPreviewFile} />
            ))
          )}
        </SortableContext>
      </div>
    </div>
  );
}

// --- Main Component ---

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

export default function FileOrganization({ packageId, initialPackage, onComplete }: FileOrganizationProps) {
  // State to track files in each category
  // Map: CategoryName -> List of DocumentFile
  const [filesByCategory, setFilesByCategory] = useState<Record<string, DocumentFile[]>>({});
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeFile, setActiveFile] = useState<DocumentFile | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Modals
  const [warningModal, setWarningModal] = useState<{ isOpen: boolean; title: string; message: string }>({
    isOpen: false,
    title: "",
    message: ""
  });
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
    isDangerous?: boolean;
    confirmLabel?: string;
  }>({
    isOpen: false,
    title: "",
    message: "",
    onConfirm: () => {}
  });
  const [previewModal, setPreviewModal] = useState<{
      isOpen: boolean;
      fileId: string;
      fileName: string;
  }>({
      isOpen: false,
      fileId: "",
      fileName: ""
  });

  // Helper to parse package data into map
  const parsePackageToMap = (pkg: DealPackage) => {
      const map: Record<string, DocumentFile[]> = {};
      CATEGORIES.forEach(cat => map[cat] = []);
      
      if (pkg && pkg.documents) {
        Object.entries(pkg.documents).forEach(([type, docs]) => {
            if (!map[type]) map[type] = [];
            if (Array.isArray(docs)) {
                docs.forEach(doc => {
                    map[type].push({
                        id: doc.document_id,
                        name: doc.filename,
                        type: doc.document_type
                    });
                });
            }
        });
      }
      return map;
  };

  // Initialize state from initialPackage
  useEffect(() => {
    setFilesByCategory(parsePackageToMap(initialPackage));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPackage]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
        activationConstraint: {
            distance: 8,
        },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event;
    const { file } = active.data.current as { file: DocumentFile } || {};
    setActiveId(active.id as string);
    setActiveFile(file);
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { active, over } = event;
    if (!over) return;

    // Find the containers
    const activeContainer = findContainer(active.id as string);
    const overContainer = findContainer(over.id as string) || (CATEGORIES.includes(over.id as string) ? over.id as string : null);

    if (!activeContainer || !overContainer || activeContainer === overContainer) {
      return;
    }

    // Move item in local state for smooth visual feedback
    setFilesByCategory((prev) => {
      const activeItems = prev[activeContainer];
      const overItems = prev[overContainer];
      const activeIndex = activeItems.findIndex((item) => item.id === active.id);
      
      // If dropping on a container (folder), add to end
      // If dropping on an item, insert at that index
      let overIndex;
      if (CATEGORIES.includes(over.id as string)) {
        overIndex = overItems.length + 1;
      } else {
        const isBelowOverItem =
          over &&
          active.rect.current.translated &&
          active.rect.current.translated.top >
            over.rect.top + over.rect.height;

        const modifier = isBelowOverItem ? 1 : 0;
        overIndex = overIndex = overItems.findIndex((item) => item.id === over.id) + modifier;
      }

      return {
        ...prev,
        [activeContainer]: [
          ...prev[activeContainer].filter((item) => item.id !== active.id),
        ],
        [overContainer]: [
          ...prev[overContainer].slice(0, overIndex),
          activeItems[activeIndex],
          ...prev[overContainer].slice(overIndex, prev[overContainer].length),
        ],
      };
    });
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    const { file } = active.data.current as { file: DocumentFile } || {};

    // Determine final container
    const activeContainer = findContainer(active.id as string);
    const overContainer = findContainer(over?.id as string) || (over && CATEGORIES.includes(over.id as string) ? over.id as string : null);

    if (activeContainer && overContainer && activeContainer !== overContainer) {
       // Backend Update
       try {
           console.log(`Moving document ${file.id} from ${activeContainer} to ${overContainer}`);
           await apiClient.updateDocumentCategory(packageId, file.id, overContainer);
           // Update the file's type locally
           file.type = overContainer;
       } catch (error) {
           console.error("Failed to update category:", error);
           setWarningModal({
               isOpen: true,
               title: "Move Failed",
               message: "Failed to move file. Please try again."
           });
       }
    }

    setActiveId(null);
    setActiveFile(null);
  };

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

  const handlePreviewRequest = (fileId: string, fileName: string) => {
      setPreviewModal({
          isOpen: true,
          fileId,
          fileName
      });
  };

  const executeDeleteFile = async (fileId: string) => {
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
      } catch (err) {
          console.error("Failed to delete file:", err);
          setWarningModal({
              isOpen: true,
              title: "Delete Failed",
              message: "Failed to delete file. Please try again."
          });
      }
  };

  const handleUploadFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!e.target.files || e.target.files.length === 0) return;
      
      const files = Array.from(e.target.files);
      setIsUploading(true);
      
      try {
          // Upload and get updated package
          // This endpoint automatically characterizes files via AI
          const updatedPackage = await apiClient.uploadAdditionalDocuments(packageId, files);
          
          // Update local state with new package data
          setFilesByCategory(parsePackageToMap(updatedPackage));
          
          setWarningModal({
              isOpen: true,
              title: "Upload Successful",
              message: `Successfully uploaded ${files.length} file(s).\n\nThey have been automatically characterized and placed in the appropriate folders.`
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
          // Reset input
          if (fileInputRef.current) fileInputRef.current.value = "";
      }
  };

  const findContainer = (id: string): string | undefined => {
    if (CATEGORIES.includes(id)) {
      return id;
    }

    return Object.keys(filesByCategory).find((key) =>
      filesByCategory[key].find((item) => item.id === id)
    );
  };

  const handleContinue = () => {
    // Check if critical folders have files
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
            onConfirm: () => onComplete()
        });
        return;
    }
    
    onComplete();
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-6">
        <div>
            <h2 className="text-xl font-semibold text-neutral-900">Review & Organize Files</h2>
            <p className="text-sm text-neutral-500">Drag and drop files to their correct categories. Add or remove files as needed.</p>
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
                className="px-4 py-2 bg-white border border-neutral-300 text-neutral-700 rounded-lg font-medium hover:bg-neutral-50 transition-colors shadow-sm flex items-center gap-2"
            >
                {isUploading ? (
                    <>
                        <div className="w-4 h-4 border-2 border-neutral-400 border-t-neutral-800 rounded-full animate-spin"></div>
                        <span>Uploading...</span>
                    </>
                ) : (
                    <>
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="17 8 12 3 7 8"></polyline>
                            <line x1="12" x2="12" y1="3" y2="15"></line>
                        </svg>
                        Upload Files
                    </>
                )}
            </button>
            <button
                onClick={handleContinue}
                disabled={isUploading}
                className="px-6 py-2 bg-neutral-900 text-white rounded-lg font-medium hover:bg-neutral-800 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
                Confirm & Start Analysis
            </button>
        </div>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pb-20">
          {CATEGORIES.map((category) => (
            <Folder
              key={category}
              id={category}
              title={category}
              files={filesByCategory[category] || []}
              onDeleteFile={handleDeleteRequest}
              onPreviewFile={handlePreviewRequest}
            />
          ))}
        </div>

        <DragOverlay dropAnimation={{ sideEffects: defaultDropAnimationSideEffects({ styles: { active: { opacity: '0.5' } } }) }}>
          {activeFile ? <SortableFile id={activeId!} file={activeFile} /> : null}
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