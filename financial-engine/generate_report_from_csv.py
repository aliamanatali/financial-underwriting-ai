import csv
import os
from collections import defaultdict

def generate_report(csv_path):
    print(f"Generating Report from: {csv_path}")
    print("="*60)
    
    data = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data = list(reader)
    except FileNotFoundError:
        print("Error: File not found.")
        return

    # Aggregators
    property_meta = {}
    income_items = defaultdict(list)
    expense_items = defaultdict(list)
    capital_items = defaultdict(list)
    debt_items = defaultdict(list)
    missing_data_rows = []
    
    total_revenue = 0.0
    total_expenses = 0.0
    
    # Processing
    for row in data:
        raw = row.get('raw_text', '')
        norm_val = row.get('normalized_value', '')
        group = row.get('category_group', '')
        amount_str = row.get('amount', '0.0')
        source = row.get('source_document', '')
        
        try:
            amount = float(amount_str)
        except (ValueError, TypeError):
            amount = 0.0
        
        # CATEGORIZATION LOGIC
        
        # 1. Property Info
        if group == 'Property Info' or 'Property' in group:
            if 'Address' in norm_val or 'Address' in raw:
                # Keep the longest address found
                if len(raw) > len(property_meta.get('Address', '')):
                    property_meta['Address'] = raw
            elif 'Units' in norm_val or 'Units' in raw:
                # If amount > 0, use it as unit count
                if amount > 0:
                    # Logic to find the most "plausible" unit count (mode or max?)
                    # Usually it repeats. Let's just store the last one seen or logic for max frequency later?
                    # For now, just overwriting might flip-flop. 
                    # Let's store all seen counts and take the mode at the end?
                    property_meta['Total Units'] = int(amount)
            elif 'Year Built' in norm_val or 'Year' in raw:
                if amount > 1800: property_meta['Year Built'] = int(amount)
            elif 'Purchase Price' in norm_val or 'Price' in raw:
                if amount > 1000: 
                    property_meta['Purchase Price'] = amount
            else:
                if norm_val not in property_meta:
                    property_meta[norm_val] = raw
        
        # 2. Financials
        elif group == 'Revenue' or 'Income' in group:
            if amount > 0:
                income_items[norm_val].append(amount)
                total_revenue += amount
            else:
                if amount == 0:
                     # Log zero revenue items just in case
                     pass
                
        elif group == 'Operating Expense' or 'Expense' in group:
            if amount > 0:
                expense_items[norm_val].append(amount)
                total_expenses += amount
            else:
                pass

        elif group == 'Tax & Insurance':
             if amount > 0:
                expense_items[norm_val].append(amount)
                total_expenses += amount
             else:
                pass
                
        elif group == 'Capital Expenditure':
            if amount > 0:
                capital_items[norm_val].append(amount)
            else:
                pass
        
        elif group == 'Debt':
             if amount > 0:
                debt_items[norm_val].append(amount)
        
        else:
            # Uncategorized or Other
            if amount > 0:
                 # Check if it looks like an expense?
                 pass

    # REPORT OUTPUT
    
    print("\n--- PROPERTY METADATA ---")
    for k, v in property_meta.items():
        if k == 'Purchase Price':
             print(f"{k:25}: ${v:,.2f}")
        else:
             print(f"{k:25}: {v}")
        
    print("\n--- REVENUE ---")
    
    for cat, amounts in income_items.items():
        count = len(amounts)
        total = sum(amounts)
        avg = total / count if count else 0
        print(f"{cat:30}: ${total:,.2f} (Count: {count}, Avg: ${avg:,.2f})")

    print(f"\nTOTAL DETECTED REVENUE SUM: ${total_revenue:,.2f}")

    print("\n--- OPERATING EXPENSES ---")
    for cat, amounts in expense_items.items():
        count = len(amounts)
        total = sum(amounts)
        print(f"{cat:30}: ${total:,.2f} (Count: {count})")
        
    print(f"\nTOTAL DETECTED EXPENSES: ${total_expenses:,.2f}")

    if total_revenue > 0:
        noi = total_revenue - total_expenses
        expense_ratio = (total_expenses / total_revenue) * 100
        print(f"\n--- FINANCIAL SUMMARY ---")
        print(f"NET OPERATING INCOME (NOI): ${noi:,.2f}")
        print(f"EXPENSE RATIO             : {expense_ratio:.2f}%")
    
    if capital_items:
        print("\n--- CAPITAL EXPENDITURES (Excluded from NOI) ---")
        for cat, amounts in capital_items.items():
            print(f"{cat:30}: ${sum(amounts):,.2f}")

    if debt_items:
        print("\n--- DEBT ITEMS (Balance/Payments) ---")
        for cat, amounts in debt_items.items():
            print(f"{cat:30}: ${sum(amounts):,.2f}")


    print("\n" + "="*60)
    print("END OF REPORT")

if __name__ == "__main__":
    # Use the file provided in the prompt
    csv_file = "financial-engine/batch_logs/normalization_20260205_173141.csv"
    if os.path.exists(csv_file):
        generate_report(csv_file)
    else:
        print(f"File not found at {csv_file}")
        # Try to find any normalization file in the directory
        import glob
        files = glob.glob("financial-engine/batch_logs/normalization_*.csv")
        if files:
            print(f"Found alternative file: {files[-1]}")
            generate_report(files[-1])