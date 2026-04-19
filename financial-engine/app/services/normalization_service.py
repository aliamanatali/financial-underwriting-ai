import asyncio
import json
from typing import List, Dict, Any
from app.models.schemas import StandardizedExpense, ExpenseCategory, AuditLog, RentRollItem, CategoryGroup
import logging
from datetime import datetime
from app.services.batch_logging_service import BatchLoggingService

logger = logging.getLogger(__name__)

# Maximum concurrent Gemini batch calls across all NormalizationService
# instances.  Shared class-level semaphore prevents a large re-analyze
# from saturating the event loop with LLM calls and starving other
# requests (dashboard, SSE, etc.).
_NORMALIZATION_GEMINI_CONCURRENCY = 10

# Module-level cache metrics for observability.
# Reset on process restart. Exposed via GET /api/v1/debug/cache-metrics.
CACHE_METRICS = {"hits": 0, "misses": 0, "writes_skipped_low_confidence": 0}

class NormalizationService:
    # Cache TTL: 7 days. Reduced from 30 days to limit the blast radius of
    # bad LLM classifications that get cached and poison future deals.
    CACHE_TTL_SECONDS = 86400 * 7  # 7 days

    # Minimum confidence to cache an LLM classification. Low-confidence
    # mappings should not poison future deals — they'll be re-evaluated
    # by the LLM on the next occurrence.
    CACHE_MIN_CONFIDENCE = 0.85

    # Class-level semaphore shared across all instances — bounds total
    # concurrent Gemini calls from normalization regardless of how many
    # callers (re-analyze, normal flow, etc.) are active.
    _gemini_semaphore = asyncio.Semaphore(_NORMALIZATION_GEMINI_CONCURRENCY)

    def __init__(self, llm_service: Any, batch_logging_service: BatchLoggingService = None):
        self.llm_service = llm_service
        self.collection_name = "expense_mappings"
        self.batch_logging_service = batch_logging_service

    @staticmethod
    def _cache_key(description: str, section_context: str = "unknown") -> str:
        """Build the Redis cache key for a description+context pair.

        Key format: mapping:{description}:{section_context}

        Migration note (2026-04-18): The old key format was mapping:{description}
        (no section_context suffix). _get_cached_mappings falls back to reading
        the old format when the new key misses, and forward-writes it under the
        new key so future reads are fast. Old keys expire naturally under the
        7-day TTL — the fallback can be removed ~30 days after deployment.
        """
        return f"mapping:{description}:{section_context}"

    @staticmethod
    def _legacy_cache_key(description: str) -> str:
        """Old-format Redis key (pre section_context). Used for migration fallback."""
        return f"mapping:{description}"

    async def _get_cached_mappings(self, descriptions: List[str], section_context: str = "unknown") -> Dict[str, Dict]:
        """Retrieve cached mappings from Redis and MongoDB.

        Reads new-format keys first, falls back to old-format keys for
        migration, and back-fills new-format keys from MongoDB or old-format
        hits so subsequent reads are fast.
        """
        from app.db.mongodb import get_database
        from app.db.redis import redis_client
        from app.config import settings

        cache = {}
        missing_in_redis = []

        # 1. Try Redis — new-format key first, then legacy fallback
        if redis_client.client:
            new_keys = [self._cache_key(desc, section_context) for desc in descriptions]
            try:
                values = await redis_client.client.mget(new_keys)
                need_legacy_lookup = []
                for desc, val in zip(descriptions, values):
                    if val:
                        try:
                            cache[desc] = json.loads(val)
                        except json.JSONDecodeError:
                            need_legacy_lookup.append(desc)
                    else:
                        need_legacy_lookup.append(desc)

                # Fallback: try old-format keys for descriptions that missed
                if need_legacy_lookup:
                    legacy_keys = [self._legacy_cache_key(desc) for desc in need_legacy_lookup]
                    legacy_values = await redis_client.client.mget(legacy_keys)
                    forward_write_pipeline = redis_client.client.pipeline()
                    has_forward_writes = False

                    for desc, val in zip(need_legacy_lookup, legacy_values):
                        if val:
                            try:
                                parsed = json.loads(val)
                                cache[desc] = parsed
                                # Forward-write under new key so future reads hit directly
                                new_key = self._cache_key(desc, section_context)
                                forward_write_pipeline.set(new_key, val, ex=NormalizationService.CACHE_TTL_SECONDS)
                                has_forward_writes = True
                            except json.JSONDecodeError:
                                missing_in_redis.append(desc)
                        else:
                            missing_in_redis.append(desc)

                    if has_forward_writes:
                        try:
                            await forward_write_pipeline.execute()
                        except Exception as e:
                            logger.error(f"Redis forward-write error: {e}")

            except Exception as e:
                logger.error(f"Redis get error: {e}")
                missing_in_redis = descriptions
        else:
            missing_in_redis = descriptions

        if not missing_in_redis:
            return cache

        # 2. Try MongoDB for what's missing in Redis
        if settings.use_mongodb:
            try:
                db = get_database()
                cursor = db[self.collection_name].find({"original_text": {"$in": missing_in_redis}})

                mongo_hits = []
                async for doc in cursor:
                    if "original_text" in doc and "mapped_category" in doc:
                        clean_doc = {
                            "original_text": doc["original_text"],
                            "mapped_category": doc["mapped_category"],
                            "confidence": doc.get("confidence", 0.85),
                            "reasoning": doc.get("reasoning")
                        }
                        cache[doc["original_text"]] = clean_doc
                        mongo_hits.append(clean_doc)

                # Populate Redis (new-format key) with Mongo hits
                if redis_client.client and mongo_hits:
                    try:
                        pipeline = redis_client.client.pipeline()
                        for hit in mongo_hits:
                            key = self._cache_key(hit["original_text"], section_context)
                            pipeline.set(key, json.dumps(hit), ex=NormalizationService.CACHE_TTL_SECONDS)
                        await pipeline.execute()
                    except Exception as e:
                        logger.error(f"Redis populate error: {e}")

            except Exception as e:
                logger.error(f"Failed to fetch cached mappings from Mongo: {e}")

        return cache

    async def _save_mappings(self, mappings: List[Dict], section_context: str = "unknown"):
        """Save new mappings to MongoDB and Redis.

        Only caches mappings with confidence >= CACHE_MIN_CONFIDENCE.
        Low-confidence mappings are stored in MongoDB (for audit trail)
        but NOT in Redis, so the LLM is re-invoked next time.
        """
        from app.db.mongodb import get_database
        from app.db.redis import redis_client
        from app.config import settings
        from pymongo import UpdateOne

        if not mappings:
            return

        # 1. Save to Redis — only high-confidence mappings
        if redis_client.client:
            try:
                pipeline = redis_client.client.pipeline()
                cached_count = 0
                skipped_count = 0
                for item in mappings:
                    if "original_text" in item and "mapped_category" in item:
                        confidence = item.get("confidence", 0.85)
                        if confidence < NormalizationService.CACHE_MIN_CONFIDENCE:
                            skipped_count += 1
                            continue
                        cache_obj = {
                            "original_text": item["original_text"],
                            "mapped_category": item["mapped_category"],
                            "confidence": confidence,
                            "reasoning": item.get("reasoning")
                        }
                        key = self._cache_key(item["original_text"], section_context)
                        pipeline.set(key, json.dumps(cache_obj), ex=NormalizationService.CACHE_TTL_SECONDS)
                        cached_count += 1
                if cached_count > 0:
                    await pipeline.execute()
                if skipped_count > 0:
                    CACHE_METRICS["writes_skipped_low_confidence"] += skipped_count
                    logger.info(f"Skipped caching {skipped_count} low-confidence mappings (< {NormalizationService.CACHE_MIN_CONFIDENCE})")
            except Exception as e:
                logger.error(f"Failed to save mappings to Redis: {e}")

        # 2. Save to MongoDB (all mappings, including low-confidence, for audit trail)
        if settings.use_mongodb:
            try:
                db = get_database()
                operations = []
                for item in mappings:
                    if "original_text" in item and "mapped_category" in item:
                        operations.append(
                            UpdateOne(
                                {"original_text": item["original_text"]},
                                {"$set": {
                                    "original_text": item["original_text"],
                                    "mapped_category": item["mapped_category"],
                                    "confidence": item.get("confidence", 0.85),
                                    "reasoning": item.get("reasoning"),
                                    "updated_at": datetime.now().isoformat()
                                }},
                                upsert=True
                            )
                        )

                if operations:
                    await db[self.collection_name].bulk_write(operations)
                    logger.info(f"Cached {len(operations)} expense mappings in MongoDB")
            except Exception as e:
                logger.error(f"Failed to save cached mappings to Mongo: {e}")

    @staticmethod
    async def invalidate_cache_entry(description: str, section_context: str = "unknown"):
        """Remove a cached mapping from both Redis and MongoDB.

        Called when a user corrects a classification via the Verify Data UI.
        The old (incorrect) mapping is purged so the next occurrence goes
        back through the LLM instead of serving stale data.
        """
        from app.db.mongodb import get_database
        from app.db.redis import redis_client
        from app.config import settings

        # 1. Delete from Redis (both new and legacy key formats)
        if redis_client.client:
            try:
                new_key = NormalizationService._cache_key(description, section_context)
                legacy_key = NormalizationService._legacy_cache_key(description)
                await redis_client.client.delete(new_key, legacy_key)
                logger.info(f"Invalidated Redis cache for: '{description}'")
            except Exception as e:
                logger.error(f"Redis invalidation error for '{description}': {e}")

        # 2. Delete from MongoDB
        if settings.use_mongodb:
            try:
                db = get_database()
                result = await db["expense_mappings"].delete_one({"original_text": description})
                if result.deleted_count:
                    logger.info(f"Invalidated MongoDB cache for: '{description}'")
            except Exception as e:
                logger.error(f"MongoDB invalidation error for '{description}': {e}")

    def _parse_int_robust(self, value: Any) -> int:
        """Helper to safely parse integer strings, handling text suffixes like 'sq ft'."""
        if value is None:
            return 0
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        
        # String handling
        s = str(value).strip().lower()
        if not s or s == "-" or s == "n/a":
            return 0
            
        # Remove commas
        s = s.replace(",", "")
        
        # Extract first sequence of digits
        import re
        match = re.search(r'\d+', s)
        if match:
            try:
                return int(match.group(0))
            except ValueError:
                return 0
        return 0

    def _parse_amount(self, value: Any) -> float:
        """Helper to safely parse amount strings/floats."""
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Handle Mixed Content (e.g., Chinese characters + numbers)
            # Extract only the valid number part if mixed
            import re
            
            # Regex to find the first valid number pattern (including negatives, decimals, commas)
            # Looks for: optional negative sign, digits with optional commas, optional decimal part
            # Matches: "$1,234.56", "-500", "2180 (Chinese text)", "(500)"
            
            # First, standard cleaning
            clean_val = value.replace('$', '').replace(',', '').strip()
            
            # Handle negative values in parentheses e.g. (500) -> -500
            if clean_val.startswith('(') and clean_val.endswith(')'):
                clean_val = '-' + clean_val[1:-1]

            # Handle negative signs with spaces e.g. "- 500" -> "-500"
            if clean_val.startswith('-') and ' ' in clean_val:
                 clean_val = clean_val.replace(' ', '')
                 
            # Extract number if still mixed with text (e.g. "2180 text")
            # We look for a pattern like: -? [0-9]+ (\. [0-9]+)?
            match = re.search(r'-?\d+(\.\d+)?', clean_val)
            if match:
                clean_val = match.group(0)

            try:
                return float(clean_val)
            except ValueError:
                return 0.0
        return 0.0

    async def normalize_expenses_async(self, raw_expenses: List[Dict], document_id: str = None, total_units: int = 0) -> List[StandardizedExpense]:
        """
        Normalizes a list of raw expense data into StandardizedExpense objects using cached mappings and parallel batch processing.
        """
        if not raw_expenses:
            return []

        # PRE-PROCESSING: Deduplication of numeric "descriptions"
        # The extraction engine sometimes picks up the value column as a separate line item description.
        # Example: "Property Tax" -> $10,000 AND "$10,000" -> $10,000.
        # We filter out items where the description essentially parses to a number.
        cleaned_expenses = []
        for exp in raw_expenses:
            desc = str(exp.get("description", "")).strip()
            
            # Skip empty descriptions
            if not desc:
                continue

            # Check if description is numeric (currency or plain number)
            is_numeric_desc = False
            try:
                # Remove common text currency symbols/formatting to check for pure number
                # We want to catch "$44,740", "44,740", "(44,740)", "-44,740"
                clean_desc = desc.replace('$', '').replace(',', '').replace('(', '').replace(')', '').strip()
                if clean_desc:
                    float(clean_desc)
                    is_numeric_desc = True
            except ValueError:
                is_numeric_desc = False
            
            if is_numeric_desc:
                logger.warning(f"Skipping numeric description/duplicate: '{desc}' (Amount: {exp.get('amount')})")
                continue
                
            cleaned_expenses.append(exp)
            
        raw_expenses = cleaned_expenses

        categories = [e.value for e in ExpenseCategory]

        # Determine the dominant section_context for this batch (used for cache key).
        # Individual items may have their own section_context from the extraction LLM.
        # For cache lookups, we group by (description, section_context) pairs.

        # 1. Check Cache — keyed by (description, section_context)
        # Build unique (desc, section_context) pairs for cache lookup
        desc_ctx_pairs = []
        for item in raw_expenses:
            desc = item.get("description", "")
            ctx = item.get("section_context", "unknown") or "unknown"
            desc_ctx_pairs.append((desc, ctx))

        # Get all unique descriptions for cache lookup (grouped by section_context)
        unique_descs = list(set(d for d, _ in desc_ctx_pairs))
        # Use the first item's section_context as the batch context for cache reads
        # (items from the same document typically share context)
        batch_section_context = desc_ctx_pairs[0][1] if desc_ctx_pairs else "unknown"
        cached_mappings = await self._get_cached_mappings(unique_descs, section_context=batch_section_context)

        uncached_expenses = []

        # We'll build a map of description -> mapped_item
        final_mapped_data_dict = {}

        for i, expense in enumerate(raw_expenses):
            desc = expense.get("description", "")
            if desc in cached_mappings:
                # Use cached
                cached = cached_mappings[desc]
                final_mapped_data_dict[desc] = {
                    "original_text": desc,
                    "mapped_category": cached["mapped_category"],
                    "amount": expense.get("amount"), # Use current amount, not cached amount
                    "amount_t3": expense.get("amount_t3"),
                    "amount_t6": expense.get("amount_t6"),
                    "amount_t9": expense.get("amount_t9"),
                    "confidence": cached.get("confidence", 0.85), # Replay original LLM confidence from cache
                    "reasoning": cached.get("reasoning"),
                    "page_number": expense.get("page_number"),
                    "bbox": expense.get("bbox")
                }
            else:
                uncached_expenses.append(expense)

        cache_hits = len(final_mapped_data_dict)
        cache_misses = len(uncached_expenses)
        CACHE_METRICS["hits"] += cache_hits
        CACHE_METRICS["misses"] += cache_misses
        logger.info(f"Normalization cache: hits={cache_hits}, misses={cache_misses}, total={len(raw_expenses)}")

        # 2. Process Uncached in Batches
        new_mappings_to_save = []
        
        if uncached_expenses:
            BATCH_SIZE = 100
            batches = [uncached_expenses[i:i + BATCH_SIZE] for i in range(0, len(uncached_expenses), BATCH_SIZE)]
            
            logger.info(f"Normalizing {len(uncached_expenses)} new expenses in {len(batches)} batches")
            
            async def process_batch(batch):
                try:
                    # Use the async version of map_expenses_to_categories - WITH FAST MODEL
                    # Assuming map_expenses_to_categories_async eventually calls generate_content_async,
                    # we need to ensure the fast model is used if possible.
                    # If the service method doesn't support the flag, we rely on the implementation.
                    # Based on my changes to gemini_client, map_expenses_to_categories_async uses use_fast_model=True.
                    return await self.llm_service.map_expenses_to_categories_async(batch, categories)
                except Exception as e:
                    logger.error(f"Error processing batch: {e}")
                    return []

            # Execute batches in parallel, bounded by class-level semaphore
            async def process_batch_with_sem(batch):
                async with self._gemini_semaphore:
                    return await process_batch(batch)

            results = await asyncio.gather(*[process_batch_with_sem(batch) for batch in batches])
            
            # Flatten results and prepare for merge
            for i, res in enumerate(results):
                if res:
                    for item in res:
                        # Ensure original amount is preserved if LLM messed it up
                        desc = item.get("original_text", "")

                        # Link back to original raw expense to get amounts and metadata
                        original_match = next((e for e in batches[i] if e.get("description") == desc), {})
                        
                        # Merge amounts from original extraction
                        item["amount"] = original_match.get("amount", item.get("amount"))
                        item["amount_t3"] = original_match.get("amount_t3")
                        item["amount_t6"] = original_match.get("amount_t6")
                        item["amount_t9"] = original_match.get("amount_t9")
                        item["page_number"] = original_match.get("page_number")
                        item["bbox"] = original_match.get("bbox")
                        
                        final_mapped_data_dict[desc] = item
                        new_mappings_to_save.append(item)
                else:
                    logger.warning(f"Batch {i} failed LLM processing, applying fallback mapping")
                    fallback_batch = self._fallback_simple_mapping_raw(batches[i])
                    for item in fallback_batch:
                        desc = item.get("original_text", "")
                        final_mapped_data_dict[desc] = item
                        # We don't save fallback to cache usually, or maybe we do with low confidence?
                        # Let's NOT save fallback to cache so we retry LLM next time.

            # 3. Save new mappings to cache (keyed by section_context)
            if new_mappings_to_save:
                await self._save_mappings(new_mappings_to_save, section_context=batch_section_context)

        # 4. Construct Final List
        try:
            normalized_expenses = []
            
            # Iterate through original raw_expenses to maintain order and ensure all are covered
            for expense in raw_expenses:
                desc = expense.get("description", "")
                
                # --- FIX: Expense Aggregation Errors ---
                # 1. Exclude Loan/Principal amounts if they sneaked in as expenses
                desc_lower = desc.lower()
                forced_category = None

                # FIX: Broader detection for Balance Sheet items (Liabilities)
                # "Current Loan Balance", "Mortgage Payable", "Note Payable", "Principal Balance"
                is_liability_keyword = any(k in desc_lower for k in ["loan balance", "principal balance", "mortgage payable", "note payable", "loan amount"])
                if is_liability_keyword:
                     logger.info(f"Identified likely Debt Balance/Liability item: {desc}. Forcing category to CURRENT_LOAN_BALANCE.")
                     forced_category = ExpenseCategory.CURRENT_LOAN_BALANCE

                # Safety net: Past-due / receivable items should never be revenue or OpEx
                past_due_keywords = ["past due", "outstanding balance", "overdue", "arrears", "delinquent"]
                if not forced_category and any(k in desc_lower for k in past_due_keywords):
                     logger.info(f"Reclassifying past-due item to Accounts Receivable: {desc}")
                     forced_category = ExpenseCategory.ACCOUNTS_RECEIVABLE

                # FIX: Explicit Debt Service Mapping (Principal & Interest often misclassified as OpEx)
                if "current principal" in desc_lower or "principal due" in desc_lower:
                     logger.info(f"Reclassifying Debt Principal: {desc} to CURRENT_LOAN_BALANCE")
                     forced_category = ExpenseCategory.CURRENT_LOAN_BALANCE
                
                elif "current interest" in desc_lower or "interest due" in desc_lower:
                     logger.info(f"Reclassifying Debt Interest: {desc} to UNCATEGORIZED (Debt Service)")
                     forced_category = ExpenseCategory.UNCATEGORIZED

                # FIX: Explicit Revenue Mapping (Income items appearing in Expenses)
                if "rental income" in desc_lower or "rent income" in desc_lower:
                     logger.info(f"Reclassifying Revenue item: {desc} to GROSS_POTENTIAL_RENT")
                     forced_category = ExpenseCategory.GROSS_POTENTIAL_RENT

                elif "interest income" in desc_lower:
                     logger.info(f"Reclassifying Interest Income: {desc} to OTHER_INCOME")
                     forced_category = ExpenseCategory.OTHER_INCOME

                # FIX: Explicit Other Income Mapping (Ancillary revenue misclassified as expense)
                elif any(k in desc_lower for k in ["parking revenue", "parking income", "laundry revenue", "laundry income",
                         "storage revenue", "storage income", "vending revenue", "vending income",
                         "garage revenue", "garage income"]):
                     logger.info(f"Reclassifying Ancillary Revenue item: {desc} to OTHER_INCOME")
                     forced_category = ExpenseCategory.OTHER_INCOME

                # FIX: Explicit Payroll Mapping (Manager/salary items misclassified)
                if not forced_category and any(k in desc_lower for k in [
                    "onsite manager", "on-site manager", "resident manager", "site manager",
                    "manager salary", "manager payroll", "building superintendent", "super salary"
                ]):
                     logger.info(f"Reclassifying Payroll item: {desc} to PAYROLL")
                     forced_category = ExpenseCategory.PAYROLL

                # FIX: Exclude Vacancy/Concessions from Expenses
                # These are deductions from Revenue, not Operating Expenses.
                # We map them to UNCATEGORIZED for now, and ensure FinancialService excludes them.
                is_vacancy_keyword = any(k in desc_lower for k in ["vacancy", "concession", "bad debt", "loss to lease", "rent loss"])
                if is_vacancy_keyword:
                     logger.info(f"Identified Revenue Deduction item (Vacancy/Concessions): {desc}. Forcing category to UNCATEGORIZED to exclude from OpEx.")
                     forced_category = ExpenseCategory.UNCATEGORIZED

                # 2. Filter out Student Financial Data from Expenses
                # Check description for student/tuition keywords
                student_keywords = [
                    "tuition", "scholarship", "grant", "financial aid", "semester",
                    "student services", "living expenses", "resident tuition", "award letter"
                ]
                if any(k in desc_lower for k in student_keywords):
                    logger.warning(f"Reclassifying student financial item to Capital Reserves (Non-Op): {desc}")
                    # We force it to CAPITAL_RESERVES to exclude from NOI
                    forced_category = ExpenseCategory.CAPITAL_RESERVES

                # 3. Exclude Capital Expenditures (CapEx) incorrectly classified as Operating Expenses
                # User-reported issues: "Guard railings", "Staircase landings", "Roofing", "Well drilling", "Permits"
                capex_keywords = [
                    "well drilling", "drilling", "pump replacement",
                    "guard rail", "railing", "balcony repair", "staircase", "landing",
                    "roofing", "roof replacement", "shingles",
                    "construction", "renovation", "remodel", "upgrades",
                    "plan check", "architect", "engineering",
                    "asphalt", "paving", "concrete", "foundation",
                    "hvac replacement", "boiler replacement", "capital"
                ]
                # "roof repair" is handled separately below — bare keyword catches
                # both full repairs (CapEx) and patching jobs (OpEx).
                roof_repair_maintenance_qualifiers = [
                    "minor", "patch", "small", "touch-up", "touch up",
                    "seal", "sealant", "caulk", "leak repair"
                ]
                # Permits are only CapEx when combined with capital-work qualifiers.
                permit_capex_qualifiers = [
                    "construction", "renovation", "upgrade", "installation",
                    "replacement", "new", "capital", "electrical"
                ]

                if any(k in desc_lower for k in capex_keywords):
                     logger.warning(f"Reclassifying CapEx item to Capital Reserves: {desc} - {expense.get('amount')}")
                     forced_category = ExpenseCategory.CAPITAL_RESERVES
                elif "roof repair" in desc_lower or "roof rebuild" in desc_lower:
                     # Only CapEx if NOT accompanied by maintenance qualifiers
                     is_maintenance = any(q in desc_lower for q in roof_repair_maintenance_qualifiers)
                     if not is_maintenance:
                         logger.warning(f"Reclassifying roof repair to Capital Reserves: {desc} - {expense.get('amount')}")
                         forced_category = ExpenseCategory.CAPITAL_RESERVES
                elif "permit" in desc_lower and any(q in desc_lower for q in permit_capex_qualifiers):
                     logger.warning(f"Reclassifying qualified permit to Capital Reserves: {desc} - {expense.get('amount')}")
                     forced_category = ExpenseCategory.CAPITAL_RESERVES

                # Safety net: High-dollar items with CapEx keywords that the LLM
                # classified as OpEx. Proposals, modernizations, replacements > $5k
                # are almost certainly capital expenditures, not operating expenses.
                high_dollar_capex_keywords = ["proposal", "modernization", "replacement", "installation"]
                opex_categories = {
                    ExpenseCategory.REPAIRS_MAINTENANCE, ExpenseCategory.CONTRACT_SERVICES,
                    ExpenseCategory.OTHER_OPERATING_EXPENSES, ExpenseCategory.GENERAL_ADMINISTRATIVE,
                }
                if not forced_category and any(k in desc_lower for k in high_dollar_capex_keywords):
                    amount_val = expense.get("amount", 0)
                    parsed_amt = abs(self._parse_amount(amount_val)) if amount_val else 0
                    if parsed_amt > 5000:
                        # Only override if LLM put it in an OpEx category.
                        # Reads final_mapped_data_dict which is populated earlier in this
                        # same loop iteration (from cache hit or LLM batch result).
                        mapped_item_check = final_mapped_data_dict.get(desc)
                        if mapped_item_check:
                            try:
                                llm_cat = ExpenseCategory(mapped_item_check.get("mapped_category", ""))
                            except ValueError:
                                llm_cat = None
                            if llm_cat in opex_categories:
                                logger.warning(f"Reclassifying high-dollar CapEx item: {desc} (${parsed_amt:,.0f}) to Capital Reserves")
                                forced_category = ExpenseCategory.CAPITAL_RESERVES

                # 4a. Deposits are balance-sheet items, not operating expenses.
                deposit_keywords = [
                    "security deposit", "tenant deposit", "earnest money",
                    "escrow deposit", "refund", "return of deposit"
                ]
                if any(k in desc_lower for k in deposit_keywords):
                     logger.info(f"Reclassifying Deposit/Refund item: {desc}")
                     forced_category = ExpenseCategory.DEPOSIT

                # 4b. Exclude other Non-Operating Items (Loans, Depreciation)
                non_op_keywords = [
                    "depreciation", "amortization", "interest expense", "loan interest",
                    "loan principal", "mortgage", "lender", "bank fee", "financing",
                    "legal settlement", "attorney fee - purchase", "closing cost"
                ]
                if not forced_category and any(k in desc_lower for k in non_op_keywords):
                     if "interest" in desc_lower and "income" in desc_lower:
                         # Interest Income -> Other Income (Revenue)
                         pass
                     else:
                         logger.info(f"Reclassifying Non-Operating item: {desc}")
                         forced_category = ExpenseCategory.UNCATEGORIZED

                # 5. Exclude "Profit & Loss" document header/summary lines that might be massive sums
                # "Assets + Liabilities + Expenses" sum
                # FIX: Enhanced Document Title / Filename Exclusion
                if any(x in desc_lower for x in ["profit & loss", "balance sheet", "financial statement", "rent roll", "offering memorandum"]):
                    # If it looks like a file name (has extension)
                    if any(ext in desc_lower for ext in [".xlsx", ".xls", ".pdf", ".docx", ".doc"]):
                         logger.warning(f"Excluding likely Filename/Document Title: {desc}")
                         continue
                         
                    if expense.get("amount", 0) > 1_000_000: # Arbitrary high threshold for "Total" lines
                         logger.warning(f"Excluding likely Document Title/Total line: {desc} - {expense.get('amount')}")
                         continue

                # 4. Exclude Global Expense Summaries to prevent duplication
                # e.g., "Total Operating Expenses", "Total Expenses", "Total Ordinary Expenses"
                # But allow category totals (e.g. "Total Repairs") because deduplication logic in FinancialService handles those.
                # We specifically want to target the Grand Total of expenses.
                if desc_lower in ["total expenses", "total operating expenses", "total ordinary expenses", "total opex", "total expense"]:
                     logger.warning(f"Excluding Global Expense Summary line to prevent double-counting: {desc} - {expense.get('amount')}")
                     continue

                # Also check for "Total <X>" where X is generic
                if desc_lower.startswith("total ") and ("operating expense" in desc_lower or "expense" == desc_lower.replace("total ", "").strip()):
                     logger.warning(f"Excluding Global Expense Summary line: {desc}")
                     continue

                # 5. Exclude Assessed Values / Property Values from Expenses
                # These are often large numbers (e.g. $1.5M) misclassified as tax expenses because they appear on tax bills.
                # Keywords: "Net Taxable Value", "Total Real Property" (value context), "Gross Assessment", "Land Value"
                # We must be careful not to exclude "Special Assessment" which is a valid tax.
                assessment_keywords = [
                    "net taxable value", "gross assessment", "total real property",
                    "assessed value", "taxable value", "land value", "improvement value",
                    "personal property value", "total value", "full cash value"
                ]
                
                # Check for strict matches.
                # "Total Real Property" is tricky because it could be "Total Real Property Tax", but usually that's "Total Taxes".
                # On tax bills, "Total Real Property" usually heads the value column or the summary of values.
                # If the amount is very large (e.g. > $100k) and matches these keywords, it's definitely value not tax.
                if any(k in desc_lower for k in assessment_keywords):
                    # Exception: Actual assessment charges (special assessment, city assessment, etc.)
                    # These are real operating expenses that should NOT be excluded.
                    is_real_assessment = any(k in desc_lower for k in [
                        "special assessment", "city assessment", "county assessment",
                        "assessment fee", "assessment charge", "annual assessment",
                        "hoa assessment", "condo assessment", "assessments"
                    ])
                    # "assessments" alone (plural) is typically a line-item charge, not a property value.
                    # But "assessed value", "gross assessment" (singular in value context) are property values.
                    if not is_real_assessment:
                         logger.warning(f"Excluding likely Assessed Value/Property Value line: {desc} - {expense.get('amount')}")
                         continue

                mapped_item = final_mapped_data_dict.get(desc)
                
                if not mapped_item:
                    # Should not happen if fallback logic works, but just in case
                    # Apply single fallback
                    fallback_list = self._fallback_simple_mapping_raw([expense])
                    mapped_item = fallback_list[0]
                
                # Ensure the mapped category is a valid enum member
                try:
                    if forced_category:
                        category_enum = forced_category
                    else:
                        category_enum = ExpenseCategory(mapped_item["mapped_category"])
                except ValueError:
                    category_enum = ExpenseCategory.UNCATEGORIZED

                # Expenses are outflows, so we normalize them to positive magnitudes.
                # Use the amount from the raw expense (source of truth) rather than LLM output if possible,
                # but LLM output usually echoes it. Safest is raw expense amount.
                amount_val = expense.get("amount")
                parsed_amount = abs(self._parse_amount(amount_val))

                # FIX: CapEx / Large Insurance Item Review Logic
                # If mapped_category is INSURANCE and amount > $50,000, it might be a limit or a large claim, not a premium.
                # Or if any single expense item is > $50,000 and NOT Taxes/Debt/Management, flag it or move to CapEx/Reserves.
                
                # Check for Insurance items that are actually coverage limits or CapEx, not premiums.
                # Per-unit scaling: $1,500/unit is a reasonable insurance premium ceiling.
                # Only auto-reclassify to Capital Reserves if description contains CapEx keywords.
                # Otherwise, keep as Insurance but lower confidence when amount looks high.
                is_insurance_limit_keyword = any(k in desc_lower for k in ["limit", "coverage", "aggregate", "liability"])
                capex_in_insurance_keyword = any(k in desc_lower for k in [
                    "reserve", "replacement", "capital", "deductible", "claim", "loss run"
                ])

                if category_enum == ExpenseCategory.INSURANCE:
                    # Items with explicit limit/coverage keywords are not premiums
                    if is_insurance_limit_keyword:
                        logger.warning(f"Insurance Limit/Coverage keyword detected (${parsed_amount:,.2f}): '{desc}'. Re-classifying as Capital Reserves.")
                        category_enum = ExpenseCategory.CAPITAL_RESERVES
                    # Items with CapEx keywords are reserves, not premiums
                    elif capex_in_insurance_keyword:
                        logger.warning(f"Insurance CapEx keyword detected (${parsed_amount:,.2f}): '{desc}'. Re-classifying as Capital Reserves.")
                        category_enum = ExpenseCategory.CAPITAL_RESERVES
                    # Per-unit ceiling check: flag high premiums but don't auto-reclassify
                    elif total_units and total_units > 0:
                        per_unit_insurance = parsed_amount / total_units
                        if per_unit_insurance > 1500:
                            logger.warning(f"Insurance per-unit cost (${per_unit_insurance:,.0f}/unit) exceeds $1,500 ceiling for '{desc}' (${parsed_amount:,.2f}). Lowering confidence.")
                            mapped_item["confidence"] = min(mapped_item.get("confidence", 0.85), 0.70)
                    elif not total_units or total_units == 0:
                        logger.warning(f"Insurance per-unit check skipped: total_units=0 for item '{desc}' (${parsed_amount:,.2f})")

                # --- Cross-classification guard (Tier 3.4) ---
                # If section_context from the extraction LLM disagrees with the
                # mapped_category from the classification LLM, flag the conflict.
                # Exception: Capital Reserves in an expense section is normal in OM layouts.
                item_section = expense.get("section_context", "unknown") or "unknown"
                if not forced_category and item_section != "unknown":
                    INCOME_CATEGORIES = {
                        ExpenseCategory.GROSS_POTENTIAL_RENT, ExpenseCategory.OTHER_INCOME,
                        ExpenseCategory.REIMBURSEMENTS, ExpenseCategory.ACCOUNTS_RECEIVABLE,
                    }
                    EXPENSE_CATEGORIES = {
                        ExpenseCategory.REAL_ESTATE_TAXES, ExpenseCategory.INSURANCE,
                        ExpenseCategory.REPAIRS_MAINTENANCE, ExpenseCategory.GENERAL_ADMINISTRATIVE,
                        ExpenseCategory.PAYROLL, ExpenseCategory.UTILITIES,
                        ExpenseCategory.MANAGEMENT_FEES, ExpenseCategory.CONTRACT_SERVICES,
                        ExpenseCategory.OTHER_OPERATING_EXPENSES, ExpenseCategory.ADVERTISING_MARKETING,
                        ExpenseCategory.LEASING_FEES,
                    }

                    if item_section == "income" and category_enum in EXPENSE_CATEGORIES:
                        logger.warning(
                            f"Cross-classification conflict: '{desc}' is in income section but classified as "
                            f"{category_enum.value}. Forcing to UNCATEGORIZED for review."
                        )
                        category_enum = ExpenseCategory.UNCATEGORIZED
                        mapped_item["confidence"] = min(mapped_item.get("confidence", 0.85), 0.50)

                    elif item_section == "expense" and category_enum in INCOME_CATEGORIES:
                        # Capital Reserves in expense section is OK (OM layout convention)
                        logger.warning(
                            f"Cross-classification conflict: '{desc}' is in expense section but classified as "
                            f"{category_enum.value}. Forcing to UNCATEGORIZED for review."
                        )
                        category_enum = ExpenseCategory.UNCATEGORIZED
                        mapped_item["confidence"] = min(mapped_item.get("confidence", 0.85), 0.50)

                    elif item_section == "capex" and category_enum not in {ExpenseCategory.CAPITAL_RESERVES, ExpenseCategory.UNCATEGORIZED}:
                        logger.warning(
                            f"Cross-classification conflict: '{desc}' is in capex section but classified as "
                            f"{category_enum.value}. Forcing to CAPITAL_RESERVES."
                        )
                        category_enum = ExpenseCategory.CAPITAL_RESERVES

                # Note: Capital Reserves with section_context="expense" is intentionally
                # NOT flagged — it's a valid OM layout where CapEx appears inside the
                # expense section, above "Total Operating Expenses".

                # Fetch reasoning if available, otherwise default
                reasoning = mapped_item.get("reasoning", f"LLM mapped '{desc}' based on semantic similarity.")

                audit_log = AuditLog(
                    field_name=f"Expense: {category_enum.value}",
                    extracted_value=parsed_amount,
                    source="T12 Income Statement",
                    confidence_score=mapped_item.get("confidence", 0.85),
                    method=f"{reasoning} (Confidence: {mapped_item.get('confidence', 0.85):.0%})",
                    document_id=document_id,
                    page_number=expense.get("page_number"),
                    bbox=expense.get("bbox")
                )

                normalized_expenses.append(
                    StandardizedExpense(
                        original_text=desc,
                        mapped_category=category_enum,
                        amount=parsed_amount,
                        amount_t3=self._parse_amount(expense.get("amount_t3")) if expense.get("amount_t3") is not None else None,
                        amount_t6=self._parse_amount(expense.get("amount_t6")) if expense.get("amount_t6") is not None else None,
                        amount_t9=self._parse_amount(expense.get("amount_t9")) if expense.get("amount_t9") is not None else None,
                        confidence=mapped_item.get("confidence", 0.85),
                        audit_log=audit_log,
                        expense_year=expense.get("expense_year"),
                        section_context=item_section,
                        source_snippet=expense.get("source_snippet"),
                    )
                )
            return normalized_expenses
            
        except Exception as e:
            logger.error(f"An unexpected error occurred during expense normalization: {e}")
            return self._fallback_simple_mapping(raw_expenses, document_id)

    def normalize_expenses(self, raw_expenses: List[Dict], document_id: str = None) -> List[StandardizedExpense]:
        """
        Synchronous wrapper for backward compatibility.
        DEPRECATED: Use normalize_expenses_async.
        """
        import asyncio
        return asyncio.run(self.normalize_expenses_async(raw_expenses, document_id))

    def _fallback_simple_mapping_raw(self, raw_expenses: List[Dict]) -> List[Dict]:
        """
        Helper to generate 'mapped' structure using simple keyword matching.
        Used when a batch fails in async processing.
        """
        mapped_data = []
        for expense in raw_expenses:
            description = expense.get("description", "").lower()
            amount = abs(self._parse_amount(expense.get("amount")))
            
            # Simple keyword matching logic (duplicated from _fallback_simple_mapping but returns dicts)
            mapped_category = ExpenseCategory.UNCATEGORIZED.value
            if any(k in description for k in ["business tax", "business license", "city business", "franchise tax", "other taxes", "business / other"]):
                mapped_category = ExpenseCategory.GENERAL_ADMINISTRATIVE.value
            elif "tax" in description or "assessment" in description: mapped_category = ExpenseCategory.REAL_ESTATE_TAXES.value
            elif "insurance" in description: mapped_category = ExpenseCategory.INSURANCE.value
            elif "repair" in description or "maintenance" in description: mapped_category = ExpenseCategory.REPAIRS_MAINTENANCE.value
            elif "management" in description: mapped_category = ExpenseCategory.MANAGEMENT_FEES.value
            elif "util" in description or "gas" in description or "electric" in description or "waste" in description: mapped_category = ExpenseCategory.UTILITIES.value
            elif any(k in description for k in ["payroll", "staff", "salary", "wages", "onsite manager", "resident manager", "site manager"]): mapped_category = ExpenseCategory.PAYROLL.value
            elif "contract" in description or "service" in description: mapped_category = ExpenseCategory.CONTRACT_SERVICES.value
            elif "advertis" in description or "market" in description: mapped_category = ExpenseCategory.ADVERTISING_MARKETING.value
            elif any(k in description for k in ["rent control", "regulatory", "compliance fee", "license fee"]): mapped_category = ExpenseCategory.OTHER_OPERATING_EXPENSES.value
            elif any(k in description for k in ["parking", "garage", "laundry", "storage", "vending"]): mapped_category = ExpenseCategory.OTHER_INCOME.value

            mapped_data.append({
                "original_text": description,
                "mapped_category": mapped_category,
                "amount": amount,
                "confidence": 0.65
            })
        return mapped_data

    def _fallback_simple_mapping(self, raw_expenses: List[Dict], document_id: str = None) -> List[StandardizedExpense]:
        """A simple keyword-based mapping as a fallback when LLM fails."""
        normalized_expenses = []
        for expense in raw_expenses:
            description = expense.get("description", "").lower()
            amount = abs(self._parse_amount(expense.get("amount")))
            
            # Simple keyword matching
            mapped_category = ExpenseCategory.UNCATEGORIZED
            if any(k in description for k in ["business tax", "business license", "city business", "franchise tax", "other taxes", "business / other"]):
                mapped_category = ExpenseCategory.GENERAL_ADMINISTRATIVE
            elif "tax" in description or "assessment" in description:
                mapped_category = ExpenseCategory.REAL_ESTATE_TAXES
            elif "insurance" in description:
                mapped_category = ExpenseCategory.INSURANCE
            elif "repair" in description or "maintenance" in description:
                mapped_category = ExpenseCategory.REPAIRS_MAINTENANCE
            elif "management" in description:
                mapped_category = ExpenseCategory.MANAGEMENT_FEES
            elif "util" in description or "gas" in description or "electric" in description or "waste" in description:
                mapped_category = ExpenseCategory.UTILITIES
            elif any(k in description for k in ["payroll", "staff", "salary", "wages", "onsite manager", "resident manager", "site manager"]):
                mapped_category = ExpenseCategory.PAYROLL
            elif "contract" in description or "service" in description:
                mapped_category = ExpenseCategory.CONTRACT_SERVICES
            elif "advertis" in description or "market" in description:
                mapped_category = ExpenseCategory.ADVERTISING_MARKETING
            elif any(k in description for k in ["rent control", "regulatory", "compliance fee", "license fee"]):
                mapped_category = ExpenseCategory.OTHER_OPERATING_EXPENSES
            elif any(k in description for k in ["parking", "garage", "laundry", "storage", "vending"]):
                mapped_category = ExpenseCategory.OTHER_INCOME

            # Build audit log
            # Updated to match new schema: source_doc -> source, reasoning -> method
            audit_log = AuditLog(
                field_name=f"Expense: {mapped_category.value}",
                extracted_value=amount,
                source="T12 Income Statement",
                confidence_score=0.65,  # Lower confidence for fallback
                method=f"Fallback mapping: '{description}' matched to {mapped_category.value} via keyword matching",
                document_id=document_id
            )
            
            normalized_expenses.append(
                StandardizedExpense(
                    original_text=description,
                    mapped_category=mapped_category,
                    amount=amount,
                    confidence=0.65,  # Lower confidence for fallback
                    audit_log=audit_log
                )
            )
        return normalized_expenses

    def normalize_rent_roll(self, raw_rent_roll: List[Dict[str, Any]]) -> List[RentRollItem]:
        """
        Normalizes raw rent roll data into a list of RentRollItem objects.
        """
        normalized_rent_roll = []
        for item in raw_rent_roll:
            # FIX: Detect Surcharges vs Base Rent
            # If "surcharge" is in description or notes (if available), or if unit_type/tenant_name hints at it,
            # we should flag it or treat it carefully.
            # Ideally, extraction logic separates this, but if it comes in as a rent row with a note:
            # For now, we rely on the fact that surcharges usually don't look like standard units,
            # OR we ensure we parse the rent amount strictly.
            
            # If current_rent is huge or oddly specific and text mentions "surcharge", it might be an extra fee.
            # But the primary fix requested is: "Rent Roll 2715.pdf mentions a '10% surcharge if 5th student.'
            # This should be Other Income, not Gross Potential Rent."
            
            # Logic: If tenant_name or unit_type contains "surcharge", exclude from rent roll OR set rent to 0?
            # Better: If it's a surcharge line item, it shouldn't be a RentRollItem.
            # We filter it out if we detect "surcharge" or "fee" in the unit/tenant fields
            # AND the unit_number is not a valid unit number (e.g. "SURCHARGE").
            
            tenant_str = str(item.get("tenant_name", "")).lower()
            unit_str = str(item.get("unit_number", "")).lower()
            
            if "surcharge" in tenant_str or "surcharge" in unit_str:
                logger.info(f"Skipping rent roll item identified as surcharge: {item}")
                continue

            # --- FIX: Blacklist Tuition/Student Financial Aid items ---
            # Check tenant_name, unit_number, unit_type, and description
            u_type_lower = str(item.get("unit_type", "")).lower()
            
            blacklist_keywords = [
                "tuition", "scholarship", "financial aid", "student services", "semester",
                "undergraduate resident", "application fee", "admin fee", "late fee", "pet fee",
                "student housing", "housing fee", "activity fee", "service fee",
                # Expanded Aggressive Filter
                "grant", "living expenses", "resident tuition", "award letter",
                # Accounts Receivable / Non-Rent Items
                "security deposit", "accounts receivable", "last month", "prepaid rent",
                "deposit", "balance forward", "previous balance"
            ]
            
            check_fields = [tenant_str, unit_str, u_type_lower, str(item.get("description", "")).lower()]
            
            # Check for exact match or substring match
            found_keyword = None
            for field in check_fields:
                for keyword in blacklist_keywords:
                    if keyword in field:
                        found_keyword = keyword
                        break
                if found_keyword:
                    break

            if found_keyword:
                logger.warning(f"Excluded Rent Roll item due to student financial keyword: '{found_keyword}' in item: {item}")
                continue
            
            # --- FIX UNIT MIX: Exclude Parking Spaces ---
            # The user report says: "6 Blue Honda Accord... $120" (Parking Space).
            # We filter out items that look like parking based on keywords in unit number, unit type, or tenant name.
            # Also check if unit type is "Parking" or "Garage".
            is_parking = False
            for s in [tenant_str, unit_str, str(item.get("unit_type", "")).lower()]:
                if any(k in s for k in ["parking", "garage", "carport", "storage", "honda", "toyota", "ford", "bmw", "mercedes", "mazda", "chevrolet", "nissan"]):
                     # Be careful not to exclude a tenant named "Parker" or "Ford".
                     # If it's in unit_type, it's definitely parking.
                     # If it's in tenant_name, it's suspicious if it matches car models.
                     # Let's rely on explicit "parking" / "garage" in unit_type first.
                     pass

            # Explicit check on unit_type
            u_type_lower = str(item.get("unit_type", "")).lower()
            if u_type_lower in ["parking", "garage", "storage", "parking space"]:
                is_parking = True
            
            # Check for vehicle names in tenant_name if unit_number is small integer (like 6, 8, 9)
            # The report says: "6 Blue Honda Accord... $120"
            # This implies the extracted tenant name might be "Blue Honda Accord".
            if any(car in tenant_str for car in ["honda", "toyota", "ford ", "bmw", "mercedes", "mazda", "chevrolet", "nissan", "hyundai", "kia ", "jeep "]):
                is_parking = True
            
            if is_parking:
                logger.info(f"Skipping rent roll item identified as parking/storage: {item}")
                continue

            # --- FIX: Filter out Garbage Entries (e.g. "13 Unknown") ---
            # If unit_type is "Unknown" AND rents are 0, it's likely a bad extraction or a header/footer line interpreted as a unit.
            if u_type_lower == "unknown" and self._parse_amount(item.get("current_rent", 0)) == 0 and self._parse_amount(item.get("market_rent", 0)) == 0:
                logger.info(f"Skipping rent roll item identified as garbage/empty: {item}")
                continue

            # Pydantic will validate the types. We just need to ensure that the keys exist.
            # If market_rent is missing, default to current_rent or 0.0
            # Set defaults for missing or None values to prevent validation errors
            if item.get("current_rent") is None:
                item["current_rent"] = 0.0
            if item.get("market_rent") is None:
                item["market_rent"] = item.get("current_rent", 0.0) # market_rent can default to current_rent
            if item.get("lease_start") is None:
                item["lease_start"] = ""
            if item.get("tenant_name") is None:
                item["tenant_name"] = "VACANT"
            
            # New fields defaults
            # FIX: Revenue / Rent Roll Errors - Stabilized Rent is set to $0 for active units.
            # The Report: Shows Unit 2, 3, 5, 7, etc., have a "Current Rent" but a "Stabilized Rent" of $0.
            # Logic: If stabilized_rent is 0 or None, but current_rent > 0, default stabilized_rent to current_rent.
            # This assumes that for active units, the floor for stabilized rent is the current rent.
            
            current_rent_val = self._parse_amount(item.get("current_rent", 0.0))
            stabilized_rent_val = self._parse_amount(item.get("stabilized_rent", 0.0))
            
            if stabilized_rent_val <= 0 and current_rent_val > 0:
                stabilized_rent_val = current_rent_val
            elif stabilized_rent_val <= 0 and current_rent_val <= 0:
                # Only zero out if both are missing — preserve explicitly extracted
                # stabilized_rent for vacant units (e.g., Pro Forma rent from OM)
                stabilized_rent_val = 0.0

            # Parse unit size robustly
            unit_size_val = self._parse_int_robust(item.get("unit_size"))
            item["unit_size"] = unit_size_val

            if item.get("move_in_date") is None:
                item["move_in_date"] = ""

            # Ensure all required fields are present with some default if possible
            # u_type = item.get("unit_type", "Unknown")
            # # Normalize to remove "- Vacant" suffix if present (case insensitive) during ingestion
            # if u_type and isinstance(u_type, str):
            #     if u_type.lower().endswith(" - vacant"):
            #         u_type = u_type[:-9].strip()
            #     elif u_type.lower().endswith("-vacant"):
            #         u_type = u_type[:-7].strip()

            # Determine vacancy status via centralized helper
            from app.models.schemas import is_unit_vacant
            is_vacant_val = is_unit_vacant(
                current_rent=current_rent_val,
                tenant_name=item.get("tenant_name") or "",
                unit_type=item.get("unit_type") or "",
                move_in_date=item.get("move_in_date"),
                is_vacant_flag=item.get("is_vacant", False),
            )

            rent_roll_item_data = {
                "unit_number": item.get("unit_number") or "N/A",
                "unit_type": item.get("unit_type") or "Unknown",
                "unit_size": unit_size_val,
                "tenant_name": item.get("tenant_name") or "Unknown",
                "current_rent": current_rent_val, # Use robust parser
                "stabilized_rent": stabilized_rent_val,
                "market_rent": self._parse_amount(item.get("market_rent") or item.get("current_rent", 0.0)),
                "move_in_date": item.get("move_in_date", ""),
                "lease_start": item["lease_start"], # Already defaulted above
                "lease_end": item.get("lease_end", ""),
                "is_vacant": is_vacant_val
            }
            
            try:
                normalized_item = RentRollItem(**rent_roll_item_data)
                normalized_rent_roll.append(normalized_item)
            except Exception as e:
                logger.error(f"Error normalizing rent roll item: {rent_roll_item_data}. Error: {e}")

        return normalized_rent_roll



