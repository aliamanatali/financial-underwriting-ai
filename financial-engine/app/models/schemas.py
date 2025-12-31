from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any
from enum import Enum
class ProFormaEntry(BaseModel):
    name: str
    t12: float  # Historical
    f12: float  # Pro Forma

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

class RentRollItem(BaseModel):
    unit_number: str = Field(alias="Unit #")
    unit_type: str = Field(alias="Unit Type")
    tenant_name: str = Field(alias="Tenant Name")
    current_rent: float = Field(alias="Current Rent")
    market_rent: float = Field(alias="Market Rent")
    lease_start: str = Field(alias="Lease Start")
    lease_end: str = Field(alias="Lease End")

class RentRollSummary(BaseModel):
    total_units: int
    occupied_units: int
    occupancy_rate: float
    total_monthly_rent: float
    total_annual_rent: float

class FinancialLineItem(BaseModel):
    category: str
    value: Union[float, int]
    period: str  # "Monthly" or "Annual"
    type: str  # "Historical" or "ProForma"

class DealParameters(BaseModel):
    """
    Valiance Standard Assumptions.
    These parameters define the standard underwriting criteria for Valiance Capital.
    """
    model_config = {"populate_by_name": True}
    
    growth_rate: float = 0.03
    exit_cap_rate: float = Field(alias="exit_cap", default=0.06)
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

class UnderwritingAnalysis(BaseModel):
    document_id: str
    pass_fail_status: str
    gating_reasons: List[str] = []

    property_meta: PropertyMeta
    rent_roll: List[RentRollItem]
    rent_roll_summary: RentRollSummary
    normalized_expenses: List[StandardizedExpense]

    # --- ADD THESE ---
    deal_parameters: Optional[DealParameters] = None
    audit_trail: List[Dict[str, Any]] = [] # For the general audit logs

    pro_forma_noi: Optional[float] = 0.0
    cap_rate: Optional[float] = 0.0