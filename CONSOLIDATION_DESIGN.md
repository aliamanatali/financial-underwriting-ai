# Pipeline Consolidation Design

**Date:** 2026-04-18 | **Status:** Design for review. No implementation.

---

## 1. Target Architecture

**One classification service, two extraction adapters, shared everything else.**

The OM vs non-OM distinction is a document-format concern, not a classification or financial-model concern. The branch belongs at the extraction layer only. Everything downstream — classification, post-processing, caching, dedup, financial model — should be the same code path regardless of input source.

```
                    +-----------------+
                    |  Document Input |
                    +--------+--------+
                             |
              +--------------+--------------+
              |                             |
     +--------v--------+          +--------v--------+
     | OM Proforma      |          | Generic Financial|
     | Adapter           |          | Adapter          |
     | (structured tables)|        | (PDF/Excel/CSV)  |
     +--------+--------+          +--------+--------+
              |                             |
              |  {description, amount,      |
              |   section_context,          |
              |   source_snippet, ...}      |
              +--------------+--------------+
                             |
                    +--------v--------+
                    | NormalizationSvc |  <-- single service
                    | (cache, LLM,    |
                    |  guard, reclass) |
                    +--------+--------+
                             |
                    +--------v--------+
                    | FinancialService |
                    | (dedup, model)   |
                    +--------+--------+
```

**Foundation: build on `NormalizationService` and retire `MultiDocumentExtractionService.normalize_expenses_batch`.**

Rationale:
- `NormalizationService` has the more complete feature set: caching (Redis + MongoDB), confidence gating, section_context awareness, cross-classification guard, per-unit insurance scaling, forced reclassification rules.
- `MultiDocumentExtractionService.normalize_expenses_batch` has a separate LLM prompt, no cache, no guard, no forced reclassification. Its one advantage — the `type`/`subtype` field from extraction — maps directly to `section_context` and can be passed through.
- We do NOT start a new service. `NormalizationService` is the classification engine; the multi-doc extraction service keeps its extraction adapters but loses its normalization step.

**Retire `GeminiService`, keep `GeminiClient`.** `GeminiService` is a 69-line text-only wrapper. `GeminiClient` has caching, retry with exponential backoff, structured data generation, multimodal support, and streaming. Both are injected as the same dependency (`get_gemini_service()` already returns `GeminiClient`). The multi-doc flow already receives a `GeminiClient` at runtime due to the dependency injection — the `GeminiService` type annotation is stale.

---

## 1b. The Extraction-to-Normalization Adapter

The consolidated design introduces an adapter function that sits between extraction output and `NormalizationService`. This component didn't exist in the original design and is necessary because the two pipelines have different pre-classification and post-classification rule positions.

### Inputs

Raw extraction dicts from either adapter source, shaped like:
```python
{
    "raw_text": "Garage / Parking",
    "amount": 10800,
    "type": "revenue",           # from extraction LLM or OM heuristic
    "subtype": "other_income",   # from extraction LLM
    "page_number": 5,
    "bbox": [100, 200, 300, 400],
    "source_document": "OM_Leroy.pdf",
    "document_id": "abc123",
    "expense_year": 2024,
    "text_type": "Computerized",
    "amount_t3": null, "amount_t6": null, "amount_t9": null
}
```

### Outputs

Dicts shaped for `NormalizationService.normalize_expenses_async`:
```python
{
    "description": "Garage / Parking",    # mapped from raw_text
    "amount": 10800,
    "section_context": "income",          # mapped from type
    "source_snippet": null,               # carried through if present
    "page_number": 5,
    "bbox": [100, 200, 300, 400],
    "source_document": "OM_Leroy.pdf",
    "document_id": "abc123",
    "expense_year": 2024,
    "amount_t3": null, "amount_t6": null, "amount_t9": null
}
```

Plus, after `NormalizationService` returns `List[StandardizedExpense]`, the adapter converts each result to a `NormalizedDataItem` for the multi-doc verification UI, deriving `category_group` from the `ExpenseCategory → CategoryGroup` mapping constant.

### Responsibilities

