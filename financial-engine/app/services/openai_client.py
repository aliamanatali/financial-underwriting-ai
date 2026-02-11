import logging
from typing import Optional
from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self):
        self.api_key = settings.openai_api_key
        if not self.api_key:
            # We don't raise error here to allow app startup, but warn
            logger.warning("OPENAI_API_KEY not set. OpenAI features will be unavailable.")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=self.api_key)
        
        self.model = settings.openai_model or "gpt-5.2-2025-12-11"

    async def generate_content_async(self, prompt: str) -> str:
        """
        Generates content using OpenAI model asynchronously.
        """
        if not self.client:
             raise ValueError("OpenAI Client not initialized (Missing Key)")

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional real estate investment analyst. Your goal is to produce high-quality, accurate investment memos and financial reports."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            content = response.choices[0].message.content
            return content if content else ""
        except Exception as e:
            logger.error(f"Error generating content with OpenAI: {e}")
            raise