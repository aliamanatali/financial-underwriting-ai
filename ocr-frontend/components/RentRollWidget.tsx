"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { RentRollItem, RentRollSummary, UnderwritingAnalysis, StudentHousingConfig } from "@/lib/types";
import { apiClient } from "@/lib/api";
import WarningModal from "./WarningModal";
import UnitBreakdownTable from "./UnitBreakdownTable";
import UnitBreakdownStabilizedTable from "./UnitBreakdownStabilizedTable";
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
import WidgetTooltip from "./WidgetTooltip";
import RentRollPreviewModal from "./RentRollPreviewModal";

type EditableRentRollItem = Omit<RentRollItem, "unit_size" | "current_rent" | "stabilized_rent" | "market_rent" | "deposit"> & {
  id: string;
  unit_size: string | number;
  current_rent: string | number;
  stabilized_rent: string | number;
  market_rent: string | number;
  deposit: string | number;
  is_vacant: boolean;
  beds_single?: number;
  beds_double?: number;
  market_rent_single?: number;
  market_rent_double?: number;
  unit_config_label?: string;
  bed_count?: number;
  occupancy_type?: string;
};

interface RentRollWidgetProps {
  rentRoll: RentRollItem[];
  summary?: RentRollSummary;
  packageId: string;
  onUpdate?: () => void;
  studentHousingConfig?: StudentHousingConfig;
  onOpenConfig?: () => void;
  initialTab?: "details" | "omExport" | "unitBreakdown" | "unitBreakdownStabilized";
  initialEditMode?: boolean;
  fullAnalysis?: UnderwritingAnalysis; // Add optional full analysis prop
  validationTrigger?: number;
}

// Helpers for date input conversion (YYYY-MM-DD <-> MM/DD/YYYY)
/**
 * Strips time from a date string (e.g. "2024-06-01 00:00:00" -> "2024-06-01")
 * @param {string | undefined | null} dateStr - The date string to clean.
 * @returns {string} The date part only.
 */
const formatDateOnly = (dateStr: string | undefined | null) => {
  if (!dateStr) return "";
  // Split by space or 'T' to handle both SQL-style and ISO-style date-times
  return dateStr.split(/[ T]/)[0];
};

/**
 * Converts a date string from MM/DD/YYYY format to YYYY-MM-DD format for date inputs.
 * @param {string | undefined | null} displayDate - The date string to convert.
 * @returns {string} The formatted date string or an empty string if invalid.
 */
