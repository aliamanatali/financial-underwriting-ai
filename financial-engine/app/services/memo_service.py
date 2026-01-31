from typing import Dict, Any
from app.models.schemas import UnderwritingAnalysis
import logging
from fpdf import FPDF

logger = logging.getLogger(__name__)

class PDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, 'CONFIDENTIAL INVESTMENT MEMO', 0, 0, 'R')
        self.ln(12)
        # Draw a line separator
        self.set_draw_color(200, 200, 200)
        self.line(10, 22, 200, 22)
        self.ln(5)
        self.set_text_color(0, 0, 0)
        self.set_draw_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
        self.set_text_color(0, 0, 0)

class MemoService:
    def __init__(self, gemini_service: "GeminiService" = None):
        self.gemini_service = gemini_service

    async def generate_investment_memo(self, analysis_data: UnderwritingAnalysis) -> str:
        """
        Generates a markdown-formatted investment memo using an LLM.
        Falls back to template if LLM is unavailable.
        """
        try:
            if self.gemini_service:
                memo_content = await self._generate_memo_with_llm(analysis_data)
            else:
                memo_content = self._generate_memo_template(analysis_data)
            return memo_content
        except Exception as e:
            logger.error(f"Error generating memo: {e}. Falling back to template.")
            return self._generate_memo_template(analysis_data)

    async def _generate_memo_with_llm(self, analysis_data: UnderwritingAnalysis) -> str:
        """
        Uses LLM to generate a sophisticated investment memo.
        """
        # Calculate metrics
        cap_rate = analysis_data.cap_rate * 100 if analysis_data.cap_rate else 0
        historical_cap_rate = analysis_data.historical_cap_rate * 100 if analysis_data.historical_cap_rate else 0
        occupancy_rate = analysis_data.rent_roll_summary.occupancy_rate * 100 if analysis_data.rent_roll_summary else 0
        upside = cap_rate - historical_cap_rate

        # Ensure distinct status
        deal_status = 'PASS' if analysis_data.pass_fail_status == 'PASS' else 'FAIL'
        
        prompt = f"""
        Write a professional investment memo for a real estate deal with the following details:
        
        Property: {analysis_data.property_meta.address}
        Year Built: {analysis_data.property_meta.year_built}
        Total Units: {analysis_data.property_meta.total_units}
        Current Occupancy: {occupancy_rate:.1f}%
        Current Cap Rate: {historical_cap_rate:.2f}%
        Pro Forma Cap Rate: {cap_rate:.2f}%
        Upside Potential: {upside:.2f}%
        
        Deal Status: {deal_status}
        
        Investment Checklist:
        - Multifamily? {analysis_data.conclusion.investment_checklist.is_multifamily if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        - Near Campus? {analysis_data.conclusion.investment_checklist.near_campus if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        - Business Plan: {analysis_data.conclusion.investment_checklist.business_plan if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        - Below Market Rents? {analysis_data.conclusion.investment_checklist.rents_below_market if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        - Mismanaged? {analysis_data.conclusion.investment_checklist.is_mismanaged if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        - Diligence Issues: {analysis_data.conclusion.investment_checklist.diligence_issues if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        - Primary Risks: {analysis_data.conclusion.investment_checklist.primary_risks if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        - Price Per Unit: {analysis_data.conclusion.investment_checklist.price_per_unit_analysis if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        
        Include the following sections:
        1. Executive Summary (2-3 sentences)
        2. Investment Checklist & Questions (Address the items above in a table). DO NOT include the Deal Status or Recommendation in this table.
        3. Key Questions:
           - Is there upside potential? (Answer: Yes, upside of {upside:.2f}%)
           - What are the primary risks?
           - What is the value-add strategy?
        4. SWOT Analysis (Strengths, Weaknesses, Opportunities, Threats)
        4. Investment Highlights
        5. Risk Mitigation
        
        Write in professional, concise language suitable for an investment committee.
        
        IMPORTANT: Return ONLY the memo content in valid Markdown. Do not include any introductory text like "Here is the memo" or "Based on the details provided". Start directly with the # INVESTMENT MEMO title.
        
        The final section MUST be exactly:
        ## RECOMMENDATION
        
        **Status:** {deal_status}
        """
        
        try:
            # Check if service supports async
            if hasattr(self.gemini_service, 'generate_content_async'):
                # Use fast model for memo generation to speed up the process
                memo = await self.gemini_service.generate_content_async(prompt, use_fast_model=True)
            else:
                memo = self.gemini_service.generate_content(prompt)
            return memo
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Instead of re-raising, we should fallback to template here or in caller
            # Caller handles it, so raising is fine if caller catches it.
            # But let's be safe and return None to trigger fallback in generate_investment_memo
            raise

    def _sanitize_text_for_pdf(self, text: str) -> str:
        """
        Replaces unsupported Unicode characters with ASCII equivalents for FPDF standard fonts.
        """
        replacements = {
            "•": "-",
            "✓": "+",
            "✗": "x",
            "→": "->",
            "←": "<-",
            "–": "-",
            "—": "-",
            "’": "'",
            "“": '"',
            "”": '"',
        }
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        
        # Final safety check: replace any remaining non-latin-1 chars with ?
        return text.encode('latin-1', 'replace').decode('latin-1')

    def _render_table(self, pdf, lines):
        """
        Renders a Markdown table into the PDF.
        """
        data = []
        headers = []
        
        for i, line in enumerate(lines):
            line = self._sanitize_text_for_pdf(line).strip()
            if not line: continue
            
            # Split by pipe and remove empty first/last elements
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 3: continue # Not a valid table row | a |
            
            row_data = parts[1:-1]
            
            if i == 0:
                headers = row_data
            elif set(line) <= set('|- :'): # Separator line
                continue
            else:
                data.append(row_data)
        
        if not headers and not data:
            return

        # Config
        page_width = pdf.w - 2 * pdf.l_margin
        col_width = page_width / len(headers)
        line_height = 6
        
        # Render Headers
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_fill_color(240, 240, 240) # Light gray
        for header in headers:
            pdf.cell(col_width, 8, header, 1, 0, 'L', True)
        pdf.ln()
        
        # Render Data
        pdf.set_font('Helvetica', '', 10)
        pdf.set_fill_color(255, 255, 255)
        
        for row in data:
            # Ensure row has same number of columns as headers
            if len(row) < len(headers):
                row.extend([''] * (len(headers) - len(row)))
            elif len(row) > len(headers):
                row = row[:len(headers)]

            # Calculate max height for this row
            max_height = line_height
            
            # First pass: calculate height needed for largest cell
            # We use a temporary check. fpdf2 has dry_run=True, output="LINES"
            # Fallback for older fpdf versions or safety: simple length heuristic or just fixed height
            # Given we want robustness, we'll try the modern way first
            
            row_heights = []
            for item in row:
                try:
                    # Modern fpdf2 approach
                    multi_cell_lines = pdf.multi_cell(col_width, line_height, item, dry_run=True, output="LINES")
                    height = len(multi_cell_lines) * line_height
                except:
                    # Fallback or if method signature differs
                    # Simple heuristic: ~50 chars per line for this width?
                    # Let's assume approx width.
                    # Better fallback: use get_string_width
                    text_width = pdf.get_string_width(item)
                    lines_count = int(text_width / (col_width - 2)) + 1
                    height = lines_count * line_height
                
                row_heights.append(height)
            
            if row_heights:
                max_height = max(row_heights)
                
            # Check for page break
            if pdf.get_y() + max_height > pdf.h - pdf.b_margin:
                pdf.add_page()
                # Reprint headers on new page? Optional, skipping for now

            # Save start position
            x_start = pdf.get_x()
            y_start = pdf.get_y()
            
            # Print cells
            for i, item in enumerate(row):
                pdf.set_xy(x_start + (i * col_width), y_start)
                # Write text without border
                pdf.multi_cell(col_width, line_height, item, border=0)
                # Draw border rectangle with max_height to ensure uniform row height
                pdf.rect(x_start + (i * col_width), y_start, col_width, max_height)
                
            # Move to next line
            pdf.set_y(y_start + max_height)

    async def generate_investment_memo_pdf(self, analysis_data: UnderwritingAnalysis) -> bytes:
        """
        Generates a PDF investment memo.
        """
        if analysis_data.investment_memo:
            content = analysis_data.investment_memo
        else:
            content = await self.generate_investment_memo(analysis_data)
        
        pdf = PDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Detect Table Start
            if line.startswith('|') and i + 1 < len(lines) and set(lines[i+1].strip()) <= set('|- :'):
                # Gather table lines
                table_lines = []
                while i < len(lines) and lines[i].strip().startswith('|'):
                    table_lines.append(lines[i])
                    i += 1
                self._render_table(pdf, table_lines)
                pdf.ln(5) # Space after table
                continue

            # Sanitize line before processing
            line = self._sanitize_text_for_pdf(line)

            # Skip the main title as it is covered by the header
            if line.strip().upper() == '# INVESTMENT MEMO':
                i += 1
                continue

            if not line:
                pdf.ln(2)
                i += 1
                continue

            if line.startswith('# '):
                pdf.ln(5)
                pdf.set_font('Helvetica', 'B', 16)
                pdf.set_text_color(44, 62, 80) # Dark blue/gray
                pdf.cell(0, 10, line.replace('# ', ''), 0, 1, 'L')
                pdf.set_text_color(0, 0, 0)
            elif line.startswith('## '):
                pdf.ln(4)
                pdf.set_font('Helvetica', 'B', 14)
                pdf.set_text_color(44, 62, 80)
                pdf.cell(0, 8, line.replace('## ', ''), 0, 1, 'L')
                pdf.set_text_color(0, 0, 0)
            elif line.startswith('### '):
                pdf.ln(2)
                pdf.set_font('Helvetica', 'B', 12)
                pdf.cell(0, 6, line.replace('### ', ''), 0, 1, 'L')
            elif line.startswith('- '):
                 pdf.set_font('Helvetica', '', 11)
                 if pdf.get_x() > 15:
                     pdf.ln()
                 pdf.multi_cell(0, 6, f"  - {line[2:]}")
            else:
                pdf.set_font('Helvetica', '', 11)
                # Remove bold markers for PDF (simple cleanup)
                clean_line = line.replace('**', '')
                if pdf.get_x() > 15:
                    pdf.ln()
                pdf.multi_cell(0, 6, clean_line)
            
            i += 1
                
        # In fpdf2, pdf.output() returns bytearray if dest='S'
        output = pdf.output(dest='S')
        
        # Handle different fpdf versions/return types
        if isinstance(output, str):
            return output.encode('latin-1')
        elif isinstance(output, bytearray):
            return bytes(output)
        else:
            return output

    def _generate_memo_template(self, analysis_data: UnderwritingAnalysis) -> str:
        """
        Generates a template-based memo (fallback).
        """
        cap_rate = analysis_data.cap_rate * 100 if analysis_data.cap_rate else 0
        historical_cap_rate = analysis_data.historical_cap_rate * 100 if analysis_data.historical_cap_rate else 0
        occupancy_rate = analysis_data.rent_roll_summary.occupancy_rate * 100
        upside = cap_rate - historical_cap_rate
        noi = analysis_data.pro_forma_noi if analysis_data.pro_forma_noi else 0
        
        # Ensure clean status
        deal_status = 'PASS' if analysis_data.pass_fail_status == 'PASS' else 'FAIL'

        memo = f"""# INVESTMENT MEMO

## Property: {analysis_data.property_meta.address}

### EXECUTIVE SUMMARY
This {analysis_data.property_meta.total_units}-unit multifamily asset presents a compelling value-add opportunity with strong fundamentals and clear path to value creation. Current occupancy is {occupancy_rate:.1f}% with Pro Forma cap rate of {cap_rate:.2f}%.

---

## INVESTMENT CHECKLIST

| Question | Status |
|----------|--------|
| **Is the property a multifamily investment?** | {analysis_data.conclusion.investment_checklist.is_multifamily if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |
| **Is it within 6 blocks of campus?** | {analysis_data.conclusion.investment_checklist.near_campus if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |
| **What is the business plan to capture value?** | {analysis_data.conclusion.investment_checklist.business_plan if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |
| **Are existing rents below market?** | {analysis_data.conclusion.investment_checklist.rents_below_market if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |
| **Is it poorly run/mismanaged?** | {analysis_data.conclusion.investment_checklist.is_mismanaged if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |
| **What diligence items remain unresolved?** | {analysis_data.conclusion.investment_checklist.diligence_issues if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |
| **What are the primary risks?** | {analysis_data.conclusion.investment_checklist.primary_risks if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |
| **Price Per Unit Analysis** | {analysis_data.conclusion.investment_checklist.price_per_unit_analysis if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |

## KEY QUESTIONS

### Is there upside potential?
**YES** – The deal presents an upside potential of **{upside:.2f}%**, with opportunity to increase cap rate from {historical_cap_rate:.2f}% to {cap_rate:.2f}%.

**Pro Forma NOI: ${noi:,.0f}**
**Pro Forma Cap Rate: {cap_rate:.2f}%**

### What are the primary risks?
- **Market Risk**: Economic downturn could impact rental demand and vacancy rates.
- **Interest Rate Risk**: Rising rates could affect refinance and acquisition financing.
- **Operational Risk**: Asset management execution is critical to achieving projections.
- **Structural/Physical Risk**: Building age ({analysis_data.property_meta.year_built}) requires ongoing capital reserves for maintenance.

### What is the value-add strategy?
1. **Rent Growth**: Market rent achievement through tenant turnover and lease-ups.
2. **Expense Optimization**: Implement cost controls and operational efficiencies.
3. **Capital Improvements**: Strategic CapEx to improve NOI and rents.
4. **Occupancy Stabilization**: Reduce vacancy through targeted marketing and tenant retention.

---

## SWOT ANALYSIS

### Strengths
✓ {analysis_data.property_meta.total_units}-unit portfolio provides diversified revenue base
✓ Strong current occupancy rate of {occupancy_rate:.1f}%
✓ Potential for above-market rent growth
✓ Established property with proven operations

### Weaknesses
✗ Property age ({analysis_data.property_meta.year_built}) may require capital reserves
✗ Limited upside without rent growth execution
✗ Market-dependent tenant demand

### Opportunities
→ Market rent achievement upside of {upside:.2f}%
→ Operational efficiencies and cost reduction
→ Value-add capital improvements
→ Favorable financing environment for refinance

### Threats
← Economic recession impacting rents and occupancy
← Rising operating expenses and inflation
← Increased competition from new supply
← Interest rate increases impacting cap rates

---

## INVESTMENT HIGHLIGHTS

• **Strong Fundamentals**: {occupancy_rate:.1f}% occupancy with stable tenant base
• **Clear Value Creation Path**: {upside:.2f}% upside to pro forma cap rate
• **Market Opportunity**: Location supports rent growth and market rate achievement
• **Proven Asset Class**: Multifamily provides stable cash flow and inflation hedge

---

## RECOMMENDATION

**Status:** {deal_status}

{f'**GATING CONCERNS**: {", ".join(analysis_data.gating_reasons)}' if analysis_data.gating_reasons else '✓ Deal passes all gating criteria'}

"""
        return memo