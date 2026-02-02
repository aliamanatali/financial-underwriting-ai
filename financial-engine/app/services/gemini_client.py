import os
import json
import logging
import base64
import asyncio
import time
import hashlib
from typing import List, Dict, Optional, Type, Any
from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions
from pydantic import BaseModel, ValidationError
from app.config import settings
from app.db.redis import redis_client

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        # Initialize the new client
        self.client = genai.Client(api_key=self.api_key)
        
        # Model names
        self.model_name = settings.gemini_model or 'gemini-2.0-flash-exp'
        self.fast_model_name = settings.gemini_fast_model or 'gemini-2.0-flash-exp'
        
        self.max_retries = 3
        self.base_delay = 1.0

    def generate_content(self, prompt: str, pdf_data: Optional[bytes] = None, mime_type: str = "application/pdf") -> str:
        """
        Generates content using the Gemini model, with optional PDF/Image data.
        """
        try:
            if pdf_data:
                # Create parts for multimodal input
                parts = [
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=pdf_data, mime_type=mime_type)
                ]
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=parts,
                    config=types.GenerateContentConfig(temperature=0.0)
                )
            else:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.0)
                )
            return response.text
        except Exception as e:
            logger.error(f"Error generating content with Gemini: {e}")
            return f"An error occurred: {e}"

    def _generate_cache_key(self, prompt: str, pdf_data: Optional[bytes], use_fast_model: bool) -> str:
        """Generate a deterministic cache key for the request."""
        # Base content
        content = f"{prompt}:{use_fast_model}:{settings.gemini_model if not use_fast_model else settings.gemini_fast_model}"
        
        # Add PDF hash if present
        if pdf_data:
            # Partial hash for speed if > 10MB
            if len(pdf_data) > 10 * 1024 * 1024:
                chunk = pdf_data[:1024] + pdf_data[-1024:]
                pdf_hash = hashlib.md5(chunk).hexdigest() + f":len={len(pdf_data)}"
            else:
                pdf_hash = hashlib.md5(pdf_data).hexdigest()
            content += f":pdf={pdf_hash}"
            
        return f"gemini_cache:{hashlib.sha256(content.encode()).hexdigest()}"

    async def generate_content_async(
        self,
        prompt: str,
        pdf_data: Optional[bytes] = None,
        use_fast_model: bool = False,
        mime_type: str = "application/pdf"
    ) -> str:
        """
        Generates content using the Gemini model asynchronously, with optional PDF/Image data.
        Includes retry logic for rate limiting and transient errors.
        """
        # 1. Check Cache
        cache_key = self._generate_cache_key(prompt, pdf_data, use_fast_model)
        if redis_client.client:
            try:
                cached_response = await redis_client.get(cache_key)
                if cached_response:
                    # Don't return cached errors - invalidate and retry
                    if cached_response.startswith("An error occurred:"):
                        logger.warning("Cached error found, invalidating cache and retrying")
                        await redis_client.delete(cache_key)
                    else:
                        logger.info("Gemini Cache Hit")
                        return cached_response
            except Exception as e:
                logger.error(f"Redis cache get error: {e}")

        last_exception = None
        model_name = self.fast_model_name if use_fast_model else self.model_name
        
        for attempt in range(self.max_retries):
            try:
                if pdf_data:
                    # Create parts for multimodal input
                    parts = [
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=pdf_data, mime_type=mime_type)
                    ]
                    response = await self.client.aio.models.generate_content(
                        model=model_name,
                        contents=parts,
                        config=types.GenerateContentConfig(temperature=0.0)
                    )
                else:
                    response = await self.client.aio.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.0)
                    )
                
                # Cache and return (only cache successful responses)
                result_text = response.text
                if result_text and not result_text.startswith("An error occurred:"):
                    if redis_client.client:
                        try:
                            await redis_client.set(cache_key, result_text, expire=86400)
                        except Exception as e:
                            logger.error(f"Redis cache set error: {e}")
                return result_text
                
            except google_exceptions.ResourceExhausted as e:
                # Handle rate limiting (429)
                delay = self.base_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Rate limit exceeded (attempt {attempt + 1}/{self.max_retries}). Retrying in {delay}s...")
                await asyncio.sleep(delay)
                last_exception = e
                
            except google_exceptions.ServiceUnavailable as e:
                # Handle service unavailable (503)
                delay = self.base_delay * (2 ** attempt)
                logger.warning(f"Service unavailable (attempt {attempt + 1}/{self.max_retries}). Retrying in {delay}s...")
                await asyncio.sleep(delay)
                last_exception = e
                
            except Exception as e:
                # For other errors, log and return error message immediately or maybe retry?
                # Usually we don't retry on bad request etc.
                logger.error(f"Error generating content asynchronously with Gemini: {e}")
                return f"An error occurred: {e}"
        
        # If we exhausted retries
        logger.error(f"Failed to generate content after {self.max_retries} attempts. Last error: {last_exception}")
        return f"An error occurred: {last_exception}"
    async def generate_content_stream_async(self, prompt: str, pdf_data: Optional[bytes] = None, use_fast_model: bool = False):
        """
        Generates content using the Gemini model asynchronously with streaming.
        """
        model_name = self.fast_model_name if use_fast_model else self.model_name
        
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                if pdf_data:
                    # Create parts for multimodal input
                    parts = [
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=pdf_data, mime_type="application/pdf")
                    ]
                    response = await self.client.aio.models.generate_content_stream(
                        model=model_name,
                        contents=parts,
                        config=types.GenerateContentConfig(temperature=0.0)
                    )
                else:
                    response = await self.client.aio.models.generate_content_stream(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.0)
                    )
                
                async for chunk in response:
                    if chunk.text:
                        yield chunk.text
                return

            except google_exceptions.ResourceExhausted as e:
                delay = self.base_delay * (2 ** attempt)
                logger.warning(f"Rate limit exceeded (attempt {attempt + 1}/{self.max_retries}). Retrying in {delay}s...")
                await asyncio.sleep(delay)
                last_exception = e
            except google_exceptions.ServiceUnavailable as e:
                delay = self.base_delay * (2 ** attempt)
                logger.warning(f"Service unavailable (attempt {attempt + 1}/{self.max_retries}). Retrying in {delay}s...")
                await asyncio.sleep(delay)
                last_exception = e
            except Exception as e:
                logger.error(f"Error generating content stream with Gemini: {e}")
                yield f"An error occurred: {e}"
                return

        logger.error(f"Failed to stream content after {self.max_retries} attempts. Last error: {last_exception}")
        yield f"Error: Service temporarily unavailable. Please try again."

    async def map_expenses_to_categories_async(self, raw_expenses: List[Dict], categories: List[str]) -> List[Dict]:
        """
        Maps raw expenses to predefined categories using the Gemini model asynchronously.
        Uses the fast model for cost and speed efficiency.
        """
        prompt = f"""
        Given a list of raw expenses and a list of categories, map each expense to the most appropriate category.
        Return a JSON array where each object has 'original_text', 'mapped_category', 'amount', and 'confidence'.
        Confidence should be a float between 0 and 1.

        Raw Expenses: {raw_expenses}
        Categories: {categories}
        """
        try:
            # Use fast model for categorization
            response_text = await self.generate_content_async(prompt, use_fast_model=True)
            cleaned_json = self._clean_json_string(response_text)
            return json.loads(cleaned_json)
        except Exception as e:
            logger.error(f"Error mapping expenses to categories: {e}")
            return []

    def map_expenses_to_categories(self, raw_expenses: List[Dict], categories: List[str]) -> List[Dict]:
        """
        Maps raw expenses to predefined categories using the Gemini model.
        DEPRECATED: Use map_expenses_to_categories_async for better performance.
        """
        # Kept for backward compatibility if synchronous call is absolutely needed
        return asyncio.run(self.map_expenses_to_categories_async(raw_expenses, categories))

    async def generate_structured_data_async(
        self,
        prompt: str,
        pdf_data: Optional[bytes] = None,
        pydantic_schema: Optional[Type[BaseModel]] = None,
        expect_list: bool = True,
        use_fast_model: bool = False,
        mime_type: str = "application/pdf"
    ) -> Any:
        """
        Generates structured data asynchronously. Returns List[Dict] if expect_list=True, else Dict.
        
        Args:
            prompt: The prompt to send to Gemini
            pdf_data: Optional PDF bytes for vision-based processing
            pydantic_schema: Optional Pydantic model for validation
            expect_list: If True, ensures output is a list. If False, expects a single dict.
            use_fast_model: If True, uses the faster, cheaper model.
            mime_type: MIME type of the file (pdf or image)
        
        Returns:
            List[Dict] if expect_list=True, Dict otherwise
        """
        response_text = await self.generate_content_async(prompt, pdf_data, use_fast_model=use_fast_model, mime_type=mime_type)
        
        if response_text.startswith("An error occurred:"):
            logger.error(f"Gemini API Error in structured data generation: {response_text}")
            return [] if expect_list else {}

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
        expect_list: bool = True,
        mime_type: str = "application/pdf"
    ) -> Any:
        """
        Generates structured data. Returns List[Dict] if expect_list=True, else Dict.
        
        Args:
            prompt: The prompt to send to Gemini
            pdf_data: Optional PDF bytes for vision-based processing
            pydantic_schema: Optional Pydantic model for validation
            expect_list: If True, ensures output is a list. If False, expects a single dict.
            mime_type: MIME type of the file
        
        Returns:
            List[Dict] if expect_list=True, Dict otherwise
        """
        response_text = self.generate_content(prompt, pdf_data, mime_type=mime_type)
        
        if response_text.startswith("An error occurred:"):
            logger.error(f"Gemini API Error in structured data generation: {response_text}")
            return [] if expect_list else {}

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
