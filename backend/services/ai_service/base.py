from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        raise NotImplementedError

    def _safe_generate(self, prompt: str) -> str:
        try:
            return self.generate(prompt)
        except Exception as e:
            return f'{{"explanation": "AI analysis unavailable: {str(e)}", "fix": "N/A", "improved_code": ""}}'
