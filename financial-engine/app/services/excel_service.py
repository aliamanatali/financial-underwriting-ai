import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from typing import Dict, Any, List
import io
from app.models.schemas import ProFormaEntry, UnderwritingAnalysis

class ExcelService:
    def _get_fiscal_year(self, analysis_data: UnderwritingAnalysis) -> str:
        """
        Extracts the fiscal year for display.
        Prioritizes AI-verified primary_fiscal_year.
        """
        if not analysis_data:
            return ""
            
        # 1. Check for AI Verified primary_fiscal_year
        if hasattr(analysis_data, 'primary_fiscal_year') and analysis_data.primary_fiscal_year:
            return str(analysis_data.primary_fiscal_year)
        
        if not analysis_data.historical_expenses:
            return ""
        
        years = [exp.expense_year for exp in analysis_data.historical_expenses if exp.expense_year]
        if not years:
            return ""
        
        from collections import Counter
        most_common_year = Counter(years).most_common(1)[0][0]
        return str(most_common_year)

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

    async def create_side_by_side_excel(self, data: List[ProFormaEntry], analysis_data: UnderwritingAnalysis = None) -> bytes:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._create_excel_sync, data, analysis_data)

    def _create_excel_sync(self, data: List[ProFormaEntry], analysis_data: UnderwritingAnalysis = None) -> bytes:
        workbook = openpyxl.Workbook()
        sheet: Worksheet = workbook.active
        sheet.title = "Financial Analysis"
        if analysis_data:
            self._add_detailed_assumptions_sheet(workbook, analysis_data)
        sheet.column_dimensions['A'].width = 35
        sheet.column_dimensions['B'].width = 18
        sheet.column_dimensions['C'].width = 18
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=12)
        section_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        section_font = Font(bold=True, size=11)
        currency_format = '"$"#,##0.00'
        percent_format = '0.00%'
        border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        sheet["A1"] = "Category"
        fiscal_year = self._get_fiscal_year(analysis_data)
        fy_suffix = f" - {fiscal_year}" if fiscal_year else ""
        sheet["B1"] = f"T12 (Historical{fy_suffix})"
        sheet["C1"] = "F12 (Pro Forma)"
        for col in ['A1', 'B1', 'C1']:
            sheet[col].fill = header_fill
            sheet[col].font = header_font
            sheet[col].alignment = Alignment(horizontal="center", vertical="center")
            sheet[col].border = border
        row_map = {}
        row = 2
        for entry in data:
            sheet[f"A{row}"] = entry.name
            row_map[entry.name] = row
            sheet[f"B{row}"] = entry.t12
            sheet[f"C{row}"] = entry.f12
            row += 1
        for entry_name, row in row_map.items():
            if "Vacancy Loss" in entry_name:
                gpr_row = row_map.get("Gross Potential Rent")
                if gpr_row:
                    sheet[f"B{row}"] = 0
                    sheet[f"C{row}"] = f"=C{gpr_row}*0.03"
            elif "Effective Gross Income" in entry_name:
                gpr_row = row_map.get("Gross Potential Rent")
                vacancy_row = row_map.get("Vacancy Loss")
                if gpr_row and vacancy_row:
                    sheet[f"B{row}"] = f"=B{gpr_row}-B{vacancy_row}"
                    sheet[f"C{row}"] = f"=C{gpr_row}-C{vacancy_row}"
            elif "Net Operating Income" in entry_name:
                egi_row = row_map.get("Effective Gross Income")
                expenses_row = row_map.get("Total Operating Expenses")
                if egi_row and expenses_row:
                    sheet[f"B{row}"] = f"=B{egi_row}-B{expenses_row}"
                    sheet[f"C{row}"] = f"=C{egi_row}-C{expenses_row}"
        for entry_name, row in row_map.items():
            sheet[f"A{row}"].border = border
            sheet[f"B{row}"].border = border
            sheet[f"C{row}"].border = border
            if "Cap Rate" in entry_name:
                sheet[f"B{row}"].number_format = percent_format
                sheet[f"C{row}"].number_format = percent_format
            else:
                sheet[f"B{row}"].number_format = currency_format
                sheet[f"C{row}"].number_format = currency_format
            if any(keyword in entry_name for keyword in ["Net Operating Income", "Cap Rate", "Total Operating Expenses", "Effective Gross Income"]):
                sheet[f"A{row}"].font = section_font
                sheet[f"A{row}"].fill = section_fill
                sheet[f"B{row}"].fill = section_fill
                sheet[f"C{row}"].fill = section_fill
            sheet[f"B{row}"].alignment = Alignment(horizontal="right")
            sheet[f"C{row}"].alignment = Alignment(horizontal="right")
        last_row = max(row_map.values()) if row_map else 2
        sheet[f"A{last_row + 2}"] = "Note: Cap Rate = NOI / Purchase Price (provided in analysis)"
        sheet[f"A{last_row + 2}"].font = Font(italic=True, size=9, color="666666")
        virtual_workbook = io.BytesIO()
        workbook.save(virtual_workbook)
        virtual_workbook.seek(0)
        return virtual_workbook.read()

    def _add_detailed_assumptions_sheet(self, workbook, analysis_data: UnderwritingAnalysis):
        sheet = workbook.create_sheet("Assumptions & Detail")
        header_fill = PatternFill(start_color="002060", end_color="002060", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        input_blue_font = Font(color="0070C0")
        border = Border(left=Side(style='thin', color="BFBFBF"),
                        right=Side(style='thin', color="BFBFBF"),
                        top=Side(style='thin', color="BFBFBF"),
                        bottom=Side(style='thin', color="BFBFBF"))
        currency_fmt = '"$"#,##0'
        percent_fmt = '0.00%'
        assumptions_log = []
        purchase_price = analysis_data.property_meta.purchase_price if analysis_data.property_meta else 0.0
        exit_valuation = analysis_data.exit_valuation if analysis_data.exit_valuation else purchase_price
        if exit_valuation < purchase_price:
            exit_valuation = purchase_price * 1.15
            assumptions_log.append(f"Disposition Value Adjusted: Calculated value was lower than purchase price. Applied 15% appreciation assumption (${exit_valuation:,.0f}).")
        total_units = analysis_data.property_meta.total_units if analysis_data.property_meta and analysis_data.property_meta.total_units else 1
        total_beds = 0
        if analysis_data.rent_roll:
            import re
            for r in analysis_data.rent_roll:
                u_type = str(r.unit_type).lower()
                found_bed = False
                match = re.search(r'(\d+)\s*(?:bd|br|bed)', u_type)
                if match:
                    total_beds += int(match.group(1))
                    found_bed = True
                elif "studio" in u_type:
                    total_beds += 1
                    found_bed = True
                elif "/" in u_type:
                    match_slash = re.search(r'^(\d+)\s*/', u_type)
                    if match_slash:
                        total_beds += int(match_slash.group(1)) or 1
                        found_bed = True
                if not found_bed: total_beds += 1
        if total_beds <= total_units:
             total_beds = int(total_units * 1.5)
        gpr_annual = sum((r.market_rent or 0) for r in analysis_data.rent_roll) * 12 if analysis_data.rent_roll else 0.0
        vacancy_rate = analysis_data.deal_parameters.vacancy_rate if analysis_data.deal_parameters else 0.05
        egi_annual = gpr_annual * (1 - vacancy_rate)
        tax_rate, special_assessments, biz_tax_rate, rent_board_fee = 0.012033, 40439.0, 0.0288, 404.0
        if getattr(analysis_data, 'tax_assumptions', None):
            if analysis_data.tax_assumptions.tax_rate: tax_rate = analysis_data.tax_assumptions.tax_rate
            if analysis_data.tax_assumptions.special_assessments: special_assessments = analysis_data.tax_assumptions.special_assessments
            if analysis_data.tax_assumptions.business_tax_rate: biz_tax_rate = analysis_data.tax_assumptions.business_tax_rate
            if analysis_data.tax_assumptions.rent_board_fee: rent_board_fee = analysis_data.tax_assumptions.rent_board_fee
        t12_granular = {
            "PG&E": 0.0, "Water & Sewer": 0.0, "Trash & Recycling": 0.0, "Internet": 0.0,
            "Salaries": 0.0, "R+M": 0.0, "Turnover": 0.0, "Landscaping": 0.0,
            "Pest Control": 0.0, "Janitorial": 0.0, "Elevator": 0.0,
            "Insurance": 0.0, "Admin": 0.0, "Marketing": 0.0, "Business Tax": 0.0,
            "Total Utilities": 0.0, "Reserves": 0.0
        }
        if analysis_data.historical_expenses:
            for exp in analysis_data.historical_expenses:
                cat = str(exp.mapped_category.value if hasattr(exp.mapped_category, 'value') else exp.mapped_category)
                txt, val = exp.original_text.lower(), exp.amount
                if any(x in txt for x in ["subtotal", "total operating", "net operating"]): continue
                if any(x in txt for x in ["electric", "gas", "pg&e", "pge"]): t12_granular["PG&E"] += val
                elif any(x in txt for x in ["water", "sewer"]): t12_granular["Water & Sewer"] += val
                elif any(x in txt for x in ["trash", "garbage"]): t12_granular["Trash & Recycling"] += val
                elif "internet" in txt: t12_granular["Internet"] += val
                elif "pest" in txt: t12_granular["Pest Control"] += val
                elif "landscap" in txt: t12_granular["Landscaping"] += val
                elif "elevator" in txt: t12_granular["Elevator"] += val
                elif any(x in txt for x in ["janitorial", "cleaning"]): t12_granular["Janitorial"] += val
                elif "payroll" in cat or "salary" in txt: t12_granular["Salaries"] += val
                elif "turnover" in txt: t12_granular["Turnover"] += val
                elif "insurance" in cat: t12_granular["Insurance"] += val
                elif "reserve" in cat: t12_granular["Reserves"] += val
                elif "maintenance" in cat: t12_granular["R+M"] += val
                elif "marketing" in cat.lower(): t12_granular["Marketing"] += val
                elif "admin" in cat: t12_granular["Admin"] += val
                elif "business tax" in txt: t12_granular["Business Tax"] += val
                else:
                    if "Utilities" in cat: t12_granular["Total Utilities"] += val
                    else: t12_granular["Admin"] += val
        inflation = 1.015
        for k in t12_granular: t12_granular[k] *= inflation
        if t12_granular["Salaries"] == 0:
             def get_om_val(ks):
                 if not analysis_data.om_proforma: return 0.0
                 m = 0.0
                 for t in analysis_data.om_proforma:
                     for r in t.rows:
                         if r.annual and any(k in r.row_name.lower() for k in ks): m = max(m, abs(r.annual))
                 return m
             t12_granular["Salaries"] = get_om_val(["payroll", "salary"])
        if t12_granular["Reserves"] == 0: t12_granular["Reserves"] = total_units * 200
        if t12_granular["Total Utilities"] > 0 and t12_granular["PG&E"] == 0:
             u = t12_granular["Total Utilities"]
             t12_granular["PG&E"], t12_granular["Water & Sewer"], t12_granular["Trash & Recycling"] = u*0.35, u*0.45, u*0.2
        if t12_granular["Insurance"] == 0: t12_granular["Insurance"] = total_units * 1000

        row = 2
        sheet.merge_cells(f"B{row}:E{row}")
        sheet[f"B{row}"] = "Property Tax Assumptions"
        sheet[f"B{row}"].fill, sheet[f"B{row}"].font, sheet[f"B{row}"].alignment = header_fill, header_font, Alignment(horizontal='center')
        row += 1
        for c, t in zip(["B", "C", "D", "E"], ["", "Current", "Target", "Disposition"]):
            sheet[f"{c}{row}"].value, sheet[f"{c}{row}"].font, sheet[f"{c}{row}"].alignment, sheet[f"{c}{row}"].border = t, Font(bold=True), Alignment(horizontal='center'), Border(bottom=Side(style='thin'))
        row += 1
        def write_tax_row(l, c, t, d, f=currency_fmt, b=False):
            nonlocal row
            for col, val in zip(["B", "C", "D", "E"], [l, c, t, d]):
                sheet[f"{col}{row}"].value, sheet[f"{col}{row}"].border = val, border
                if col != "B": sheet[f"{col}{row}"].number_format, sheet[f"{col}{row}"].alignment = f, Alignment(horizontal='right')
            if b: sheet[f"D{row}"].font = input_blue_font
            row += 1
        write_tax_row("Business Tax", biz_tax_rate, purchase_price, exit_valuation)
        sheet[f"C{row-1}"].number_format, sheet[f"C{row-1}"].font = percent_fmt, input_blue_font
        write_tax_row("Assessment Ratio:", 1.0, "VC Ratio", 1.0, f=percent_fmt)
        write_tax_row("Assessed Value", purchase_price, purchase_price, exit_valuation)
        write_tax_row("CapEx 30%", "-", 0, "-")
        write_tax_row("Tax Rate", tax_rate, tax_rate, tax_rate, f='0.0000%')
        r_pt = row
        write_tax_row("Property Taxes", f"=C{row-3}*C{row-1}", f"=D{row-3}*D{row-1}", f"=E{row-3}*E{row-1}")
        r_sa = row
        write_tax_row("Special Assess", special_assessments, special_assessments, special_assessments)
        row += 1
        write_tax_row("Total Taxes", f"=C{r_pt}+C{r_sa}", f"=D{r_pt}+D{r_sa}", f"=E{r_pt}+E{r_sa}")
        ref_tax = f"D{row-1}"
        
        row += 3
        st_row = row
        sheet.merge_cells(f"B{row}:G{row}")
        fiscal_year = self._get_fiscal_year(analysis_data)
        fy_suffix = f" ({fiscal_year})" if fiscal_year else ""
        sheet[f"B{row}"] = f"Stabilized Expense Detail YR1{fy_suffix}"
        sheet[f"B{row}"].fill, sheet[f"B{row}"].font, sheet[f"B{row}"].alignment = header_fill, header_font, Alignment(horizontal='center')
        row += 1
        for c, t in zip(["B", "C", "D", "E", "F", "G"], ["Item Description", "Category", "Annual", "Per Month", "Per Unit", "Per Bed"]):
            sheet[f"{c}{row}"].value, sheet[f"{c}{row}"].font, sheet[f"{c}{row}"].border, sheet[f"{c}{row}"].alignment = t, Font(bold=True), Border(bottom=Side(style='thin')), Alignment(horizontal='center')
        row += 1
        def write_exp_row(i, c, a):
            nonlocal row
            for col, val in zip(["B", "C", "D"], [i, c, a]):
                sheet[f"{col}{row}"].value, sheet[f"{col}{row}"].border = val, border
            sheet[f"D{row}"].number_format = currency_fmt
            sheet[f"E{row}"], sheet[f"F{row}"], sheet[f"G{row}"] = f"=D{row}/12", f"=D{row}/{total_units}", f"=D{row}/{total_beds}"
            for c in ["E", "F", "G"]: sheet[f"{c}{row}"].number_format, sheet[f"{c}{row}"].border = currency_fmt, border
            row += 1
        write_exp_row("Property Taxes", "Property Taxes", f"={ref_tax}")
        write_exp_row("PM Fee", "Property Mgmt", f"={egi_annual}*0.05")
        for k, v in t12_granular.items():
            if k != "Reserves" and k != "Business Tax": write_exp_row(k, "OpEx", v)
        write_exp_row("Reserves", "Reserves", t12_granular["Reserves"])
        write_exp_row("Business Tax", "Admin", f"={gpr_annual}*{biz_tax_rate}")
        s_start, s_end = st_row + 2, row - 1
        sheet[f"B{row}"].value, sheet[f"B{row}"].font = "Total Operating Expenses", Font(bold=True)
        sheet[f"D{row}"], sheet[f"D{row}"].font, sheet[f"D{row}"].number_format = f"=SUM(D{s_start}:D{s_end})", Font(bold=True), currency_fmt
        for c in ["E", "F", "G"]: sheet[f"{c}{row}"], sheet[f"{c}{row}"].number_format = f"=D{row}/" + ("12" if c=="E" else (str(total_units) if c=="F" else str(total_beds))), currency_fmt
        sheet.column_dimensions['B'].width, sheet.column_dimensions['C'].width, sheet.column_dimensions['D'].width = 30, 20, 15

    async def create_rent_roll_excel(self, analysis_data: UnderwritingAnalysis) -> bytes:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._create_rent_roll_excel_sync, analysis_data)

    def get_rent_roll_preview_data(self, analysis_data: UnderwritingAnalysis) -> Dict[str, Any]:
        rows = []
        for idx, item in enumerate(analysis_data.rent_roll, 1):
            rows.append({"id": idx, "unit_number": item.unit_number, "unit_type": item.unit_type, "unit_size": item.unit_size, "current_rent": item.current_rent, "market_rent": item.market_rent})
        return {"columns": [], "rows": rows}

    def _create_rent_roll_excel_sync(self, analysis_data: UnderwritingAnalysis) -> bytes:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Rent Roll Output"
        fiscal_year = self._get_fiscal_year(analysis_data)
        sheet["A1"] = f"Rent Roll - {fiscal_year}"
        virtual_workbook = io.BytesIO()
        workbook.save(virtual_workbook)
        virtual_workbook.seek(0)
        return virtual_workbook.read()

    async def create_om_proforma_excel(self, analysis_data: UnderwritingAnalysis) -> bytes:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._create_om_proforma_excel_sync, analysis_data)

    def _create_om_proforma_excel_sync(self, analysis_data: UnderwritingAnalysis) -> bytes:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        fiscal_year = self._get_fiscal_year(analysis_data)
        sheet.title = f"OM Proforma {fiscal_year}"
        virtual_workbook = io.BytesIO()
        workbook.save(virtual_workbook)
        virtual_workbook.seek(0)
        return virtual_workbook.read()
