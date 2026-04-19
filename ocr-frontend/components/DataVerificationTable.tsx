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
  onVerifyAll: _onVerifyAll,
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
    id: string;
    occurrences: NormalizedDataItem[];
    category_group: string;
    isDuplicateEdited?: boolean;
  }

  const groupedItems = items.reduce((acc, item) => {
    const group = item.category_group || "Other";
    if (!acc[group]) acc[group] = [];
    const isDeduplicatedField = !!item.normalized_value &&
      item.normalized_value !== "Uncategorized" && item.normalized_value !== "Other";
    if (isDeduplicatedField) {
      acc[group].findIndex((e) => e.normalized_value === item.normalized_value);
    }
    acc[group].push(item);
    return acc;
  }, {} as Record<string, NormalizedDataItem[]>);

  const processedGroupedItems = Object.keys(groupedItems).reduce((acc, group) => {
    const itemsInGroup = groupedItems[group];
    const processedItems: GroupedDataField[] = [];
    const dedupMap = new Map<string, GroupedDataField>();

    itemsInGroup.forEach((item) => {
      const isDeduplicatedField = !!item.normalized_value &&
        item.normalized_value !== "Uncategorized" && item.normalized_value !== "Other";

      if (isDeduplicatedField) {
        if (!dedupMap.has(item.normalized_value)) {
          const newGroup: GroupedDataField = { id: item.id, occurrences: [item], category_group: group };
          dedupMap.set(item.normalized_value, newGroup);
          processedItems.push(newGroup);
        } else {
          const existing = dedupMap.get(item.normalized_value)!;
          existing.occurrences.push(item);
          const currentSelected = existing.occurrences.find((o) => o.id === existing.id);
          if (item.user_verified && (!currentSelected || !currentSelected.user_verified)) existing.id = item.id;
          else if (!currentSelected?.user_verified && item.confidence > (currentSelected?.confidence || 0)) existing.id = item.id;
        }
      } else {
        processedItems.push({ id: item.id, occurrences: [item], category_group: group });
      }
    });

    acc[group] = processedItems;
    return acc;
  }, {} as Record<string, GroupedDataField[]>);

  const groupOrder: CategoryGroup[] = ["Revenue", "Operating Expense", "Capital Expenditure", "Tax & Insurance", "Debt", "Property Info", "Other"];

  const handleSave = async (itemId: string) => {
    const originalItem = items.find((i) => i.id === itemId);
    if (originalItem) {
      if (onUpdateItem) {
        setIsSaving(true);
        try {
          let finalAmount: number | string | undefined;
          if (editAmountValue !== "") {
            const clean = String(editAmountValue).replace(/[$,]/g, "").trim();
            const num = Number(clean);
            finalAmount = clean !== "" && !isNaN(num) ? num : editAmountValue;
          }
          await onUpdateItem({ ...originalItem, raw_text: editRawTextValue, user_correction: editValue, metadata: { ...(originalItem.metadata || {}), amount: finalAmount } });
        } finally { setIsSaving(false); }
      } else {
        const correctionChanged = editValue !== originalItem.normalized_value;
        const rawTextChanged = editRawTextValue !== originalItem.raw_text;
        if (correctionChanged || rawTextChanged) onVerify(itemId, correctionChanged ? editValue : undefined, rawTextChanged ? editRawTextValue : undefined);
        else onVerify(itemId);
      }
    }
    setEditingId(null); setEditValue(""); setEditRawTextValue(""); setEditAmountValue("");
  };

  const handleDelete = async (itemId: string) => {
    if (onRemoveItem && confirm("Remove this item?")) {
      setIsSaving(true);
      try { await onRemoveItem(itemId); } finally { setIsSaving(false); }
    }
  };

  const handleAddNewItem = async (group: string) => {
    if (onAddItem && newItem.raw_text) {
      setIsSaving(true);
      try {
        let finalAmount: number | string | undefined;
        if (newItem.amount !== "") {
          const clean = String(newItem.amount).replace(/[$,]/g, "").trim();
          const num = Number(clean);
          finalAmount = clean !== "" && !isNaN(num) ? num : newItem.amount;
        }
        await onAddItem({ raw_text: newItem.raw_text, normalized_value: newItem.category || "Uncategorized", category_group: group as CategoryGroup, confidence: 1.0, user_verified: true, source_document: "Manual Entry", metadata: { amount: finalAmount, is_manual: true } });
        setIsAdding(null); setNewItem({ raw_text: "", category: "", amount: "" });
      } finally { setIsSaving(false); }
    }
  };

  const handleCancel = () => { setEditingId(null); setEditValue(""); setEditRawTextValue(""); setEditAmountValue(""); };

  const getConfidenceBadge = (confidence: number) => {
    const pct = (confidence * 100).toFixed(0) + "%";
    if (confidence >= 0.95) return <span className="badge-high">{pct}</span>;
    if (confidence >= 0.85) return <span className="badge-medium">{pct}</span>;
    return <span className="badge-low">{pct}</span>;
  };

  const getDocumentId = (item: NormalizedDataItem): string | undefined => {
    if (!documents) return undefined;
    const allDocs = Object.values(documents).flat();
    return allDocs.find((d) => d.filename === item.source_document)?.document_id;
  };

  const handleOccurrenceChange = (groupField: GroupedDataField, newOccurrenceId: string) => {
    const normalizedValue = groupField.occurrences[0]?.normalized_value;
    if (normalizedValue) setSelectedOccurrenceIds((prev) => ({ ...prev, [normalizedValue]: newOccurrenceId }));
  };

  const inputCls = "block w-full px-2 py-1.5 text-xs font-mono border border-[#E2E8F0] bg-[#F8FAFC] rounded-md text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:ring-1 focus:ring-[#F97316]/40 focus:border-[#F97316]/50 transition-all";
  const selectCls = "block w-full px-3 py-2 text-xs border border-[#E2E8F0] bg-[#F8FAFC] rounded-md text-[#0F172A] focus:outline-none focus:ring-1 focus:ring-[#F97316]/40 focus:border-[#F97316]/50 transition-all";

  return (
    <div className="space-y-6">
      <div className="space-y-8">
        {groupOrder.map((group) => {
          const rawGroupItems = processedGroupedItems[group];
          if (!rawGroupItems || rawGroupItems.length === 0) return null;

          const groupItems = rawGroupItems.map((field) => {
            let filteredOccurrences = field.occurrences;
            if (globalFilter === "Handwritten") filteredOccurrences = field.occurrences.filter((o) => o.text_type === "Human Written");
            const normalizedValue = field.occurrences[0]?.normalized_value;
            let selectedId = normalizedValue ? selectedOccurrenceIds[normalizedValue] : undefined;
            selectedId = selectedId || field.id;
            if (!filteredOccurrences.some((o) => o.id === selectedId) && filteredOccurrences.length > 0) selectedId = filteredOccurrences[0].id;
            const highestConfItem = field.occurrences.reduce((p, c) => (p.confidence > c.confidence ? p : c), field.occurrences[0]);
            const selectedItem = field.occurrences.find((o) => o.id === selectedId) || field.occurrences[0];
            const isDuplicateEdited = selectedItem.user_verified && selectedItem.id !== highestConfItem.id;
            return { ...field, occurrences: filteredOccurrences, id: selectedId, isDuplicateEdited };
          }).filter((field) => {
            if (field.occurrences.length === 0) return false;
            if (globalFilter === "Duplicates") return field.occurrences.length > 1;
            return true;
          });

          if (groupItems.length === 0) return null;

          return (
            <div key={group} className="bg-white rounded-xl border border-[#E2E8F0] overflow-hidden shadow-[var(--shadow-card)]">
              {/* Group header */}
              <div className="bg-[#F1F5F9] px-6 py-4 border-b border-[#E2E8F0] flex justify-between items-center flex-wrap gap-4">
                <div className="flex items-center gap-3">
                  <h3 className="text-sm font-semibold text-[#0F172A]">{group}</h3>
                  <span className="text-[10px] text-[#64748B] bg-white border border-[#E2E8F0] px-2 py-0.5 rounded-full">{groupItems.length} items</span>
                </div>
                {onAddItem && (
                  <button
                    onClick={() => { setIsAdding(group); setNewItem({ raw_text: "", category: "", amount: "" }); }}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-[#F8FAFC] text-[#475569] hover:text-[#0F172A] border border-[#E2E8F0] hover:border-[#CBD5E1] text-xs font-medium rounded-lg transition-colors"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 12h14" /><path d="M12 5v14" />
                    </svg>
                    Add Item
                  </button>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-[#F1F5F9]">
                  <thead>
                    <tr className="bg-[#F1F5F9]">
                      {["Source Document", "Raw Text", "Mapped Category", "Amount / Value", "Confidence", "Actions"].map((h, i) => (
                        <th key={h} className={`px-6 py-3 text-[10px] font-semibold text-[#64748B] uppercase tracking-widest ${i >= 3 ? (i === 3 ? "text-right" : i === 4 ? "text-center" : "text-right") : "text-left"}`}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#F1F5F9]">
                    {isAdding === group && (
                      <tr className="bg-[rgba(59,130,246,0.04)]">
                        <td className="px-6 py-4 text-xs text-[#64748B] italic">Manual Entry</td>
                        <td className="px-6 py-4">
                          <input type="text" placeholder="Item Name / Raw Text" value={newItem.raw_text} onChange={(e) => setNewItem({ ...newItem, raw_text: e.target.value })} className={inputCls} autoFocus />
                        </td>
                        <td className="px-6 py-4">
                          <select value={newItem.category} onChange={(e) => setNewItem({ ...newItem, category: e.target.value })} className={selectCls}>
                            <option value="">Select Category</option>
                            {availableCategories.map((cat) => <option key={cat} value={cat}>{cat}</option>)}
                          </select>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <input type="text" placeholder="Amount" value={newItem.amount} onChange={(e) => setNewItem({ ...newItem, amount: e.target.value })} className="w-24 bg-[#F8FAFC] border border-[#E2E8F0] rounded-md px-2 py-1.5 text-xs text-right font-mono text-[#0F172A] focus:outline-none focus:ring-1 focus:ring-[#F97316]/40 ml-auto" />
                        </td>
                        <td className="px-6 py-4 text-center"><span className="text-[#64748B] text-xs">—</span></td>
                        <td className="px-6 py-4 text-right">
                          <div className="flex items-center justify-end gap-3">
                            <button onClick={() => handleAddNewItem(group)} disabled={isSaving || !newItem.raw_text} className="text-[#22C55E] hover:text-[#16A34A] font-semibold text-xs disabled:opacity-40">
                              {isSaving && isAdding === group ? "Saving..." : "Save"}
                            </button>
                            <button onClick={() => setIsAdding(null)} className="text-[#64748B] hover:text-[#475569] font-medium text-xs">Cancel</button>
                          </div>
                        </td>
                      </tr>
                    )}

                    {groupItems.map((groupField) => {
                      const item = groupField.occurrences.find((o) => o.id === groupField.id) || groupField.occurrences[0];
                      const hasDuplicates = groupField.occurrences.length > 1;
                      const isEdited = !!item.user_correction || groupField.isDuplicateEdited;

                      return (
                        <tr key={groupField.id} className={`transition-colors duration-150 ${
                          isEdited ? "bg-[rgba(249,115,22,0.05)]" :
                          item.user_verified ? "bg-[rgba(34,197,94,0.03)]" : "hover:bg-[#F1F5F9]"
                        }`}>

                          {/* Source Document */}
                          <td className="px-6 py-4 text-xs text-[#475569]">
                            <div className="flex flex-col items-start gap-1">
                              {isEdited && (
                                <span className="text-[9px] uppercase font-bold text-[#F97316] px-1.5 py-0.5 bg-[rgba(249,115,22,0.1)] rounded border border-[rgba(249,115,22,0.2)] mb-1">
                                  Edited
                                </span>
                              )}
                              <div className="flex items-center gap-2 w-full">
                                <div className="flex items-center flex-1 min-w-0" title={item.source_document}>
                                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2 text-[#64748B] shrink-0">
                                    <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" strokeLinecap="round" strokeLinejoin="round" />
                                  </svg>
                                  <span className="truncate max-w-[110px]">{item.source_document}</span>
                                </div>
                                {item.metadata?.page_number && item.metadata?.document_id && (
                                  <button onClick={() => setViewingItem(item)} className="p-1 text-[#64748B] hover:text-[#F97316] hover:bg-[rgba(249,115,22,0.08)] rounded transition-colors shrink-0" title="View Source Document">
                                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" />
                                    </svg>
                                  </button>
                                )}
                              </div>
                            </div>
                          </td>

                          {/* Raw Text */}
                          <td className="px-6 py-4 text-xs">
                            {editingId === item.id ? (
                              <input type="text" value={editRawTextValue} onChange={(e) => setEditRawTextValue(e.target.value)} className={inputCls} />
                            ) : (hasDuplicates && globalFilter === "Duplicates") ? (
                              <div className="flex flex-col gap-1.5">
                                <span className="tag-duplicate">
                                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-1">
                                    <path d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                  </svg>
                                  Duplicates Found ({groupField.occurrences.length})
                                </span>
                                <select value={groupField.id} onChange={(e) => handleOccurrenceChange(groupField, e.target.value)}
                                  className="bg-[rgba(245,158,11,0.06)] border border-[rgba(245,158,11,0.2)] rounded px-2 py-1.5 text-xs font-mono text-[#0F172A] focus:ring-1 focus:ring-[#F59E0B]/40 outline-none max-w-[250px]">
                                  {groupField.occurrences.map((occ) => {
                                    let display = occ.raw_text || "Empty Value";
                                    if (occ.metadata?.amount !== undefined && occ.metadata.amount !== 0 && occ.metadata.amount !== "") {
                                      const isYB = occ.normalized_value === "Year Built";
                                      const isNC = isYB || ["Total Units", "Rentable Square Feet", "Occupancy Rate"].includes(occ.normalized_value || "");
                                      const fa = typeof occ.metadata.amount === "number" && occ.metadata.amount > 1000 && !isNC ? `$${occ.metadata.amount.toLocaleString()}` : String(occ.metadata.amount);
                                      if (!display.includes(String(occ.metadata.amount))) display = `${display} [Amount: ${fa}]`;
                                    }
                                    return <option key={occ.id} value={occ.id}>{display}</option>;
                                  })}
                                </select>
                              </div>
                            ) : (
                              <div className="max-w-xs" title={item.raw_text}>
                                <span className="font-mono text-[10px] bg-[#F8FAFC] px-2 py-1.5 rounded-md text-[#475569] border border-[#E2E8F0] inline-block truncate max-w-[200px]">
                                  {item.raw_text}
                                </span>
                                {item.text_type === "Human Written" && (
                                  <span className="tag-handwritten ml-2">
                                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-1"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" /></svg>
                                    Human Written
                                  </span>
                                )}
                                {hasDuplicates && globalFilter !== "Duplicates" && (
                                  <span className="tag-duplicate ml-2">
                                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-1"><path d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                                    Duplicates ({groupField.occurrences.length})
                                  </span>
                                )}
                              </div>
                            )}
                          </td>

                          {/* Mapped Category */}
                          <td className="px-6 py-4 text-xs">
                            {editingId === item.id ? (
                              <select value={editValue} onChange={(e) => setEditValue(e.target.value)} className={selectCls} autoFocus>
                                {availableCategories.map((cat) => <option key={cat} value={cat}>{cat}</option>)}
                              </select>
                            ) : (
                              <span className="font-medium text-[#0F172A]">{item.user_correction || item.normalized_value}</span>
                            )}
                          </td>

                          {/* Amount */}
                          <td className="px-6 py-4 text-right font-mono text-xs">
                            {editingId === item.id ? (
                              <input type="text" value={editAmountValue} onChange={(e) => setEditAmountValue(e.target.value)} placeholder="Amount"
                                className="w-24 bg-[#F8FAFC] border border-[#E2E8F0] rounded-md px-2 py-1.5 text-xs text-right font-mono text-[#0F172A] focus:outline-none focus:ring-1 focus:ring-[#F97316]/40 ml-auto" />
                            ) : item.metadata?.amount !== undefined ? (
                              <span className="text-[#0F172A] font-semibold">
                                {(() => {
                                  const isYB = item.normalized_value === "Year Built";
                                  const isNC = isYB || ["Total Units", "Rentable Square Feet", "Occupancy Rate"].includes(item.normalized_value || "");
                                  if (typeof item.metadata.amount === "number" && item.metadata.amount > 1000) {
                                    if (isYB) return String(item.metadata.amount);
                                    if (isNC) return item.metadata.amount.toLocaleString();
                                    return `$${item.metadata.amount.toLocaleString()}`;
                                  }
                                  return item.metadata.amount;
                                })()}
                              </span>
                            ) : <span className="text-[#64748B]">—</span>}
                          </td>

                          {/* Confidence */}
                          <td className="px-6 py-4 text-center">
                            {getConfidenceBadge(item.confidence)}
                          </td>

                          {/* Actions */}
                          <td className="px-6 py-4 text-right">
                            {editingId === item.id ? (
                              <div className="flex items-center justify-end gap-3">
                                <button onClick={() => handleSave(item.id)} disabled={isSaving} className="text-[#22C55E] hover:text-[#16A34A] font-semibold text-xs disabled:opacity-40">
                                  {isSaving && editingId === item.id ? "Saving..." : "Save"}
                                </button>
                                <button onClick={handleCancel} className="text-[#64748B] hover:text-[#475569] font-medium text-xs">Cancel</button>
                              </div>
                            ) : (
                              <div className="flex items-center justify-end gap-3">
                                <button onClick={() => handleEdit(item)} className="text-[#64748B] hover:text-[#F97316] font-medium text-xs transition-colors">Edit</button>
                                {!item.user_verified ? (
                                  <button onClick={() => onVerify(item.id)} className="text-[#F97316] hover:text-[#EA6C0A] font-semibold text-xs transition-colors">Verify</button>
                                ) : (
                                  <span className="inline-flex items-center text-[#22C55E] font-medium text-xs">
                                    <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" className="mr-1">
                                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                    </svg>
                                    Verified
                                  </span>
                                )}
                                {onRemoveItem && (
                                  <button onClick={() => handleDelete(item.id)} className="p-1 text-[#64748B] hover:text-[#EF4444] hover:bg-[rgba(239,68,68,0.08)] rounded transition-colors" title="Delete">
                                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                      <path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
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
