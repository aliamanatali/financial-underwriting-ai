"use client";

import React, { useState, useEffect } from "react";
import { RentRollItem, RentRollSummary, UnderwritingAnalysis, StudentHousingConfig } from "@/lib/types";
import { apiClient } from "@/lib/api";
import WarningModal from "./WarningModal";
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

type EditableRentRollItem = Omit<RentRollItem, "unit_size" | "current_rent" | "stabilized_rent" | "market_rent"> & {
  id: string;
  unit_size: string | number;
  current_rent: string | number;
  stabilized_rent: string | number;
  market_rent: string | number;
};

interface RentRollWidgetProps {
  rentRoll: RentRollItem[];
  summary?: RentRollSummary;
  packageId: string;
  onUpdate?: () => void;
  studentHousingConfig?: StudentHousingConfig;
  onOpenConfig?: () => void;
}

// Helpers for date input conversion (YYYY-MM-DD <-> MM/DD/YYYY)
const toInputDate = (displayDate: string | undefined | null) => {
  if (!displayDate) return "";
  
  // If it's already in YYYY-MM-DD format, return as is
  if (displayDate.match(/^\d{4}-\d{2}-\d{2}$/)) return displayDate;

  const parts = displayDate.split('/');
  if (parts.length === 3) {
    let [month, day, year] = parts;
    
    // Handle 2-digit years (e.g. "24" -> "2024")
    if (year.length === 2) {
      year = "20" + year;
    }
    
    // Ensure padding
    month = month.padStart(2, '0');
    day = day.padStart(2, '0');
    
    return `${year}-${month}-${day}`;
  }
  
  // If parsing fails, return empty string to avoid input error
  return "";
};

const fromInputDate = (inputDate: string) => {
  if (!inputDate) return "";
  const parts = inputDate.split('-');
  if (parts.length === 3) {
    // YYYY-MM-DD -> MM/DD/YYYY
    return `${parts[1]}/${parts[2]}/${parts[0]}`;
  }
  return inputDate;
};

