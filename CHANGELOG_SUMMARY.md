# Financial Underwriting AI — What Changed & Why

> A developer-friendly summary of all recent improvements across the Financial Engine, OCR Backend, and Frontend.

---

## TL;DR

The financial analysis pipeline was producing **inaccurate numbers** due to misclassified expenses, missing revenue items, hardcoded loan values, and two diverging code paths (single-doc vs multi-doc) that behaved differently. These changes **unify the pipeline, fix the math, add caching, and make the frontend actually show what's happening** in the financial model.

**By the numbers:** ~7,600 lines added, ~1,000 removed across 49 files. 199 new tests. 6 real deals validated end-to-end.

---

## 1. Expense Classification — Fixed & Unified

### Problem
The system had **two separate classification pipelines** — one for single-document uploads and another for multi-document packages. They used different rules, different caching, and produced different results for the same input. Items like "Garage/Parking" could be classified as an expense in one path and revenue in another.

### What We Did
- **Unified both pipelines** into a single classification path via an adapter pattern ([multi_doc_normalization_adapter.py](financial-engine/app/services/multi_doc_normalization_adapter.py)). Now both flows use `NormalizationService` with the same rules.
- **Added section-context awareness** — the classifier now knows whether a line item came from the "Income" or "Expense" section of a document, preventing misclassification of ambiguous items.
- **Merged rule sets** — combined 11 pre-classification rules from the multi-doc path with 15+ post-classification rules from the single-doc path. Includes: past-due items → Accounts Receivable, high-dollar CapEx detection, deposit routing, and permit handling.
- **Cross-classification guard** — catches items classified into a category that contradicts their source section (e.g., revenue item classified as an expense).

### Impact
Items like "Other Income" and "Reimbursements" now correctly flow into revenue instead of being dropped or miscategorized. Tested across 1,097 real line items from 6 deals — safety nets fired 12 times, all correct.

---

## 2. Caching — Two-Layer System

### Problem
Every analysis triggered fresh Gemini LLM calls to classify expenses, even for descriptions the system had seen before. This was slow (~2-4s per call) and expensive.

### What We Did
- **Two-layer cache**: Redis (fast, 7-day TTL) → MongoDB (persistent fallback) → Gemini LLM (last resort). See [normalization_service.py](financial-engine/app/services/normalization_service.py).
- **Confidence-gated writes** — only cache classifications with ≥85% confidence. Low-confidence results get re-evaluated next time.
- **Cache inspection endpoints** ([cache.py](financial-engine/app/api/routes/cache.py)) — search, view, and clear cached mappings for debugging.
- **Concurrency control** — semaphore limits concurrent Gemini calls to 10, preventing API rate limit errors.

### Impact
Repeat analyses are near-instant. First-time analysis still calls the LLM, but subsequent runs for similar properties hit cache.

---

## 3. Financial Model Fixes

### Problem
- Revenue items (Other Income, Reimbursements) were being **excluded from NOI**, making properties look less profitable.
- A **hardcoded $5M loan amount** was used regardless of actual deal parameters, producing nonsensical returns (negative equity, fake 13% IRR).
- High-vacancy deals had no model for lease-up costs.
- OM (Offering Memorandum) data could discard valid data from other sources too aggressively.

### What We Did
- **Revenue items now count toward NOI** in the financial waterfall ([financial_service.py](financial-engine/app/services/financial_service.py)).
- **Loan amount calculated from deal parameters** (65% LTV of purchase price) instead of hardcoded.
- **OM Primacy guard** — OM data only replaces other sources when it has ≥10 items covering all 5 major expense categories. Otherwise, data is merged.
- **Lease-up loss model** — high-vacancy acquisitions (>10% physical vacancy) get a distinct Year 1 NOI with per-unit downtime costs, feeding into the IRR model.
- **Management fee injection** — if no management fee is found, one is added at 4% of EGI (industry standard).
- **Deterministic scenario selection** — when an OM has multiple scenarios (Year 1, Stabilized, Pro Forma), the system picks one deterministically using a defined preference order, eliminating $25K+ run-to-run variance.

