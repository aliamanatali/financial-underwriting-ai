import os
import google.generativeai as genai

class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-3-pro-preview')

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

    async def generate_content_async(self, prompt: str) -> str:
        """
        Generates content using the Gemini model asynchronously.
        """
        try:
            response = await self.model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            # Handle potential API errors
            return f"An error occurred: {e}"
