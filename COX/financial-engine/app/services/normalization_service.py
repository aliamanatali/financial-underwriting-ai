import json
from typing import List, Dict
from app.models.schemas import FinancialLineItem, ExpenseCategory
import logging

logger = logging.getLogger(__name__)

class NormalizationService:
    def __init__(self, llm_service: "GeminiService"):
        self.llm_service = llm_service

    def normalize_expenses(self, raw_expenses: List[Dict]) -> List[FinancialLineItem]:
        """
        Normalizes a list of raw expense data into a standardized format using an LLM.
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
                        f"Defaulting to '{ExpenseCategory.OTHER.value}'."
                    )
                    category_enum = ExpenseCategory.OTHER

                normalized_expenses.append(
                    FinancialLineItem(
                        category=category_enum.value,
                        value=item["amount"],
                        period="Annual",
                        type="Historical"
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

    def _fallback_simple_mapping(self, raw_expenses: List[Dict]) -> List[FinancialLineItem]:
        """A simple keyword-based mapping as a fallback."""
        normalized_expenses = []
        for expense in raw_expenses:
            description = expense.get("description", "").lower()
            mapped_category = ExpenseCategory.UNCATEGORIZED
            if "tax" in description:
                mapped_category = ExpenseCategory.REAL_ESTATE_TAXES
            elif "insurance" in description:
                mapped_category = ExpenseCategory.INSURANCE
            elif "repair" in description or "maintenance" in description:
                mapped_category = ExpenseCategory.REPAIRS_MAINTENANCE
            elif "management" in description:
                mapped_category = ExpenseCategory.MANAGEMENT_FEES
            elif "util" in description or "gas" in description or "electric" in description:
                mapped_category = ExpenseCategory.UTILITIES
            
            normalized_expenses.append(
                FinancialLineItem(
                    category=mapped_category.value,
                    value=expense.get("amount", 0.0),
                    period="Annual",
                    type="Historical"
                )
            )
        return normalized_expenses