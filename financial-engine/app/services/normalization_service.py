import json
from typing import List, Dict, Any
from app.models.schemas import StandardizedExpense, ExpenseCategory, AuditLog, RentRollItem
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class NormalizationService:
    def __init__(self, llm_service: Any):
        self.llm_service = llm_service
        self.collection_name = "expense_mappings"

    async def _get_cached_mappings(self, descriptions: List[str]) -> Dict[str, Dict]:
        """Retrieve cached mappings from Redis and MongoDB."""
        from app.db.mongodb import get_database
        from app.db.redis import redis_client
        from app.config import settings
        
        cache = {}
        missing_in_redis = []

        # 1. Try Redis
        if redis_client.client:
            keys = [f"mapping:{desc}" for desc in descriptions]
            try:
                values = await redis_client.client.mget(keys)
                for desc, val in zip(descriptions, values):
                    if val:
                        try:
                            cache[desc] = json.loads(val)
                        except json.JSONDecodeError:
                            missing_in_redis.append(desc)
                    else:
                        missing_in_redis.append(desc)
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
                # Find documents where original_text is in our list
                cursor = db[self.collection_name].find({"original_text": {"$in": missing_in_redis}})
                
                mongo_hits = []
                async for doc in cursor:
                    if "original_text" in doc and "mapped_category" in doc:
                        clean_doc = {
                            "original_text": doc["original_text"],
                            "mapped_category": doc["mapped_category"],
                            "confidence": doc.get("confidence", 0.85)
                        }
                        cache[doc["original_text"]] = clean_doc
                        mongo_hits.append(clean_doc)
                
                # Populate Redis with Mongo hits
                if redis_client.client and mongo_hits:
                    try:
                        pipeline = redis_client.client.pipeline()
                        for hit in mongo_hits:
                            pipeline.set(f"mapping:{hit['original_text']}", json.dumps(hit), ex=86400 * 30) # 30 days
                        await pipeline.execute()
                    except Exception as e:
                        logger.error(f"Redis populate error: {e}")

            except Exception as e:
                logger.error(f"Failed to fetch cached mappings from Mongo: {e}")
        
        return cache

    async def _save_mappings(self, mappings: List[Dict]):
        """Save new mappings to MongoDB and Redis."""
        from app.db.mongodb import get_database
        from app.db.redis import redis_client
        from app.config import settings
        from pymongo import UpdateOne
        
        if not mappings:
            return

        # 1. Save to Redis
        if redis_client.client:
            try:
                pipeline = redis_client.client.pipeline()
                for item in mappings:
                     if "original_text" in item and "mapped_category" in item:
                        cache_obj = {
                            "original_text": item["original_text"],
                            "mapped_category": item["mapped_category"],
                            "confidence": item.get("confidence", 0.85)
                        }
                        pipeline.set(f"mapping:{item['original_text']}", json.dumps(cache_obj), ex=86400 * 30)
                await pipeline.execute()
            except Exception as e:
                logger.error(f"Failed to save mappings to Redis: {e}")

        # 2. Save to MongoDB
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

    def _parse_amount(self, value: Any) -> float:
        """Helper to safely parse amount strings/floats."""
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Remove currency symbols, commas, and whitespace
            clean_val = value.replace('$', '').replace(',', '').strip()
            # Handle negative values in parentheses e.g. (500)
            if clean_val.startswith('(') and clean_val.endswith(')'):
                clean_val = '-' + clean_val[1:-1]
            
            # Handle negative signs with spaces e.g. "- 500" -> "-500"
            if clean_val.startswith('-') and ' ' in clean_val:
                 clean_val = clean_val.replace(' ', '')

            try:
                return float(clean_val)
            except ValueError:
                return 0.0
        return 0.0

    async def normalize_expenses_async(self, raw_expenses: List[Dict], document_id: str = None) -> List[StandardizedExpense]:
        """
        Normalizes a list of raw expense data into StandardizedExpense objects using cached mappings and parallel batch processing.
        """
        import asyncio
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
        
        # 1. Check Cache
        descriptions = [item.get("description", "") for item in raw_expenses]
        cached_mappings = await self._get_cached_mappings(descriptions)
        
        uncached_expenses = []
        uncached_indices = [] # Track original indices to merge back (not strictly necessary if we just list append)
        
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
                    "confidence": cached.get("confidence", 0.95), # High confidence for cache
                    "page_number": expense.get("page_number"),
                    "bbox": expense.get("bbox")
                }
            else:
                uncached_expenses.append(expense)

        logger.info(f"Normalization Cache Hit Rate: {len(final_mapped_data_dict)}/{len(raw_expenses)}")

        # 2. Process Uncached in Batches
        new_mappings_to_save = []
        
        if uncached_expenses:
            BATCH_SIZE = 25
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

            # Execute batches in parallel
            results = await asyncio.gather(*[process_batch(batch) for batch in batches])
            
            # Flatten results and prepare for merge
            for i, res in enumerate(results):
                if res:
                    for item in res:
                        # Ensure original amount is preserved if LLM messed it up,
                        # but usually map_expenses_to_categories returns what we sent plus fields.
                        # We need to link back to the raw expense to get metadata if lost.
                        # Assuming LLM returns 'original_text' matching input 'description'.
                        desc = item.get("original_text", "")
                        
                        # Find original expense for this desc to get amount/metadata if needed
                        # (Simple lookup assumes uniqueness in batch or sufficient context)
                        
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

            # 3. Save new mappings to cache
            if new_mappings_to_save:
                # Fire and forget save? Or await? Await is safer.
                await self._save_mappings(new_mappings_to_save)

        # 4. Construct Final List
        try:
            normalized_expenses = []
            
            # Iterate through original raw_expenses to maintain order and ensure all are covered
            for expense in raw_expenses:
                desc = expense.get("description", "")
                mapped_item = final_mapped_data_dict.get(desc)
                
                if not mapped_item:
                    # Should not happen if fallback logic works, but just in case
                    # Apply single fallback
                    fallback_list = self._fallback_simple_mapping_raw([expense])
                    mapped_item = fallback_list[0]
                
                # Ensure the mapped category is a valid enum member
                try:
                    category_enum = ExpenseCategory(mapped_item["mapped_category"])
                except ValueError:
                    category_enum = ExpenseCategory.UNCATEGORIZED

                # Expenses are outflows, so we normalize them to positive magnitudes.
                # Use the amount from the raw expense (source of truth) rather than LLM output if possible,
                # but LLM output usually echoes it. Safest is raw expense amount.
                amount_val = expense.get("amount")
                parsed_amount = abs(self._parse_amount(amount_val))

                audit_log = AuditLog(
                    field_name=f"Expense: {category_enum.value}",
                    extracted_value=parsed_amount,
                    source="T12 Income Statement",
                    confidence_score=mapped_item.get("confidence", 0.85),
                    method=f"LLM mapped '{desc}' to {category_enum.value} with {mapped_item.get('confidence', 0.85):.0%} confidence",
                    document_id=document_id,
                    page_number=expense.get("page_number"),
                    bbox=expense.get("bbox")
                )

                normalized_expenses.append(
                    StandardizedExpense(
                        original_text=desc,
                        mapped_category=category_enum,
                        amount=parsed_amount,
                        confidence=mapped_item.get("confidence", 0.85),
                        audit_log=audit_log
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
            if "tax" in description: mapped_category = ExpenseCategory.REAL_ESTATE_TAXES.value
            elif "insurance" in description: mapped_category = ExpenseCategory.INSURANCE.value
            elif "repair" in description or "maintenance" in description: mapped_category = ExpenseCategory.REPAIRS_MAINTENANCE.value
            elif "management" in description: mapped_category = ExpenseCategory.MANAGEMENT_FEES.value
            elif "util" in description or "gas" in description or "electric" in description or "waste" in description: mapped_category = ExpenseCategory.UTILITIES.value
            elif "payroll" in description or "staff" in description: mapped_category = ExpenseCategory.PAYROLL.value
            elif "contract" in description or "service" in description: mapped_category = ExpenseCategory.CONTRACT_SERVICES.value
            elif "advertis" in description or "market" in description: mapped_category = ExpenseCategory.ADVERTISING_MARKETING.value
            
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
            if "tax" in description:
                mapped_category = ExpenseCategory.REAL_ESTATE_TAXES
            elif "insurance" in description:
                mapped_category = ExpenseCategory.INSURANCE
            elif "repair" in description or "maintenance" in description:
                mapped_category = ExpenseCategory.REPAIRS_MAINTENANCE
            elif "management" in description:
                mapped_category = ExpenseCategory.MANAGEMENT_FEES
            elif "util" in description or "gas" in description or "electric" in description or "waste" in description:
                mapped_category = ExpenseCategory.UTILITIES
            elif "payroll" in description or "staff" in description:
                mapped_category = ExpenseCategory.PAYROLL
            elif "contract" in description or "service" in description:
                mapped_category = ExpenseCategory.CONTRACT_SERVICES
            elif "advertis" in description or "market" in description:
                mapped_category = ExpenseCategory.ADVERTISING_MARKETING
            
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
            if item.get("stabilized_rent") is None:
                item["stabilized_rent"] = 0.0
            if item.get("unit_size") is None:
                item["unit_size"] = 0
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

            rent_roll_item_data = {
                "unit_number": item.get("unit_number", "N/A"),
                "unit_type": item.get("unit_type", "Unknown"),
                "unit_size": int(item.get("unit_size", 0)),
                "tenant_name": item.get("tenant_name", "Unknown"),
                "current_rent": item.get("current_rent", 0.0),
                "stabilized_rent": item.get("stabilized_rent", 0.0),
                "market_rent": item["market_rent"], # Already defaulted above
                "move_in_date": item.get("move_in_date", ""),
                "lease_start": item["lease_start"], # Already defaulted above
                "lease_end": item.get("lease_end", ""),
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