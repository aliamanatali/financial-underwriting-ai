# Extraction Logic Audit

**Date:** 2026-04-18
**Scope:** Full trace of PDF upload through figure classification and storage
**Status:** Diagnostic only. No code changes.

---

## Correcting Your Mental Model

Your recollection:

> 1. Identify all numeric figures in the source document
> 2. For each figure, look at surrounding context
> 3. Use that context to classify what the figure represents
> 4. If the classification is confident enough, keep it

**This is partially wrong.** Here's what actually happens:

1. Gemini Vision OCR extracts the **entire document as raw text** — it does not identify individual figures. There is no "figure detection" step. The OCR prompt (`ocr-backend/app/services/gemini_service.py:89-160`) is a full-page transcription system ("DocuMind") that outputs everything on every page verbatim.

2. The Financial Engine sends that raw text to **a second LLM call** (Gemini) with a structured extraction prompt that says "extract all EXPENSE line items" or "extract rent roll data." This LLM returns a JSON array of `{description, amount}` pairs. There is **no regex-based figure finder, no bounding-box number detection, no surrounding-context window**. The LLM does the parsing and the pairing in one shot.

3. Classification into standard categories happens in a **third LLM call** (or cache hit). Each `description` string is sent to `map_expenses_to_categories_async` which asks Gemini to assign it to one of the `ExpenseCategory` enum values.

4. There is **no confidence threshold that gates keep vs. discard**. Every item the extraction LLM returns is kept. Confidence scores are informational — they affect display color in the UI but never cause an item to be dropped.

The key thing you're missing: **there are three separate LLM calls in series**, not a single extraction-and-classify pipeline. And there is no regex/parser stage — it's LLM all the way down for figure identification.

---

## 1. Extraction Pipeline Overview

### Entry Points

**Upload:** `POST /api/documents/upload` in `ocr-backend/app/api/routes/documents.py:32-90`
- Accepts PDF/image, saves to GCP Cloud Storage
- Queues Celery task `process_document_task`

**Analysis trigger:** `POST /api/v1/analysis` in `financial-engine/app/main.py:86-91`
- Frontend calls this after OCR completes
- Financial Engine fetches the extracted text from OCR Backend via `GET /api/documents/{id}/text`

### Full Path

```
PDF Upload
    |
    v
[ocr-backend] documents.py:32 — POST /api/documents/upload
    |
    v
[ocr-backend] storage_service.py:129 — save_file() to GCP Cloud Storage
    |
    v
[ocr-backend] document_tasks.py:45 — process_document_task (Celery)
    |   Determines chunking strategy (>50 pages or >5MB = chunk)
    |   Default: 15 pages/chunk, 5 pages/chunk for scanned docs
    |
    v
[ocr-backend] gemini_service.py:220 — extract_pdf_chunk()
    |   Sends base64 PDF chunk + DocuMind prompt to Gemini Vision
    |   Returns raw text with page markers ("--- PAGE N ---")
    |   NO figure extraction — just verbatim transcription
    |
    v
[ocr-backend] document_tasks.py:405 — aggregate_chunks_task
    |   Combines chunks, calculates confidence, stores in MongoDB
    |   MongoDB schema: {document_id, extracted_text, metadata, status}
    |
    v
[financial-engine] ingestion_service.py:630 — ingest_pdf_document()
    |   Fetches raw text from OCR Backend
    |   2-phase parallel extraction:
    |     Phase 1: Property meta + Rent roll (parallel)
    |     Phase 2: T12 financials
    |
    v
[financial-engine] ingestion_service.py:1069 — ingest_financials_from_pdf()
    |   LLM CALL #2: Sends raw text + structured prompt to Gemini
    |   Prompt: "Extract all EXPENSE line items... Return JSON array"
    |   Returns: [{description, amount, amount_t3/t6/t9, expense_year}]
    |
    v
[financial-engine] normalization_service.py:200 — normalize_expenses_async()
    |   Pre-filters: removes numeric-only descriptions (line 220-236)
    |   Checks Redis/MongoDB cache for known description->category mappings
    |   For cache misses:
    |     LLM CALL #3: gemini_client.py:231 — map_expenses_to_categories_async()
    |     Sends batch of descriptions + category list to Gemini
    |     Returns: [{original_text, mapped_category, confidence, reasoning}]
    |   Post-processing: forced reclassification rules (lines 347-497)
    |   Outputs: List[StandardizedExpense]
    |
    v
[financial-engine] financial_service.py:30 — _deduplicate_expenses()
    |   OM Primacy → Year filtering → Frequency dedup → Total line detection
    |
    v
[financial-engine] financial_service.py:599+ — 5-step financial model
    |   GPR → EGI → NOI → Debt Service → IRR/MOIC/CoC
    |
    v
[financial-engine] storage_service.py — save_analysis_result() to MongoDB
```

