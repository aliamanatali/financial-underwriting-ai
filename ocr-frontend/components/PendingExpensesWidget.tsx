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

interface PendingExpensesWidgetProps {
  items: NormalizedDataItem[];
  availableCategories: string[];
  onUpdateExpenses: (updatedItems: NormalizedDataItem[]) => Promise<void>;
  onAddExpense: (newItem: Partial<NormalizedDataItem>) => Promise<void>;
  onRemoveExpense: (itemId: string) => Promise<void>;
  onRegenerate: () => Promise<void>;
  documents?: Record<string, DocumentMetadata[]> | DocumentMetadata[];
  packageId?: string;
}

export default function PendingExpensesWidget({
  items = [],
  availableCategories = [],
  onUpdateExpenses,
  onAddExpense,
  onRemoveExpense,
  onRegenerate,
  documents,
  packageId,
}: PendingExpensesWidgetProps) {
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
    const capexCategories = ["Capital Reserves"];
    
    if (revenueCategories.includes(category)) return "Revenue" as CategoryGroup;
    if (taxInsuranceCategories.includes(category)) return "Tax & Insurance" as CategoryGroup;
    if (capexCategories.includes(category)) return "Capital Expenditure" as CategoryGroup;
    return "Operating Expense" as CategoryGroup;
  };

  const expenseItems = useMemo(() => {
    try {
      return items.filter(
        (item) => item && item.category_group === "Pending Expense"
      );
    } catch (e) {
      console.error("Error filtering pending expenses:", e);
      return [];
    }
  }, [items]);

  const [localExpenses, setLocalExpenses] = useState<ExpenseItem[]>([]);

  useEffect(() => {
    setLocalExpenses(
      expenseItems.map((item) => ({
        id: item.id,
        name: item.raw_text || "",
        amount: typeof item.metadata?.amount === 'number' ? item.metadata.amount : 0,
        category: item.user_correction || item.normalized_value || "Uncategorized",
        source_document: item.source_document,
        metadata: item.metadata
      }))
    );
  }, [expenseItems]);

  const getDocumentId = (sourceDocument?: string): string | undefined => {
    if (!documents || !sourceDocument) return undefined;
    const allDocs = Array.isArray(documents) ? documents : Object.values(documents).flat();
    const doc = allDocs.find(d => d.filename === sourceDocument);
    return doc?.document_id;
  };

  const startEditing = (expense: ExpenseItem) => {
    setEditingId(expense.id);
    setEditValues({ ...expense });
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditValues({});
  };

  const handleSaveEdit = async (id: string, skipLoading: boolean = false) => {
    if (!skipLoading) setIsSaving(true);
    try {
        const originalItem = items.find((i) => i.id === id);
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
            
            await onUpdateExpenses([updatedItem]);
        }
        setEditingId(null);
        setEditValues({});
    } finally {
        if (!skipLoading) setIsSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm("Are you sure you want to remove this item?")) {
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
            category_group: "Pending Expense" as CategoryGroup,
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
      <div className="bg-slate-50 px-6 py-4 border-b border-slate-200 flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Proposals & Unpaid Bills</h3>
          <p className="text-xs text-slate-500">Review and categorize potential expenses. These will be included in the report upon saving.</p>
        </div>
        <div className="flex items-center gap-3">
            <button
                onClick={() => setIsAdding(true)}
                className="flex items-center gap-2 px-3 py-1.5 bg-white hover:bg-neutral-50 text-neutral-900 border border-neutral-200 text-xs font-medium rounded-lg transition-colors shadow-sm"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12h14"></path>
                    <path d="M12 5v14"></path>
                </svg>
                Add Item
            </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-white">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Description</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Category</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Amount</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider w-24">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-slate-200">
            {localExpenses.map((expense) => (
              <tr key={expense.id} className={`${editingId === expense.id ? 'bg-blue-50/30' : 'hover:bg-slate-50'} transition-colors`}>
                <td className="px-6 py-3 text-sm">
                  {editingId === expense.id ? (
                    <input
                        type="text"
                        value={editValues.name}
                        onChange={(e) => setEditValues({ ...editValues, name: e.target.value })}
                        className="w-full bg-white border border-blue-200 rounded px-2 py-1 focus:ring-1 focus:ring-blue-500 outline-none font-medium"
                    />
                  ) : (
                    <div className="flex items-center gap-2">
                        <span className="text-slate-900 font-medium">{expense.name}</span>
                    </div>
                  )}
                </td>
                <td className="px-6 py-3 text-sm">
                  {editingId === expense.id ? (
                    <select
                        value={editValues.category}
                        onChange={(e) => setEditValues({ ...editValues, category: e.target.value })}
                        className="w-full bg-white border border-blue-200 rounded px-2 py-1 focus:ring-1 focus:ring-blue-500 outline-none text-xs"
                    >
                        {availableCategories.map((cat) => (
                            <option key={cat} value={cat}>{cat}</option>
                        ))}
                    </select>
                  ) : (
                    <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded text-[10px] font-medium border border-slate-200">
                        {expense.category}
                    </span>
                  )}
                </td>
                <td className="px-6 py-3 text-sm text-right font-mono">
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
                            className="w-24 bg-white border border-blue-200 rounded px-2 py-1 focus:ring-1 focus:ring-blue-500 outline-none text-right"
                        />
                    </div>
                  ) : (
                    <span className="text-slate-900 font-semibold">${expense.amount.toLocaleString()}</span>
                  )}
                </td>
                <td className="px-6 py-3 text-sm text-right">
                  <div className="flex items-center justify-end gap-2">
                    {editingId === expense.id ? (
                        <>
                            <button
                                onClick={() => handleSaveEdit(expense.id)}
                                disabled={isSaving}
                                className="p-1 text-emerald-600 hover:bg-emerald-50 rounded transition-colors"
                                title="Save"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <polyline points="20 6 9 17 4 12"></polyline>
                                </svg>
                            </button>
                            <button
                                onClick={cancelEditing}
                                className="p-1 text-slate-400 hover:bg-slate-100 rounded transition-colors"
                                title="Cancel"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <line x1="18" y1="6" x2="6" y2="18"></line>
                                    <line x1="6" y1="6" x2="18" y2="18"></line>
                                </svg>
                            </button>
                        </>
                    ) : (
                        <>
                            {expense.metadata?.page_number && getDocumentId(expense.source_document) && (
                                <button
                                  onClick={() => {
                                    const originalItem = items.find(i => i.id === expense.id);
                                    if (originalItem) setViewingItem(originalItem);
                                  }}
                                  className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-colors"
                                  title={`View ${expense.source_document} (Page ${expense.metadata.page_number})`}
                                >
                                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
                                    <circle cx="12" cy="12" r="3"/>
                                  </svg>
                                </button>
                            )}
                            <button
                                onClick={() => startEditing(expense)}
                                className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-colors"
                                title="Edit"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path>
                                </svg>
                            </button>
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
                        </>
                    )}
                  </div>
                </td>
              </tr>
            ))}

            {isAdding && (
              <tr className="bg-blue-50/50">
                <td className="px-6 py-3 text-sm">
                  <input
                    type="text"
                    placeholder="New Item Name"
                    value={newItem.name}
                    onChange={(e) => setNewItem({ ...newItem, name: e.target.value })}
                    className="w-full bg-white border border-blue-200 rounded px-2 py-1 focus:ring-1 focus:ring-blue-500 outline-none font-medium"
                    autoFocus
                  />
                </td>
                <td className="px-6 py-3 text-sm">
                  <select
                    value={newItem.category}
                    onChange={(e) => setNewItem({ ...newItem, category: e.target.value })}
                    className="w-full bg-white border border-blue-200 rounded px-2 py-1 focus:ring-1 focus:ring-blue-500 outline-none text-xs"
                  >
                    {availableCategories.map((cat) => (
                      <option key={cat} value={cat}>{cat}</option>
                    ))}
                  </select>
                </td>
                <td className="px-6 py-3 text-sm text-right">
                    <div className="flex items-center justify-end">
                      <span className="text-slate-400 mr-1">$</span>
                      <input
                        type="text"
                        placeholder="0"
                        value={newItem.amount}
                        onChange={(e) => setNewItem({ ...newItem, amount: parseFloat(e.target.value) || 0 })}
                        className="w-24 bg-white border border-blue-200 rounded px-2 py-1 focus:ring-1 focus:ring-blue-500 outline-none text-right"
                      />
                    </div>
                </td>
                <td className="px-6 py-3 text-sm text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={handleAddNewExpense}
                        disabled={isSaving}
                        className="p-1 text-emerald-600 hover:bg-emerald-50 rounded transition-colors"
                        title="Save"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                      </button>
                      <button
                        onClick={() => setIsAdding(false)}
                        className="p-1 text-slate-400 hover:bg-slate-100 rounded transition-colors"
                        title="Cancel"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <line x1="18" y1="6" x2="6" y2="18"></line>
                          <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
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
          <h3 className="text-sm font-medium text-slate-900">No Pending Items Found</h3>
          <p className="text-xs text-slate-500 mt-1">No proposals or unpaid bills were detected. You can add them manually.</p>
        </div>
      )}

      {viewingItem && getDocumentId(viewingItem.source_document) && (
        <SourceDocumentViewer
          documentId={getDocumentId(viewingItem.source_document)!}
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
