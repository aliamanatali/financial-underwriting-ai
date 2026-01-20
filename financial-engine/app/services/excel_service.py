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
        
        # --- Sheet 1: Rent Roll Output ---
        sheet = workbook.create_sheet("Rent Roll Output")
        
        # Styles
        # Using a standard clean style, trying to match implied professionalism
        header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid") # Light Grey
        header_font = Font(bold=True, size=10)
        border_style = Border(bottom=Side(style='thin'))
        
        # Standard formats
        currency_fmt = '#,##0' # " 1,600 " style - integer with comma
        currency_dec_fmt = '#,##0.00'
        percent_fmt = '0.0%'
        
        # --- Headers ---
        # Row 1: Top Headers
        sheet["AA1"] = "Unit Breakdown - Existing"
        sheet["AA1"].font = Font(bold=True)
        
        # Parent Categories (Merged Cells)
        parent_headers = [
            ("C", "H", "Unit Mix Summary"),
            ("I", "J", "Current Effective"),
            ("K", "M", "Pro Forma Rents"),
            ("N", "O", "Pro Forma Rent Comparison"),
            ("P", "U", "Notes on Tenancy")
        ]
        
        for start_col, end_col, title in parent_headers:
            sheet.merge_cells(f"{start_col}1:{end_col}1")
            c = sheet[f"{start_col}1"]
            c.value = title
            c.font = header_font
            c.fill = header_fill
            c.alignment = Alignment(horizontal='center')
            # Border for merged range
            # We need to set border for all cells in range to look right
            # Simple approach: just outer cells
            for col_code in range(ord(start_col), ord(end_col)+1):
                sheet[f"{chr(col_code)}1"].border = border_style

        # Row 2: Headers
        # Map: Col Letter -> Header Name
        headers_map = {
            "C": "Count",
            "D": "Unit",
            "E": "Occupancy Type",
            "F": "Units",
            "G": "Beds",
            "H": "Size",
            "I": "$/Month",
            "J": "$/SF",
            "K": "Units",
            "L": "$/Month",
            "M": "$/SqFt",
            "N": "$ Increase",
            "O": "% Increase",
            "P": "Pro Forma Unit Type",
            "Q": "Unit Config",
            "R": "Beds",
            "S": "RC",
            "T": "Start Date",
            "U": "End Date",
            # Removed X "Other"
            
            # Summary Section
            "AA": "Unit Type",
            "AB": "Avg Current Rent",
            "AC": "Size",
            "AD": "Total SF",
            "AE": "Rent / SF",
            "AF": "Units",
            "AG": "Mix %",
            "AH": "SF %",
            "AI": "Beds",
            "AJ": "$/Beds"
        }
        
        header_row = 2
        for col_let, title in headers_map.items():
            cell = sheet[f"{col_let}{header_row}"]
            cell.value = title
            cell.font = header_font
            cell.border = border_style
            cell.alignment = Alignment(horizontal='center')

        # --- Data Processing ---
        
        # Data Rows Start at 3
        start_row = 3
        current_row = start_row
        
        rent_roll = analysis_data.rent_roll
        
        # Keep track of unique unit types encountered
        unique_unit_types = set()
        
        # Common borders
        data_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        
        for idx, item in enumerate(rent_roll, 1):
            # 1. Data Transformation
            # Use raw unit type as requested by user
            unit_type = item.unit_type or "Unknown"
            unique_unit_types.add(unit_type)
            
            # Heuristic for Beds: Try to extract a number from unit type if possible
            beds = 1 # Default fallback
            try:
                # Simple heuristic: Look for first digit.
                # "2/1.00" -> 2. "Studio" -> 0 (maybe? usually studio is 0 or 1 bed equivalent)
                # If we want to avoid "hardcoding rules", we can't do much.
                # However, we need a number for the Beds column (G) and summary calculations.
                # Let's try to parse the first digit found.
                import re
                match = re.search(r'\d+', unit_type)
                if match:
                    beds = int(match.group())
                elif "studio" in unit_type.lower():
                    beds = 1 # Common assumption if no number found
            except:
                pass

            # 2. Write Main Columns
            def set_cell(col, val, fmt=None, align='right'):
                c = sheet[f"{col}{current_row}"]
                c.value = val
                if fmt: c.number_format = fmt
                if align: c.alignment = Alignment(horizontal=align)
                c.border = data_border
                
            set_cell("C", idx, align='center')
            set_cell("D", item.unit_number, align='left')
            set_cell("E", unit_type, align='left')
            set_cell("F", 1, align='center')
            set_cell("G", beds, align='center')
            set_cell("H", item.unit_size, "#,##0", align='right')
            
            set_cell("I", item.current_rent, currency_fmt)
            
            # J: $/SF = Current Rent / Size
            set_cell("J", f"=IFERROR(I{current_row}/H{current_row},0)", currency_dec_fmt)
            
            set_cell("K", 1, align='center')
            
            set_cell("L", item.market_rent, currency_fmt)
            
            # M: $/SqFt (Market)
            set_cell("M", f"=IFERROR(L{current_row}/H{current_row},0)", currency_dec_fmt)
            
            # N: $ Increase = Market - Current (0 if Vacant)
            # Assuming Vacant if Current Rent (I) is 0
            set_cell("N", f"=IF(I{current_row}=0, 0, L{current_row}-I{current_row})", currency_fmt)
            
            # O: % Increase
            set_cell("O", f"=IFERROR(N{current_row}/I{current_row},0)", percent_fmt)
            
            # Pro Forma
            set_cell("P", unit_type, align='left')
            set_cell("Q", unit_type, align='left')
            set_cell("R", beds, align='center')
            set_cell("S", "RC" if "rent control" in (item.unit_type or "").lower() else "-", align='center')
            
            # Dates
            def fmt_date(d):
                if not d: return ""
                try:
                    parts = d.split('-')
                    if len(parts) == 3:
                        return f"{int(parts[1])}/{int(parts[2])}/{parts[0]}"
                    return d
                except:
                    return d

            set_cell("T", fmt_date(item.lease_start), align='center')
            set_cell("U", fmt_date(item.lease_end), align='center')

            current_row += 1

        last_data_row = current_row - 1
        
        # --- Footer Rows ---
        # Helper for footer styles
        footer_font = Font(bold=True)
        footer_border = Border(top=Side(style='thick'))
        
        # Row: TOTAL
        total_row = current_row
        sheet[f"C{total_row}"] = "TOTAL"
        sheet[f"C{total_row}"].font = footer_font
        sheet[f"C{total_row}"].border = footer_border
        
        # Sum Units
        sheet[f"F{total_row}"] = f"=SUM(F{start_row}:F{last_data_row})"
        sheet[f"F{total_row}"].font = footer_font
        sheet[f"F{total_row}"].border = footer_border
        sheet[f"F{total_row}"].alignment = Alignment(horizontal='center')
        
        # Sum Current Rent
        sheet[f"I{total_row}"] = f"=SUM(I{start_row}:I{last_data_row})"
        sheet[f"I{total_row}"].number_format = currency_fmt
        sheet[f"I{total_row}"].font = footer_font
        sheet[f"I{total_row}"].border = footer_border
        
        # Sum Market Rent
        sheet[f"L{total_row}"] = f"=SUM(L{start_row}:L{last_data_row})"
        sheet[f"L{total_row}"].number_format = currency_fmt
        sheet[f"L{total_row}"].font = footer_font
        sheet[f"L{total_row}"].border = footer_border
        
        # K: Total Units (Pro Forma)
        sheet[f"K{total_row}"] = f"=SUM(K{start_row}:K{last_data_row})"
        sheet[f"K{total_row}"].font = footer_font
        sheet[f"K{total_row}"].border = footer_border
        sheet[f"K{total_row}"].alignment = Alignment(horizontal='center')
        
        # M: $/SqFt Total (Market Rent / Total Size)
        # Total Size is SUM(H)
        total_size_range_formula = f"SUM(H{start_row}:H{last_data_row})"
        sheet[f"M{total_row}"] = f"=IFERROR(L{total_row}/{total_size_range_formula},0)"
        sheet[f"M{total_row}"].number_format = currency_dec_fmt
        sheet[f"M{total_row}"].font = footer_font
        sheet[f"M{total_row}"].border = footer_border
        
        # N: Total $ Increase
        sheet[f"N{total_row}"] = f"=SUM(N{start_row}:N{last_data_row})"
        sheet[f"N{total_row}"].number_format = currency_fmt
        sheet[f"N{total_row}"].font = footer_font
        sheet[f"N{total_row}"].border = footer_border
        
        # O: Total % Increase (Total Increase / Total Current Rent)
        sheet[f"O{total_row}"] = f"=IFERROR(N{total_row}/I{total_row},0)"
        sheet[f"O{total_row}"].number_format = percent_fmt
        sheet[f"O{total_row}"].font = footer_font
        sheet[f"O{total_row}"].border = footer_border
        
        # Apply border to remaining columns
        for col in ['D', 'E', 'G', 'H', 'J', 'P', 'Q', 'R', 'S', 'T', 'U']:
             sheet[f"{col}{total_row}"].border = footer_border

        current_row += 1
        
        # Row: Per Unit
        per_unit_row = current_row
        sheet[f"C{per_unit_row}"] = "Per Unit"
        sheet[f"C{per_unit_row}"].font = footer_font
        sheet[f"I{per_unit_row}"] = f"=IFERROR(I{total_row}/F{total_row},0)"
        sheet[f"I{per_unit_row}"].number_format = currency_dec_fmt
        sheet[f"I{per_unit_row}"].font = footer_font
        sheet[f"L{per_unit_row}"] = f"=IFERROR(L{total_row}/F{total_row},0)"
        sheet[f"L{per_unit_row}"].number_format = currency_dec_fmt
        sheet[f"L{per_unit_row}"].font = footer_font
        
        # N: Avg Increase per Unit
        sheet[f"N{per_unit_row}"] = f"=IFERROR(N{total_row}/F{total_row},0)"
        sheet[f"N{per_unit_row}"].number_format = currency_dec_fmt
        sheet[f"N{per_unit_row}"].font = footer_font
        
        current_row += 1
        
        # Row: Per Bed
        total_beds_formula = f"SUM(G{start_row}:G{last_data_row})"
        
        per_bed_row = current_row
        sheet[f"C{per_bed_row}"] = "Per Bed"
        sheet[f"C{per_bed_row}"].font = footer_font
        sheet[f"I{per_bed_row}"] = f"=IFERROR(I{total_row}/{total_beds_formula},0)"
        sheet[f"I{per_bed_row}"].number_format = currency_dec_fmt
        sheet[f"I{per_bed_row}"].font = footer_font
        sheet[f"L{per_bed_row}"] = f"=IFERROR(L{total_row}/{total_beds_formula},0)"
        sheet[f"L{per_bed_row}"].number_format = currency_dec_fmt
        sheet[f"L{per_bed_row}"].font = footer_font
        
        # N: Avg Increase per Bed
        sheet[f"N{per_bed_row}"] = f"=IFERROR(N{total_row}/{total_beds_formula},0)"
        sheet[f"N{per_bed_row}"].number_format = currency_dec_fmt
        sheet[f"N{per_bed_row}"].font = footer_font
        
        current_row += 1
        
        # Row: Per SqFt
        total_size_formula = f"SUM(H{start_row}:H{last_data_row})"
        
        per_sqft_row = current_row
        sheet[f"C{per_sqft_row}"] = "Per SqFt"
        sheet[f"C{per_sqft_row}"].font = footer_font
        sheet[f"I{per_sqft_row}"] = f"=IFERROR(I{total_row}/{total_size_formula},0)"
        sheet[f"I{per_sqft_row}"].number_format = currency_dec_fmt
        sheet[f"I{per_sqft_row}"].font = footer_font
        sheet[f"L{per_sqft_row}"] = f"=IFERROR(L{total_row}/{total_size_formula},0)"
        sheet[f"L{per_sqft_row}"].number_format = currency_dec_fmt
        sheet[f"L{per_sqft_row}"].font = footer_font
        
        # N: Avg Increase per SqFt
        sheet[f"N{per_sqft_row}"] = f"=IFERROR(N{total_row}/{total_size_formula},0)"
        sheet[f"N{per_sqft_row}"].number_format = currency_dec_fmt
        sheet[f"N{per_sqft_row}"].font = footer_font
        
        current_row += 1
        
        # Row: Annualized
        annualized_row = current_row
        sheet[f"C{annualized_row}"] = "Annualized"
        sheet[f"C{annualized_row}"].font = footer_font
        sheet[f"I{annualized_row}"] = f"=I{total_row}*12"
        sheet[f"I{annualized_row}"].number_format = currency_fmt
        sheet[f"I{annualized_row}"].font = footer_font
        sheet[f"L{annualized_row}"] = f"=L{total_row}*12"
        sheet[f"L{annualized_row}"].number_format = currency_fmt
        sheet[f"L{annualized_row}"].font = footer_font
        
        # N: Annualized Increase
        sheet[f"N{annualized_row}"] = f"=N{total_row}*12"
        sheet[f"N{annualized_row}"].number_format = currency_fmt
        sheet[f"N{annualized_row}"].font = footer_font
        
        # --- Summary Section (Right Side) ---
        # Starts at AA3 (Row 3, same as data start)
        summary_row = 3
        
        # Sort groups: Studio first, then 1 Bed, 2 Bed...
        def sort_key(k):
            k = k.lower()
            if "studio" in k: return 0
            if "1" in k: return 1
            if "2" in k: return 2
            if "3" in k: return 3
            if "4" in k: return 4
            return 99

        sorted_types = sorted(list(unique_unit_types), key=sort_key)
        
        # Define ranges for formulas
        r_type = f"$E${start_row}:$E${last_data_row}"
        r_rent = f"$I${start_row}:$I${last_data_row}"
        r_size = f"$H${start_row}:$H${last_data_row}"
        r_beds = f"$G${start_row}:$G${last_data_row}"
        
        summary_border = Border(bottom=Side(style='thin'))
        
        # Summary Headers
        summ_headers = ["Unit Type", "Avg Current Rent", "Size", "Total SF", "Rent / SF", "Units", "Mix %", "SF %", "Beds", "$/Beds"]
        summ_cols = ["AA", "AB", "AC", "AD", "AE", "AF", "AG", "AH", "AI", "AJ"]
        
        for col, title in zip(summ_cols, summ_headers):
            c = sheet[f"{col}2"]
            c.value = title
            c.font = header_font
            c.border = border_style
            c.alignment = Alignment(horizontal='center')

        for u_type in sorted_types:
            # Common set function
            def set_summ(col, val, fmt=None, align='right'):
                c = sheet[f"{col}{summary_row}"]
                c.value = val
                if fmt: c.number_format = fmt
                if align: c.alignment = Alignment(horizontal=align)
                c.border = summary_border

            # Formulas need to escape quotes in strings
            safe_type = u_type.replace('"', '""')
            
            set_summ("AA", u_type, align='left')
            
            # AB: Avg Current Rent
            set_summ("AB", f"=IFERROR(AVERAGEIF({r_type}, \"{safe_type}\", {r_rent}),0)", currency_fmt)
            
            # AC: Size (Avg)
            set_summ("AC", f"=IFERROR(AVERAGEIF({r_type}, \"{safe_type}\", {r_size}),0)", "#,##0")
            
            # AD: Total SF
            set_summ("AD", f"=SUMIF({r_type}, \"{safe_type}\", {r_size})", "#,##0")
            
            # AE: Rent / SF
            set_summ("AE", f"=IFERROR(AB{summary_row}/AC{summary_row},0)", currency_dec_fmt)
            
            # AF: Units
            set_summ("AF", f"=COUNTIF({r_type}, \"{safe_type}\")", align='center')
            
            # AG: Mix %
            set_summ("AG", f"=IFERROR(AF{summary_row}/$F${total_row},0)", percent_fmt)
            
            # AH: SF %
            set_summ("AH", f"=IFERROR(AD{summary_row}/SUM({r_size}),0)", percent_fmt)
            
            # AI: Beds (Avg)
            set_summ("AI", f"=IFERROR(AVERAGEIF({r_type}, \"{safe_type}\", {r_beds}),0)", "0.0", align='center')
            
            # AJ: $/Beds
            set_summ("AJ", f"=IFERROR(AB{summary_row}/AI{summary_row},0)", currency_fmt)
            
            summary_row += 1
            
        # Summary Total Row
        def set_summ_total(col, val, fmt=None, align='right'):
            c = sheet[f"{col}{summary_row}"]
            c.value = val
            if fmt: c.number_format = fmt
            if align: c.alignment = Alignment(horizontal=align)
            c.font = footer_font
            c.border = footer_border

        set_summ_total("AA", "Total / Wtd Avg", align='left')
        
        start_sum = 3
        end_sum = summary_row - 1
        
        # AF (Units Total)
        set_summ_total("AF", f"=SUM(AF{start_sum}:AF{end_sum})", align='center')
        
        # AB (Avg Rent) - Weighted Average
        set_summ_total("AB", f"=IFERROR(SUMPRODUCT(AF{start_sum}:AF{end_sum},AB{start_sum}:AB{end_sum})/AF{summary_row},0)", currency_fmt)
        
        # AD (Total SF)
        set_summ_total("AD", f"=SUM(AD{start_sum}:AD{end_sum})", "#,##0")
        
        # AC (Avg Size)
        set_summ_total("AC", f"=IFERROR(AD{summary_row}/AF{summary_row},0)", "#,##0")
        
        # AE (Rent / SF)
        set_summ_total("AE", f"=IFERROR(AB{summary_row}/AC{summary_row},0)", currency_dec_fmt)
        
        # AG (Mix %)
        set_summ_total("AG", f"=SUM(AG{start_sum}:AG{end_sum})", percent_fmt)
        
        # AH (SF %)
        set_summ_total("AH", f"=SUM(AH{start_sum}:AH{end_sum})", percent_fmt)
        
        # AI (Avg Beds)
        set_summ_total("AI", f"=IFERROR(SUMPRODUCT(AF{start_sum}:AF{end_sum},AI{start_sum}:AI{end_sum})/AF{summary_row},0)", "0.0", align='center')
        
        # AJ ($/Beds)
        set_summ_total("AJ", f"=IFERROR(AB{summary_row}/AI{summary_row},0)", currency_fmt)

        # Column Widths
        for col_char in ['C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG', 'AH', 'AI', 'AJ']:
            sheet.column_dimensions[col_char].width = 12
        sheet.column_dimensions['E'].width = 15 # Occ Type
        sheet.column_dimensions['T'].width = 15 # Date
        sheet.column_dimensions['U'].width = 15 # Date
        sheet.column_dimensions['AA'].width = 20 # Unit Type Summary

        # --- Unit Breakdown - Stabilized (Updated Request) ---
        # Starts at AL (Column 38)
        
        # 1. Headers
        stab_start_col = "AL"
        sheet[f"{stab_start_col}1"] = "Unit Breakdown - Stabilized"
        sheet[f"{stab_start_col}1"].font = Font(bold=True)
        
        # Columns based on image
        stab_headers = [
            "Unit Type",
            "Pro Forma Rent",
            "Size",
            "Total SF",
            "Rent / SF",
            "Units",
            "Mix %",
            "SF %",
            "Beds",
            "$/Beds",
            "Single",
            "Double",
            "Single $",
            "Double $",
            "Unit Config"
        ]
        
        # Map: AL -> AZ
        stab_cols = ["AL", "AM", "AN", "AO", "AP", "AQ", "AR", "AS", "AT", "AU", "AV", "AW", "AX", "AY", "AZ"]
        
        for col, title in zip(stab_cols, stab_headers):
            c = sheet[f"{col}2"]
            c.value = title
            c.font = header_font
            c.border = border_style
            c.alignment = Alignment(horizontal='center', wrap_text=True)
            
        # 3. Data Rows
        stab_row = 3
        # We reuse sorted_types from previous summary
        
        # Ranges for formulas
        r_market_rent = f"$L${start_row}:$L${last_data_row}"
        r_total_units_cell = f"$F${total_row}"
        # We need sum of total SF for SF % calculation
        r_grand_total_sf_cell = f"$AD${summary_row}" # This is the "Total SF" in the Summary table at AA
        
        # Wait, AD column in summary table is calculated using SUMIF.
        # But we need the GRAND TOTAL SF.
        # In the summary table (AA), row `summary_row` is the TOTAL line.
        # The Total SF is at AD{summary_row}.
        r_total_sf_val = f"$AD${summary_row}"
        
        for u_type in sorted_types:
            safe_type = u_type.replace('"', '""')
            
            # Common style
            def set_stab(col, val, fmt=None, align='right'):
                c = sheet[f"{col}{stab_row}"]
                c.value = val
                if fmt: c.number_format = fmt
                if align: c.alignment = Alignment(horizontal=align)
                c.border = summary_border

            # AL: Unit Type
            set_stab("AL", u_type, align='left')
            
            # AM: Pro Forma Rent (Market Rent Avg)
            set_stab("AM", f"=IFERROR(AVERAGEIF({r_type}, \"{safe_type}\", {r_market_rent}),0)", currency_fmt)
            
            # AN: Size (Avg SF)
            set_stab("AN", f"=IFERROR(AVERAGEIF({r_type}, \"{safe_type}\", {r_size}),0)", "#,##0")
            
            # AO: Total SF = Sum Size
            set_stab("AO", f"=SUMIF({r_type}, \"{safe_type}\", {r_size})", "#,##0")
            
            # AP: Rent / SF = Rent / Size
            set_stab("AP", f"=IFERROR(AM{stab_row}/AN{stab_row},0)", currency_dec_fmt)
            
            # AQ: Units
            set_stab("AQ", f"=COUNTIF({r_type}, \"{safe_type}\")", "#,##0", align='center')
            
            # AR: Mix % = Units / Total Units
            set_stab("AR", f"=IFERROR(AQ{stab_row}/{r_total_units_cell},0)", percent_fmt)
            
            # AS: SF % = Total SF / Grand Total SF
            # We can use SUM(AO range) but we are building it row by row.
            # We can reference the total from the other summary table or calculate sum at bottom.
            # Using bottom sum reference is circular if we build top down? No.
            # But we can't reference bottom yet.
            # Let's use the total from the existing summary table (AA) -> AD{summary_row}
            set_stab("AS", f"=IFERROR(AO{stab_row}/{r_total_sf_val},0)", percent_fmt)
            
            # AT: Beds (Avg)
            set_stab("AT", f"=IFERROR(AVERAGEIF({r_type}, \"{safe_type}\", {r_beds}),0)", "0.0", align='center')
            
            # AU: $/Beds = Rent / Beds
            set_stab("AU", f"=IFERROR(AM{stab_row}/AT{stab_row},0)", currency_fmt)
            
            # AV-AZ: Student housing specifics (Dummy Data Logic)
            # Assumption: All beds are "Single" for simplicity in dummy data
            # Single Count = Beds
            set_stab("AV", f"=AT{stab_row}", "0", align='center') # Single = Beds
            set_stab("AW", "-", align='center') # Double (Assume 0)
            
            # Single $ = Rent / Singles (which is same as $/Bed)
            set_stab("AX", f"=AU{stab_row}", currency_fmt) # Single $
            set_stab("AY", "-", align='center') # Double $
            
            # Unit Config Text
            set_stab("AZ", f"=AT{stab_row} & \" Single\"", align='center') # e.g. "2 Single"
            
            stab_row += 1

        # 4. Total Row
        def set_stab_total(col, val, fmt=None, align='right'):
            c = sheet[f"{col}{stab_row}"]
            c.value = val
            if fmt: c.number_format = fmt
            if align: c.alignment = Alignment(horizontal=align)
            c.font = footer_font
            c.border = footer_border

        set_stab_total("AL", "Total / Wtd Avg", align='left')
        
        start_s = 3
        end_s = stab_row - 1
        
        # AQ: Units Total
        set_stab_total("AQ", f"=SUM(AQ{start_s}:AQ{end_s})", "#,##0", align='center')
        
        # AM: Wtd Avg Rent
        set_stab_total("AM", f"=IFERROR(SUMPRODUCT(AQ{start_s}:AQ{end_s},AM{start_s}:AM{end_s})/AQ{stab_row},0)", currency_fmt)
        
        # AN: Wtd Avg Size
        set_stab_total("AN", f"=IFERROR(SUMPRODUCT(AQ{start_s}:AQ{end_s},AN{start_s}:AN{end_s})/AQ{stab_row},0)", "#,##0")
        
        # AO: Total SF
        set_stab_total("AO", f"=SUM(AO{start_s}:AO{end_s})", "#,##0")
        
        # AP: Wtd Avg Rent/SF (Total Rent / Total SF)
        # Total Rent = Units * Rent = AQ * AM (approx) -> Better: SumProduct(Units, Rent)
        # Total SF = AO
        set_stab_total("AP", f"=IFERROR((AM{stab_row}*AQ{stab_row})/AO{stab_row},0)", currency_dec_fmt)
        
        # AR: Mix % Total (100%)
        set_stab_total("AR", f"=SUM(AR{start_s}:AR{end_s})", percent_fmt)
        
        # AS: SF % Total (100%)
        set_stab_total("AS", f"=SUM(AS{start_s}:AS{end_s})", percent_fmt)
        
        # AT: Avg Beds
        set_stab_total("AT", f"=IFERROR(SUMPRODUCT(AQ{start_s}:AQ{end_s},AT{start_s}:AT{end_s})/AQ{stab_row},0)", "0.0", align='center')
        
        # AU: $/Beds (Avg)
        set_stab_total("AU", f"=IFERROR(AM{stab_row}/AT{stab_row},0)", currency_fmt)
        
        # AV: Single Total (Avg)
        set_stab_total("AV", f"=AT{stab_row}", "0.0", align='center')
        
        # AW: Double Total
        set_stab_total("AW", "-", align='center')
        
        # AX: Single $ (Avg)
        set_stab_total("AX", f"=AU{stab_row}", currency_fmt)
        
        # AY: Double $
        set_stab_total("AY", "-", align='center')
        
        # AZ
        set_stab_total("AZ", "-", align='center')

        # 5. Explanatory Text for Dummy Data
        stab_row += 2
        sheet[f"AL{stab_row}"] = "Assumptions & Notes:"
        sheet[f"AL{stab_row}"].font = Font(bold=True)
        
        stab_row += 1
        notes = [
            "1. Pro Forma Rent refers to the Market Rent (potential rent at current market rates).",
            "2. Student Housing Configuration (Single/Double, Unit Config) is estimated.",
            "3. Assumption: All beds are treated as 'Single' occupancy for this projection.",
            "4. Single $ is calculated as Pro Forma Rent / Beds.",
            "5. Actual unit configurations may vary based on leasing strategy."
        ]
        
        for note in notes:
            sheet[f"AL{stab_row}"] = note
            stab_row += 1

        # Column Widths for new table
        for col in stab_cols:
             sheet.column_dimensions[col].width = 12
        sheet.column_dimensions['AL'].width = 20
        sheet.column_dimensions['AZ'].width = 20

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


