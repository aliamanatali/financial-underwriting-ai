import numpy_financial as npf # type: ignore
import math
from app.models.schemas import UnderwritingAnalysis, DealParameters, ProFormaExpenseItem, ExpenseCategory, UnitTypeSummary
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

from app.services.audit_log_service import AuditLogService

class FinancialService:
    def __init__(self, audit_log_service: AuditLogService):
        self.audit_log_service = audit_log_service

    def _sanitize_value(self, value: Optional[float]) -> float:
        """
        Safely sanitize float values to ensure they are JSON compliant.
        Replaces NaN and Infinity with 0.0.
        """
        if value is None:
            return 0.0
        try:
            if isinstance(value, (float, int)):
                if math.isnan(value) or math.isinf(value):
                    return 0.0
        except Exception:
            return 0.0
        return value

    def _deduplicate_expenses(self, expenses: List[Any]) -> List[Any]:
        """
        Deduplicates expenses with Document Priority Enforcement (OM > Financials).
        
        Logic:
        1. Document Priority: If expenses exist from an OM (Offering Memorandum),
           and they appear sufficient, we IGNORE other sources (T12, Excel, etc.)
           per the "OM Primacy" rule.
        2. Year-based Filtering: If multiple years found, pick the most relevant one.
        3. Deduplication: Group by category and clean up duplicates/totals.
        """
        from collections import defaultdict, Counter
        
        if not expenses:
            return []

        # --- Step 0: Document Priority Filtering (OM > Others) ---
        # "if we have OM, we should be able to get all the data... we dont need to pick supporting documents"
        
        om_expenses = []
        pnl_expenses = []
        raw_bill_expenses = []
        
        manual_entries = []
        verified_any_source = []
        for exp in expenses:
            src = (exp.source_document or "").upper()
            is_verified = hasattr(exp, 'user_verified') and exp.user_verified
            
            if "MANUAL" in src:
                manual_entries.append(exp)
            elif is_verified:
                verified_any_source.append(exp)
            
            if "OM" in src or "OFFERING" in src or "MEMORANDUM" in src:
                om_expenses.append(exp)
            elif any(kw in src for kw in ["P&L", "PL ", "T12", "STATEMENT", "OPERATING"]):
                pnl_expenses.append(exp)
            else:
                raw_bill_expenses.append(exp)
        
        # Priority 1: OM Primacy
        # OM is authoritative ONLY if it covers the major expense categories.
        # A sparse OM (e.g., 6 line items) should not discard a complete T12.
        REQUIRED_OM_CATEGORIES = {
            ExpenseCategory.REAL_ESTATE_TAXES,
            ExpenseCategory.INSURANCE,
            ExpenseCategory.UTILITIES,
            ExpenseCategory.REPAIRS_MAINTENANCE,
            ExpenseCategory.MANAGEMENT_FEES,
        }
        om_categories_present = {exp.mapped_category for exp in om_expenses if hasattr(exp, 'mapped_category')}
        om_has_required_coverage = REQUIRED_OM_CATEGORIES.issubset(om_categories_present)
        om_is_substantial = len(om_expenses) >= 10 and om_has_required_coverage

        if om_is_substantial:
            logger.info(f"OM Primacy: Found {len(om_expenses)} items covering {len(om_categories_present & REQUIRED_OM_CATEGORIES)}/5 required categories. Ignoring other sources (except verified items).")
            # Keep OM expenses + manual entries + any item verified by user from other sources
            # Use a set of IDs to avoid duplicates if a verified item is also in om_expenses
            seen_ids = {e.id for e in om_expenses if hasattr(e, 'id') and e.id}
            others_to_keep = [e for e in (manual_entries + verified_any_source) if not (hasattr(e, 'id') and e.id in seen_ids)]
            expenses = om_expenses + others_to_keep
        
        # Priority 2: T12/P&L Primacy over Raw Bills
        # If we have a P&L, we should ignore ALL raw bills for expenses.
        elif len(pnl_expenses) > 0:
            logger.info(f"P&L Detected. Implementing Strict Source Hierarchy (P&L > Raw Bills).")
            
            # Identify if any expenses are clearly from an Excel/P&L file
            # Instruction: Completely discard all expense extractions from PDF utility bills or invoices.
            logger.info(f"Hierarchy: Discarding {len(raw_bill_expenses)} items from raw bills/PDFs because a P&L exists.")
            
            # We only keep property info or non-expense categories from raw bills?
            # Re-reading instruction: "discard all expense extractions".
            # So if it's categorized as an expense, we discard it.
            
            filtered_raw_bills = []
            for exp in raw_bill_expenses:
                # We only keep items from raw bills if they are NOT expenses (e.g. Property Meta)
                # Note: In this loop, items are usually already categorized.
                # However, many things are categorized as 'Other Operating Expenses' by default.
                
                # Check category group if available, or use keywords
                is_expense = True
                if hasattr(exp, 'category_group') and exp.category_group:
                    from app.models.schemas import CategoryGroup
                    if exp.category_group not in [CategoryGroup.OPERATING_EXPENSE, CategoryGroup.TAX_INSURANCE, CategoryGroup.OTHER]:
                        is_expense = False
                
                if not is_expense:
                    filtered_raw_bills.append(exp)
                else:
                    logger.debug(f"Hierarchy: Discarding raw expense item: {exp.original_text}")
            
            expenses = pnl_expenses + filtered_raw_bills + manual_entries
        
        # --- Step 1: Year-Based Filtering ---
        # Collect years from all expenses
        years = []
        for exp in expenses:
            # Check for expense_year attribute (StandardizedExpense)
            if hasattr(exp, 'expense_year') and exp.expense_year:
                years.append(exp.expense_year)
        
        if years:
            year_counts = Counter(years)
            unique_years = sorted(year_counts.keys(), reverse=True) # Descending (Recent first)
            
            if len(unique_years) > 1:
                # We have mixed years. We need to pick a winner.
                target_year = unique_years[0] # Default to most recent
                most_frequent_year = year_counts.most_common(1)[0][0]
                
                # Heuristic: Use most recent unless it's very sparse compared to another year
                # e.g. 2024 (2 items) vs 2023 (50 items) -> Use 2023
                if year_counts[target_year] < 5 and year_counts[most_frequent_year] > 15:
                    target_year = most_frequent_year
                    logger.info(f"Multi-year data detected. Prioritizing most frequent year {target_year} over most recent {unique_years[0]} due to data volume.")
                else:
                    logger.info(f"Multi-year data detected. Prioritizing most recent year {target_year}.")
                
                # Filter out expenses that have a year explicitly different from target_year
                filtered_expenses = []
                excluded_count = 0
                
                for exp in expenses:
                    if hasattr(exp, 'expense_year') and exp.expense_year:
                        if exp.expense_year == target_year:
                            filtered_expenses.append(exp)
                        else:
                            excluded_count += 1
                    else:
                        # Keep items with no year (they might be generic or applicable to all)
                        filtered_expenses.append(exp)
                
                if excluded_count > 0:
                    logger.info(f"Excluded {excluded_count} expenses from non-target years to ensure consistency.")
                    expenses = filtered_expenses

        # --- Step 1: Group by Category ---
        by_category = defaultdict(list)
        for exp in expenses:
            by_category[exp.mapped_category].append(exp)
            
        final_expenses = []
        
        for category, items in by_category.items():
            if len(items) <= 1:
                final_expenses.extend(items)
                continue
            
            # Priority 0: Separate User-Verified Items
            verified_items = [i for i in items if hasattr(i, 'user_verified') and i.user_verified]
            unverified_items = [i for i in items if not (hasattr(i, 'user_verified') and i.user_verified)]
            
            # If we have verified items, we still want to keep other non-duplicate items
            # but for certain categories like Tax/Insurance, verified items should indeed be the only ones.
            if verified_items:
                # Handle potential string or enum category comparison
                is_fixed_category = any(
                    (category == c or str(category) == str(c) or str(category) == c.value)
                    for c in [ExpenseCategory.REAL_ESTATE_TAXES, ExpenseCategory.INSURANCE, ExpenseCategory.MANAGEMENT_FEES]
                )
                
                if is_fixed_category:
                    logger.info(f"Deduplicating {category}: Keeping {len(verified_items)} user-verified items and discarding others.")
                    # If multiple verified items exist for these fixed categories, we take the LATEST one (highest index)
                    # as it's likely the most recent user edit.
                    final_expenses.append(verified_items[-1])
                    continue
                else:
                    # For variable categories, we keep verified items
                    # and then process unverified ones, but we should deduplicate against verified items too.
                    final_expenses.extend(verified_items)
                    
                    # Deduplicate unverified items against verified ones (by amount)
                    verified_amounts = {round(i.amount, 2) for i in verified_items}
                    items = [i for i in unverified_items if round(i.amount, 2) not in verified_amounts]
                    
                    if not items:
                        continue
            
            # --- Strategy 0.5: Frequency-Based Deduplication (Duplicate Entries) ---
            # Fix for "Fire alarm monitoring extracted 30 times" and "Duplicate Property Tax entries"
            # Logic:
            # - If an EXACT amount appears > 15 times, it's likely a system extraction error (Page repeats). Keep 1.
            # - If a Large Amount (> $5,000) appears > 1 time for periodic items (Tax, Insurance), keep 1 (or Max).
            
            from collections import Counter
            amount_counts = Counter(i.amount for i in items)
            repeated_amounts = {amt for amt, count in amount_counts.items() if count > 1}
            
            unique_items_map = {} # Key: Amount -> Item
            items_to_keep = []
            
            # Threshold for "suspiciously frequent" small items
            HIGH_FREQUENCY_THRESHOLD = 4
            
            for item in items:
                amt = item.amount
                if amt in repeated_amounts:
                    # If it's a very frequent item (e.g. Fire Alarm $1,140 appearing 30 times)
                    if amount_counts[amt] > HIGH_FREQUENCY_THRESHOLD:
                        if amt not in unique_items_map:
                             unique_items_map[amt] = item
                             items_to_keep.append(item)
                             logger.warning(f"Deduplicating frequent item in {category}: {item.original_text} (${amt}) found {amount_counts[amt]} times. Keeping 1.")
                        continue
                    
                    # If it's a Large Item (> $5,000) duplicated (e.g. Tax Bill appearing twice)
                    if amt > 5000:
                         if amt not in unique_items_map:
                             unique_items_map[amt] = item
                             items_to_keep.append(item)
                             logger.warning(f"Deduplicating large item in {category}: {item.original_text} (${amt}) found {amount_counts[amt]} times. Keeping 1.")
                         continue
                
                # Otherwise keep it
                items_to_keep.append(item)
            
            items = items_to_keep # Update the list for subsequent strategies
            
            if not items:
                continue

            # --- Strategy 1: Look for Explicit Totals ---
            total_item = None
            others = []
            
            for item in items:
                desc = item.original_text.lower() if item.original_text else ""
                if "total" in desc:
                    if total_item is None or item.amount > total_item.amount:
                         if total_item: others.append(total_item) # Demote previous total
                         total_item = item
                    else:
                        others.append(item)
                else:
                    others.append(item)
            
            # If we found a Total line, use it
            if total_item:
                sum_others = sum(e.amount for e in others)
                logger.info(f"Deduplicating {category}: Keeping 'Total' item '${total_item.amount}' ({total_item.original_text})")
                final_expenses.append(total_item)
                continue

            # --- Strategy 2: Duplicate Detection (Multi-Year) ---
            items.sort(key=lambda x: x.amount, reverse=True)
            
            # If category is Taxes or Insurance, take MAX (Largest Annual Bill)
            if category in [ExpenseCategory.REAL_ESTATE_TAXES, ExpenseCategory.INSURANCE, ExpenseCategory.MANAGEMENT_FEES]:
                 largest = items[0]
                 
                 # Sanity Check for Insurance specifically (avoid capturing Property Values/Limits)
                 # Max plausible insurance is ~$2,500/unit/year.
                 # We don't have unit count here easily, but we can check absolute outliers.
                 # $100k for insurance on a single building is suspicious unless it's huge.
                 # CRITICAL: Never ignore user-verified values, even if they seem high.
                 if category == ExpenseCategory.INSURANCE and largest.amount > 100000 and not getattr(largest, 'user_verified', False):
                     # Check if we have a smaller, more reasonable item?
                     reasonable_items = [i for i in items if 1000 < i.amount < 50000]
                     if reasonable_items:
                         largest = max(reasonable_items, key=lambda x: x.amount)
                         logger.warning(f"Ignored suspicious Insurance amount ${items[0].amount}. Using reasonable fallback ${largest.amount}")
                     else:
                         # If only huge items exist, we might cap it later or flag it.
                         logger.warning(f"Suspiciously high Insurance: ${largest.amount}. This might be a coverage limit or property value.")
                         
                 logger.info(f"Deduplicating {category}: Taking selected item '${largest.amount}' out of {len(items)} items")
                 final_expenses.append(largest)
                 continue

            # --- Strategy 3: Aggressive Utility Deduplication ---
            # If Utilities sum is massive (> $100k for small prop) and we have many items,
            # it implies we might be summing monthly bills AND annual summaries extracted from P&L.
            if category == ExpenseCategory.UTILITIES:
                total_sum = sum(e.amount for e in items)
                largest = items[0] # Items are already sorted desc by amount
                
                # If we have many items (>12 implies monthly data exists) AND a large total
                # Check if the largest item is likely an annual summary
                if len(items) > 12:
                     # Calculate sum of all OTHER items
                     rest_sum = total_sum - largest.amount
                     
                     # If the largest item is roughly equal to the sum of the rest (within 20% margin),
                     # it's highly likely a "Total" line that wasn't caught by the "Total" keyword check.
                     # OR if the largest item is just massive (> $20k) and we have > 20 items.
                     
                     is_duplicate_likely = False
                     if rest_sum > 0 and abs(largest.amount - rest_sum) / rest_sum < 0.25:
                         is_duplicate_likely = True
                         
                     # Also check for explicit "Total" or similar in text if not caught before
                     if "total" in (largest.original_text or "").lower():
                         is_duplicate_likely = True

                     if is_duplicate_likely or (len(items) > 20 and total_sum > 200000):
                        logger.warning(f"Utilities sum ${total_sum} is suspicious with {len(items)} items. Taking largest item as Annual Total.")
                        final_expenses.append(largest)
                        continue

            # --- Strategy 4: General Multi-Year Check ---
            # If we have two huge items (e.g. Repairs 2022: $50k, Repairs 2023: $48k)
            # Summing them ($98k) might be wrong if we want "Annualized".
            # Taking average or max is safer for "Stabilized" underwriting.
            # For now, we stick to summing "Operating" expenses like Repairs/Contract Services,
            # as they are variable. But we warn if count is high.

            final_expenses.extend(items)
                
        return final_expenses

    def check_deal_viability(self, analysis: UnderwritingAnalysis) -> Dict[str, Any]:
        """
        Checks hard gating criteria (Unit Count, Loan Amount, etc.)
        """
        reasons = []
        status = "PASS"
        # Ensure parameters exist, else use defaults
        params = analysis.deal_parameters or DealParameters()
        
        # 1. Loan Amount Check (Preliminary, based on Purchase Price if available)
        # Note: True Loan Amount is calculated in Step 4, but we can check rough sizing here.
        purchase_price = analysis.property_meta.purchase_price or 0
        
        # Only check if Purchase Price is known. If 0/Missing, we defer to Step 4 (Implied Valuation).
        # OR if user explicitly provided a loan amount, we can check it regardless of purchase price.
        
        explicit_loan = None
        if params.loan_amount is not None and params.loan_amount > 0:
             explicit_loan = float(params.loan_amount)

        if explicit_loan or purchase_price > 0:
            if explicit_loan:
                estimated_loan = explicit_loan
            else:
                estimated_loan = purchase_price * params.ltv
                
            # Removed loan amount FAIL gating logic
        elif explicit_loan is None and purchase_price == 0:
             # Case where we have NO info to estimate loan
             # Removed loan amount FAIL gating logic
             pass
        
        # FINAL OVERRIDE: Never block analysis completely on data checks.
        # We want to see the report even if it's "bad".
        if status == "FAIL":
            logger.warning(f"Deal viability check failed with reasons: {reasons}.")
            # status = "PASS" # Removed override to ensure criteria checks are enforced
        
        return {"status": status, "reasons": reasons}

    def calculate_historical(self, analysis: UnderwritingAnalysis) -> Dict[str, float]:
        """
        Calculates T12 historical performance based on extracted data.
        Now also supports T3, T6, T9 trailing periods.
        """
        from app.models.schemas import HistoricalSummary

        hgi = sum(item.current_rent * 12 for item in analysis.rent_roll)
        
        # Deduplicate expenses (Fix for "Redundant Tax Entries")
        if analysis.historical_expenses:
            analysis.historical_expenses = self._deduplicate_expenses(analysis.historical_expenses)
        
        total_expenses = 0.0
        total_expenses_t3 = 0.0
        total_expenses_t6 = 0.0
        total_expenses_t9 = 0.0
        
        # --- FIX: HARD FILTERING of the Historical List ---
        # Instead of just skipping them during sum, we must REMOVE them from the list entirely
        # so they don't show up in the frontend or report tables.
        valid_expenses = []
        
        if analysis.historical_expenses:
            # FIX: Pre-calculate Other Income before we filter the list!
            # We want to capture this value for Pro Forma use, even if we filter it from T12 Expense column.
            t12_other_income = 0.0
            for expense in analysis.historical_expenses:
                 if expense.mapped_category in [ExpenseCategory.OTHER_INCOME, ExpenseCategory.REIMBURSEMENTS]:
                     t12_other_income += expense.amount
                     
            analysis.other_income = self._sanitize_value(t12_other_income)
            logger.info(f"Captured Historical Other Income: ${t12_other_income:,.2f}")

            for expense in analysis.historical_expenses:
                # Handle Enum or String category
                cat_val = expense.mapped_category.value if hasattr(expense.mapped_category, 'value') else str(expense.mapped_category)
                cat_val_lower = cat_val.lower()
                
                # 1. CATEGORY CHECK
                # Exclude Capital items, Debt, and Non-Operating
                if expense.mapped_category in [
                    ExpenseCategory.CAPITAL_RESERVES,
                    ExpenseCategory.CURRENT_LOAN_BALANCE,
                    ExpenseCategory.LEASING_FEES, # Exclude Leasing Fees from NOI as per standard (below the line)
                    ExpenseCategory.PROPERTY_INFO,
                    ExpenseCategory.TOTAL_UNITS,
                    ExpenseCategory.YEAR_BUILT,
                    ExpenseCategory.PURCHASE_PRICE,
                    ExpenseCategory.PRICE_PER_UNIT,
                    ExpenseCategory.DEPOSIT, # Earnest money, security deposits — balance sheet items, not OpEx
                    ExpenseCategory.UNCATEGORIZED, # Exclude Uncategorized (often bad extractions or revenue deductions)
                    ExpenseCategory.ACCOUNTS_RECEIVABLE,
                    # FIX: Exclude Revenue Items from Expense Sum
                    ExpenseCategory.OTHER_INCOME,
                    ExpenseCategory.GROSS_POTENTIAL_RENT,
                    ExpenseCategory.REIMBURSEMENTS,
                ]:
                    if expense.mapped_category == ExpenseCategory.UNCATEGORIZED:
                        logger.warning(f"DROPPED UNCATEGORIZED T12 expense: '{expense.original_text}' (${expense.amount:,.2f}) — review normalization if this is a real operating expense")
                    else:
                        logger.info(f"Removing Non-Operating Item: {expense.mapped_category} - {expense.original_text} (${expense.amount:,.2f})")
                    continue
                
                # 2. STRING CHECK (Case-insensitive)
                if any(x in cat_val_lower for x in [
                    "debt", "mortgage", "non-operating", "capital expenditure",
                    "depreciation", "amortization", "leasing commissions",
                    "property characteristic", "uncategorized", "loan", "receivable"
                ]):
                    logger.info(f"Removing Suspicious Text Item: {cat_val} - {expense.original_text} (${expense.amount:,.2f})")
                    continue
                
                # 2b. REVENUE KEYWORD CHECK
                # "Income", "Revenue" in category name (except "Net Operating Income" which isn't a category)
                if "income" in cat_val_lower or "revenue" in cat_val_lower or "reimbursement" in cat_val_lower:
                     logger.info(f"Removing Revenue Item from Expenses: {cat_val} - {expense.original_text} (${expense.amount:,.2f})")
                     continue
 
                # 3. OUTLIER CHECK
                if expense.amount > 200000 and expense.mapped_category not in [ExpenseCategory.REAL_ESTATE_TAXES, ExpenseCategory.INSURANCE]:
                     logger.warning(f"Removing Suspiciously Large Item: {expense.original_text} (${expense.amount:,.2f})")
                     continue
 
                # If passed all checks, include in sum AND final list
                total_expenses += expense.amount
                
                # Sum Trailing Periods (Annualized)
                # Note: We assume LLM extracts the PERIOD sum, so we annualize here.
                # If LLM already annualized, this will be wrong, but usually P&Ls show period totals.
                # Heuristic: If T3 > T12, it's already annualized.
                if expense.amount_t3 is not None:
                    total_expenses_t3 += expense.amount_t3 * 4
                if expense.amount_t6 is not None:
                    total_expenses_t6 += expense.amount_t6 * 2
                if expense.amount_t9 is not None:
                    total_expenses_t9 += expense.amount_t9 * (12/9)
                
                valid_expenses.append(expense)
            
            # UPDATE THE OBJECT WITH FILTERED LIST
            analysis.historical_expenses = valid_expenses
 
            if total_expenses == 0:
                logger.warning("Historical expenses list is present but total amount is 0. Check normalization.")
        else:
            logger.warning("No historical expenses found in analysis object.")
 
        purchase_price = analysis.property_meta.purchase_price or 0
        
        # Calculate T12 Snapshot
        historical_noi = hgi - total_expenses
        historical_cap_rate = historical_noi / purchase_price if purchase_price > 0 else 0
        
        # Build Periods
        periods = []
        
        # T12 (Always)
        periods.append(HistoricalSummary(
            period="T12",
            total_expenses=self._sanitize_value(total_expenses),
            noi=self._sanitize_value(historical_noi),
            cap_rate=self._sanitize_value(historical_cap_rate)
        ))
        
        # Synthetic Period Generation (as per user request: "generate others from our selves by dividing the values")
        # If T3, T6, or T9 data wasn't explicitly extracted, generate them by dividing T12.
        
        # T3
        val_t3 = total_expenses_t3 if total_expenses_t3 > 0 else (total_expenses * (3/12))
        hgi_t3 = hgi * (3/12)
        noi_t3 = hgi_t3 - val_t3
        periods.append(HistoricalSummary(
            period="T3",
            total_expenses=self._sanitize_value(val_t3),
            noi=self._sanitize_value(noi_t3),
            cap_rate=self._sanitize_value(noi_t3 / (purchase_price * (3/12)) if purchase_price > 0 else 0)
        ))
            
        # T6
        val_t6 = total_expenses_t6 if total_expenses_t6 > 0 else (total_expenses * (6/12))
        hgi_t6 = hgi * (6/12)
        noi_t6 = hgi_t6 - val_t6
        periods.append(HistoricalSummary(
            period="T6",
            total_expenses=self._sanitize_value(val_t6),
            noi=self._sanitize_value(noi_t6),
            cap_rate=self._sanitize_value(noi_t6 / (purchase_price * (6/12)) if purchase_price > 0 else 0)
        ))
            
        # T9
        val_t9 = total_expenses_t9 if total_expenses_t9 > 0 else (total_expenses * (9/12))
        hgi_t9 = hgi * (9/12)
        noi_t9 = hgi_t9 - val_t9
        periods.append(HistoricalSummary(
            period="T9",
            total_expenses=self._sanitize_value(val_t9),
            noi=self._sanitize_value(noi_t9),
            cap_rate=self._sanitize_value(noi_t9 / (purchase_price * (9/12)) if purchase_price > 0 else 0)
        ))
            
        analysis.historical_periods = periods
        
        # Save defaults to Analysis Object (Backward Compatibility uses T12)
        analysis.historical_total_expenses = self._sanitize_value(total_expenses)
        analysis.historical_noi = self._sanitize_value(historical_noi)
        analysis.historical_cap_rate = self._sanitize_value(historical_cap_rate)
        
        return {
            "gross_income": hgi,
            "total_expenses": total_expenses,
            "historical_noi": historical_noi,
            "historical_cap_rate": analysis.historical_cap_rate,
        }

    def calculate_pro_forma(self, analysis: UnderwritingAnalysis) -> Dict[str, Any]:
        """
        Executes the 5-Step Deterministic Financial Model.
        """
        if not analysis.deal_parameters:
            analysis.deal_parameters = DealParameters()
        
        # Sanitize parameters to prevent NaN propagation
        self._sanitize_parameters(analysis.deal_parameters)
            
        self.audit_log_service.add_log(analysis, "Pro Forma Start", "Initiating 5-Step Calculation", "System", "Orchestration")

        # Step 1: Revenue Logic
        self._calculate_revenue(analysis)
        
        # Step 2: Expense Logic
        self._calculate_expenses(analysis)
        
        # Step 3: Profitability Metrics (NOI)
        self._calculate_profitability(analysis)
        
        # Step 4: Debt & Cash Flow
        self._calculate_debt_and_cash_flow(analysis)
        
        # Step 5: Time-Based Returns (IRR & MOIC)
        self._calculate_returns(analysis)
        
        return {
            "status": "Success",
            "pro_forma_noi": analysis.pro_forma_noi,
            "pro_forma_expenses": analysis.pro_forma_expenses,
            "cap_rate": analysis.cap_rate,
            "exit_cap_rate": analysis.deal_parameters.exit_cap_rate if analysis.deal_parameters else 0.0,
            "irr": analysis.irr,
            "moic": analysis.moic
        }

    def _sanitize_parameters(self, params: DealParameters):
        """Helper to ensure no NaN values in deal parameters"""
        if math.isnan(params.growth_rate): params.growth_rate = 0.03
        if math.isnan(params.vacancy_rate): params.vacancy_rate = 0.05
        if math.isnan(params.management_fee_rate): params.management_fee_rate = 0.04
        if math.isnan(params.tax_rate): params.tax_rate = 0.012
        if math.isnan(params.exit_cap_rate): params.exit_cap_rate = 0.06
        if math.isnan(params.ltv): params.ltv = 0.65
        if math.isnan(params.sofr_rate): params.sofr_rate = 0.05
        if math.isnan(params.bridge_spread): params.bridge_spread = 0.02
        if math.isnan(params.treasury_rate_5yr): params.treasury_rate_5yr = 0.042
        if math.isnan(params.perm_spread): params.perm_spread = 0.0185
        if math.isnan(params.closing_costs): params.closing_costs = 0.0
        if math.isnan(params.renovation_budget): params.renovation_budget = 0.0

    # --- Step 1: Revenue Logic ---
    def _calculate_revenue(self, analysis: UnderwritingAnalysis):
        params = analysis.deal_parameters or DealParameters()

        # Determine Scaling Factor (if Total Units overridden)
        extracted_unit_count = len(analysis.rent_roll)
        
        # FIX: Trust Rent Roll count over Document Metadata for Total Units
        # If rent roll is present, that IS the unit count.
        if extracted_unit_count > 0:
            target_unit_count = extracted_unit_count
            # Update property meta to reflect the correct count
            if analysis.property_meta.total_units != extracted_unit_count:
                logger.info(f"Correcting Property Meta Unit Count from {analysis.property_meta.total_units} to {extracted_unit_count} (based on Rent Roll)")
                analysis.property_meta.total_units = extracted_unit_count
        else:
            target_unit_count = analysis.property_meta.total_units or 0

        # If rent_roll is empty but summary exists, rely on summary (legacy path), else scale
        scaling_factor = 1.0
        if extracted_unit_count > 0 and target_unit_count > 0:
            if extracted_unit_count != target_unit_count:
                scaling_factor = target_unit_count / extracted_unit_count
                logger.info(f"Scaling revenue by factor {scaling_factor:.4f} (Extracted: {extracted_unit_count} -> Target: {target_unit_count})")

        # 0. Generate Unit Mix Summary
        unit_groups: Dict[str, List[float]] = {}
        unit_market_rents: Dict[str, List[float]] = {}
        
        for item in analysis.rent_roll:
            u_type = item.unit_type or "Unknown"
            
            # Update vacancy based on tenant name or current rent if not explicitly set
            if getattr(item, 'is_vacant', None) is None:
                item.is_vacant = ((item.tenant_name or "").lower() == "vacant" or (item.current_rent == 0 and (not item.tenant_name or (item.tenant_name or "").lower() == "vacant")))

            # Use current rent as fallback for market rent if 0 (Fix for Missing Market Rent)
            current = item.current_rent or 0
            market = item.market_rent or 0
            
            # --- FIX: Handle 0$ Market Rent for Vacant Units ---
            # If market rent is 0, we try to use the average market rent for this unit type.
            # If not available yet, we use the current rent (if > 0).
            # If current rent is also 0 (e.g. Vacant), we flag it for second pass.
            
            if market == 0 and current > 0:
                market = current # Conservative fallback: Market = Current
            
            if u_type not in unit_groups:
                unit_groups[u_type] = []
                unit_market_rents[u_type] = []
            
            # Use current if not vacant, else 0
            is_vacant = getattr(item, 'is_vacant', False)
            if is_vacant:
                unit_groups[u_type].append(0.0)
            else:
                unit_groups[u_type].append(current)
                
            unit_market_rents[u_type].append(market)
            
            # Update item in place just in case we need it later
            if item.market_rent == 0:
                item.market_rent = market
                
        # --- SECOND PASS: Fix 0$ Market Rents using Averages ---
        # Now that we've collected data, calculate average market rent per unit type (excluding 0s)
        avg_market_per_type = {}
        for u_type, mkts in unit_market_rents.items():
            valid_rents = [m for m in mkts if m > 0]
            if valid_rents:
                avg_market_per_type[u_type] = sum(valid_rents) / len(valid_rents)
        
        # Apply average market rent to units that still have 0
        for item in analysis.rent_roll:
            if (item.market_rent or 0) == 0:
                u_type = item.unit_type or "Unknown"
                if u_type in avg_market_per_type:
                    fallback = avg_market_per_type[u_type]
                    item.market_rent = fallback
                    logger.info(f"Filled missing Market Rent for unit {item.unit_number} ({u_type}) with average: ${fallback}")
                    # Update our tracking dicts for the summary loop below
                    unit_market_rents[u_type].append(fallback)
            
        summary_list = []
        total_scaled_count = 0
        
        for u_type, rents in unit_groups.items():
            raw_count = len(rents)
            # Scale count
            scaled_count = int(round(raw_count * scaling_factor))
            total_scaled_count += scaled_count
            
            # Calculate average rent excluding units marked as 0 (vacant)
            # In unit_groups, we already appended 0.0 for vacant units.
            paying_rents = [r for r in rents if r > 0]
            avg_rent = sum(paying_rents) / len(paying_rents) if paying_rents else 0
            mkt_rents = unit_market_rents.get(u_type, [])
            avg_mkt = sum(mkt_rents) / raw_count if raw_count > 0 else 0
            
            summary_list.append(UnitTypeSummary(
                unit_type=u_type,
                count=scaled_count,
                avg_rent=self._sanitize_value(avg_rent),
                market_rent=self._sanitize_value(avg_mkt)
            ))
        
        # Adjust rounding errors in unit count to match exactly target_unit_count
        if summary_list and total_scaled_count != target_unit_count:
            diff = target_unit_count - total_scaled_count
            # Add/subtract diff from the largest group
            summary_list.sort(key=lambda x: x.count, reverse=True)
            summary_list[0].count += diff
            
        analysis.unit_mix_summary = summary_list

        # 1. Gross Potential Rent (GPR)
        # Formula: Total Units * Market Rent per Unit * 12
        # Note: We sum up individual units from Rent Roll for accuracy
        raw_gpr = sum((item.market_rent or 0) * 12 for item in analysis.rent_roll)
        gpr = raw_gpr * scaling_factor
        
        # Fallback: If individual items missing but summary exists
        if gpr == 0 and analysis.rent_roll_summary and analysis.rent_roll_summary.total_annual_rent > 0:
             # Assume summary total annual rent is effectively GPR (or close to it) if we lack details
             # Or better: if we have total monthly rent * 12
             gpr = analysis.rent_roll_summary.total_monthly_rent * 12
             logger.warning("Using Rent Roll Summary for GPR as detailed list sum was 0")
        
        # FINAL FALLBACK: If GPR is still 0 (no rent roll items, no summary), try Current Rent Annual
        if gpr == 0:
             raw_current = sum((item.current_rent or 0) * 12 for item in analysis.rent_roll)
             if raw_current > 0:
                 gpr = raw_current * scaling_factor
                 logger.warning("Using Current Rent for GPR (Market Rent missing)")
             
        analysis.gross_potential_rent = self._sanitize_value(gpr)
        self.audit_log_service.add_log(analysis, "GPR", f"${gpr:,.0f}", "Rent Roll", "Sum of (Market Rent * 12)")

        # 2. Loss to Lease
        # Formula: GPR - (Current Rent Roll Sum * 12)
        current_rent_annual_raw = sum((item.current_rent or 0) * 12 for item in analysis.rent_roll)
        current_rent_annual = current_rent_annual_raw * scaling_factor
        
        # Fallback for current rent
        if current_rent_annual == 0 and analysis.rent_roll_summary:
            # If we used the summary, check if we need to scale it too?
            # Ideally the summary object might not be scaled yet if it came from extraction.
            # But if rent_roll list was empty, scaling_factor is 1.0 anyway.
            current_rent_annual = analysis.rent_roll_summary.total_annual_rent

        # Update Rent Roll Summary stats with scaling
        if analysis.rent_roll_summary:
             # Scale occupied units if we have a valid scaling factor
             if scaling_factor != 1.0:
                 raw_occupied = analysis.rent_roll_summary.occupied_units
                 analysis.rent_roll_summary.occupied_units = int(round(raw_occupied * scaling_factor))
                 
                 # Re-calculate occupancy rate just in case, or preserve it?
                 # If we scale both total and occupied by same factor, rate is same.
                 
                 analysis.rent_roll_summary.total_monthly_rent = analysis.rent_roll_summary.total_monthly_rent * scaling_factor
                 analysis.rent_roll_summary.total_annual_rent = analysis.rent_roll_summary.total_annual_rent * scaling_factor
                 
                 # Re-calculate occupancy rate to ensure consistency with new counts
                 if analysis.rent_roll_summary.total_units > 0:
                     analysis.rent_roll_summary.occupancy_rate = analysis.rent_roll_summary.occupied_units / analysis.rent_roll_summary.total_units

        # Apply Occupancy Override if present
        if params.occupancy_override is not None and analysis.rent_roll_summary:
             logger.info(f"Applying Occupancy Override: {params.occupancy_override:.2%}")
             target_occupancy = params.occupancy_override
             
             # Capture old values for scaling rent
             old_occupied = analysis.rent_roll_summary.occupied_units
             
             # Update rate
             analysis.rent_roll_summary.occupancy_rate = target_occupancy
             
             # Update count
             if analysis.rent_roll_summary.total_units > 0:
                  new_occupied = int(round(analysis.rent_roll_summary.total_units * target_occupancy))
                  analysis.rent_roll_summary.occupied_units = new_occupied
                  
                  # Adjust current_rent_annual to reflect the manual occupancy change
                  # If we gained units, we assume they pay average rent of existing units
                  if old_occupied > 0 and new_occupied != old_occupied:
                      rent_adjustment_factor = new_occupied / old_occupied
                      current_rent_annual = current_rent_annual * rent_adjustment_factor
                      
                      # Also update the summary totals for consistency
                      analysis.rent_roll_summary.total_monthly_rent *= rent_adjustment_factor
                      analysis.rent_roll_summary.total_annual_rent *= rent_adjustment_factor
                      
                      logger.info(f"Adjusted Current Rent Annual by {rent_adjustment_factor:.4f} due to occupancy override")
             

        loss_to_lease = gpr - current_rent_annual
        analysis.loss_to_lease = self._sanitize_value(loss_to_lease)
        self.audit_log_service.add_log(analysis, "Loss to Lease", f"${loss_to_lease:,.0f}", "Calculation", "GPR - Current Rent Annualized")

        # 3. Vacancy Loss
        # Formula: GPR * 0.03 (Valiance Constraint)
        vacancy_loss = gpr * params.vacancy_rate
        analysis.vacancy_loss = self._sanitize_value(vacancy_loss)
        self.audit_log_service.add_log(analysis, "Vacancy Loss", f"${vacancy_loss:,.0f}", "Valiance Rule", f"{params.vacancy_rate:.1%} of GPR")

        # 4. Effective Gross Income (EGI)
        # Formula: GPR - LossToLease - VacancyLoss + Other Income
        # Note: Assuming 'Other Income' is 0 for now as it's not in the base extraction yet,
        # but could be added from T12 extraction if available.
        
        # Note: We aggregate extracted 'Other Income' and 'Reimbursements' from T12.
        # FIX: We now capture this in calculate_historical and store it in analysis.other_income.
        # Use that value as base, but fallback to re-calculating if 0 (e.g. if calc_historical wasn't run).
        
        other_income_total = analysis.other_income or 0.0
        
        if other_income_total == 0 and analysis.historical_expenses:
             # Fallback: Iteration (Only works if historical_expenses hasn't been filtered yet)
             for expense in analysis.historical_expenses:
                if expense.mapped_category in [ExpenseCategory.OTHER_INCOME, ExpenseCategory.REIMBURSEMENTS]:
                     other_income_total += expense.amount

        # Scale Other Income if we scaled units?
        # Typically Laundry/Parking scales with units.
        if scaling_factor != 1.0 and other_income_total > 0:
             other_income_total *= scaling_factor
             logger.info(f"Scaled Other Income by {scaling_factor:.4f} -> ${other_income_total:,.0f}")
             
        analysis.other_income = self._sanitize_value(other_income_total)
        
        egi = gpr - loss_to_lease - vacancy_loss + other_income_total
        analysis.effective_gross_income = self._sanitize_value(egi)
        self.audit_log_service.add_log(analysis, "Other Income", f"${other_income_total:,.0f}", "T12 Extraction", "Sum of Other Income & Reimbursements")
        self.audit_log_service.add_log(analysis, "EGI", f"${egi:,.0f}", "Calculation", "GPR - LossToLease - VacancyLoss + OtherIncome")

    # --- Step 2: Expense Logic ---
    def _calculate_expenses(self, analysis: UnderwritingAnalysis):
        params = analysis.deal_parameters or DealParameters()
        egi = analysis.effective_gross_income or 0
        purchase_price = analysis.property_meta.purchase_price or 0
        
        expense_breakdown: List[ProFormaExpenseItem] = []

        # 1. Property Taxes (Prop 13 Reset)
        # Formula: (Purchase Price * Tax Rate) + Special Assessments
        pro_forma_tax = self._sanitize_value(purchase_price * params.tax_rate)
        expense_breakdown.append(ProFormaExpenseItem(name=ExpenseCategory.REAL_ESTATE_TAXES.value, amount=pro_forma_tax))
        self.audit_log_service.add_log(analysis, "Expense: Taxes", f"${pro_forma_tax:,.0f}", "Valiance Rule", f"Purchase Price * {params.tax_rate:.2%}")

        # 2. Management Fee
        # Formula: EGI * 0.04
        mgmt_fee = self._sanitize_value(egi * params.management_fee_rate)
        expense_breakdown.append(ProFormaExpenseItem(name=ExpenseCategory.MANAGEMENT_FEES.value, amount=mgmt_fee))
        self.audit_log_service.add_log(analysis, "Expense: Mgmt Fee", f"${mgmt_fee:,.0f}", "Valiance Rule", f"{params.management_fee_rate:.1%} of EGI")

        # 3. Other Operating Expenses (Sourced from T12)
        # We aggregate historical expenses by category, excluding Taxes and Mgmt Fees which are recalculated.
        other_expenses_map: Dict[str, float] = {}
        has_t12_data = False
        
        # Track presence of critical expenses
        has_payroll = False
        has_marketing = False

        if analysis.historical_expenses:
            has_t12_data = True
            
            # Group items by category to prioritize verified ones
            from collections import defaultdict
            items_by_cat = defaultdict(list)
            for exp in analysis.historical_expenses:
                cat_val = exp.mapped_category.value if hasattr(exp.mapped_category, 'value') else str(exp.mapped_category)
                items_by_cat[cat_val].append(exp)
            
            for cat_name, items in items_by_cat.items():
                # Identify first item to check category type (for exclusions)
                first_item = items[0]
                
                # --- FIX: Strict Exclusion Logic ---
                # Exclude Taxes/Mgmt (calculated separately)
                # Exclude Non-OpEx categories (Debt, Reserves, Uncategorized, Property Info)
                
                # Check Enum exclusions
                if first_item.mapped_category in [
                    ExpenseCategory.REAL_ESTATE_TAXES,
                    ExpenseCategory.MANAGEMENT_FEES,
                    ExpenseCategory.CURRENT_LOAN_BALANCE,
                    ExpenseCategory.CAPITAL_RESERVES,
                    ExpenseCategory.UNCATEGORIZED, # Exclude Uncategorized from Pro Forma Sum
                    ExpenseCategory.PROPERTY_INFO,
                    ExpenseCategory.ACCOUNTS_RECEIVABLE,
                    ExpenseCategory.PURCHASE_PRICE,
                    ExpenseCategory.PRICE_PER_UNIT,
                    ExpenseCategory.TOTAL_UNITS,
                    ExpenseCategory.YEAR_BUILT,
                    ExpenseCategory.LEASING_FEES,
                    # FIX: Exclude Revenue Items from Pro Forma Expense Sum
                    ExpenseCategory.OTHER_INCOME,
                    ExpenseCategory.GROSS_POTENTIAL_RENT,
                    ExpenseCategory.REIMBURSEMENTS
                ]:
                    continue
                
                # Additional String Checks (Case-insensitive for safety)
                cat_val_lower = cat_name.lower()
                if any(x in cat_val_lower for x in [
                    "debt", "mortgage", "non-operating", "capital expenditure",
                    "depreciation", "amortization", "uncategorized",
                    "property characteristic", "loan", "receivable", "deposit"
                ]):
                    continue
                
                # Exclude Revenue keywords
                if "income" in cat_val_lower or "revenue" in cat_val_lower or "reimbursement" in cat_val_lower:
                    continue

                # Check for critical categories
                verified_in_cat = [i for i in items if getattr(i, 'user_verified', False)]
                
                if verified_in_cat:
                    # PRIORITY: If user verified/edited items in this category, use ONLY those.
                    # This ensures that edited values completely replace unverified ones.
                    cat_total = sum(i.amount for i in verified_in_cat)
                    logger.info(f"Priority: Using {len(verified_in_cat)} user-verified items for category '{cat_name}' (Total: ${cat_total})")
                    
                    # Update trackers
                    if any(i.mapped_category == ExpenseCategory.PAYROLL for i in verified_in_cat):
                        has_payroll = True
                    if any("Marketing" in str(i.mapped_category) or "Advertising" in str(i.mapped_category) for i in verified_in_cat):
                        has_marketing = True
                else:
                    # No verified items, sum up unverified ones
                    cat_total = sum(i.amount for i in items)
                    
                    # Update trackers
                    if any(i.mapped_category == ExpenseCategory.PAYROLL for i in items):
                        has_payroll = True
                    if any("Marketing" in str(i.mapped_category) or "Advertising" in str(i.mapped_category) for i in items):
                        has_marketing = True

                other_expenses_map[cat_name] = cat_total
        else:
             self.audit_log_service.add_log(analysis, "Data Warning", "No T12 Expenses Found", "Extraction", "Using only calculated Taxes & Mgmt Fee")
        
        # Dynamic Estimation for Missing Expenses
        # If Payroll or Marketing is missing, we estimate them based on standard industry ratios
        # Payroll ~ $1,200 - $1,500 per unit per year (Standard for 20+ units)
        # Marketing ~ $150 - $300 per unit per year
        
        # Only estimate if unit count > 5 (small properties might not have payroll)
        # FIX: Prioritize Rent Roll count
        unit_count = len(analysis.rent_roll) or analysis.property_meta.total_units or 0
        
        # Check Flow Type: For OM_DRIVEN (Flow A), do NOT auto-guess missing expenses.
        is_flow_a = getattr(analysis, "underwriting_flow", "MULTI_SOURCE") == "OM_DRIVEN"

        if unit_count > 5:
            if not has_payroll:
                if is_flow_a:
                    logger.info("Flow A (OM_DRIVEN): Skipping Payroll estimation (Missing in OM).")
                else:
                    # Conservative estimate: $1,200 per unit
                    est_payroll = unit_count * 1200.0
                    other_expenses_map[ExpenseCategory.PAYROLL.value] = est_payroll
                    self.audit_log_service.add_log(analysis, "Expense Estimation", f"${est_payroll:,.0f}", "Missing Data", "Estimated Payroll ($1,200/unit)")
                    logger.info(f"Estimated Payroll for {unit_count} units: ${est_payroll}")
            
            if not has_marketing:
                if is_flow_a:
                    logger.info("Flow A (OM_DRIVEN): Skipping Marketing estimation (Missing in OM).")
                else:
                     # Conservative estimate: $200 per unit
                    est_marketing = unit_count * 200.0
                    # Use value string for map key
                    other_expenses_map[ExpenseCategory.ADVERTISING_MARKETING.value] = est_marketing
                    self.audit_log_service.add_log(analysis, "Expense Estimation", f"${est_marketing:,.0f}", "Missing Data", "Estimated Marketing ($200/unit)")
                    logger.info(f"Estimated Marketing for {unit_count} units: ${est_marketing}")

        # Add aggregated other expenses to breakdown
        total_other_opex = 0.0
        for name, amount in other_expenses_map.items():
            safe_amount = self._sanitize_value(amount)
            expense_breakdown.append(ProFormaExpenseItem(name=name, amount=safe_amount))
            total_other_opex += safe_amount
            
        if has_t12_data:
            self.audit_log_service.add_log(analysis, "Other OpEx", f"${total_other_opex:,.0f}", "Aggregation", "Sum of T12 Expenses (Excl. Tax/Mgmt)")

        total_opex = sum(item.amount for item in expense_breakdown)
        
        # 4. Enforce 38% Rule for F12 Pro Forma (Floor)
        target_ratio = params.expense_ratio_target # 0.38
        target_opex = egi * target_ratio
        
        if total_opex < target_opex:
            shortfall = target_opex - total_opex
            # Add shortfall as "Capital Reserves" to hit the 38% target
            expense_breakdown.append(ProFormaExpenseItem(name=ExpenseCategory.CAPITAL_RESERVES.value, amount=shortfall))
            total_opex = target_opex
            self.audit_log_service.add_log(analysis, "Expense Adjustment", f"${shortfall:,.0f}", "38% Rule", f"Added Reserves to hit {target_ratio:.0%} Expense Ratio")

        analysis.pro_forma_expenses = self._sanitize_value(total_opex)
        analysis.pro_forma_expenses_detailed = expense_breakdown
        
        expense_ratio = total_opex / egi if egi > 0 else 0
        self.audit_log_service.add_log(analysis, "Total OpEx", f"${total_opex:,.0f}", "Calculation", f"Final Ratio: {expense_ratio:.1%}")

    # --- Step 3: Profitability Metrics (NOI) ---
    def _calculate_profitability(self, analysis: UnderwritingAnalysis):
        egi = analysis.effective_gross_income or 0
        opex = analysis.pro_forma_expenses or 0
        purchase_price = analysis.property_meta.purchase_price or 0
        params = analysis.deal_parameters or DealParameters()

        # 1. Net Operating Income (NOI)
        # Formula: EGI - OpEx
        noi = egi - opex
        analysis.pro_forma_noi = self._sanitize_value(noi)
        self.audit_log_service.add_log(analysis, "NOI", f"${noi:,.0f}", "Calculation", "EGI - OpEx")

        # 2. Yield on Cost (Unlevered Yield)
        # Formula: NOI / Total Project Cost
        # Total Project Cost = Purchase Price + Closing Costs + Renovation Budget
        total_project_cost = purchase_price + params.closing_costs + params.renovation_budget
        analysis.total_project_cost = total_project_cost
        
        yield_on_cost = noi / total_project_cost if total_project_cost > 0 else 0
        analysis.yield_on_cost = self._sanitize_value(yield_on_cost)
        self.audit_log_service.add_log(analysis, "Yield on Cost", f"{yield_on_cost:.2%}", "Calculation", "NOI / Total Project Cost")

        # 3. Entry Cap Rate
        # Formula: NOI / Purchase Price
        entry_cap_rate = noi / purchase_price if purchase_price > 0 else 0
        analysis.cap_rate = self._sanitize_value(entry_cap_rate)
        self.audit_log_service.add_log(analysis, "Entry Cap Rate", f"{entry_cap_rate:.2%}", "Calculation", "NOI / Purchase Price")

    # --- Step 4: Debt & Cash Flow ---
    def _calculate_debt_and_cash_flow(self, analysis: UnderwritingAnalysis):
        params = analysis.deal_parameters or DealParameters()
        purchase_price = analysis.property_meta.purchase_price or 0
        noi = analysis.pro_forma_noi or 0
        total_project_cost = analysis.total_project_cost or 0

        # 1. Loan Amount Logic
        # PRIORITY: If user explicitly provided loan_amount in parameters, use that
        # Log the incoming param for debugging
        logger.info(f"Loan Calculation - Params Loan Amount: {params.loan_amount}, Purchase Price: {purchase_price}, LTV: {params.ltv}")

        if params.loan_amount is not None and params.loan_amount > 0:
            loan_amount = float(params.loan_amount)
            method = f"User-Specified Loan Amount"
            logger.info(f"Using user-specified loan amount: ${loan_amount:,.0f}")
        
        # CASE A: Purchase Price is known -> Standard LTV calculation
        elif purchase_price > 0:
            loan_amount = purchase_price * params.ltv
            method = f"Purchase Price * {params.ltv:.0%} LTV"
        
        # CASE B: Purchase Price is missing (0) -> Back-solve from NOI/Cap Rate (Implied Value)
        else:
            # Assume a market cap rate (e.g., 5.5% or exit cap rate) to estimate value
            # If NOI is negative, implied value is 0 (cannot have negative property value for loan purposes)
            implied_value = max(0.0, noi / params.exit_cap_rate if params.exit_cap_rate > 0 else 0)
            loan_amount = implied_value * params.ltv
            method = f"Implied Value (NOI/{params.exit_cap_rate:.1%}) * {params.ltv:.0%} LTV (Price Missing)"
            
            # Update purchase price in meta so other metrics (Cap Rate) work?
            # Ideally, we flag this as an estimate.
            if implied_value > 0:
                logger.warning(f"Purchase Price missing. Using Implied Value ${implied_value:,.0f} for Loan calc.")
                # We won't overwrite extracted Purchase Price to preserve data integrity,
                # but we will use this implied loan amount.
                
                # FIX: We MUST update total_project_cost if we used implied value for loan!
                # Otherwise equity_invested becomes negative and Cash-on-Cash drops to 0.
                total_project_cost = implied_value + params.closing_costs + params.renovation_budget
                analysis.total_project_cost = self._sanitize_value(total_project_cost)

        analysis.loan_amount = self._sanitize_value(loan_amount)
        self.audit_log_service.add_log(analysis, "Loan Amount", f"${loan_amount:,.0f}", "Calculation", method)

        # 2. Debt Service (Interest Only - "Bridge Debt")
        # Formula: SOFR + Spread
        interest_rate = params.sofr_rate + params.bridge_spread
        
        # Calculate Perm Debt Option (for comparison/memo)
        perm_rate = params.treasury_rate_5yr + params.perm_spread
        
        annual_debt_service = loan_amount * interest_rate
        analysis.annual_debt_service = self._sanitize_value(annual_debt_service)
        self.audit_log_service.add_log(analysis, "Debt Service", f"${annual_debt_service:,.0f}", "Calculation", f"Loan * {interest_rate:.2%} (IO)")

        # 3. Levered Cash Flow
        # Formula: NOI - Annual Debt Service
        cash_flow = noi - annual_debt_service
        analysis.cash_flow = self._sanitize_value(cash_flow)
        self.audit_log_service.add_log(analysis, "Cash Flow", f"${cash_flow:,.0f}", "Calculation", "NOI - Debt Service")

        # 4. Cash on Cash Return
        # Formula: Cash Flow / Equity Invested
        # Equity Invested = Total Project Cost - Loan Amount
        equity_invested = total_project_cost - loan_amount
        analysis.equity_invested = self._sanitize_value(equity_invested)
        
        coc = cash_flow / equity_invested if equity_invested > 0 else 0
        analysis.cash_on_cash_return = self._sanitize_value(coc)
        self.audit_log_service.add_log(analysis, "Cash on Cash", f"{coc:.2%}", "Calculation", "Cash Flow / Equity Invested")
        
        # Additional Metrics
        analysis.dscr = self._sanitize_value(noi / annual_debt_service if annual_debt_service > 0 else 0)
        analysis.debt_yield = self._sanitize_value(noi / loan_amount if loan_amount > 0 else 0)

    # --- Step 5: Time-Based Returns (IRR & MOIC) ---
    def _calculate_returns(self, analysis: UnderwritingAnalysis):
        params = analysis.deal_parameters or DealParameters()

        # VALIDATION: Ensure rent_growth is valid before projection
        if params.growth_rate is None or math.isnan(params.growth_rate):
             params.growth_rate = 0.03
             
        # Generate Sensitivity Matrix
        self._generate_sensitivity_matrix(analysis)
        
        # 1. Revenue Growth Logic
        # 5-Year Array/Loop
        cash_flows = []
        equity_invested = analysis.equity_invested or 0
        
        # Year 0: Investment (Negative)
        cash_flows.append(-equity_invested)
        
        # Current NOI is Year 1 Base
        current_noi = analysis.pro_forma_noi or 0
        
        # IMPORTANT: We assume NOI grows at the same rate as Revenue for simplicity in this model,
        # OR we could grow Revenue and Expenses separately.
        # Given the prompt says "Rents grow 3% annually", we'll apply growth to NOI for simplicity 
        # unless full pro-forma tables are needed. 
        # Re-reading prompt: "Year N Revenue = Year N-1 Revenue * 1.03".
        # It doesn't specify Expense growth, but usually expenses grow too (at 2-3%).
        # Let's assume NOI grows at 3% to keep it consistent with Revenue growth, 
        # or implies Revenue grows and Expenses stay flat (which is aggressive).
        # Better approach: Grow Revenue by 3%, Expenses by 3% (Standard), so NOI grows by 3%.
        
        annual_noi = current_noi
        
        # Years 1-4 Cash Flow
        for year in range(1, params.hold_period):
            # Cash Flow = NOI - Debt Service
            cf = annual_noi - (analysis.annual_debt_service or 0)
            cash_flows.append(cf)
            
            # Grow NOI for next year
            annual_noi *= (1 + params.growth_rate)
            
        # Year 5 (Exit Year)
        year_5_noi = annual_noi
        # Note: Sell on Year 6 NOI (forward NOI)
        year_6_noi = year_5_noi * (1 + params.growth_rate)
        
        # 2. Exit Valuation
        # Formula: Year 6 NOI / Exit Cap Rate
        if params.exit_cap_rate and params.exit_cap_rate > 0:
            sale_price = year_6_noi / params.exit_cap_rate
        else:
            sale_price = 0.0
        analysis.exit_valuation = self._sanitize_value(sale_price)
        
        # 3. Net Sale Proceeds
        # Formula: Sale Price - Sales Costs (2%) - Outstanding Loan Balance
        sales_costs = sale_price * params.sales_cost_rate
        loan_balance = analysis.loan_amount or 0 # Interest Only, so balance is constant
        net_proceeds = sale_price - sales_costs - loan_balance
        analysis.net_sale_proceeds = self._sanitize_value(net_proceeds)
        
        # Year 5 Cash Flow includes Operations + Sale
        year_5_cf = (year_5_noi - (analysis.annual_debt_service or 0)) + net_proceeds
        cash_flows.append(year_5_cf)
        
        # 4. MOIC
        # Formula: Sum(Positive Cash Flows) / Abs(Sum(Negative Cash Flows))
        # Note: cash_flows[0] is negative equity. Any other negative CFs are capital calls.
        total_inflows = sum(cf for cf in cash_flows if cf > 0)
        total_outflows = abs(sum(cf for cf in cash_flows if cf < 0))
        moic = total_inflows / total_outflows if total_outflows > 0 else 0
        analysis.moic = self._sanitize_value(moic)
        
        # 5. IRR
        try:
            # Check for zero cash flows
            if not cash_flows:
                irr = 0.0
            # If all cash flows are negative (total loss), return -1.0 (-100%)
            elif all(cf <= 0 for cf in cash_flows):
                irr = -1.0
            # If all cash flows are positive (no investment?), return 0.0 (undefined)
            elif all(cf >= 0 for cf in cash_flows):
                irr = 0.0
            else:
                irr = npf.irr(cash_flows)
                # Handle complex results
                if isinstance(irr, complex):
                    irr = 0.0
                elif irr is None or math.isnan(irr) or math.isinf(irr):
                    irr = 0.0
                else:
                    irr = float(irr)
        except Exception:
            irr = 0.0
            
        analysis.irr = self._sanitize_value(irr)
        
        self.audit_log_service.add_log(analysis, "IRR", f"{irr:.2%}", "Numpy Financial", "IRR of 5-Year Cash Flows")
        self.audit_log_service.add_log(analysis, "MOIC", f"{moic:.2f}x", "Calculation", "Total Inflows / Total Outflows (Incl. Cap Calls)")

    def _calculate_irr_simulation(self, analysis: UnderwritingAnalysis, growth_rate: float, exit_cap_rate: float) -> float:
        """
        Helper to simulate IRR for Sensitivity Analysis.
        Does not modify analysis object.
        """
        params = analysis.deal_parameters or DealParameters()
        
        equity_invested = analysis.equity_invested or 0
        current_noi = analysis.pro_forma_noi or 0
        annual_debt_service = analysis.annual_debt_service or 0
        loan_amount = analysis.loan_amount or 0
        
        cash_flows = []
        # Year 0
        cash_flows.append(-equity_invested)
        
        annual_noi = current_noi
        
        # Years 1 to (Hold-1)
        for year in range(1, params.hold_period):
            cf = annual_noi - annual_debt_service
            cash_flows.append(cf)
            annual_noi *= (1 + growth_rate)
            
        # Year 5 (Exit)
        year_exit_noi = annual_noi
        
        # Sell on forward NOI (Year 6)
        # Note: If exit cap is applied to T12 (Year 5 actual), use year_exit_noi.
        # If applied to Forward 12 (Year 6), use year_forward_noi.
        # Standard practice is often Forward 12 for pricing.
        year_forward_noi = year_exit_noi * (1 + growth_rate)
        
        if exit_cap_rate > 0:
            sale_price = year_forward_noi / exit_cap_rate
        else:
            sale_price = 0.0
            
        sales_costs = sale_price * params.sales_cost_rate
        net_proceeds = sale_price - sales_costs - loan_amount
        
        # Year 5 Cash Flow
        year_exit_cf = (year_exit_noi - annual_debt_service) + net_proceeds
        cash_flows.append(year_exit_cf)
        
        try:
            # Check for zero cash flows
            if not cash_flows:
                return 0.0
            # If all cash flows are negative (total loss), return -1.0 (-100%)
            if all(cf <= 0 for cf in cash_flows):
                return -1.0
            # If all cash flows are positive, return 0.0
            if all(cf >= 0 for cf in cash_flows):
                return 0.0
                
            irr = npf.irr(cash_flows)
            
            # Handle complex results (rare but possible with weird polynomials)
            if isinstance(irr, complex):
                return 0.0
                
            if irr is None or math.isnan(irr) or math.isinf(irr):
                return 0.0
                
            return float(irr)
        except Exception as e:
            logger.warning(f"IRR Simulation failed: {str(e)}")
            return 0.0

    def _generate_sensitivity_matrix(self, analysis: UnderwritingAnalysis):
        params = analysis.deal_parameters or DealParameters()
        base_exit_cap = params.exit_cap_rate
        base_growth = params.growth_rate
        
        # Rows: Exit Cap Rate (Base-0.5%, Base, Base+0.5%)
        # Columns: Rent Growth (Base-1%, Base, Base+1%)
        
        row_steps = [-0.005, 0.0, 0.005]
        col_steps = [-0.01, 0.0, 0.01]
        
        exit_caps = [max(0, base_exit_cap + step) for step in row_steps]
        growth_rates = [base_growth + step for step in col_steps]
        
        values = []
        for cap in exit_caps:
            row_vals = []
            for growth in growth_rates:
                irr = self._calculate_irr_simulation(analysis, growth, cap)
                row_vals.append(irr)
            values.append(row_vals)
            
        analysis.sensitivity_analysis = {
            "rows": exit_caps,
            "columns": growth_rates,
            "values": values
        }

    def get_audit_trail(self, analysis: UnderwritingAnalysis) -> List[Dict[str, Any]]:
        return analysis.audit_trail