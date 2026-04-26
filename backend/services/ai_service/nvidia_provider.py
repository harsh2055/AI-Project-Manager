import os
import httpx
from .base import BaseLLMProvider


class NvidiaProvider(BaseLLMProvider):
    API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

    def __init__(self):
        self.api_key = os.getenv("NVIDIA_API_KEY", "")
        self.model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
        if not self.api_key:
            raise EnvironmentError("NVIDIA_API_KEY is not set.")

    def generate(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 1024, "top_p": 0.7}
        with httpx.Client(timeout=120) as client:
            response = client.post(self.API_URL, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
