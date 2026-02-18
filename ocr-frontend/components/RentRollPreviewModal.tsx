import React, { useState, useMemo, useEffect } from "react";
import { createPortal } from "react-dom";
import { AgGridReact } from "ag-grid-react";
import {
  ColDef,
  ColGroupDef,
  ModuleRegistry,
  ClientSideRowModelModule,
  ValidationModule,
  PaginationModule,
  CellStyleModule,
  TextFilterModule,
  NumberFilterModule,
  DateFilterModule,
  CustomFilterModule
} from "ag-grid-community";
import { UnderwritingAnalysis } from "@/lib/types";
import { apiClient } from "@/lib/api";

import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";

// Register AG Grid modules
ModuleRegistry.registerModules([
  ClientSideRowModelModule,
  ValidationModule,
  PaginationModule,
  CellStyleModule,
  TextFilterModule,
  NumberFilterModule,
  DateFilterModule,
  CustomFilterModule
]);

interface RentRollPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  analysisData: UnderwritingAnalysis;
  onConfirmDownload: () => void;
  isDownloading: boolean;
}

export default function RentRollPreviewModal({
  isOpen,
  onClose,
  analysisData,
  onConfirmDownload,
  isDownloading,
}: RentRollPreviewModalProps) {
  const [data, setData] = useState<any>(null);
  const [colDefs, setColDefs] = useState<(ColDef | ColGroupDef)[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Helper to process column definitions
  const processColDefs = (cols: any[]): (ColDef | ColGroupDef)[] => {
      return cols.map((col: any) => {
         if (col.children) {
             return {
                 headerName: col.headerName,
                 children: processColDefs(col.children)
             } as ColGroupDef;
         }

         const def: ColDef = {
             field: col.field,
             headerName: col.headerName,
             width: col.width,
             sortable: false,
             filter: false,
             resizable: true,
             pinned: col.pinned,
             cellStyle: { ...col.cellStyle, textAlign: 'center' },
             cellClass: 'text-center'
         };

         if (col.type === "currency") {
             def.valueFormatter = (params) => {
                 if (params.value === "-" || params.value === null || params.value === undefined || params.value === "") return "";
                 return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(params.value);
             };
             def.type = 'numericColumn'; 
         } else if (col.type === "percent") {
             def.valueFormatter = (params) => {
                 if (params.value === "-" || params.value === null || params.value === undefined || params.value === "") return "";
                 return (params.value * 100).toFixed(1) + '%';
             };
             def.type = 'numericColumn';
         } else if (col.field && ['unit_size', 'size', 'total_sf', 'avg_size'].some(k => col.field.includes(k))) {
             def.valueFormatter = (params) => params.value ? params.value.toLocaleString() : '';
             def.type = 'numericColumn';
         } else if (col.field && ['lease_start', 'lease_end', 'move_in_date', 'date'].some(k => col.field.toLowerCase().includes(k))) {
             def.valueFormatter = (params) => {
                 if (!params.value) return "";
                 return String(params.value).split(/[ T]/)[0];
             };
         }

         return def;
      });
  };

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      setError(null);
      
      const fetchPreview = async () => {
        try {
          const responseData = await apiClient.getRentRollPreview(analysisData);
          setData(responseData);
          setColDefs(processColDefs(responseData.columns));
        } catch (err: any) {
          console.error("Failed to fetch rent roll preview:", err);
          setError(err.message || "Failed to load preview data.");
        } finally {
          setLoading(false);
        }
      };

      fetchPreview();
    }
  }, [isOpen, analysisData]);

  const defaultColDef = useMemo(() => {
    return {
      width: 120,
      minWidth: 80,
      filter: false,
      resizable: true,
    };
  }, []);

  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  if (!isOpen || !mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 left-0 top-0 w-screen h-screen">
      <div className="bg-white rounded-xl shadow-2xl w-[95vw] h-[90vh] flex flex-col overflow-hidden relative">
        {/* Header */}
        <div className="px-6 py-4 border-b border-neutral-200 flex justify-between items-center bg-neutral-50">
          <div>
            <h2 className="text-xl font-bold text-neutral-900">Rent Roll Preview</h2>
            <p className="text-sm text-neutral-500">Review data before downloading Excel.</p>
          </div>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 p-6 bg-neutral-50/30 relative min-h-0">
          {loading ? (
             <div className="absolute inset-0 flex items-center justify-center">
                 <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-neutral-900"></div>
             </div>
          ) : error ? (
              <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-rose-500 font-medium bg-rose-50 px-4 py-2 rounded-lg border border-rose-200">
                      Error: {error}
                  </div>
              </div>
          ) : (
            <div className="h-full w-full ag-theme-quartz" style={{ height: '100%', width: '100%' }}>
                <AgGridReact
                    rowData={data?.rows || []}
                    columnDefs={colDefs}
                    defaultColDef={defaultColDef}
                    alwaysShowHorizontalScroll={true}
                />
            </div>
          )}
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
            onClick={onConfirmDownload}
            disabled={isDownloading || loading || !!error}
            className="px-6 py-2 text-sm font-medium text-white bg-neutral-900 hover:bg-neutral-800 rounded-lg transition-colors flex items-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {isDownloading ? (
                <>
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Generating Excel...
                </>
            ) : (
                <>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                Download Excel File
                </>
            )}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}