### ASCII Flow Diagram

```
                    +-----------+
                    |  PDF File |
                    +-----+-----+
                          |
                    POST /upload
                          |
               +----------v-----------+
               |    OCR Backend       |
               |  (Celery + Gemini    |
               |   Vision = raw text) |
               +----------+-----------+
                          |
                  GET /documents/{id}/text
                          |
               +----------v-----------+
               |   Financial Engine   |
               |                      |
               |  1. Ingestion        |  <-- LLM Call #2 (extract figures)
               |  2. Normalization    |  <-- LLM Call #3 (classify categories)
               |  3. Deduplication    |  <-- Deterministic rules
               |  4. Financial Model  |  <-- Deterministic math
               |  5. Storage          |
               +----------+-----------+
                          |
                    Save to MongoDB
                          |
               +----------v-----------+
               |      Frontend        |
               |  (display + verify)  |
               +----------------------+
```

---

## 2. Figure Identification

**There is no dedicated figure-identification step.** Figures are identified by the LLM during structured extraction.

### Where it happens

- **T12 expenses:** `ingestion_service.py:1069-1106` — `ingest_financials_from_pdf()`
- **Rent roll:** `ingestion_service.py:549-605` — `extract_rent_roll_from_pdf()`
- **Property meta:** `ingestion_service.py:449-485` — `extract_property_meta_from_pdf()`
- **Excel rent rolls:** `ingestion_service.py:318-547` — `extract_rent_roll_from_excel()`

### How numbers are parsed

The LLM returns JSON with numeric values already parsed. Post-extraction, two helper functions clean up edge cases:

**`_parse_amount()`** (`normalization_service.py:162-198`):
- Strips `$` and `,`
- Converts `(500)` → `-500` (parenthetical negatives)
- Handles `- 500` → `-500` (spaced negatives)
- Falls back to regex `r'-?\d+(\.\d+)?'` for mixed text+number strings
- Returns `0.0` on failure

**`_parse_int_robust()`** (`normalization_service.py:135-160`):
- For non-currency fields (sqft, unit count)
- Strips commas, extracts first digit sequence via `r'\d+'`
- Returns `0` on failure

### What it does NOT handle well

- **Ranges** ("$2,400-$2,800"): The LLM decides which number to use. No explicit range handling in parsing code.
- **Dates vs. numbers**: The LLM is expected to distinguish "1924" (year built) from "$1,924" (amount). No code-level safeguard — `_parse_int_robust` will happily extract `1924` from any string.
- **$ prefix ambiguity**: The OCR text contains raw `$` signs. The extraction LLM is supposed to interpret them contextually. The `_parse_amount` function strips them unconditionally.

### Different paths per document type

| Document | Extraction Function | LLM Prompt |
|----------|-------------------|------------|
| T12/P&L | `ingest_financials_from_pdf()` | "Extract all EXPENSE line items... Return JSON array" |
| Rent Roll (PDF) | `extract_rent_roll_from_pdf()` | "Extract unit_number, tenant_name, current_rent, market_rent..." |
| Rent Roll (Excel) | `extract_rent_roll_from_excel()` | No LLM — pandas parsing with header detection |
| Property Meta | `extract_property_meta_from_pdf()` | "Extract property name, address, year built, purchase price..." |
| OM (expenses) | Same as T12 path | Same prompt, different source text |

