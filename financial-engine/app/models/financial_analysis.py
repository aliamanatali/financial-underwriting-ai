from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Optional, Any


class PropertyMeta(BaseModel):
    address: Optional[str] = None
    year_built: Optional[int] = None
    purchase_price: Optional[float] = None
    total_units: Optional[int] = None

class RentRollItem(BaseModel):
    unit_number: Optional[str] = Field(None, alias="Unit #")
    unit_type: Optional[str] = Field(None, alias="Unit Type")
    tenant_name: Optional[str] = Field(None, alias="Tenant Name")
    current_rent: Optional[float] = Field(None, alias="Current Rent")
    market_rent: Optional[float] = Field(None, alias="Market Rent")
    lease_start: Optional[str] = Field(None, alias="Lease Start")
    lease_end: Optional[str] = Field(None, alias="Lease End")

class DealDataInput(BaseModel):
    property_meta: PropertyMeta
    rent_roll: List[RentRollItem]
    closing_costs: float
    holding_period_years: int
    sell_cap_rate: float
    historical_noi: float
    rent_roll_summary: "RentRollSummary"
    normalized_expenses: List["StandardizedExpense"]
    deal_parameters: "DealParameters"
    pro_forma_entries: Optional[List["ProFormaEntry"]] = None


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

class StandardizedExpense(BaseModel):
    original_text: str
    mapped_category: ExpenseCategory
    amount: float
    confidence: float

class ProFormaEntry(BaseModel):
    name: str
    t12: float
    f12: float
class RentRollSummary(BaseModel):
    total_units: int
    occupancy_percentage: float = Field(alias="occupancy_%")
    average_rent_per_unit_type: dict[str, float]

class DealParameters(BaseModel):
    rent_growth: float = 0.03
    vacancy_rate: float = 0.03
    expense_ratio: float = 0.38
    exit_cap_rate: float = 0.06
    exit_cap_rate: float = 0.06

class DealData(BaseModel):
    purchase_price: float
    closing_costs: float
    holding_period_years: int
    sell_cap_rate: float
    pro_forma_entries: Optional[List[ProFormaEntry]] = None
    historical_noi: float
    rent_roll_summary: RentRollSummary
    normalized_expenses: List[StandardizedExpense]
    deal_parameters: DealParameters
class AuditTrail(BaseModel):
    field: str
    value: Any
    source: str
    method: str

class UnderwritingAnalysis(BaseModel):
    document_id: str
    pass_fail_status: str
    reasons: List[str] = []
    normalized_expenses: List[StandardizedExpense]
    rent_roll_summary: RentRollSummary
    pro_forma_noi: float
    cap_rate: float
    pro_forma_entries: Optional[List[ProFormaEntry]] = None
    audit_trail: List[AuditTrail]