from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any
from enum import Enum

# --- 1. Enums ---
class ExpenseCategory(str, Enum):
    REAL_ESTATE_TAXES = "Real Estate Taxes"
    INSURANCE = "Insurance"
    REPAIRS_MAINTENANCE = "Repairs & Maintenance"
    GENERAL_ADMINISTRATIVE = "General & Administrative"
    PAYROLL = "Payroll"
    UTILITIES = "Utilities"
    MANAGEMENT_FEES = "Management Fees"
    CONTRACT_SERVICES = "Contract Services"
    OTHER_OPERATING_EXPENSES = "Other Operating Expenses"
    CAPITAL_RESERVES = "Capital Reserves"
    ADVERTISING_MARKETING = "Advertising & Marketing"
    LEASING_FEES = "Leasing Fees"
    UNCATEGORIZED = "Uncategorized"

# --- 2. Sub-Models ---
class ProFormaEntry(BaseModel):
    name: str
    t12: float  # Historical
    f12: float  # Pro Forma

class AuditLog(BaseModel):
    field_name: str
    extracted_value: Any
    source_doc: str
    confidence_score: float
    reasoning: str

class PropertyMeta(BaseModel):
    address: Optional[str] = "Unknown"
    year_built: Optional[int] = 0
    purchase_price: Optional[float] = 0.0
    total_units: Optional[int] = 0
    is_renovated: bool = False
    current_loan_balance: Optional[float] = 0.0

class RentRollItem(BaseModel):
    unit_number: str
    unit_type: str
    tenant_name: Optional[str] = "Unknown"
    current_rent: float = 0.0
    market_rent: Optional[float] = 0.0
    lease_start: Optional[str] = None
    lease_end: Optional[str] = None

class RentRollSummary(BaseModel):
    total_units: int
    occupied_units: int
    occupancy_rate: float
    total_monthly_rent: float
    total_annual_rent: float

class ProFormaExpenseItem(BaseModel):
    name: str
    amount: float

class DealParameters(BaseModel):
    growth_rate: float = 0.03
    exit_cap_rate: float = 0.06 
    vacancy_rate: float = 0.03
    loan_amount: float = 5_000_000
    min_unit_count: int = 15
    max_unit_count: int = 80
    max_build_year: int = 1970

class StandardizedExpense(BaseModel):
    original_text: str
    mapped_category: ExpenseCategory
    amount: float
    confidence: float
    audit_log: AuditLog

# --- 3. Main Analysis Model ---
class UnderwritingAnalysis(BaseModel):
    document_id: str
    pass_fail_status: str
    gating_reasons: List[str] = []

    property_meta: PropertyMeta
    rent_roll: List[RentRollItem]
    rent_roll_summary: RentRollSummary
    historical_expenses: List[StandardizedExpense]

    deal_parameters: Optional[DealParameters] = None
    
    audit_trail: List[Dict[str, Any]] = []
    
    pro_forma_expenses_detailed: List[ProFormaExpenseItem] = []

    pro_forma_noi: Optional[float] = 0.0
    pro_forma_expenses: Optional[float] = 0.0
    cap_rate: Optional[float] = 0.0
    exit_cap_rate: Optional[float] = 0.0
    
    historical_noi: Optional[float] = 0.0
    historical_total_expenses: float = 0.0
    historical_cap_rate: Optional[float] = 0.0





# from pydantic import BaseModel
# from typing import List, Optional, Any, Dict
# from enum import Enum

# # --- 1. Enums ---
# class ExpenseCategory(str, Enum):
#     REAL_ESTATE_TAXES = "Real Estate Taxes"
#     INSURANCE = "Insurance"
#     REPAIRS_MAINTENANCE = "Repairs & Maintenance"
#     GENERAL_ADMINISTRATIVE = "General & Administrative"
#     PAYROLL = "Payroll"
#     UTILITIES = "Utilities"
#     MANAGEMENT_FEES = "Management Fees"
#     CONTRACT_SERVICES = "Contract Services"
#     OTHER_OPERATING_EXPENSES = "Other Operating Expenses"
#     CAPITAL_RESERVES = "Capital Reserves"
#     ADVERTISING_MARKETING = "Advertising & Marketing"
#     LEASING_FEES = "Leasing Fees"
#     UNCATEGORIZED = "Uncategorized"


# # --- 2. Sub-Models ---
# class ProFormaEntry(BaseModel):
#     name: str
#     t12: float  # Historical
#     f12: float  # Pro Forma

# class AuditLog(BaseModel):
#     """
#     Ground of Truth Log Entry.
#     Tracks exactly how a value was derived.
#     """
#     field: str
#     value: Any
#     source: str         # e.g., "OM", "T12", "Calculation"
#     method: str         # e.g., "Extracted via OCR", "Formula: EGI * 38%"
#     confidence_score: float = 1.0
#     timestamp: Optional[str] = None

# class PropertyMeta(BaseModel):
#     address: Optional[str] = "Unknown"
#     year_built: Optional[int] = 0
#     purchase_price: Optional[float] = 0.0
#     total_units: Optional[int] = 0
#     is_renovated: bool = False
#     current_loan_balance: Optional[float] = 0.0

# class RentRollItem(BaseModel):
#     unit_number: str
#     unit_type: str
#     tenant_name: Optional[str] = "Unknown"
#     current_rent: float = 0.0 
#     market_rent: float = 0.0
#     lease_start: Optional[str] = None
#     lease_end: Optional[str] = None

# class RentRollSummary(BaseModel):
#     total_units: int
#     occupied_units: int
#     occupancy_rate: float
#     total_monthly_rent: float
#     total_annual_rent: float

# class ProFormaExpenseItem(BaseModel):
#     name: str
#     amount: float

# class DealParameters(BaseModel):
#     growth_rate: float = 0.03
#     exit_cap_rate: float = 0.06 
#     vacancy_rate: float = 0.03
#     loan_amount: float = 5_000_000
#     min_unit_count: int = 15
#     max_unit_count: int = 80
#     max_build_year: int = 1970

# class StandardizedExpense(BaseModel):
#     original_text: str
#     mapped_category: ExpenseCategory
#     amount: float
#     confidence: float
#     audit_log: AuditLog

# # --- 3. Main Analysis Model ---
# class UnderwritingAnalysis(BaseModel):
#     document_id: str
#     pass_fail_status: str
#     gating_reasons: List[str] = []

#     property_meta: PropertyMeta
#     rent_roll: List[RentRollItem]
#     rent_roll_summary: RentRollSummary
    
#     # Historical Data
#     historical_expenses: List[StandardizedExpense] = []
#     historical_gross_income: float = 0.0
#     historical_total_expenses: float = 0.0
#     historical_noi: Optional[float] = 0.0
#     historical_cap_rate: Optional[float] = 0.0
#     debt_yield: Optional[float] = 0.0
#     dscr: Optional[float] = 0.0

#     # Pro Forma Data
#     deal_parameters: Optional[DealParameters] = None
#     pro_forma_expenses_detailed: List[ProFormaExpenseItem] = []
#     pro_forma_gross_income: float = 0.0
#     pro_forma_expenses: Optional[float] = 0.0
#     pro_forma_noi: Optional[float] = 0.0
#     cap_rate: Optional[float] = 0.0
#     exit_cap_rate: Optional[float] = 0.0

#     # The Source of Truth Log
#     audit_trail: List[Dict[str, Any]] = []