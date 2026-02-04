"use client";

import React, { useState } from "react";
import { RentRollItem } from "@/lib/types";
import WidgetTooltip from "./WidgetTooltip";

interface CombinedRentRollTableProps {
  rentRoll: RentRollItem[];
  formatCurrency: (val: number) => string;
}

export default function CombinedRentRollTable({ rentRoll, formatCurrency }: CombinedRentRollTableProps) {
  const [sortField, setSortField] = useState<keyof RentRollItem>("unit_number");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  if (!rentRoll || rentRoll.length === 0) return null;

  const handleSort = (field: keyof RentRollItem) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  const sortedRentRoll = [...rentRoll].sort((a, b) => {
    const valA = a[sortField];
    const valB = b[sortField];

    if (valA === undefined || valB === undefined) return 0;

    if (typeof valA === "string" && typeof valB === "string") {
      // Natural sort for unit numbers (e.g., "Unit 2" before "Unit 10")
      return sortDirection === "asc" 
        ? valA.localeCompare(valB, undefined, { numeric: true })
        : valB.localeCompare(valA, undefined, { numeric: true });
    }

    if (valA < valB) return sortDirection === "asc" ? -1 : 1;
    if (valA > valB) return sortDirection === "asc" ? 1 : -1;
    return 0;
  });

  // Determine if optional columns have data
  // Determine if optional columns have data
  const hasDeposits = rentRoll.some(i => i.deposit && i.deposit > 0);
  const hasParking = rentRoll.some(i => i.parking && i.parking.trim() !== "");
  const hasComments = rentRoll.some(i => i.comments && i.comments.trim() !== "");
  // Using explicit type cast to access optional floor property
  const hasFloor = rentRoll.some(i => (i as any).floor && (i as any).floor.trim() !== "");

  return (
    <div className="mt-8">
      <div className="flex items-center gap-2 mb-4">
        <h2 className="text-xl font-bold text-neutral-900">Combined Rent Roll</h2>
        <WidgetTooltip
          title="Aggregated Source Data"
          description="This table displays the master rent roll derived from all uploaded documents (PDFs, Excel). It shows which file provided data for each unit."
        />
        <span className="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 text-xs font-medium border border-indigo-100">
          {rentRoll.length} Units
        </span>
      </div>

      <div className="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-neutral-50 border-b border-neutral-200 text-xs text-neutral-500 font-semibold uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort("unit_number")}>
                  Unit # {sortField === "unit_number" && (sortDirection === "asc" ? "↑" : "↓")}
                </th>
                <th className="px-4 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort("unit_type")}>
                  Type {sortField === "unit_type" && (sortDirection === "asc" ? "↑" : "↓")}
                </th>
                
                {hasFloor && (
                  <th className="px-4 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort("floor" as any)}>
                    Floor {sortField === ("floor" as any) && (sortDirection === "asc" ? "↑" : "↓")}
                  </th>
                )}

                <th className="px-4 py-3 cursor-pointer hover:bg-neutral-100 text-right" onClick={() => handleSort("unit_size")}>
                  Size (SF) {sortField === "unit_size" && (sortDirection === "asc" ? "↑" : "↓")}
                </th>
                <th className="px-4 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort("tenant_name")}>
                  Tenant {sortField === "tenant_name" && (sortDirection === "asc" ? "↑" : "↓")}
                </th>
                <th className="px-4 py-3 cursor-pointer hover:bg-neutral-100 text-right" onClick={() => handleSort("current_rent")}>
                  Current Rent {sortField === "current_rent" && (sortDirection === "asc" ? "↑" : "↓")}
                </th>
                <th className="px-4 py-3 cursor-pointer hover:bg-neutral-100 text-right" onClick={() => handleSort("market_rent")}>
                  Market Rent {sortField === "market_rent" && (sortDirection === "asc" ? "↑" : "↓")}
                </th>
                
                {hasDeposits && (
                  <th className="px-4 py-3 cursor-pointer hover:bg-neutral-100 text-right" onClick={() => handleSort("deposit")}>
                    Deposit {sortField === "deposit" && (sortDirection === "asc" ? "↑" : "↓")}
                  </th>
                )}
                {hasParking && (
                  <th className="px-4 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort("parking")}>
                    Parking {sortField === "parking" && (sortDirection === "asc" ? "↑" : "↓")}
                  </th>
                )}
                {hasComments && (
                  <th className="px-4 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort("comments")}>
                    Comments {sortField === "comments" && (sortDirection === "asc" ? "↑" : "↓")}
                  </th>
                )}

                <th className="px-4 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort("lease_start")}>
                  Lease Start {sortField === "lease_start" && (sortDirection === "asc" ? "↑" : "↓")}
                </th>
                <th className="px-4 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort("lease_end")}>
                  Lease End {sortField === "lease_end" && (sortDirection === "asc" ? "↑" : "↓")}
                </th>
                <th className="px-4 py-3 cursor-pointer hover:bg-neutral-100" onClick={() => handleSort("source_file")}>
                  Source File {sortField === "source_file" && (sortDirection === "asc" ? "↑" : "↓")}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {sortedRentRoll.map((item, idx) => (
                <tr key={idx} className="hover:bg-neutral-50 transition-colors">
                  <td className="px-4 py-2.5 font-medium text-neutral-900">{item.unit_number}</td>
                  <td className="px-4 py-2.5 text-neutral-600">{item.unit_type}</td>
                  
                  {hasFloor && (
                    <td className="px-4 py-2.5 text-neutral-600">{(item as any).floor || "-"}</td>
                  )}

                  <td className="px-4 py-2.5 text-right text-neutral-600">{item.unit_size || "-"}</td>
                  <td className="px-4 py-2.5 text-neutral-900 truncate max-w-[150px]" title={item.tenant_name}>{item.tenant_name}</td>
                  <td className="px-4 py-2.5 text-right font-medium text-neutral-900">{formatCurrency(item.current_rent)}</td>
                  <td className="px-4 py-2.5 text-right text-neutral-600">{formatCurrency(item.market_rent)}</td>
                  
                  {hasDeposits && (
                    <td className="px-4 py-2.5 text-right text-neutral-600">{item.deposit ? formatCurrency(item.deposit) : "-"}</td>
                  )}
                  {hasParking && (
                    <td className="px-4 py-2.5 text-neutral-600 truncate max-w-[150px]" title={item.parking}>{item.parking || "-"}</td>
                  )}
                  {hasComments && (
                    <td className="px-4 py-2.5 text-neutral-600 text-xs truncate max-w-[200px]" title={item.comments}>{item.comments || "-"}</td>
                  )}

                  <td className="px-4 py-2.5 text-neutral-600 text-xs">{item.lease_start || "-"}</td>
                  <td className="px-4 py-2.5 text-neutral-600 text-xs">{item.lease_end || "-"}</td>
                  <td className="px-4 py-2.5 text-xs text-neutral-500 max-w-[200px] truncate" title={item.source_file}>
                    {item.source_file ? (
                      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-neutral-100 border border-neutral-200 text-neutral-600">
                        <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
                          <polyline points="14 2 14 8 20 8"/>
                        </svg>
                        {item.source_file}
                      </span>
                    ) : (
                      <span className="text-neutral-300 italic">Unknown</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}