# import json
# from typing import List, Dict, Any
# from app.models.schemas import StandardizedExpense, ExpenseCategory, AuditLog, RentRollItem
# from datetime import datetime
# import logging

# logger = logging.getLogger(__name__)

# class NormalizationService:
#     def __init__(self, llm_service: "GeminiService"):
#         self.llm_service = llm_service

#     def normalize_expenses(self, raw_expenses: List[Dict]) -> List[StandardizedExpense]:
#         if not raw_expenses:
#             return []

#         categories = [e.value for e in ExpenseCategory]
        
#         try:
#             mapped_data = self.llm_service.map_expenses_to_categories(raw_expenses, categories)
            
#             normalized_expenses = []
#             for item in mapped_data:
#                 try:
#                     category_enum = ExpenseCategory(item["mapped_category"])
#                 except ValueError:
#                     category_enum = ExpenseCategory.UNCATEGORIZED

#                 # FIX: Keys match Schema EXACTLY now.
#                 audit_log = AuditLog(
#                     field_name=f"Expense: {category_enum.value}",
#                     extracted_value=item.get("amount", 0.0),
#                     source="T12 Income Statement",
#                     confidence_score=item.get("confidence", 0.85),
#                     method=f"LLM mapped '{item.get('original_text', '')}' to {category_enum.value} with {item.get('confidence', 0.85):.0%} confidence"
#                 )

