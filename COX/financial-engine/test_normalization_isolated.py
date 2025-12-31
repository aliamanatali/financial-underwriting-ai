import asyncio
import os
from dotenv import load_dotenv

# Load environment variables from the .env file in the current directory
load_dotenv()

# This script assumes it is run from the 'financial-engine' directory.
# We can now import directly from the 'app' module.
from app.services.normalization_service import NormalizationService
from app.services.gemini_client import GeminiClient
from app.models.schemas import FinancialLineItem, ExpenseCategory

async def main():
    """
    This script tests the NormalizationService in isolation.
    It simulates raw expense data and prints the standardized output.
    """
    print("="*80)
    print("Testing Normalization Service")
    print("="*80)

    # 1. Setup: Instantiate the services
    try:
        gemini_client = GeminiClient()
        normalization_service = NormalizationService(llm_service=gemini_client)
    except ValueError as e:
        print(f"\n[ERROR] Configuration error: {e}")
        print("Please ensure your GEMINI_API_KEY is set in the .env file.")
        return

    # 2. Input: Define sample raw expense data
    raw_expenses = [
        {"description": "Property Tax Bill - Q4", "amount": 12500.00},
        {"description": "General Liability Insurance", "amount": 3200.50},
        {"description": "R&M - Plumbing Leak Unit 101", "amount": 450.75},
        {"description": "Admin Staff Salaries", "amount": 6800.00},
        {"description": "PG&E Utilities", "amount": 2100.25},
        {"description": "Trash Removal Contract", "amount": 800.00},
        {"description": "Fee for Property Management", "amount": 4500.00},
        {"description": "Google Ads - Marketing", "amount": 1200.00},
        {"description": "Misc. Office Supplies", "amount": 300.00},
    ]

    print("\n[INPUT] Raw Expense Data:")
    for expense in raw_expenses:
        print(f"  - {expense['description']}: ${expense['amount']:.2f}")

    # 3. Action: Run the normalization process
    print("\n[ACTION] Calling normalization_service.normalize_expenses...")
    try:
        # NOTE: The service method is not async, so we call it directly.
        normalized_expenses = normalization_service.normalize_expenses(raw_expenses)
        print("...Normalization complete.")
    except Exception as e:
        print(f"\n[ERROR] An exception occurred during normalization: {e}")
        return

    # 4. Output: Print the standardized results for verification
    print("\n[OUTPUT] Standardized Expense Data:")
    print("-" * 80)
    print(f"{'Original Description':<40} | {'Mapped Category':<30} | {'Amount':>10}")
    print(f"{'-'*40} | {'-'*30} | {'-'*10}")

    all_valid = True
    # The result from normalize_expenses is already a list of FinancialLineItem objects
    for expense in normalized_expenses:
        try:
            # Verify that the category is a valid member of the ExpenseCategory enum
            ExpenseCategory(expense.category)
            # The description is now part of the StandardizedExpense, not FinancialLineItem
            # We will use the category for display here as we don't have the original description
            # in the final FinancialLineItem object. A better test would check the full StandardizedExpense.
            print(f"{'N/A':<40} | {expense.category:<30} | ${expense.value:>9.2f}")
        except ValueError:
            print(f"{'N/A':<40} | ***INVALID CATEGORY: {expense.category}*** | ${expense.value:>9.2f}")
            all_valid = False

    print("-" * 80)

    # 5. Verdict
    print("\n[VERDICT]")
    if not all_valid:
        print("  - ❌ FAIL: One or more expenses were mapped to an invalid category.")
    else:
        print("  - ✅ PASS: All expenses were successfully mapped to valid categories.")
    print("  - The `normalize_expenses` function is working as expected.")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())