from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any
from enum import Enum

# --- 1. Enums ---

class DocumentType(str, Enum):
    """
    The 8 document categories that constitute the inputs for underwriting analysis.
    Each folder will contain documents of a specific type.
    """
    OFFERING_MEMORANDUM = "Offering Memorandum"
    RENT_ROLL = "Rent Roll"
    LEASES = "Leases"
    FINANCIALS = "Financials"  # T12, P&L statements, etc.
    BUILDING_PLANS_PERMITS = "Building Plans & Permits"
    DISCLOSURES = "Disclosures"
    TAX_BILLS = "Tax Bills"
    UTILITIES = "Utilities"


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
    source: str
    confidence_score: float
    method: str
    timestamp: Optional[str] = None

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
    # Revenue & Expense Assumptions
    growth_rate: float = 0.03
    vacancy_rate: float = 0.03
    management_fee_rate: float = 0.04
    expense_ratio_target: float = 0.38
    tax_rate: float = 0.012  # ~1.2% for CA
    
    # Exit Assumptions
    exit_cap_rate: float = 0.06
    sales_cost_rate: float = 0.02
    hold_period: int = 5
    
    # Loan/Debt Assumptions
    ltv: float = 0.65  # Loan to Value
    loan_amount: Optional[float] = None # Manual override for loan amount
    sofr_rate: float = 0.053 # Base rate
    bridge_spread: float = 0.02 # Spread over SOFR
    treasury_rate_5yr: float = 0.042 # 5-Year US Treasury Rate
    perm_spread: float = 0.0185 # 185 bps over Treasuries
    
    # Project Cost Assumptions
    closing_costs: float = 100_000.0
    renovation_budget: float = 0.0
    
    # Gating Thresholds
    min_loan_amount: float = 5_000_000
    min_unit_count: int = 15
    max_unit_count: int = 80
    max_build_year: int = 1970

class StandardizedExpense(BaseModel):
    original_text: str
    mapped_category: ExpenseCategory
    amount: float
    confidence: float
    audit_log: AuditLog
    user_verified: bool = False  # Track if user has manually verified/corrected this mapping
    user_corrected_category: Optional[ExpenseCategory] = None  # If user changed the mapping

# --- 2.2 Explainability Models ---

class ExplanationSource(BaseModel):
    document: str  # e.g., "T12", "Rent Roll", "User Input", "Assumption Engine"
    fields_used: List[str]  # e.g., ["Effective Gross Income", "Total Operating Expenses"]
    data_type: str  # "Direct", "User-provided", "Derived"

class ExplanationCalculation(BaseModel):
    formula: str  # e.g., "NOI = Effective Gross Income - Total Operating Expenses"
    inputs: Dict[str, Any]  # e.g., {"Effective Gross Income": 480000.00, ...}

class ExplainabilityMetadata(BaseModel):
    metric: str  # e.g., "Net Operating Income (NOI)"
    value: Any
    source: ExplanationSource
    calculation: ExplanationCalculation
    adjustments: List[str]  # e.g., ["Value floored at $0"]
    classification: str  # "Direct", "Derived", "Derived with Assumptions", "Derived with Safeguards", "Invalid / Not Meaningful"

class DecisionImpact(BaseModel):
    metric: str
    decision: str  # What the AI decided/calculated
    reasoning: str # How it came with the decision
    impact: str    # Impact for the client

class InvestmentChecklist(BaseModel):
    is_multifamily: str = "Unknown"
    near_campus: str = "Unknown"
    business_plan: str = "Unknown"
    rents_below_market: str = "Unknown"
    is_mismanaged: str = "Unknown"
    diligence_issues: str = "Unknown"
    primary_risks: str = "Unknown"
    price_per_unit_analysis: str = "Unknown"

class UnitTypeSummary(BaseModel):
    unit_type: str
    count: int
    avg_rent: float
    market_rent: float

class Conclusion(BaseModel):
    summary: str # High level summary
    key_decisions: List[DecisionImpact]
    investment_checklist: Optional[InvestmentChecklist] = None

# --- 2.5 Multi-Document Support Models ---

