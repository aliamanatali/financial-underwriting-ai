"use client";

import React from "react";
import { RentRollItem, StudentHousingConfig } from "@/lib/types";

type EditableRentRollItem = Omit<RentRollItem, "unit_size" | "current_rent" | "stabilized_rent" | "market_rent"> & {
  id: string;
  unit_size: string | number;
  current_rent: string | number;
  stabilized_rent: string | number;
  market_rent: string | number;
  beds_single?: number;
  beds_double?: number;
  market_rent_single?: number;
  market_rent_double?: number;
  unit_config_label?: string;
};

interface UnitBreakdownTableProps {
  rentRoll: EditableRentRollItem[];
  studentHousingConfig?: StudentHousingConfig;
  isEditing?: boolean;
  onItemChange?: (unitType: string, field: keyof EditableRentRollItem, value: any) => void;
}

export default function UnitBreakdownStabilizedTable({ rentRoll, studentHousingConfig, isEditing, onItemChange }: UnitBreakdownTableProps) {
  const [localRentRoll, setLocalRentRoll] = React.useState(rentRoll);

  React.useEffect(() => {
    setLocalRentRoll(rentRoll);
  }, [rentRoll]);

  const formatCurrency = (val: number, decimals = 0) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: decimals, minimumFractionDigits: decimals }).format(val);
  const formatPercent = (val: number) => new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 1 }).format(val);

  const handleNumericChange = (unitType: string, field: keyof EditableRentRollItem, value: string) => {
    const numericValue = value.replace(/[^0-9.]/g, '');
    if (onItemChange) {
      onItemChange(unitType, field, numericValue);
    }
  };
 
   const handleLocalChange = (unitType: string, field: keyof EditableRentRollItem, value: any) => {
    setLocalRentRoll(prev =>
      prev.map(item =>
        item.unit_type === unitType ? { ...item, [field]: value } : item
      )
    );
    if (onItemChange) {
      onItemChange(unitType, field, value);
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

      const conf_obj = studentHousingConfig?.unit_type_configs.find(c => c.unit_type === unitType);
      const occupancy = conf_obj?.occupancy_type || "Single";
      const label = conf_obj?.unit_config_label || "Single";
      const beds_s = conf_obj?.beds_single ?? 0;
      const beds_d = conf_obj?.beds_double ?? 0;
      const price_s = conf_obj?.market_rent_single ?? 0;
      const price_d = conf_obj?.market_rent_double ?? 0;

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
      };
    });
  }, [rentRoll, studentHousingConfig]);

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
      <table className="min-w-full text-left text-sm whitespace-nowrap">
        <thead className="bg-neutral-900 text-white text-xs uppercase font-semibold">
          <tr>
            <th className="px-4 py-3">Unit Type</th>
            <th className="px-4 py-3 text-right">Pro Forma Rent</th>
            <th className="px-4 py-3 text-right">Size</th>
            <th className="px-4 py-3 text-right">Total SF</th>
            <th className="px-4 py-3 text-right">Rent / SF</th>
            <th className="px-4 py-3 text-center">Units</th>
            <th className="px-4 py-3 text-center">Mix %</th>
            <th className="px-4 py-3 text-center">SF %</th>
            <th className="px-4 py-3 text-center">Beds</th>
            <th className="px-4 py-3 text-right">$/Beds</th>
            <th className="px-4 py-3 text-center">Single</th>
            <th className="px-4 py-3 text-center">Double</th>
            <th className="px-4 py-3 text-right">Single $</th>
            <th className="px-4 py-3 text-right">Double $</th>
            <th className="px-4 py-3 text-center">Unit Config</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-100">
          {data.map((row, idx) => (
            <tr key={idx} className="hover:bg-neutral-50/50 transition-colors">
              <td className="px-4 py-2.5 font-medium">{row.unit_type}</td>
              <td className="px-4 py-2.5 text-right">
                {isEditing && onItemChange ? (
                  <input
                    type="text"
                    value={localRentRoll.find(item => item.unit_type === row.unit_type)?.market_rent || ''}
                    onChange={(e) => handleLocalChange(row.unit_type, "market_rent", e.target.value)}
                    className="w-24 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-right focus:ring-1 focus:ring-neutral-900 focus:outline-none"
                  />
                ) : (
                  formatCurrency(row.avgMarketRent)
                )}
              </td>
              <td className="px-4 py-2.5 text-right">
                {isEditing && onItemChange ? (
                  <input
                    type="text"
                    value={localRentRoll.find(item => item.unit_type === row.unit_type)?.unit_size || ''}
                    onChange={(e) => handleLocalChange(row.unit_type, "unit_size", e.target.value)}
                    className="w-20 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-right focus:ring-1 focus:ring-neutral-900 focus:outline-none"
                  />
                ) : (
                  row.avgSize.toFixed(0)
                )}
              </td>
              <td className="px-4 py-2.5 text-right">{row.totalSf.toFixed(0)}</td>
              <td className="px-4 py-2.5 text-right">{formatCurrency(row.rentPerSf, 2)}</td>
              <td className="px-4 py-2.5 text-center">{row.unitCount}</td>
              <td className="px-4 py-2.5 text-center">{formatPercent(row.mixPercent)}</td>
              <td className="px-4 py-2.5 text-center">{formatPercent(row.sfPercent)}</td>
              <td className="px-4 py-2.5 text-center">{row.beds}</td>
              <td className="px-4 py-2.5 text-right">{formatCurrency(row.rentPerBed)}</td>
              <td className="px-4 py-2.5 text-center">
                {isEditing && onItemChange ? (
                  <input type="text" value={localRentRoll.find(item => item.unit_type === row.unit_type)?.beds_single || ''} onChange={(e) => handleLocalChange(row.unit_type, "beds_single" as any, e.target.value)} className="w-16 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none" />
                ) : (
                  row.beds_s > 0 ? row.beds_s : "-"
                )}
              </td>
              <td className="px-4 py-2.5 text-center">
                {isEditing && onItemChange ? (
                  <input type="text" value={localRentRoll.find(item => item.unit_type === row.unit_type)?.beds_double || ''} onChange={(e) => handleLocalChange(row.unit_type, "beds_double" as any, e.target.value)} className="w-16 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none" />
                ) : (
                  row.beds_d > 0 ? row.beds_d : "-"
                )}
              </td>
              <td className="px-4 py-2.5 text-right">
                {isEditing && onItemChange ? (
                  <input type="text" value={localRentRoll.find(item => item.unit_type === row.unit_type)?.market_rent_single || ''} onChange={(e) => handleLocalChange(row.unit_type, "market_rent_single" as any, e.target.value)} className="w-24 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-right focus:ring-1 focus:ring-neutral-900 focus:outline-none" />
                ) : (
                  row.price_s > 0 ? formatCurrency(row.price_s) : (row.beds_s > 0 ? formatCurrency(row.rentPerBed) : "-")
                )}
              </td>
              <td className="px-4 py-2.5 text-right">
                {isEditing && onItemChange ? (
                  <input type="text" value={localRentRoll.find(item => item.unit_type === row.unit_type)?.market_rent_double || ''} onChange={(e) => handleLocalChange(row.unit_type, "market_rent_double" as any, e.target.value)} className="w-24 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-right focus:ring-1 focus:ring-neutral-900 focus:outline-none" />
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
                <td className="px-4 py-3">Total / Wtd Avg</td>
                <td className="px-4 py-3 text-right">{formatCurrency(totals.weightedAvgRent)}</td>
                <td className="px-4 py-3 text-right">{totals.weightedAvgSize.toFixed(0)}</td>
                <td className="px-4 py-3 text-right">{totals.totalSf.toFixed(0)}</td>
                <td className="px-4 py-3 text-right">{formatCurrency(totals.weightedAvgRentPerSf, 2)}</td>
                <td className="px-4 py-3 text-center">{totals.totalUnits}</td>
                <td className="px-4 py-3 text-center">{formatPercent(totals.totalMixPercent)}</td>
                <td className="px-4 py-3 text-center">{formatPercent(totals.totalSfPercent)}</td>
                <td className="px-4 py-3 text-center">{totals.weightedAvgBeds.toFixed(1)}</td>
                <td className="px-4 py-3 text-right">{formatCurrency(totals.weightedAvgRentPerBed)}</td>
                <td className="px-4 py-3 text-center">{totals.totalBedsSingle}</td>
                <td className="px-4 py-3 text-center">{totals.totalBedsDouble}</td>
                <td className="px-4 py-3 text-right">{formatCurrency(totals.totalMarketRentSingle)}</td>
                <td className="px-4 py-3 text-right">{formatCurrency(totals.totalMarketRentDouble)}</td>
                <td className="px-4 py-3 text-center">-</td>
            </tr>
        </tfoot>
      </table>
    </div>
  );
}