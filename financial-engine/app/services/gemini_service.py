import os
from google import genai
from google.genai import types

class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        # Initialize the new client
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = 'gemini-2.0-flash-exp'

    def generate_content(self, prompt: str) -> str:
        """
        Generates content using the Gemini model.
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0)
            )
            return response.text
        except Exception as e:
            # Handle potential API errors
            return f"An error occurred: {e}"

    async def generate_content_async(self, prompt: str) -> str:
        """
        Generates content using the Gemini model asynchronously.
        """
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0)
            )
            return response.text
        except Exception as e:
            # Handle potential API errors
            return f"An error occurred: {e}"