const toInputDate = (displayDate: string | undefined | null) => {
  const dateOnly = formatDateOnly(displayDate);
  if (!dateOnly) return "";
  
  // If it's already in YYYY-MM-DD format, return as is
  if (dateOnly.match(/^\d{4}-\d{2}-\d{2}$/)) return dateOnly;

  const parts = dateOnly.split('/');
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

/**
 * Converts a date string from YYYY-MM-DD format to MM/DD/YYYY format for display.
 * @param {string} inputDate - The date string to convert.
 * @returns {string} The formatted date string.
 */
const fromInputDate = (inputDate: string) => {
  const dateOnly = formatDateOnly(inputDate);
  if (!dateOnly) return "";
  const parts = dateOnly.split('-');
  if (parts.length === 3) {
    // YYYY-MM-DD -> MM/DD/YYYY
    return `${parts[1]}/${parts[2]}/${parts[0]}`;
  }
  return dateOnly;
};

function getBedCountFromUnitType(unit_type: string): number {
  if (!unit_type) return 1;

  // Heuristic 1: Bed/Bath format "0/1.00", "2/1"
  const match_slash = unit_type.match(/^(\d+)\s*\//);
  if (match_slash) {
    const val = parseInt(match_slash[1], 10);
    return val > 0 ? val : 1; // Treat 0 beds (Studio) as 1 bed
  }

  // Heuristic 2: "2bd", "2 br"
  const match_bd = (unit_type || "").toLowerCase().match(/(\d+)\s*(?:bd|br|bed)/);
  if (match_bd) {
    return parseInt(match_bd[1], 10);
  }

  if ((unit_type || "").toLowerCase().includes("studio")) {
    return 1;
  }

  // Fallback: Look for first digit
  const match = unit_type.match(/\d+/);
  if (match) {
    return parseInt(match[0], 10);
  }

  return 1;
}

function updateUnitTypeString(oldType: string, newBeds: number): string {
    if (!oldType) return `${newBeds}/1.00`;
    
    // Pattern 1: X/Y (e.g. 2/1.00)
    if (oldType.match(/^\d+\s*\//)) {
        return oldType.replace(/^\d+/, newBeds.toString());
    }
    
    // Pattern 2: Xbd or X br
    if (oldType.match(/^\d+\s*(?:bd|br|bed)/i)) {
        return oldType.replace(/^\d+/, newBeds.toString());
    }

    // Pattern 3: XxY (e.g. 1x1)
    if (oldType.toLowerCase().match(/^\d+\s*x\s*\d+/)) {
        return oldType.toLowerCase().replace(/^\d+/, newBeds.toString());
    }
    
    // Default fallback
    return `${newBeds}/1.00`;
}

/**
 * A component that displays and allows editing of a rent roll, with different views and export functionalities.
 * @param {RentRollWidgetProps} props - The props for the component.
 * @returns {JSX.Element} The rendered RentRollWidget component.
 */
export default function RentRollWidget({
  rentRoll,
  summary,
  packageId,
  // Using partial because we might not have the full object in the widget props,
  // but we need it for export. If it's not passed, we'll try to fetch or construct it.
  // Ideally, the parent should pass the full analysis object.
  fullAnalysis,
  onUpdate,
  studentHousingConfig,
  onOpenConfig,
  initialTab = "details",
  initialEditMode = false,
  validationTrigger,
}: RentRollWidgetProps) {
  const [activeTab, setActiveTab] = useState<"details" | "omExport" | "unitBreakdown" | "unitBreakdownStabilized">(initialTab);
  const [isEditing, setIsEditing] = useState<boolean>(initialEditMode || false);
  
  const componentRef = React.useRef<HTMLDivElement>(null);

  // Effect to handle initial props changes if they come from parent updates (e.g. URL param changes)
  useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab);
    }
    if (initialEditMode !== undefined) {
      setIsEditing(initialEditMode);
    }
    
    // Scroll to the widget if triggered
    if (validationTrigger && componentRef.current) {
        componentRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [initialTab, initialEditMode, validationTrigger]);

  // Initialize with IDs and merge Student Housing Config
  const initializeItems = (items: RentRollItem[], config?: StudentHousingConfig): EditableRentRollItem[] => {
    console.log("RentRollWidget: Initializing Items. Config present:", !!config);
    return items
      .filter(item => String(item.unit_number || "").trim() !== "3048" && String(item.unit_type || "").trim() !== "3048")
      .map(item => {
      // Robust matching: trim and lowercase
      const typeConfig = config?.unit_type_configs.find(c =>
        (c.unit_type || "").trim().toLowerCase() === (item.unit_type || "").trim().toLowerCase()
      );
      
      if (config && !typeConfig) {
          console.warn(`RentRollWidget: No config found for unit type: '${item.unit_type}'`);
      }

      return {
        ...item,
        unit_number: item.unit_number || item.unit_type || "",
        id: item.unit_number ? item.unit_number : (item.unit_type ? `${item.unit_type}-${Math.random()}` : `unit-${Math.random()}`),
        deposit: item.deposit || 0,
        is_vacant: item.is_vacant ?? (
            item.tenant_name?.toLowerCase().includes("vacant") ||
            item.unit_type?.toLowerCase().includes("vacant") ||
            (parseFloat(String(item.current_rent)) === 0 && (item.tenant_name?.toLowerCase().includes("vacant") || !item.tenant_name || item.tenant_name.toLowerCase() === "unknown"))
        ),
        tenant_name: (item.is_vacant || (
            item.tenant_name?.toLowerCase().includes("vacant") ||
            item.unit_type?.toLowerCase().includes("vacant") ||
            (parseFloat(String(item.current_rent)) === 0 && (item.tenant_name?.toLowerCase().includes("vacant") || !item.tenant_name || item.tenant_name.toLowerCase() === "unknown"))
        )) ? "Vacant" : (item.tenant_name || "Unknown"),
        // Merge config values if they exist
        beds_single: typeConfig?.beds_single,
        beds_double: typeConfig?.beds_double,
        market_rent_single: typeConfig?.market_rent_single,
        market_rent_double: typeConfig?.market_rent_double,
        unit_config_label: typeConfig?.unit_config_label,
        bed_count: typeConfig?.bed_count,
        occupancy_type: typeConfig?.occupancy_type
      };
    });
  };

  const [items, setItems] = useState<EditableRentRollItem[]>(
    initializeItems(rentRoll, studentHousingConfig)
  );

  // Check for dynamic columns
  const hasDeposits = React.useMemo(() => items.some(i => Number(i.deposit) > 0), [items]);
  const hasParking = React.useMemo(() => items.some(i => i.parking && i.parking.trim() !== "" && i.parking.trim() !== "-"), [items]);
  const hasComments = React.useMemo(() => items.some(i => i.comments && i.comments.trim() !== "" && i.comments.trim() !== "-"), [items]);
  const hasMoveInDate = React.useMemo(() => items.some(i => i.move_in_date && i.move_in_date.trim() !== "" && i.move_in_date.trim() !== "-" && i.move_in_date.trim().toUpperCase() !== "V"), [items]);
  const hasTenantName = false;
  const hasFloor = React.useMemo(() => items.some(i => (i as any).floor && (i as any).floor.trim() !== "" && (i as any).floor.trim() !== "-"), [items]);

  const isNonOMFlow = !fullAnalysis?.om_proforma || fullAnalysis.om_proforma.length === 0;

  // Filter items for display and calculations in Non-OM flows
  const visibleItems = React.useMemo(() => {
    if (!isNonOMFlow || isEditing) return items;
    
    return items.filter(item => {
      const sizeStr = String(item.unit_size).toLowerCase().trim();
      // Filter out if size is 0, "-", "unknown"
      return !(
        !item.unit_size ||
        item.unit_size === 0 ||
        sizeStr === "-" ||
        sizeStr === "unknown" ||
        sizeStr === "unkown" // Handle common typo from prompt
      );
    });
  }, [items, isNonOMFlow, isEditing]);

  useEffect(() => {
    setItems(initializeItems(rentRoll, studentHousingConfig));
  }, [rentRoll, studentHousingConfig]);

  const router = useRouter();
  const [isSaving, setIsSaving] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [showWarning, setShowWarning] = useState(false);
  const [warningMessage, setWarningMessage] = useState("");
  const [showPreview, setShowPreview] = useState(false);
  const [pendingExportData, setPendingExportData] = useState<UnderwritingAnalysis | null>(null);

  // Map of Row ID -> { fieldName: errorMessage }
  const [rowErrors, setRowErrors] = useState<Record<string, Record<string, string>>>({});
  const [initialPayloadStr, setInitialPayloadStr] = useState<string | null>(null);

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



  const validateItem = (item: EditableRentRollItem) => {
    const errors: Record<string, string> = {};
    if (!item.unit_number) errors.unit_number = "Required";
    if (!item.unit_type) errors.unit_type = "Required";
    
    const sizeVal = parseFloat(String(item.unit_size));
    if (isNaN(sizeVal) || sizeVal <= 0) errors.unit_size = "Invalid Size";
    
    const marketVal = parseFloat(String(item.market_rent));
    if (isNaN(marketVal) || marketVal <= 0) errors.market_rent = "Required";
    
    const currentVal = parseFloat(String(item.current_rent));
    if (item.is_vacant) {
        if (!isNaN(currentVal) && currentVal > 0) {
            errors.current_rent = "Must be 0 if vacant";
        }
        if (item.tenant_name?.toLowerCase() !== "vacant") {
            errors.tenant_name = "Must be 'Vacant'";
        }
    } else {
        if (item.tenant_name?.toLowerCase() === "vacant") {
            errors.tenant_name = "Required if not vacant";
        }
    }

    const validateYear = (date: string, field: string) => {
      if (!date) return;
      let year;
      // Handle YYYY-MM-DD
      if (date.includes('-')) {
        year = parseInt(date.split('-')[0], 10);
      }
      // Handle MM/DD/YYYY
      else if (date.includes('/')) {
        const parts = date.split('/');
        if (parts.length >= 3) {
          let yearStr = parts[2];
          if (yearStr && yearStr.length === 2) {
            yearStr = "20" + yearStr; // handle 2-digit years
          }
          year = parseInt(yearStr, 10);
        }
      }
      
      if (year && (year < 1900 || year > 2100)) {
        errors[field] = "Invalid Year";
      }
    };

    validateYear(item.lease_start, "lease_start");
    validateYear(item.lease_end, "lease_end");
    validateYear(item.move_in_date, "move_in_date");
    
    if (item.lease_start && item.lease_end) {
        const start = new Date(item.lease_start);
        const end = new Date(item.lease_end);
        if (end < start) {
            errors.lease_end = "Must be after start";
        }
    }

    return errors;
  };

  const handleItemChangeById = (id: string, field: keyof EditableRentRollItem, value: any) => {
    const newItems = [...items];
    const index = newItems.findIndex(item => item.id === id);
    if (index === -1) return;

    let updatedItem = {
      ...newItems[index],
      [field]: value,
    };

    // Special logic for vacant status
    if (field === "is_vacant") {
        if (value === true) {
            updatedItem.tenant_name = "Vacant";
            updatedItem.current_rent = 0;
            updatedItem.lease_start = "";
            updatedItem.lease_end = "";
        } else {
            if (updatedItem.tenant_name === "Vacant") {
                updatedItem.tenant_name = "Unknown";
            }
        }
    }

    // If tenant name is changed to Vacant manually
    if (field === "tenant_name" && value?.toLowerCase() === "vacant") {
        updatedItem.is_vacant = true;
        updatedItem.current_rent = 0;
    }

    // If current rent is set > 0, it shouldn't be vacant
    if (field === "current_rent") {
        const rentVal = parseFloat(String(value)) || 0;
        if (rentVal > 0) {
            updatedItem.is_vacant = false;
            if (updatedItem.tenant_name === "Vacant") {
                updatedItem.tenant_name = "Unknown";
            }
        } else {
            // If current rent is zero, stabilized rent should also be zero
            updatedItem.stabilized_rent = 0;
        }
    }

    // Ensure numeric fields are rounded to nearest whole number when changed
    if (field === "market_rent" || field === "current_rent" || field === "stabilized_rent" || field === "deposit") {
        const numVal = parseFloat(String(value)) || 0;
        updatedItem[field] = Math.round(numVal);
    }

    // Handle bed count changes and update unit type string
    if (field === "bed_count") {
        const newBeds = parseInt(String(value)) || 0;
        updatedItem.unit_type = updateUnitTypeString(updatedItem.unit_type || "", newBeds);
        updatedItem.unit_config_label = updatedItem.unit_type; // Sync config label
    }

    // Handle unit type changes and update bed count
    if (field === "unit_type") {
        updatedItem.bed_count = getBedCountFromUnitType(value);
        updatedItem.unit_config_label = value; // Sync config label
    }

    // Handle unit config label changes and update unit type and bed count
    if (field === "unit_config_label") {
        updatedItem.unit_type = value;
        updatedItem.bed_count = getBedCountFromUnitType(value);
    }

    newItems[index] = updatedItem;
    setItems(newItems);

    const errors = validateItem(updatedItem);
    if (Object.keys(errors).length > 0) {
      setRowErrors(prev => ({
        ...prev,
        [updatedItem.id]: errors,
      }));
    } else {
      // If there are no errors, remove the entry for this item
      setRowErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[updatedItem.id];
        return newErrors;
      });
    }
  };
 
  const handleNumericChangeById = (id: string, field: keyof EditableRentRollItem, value: string) => {
    const numericValue = value.replace(/[^0-9.]/g, '');
    handleItemChangeById(id, field, numericValue);
  };

  const generatePayload = (currentItems: EditableRentRollItem[]) => {
      const cleanItems: RentRollItem[] = currentItems.map(({ id, ...rest }) => ({
        ...rest,
        unit_size: parseFloat(String(rest.unit_size)) || 0,
        current_rent: parseFloat(String(rest.current_rent)) || 0,
        stabilized_rent: parseFloat(String(rest.stabilized_rent)) || 0,
        market_rent: parseFloat(String(rest.market_rent)) || 0,
        deposit: parseFloat(String(rest.deposit)) || 0,
      }));

      const uniqueUnitTypes = Array.from(new Set(currentItems.map(i => i.unit_type)));
      const newUnitTypeConfigs = uniqueUnitTypes.map(unitType => {
          const item = currentItems.find(i => i.unit_type === unitType);
          const existingConfig = studentHousingConfig?.unit_type_configs?.find(c =>
            (c.unit_type || "").trim().toLowerCase() === (unitType || "").trim().toLowerCase()
          );
          
          if (item) {
              return {
                  unit_type: unitType,
                  beds_single: item.beds_single ?? existingConfig?.beds_single,
                  beds_double: item.beds_double ?? existingConfig?.beds_double,
                  market_rent_single: item.market_rent_single ?? existingConfig?.market_rent_single,
                  market_rent_double: item.market_rent_double ?? existingConfig?.market_rent_double,
                  unit_config_label: item.unit_config_label ?? existingConfig?.unit_config_label ?? "Single",
                  bed_count: item.bed_count !== undefined ? item.bed_count : (existingConfig?.bed_count || getBedCountFromUnitType(unitType)),
                  occupancy_type: (item.occupancy_type as "Single" | "Double" | "Mixed") || existingConfig?.occupancy_type || "Single",
              };
          }
          return existingConfig || {
              unit_type: unitType,
              bed_count: 1,
              occupancy_type: "Single",
              unit_config_label: "Single"
          };
      });

      return {
          rent_roll: cleanItems,
          student_housing_config: {
              ...(studentHousingConfig || { unit_type_configs: [] }),
              unit_type_configs: newUnitTypeConfigs
          }
      };
  };

  const handleEdit = () => {
    setIsEditing(true);
    setInitialPayloadStr(JSON.stringify(generatePayload(items)));
    // Validate all items when entering edit mode
    const initialErrors: Record<string, Record<string, string>> = {};
      items.forEach(item => {
        const errors = validateItem(item);
        if (Object.keys(errors).length > 0) {
          initialErrors[item.id] = errors;
        }
      });
    setRowErrors(initialErrors);
  };

  const handleUnitBreakdownChange = (unitType: string, field: keyof EditableRentRollItem, value: any) => {
    setItems(prevItems => prevItems.map(item => {
      if (item.unit_type === unitType) {
        let updatedItem = {
          ...item,
          [field]: value,
        };

        // Handle bed count changes and update unit type string
        if (field === "bed_count") {
            const newBeds = parseInt(String(value)) || 0;
            updatedItem.unit_type = updateUnitTypeString(item.unit_type || "", newBeds);
        }

        return updatedItem;
      }
      return item;
    }));
  };

  const handleSave = async () => {
    console.log("RentRollWidget: handleSave started");
    setIsSaving(true);

    if (activeTab === 'details') {
      let errorCount = 0;
      const newRowErrors: Record<string, Record<string, string>> = {};

      const unitNumbers = new Set();
      const duplicateUnits = new Set();
      items.forEach(i => {
          if (i.unit_number) {
              const num = i.unit_number.trim().toLowerCase();
              if (unitNumbers.has(num)) {
                  duplicateUnits.add(num);
              }
              unitNumbers.add(num);
          }
      });

      items.forEach((item) => {
          const errors = validateItem(item);
          if (item.unit_number && duplicateUnits.has(item.unit_number.trim().toLowerCase())) {
              errors.unit_number = "Duplicate #";
          }

          if (Object.keys(errors).length > 0) {
              newRowErrors[item.id] = errors;
              errorCount++;
          }
      });

      setRowErrors(newRowErrors); // Update state with all current errors

      if (errorCount > 0) {
          console.log("RentRollWidget: Validation failed with", errorCount, "errors");
          setWarningMessage(
              `Found ${errorCount} unit(s) with incomplete data.\n\nPlease ensure:\n• All units have Number, Type, and Size (> 0)\n• Market Rents are set (> 0)`
          );
          setShowWarning(true);
          setIsSaving(false);
          return;
      }
    }

    setRowErrors({});

    try {
      const payload: any = generatePayload(items);
      const currentPayloadStr = JSON.stringify(payload);
      
      if (initialPayloadStr === currentPayloadStr) {
          console.log("RentRollWidget: No changes detected, skipping update");
          setIsEditing(false);
          setIsSaving(false);
          return;
      }

      console.log("RentRollWidget: Sending update payload", payload);
      await apiClient.updateManualOverrides(packageId, payload);
      console.log("RentRollWidget: Update successful");
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
    // Construct the full analysis object needed for export
    // The backend expects an UnderwritingAnalysis object
    // Start with the full analysis object if available, or a minimal one
    const baseAnalysis = fullAnalysis || {
        document_id: packageId,
        pass_fail_status: "PENDING", // Default values to satisfy validation
        property_meta: {
            address: "Unknown",
            year_built: 0,
            purchase_price: 0,
            total_units: 0
        },
        historical_expenses: [],
        rent_roll: [],
        rent_roll_summary: summary || localSummary,
    };

    const exportData = {
        ...baseAnalysis,
        document_id: packageId,
        rent_roll: visibleItems.map(({ id, stabilized_rent, ...rest }) => ({
            ...rest,
            unit_size: parseFloat(String(rest.unit_size)) || 0,
            current_rent: parseFloat(String(rest.current_rent)) || 0,
            market_rent: parseFloat(String(rest.market_rent)) || 0,
        })),
        rent_roll_summary: summary || localSummary,
        student_housing_config: studentHousingConfig
    };

    setPendingExportData(exportData as any);
    setShowPreview(true);
  };

  const confirmDownload = async () => {
    if (!pendingExportData) return;
    
    setIsExporting(true);
    try {
        await apiClient.downloadExport(pendingExportData, "rent-roll");
        setShowPreview(false);
    } catch (error) {
        console.error("Error exporting rent roll:", error);
        alert("Failed to export rent roll.");
    } finally {
        setIsExporting(false);
    }
  };

  const handleCancel = () => {
    setItems(initializeItems(rentRoll, studentHousingConfig));
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
        is_vacant: true,
        current_rent: 0,
        stabilized_rent: 0,
        market_rent: 0,
        deposit: 0,
        parking: "",
        comments: "",
        move_in_date: "",
        lease_start: "",
        lease_end: "",
      },
    ]);
  };


  const removeItemById = (id: string) => {
    setItems(prevItems => prevItems.filter(item => item.id !== id));
  };

  // Calculate local summary for immediate feedback
  const localSummary = React.useMemo(() => {
    const totalUnits = visibleItems.length;
    
    // Filter items that are actually paying rent (occupied)
    const payingItems = visibleItems.filter(i =>
      i.tenant_name &&
      i.tenant_name.toLowerCase() !== "vacant" &&
      (parseFloat(String(i.current_rent)) || 0) > 0
    );

    const occupiedUnits = payingItems.length;
    const occupancyRate = totalUnits > 0 ? occupiedUnits / totalUnits : 0;
    
    const totalUnitSize = visibleItems.reduce((sum, item) => sum + (parseFloat(String(item.unit_size)) || 0), 0);
    const payingUnitSize = payingItems.reduce((sum, item) => sum + (parseFloat(String(item.unit_size)) || 0), 0);
    const avgUnitSize = totalUnits > 0 ? totalUnitSize / totalUnits : 0;

    const totalMonthlyRent = visibleItems.reduce((sum, item) => sum + (parseFloat(String(item.current_rent)) || 0), 0);
    const totalAnnualRent = totalMonthlyRent * 12;
    
    const totalStabilizedRent = visibleItems.reduce((sum, item) => sum + (parseFloat(String(item.stabilized_rent)) || 0), 0);
    const totalMarketRent = visibleItems.reduce((sum, item) => sum + (parseFloat(String(item.market_rent)) || 0), 0);

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

    visibleItems.forEach(item => {
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
      percent: visibleItems.length > 0 ? data.count / visibleItems.length : 0,
      avgCurrentRent: data.payingCount > 0 ? data.totalCurrentRent / data.payingCount : 0,
      avgStabilizedRent: data.count > 0 ? data.totalStabilizedRent / data.count : 0,
      avgMarketRent: data.count > 0 ? data.totalMarketRent / data.count : 0,
      avgSqFt: data.count > 0 ? data.totalSqFt / data.count : 0
    })).sort((a, b) => b.count - a.count); // Sort by count descending
  }, [items]);

  const displaySummary = isEditing ? localSummary : (summary || localSummary);

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0, minimumFractionDigits: 0 }).format(Math.round(val));

  const formatPercent = (val: number) =>
    Math.round(val * 100) + "%";

  return (
    <>
      <div ref={componentRef} className="scroll-mt-20">
      <WarningModal
        isOpen={showWarning}
        onClose={() => setShowWarning(false)}
        title="Incomplete Data"
        message={warningMessage}
      />
      
      {pendingExportData && (
        <RentRollPreviewModal
            isOpen={showPreview}
            onClose={() => setShowPreview(false)}
            analysisData={pendingExportData}
            onConfirmDownload={confirmDownload}
            isDownloading={isExporting}
        />
      )}

      <div className="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden mb-6">
        <div className="px-6 py-4 border-b border-neutral-100 flex items-center justify-between bg-neutral-50/50">
          <div className="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-neutral-500">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="3" y1="9" x2="21" y2="9"></line>
              <line x1="9" y1="21" x2="9" y2="9"></line>
            </svg>
            <div className="flex items-center border border-neutral-200 rounded-lg p-0.5 bg-white shadow-inner">
              <button
                onClick={() => setActiveTab("details")}
                className={`px-3 py-1 text-xs font-bold rounded-md transition-colors ${activeTab === "details" ? "bg-neutral-800 text-white shadow-sm" : "text-neutral-600 hover:bg-neutral-100"}`}
              >
                Rent Roll Information
              </button>
              <button
                onClick={() => setActiveTab("omExport")}
                className={`px-3 py-1 text-xs font-bold rounded-md transition-colors ${activeTab === "omExport" ? "bg-neutral-800 text-white shadow-sm" : "text-neutral-600 hover:bg-neutral-100"}`}
              >
                Rent Roll Detailed
              </button>
              <button
                onClick={() => setActiveTab("unitBreakdown")}
                className={`px-3 py-1 text-xs font-bold rounded-md transition-colors ${activeTab === "unitBreakdown" ? "bg-neutral-800 text-white shadow-sm" : "text-neutral-600 hover:bg-neutral-100"}`}
              >
                Unit Breakdown - Existing
              </button>
              <button
                onClick={() => setActiveTab("unitBreakdownStabilized")}
                className={`px-3 py-1 text-xs font-bold rounded-md transition-colors ${activeTab === "unitBreakdownStabilized" ? "bg-neutral-800 text-white shadow-sm" : "text-neutral-600 hover:bg-neutral-100"}`}
              >
                Unit Breakdown Stabilized
              </button>
            </div>
          </div>
          {!isEditing ? (
            <div className="flex gap-2">
              <button
                onClick={handleExport}
                disabled={isExporting}
                className="text-xs font-medium text-neutral-600 hover:text-neutral-900 border border-neutral-200 px-3 py-1.5 rounded-lg bg-white hover:bg-neutral-50 transition-all shadow-sm flex items-center gap-1.5"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="7 10 12 15 17 10"></polyline>
                  <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                Preview Rent Roll
              </button>
              <button
                onClick={handleEdit}
                className="text-xs font-medium text-neutral-600 hover:text-neutral-900 border border-neutral-200 px-3 py-1.5 rounded-lg bg-white hover:bg-neutral-50 transition-all shadow-sm flex items-center gap-1.5"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
                Edit {activeTab === "details" ? "Rent Roll" : activeTab === "omExport" ? "Rent Roll Detailed" : "Unit Breakdown"}
              </button>
            </div>
          ) : (
            <div className="flex gap-2">
              <>
                {activeTab === 'details' && (
                  <button
                    onClick={addItem}
                    className="text-xs font-medium text-neutral-600 hover:text-neutral-900 border border-neutral-200 px-3 py-1.5 rounded-lg bg-white hover:bg-neutral-50 transition-all shadow-sm"
                  >
                    + Add Unit
                  </button>
                )}
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
                  {isSaving ? (
                      <>
                        <svg className="animate-spin h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Saving...
                      </>
                  ) : "Save Changes"}
                </button>
              </>
            </div>
          )}
        </div>

        {activeTab === 'details' && (
           <div className="overflow-x-auto">
           <DndContext
             sensors={sensors}
             collisionDetection={closestCenter}
             onDragEnd={handleDragEnd}
           >
             <table className="w-full text-center text-sm">
               <thead>
                 <tr className="bg-neutral-900 border-b border-neutral-900 text-xs text-white uppercase tracking-wider font-semibold whitespace-nowrap">
                 <th className="px-4 py-3 text-center min-w-[150px]">Unit #</th>
                 <th className="px-4 py-3 text-center">Vacant</th>
                 {hasTenantName && !isEditing && isNonOMFlow && <th className="px-4 py-3 text-center">Tenant</th>}
                 <th className="px-4 py-3 text-center">Unit Size</th>
                 <th className="px-4 py-3 text-center">Unit Type</th>
                 <th className="px-4 py-3 text-center">Current Rent</th>
                 <th className="px-4 py-3 text-center">
                   <div className="flex items-center justify-center gap-1">
                     Market Rent
                     {isNonOMFlow && (
                       <WidgetTooltip
                         title="Market Rent Calculation"
                         description="Since the Offering Memorandum (OM) is unavailable, Market Rent is calculated as the average rent of non-vacant units of the same unit type."
                       />
                     )}
                   </div>
                 </th>
                 {hasDeposits && <th className="px-4 py-3 text-center">Deposit</th>}
                 {hasParking && <th className="px-4 py-3 text-center">Parking</th>}
                 {hasComments && <th className="px-4 py-3 text-center">Comments</th>}
                 {hasMoveInDate && <th className="px-4 py-3 text-center">Move-In Date</th>}
                 {hasFloor && <th className="px-4 py-3 text-center">Floor</th>}
                 <th className="px-4 py-3 text-center">Lease Start</th>
                 <th className="px-4 py-3 text-center">Lease End</th>
                   {isEditing && <th className="px-4 py-3 text-center">Action</th>}
                 </tr>
               </thead>
               <tbody className="divide-y divide-neutral-100">
                 <SortableContext
                   items={visibleItems.map((item) => item.id)}
                   strategy={verticalListSortingStrategy}
                 >
                   {visibleItems.map((item, idx) => (
                     <SortableRow
                       key={item.id}
                       item={item}
                       idx={idx}
                       isEditing={isEditing}
                       errors={rowErrors[item.id]}
                       handleItemChange={handleItemChangeById}
                       handleNumericChange={handleNumericChangeById}
                       formatCurrency={formatCurrency}
                       removeItem={removeItemById}
                       hasDeposits={hasDeposits}
                       hasParking={hasParking}
                       hasComments={hasComments}
                       hasMoveInDate={hasMoveInDate}
                       hasFloor={hasFloor}
                       hasTenantName={hasTenantName && isNonOMFlow}
                     />
                   ))}
                 </SortableContext>
                 {visibleItems.length === 0 && (
                   <tr>
                     <td colSpan={15} className="px-6 py-8 text-center text-neutral-500 text-sm">
                       No rent roll data available.
                     </td>
                   </tr>
                 )}
               </tbody>
               <tfoot className="bg-neutral-900 text-white border-t border-neutral-800">
                {/* Header Row */}
                <tr className="text-xs font-semibold uppercase tracking-wider border-b border-neutral-800">
                  <td className="px-4 py-3 text-center">Total Units</td>
                  <td colSpan={(hasTenantName && isNonOMFlow) ? (isEditing ? 1 : 2) : 1} className="px-4 py-3"></td>
                  <td className="px-4 py-3 text-center">Avg Unit Size</td>
                  <td colSpan={1} className="px-4 py-3"></td>
                  <td className="px-4 py-3 text-center">Current Rent</td>
                  <td className="px-4 py-3 text-center">Market Rent</td>
                  <td colSpan={10}></td>
                </tr>
                {/* Data Row */}
                <tr className="border-b border-neutral-800/50 align-top">
                  <td className="px-4 py-3 text-center">
                    <div className="font-bold text-lg">{displaySummary.total_units}</div>
                  </td>
                  <td colSpan={(hasTenantName && isNonOMFlow) ? (isEditing ? 1 : 2) : 1} className="px-4 py-3"></td>
                  <td className="px-4 py-3 text-center">
                     <div className="font-bold text-lg">{Math.round(displaySummary.avg_unit_size || 0)}</div>
                  </td>
                  <td colSpan={1} className="px-4 py-3"></td>
                  <td className="px-4 py-3 text-center">
                     <div className="text-xs space-y-1">
                       <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Monthly</span> <span className="font-bold">{formatCurrency(displaySummary.total_monthly_rent)}</span></div>
                       <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Annual</span> <span className="font-bold">{formatCurrency(displaySummary.total_annual_rent)}</span></div>
                       <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Avg Unit</span> <span className="font-bold">{formatCurrency(displaySummary.avg_rent_per_unit)}</span></div>
                       <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Avg SF</span> <span className="font-bold">${Math.round(displaySummary.avg_rent_per_sf || 0)}</span></div>
                     </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                     <div className="text-xs space-y-1">
                       <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Monthly</span> <span className="font-bold">{formatCurrency(displaySummary.total_market_rent)}</span></div>
                       <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Annual</span> <span className="font-bold">{formatCurrency((displaySummary.total_market_rent || 0) * 12)}</span></div>
                       <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Avg Unit</span> <span className="font-bold">{formatCurrency(displaySummary.avg_market_per_unit)}</span></div>
                       <div className="flex justify-between gap-4"><span className="text-neutral-400 font-normal">Avg SF</span> <span className="font-bold">${Math.round(displaySummary.avg_market_per_sf || 0)}</span></div>
                     </div>
                  </td>
                  <td colSpan={10}></td>
                </tr>
             </tfoot>
             </table>
           </DndContext>
         </div>
        )}
        {activeTab === 'omExport' && (
          <div className="overflow-x-auto horizontal-scrollbar">
            <table className="min-w-full text-center text-sm whitespace-nowrap">
            <thead className="bg-neutral-900 text-white text-xs uppercase font-semibold">
              <tr>
                <th colSpan={1} className="px-4 py-2 text-center border-b border-r border-neutral-800"></th>
                <th colSpan={5} className="px-4 py-2 text-center border-b border-r border-neutral-800 bg-neutral-800">Unit Mix Summary</th>
                  <th colSpan={1} className="px-4 py-2 text-center border-b border-r border-neutral-800 bg-neutral-700">Current Effective</th>
                  <th colSpan={3} className="px-4 py-2 text-center border-b border-r border-neutral-800 bg-neutral-800">Pro Forma Rents</th>
                  <th colSpan={2} className="px-4 py-2 text-center border-b border-r border-neutral-800 bg-neutral-700">Pro Forma Rent Comparison</th>
                  <th colSpan={6} className="px-4 py-2 text-center border-b border-r border-neutral-800 bg-neutral-800">Notes on Tenancy</th>
                </tr>
                <tr className="tracking-wider whitespace-nowrap">
                  <th className="px-4 py-3 border-r sticky left-0 bg-neutral-900 z-10 text-center">Unit</th>
                  <th className="px-4 py-3 border-r sticky left-[4rem] bg-neutral-900 z-10 text-center">Occupancy Type</th>
                  <th className="px-4 py-3 border-r text-center">Beds</th>
                  <th className="px-4 py-3 border-r text-center">Size</th>
                  <th className="px-4 py-3 border-r text-center">$/Month</th>
                  <th className="px-4 py-3 border-r text-center">
                    <div className="flex items-center justify-center gap-1">
                      $/SF
                      <WidgetTooltip
                        title="Rent per Square Foot (Annual)"
                        description="The annualized rent calculated on a per-square-foot basis."
                        formulas={[{ label: "$/SF", formula: "(Current Rent * 12) / Unit Size" }]}
                      />
                    </div>
                </th>
                <th className="px-4 py-3 border-r text-center">$/Month</th>
                <th className="px-4 py-3 border-r text-center">
                    <div className="flex items-center justify-center gap-1">
                      $/SqFt
                      <WidgetTooltip
                        title="Pro Forma Rent per Square Foot (Annual)"
                        description="The annualized pro forma market rent calculated on a per-square-foot basis."
                        formulas={[{ label: "$/SqFt", formula: "(Market Rent * 12) / Unit Size" }]}
                      />
                    </div>
                  </th>
                  <th className="px-4 py-3 border-r text-center">
                    <div className="flex items-center justify-center gap-1">
                      $ Increase
                      <WidgetTooltip
                        title="Rent Increase ($)"
                        description="The dollar amount difference between the pro forma market rent and the current rent."
                        formulas={[{ label: "$ Increase", formula: "Market Rent - Current Rent" }]}
                      />
                    </div>
                  </th>
                  <th className="px-4 py-3 border-r text-center">
                    <div className="flex items-center justify-center gap-1">
                      % Increase
                      <WidgetTooltip
                        title="Rent Increase (%)"
                        description="The percentage increase from the current rent to the pro forma market rent."
                        formulas={[{ label: "% Increase", formula: "((Market Rent - Current Rent) / Current Rent) * 100" }]}
                      />
                    </div>
                  </th>
                  <th className="px-4 py-3 border-r text-center">Pro Forma Unit Type</th>
                  <th className="px-4 py-3 border-r text-center">Unit Config</th>
                  <th className="px-4 py-3 border-r text-center">Beds</th>
                  <th className="px-4 py-3 border-r text-center">RC</th>
                  <th className="px-4 py-3 border-r text-center">Start Date</th>
                  <th className="px-4 py-3 text-center">End Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {visibleItems.map((item, idx) => {
                  const config = studentHousingConfig?.unit_type_configs.find(c => c.unit_type === item.unit_type);
                  // Prioritize bed_count from the item, fall back to config, then to 1.
                  const bedCount = (item as any).bed_count || config?.bed_count || getBedCountFromUnitType(item.unit_type);
                  return (
                    <tr key={item.id} className="hover:bg-neutral-50/50 transition-colors">
                      <td className="px-4 py-2.5 sticky left-0 bg-white group-hover:bg-neutral-50/50 text-center">
                        {isEditing ? (
                          <input type="text" value={item.unit_number || ""} onChange={(e) => handleItemChangeById(item.id, "unit_number", e.target.value)} className="w-32 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none" />
                        ) : (
                          item.unit_number
                        )}
                      </td>
                      <td className="px-4 py-2.5 sticky left-[4rem] bg-white group-hover:bg-neutral-50/50 text-center">
                        {isEditing ? (
                          <input type="text" value={item.unit_type || ""} onChange={(e) => handleItemChangeById(item.id, "unit_type", e.target.value)} className="w-24 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none" />
                        ) : (
                          item.unit_type
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        {isEditing ? (
                            <input
                              type="text"
                              value={bedCount}
                              onChange={(e) => handleItemChangeById(item.id, "bed_count" as any, parseInt(e.target.value) || 0)}
                              className="w-12 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
                            />
                        ) : (
                            bedCount
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        {isEditing ? (
                          <input type="text" value={item.unit_size} onChange={(e) => handleNumericChangeById(item.id, "unit_size", e.target.value)} className="w-20 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none" />
                        ) : (
                          item.unit_size
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        {isEditing ? (
                          <input type="text" value={item.current_rent} onChange={(e) => handleNumericChangeById(item.id, "current_rent", e.target.value)} className="w-24 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none" />
                        ) : (
                          formatCurrency(Number(item.current_rent))
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-center">${Math.round(Number(item.current_rent) * 12 / (Number(item.unit_size) || 1))}</td>
                      <td className="px-4 py-2.5 text-center">
                        {isEditing ? (
                          <input type="text" value={item.market_rent} onChange={(e) => handleNumericChangeById(item.id, "market_rent", e.target.value)} className="w-24 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none" />
                        ) : (
                          formatCurrency(Number(item.market_rent))
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-center">${Math.round(Number(item.market_rent) * 12 / (Number(item.unit_size) || 1))}</td>
                      <td className="px-4 py-2.5 text-center">
                        {isEditing ? (
                          <input
                            type="text"
                            value={Math.round(Number(item.market_rent) - Number(item.current_rent))}
                            onChange={(e) => {
                              const diff = parseFloat(e.target.value) || 0;
                              handleItemChangeById(item.id, "market_rent", Math.round(Number(item.current_rent) + diff));
                            }}
                            className="w-20 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
                          />
                        ) : (
                          formatCurrency(Number(item.market_rent) - Number(item.current_rent))
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        {isEditing ? (
                           <div className="flex items-center justify-center gap-1">
                              <input
                                type="text"
                                value={Number(item.current_rent) > 0 ? Math.round(((Number(item.market_rent) - Number(item.current_rent)) / Number(item.current_rent)) * 100) : "0"}
                                onChange={(e) => {
                                  const val = e.target.value;
                                  if (val === "") return;
                                  const percent = parseFloat(val) || 0;
                                  handleItemChangeById(item.id, "market_rent", Math.round(Number(item.current_rent) * (1 + percent / 100)));
                                }}
                                className="w-16 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
                              />
                              <span className="text-[10px] text-neutral-400">%</span>
                           </div>
                        ) : (
                          Number(item.current_rent) > 0 ? `${Math.round(((Number(item.market_rent) - Number(item.current_rent)) / Number(item.current_rent)) * 100)}%` : "0%"
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                          {isEditing ? (
                              <input type="text" value={item.unit_type || ""} onChange={(e) => handleItemChangeById(item.id, "unit_type", e.target.value)} className="w-24 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none" />
                          ) : (
                              item.unit_type
                          )}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                          {isEditing ? (
                              <input type="text" value={item.unit_config_label || item.unit_type || ""} onChange={(e) => handleItemChangeById(item.id, "unit_config_label" as any, e.target.value)} className="w-24 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none" />
                          ) : (
                              item.unit_config_label || item.unit_type
                          )}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                          {isEditing ? (
                              <input
                                type="text"
                                value={bedCount}
                                onChange={(e) => handleItemChangeById(item.id, "bed_count" as any, parseInt(e.target.value) || 0)}
                                className="w-12 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
                              />
                          ) : (
                              bedCount
                          )}
                      </td>
                      <td className="px-4 py-2.5 text-center">{(item.unit_type || "").toLowerCase().includes('rent control') ? 'RC' : '-'}</td>
                      <td className="px-4 py-2.5 text-center">
                        {isEditing ? (
                          <input type="date" value={toInputDate(item.lease_start)} onChange={(e) => handleItemChangeById(item.id, "lease_start", fromInputDate(e.target.value))} className="w-28 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none" />
                        ) : (
                           (formatDateOnly(item.lease_start) && formatDateOnly(item.lease_start).toUpperCase() !== "V") ? formatDateOnly(item.lease_start) : "-"
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        {isEditing ? (
                          <input type="date" value={toInputDate(item.lease_end)} onChange={(e) => handleItemChangeById(item.id, "lease_end", fromInputDate(e.target.value))} className="w-28 bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none" />
                        ) : (
                          (formatDateOnly(item.lease_end) && formatDateOnly(item.lease_end).toUpperCase() !== "V") ? formatDateOnly(item.lease_end) : "-"
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
       {activeTab === 'unitBreakdown' && (
          <UnitBreakdownTable
            rentRoll={visibleItems}
            studentHousingConfig={studentHousingConfig}
            isEditing={isEditing}
            onItemChange={handleUnitBreakdownChange}
            formatCurrency={formatCurrency}
          />
       )}
       {activeTab === 'unitBreakdownStabilized' && (
         <UnitBreakdownStabilizedTable
           rentRoll={visibleItems}
           studentHousingConfig={studentHousingConfig}
            isEditing={isEditing}
            onItemChange={handleUnitBreakdownChange}
          />
       )}
      </div>

      {/* Rent Roll Summary Table */}
      {activeTab === 'details' && (
        <div className="mt-8">
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm overflow-hidden">
            <div className="bg-neutral-900 px-6 py-3 text-center border-b border-neutral-900">
              <h3 className="text-white font-medium">Rent Roll Summary</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-center text-sm">
                <thead>
                  <tr className="border-b border-neutral-200 text-xs text-neutral-900 font-bold whitespace-nowrap">
                    <th className="px-6 py-3 text-center">Unit Mix</th>
                    <th className="px-6 py-3 text-center">Unit Count</th>
                    <th className="px-6 py-3 text-center">%</th>
                    <th className="px-6 py-3 text-center">Avg. Current Rent</th>
                    <th className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        Market Rent
                        {isNonOMFlow && (
                          <WidgetTooltip
                            title="Market Rent Calculation"
                            description="Since the Offering Memorandum (OM) is unavailable, Market Rent is calculated as the average rent of non-vacant units of the same unit type."
                          />
                        )}
                      </div>
                    </th>
                    <th className="px-6 py-3 text-center">Avg. Sq Ft</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {summaryGroups.map((group, idx) => (
                    <tr key={idx} className="hover:bg-neutral-50/50 transition-colors">
                      <td className="px-6 py-3 font-medium text-neutral-900 text-center">{group.type}</td>
                      <td className="px-6 py-3 text-center text-neutral-600">{group.count}</td>
                      <td className="px-6 py-3 text-center text-neutral-600">{formatPercent(group.percent)}</td>
                      <td className="px-6 py-3 text-center text-neutral-600">{group.avgCurrentRent === 0 ? "-" : formatCurrency(group.avgCurrentRent)}</td>
                      <td className="px-6 py-3 text-center text-neutral-600">{formatCurrency(group.avgMarketRent)}</td>
                      <td className="px-6 py-3 text-center text-neutral-600">{Math.round(group.avgSqFt)}</td>
                    </tr>
                  ))}
                  {/* Totals Row */}
                  <tr className="border-t-2 border-neutral-900 font-bold bg-white">
                    <td className="px-6 py-4 text-neutral-900 text-center">Totals/Average</td>
                    <td className="px-6 py-4 text-center text-neutral-900">{displaySummary.total_units}</td>
                    <td className="px-6 py-4 text-center text-neutral-900">100%</td>
                    <td className="px-6 py-4 text-center text-neutral-900">
                      {formatCurrency(displaySummary.occupied_units > 0 ? displaySummary.total_monthly_rent / displaySummary.occupied_units : 0)}
                    </td>
                    <td className="px-6 py-4 text-center text-neutral-900">{formatCurrency(displaySummary.avg_market_per_unit)}</td>
                    <td className="px-6 py-4 text-center text-neutral-900">{Math.round(displaySummary.avg_unit_size)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
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
  handleNumericChange,
  formatCurrency,
  removeItem,
  hasDeposits,
  hasParking,
  hasComments,
  hasMoveInDate,
  hasFloor,
  hasTenantName,
}: {
  item: EditableRentRollItem;
  idx: number;
  isEditing: boolean;
  errors?: Record<string, string>;
  handleItemChange: (id: string, field: keyof EditableRentRollItem, value: any) => void;
  handleNumericChange: (id: string, field: keyof EditableRentRollItem, value: string) => void;
  formatCurrency: (val: number) => string;
  removeItem: (id: string) => void;
  hasDeposits: boolean;
  hasParking: boolean;
  hasComments: boolean;
  hasMoveInDate: boolean;
  hasFloor?: boolean;
  hasTenantName?: boolean;
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
        isDragging ? "bg-neutral-50 shadow-md" : errors ? "bg-rose-50" : "bg-white"
      } ${
        errors ? "border-l-rose-500 bg-rose-50/10" : "border-l-transparent"
      }`}
    >
      <td className="px-4 py-2.5 font-medium text-neutral-900 text-center min-w-[150px]">
        <div className="flex items-center justify-center gap-2">
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
                value={item.unit_number || ""}
                placeholder={item.unit_type || ""}
                onChange={(e) => handleItemChange(item.id, "unit_number", e.target.value)}
                className={`w-full bg-white border rounded px-2 py-1 text-xs text-center focus:ring-1 focus:outline-none ${
                  errors?.unit_number ? "border-rose-500 bg-rose-50 focus:ring-rose-500" : "border-neutral-200 focus:ring-neutral-900"
                }`}
              />
              {errors?.unit_number && <div className="text-[10px] text-rose-600 mt-1">{errors.unit_number}</div>}
            </div>
          ) : (
            item.unit_number || item.unit_type || "-"
          )}
        </div>
      </td>
      <td className="px-4 py-2.5 text-center">
        <input
            type="checkbox"
            checked={item.is_vacant || false}
            disabled={!isEditing}
            onChange={(e) => handleItemChange(item.id, "is_vacant", e.target.checked)}
            className="w-4 h-4 accent-neutral-900 border-neutral-300 rounded focus:ring-neutral-900"
        />
      </td>
      {hasTenantName && !isEditing && (
        <td className="px-4 py-2.5 text-center text-neutral-600">
          {item.tenant_name || "-"}
        </td>
      )}
      <td className="px-4 py-2.5 text-center text-neutral-600">
        {isEditing ? (
          <div className="w-20 mx-auto">
            <input
              type="text"
              value={item.unit_size}
              onChange={(e) => handleNumericChange(item.id, "unit_size", e.target.value)}
              className={`w-full bg-white border rounded px-2 py-1 text-xs text-center focus:ring-1 focus:outline-none ${
                errors?.unit_size ? "border-rose-500 bg-rose-50 focus:ring-rose-500" : "border-neutral-200 focus:ring-neutral-900"
              }`}
            />
            {errors?.unit_size && <div className="text-[10px] text-rose-600 mt-1">{errors.unit_size}</div>}
          </div>
        ) : (
          item.unit_size || "-"
        )}
      </td>
      <td className="px-4 py-2.5 text-neutral-600 text-center">
        {isEditing ? (
          <div className="w-full">
            <input
              type="text"
              value={item.unit_type || ""}
              onChange={(e) => handleItemChange(item.id, "unit_type", e.target.value)}
              className={`w-full bg-white border rounded px-2 py-1 text-xs text-center focus:ring-1 focus:outline-none ${
                errors?.unit_type ? "border-rose-500 bg-rose-50 focus:ring-rose-500" : "border-neutral-200 focus:ring-neutral-900"
              }`}
            />
            {errors?.unit_type && <div className="text-[10px] text-rose-600 mt-1">{errors.unit_type}</div>}
          </div>
        ) : (
          item.unit_type
        )}
      </td>
      <td className="px-4 py-2.5 text-center font-medium text-neutral-900">
        {isEditing ? (
          <div className="w-20 mx-auto">
            <input
              type="text"
              value={item.current_rent}
              onChange={(e) => handleNumericChange(item.id, "current_rent", e.target.value)}
              className={`w-full bg-white border rounded px-2 py-1 text-xs text-center focus:ring-1 focus:outline-none ${
                errors?.current_rent ? "border-rose-500 bg-rose-50 focus:ring-rose-500" : "border-neutral-200 focus:ring-neutral-900"
              }`}
            />
            {errors?.current_rent && <div className="text-[10px] text-rose-600 mt-1">{errors.current_rent}</div>}
          </div>
        ) : (
          formatCurrency(typeof item.current_rent === 'number' ? item.current_rent : parseFloat(item.current_rent) || 0)
        )}
      </td>
      <td className="px-4 py-2.5 text-center text-neutral-600">
        {isEditing ? (
          <div className="w-20 mx-auto">
            <input
              type="text"
              value={item.market_rent}
              onChange={(e) => handleNumericChange(item.id, "market_rent", e.target.value)}
              className={`w-full bg-white border rounded px-2 py-1 text-xs text-center focus:ring-1 focus:outline-none ${
                errors?.market_rent ? "border-rose-500 bg-rose-50 focus:ring-rose-500" : "border-neutral-200 focus:ring-neutral-900"
              }`}
            />
            {errors?.market_rent && <div className="text-[10px] text-rose-600 mt-1">{errors.market_rent}</div>}
          </div>
        ) : (
          formatCurrency(typeof item.market_rent === 'number' ? item.market_rent : parseFloat(item.market_rent) || 0)
        )}
      </td>

      {hasDeposits && (
        <td className="px-4 py-2.5 text-center text-neutral-600">
          {isEditing ? (
            <div className="w-20 mx-auto">
              <input
                type="text"
                value={item.deposit}
                onChange={(e) => handleNumericChange(item.id, "deposit", e.target.value)}
                className="w-full bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
              />
            </div>
          ) : (
            formatCurrency(typeof item.deposit === 'number' ? item.deposit : parseFloat(item.deposit) || 0)
          )}
        </td>
      )}

      {hasParking && (
        <td className="px-4 py-2.5 text-neutral-600 text-center">
          {isEditing ? (
            <input
              type="text"
              value={item.parking || ""}
              onChange={(e) => handleItemChange(item.id, "parking", e.target.value)}
              className="w-full bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
            />
          ) : (
            (item.parking && item.parking !== "-") ? item.parking : "-"
          )}
        </td>
      )}

      {hasComments && (
        <td className="px-4 py-2.5 text-neutral-600 text-center">
           {isEditing ? (
            <input
              type="text"
              value={item.comments || ""}
              onChange={(e) => handleItemChange(item.id, "comments", e.target.value)}
              className="w-full bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
            />
          ) : (
            <span className="truncate max-w-[150px] block mx-auto" title={item.comments}>{(item.comments && item.comments !== "-") ? item.comments : "-"}</span>
          )}
        </td>
      )}
      {hasMoveInDate && (
        <td className="px-4 py-2.5 text-center text-neutral-500 text-xs">
          {isEditing ? (
            <input
              type="date"
              value={toInputDate(item.move_in_date)}
              min="1900-01-01"
              max="2100-12-31"
              onChange={(e) => handleItemChange(item.id, "move_in_date", fromInputDate(e.target.value))}
              className={`w-28 mx-auto bg-white border rounded px-2 py-1 text-xs text-center focus:ring-1 focus:outline-none ${
                errors?.move_in_date ? "border-rose-500 bg-rose-50 focus:ring-rose-500" : "border-neutral-200 focus:ring-neutral-900"
            }`}
          />
          ) : (
            (formatDateOnly(item.move_in_date) && formatDateOnly(item.move_in_date).toUpperCase() !== "V") ? formatDateOnly(item.move_in_date) : "-"
          )}
          {errors?.move_in_date && <div className="text-[10px] text-rose-600 mt-1">{errors.move_in_date}</div>}
        </td>
      )}
      {hasFloor && (
        <td className="px-4 py-2.5 text-center text-neutral-600">
           {isEditing ? (
            <input
              type="text"
              value={(item as any).floor || ""}
              onChange={(e) => handleItemChange(item.id, "floor" as any, e.target.value)}
              className="w-full bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-center focus:ring-1 focus:ring-neutral-900 focus:outline-none"
            />
          ) : (
            (item as any).floor || "-"
          )}
        </td>
      )}
      <td className="px-4 py-2.5 text-center text-neutral-500 text-xs">
        {isEditing ? (
          <div className="w-28 mx-auto">
            <input
              type="date"
              value={toInputDate(item.lease_start)}
              min="1900-01-01"
              max="2100-12-31"
              onChange={(e) => handleItemChange(item.id, "lease_start", fromInputDate(e.target.value))}
              className={`w-full bg-white border rounded px-2 py-1 text-xs text-center focus:ring-1 focus:outline-none ${
                errors?.lease_start ? "border-rose-500 bg-rose-50 focus:ring-rose-500" : "border-neutral-200 focus:ring-neutral-900"
              }`}
            />
             {errors?.lease_start && <div className="text-[10px] text-rose-600 mt-1">{errors.lease_start}</div>}
          </div>
        ) : (
          (formatDateOnly(item.lease_start) && formatDateOnly(item.lease_start).toUpperCase() !== "V") ? formatDateOnly(item.lease_start) : "-"
        )}
      </td>
      <td className="px-4 py-2.5 text-center text-neutral-500 text-xs">
        {isEditing ? (
          <input
            type="date"
            value={toInputDate(item.lease_end)}
            min="1900-01-01"
            max="2100-12-31"
            onChange={(e) => handleItemChange(item.id, "lease_end", fromInputDate(e.target.value))}
           className={`w-full bg-white border rounded px-2 py-1 text-xs text-center focus:ring-1 focus:outline-none ${
              errors?.lease_end ? "border-rose-500 bg-rose-50 focus:ring-rose-500" : "border-neutral-200 focus:ring-neutral-900"
          }`}
        />
        ) : (
          (formatDateOnly(item.lease_end) && formatDateOnly(item.lease_end).toUpperCase() !== "V") ? formatDateOnly(item.lease_end) : "-"
        )}
        {errors?.lease_end && <div className="text-[10px] text-rose-600 mt-1">{errors.lease_end}</div>}
      </td>
      {isEditing && (
        <td className="px-4 py-2.5 text-center">
          <button
            onClick={() => removeItem(item.id)}
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
