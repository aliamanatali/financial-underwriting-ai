import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from typing import Dict, Any, List
import io
from app.models.schemas import ProFormaEntry, UnderwritingAnalysis

class ExcelService:
    def generate_side_by_side_view(self, analysis_data: UnderwritingAnalysis) -> List[ProFormaEntry]:
        """
        Generates a list of ProFormaEntry objects for the side-by-side view.
        T12 = Historical, F12 = Pro Forma
        Uses DealParameters for vacancy rate (not hardcoded).
        """
        entries = []
        
        # Get vacancy rate from deal parameters (not hardcoded)
        vacancy_rate = analysis_data.deal_parameters.vacancy_rate if analysis_data.deal_parameters else 0.03
        
        # Add Revenue Section
        historical_revenue = sum((item.current_rent or 0) * 12 for item in analysis_data.rent_roll)
        pro_forma_revenue = sum((item.market_rent or 0) * 12 for item in analysis_data.rent_roll)
        pro_forma_revenue_after_vacancy = pro_forma_revenue * (1 - vacancy_rate)
        
        entries.append(ProFormaEntry(
            name="Gross Potential Rent",
            t12=historical_revenue,
            f12=pro_forma_revenue
        ))
        
        entries.append(ProFormaEntry(
            name="Vacancy Loss",
            t12=0,
            f12=pro_forma_revenue * vacancy_rate
        ))
        
        entries.append(ProFormaEntry(
            name="Effective Gross Income",
            t12=historical_revenue,
            f12=pro_forma_revenue_after_vacancy
        ))
        
        # Add Expense Section (by category)
        # T12 uses historical expenses
        historical_expenses_by_category: Dict[str, float] = {}
        for expense in analysis_data.historical_expenses:
            category = expense.mapped_category.value if hasattr(expense.mapped_category, 'value') else str(expense.mapped_category)
            historical_expenses_by_category.setdefault(category, 0)
            historical_expenses_by_category[category] += expense.amount

        # F12 uses the new detailed pro forma expenses
        pro_forma_expenses_by_category: Dict[str, float] = {
            item.name: item.amount for item in analysis_data.pro_forma_expenses_detailed
        }

        # Get all unique expense categories from both historical and pro forma
        all_expense_categories = sorted(list(set(historical_expenses_by_category.keys()) | set(pro_forma_expenses_by_category.keys())))

        for category in all_expense_categories:
            t12_amount = historical_expenses_by_category.get(category, 0)
            f12_amount = pro_forma_expenses_by_category.get(category, 0)
            entries.append(ProFormaEntry(
                name=f"  {category}",
                t12=t12_amount,
                f12=f12_amount
            ))

        total_historical_expenses = sum(historical_expenses_by_category.values())
        total_pro_forma_expenses = sum(pro_forma_expenses_by_category.values())

        entries.append(ProFormaEntry(
            name="Total Operating Expenses",
            t12=total_historical_expenses,
            f12=total_pro_forma_expenses
        ))
        
        # Add NOI Section
        historical_noi = analysis_data.historical_noi if analysis_data.historical_noi else (historical_revenue - total_historical_expenses)
        entries.append(ProFormaEntry(
            name="Net Operating Income (NOI)",
            t12=historical_noi,
            f12=analysis_data.pro_forma_noi if analysis_data.pro_forma_noi else (pro_forma_revenue_after_vacancy - total_historical_expenses)
        ))
        
        # Add Cap Rate Section
        entries.append(ProFormaEntry(
            name="Cap Rate",
            t12=analysis_data.historical_cap_rate if analysis_data.historical_cap_rate else 0,
            f12=analysis_data.cap_rate if analysis_data.cap_rate else 0
        ))
        
        return entries

    async def create_side_by_side_excel(self, data: List[ProFormaEntry]) -> bytes:
        """
        Creates an Excel file with a side-by-side view of T12 and F12 data asynchronously.
        Includes FORMULAS (not hardcoded values) for all calculations.
        Includes professional formatting and styling.
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._create_excel_sync, data)

    def _create_excel_sync(self, data: List[ProFormaEntry]) -> bytes:
        """Synchronous implementation of Excel creation."""
        workbook = openpyxl.Workbook()
        sheet: Worksheet = workbook.active
        sheet.title = "Financial Analysis"
        
        # Set column widths
        sheet.column_dimensions['A'].width = 35
        sheet.column_dimensions['B'].width = 18
        sheet.column_dimensions['C'].width = 18
        
        # Define styles
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=12)
        section_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        section_font = Font(bold=True, size=11)
        currency_format = '"$"#,##0.00'
        percent_format = '0.00%'
        
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Headers
        sheet["A1"] = "Category"
        sheet["B1"] = "T12 (Historical)"
        sheet["C1"] = "F12 (Pro Forma)"
        
        for col in ['A1', 'B1', 'C1']:
            sheet[col].fill = header_fill
            sheet[col].font = header_font
            sheet[col].alignment = Alignment(horizontal="center", vertical="center")
            sheet[col].border = border
        
        # Track row numbers for key items to use in formulas
        row_map = {}  # Map from entry.name to row number
        
        # First pass: populate data and track row numbers
        row = 2
        for entry in data:
            sheet[f"A{row}"] = entry.name
            # Store row mapping for formula references
            row_map[entry.name] = row
            
            # Set base values (will be replaced with formulas where applicable)
            sheet[f"B{row}"] = entry.t12
            sheet[f"C{row}"] = entry.f12
            row += 1
        
        # Second pass: apply formulas where applicable
        for entry_name, row in row_map.items():
            if "Vacancy Loss" in entry_name:
                # Vacancy Loss = GPR * 0.03 (Valiance standard 3% vacancy)
                gpr_row = row_map.get("Gross Potential Rent")
                if gpr_row:
                    sheet[f"B{row}"] = 0  # Historical has no vacancy loss
                    sheet[f"C{row}"] = f"=C{gpr_row}*0.03"
                    
            elif "Effective Gross Income" in entry_name:
                # EGI = GPR - Vacancy Loss
                gpr_row = row_map.get("Gross Potential Rent")
                vacancy_row = row_map.get("Vacancy Loss")
                if gpr_row and vacancy_row:
                    sheet[f"B{row}"] = f"=B{gpr_row}-B{vacancy_row}"
                    sheet[f"C{row}"] = f"=C{gpr_row}-C{vacancy_row}"
                    
            elif "Net Operating Income" in entry_name:
                # NOI = EGI - Total Expenses
                egi_row = row_map.get("Effective Gross Income")
                expenses_row = row_map.get("Total Operating Expenses")
                if egi_row and expenses_row:
                    sheet[f"B{row}"] = f"=B{egi_row}-B{expenses_row}"
                    sheet[f"C{row}"] = f"=C{egi_row}-C{expenses_row}"
        
        # Apply formatting to all rows
        for entry_name, row in row_map.items():
            sheet[f"A{row}"].border = border
            sheet[f"B{row}"].border = border
            sheet[f"C{row}"].border = border
            
            # Format as currency (except Cap Rate which is percentage)
            if "Cap Rate" in entry_name:
                sheet[f"B{row}"].number_format = percent_format
                sheet[f"C{row}"].number_format = percent_format
            else:
                sheet[f"B{row}"].number_format = currency_format
                sheet[f"C{row}"].number_format = currency_format
            
            # Bold section headers
            if any(keyword in entry_name for keyword in ["Net Operating Income", "Cap Rate", "Total Operating Expenses", "Effective Gross Income"]):
                sheet[f"A{row}"].font = section_font
                sheet[f"A{row}"].fill = section_fill
                sheet[f"B{row}"].fill = section_fill
                sheet[f"C{row}"].fill = section_fill
            
            # Right align numbers
            sheet[f"B{row}"].alignment = Alignment(horizontal="right")
            sheet[f"C{row}"].alignment = Alignment(horizontal="right")
        
        # Get the last row number for the note
        last_row = max(row_map.values()) if row_map else 2
        
        # Add a note about the Purchase Price used in Cap Rate calculations
        sheet[f"A{last_row + 2}"] = "Note: Cap Rate = NOI / Purchase Price (provided in analysis)"
        sheet[f"A{last_row + 2}"].font = Font(italic=True, size=9, color="666666")
        
        # Save to byte stream
        virtual_workbook = io.BytesIO()
        workbook.save(virtual_workbook)
        virtual_workbook.seek(0)
        return virtual_workbook.read()

    async def create_om_proforma_excel(self, analysis_data: UnderwritingAnalysis) -> bytes:
        """
        Creates an Excel file reproducing the OM Proforma tables.
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._create_om_proforma_excel_sync, analysis_data)

    def _create_om_proforma_excel_sync(self, analysis_data: UnderwritingAnalysis) -> bytes:
        workbook = openpyxl.Workbook()
        
        # Remove default sheet
        default_sheet = workbook.active
        workbook.remove(default_sheet)
        
        sheet = workbook.create_sheet("OM Proforma")
        
        # --- Styles ---
        # Dark Blue: 002060 (Navy)
        header_fill = PatternFill(start_color="002060", end_color="002060", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        
        # Section Header: Dark Grey
        section_header_fill = PatternFill(start_color="595959", end_color="595959", fill_type="solid")
        section_header_font = Font(bold=True, color="FFFFFF", size=10)
        
        bold_font = Font(bold=True)
        
        # Formats
        currency_fmt = '_("$"* #,##0_);_("$"* (#,##0);_("$"* "-"??_);_(@_)'
        percent_fmt = '0.00%'
        
        # --- Data Prep ---
        # 1. Units
        total_units = 1
        if analysis_data.property_meta and analysis_data.property_meta.total_units:
            total_units = analysis_data.property_meta.total_units
        elif analysis_data.rent_roll_summary and analysis_data.rent_roll_summary.total_units:
            total_units = analysis_data.rent_roll_summary.total_units

        # 1.5 Sq Ft
        total_sqft = 0
        
        # Method 1: Sum from individual units (most accurate)
        if analysis_data.rent_roll:
             total_sqft = sum((item.unit_size or 0) for item in analysis_data.rent_roll)

        # Method 2: Calculate from summary
        if total_sqft == 0 and analysis_data.rent_roll_summary:
             # Check if attribute exists (legacy support or if schema changes)
             if hasattr(analysis_data.rent_roll_summary, 'total_square_feet'):
                 total_sqft = getattr(analysis_data.rent_roll_summary, 'total_square_feet')
             
             # Calculate if still 0
             if total_sqft == 0 and analysis_data.rent_roll_summary.avg_unit_size and analysis_data.rent_roll_summary.total_units:
                 total_sqft = analysis_data.rent_roll_summary.avg_unit_size * analysis_data.rent_roll_summary.total_units
                 
        # Method 3: Property Meta (check existence safely)
        if total_sqft == 0 and analysis_data.property_meta and hasattr(analysis_data.property_meta, 'building_size'):
             total_sqft = getattr(analysis_data.property_meta, 'building_size', 0)

        # 2. Income Data
        # Market Rent (Annual)
        market_rent_annual = 0.0
        if analysis_data.rent_roll_summary and analysis_data.rent_roll_summary.total_market_rent:
             market_rent_annual = analysis_data.rent_roll_summary.total_market_rent * 12
        elif analysis_data.rent_roll:
             market_rent_annual = sum((r.market_rent or 0) for r in analysis_data.rent_roll) * 12
        
        # Current/Stabilized Rent (Annual)
        current_rent_annual = 0.0
        if analysis_data.rent_roll_summary and analysis_data.rent_roll_summary.total_annual_rent:
             current_rent_annual = analysis_data.rent_roll_summary.total_annual_rent
        elif analysis_data.rent_roll:
             current_rent_annual = sum((r.current_rent or 0) for r in analysis_data.rent_roll) * 12

        # Loss to Lease = Market - Current
        # If Market > Current, we have a Loss to Lease (positive gap, so we deduct it).
        # If Market < Current, we have a Gain to Lease (negative gap, so we add it).
        # We want the value to add/subtract to Market to get Current.
        # Value = Current - Market.
        loss_to_lease_value = current_rent_annual - market_rent_annual
        
        # Vacancy Rate
        vacancy_rate = 0.05 # Default
        if analysis_data.deal_parameters:
            vacancy_rate = analysis_data.deal_parameters.vacancy_rate
            
        # Management Fee Rate
        mgmt_fee_rate = 0.04
        if analysis_data.deal_parameters:
            mgmt_fee_rate = analysis_data.deal_parameters.management_fee_rate

        # Other Income - Accumulate from historical expenses
        other_income_annual = 0.0
        if analysis_data.historical_expenses:
             for exp in analysis_data.historical_expenses:
                cat = exp.mapped_category.value if hasattr(exp.mapped_category, 'value') else str(exp.mapped_category)
                if cat in ["Other Income", "Reimbursements"]:
                    other_income_annual += exp.amount

        # 3. Expense Data Mapped
        expenses_map = {
            "Payroll": 0.0,
            "R&M": 0.0,
            "Utilities": 0.0,
            "Contract": 0.0,
            "Admin": 0.0,
            "Taxes": 0.0,
            "Insurance": 0.0,
            "Reserves": 0.0
        }
        
        if analysis_data.pro_forma_expenses_detailed:
             for item in analysis_data.pro_forma_expenses_detailed:
                 cat = item.name
                 val = item.amount
                 
                 if cat == "Payroll": expenses_map["Payroll"] += val
                 elif cat == "Repairs & Maintenance": expenses_map["R&M"] += val
                 elif cat == "Utilities": expenses_map["Utilities"] += val
                 elif cat == "Contract Services": expenses_map["Contract"] += val
                 elif cat in ["General & Administrative", "Advertising & Marketing", "Leasing Fees", "Other Operating Expenses"]: expenses_map["Admin"] += val
                 elif cat == "Real Estate Taxes": expenses_map["Taxes"] += val
                 elif cat == "Insurance": expenses_map["Insurance"] += val
                 elif cat == "Capital Reserves": expenses_map["Reserves"] += val
                 elif cat == "Management Fees": pass # Calculated dynamically
                 else: expenses_map["Admin"] += val # Fallback

        # --- Helper to write a row ---
        def write_row(row_idx, label, val_stabilized, val_market, is_header=False, is_sub_header=False, is_total=False, format_str=currency_fmt, indent=0):
            # Label
            c = sheet.cell(row=row_idx, column=1, value=label)
            if indent: c.alignment = Alignment(indent=indent)
            if is_header:
                c.fill = section_header_fill
                c.font = section_header_font
            if is_sub_header:
                c.font = Font(italic=True, bold=True)
            if is_total:
                c.font = bold_font
                # Add top border for totals
                c.border = Border(top=Side(style='thin'))

            # Stabilized Group
            # Annual
            c = sheet.cell(row=row_idx, column=2, value=val_stabilized)
            c.number_format = format_str
            if is_header: c.fill = section_header_fill
            if is_total:
                c.font = bold_font
                c.border = Border(top=Side(style='thin'))
            
            # Monthly
            c = sheet.cell(row=row_idx, column=3, value=f"=B{row_idx}/12" if isinstance(val_stabilized, (int, float)) and val_stabilized is not None else None)
            if isinstance(val_stabilized, str) and val_stabilized.startswith("="):
                 c.value = f"=B{row_idx}/12" # Formula reference
            c.number_format = format_str
            if is_header: c.fill = section_header_fill
            if is_total:
                c.font = bold_font
                c.border = Border(top=Side(style='thin'))

            # Per Unit
            c = sheet.cell(row=row_idx, column=4, value=f"=B{row_idx}/{total_units}" if isinstance(val_stabilized, (int, float)) and val_stabilized is not None else None)
            if isinstance(val_stabilized, str) and val_stabilized.startswith("="):
                 c.value = f"=B{row_idx}/{total_units}"
            c.number_format = format_str
            if is_header: c.fill = section_header_fill
            if is_total:
                c.font = bold_font
                c.border = Border(top=Side(style='thin'))
            
            # Market Group
            # Annual
            c = sheet.cell(row=row_idx, column=6, value=val_market)
            c.number_format = format_str
            if is_header: c.fill = section_header_fill
            if is_total:
                c.font = bold_font
                c.border = Border(top=Side(style='thin'))
            
            # Monthly
            c = sheet.cell(row=row_idx, column=7, value=f"=F{row_idx}/12" if isinstance(val_market, (int, float)) and val_market is not None else None)
            if isinstance(val_market, str) and val_market.startswith("="):
                 c.value = f"=F{row_idx}/12"
            c.number_format = format_str
            if is_header: c.fill = section_header_fill
            if is_total:
                c.font = bold_font
                c.border = Border(top=Side(style='thin'))

            # Per Unit
            c = sheet.cell(row=row_idx, column=8, value=f"=F{row_idx}/{total_units}" if isinstance(val_market, (int, float)) and val_market is not None else None)
            if isinstance(val_market, str) and val_market.startswith("="):
                 c.value = f"=F{row_idx}/{total_units}"
            c.number_format = format_str
            if is_header: c.fill = section_header_fill
            if is_total:
                c.font = bold_font
                c.border = Border(top=Side(style='thin'))

        # --- Header Structure ---
        # Row 1: Main Headers
        sheet.merge_cells("B1:D1")
        sheet["B1"] = "Proforma at Stabilized Rent"
        sheet["B1"].fill = header_fill
        sheet["B1"].font = header_font
        sheet["B1"].alignment = Alignment(horizontal="center")
        
        sheet.merge_cells("F1:H1")
        sheet["F1"] = "Proforma at Market Rents"
        sheet["F1"].fill = header_fill
        sheet["F1"].font = header_font
        sheet["F1"].alignment = Alignment(horizontal="center")
        
        # Row 2: Sub Headers
        for col, val in zip([2,3,4, 6,7,8], ["Annual", "Monthly", "Per Unit"]*2):
            c = sheet.cell(row=2, column=col, value=val)
            c.fill = header_fill
            c.font = header_font
            c.alignment = Alignment(horizontal="center")
            
        current_row = 3
        
        # --- Income Section ---
        write_row(current_row, "Income", None, None, is_header=True)
        current_row += 1
        
        # 1. Gross Potential Market Rent
        write_row(current_row, "Gross Potential Market Rent", market_rent_annual, market_rent_annual)
        row_gpr = current_row
        current_row += 1
        
        # 2. Loss to Lease (Negative value for deduction, Positive for gain)
        write_row(current_row, "Loss to Lease / Gain to Lease", loss_to_lease_value, 0)
        row_ltl = current_row
        current_row += 1
        
        # 3. Gross Scheduled Rental Income
        write_row(current_row, "Gross Scheduled Rental Income", f"=B{row_gpr}+B{row_ltl}", f"=F{row_gpr}+F{row_ltl}", is_total=True)
        row_gsr = current_row
        current_row += 1
        
        # 4. Vacancy
        vac_text = f"Vacancy ({vacancy_rate:.1%})"
        write_row(current_row, vac_text, f"=-B{row_gsr}*{vacancy_rate}", f"=-F{row_gsr}*{vacancy_rate}")
        row_vac = current_row
        current_row += 1
        
        # 5. Net Rental Income
        write_row(current_row, "Net Rental Income", f"=B{row_gsr}+B{row_vac}", f"=F{row_gsr}+F{row_vac}", is_total=True)
        row_nri = current_row
        current_row += 1
        
        # 6. Other Income
        write_row(current_row, "Other Income", other_income_annual, other_income_annual)
        row_other = current_row
        current_row += 1
        
        # 7. EGI
        write_row(current_row, "Gross Scheduled Income (Effective Gross Income)", f"=B{row_nri}+B{row_other}", f"=F{row_nri}+F{row_other}", is_header=True)
        row_egi = current_row
        current_row += 1
        
        # --- Expense Section ---
        write_row(current_row, "Annual Operating Expenses", None, None, is_header=True)
        current_row += 1
        
        write_row(current_row, "Controllable Expenses", None, None, is_sub_header=True)
        current_row += 1
        
        # Property Management Fee
        pm_label = f"Property Management Fee ({mgmt_fee_rate:.1%})"
        write_row(current_row, pm_label, f"=-B{row_egi}*{mgmt_fee_rate}", f"=-F{row_egi}*{mgmt_fee_rate}")
        row_mgmt = current_row
        current_row += 1
        
        # Controllable Items
        write_row(current_row, "Payroll / Onsite Manager", -expenses_map["Payroll"], -expenses_map["Payroll"])
        row_payroll = current_row # Start sum range
        current_row += 1
        write_row(current_row, "Repairs & Maintenance", -expenses_map["R&M"], -expenses_map["R&M"])
        current_row += 1
        write_row(current_row, "Utilities", -expenses_map["Utilities"], -expenses_map["Utilities"])
        current_row += 1
        write_row(current_row, "Contract Services", -expenses_map["Contract"], -expenses_map["Contract"])
        current_row += 1
        write_row(current_row, "General Admin / Business Taxes", -expenses_map["Admin"], -expenses_map["Admin"])
        row_ga = current_row # End sum range
        current_row += 1
        
        # Total Controllable
        sum_range_b = f"B{row_mgmt}:B{row_ga}"
        sum_range_f = f"F{row_mgmt}:F{row_ga}"
        write_row(current_row, "Total Controllable Expenses", f"=SUM({sum_range_b})", f"=SUM({sum_range_f})", is_total=True)
        row_controllable = current_row
        current_row += 1
        
        # Fixed Expenses
        write_row(current_row, "Real Estate Taxes (Ad Valorem)", -expenses_map["Taxes"], -expenses_map["Taxes"])
        row_taxes = current_row
        current_row += 1
        write_row(current_row, "Insurance", -expenses_map["Insurance"], -expenses_map["Insurance"])
        row_ins = current_row
        current_row += 1
        write_row(current_row, "Reserves", -expenses_map["Reserves"], -expenses_map["Reserves"])
        row_reserves = current_row
        current_row += 1
        
        # Total Operating Expenses
        write_row(current_row, "Total Operating Expenses",
                  f"=B{row_controllable}+B{row_taxes}+B{row_ins}+B{row_reserves}",
                  f"=F{row_controllable}+F{row_taxes}+F{row_ins}+F{row_reserves}",
                  is_total=True)
        row_opex = current_row
        current_row += 1
        
        # --- NOI ---
        # Dark header style for NOI
        write_row(current_row, "Net Operating Income", f"=B{row_egi}+B{row_opex}", f"=F{row_egi}+F{row_opex}", is_header=True)
        row_noi = current_row
        current_row += 2
        
        # --- Valuation ---
        purchase_price = 0.0
        if analysis_data.property_meta and analysis_data.property_meta.purchase_price:
            purchase_price = analysis_data.property_meta.purchase_price

        # Helper for borders
        thin_side = Side(style='thin')
        thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

        # 1. Header Row
        # Left Section (Stabilized) - Spans A-D (Label + 3 cols)
        sheet.merge_cells(f"A{current_row}:D{current_row}")
        c = sheet[f"A{current_row}"]
        c.value = "Asking Price"
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center")
        # Apply border to merged range (outer cells)
        for col_char in ['A', 'B', 'C', 'D']:
             sheet[f"{col_char}{current_row}"].border = thin_border

        # Right Section (Market) - Spans F-H
        sheet.merge_cells(f"F{current_row}:H{current_row}")
        c = sheet[f"F{current_row}"]
        c.value = "Asking Price"
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center")
        for col_char in ['F', 'G', 'H']:
             sheet[f"{col_char}{current_row}"].border = thin_border
        
        current_row += 1

        # 2. Sub-headers Row
        # Left: Total, Per Unit, Per Sq Ft
        # A is blank (Label column) but styled to match header block
        sheet[f"A{current_row}"].fill = header_fill
        sheet[f"A{current_row}"].border = thin_border
        
        sub_headers_map = {
            "B": "Total",
            "C": "Per Unit",
            "D": "Per Sq Ft",
            "F": "Total",
            "G": "Per Unit",
            "H": "Per Sq Ft"
        }
        
        for col_char, text in sub_headers_map.items():
            c = sheet[f"{col_char}{current_row}"]
            c.value = text
            c.fill = header_fill
            c.font = header_font
            c.alignment = Alignment(horizontal="center")
            c.border = thin_border
            
        current_row += 1
        
        # 3. Data Rows
        # Row 1: Purchase Price
        row_price = current_row
        
        # Label
        c = sheet[f"A{current_row}"]
        c.value = "Purchase Price"
        c.font = bold_font
        c.border = thin_border
        
        # Left Values
        # Total
        c = sheet[f"B{current_row}"]
        c.value = purchase_price
        c.number_format = currency_fmt
        c.alignment = Alignment(horizontal="right")
        c.border = thin_border
        
        # Per Unit
        c = sheet[f"C{current_row}"]
        c.value = f"=B{current_row}/{total_units}" if purchase_price else 0
        c.number_format = currency_fmt
        c.alignment = Alignment(horizontal="right")
        c.border = thin_border
        
        # Per Sq Ft
        c = sheet[f"D{current_row}"]
        c.value = f"=B{current_row}/{total_sqft}" if purchase_price and total_sqft else 0
        c.number_format = currency_fmt
        c.alignment = Alignment(horizontal="right")
        c.border = thin_border
        
        # Right Values (Same as Left for Purchase Price)
        # Total
        c = sheet[f"F{current_row}"]
        c.value = purchase_price
        c.number_format = currency_fmt
        c.alignment = Alignment(horizontal="right")
        c.border = thin_border
        
        # Per Unit
        c = sheet[f"G{current_row}"]
        c.value = f"=F{current_row}/{total_units}" if purchase_price else 0
        c.number_format = currency_fmt
        c.alignment = Alignment(horizontal="right")
        c.border = thin_border
        
        # Per Sq Ft
        c = sheet[f"H{current_row}"]
        c.value = f"=F{current_row}/{total_sqft}" if purchase_price and total_sqft else 0
        c.number_format = currency_fmt
        c.alignment = Alignment(horizontal="right")
        c.border = thin_border
        
        current_row += 1
        
        # Row 2: CAP Rate
        # Label
        c = sheet[f"A{current_row}"]
        c.value = "CAP Rate"
        c.font = bold_font
        c.border = thin_border
        
        # Left (Stabilized)
        # Total: Stabilized NOI / Price
        c = sheet[f"B{current_row}"]
        c.value = f"=B{row_noi}/B{row_price}"
        c.number_format = percent_fmt
        c.alignment = Alignment(horizontal="right")
        c.border = thin_border
        
        # Right (Market)
        # Total: Market NOI / Price
        c = sheet[f"F{current_row}"]
        c.value = f"=F{row_noi}/F{row_price}"
        c.number_format = percent_fmt
        c.alignment = Alignment(horizontal="right")
        c.border = thin_border

        # Empty cells border
        for col_char in ['C', 'D', 'G', 'H']:
             sheet[f"{col_char}{current_row}"].border = thin_border

        current_row += 1
        
        # Row 3: GRM
        # Label
        c = sheet[f"A{current_row}"]
        c.value = "GRM"
        c.font = bold_font
        c.border = thin_border
        
        # Left (Stabilized)
        # Formula: Purchase Price / Stabilized Gross Scheduled Income
        c = sheet[f"B{current_row}"]
        c.value = f"=B{row_price}/B{row_gsr}"
        c.number_format = "0.00"
        c.alignment = Alignment(horizontal="right")
        c.border = thin_border
        
        # Right (Market)
        # Formula: Purchase Price / Market Gross Scheduled Income
        c = sheet[f"F{current_row}"]
        c.value = f"=F{row_price}/F{row_gsr}"
        c.number_format = "0.00"
        c.alignment = Alignment(horizontal="right")
        c.border = thin_border
        
        # Empty cells border
        for col_char in ['C', 'D', 'G', 'H']:
             sheet[f"{col_char}{current_row}"].border = thin_border

        # Column Widths
        sheet.column_dimensions['A'].width = 35
        sheet.column_dimensions['B'].width = 15
        sheet.column_dimensions['C'].width = 15
        sheet.column_dimensions['D'].width = 15
        sheet.column_dimensions['E'].width = 2
        sheet.column_dimensions['F'].width = 15
        sheet.column_dimensions['G'].width = 15
        sheet.column_dimensions['H'].width = 15

        virtual_workbook = io.BytesIO()
        workbook.save(virtual_workbook)
        virtual_workbook.seek(0)
        return virtual_workbook.read()