### Impact
NOI, Cap Rate, IRR, MOIC, and Cash-on-Cash are now accurate reflections of the deal, not artifacts of bugs.

---

## 4. Frontend Improvements

### Problem
The pro forma table jumped from Gross Potential Rent straight to NOI, hiding intermediate steps. Users couldn't tell how the numbers were derived. Loan amounts were wrong.

### What We Did
- **Added EGI waterfall rows** to the underwriting dashboard — Loss to Lease, Vacancy Loss, Other Income, and EGI subtotal are now visible ([UnderwritingDashboard.tsx](ocr-frontend/components/UnderwritingDashboard.tsx)).
- **Backend-calculated loan** replaces the hardcoded value.
- **Negative equity safety checks** — CoC and MOIC show meaningful values instead of blank zeros.
- **Improved tooltips** for financial metrics so users can understand what each number means.
- **Processing page UX** improvements — better progress tracking and document organization ([processing page](ocr-frontend/app/processing/[packageId]/page.tsx)).

---

## 5. Developer Tools & Observability

### What We Added
- **Re-analysis endpoint** ([dev_tools.py](financial-engine/app/api/routes/dev_tools.py)) — `POST /reanalyze/{package_id}?level=N` with 4 levels:
  - Level 1: Re-run financial model only
  - Level 2: Re-normalize + re-run model
  - Level 3: Bust normalization cache + re-normalize
  - Level 4: Full re-extract from OCR text
- **Cache inspection API** — search and clear cached classifications.
- **Centralized category-group mapping** ([category_group_mapping.py](financial-engine/app/services/category_group_mapping.py)) — single source of truth for how expense categories map to display groups.
- Gated behind `ENABLE_REANALYZE_ENDPOINTS` env flag (off in production).

---

## 6. Test Coverage

Added **199 tests** covering:

| Test File | What It Covers |
|---|---|
| `test_phase1_fixes` | Revenue filtering, OM subtotal filtering, column labeling |
| `test_phase2_fixes` | Vacancy detection, OM scenario selection |
| `test_phase2_5_fixes` | Deterministic extraction (no visual fallback when structured works) |
| `test_phase3_fixes` | Lease-up loss model, management fee injection |
| `test_tier1_fixes` | Bug fixes + cache hygiene |
| `test_tier2_cache` | Two-layer cache behavior, confidence gating |
| `test_tier3_section_context` | Section-aware classification, cross-classification guards |
| `test_tier_a_foundation` | Adapter pattern, rule-set merging |
| `test_tier_b_consolidation` | End-to-end multi-doc through unified pipeline |
| `test_normalization_keywords` | Keyword-based pre-classification rules |
| `test_ltl_vacant_fix` | Loss-to-lease and vacancy edge cases |
| `test_om_proforma_type_heuristic` | OM document type detection |

---

## Before vs After

| Area | Before | After |
|---|---|---|
| Classification paths | 2 separate, diverging | 1 unified pipeline |
| Cache | None (LLM every time) | Redis + MongoDB, 7-day TTL |
| Revenue in NOI | Dropped silently | Included correctly |
| Loan amount | Hardcoded $5M | Calculated from deal (65% LTV) |
| Pro forma transparency | GPR → NOI (black box) | Full EGI waterfall visible |
| OM data handling | All-or-nothing replacement | Guarded merge (≥10 items, 5 categories) |
| High-vacancy deals | Same model as stabilized | Lease-up loss Year 1 model |
| Run-to-run consistency | $25K+ variance possible | Deterministic scenario selection |
| Test coverage | Minimal | 199 targeted tests |
| Re-analysis | Re-upload required | 4-level re-analysis API |

---

## Files Removed
- `financial-engine/app/services/gemini_service.py` — dead code, replaced by `gemini_client.py`.