**1. Pre-classification cleanup (from multi-doc's `_validate_and_fix_extraction`):**

| Rule | Adapter action | NormSvc safety net |
|------|---------------|-------------------|
| Student blacklist | Set `type="other"` → `section_context="unknown"` | Existing forced-reclass → `CAPITAL_RESERVES` (line 521) |
| Past due → receivable | Change `type` to "receivable" → `section_context="unknown"` | **Port:** past-due keywords → `ACCOUNTS_RECEIVABLE` |
| Late fees subtype | Set `subtype="late_fee"` (hint for LLM) | None needed |
| Parking/laundry subtype | Set `subtype="other_income"` (hint for LLM) | Existing forced-reclass for "parking revenue" etc. (line 498) |
| Reimbursement subtype | Set `subtype="reimbursement"` (hint for LLM) | None needed |
| CapEx keywords | Change `type` to "capex" → `section_context="capex"` | Existing capex keyword forced-reclass (line 532) |
| High-dollar CapEx | Change `type` based on amount + keyword → `section_context="capex"` | **Port:** amount > $5k + keyword → `CAPITAL_RESERVES` |
| Permit fees (qualified) | Change `type` to "capex" → `section_context="capex"` | Narrow existing "permit" keyword (line 538) |
| Deposits | Change `type` to "property_info" → filtered pre-normalization | **Port:** deposit keywords → `DEPOSIT` |
| Rent subtype | Set `subtype="rent"` (hint for LLM) | Existing "rental income" → `GROSS_POTENTIAL_RENT` (line 490) |
| Total line suppression | Delete item (don't pass to NormSvc) | Existing global total suppression (line 584) |

**2. Field mapping:** `raw_text` → `description`, `type` → `section_context` (revenue→income, expense→expense, capex→capex, else→unknown).

**3. Post-normalization conversion:** `StandardizedExpense` → `NormalizedDataItem`, using the `ExpenseCategory → CategoryGroup` mapping constant.

**4. Metadata propagation:** `source_document`, `document_id`, `page_number`, `bbox`, `text_type`, `expense_year`, trailing-period amounts — all carried from extraction dict through to `NormalizedDataItem.metadata`.

### `ExpenseCategory → CategoryGroup` mapping constant (new, shared)

```python
CATEGORY_TO_GROUP: Dict[ExpenseCategory, CategoryGroup] = {
    # Revenue
    ExpenseCategory.GROSS_POTENTIAL_RENT: CategoryGroup.REVENUE,
    ExpenseCategory.OTHER_INCOME: CategoryGroup.REVENUE,
    ExpenseCategory.REIMBURSEMENTS: CategoryGroup.REVENUE,
    # Balance sheet
    ExpenseCategory.ACCOUNTS_RECEIVABLE: CategoryGroup.OTHER,
    # Tax & Insurance
    ExpenseCategory.REAL_ESTATE_TAXES: CategoryGroup.TAX_INSURANCE,
    ExpenseCategory.INSURANCE: CategoryGroup.TAX_INSURANCE,
    # Capital
    ExpenseCategory.CAPITAL_RESERVES: CategoryGroup.CAPITAL_EXPENDITURE,
    # Debt
    ExpenseCategory.CURRENT_LOAN_BALANCE: CategoryGroup.DEBT,
    # Property Info
    ExpenseCategory.PURCHASE_PRICE: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.DEPOSIT: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.PRICE_PER_UNIT: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.TOTAL_UNITS: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.YEAR_BUILT: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.PROPERTY_INFO: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.PHYSICAL_CONDITION: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.PROPERTY_NAME: CategoryGroup.PROPERTY_INFO,
    ExpenseCategory.PROPERTY_ADDRESS: CategoryGroup.PROPERTY_INFO,
    # Other
    ExpenseCategory.UNCATEGORIZED: CategoryGroup.OTHER,
}
# All remaining ExpenseCategory values default to CategoryGroup.OPERATING_EXPENSE
```

### Minor behavior change to document

Multi-doc's fallback confidence was 0.5 (line 1206 in `normalize_expenses_batch`). Post-consolidation, fallback confidence is 0.65 (`NormalizationService._fallback_simple_mapping`). This is a minor change — both indicate low confidence — but should be noted in release documentation.

---

## 2. Which Pipeline Wins at Each Layer

| Layer | Keep | Retire | Justification |
|-------|------|--------|---------------|
| **Gemini wrapper** | `GeminiClient` | `GeminiService` | GeminiClient has caching, retries, multimodal, streaming. GeminiService is a subset. Multi-doc already receives GeminiClient at runtime via DI. |
| **Extraction (OM)** | `MultiDocExtractionSvc.extract_om_proforma_from_pdf` + `_convert_om_proforma_to_expenses` | N/A | This is the only code that understands OM proforma structure. Keep it, but map its `type` field to `section_context` at output. |
| **Extraction (generic)** | `MultiDocExtractionSvc.extract_from_visual_document` + `_get_financial_extraction_prompt` | `IngestionService.ingest_financials_from_pdf` | Multi-doc's extraction prompt returns richer metadata (page_number, bbox, type, subtype, text_type). Single-doc's prompt is simpler. Keep multi-doc's prompt but add `section_context` and `source_snippet` from Tier 3. |
| **Extraction (Excel)** | `MultiDocExtractionSvc.extract_from_excel` | `IngestionService.extract_rent_roll_from_excel` | Multi-doc handles P&L sheets; single-doc only handles rent rolls. |
| **Post-extraction validation** | `MultiDocExtractionSvc._validate_and_fix_extraction` | Merge into `NormalizationService` forced-reclassification | Multi-doc has 11 rules; NormalizationService has ~15. Significant overlap (vacancy, capex, student data, deposits). Merge the union, deduplicate. |
| **Classification (LLM)** | `GeminiClient.map_expenses_to_categories_async` (via `NormalizationService`) | `MultiDocExtractionSvc.normalize_expenses_batch` | NormalizationService has caching, confidence gating, section_context prompt. Multi-doc's batch normalize goes to LLM raw every time with no cache. |
| **Post-classification guard** | `NormalizationService` cross-classification guard (Tier 3.4) | N/A (multi-doc has nothing equivalent) | Multi-doc trusts the LLM output blindly. The guard catches income/expense mismatches. |
| **Cache** | `NormalizationService` Redis+MongoDB cache (Tier 2) | N/A (multi-doc has no cache) | Every multi-doc LLM call is a fresh round-trip. Caching identical descriptions across deals saves latency and cost. |
| **Dedup (pre-analysis)** | `synthesis_service.deduplicate_expenses` | N/A | Hash-based cross-document dedup. Complements `financial_service._deduplicate_expenses` (category-level dedup). Both run. |
| **Dedup (in analysis)** | `financial_service._deduplicate_expenses` | N/A | Already shared. Tier 1.4 improvements apply to both flows. |
| **Financial model** | `FinancialService` (all of it) | N/A | Already shared. No changes needed. |

---

## 3. Tier 1-3 Improvements in Consolidated Design

| Improvement | Where it lands | Obsolete? |
|-------------|---------------|-----------|
| 1.1 Batch scoping fix | `NormalizationService.normalize_expenses_async` — now the only classification path. Applies to all deals. | No |
| 1.2 Unit 6/8 removal | `NormalizationService.normalize_rent_roll` — already the only rent roll normalizer multi-doc would use. But multi-doc currently has its own rent roll handling via `process_rent_roll_documents`. Needs wiring. | No, but needs adapter |
| 1.3 Insurance scaling | `NormalizationService.normalize_expenses_async` — now receives all deals' expenses. `total_units` must be passed from multi-doc context. | No |
| 1.4 OM Primacy | `financial_service._deduplicate_expenses` — already shared. | No |
| 2.1 Redis TTL | `NormalizationService` cache — now used by all deals. | No |
| 2.2 Confidence gating | Same. Low-confidence multi-doc classifications will no longer be cached either. | No |
| 2.3 Cache endpoints | Same. Now useful for diagnosing multi-doc deals too. | No |
| 2.4 Cache key migration | The `mapping:{desc}:{section_context}` format carries forward. Old-format keys expire naturally. | **Yes after 30 days** — can be removed once TTL window passes |
| 2.5 Cache invalidation | Already shared (verify endpoint calls it). Now the invalidated entries are read by multi-doc deals too. | No |
| 3.1 Extraction prompt | Multi-doc's `_get_financial_extraction_prompt` gets `section_context` + `source_snippet` added (equivalent to what was done in `ingestion_service.py`). | No — needs porting |
| 3.2 Schema fields | `StandardizedExpense.section_context` and `source_snippet` — now populated by all extraction paths. | No |
| 3.3 Classification prompt | `map_expenses_to_categories_async` — now the only classification prompt. Section_context guidance applies to all deals. | No |
| 3.4 Cross-classification guard | Fires on all deals. Multi-doc items with `type="revenue"` mapped to `section_context="income"` will be guarded. | No |
| 3.5 Cache key with context | `mapping:{desc}:{section_context}` — OM items get context-specific cache; non-OM items with `type` mapped to context get it too. | No |

---

## 4. Gaps in the Multi-Doc Pipeline (Unaudited Until Now)

**Top 10 issues found during audit:**

1. **Duplicate `_extract_from_text_with_llm` method** (lines 167-216 and 325-396). Two implementations, slightly different retry logic. The second has retries; the first doesn't. Dead code risk.

2. **No section_context in extraction prompt** (line 218-323). The extraction prompt returns `type` but doesn't ask for `section_context`. The `type` field is determined by the LLM based on content, not document position. Adding `section_context` (or mapping `type` → `section_context`) is the Tier 3 port.

3. **No classification cache.** Every `normalize_expenses_batch` call (line 1180) is a fresh LLM round-trip. 2715 Dwight Way's 549 items = 549 items classified with no caching. Same "Property Insurance" description classified independently every time.

4. **Revenue items silently dropped at line 2150.** The `historical_expenses` filter excludes `category_group == "Revenue"`. Items correctly classified as Other Income (Parking, Laundry) never reach `financial_service.calculate_historical()`, causing `other_income = $0`. This is the root cause of the Keystone and 2715 Dwight anomaly.

5. **OM proforma `type` assignment uses keyword heuristics** (line 1419-1432). "Garage / Parking" doesn't match any revenue keyword ("income", "rent", "revenue", "reimbursement") → defaults to `type="expense"`. This is the exact failure case that section_context solves.

6. **Contextual verification agent can silently exclude items** (line 1754). AI-verified items marked "non-beneficial" are removed from the final list. No user notification, no audit log entry for the exclusion.

7. **Excel P&L detection by filename keyword** (line 579). If the filename doesn't contain "statement", "p&l", or "pnl", the P&L parsing path doesn't trigger and the file gets a single aggregated entry instead of line items.

8. **Fiscal year filtering is document-level** (lines 1930-1951). If a T12 PDF has mixed-year columns, the entire document is included or excluded based on its `max_year`. Item-level year filtering (which `financial_service._deduplicate_expenses` does) is more granular but runs too late.

9. **OM synthetic unit numbers** (lines 1587-1603). When expanding OM rent roll items with count > 1, generates pseudo-IDs like "OM-1-1". Could collide with real unit numbers.

10. **No insurance limit detection.** Multi-doc has no equivalent of Tier 1.3's insurance scaling. A $1M coverage limit classified as "Insurance" by the LLM flows through unquestioned.

---

## 5. Migration Path

**Incremental, feature-flagged, three phases.**

### Phase 1: Dead-code and type-annotation cleanup (zero risk, no behavioral change)

`get_gemini_service()` in `dependencies.py:17` already returns `GeminiClient()`. The multi-doc route at `multi_document.py:368` annotates the dependency as `GeminiService` but receives a `GeminiClient` at runtime. `MultiDocumentExtractionService` only calls `generate_content_async()`, which both classes implement, so the mismatch is invisible at runtime.

Phase 1 is housekeeping: remove the `GeminiService` class, update type annotations, delete any dead imports. **This ships no improvement** — it removes confusion for future maintainers and clears the path for Phase 2.

**Rollback:** Revert the annotation. Zero functional change (it was already working via duck typing).

### Phase 2: Route multi-doc classification through NormalizationService (medium risk)

Replace `MultiDocumentExtractionService.normalize_expenses_batch()` call at `multi_document_extraction_service.py:1976` with the extraction-to-normalization adapter (Section 1b) calling `NormalizationService.normalize_expenses_async()`. This is the only call site — `normalize_expense_category` (line 1220) is dead code.

Deliverables:

1. **Adapter function** implementing Section 1b: pre-classification cleanup, field mapping, `NormalizationService` call, post-normalization conversion to `NormalizedDataItem`.

2. **`ExpenseCategory → CategoryGroup` mapping constant** (Section 1b) as a shared constant in `schemas.py` or a utility module.

3. **Three NormSvc safety-net additions** (ports from multi-doc rules that need post-classification backup):
   - Past-due keywords → `ACCOUNTS_RECEIVABLE`
   - High-dollar CapEx (amount > $5k + keyword) → `CAPITAL_RESERVES`
   - Deposit keywords → `DEPOSIT`

4. **Permit keyword narrowing** in NormSvc: change bare "permit" in `capex_keywords` to qualified "permit" + capital-work qualifier, matching multi-doc's rule 8.

5. **`ExpenseCategory.DEPOSIT` added to the OpEx exclusion list** at `financial_service.py:425-438`.

6. **BATCH_SIZE tuning**: raise from 25 to 100 for the multi-doc path (Phase 2a, can ship independently).

7. Pass `total_units` from the package's synthesized property metadata.

**Feature flag:** Add `use_consolidated_normalization: bool = True` to the normalize endpoint. When `False`, falls back to the old `normalize_expenses_batch` path. Remove flag once validated on 5+ deals.

**Rollback:** Flip the flag to `False`. Old path still exists.

### Phase 3: Fix the revenue-item filter (high impact, requires frontend awareness)

Change `multi_document.py:2150` to include `"Revenue"` in the category_group filter:
```python
if item.category_group in ["Operating Expense", "Tax & Insurance", "Revenue"]:
```

This lets Other Income items (Parking, Laundry) flow into `historical_expenses`, where `financial_service.calculate_historical` already sums `OTHER_INCOME` items into `analysis.other_income` (line 410-413).

**Risk:** The frontend's expense verification UI shows `historical_expenses`. Adding Revenue items to it means Parking/Laundry/Reimbursements will appear in the "Expenses" verification table. The frontend's `ExpenseRevenueList.tsx` already splits items by category string, so they'd render in the Revenue tab. But `DataVerificationTable.tsx` might not expect Revenue items in the expense list. Needs frontend testing.

**Rollback:** Revert the filter change. Revenue items go back to being dropped.

**Pre-ship consideration: retroactive incorrectness of stored analyses.** The `category_group in ["Operating Expense", "Tax & Insurance"]` filter has been in production since the multi-doc flow launched. Every stored analysis for a deal with ancillary revenue (parking, laundry, storage, pet fees) has `other_income = $0` when it should have a non-zero value. This affects both OM-driven deals (confirmed: Keystone `other_income = $0` despite $17,166 in parking + laundry) and non-OM deals (confirmed: 2715 Dwight `other_income = $0` despite 26 revenue items in `financials_data`).

Shipping Phase 3 means:
- New analyses will correctly include Other Income, producing different NOI and return metrics than prior runs of the same deal.
- Existing stored analyses are retroactively known to be wrong — they understate EGI, overstate the expense ratio, and understate returns.
- If any analyst or investor relied on the `other_income = $0` figure in a previously delivered report, the corrected number will differ.

This is a **customer-facing question** that should be surfaced before ship: does the team want to (a) re-run all existing analyses after Phase 3 deploys, (b) only apply the fix to new analyses going forward, or (c) notify analysts that prior reports understated Other Income? The code change itself is one line, but the business impact needs a decision.

---

## 6. Risks

1. **Multi-doc's `_validate_and_fix_extraction` and NormalizationService's forced-reclassification overlap but aren't identical.** The multi-doc service has past-due/receivable handling, pending-expense detection, and deposit reclassification that NormalizationService lacks. If we retire `normalize_expenses_batch` without porting these rules, receivables could be classified as revenue and deposits as expenses. **Mitigation:** Merge the union of both rule sets into NormalizationService before switching.

2. **Cache behavior changes for multi-doc deals.** Currently, every multi-doc classification is a fresh LLM call. After consolidation, repeated descriptions get cache hits. This is faster and cheaper but means a bad classification on Deal A poisons Deal B. Tier 2's confidence gating (don't cache < 0.85) and 7-day TTL mitigate this, but it's a behavioral change that needs monitoring. **Mitigation:** Log cache hit/miss rates for the first 10 consolidated deals.

3. **The multi-doc document priority logic at `multi_document.py:500-512` silently zeroes out non-OM documents when an OM exists.** This is upstream of classification — consolidation doesn't change it. But it means OM-flow deals will only have OM-extracted items in the classification pipeline. If the OM extraction misses items that a T12 would have caught, they're gone. **This is pre-existing, not a consolidation risk**, but worth documenting because analysts may expect T12 data to appear even when an OM is present.

4. **`normalize_expenses_async` expects `{description, amount}` dicts. Multi-doc extraction returns `{raw_text, amount, type, subtype, page_number, bbox, ...}`.** The field name mapping (`raw_text` → `description`) is trivial but must be exact. If any extraction path returns a field under a different name (e.g., `text` vs `raw_text`), items silently get empty descriptions and fall through to the numeric-description filter. **Mitigation:** Add a thin adapter function that validates required fields before calling normalize.

5. **Batch size mismatch — quantified.** NormalizationService uses BATCH_SIZE=25 for LLM calls. Multi-doc sends all items at once.

   Measured on 2715 Dwight Way (549 total items, 234 classifiable, 160 unique descriptions):

   | Scenario | LLM calls | Items per call | Cache hits |
   |----------|----------:|---------------:|-----------:|
   | Pre-consolidation (multi-doc) | 1 | 234 | 0 (no cache) |
   | Post-consolidation, BATCH_SIZE=25, cold cache | 7 | 25 | 74 (32%) |
   | Post-consolidation, BATCH_SIZE=100, cold cache | 2 | 100 | 74 (32%) |
   | Post-consolidation, warm cache (2nd run) | 0 | — | 234 (100%) |

   Measured on Keystone (116 total items, 66 classifiable, 32 unique):

   | Scenario | LLM calls | Cache hits |
   |----------|----------:|-----------:|
   | Pre-consolidation | 1 | 0 |
   | Post, BATCH_SIZE=25, cold | 2 | 34 (52%) |
   | Post, BATCH_SIZE=100, cold | 1 | 34 (52%) |

   At BATCH_SIZE=25, a complex non-OM deal goes from 1 LLM call to 7, but with 3-concurrent semaphore that's ~3 serial round-trips. At BATCH_SIZE=100, it's 2 calls (effectively 1 serial round-trip).

   **There is no technical reason BATCH_SIZE can't be raised to 100** for the multi-doc path. The LLM context window can handle 100 `{description, amount, section_context}` items easily. The 25-item limit was chosen for the single-doc path where total items are typically 10-15. For multi-doc consolidation, raising to 100 is a sensible Phase 2a tuning before Phase 2 proper.

   **On second and subsequent runs of any deal**, the cache eliminates all LLM calls entirely. This is a permanent speedup that multi-doc currently lacks.

   **Note:** The 32% (2715 Dwight) and 52% (Keystone) hit rates are intra-deal on cold cache — repeated descriptions within a single deal's documents. Inter-deal cache hit rate (how often Deal B benefits from Deal A's cached classifications) is unknown and should be measured after the first 10 consolidated deals ship.

