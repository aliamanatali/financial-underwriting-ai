from pydantic import BaseModel, Field
from typing import List, Optional, Union

class PropertyMeta(BaseModel):
    address: str
    year_built: int
    purchase_price: float
    total_units: int

class RentRollItem(BaseModel):
    unit_number: str = Field(alias="Unit #")
    unit_type: str = Field(alias="Unit Type")
    tenant_name: str = Field(alias="Tenant Name")
    current_rent: float = Field(alias="Current Rent")
    market_rent: float = Field(alias="Market Rent")
    lease_start: str = Field(alias="Lease Start")
    lease_end: str = Field(alias="Lease End")

class FinancialLineItem(BaseModel):
    category: str
    value: Union[float, int]
    period: str  # "Monthly" or "Annual"
    type: str  # "Historical" or "ProForma"

class DealParameters(BaseModel):
    growth_rate: float
    exit_cap_rate: float = Field(alias="exit_cap")

class UnderwritingAnalysis(BaseModel):
    property_meta: PropertyMeta
    rent_roll: List[RentRollItem]
    operating_expenses: List[FinancialLineItem]
    pro_forma: List[FinancialLineItem]
    deal_parameters: DealParameters