**Each document type has its own extraction path and prompt.** They do NOT share a common figure-identification pipeline.

---

## 3. Context-Based Classification

### How classification actually works

Classification is **not** based on surrounding context windows. It works like this:

1. The extraction LLM (Call #2) returns `{description: "Repair - Plumbing", amount: 500.00}`
2. The `description` string is the **only context** used for classification
3. Classification happens via one of three mechanisms, tried in order:

#### Mechanism 1: Cache lookup (Redis → MongoDB)

**File:** `normalization_service.py:16-79` — `_get_cached_mappings()`

- Key: exact `description` string (e.g., `"Repair - Plumbing"`)
- Redis key format: `mapping:{description}`
- Redis TTL: 30 days
- MongoDB collection: `expense_mappings`
- If cache hit: confidence = `0.95` (hardcoded at line 264)

**Implication:** If "Business/Other Taxes" was classified as "General & Administrative" for a previous deal, it will be classified the same way for ALL future deals via cache. The cache does not distinguish between deals or document contexts.

#### Mechanism 2: LLM classification (Gemini)

**File:** `gemini_client.py:231-266` — `map_expenses_to_categories_async()`

**Full prompt template:**
```
You are an expert Real Estate Financial Analyst for Valiance Capital.
Your task is to normalize a list of raw expense line items from a T12
Operating Statement into standard financial categories.

### GUIDELINES:
1. **Analyze Context**: Look at the 'description' text carefully.
   Ignore amounts when categorizing, focus on the nature of the expense.
2. **CapEx vs OpEx**: If an item looks like a major renovation
   (e.g., "Roof Replacement", "Unit Upgrade", "New HVAC"),
   categorize it as 'Capital Reserves' or 'Uncategorized'.
3. **Confidence**: Assign a confidence score (0.0 to 1.0).
4. **Reasoning**: Provide a short, user-friendly explanation.

### INPUT DATA:
Raw Expenses: {json.dumps(raw_expenses)}
Target Categories: {json.dumps(categories)}

### OUTPUT FORMAT:
Return a valid JSON array of objects:
- "original_text": The original description.
- "mapped_category": The category from the provided list.
- "reasoning": A brief (5-10 words) explanation.
- "confidence": 0.0 to 1.0.
```

- **Model:** Gemini fast model (`gemini-2.0-flash-exp`) at temperature 0.0
- **Batch size:** 25 descriptions per LLM call
- **Concurrency:** 3 concurrent batches (semaphore)
- **Context available to LLM:** Only the `description` string and `amount` (amounts are in the raw_expenses dict, though the prompt says "ignore amounts")

**Critical observation:** The LLM sees the description string in isolation. It does NOT see:
- The surrounding page text
- Which document the item came from
- Whether it appeared in an income section or expense section
- The line above or below in the source document

#### Mechanism 3: Keyword fallback

**File:** `normalization_service.py:580-609` — `_fallback_simple_mapping_raw()`

Only fires if the LLM batch call fails entirely. Keyword map:

```python
"tax" or "assessment"          → Real Estate Taxes
"insurance"                     → Insurance
"repair" or "maintenance"       → Repairs & Maintenance
"management"                    → Management Fees
"util" or "gas" or "electric"  → Utilities
"payroll" or "staff" or ...    → Payroll
"contract" or "service"        → Contract Services
"advertis" or "market"         → Advertising & Marketing
"parking" or "garage" or ...   → Other Income    ← NOTE THIS
"rent control" or "regulatory" → Other Operating Expenses
everything else                → Uncategorized
```

Confidence for all fallback items: `0.65`

#### Post-classification forced reclassification

**File:** `normalization_service.py:347-536`

After the LLM (or cache) assigns a category, a long chain of keyword checks can **override** that assignment. These are hardcoded rules for known problem areas:

| Keywords | Forced Category |
|----------|----------------|
| "loan balance", "principal balance", "mortgage payable" | Current Loan Balance |
| "rental income", "rent income" | Gross Potential Rent |
| "parking revenue", "garage income", "laundry income" | Other Income |
| "vacancy", "concession", "bad debt", "loss to lease" | Uncategorized (excluded from OpEx) |
| CapEx list (20+ keywords: "roofing", "renovation", etc.) | Capital Reserves |
| "depreciation", "amortization", "interest expense" | Uncategorized |
| Insurance + amount > $25k, or limit/coverage keywords | Capital Reserves |

### How ties are broken

**They aren't.** If "Business/Other Taxes" appears, the LLM decides. The forced-reclassification chain runs top-to-bottom — first match wins. If "tax" appears in both the vacancy keyword check and the fallback keyword map, whichever `if` block fires first determines the category. There is no scoring or disambiguation logic.

---

## 4. Confidence Scoring

### How confidence is computed

| Source | Confidence Value | How Determined |
|--------|-----------------|----------------|
| LLM classification | 0.0–1.0 | LLM's self-reported confidence in JSON output |
| Cache hit (Redis/Mongo) | 0.95 | Hardcoded (`normalization_service.py:264`) |
| Keyword fallback | 0.65 | Hardcoded (`normalization_service.py:607`) |
| User-verified | 1.0 (implicit) | `user_verified=True` overrides all dedup logic |

### What the UI shows

The frontend (`ExpensesVerificationWidget.tsx:481-494`) converts decimal to percentage and color-codes:
- >= 95%: Green (emerald)
- 85–94%: Amber
- < 85%: Red (rose)

### Thresholds

**There is NO confidence threshold that gates keep vs. discard.** Every item returned by the extraction LLM is kept regardless of confidence. The 85%/90%/95%/99%/100% values visible in the UI are purely informational.

**There is NO separate "needs human review" threshold.** The red color (< 85%) is the closest analog, but it doesn't trigger any workflow — it's just a visual indicator.

---

## 5. Duplicate Detection

### Where it lives

**File:** `financial_service.py:30-329` — `_deduplicate_expenses()`

### Algorithm (in order)

**Step 0 — Document Priority** (lines 46-112):
- Groups expenses by source document (OM vs. P&L vs. raw bills)
- **OM Primacy:** If OM has > 5 expense items, discard ALL other sources (except manual entries and user-verified items)
- **P&L Primacy:** If P&L exists, discard all raw bill expenses (keep non-expense categories from bills)

**Step 1 — Year Filtering** (lines 114-155):
- If multiple years detected, pick most recent
- Exception: if most recent year has < 5 items AND another year has > 15, use the more populated year

**Step 2 — Group by Category** (line 157-161):
- Groups all remaining expenses by `mapped_category` enum value

**Step 3 — Per-category dedup** (lines 162-329):

For each category with > 1 item:

1. **User-verified priority** (lines 169-198): If user-verified items exist for Tax/Insurance/Management, keep only the latest verified item. For other categories, keep all verified and dedup unverified by amount against verified amounts.

2. **Frequency dedup** (lines 200-238): If exact same amount appears > 4 times → keep 1. If amount > $5,000 appears > 1 time → keep 1.

3. **Total line detection** (lines 243-263): If any item has "total" in description, keep that item and discard all others in that category. **No sum verification** — it just looks for the word "total."

4. **Tax/Insurance special** (lines 265-289): Take the MAX amount item. For Insurance, cap at $100k unless user-verified; prefer items in $1k–$50k range.

5. **Utility special** (lines 291-319): If > 12 items and largest ≈ sum of rest (within 25%), keep only the largest (likely annual total).

6. **General fallback** (line 328): Keep all items (sum them).

### What it hashes on

Dedup is by **category + amount**. Items within the same `mapped_category` are compared by `amount` value (`round(i.amount, 2)`). There is no hashing on `raw_text`, source page, or description.

### Why same-category-different-amount items both appear

"Business/Other Taxes $25,770" and "Business/Other Taxes $30,078" would both survive dedup because:
1. They're in the same category group
2. But frequency dedup only fires if the **exact same amount** appears multiple times
3. Since $25,770 != $30,078, both pass through
4. The general fallback (line 328) keeps all items → they get summed

**However** — the actual failure case is more subtle. If these items get mapped to **different** categories by the LLM (e.g., one to "Real Estate Taxes" and the other to "General & Administrative"), they appear in separate category groups and never interact during dedup at all. They both survive as independent line items in different categories, and both amounts count toward total expenses.

---

## 6. Income vs. Expense Separation

### Where it happens

Income/expense separation is NOT a single check. It's distributed across three layers:

**Layer 1 — Extraction prompt** (`ingestion_service.py:1075-1097`):
The T12 extraction prompt says "Extract all EXPENSE line items. Also extract OTHER INCOME... Ignore primary rental income." The LLM is supposed to label items appropriately in the description.

**Layer 2 — Forced reclassification** (`normalization_service.py:367-397`):
- "rental income" → `GROSS_POTENTIAL_RENT`
- "parking revenue", "garage income" → `OTHER_INCOME`
- "vacancy", "concession" → `UNCATEGORIZED`

**Layer 3 — Financial model exclusion** (`financial_service.py:395-449`):
The financial model explicitly excludes these categories from the T12 OpEx sum:
```
CAPITAL_RESERVES, CURRENT_LOAN_BALANCE, LEASING_FEES,
PROPERTY_INFO, TOTAL_UNITS, YEAR_BUILT, PURCHASE_PRICE,
PRICE_PER_UNIT, UNCATEGORIZED, ACCOUNTS_RECEIVABLE,
OTHER_INCOME, GROSS_POTENTIAL_RENT, REIMBURSEMENTS
```

**Layer 4 — Frontend display** (`ExpenseRevenueList.tsx:24-39`):
Frontend filters by category string: items matching `["Gross Potential Rent", "Other Income", "Reimbursements", "Accounts Receivable"]` render in the Revenue section; everything else renders as Expense.

### Is there a check preventing dual classification?

**No.** There is no mechanism preventing the same figure from appearing as both income and expense. If the extraction LLM returns "Garage/Parking $10,800" from two different pages (or the same page interpreted differently), each instance is processed independently through normalization. The LLM might classify one as "Other Income" and the other as "Other Operating Expenses." The dedup logic would not catch this because they'd be in different category groups.

### Walking through "Garage/Parking $10,800"

1. OCR extracts full page text containing "Garage/Parking    $10,800"
2. T12 extraction LLM returns `{description: "Garage/Parking", amount: 10800}`
3. Normalization checks forced reclassification:
   - Line 377: Checks for "parking revenue", "parking income", "garage revenue", "garage income"
   - **"Garage/Parking" does NOT match** any of these — it's not "garage revenue" or "garage income"
   - The keyword check requires the full phrase, not just "garage" or "parking"
4. Falls to LLM classification. The LLM sees description "Garage/Parking" and categories list.
   - If the LLM interprets it as income → "Other Income"
   - If the LLM interprets it as an expense → "Other Operating Expenses"
   - **The outcome depends entirely on the LLM's judgment for this specific description**
5. If it appears twice (e.g., once from OM, once from T12), each instance is classified independently
6. The cache (`mapping:Garage/Parking`) will lock in whichever classification happened first for future occurrences of that exact description string

### Walking through "Vacancy $54,000"

1. T12 extraction returns `{description: "Vacancy", amount: 54000}`
2. Normalization forced reclassification (line 394):
   - `is_vacancy_keyword = any(k in desc_lower for k in ["vacancy", "concession", "bad debt", "loss to lease", "rent loss"])`
   - **"vacancy" matches** → forced to `UNCATEGORIZED`
3. Financial model (layer 3): `UNCATEGORIZED` is in the exclusion list → excluded from OpEx sum
4. **This case is handled correctly** — vacancy items are explicitly caught and excluded

---

## 7. Non-Currency Field Handling

### How the pipeline distinguishes field types

It doesn't use a unified type system. Each extraction path has its own ad-hoc handling:

**Property meta** (`ingestion_service.py:449-536`):
- Extracted via dedicated LLM prompt that asks for specific fields: `purchase_price` (float), `total_units` (int), `year_built` (int), `building_size` (int)
- The LLM returns typed JSON. Post-extraction sanity checks:
  - Purchase price < $100k → reset to 0 (line 520)
  - Purchase price < $500k AND units > 4 → reset (line 524)
  - Purchase price < $1M AND units > 10 → reset (line 528)

**Rent roll** (`normalization_service.py:663-857`):
- `unit_size` parsed with `_parse_int_robust()` (line 808) — extracts first digit sequence
- `current_rent` / `market_rent` parsed with `_parse_amount()` — handles $, commas, parentheses
- `is_vacant` determined by keyword scan of `tenant_name` and `unit_type` fields

**T12 expenses**: All amounts are currency. No non-currency fields in this path.

### Where `$` gets attached

**At render time in the frontend.** The backend stores raw numbers. Three rendering approaches in the frontend:

1. `Intl.NumberFormat("en-US", {style: "currency", currency: "USD"})` in `UnderwritingDashboard.tsx:316-322`
2. Template literal: `` `$${amount.toLocaleString()}` `` in `ExpensesVerificationWidget.tsx:468`
3. Hardcoded span: `<span>$</span><input value={amount}>` for editable fields

### Is there a field-type schema?

**No.** Everything is stored as a number. The `ExpenseCategory` enum distinguishes expense-like items from property-info items (`YEAR_BUILT`, `TOTAL_UNITS`, `PURCHASE_PRICE`), but within each category the value is just a float. There is no `{value: 1924, type: "year"}` schema. The frontend renders `$` on everything that isn't explicitly in the property-info display section.

**Example problem:** If `year_built = 1924` somehow ended up in an expense category (e.g., misclassified by LLM), it would display as "$1,924" in the expense table. The only safeguard is the LLM classifying it correctly in the first place.

---

## 8. Failure Modes Observed While Reading the Code

### Critical

1. **Cache poisons classification permanently** — `normalization_service.py:16-79`: A description mapped once (correctly or not) is cached for 30 days in Redis and indefinitely in MongoDB. If "Garage/Parking" gets classified as "Other Operating Expenses" once, it stays that way for all future deals until the cache entry expires or is manually cleared.

2. **No income/expense section awareness** — `ingestion_service.py:1075-1097`: The T12 extraction prompt says "extract all EXPENSE line items" and "also extract OTHER INCOME," but doesn't tell the LLM which section of the document each item came from. If the OM has an income table and an expense table on the same page, the LLM must infer section boundaries from layout alone.

3. **Forced reclassification requires exact substring** — `normalization_service.py:377-381`: "parking revenue" catches "Parking Revenue" but not "Garage/Parking" or "Parking" alone. The keyword lists are narrow and miss common variants.

4. **OM Primacy with sparse data** — `financial_service.py:73`: If the OM has exactly 6 expense line items, ALL other sources (complete T12, detailed P&L) are discarded. The threshold of 5 is arbitrary and too low.

### High

5. **Batch variable scoping bug** — `normalization_service.py:312`: `original_match = next((e for e in batch if ...))` references `batch` but `batch` is undefined in this scope. Should be `batches[i]` or the current iteration's batch. This likely causes silent failures where amounts aren't linked back to original raw expenses.

6. **Total line detection has no sum verification** — `financial_service.py:258-263`: If a line has "total" in its description, ALL other items in that category are dropped and the total is kept. But there's no check that the "total" amount actually equals the sum of the others. If OCR misreads "Total Repairs: $45,000" as $450,000, all individual repair items are silently dropped.

7. **Insurance amount gating is aggressive** — `normalization_service.py:532-537`: ANY insurance item > $25k is reclassified to Capital Reserves. For a 100-unit property, $25k insurance is reasonable. This rule would incorrectly exclude legitimate insurance premiums for larger properties.

8. **Year-built confusion** — `synthesis_service.py:660-667`: Extracts first 4-digit number in 1800-2030 range. A fire inspection date of "2020" could be extracted as year built instead of the actual "1965" buried deeper in the text.

### Medium

9. **Parking space detection by car brand** — `normalization_service.py:728-749`: Filters rent roll items by checking if tenant name contains "honda", "toyota", "ford", etc. A tenant named "Ford" or "Harrison Ford LLC" would have their unit excluded from the rent roll.

10. **Hardcoded unit 6/8 logic** — `normalization_service.py:757-777`: Specific logic for Units 6 and 8 that sets rent to $0 and adds comments about returning tenants. This is deal-specific code that will fire on every deal with units numbered 6 or 8.

11. **Numeric description filter is over-broad** — `normalization_service.py:220-236`: Any description that parses as a number is discarded. A legitimate expense labeled "404" (e.g., room 404 maintenance) or "911" (emergency services fee) would be silently dropped.

12. **Confidence 0.85 default everywhere** — `normalization_service.py:60,100,121,264,546`: When confidence is missing from cache or LLM response, it defaults to 0.85. This means "I have no idea" and "I'm fairly confident" look the same in the UI.

13. **`_parse_amount` swallows errors silently** — `normalization_service.py:196-197`: Returns 0.0 for any unparseable value. A legitimate expense with a garbled amount like "1O,500" (letter O instead of zero) becomes $0 with no warning.

14. **Dedup groups by enum, not by semantic meaning** — `financial_service.py:160`: If the LLM classifies "Water & Sewer" as "Utilities" for one occurrence and "Other Operating Expenses" for another (from a different document), they end up in different groups and both survive dedup → double-counted.

---

## 9. Real Failure Case Traces

### Case A: "Business/Other Taxes" appearing twice with different amounts mapping to different categories

**Setup:** Two line items from the same or different documents:
- "Business/Other Taxes" — $25,770
- "Business/Other Taxes" — $30,078

**Trace:**

1. Both descriptions are identical: `"Business/Other Taxes"`
2. `normalize_expenses_async` (line 252-268): First occurrence checked against cache. Cache miss → added to uncached batch.
3. Second occurrence: Same description string → already in `final_mapped_data_dict` (line 322). **But wait** — `final_mapped_data_dict` is keyed by description, so the second occurrence with the same description would overwrite the first's mapped data (line 322: `final_mapped_data_dict[desc] = item`).
4. In the final construction loop (line 343), both raw expenses iterate, both look up the same `final_mapped_data_dict[desc]` entry → **they get the same category.**
5. So identical descriptions CANNOT map to different categories in a single normalization run.

**The real failure scenario:** The items have **slightly different descriptions** across documents:
- From OM: `"Business/Other Taxes"` → LLM maps to "Real Estate Taxes" (because "Taxes")
- From T12: `"Business & Other Taxes"` → Different cache key → LLM maps to "General & Administrative" (because "Business" + "Other")

Both survive because: different descriptions = different cache keys = independent LLM calls = potentially different classifications. Dedup doesn't catch it because they're in different category groups.

### Case B: "Garage/Parking $10,800" appearing as both Other Income and Other Operating Expense

**Trace:**

1. Description arrives as `"Garage/Parking"`
2. Forced reclassification check (line 377): keywords are `["parking revenue", "parking income", "garage revenue", "garage income"]`. None match `"Garage/Parking"` → **no forced reclassification.**
3. Cache check: If first time → cache miss → LLM Call #3
4. LLM prompt includes description `"Garage/Parking"` and full category list. The LLM must decide:
   - Is this income (Other Income) or expense (Other Operating Expenses)?
   - Without section context ("Income" header vs "Expense" header from the source document), it's ambiguous
5. If the LLM says "Other Income" → cached as such → all future `"Garage/Parking"` items are Other Income
6. **But** if the description is slightly different across documents (e.g., `"Garage / Parking"` with spaces, or `"Parking/Garage"` reversed), each variant gets its own LLM call and potentially different classification
7. Keyword fallback (`normalization_service.py:601`): `"parking" or "garage"` → `OTHER_INCOME`. So fallback always classifies this as income. But the LLM path (which runs first for cache misses) might disagree.

**Root cause:** The system has no awareness of whether an item appeared in an income section or expense section of the source document. Classification relies entirely on the description string.

### Case C: "Vacancy $54,000" appearing in the expense verification section

**Trace:**

1. T12 extraction LLM returns `{description: "Vacancy", amount: 54000}`
2. The extraction prompt says "Extract all EXPENSE line items." The LLM includes vacancy because it appears on the T12 statement.
3. Normalization (line 394): `"vacancy"` matches the vacancy keyword list → forced to `UNCATEGORIZED`
4. Financial model: `UNCATEGORIZED` is in the exclusion list → **correctly excluded from OpEx sum**
5. **But it still appears in the verification UI** because the frontend receives ALL `StandardizedExpense` items, including uncategorized ones
6. Frontend `ExpenseRevenueList.tsx:24-39`: "Uncategorized" is not in the `revenueCategories` list → **it renders in the Expense section of the UI**

**Result:** Vacancy correctly doesn't affect the financial model, but incorrectly appears as an expense in the verification interface. An analyst seeing "Vacancy $54,000" in the expense list would reasonably think it's being counted as an operating expense (it's not, but the UI doesn't communicate this).

---

## 10. Key Files Index

### OCR Backend (`ocr-backend/app/`)

```
api/routes/documents.py    — All upload/retrieval/progress endpoints (12 routes)
services/gemini_service.py — Gemini Vision OCR wrapper; DocuMind prompt, chunk extraction, confidence parsing
services/pdf_chunking_service.py — PDF splitting; page count/size thresholds, high-density detection
services/storage_service.py — GCP Cloud Storage CRUD (upload, download, signed URLs)
tasks/document_tasks.py    — Celery orchestration: chunk dispatch, parallel processing, result aggregation
tasks/redis_progress.py    — Real-time progress tracking via Redis pub/sub; SSE event publishing
models/document.py         — MongoDB document schema (status, metadata, extracted_text)
```

### Financial Engine (`financial-engine/app/`)

```
services/ingestion_service.py      — Raw text → structured data; LLM prompts for T12/rent roll/property meta extraction
services/normalization_service.py  — Description → ExpenseCategory mapping; cache, LLM, keyword fallback, forced reclassification, rent roll normalization
services/gemini_client.py          — Gemini LLM wrapper; expense categorization prompt, structured data generation, retry/circuit breaker
services/financial_service.py      — 5-step deterministic model (GPR→EGI→NOI→DS→Returns); deduplication engine
services/synthesis_service.py      — Multi-document merging; document priority weights, metadata voting, rent roll master build
services/explainability_service.py — Audit trail construction; analyst commentary generation via LLM
services/storage_service.py        — MongoDB CRUD for deal packages and analysis results
services/excel_service.py          — Excel/PDF report generation from analysis results
models/schemas.py                  — All Pydantic models; ExpenseCategory enum (25 values), StandardizedExpense, RentRollItem, DealParameters, UnderwritingAnalysis
```

### Frontend (`ocr-frontend/`)

```
components/UnderwritingDashboard.tsx      — Main analysis display; formatCurrency(), pro forma tables, rent roll
components/ExpensesVerificationWidget.tsx — Expense verification table; confidence color coding, duplicate detection, inline editing
components/ExpenseRevenueList.tsx         — Income/expense split display; category string matching for revenue vs expense
components/DataVerificationTable.tsx      — Normalized data verification; category grouping, manual item addition
components/VerificationWidget.tsx         — Verification flow orchestrator; API calls for verify/update/remove
lib/types.ts                             — TypeScript interfaces; StandardizedExpense, NormalizedDataItem, CategoryGroup
```
