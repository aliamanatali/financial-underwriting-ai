"use client";

import React from "react";
import { RentRollItem, StudentHousingConfig } from "@/lib/types";

interface UnitBreakdownTableProps {
  rentRoll: RentRollItem[];
  studentHousingConfig?: StudentHousingConfig;
}

export default function UnitBreakdownTable({ rentRoll, studentHousingConfig }: UnitBreakdownTableProps) {
  const formatCurrency = (val: number, decimals = 0) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: decimals, minimumFractionDigits: decimals }).format(val);
  const formatPercent = (val: number) => new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 1 }).format(val);

  const data = React.useMemo(() => {
    if (!rentRoll) return [];

    const totalUnitsOverall = rentRoll.length;
    const totalSfOverall = rentRoll.reduce((sum, item) => sum + (item.unit_size || 0), 0);
    
    const uniqueUnitTypes = Array.from(new Set(rentRoll.map(item => item.unit_type)));

    return uniqueUnitTypes.map(unitType => {
      const items = rentRoll.filter(item => item.unit_type === unitType);
      const unitCount = items.length;
      const avgCurrentRent = items.reduce((sum, item) => sum + (item.current_rent || 0), 0) / (unitCount || 1);
      const avgSize = items.reduce((sum, item) => sum + (item.unit_size || 0), 0) / (unitCount || 1);
      const totalSf = avgSize * unitCount;
      const rentPerSf = avgCurrentRent / (avgSize || 1);
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
      const beds = totalBeds / (unitCount || 1);
      const rentPerBed = avgCurrentRent / (beds || 1);

      return {
        unit_type: unitType,
        avgCurrentRent,
        avgSize,
        totalSf,
        rentPerSf,
        unitCount,
        mixPercent,
        sfPercent,
        beds,
        rentPerBed,
      };
    });
  }, [rentRoll]);

  const totals = React.useMemo(() => {
    const totalUnits = data.reduce((sum, row) => sum + row.unitCount, 0);
    const totalSf = data.reduce((sum, row) => sum + row.totalSf, 0);
    const weightedAvgRent = data.reduce((sum, row) => sum + row.avgCurrentRent * row.unitCount, 0) / (totalUnits || 1);
    const weightedAvgSize = totalSf / (totalUnits || 1);
    const weightedAvgRentPerSf = weightedAvgRent / (weightedAvgSize || 1);
    const totalMixPercent = data.reduce((sum, row) => sum + row.mixPercent, 0);
    const totalSfPercent = data.reduce((sum, row) => sum + row.sfPercent, 0);
    const weightedAvgBeds = data.reduce((sum, row) => sum + row.beds * row.unitCount, 0) / (totalUnits || 1);
    const weightedAvgRentPerBed = weightedAvgRent / (weightedAvgBeds || 1);
    
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
    };
  }, [data]);

  return (
    <div className="overflow-x-auto p-4">
      <table className="min-w-full text-left text-sm whitespace-nowrap">
        <thead className="bg-neutral-900 text-white text-xs uppercase font-semibold">
          <tr>
            <th className="px-4 py-3">Unit Type</th>
            <th className="px-4 py-3 text-right">Avg Current Rent</th>
            <th className="px-4 py-3 text-right">Size</th>
            <th className="px-4 py-3 text-right">Total SF</th>
            <th className="px-4 py-3 text-right">Rent / SF</th>
            <th className="px-4 py-3 text-center">Units</th>
            <th className="px-4 py-3 text-center">Mix %</th>
            <th className="px-4 py-3 text-center">SF %</th>
            <th className="px-4 py-3 text-center">Beds</th>
            <th className="px-4 py-3 text-right">$/Beds</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-100">
          {data.map((row, idx) => (
            <tr key={idx} className="hover:bg-neutral-50/50 transition-colors">
              <td className="px-4 py-2.5 font-medium">{row.unit_type}</td>
              <td className="px-4 py-2.5 text-right">{formatCurrency(row.avgCurrentRent)}</td>
              <td className="px-4 py-2.5 text-right">{row.avgSize.toFixed(0)}</td>
              <td className="px-4 py-2.5 text-right">{row.totalSf.toFixed(0)}</td>
              <td className="px-4 py-2.5 text-right">{formatCurrency(row.rentPerSf, 2)}</td>
              <td className="px-4 py-2.5 text-center">{row.unitCount}</td>
              <td className="px-4 py-2.5 text-center">{formatPercent(row.mixPercent)}</td>
              <td className="px-4 py-2.5 text-center">{formatPercent(row.sfPercent)}</td>
              <td className="px-4 py-2.5 text-center">{row.beds}</td>
              <td className="px-4 py-2.5 text-right">{formatCurrency(row.rentPerBed)}</td>
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
            </tr>
        </tfoot>
      </table>
    </div>
  );
}