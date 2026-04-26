import os
import httpx
from .base import BaseLLMProvider


class GroqProvider(BaseLLMProvider):
    API_URL = "https://api.groq.com/openai/v1/chat/completions"
    MODEL = "llama3-8b-8192"

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "")
        if not self.api_key:
            raise EnvironmentError("GROQ_API_KEY is not set.")

    def generate(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 1024}
        with httpx.Client(timeout=30) as client:
            response = client.post(self.API_URL, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
