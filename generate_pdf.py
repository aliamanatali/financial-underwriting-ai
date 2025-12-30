from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Valiance Capital - Underwriting Test Data', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 10, title, 0, 1, 'L', 1)
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 10, body)
        self.ln()

def create_sample_pdf():
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # --- Section 1: Deal Parameters ---
    pdf.chapter_title("1. Deal Parameters / Property Info")
    
    params = [
        ("Property Name", "Keystone Apartments"),
        ("Address", "123 Main St, Berkeley, CA 94704"),
        ("Number of Units", "50"),
        ("Year Built", "1985"),
        ("Year Renovated", "N/A"),
        ("Loan Amount", "$10,000,000"),
        ("Ask Price", "$12,500,000")
    ]
    
    pdf.set_font("Arial", size=10)
    for key, value in params:
        pdf.cell(50, 8, key + ":", 0, 0)
        pdf.cell(0, 8, value, 0, 1)
    pdf.ln(5)

    # --- Section 2: T12 Financials ---
    pdf.chapter_title("2. T12 (Trailing 12 Months) Financial Statement")
    
    # Header
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(100, 8, "Line Item", 1)
    pdf.cell(50, 8, "Amount (Annual)", 1)
    pdf.ln()
    
    # Data
    financials = [
        ("INCOME", ""),
        ("Gross Potential Rent", "$1,200,000"),
        ("Vacancy Loss", "($60,000)"),
        ("Concessions", "($10,000)"),
        ("Other Income (Laundry/Parking)", "$15,000"),
        ("Total Effective Income", "$1,145,000"),
        ("", ""), # Spacer
        ("EXPENSES", ""),
        ("Property Taxes", "$120,000"),
        ("Insurance", "$30,000"),
        ("Repairs & Maintenance", "$50,000"),
        ("Management Fees", "$40,000"),
        ("Utilities - Water/Sewer", "$15,000"),
        ("Utilities - Gas/Electric", "$10,000"),
        ("Payroll", "$35,000"),
        ("Marketing & Admin", "$13,000"),
        ("Total Operating Expenses", "$313,000"),
        ("", ""), # Spacer
        ("NET OPERATING INCOME (NOI)", "$832,000"),
    ]

    pdf.set_font("Arial", size=10)
    for item, amount in financials:
        if item in ["INCOME", "EXPENSES", "NET OPERATING INCOME (NOI)"]:
            pdf.set_font("Arial", 'B', 10) # Bold for headers
        else:
            pdf.set_font("Arial", '', 10)
            
        pdf.cell(100, 8, item, 1)
        pdf.cell(50, 8, amount, 1)
        pdf.ln()
    pdf.ln(5)

    # --- Section 3: Rent Roll ---
    pdf.chapter_title("3. Rent Roll (Sample - 5 Units)")
    
    # Header
    pdf.set_font("Arial", 'B', 9)
    col_widths = [20, 30, 50, 25, 30, 30]
    headers = ["Unit", "Type", "Tenant", "Rent", "Start", "End"]
    
    for i in range(len(headers)):
        pdf.cell(col_widths[i], 8, headers[i], 1)
    pdf.ln()
    
    # Data
    rent_roll_data = [
        ("101", "1BR/1BA", "John Doe", "$2,000", "2024-01-01", "2024-12-31"),
        ("102", "2BR/2BA", "Jane Smith", "$2,500", "2024-03-15", "2025-03-14"),
        ("103", "1BR/1BA", "Mike Johnson", "$1,950", "2023-11-01", "2024-10-31"),
        ("104", "2BR/2BA", "Emily Davis", "$2,600", "2024-06-01", "2025-05-31"),
        ("105", "Studio", "Vacant", "$0", "N/A", "N/A"),
    ]

    pdf.set_font("Arial", size=9)
    for row in rent_roll_data:
        for i in range(len(row)):
            pdf.cell(col_widths[i], 8, row[i], 1)
        pdf.ln()

    # Save
    pdf.output("sample_financial_data.pdf")
    print("PDF generated successfully: sample_financial_data.pdf")

if __name__ == '__main__':
    create_sample_pdf()
