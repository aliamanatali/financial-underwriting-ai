# Bug Fix Report — Financial Underwriting Dashboard

## What the Client Reported

1. **"If IRR is ~13%, Cash-on-Cash should also be above 0 — something is wrong with the formula."**
2. **"The Net Operating Income number looks incorrect — basic math seems off."**

---

## Bug 1 — CoC, MOIC, and IRR Were All Wrong

### What went wrong
The app was hardcoding a **$5,000,000 loan** as the default for every property — regardless of its actual price.
This property cost **$3,135,000**. A $5M loan on a $3.1M property means the bank is giving you more money than the property is worth.

That made the equity calculation go **negative** (you'd theoretically pocket $1.7M at closing, which is impossible).

- **CoC and MOIC** hit a safety check (`if equity > 0`) and returned **0** — hence the blank zeros.
- **IRR** treated that impossible $1.7M "profit at closing" as a real cash inflow, which is what produced the fake **13.07%** figure.

All three numbers were wrong because of one bad default.

### How we fixed it
Removed the hardcoded `$5,000,000` from three places in the frontend code. The backend now calculates the loan correctly using the standard **65% LTV rule**:
> 65% × $3,135,000 = **$2,037,750** loan → real equity → real CoC, MOIC, and IRR.

---

## Bug 2 — NOI Looked Like Bad Math

### What went wrong
The summary table showed:

| Item | F12 (Pro Forma) |
|---|---|
| Gross Potential Rent | $325,200 |
| Total Expenses | ($90,944) |
| **Net Operating Income** | **$148,383** |

Anyone reading this would calculate $325,200 − $90,944 = **$234,255** — not $148,383. It looks like a math error.

**It wasn't.** The NOI was correct. The table was just hiding the steps in between:

| Step | Amount |
|---|---|
| Market Rent (GPR) | $325,200 |
| Less: Gap between market & actual rents | ($86,916) |
| Less: Vacancy allowance (3%) | ($9,756) |
| Plus: Other income | $10,800 |
| **= Effective Gross Income (EGI)** | **$239,328** |
| Less: Operating Expenses | ($90,944) |
| **= Net Operating Income** | **$148,383** ✓ |

The table jumped straight from top-line rent to expenses, skipping the middle steps entirely.

### How we fixed it
Added the missing rows to the table — Loss to Lease, Vacancy Loss, Other Income, and the EGI subtotal. Now the math is visible and checks out line by line.

---

## Uncommitted Changes (Current Session)

### Fix 1 — Loan Amount No Longer Hardcoded

**Files changed:** `financial-engine/app/api/routes/multi_document.py`, `financial-engine/app/models/schemas 2.py`, `ocr-frontend/components/UnderwritingDashboard.tsx`

`loan_amount` was hardcoded to `$5,000,000` as a default in three places. Changed to `Optional[float] = None` in the backend schema and removed the hardcoded initialization in the route. The frontend now reads `analysis.loan_amount` (backend-calculated via 65% LTV) instead of always defaulting to $5M.

**What it fixes:** Every deal was computing debt service, CoC, DSCR, and IRR against a $5M loan regardless of actual purchase price. Now each deal uses its correct loan amount.

---

### Fix 2 — EGI Waterfall Rows Added to Dashboard

**File changed:** `ocr-frontend/components/UnderwritingDashboard.tsx`

Added four new rows to the revenue section of the financial table:
- **Less: Loss to Lease** — gap between market rent and actual rent
- **Less: Vacancy Loss** — vacancy allowance deduction
- **Plus: Other Income** — ancillary income (parking, laundry, etc.)
- **= Effective Gross Income (EGI)** — subtotal before expenses

Rows only render when the value is > 0, so clean deals don't show empty lines.

**What it fixes:** The table was jumping from Gross Potential Rent straight to Total Expenses, making NOI look like bad math. Now the full income waterfall is visible and auditable.

---

### Fix 3 — New TypeScript Types for EGI and Loan Fields

**File changed:** `ocr-frontend/lib/types.ts`

Added the following fields to the `UnderwritingAnalysis` interface:
`gross_potential_rent`, `loss_to_lease`, `vacancy_loss`, `other_income`, `effective_gross_income`, `loan_amount`, `equity_invested`

**What it fixes:** Without these type definitions the frontend couldn't access the backend-returned values for these fields — TypeScript would ignore or error on them silently.

---

### Fix 4 — Invalid Gemini Fast Model ID Corrected

**File changed:** `financial-engine/app/config.py`

Changed `gemini_fast_model` from `"gemini-3-flash-preview"` (does not exist) to `"gemini-2.0-flash"`.

**What it fixes:** Any feature using the fast model — chat responses, quick expense normalization — was failing because the Gemini API rejected the invalid model name. Now it routes to the correct model.
