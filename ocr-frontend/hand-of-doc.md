Here's the complete Tier D ticket package to hand off. I'll format it so another developer can pick it up without needing the conversation context.

---

# Tier D Backlog — Handoff Document

## Project Context (One Paragraph)

The Valiance Capital financial underwriting platform ingests property documents (Offering Memorandums, rent rolls, P&Ls, utility bills) and produces institutional-grade underwriting reports including NOI, cap rate, DSCR, and IRR. A multi-tier refactor (Tiers A-C and Phases 1-3) consolidated the classification pipeline, added safety nets for common misclassifications, implemented a lease-up model for high-vacancy properties, added default management fee injection, and made OM extraction deterministic. The refactor shipped with 199 passing tests and zero regressions on two validated deals (Keystone and Leroy). The items below are known issues that were logged during the refactor but deferred for scope reasons, plus three new issues surfaced during final validation on 2715 Dwight.

Reference documents in repo root:

- `REFACTOR_COMPLETE.md` — overall project summary
- `CONSOLIDATION_DESIGN.md` — architecture and design decisions
- `PHASE_1_LESSONS.md` — validation gotchas to avoid
- `TIER_B_5_OBSERVATION.md` — real-deal observation results

---

## Known Tier D Tickets (Logged During Refactor)

### D1 — Expand OM Proforma Summary-Line Filter

**Status:** Logged in Tier B, partially addressed in Phase 1, still not comprehensive

**Problem:** The `_convert_om_proforma_to_expenses` method in `multi_document_extraction_service.py` has a summary-line filter that drops non-expense rows like "NOI", "Total Income", "Total Expenses", "EGI". Phase 1 expanded this to also catch "Total Controllable", "Sub-Total", "Net Rental Income", and exact-match "Gross Scheduled Income". But new OM formats will continue to surface new subtotal variants that leak through.

