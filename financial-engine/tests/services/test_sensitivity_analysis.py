import pytest
from unittest.mock import MagicMock
from app.services.financial_service import FinancialService
from app.models.schemas import UnderwritingAnalysis, DealParameters, PropertyMeta, RentRollSummary
from app.services.audit_log_service import AuditLogService

@pytest.fixture
def mock_audit_log_service():
    return MagicMock(spec=AuditLogService)

@pytest.fixture
def financial_service(mock_audit_log_service):
    return FinancialService(audit_log_service=mock_audit_log_service)

@pytest.fixture
def basic_analysis():
    """
    Creates a valid UnderwritingAnalysis object with pre-populated fields 
    necessary for testing _calculate_returns and sensitivity analysis.
    """
    params = DealParameters(
        growth_rate=0.03,
        exit_cap_rate=0.06,
        ltv=0.65,
        sofr_rate=0.04,
        bridge_spread=0.02,
        hold_period=5,
        sales_cost_rate=0.02,
        closing_costs=100_000,
        renovation_budget=50_000
    )
    
    meta = PropertyMeta(
        purchase_price=5_000_000,
        total_units=20,
        year_built=1990,
        address="123 Test St",
        is_renovated=False
    )
    
    # Initialize basic analysis object
    analysis = UnderwritingAnalysis(
        document_id="test_doc_123",
        pass_fail_status="PASS",
        property_meta=meta,
        deal_parameters=params,
        rent_roll=[],
        rent_roll_summary=RentRollSummary(
            total_units=20, occupied_units=18, occupancy_rate=0.9, 
            total_monthly_rent=0, total_annual_rent=0
        ),
        historical_expenses=[]
    )
    
    # Pre-populate fields that are typically calculated in steps 1-4 of the pro forma
    # These are the inputs required for Step 5: Returns & Sensitivity
    
    # Scenario:
    # Purchase: 5M
    # Loan: 3.25M (65% LTV)
    # Total Cost: 5M + 100k + 50k = 5.15M
    # Equity: 5.15M - 3.25M = 1.9M
    # NOI: 300k (6% Cap on 5M)
    # Debt: 3.25M * 6% (4% SOFR + 2% Spread) = 195k
    
    analysis.total_project_cost = 5_150_000.0
    analysis.loan_amount = 3_250_000.0
    analysis.equity_invested = 1_900_000.0
    analysis.pro_forma_noi = 300_000.0
    analysis.annual_debt_service = 195_000.0
    
    return analysis

def test_calculate_returns_base_case(financial_service, basic_analysis):
    """
    Verifies that base IRR, MOIC, and exit valuation are calculated correctly.
    """
    # Execute
    financial_service._calculate_returns(basic_analysis)
    
    # Verify Exit Metrics
    assert basic_analysis.exit_valuation is not None
    assert basic_analysis.exit_valuation > 0
    
    # Verify Returns
    assert basic_analysis.irr is not None
    assert basic_analysis.moic is not None
    
    # Sanity checks
    # MOIC should be positive (likely > 1.0 given the positive leverage in this scenario)
    assert basic_analysis.moic > 0
    # IRR should be a float
    assert isinstance(basic_analysis.irr, float)
    
    # Verify Audit Logs were called
    assert financial_service.audit_log_service.add_log.called

def test_sensitivity_matrix_structure(financial_service, basic_analysis):
    """
    Verifies the dimensions and structure of the sensitivity matrix.
    """
    # Execute
    financial_service._calculate_returns(basic_analysis)
    
    matrix = basic_analysis.sensitivity_analysis
    assert matrix is not None, "Sensitivity Analysis matrix should be generated"
    
    assert "rows" in matrix # Exit Caps
    assert "columns" in matrix # Growth Rates
    assert "values" in matrix # IRR grid
    
    # Check dimensions based on hardcoded steps in service
    # row_steps = [-0.005, 0.0, 0.005] -> 3 rows
    # col_steps = [-0.01, 0.0, 0.01] -> 3 cols
    assert len(matrix["rows"]) == 3
    assert len(matrix["columns"]) == 3
    assert len(matrix["values"]) == 3
    
    for row in matrix["values"]:
        assert len(row) == 3

