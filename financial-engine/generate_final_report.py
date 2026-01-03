import json

def generate_report():
    # Data derived from previous analysis steps
    t12_data = {
        "source_file": "Keystone_Apartments_Inputs_messy/04 - Financials/T12_Statement.xlsx",
        "gross_revenue": 345338.00,
        "total_expenses": 120742.90,
        "noi": 224595.10,
        "cap_rate": 2.25
    }

    rent_roll_data = {
        "source_file": "Keystone_Apartments_Inputs_messy/02 - Rent Roll/rent_roll.xlsx",
        "annualized_actual_rent": 322512.00,
        "annualized_market_rent": 360000.00
    }

    user_expectations = {
        "description": "Provided in feedback",
        "gross_potential_rent": 1200000.00,
        "noi": 1148950.00,
        "cap_rate": 11.49,
        "purchase_price": 0.00 # Placeholder - to be filled by user input or extraction
    }

    # Consistency Flags
    flags = []

    # 1. T12 vs Rent Roll
    if abs(t12_data["gross_revenue"] - rent_roll_data["annualized_actual_rent"]) > 50000:
         flags.append({
            "severity": "MEDIUM",
            "issue": "T12 Revenue differs from Annualized Rent Roll",
            "details": f"T12: ${t12_data['gross_revenue']:,.2f} vs Rent Roll: ${rent_roll_data['annualized_actual_rent']:,.2f}"
        })

    # 2. Data vs Expectations (The Major Discrepancy)
    if abs(t12_data["noi"] - user_expectations["noi"]) > 100000:
        flags.append({
            "severity": "CRITICAL",
            "issue": "Financial Data does not match User Expectations",
            "details": f"Calculated NOI (${t12_data['noi']:,.2f}) is significantly lower than expected (${user_expectations['noi']:,.2f}). The provided Excel files do not support the 11.49% Cap Rate."
        })

    report = {
        "analysis_summary": {
            "status": "DATA_MISMATCH",
            "purchase_price": user_expectations["purchase_price"],
            "calculated_metrics": {
                "gross_revenue": t12_data["gross_revenue"],
                "total_expenses": t12_data["total_expenses"],
                "noi": t12_data["noi"],
                "cap_rate_percent": t12_data["cap_rate"]
            },
            "rent_roll_metrics": {
                "annualized_actual": rent_roll_data["annualized_actual_rent"],
                "annualized_market": rent_roll_data["annualized_market_rent"]
            },
            "expected_metrics_from_feedback": {
                "gross_revenue": user_expectations["gross_potential_rent"],
                "noi": user_expectations["noi"],
                "cap_rate_percent": user_expectations["cap_rate"]
            }
        },
        "flags": flags
    }

    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    generate_report()