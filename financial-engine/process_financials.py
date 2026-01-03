import pandas as pd
import json
import re
import os
import numpy as np

# Updated Purchase Price from user feedback
PURCHASE_PRICE = 0

def normalize_value(val):
    """
    Converts string currency formats to float.
    Removes $, commas. Handles parentheses as negative.
    """
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    
    val_str = str(val).strip()
    if not val_str:
        return 0.0
        
    # Check for parentheses indicating negative
    is_negative = False
    if val_str.startswith('(') and val_str.endswith(')'):
        is_negative = True
        val_str = val_str[1:-1]
        
    # Remove currency symbols and commas
    val_str = re.sub(r'[$,]', '', val_str)
    
    try:
        num = float(val_str)
        return -num if is_negative else num
    except ValueError:
        return 0.0

def process_file(file_path):
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}

    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        return {"error": f"Failed to read excel: {str(e)}"}
    
    # Normalize all numeric columns (cols 1 onwards)
    month_columns = df.columns[1:]
    
    for col in month_columns:
        df[col] = df[col].apply(normalize_value)
        
    revenue_items = []
    expense_items = []
    
    # Finding section markers
    revenue_section = True
    
    # Storage for calculated totals
    calc_revenue_monthly = {col: 0.0 for col in month_columns}
    calc_expense_monthly = {col: 0.0 for col in month_columns}
    
    provided_total_revenue = None
    provided_total_expenses = None
    provided_noi = None
    
    inconsistencies = []

    for idx, row in df.iterrows():
        category = str(row[df.columns[0]]).strip()
        lower_cat = category.lower()
        
        # Skip empty rows
        if not category or category == 'nan':
            continue

        # Get row values
        values = {col: float(row[col]) for col in month_columns}
        annual_total = sum(values.values())
        
        item_data = {
            "category": category,
            "monthly": values,
            "annual": annual_total
        }
        
        # Check logic for Total Rows vs Item Rows
        # Flexible matching for "Total Rev", "Total Revenue", "Total Exp", "Total Expenses"
        if "total rev" in lower_cat or "total income" in lower_cat:
            provided_total_revenue = item_data
            revenue_section = False # Switch to expenses
            continue
            
        if "total exp" in lower_cat or "total operating expenses" in lower_cat:
            provided_total_expenses = item_data
            continue
            
        if "net operating income" in lower_cat or "noi" in lower_cat:
            provided_noi = item_data
            continue
            
        # Classify items
        if revenue_section:
            revenue_items.append(item_data)
            for col in month_columns:
                calc_revenue_monthly[col] += values[col]
        else:
            # We assume everything after Total Revenue is an expense until NOI
            expense_items.append(item_data)
            for col in month_columns:
                calc_expense_monthly[col] += values[col]

    # Calculate Annual Totals
    calc_revenue_annual = sum(calc_revenue_monthly.values())
    calc_expense_annual = sum(calc_expense_monthly.values())
    calc_noi_annual = calc_revenue_annual - calc_expense_annual
    
    # 1. Check Revenue Consistency
    if provided_total_revenue:
        diff = abs(provided_total_revenue['annual'] - calc_revenue_annual)
        if diff > 1.0: # Tolerance for rounding
            inconsistencies.append({
                "type": "Revenue Mismatch",
                "details": f"Calculated Annual Revenue ({calc_revenue_annual:,.2f}) does not match Provided Total Revenue ({provided_total_revenue['annual']:,.2f})"
            })
            
    # 2. Check Expense Consistency
    if provided_total_expenses:
        diff = abs(provided_total_expenses['annual'] - calc_expense_annual)
        if diff > 1.0:
            inconsistencies.append({
                "type": "Expense Mismatch",
                "details": f"Calculated Annual Expenses ({calc_expense_annual:,.2f}) does not match Provided Total Expenses ({provided_total_expenses['annual']:,.2f})"
            })

    # 3. Check NOI Consistency (if provided)
    if provided_noi:
        diff = abs(provided_noi['annual'] - calc_noi_annual)
        if diff > 1.0:
            inconsistencies.append({
                "type": "NOI Mismatch",
                "details": f"Calculated Annual NOI ({calc_noi_annual:,.2f}) does not match Provided NOI ({provided_noi['annual']:,.2f})"
            })
            
    # 4. Check negative values where they shouldn't be (Revenue usually positive)
    for item in revenue_items:
        if item['annual'] < 0:
             inconsistencies.append({
                "type": "Negative Revenue",
                "details": f"Revenue item '{item['category']}' is negative ({item['annual']:,.2f})"
            })

    # Calculate Cap Rate
    # Purchase price should be passed in or extracted, avoiding hardcoded default if possible
    purchase_price = PURCHASE_PRICE
    if purchase_price == 0 and 'purchase_price' in globals():
         purchase_price = globals()['PURCHASE_PRICE']

    cap_rate_percent = (calc_noi_annual / purchase_price) * 100 if purchase_price else 0

    return {
        "status": "success" if not inconsistencies else "warning",
        "financial_summary": {
            "gross_revenue": calc_revenue_annual,
            "total_expenses": calc_expense_annual,
            "net_operating_income": calc_noi_annual,
            "purchase_price": purchase_price,
            "cap_rate_percent": round(cap_rate_percent, 2)
        },
        "inconsistencies": inconsistencies,
        "line_items": {
            "revenue": [ {k:v for k,v in i.items() if k != 'monthly'} for i in revenue_items], # Summarized for brevity
            "expenses": [ {k:v for k,v in i.items() if k != 'monthly'} for i in expense_items]
        }
    }

if __name__ == "__main__":
    # Pointing to the messy file
    file_path = "../../Keystone_Apartments_Inputs_messy/04 - Financials/T12_Statement.xlsx"
    result = process_file(file_path)
    print(json.dumps(result, indent=2))