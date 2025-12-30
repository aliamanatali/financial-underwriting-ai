import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from typing import Dict, Any, List
import io

class ExcelService:
    def create_side_by_side_excel(self, data: List["ProFormaEntry"]) -> bytes:
        """
        Creates an Excel file with a side-by-side view of T12 and F12 data.
        """
        workbook = openpyxl.Workbook()
        sheet: Worksheet = workbook.active
        sheet.title = "Side-by-Side Analysis"

        # Headers
        sheet["A1"] = "Category"
        sheet["B1"] = "T12 (Historical)"
        sheet["C1"] = "F12 (Pro Forma)"

        # Populate Data
        for row, entry in enumerate(data, start=2):
            sheet[f"A{row}"] = entry.name
            sheet[f"B{row}"] = entry.t12
            sheet[f"C{row}"] = entry.f12

        # Save to a byte stream
        virtual_workbook = io.BytesIO()
        workbook.save(virtual_workbook)
        virtual_workbook.seek(0)
        return virtual_workbook.read()