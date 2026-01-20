# Financial Underwriting System Documentation

This document provides a comprehensive overview of the Financial Underwriting AI system, detailing the end-to-end flow, data extraction processes, calculation logic, and dashboard widgets.

---

## 1. System Architecture & Flow

The system follows a linear pipeline to transform raw documents (PDFs, Excel) into a structured financial model.

### **Step 1: Ingestion & Extraction**
*   **Input**: User uploads Offering Memorandums (OM), Rent Rolls, or T12 Income Statements.
*   **Process**: 
    1.  **OCR (Optical Character Recognition)**: Converts extracted text from documents.
    2.  **LLM Extraction**: An AI model parses the text to identify key data points (e.g., "Real Estate Taxes", "Unit 101 Rent").
    3.  **Normalization**: Raw text is mapped to standardized categories (e.g., "Repairs & Maint - Plumbing" $\rightarrow$ `REPAIRS_MAINTENANCE`).

### **Step 2: Verification & overrides**
*   **Process**: The system presents extracted data to the user.
*   **Action**: Users can manually override critical inputs like `Total Units`, `Purchase Price`, or specific Rent Roll items before the financial calculations run.

### **Step 3: The 5-Step Financial Model**
Once data is prepared, the `FinancialService` executes a deterministic 5-step modeling process:
1.  **Revenue Logic**: Calculates Gross Potential Rent, Vacancy Loss, and Effective Gross Income.
2.  **Expense Logic**: Standardizes operating expenses and applies "Valiance Rules" (e.g., re-calculating taxes based on purchase price).
3.  **Profitability Metrics**: Derives Net Operating Income (NOI) and Entry Cap Rate.
4.  **Debt & Cash Flow**: Models loan sizing, debt service, and levered cash flow.
5.  **Return Analysis**: Projects a 5-year hold period to calculate IRR and MOIC.

### **Step 4: Output Generation**
*   **Dashboard**: Interactive React UI for analysis.
*   **Exports**: Downloadable Excel models and Investment Memos.

---

## 2. Dashboard Widgets & Report Explanation

The frontend dashboard (`UnderwritingDashboard.tsx`) is divided into several analytical sections.

### **A. Property Details**
Located at the top, this bar provides the fundamental physical and financial constraints of the deal.
*   **Year Built**: Vintage of the property.
*   **Total Units**: The divisor for "Per Unit" metrics.
*   **Occupancy**: `Occupied Units / Total Units`. If > 100%, it flags a data error.
*   **Purchase Price**: The asking price or estimated value.
*   **Price Per Unit**: `Purchase Price / Total Units`.
*   **Existing Loan**: Current debt load (informational).

### **B. AI Underwriting Conclusion**
A high-level summary card that mimics a human analyst's "Go/No-Go" decision.
*   **Qualification Status**: "PASS" or "FAIL" based on hard gating criteria (e.g., minimum unit count, vintage).
*   **Investment Checklist**: Boolean checks for criteria like "Is Multifamily?", "Near Campus?", "Below Market Rents?".
*   **Business Plan & Risks**: AI-generated narrative summarizing the value-add strategy and potential pitfalls.

### **C. Investment Returns (The "Money" Card)**
The dark card highlighting the projected return profile over a 5-year hold.
*   **IRR (Levered)**: Internal Rate of Return. The annualized effective compounded return rate.
*   **MOIC**: Multiple on Invested Capital. `(Total Cash Distributions + Net Sale Proceeds) / Initial Equity`.
*   **Cash-on-Cash**: `Annual Pre-Tax Cash Flow / Initial Equity Invested`. Represents the immediate cash yield.

### **D. Operating Analysis Table**
A side-by-side comparison of **T12 (Historical)** vs. **F12 (Pro Forma)** performance.
*   **Variance %**: Shows the percentage change between historical actuals and projected figures.
*   **Tooltips**: Hovering over line items reveals "Explainability Metadata" — showing exactly which document and field the number came from.

### **E. Deal Parameters (Sensitivity Controls)**
An interactive panel allowing users to stress-test the model. Changing these sliders immediately re-runs the calculations.
*   **Rent Growth Rate**: Annual % increase in rental income.
*   **Vacancy Rate**: % of Gross Potential Rent lost to vacancy.
*   **Exit Cap Rate**: The Cap Rate used to value the property at sale (Year 6).
*   **Loan Amount**: The debt principal, affecting equity requirements and cash flow.