export default function RentRollWidget({
  rentRoll,
  summary,
  packageId,
  onUpdate,
  studentHousingConfig,
  onOpenConfig,
}: RentRollWidgetProps) {
  const [isEditing, setIsEditing] = useState(false);
  // Initialize with IDs
  const [items, setItems] = useState<EditableRentRollItem[]>(
    rentRoll.map(item => ({ ...item, id: item.unit_number || `unit-${Math.random()}` }))
  );

  useEffect(() => {
    setItems(rentRoll.map(item => ({ ...item, id: item.unit_number || `unit-${Math.random()}` })));
  }, [rentRoll]);

  const [isSaving, setIsSaving] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [showWarning, setShowWarning] = useState(false);
  const [warningMessage, setWarningMessage] = useState("");
  // Map of Row ID -> { fieldName: errorMessage }
  const [rowErrors, setRowErrors] = useState<Record<string, Record<string, string>>>({});

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



  const handleItemChange = (index: number, field: keyof EditableRentRollItem, value: any) => {
    const newItems = [...items];
    newItems[index] = {
      ...newItems[index],
      [field]: value,
    };
    setItems(newItems);
  };

  const handleSave = async () => {
    setIsSaving(true);

    // 1. Normalize data first (convert strings to numbers, handle empty values)
    const cleanItems: RentRollItem[] = items.map(({ id, ...rest }) => ({
      ...rest,
      unit_size: parseFloat(String(rest.unit_size)) || 0,
      current_rent: parseFloat(String(rest.current_rent)) || 0,
      stabilized_rent: parseFloat(String(rest.stabilized_rent)) || 0,
      market_rent: parseFloat(String(rest.market_rent)) || 0,
    }));

    // 2. Validate normalized data
    const newRowErrors: Record<string, Record<string, string>> = {};
    let errorCount = 0;

    cleanItems.forEach((item, index) => {
      const rowId = items[index].id; // Get ID from original items
      const errors: Record<string, string> = {};

      if (!item.unit_number) errors.unit_number = "Required";
      if (!item.unit_type) errors.unit_type = "Required";
      if (item.unit_size <= 0) errors.unit_size = "Required";

      if (item.stabilized_rent <= 0) errors.stabilized_rent = "Required";
      if (item.market_rent <= 0) errors.market_rent = "Required";

      // Occupancy Logic:
      // 1. If paying rent (Current Rent > 0), Lease Start Date is required.
      if (item.current_rent > 0 && !item.lease_start) {
        errors.lease_start = "Required";
      }

      if (Object.keys(errors).length > 0) {
        newRowErrors[rowId] = errors;
        errorCount++;
      }
    });

    if (errorCount > 0) {
      setRowErrors(newRowErrors);
      setWarningMessage(
        `Found ${errorCount} unit(s) with incomplete data.\n\nPlease ensure:\n• All units have Number, Type, and Size (> 0)\n• Stabilized and Market Rents are set (> 0)\n• Occupied units (Current Rent > 0) have a Lease Start Date`
      );
      setShowWarning(true);
      setIsSaving(false);
      return;
    }
    
    // Clear invalid rows if all good
    setRowErrors({});

    try {
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
    // Check if configuration is missing
    const hasConfig = studentHousingConfig && studentHousingConfig.unit_type_configs.length > 0;
    
    if (!hasConfig && onOpenConfig) {
        onOpenConfig();
        return;
    }

    setIsExporting(true);
    try {
      // Construct a temporary analysis object with the CURRENT state of the rent roll
      // This ensures edited values (even if not saved to backend yet) are exported
      const exportData: Partial<UnderwritingAnalysis> = {
        document_id: packageId, // Use packageId as doc id for filename
        rent_roll: items.map(item => ({
          ...item,
          unit_size: parseFloat(String(item.unit_size)) || 0,
          current_rent: parseFloat(String(item.current_rent)) || 0,
          stabilized_rent: parseFloat(String(item.stabilized_rent)) || 0,
          market_rent: parseFloat(String(item.market_rent)) || 0,
        })),
        rent_roll_summary: displaySummary,
        student_housing_config: studentHousingConfig,
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
    setRowErrors({});
    setIsEditing(false);
  };

  const addItem = () => {
    // Determine the next unit number based on the maximum existing number found
    let maxNum = 0;
    const regex = /\d+/;
    items.forEach(item => {
      const match = item.unit_number?.match(regex);
      if (match) {
        const num = parseInt(match[0], 10);
        if (num > maxNum) {
          maxNum = num;
        }
      }
    });

    let nextNum = maxNum + 1;
    let nextUnitNumber = `# ${nextNum}`;
    const existingUnitNumbers = new Set(items.map(i => i.unit_number?.trim().toLowerCase() || ""));
    
    // Ensure uniqueness just in case (e.g. if mixed formats cause collision)
    while (existingUnitNumbers.has(nextUnitNumber.toLowerCase())) {
        nextNum++;
        nextUnitNumber = `# ${nextNum}`;
    }

    setItems([
      ...items,
      {
        id: `new-${Date.now()}`,
        unit_number: nextUnitNumber,
        unit_size: 0,
        unit_type: "0/1.00",
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
      (parseFloat(String(i.current_rent)) || 0) > 0
    );

    const occupiedUnits = payingItems.length;
    const occupancyRate = totalUnits > 0 ? occupiedUnits / totalUnits : 0;
    
    const totalUnitSize = items.reduce((sum, item) => sum + (parseFloat(String(item.unit_size)) || 0), 0);
    const payingUnitSize = payingItems.reduce((sum, item) => sum + (parseFloat(String(item.unit_size)) || 0), 0);
    const avgUnitSize = totalUnits > 0 ? totalUnitSize / totalUnits : 0;

    const totalMonthlyRent = items.reduce((sum, item) => sum + (parseFloat(String(item.current_rent)) || 0), 0);
    const totalAnnualRent = totalMonthlyRent * 12;
    
    const totalStabilizedRent = items.reduce((sum, item) => sum + (parseFloat(String(item.stabilized_rent)) || 0), 0);
    const totalMarketRent = items.reduce((sum, item) => sum + (parseFloat(String(item.market_rent)) || 0), 0);

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
      const key = item.unit_type || "Unknown";
      
      if (!groups[key]) {
        groups[key] = { count: 0, payingCount: 0, totalCurrentRent: 0, totalStabilizedRent: 0, totalMarketRent: 0, totalSqFt: 0 };
      }
      
      groups[key].count++;
      const currentRent = parseFloat(String(item.current_rent)) || 0;
      if (currentRent > 0) {
        groups[key].payingCount++;
      }
      groups[key].totalCurrentRent += currentRent;
      groups[key].totalStabilizedRent += parseFloat(String(item.stabilized_rent)) || 0;
      groups[key].totalMarketRent += parseFloat(String(item.market_rent)) || 0;
      groups[key].totalSqFt += parseFloat(String(item.unit_size)) || 0;
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
      <WarningModal
        isOpen={showWarning}
        onClose={() => setShowWarning(false)}
        title="Incomplete Data"
        message={warningMessage}
      />

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
                    errors={rowErrors[item.id]}
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
  errors,
  handleItemChange,
  formatCurrency,
  removeItem,
}: {
  item: EditableRentRollItem;
  idx: number;
  isEditing: boolean;
  errors?: Record<string, string>;
  handleItemChange: (index: number, field: keyof EditableRentRollItem, value: any) => void;
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
      className={`group hover:bg-neutral-50/50 transition-colors border-l-4 ${
        isDragging ? "bg-neutral-50 shadow-md" : "bg-white"
      } ${
        errors ? "border-l-rose-500 bg-rose-50/10" : "border-l-transparent"
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
            <div className="w-full">
              <input
                type="text"
                value={item.unit_number}
                onChange={(e) => handleItemChange(idx, "unit_number", e.target.value)}
                className={`w-full bg-white border rounded px-2 py-1 text-xs focus:ring-1 focus:outline-none ${
                  errors?.unit_number ? "border-rose-500 bg-rose-50 focus:ring-rose-500" : "border-neutral-200 focus:ring-neutral-900"
                }`}
              />
              {errors?.unit_number && <div className="text-[10px] text-rose-600 mt-1">{errors.unit_number}</div>}
            </div>
          ) : (
            item.unit_number
          )}
        </div>
      </td>
      <td className="px-4 py-2.5 text-right text-neutral-600">
        {isEditing ? (
          <div className="w-20 ml-auto">
            <input
              type="text"
              value={item.unit_size}
              onChange={(e) => handleItemChange(idx, "unit_size", e.target.value)}
              className={`w-full bg-white border rounded px-2 py-1 text-xs text-right focus:ring-1 focus:outline-none ${
                errors?.unit_size ? "border-rose-500 bg-rose-50 focus:ring-rose-500" : "border-neutral-200 focus:ring-neutral-900"
              }`}
            />
            {errors?.unit_size && <div className="text-[10px] text-rose-600 mt-1">{errors.unit_size}</div>}
          </div>
        ) : (
          item.unit_size || "-"
        )}
      </td>
      <td className="px-4 py-2.5 text-neutral-600">
        {isEditing ? (
          <div className="w-full">
            <input
              type="text"
              value={item.unit_type}
              onChange={(e) => handleItemChange(idx, "unit_type", e.target.value)}
              className={`w-full bg-white border rounded px-2 py-1 text-xs focus:ring-1 focus:outline-none ${
                errors?.unit_type ? "border-rose-500 bg-rose-50 focus:ring-rose-500" : "border-neutral-200 focus:ring-neutral-900"
              }`}
            />
            {errors?.unit_type && <div className="text-[10px] text-rose-600 mt-1">{errors.unit_type}</div>}
          </div>
        ) : (
          item.unit_type
        )}
      </td>
      <td className="px-4 py-2.5 text-right font-medium text-neutral-900">
        {isEditing ? (
          <div className="w-20 ml-auto">
            <input
              type="text"
              value={item.current_rent}
              onChange={(e) => handleItemChange(idx, "current_rent", e.target.value)}
              className="w-full bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-right focus:ring-1 focus:ring-neutral-900 focus:outline-none"
            />
          </div>
        ) : (
          formatCurrency(typeof item.current_rent === 'number' ? item.current_rent : parseFloat(item.current_rent) || 0)
        )}
      </td>
      <td className="px-4 py-2.5 text-right text-neutral-600">
        {isEditing ? (
          <div className="w-20 ml-auto">
            <input
              type="text"
              value={item.stabilized_rent}
              onChange={(e) => handleItemChange(idx, "stabilized_rent", e.target.value)}
              className={`w-full bg-white border rounded px-2 py-1 text-xs text-right focus:ring-1 focus:outline-none ${
                errors?.stabilized_rent ? "border-rose-500 bg-rose-50 focus:ring-rose-500" : "border-neutral-200 focus:ring-neutral-900"
              }`}
            />
            {errors?.stabilized_rent && <div className="text-[10px] text-rose-600 mt-1">{errors.stabilized_rent}</div>}
          </div>
        ) : (
          formatCurrency(typeof item.stabilized_rent === 'number' ? item.stabilized_rent : parseFloat(item.stabilized_rent) || 0)
        )}
      </td>
      <td className="px-4 py-2.5 text-right text-neutral-600">
        {isEditing ? (
          <div className="w-20 ml-auto">
            <input
              type="text"
              value={item.market_rent}
              onChange={(e) => handleItemChange(idx, "market_rent", e.target.value)}
              className={`w-full bg-white border rounded px-2 py-1 text-xs text-right focus:ring-1 focus:outline-none ${
                errors?.market_rent ? "border-rose-500 bg-rose-50 focus:ring-rose-500" : "border-neutral-200 focus:ring-neutral-900"
              }`}
            />
            {errors?.market_rent && <div className="text-[10px] text-rose-600 mt-1">{errors.market_rent}</div>}
          </div>
        ) : (
          formatCurrency(typeof item.market_rent === 'number' ? item.market_rent : parseFloat(item.market_rent) || 0)
        )}
      </td>
      <td className="px-4 py-2.5 text-center text-neutral-500 text-xs">
        {isEditing ? (
          <input
            type="date"
            value={toInputDate(item.move_in_date)}
            onChange={(e) => handleItemChange(idx, "move_in_date", fromInputDate(e.target.value))}
            className="w-28 mx-auto bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
          />
        ) : (
          item.move_in_date || "-"
        )}
      </td>
      <td className="px-4 py-2.5 text-center text-neutral-500 text-xs">
        {isEditing ? (
          <div className="w-28 mx-auto">
            <input
              type="date"
              value={toInputDate(item.lease_start)}
              onChange={(e) => handleItemChange(idx, "lease_start", fromInputDate(e.target.value))}
              className={`w-full bg-white border rounded px-2 py-1 text-xs text-center focus:ring-1 focus:outline-none ${
                errors?.lease_start ? "border-rose-500 bg-rose-50 focus:ring-rose-500" : "border-neutral-200 focus:ring-neutral-900"
              }`}
            />
             {errors?.lease_start && <div className="text-[10px] text-rose-600 mt-1">{errors.lease_start}</div>}
          </div>
        ) : (
          item.lease_start || "-"
        )}
      </td>
      <td className="px-4 py-2.5 text-center text-neutral-500 text-xs">
        {isEditing ? (
          <input
            type="date"
            value={toInputDate(item.lease_end)}
            onChange={(e) => handleItemChange(idx, "lease_end", fromInputDate(e.target.value))}
            className="w-28 mx-auto bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
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