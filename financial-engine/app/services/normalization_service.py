import json
from typing import List, Dict, Any
from app.models.schemas import StandardizedExpense, ExpenseCategory, AuditLog, RentRollItem
import logging

logger = logging.getLogger(__name__)

class NormalizationService:
    def __init__(self, llm_service: "GeminiService"):
        self.llm_service = llm_service

    def normalize_expenses(self, raw_expenses: List[Dict]) -> List[StandardizedExpense]:
        """
        Normalizes a list of raw expense data into StandardizedExpense objects.
        Each expense includes:
        - original_text: What the PDF said (e.g., "Repairs & Maintenance - Plumbing")
        - mapped_category: The standardized category (e.g., ExpenseCategory.REPAIRS_MAINTENANCE)
        - amount: The dollar amount
        - confidence: How confident the mapping is (0.0 to 1.0)
        - audit_log: Source and reasoning for the mapping
        """
        if not raw_expenses:
            return []

        categories = [e.value for e in ExpenseCategory]
        
        try:
            mapped_data = self.llm_service.map_expenses_to_categories(raw_expenses, categories)
            
            normalized_expenses = []
            for item in mapped_data:
                # Ensure the mapped category is a valid enum member
                try:
                    category_enum = ExpenseCategory(item["mapped_category"])
                except ValueError:
                    logger.warning(
                        f"LLM mapped to an invalid category: '{item['mapped_category']}'. "
                        f"Defaulting to '{ExpenseCategory.UNCATEGORIZED.value}'."
                    )
                    category_enum = ExpenseCategory.UNCATEGORIZED

                # Build audit log for this normalized expense
                audit_log = AuditLog(
                    field_name=f"Expense: {category_enum.value}",
                    extracted_value=item["amount"],
                    source_doc="T12 Income Statement",
                    confidence_score=item.get("confidence", 0.85),
                    reasoning=f"LLM mapped '{item['original_text']}' to {category_enum.value} with {item.get('confidence', 0.85):.0%} confidence"
                )

                normalized_expenses.append(
                    StandardizedExpense(
                        original_text=item.get("original_text", ""),
                        mapped_category=category_enum,
                        amount=item.get("amount", 0.0),
                        confidence=item.get("confidence", 0.85),
                        audit_log=audit_log
                    )
                )
            return normalized_expenses
            
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error processing LLM response for expense normalization: {e}")
            # Fallback to simple mapping if LLM fails
            return self._fallback_simple_mapping(raw_expenses)
        except Exception as e:
            logger.error(f"An unexpected error occurred during expense normalization: {e}")
            # Fallback for any other unexpected errors
            return self._fallback_simple_mapping(raw_expenses)

    def _fallback_simple_mapping(self, raw_expenses: List[Dict]) -> List[StandardizedExpense]:
        """A simple keyword-based mapping as a fallback when LLM fails."""
        normalized_expenses = []
        for expense in raw_expenses:
            description = expense.get("description", "").lower()
            amount = expense.get("amount", 0.0)
            
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
            audit_log = AuditLog(
                field_name=f"Expense: {mapped_category.value}",
                extracted_value=amount,
                source_doc="T12 Income Statement",
                confidence_score=0.65,  # Lower confidence for fallback
                reasoning=f"Fallback mapping: '{description}' matched to {mapped_category.value} via keyword matching"
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
            if item.get("market_rent") is None:
                item["market_rent"] = item.get("current_rent", 0.0)

            # If lease_start is missing, default to an empty string
            if item.get("lease_start") is None:
                item["lease_start"] = ""

            # Ensure all required fields are present with some default if possible
            rent_roll_item_data = {
                "unit_number": item.get("unit_number", "N/A"),
                "unit_type": item.get("unit_type", "Unknown"),
                "tenant_name": item.get("tenant_name", "Unknown"),
                "current_rent": item.get("current_rent", 0.0),
                "market_rent": item["market_rent"], # Already defaulted above
                "lease_start": item["lease_start"], # Already defaulted above
                "lease_end": item.get("lease_end", ""),
            }
            
            try:
                normalized_item = RentRollItem(**rent_roll_item_data)
                normalized_rent_roll.append(normalized_item)
            except Exception as e:
                logger.error(f"Error normalizing rent roll item: {rent_roll_item_data}. Error: {e}")

        return normalized_rent_roll