---

## 3. Calculations & Formulas

The core logic resides in `financial_service.py`. Below are the specific formulas used.

### **Revenue Calculations**
1.  **Gross Potential Rent (GPR)**:
    $$GPR = \sum (\text{Market Rent per Unit} \times 12)$$
    *Derived from the Rent Roll.*

2.  **Loss to Lease**:
    $$\text{Loss to Lease} = GPR - (\sum \text{Current Rent} \times 12)$$
    *Represents the revenue lost by charging below-market rents.*

3.  **Vacancy Loss**:
    $$\text{Vacancy Loss} = GPR \times \text{Vacancy Rate (Default 5\%)}$$

4.  **Effective Gross Income (EGI)**:
    $$EGI = GPR - \text{Loss to Lease} - \text{Vacancy Loss} + \text{Other Income}$$

### **Expense Calculations**
1.  **Property Taxes (Prop 13 Reset)**:
    $$\text{Taxes} = \text{Purchase Price} \times \text{Tax Rate (Default 1.2\%)}$$
    *Note: We ignore historical taxes and recalculate based on the new purchase price.*

2.  **Management Fee**:
    $$\text{Mgmt Fee} = EGI \times \text{Fee Rate (Default 4\%)}$$

3.  **Operating Expenses (OpEx)**:
    *   Sum of all normalized T12 expenses (Repairs, Utilities, Insurance, etc.).
    *   **38% Rule (Valiance Constraint)**: If total extracted expenses are $< 38\%$ of EGI, the system adds a "Capital Reserves" buffer to raise expenses to that floor.

4.  **Net Operating Income (NOI)**:
    $$NOI = EGI - \text{Total Operating Expenses}$$

### **Valuation & Debt Metrics**
1.  **Entry Cap Rate**:
    $$\text{Cap Rate} = \frac{NOI}{\text{Purchase Price}}$$

2.  **Total Project Cost**:
    $$\text{Project Cost} = \text{Purchase Price} + \text{Closing Costs} + \text{Renovation Budget}$$

3.  **Equity Invested**:
    $$\text{Equity} = \text{Total Project Cost} - \text{Loan Amount}$$

4.  **Annual Debt Service**:
    $$\text{Interest Payment} = \text{Loan Amount} \times (\text{SOFR} + \text{Spread})$$
    *Note: The model currently assumes Interest-Only (IO) bridge debt.*

5.  **Cash Flow**:
    $$\text{Cash Flow} = NOI - \text{Annual Debt Service}$$

### **Exit & Returns (5-Year Projection)**
1.  **Sale Price (Year 5)**:
    $$\text{Sale Price} = \frac{\text{Forward NOI (Year 6)}}{\text{Exit Cap Rate}}$$

2.  **Net Sale Proceeds**:
    $$\text{Proceeds} = \text{Sale Price} - \text{Sales Costs (2\%)} - \text{Loan Balance}$$

3.  **IRR Calculation**:
    Calculated using `numpy.irr` on the stream: `[-Equity, CF1, CF2, CF3, CF4, CF5 + Proceeds]`.

---

## 4. Data Extraction & Normalization Source

Data is sourced from uploaded documents and processed via `NormalizationService`.

### **Expense Normalization**
Raw text from T12 statements is mapped to the `ExpenseCategory` Enum:
*   `REAL_ESTATE_TAXES` (Often recalculated)
*   `INSURANCE`
*   `REPAIRS_MAINTENANCE`
*   `MANAGEMENT_FEES`
*   `UTILITIES`
*   `PAYROLL`
*   `MARKETING`
*   `ADMINISTRATIVE`
*   `OTHER`

### **Rent Roll Normalization**
Rent rolls are parsed into `RentRollItem` objects containing:
*   `Unit #`, `Unit Type`, `Tenant Name`
*   `Current Rent`, `Market Rent`
*   `Lease Start/End` dates

**Scaling Logic**: If the extracted rent roll has fewer units than the `Total Units` property metadata (e.g., missing pages), the system calculates a `Scaling Factor` (`Total / Extracted`) and grosses up the revenue to represent the full building.