#                 normalized_expenses.append(
#                     StandardizedExpense(
#                         original_text=item.get("original_text", ""),
#                         mapped_category=category_enum,
#                         amount=item.get("amount", 0.0),
#                         confidence=item.get("confidence", 0.85),
#                         audit_log=audit_log
#                     )
#                 )
#             return normalized_expenses
            
#         except Exception as e:
#             logger.error(f"Normalization error: {e}")
#             return self._fallback_simple_mapping(raw_expenses)

#     def _fallback_simple_mapping(self, raw_expenses: List[Dict]) -> List[StandardizedExpense]:
#         normalized_expenses = []
#         for expense in raw_expenses:
#             description = expense.get("description", "").lower()
#             amount = expense.get("amount", 0.0)
            
#             mapped_category = ExpenseCategory.UNCATEGORIZED
#             if "tax" in description: mapped_category = ExpenseCategory.REAL_ESTATE_TAXES
#             elif "insurance" in description: mapped_category = ExpenseCategory.INSURANCE
#             elif "repair" in description: mapped_category = ExpenseCategory.REPAIRS_MAINTENANCE
#             elif "management" in description: mapped_category = ExpenseCategory.MANAGEMENT_FEES
#             elif "util" in description: mapped_category = ExpenseCategory.UTILITIES
#             elif "water" in description: mapped_category = ExpenseCategory.UTILITIES
#             elif "electric" in description: mapped_category = ExpenseCategory.UTILITIES
            
