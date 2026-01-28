"use client";

import React from "react";
import { RentRollItem, StudentHousingConfig } from "@/lib/types";
import WidgetTooltip from "./WidgetTooltip";

type EditableRentRollItem = Omit<RentRollItem, "unit_size" | "current_rent" | "stabilized_rent" | "market_rent"> & {
  id: string;
  unit_size: string | number;
  current_rent: string | number;
  stabilized_rent: string | number;
  market_rent: string | number;
};

interface UnitBreakdownTableProps {
  rentRoll: EditableRentRollItem[];
  studentHousingConfig?: StudentHousingConfig;
  isEditing?: boolean;
  onItemChange?: (unitType: string, field: keyof EditableRentRollItem, value: any) => void;
  formatCurrency: (val: number, decimals?: number) => string;
}

export default function UnitBreakdownTable({ rentRoll, studentHousingConfig, isEditing, onItemChange, formatCurrency }: UnitBreakdownTableProps) {
  const [localRentRoll, setLocalRentRoll] = React.useState(rentRoll);

  React.useEffect(() => {
    setLocalRentRoll(rentRoll);
  }, [rentRoll]);

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
      const avgCurrentRent = items.reduce((sum, item) => sum + (parseFloat(String(item.current_rent)) || 0), 0) / (unitCount || 1);
      const avgSize = items.reduce((sum, item) => sum + (parseFloat(String(item.unit_size)) || 0), 0) / (unitCount || 1);
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
    <div className="overflow-x-auto p-4 horizontal-scrollbar">
      <table className="min-w-full text-left text-sm whitespace-nowrap">
        <thead className="bg-neutral-900 text-white text-xs uppercase font-semibold">
          <tr>
            <th className="px-4 py-3">Unit Type</th>
            <th className="px-4 py-3 text-right">Avg Current Rent</th>
            <th className="px-4 py-3 text-right">Size</th>
            <th className="px-4 py-3 text-right">
              <div className="flex items-center justify-end">
                Total SF
                <WidgetTooltip
                  title="Total Square Feet"
                  description="The total square footage for all units of this type."
                  formulas={[{ label: "Total SF", formula: "Average Size * Unit Count" }]}
                />
              </div>
            </th>
            <th className="px-4 py-3 text-right">
              <div className="flex items-center justify-end">
                Rent / SF
                <WidgetTooltip
                  title="Rent per Square Foot"
                  description="The average monthly rent calculated on a per-square-foot basis."
                  formulas={[{ label: "Rent / SF", formula: "Average Current Rent / Average Size" }]}
                />
              </div>
            </th>
            <th className="px-4 py-3 text-center">Units</th>
            <th className="px-4 py-3 text-center">
              <div className="flex items-center justify-center">
                Mix %
                <WidgetTooltip
                  title="Unit Mix Percentage"
                  description="The percentage of this unit type relative to the total number of units."
                  formulas={[{ label: "Mix %", formula: "(Unit Count / Total Units) * 100" }]}
                />
              </div>
            </th>
            <th className="px-4 py-3 text-center">
              <div className="flex items-center justify-center">
                SF %
                <WidgetTooltip
                  title="Square Footage Percentage"
                  description="The percentage of total square footage for this unit type relative to the overall total square footage."
                  formulas={[{ label: "SF %", formula: "(Total SF / Total SF Overall) * 100" }]}
                />
              </div>
            </th>
            <th className="px-4 py-3 text-center">Beds</th>
            <th className="px-4 py-3 text-right">
              <div className="flex items-center justify-end">
                $/Beds
                <WidgetTooltip
                  title="Rent per Bed"
                  description="The average monthly rent calculated on a per-bed basis."
                  formulas={[{ label: "$/Beds", formula: "Average Current Rent / Beds" }]}
                />
              </div>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-100">
          {data.map((row, idx) => (
            <tr key={idx} className="hover:bg-neutral-50/50 transition-colors">
              <td className="px-4 py-2.5 font-medium">{row.unit_type}</td>
              <td className="px-4 py-2.5 text-right">
                {formatCurrency(row.avgCurrentRent)}
              </td>
              <td className="px-4 py-2.5 text-right">
                {row.avgSize.toFixed(0)}
              </td>
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