6. **Multi-doc's `normalize_expenses_batch` prompt returns `category` and `group` (e.g., "Real Estate Taxes" + "Tax & Insurance"). NormalizationService's `map_expenses_to_categories_async` returns `mapped_category` only (an `ExpenseCategory` enum value).** The `category_group` that multi-doc uses for the line 2150 filter comes from the normalization, not the extraction. After consolidation, `category_group` will need to be derived from the `ExpenseCategory` enum rather than returned by the LLM. **This is straightforward** — the mapping already exists in `_fallback_categorization` — but must be wired up.

---

## 7. Rule-Set Merge Inventory

Side-by-side comparison of `MultiDocExtractionSvc._validate_and_fix_extraction` (pre-classification, operates on raw `type` field) and `NormalizationService` forced-reclassification (post-classification, operates on `ExpenseCategory` enum).

### Where the rules hook in

- **Multi-doc rules** fire BEFORE the LLM classification call. They modify the `type`/`subtype` fields that the LLM sees as hints. They operate on raw extraction output.
- **NormalizationService rules** fire AFTER the LLM classification returns. They override the LLM's `mapped_category` based on keyword checks. They operate on the `description` string.

This distinction matters: some rules are better as pre-classification hints (they inform the LLM) and some are better as post-classification overrides (they correct the LLM). The merged design should preserve both hook points.

