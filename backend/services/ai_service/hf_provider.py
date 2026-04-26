import os
import httpx
from .base import BaseLLMProvider


class HuggingFaceProvider(BaseLLMProvider):
    MODEL = "mistralai/Mistral-7B-Instruct-v0.2"

    def __init__(self):
        self.api_key = os.getenv("HF_API_KEY", "")
        if not self.api_key:
            raise EnvironmentError("HF_API_KEY is not set.")
        self.api_url = f"https://api-inference.huggingface.co/models/{self.MODEL}"

    def generate(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"inputs": f"[INST] {prompt} [/INST]", "parameters": {"max_new_tokens": 1024, "temperature": 0.2, "return_full_text": False}}
        with httpx.Client(timeout=60) as client:
            response = client.post(self.api_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                return data[0].get("generated_text", "").strip()
            return str(data)
