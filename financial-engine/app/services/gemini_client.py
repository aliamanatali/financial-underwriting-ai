import os
import json
import logging
import base64
from typing import List, Dict, Optional, Type, Any
import google.generativeai as genai
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(
            'gemini-2.5-pro',
            generation_config={"temperature": 0.0}
        )

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

    async def generate_content_async(self, prompt: str, pdf_data: Optional[bytes] = None) -> str:
        """
        Generates content using the Gemini model asynchronously, with optional PDF data.
        """
        try:
            if pdf_data:
                pdf_part = {
                    "mime_type": "application/pdf",
                    "data": base64.b64encode(pdf_data).decode("utf-8")
                }
                response = await self.model.generate_content_async([prompt, pdf_part])
            else:
                response = await self.model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating content asynchronously with Gemini: {e}")
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

    async def generate_structured_data_async(
        self,
        prompt: str,
        pdf_data: Optional[bytes] = None,
        pydantic_schema: Optional[Type[BaseModel]] = None,
        expect_list: bool = True
    ) -> Any:
        """
        Generates structured data asynchronously. Returns List[Dict] if expect_list=True, else Dict.
        
        Args:
            prompt: The prompt to send to Gemini
            pdf_data: Optional PDF bytes for vision-based processing
            pydantic_schema: Optional Pydantic model for validation
            expect_list: If True, ensures output is a list. If False, expects a single dict.
        
        Returns:
            List[Dict] if expect_list=True, Dict otherwise
        """
        response_text = await self.generate_content_async(prompt, pdf_data)
        
        # --- FIX: Removed the strict startswith check here ---
        # We trust _clean_json_string to find the JSON logic inside Markdown

        try:
            cleaned_json = self._clean_json_string(response_text)
            data = json.loads(cleaned_json)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error for text: '{response_text}'. Attempting correction. Error: {e}")
            # Ask Gemini to fix the JSON
            correction_prompt = f"""The following text is not valid JSON. Please correct it and return ONLY the valid JSON.
Do not include any other text or explanations.

{response_text}"""
            corrected_response = await self.generate_content_async(correction_prompt)
            cleaned_json = self._clean_json_string(corrected_response)
            try:
                data = json.loads(cleaned_json)
            except json.JSONDecodeError as e2:
                logger.error(f"Failed to parse even after correction: {e2}")
                raise ValueError(f"Gemini returned invalid JSON even after correction: {cleaned_json}")

        # Handle List vs Single Object based on expect_list flag
        if expect_list:
            # Ensure we return a list
            if not isinstance(data, list):
                data = [data]
            
            # Validate with Pydantic if schema provided
            if pydantic_schema:
                validated_list = []
                for item in data:
                    if isinstance(item, dict):
                        try:
                            validated_obj = pydantic_schema(**item)
                            validated_list.append(validated_obj.model_dump())
                        except ValidationError as e:
                            logger.warning(f"Validation error for item: {e}, attempting to fix.")
                            # Add a more explicit prompt to fix the validation error
                            correction_prompt = f"""The following JSON object is invalid. Please correct it based on the schema and return ONLY the valid JSON.
Invalid JSON: {item}
Error: {e}
"""
                            corrected_response = await self.generate_content_async(correction_prompt)
                            cleaned_json = self._clean_json_string(corrected_response)
                            try:
                                corrected_data = json.loads(cleaned_json)
                                validated_obj = pydantic_schema(**corrected_data)
                                validated_list.append(validated_obj.model_dump())
                            except (json.JSONDecodeError, ValidationError) as e2:
                                logger.error(f"Failed to fix validation error: {e2}")
                                # If the correction fails, we will not include the item in the list
                                pass
                return validated_list
            return data # Return raw data if no schema is provided
        else:
            # Expecting single object - return first item if list, else return dict
            if isinstance(data, list):
                data = data[0] if data else {}
            
            # Validate with Pydantic if schema provided
            if pydantic_schema:
                try:
                    validated_obj = pydantic_schema(**data)
                    return validated_obj.model_dump()
                except ValidationError as e:
                    logger.error(f"Pydantic validation failed for single object: {e}. Raw data: {data}")
                    raise ValueError(f"LLM output failed Pydantic validation for single object: {e}")
            
            return data

    def generate_structured_data(
        self,
        prompt: str,
        pdf_data: Optional[bytes] = None,
        pydantic_schema: Optional[Type[BaseModel]] = None,
        expect_list: bool = True
    ) -> Any:
        """
        Generates structured data. Returns List[Dict] if expect_list=True, else Dict.
        
        Args:
            prompt: The prompt to send to Gemini
            pdf_data: Optional PDF bytes for vision-based processing
            pydantic_schema: Optional Pydantic model for validation
            expect_list: If True, ensures output is a list. If False, expects a single dict.
        
        Returns:
            List[Dict] if expect_list=True, Dict otherwise
        """
        response_text = self.generate_content(prompt, pdf_data)
        
        # --- FIX: Removed the strict startswith check here ---
        # We trust _clean_json_string to find the JSON logic inside Markdown

        try:
            cleaned_json = self._clean_json_string(response_text)
            data = json.loads(cleaned_json)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error for text: '{response_text}'. Attempting correction. Error: {e}")
            # Ask Gemini to fix the JSON
            correction_prompt = f"""The following text is not valid JSON. Please correct it and return ONLY the valid JSON.
Do not include any other text or explanations.

{response_text}"""
            corrected_response = self.generate_content(correction_prompt)
            cleaned_json = self._clean_json_string(corrected_response)
            try:
                data = json.loads(cleaned_json)
            except json.JSONDecodeError as e2:
                logger.error(f"Failed to parse even after correction: {e2}")
                raise ValueError(f"Gemini returned invalid JSON even after correction: {cleaned_json}")

        # Handle List vs Single Object based on expect_list flag
        if expect_list:
            # Ensure we return a list
            if not isinstance(data, list):
                data = [data]
            
            # Validate with Pydantic if schema provided
            if pydantic_schema:
                validated_list = []
                for item in data:
                    if isinstance(item, dict):
                        try:
                            validated_obj = pydantic_schema(**item)
                            validated_list.append(validated_obj.model_dump())
                        except ValidationError as e:
                            logger.warning(f"Validation error for item: {e}, attempting to fix.")
                            # Add a more explicit prompt to fix the validation error
                            correction_prompt = f"""The following JSON object is invalid. Please correct it based on the schema and return ONLY the valid JSON.
Invalid JSON: {item}
Error: {e}
"""
                            corrected_response = self.generate_content(correction_prompt)
                            cleaned_json = self._clean_json_string(corrected_response)
                            try:
                                corrected_data = json.loads(cleaned_json)
                                validated_obj = pydantic_schema(**corrected_data)
                                validated_list.append(validated_obj.model_dump())
                            except (json.JSONDecodeError, ValidationError) as e2:
                                logger.error(f"Failed to fix validation error: {e2}")
                                # If the correction fails, we will not include the item in the list
                                pass
                return validated_list
            return data # Return raw data if no schema is provided
        else:
            # Expecting single object - return first item if list, else return dict
            if isinstance(data, list):
                data = data[0] if data else {}
            
            # Validate with Pydantic if schema provided
            if pydantic_schema:
                try:
                    validated_obj = pydantic_schema(**data)
                    return validated_obj.model_dump()
                except ValidationError as e:
                    logger.error(f"Pydantic validation failed for single object: {e}. Raw data: {data}")
                    raise ValueError(f"LLM output failed Pydantic validation for single object: {e}")
            
            return data

    def _clean_json_string(self, json_string: str) -> str:
        """
        Cleans a JSON string that may be wrapped in markdown.
        """
        # Use regex to find JSON content between ```json and ```
        import re
        match = re.search(r"```json\s*([\s\S]*?)\s*```", json_string, re.DOTALL)
        if match:
            return match.group(1).strip()
        return json_string.strip()
