"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { NormalizedDataItem, CategoryGroup, DocumentMetadata } from "@/lib/types";

const SourceDocumentViewer = dynamic(() => import("./SourceDocumentViewer"), {
  ssr: false,
});

export type GlobalFilter = "All" | "Handwritten" | "Duplicates";

interface DataVerificationTableProps {
  items: NormalizedDataItem[];
  availableCategories: string[];
  documents: Record<string, DocumentMetadata[]>;
  packageId?: string;
  globalFilter?: GlobalFilter;
  onVerify: (itemId: string, userCorrection?: string, userRawText?: string) => void;
  onVerifyAll: () => void;
  onUpdateItem?: (updatedItem: NormalizedDataItem) => Promise<void>;
  onAddItem?: (newItem: Partial<NormalizedDataItem>) => Promise<void>;
  onRemoveItem?: (itemId: string) => Promise<void>;
}

export default function DataVerificationTable({
  items,
  availableCategories,
  documents,
  packageId,
  globalFilter = "All",
  onVerify,
  onVerifyAll,
  onUpdateItem,
  onAddItem,
  onRemoveItem,
}: DataVerificationTableProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>("");
  const [editRawTextValue, setEditRawTextValue] = useState<string>("");
  const [editAmountValue, setEditAmountValue] = useState<string | number>("");
  const [viewingItem, setViewingItem] = useState<NormalizedDataItem | null>(null);
  
  const [selectedOccurrenceIds, setSelectedOccurrenceIds] = useState<Record<string, string>>({});
  const [isAdding, setIsAdding] = useState<string | null>(null);
  const [newItem, setNewItem] = useState<{ raw_text: string; category: string; amount: string | number }>({ raw_text: "", category: "", amount: "" });
  const [isSaving, setIsSaving] = useState(false);

  const handleEdit = (item: NormalizedDataItem) => {
    setEditingId(item.id);
    setEditValue(item.user_correction || item.normalized_value);
    setEditRawTextValue(item.raw_text || "");
    setEditAmountValue(item.metadata?.amount ?? "");
  };

  interface GroupedDataField {
    id: string; // The ID of the currently selected occurrence
    occurrences: NormalizedDataItem[];
    category_group: string;
  }

  // Group items by category_group, handling deduplication
  const groupedItems = items.reduce((acc, item) => {
    const group = item.category_group || "Other";
    if (!acc[group]) {
      acc[group] = [];
    }
    
    // Deduplicate ALL fields that have a normalized value (excluding generic ones like Uncategorized/Other)
    const isDeduplicatedField = !!item.normalized_value &&
                               item.normalized_value !== "Uncategorized" &&
                               item.normalized_value !== "Other";
    
    if (isDeduplicatedField) {
      // Find if we already have this field in the group
      const existingFieldIndex = acc[group].findIndex(
        (existing) => existing.normalized_value === item.normalized_value
      );
      
      if (existingFieldIndex !== -1) {
        // We already have this field, so we need to store it as an occurrence
        // But the current groupedItems structure doesn't easily support nested occurrences
        // Let's modify the structure slightly below by mapping over it before render
        // For now, just add it to the array. We will post-process.
      }
    }
    
    acc[group].push(item);
    return acc;
  }, {} as Record<string, NormalizedDataItem[]>);

  // Post-process grouped items to handle deduplication
  const processedGroupedItems = Object.keys(groupedItems).reduce((acc, group) => {
    const itemsInGroup = groupedItems[group];
    const processedItems: GroupedDataField[] = [];
    const dedupMap = new Map<string, GroupedDataField>();

    itemsInGroup.forEach(item => {
      const isDeduplicatedField = !!item.normalized_value &&
                                 item.normalized_value !== "Uncategorized" &&
                                 item.normalized_value !== "Other";

      if (isDeduplicatedField) {
        if (!dedupMap.has(item.normalized_value)) {
          const newGroup: GroupedDataField = {
            id: item.id,
            occurrences: [item],
            category_group: group
          };
          dedupMap.set(item.normalized_value, newGroup);
          processedItems.push(newGroup);
        } else {
          const existing = dedupMap.get(item.normalized_value)!;
          existing.occurrences.push(item);
          // Auto-select verified or higher confidence
          const currentSelected = existing.occurrences.find(o => o.id === existing.id);
          if (item.user_verified && (!currentSelected || !currentSelected.user_verified)) {
              existing.id = item.id;
          } else if (!currentSelected?.user_verified && item.confidence > (currentSelected?.confidence || 0)) {
              existing.id = item.id;
          }
        }
      } else {
        processedItems.push({
          id: item.id,
          occurrences: [item],
          category_group: group
        });
      }
    });

    acc[group] = processedItems;
    return acc;
  }, {} as Record<string, GroupedDataField[]>);

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

  const handleSave = async (itemId: string) => {
    const originalItem = items.find((i) => i.id === itemId);
    if (originalItem) {
      if (onUpdateItem) {
        setIsSaving(true);
        try {
          let finalAmount: number | string | undefined = undefined;
          if (editAmountValue !== "") {
              const cleanValue = String(editAmountValue).replace(/[$,]/g, '').trim();
              const numParsed = Number(cleanValue);
              if (cleanValue !== "" && !isNaN(numParsed)) {
                  finalAmount = numParsed;
              } else {
                  finalAmount = editAmountValue;
              }
          }

          await onUpdateItem({
             ...originalItem,
             raw_text: editRawTextValue,
             user_correction: editValue,
             metadata: {
                ...(originalItem.metadata || {}),
                amount: finalAmount
             }
          });
        } finally {
          setIsSaving(false);
        }
      } else {
        const correctionChanged = editValue !== originalItem.normalized_value;
        const rawTextChanged = editRawTextValue !== originalItem.raw_text;
        
        if (correctionChanged || rawTextChanged) {
          onVerify(
            itemId,
            correctionChanged ? editValue : undefined,
            rawTextChanged ? editRawTextValue : undefined
          );
        } else {
          onVerify(itemId);
        }
      }
    }
    setEditingId(null);
    setEditValue("");
    setEditRawTextValue("");
    setEditAmountValue("");
  };

  const handleDelete = async (itemId: string) => {
     if (onRemoveItem) {
         if (confirm("Are you sure you want to remove this item?")) {
             setIsSaving(true);
             try {
                 await onRemoveItem(itemId);
             } finally {
                 setIsSaving(false);
             }
         }
     }
  };

  const handleAddNewItem = async (group: string) => {
      if (onAddItem && newItem.raw_text) {
          setIsSaving(true);
          try {
              let finalAmount: number | string | undefined = undefined;
              if (newItem.amount !== "") {
                  const cleanValue = String(newItem.amount).replace(/[$,]/g, '').trim();
                  const numParsed = Number(cleanValue);
                  if (cleanValue !== "" && !isNaN(numParsed)) {
                      finalAmount = numParsed;
                  } else {
                      finalAmount = newItem.amount;
                  }
              }

              await onAddItem({
                  raw_text: newItem.raw_text,
                  normalized_value: newItem.category || "Uncategorized",
                  category_group: group as CategoryGroup,
                  confidence: 1.0,
                  user_verified: true,
                  source_document: "Manual Entry",
                  metadata: {
                      amount: finalAmount,
                      is_manual: true
                  }
              });
              setIsAdding(null);
              setNewItem({ raw_text: "", category: "", amount: "" });
          } finally {
              setIsSaving(false);
          }
      }
  };

  const handleCancel = () => {
    setEditingId(null);
    setEditValue("");
    setEditRawTextValue("");
    setEditAmountValue("");
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

  const handleOccurrenceChange = (groupField: GroupedDataField, newOccurrenceId: string) => {
    const newOccurrence = groupField.occurrences.find(o => o.id === newOccurrenceId);
    if (newOccurrence) {
      const normalizedValue = groupField.occurrences[0]?.normalized_value;
      if (normalizedValue) {
        setSelectedOccurrenceIds(prev => ({
          ...prev,
          [normalizedValue]: newOccurrenceId
        }));
      }
    }
  };

  return (
    <div className="space-y-6">
      {/* Grouped Tables */}
      <div className="space-y-8">
        {groupOrder.map((group) => {
            const rawGroupItems = processedGroupedItems[group];
            if (!rawGroupItems || rawGroupItems.length === 0) return null;

            const groupItems = rawGroupItems.map(field => {
               let filteredOccurrences = field.occurrences;
               if (globalFilter === "Handwritten") {
                   filteredOccurrences = field.occurrences.filter(o => o.text_type === "Human Written");
               }
               
               const normalizedValue = field.occurrences[0]?.normalized_value;
               let selectedId = normalizedValue ? selectedOccurrenceIds[normalizedValue] : undefined;
               selectedId = selectedId || field.id;
               
               if (!filteredOccurrences.some(o => o.id === selectedId) && filteredOccurrences.length > 0) {
                   selectedId = filteredOccurrences[0].id;
               }

               return { ...field, occurrences: filteredOccurrences, id: selectedId };
            }).filter(field => {
               if (field.occurrences.length === 0) return false;
               if (globalFilter === "Duplicates") {
                   return field.occurrences.length > 1;
               }
               return true;
            });

            if (groupItems.length === 0 && rawGroupItems.length > 0) {
                 // We still might want to render the header and an empty state, or just hide it. Let's show it so they can unfilter.
            } else if (groupItems.length === 0) {
                 return null;
            }

            return (
                <div key={group} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                    <div className="bg-slate-50 px-6 py-4 border-b border-slate-200 flex justify-between items-center flex-wrap gap-4">
                        <div className="flex items-center gap-4">
                            <h3 className="text-lg font-semibold text-slate-900">{group}</h3>
                            <span className="text-sm text-slate-500">{groupItems.length} items</span>
                        </div>
                        <div className="flex space-x-3 items-center">
                            {onAddItem && (
                                <button
                                    onClick={() => {
                                        setIsAdding(group);
                                        setNewItem({ raw_text: "", category: "", amount: "" });
                                    }}
                                    className="flex items-center gap-2 px-3 py-1.5 bg-white hover:bg-neutral-50 text-neutral-900 border border-neutral-200 text-xs font-medium rounded-lg transition-colors shadow-sm"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M5 12h14"></path>
                                        <path d="M12 5v14"></path>
                                    </svg>
                                    Add Item
                                </button>
                            )}
                        </div>
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
                            <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Amount / Value
                            </th>
                            <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Confidence
                            </th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Actions
                            </th>
                        </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-200">
                            {isAdding === group && (
                                <tr className="bg-blue-50/50">
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                                        <span className="text-slate-400 italic">Manual Entry</span>
                                    </td>
                                    <td className="px-6 py-4 text-sm text-slate-900">
                                        <input
                                            type="text"
                                            placeholder="Item Name / Raw Text"
                                            value={newItem.raw_text}
                                            onChange={(e) => setNewItem({ ...newItem, raw_text: e.target.value })}
                                            className="block w-full px-2 py-1.5 text-xs font-mono border border-slate-300 rounded-md shadow-sm focus:ring-[#FF5E00] focus:border-[#FF5E00]"
                                            autoFocus
                                        />
                                    </td>
                                    <td className="px-6 py-4 text-sm">
                                        <select
                                            value={newItem.category}
                                            onChange={(e) => setNewItem({ ...newItem, category: e.target.value })}
                                            className="block w-full px-3 py-2 text-sm border border-slate-300 rounded-md shadow-sm focus:ring-[#FF5E00] focus:border-[#FF5E00]"
                                        >
                                            <option value="">Select Category</option>
                                            {availableCategories.map((cat) => (
                                                <option key={cat} value={cat}>{cat}</option>
                                            ))}
                                        </select>
                                    </td>
                                    <td className="px-6 py-4 text-sm text-right font-mono">
                                        <input
                                            type="text"
                                            placeholder="Amount"
                                            value={newItem.amount}
                                            onChange={(e) => setNewItem({ ...newItem, amount: e.target.value })}
                                            className="w-24 bg-white border border-slate-300 rounded-md px-2 py-1.5 focus:ring-1 focus:ring-[#FF5E00] outline-none text-right ml-auto"
                                        />
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-center">
                                        <span className="text-slate-400 text-xs">-</span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-right">
                                        <div className="flex items-center justify-end space-x-3">
                                            <button
                                                onClick={() => handleAddNewItem(group)}
                                                disabled={isSaving || !newItem.raw_text}
                                                className="text-emerald-600 hover:text-emerald-800 font-semibold disabled:opacity-50 flex items-center gap-1"
                                            >
                                                {isSaving && isAdding === group ? (
                                                    <>
                                                        <svg className="animate-spin h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                                        </svg>
                                                        Saving...
                                                    </>
                                                ) : (
                                                    "Save"
                                                )}
                                            </button>
                                            <button
                                                onClick={() => setIsAdding(null)}
                                                className="text-slate-500 hover:text-slate-700 font-medium"
                                            >
                                                Cancel
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            )}
                        {groupItems.map((groupField) => {
                            const item = groupField.occurrences.find(o => o.id === groupField.id) || groupField.occurrences[0];
                            const hasDuplicates = groupField.occurrences.length > 1;

                            return (
                            <tr
                            key={groupField.id}
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
                                  {item.metadata?.page_number && item.metadata?.document_id && (
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
                                {editingId === item.id ? (
                                    <input
                                        type="text"
                                        value={editRawTextValue}
                                        onChange={(e) => setEditRawTextValue(e.target.value)}
                                        className="block w-full px-2 py-1.5 text-xs font-mono border border-slate-300 rounded-md shadow-sm focus:ring-[#FF5E00] focus:border-[#FF5E00]"
                                    />
                                ) : (hasDuplicates && globalFilter === "Duplicates") ? (
                                    <div className="flex flex-col gap-1">
                                        <div className="flex items-center gap-1.5 mb-1">
                                            <span className="flex items-center text-[10px] font-bold text-amber-600 uppercase bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                                                <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                                </svg>
                                                Duplicates Found ({groupField.occurrences.length})
                                            </span>
                                        </div>
                                        <select
                                            value={groupField.id}
                                            onChange={(e) => handleOccurrenceChange(groupField, e.target.value)}
                                            className="bg-amber-50/30 border border-amber-300 rounded px-2 py-1.5 text-xs font-mono text-slate-700 focus:ring-1 focus:ring-amber-500 outline-none max-w-[250px] shadow-sm"
                                        >
                                            {groupField.occurrences.map((occ) => {
                                                let displayVal = occ.raw_text || "Empty Value";
                                                // If it's a purely numeric field and raw_text is uninformative, append the amount
                                                if (occ.metadata?.amount !== undefined && occ.metadata.amount !== 0 && occ.metadata.amount !== "") {
                                                    const formattedAmount = typeof occ.metadata.amount === 'number' && occ.metadata.amount > 1000
                                                        ? `$${occ.metadata.amount.toLocaleString()}`
                                                        : String(occ.metadata.amount);
                                                    
                                                    // Only append if raw_text doesn't already contain the number
                                                    if (!displayVal.includes(String(occ.metadata.amount))) {
                                                        displayVal = `${displayVal} [Amount: ${formattedAmount}]`;
                                                    }
                                                }
                                                return (
                                                <option key={occ.id} value={occ.id}>
                                                    {displayVal}
                                                </option>
                                            )})}
                                        </select>
                                    </div>
                                ) : (
                                    <div className="max-w-xs" title={item.raw_text}>
                                    <span className="font-mono text-xs bg-slate-100 px-2 py-1.5 rounded-md text-slate-600 border border-slate-200 inline-block truncate max-w-[200px]">
                                        {item.raw_text}
                                    </span>
                                    {item.text_type === "Human Written" && (
                                        <span className="inline-flex items-center ml-2 px-1.5 py-0.5 rounded text-[10px] font-medium text-orange-600 bg-orange-50 border border-orange-200" title="Handwritten">
                                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-3 h-3 mr-1"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg>
                                            Human Written
                                        </span>
                                    )}
                                    {hasDuplicates && globalFilter !== "Duplicates" && (
                                        <span className="inline-flex items-center ml-2 px-1.5 py-0.5 rounded text-[10px] font-medium text-amber-600 bg-amber-50 border border-amber-200" title="Duplicates">
                                            <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                            </svg>
                                            Duplicates Found ({groupField.occurrences.length})
                                        </span>
                                    )}
                                    </div>
                                )}
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


                            {/* Amount / Value */}
                            <td className="px-6 py-4 text-sm text-right font-mono">
                                {editingId === item.id ? (
                                    <input
                                        type="text"
                                        value={editAmountValue}
                                        onChange={(e) => setEditAmountValue(e.target.value)}
                                        className="w-24 bg-white border border-slate-300 rounded-md px-2 py-1.5 focus:ring-1 focus:ring-[#FF5E00] outline-none text-right ml-auto"
                                        placeholder="Amount"
                                    />
                                ) : (
                                    item.metadata?.amount !== undefined ? (
                                        <span className="text-slate-900 font-semibold">
                                            {typeof item.metadata.amount === 'number' && item.metadata.amount > 1000 ?
                                                `$${item.metadata.amount.toLocaleString()}` :
                                                item.metadata.amount}
                                        </span>
                                    ) : <span className="text-slate-400 text-xs">-</span>
                                )}
                            </td>

                            {/* Confidence */}
                            <td className="px-6 py-4 whitespace-nowrap text-center">
                                <span
                                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getConfidenceColor(
                                    item.confidence
                                )}`}
                                >
                                {(item.confidence * 100).toFixed(0)}%
                                </span>
                            </td>

                            {/* Actions */}
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-right">
                                {editingId === item.id ? (
                                <div className="flex items-center justify-end space-x-3">
                                    <button
                                    onClick={() => handleSave(item.id)}
                                    disabled={isSaving}
                                    className="text-emerald-600 hover:text-emerald-800 font-semibold disabled:opacity-50 flex items-center gap-1"
                                    >
                                    {isSaving && editingId === item.id ? (
                                        <>
                                            <svg className="animate-spin h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                            </svg>
                                            Saving...
                                        </>
                                    ) : (
                                        "Save"
                                    )}
                                    </button>
                                    <button
                                    onClick={handleCancel}
                                    className="text-slate-500 hover:text-slate-700 font-medium"
                                    >
                                    Cancel
                                    </button>
                                </div>
                                ) : (
                                <div className="flex items-center justify-end space-x-4">
                                    <button
                                        onClick={() => handleEdit(item)}
                                        className="text-slate-500 hover:text-[#FF5E00] font-medium transition-colors"
                                    >
                                        Edit
                                    </button>
                                    {!item.user_verified ? (
                                        <button
                                        onClick={() => onVerify(item.id)}
                                        className="text-[#FF5E00] hover:text-blue-800 font-semibold transition-colors flex items-center"
                                        >
                                        Verify
                                        </button>
                                    ) : (
                                       <span className="inline-flex items-center text-emerald-700 font-medium text-sm">
                                            <svg className="w-4 h-4 mr-1.5" fill="currentColor" viewBox="0 0 20 20">
                                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                            </svg>
                                            Verified
                                        </span>
                                    )}
                                    {onRemoveItem && (
                                        <button
                                            onClick={() => handleDelete(item.id)}
                                            className="p-1 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                                            title="Delete"
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <path d="M3 6h18"></path>
                                                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                                                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                                            </svg>
                                        </button>
                                    )}
                                </div>
                                )}
                            </td>
                            </tr>
                            );
                        })}
                        </tbody>
                    </table>
                    </div>
                </div>
            );
        })}
      </div>

      {/* Legend */}
      {/* <div className="bg-white rounded-lg p-4 border border-slate-200">
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
      </div> */}
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