### Rule comparison

| # | Rule | Multi-doc (`_validate_and_fix`) | NormalizationSvc (forced reclass) | Overlap | Merge action |
|---|------|:----:|:----:|---------|-------------|
| 1 | **Student/tuition blacklist** | line 998: sets `type="other"` | line 521: forces `CAPITAL_RESERVES` | **Partial** — same trigger keywords, different outcome. Multi-doc keeps item as "other" (effectively ignored). NormSvc routes to CapReserves (excluded from NOI). | Keep NormSvc behavior (CapReserves). More explicit exclusion from NOI. |
| 2 | **Past due → receivable** | line 1011: changes `type` from "revenue" to "receivable" | *Not present* | **Multi-doc only** | **Port to NormSvc.** Add forced reclass: if description contains past-due keywords, force to `ACCOUNTS_RECEIVABLE`. Hook: post-classification. |
| 3 | **Late fees → other_income subtype** | line 1018: sets `subtype="late_fee"` (keeps type="revenue") | *Not present* | **Multi-doc only** | No port needed. This sets a subtype hint for the LLM. In consolidated flow, the LLM prompt's section_context guidance handles this: revenue-section items with "late fee" in description → Other Income. |
| 4 | **Parking/laundry/garage → other_income subtype** | line 1024: sets `subtype="other_income"` (keeps type="revenue") | line 498: forces `OTHER_INCOME` if description contains "parking revenue", "garage income", etc. | **Partial** — multi-doc sets subtype (hint); NormSvc forces category (override). NormSvc's keyword list requires the full phrase ("parking revenue") while multi-doc matches bare "parking". | Keep both. Multi-doc's subtype setting becomes section_context mapping pre-classification. NormSvc's forced reclass catches cases where LLM ignores the hint. |
| 5 | **Utility reimbursements** | line 1030: sets `subtype="reimbursement"` | *Not present* | **Multi-doc only** | No port needed. Subtype hint for LLM classification. |
| 6 | **CapEx detection (specific keywords)** | line 1036: "electrical upgrade", "roof replacement", etc. → `type="capex"` | line 532: "roofing", "renovation", "hvac replacement", etc. → `CAPITAL_RESERVES` | **Substantial overlap, different keyword lists.** Multi-doc has: elevator modernization, cylinder replacement, retaining wall, seismic, panel upgrade, new service. NormSvc has: well drilling, guard rail, staircase, shingles, asphalt, paving, architect, engineering. | Merge the union. NormSvc's post-classification position is better (corrects LLM mistakes). Add multi-doc's unique keywords to NormSvc's `capex_keywords` list. |
| 7 | **High-dollar CapEx heuristic** | line 1042: "proposal", "modernization", "replacement" + amount > $5k → `type="capex"` | *Not present* | **Multi-doc only** | **Port to NormSvc** as a post-classification check. If description contains proposal/modernization/replacement AND amount > $5k AND category is an OpEx category, force to `CAPITAL_RESERVES`. Hook: post-classification (needs amount, which is available). |
| 8 | **Permit fees for capital work** | line 1050: "permit" + capital keywords → `type="capex"` | line 538: "permit" in general capex_keywords list (no qualifier) | **Conflict.** Multi-doc only reclassifies permits with capital qualifiers. NormSvc reclassifies ALL permits. | Keep multi-doc's narrower rule. NormSvc's "permit" without qualifier is too broad — a $200 building permit for a minor repair shouldn't be CapEx. **Narrow NormSvc's rule** to match. |
| 9 | **Deposits/earnest money → property_info** | line 1056: deposit, earnest money, escrow → `type="property_info"` | line 553: "security deposit", "tenant deposit" → `UNCATEGORIZED` | **Partial overlap, different targets.** Multi-doc routes to property_info. NormSvc routes to UNCATEGORIZED. Neither is ideal — deposits are balance sheet items. | Standardize: force to `DEPOSIT` (existing `ExpenseCategory.DEPOSIT` at `schemas.py:67`). **Required co-change:** add `ExpenseCategory.DEPOSIT` to the OpEx exclusion list at `financial_service.py:425-438` — it is currently absent, meaning any deposit classified as DEPOSIT would count toward operating expenses. This must ship as part of the rule merge, not after. |
| 10 | **Rent subtype fallback** | line 1063: bare "rent" → `subtype="rent"` | line 490: "rental income", "rent income" → `GROSS_POTENTIAL_RENT` | **Partial.** Multi-doc hints to LLM. NormSvc forces category. | Keep both. Different hook points, complementary. |
| 11 | **Total line suppression** | line 1068: "total charges", "total due", etc. → skip (delete) | line 584: "total operating expenses", "total expenses" → skip | **Different targets.** Multi-doc catches utility bill totals. NormSvc catches global expense summaries. | Merge both. Utility bill totals and global expense summaries both need suppression. NormSvc's hook (post-classification) is fine for this. |
| 12 | **Liability/debt detection** | *Not present* | line 473: "loan balance", "mortgage payable" → `CURRENT_LOAN_BALANCE` | **NormSvc only** | Keep as-is. |
| 13 | **Debt service (principal/interest)** | *Not present* | line 480: "current principal" → `CURRENT_LOAN_BALANCE`, "current interest" → `UNCATEGORIZED` | **NormSvc only** | Keep as-is. |
| 14 | **Revenue mapping (rental income)** | *Not present* (handled by `type` field) | line 489: "rental income" → `GROSS_POTENTIAL_RENT` | **NormSvc only** | Keep as-is. In consolidated flow, `section_context="income"` + LLM should handle this, but the forced reclass is a safety net. |
| 15 | **Payroll mapping** | *Not present* | line 505: "onsite manager", "building superintendent" → `PAYROLL` | **NormSvc only** | Keep as-is. |
| 16 | **Vacancy/concessions exclusion** | *Not present* | line 516: "vacancy", "concession", "bad debt" → `UNCATEGORIZED` | **NormSvc only** | Keep as-is. |
| 17 | **Non-operating items** | *Not present* | line 552: "depreciation", "amortization", "security deposit" → `UNCATEGORIZED` | **NormSvc only** | Keep as-is. |
| 18 | **Document title exclusion** | *Not present* | line 570: "profit & loss", "balance sheet" + file extension or > $1M → skip | **NormSvc only** | Keep as-is. |
| 19 | **Assessed value exclusion** | *Not present* | line 597: "net taxable value", "assessed value" → skip (unless real assessment) | **NormSvc only** | Keep as-is. |
| 20 | **Insurance scaling** | *Not present* | line 648: per-unit ceiling, limit/coverage keyword check | **NormSvc only (Tier 1.3)** | Keep as-is. |
| 21 | **Cross-classification guard** | *Not present* | line 675: section_context vs mapped_category conflict → UNCATEGORIZED | **NormSvc only (Tier 3.4)** | Keep as-is. |

