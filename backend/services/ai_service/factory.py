import os
from .base import BaseLLMProvider
from .groq_provider import GroqProvider
from .together_provider import TogetherProvider
from .hf_provider import HuggingFaceProvider
from .ollama_provider import OllamaProvider
from .nvidia_provider import NvidiaProvider


def get_provider() -> BaseLLMProvider:
    provider_name = os.getenv("LLM_PROVIDER", "groq").lower()
    if provider_name == "groq":
        return GroqProvider()
    elif provider_name == "together":
        return TogetherProvider()
    elif provider_name == "hf":
        return HuggingFaceProvider()
    elif provider_name == "ollama":
        return OllamaProvider()
    elif provider_name == "nvidia":
        return NvidiaProvider()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER '{provider_name}'. Choose: groq | together | hf | ollama | nvidia")
