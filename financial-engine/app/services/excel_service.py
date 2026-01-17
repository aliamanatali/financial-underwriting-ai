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

    async def create_rent_roll_excel(self, analysis_data: UnderwritingAnalysis) -> bytes:
        """
        Creates an Excel file with the Rent Roll detail and summary.
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._create_rent_roll_excel_sync, analysis_data)

    def _create_rent_roll_excel_sync(self, analysis_data: UnderwritingAnalysis) -> bytes:
        workbook = openpyxl.Workbook()
        
        # Remove default sheet
        default_sheet = workbook.active
        workbook.remove(default_sheet)
        
        # --- Sheet 1: Rent Roll Detail & Summary ---
        sheet = workbook.create_sheet("Rent Roll")
        
        # Styles
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        section_header_fill = PatternFill(start_color="595959", end_color="595959", fill_type="solid")
        section_header_font = Font(bold=True, color="FFFFFF", size=11)
        
        currency_fmt = '_("$"* #,##0_);_("$"* (#,##0);_("$"* "-"??_);_(@_)'
        percent_format = '0.00%'
        
        # --- Part 1: Detailed Rent Roll ---
        sheet["A1"] = "Detailed Rent Roll"
        sheet["A1"].font = Font(bold=True, size=14)
        
        # Headers
        headers = [
            "Unit #", "Unit Size", "Unit Type",
            "Current Rent", "Stabilized Rent", "Market Rent",
            "Move-In Date", "Lease Start", "Lease End"
        ]
        
        start_row = 3
        for col_idx, header in enumerate(headers, 1):
            cell = sheet.cell(row=start_row, column=col_idx, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
            
        # Data
        row_idx = start_row + 1
        for item in analysis_data.rent_roll:
            sheet.cell(row=row_idx, column=1, value=item.unit_number)
            sheet.cell(row=row_idx, column=2, value=item.unit_size)
            sheet.cell(row=row_idx, column=3, value=item.unit_type)
            # Removed Tenant Name (Column 4)
            
            c = sheet.cell(row=row_idx, column=4, value=item.current_rent)
            c.number_format = currency_fmt
            
            c = sheet.cell(row=row_idx, column=5, value=item.stabilized_rent)
            c.number_format = currency_fmt
            
            c = sheet.cell(row=row_idx, column=6, value=item.market_rent)
            c.number_format = currency_fmt
            
            sheet.cell(row=row_idx, column=7, value=item.move_in_date)
            sheet.cell(row=row_idx, column=8, value=item.lease_start)
            sheet.cell(row=row_idx, column=9, value=item.lease_end)
            
            row_idx += 1
            
        # Column Widths
        sheet.column_dimensions['A'].width = 12
        sheet.column_dimensions['B'].width = 12
        sheet.column_dimensions['C'].width = 15
        sheet.column_dimensions['D'].width = 15
        sheet.column_dimensions['E'].width = 15
        sheet.column_dimensions['F'].width = 15
        sheet.column_dimensions['G'].width = 15
        sheet.column_dimensions['H'].width = 15
        sheet.column_dimensions['I'].width = 15

        # --- Part 2: Summaries (Using Formulas) ---
        if analysis_data.rent_roll_summary:
            current_row = row_idx + 3 # Spacer
            
            sheet[f"A{current_row}"] = "Rent Roll Summary"
            sheet[f"A{current_row}"].font = Font(bold=True, size=14)
            current_row += 2

            # Define data ranges (Adjusted for removed column)
            # Data starts at row 4 (start_row + 1)
            # Ends at row_idx - 1
            last_data_row = row_idx - 1
            r_unit_no = f"$A$4:$A${last_data_row}"
            r_size = f"$B$4:$B${last_data_row}"
            r_type = f"$C$4:$C${last_data_row}"
            r_curr = f"$D$4:$D${last_data_row}"
            r_stab = f"$E$4:$E${last_data_row}"
            r_mkt = f"$F$4:$F${last_data_row}"

            # --- Section 2.1: High Level Metrics ---
            summary_headers = ["Metric", "Value"]
            
            # Header
            cell = sheet.cell(row=current_row, column=1, value="Metric")
            cell.fill = section_header_fill
            cell.font = section_header_font
            
            cell = sheet.cell(row=current_row, column=2, value="Value")
            cell.fill = section_header_fill
            cell.font = section_header_font
            
            current_row += 1
            
            # 1. Total Units
            sheet.cell(row=current_row, column=1, value="Total Units")
            sheet.cell(row=current_row, column=2, value=f"=COUNTA({r_unit_no})").number_format = "0"
            row_total_units = current_row
            current_row += 1
            
            # 2. Occupied Units
            sheet.cell(row=current_row, column=1, value="Occupied Units")
            sheet.cell(row=current_row, column=2, value=f"=COUNTIF({r_curr}, \">0\")").number_format = "0"
            row_occupied = current_row
            current_row += 1
            
            # 3. Occupancy Rate
            sheet.cell(row=current_row, column=1, value="Occupancy Rate")
            sheet.cell(row=current_row, column=2, value=f"=B{row_occupied}/B{row_total_units}").number_format = percent_format
            current_row += 1
            
            # 4. Avg Unit Size
            sheet.cell(row=current_row, column=1, value="Avg Unit Size")
            sheet.cell(row=current_row, column=2, value=f"=AVERAGE({r_size})").number_format = "0"
            current_row += 1
            
            # 5. Total Monthly Rent
            sheet.cell(row=current_row, column=1, value="Total Monthly Rent")
            sheet.cell(row=current_row, column=2, value=f"=SUM({r_curr})").number_format = currency_fmt
            row_monthly_rent = current_row
            current_row += 1
            
            # 6. Total Annual Rent
            sheet.cell(row=current_row, column=1, value="Total Annual Rent")
            sheet.cell(row=current_row, column=2, value=f"=B{row_monthly_rent}*12").number_format = currency_fmt
            current_row += 1
            
            # 7. Avg Rent per Unit (Occupied)
            sheet.cell(row=current_row, column=1, value="Avg Rent per Unit (Occupied)")
            sheet.cell(row=current_row, column=2, value=f"=B{row_monthly_rent}/B{row_occupied}").number_format = currency_fmt
            current_row += 1
            
            # 8. Avg Rent per SF (Using Paying Unit Size only to be accurate, but complexity of SUMIFs)
            # Simplification: Total Rent / Total Occupied SF
            # Formula: SUM(Current Rent) / SUMIF(Current Rent, >0, Unit Size)
            sheet.cell(row=current_row, column=1, value="Avg Rent per SF")
            sheet.cell(row=current_row, column=2, value=f"=B{row_monthly_rent}/SUMIF({r_curr}, \">0\", {r_size})").number_format = currency_fmt
            current_row += 1
            
            current_row += 2 # Spacer

            # --- Section 2.2: Unit Mix Detailed Summary ---
            sheet[f"A{current_row}"] = "Unit Mix Analysis"
            sheet[f"A{current_row}"].font = Font(bold=True, size=12)
            current_row += 1

            # Headers for Unit Mix
            mix_headers = ["Unit Mix", "Unit Count", "% of Total", "Avg Current Rent", "Avg Stabilized Rent", "Avg Market Rent", "Avg Sq Ft"]
            for col_idx, header in enumerate(mix_headers, 1):
                cell = sheet.cell(row=current_row, column=col_idx, value=header)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")
            
            current_row += 1
            start_mix_row = current_row
            
            # Identify Unique Unit Types for the rows
            # We still need Python to identify the unique types to generate the rows,
            # but the values will be formulas.
            unique_types = sorted(list(set([item.unit_type or "Unknown" for item in analysis_data.rent_roll])))
            
            for u_type in unique_types:
                # We need to escape double quotes in the formula string
                safe_type = u_type.replace('"', '""')
                
                # Unit Mix Name
                sheet.cell(row=current_row, column=1, value=u_type)
                
                # Count: =COUNTIF(Range, "Type")
                sheet.cell(row=current_row, column=2, value=f"=COUNTIF({r_type}, \"{safe_type}\")").number_format = "0"
                
                # % of Total: =B{current}/COUNTA(Range)
                sheet.cell(row=current_row, column=3, value=f"=B{current_row}/COUNTA({r_unit_no})").number_format = percent_format
                
                # Avg Current Rent: =AVERAGEIF(Range, "Type", RentRange)
                sheet.cell(row=current_row, column=4, value=f"=IFERROR(AVERAGEIF({r_type}, \"{safe_type}\", {r_curr}), 0)").number_format = currency_fmt
                
                # Avg Stabilized Rent
                sheet.cell(row=current_row, column=5, value=f"=IFERROR(AVERAGEIF({r_type}, \"{safe_type}\", {r_stab}), 0)").number_format = currency_fmt
                
                # Avg Market Rent
                sheet.cell(row=current_row, column=6, value=f"=IFERROR(AVERAGEIF({r_type}, \"{safe_type}\", {r_mkt}), 0)").number_format = currency_fmt
                
                # Avg Sq Ft
                sheet.cell(row=current_row, column=7, value=f"=IFERROR(AVERAGEIF({r_type}, \"{safe_type}\", {r_size}), 0)").number_format = "0"
                
                current_row += 1
            
            # Totals Row (Sum of the mix rows)
            end_mix_row = current_row - 1
            sheet.cell(row=current_row, column=1, value="Totals / Averages").font = Font(bold=True)
            
            # Total Count
            sheet.cell(row=current_row, column=2, value=f"=SUM(B{start_mix_row}:B{end_mix_row})").font = Font(bold=True)
            
            # Total % (Should be 100%)
            sheet.cell(row=current_row, column=3, value=f"=SUM(C{start_mix_row}:C{end_mix_row})").number_format = percent_format
            sheet.cell(row=current_row, column=3).font = Font(bold=True)
            
            # Weighted Averages for the total row
            # Weighted Avg Rent = Sum(Count * AvgRent) / TotalCount
            # Or simpler: Just re-calculate using the full raw ranges
            sheet.cell(row=current_row, column=4, value=f"=AVERAGE({r_curr})").number_format = currency_fmt
            sheet.cell(row=current_row, column=4).font = Font(bold=True)
            
            sheet.cell(row=current_row, column=5, value=f"=AVERAGE({r_stab})").number_format = currency_fmt
            sheet.cell(row=current_row, column=5).font = Font(bold=True)
            
            sheet.cell(row=current_row, column=6, value=f"=AVERAGE({r_mkt})").number_format = currency_fmt
            sheet.cell(row=current_row, column=6).font = Font(bold=True)
            
            sheet.cell(row=current_row, column=7, value=f"=AVERAGE({r_size})").number_format = "0"
            sheet.cell(row=current_row, column=7).font = Font(bold=True)

            # Auto-fit columns
            for col in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
                sheet.column_dimensions[col].width = 20
            sheet.column_dimensions['A'].width = 30

        # Save
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

        # Method 1: Use Property Meta "building_size" (Extracted from OM as NRA/Rentable SF) - PRIORITY
        if analysis_data.property_meta and hasattr(analysis_data.property_meta, 'building_size') and analysis_data.property_meta.building_size > 0:
             total_sqft = analysis_data.property_meta.building_size
        
        # Method 2: Sum from individual units (Fallback if OM building size missing)
        elif analysis_data.rent_roll:
             total_sqft = sum((item.unit_size or 0) for item in analysis_data.rent_roll)

        # Method 3: Calculate from summary (Last resort)
        if total_sqft == 0 and analysis_data.rent_roll_summary:
             # Check if attribute exists (legacy support or if schema changes)
             if hasattr(analysis_data.rent_roll_summary, 'total_square_feet'):
                 total_sqft = getattr(analysis_data.rent_roll_summary, 'total_square_feet')
             
             # Calculate if still 0
             if total_sqft == 0 and analysis_data.rent_roll_summary.avg_unit_size and analysis_data.rent_roll_summary.total_units:
                 total_sqft = analysis_data.rent_roll_summary.avg_unit_size * analysis_data.rent_roll_summary.total_units

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

        # --- OM Data Lookup Helper ---
        # Build a lookup for OM data to support specific granular rows
        om_lookup = {}
        if analysis_data.om_proforma:
            for table in analysis_data.om_proforma:
                # Detect scenario type (Stabilized/Current vs Market)
                name_lower = table.scenario_name.lower()
                # Heuristic: "market" or "pro forma" usually implies the future state column
                # "current", "actual", "t12", "year 1" usually implies the stabilized/current column
                is_market = "market" in name_lower or "pro forma" in name_lower
                bucket = 'market' if is_market else 'stabilized'
                
                # Track insertion order to distinguish Income vs Expense rows
                current_index = 0
                for row in table.rows:
                    if row.annual is not None:
                        key = row.row_name.lower().strip()
                        if key not in om_lookup:
                            om_lookup[key] = {
                                'stabilized': 0.0,
                                'market': 0.0,
                                'display_name': row.row_name,
                                'index': current_index
                            }
                            current_index += 1
                        om_lookup[key][bucket] = row.annual

        # Determine Split Point between Income and Expenses
        # We look for "Total Income", "Effective Gross Income", etc. to define the cutoff.
        # Unmapped rows BEFORE this index are likely Income.
        # Unmapped rows AFTER this index are likely Expenses.
        cutoff_index = 10000 # Default to high number (treat as Income) if not found? No, unsafe.
        # Better default: If we can't find a cutoff, we might default to Expense to be conservative?
        # Let's try to find it.
        
        cutoff_keywords = ["effective gross", "gross operating", "total income", "gross income", "total operating income", "gross scheduled"]
        found_cutoff = False
        for key, val in om_lookup.items():
            if any(k in key for k in cutoff_keywords):
                cutoff_index = val['index']
                found_cutoff = True
                break
        
        if not found_cutoff:
            # Fallback: Try to find the first "Expense" or "Total Expense" and set cutoff before it?
            # Or just set to -1 to treat everything as Expense (conservative)
            cutoff_index = -1

        # Track which keys have been mapped to standard categories
        consumed_keys = set()

        def get_om_values(keywords: List[str], aggregate: bool = True):
            """
            Searches OM lookup for rows containing any of the keywords.
            Returns (stabilized_sum, market_sum) and a boolean indicating if any were found.
            Marks matched keys as consumed to avoid double-counting or re-listing.
            """
            if not aggregate:
                # Max Independent Strategy: Find the single best match instead of summing
                best_key = None
                best_vals = None
                max_magnitude = -1.0

                for key, vals in om_lookup.items():
                    if key in consumed_keys:
                        continue
                    
                    if any(k in key for k in keywords):
                        # Heuristic: Pick the entry with the largest values
                        curr_mag = max(abs(vals['stabilized']), abs(vals['market']))
                        if curr_mag > max_magnitude:
                            max_magnitude = curr_mag
                            best_key = key
                            best_vals = vals
                
                if best_key and best_vals:
                    consumed_keys.add(best_key)
                    return (best_vals['stabilized'], best_vals['market'])
                return (None, None)

            # Aggregate Strategy (Default): Sum all matches
            stab_sum = 0.0
            mark_sum = 0.0
            found_any = False
            for key, vals in om_lookup.items():
                if key in consumed_keys:
                    continue
                
                if any(k in key for k in keywords):
                    stab_sum += vals['stabilized']
                    mark_sum += vals['market']
                    consumed_keys.add(key)
                    found_any = True
            return (stab_sum, mark_sum) if found_any else (None, None)

        def priority_value(keywords: List[str], fallback_stab, fallback_mkt, is_deduction=False, aggregate=True):
            """
            Prioritizes values extracted from the OM over calculated fallbacks.
            """
            om_stab, om_mkt = get_om_values(keywords, aggregate=aggregate)
            
            val_stab = fallback_stab
            val_mkt = fallback_mkt
            
            if om_stab is not None:
                # Force sign based on line type to handle inconsistent extraction signs
                val_stab = -abs(om_stab) if is_deduction else abs(om_stab)
            
            if om_mkt is not None:
                val_mkt = -abs(om_mkt) if is_deduction else abs(om_mkt)
                
            return val_stab, val_mkt

        def clean_row_name(name: str) -> str:
            import re
            
            def replacer(match):
                full_match = match.group(0)
                # If the match is enclosed in parentheses, we keep them but format the inner number
                is_paren = full_match.startswith('(') and full_match.endswith(')')
                
                # Extract the number part
                number_str = match.group(1) if is_paren else full_match
                
                try:
                    val = float(number_str)
                    # Handle typical percentages (0.01 to 0.99) - be generous up to 1.0
                    if 0 < val <= 1:
                         formatted = f"{val*100:.1f}%".replace(".0%", "%")
                         return f"({formatted})" if is_paren else formatted
                    return full_match
                except:
                    return full_match

            # Regex Explanation:
            # We need to be careful not to match substrings inside words, but we want to catch "0.05"
            # (\(0\.\d+\))  -> Captures (0.05)
            # |             -> OR
            # \b(0\.\d+)\b  -> Captures 0.05 as a whole word
            return re.sub(r'(\(0\.\d+\)|\b0\.\d+\b)', replacer, name)

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
        gpr_stab, gpr_mkt = priority_value(
            ["gross potential", "market rent", "gpr", "street rent", "scheduled rent", "gross market", "market potential", "pro forma rent"],
            market_rent_annual,
            market_rent_annual,
            is_deduction=False,
            aggregate=False
        )
        write_row(current_row, "Gross Potential Market Rent", gpr_stab, gpr_mkt)
        row_gpr = current_row
        current_row += 1
        
        # 2. Loss to Lease (Negative value for deduction, Positive for gain)
        ltl_stab, ltl_mkt = priority_value(
            ["loss to lease", "gain to lease", "ltl", "concessions"],
            loss_to_lease_value,
            0,
            is_deduction=True
        )
        write_row(current_row, "Loss to Lease / Gain to Lease", ltl_stab, ltl_mkt)
        row_ltl = current_row
        current_row += 1
        
        # 3. Gross Scheduled Rental Income
        write_row(current_row, "Gross Scheduled Rental Income", f"=B{row_gpr}+B{row_ltl}", f"=F{row_gpr}+F{row_ltl}", is_total=True)
        row_gsr = current_row
        current_row += 1
        
        # 4. Vacancy
        vac_text = f"Vacancy ({vacancy_rate:.1%})"
        vac_stab, vac_mkt = priority_value(
            ["vacancy", "vacency", "credit loss", "bad debt"],
            f"=-B{row_gsr}*{vacancy_rate}",
            f"=-F{row_gsr}*{vacancy_rate}",
            is_deduction=True
        )
        write_row(current_row, vac_text, vac_stab, vac_mkt)
        row_vac = current_row
        current_row += 1
        
        # 5. Net Rental Income
        write_row(current_row, "Net Rental Income", f"=B{row_gsr}+B{row_vac}", f"=F{row_gsr}+F{row_vac}", is_total=True)
        row_nri = current_row
        current_row += 1
        
        # 6. Additional Income Rows (Garage, Laundry)
        # Garage / Parking
        garage_stab, garage_mkt = get_om_values(["garage", "parking"])
        row_garage = None
        if garage_stab is not None or garage_mkt is not None:
            write_row(current_row, "Garage / Parking", abs(garage_stab or 0), abs(garage_mkt or 0))
            row_garage = current_row
            current_row += 1
            
        # Laundry Income
        laundry_stab, laundry_mkt = get_om_values(["laundry", "vending", "washer"])
        row_laundry = None
        if laundry_stab is not None or laundry_mkt is not None:
            write_row(current_row, "Laundry Income", abs(laundry_stab or 0), abs(laundry_mkt or 0))
            row_laundry = current_row
            current_row += 1

        # 7. Other Income
        # Try to find "Other Income" in OM specifically
        other_stab, other_mkt = priority_value(
            ["other income", "miscellaneous", "misc income", "app fees", "application fees", "late fees", "pet fees", "reimbursement", "rub"],
            other_income_annual,
            other_income_annual,
            is_deduction=False
        )
        write_row(current_row, "Other Income", other_stab, other_mkt)
        row_other = current_row
        current_row += 1

        # --- Dynamic Injection: Additional Income Items ---
        # Inject unmapped rows that appear BEFORE the Income/Expense cutoff
        summary_blocklist = [
            "net operating income", "noi",
            "total operating expenses", "total expenses", "total expense", "total controllable expenses",
            "effective gross income", "gross scheduled income", "total income", "gross scheduled rental income",
            "gross potential rent", "market rent", "potential rent",
            "net rental income",
            "cash flow", "cash on cash", "debt service",
            "operating reserve", "replacement reserve",
            "total", "subtotal", "sub-total", "sub total",
            "total utilities", "total contract services"
        ]

        # Preparing EGI Sum parts
        egi_parts_b = [f"B{row_nri}", f"B{row_other}"]
        egi_parts_f = [f"F{row_nri}", f"F{row_other}"]
        
        if row_garage:
            egi_parts_b.append(f"B{row_garage}")
            egi_parts_f.append(f"F{row_garage}")
        if row_laundry:
            egi_parts_b.append(f"B{row_laundry}")
            egi_parts_f.append(f"F{row_laundry}")

        for key, vals in om_lookup.items():
            if key in consumed_keys:
                continue
            
            # Check if this looks like an Income item (index < cutoff)
            # If cutoff_index is -1 (not found), this condition is always False (Safe)
            if vals['index'] >= cutoff_index:
                continue

            if any(block in key for block in summary_blocklist):
                continue

            # Write Dynamic Income Row
            val_stab = abs(vals['stabilized']) if vals['stabilized'] is not None else 0
            val_mkt = abs(vals['market']) if vals['market'] is not None else 0
            
            write_row(current_row, clean_row_name(vals.get('display_name', key.title())), val_stab, val_mkt)
            
            # Add to EGI Sum
            egi_parts_b.append(f"B{current_row}")
            egi_parts_f.append(f"F{current_row}")
            
            consumed_keys.add(key) # Mark as consumed
            current_row += 1
        
        # 8. EGI
        write_row(current_row, "Gross Scheduled Income (Effective Gross Income)",
                  "=" + "+".join(egi_parts_b),
                  "=" + "+".join(egi_parts_f),
                  is_header=True)
        row_egi = current_row
        current_row += 1
        
        # --- Expense Section ---
        write_row(current_row, "Annual Operating Expenses", None, None, is_header=True)
        current_row += 1
        
        write_row(current_row, "Controllable Expenses", None, None, is_sub_header=True)
        current_row += 1
        
        # Property Management Fee
        pm_label = f"Property Management Fee ({mgmt_fee_rate:.1%})"
        pm_stab, pm_mkt = priority_value(
            ["management", "mgmt", "manager off"],
            f"=-B{row_egi}*{mgmt_fee_rate}",
            f"=-F{row_egi}*{mgmt_fee_rate}",
            is_deduction=True
        )
        write_row(current_row, pm_label, pm_stab, pm_mkt)
        row_mgmt = current_row
        current_row += 1
        
        # Controllable Items
        # Payroll
        pay_stab, pay_mkt = priority_value(
            ["payroll", "salary", "salaries", "wages", "personnel", "onsite", "superintendent"],
            -expenses_map["Payroll"],
            -expenses_map["Payroll"],
            is_deduction=True
        )
        write_row(current_row, "Payroll / Onsite Manager", pay_stab, pay_mkt)
        row_payroll = current_row # Start sum range
        current_row += 1
        
        # R&M
        rm_stab, rm_mkt = priority_value(
            ["repair", "maintenance", "r&m", "turnover", "painting", "cleaning", "supplies", "decorating"],
            -expenses_map["R&M"],
            -expenses_map["R&M"],
            is_deduction=True
        )
        write_row(current_row, "Repairs & Maintenance", rm_stab, rm_mkt)
        current_row += 1
        
        # Utilities
        util_stab, util_mkt = priority_value(
            ["utilit", "electric", "water", "sewer", "trash", "gas", "rubbish", "cable"],
            -expenses_map["Utilities"],
            -expenses_map["Utilities"],
            is_deduction=True
        )
        write_row(current_row, "Utilities", util_stab, util_mkt)
        current_row += 1
        
        # Contract Services
        con_stab, con_mkt = priority_value(
            ["contract", "landscap", "pest", "elevator", "pool", "security", "alarm", "snow", "grounds"],
            -expenses_map["Contract"],
            -expenses_map["Contract"],
            is_deduction=True
        )
        write_row(current_row, "Contract Services", con_stab, con_mkt)
        current_row += 1
        
        # Admin - Check for specific break-outs
        # Business / Other Taxes
        biz_tax_stab, biz_tax_mkt = get_om_values(["business tax", "license", "gross receipt", "business / other", "other taxes", "franchise tax"])
        if biz_tax_stab is not None or biz_tax_mkt is not None:
             write_row(current_row, "Business / other taxes", -abs(biz_tax_stab or 0), -abs(biz_tax_mkt or 0))
             current_row += 1
             
        # Rent Control / Other City Fees
        rc_stab, rc_mkt = get_om_values(["rent control", "rent registration", "city fee", "rent stabilization"])
        if rc_stab is not None or rc_mkt is not None:
             write_row(current_row, "Rent Control / Other City Fees", -abs(rc_stab or 0), -abs(rc_mkt or 0))
             current_row += 1
        
        # General Admin
        # Only appear if explicitly found in OM (no fallback) to avoid duplication or hallucination
        ga_stab, ga_mkt = get_om_values(["general", "admin", "office", "professional", "legal", "accounting", "phone", "internet", "dues", "subscription"])
        
        if ga_stab is not None or ga_mkt is not None:
             write_row(current_row, "General Admin", -abs(ga_stab or 0), -abs(ga_mkt or 0))
             current_row += 1
        
        # End sum range for Controllable Expenses
        row_controllable_end = current_row - 1
        
        # Total Controllable
        sum_range_b = f"B{row_mgmt}:B{row_controllable_end}"
        sum_range_f = f"F{row_mgmt}:F{row_controllable_end}"
        write_row(current_row, "Total Controllable Expenses", f"=SUM({sum_range_b})", f"=SUM({sum_range_f})", is_total=True)
        row_controllable = current_row
        current_row += 1
        
        # Fixed Expenses
        ret_stab, ret_mkt = priority_value(
            ["real estate tax", "property tax", "ad valorem"],
            -expenses_map["Taxes"],
            -expenses_map["Taxes"],
            is_deduction=True
        )
        write_row(current_row, "Real Estate Taxes (Ad Valorem)", ret_stab, ret_mkt)
        row_taxes = current_row
        current_row += 1
        
        # Assessments
        assess_stab, assess_mkt = get_om_values(["assessment", "direct charge", "special charge"])
        row_assess = None
        if assess_stab is not None or assess_mkt is not None:
             write_row(current_row, "Assessments", -abs(assess_stab or 0), -abs(assess_mkt or 0))
             row_assess = current_row
             current_row += 1
        
        # Insurance
        ins_stab, ins_mkt = priority_value(
            ["insurance", "hazard", "liability", "workers comp"],
            -expenses_map["Insurance"],
            -expenses_map["Insurance"],
            is_deduction=True
        )
        write_row(current_row, "Property Insurance", ins_stab, ins_mkt)
        row_ins = current_row
        current_row += 1

        # Pre-calculate Reserves to consume keys (prevent duplication in dynamic section)
        # We don't write the row yet, just consume the values/keys
        res_stab, res_mkt = priority_value(
            ["reserve", "replacement", "capital"],
            -expenses_map["Reserves"],
            -expenses_map["Reserves"],
            is_deduction=True
        )

        # --- Dynamic Injection of Unmapped OM Rows ---
        # Any row from the OM that wasn't consumed by the standard mapping above
        # is added here to ensure "no row left behind".
        
        # Sub-Total parts initialization
        sub_total_parts_b = [f"B{row_controllable}", f"B{row_taxes}", f"B{row_ins}"]
        sub_total_parts_f = [f"F{row_controllable}", f"F{row_taxes}", f"F{row_ins}"]
        if row_assess:
            sub_total_parts_b.append(f"B{row_assess}")
            sub_total_parts_f.append(f"F{row_assess}")

        # Iterate through om_lookup to find unconsumed items (Expenses)
        # These are items that come AFTER the cutoff (or if cutoff not found)
        found_dynamic_rows = False
        for key, vals in om_lookup.items():
            if key in consumed_keys:
                continue
            
            # If we successfully defined a cutoff, skip items that appear before it
            # (They should have been caught in Income section, or intentionally skipped)
            # If cutoff is -1, we include everything here (Safe fallback)
            if cutoff_index != -1 and vals['index'] < cutoff_index:
                continue

            # Check blocklist
            if any(block in key for block in summary_blocklist):
                continue

            if vals['stabilized'] == 0 and vals['market'] == 0:
                continue

            # Add Header for Dynamic Section if first time
            if not found_dynamic_rows:
                 write_row(current_row, "Additional Line Items", None, None, is_sub_header=True)
                 current_row += 1
                 found_dynamic_rows = True
            
            # Write the row
            # Use negative absolute value to ensure deduction, consistent with other expenses
            val_stab = -abs(vals['stabilized']) if vals['stabilized'] is not None else 0
            val_mkt = -abs(vals['market']) if vals['market'] is not None else 0
            
            write_row(current_row, vals.get('display_name', key.title()), val_stab, val_mkt)
            
            # Add to subtotal
            sub_total_parts_b.append(f"B{current_row}")
            sub_total_parts_f.append(f"F{current_row}")
            
            consumed_keys.add(key)
            current_row += 1
        
        # Sub-Total (Expenses before Reserves)
        write_row(current_row, "Sub-Total",
                  "=" + "+".join(sub_total_parts_b),
                  "=" + "+".join(sub_total_parts_f),
                  is_total=True)
        row_subtotal = current_row
        current_row += 1
        
        # Reserves
        # Values calculated earlier to prevent duplication
        write_row(current_row, "Reserves", res_stab, res_mkt)
        row_reserves = current_row
        current_row += 1
        
        # Total Operating Expenses
        write_row(current_row, "Total Operating Expenses",
                  f"=B{row_subtotal}+B{row_reserves}",
                  f"=F{row_subtotal}+F{row_reserves}",
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
        
        # Priority: OM Proforma Table Value -> Property Meta -> 0
        found_om_price = False
        if analysis_data.om_proforma:
            for table in analysis_data.om_proforma:
                if table.purchase_price and table.purchase_price > 0:
                    purchase_price = table.purchase_price
                    found_om_price = True
                    break
        
        if not found_om_price and analysis_data.property_meta and analysis_data.property_meta.purchase_price:
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


