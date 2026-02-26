import os
import asyncio
import logging
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

from app.config import settings

class GeminiService:
    def __init__(self):
        self.api_key = settings.gemini_api_key
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        # Initialize the new client
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = settings.gemini_model
        self.fast_model_name = settings.gemini_fast_model

    def generate_content(self, prompt: str, use_fast_model: bool = False) -> str:
        """
        Generates content using the Gemini model.
        """
        try:
            model = self.fast_model_name if use_fast_model else self.model_name
            response = self.client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0)
            )
            return response.text
        except Exception as e:
            # Handle potential API errors
            return f"An error occurred: {e}"

    async def generate_content_async(self, prompt: str, use_fast_model: bool = False) -> str:
        """
        Generates content using the Gemini model asynchronously with retries.
        """
        model = self.fast_model_name if use_fast_model else self.model_name
        try:
            # Retry logic for 500 errors and timeouts
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type((genai_errors.ServerError, genai_errors.APIError, asyncio.TimeoutError)),
                reraise=True
            ):
                with attempt:
                    response = await asyncio.wait_for(
                        self.client.aio.models.generate_content(
                            model=model,
                            contents=prompt,
                            config=types.GenerateContentConfig(temperature=0.0)
                        ),
                        timeout=90.0
                    )
                    return response.text
        except asyncio.TimeoutError:
            logger.error("Gemini request timed out after multiple retries")
            return "Error: Request timed out after multiple retries."
        except Exception as e:
            logger.error(f"Gemini request failed: {e}")
            return f"An error occurred: {e}"
