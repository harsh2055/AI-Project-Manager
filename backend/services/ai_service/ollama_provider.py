import os
import httpx
from .base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/v1/chat/completions")
    MODEL = os.getenv("OLLAMA_MODEL", "llama3")

    def __init__(self):
        self.api_key = os.getenv("OLLAMA_API_KEY", "ollama")

    def generate(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 1024}
        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(self.API_URL, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if "404" in str(e):
                return self._generate_legacy(prompt)
            raise

    def _generate_legacy(self, prompt: str):
        legacy_url = self.API_URL.replace("/v1/chat/completions", "/api/generate")
        with httpx.Client(timeout=60) as client:
            response = client.post(legacy_url, json={"model": self.MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.2}})
            response.raise_for_status()
            return response.json().get("response", "").strip()
