"""Виклики LLM: справжній Anthropic API або mock із фікстури (офлайн, детерміновано).
Відповідь завжди валідується Pydantic; на невалідний JSON — 1 повторна спроба з текстом помилки."""

import json
import os
import re
from pathlib import Path

import anthropic
from pydantic import BaseModel, ValidationError

from . import prompts
from .models import Usage, Variant, VariantList, WinnerAnalysis

DEFAULT_MODEL = "claude-sonnet-5"
MOCK_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "mock_llm_response.json"
# $ за 1M токенів (input, output) — для оцінки вартості в runs.csv.
PRICES = {
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-opus-5": (5.0, 25.0),
}


class LLMError(RuntimeError):
    """Зрозуміла помилка для користувача CLI/UI."""


def estimate_cost(usage: Usage, model: str) -> float:
    price_in, price_out = PRICES.get(model, (0.0, 0.0))
    return (usage.input_tokens * price_in + usage.output_tokens * price_out) / 1_000_000


def parse_json(text: str, schema: type[BaseModel]) -> BaseModel:
    """Модель іноді обгортає JSON у ```-блок — прибираємо обгортку перед валідацією."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return schema.model_validate(json.loads(cleaned))


class LLMClient:
    def __init__(self, mock: bool = False, model: str | None = None):
        self.mock = mock
        self.model = "mock" if mock else (model or os.getenv("HOOKGEN_MODEL") or DEFAULT_MODEL)
        self.usage = Usage()
        if mock:
            self._fixture = json.loads(MOCK_FIXTURE.read_text(encoding="utf-8"))
        else:
            # Перевіряємо ключ одразу, щоб не впасти з незрозумілим TypeError посеред пайплайну.
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise LLMError("Не задано ANTHROPIC_API_KEY. Додайте ключ або запустіть з --mock.")
            self._client = anthropic.Anthropic()

    def analyze(self, prompt: str) -> WinnerAnalysis:
        return self._ask(prompt, WinnerAnalysis, mock_key="analysis")

    def variants(self, prompt: str, refill: bool = False) -> list[Variant]:
        result = self._ask(prompt, VariantList, mock_key="refill" if refill else "variants")
        return result.variants

    def _ask(self, prompt: str, schema: type[BaseModel], mock_key: str) -> BaseModel:
        if self.mock:
            data = self._fixture[mock_key]
            return schema.model_validate(data if isinstance(data, dict) else {"variants": data})
        messages = [{"role": "user", "content": prompt}]
        for attempt in range(2):
            text = self._call(messages)
            try:
                return parse_json(text, schema)
            except (json.JSONDecodeError, ValidationError) as e:
                if attempt == 1:
                    raise LLMError(f"LLM двічі повернув невалідний JSON: {e}") from e
                messages += [{"role": "assistant", "content": text},
                             {"role": "user", "content": prompts.fix_json_prompt(str(e))}]

    def _call(self, messages: list[dict]) -> str:
        try:
            response = self._client.messages.create(
                model=self.model, max_tokens=16000,
                system=prompts.SYSTEM, messages=messages,
            )
        except anthropic.AuthenticationError as e:
            raise LLMError("Невірний ANTHROPIC_API_KEY або його немає. Спробуйте --mock.") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"Помилка Anthropic API ({e.status_code}): {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise LLMError("Немає з'єднання з Anthropic API. Спробуйте --mock.") from e
        self.usage = self.usage + Usage(input_tokens=response.usage.input_tokens,
                                        output_tokens=response.usage.output_tokens)
        if response.stop_reason in ("refusal", "max_tokens"):
            raise LLMError(f"LLM не завершив відповідь (stop_reason={response.stop_reason})")
        return "".join(b.text for b in response.content if b.type == "text")
