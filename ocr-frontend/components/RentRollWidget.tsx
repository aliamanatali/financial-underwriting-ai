"use client";

import React, { useState, useEffect } from "react";
import { RentRollItem, RentRollSummary, UnderwritingAnalysis } from "@/lib/types";
import { apiClient } from "@/lib/api";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

type DraggableRentRollItem = RentRollItem & { id: string };

interface RentRollWidgetProps {
  rentRoll: RentRollItem[];
  summary?: RentRollSummary;
  packageId: string;
  onUpdate?: () => void;
}

export default function RentRollWidget({
  rentRoll,
  summary,
  packageId,
  onUpdate,
}: RentRollWidgetProps) {
  const [isEditing, setIsEditing] = useState(false);
  // Initialize with IDs
  const [items, setItems] = useState<DraggableRentRollItem[]>(
    rentRoll.map(item => ({ ...item, id: item.unit_number || `unit-${Math.random()}` }))
  );

  useEffect(() => {
    setItems(rentRoll.map(item => ({ ...item, id: item.unit_number || `unit-${Math.random()}` })));
  }, [rentRoll]);

  const [isSaving, setIsSaving] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      setItems((items) => {
        const oldIndex = items.findIndex((item) => item.id === active.id);
        const newIndex = items.findIndex((item) => item.id === over.id);

        return arrayMove(items, oldIndex, newIndex);
      });
    }
  };



  const handleItemChange = (index: number, field: keyof RentRollItem, value: any) => {
    const newItems = [...items];
    newItems[index] = {
      ...newItems[index],
      [field]: ["current_rent", "market_rent", "stabilized_rent", "unit_size"].includes(field) ? parseFloat(value) || 0 : value,
    };
    setItems(newItems);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Remove 'id' before saving
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const cleanItems = items.map(({ id, ...rest }) => rest);
      await apiClient.updateManualOverrides(packageId, { rent_roll: cleanItems });
      setIsEditing(false);
      if (onUpdate) {
        onUpdate();
      }
    } catch (error) {
      console.error("Error saving rent roll:", error);
      alert("Failed to save changes. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      // Construct a temporary analysis object with the CURRENT state of the rent roll
      // This ensures edited values (even if not saved to backend yet) are exported
      const exportData: Partial<UnderwritingAnalysis> = {
        document_id: packageId, // Use packageId as doc id for filename
        rent_roll: items,
        rent_roll_summary: displaySummary,
        // Fill other required fields with safe defaults if needed by the backend schema validation
        pass_fail_status: "PASS",
        property_meta: { address: "Export", year_built: 0, purchase_price: 0, total_units: items.length },
        historical_expenses: [],
      };

      await apiClient.downloadExport(exportData as UnderwritingAnalysis, 'rent-roll');
    } catch (error) {
      console.error("Export failed:", error);
      alert("Failed to export Excel file.");
    } finally {
      setIsExporting(false);
    }
  };

  const handleCancel = () => {
    setItems(rentRoll.map(item => ({ ...item, id: item.unit_number || `unit-${Math.random()}` })));
    setIsEditing(false);
  };

  const addItem = () => {
    setItems([
      ...items,
      {
        id: `new-${Date.now()}`,
        unit_number: `Unit ${items.length + 1}`,
        unit_size: 0,
        unit_type: "1BR",
        tenant_name: "Vacant",
        current_rent: 0,
        stabilized_rent: 0,
        market_rent: 0,
        move_in_date: "",
        lease_start: "",
        lease_end: "",
      },
    ]);
  };


  const removeItem = (index: number) => {
    const newItems = [...items];
    newItems.splice(index, 1);
    setItems(newItems);
  };

  // Calculate local summary for immediate feedback
  const localSummary = React.useMemo(() => {
    const totalUnits = items.length;
    
    // Filter items that are actually paying rent (occupied)
    const payingItems = items.filter(i =>
      i.tenant_name &&
      i.tenant_name.toLowerCase() !== "vacant" &&
      (i.current_rent || 0) > 0
    );

    const occupiedUnits = payingItems.length;
    const occupancyRate = totalUnits > 0 ? occupiedUnits / totalUnits : 0;
    
    const totalUnitSize = items.reduce((sum, item) => sum + (item.unit_size || 0), 0);
    const payingUnitSize = payingItems.reduce((sum, item) => sum + (item.unit_size || 0), 0);
    const avgUnitSize = totalUnits > 0 ? totalUnitSize / totalUnits : 0;

    const totalMonthlyRent = items.reduce((sum, item) => sum + (item.current_rent || 0), 0);
    const totalAnnualRent = totalMonthlyRent * 12;
    
    const totalStabilizedRent = items.reduce((sum, item) => sum + (item.stabilized_rent || 0), 0);
    const totalMarketRent = items.reduce((sum, item) => sum + (item.market_rent || 0), 0);

    // Calculate averages based on paying units only (ignoring 0$ rent units)
    const avgRentPerUnit = occupiedUnits > 0 ? totalMonthlyRent / occupiedUnits : 0;
    const avgRentPerSF = payingUnitSize > 0 ? totalMonthlyRent / payingUnitSize : 0;
    
    const avgStabilizedPerUnit = totalUnits > 0 ? totalStabilizedRent / totalUnits : 0;
    const avgStabilizedPerSF = totalUnitSize > 0 ? totalStabilizedRent / totalUnitSize : 0;
    
    const avgMarketPerUnit = totalUnits > 0 ? totalMarketRent / totalUnits : 0;
    const avgMarketPerSF = totalUnitSize > 0 ? totalMarketRent / totalUnitSize : 0;

    return {
      total_units: totalUnits,
      occupied_units: occupiedUnits,
      occupancy_rate: occupancyRate,
      avg_unit_size: avgUnitSize,
      total_monthly_rent: totalMonthlyRent,
      total_annual_rent: totalAnnualRent,
      total_stabilized_rent: totalStabilizedRent,
      total_market_rent: totalMarketRent,
      avg_rent_per_unit: avgRentPerUnit,
      avg_rent_per_sf: avgRentPerSF,
      avg_stabilized_per_unit: avgStabilizedPerUnit,
      avg_stabilized_per_sf: avgStabilizedPerSF,
      avg_market_per_unit: avgMarketPerUnit,
      avg_market_per_sf: avgMarketPerSF
    };
  }, [items]);

  // Calculate summary groups by unit type
  const summaryGroups = React.useMemo(() => {
    const groups: Record<string, {
      count: number;
      payingCount: number;
      totalCurrentRent: number;
      totalStabilizedRent: number;
      totalMarketRent: number;
      totalSqFt: number;
    }> = {};

    items.forEach(item => {
      let key = item.unit_type || "Unknown";
      
     // Check if unit is vacant (explicitly or 0 rent)
      const isVacant = (item.tenant_name && item.tenant_name.toLowerCase() === "vacant") || (item.current_rent || 0) === 0;
      if (isVacant) {
        key = `${key} - Vacant`;
      }
      
      if (!groups[key]) {
        groups[key] = { count: 0, payingCount: 0, totalCurrentRent: 0, totalStabilizedRent: 0, totalMarketRent: 0, totalSqFt: 0 };
      }
      
      groups[key].count++;
      if ((item.current_rent || 0) > 0) {
        groups[key].payingCount++;
      }
      groups[key].totalCurrentRent += item.current_rent || 0;
      groups[key].totalStabilizedRent += item.stabilized_rent || 0;
      groups[key].totalMarketRent += item.market_rent || 0;
      groups[key].totalSqFt += item.unit_size || 0;
    });

    return Object.entries(groups).map(([type, data]) => ({
      type,
      count: data.count,
      percent: items.length > 0 ? data.count / items.length : 0,
      avgCurrentRent: data.payingCount > 0 ? data.totalCurrentRent / data.payingCount : 0,
      avgStabilizedRent: data.count > 0 ? data.totalStabilizedRent / data.count : 0,
      avgMarketRent: data.count > 0 ? data.totalMarketRent / data.count : 0,
      avgSqFt: data.count > 0 ? data.totalSqFt / data.count : 0
    })).sort((a, b) => b.count - a.count); // Sort by count descending
  }, [items]);

  const displaySummary = isEditing ? localSummary : (summary || localSummary);

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);

  const formatPercent = (val: number) =>
    (val * 100).toFixed(0) + "%";

  return (
    <>
      <div className="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden mb-6">
      <div className="px-6 py-4 border-b border-neutral-100 flex items-center justify-between bg-neutral-50/50">
        <h3 className="text-lg font-bold text-neutral-900 flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-neutral-500">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="3" y1="9" x2="21" y2="9"></line>
            <line x1="9" y1="21" x2="9" y2="9"></line>
          </svg>
          Rent Roll Detail
        </h3>
        {!isEditing ? (
          <div className="flex gap-2">
            <button
              onClick={handleExport}
              disabled={isExporting}
              className="text-xs font-medium text-neutral-600 hover:text-neutral-900 border border-neutral-200 px-3 py-1.5 rounded-lg bg-white hover:bg-neutral-50 transition-all shadow-sm flex items-center gap-1.5"
            >
              {isExporting ? (
                <span>Exporting...</span>
              ) : (
                <>
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7 10 12 15 17 10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                  </svg>
                  Export Excel
                </>
              )}
            </button>
            <button
              onClick={() => setIsEditing(true)}
              className="text-xs font-medium text-neutral-600 hover:text-neutral-900 border border-neutral-200 px-3 py-1.5 rounded-lg bg-white hover:bg-neutral-50 transition-all shadow-sm flex items-center gap-1.5"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
              </svg>
              Edit Rent Roll
            </button>
          </div>
        ) : (
          <div className="flex gap-2">
             <button
              onClick={addItem}
              className="text-xs font-medium text-neutral-600 hover:text-neutral-900 border border-neutral-200 px-3 py-1.5 rounded-lg bg-white hover:bg-neutral-50 transition-all shadow-sm"
            >
              + Add Unit
            </button>
            <button
              onClick={handleCancel}
              className="text-xs font-medium text-neutral-600 hover:text-neutral-900 border border-neutral-200 px-3 py-1.5 rounded-lg bg-white hover:bg-neutral-50 transition-all shadow-sm"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="text-xs font-medium bg-neutral-900 text-white px-3 py-1.5 rounded-lg hover:bg-neutral-800 transition-all shadow-sm flex items-center gap-1.5 disabled:opacity-50"
            >
              {isSaving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        )}
      </div>

      <div className="overflow-x-auto">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="bg-neutral-900 border-b border-neutral-900 text-xs text-white uppercase tracking-wider font-semibold">
                <th className="px-4 py-3">Unit #</th>
                <th className="px-4 py-3 text-right">Unit Size</th>
                <th className="px-4 py-3">Unit Type</th>
                <th className="px-4 py-3 text-right">Current Rent</th>
                <th className="px-4 py-3 text-right">Stabilized Rent</th>
                <th className="px-4 py-3 text-right">Market Rent</th>
                <th className="px-4 py-3 text-center">Move-In Date</th>
                <th className="px-4 py-3 text-center">Lease Start</th>
                <th className="px-4 py-3 text-center">Lease End</th>
                {isEditing && <th className="px-4 py-3 text-center">Action</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              <SortableContext
                items={items.map((item) => item.id)}
                strategy={verticalListSortingStrategy}
              >
                {items.map((item, idx) => (
                  <SortableRow
                    key={item.id}
                    item={item}
                    idx={idx}
                    isEditing={isEditing}
                    handleItemChange={handleItemChange}
                    formatCurrency={formatCurrency}
                    removeItem={removeItem}
                  />
                ))}
              </SortableContext>
              {items.length === 0 && (
                <tr>
                  <td colSpan={isEditing ? 10 : 9} className="px-6 py-8 text-center text-neutral-500 text-sm">
                    No rent roll data available.
                  </td>
                </tr>
              )}
            </tbody>
            <tfoot className="bg-neutral-900 text-white border-t border-neutral-800">
             {/* Header Row */}
             <tr className="text-xs font-semibold uppercase tracking-wider border-b border-neutral-800">
               <td className="px-4 py-3 text-center">Total Units</td>
               <td className="px-4 py-3 text-right">Avg Unit Size</td>
               <td className="px-4 py-3"></td>
               <td className="px-4 py-3 text-right">Current Rent</td>
               <td className="px-4 py-3 text-right">Stabilized Rent</td>
               <td className="px-4 py-3 text-right">Market Rent</td>
               <td colSpan={isEditing ? 4 : 3}></td>
             </tr>
             {/* Data Row */}
             <tr className="border-b border-neutral-800/50 align-top">
               <td className="px-4 py-3 text-center">
                 <div className="font-bold text-lg">{displaySummary.total_units}</div>
               </td>
               <td className="px-4 py-3 text-right">
                  <div className="font-bold text-lg">{Math.round(displaySummary.avg_unit_size || 0)}</div>
               </td>
               <td className="px-4 py-3"></td>
               <td className="px-4 py-3 text-right">
                  <div className="text-xs space-y-1">
                    <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Monthly</span> <span className="font-bold">{formatCurrency(displaySummary.total_monthly_rent)}</span></div>
                    <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Annual</span> <span className="font-bold">{formatCurrency(displaySummary.total_annual_rent)}</span></div>
                    <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Avg Unit</span> <span className="font-bold">{formatCurrency(displaySummary.avg_rent_per_unit)}</span></div>
                    <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Avg SF</span> <span className="font-bold">${(displaySummary.avg_rent_per_sf || 0).toFixed(2)}</span></div>
                  </div>
               </td>
               <td className="px-4 py-3 text-right">
                  <div className="text-xs space-y-1">
                    <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Monthly</span> <span className="font-bold">{formatCurrency(displaySummary.total_stabilized_rent)}</span></div>
                    <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Annual</span> <span className="font-bold">{formatCurrency((displaySummary.total_stabilized_rent || 0) * 12)}</span></div>
                    <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Avg Unit</span> <span className="font-bold">{formatCurrency(displaySummary.avg_stabilized_per_unit)}</span></div>
                    <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Avg SF</span> <span className="font-bold">${(displaySummary.avg_stabilized_per_sf || 0).toFixed(2)}</span></div>
                  </div>
               </td>
               <td className="px-4 py-3 text-right">
                  <div className="text-xs space-y-1">
                    <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Monthly</span> <span className="font-bold">{formatCurrency(displaySummary.total_market_rent)}</span></div>
                    <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Annual</span> <span className="font-bold">{formatCurrency((displaySummary.total_market_rent || 0) * 12)}</span></div>
                    <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Avg Unit</span> <span className="font-bold">{formatCurrency(displaySummary.avg_market_per_unit)}</span></div>
                    <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Avg SF</span> <span className="font-bold">${(displaySummary.avg_market_per_sf || 0).toFixed(2)}</span></div>
                  </div>
               </td>
               <td colSpan={isEditing ? 4 : 3}></td>
             </tr>
          </tfoot>
          </table>
        </DndContext>
      </div>
     </div>

      {/* Rent Roll Summary Table */}
      <div className="mt-8">
        <h2 className="text-2xl font-bold text-neutral-900 mb-4">RENT ROLL SUMMARY</h2>
        <div className="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden">
          <div className="bg-neutral-900 px-6 py-3 text-center border-b border-neutral-900">
            <h3 className="text-white font-medium">Rent Roll Summary</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-neutral-200 text-xs text-neutral-900 font-bold">
                  <th className="px-6 py-3">Unit Mix</th>
                  <th className="px-6 py-3 text-center">Unit Count</th>
                  <th className="px-6 py-3 text-center">%</th>
                  <th className="px-6 py-3 text-right">Avg. Current Rent</th>
                  <th className="px-6 py-3 text-right">Stabilized Rent</th>
                  <th className="px-6 py-3 text-right">Market Rent</th>
                  <th className="px-6 py-3 text-right">Avg. Sq Ft</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {summaryGroups.map((group, idx) => (
                  <tr key={idx} className="hover:bg-neutral-50/50 transition-colors">
                    <td className="px-6 py-3 font-medium text-neutral-900">{group.type}</td>
                    <td className="px-6 py-3 text-center text-neutral-600">{group.count}</td>
                    <td className="px-6 py-3 text-center text-neutral-600">{formatPercent(group.percent)}</td>
                    <td className="px-6 py-3 text-right text-neutral-600">{group.avgCurrentRent === 0 ? "-" : formatCurrency(group.avgCurrentRent)}</td>
                    <td className="px-6 py-3 text-right text-neutral-600">{formatCurrency(group.avgStabilizedRent)}</td>
                    <td className="px-6 py-3 text-right text-neutral-600">{formatCurrency(group.avgMarketRent)}</td>
                    <td className="px-6 py-3 text-right text-neutral-600">{Math.round(group.avgSqFt)}</td>
                  </tr>
                ))}
                {/* Totals Row */}
                <tr className="border-t-2 border-neutral-900 font-bold bg-white">
                  <td className="px-6 py-4 text-neutral-900">Totals/Average</td>
                  <td className="px-6 py-4 text-center text-neutral-900">{displaySummary.total_units}</td>
                  <td className="px-6 py-4 text-center text-neutral-900">100%</td>
                  <td className="px-6 py-4 text-right text-neutral-900">
                    {formatCurrency(displaySummary.occupied_units > 0 ? displaySummary.total_monthly_rent / displaySummary.occupied_units : 0)}
                  </td>
                  <td className="px-6 py-4 text-right text-neutral-900">{formatCurrency(displaySummary.avg_stabilized_per_unit)}</td>
                  <td className="px-6 py-4 text-right text-neutral-900">{formatCurrency(displaySummary.avg_market_per_unit)}</td>
                  <td className="px-6 py-4 text-right text-neutral-900">{Math.round(displaySummary.avg_unit_size)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}

function SortableRow({
  item,
  idx,
  isEditing,
  handleItemChange,
  formatCurrency,
  removeItem,
}: {
  item: RentRollItem;
  idx: number;
  isEditing: boolean;
  handleItemChange: (index: number, field: keyof RentRollItem, value: any) => void;
  formatCurrency: (val: number) => string;
  removeItem: (index: number) => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: (item as any).id || item.unit_number });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 10 : 1,
    position: isDragging ? "relative" : undefined,
  } as React.CSSProperties;

  return (
    <tr
      ref={setNodeRef}
      style={style}
      className={`group hover:bg-neutral-50/50 transition-colors ${isDragging ? "bg-neutral-50 shadow-md" : "bg-white"
        }`}
    >
      <td className="px-4 py-2.5 font-medium text-neutral-900">
        <div className="flex items-center gap-2">
           {isEditing && (
            <div
              {...attributes}
              {...listeners}
              className="cursor-grab hover:text-neutral-900 text-neutral-400 p-1"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="9" cy="12" r="1"></circle>
                <circle cx="9" cy="5" r="1"></circle>
                <circle cx="9" cy="19" r="1"></circle>
                <circle cx="15" cy="12" r="1"></circle>
                <circle cx="15" cy="5" r="1"></circle>
                <circle cx="15" cy="19" r="1"></circle>
              </svg>
            </div>
           )}
          {isEditing ? (
            <input
              type="text"
              value={item.unit_number}
              onChange={(e) => handleItemChange(idx, "unit_number", e.target.value)}
              className="w-full bg-white border border-neutral-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-neutral-900 focus:outline-none"
            />
          ) : (
            item.unit_number
          )}
        </div>
      </td>
      <td className="px-4 py-2.5 text-right text-neutral-600">
        {isEditing ? (
          <input
            type="number"
            value={item.unit_size}
            onChange={(e) => handleItemChange(idx, "unit_size", e.target.value)}
            className="w-20 ml-auto bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-right focus:ring-1 focus:ring-neutral-900 focus:outline-none"
          />
        ) : (
          item.unit_size || "-"
        )}
      </td>
      <td className="px-4 py-2.5 text-neutral-600">
        {isEditing ? (
          <input
            type="text"
            value={item.unit_type}
            onChange={(e) => handleItemChange(idx, "unit_type", e.target.value)}
            className="w-full bg-white border border-neutral-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-neutral-900 focus:outline-none"
          />
        ) : (
          item.unit_type
        )}
      </td>
      <td className="px-4 py-2.5 text-right font-medium text-neutral-900">
        {isEditing ? (
          <input
            type="number"
            value={item.current_rent}
            onChange={(e) => handleItemChange(idx, "current_rent", e.target.value)}
            className="w-20 ml-auto bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-right focus:ring-1 focus:ring-neutral-900 focus:outline-none"
          />
        ) : (
          formatCurrency(item.current_rent)
        )}
      </td>
      <td className="px-4 py-2.5 text-right text-neutral-600">
        {isEditing ? (
          <input
            type="number"
            value={item.stabilized_rent}
            onChange={(e) => handleItemChange(idx, "stabilized_rent", e.target.value)}
            className="w-20 ml-auto bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-right focus:ring-1 focus:ring-neutral-900 focus:outline-none"
          />
        ) : (
          formatCurrency(item.stabilized_rent || 0)
        )}
      </td>
      <td className="px-4 py-2.5 text-right text-neutral-600">
        {isEditing ? (
          <input
            type="number"
            value={item.market_rent}
            onChange={(e) => handleItemChange(idx, "market_rent", e.target.value)}
            className="w-20 ml-auto bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-right focus:ring-1 focus:ring-neutral-900 focus:outline-none"
          />
        ) : (
          formatCurrency(item.market_rent || 0)
        )}
      </td>
      <td className="px-4 py-2.5 text-center text-neutral-500 text-xs">
        {isEditing ? (
          <input
            type="text"
            value={item.move_in_date || ""}
            placeholder="MM/DD/YY"
            onChange={(e) => handleItemChange(idx, "move_in_date", e.target.value)}
            className="w-24 mx-auto bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
          />
        ) : (
          item.move_in_date || "-"
        )}
      </td>
      <td className="px-4 py-2.5 text-center text-neutral-500 text-xs">
        {isEditing ? (
          <input
            type="text"
            value={item.lease_start || ""}
            placeholder="MM/DD/YY"
            onChange={(e) => handleItemChange(idx, "lease_start", e.target.value)}
            className="w-24 mx-auto bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
          />
        ) : (
          item.lease_start || "-"
        )}
      </td>
      <td className="px-4 py-2.5 text-center text-neutral-500 text-xs">
        {isEditing ? (
          <input
            type="text"
            value={item.lease_end || ""}
            placeholder="MM/DD/YY"
            onChange={(e) => handleItemChange(idx, "lease_end", e.target.value)}
            className="w-24 mx-auto bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
          />
        ) : (
          item.lease_end || "-"
        )}
      </td>
      {isEditing && (
        <td className="px-4 py-2.5 text-center">
          <button
            onClick={() => removeItem(idx)}
            className="text-neutral-400 hover:text-rose-500 transition-colors p-1"
            title="Remove Unit"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6 6 18"></path>
              <path d="m6 6 12 12"></path>
            </svg>
          </button>
        </td>
      )}
    </tr>
  );
}