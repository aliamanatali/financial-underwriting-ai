"use client";

import { useState, useEffect, useMemo } from "react";
import { NormalizedDataItem, CategoryGroup, DocumentMetadata } from "@/lib/types";
import dynamic from "next/dynamic";

const SourceDocumentViewer = dynamic(() => import("@/components/SourceDocumentViewer"), {
  ssr: false,
});

interface ExpenseItem {
  id: string;
  name: string;
  amount: number;
  category: string;
  isNew?: boolean;
  source_document?: string;
  metadata?: any;
}

export type GlobalFilter = "All" | "Handwritten" | "Duplicates";

interface ExpensesVerificationWidgetProps {
  items: NormalizedDataItem[];
  availableCategories: string[];
  globalFilter?: GlobalFilter;
  onUpdateExpenses: (updatedItems: NormalizedDataItem[]) => Promise<void>;
  onAddExpense: (newItem: Partial<NormalizedDataItem>) => Promise<void>;
  onRemoveExpense: (itemId: string) => Promise<void>;
  onRegenerate: () => Promise<void>;
  documents?: Record<string, DocumentMetadata[]> | DocumentMetadata[];
  packageId?: string;
}

interface GroupedExpense {
  id: string;
  name: string;
  category: string;
  amount: number;
  occurrences: NormalizedDataItem[];
  selectedOccurrenceId: string;
  originalSelectedId: string;
}

