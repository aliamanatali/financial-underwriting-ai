import React, { useState, useEffect } from "react";
import { RentRollItem, StudentHousingConfig, UnderwritingAnalysis, UnitTypeConfig } from "@/lib/types";
import { apiClient } from "@/lib/api";

interface RentRollExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  analysis: UnderwritingAnalysis;
}

export default function RentRollExportModal({
  isOpen,
  onClose,
  analysis,
}: RentRollExportModalProps) {
  const [rentRoll, setRentRoll] = useState<RentRollItem[]>(analysis.rent_roll || []);
  const [isExporting, setIsExporting] = useState(false);
  
  // Config State: List of configs per unit type
  const [config, setConfig] = useState<StudentHousingConfig>({
    unit_type_configs: []
  });

  // Initialize on open
  useEffect(() => {
    if (isOpen) {
        const items = analysis.rent_roll || [];
        setRentRoll(items);
        // We don't initialize config here, we do it in a separate effect that watches rentRoll
        // but we need to ensure we don't overwrite if it was already set?
        // Actually, for a fresh modal open, we want fresh config based on fresh rent roll.
        // But if we are re-opening? The state is local to this component, so it resets on unmount/remount?
        // Yes, if parent conditionally renders it. If hidden via CSS, state persists.
        // Assuming conditionally rendered or reset via key.
    }
  }, [isOpen, analysis.rent_roll]);

  // Sync Config with Rent Roll State
  useEffect(() => {
      syncConfigWithRentRoll(rentRoll);
  }, [rentRoll]);

  // Helper to sync configs while preserving existing settings
  const syncConfigWithRentRoll = (items: RentRollItem[]) => {
      const uniqueTypes = Array.from(new Set(items.map(i => i.unit_type || "Unknown"))).sort();
      
      setConfig(prevConfig => {
          const existingConfigs = prevConfig.unit_type_configs;
          const newConfigs: UnitTypeConfig[] = uniqueTypes.map(type => {
              // Check if we already have a config for this type
              const existing = existingConfigs.find(c => c.unit_type === type);
              if (existing) return existing;

              // Otherwise create default
              let beds = 1;
              const match = type.match(/(\d+)/);
              if (match) beds = parseInt(match[1]);
              if (type.toLowerCase().includes("studio")) beds = 1;

              return {
                  unit_type: type,
                  bed_count: beds,
                  occupancy_type: "Single",
                  unit_config_label: "Single"
              };
          });
          
          return { unit_type_configs: newConfigs };
      });
  };

  const handleItemChange = (index: number, field: keyof RentRollItem, value: any) => {
    const newItems = [...rentRoll];
    newItems[index] = {
      ...newItems[index],
      [field]: ["current_rent", "market_rent", "stabilized_rent", "unit_size"].includes(field) ? parseFloat(value) || 0 : value,
    };
    setRentRoll(newItems);
  };

  const handleConfigChange = (index: number, field: keyof UnitTypeConfig, value: any) => {
      const newConfigs = [...config.unit_type_configs];
      newConfigs[index] = {
          ...newConfigs[index],
          [field]: value
      };
      setConfig({ unit_type_configs: newConfigs });
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      // Create a temporary analysis object with overrides
      const exportPayload = {
        ...analysis,
        rent_roll: rentRoll,
        student_housing_config: config,
      };

      await apiClient.downloadExport(exportPayload, "rent-roll");
      onClose();
    } catch (error) {
      console.error("Export failed:", error);
      alert("Failed to export Rent Roll.");
    } finally {
      setIsExporting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-6xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-neutral-200 flex justify-between items-center bg-neutral-50">
          <div>
            <h2 className="text-xl font-bold text-neutral-900">Export Rent Roll</h2>
            <p className="text-sm text-neutral-500">Review data and configure export settings</p>
          </div>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6 bg-neutral-50/30 space-y-6">
            
            {/* Rent Roll Table Section */}
            <div className="bg-white border border-neutral-200 rounded-lg shadow-sm overflow-hidden flex flex-col">
                <div className="px-6 py-4 border-b border-neutral-200 bg-neutral-50/50">
                    <h3 className="text-lg font-bold text-neutral-900">1. Edit Rent Roll</h3>
                    <p className="text-sm text-neutral-500">Modify unit details before export</p>
                </div>
                <div className="overflow-x-auto max-h-[40vh]">
                <table className="w-full text-sm text-left">
                    <thead className="bg-neutral-100 text-neutral-600 text-xs uppercase font-semibold sticky top-0 z-10 shadow-sm">
                    <tr>
                        <th className="px-4 py-3">Unit #</th>
                        <th className="px-4 py-3">Unit Type</th>
                        <th className="px-4 py-3 text-right">Size (SF)</th>
                        <th className="px-4 py-3 text-right">Current Rent</th>
                        <th className="px-4 py-3 text-right">Market Rent</th>
                        <th className="px-4 py-3">Lease Start</th>
                        <th className="px-4 py-3">Lease End</th>
                    </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-100">
                    {rentRoll.map((item, idx) => (
                        <tr key={idx} className="hover:bg-neutral-50 transition-colors">
                        <td className="px-4 py-2">
                            <input
                            type="text"
                            value={item.unit_number}
                            onChange={(e) => handleItemChange(idx, "unit_number", e.target.value)}
                            className="w-full bg-transparent border border-transparent hover:border-neutral-300 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded px-2 py-1 outline-none"
                            />
                        </td>
                        <td className="px-4 py-2">
                            <input
                            type="text"
                            value={item.unit_type}
                            onChange={(e) => handleItemChange(idx, "unit_type", e.target.value)}
                            className="w-full bg-transparent border border-transparent hover:border-neutral-300 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded px-2 py-1 outline-none"
                            />
                        </td>
                        <td className="px-4 py-2">
                            <input
                            type="number"
                            value={item.unit_size}
                            onChange={(e) => handleItemChange(idx, "unit_size", e.target.value)}
                            className="w-full text-right bg-transparent border border-transparent hover:border-neutral-300 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded px-2 py-1 outline-none"
                            />
                        </td>
                        <td className="px-4 py-2">
                            <input
                            type="number"
                            value={item.current_rent}
                            onChange={(e) => handleItemChange(idx, "current_rent", e.target.value)}
                            className="w-full text-right bg-transparent border border-transparent hover:border-neutral-300 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded px-2 py-1 outline-none"
                            />
                        </td>
                        <td className="px-4 py-2">
                            <input
                            type="number"
                            value={item.market_rent}
                            onChange={(e) => handleItemChange(idx, "market_rent", e.target.value)}
                            className="w-full text-right bg-transparent border border-transparent hover:border-neutral-300 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded px-2 py-1 outline-none"
                            />
                        </td>
                        <td className="px-4 py-2">
                            <input
                            type="text"
                            value={item.lease_start || ""}
                            placeholder="YYYY-MM-DD"
                            onChange={(e) => handleItemChange(idx, "lease_start", e.target.value)}
                            className="w-full bg-transparent border border-transparent hover:border-neutral-300 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded px-2 py-1 outline-none"
                            />
                        </td>
                        <td className="px-4 py-2">
                            <input
                            type="text"
                            value={item.lease_end || ""}
                            placeholder="YYYY-MM-DD"
                            onChange={(e) => handleItemChange(idx, "lease_end", e.target.value)}
                            className="w-full bg-transparent border border-transparent hover:border-neutral-300 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded px-2 py-1 outline-none"
                            />
                        </td>
                        </tr>
                    ))}
                    </tbody>
                </table>
                </div>
            </div>

            {/* Configuration Section - Dynamic Table */}
            <div className="bg-white border border-neutral-200 rounded-lg shadow-sm overflow-hidden flex flex-col">
                <div className="px-6 py-4 border-b border-neutral-200 bg-neutral-50/50">
                    <h3 className="text-lg font-bold text-neutral-900">2. Student Housing Assumptions</h3>
                    <p className="text-sm text-neutral-500">Configure assumptions for each Unit Type found in the Rent Roll</p>
                </div>
                
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-neutral-100 text-neutral-600 text-xs uppercase font-semibold">
                            <tr>
                                <th className="px-6 py-3">Unit Type</th>
                                <th className="px-6 py-3">Bed Count</th>
                                <th className="px-6 py-3">Occupancy Type</th>
                                <th className="px-6 py-3">Unit Config Label</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-neutral-100">
                            {config.unit_type_configs.map((conf, idx) => (
                                <tr key={idx} className="hover:bg-neutral-50 transition-colors">
                                    <td className="px-6 py-3 font-medium text-neutral-900">
                                        {conf.unit_type}
                                    </td>
                                    <td className="px-6 py-3">
                                        <input
                                            type="number"
                                            min="0"
                                            max="10"
                                            value={conf.bed_count}
                                            onChange={(e) => handleConfigChange(idx, "bed_count", parseInt(e.target.value) || 0)}
                                            className="w-20 border border-neutral-300 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-emerald-500 outline-none"
                                        />
                                    </td>
                                    <td className="px-6 py-3">
                                        <select
                                            value={conf.occupancy_type}
                                            onChange={(e) => handleConfigChange(idx, "occupancy_type", e.target.value)}
                                            className="border border-neutral-300 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-emerald-500 outline-none bg-white"
                                        >
                                            <option value="Single">Single</option>
                                            <option value="Double">Double</option>
                                        </select>
                                    </td>
                                    <td className="px-6 py-3">
                                        <input
                                            type="text"
                                            value={conf.unit_config_label}
                                            onChange={(e) => handleConfigChange(idx, "unit_config_label", e.target.value)}
                                            className="w-full border border-neutral-300 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-emerald-500 outline-none"
                                            placeholder="e.g. Single"
                                        />
                                    </td>
                                </tr>
                            ))}
                            {config.unit_type_configs.length === 0 && (
                                <tr>
                                    <td colSpan={4} className="px-6 py-8 text-center text-neutral-500">
                                        No unit types found. Add data to the Rent Roll table above.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
                
                <div className="bg-blue-50/50 p-4 text-blue-800 text-xs border-t border-blue-100 flex gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                    <p>
                        <strong>Bed Count:</strong> Used to calculate rent per bed. 
                        <strong>Occupancy Type:</strong> "Single" assumes beds = units (1:1). "Double" splits rent differently.
                        <strong>Label:</strong> Appended to bed count in export (e.g., "2 Single").
                    </p>
                </div>
            </div>

        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-neutral-200 bg-neutral-50 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-neutral-600 hover:text-neutral-900 bg-white border border-neutral-300 hover:bg-neutral-50 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleExport}
            disabled={isExporting}
            className="px-6 py-2 text-sm font-medium text-white bg-neutral-900 hover:bg-neutral-800 rounded-lg transition-colors flex items-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {isExporting ? (
                <>
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Exporting...
                </>
            ) : (
                <>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                Export Excel
                </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}