def test_sensitivity_matrix_integrity(financial_service, basic_analysis):
    """
    Verifies that the center value of the matrix matches the base case IRR.
    """
    financial_service._calculate_returns(basic_analysis)
    
    base_irr = basic_analysis.irr
    matrix = basic_analysis.sensitivity_analysis
    
    # Center is index [1][1] (Base Cap, Base Growth)
    center_irr = matrix["values"][1][1]
    
    # Should be identical or very close floating point wise
    assert abs(center_irr - base_irr) < 0.0001, "Center of sensitivity matrix should match base IRR"

def test_sensitivity_matrix_logic(financial_service, basic_analysis):
    """
    Verifies the financial logic of the sensitivity matrix.
    - Higher Exit Cap -> Lower Price -> Lower IRR (Rows)
    - Higher Growth -> Higher NOI -> Higher IRR (Columns)
    """
    financial_service._calculate_returns(basic_analysis)
    matrix = basic_analysis.sensitivity_analysis
    values = matrix["values"]
    
    # 1. Test Rows (Exit Cap Rate increases down the rows)
    # Row 0 (Low Cap, High Price) > Row 1 (Base) > Row 2 (High Cap, Low Price)
    # Checking middle column (Base Growth)
    assert values[0][1] > values[1][1], "Lower Exit Cap should yield higher IRR"
    assert values[1][1] > values[2][1], "Higher Exit Cap should yield lower IRR"

    # 2. Test Columns (Growth Rate increases across columns)
    # Col 0 (Low Growth) < Col 1 (Base) < Col 2 (High Growth)
    # Checking middle row (Base Cap)
    assert values[1][0] < values[1][1], "Lower Growth should yield lower IRR"
    assert values[1][1] < values[1][2], "Higher Growth should yield higher IRR"

def test_edge_case_zero_growth(financial_service, basic_analysis):
    """
    Test IRR calculation with 0% growth.
    """
    basic_analysis.deal_parameters.growth_rate = 0.0
    financial_service._calculate_returns(basic_analysis)
    
    assert basic_analysis.irr is not None
    irr_zero_growth = basic_analysis.irr
    
    # Compare with high growth
    # Create new analysis to avoid state pollution, or reset/update
    basic_analysis.deal_parameters.growth_rate = 0.05
    financial_service._calculate_returns(basic_analysis)
    irr_high_growth = basic_analysis.irr
    
    assert irr_high_growth > irr_zero_growth

def test_edge_case_negative_noi(financial_service, basic_analysis):
    """
    Test robust handling of negative NOI (distressed asset).
    """
    basic_analysis.pro_forma_noi = -100_000
    
    financial_service._calculate_returns(basic_analysis)
    
    # Should not crash
    assert basic_analysis.irr is not None
    # IRR handles negative flows, but if all are negative (or exit is negative/zero),
    # numpy_financial might return error or very low number.
    # Service wrapper should catch exceptions and default to 0.0 if calculation fails/is complex.
    # Or return a valid negative IRR.
    assert isinstance(basic_analysis.irr, float)

def test_calculate_irr_simulation_isolated(financial_service, basic_analysis):
    """
    Test the simulation helper method directly.
    """
    base_growth = 0.03
    base_exit = 0.06
    
    irr = financial_service._calculate_irr_simulation(basic_analysis, base_growth, base_exit)
    assert isinstance(irr, float)
    
    # Test Sensitivity Logic via direct helper calls
    
    # Higher growth -> Higher IRR
    irr_high = financial_service._calculate_irr_simulation(basic_analysis, 0.05, base_exit)
    assert irr_high > irr
    
    # Higher exit cap -> Lower Price -> Lower IRR
    irr_low_val = financial_service._calculate_irr_simulation(basic_analysis, base_growth, 0.08)
    assert irr_low_val < irr