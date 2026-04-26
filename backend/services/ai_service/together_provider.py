import os
import httpx
from .base import BaseLLMProvider


class TogetherProvider(BaseLLMProvider):
    API_URL = "https://api.together.xyz/v1/chat/completions"
    MODEL = "mistralai/Mixtral-8x7B-Instruct-v0.1"

    def __init__(self):
        self.api_key = os.getenv("TOGETHER_API_KEY", "")
        if not self.api_key:
            raise EnvironmentError("TOGETHER_API_KEY is not set.")

    def generate(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 1024}
        with httpx.Client(timeout=45) as client:
            response = client.post(self.API_URL, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
