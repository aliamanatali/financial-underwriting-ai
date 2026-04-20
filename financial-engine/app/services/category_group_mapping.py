"""
Authoritative mapping from ExpenseCategory to CategoryGroup.

Used by the extraction-to-normalization adapter to derive category_group
from NormalizationService's mapped_category output. This replaces the
implicit mappings scattered across _fallback_categorization and the
normalize_expenses_batch LLM prompt.
"""

from app.models.schemas import ExpenseCategory, CategoryGroup

CATEGORY_TO_GROUP: dict[ExpenseCategory, CategoryGroup] = {
    # Revenue
    ExpenseCategory.GROSS_POTENTIAL_RENT: CategoryGroup.REVENUE,
    ExpenseCategory.OTHER_INCOME: CategoryGroup.REVENUE,
    ExpenseCategory.REIMBURSEMENTS: CategoryGroup.REVENUE,

    # Balance sheet
    ExpenseCategory.ACCOUNTS_RECEIVABLE: CategoryGroup.OTHER,

    # Tax & Insurance
    ExpenseCategory.REAL_ESTATE_TAXES: CategoryGroup.TAX_INSURANCE,
    ExpenseCategory.INSURANCE: CategoryGroup.TAX_INSURANCE,

    # Capital
    ExpenseCategory.CAPITAL_RESERVES: CategoryGroup.CAPITAL_EXPENDITURE,

    # Debt
    ExpenseCategory.CURRENT_LOAN_BALANCE: CategoryGroup.DEBT,

    # Property Info
    ExpenseCategory.PURCHASE_PRICE: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.DEPOSIT: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.PRICE_PER_UNIT: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.TOTAL_UNITS: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.YEAR_BUILT: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.PROPERTY_INFO: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.PHYSICAL_CONDITION: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.PROPERTY_NAME: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.PROPERTY_ADDRESS: CategoryGroup.PROPERTY_INFO,

    # Other
    ExpenseCategory.UNCATEGORIZED: CategoryGroup.OTHER,

    # Operating Expense (explicit rather than relying on default)
    ExpenseCategory.REPAIRS_MAINTENANCE: CategoryGroup.OPERATING_EXPENSE,
    ExpenseCategory.GENERAL_ADMINISTRATIVE: CategoryGroup.OPERATING_EXPENSE,
    ExpenseCategory.PAYROLL: CategoryGroup.OPERATING_EXPENSE,
    ExpenseCategory.UTILITIES: CategoryGroup.OPERATING_EXPENSE,
    ExpenseCategory.MANAGEMENT_FEES: CategoryGroup.OPERATING_EXPENSE,
    ExpenseCategory.CONTRACT_SERVICES: CategoryGroup.OPERATING_EXPENSE,
    ExpenseCategory.OTHER_OPERATING_EXPENSES: CategoryGroup.OPERATING_EXPENSE,
    ExpenseCategory.ADVERTISING_MARKETING: CategoryGroup.OPERATING_EXPENSE,
    ExpenseCategory.LEASING_FEES: CategoryGroup.OPERATING_EXPENSE,
}


def get_category_group(category: ExpenseCategory) -> CategoryGroup:
    """Look up the CategoryGroup for an ExpenseCategory.

    Raises KeyError with a clear message if the enum value is missing
    from the mapping — this catches the case where someone adds a new
    ExpenseCategory without updating CATEGORY_TO_GROUP.
    """
    try:
        return CATEGORY_TO_GROUP[category]
    except KeyError:
        raise KeyError(
            f"ExpenseCategory.{category.name} ({category.value!r}) has no entry in "
            f"CATEGORY_TO_GROUP. Add it to category_group_mapping.py."
        )
