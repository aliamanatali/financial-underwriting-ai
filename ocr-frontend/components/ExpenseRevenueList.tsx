"use client";

import React, { useState } from "react";
import { StandardizedExpense } from "@/lib/types";
import WidgetTooltip from "./WidgetTooltip";

interface ExpenseRevenueListProps {
  expenses: StandardizedExpense[];
  formatCurrency: (val: number) => string;
}

export default function ExpenseRevenueList({ expenses, formatCurrency }: ExpenseRevenueListProps) {
  const [activeTab, setActiveTab] = useState<"expenses" | "revenue">("expenses");
  const [sortField, setSortField] = useState<keyof StandardizedExpense | "source">("mapped_category");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  if (!expenses || expenses.length === 0) return null;

  // Filter items based on category
  // We assume categories starting with "Gross Potential Rent", "Other Income", "Reimbursements" are Revenue
  // All others are Expenses (excluding specific exclusions if necessary, but we'll show what's there)
  
  const revenueCategories = [
    "Gross Potential Rent", 
    "Other Income", 
    "Reimbursements", 
    "Accounts Receivable"
  ];

  const revenueItems = expenses.filter(item => {
    const cat = String(item.mapped_category);
    return revenueCategories.some(r => cat.includes(r));
  });

  const expenseItems = expenses.filter(item => {
    const cat = String(item.mapped_category);
    return !revenueCategories.some(r => cat.includes(r));
  });

  const currentItems = activeTab === "expenses" ? expenseItems : revenueItems;

  const handleSort = (field: keyof StandardizedExpense | "source") => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  const sortedItems = [...currentItems].sort((a, b) => {
    let valA: any = a[sortField as keyof StandardizedExpense];
    let valB: any = b[sortField as keyof StandardizedExpense];

    // Special handling for nested properties or specific fields
    if (sortField === "source") {
        valA = a.audit_log?.source || "Unknown";
        valB = b.audit_log?.source || "Unknown";
    }

    if (valA === undefined || valB === undefined) return 0;

    if (typeof valA === "string" && typeof valB === "string") {
      return sortDirection === "asc" 
        ? valA.localeCompare(valB)
        : valB.localeCompare(valA);
    }

    if (valA < valB) return sortDirection === "asc" ? -1 : 1;
    if (valA > valB) return sortDirection === "asc" ? 1 : -1;
    return 0;
  });

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-bold text-neutral-900">Historical Financials</h2>
          <WidgetTooltip
            title="Extracted Financial Data"
            description="Line items extracted from T12, P&L, or other financial documents."
          />
          <span className="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 text-xs font-medium border border-indigo-100">
            {expenses.length} Items
          </span>
        </div>
        
        <div className="flex items-center border border-neutral-200 rounded-lg p-0.5 bg-white shadow-inner">
            <button
            onClick={() => setActiveTab("expenses")}
            className={`px-3 py-1 text-xs font-bold rounded-md transition-colors ${activeTab === "expenses" ? "bg-neutral-800 text-white shadow-sm" : "text-neutral-600 hover:bg-neutral-100"}`}
            >
            Expenses ({expenseItems.length})
            </button>
            <button
            onClick={() => setActiveTab("revenue")}
            className={`px-3 py-1 text-xs font-bold rounded-md transition-colors ${activeTab === "revenue" ? "bg-neutral-800 text-white shadow-sm" : "text-neutral-600 hover:bg-neutral-100"}`}
            >
            Revenue ({revenueItems.length})
            </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-neutral-50 border-b border-neutral-200 text-xs text-neutral-500 font-semibold uppercase tracking-wider sticky top-0 z-10">
              <tr>
                <th className="px-6 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort("mapped_category")}>
                  Category {sortField === "mapped_category" && (sortDirection === "asc" ? "↑" : "↓")}
                </th>
                <th className="px-6 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort("original_text")}>
                  Original Description {sortField === "original_text" && (sortDirection === "asc" ? "↑" : "↓")}
                </th>
                <th className="px-6 py-3 cursor-pointer hover:bg-neutral-100 text-right" onClick={() => handleSort("amount")}>
                  Amount {sortField === "amount" && (sortDirection === "asc" ? "↑" : "↓")}
                </th>
                <th className="px-6 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort("source")}>
                  Source Document {sortField === "source" && (sortDirection === "asc" ? "↑" : "↓")}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {sortedItems.length > 0 ? (
                sortedItems.map((item, idx) => (
                    <tr key={idx} className="hover:bg-neutral-50 transition-colors">
                    <td className="px-6 py-2.5 font-medium text-neutral-900">
                        <span className={`px-2 py-0.5 rounded text-xs ${
                            activeTab === "revenue" 
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-100" 
                                : "bg-orange-50 text-orange-700 border border-orange-100"
                        }`}>
                        {item.mapped_category}
                        </span>
                    </td>
                    <td className="px-6 py-2.5 text-neutral-600 truncate max-w-[300px]" title={item.original_text}>
                        {item.original_text}
                    </td>
                    <td className="px-6 py-2.5 text-right font-medium text-neutral-900">
                        {formatCurrency(item.amount)}
                    </td>
                    <td className="px-6 py-2.5 text-xs text-neutral-500 max-w-[200px] truncate" title={item.audit_log?.source}>
                        {item.audit_log?.source ? (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-neutral-100 border border-neutral-200 text-neutral-600">
                            <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
                            <polyline points="14 2 14 8 20 8"/>
                            </svg>
                            {item.audit_log.source}
                        </span>
                        ) : (
                        <span className="text-neutral-300 italic">Unknown</span>
                        )}
                    </td>
                    </tr>
                ))
              ) : (
                <tr>
                    <td colSpan={4} className="px-6 py-8 text-center text-neutral-500">
                        No {activeTab} items found in the extracted data.
                    </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}