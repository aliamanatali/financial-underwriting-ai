import os
import json
import logging
from typing import List, Dict
import google.generativeai as genai

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-pro')

    def generate_content(self, prompt: str) -> str:
        """
        Generates content using the Gemini model.
        """
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            # Handle potential API errors
            return f"An error occurred: {e}"

    def map_expenses_to_categories(self, raw_expenses: List[Dict], categories: List[str]) -> List[Dict]:
        """
        Maps raw expenses to predefined categories using the Gemini model.
        """
        prompt = f"""
        Given a list of raw expenses and a list of categories, map each expense to the most appropriate category.
        Return a JSON array where each object has 'original_text', 'mapped_category', 'amount', and 'confidence'.
        Confidence should be a float between 0 and 1.

        Raw Expenses: {raw_expenses}
        Categories: {categories}
        """
        try:
            response = self.model.generate_content(prompt)
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Error mapping expenses to categories: {e}")
            return []