### Rules needing a different hook point

**Rule 7 (high-dollar CapEx heuristic)** needs the `amount` field, which is available in the forced-reclassification chain (it's on the raw expense dict). No hook-point change needed — it fits naturally alongside the existing capex keyword check at NormSvc line 532.

**Rule 2 (past-due → receivable)** needs to force a category (`ACCOUNTS_RECEIVABLE`) that is currently in the ExpenseCategory enum but has no forced-reclassification rule. It fits at the same hook point as the liability detection (NormSvc line 473). No architectural change.

**Rule 8 (permit narrowing)** requires modifying NormSvc's existing `capex_keywords` list to remove bare "permit" and add the qualified version. This is a keyword edit, not a hook-point change.

### Summary

- **6 rules are NormSvc-only** (12-21). Keep as-is.
- **3 rules are multi-doc-only and need porting** (2, 7, and the utility-total part of 11).
- **4 rules overlap** (1, 4, 6, 8). Merge to NormSvc's versions, absorbing multi-doc's unique keywords.
- **3 rules are multi-doc subtype hints** (3, 5, 10). No port needed — they become `section_context` mapping in the consolidated flow.
- **1 rule has a conflict** (8, permits). Narrow NormSvc's rule to match multi-doc's qualified version.
- **1 rule has a destination disagreement** (9, deposits). Standardize to `DEPOSIT` category.

---

## 8. Intentional Behavior Changes (Tier B Validation)

**Loss to Lease / Vacancy:** Legacy classifies both as `Gross Potential Rent` (a revenue category with negative amount). Consolidated forces both to `Uncategorized` via the "loss to lease" and "vacancy" keyword checks in NormalizationService. Both paths exclude these from OpEx — GPR and UNCATEGORIZED are both in the exclusion list at `financial_service.py:425`. The financial effect is identical. The semantic difference is that consolidated explicitly marks them as "not an operating category" rather than lumping them with GPR.

**Business / Other Taxes caching note:** Gemini consistently classifies "Business / Other Taxes" as Real Estate Taxes at confidence 0.90. This is above the Tier 2 cache threshold (0.85), so the classification will be cached and served to future deals. The 0.80 confidence observed in earlier runs was run-to-run variance. Both RE Tax and G&A are OpEx categories, so the financial effect is minimal, but the classification is not semantically ideal (Business Taxes are closer to G&A). Logged as Tier D ticket.

---

## 9. Tier D Tickets

| # | Title | Source | Status |
|---|-------|--------|--------|
| D1 | ~~Expand OM proforma summary-line filter to catch subtotals~~ | Tier B equivalence test | **Resolved** — Phase 1 Fix 2 |
| D2 | Multi-source items with identical raw_text lose source attribution in adapter's raw_by_desc lookup | Tier B adapter trace (8% of 2715 Dwight items affected) | Open |
| D3 | ~~Refine Business/Other Taxes classification via prompt tuning~~ | Tier B equivalence test | **Resolved** — Phase 3 Fix 3 |
| D4 | Apply structured parsing to OM property meta fields (purchase_price, year_built, total_units) instead of LLM extraction | Phase 3 validation — OM key data extraction is nondeterministic; purchase_price appeared on some runs but not others, causing cap rate to jump from 0% to 5.72% between identical code runs. Same class of issue Phase 2.5 solved for expenses. | Open |

---

## 10. Status: Shipped in Tier C

**Shipped:** 2026-04-18

**Test count at cutover:** 129 passed, 0 failed (7 pre-existing `test_sensitivity_analysis.py` failures excluded, unchanged since Tier 1).

**Legacy code deleted:**
- `MultiDocumentExtractionService.normalize_expenses_batch` — the legacy LLM classification function
- `MultiDocumentExtractionService._legacy_normalize_expenses` — the Tier B fallback wrapper
- `MultiDocumentExtractionService._fallback_categorization` — the keyword fallback for multi-doc
- `GeminiService` class (`gemini_service.py`) — retired in Tier A
- Feature flag `use_consolidated_normalization` — removed from `config.py`
- Debug comparison endpoint `POST /api/v1/debug/compare-normalization/{package_id}` — no longer needed

**Validation data:** See [TIER_B_5_OBSERVATION.md](TIER_B_5_OBSERVATION.md) — 6 real deals processed through both paths, 12 safety-net triggers (100% correct), 0 regressions.

**Tier D tickets remain open:** D1 (subtotal filter), D2 (source attribution), D3 (Business/Other Taxes refinement). These are scoped for future work.
