"""Детерміновані перевірки тексту варіанта: ліміти, заборонені фрази, ризики для Meta.
Кожна перевірка повертає список Flag; LLM тут не бере участі — тільки regex і правила бренду."""

import re

from .models import BrandGuide, Element, Flag

# Абсолютні або непідтверджувані обіцянки, на які скаржаться модератори Meta.
UNVERIFIABLE_PATTERNS = [
    r"\d+(?:\.\d+)?\s*%", r"#\s*1\b", r"\b(?:always|never|forever)\b",
    r"\bclinically\b", r"\bproven\b",
]
# Евристика Meta Personal Attributes: реклама не має стверджувати, що читач «має проблему».
PERSONAL_PATTERNS = [r"\bare you\b", r"\byou have\b", r"\byour \w+ problem\b"]
PRICE_RE = re.compile(r"\$\s?(\d+(?:\.\d{1,2})?)")
PAIRS_RE = re.compile(r"\b(\d+)\s+pairs?\b", re.IGNORECASE)


def check_length(element: Element, text: str, brand: BrandGuide) -> list[Flag]:
    limit = brand.limits.for_element(element)
    if len(text) <= limit:
        return []
    return [Flag(code="TOO_LONG", severity="block",
                 message=f"{len(text)} символів > ліміт {limit} для {element}")]


def check_banned(text: str, brand: BrandGuide) -> list[Flag]:
    flags = []
    for phrase in brand.banned_phrases:
        # Межі слів через lookaround, бо \b не працює поруч із символами на кшталт "%".
        pattern = rf"(?<!\w){re.escape(phrase)}(?!\w)"
        if re.search(pattern, text, re.IGNORECASE):
            flags.append(Flag(code="BANNED_PHRASE", severity="block",
                              message=f"заборонена фраза «{phrase}»"))
    return flags


def check_unverifiable(text: str) -> list[Flag]:
    found = [m.group(0) for p in UNVERIFIABLE_PATTERNS
             for m in re.finditer(p, text, re.IGNORECASE)]
    if not found:
        return []
    return [Flag(code="UNVERIFIABLE_CLAIM", severity="warn",
                 message=f"непідтверджуване твердження: {', '.join(found)}")]


def check_personal_attribute(text: str) -> list[Flag]:
    found = [m.group(0) for p in PERSONAL_PATTERNS
             for m in re.finditer(p, text, re.IGNORECASE)]
    if not found:
        return []
    return [Flag(code="PERSONAL_ATTRIBUTE", severity="warn",
                 message=f"ризик політики Meta щодо особистих характеристик: «{found[0]}»")]


def _allowed_numbers(regex: re.Pattern, facts: list[str]) -> set[float]:
    return {float(m) for fact in facts for m in regex.findall(fact)}


def check_off_brand_fact(text: str, brand: BrandGuide) -> list[Flag]:
    """Ціна або кількість пар, яких немає в product.facts, — ймовірна галюцинація LLM."""
    facts = brand.product.facts
    flags = []
    for regex, label in ((PRICE_RE, "ціна"), (PAIRS_RE, "кількість пар")):
        allowed = _allowed_numbers(regex, facts)
        for value in regex.findall(text):
            if float(value) not in allowed:
                flags.append(Flag(code="OFF_BRAND_FACT", severity="warn",
                                  message=f"{label} «{value}» не збігається з фактами бренду"))
    return flags


def run_checks(element: Element, text: str, brand: BrandGuide) -> list[Flag]:
    return (check_length(element, text, brand) + check_banned(text, brand)
            + check_unverifiable(text) + check_personal_attribute(text)
            + check_off_brand_fact(text, brand))


def status_from_flags(flags: list[Flag]) -> str:
    return "rejected" if any(f.severity == "block" for f in flags) else "ready"
