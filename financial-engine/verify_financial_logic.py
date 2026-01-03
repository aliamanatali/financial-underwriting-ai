from app.models.schemas import UnderwritingAnalysis, DealParameters, PropertyMeta, RentRollItem, StandardizedExpense, ExpenseCategory, AuditLog, RentRollSummary
from app.services.financial_service import FinancialService
from app.services.audit_log_service import AuditLogService
import logging
import math

# Configure basic logging
logging.basicConfig(level=logging.INFO)

def verify_logic():
    print("\n--- Starting Financial Logic Verification ---\n")
    
    # 1. Setup Mock Data
    audit_service = AuditLogService()
    service = FinancialService(audit_service)
    
    # Mock Property: "Keystone Apartments"
    # Purchase Price: $10,000,000
    # Units: 50
    # Market Rent: $2,000/mo -> GPR $1,200,000
    # Current Rent: $1,800/mo -> Current $1,080,000
    
    rent_roll = []
    for i in range(50):
        rent_roll.append(RentRollItem(
            unit_number=f"10{i}",
            unit_type="1BR",
            current_rent=1800.0,
            market_rent=2000.0,
            tenant_name="Test Tenant"
        ))
        
    analysis = UnderwritingAnalysis(
        document_id="test_doc_123",
        pass_fail_status="PENDING",
        property_meta=PropertyMeta(
            address="123 Main St",
            purchase_price=10_000_000.0, # Hardcoded for testing purposes
            total_units=50,
            year_built=1990,
            is_renovated=True
        ),
        rent_roll=rent_roll,
        rent_roll_summary=RentRollSummary(
            total_units=50,
            occupied_units=50,
            occupancy_rate=1.0,
            total_monthly_rent=90000.0,
            total_annual_rent=1080000.0
        ),
        historical_expenses=[
            StandardizedExpense(
                original_text="Insurance",
                mapped_category=ExpenseCategory.INSURANCE,
                amount=15000.0,
                confidence=0.9,
                audit_log=AuditLog(field_name="Insurance", extracted_value="15000", source_doc="T12", confidence_score=0.9, reasoning="Exact Match")
            ),
            StandardizedExpense(
                original_text="Repairs",
                mapped_category=ExpenseCategory.REPAIRS_MAINTENANCE,
                amount=35000.0,
                confidence=0.8,
                audit_log=AuditLog(field_name="Repairs", extracted_value="35000", source_doc="T12", confidence_score=0.8, reasoning="Exact Match")
            ),
             StandardizedExpense(
                original_text="Utilities",
                mapped_category=ExpenseCategory.UTILITIES,
                amount=45000.0,
                confidence=0.9,
                audit_log=AuditLog(field_name="Utilities", extracted_value="45000", source_doc="T12", confidence_score=0.9, reasoning="Exact Match")
            ),
            # Add some others to simulate a full T12
            StandardizedExpense(
                original_text="General Admin",
                mapped_category=ExpenseCategory.GENERAL_ADMINISTRATIVE,
                amount=10000.0,
                confidence=0.7,
                audit_log=AuditLog(field_name="G&A", extracted_value="10000", source_doc="T12", confidence_score=0.7, reasoning="Exact Match")
            )
        ],
        deal_parameters=DealParameters(
            vacancy_rate=0.03,
            management_fee_rate=0.04,
            expense_ratio_target=0.38,
            tax_rate=0.012,
            ltv=0.65,
            sofr_rate=0.053,
            bridge_spread=0.02,
            exit_cap_rate=0.06,
            closing_costs=100_000.0,
            renovation_budget=0.0
        )
    )
    
    print("Running Calculation...")
    result = service.calculate_pro_forma(analysis)
    
    # --- Verify Step 1: Revenue ---
    print("\n[Step 1: Revenue]")
    expected_gpr = 50 * 2000 * 12 # 1,200,000
    print(f"GPR: Expected ${expected_gpr:,.0f} | Actual ${analysis.gross_potential_rent:,.0f}")
    assert analysis.gross_potential_rent == expected_gpr, "GPR Mismatch"
    
    expected_loss_to_lease = expected_gpr - (50 * 1800 * 12) # 1,200,000 - 1,080,000 = 120,000
    print(f"Loss to Lease: Expected ${expected_loss_to_lease:,.0f} | Actual ${analysis.loss_to_lease:,.0f}")
    assert analysis.loss_to_lease == expected_loss_to_lease, "Loss to Lease Mismatch"
    
    expected_vacancy = expected_gpr * 0.03 # 36,000
    print(f"Vacancy Loss: Expected ${expected_vacancy:,.0f} | Actual ${analysis.vacancy_loss:,.0f}")
    assert analysis.vacancy_loss == expected_vacancy, "Vacancy Loss Mismatch"
    
    expected_egi = expected_gpr - expected_loss_to_lease - expected_vacancy # 1,200,000 - 120,000 - 36,000 = 1,044,000
    print(f"EGI: Expected ${expected_egi:,.0f} | Actual ${analysis.effective_gross_income:,.0f}")
    assert analysis.effective_gross_income == expected_egi, "EGI Mismatch"
    
    # --- Verify Step 2: Expenses ---
    print("\n[Step 2: Expenses]")
    # Tax = 10M * 1.2% = 120,000
    # Mgmt = 1,044,000 * 4% = 41,760
    # Other Expenses (from T12 mock):
    # Insurance: 15,000
    # Repairs: 35,000
    # Utilities: 45,000
    # G&A: 10,000
    # Total Other: 105,000
    
    expected_tax = 10_000_000 * 0.012
    expected_mgmt = expected_egi * 0.04
    expected_other = 15000 + 35000 + 45000 + 10000
    
    expected_opex = expected_tax + expected_mgmt + expected_other # 120,000 + 41,760 + 105,000 = 266,760
    
    print(f"Total OpEx: Expected ${expected_opex:,.0f} | Actual ${analysis.pro_forma_expenses:,.0f}")
    assert math.isclose(analysis.pro_forma_expenses, expected_opex, rel_tol=1e-5), "OpEx Mismatch"
    
    # Expense Ratio Check
    expected_ratio = expected_opex / expected_egi
    print(f"Expense Ratio: {expected_ratio:.1%}")
    
    # --- Verify Step 3: NOI ---
    print("\n[Step 3: NOI]")
    expected_noi = expected_egi - expected_opex # 1,044,000 - 396,720 = 647,280
    print(f"NOI: Expected ${expected_noi:,.0f} | Actual ${analysis.pro_forma_noi:,.0f}")
    assert math.isclose(analysis.pro_forma_noi, expected_noi, rel_tol=1e-5), "NOI Mismatch"
    
    # --- Verify Step 4: Debt ---
    print("\n[Step 4: Debt]")
    expected_loan = 10_000_000 * 0.65 # 6,500,000
    print(f"Loan Amount: Expected ${expected_loan:,.0f} | Actual ${analysis.loan_amount:,.0f}")
    assert analysis.loan_amount == expected_loan, "Loan Amount Mismatch"
    
    interest_rate = 0.053 + 0.02 # 7.3%
    expected_debt_service = expected_loan * interest_rate # 474,500
    print(f"Debt Service: Expected ${expected_debt_service:,.0f} | Actual ${analysis.annual_debt_service:,.0f}")
    assert math.isclose(analysis.annual_debt_service, expected_debt_service, rel_tol=1e-5), "Debt Service Mismatch"
    
    expected_cash_flow = expected_noi - expected_debt_service # 647,280 - 474,500 = 172,780
    print(f"Cash Flow: Expected ${expected_cash_flow:,.0f} | Actual ${analysis.cash_flow:,.0f}")
    assert math.isclose(analysis.cash_flow, expected_cash_flow, rel_tol=1e-5), "Cash Flow Mismatch"

    # Equity = 10M + 100k - 6.5M = 3.6M
    expected_equity = 10_000_000 + 100_000 - 6_500_000
    expected_coc = expected_cash_flow / expected_equity # 172,780 / 3,600,000 = 4.799%
    print(f"CoC: Expected {expected_coc:.2%} | Actual {analysis.cash_on_cash_return:.2%}")
    assert math.isclose(analysis.cash_on_cash_return, expected_coc, rel_tol=1e-5), "CoC Mismatch"

    # --- Verify Step 5: Returns (IRR/MOIC) ---
    print("\n[Step 5: Returns]")
    # We won't manually calc IRR here as it's complex, but we'll check MOIC directionally.
    # Total Inflows roughly 5 years of cash flow + Net Sale Proceeds.
    # Just checking it calculated something non-zero.
    print(f"IRR: {analysis.irr:.2%}")
    print(f"MOIC: {analysis.moic:.2f}x")
    
    assert analysis.irr > 0, "IRR should be positive"
    assert analysis.moic > 1.0, "MOIC should be > 1.0"
    
    print("\n✅ VERIFICATION SUCCESSFUL: All Deterministic Formulas Match!")

if __name__ == "__main__":
    verify_logic()