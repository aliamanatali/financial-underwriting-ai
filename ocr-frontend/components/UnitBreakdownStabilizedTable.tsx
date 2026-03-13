"use client";

import React from "react";
import { RentRollItem, StudentHousingConfig } from "@/lib/types";
import WidgetTooltip from "./WidgetTooltip";

type EditableRentRollItem = Omit<RentRollItem, "unit_size" | "current_rent" | "stabilized_rent" | "market_rent" | "deposit"> & {
  id: string;
  unit_size: string | number;
  current_rent: string | number;
  stabilized_rent: string | number;
  market_rent: string | number;
  deposit?: string | number;
  beds_single?: number;
  beds_double?: number;
  market_rent_single?: number;
  market_rent_double?: number;
  unit_config_label?: string;
  bed_count?: number;
  occupancy_type?: string;
};

interface UnitBreakdownTableProps {
  rentRoll: EditableRentRollItem[];
  studentHousingConfig?: StudentHousingConfig;
  isEditing?: boolean;
  onItemChange?: (unitType: string, field: keyof EditableRentRollItem, value: any) => void;
}

export default function UnitBreakdownStabilizedTable({ rentRoll, studentHousingConfig, isEditing, onItemChange }: UnitBreakdownTableProps) {
  const [localRentRoll, setLocalRentRoll] = React.useState(rentRoll);

  // Initialize localRentRoll with config values when editing starts or config/rentRoll changes
  React.useEffect(() => {
    if (isEditing && studentHousingConfig) {
        setLocalRentRoll(prev => prev.map(item => {
            const config = studentHousingConfig.unit_type_configs.find(c => c.unit_type?.trim().toLowerCase() === item.unit_type?.trim().toLowerCase());
            if (config) {
                // Determine default bed count if not set
                let defaultBeds = 1;
                if (!config.bed_count) {
                    const type = item.unit_type || "";
                    const match = type.match(/(\d+)\s*(?:bd|br|bed|bedroom)/i);
                    if (match) {
                        defaultBeds = parseInt(match[1]);
                    } else if (type.toLowerCase().includes("studio")) {
                        defaultBeds = 1;
                    } else {
                        const startMatch = type.match(/^(\d+)/);
                        if (startMatch) defaultBeds = parseInt(startMatch[1]);
                    }
                }

                return {
                    ...item,
                    beds_single: item.beds_single ?? config.beds_single,
                    beds_double: item.beds_double ?? config.beds_double,
                    market_rent_single: item.market_rent_single ?? config.market_rent_single,
                    market_rent_double: item.market_rent_double ?? config.market_rent_double,
                    unit_config_label: item.unit_config_label ?? config.unit_config_label,
                    bed_count: item.bed_count ?? (config.bed_count || defaultBeds),
                    occupancy_type: item.occupancy_type ?? config.occupancy_type
                };
            }
            return item;
        }));
    } else {
        setLocalRentRoll(rentRoll);
    }
  }, [rentRoll, isEditing, studentHousingConfig]);

  const formatCurrency = (val: number, decimals = 0) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: decimals, minimumFractionDigits: decimals }).format(Math.round(val));
  const formatPercent = (val: number) => new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Math.round(val));

  const handleNumericChange = (unitType: string, field: keyof EditableRentRollItem, value: string) => {
    const numericValue = value.replace(/[^0-9.]/g, '');
    if (onItemChange) {
      onItemChange(unitType, field, numericValue);
    }
  };
 
   const handleLocalChange = (unitType: string, field: keyof EditableRentRollItem, value: any) => {
    // Calculate new state first
    const updated = localRentRoll.map(item => {
        if (item.unit_type === unitType) {
            let newItem = { ...item, [field]: value };

            // UX Improvement: Auto-update label if it matches the occupancy type
            if (field === "occupancy_type") {
                // If label was same as old occupancy (default), update it to new occupancy
                if (item.unit_config_label === item.occupancy_type) {
                    newItem.unit_config_label = value;
                }

                // Intelligent Preset for Mixed/Single/Double Logic
                if (value === "Single") {
                    newItem.beds_single = newItem.bed_count;
                    newItem.beds_double = 0;
                } else if (value === "Double") {
                    newItem.beds_single = 0;
                    newItem.beds_double = newItem.bed_count;
                }
                // For "Mixed", we leave values as-is
                if (!newItem.beds_single) newItem.beds_single = 0;
                if (!newItem.beds_double) newItem.beds_double = 0;
            }

            // UX Improvement: If bed count changes, auto-update sub-counts if strictly Single or Double
            if (field === "bed_count") {
                if (newItem.occupancy_type === "Single") {
                    newItem.beds_single = value;
                } else if (newItem.occupancy_type === "Double") {
                    newItem.beds_double = value;
                }
            }

            return newItem;
        }
        return item;
    });

    // Set local state
    setLocalRentRoll(updated);
    
    // Propagate changes to parent outside of state updater
    const updatedItem = updated.find(i => i.unit_type === unitType);
    if (updatedItem && onItemChange) {
        onItemChange(unitType, field, value);
        if (field === "occupancy_type") {
            onItemChange(unitType, "unit_config_label", updatedItem.unit_config_label);
            onItemChange(unitType, "beds_single", updatedItem.beds_single);
            onItemChange(unitType, "beds_double", updatedItem.beds_double);
        }
        if (field === "bed_count") {
            onItemChange(unitType, "beds_single", updatedItem.beds_single);
            onItemChange(unitType, "beds_double", updatedItem.beds_double);
        }
    }
  };

   const data = React.useMemo(() => {
     const sourceData = isEditing ? localRentRoll : rentRoll;
    if (!sourceData) return [];

    const totalUnitsOverall = sourceData.length;
    const totalSfOverall = sourceData.reduce((sum, item) => sum + (parseFloat(String(item.unit_size)) || 0), 0);
    
    const uniqueUnitTypes = Array.from(new Set(sourceData.map(item => item.unit_type)));

    return uniqueUnitTypes.map(unitType => {
      const items = sourceData.filter(item => item.unit_type === unitType);
      const unitCount = items.length;
      const avgMarketRent = items.reduce((sum, item) => sum + (parseFloat(String(item.market_rent)) || 0), 0) / (unitCount || 1);
      const avgSize = items.reduce((sum, item) => sum + (parseFloat(String(item.unit_size)) || 0), 0) / (unitCount || 1);
      const totalSf = avgSize * unitCount;
      const rentPerSf = avgMarketRent / (avgSize || 1);
      const mixPercent = unitCount / (totalUnitsOverall || 1);
      const sfPercent = totalSf / (totalSfOverall || 1);

      const getBedCount = (unit_type: string): number => {
          if (!unit_type) return 1;
          const u_type = unit_type.toLowerCase();
          
          const match_bd = u_type.match(/(\d+)\s*(?:bd|br|bed)/);
          if (match_bd) return parseInt(match_bd[1], 10);
          
          if (u_type.includes("studio")) return 1;
          
          const match_slash = u_type.match(/^(\d+)\s*\//);
          if (match_slash) {
              const val = parseInt(match_slash[1], 10);
              return val > 0 ? val : 1;
          }
          
          const match_digit = u_type.match(/\d+/);
          if (match_digit) return parseInt(match_digit[0], 10);

          return 1;
      };

      const totalBeds = items.reduce((sum, item) => sum + getBedCount(item.unit_type), 0);
      let beds = totalBeds / (unitCount || 1);
      const rentPerBed = avgMarketRent / (beds || 1);

      // Prioritize localRentRoll if we have values (especially during editing)
      // Otherwise fall back to config
      const sampleItem = items[0]; // All items in this group should have same type-level config
      
      const conf_obj = studentHousingConfig?.unit_type_configs.find(c => c.unit_type?.trim().toLowerCase() === unitType?.trim().toLowerCase());
      
      const occupancy = sampleItem?.occupancy_type || conf_obj?.occupancy_type || "Single";
      const label = sampleItem?.unit_config_label || conf_obj?.unit_config_label || "Single";
      const bed_count = sampleItem?.bed_count || conf_obj?.bed_count || 0;
      
      const beds_s = sampleItem?.beds_single ?? (conf_obj?.beds_single ?? 0);
      const beds_d = sampleItem?.beds_double ?? (conf_obj?.beds_double ?? 0);
      const price_s = sampleItem?.market_rent_single ?? (conf_obj?.market_rent_single ?? 0);
      const price_d = sampleItem?.market_rent_double ?? (conf_obj?.market_rent_double ?? 0);

      if (beds_s > 0 || beds_d > 0) {
        beds = beds_s + beds_d;
      }

      let config_str = "";
      const parts = [];
      if (beds_s > 0) parts.push(`${beds_s} Single`);
      if (beds_d > 0) parts.push(`${beds_d} Double`);
      config_str = parts.join(", ");
      if (!config_str) {
        config_str = `${conf_obj?.bed_count || 0} ${label}`;
      }

      return {
        unit_type: unitType,
        avgMarketRent,
        avgSize,
        totalSf,
        rentPerSf,
        unitCount,
        mixPercent,
        sfPercent,
        beds,
        rentPerBed,
        beds_s,
        beds_d,
        price_s,
        price_d,
        config_str,
        occupancy,
        bed_count
      };
    });
  }, [rentRoll, studentHousingConfig, localRentRoll, isEditing]);

  const totals = React.useMemo(() => {
    const totalUnits = data.reduce((sum, row) => sum + row.unitCount, 0);
    const totalSf = data.reduce((sum, row) => sum + row.totalSf, 0);
    const weightedAvgRent = data.reduce((sum, row) => sum + row.avgMarketRent * row.unitCount, 0) / (totalUnits || 1);
    const weightedAvgSize = totalSf / (totalUnits || 1);
    const weightedAvgRentPerSf = weightedAvgRent / (weightedAvgSize || 1);
    const totalMixPercent = data.reduce((sum, row) => sum + row.mixPercent, 0);
    const totalSfPercent = data.reduce((sum, row) => sum + row.sfPercent, 0);
    const weightedAvgBeds = data.reduce((sum, row) => sum + row.beds * row.unitCount, 0) / (totalUnits || 1);
    const weightedAvgRentPerBed = weightedAvgRent / (weightedAvgBeds || 1);
    const totalBedsSingle = data.reduce((sum, row) => sum + (row.beds_s || 0), 0);
    const totalBedsDouble = data.reduce((sum, row) => sum + (row.beds_d || 0), 0);
    const totalMarketRentSingle = data.reduce((sum, row) => sum + (row.price_s || 0), 0);
    const totalMarketRentDouble = data.reduce((sum, row) => sum + (row.price_d || 0), 0);
    
    return {
      totalUnits,
      weightedAvgRent,
      weightedAvgSize,
      totalSf,
      weightedAvgRentPerSf,
      totalMixPercent,
      totalSfPercent,
      weightedAvgBeds,
      weightedAvgRentPerBed,
      totalBedsSingle,
      totalBedsDouble,
      totalMarketRentSingle,
      totalMarketRentDouble,
    };
  }, [data]);

  return (
    <div className="overflow-x-auto p-4 horizontal-scrollbar">
      <table className="min-w-full text-center text-sm whitespace-nowrap">
        <thead className="bg-neutral-900 text-white text-xs uppercase font-semibold">
          <tr className="whitespace-nowrap">
            <th className="px-4 py-3 text-center">Unit Type</th>
            <th className="px-4 py-3 text-center">Pro Forma Rent</th>
            <th className="px-4 py-3 text-center">
              <div className="flex items-center justify-center gap-1">
                Size
                <WidgetTooltip
                  title="Average Unit Size"
                  description="The average square footage of units in this category."
                  formulas={[{ label: "Avg Size", formula: "Sum of Unit Sizes / Unit Count" }]}
                />
              </div>
            </th>
            <th className="px-4 py-3 text-center">
              <div className="flex items-center justify-center gap-1">
                Total SF
                <WidgetTooltip
                  title="Total Square Feet"
                  description="The total square footage for all units of this type."
                  formulas={[{ label: "Total SF", formula: "Average Size * Unit Count" }]}
                />
              </div>
            </th>
            <th className="px-4 py-3 text-center">
              <div className="flex items-center justify-center gap-1">
                Rent / SF
                <WidgetTooltip
                  title="Rent per Square Foot"
                  description="The average pro forma monthly rent calculated on a per-square-foot basis."
                  formulas={[{ label: "Rent / SF", formula: "Average Market Rent / Average Size" }]}
                />
              </div>
            </th>
            <th className="px-4 py-3 text-center">Units</th>
            <th className="px-4 py-3 text-center">
              <div className="flex items-center justify-center gap-1">
                Mix %
                <WidgetTooltip
                  title="Unit Mix Percentage"
                  description="The percentage of this unit type relative to the total number of units."
                  formulas={[{ label: "Mix %", formula: "(Unit Count / Total Units) * 100" }]}
                />
              </div>
            </th>
            <th className="px-4 py-3 text-center">
              <div className="flex items-center justify-center gap-1">
                SF %
                <WidgetTooltip
                  title="Square Footage Percentage"
                  description="The percentage of total square footage for this unit type relative to the overall total square footage."
                  formulas={[{ label: "SF %", formula: "(Total SF / Total SF Overall) * 100" }]}
                />
              </div>
            </th>
            <th className="px-4 py-3 text-center">Beds</th>
            <th className="px-4 py-3 text-center">
              <div className="flex items-center justify-center gap-1">
                $/Beds
                <WidgetTooltip
                  title="Rent per Bed"
                  description="The average pro forma monthly rent calculated on a per-bed basis."
                  formulas={[{ label: "$/Beds", formula: "Average Market Rent / Beds" }]}
                />
              </div>
            </th>
            <th className="px-4 py-3 text-center">Bed Count</th>
            <th className="px-4 py-3 text-center">Occupancy Type</th>
            <th className="px-4 py-3 text-center">Single</th>
            <th className="px-4 py-3 text-center">Double</th>
            <th className="px-4 py-3 text-center">Single $</th>
            <th className="px-4 py-3 text-center">Double $</th>
            <th className="px-4 py-3 text-center">Unit Config</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-100">
          {data.map((row, idx) => (
            <tr key={idx} className="hover:bg-neutral-50/50 transition-colors">
              <td className="px-4 py-2.5 font-medium text-center">{row.unit_type}</td>
              <td className="px-4 py-2.5 text-center">
                {isEditing && onItemChange ? (
                  <input
                    type="text"
                    value={localRentRoll.find(item => item.unit_type === row.unit_type)?.market_rent || ''}
                    onChange={(e) => handleLocalChange(row.unit_type, "market_rent", e.target.value)}
                    className="w-24 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
                  />
                ) : (
                  formatCurrency(row.avgMarketRent)
                )}
              </td>
              <td className="px-4 py-2.5 text-center">
                {row.avgSize.toFixed(0)}
              </td>
              <td className="px-4 py-2.5 text-center">{row.totalSf.toFixed(0)}</td>
              <td className="px-4 py-2.5 text-center">{formatCurrency(row.rentPerSf, 2)}</td>
              <td className="px-4 py-2.5 text-center">{row.unitCount}</td>
              <td className="px-4 py-2.5 text-center">{formatPercent(row.mixPercent)}</td>
              <td className="px-4 py-2.5 text-center">{formatPercent(row.sfPercent)}</td>
              <td className="px-4 py-2.5 text-center">{row.beds}</td>
              <td className="px-4 py-2.5 text-center">{formatCurrency(row.rentPerBed)}</td>
              <td className="px-4 py-2.5 text-center">
                  {isEditing && onItemChange ? (
                      <input
                        type="text"
                        value={localRentRoll.find(item => item.unit_type === row.unit_type)?.bed_count || ''}
                        onChange={(e) => handleLocalChange(row.unit_type, "bed_count" as any, parseInt(e.target.value) || 0)}
                        className="w-16 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
                      />
                  ) : (
                      row.bed_count || "-"
                  )}
              </td>
              <td className="px-4 py-2.5 text-center">
                   {isEditing && onItemChange ? (
                      <select
                          value={localRentRoll.find(item => item.unit_type === row.unit_type)?.occupancy_type || 'Single'}
                          onChange={(e) => handleLocalChange(row.unit_type, "occupancy_type" as any, e.target.value)}
                          className="w-24 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
                      >
                          <option value="Single">Single</option>
                          <option value="Double">Double</option>
                          <option value="Mixed">Mixed</option>
                      </select>
                  ) : (
                      row.occupancy || "Single"
                  )}
              </td>
              <td className="px-4 py-2.5 text-center">
                {isEditing && onItemChange ? (
                  <input
                    type="text"
                    value={localRentRoll.find(item => item.unit_type === row.unit_type)?.beds_single || ''}
                    onChange={(e) => handleLocalChange(row.unit_type, "beds_single" as any, parseInt(e.target.value) || 0)}
                    disabled={(localRentRoll.find(item => item.unit_type === row.unit_type)?.occupancy_type || 'Single') === "Double"}
                    className={`w-16 border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none ${(localRentRoll.find(item => item.unit_type === row.unit_type)?.occupancy_type || 'Single') === "Double" ? "bg-neutral-100 text-neutral-400" : "bg-white"}`}
                  />
                ) : (
                  row.beds_s > 0 ? row.beds_s : "-"
                )}
              </td>
              <td className="px-4 py-2.5 text-center">
                {isEditing && onItemChange ? (
                  <input
                    type="text"
                    value={localRentRoll.find(item => item.unit_type === row.unit_type)?.beds_double || ''}
                    onChange={(e) => handleLocalChange(row.unit_type, "beds_double" as any, parseInt(e.target.value) || 0)}
                    disabled={(localRentRoll.find(item => item.unit_type === row.unit_type)?.occupancy_type || 'Single') === "Single"}
                    className={`w-16 border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none ${(localRentRoll.find(item => item.unit_type === row.unit_type)?.occupancy_type || 'Single') === "Single" ? "bg-neutral-100 text-neutral-400" : "bg-white"}`}
                  />
                ) : (
                  row.beds_d > 0 ? row.beds_d : "-"
                )}
              </td>
              <td className="px-4 py-2.5 text-center">
                {isEditing && onItemChange ? (
                  <input
                    type="text"
                    value={localRentRoll.find(item => item.unit_type === row.unit_type)?.market_rent_single || ''}
                    onChange={(e) => handleLocalChange(row.unit_type, "market_rent_single" as any, parseFloat(e.target.value) || 0)}
                    disabled={(localRentRoll.find(item => item.unit_type === row.unit_type)?.occupancy_type || 'Single') === "Double"}
                    className={`w-24 border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none ${(localRentRoll.find(item => item.unit_type === row.unit_type)?.occupancy_type || 'Single') === "Double" ? "bg-neutral-100 text-neutral-400" : "bg-white"}`}
                  />
                ) : (
                  row.price_s > 0 ? formatCurrency(row.price_s) : (row.beds_s > 0 ? formatCurrency(row.rentPerBed) : "-")
                )}
              </td>
              <td className="px-4 py-2.5 text-center">
                {isEditing && onItemChange ? (
                  <input
                    type="text"
                    value={localRentRoll.find(item => item.unit_type === row.unit_type)?.market_rent_double || ''}
                    onChange={(e) => handleLocalChange(row.unit_type, "market_rent_double" as any, parseFloat(e.target.value) || 0)}
                    disabled={(localRentRoll.find(item => item.unit_type === row.unit_type)?.occupancy_type || 'Single') === "Single"}
                    className={`w-24 border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none ${(localRentRoll.find(item => item.unit_type === row.unit_type)?.occupancy_type || 'Single') === "Single" ? "bg-neutral-100 text-neutral-400" : "bg-white"}`}
                  />
                ) : (
                  row.price_d > 0 ? formatCurrency(row.price_d) : (row.beds_d > 0 ? formatCurrency(row.rentPerBed) : "-")
                )}
              </td>
              <td className="px-4 py-2.5 text-center">
                {isEditing && onItemChange ? (
                  <input type="text" value={localRentRoll.find(item => item.unit_type === row.unit_type)?.unit_config_label || ''} onChange={(e) => handleLocalChange(row.unit_type, "unit_config_label" as any, e.target.value)} className="w-24 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none" />
                ) : (
                  row.config_str
                )}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot className="bg-neutral-900 text-white border-t-2 border-neutral-800 font-bold">
            <tr>
                <td className="px-4 py-3 text-center">Total / Wtd Avg</td>
                <td className="px-4 py-3 text-center">{formatCurrency(totals.weightedAvgRent)}</td>
                <td className="px-4 py-3 text-center">{totals.weightedAvgSize.toFixed(0)}</td>
                <td className="px-4 py-3 text-center">{totals.totalSf.toFixed(0)}</td>
                <td className="px-4 py-3 text-center">{formatCurrency(totals.weightedAvgRentPerSf, 2)}</td>
                <td className="px-4 py-3 text-center">{totals.totalUnits}</td>
                <td className="px-4 py-3 text-center">{formatPercent(totals.totalMixPercent)}</td>
                <td className="px-4 py-3 text-center">{formatPercent(totals.totalSfPercent)}</td>
                <td className="px-4 py-3 text-center">{totals.weightedAvgBeds.toFixed(1)}</td>
                <td className="px-4 py-3 text-center">{formatCurrency(totals.weightedAvgRentPerBed)}</td>
                <td className="px-4 py-3 text-center">-</td>
                <td className="px-4 py-3 text-center">-</td>
                <td className="px-4 py-3 text-center">{totals.totalBedsSingle}</td>
                <td className="px-4 py-3 text-center">{totals.totalBedsDouble}</td>
                <td className="px-4 py-3 text-center">{formatCurrency(totals.totalMarketRentSingle)}</td>
                <td className="px-4 py-3 text-center">{formatCurrency(totals.totalMarketRentDouble)}</td>
                <td className="px-4 py-3 text-center">-</td>
            </tr>
        </tfoot>
      </table>
    </div>
  );
}