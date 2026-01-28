"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { NormalizedDataItem, CategoryGroup, DocumentMetadata } from "@/lib/types";

const SourceDocumentViewer = dynamic(() => import("./SourceDocumentViewer"), {
  ssr: false,
});

interface DataVerificationTableProps {
  items: NormalizedDataItem[];
  availableCategories: string[];
  documents: Record<string, DocumentMetadata[]>;
  packageId?: string;
  onVerify: (itemId: string, userCorrection?: string) => void;
  onVerifyAll: () => void;
}

export default function DataVerificationTable({
  items,
  availableCategories,
  documents,
  packageId,
  onVerify,
  onVerifyAll,
}: DataVerificationTableProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>("");
  const [viewingItem, setViewingItem] = useState<NormalizedDataItem | null>(null);

  const handleEdit = (item: NormalizedDataItem) => {
    setEditingId(item.id);
    setEditValue(item.user_correction || item.normalized_value);
  };

  // Group items by category_group
  const groupedItems = items.reduce((acc, item) => {
    const group = item.category_group || "Other";
    if (!acc[group]) {
      acc[group] = [];
    }
    acc[group].push(item);
    return acc;
  }, {} as Record<string, NormalizedDataItem[]>);

  // Define group order
  const groupOrder: CategoryGroup[] = [
    "Revenue",
    "Operating Expense",
    "Capital Expenditure",
    "Tax & Insurance",
    "Debt",
    "Property Info",
    "Other"
  ];

  const handleSave = (itemId: string) => {
    const originalItem = items.find((i) => i.id === itemId);
    if (originalItem && editValue !== originalItem.normalized_value) {
      onVerify(itemId, editValue);
    } else {
      onVerify(itemId);
    }
    setEditingId(null);
    setEditValue("");
  };

  const handleCancel = () => {
    setEditingId(null);
    setEditValue("");
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.95) return "text-emerald-700 bg-emerald-50 border border-emerald-100";
    if (confidence >= 0.85) return "text-amber-700 bg-amber-50 border border-amber-100";
    return "text-rose-700 bg-rose-50 border border-rose-100";
  };


  const getDocumentId = (item: NormalizedDataItem): string | undefined => {
    if (!documents) return undefined;

    // Flatten all documents from the documents object
    const allDocuments = Object.values(documents).flat();
    
    // Find the document that matches the source_document filename
    const doc = allDocuments.find(d => d.filename === item.source_document);

    return doc?.document_id;
  };

  return (
    <div className="space-y-6">

      {/* Grouped Tables */}
      <div className="space-y-8">
        {groupOrder.map((group) => {
            const groupItems = groupedItems[group];
            if (!groupItems || groupItems.length === 0) return null;

            return (
                <div key={group} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                    <div className="bg-slate-50 px-6 py-4 border-b border-slate-200 flex justify-between items-center">
                        <h3 className="text-lg font-semibold text-slate-900">{group}</h3>
                        <span className="text-sm text-slate-500">{groupItems.length} items</span>
                    </div>
                    <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-white">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Source Document
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Raw Text
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Mapped Category
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Confidence
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Actions
                            </th>
                        </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-200">
                        {groupItems.map((item) => (
                            <tr
                            key={item.id}
                            className={`transition-colors duration-150 ${
                                item.user_verified ? "bg-emerald-50/30" : "hover:bg-slate-50"
                            }`}
                            >
                            {/* Source Document */}
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                                <div className="flex items-center gap-2">
                                  <div className="flex items-center flex-1 min-w-0" title={item.source_document}>
                                      <svg className="w-4 h-4 mr-2 text-slate-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                      </svg>
                                      <span className="truncate max-w-[120px]">{item.source_document}</span>
                                  </div>
                                  {item.metadata?.page_number && getDocumentId(item) && (
                                    <button
                                      onClick={() => setViewingItem(item)}
                                      className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-colors"
                                      title="View Source Document"
                                    >
                                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
                                        <circle cx="12" cy="12" r="3"/>
                                      </svg>
                                    </button>
                                  )}
                                </div>
                            </td>

                            {/* Raw Text */}
                            <td className="px-6 py-4 text-sm text-slate-900">
                                <div className="max-w-xs" title={item.raw_text}>
                                <span className="font-mono text-xs bg-slate-100 px-2 py-1.5 rounded-md text-slate-600 border border-slate-200 inline-block truncate max-w-[200px]">
                                    {item.raw_text}
                                </span>
                                </div>
                            </td>

                            {/* Mapped Category */}
                            <td className="px-6 py-4 text-sm">
                                {editingId === item.id ? (
                                <select
                                    value={editValue}
                                    onChange={(e) => setEditValue(e.target.value)}
                                    className="block w-full px-3 py-2 text-sm border-slate-300 rounded-md shadow-sm focus:ring-#FFF5F00 focus:border-#FFF5F00"
                                    autoFocus
                                >
                                    {availableCategories.map((category) => (
                                    <option key={category} value={category}>
                                        {category}
                                    </option>
                                    ))}
                                </select>
                                ) : (
                                <div className="flex flex-col">
                                    <span
                                    className={`font-medium ${
                                        item.user_correction
                                        ? "text-#E65400"
                                        : "text-slate-900"
                                    }`}
                                    >
                                    {item.user_correction || item.normalized_value}
                                    </span>
                                    {item.user_correction && (
                                    <span className="text-[10px] uppercase font-bold text-[#FF5E00] mt-1">
                                        Edited
                                    </span>
                                    )}
                                </div>
                                )}
                            </td>


                            {/* Confidence */}
                            <td className="px-6 py-4 whitespace-nowrap">
                                <span
                                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getConfidenceColor(
                                    item.confidence
                                )}`}
                                >
                                {(item.confidence * 100).toFixed(0)}%
                                </span>
                            </td>

                            {/* Actions */}
                            <td className="px-6 py-4 whitespace-nowrap text-sm">
                                {editingId === item.id ? (
                                <div className="flex space-x-3">
                                    <button
                                    onClick={() => handleSave(item.id)}
                                    className="text-emerald-600 hover:text-emerald-800 font-semibold"
                                    >
                                    Save
                                    </button>
                                    <button
                                    onClick={handleCancel}
                                    className="text-slate-500 hover:text-slate-700 font-medium"
                                    >
                                    Cancel
                                    </button>
                                </div>
                                ) : (
                                <div className="flex items-center space-x-4">
                                    {!item.user_verified ? (
                                    <>
                                        <button
                                        onClick={() => handleEdit(item)}
                                        className="text-slate-500 hover:text-[#FF5E00] font-medium transition-colors"
                                        >
                                        Edit
                                        </button>
                                        <button
                                        onClick={() => onVerify(item.id)}
                                        className="text-[#FF5E00] hover:text-blue-800 font-semibold transition-colors flex items-center"
                                        >
                                        Verify
                                        </button>
                                    </>
                                    ) : (
                                       <span className="inline-flex items-center text-emerald-700 font-medium text-sm">
                                            <svg className="w-4 h-4 mr-1.5" fill="currentColor" viewBox="0 0 20 20">
                                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                            </svg>
                                            Verified
                                        </span>
                                    )}
                                </div>
                                )}
                            </td>
                            </tr>
                        ))}
                        </tbody>
                    </table>
                    </div>
                </div>
            );
        })}
      </div>

      {/* Legend */}
      <div className="bg-white rounded-lg p-4 border border-slate-200">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
          Confidence Score Legend
        </h3>
        <div className="flex space-x-6 text-sm">
          <div className="flex items-center">
            <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full mr-2"></span>
            <span className="text-slate-600">High Confidence (≥95%)</span>
          </div>
          <div className="flex items-center">
            <span className="w-2.5 h-2.5 bg-amber-500 rounded-full mr-2"></span>
            <span className="text-slate-600">Medium Confidence (85-94%)</span>
          </div>
          <div className="flex items-center">
            <span className="w-2.5 h-2.5 bg-rose-500 rounded-full mr-2"></span>
            <span className="text-slate-600">Low Confidence (Less than 85%)</span>
          </div>
        </div>
      </div>
      {viewingItem && getDocumentId(viewingItem) && (
        <SourceDocumentViewer
          documentId={getDocumentId(viewingItem)!}
          packageId={packageId}
          filename={viewingItem.source_document}
          pageNumber={viewingItem.metadata?.page_number}
          bbox={viewingItem.metadata?.bbox}
          onClose={() => setViewingItem(null)}
        />
      )}
    </div>
  );
}