export default function ExpensesVerificationWidget({
  items = [],
  availableCategories = [],
  globalFilter = "All",
  onUpdateExpenses,
  onAddExpense,
  onRemoveExpense,
  onRegenerate,
  documents,
  packageId,
}: ExpensesVerificationWidgetProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [viewingItem, setViewingItem] = useState<NormalizedDataItem | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Partial<ExpenseItem>>({});
  const [isSaving, setIsSaving] = useState(false);

  const [newItem, setNewItem] = useState<Partial<ExpenseItem>>({
  name: "",
  amount: 0,
  category: "Other Operating Expenses",
});

const getCategoryGroup = (category: string): CategoryGroup => {
  const revenueCategories = ["Gross Potential Rent", "Other Income", "Reimbursements"];
  const taxInsuranceCategories = ["Real Estate Taxes", "Insurance"];
  
  if (revenueCategories.includes(category)) return "Revenue" as CategoryGroup;
  if (taxInsuranceCategories.includes(category)) return "Tax & Insurance" as CategoryGroup;
  return "Operating Expense" as CategoryGroup;
};

  // Filter and deduplicate expenses
  const expenseItems = useMemo(() => {
    try {
      // 1. Filter for expenses and text type
      let list = items.filter(
        (item) =>
          item && (item.category_group === "Operating Expense" ||
          item.category_group === "Tax & Insurance") &&
          (globalFilter === "All" || globalFilter === "Duplicates" || (item.text_type === "Human Written"))
      );

      // 2. Intelligent Deduplication
      const cleanedList: NormalizedDataItem[] = [];
      const seenAmounts = new Map<number, NormalizedDataItem>();

      list.forEach(item => {
        const amount = item.metadata?.amount || 0;
        const text = (item.raw_text || "").trim();
        const isJustNumber = /^\$?[0-9,.]+(?:\.00)?$/.test(text.replace(/\s/g, ''));
        
        if (!isJustNumber && text.length > 1) {
            cleanedList.push(item);
            if (amount > 0) seenAmounts.set(amount, item);
        }
      });

      list.forEach(item => {
        const amount = item.metadata?.amount || 0;
        const text = (item.raw_text || "").trim();
        const isJustNumber = /^\$?[0-9,.]+(?:\.00)?$/.test(text.replace(/\s/g, ''));
        
        if (isJustNumber) {
            if (!seenAmounts.has(amount)) {
                cleanedList.push(item);
                seenAmounts.set(amount, item);
            }
        }
      });

      return cleanedList;
    } catch (e) {
      console.error("Error filtering expenses:", e);
      return [];
    }
  }, [items, globalFilter]);

  const [localExpenses, setLocalExpenses] = useState<GroupedExpense[]>([]);

  useEffect(() => {
    // Group expenses by category and name
    const grouped = new Map<string, GroupedExpense>();
    
    expenseItems.forEach(item => {
      const name = item.raw_text?.trim() || "Unnamed Expense";
      const category = item.user_correction || item.normalized_value || "Uncategorized";
      // Create a composite key for grouping
      const key = `${category.toLowerCase()}-${name.toLowerCase()}`;
      
      if (!grouped.has(key)) {
        grouped.set(key, {
          id: item.id, // Use the first item's ID as the main ID for the row
          name,
          category,
          amount: typeof item.metadata?.amount === 'number' ? item.metadata.amount : 0,
          occurrences: [item],
          selectedOccurrenceId: item.id,
          originalSelectedId: item.id
        });
      } else {
        const existing = grouped.get(key)!;
        existing.occurrences.push(item);
        
        // If this item is verified or has a higher amount and current isn't verified, make it selected
        const currentSelected = existing.occurrences.find(o => o.id === existing.selectedOccurrenceId);
        if (item.user_verified && (!currentSelected || !currentSelected.user_verified)) {
            existing.selectedOccurrenceId = item.id;
            existing.originalSelectedId = item.id;
            existing.amount = typeof item.metadata?.amount === 'number' ? item.metadata.amount : 0;
            existing.id = item.id;
        } else if (!currentSelected?.user_verified && typeof item.metadata?.amount === 'number' && typeof currentSelected?.metadata?.amount === 'number' && item.metadata.amount > currentSelected.metadata.amount) {
            // Optional: pick highest if neither verified
            existing.selectedOccurrenceId = item.id;
            existing.originalSelectedId = item.id;
            existing.amount = item.metadata.amount;
            existing.id = item.id;
        }
      }
    });
    
    // Sort by category then name
    const sortedExpenses = Array.from(grouped.values()).sort((a, b) => {
      if (a.category !== b.category) {
        return a.category.localeCompare(b.category);
      }
      return a.name.localeCompare(b.name);
    });

    // Apply duplicates filter if selected
    const filteredExpenses = globalFilter === "Duplicates"
      ? sortedExpenses.filter(e => e.occurrences.length > 1)
      : sortedExpenses;

    setLocalExpenses(filteredExpenses);
  }, [expenseItems, globalFilter]);

  const startEditing = (expense: GroupedExpense) => {
    setEditingId(expense.id);
    setEditValues({
      id: expense.id,
      name: expense.name,
      amount: expense.amount,
      category: expense.category,
    });
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditValues({});
  };

  const handleSaveEdit = async (id: string, skipLoading: boolean = false) => {
    if (!skipLoading) setIsSaving(true);
    try {
        const expenseGroup = localExpenses.find(e => e.id === id);
        if (!expenseGroup) return;

        const originalItem = items.find((i) => i.id === expenseGroup.selectedOccurrenceId);
        
        if (originalItem && editValues) {
            const newAmount = typeof editValues.amount === 'number' ? editValues.amount : 0;
            
            const updatedItem = {
                ...originalItem,
                raw_text: editValues.name || originalItem.raw_text,
                user_correction: editValues.category,
                category_group: editValues.category ? getCategoryGroup(editValues.category) : originalItem.category_group,
                user_verified: true,
                metadata: {
                    ...(originalItem.metadata || {}),
                    amount: newAmount,
                }
            } as NormalizedDataItem;
            
            // Note: If they changed category or name, we should probably update ALL occurrences in that group
            // but for now, updating the selected one is safest and marks it verified.
            await onUpdateExpenses([updatedItem]);
        }
        setEditingId(null);
        setEditValues({});
    } finally {
        if (!skipLoading) setIsSaving(false);
    }
  };

  const handleOccurrenceChange = (expenseId: string, occurrenceId: string) => {
    setLocalExpenses(prev => prev.map(exp => {
      if (exp.id === expenseId) {
        return {
          ...exp,
          selectedOccurrenceId: occurrenceId
        };
      }
      return exp;
    }));
  };

  const handleVerifyOccurrence = async (expenseId: string) => {
    const expenseGroup = localExpenses.find(e => e.id === expenseId);
    if (!expenseGroup) return;

    const selectedOccurrence = expenseGroup.occurrences.find(o => o.id === expenseGroup.selectedOccurrenceId);
    if (!selectedOccurrence) return;

    setIsSaving(true);
    try {
        const updatedItem = {
            ...selectedOccurrence,
            user_verified: true
        } as NormalizedDataItem;

        await onUpdateExpenses([updatedItem]);
    } finally {
        setIsSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm("Are you sure you want to remove this expense?")) {
        await onRemoveExpense(id);
    }
  };

  const handleAddNewExpense = async () => {
    if (!newItem.name) return;
    setIsSaving(true);
    try {
        const category = newItem.category || "Other Operating Expenses";
        const newNormalizedItem: Partial<NormalizedDataItem> = {
            raw_text: newItem.name,
            normalized_value: category,
            field_type: "expense_category",
            category_group: getCategoryGroup(category),
            confidence: 1.0,
            user_verified: true,
            source_document: "Manual Entry",
            metadata: {
                amount: newItem.amount || 0,
                is_manual: true,
            },
        };

        await onAddExpense(newNormalizedItem);
        setIsAdding(false);
        setNewItem({ name: "", amount: 0, category: "Other Operating Expenses" });
    } finally {
        setIsSaving(false);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mb-8">
      <div className="bg-slate-50 px-6 py-4 border-b border-slate-200 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex items-center gap-4">
          <h3 className="text-lg font-semibold text-slate-900">Expenses Verification</h3>
          <span className="text-sm text-slate-500">{localExpenses.length} items</span>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
            <button
                onClick={() => setIsAdding(true)}
                className="flex items-center gap-2 px-3 py-1.5 bg-white hover:bg-neutral-50 text-neutral-900 border border-neutral-200 text-xs font-medium rounded-lg transition-colors shadow-sm"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12h14"></path>
                    <path d="M12 5v14"></path>
                </svg>
                Add Expense
            </button>
            {/* <button
                onClick={async () => {
                    if (isSaving) return;
                    setIsSaving(true);
                    try {
                        if (editingId) {
                            await handleSaveEdit(editingId, true);
                        }
                        await onRegenerate();
                    } finally {
                        setIsSaving(false);
                    }
                }}
                disabled={isSaving}
                className="flex items-center gap-2 px-3 py-1.5 bg-neutral-900 hover:bg-neutral-800 text-white text-xs font-medium rounded-lg transition-colors shadow-sm disabled:opacity-50"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 12a9 9 0 1 1-2.5-6.2"></path>
                    <path d="M21 6v6h-6"></path>
                </svg>
                Save & Update Report
            </button> */}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-white">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Source Document</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Raw Text</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Mapped Category</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Amount</th>
              <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Confidence</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider w-24">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-slate-200">
            {localExpenses.map((expense) => {
              const selectedItem = expense.occurrences.find(o => o.id === expense.selectedOccurrenceId) || expense.occurrences[0];
              const highestConfidenceItem = expense.occurrences.reduce((prev, current) =>
                  (prev.confidence > current.confidence) ? prev : current
              , expense.occurrences[0]);
              const isDuplicateEdited = selectedItem.user_verified && selectedItem.id !== highestConfidenceItem.id;
              const isEdited = !!selectedItem?.user_correction || isDuplicateEdited;
              
              return (
              <tr key={expense.id} className={`${isEdited ? 'bg-orange-50' : selectedItem?.user_verified ? 'bg-emerald-50/30' : 'hover:bg-slate-50'} transition-colors duration-150`}>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                  <div className="flex flex-col items-start gap-1">
                    {isEdited && (
                        <span className="text-[10px] uppercase font-bold text-[#FF5E00] px-1.5 py-0.5 bg-orange-100/50 rounded border border-orange-200 mb-1">
                            Edited
                        </span>
                    )}
                    <div className="flex items-center gap-2 w-full">
                      <div className="flex items-center flex-1 min-w-0" title={selectedItem?.source_document}>
                          <svg className="w-4 h-4 mr-2 text-slate-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          <span className="truncate max-w-[120px]">{selectedItem?.source_document || 'Manual Entry'}</span>
                      </div>
                      {selectedItem?.metadata?.page_number && (
                        <button
                          onClick={() => setViewingItem(selectedItem)}
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
                  </div>
                </td>
                <td className="px-6 py-4 text-sm text-slate-900">
                  {editingId === expense.id ? (
                    <input
                        type="text"
                        value={editValues.name}
                        onChange={(e) => setEditValues({ ...editValues, name: e.target.value })}
                        className="block w-full px-2 py-1.5 text-xs font-mono border border-slate-300 rounded-md shadow-sm focus:ring-[#FF5E00] focus:border-[#FF5E00]"
                    />
                  ) : (
                    <div className="max-w-xs" title={expense.name}>
                        <span className="font-mono text-xs bg-slate-100 px-2 py-1.5 rounded-md text-slate-600 border border-slate-200 inline-block truncate max-w-[200px]">
                            {expense.name}
                        </span>
                        {selectedItem?.text_type === "Human Written" && (
                            <span className="inline-flex items-center ml-2 px-1.5 py-0.5 rounded text-[10px] font-medium text-orange-600 bg-orange-50 border border-orange-200" title="Handwritten">
                                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-3 h-3 mr-1"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg>
                                Human Written
                            </span>
                        )}
                    </div>
                  )}
                </td>
                <td className="px-6 py-4 text-sm">
                  {editingId === expense.id ? (
                    <select
                        value={editValues.category}
                        onChange={(e) => setEditValues({ ...editValues, category: e.target.value })}
                        className="block w-full px-3 py-2 text-sm border-slate-300 rounded-md shadow-sm focus:ring-[#FF5E00] focus:border-[#FF5E00]"
                    >
                        {availableCategories.map((cat) => (
                            <option key={cat} value={cat}>{cat}</option>
                        ))}
                    </select>
                  ) : (
                    <div className="flex flex-col">
                        <span className="font-medium text-slate-900">
                        {expense.category}
                        </span>
                    </div>
                  )}
                </td>
                <td className="px-6 py-4 text-sm text-right font-mono">
                  {editingId === expense.id ? (
                    <div className="flex items-center justify-end">
                        <span className="text-slate-400 mr-1">$</span>
                        <input
                            type="text"
                            value={editValues.amount}
                            onChange={(e) => {
                                const val = e.target.value.replace(/[^0-9.]/g, '');
                                setEditValues({ ...editValues, amount: parseFloat(val) || 0 });
                            }}
                            className="w-24 bg-white border border-slate-300 rounded-md px-2 py-1.5 focus:ring-1 focus:ring-[#FF5E00] outline-none text-right"
                        />
                    </div>
                  ) : (expense.occurrences.length > 1 && globalFilter === "Duplicates") ? (
                    <div className="flex flex-col items-end gap-1">
                        <span className="flex items-center text-[10px] font-bold text-amber-600 uppercase bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200 mb-1">
                            <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                            </svg>
                            Duplicates
                        </span>
                        <select
                            value={expense.selectedOccurrenceId}
                            onChange={(e) => handleOccurrenceChange(expense.id, e.target.value)}
                            className="bg-amber-50/30 border border-amber-300 rounded px-2 py-1.5 text-right font-semibold text-slate-800 text-sm focus:ring-1 focus:ring-amber-500 outline-none shadow-sm"
                        >
                            {expense.occurrences.map((occ) => (
                                <option key={occ.id} value={occ.id}>
                                    ${typeof occ.metadata?.amount === 'number' ? occ.metadata.amount.toLocaleString() : 0}
                                </option>
                            ))}
                        </select>
                    </div>
                  ) : (
                    <div className="flex flex-col items-end gap-1">
                        <span className="text-slate-900 font-semibold">${expense.amount.toLocaleString()}</span>
                        {expense.occurrences.length > 1 && globalFilter !== "Duplicates" && (
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium text-amber-600 bg-amber-50 border border-amber-200">
                                <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                </svg>
                                Duplicates Found ({expense.occurrences.length})
                            </span>
                        )}
                    </div>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-center">
                    {selectedItem?.confidence !== undefined ? (
                        <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            selectedItem.confidence >= 0.95 ? "text-emerald-700 bg-emerald-50 border border-emerald-100" :
                            selectedItem.confidence >= 0.85 ? "text-amber-700 bg-amber-50 border border-amber-100" :
                            "text-rose-700 bg-rose-50 border border-rose-100"
                        }`}
                        >
                        {(selectedItem.confidence * 100).toFixed(0)}%
                        </span>
                    ) : (
                        <span className="text-slate-400 text-xs">-</span>
                    )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-right">
                  {editingId === expense.id ? (
                    <div className="flex items-center justify-end space-x-3">
                        <button
                            onClick={() => handleSaveEdit(expense.id)}
                            disabled={isSaving}
                            className="text-emerald-600 hover:text-emerald-800 font-semibold disabled:opacity-50 flex items-center gap-1"
                        >
                            {isSaving && editingId === expense.id ? (
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
                            onClick={cancelEditing}
                            className="text-slate-500 hover:text-slate-700 font-medium"
                        >
                            Cancel
                        </button>
                    </div>
                  ) : (
                    <div className="flex items-center justify-end space-x-4">
                        <button
                            onClick={() => startEditing(expense)}
                            className="text-slate-500 hover:text-[#FF5E00] font-medium transition-colors"
                        >
                            Edit
                        </button>
                        {!selectedItem?.user_verified ? (
                            <button
                            onClick={() => handleVerifyOccurrence(expense.id)}
                            className="text-[#FF5E00] hover:text-orange-800 font-semibold transition-colors flex items-center"
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
                        <button
                            onClick={() => handleDelete(expense.id)}
                            className="p-1 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                            title="Delete"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M3 6h18"></path>
                                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                            </svg>
                        </button>
                    </div>
                  )}
                </td>
              </tr>
            )})}

            {isAdding && (
              <tr className="bg-blue-50/50">
                <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                  <span className="text-slate-400 italic">Manual Entry</span>
                </td>
                <td className="px-6 py-4 text-sm">
                  <input
                    type="text"
                    placeholder="New Expense Name"
                    value={newItem.name}
                    onChange={(e) => setNewItem({ ...newItem, name: e.target.value })}
                    className="block w-full px-2 py-1.5 text-xs font-mono border border-slate-300 rounded-md shadow-sm focus:ring-[#FF5E00] focus:border-[#FF5E00]"
                    autoFocus
                  />
                </td>
                <td className="px-6 py-4 text-sm">
                  <select
                    value={newItem.category}
                    onChange={(e) => setNewItem({ ...newItem, category: e.target.value })}
                    className="block w-full px-3 py-2 text-sm border-slate-300 rounded-md shadow-sm focus:ring-[#FF5E00] focus:border-[#FF5E00]"
                  >
                    {availableCategories.map((cat) => (
                      <option key={cat} value={cat}>{cat}</option>
                    ))}
                  </select>
                </td>
                <td className="px-6 py-4 text-sm text-right">
                    <div className="flex items-center justify-end font-mono">
                      <span className="text-slate-400 mr-1">$</span>
                      <input
                        type="text"
                        placeholder="0"
                        value={newItem.amount}
                        onChange={(e) => setNewItem({ ...newItem, amount: parseFloat(e.target.value) || 0 })}
                        className="w-24 bg-white border border-slate-300 rounded-md px-2 py-1.5 focus:ring-1 focus:ring-[#FF5E00] outline-none text-right"
                      />
                    </div>
                </td>
                <td className="px-6 py-4 text-center">
                    <span className="text-slate-400 text-xs">-</span>
                </td>
                <td className="px-6 py-4 text-sm text-right">
                    <div className="flex items-center justify-end space-x-3">
                      <button
                        onClick={handleAddNewExpense}
                        disabled={isSaving}
                        className="text-emerald-600 hover:text-emerald-800 font-semibold disabled:opacity-50 flex items-center gap-1"
                      >
                        {isSaving && isAdding ? (
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
                        onClick={() => setIsAdding(false)}
                        className="text-slate-500 hover:text-slate-700 font-medium"
                      >
                        Cancel
                      </button>
                    </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      
      {localExpenses.length === 0 && !isAdding && (
        <div className="px-6 py-12 text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-slate-50 mb-4">
            <svg className="w-6 h-6 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="text-sm font-medium text-slate-900">No expenses found</h3>
          <p className="text-xs text-slate-500 mt-1">No expenses were extracted from the documents. You can add them manually.</p>
        </div>
      )}

      {viewingItem && (
        <SourceDocumentViewer
          documentId={viewingItem.metadata?.document_id || ""}
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
