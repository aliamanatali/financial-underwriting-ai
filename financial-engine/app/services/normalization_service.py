import json
from typing import List, Dict
from app.models.financial_analysis import StandardizedExpense, ExpenseCategory
import logging

logger = logging.getLogger(__name__)

class NormalizationService:
    def __init__(self, llm_service: "GeminiService"):
        self.llm_service = llm_service

    def normalize_expenses(self, raw_expenses: List[Dict]) -> List[StandardizedExpense]:
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
                    StandardizedExpense(
                        original_text=item["original_text"],
                        mapped_category=category_enum,
                        amount=item["amount"],
                        confidence=item["confidence"],
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
        """A simple keyword-based mapping as a fallback."""
        normalized_expenses = []
        for expense in raw_expenses:
            description = expense.get("description", "").lower()
            mapped_category = ExpenseCategory.OTHER
            if "tax" in description:
                mapped_category = ExpenseCategory.TAXES
            elif "insurance" in description:
                mapped_category = ExpenseCategory.INSURANCE
            elif "repair" in description or "maintenance" in description:
                mapped_category = ExpenseCategory.REPAIRS
            elif "management" in description:
                mapped_category = ExpenseCategory.MANAGEMENT
            elif "util" in description or "gas" in description or "electric" in description:
                mapped_category = ExpenseCategory.UTILITIES
            
            normalized_expenses.append(
                StandardizedExpense(
                    original_text=expense.get("description", ""),
                    mapped_category=mapped_category,
                    amount=expense.get("amount", 0.0),
                    confidence=0.5, # Lower confidence for fallback
                )
            )
        return normalized_expenses