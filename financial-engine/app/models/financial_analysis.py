from pydantic import BaseModel, Field, field_validator
from enum import Enum
from typing import List, Optional, Union, Dict, Any

# --- 1. Enums (The Valiance Dictionary) ---
class ExpenseCategory(str, Enum):
    TAXES = "Property Taxes"
    INSURANCE = "Insurance"
    REPAIRS = "Repairs & Maintenance"
    MANAGEMENT = "Management Fees"
    UTILITIES = "Utilities"
    PAYROLL = "Payroll"
    MARKETING = "Marketing"
    ADMINISTRATIVE = "Administrative"
    OTHER = "Other"

# --- 2. Audit & Provenance ---
class AuditLog(BaseModel):
    field_name: str
    extracted_value: Any
    source_doc: str      # e.g., "Keystone_OM.pdf"
    source_page: Optional[int] = None
    confidence_score: float # 0.0 to 1.0
    reasoning: Optional[str] = None # "Found in table header on page 4"

# --- 3. Rent Roll Schema ---
class RentRollItem(BaseModel):
    unit_number: str = Field(..., alias="Unit #") # Required
    unit_type: str = Field(..., alias="Unit Type")
    tenant_name: Optional[str] = Field(None, alias="Tenant Name")
    current_rent: float = Field(..., alias="Current Rent")
    market_rent: Optional[float] = Field(None, alias="Market Rent")
    lease_start: Optional[str] = Field(None, alias="Lease Start")
    lease_end: Optional[str] = Field(None, alias="Lease End")

# --- 4. Expense Schema ---
class StandardizedExpense(BaseModel):
    original_text: str  # What the PDF said
    mapped_category: ExpenseCategory # What we mapped it to
    amount: float
    period: str = "Annual" # T12 is usually annual
    audit_log: AuditLog # <--- LINKED HERE for explainability

# --- 5. High Level Objects ---
class PropertyMeta(BaseModel):
    address: str
    year_built: int
    purchase_price: float
    total_units: int

class RentRollSummary(BaseModel):
    total_units: int
    occupancy_rate: float # 0.0 to 1.0
    average_rent_per_unit_type: Dict[str, float]

class DealParameters(BaseModel):
    rent_growth: float = 0.03
    vacancy_rate: float = 0.03
    expense_ratio: float = 0.38
    exit_cap_rate: float = 0.06

# --- 6. The Master Payload (API Response) ---
class UnderwritingAnalysis(BaseModel):
    document_id: str
    pass_fail_status: str # "PASS" | "FAIL"
    gating_reasons: List[str] = []
    
    # Ingestion Data
    property_meta: PropertyMeta
    rent_roll: List[RentRollItem]
    rent_roll_summary: RentRollSummary
    historical_expenses: List[StandardizedExpense]
    
    # Logic Data (Calculated Day 2)
    pro_forma_noi: Optional[float] = 0.0
    cap_rate: Optional[float] = 0.0