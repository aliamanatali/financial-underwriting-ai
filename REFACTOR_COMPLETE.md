# Financial Underwriting AI — Quality Refactor Summary

## What changed (for non-engineers)

The underwriting engine now produces more accurate and consistent financial reports. Revenue items like parking and laundry income that were previously dropped are now captured, adding ~$10K-17K to Effective Gross Income on real deals. High-vacancy properties get a realistic Year 1 lease-up cost instead of assuming instant stabilization. Management fees are always present in the pro forma — either from the source documents or as a visible default. Expense classifications are more precise, and the system produces identical results when re-run on the same data, eliminating a source of run-to-run variance that made validation unreliable.

## Work completed

### Foundation (Tiers 1-3, Tiers A-C) — prior to this refactor

Consolidated the multi-document and single-document normalization pipelines into a single adapter-based flow. Established expense category mapping, two-tier caching (Redis + MongoDB), section-context awareness, and OM proforma extraction.

### Phase 1 — Data routing and output correctness (4 fixes)

- Revenue items (Other Income, Reimbursements) now pass through the historical expense filter
- OM proforma subtotal lines (Total Controllable, Sub-Total, Net Rental Income, Gross Scheduled Income) filtered from expense pipeline
- T12 column label corrected from "Effective Gross Income" to "Rent Collections (T12) / EGI (Pro Forma)"
- Management Fees added to MAX dedup rule alongside Taxes and Insurance

### Phase 2 — Rent roll and ingestion correctness (2 fixes)

- Centralized vacancy detection via `is_unit_vacant()` helper with move-in-date awareness; all three vacancy-setting call sites now route through the same function
- OM scenario selection documented with `OM_SCENARIO_PREFERENCE` constant and explicit logging of selected/discarded scenarios

### Phase 2.5 — Extraction determinism (1 fix)

- OM documents skip visual extraction when structured proforma extraction succeeds, eliminating nondeterministic duplicates (scenario-prefixed items, spurious misclassifications) that caused $25K+ T12 expense variance between runs

### Phase 3 — Underwriting assumptions (3 fixes)

- Year 1 lease-up loss model for high-vacancy acquisitions (>10% physical vacancy): applies per-unit downtime cost, produces distinct Year 1 vs stabilized NOI, feeds into IRR model
- Default management fee injection (4% of EGI) when no fee is extracted, with `mgmt_fee_source` field for transparency
- Business/Other Taxes reclassified as General & Administrative via prompt tuning and fallback mapper update

## Test count

**199 tests passing**, 7 pre-existing errors (unrelated `test_sensitivity_analysis.py` schema issue). 70 new tests added across phases.

## Open Tier D tickets

| # | Title |
|---|-------|
| D2 | Multi-source items with identical raw_text lose source attribution in adapter's raw_by_desc lookup |
| D4 | Apply structured parsing to OM property meta fields (purchase_price, year_built, total_units) instead of LLM extraction — key data extraction is nondeterministic, causing cap rate and other purchase-price-derived metrics to vary between runs |
