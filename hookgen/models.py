"""Pydantic-схеми всіх даних HookGen: вхідні файли, відповіді LLM і фінальний бриф.
Одне місце для типів, щоб валідація була однаковою в CLI, UI і тестах."""

from typing import Literal

from pydantic import BaseModel, Field

Element = Literal["hook", "first_line", "on_screen"]
Angle = Literal[
    "pain", "curiosity", "social_proof", "contrarian",
    "humor", "problem_solution", "ugc_testimonial",
]
ALL_ANGLES: list[str] = list(Angle.__args__)
# Базові кути отримують мінімум 1 варіант завжди — це бюджет на дослідження.
BASE_ANGLES: list[str] = ["pain", "curiosity", "social_proof", "contrarian"]


class WinnerScript(BaseModel):
    ad_id: str
    hook: str
    first_line: str
    on_screen: str
    body: str = ""
    cta: str = ""

    def with_element(self, element: Element, text: str) -> "WinnerScript":
        """Копія скрипту, де замінено рівно один елемент — основа чистого A/B."""
        return self.model_copy(update={element: text})

    def to_text(self) -> str:
        return (
            f"HOOK: {self.hook}\nFIRST_LINE: {self.first_line}\n"
            f"ON_SCREEN: {self.on_screen}\nBODY: {self.body}\nCTA: {self.cta}"
        )


class Product(BaseModel):
    name: str
    facts: list[str]


class Limits(BaseModel):
    hook_chars: int
    first_line_chars: int
    on_screen_chars: int

    def for_element(self, element: Element) -> int:
        return getattr(self, f"{element}_chars")


class BrandGuide(BaseModel):
    product: Product
    tone: str
    limits: Limits
    banned_phrases: list[str] = []
    allowed_claims: list[str] = []


class HistoryRow(BaseModel):
    ad_id: str
    hook_text: str
    angle: Angle
    ctr: float
    hook_rate: float
    spend: float
    status: Literal["winner", "loser", "active"]


class Flag(BaseModel):
    code: str
    severity: Literal["block", "warn"]
    message: str


class WinnerAnalysis(BaseModel):
    """Відповідь LLM-виклику 1: чому переможець працює."""
    pain: str
    angle: str
    structure: str
    key_emotion: str


class Variant(BaseModel):
    # Поля, які заповнює LLM:
    element_changed: Element
    angle: Angle
    new_text: str
    rationale: str
    # Поля, які заповнює код після перевірок:
    mod_id: str = ""
    original_text: str = ""
    full_script: str = ""
    flags: list[Flag] = []
    status: Literal["pending", "ready", "rejected"] = "pending"


class VariantList(BaseModel):
    """Відповідь LLM-виклику 2 (і добору)."""
    variants: list[Variant]


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


class Brief(BaseModel):
    parent_ad_id: str
    model: str
    created_at: str
    n_requested: int
    angle_plan: dict[str, int]
    analysis: WinnerAnalysis
    variants: list[Variant]
    usage: Usage = Field(default_factory=Usage)
    est_cost_usd: float = 0.0
    duration_sec: float = 0.0

    def ready(self) -> list[Variant]:
        return [v for v in self.variants if v.status == "ready"]

    def rejected(self) -> list[Variant]:
        return [v for v in self.variants if v.status == "rejected"]
