import os
import json
import logging
import base64
from typing import List, Dict, Optional, Type
import google.generativeai as genai
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-pro')

    def generate_content(self, prompt: str, pdf_data: Optional[bytes] = None) -> str:
        """
        Generates content using the Gemini model, with optional PDF data.
        """
        try:
            if pdf_data:
                pdf_part = {
                    "mime_type": "application/pdf",
                    "data": base64.b64encode(pdf_data).decode("utf-8")
                }
                response = self.model.generate_content([prompt, pdf_part])
            else:
                response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating content with Gemini: {e}")
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
            cleaned_json = self._clean_json_string(response.text)
            return json.loads(cleaned_json)
        except Exception as e:
            logger.error(f"Error mapping expenses to categories: {e}")
            return []

    def generate_structured_data(
        self,
        prompt: str,
        pdf_data: Optional[bytes] = None,
        pydantic_schema: Optional[Type[BaseModel]] = None
    ) -> List[Dict]:
        """
        Generates structured data, validates it, and performs self-correction.
        Always returns a list of dicts for consistency.
        """
        response_text = self.generate_content(prompt, pdf_data)
        
        try:
            # First attempt to parse the cleaned JSON
            cleaned_json = self._clean_json_string(response_text)
            data = json.loads(cleaned_json)
        except json.JSONDecodeError:
            # If parsing fails, ask the LLM to correct the JSON
            correction_prompt = f"""
            The following text is not valid JSON. Please correct it and return only the valid JSON.
            Do not include any other text or explanations in your response.

            {response_text}
            """
            corrected_response = self.generate_content(correction_prompt)
            cleaned_json = self._clean_json_string(corrected_response)
            data = json.loads(cleaned_json)

        # Ensure data is always a list
        if not isinstance(data, list):
            data = [data]

        # Validate with Pydantic schema if provided
        if pydantic_schema:
            try:
                # Validate each item in the list
                validated_data = [pydantic_schema(**item) if isinstance(item, dict) else pydantic_schema(**item.model_dump()) for item in data]
                return [item.model_dump() for item in validated_data]
            except (ValidationError, TypeError) as e:
                logger.error(f"Pydantic validation failed: {e}")
                raise ValueError(f"LLM output failed Pydantic validation: {e}")

        return data

    def _clean_json_string(self, json_string: str) -> str:
        """
        Cleans a JSON string that may be wrapped in markdown.
        """
        if json_string.startswith("```json"):
            json_string = json_string[7:]
        if json_string.endswith("```"):
            json_string = json_string[:-3]
        return json_string.strip()
