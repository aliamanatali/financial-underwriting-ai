def generate_dd_report():
    data = [
        {
            "item": "Property Address",
            "value": "2715 Dwight Way, Berkeley, CA",
            "source": "DD INTERNAL/Reports/PRELIM-LINKED 10-30-23.PDF"
        },
        {
            "item": "APN",
            "value": "055-1867-010-00",
            "source": "DD INTERNAL/Reports/PRELIM-LINKED 10-30-23.PDF"
        },
        {
            "item": "Owner (Vesting)",
            "value": "Hoh Chuen Hwa Hao, a Widow",
            "source": "DD INTERNAL/Reports/PRELIM-LINKED 10-30-23.PDF"
        },
        {
            "item": "Land Value",
            "value": "$310,253.00",
            "source": "DD INTERNAL/Reports/PRELIM-LINKED 10-30-23.PDF"
        },
        {
            "item": "Improvements Value",
            "value": "$1,241,612.00",
            "source": "DD INTERNAL/Reports/PRELIM-LINKED 10-30-23.PDF"
        },
        {
            "item": "Personal Property Value",
            "value": "$12,672.00",
            "source": "DD INTERNAL/Reports/PRELIM-LINKED 10-30-23.PDF"
        },
        {
            "item": "Total Assessed Value",
            "value": "$1,564,537.00", # Land + Improvements + Personal Property
            "source": "DD INTERNAL/Reports/PRELIM-LINKED 10-30-23.PDF"
        },
        {
            "item": "Property Tax (1st Installment)",
            "value": "$25,285.96",
            "source": "DD INTERNAL/Reports/PRELIM-LINKED 10-30-23.PDF"
        },
        {
            "item": "Property Tax (2nd Installment)",
            "value": "$25,285.96",
            "source": "DD INTERNAL/Reports/PRELIM-LINKED 10-30-23.PDF"
        },
        {
            "item": "Total Annual Property Tax",
            "value": "$50,571.92",
            "source": "DD INTERNAL/Reports/PRELIM-LINKED 10-30-23.PDF"
        },
        {
            "item": "Deed of Trust Amount",
            "value": "$1,800,000.00",
            "source": "DD INTERNAL/Reports/PRELIM-LINKED 10-30-23.PDF"
        },
        {
            "item": "Deed of Trust Date",
            "value": "June 7, 2004",
            "source": "DD INTERNAL/Reports/PRELIM-LINKED 10-30-23.PDF"
        },
        {
            "item": "Lender / Beneficiary",
            "value": "World Savings Bank, FSB",
            "source": "DD INTERNAL/Reports/PRELIM-LINKED 10-30-23.PDF"
        },
        {
            "item": "Special Tax (CFD A/C-3)",
            "value": "East Bay Regional Park District",
            "source": "DD INTERNAL/Reports/PRELIM-LINKED 10-30-23.PDF"
        },
        {
            "item": "Special Tax (CFD 2014-1)",
            "value": "County of Alameda California Home Finance Authority (Clean Energy)",
            "source": "DD INTERNAL/Title/PRELIM-LINKED[37].PDF"
        }
    ]

    print("\nFINANCIAL REPORT FROM DD INTERNAL DOCUMENTS")
    print("===========================================")
    print(f"{'ITEM':<35} ; {'VALUE':<65} : {'SOURCE FILE'}")
    print("-" * 130)
    
    for entry in data:
        print(f"{entry['item']:<35} ; {entry['value']:<65} : {entry['source']}")

if __name__ == "__main__":
    generate_dd_report()