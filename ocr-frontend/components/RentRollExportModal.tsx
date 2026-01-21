import React, { useState, useEffect } from "react";
import { RentRollItem, StudentHousingConfig, UnderwritingAnalysis, UnitTypeConfig } from "@/lib/types";
import { apiClient } from "@/lib/api";

interface RentRollExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  analysis: UnderwritingAnalysis;
  onAnalysisUpdate?: (newAnalysis: UnderwritingAnalysis) => void;
}

export default function RentRollExportModal({
  isOpen,
  onClose,
  analysis,
  onAnalysisUpdate,
}: RentRollExportModalProps) {
  const [isExporting, setIsExporting] = useState(false);
  
  // Config State: List of configs per unit type
  const [config, setConfig] = useState<StudentHousingConfig>({
    unit_type_configs: []
  });

  // Initialize on open
  useEffect(() => {
    if (isOpen) {
        const items = analysis.rent_roll || [];
        
        // Initialize Config: Merge Saved Config with Current Rent Roll
        // This ensures we keep saved settings but also account for any new unit types
        let initialConfig: StudentHousingConfig = { unit_type_configs: [] };
        
        if (analysis.student_housing_config && analysis.student_housing_config.unit_type_configs.length > 0) {
            initialConfig = analysis.student_housing_config;
        }

        const uniqueTypes = Array.from(new Set(items.map(i => i.unit_type || "Unknown"))).sort();
        
        const mergedConfigs: UnitTypeConfig[] = uniqueTypes.map(type => {
            // 1. Try to find in saved config
            const existing = initialConfig.unit_type_configs.find(c => c.unit_type === type);
            if (existing) return existing;

            // 2. Otherwise create default
            let beds = 1;
            // Smarter regex: Look for number followed by bd/br/bed, or studio
            const match = type.match(/(\d+)\s*(?:bd|br|bed|bedroom)/i);
            
            if (match) {
                beds = parseInt(match[1]);
            } else if (type.toLowerCase().includes("studio")) {
                beds = 1;
            } else {
                // Fallback: If simply "2" or "3", accept it?
                const startMatch = type.match(/^(\d+)/);
                if (startMatch) beds = parseInt(startMatch[1]);
            }

            return {
                unit_type: type,
                bed_count: beds,
                occupancy_type: "Single",
                unit_config_label: "Single",
                beds_single: beds,
                beds_double: 0,
                market_rent_single: 0,
                market_rent_double: 0
            };
        });

        setConfig({ unit_type_configs: mergedConfigs });
    }
  }, [isOpen, analysis]);

  const handleConfigChange = (index: number, field: keyof UnitTypeConfig, value: any) => {
      const newConfigs = [...config.unit_type_configs];
      const currentItem = newConfigs[index];
      let newItem = { ...currentItem, [field]: value };

      // UX Improvement: Auto-update label if it matches the occupancy type
      if (field === "occupancy_type") {
          // If label was same as old occupancy (default), update it to new occupancy
          if (currentItem.unit_config_label === currentItem.occupancy_type) {
              newItem.unit_config_label = value;
          }

          // Intelligent Preset for Mixed/Single/Double Logic
          if (value === "Single") {
              newItem.beds_single = currentItem.bed_count;
              newItem.beds_double = 0;
          } else if (value === "Double") {
              newItem.beds_single = 0;
              newItem.beds_double = currentItem.bed_count;
          }
          // For "Mixed", we leave values as-is (or init to 0 if undefined) to let user customize
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

      newConfigs[index] = newItem;
      setConfig({ unit_type_configs: newConfigs });
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      // Create a temporary analysis object with overrides
      const exportPayload = {
        ...analysis,
        // rent_roll: rentRoll, // We are not editing rent roll in this modal anymore
        student_housing_config: config,
      };

      // 1. Save the updated configuration to the backend first
      // This ensures persistence for future sessions
      await apiClient.updateAnalysis(analysis.document_id, exportPayload);

      // 1b. Update parent state if callback provided
      if (onAnalysisUpdate) {
          onAnalysisUpdate(exportPayload);
      }

      // 2. Proceed with download
      await apiClient.downloadExport(exportPayload, "rent-roll");
      onClose();
    } catch (error) {
      console.error("Export/Save failed:", error);
      alert("Failed to save configuration or export Rent Roll.");
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
            
            {/* Configuration Section - Dynamic Table */}
            <div className="bg-white border border-neutral-200 rounded-lg shadow-sm overflow-hidden flex flex-col">
                <div className="px-6 py-4 border-b border-neutral-200 bg-neutral-50/50">
                    <h3 className="text-lg font-bold text-neutral-900">Unit Configurations</h3>
                    <p className="text-sm text-neutral-500">Configure assumptions for each Unit Type found in the Rent Roll</p>
                </div>
                
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-neutral-100 text-neutral-600 text-xs uppercase font-semibold">
                            <tr>
                                <th className="px-6 py-3 w-[15%]">Unit Type</th>
                                <th className="px-6 py-3 w-[10%]">Bed Count</th>
                                <th className="px-6 py-3 w-[15%]">Config Type</th>
                                <th className="px-6 py-3 w-[15%]">Config Label</th>
                                <th className="px-6 py-3 w-[45%]">Detailed Breakdown (Count & Market Rent)</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-neutral-100">
                            {config.unit_type_configs.map((conf, idx) => (
                                <tr key={idx} className="hover:bg-neutral-50 transition-colors">
                                    <td className="px-6 py-4 font-medium text-neutral-900 align-top">
                                        {conf.unit_type}
                                    </td>
                                    <td className="px-6 py-4 align-top">
                                        <div className="flex flex-col gap-1">
                                            <span className="text-[10px] text-neutral-500 uppercase tracking-wider font-semibold">Total Beds</span>
                                            <input
                                                type="number"
                                                min="0"
                                                max="10"
                                                value={conf.bed_count}
                                                onChange={(e) => handleConfigChange(idx, "bed_count", parseInt(e.target.value) || 0)}
                                                className="w-20 border border-neutral-300 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-emerald-500 outline-none"
                                            />
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 align-top">
                                        <div className="flex flex-col gap-1">
                                            <span className="text-[10px] text-neutral-500 uppercase tracking-wider font-semibold">Occupancy</span>
                                            <select
                                                value={conf.occupancy_type}
                                                onChange={(e) => handleConfigChange(idx, "occupancy_type", e.target.value)}
                                                className="border border-neutral-300 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-emerald-500 outline-none bg-white w-full"
                                            >
                                                <option value="Single">Single</option>
                                                <option value="Double">Double</option>
                                                <option value="Mixed">Mixed</option>
                                            </select>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 align-top">
                                        <div className="flex flex-col gap-1">
                                            <span className="text-[10px] text-neutral-500 uppercase tracking-wider font-semibold">Label</span>
                                            <input
                                                type="text"
                                                value={conf.unit_config_label}
                                                onChange={(e) => handleConfigChange(idx, "unit_config_label", e.target.value)}
                                                className="w-full border border-neutral-300 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-emerald-500 outline-none"
                                                placeholder="e.g. Single"
                                            />
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 align-top">
                                        <div className="grid grid-cols-2 gap-4 bg-neutral-50 p-3 rounded-md border border-neutral-200">
                                            {/* Single Config */}
                                            <div className="space-y-2">
                                                <div className="text-xs font-semibold text-neutral-700 border-b border-neutral-200 pb-1 mb-2">Single</div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-neutral-500 w-12">Count:</span>
                                                    <input
                                                        type="number"
                                                        min="0"
                                                        value={conf.beds_single || 0}
                                                        onChange={(e) => handleConfigChange(idx, "beds_single", parseInt(e.target.value) || 0)}
                                                        disabled={conf.occupancy_type === "Double"}
                                                        className={`w-full border border-neutral-300 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-emerald-500 outline-none ${conf.occupancy_type === "Double" ? "bg-neutral-100 text-neutral-400" : "bg-white"}`}
                                                    />
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-neutral-500 w-12">Price:</span>
                                                    <div className="relative w-full">
                                                        <span className="absolute left-2 top-1/2 -translate-y-1/2 text-neutral-400 text-xs">$</span>
                                                        <input
                                                            type="number"
                                                            min="0"
                                                            value={conf.market_rent_single || 0}
                                                            onChange={(e) => handleConfigChange(idx, "market_rent_single", parseFloat(e.target.value) || 0)}
                                                            disabled={conf.occupancy_type === "Double"}
                                                            className={`w-full border border-neutral-300 rounded pl-5 pr-2 py-1 text-xs focus:ring-1 focus:ring-emerald-500 outline-none ${conf.occupancy_type === "Double" ? "bg-neutral-100 text-neutral-400" : "bg-white"}`}
                                                        />
                                                    </div>
                                                </div>
                                            </div>

                                            {/* Double Config */}
                                            <div className="space-y-2">
                                                <div className="text-xs font-semibold text-neutral-700 border-b border-neutral-200 pb-1 mb-2">Double</div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-neutral-500 w-12">Count:</span>
                                                    <input
                                                        type="number"
                                                        min="0"
                                                        value={conf.beds_double || 0}
                                                        onChange={(e) => handleConfigChange(idx, "beds_double", parseInt(e.target.value) || 0)}
                                                        disabled={conf.occupancy_type === "Single"}
                                                        className={`w-full border border-neutral-300 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-emerald-500 outline-none ${conf.occupancy_type === "Single" ? "bg-neutral-100 text-neutral-400" : "bg-white"}`}
                                                    />
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-neutral-500 w-12">Price:</span>
                                                    <div className="relative w-full">
                                                        <span className="absolute left-2 top-1/2 -translate-y-1/2 text-neutral-400 text-xs">$</span>
                                                        <input
                                                            type="number"
                                                            min="0"
                                                            value={conf.market_rent_double || 0}
                                                            onChange={(e) => handleConfigChange(idx, "market_rent_double", parseFloat(e.target.value) || 0)}
                                                            disabled={conf.occupancy_type === "Single"}
                                                            className={`w-full border border-neutral-300 rounded pl-5 pr-2 py-1 text-xs focus:ring-1 focus:ring-emerald-500 outline-none ${conf.occupancy_type === "Single" ? "bg-neutral-100 text-neutral-400" : "bg-white"}`}
                                                        />
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                            {config.unit_type_configs.length === 0 && (
                                <tr>
                                    <td colSpan={5} className="px-6 py-8 text-center text-neutral-500">
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
                        <strong>Mixed Occupancy:</strong> Use "Mixed" to define a split of Single and Double beds within one unit type.
                        Ensure the total bed count matches your split (e.g., 3 Beds = 1 Single + 2 Double).
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