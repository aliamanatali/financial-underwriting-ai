import json
from typing import List, Dict, Any
from app.models.schemas import StandardizedExpense, ExpenseCategory, AuditLog, RentRollItem
import logging

logger = logging.getLogger(__name__)

class NormalizationService:
    def __init__(self, llm_service: Any):
        self.llm_service = llm_service

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
        Normalizes a list of raw expense data into StandardizedExpense objects using parallel batch processing.
        """
        import asyncio
        if not raw_expenses:
            return []

        categories = [e.value for e in ExpenseCategory]
        
        # Batch size for processing
        BATCH_SIZE = 25
        batches = [raw_expenses[i:i + BATCH_SIZE] for i in range(0, len(raw_expenses), BATCH_SIZE)]
        
        logger.info(f"Normalizing {len(raw_expenses)} expenses in {len(batches)} batches")
        
        async def process_batch(batch):
            try:
                # Use the async version of map_expenses_to_categories
                return await self.llm_service.map_expenses_to_categories_async(batch, categories)
            except Exception as e:
                logger.error(f"Error processing batch: {e}")
                # Return partial fallback for this batch or empty list to trigger global fallback?
                # Let's return empty list and let the validation logic handle it, or maybe implement
                # a local fallback here. For now, returning empty will just miss these expenses in the
                # LLM path, effectively dropping them unless we fallback entirely.
                # Better approach: If a batch fails, we should probably fallback ONLY for that batch.
                return []

        # Execute batches in parallel
        results = await asyncio.gather(*[process_batch(batch) for batch in batches])
        
        # Flatten results
        mapped_data = []
        failed_batches = 0
        for i, res in enumerate(results):
            if res:
                mapped_data.extend(res)
            else:
                # If batch failed (returned empty due to error), fallback for that specific batch
                failed_batches += 1
                logger.warning(f"Batch {i} failed LLM processing, applying fallback mapping")
                # We need to manually construct the "mapped" structure for fallback
                fallback_batch = self._fallback_simple_mapping_raw(batches[i])
                mapped_data.extend(fallback_batch)

        if not mapped_data and raw_expenses:
             logger.warning("All batches failed LLM processing. Using complete fallback.")
             return self._fallback_simple_mapping(raw_expenses, document_id)

        try:
            normalized_expenses = []
            for item in mapped_data:
                # Ensure the mapped category is a valid enum member
                try:
                    category_enum = ExpenseCategory(item["mapped_category"])
                except ValueError:
                    # Try to fuzzy match or just default
                    category_enum = ExpenseCategory.UNCATEGORIZED

                # Expenses are outflows, so we normalize them to positive magnitudes.
                parsed_amount = abs(self._parse_amount(item.get("amount")))

                audit_log = AuditLog(
                    field_name=f"Expense: {category_enum.value}",
                    extracted_value=parsed_amount,
                    source="T12 Income Statement",
                    confidence_score=item.get("confidence", 0.85),
                    method=f"LLM mapped '{item.get('original_text', '')}' to {category_enum.value} with {item.get('confidence', 0.85):.0%} confidence",
                    document_id=document_id,
                    page_number=item.get("page_number"),
                    bbox=item.get("bbox")
                )

                normalized_expenses.append(
                    StandardizedExpense(
                        original_text=item.get("original_text", ""),
                        mapped_category=category_enum,
                        amount=parsed_amount,
                        confidence=item.get("confidence", 0.85),
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