**Impact:** Subtotal lines get processed as "Uncategorized" expense items, polluting the verification UI. Financial impact is nil (they stay in Uncategorized and don't hit OpEx), but UX is messy.

**Fix approach:** Rather than playing whack-a-mole with keywords, consider whether the OM proforma parser should identify rows structurally — e.g., rows with formatting that indicates summary status (bold, colored background, horizontal rule above/below) vs data rows. If structural markers aren't extractable, maintain a growing keyword list and add tests for each variant as it's encountered.

**Files involved:**

- `financial-engine/app/services/multi_document_extraction_service.py` (`_convert_om_proforma_to_expenses`)
- Tests: `financial-engine/tests/services/test_phase1_fixes.py` (subtotal filter tests)

---

### D2 — Multi-Source Items Lose Source Attribution

**Status:** Logged in Tier B observation, affects ~8% of items on multi-source deals

**Problem:** In `multi_doc_normalization_adapter.py`, the `raw_by_desc` lookup uses `dict.setdefault`, which keeps the first-encountered item when two items share the same `raw_text` but come from different `source_document` values. The second item inherits the first item's source metadata.

**Impact:** No financial correctness issue — same descriptions get same classifications regardless of source. But audit trail is misleading. When an analyst clicks "where did this number come from?" they may see the wrong source document. On 2715 Dwight this affects 46 out of 549 items (8%).

**Fix approach:** Change the lookup key from `raw_text` to `(raw_text, source_document)`. Update the adapter's `adapt_normalization_to_normalized_item` to preserve source_document through the roundtrip.

**Files involved:**

- `financial-engine/app/services/multi_doc_normalization_adapter.py`
- `financial-engine/app/services/multi_document_extraction_service.py` (where the adapter is called)
- Tests: `financial-engine/tests/services/test_tier_b_consolidation.py`

---

### D3 — Business/Other Taxes Classification Drift

**Status:** Partially addressed in Phase 3 via prompt tuning, may drift back

**Problem:** Gemini consistently classified "Business / Other Taxes" as Real Estate Taxes at ~0.90 confidence before Phase 3. Phase 3 added explicit prompt guidance and fallback mapping to route this to General & Administrative. Validation showed the fix works on Keystone and Leroy.

**Risk:** Prompt-based fixes drift over time. If a future Gemini model version interprets "Taxes" differently, or if cache entries were written before the Phase 3 fix shipped, the classification may revert. Additionally, both G&A and Real Estate Taxes are OpEx categories, so the financial impact is small — but the classification is semantically important for expense analysis.

**Fix approach:**

1. Invalidate any existing Redis/MongoDB cache entries for "Business / Other Taxes" and variants
2. Add monitoring that alerts if this description starts classifying as Real Estate Taxes again
3. Consider whether other similarly-ambiguous descriptions ("Other Fees", "Miscellaneous Taxes") need the same treatment

**Files involved:**

- `financial-engine/app/services/gemini_client.py` (prompt)
- `financial-engine/app/services/normalization_service.py` (fallback mapper)
- Tests: `financial-engine/tests/services/test_phase3_fixes.py`

---

### D4 — OM Property Meta Extraction Is Nondeterministic

**Status:** Surfaced during Phase 3 validation on Keystone, confirmed on 2715 Dwight

**Problem:** While OM proforma data (expense items) was made deterministic in Phase 2.5 by skipping visual extraction when structured parsing succeeds, property meta fields (purchase_price, year_built, total_units, property_name, property_address) are still extracted via LLM-based `_convert_om_data_to_normalized`. Each normalization run can produce different values.

**Impact on 2715 Dwight specifically:**

- System extracted purchase_price as $9,400,000
- OM clearly states $9,200,000
- Off by $200K, which cascades into cap rate, IRR, loan sizing, and every downstream metric

**Impact on Keystone:**

- Cap rate appeared to jump from 0.00% to 5.72% between runs
- Root cause: one run extracted purchase_price, others produced 0. No code change happened — just LLM nondeterminism.

**Fix approach:** Apply the same "structured extraction is authoritative" principle used in Phase 2.5 to property meta. Specifically:

1. In `_convert_om_data_to_normalized`, check if the OM has a structured "Property Overview" or "Investment Summary" table with labeled fields
2. If yes, parse those fields directly (property_name, address, year_built, total_units, purchase_price, price_per_unit, land_area, gross_sf, net_rentable_sf, beds)
3. Only fall back to LLM extraction when structured data isn't available

**Files involved:**

- `financial-engine/app/services/multi_document_extraction_service.py` (`_convert_om_data_to_normalized`)
- `financial-engine/app/services/extract_om_details.py` (if applicable)
- `financial-engine/app/models/schemas.py` (property meta schema)

---

## Newly Surfaced Issues (2715 Dwight Validation)

### D5 — Lease-Up Model Not Firing on 48%-Vacant Property

**Status:** New — discovered during 2715 Dwight validation, HIGH PRIORITY

**Problem:** 2715 Dwight is 48% physically vacant (14 of 29 units at $0 current rent, no move-in date). The Phase 3 lease-up model has a 10% vacancy threshold and should have triggered. But the system's Revenue Build shows:

- No "Year 1 Lease-Up Loss" line
- Only a $25,683 Vacancy Loss (which is 3% of GPR — stabilized math)
- Year 1 and Stabilized EGI appear identical

**Expected behavior:** At 48% vacancy with ~$2,087 market rent on 14 vacant 1x1 units + additional vacant 3x2 units, the lease-up loss should be roughly:
`14 vacant units × ~$2,087 × 2 months downtime ≈ $58,436`

Plus additional units like Unit #4 (3x2 at $4,850 market) that are also vacant.

**Investigation priorities:**

1. Is `is_unit_vacant()` correctly identifying all 14 vacant units? Spot-check: Unit #1 has $0 current rent and null move-in date → should be vacant. Unit #4 has $0 current rent and null move-in date → should be vacant.
2. Is `physical_vacancy` being computed correctly in `financial_service.py:_calculate_revenue`?
3. Is the `lease_up_vacancy_threshold = 0.10` check correctly triggering when physical vacancy > 10%?
4. If all three above are correct, why is `year1_leaseup_loss` null/zero on the analysis output?

**Files involved:**

- `financial-engine/app/services/financial_service.py` (lines 862-904, `_calculate_revenue`)
- `financial-engine/app/models/schemas.py` (`is_unit_vacant` helper at line 183-244)
- Tests: `financial-engine/tests/services/test_phase3_fixes.py` (lease-up tests)

**Test to add:** A fixture that specifically replicates 2715 Dwight's rent roll shape (high vacancy, mix of $0-rent/null-move-in units) and asserts year1_leaseup_loss > 0.

---

### D6 — Market Rent Aggregation Bug in Unit Mix Summary

**Status:** New — discovered during 2715 Dwight validation, HIGH PRIORITY

**Problem:** The Unit Mix summary on the rent roll page shows:

- Avg Current Rent: $2,455
- Avg Market Rent: $1,437

Market Rent should never be lower than Current Rent. Individual row-level market rents are correct (1x1 units show $2,087, 3x2 units show $4,580-$4,850). The aggregation/summary calculation is broken.

**Expected behavior:** Weighted average of market rents should be higher than weighted average of current rents for a below-market property.

**Investigation priorities:**

1. Find the aggregation logic for the Unit Mix Summary table (likely in frontend or in a financial service summary computation)
2. Check whether the denominator uses total units (29) or occupied units (15) — if total units but the numerator only sums occupied-unit market rents, you'd get a deflated average
3. Check whether the market rent field being summed is the correct one (there may be multiple market rent fields: per-unit market, per-bed market, per-SF market)

**Files involved (likely):**

- `ocr-frontend/components/RentRollSummary.tsx` or similar
- `financial-engine/app/services/financial_service.py` (rent roll summary calculation)
- `financial-engine/app/models/schemas.py` (RentRollSummary schema)

**Test to add:** Aggregation test that asserts `avg_market_rent >= avg_current_rent` on any below-market property.

---

### D7 — IRR Returns -100% on Distressed Deals

**Status:** New — discovered during 2715 Dwight validation, LOW PRIORITY (correctness is fine, UX is not)

**Problem:** When NOI is severely below debt service (DSCR < 1.0x), the IRR model returns -100% and MOIC 0.00x on every sensitivity table cell. Technically accurate for a "total loss" scenario, but renders the sensitivity table useless — the user can't distinguish between "bad at 5.5% exit cap" and "catastrophic at 6.5% exit cap" because both show -100%.

**Fix approach options:**

1. **Floor the IRR at -50%** with a note that actual IRR is lower (rough and simple)
2. **Add a "DSCR below covenant" flag** on the output that suppresses the sensitivity table and displays a message instead
3. **Cap IRR at the actual levered loss percentage** (more accurate but requires math work)

**Recommendation:** Option 2 is cleanest. When DSCR < 1.0x on pro forma NOI, display "This deal does not service its debt at current assumptions. IRR calculation omitted — restructure terms or reduce purchase price." Show sensitivity table only when the base case DSCR ≥ 1.0x.

**Files involved:**

- `financial-engine/app/services/financial_service.py` (`_calculate_returns`)
- Frontend sensitivity table rendering

---

### D8 — Bed Count Missing from Output

**Status:** New — discovered during 2715 Dwight validation, MEDIUM PRIORITY for student housing deals

**Problem:** For student housing deals, per-bed pricing is the key metric. The 2715 Dwight OM shows "Beds (As Is / Pro Forma): 36 / 106" prominently on the cover page. The system's output shows no bed count at all.

**Why this matters:** Student housing comps are priced per-bed, not per-unit. A 28-unit / 106-bed property is underwritten completely differently than a 28-unit / 36-bed property. Missing bed count means the analyst can't compare this deal to market comps appropriately.

**Fix approach:**

1. Add `total_beds_existing` and `total_beds_pro_forma` fields to the OM property meta schema
2. Extract from OM (either structured parsing per D4 or targeted LLM extraction)
3. Add "Price/Bed" to the property details display
4. For student housing deals specifically, make per-bed metrics first-class alongside per-unit metrics

**Files involved:**

- `financial-engine/app/models/schemas.py` (property meta)
- `financial-engine/app/services/multi_document_extraction_service.py` (`_convert_om_data_to_normalized`)
- Frontend property details component

---

## Environmental/Infrastructure Items

### D9 — 2715 Dwight Database Availability

**Status:** Infrastructure, not code

**Problem:** 2715 Dwight is only accessible in `ocr_db` and `production` databases, not `financial_ai`. During validation throughout the refactor, this prevented the deal from being fully tested through the pipeline.

**Fix approach:** Either (a) re-ingest 2715 Dwight into `financial_ai` for dev/test purposes, or (b) add database-switching support to the financial-engine config for cross-database validation.

---

### D10 — Inter-Deal Cache Hit Rate Still Unmeasured

**Status:** Cache observability added in Tier C, but steady-state hit rate never measured

**Problem:** Tier C added `GET /api/v1/debug/cache-metrics` endpoint. In development, cache hit rate hasn't been measured against real production traffic. The hypothesis was 40-60% steady-state hit rate after caching common descriptions across deals.

**Fix approach:** After a week of production traffic post-deployment, query the cache metrics endpoint and report actual hit/miss ratios. If hit rate is below 20%, investigate whether cache keys are too specific (e.g., including variable fields that don't help with deduplication).

---

## Critical Handoff Notes

### Do NOT Do These Things

1. **Don't merge the legacy pipeline back.** Tier C deleted `normalize_expenses_batch` and `_legacy_normalize_expenses`. If the consolidated path has issues, fix forward, don't revert. The legacy path had pre-existing bugs that weren't worth preserving.

2. **Don't rely on stored analyses in MongoDB as pre/post comparison baselines.** Analyses in MongoDB may have been computed by prior code versions. Always re-run `/normalize` and `/analyze` before validating code changes. See `PHASE_1_LESSONS.md`.

3. **Don't query MongoDB for `normalized_items` field.** That field doesn't exist. Actual fields are `financials_data` and `normalized_data`. This cost us a full round of debugging in Phase 1.

4. **Don't skip the diagnostic step before proposing fixes.** Multiple times during the refactor, jumping to "obvious" fixes was wrong — real root causes were surfaced by investigation. When validation produces surprising numbers, investigate before explaining away.

### Do These Things

1. **When in doubt about run-to-run variance, run it 3 times.** Real bugs are reproducible; LLM variance isn't. If you see a number change between runs, run it a third time to see if it's actually nondeterminism or a stale-data artifact.

2. **Use the dev re-analyze feature.** `POST /api/v1/dev/reanalyze/{package_id}?level=1|2|3|4` lets you iterate without re-uploading. Level 1 = financial model only (fastest), Level 3 = busts cache for fresh LLM, Level 4 = full re-extraction. Enable with `ENABLE_REANALYZE_ENDPOINTS=true` in dev `.env`.

3. **Commit per-phase, not per-feature.** When shipping fixes, follow the established pattern: one commit per logical unit (Tier D1, Tier D2, etc.) so bisect works cleanly.

4. **Test against all three deals.** Keystone (OM, high vacancy), Leroy (OM, single vacancy), 2715 Dwight (non-OM multi-source, distressed). If a change affects metrics on any of these, document the delta and reason.

---

## Priority Ordering for Next Developer

**Do first (surfaces the quickest wins on real deals):**

1. D6 — Market rent aggregation bug (mathematically impossible output, should be a clear bug fix)
2. D5 — Lease-up model not firing on 2715 Dwight (highest-impact underwriting correctness issue)
3. D4 — Property meta extraction determinism (biggest correctness issue, affects every OM deal)

**Do second (improves trust and UX):** 4. D8 — Bed count for student housing deals (matters for a whole asset class) 5. D7 — IRR behavior on distressed deals (UX improvement, not correctness) 6. D2 — Source attribution for multi-source items (audit trail improvement)

**Do when you have time:** 7. D1 — Expand subtotal filter (cosmetic) 8. D3 — Monitor Business/Other Taxes classification (prevention) 9. D10 — Measure cache hit rate (observability) 10. D9 — 2715 Dwight database availability (infrastructure)

Each of D5 and D6 should be individually investigatable and fixable in under a day. D4 is the biggest item — probably 2-3 days for a proper structured-extraction implementation.

---

Pass this document to the next developer along with `REFACTOR_COMPLETE.md` and `PHASE_1_LESSONS.md`. They have enough context to pick up where this left off without needing to reconstruct the reasoning.