class DocumentMetadata(BaseModel):
    """Metadata for an uploaded document"""
    document_id: str
    filename: str
    document_type: DocumentType
    upload_timestamp: str
    file_size: int
    page_count: Optional[int] = None
    extraction_status: str = "pending"  # pending, processing, completed, failed
    
class NormalizedDataItem(BaseModel):
    """
    Generic normalized data item for the verification UI.
    Represents a single row in the split-screen verification table.
    """
    id: str  # Unique identifier for this item
    raw_text: str  # What was extracted from the PDF
    normalized_value: str  # What it was mapped to
    field_type: str  # e.g., "expense_category", "unit_type", "lease_date"
    confidence: float  # 0.0 to 1.0
    user_verified: bool = False
    user_correction: Optional[str] = None
    source_document: str  # Which document this came from
    metadata: Optional[Dict[str, Any]] = {}
    
class DocumentNormalizationResult(BaseModel):
    """
    Result of normalizing a single document.
    Contains all the normalized items that need user verification.
    """
    document_id: str
    document_type: DocumentType
    normalized_items: List[NormalizedDataItem]
    total_items: int
    verified_items: int = 0
    confidence_average: float
    
class DealPackage(BaseModel):
    """
    A complete deal package containing all 8 document types.
    This is the top-level container for a property underwriting.
    """
    package_id: str
    property_name: str
    created_at: str
    updated_at: str
    documents: Dict[DocumentType, List[DocumentMetadata]] = {}  # Multiple docs per type
    normalization_status: str = "pending"  # pending, in_progress, completed
    verification_progress: float = 0.0  # Percentage of items verified by user
    normalized_data: List[NormalizedDataItem] = [] # Persisted extracted data
    manual_overrides: Dict[str, Any] = {} # User provided manual overrides

# --- 3. Main Analysis Model ---
class UnderwritingAnalysis(BaseModel):
    document_id: str
    pass_fail_status: str
    gating_reasons: List[str] = []

    property_meta: PropertyMeta
    rent_roll: List[RentRollItem]
    rent_roll_summary: RentRollSummary
    unit_mix_summary: List[UnitTypeSummary] = []
    historical_expenses: List[StandardizedExpense]

    deal_parameters: Optional[DealParameters] = None
    
    audit_trail: List[Dict[str, Any]] = []
    
    pro_forma_expenses_detailed: List[ProFormaExpenseItem] = []

    # Pro Forma (Day 1)
    # Explainability Metadata
    explainability: Dict[str, ExplainabilityMetadata] = {}
    gross_potential_rent: Optional[float] = 0.0
    loss_to_lease: Optional[float] = 0.0
    vacancy_loss: Optional[float] = 0.0
    effective_gross_income: Optional[float] = 0.0
    pro_forma_expenses: Optional[float] = 0.0
    pro_forma_noi: Optional[float] = 0.0
    
    # Valuation Metrics
    yield_on_cost: Optional[float] = 0.0
    cap_rate: Optional[float] = 0.0 # Entry Cap Rate
    exit_cap_rate: Optional[float] = 0.0
    
    # Debt & Cash Flow
    total_project_cost: Optional[float] = 0.0
    loan_amount: Optional[float] = 0.0
    equity_invested: Optional[float] = 0.0
    annual_debt_service: Optional[float] = 0.0
    cash_flow: Optional[float] = 0.0
    cash_on_cash_return: Optional[float] = 0.0
    dscr: Optional[float] = 0.0
    debt_yield: Optional[float] = 0.0

    # Return Metrics (5-Year Hold)
    exit_valuation: Optional[float] = 0.0
    net_sale_proceeds: Optional[float] = 0.0
    moic: Optional[float] = 0.0
    irr: Optional[float] = 0.0
    
    # Historical
    historical_noi: Optional[float] = 0.0
    historical_total_expenses: float = 0.0
    historical_cap_rate: Optional[float] = 0.0

    # Sensitivity Analysis
    sensitivity_analysis: Optional[Dict[str, Any]] = None

    # AI Conclusion & Impact
    # AI Narrative
    analyst_commentary: Optional[str] = None
    conclusion: Optional[Conclusion] = None