#             # FIX: Keys match Schema
#             audit_log = AuditLog(
#                 field_name=f"Expense: {mapped_category.value}",
#                 extracted_value=amount,
#                 source="T12 Income Statement",
#                 confidence_score=0.65,  # Lower confidence for fallback
#                 method=f"Fallback mapping: '{description}' matched to {mapped_category.value} via keyword matching"
#             )
            
#             normalized_expenses.append(
#                 StandardizedExpense(
#                     original_text=description,
#                     mapped_category=mapped_category,
#                     amount=amount,
#                     confidence=0.65,
#                     audit_log=audit_log
#                 )
#             )
#         return normalized_expenses

#     def normalize_rent_roll(self, raw_rent_roll: List[Dict[str, Any]]) -> List[RentRollItem]:
#         normalized_rent_roll = []
#         for item in raw_rent_roll:
#             # Safer parsing with defaults
#             try:
#                 rent_roll_item_data = {
#                     "unit_number": str(item.get("unit_number", "N/A")),
#                     "unit_type": str(item.get("unit_type", "Unknown")),
#                     "tenant_name": str(item.get("tenant_name", "Unknown")),
#                     "current_rent": float(item.get("current_rent") or 0.0),
#                     "market_rent": float(item.get("market_rent") or item.get("current_rent") or 0.0),
#                     "lease_start": str(item.get("lease_start", "")),
#                     "lease_end": str(item.get("lease_end", "")),
#                 }
#                 normalized_item = RentRollItem(**rent_roll_item_data)
#                 normalized_rent_roll.append(normalized_item)
#             except Exception as e:
#                 logger.error(f"Rent roll error: {e}")

#         return normalized_rent_roll