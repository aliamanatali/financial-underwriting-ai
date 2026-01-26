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

  // Initialize on analysis change or mount
  useEffect(() => {
    const items = analysis.rent_roll || [];
    
    // We want to preserve current edits if possible, but also respect saved config from analysis
    // and account for new unit types from the rent roll.
    
    // 1. Get Saved Config from Analysis (Backend State)
    let savedConfig: StudentHousingConfig = { unit_type_configs: [] };
    if (analysis.student_housing_config && analysis.student_housing_config.unit_type_configs.length > 0) {
        savedConfig = analysis.student_housing_config;
    }

    const uniqueTypes = Array.from(new Set(items.map(i => i.unit_type || "Unknown"))).sort();
    
    setConfig(currentConfig => {
        const mergedConfigs: UnitTypeConfig[] = uniqueTypes.map(type => {
            // Priority 1: Keep current local edits if they exist (User edited in modal but didn't save yet)
            const local = currentConfig.unit_type_configs.find(c => c.unit_type === type);
            if (local) return local;

            // Priority 2: Use saved config from backend
            const saved = savedConfig.unit_type_configs.find(c => c.unit_type === type);
            if (saved) return saved;

            // Priority 3: Create default for new/unknown types
            let beds = 1;
            const match = type.match(/(\d+)\s*(?:bd|br|bed|bedroom)/i);
            
            if (match) {
                beds = parseInt(match[1]);
            } else if (type.toLowerCase().includes("studio")) {
                beds = 1;
            } else {
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
        
        return { unit_type_configs: mergedConfigs };
    });
  }, [analysis]); // Run when analysis changes (e.g. rent roll update)

  const saveConfiguration = async (currentConfig?: StudentHousingConfig) => {
    const cfg = currentConfig || config;
    try {
      const exportPayload = {
        ...analysis,
        student_housing_config: cfg,
      };
      await apiClient.updateAnalysis(analysis.document_id, exportPayload);
      if (onAnalysisUpdate) {
        onAnalysisUpdate(exportPayload);
      }
    } catch (error) {
      console.error("Auto-save failed:", error);
    }
  };

  const handleConfigChange = (index: number, field: keyof UnitTypeConfig, value: any, shouldSave = false) => {
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
      const newConfigWrapper = { unit_type_configs: newConfigs };
      setConfig(newConfigWrapper);

      if (shouldSave) {
        saveConfiguration(newConfigWrapper);
      }
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
      alert("Unable to save settings or download the Rent Roll.");
    } finally {
      setIsExporting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 ${!isOpen ? 'hidden' : ''}`}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-6xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-neutral-200 flex justify-between items-center bg-neutral-50">
          <div>
            <h2 className="text-xl font-bold text-neutral-900">Rent Roll Export Settings</h2>
            <div className="space-y-1">
              <p className="text-sm text-neutral-500">Configure unit types, bed counts, and market rents before exporting.</p>
              <p className="text-xs text-neutral-400">These settings will be used to populate the Unit Mix Summary table in the export.</p>
            </div>
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
                    <h3 className="text-lg font-bold text-neutral-900">Unit Type Configuration</h3>
                    <p className="text-sm text-neutral-500">Verify and adjust the bed count, occupancy type, and market rent for each unit plan.</p>
                </div>
                
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-neutral-100 text-neutral-600 text-xs uppercase font-semibold">
                            <tr>
                                <th className="px-6 py-3 w-[15%]">Unit Type</th>
                                <th className="px-6 py-3 w-[10%]">Bed Count</th>
                                <th className="px-6 py-3 w-[15%]">Occupancy Type</th>
                                <th className="px-6 py-3 w-[15%]">Unit Label</th>
                                <th className="px-6 py-3 w-[45%]">Market Rent & Bed Config</th>
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
                                            <span className="text-[10px] text-neutral-500 uppercase tracking-wider font-semibold">Beds / Unit</span>
                                            <input
                                                type="text"
                                                value={conf.bed_count}
                                                onChange={(e) => handleConfigChange(idx, "bed_count", parseInt(e.target.value) || 0)}
                                                onBlur={() => saveConfiguration()}
                                                className="w-20 border border-neutral-300 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-emerald-500 outline-none"
                                            />
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 align-top">
                                        <div className="flex flex-col gap-1">
                                            <span className="text-[10px] text-neutral-500 uppercase tracking-wider font-semibold">Occupancy</span>
                                            <select
                                                value={conf.occupancy_type}
                                                onChange={(e) => handleConfigChange(idx, "occupancy_type", e.target.value, true)}
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
                                                onBlur={() => saveConfiguration()}
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
                                                    <span className="text-xs text-neutral-500 w-12">Beds:</span>
                                                    <input
                                                        type="text"
                                                        value={conf.beds_single || 0}
                                                        onChange={(e) => handleConfigChange(idx, "beds_single", parseInt(e.target.value) || 0)}
                                                        onBlur={() => saveConfiguration()}
                                                        disabled={conf.occupancy_type === "Double"}
                                                        className={`w-full border border-neutral-300 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-emerald-500 outline-none ${conf.occupancy_type === "Double" ? "bg-neutral-100 text-neutral-400" : "bg-white"}`}
                                                    />
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-neutral-500 w-12">Rent:</span>
                                                    <div className="relative w-full">
                                                        <span className="absolute left-2 top-1/2 -translate-y-1/2 text-neutral-400 text-xs">$</span>
                                                        <input
                                                            type="text"
                                                            value={conf.market_rent_single || 0}
                                                            onChange={(e) => handleConfigChange(idx, "market_rent_single", parseFloat(e.target.value) || 0)}
                                                            onBlur={() => saveConfiguration()}
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
                                                    <span className="text-xs text-neutral-500 w-12">Beds:</span>
                                                    <input
                                                        type="text"
                                                        value={conf.beds_double || 0}
                                                        onChange={(e) => handleConfigChange(idx, "beds_double", parseInt(e.target.value) || 0)}
                                                        onBlur={() => saveConfiguration()}
                                                        disabled={conf.occupancy_type === "Single"}
                                                        className={`w-full border border-neutral-300 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-emerald-500 outline-none ${conf.occupancy_type === "Single" ? "bg-neutral-100 text-neutral-400" : "bg-white"}`}
                                                    />
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-neutral-500 w-12">Rent:</span>
                                                    <div className="relative w-full">
                                                        <span className="absolute left-2 top-1/2 -translate-y-1/2 text-neutral-400 text-xs">$</span>
                                                        <input
                                                            type="text"
                                                            value={conf.market_rent_double || 0}
                                                            onChange={(e) => handleConfigChange(idx, "market_rent_double", parseFloat(e.target.value) || 0)}
                                                            onBlur={() => saveConfiguration()}
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
                                        No unit types detected in the current analysis.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
                
                <div className="bg-blue-50/50 p-4 text-blue-800 text-xs border-t border-blue-100 flex gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                    <p>
                        <strong>Mixed Occupancy:</strong> Select "Mixed" to allocate beds between Single and Double occupancy.
                        Total beds must match the Unit Bed Count.
                    </p>
                </div>
            </div>

        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-neutral-200 bg-neutral-50 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-neutral-600 hover:text-neutral-900 bg-white border border-neutral-300 hover:bg-neutral-50 rounded-lg transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={handleExport}
            disabled={isExporting}
            className="px-6 py-2 text-sm font-medium text-white bg-neutral-900 hover:bg-neutral-800 rounded-lg transition-colors flex items-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed cursor-pointer"
          >
            {isExporting ? (
                <>
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Downloading...
                </>
            ) : (
                <>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                Download Rent Roll
                </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}