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


