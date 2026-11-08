"""Fuzzy-дедуп варіантів проти історії хуків і всередині поточного батчу.
token_set_ratio стійкий до перестановки слів і дрібних вставок — типовий «перефраз» від LLM."""

import re

from rapidfuzz import fuzz

from .models import Flag

DEFAULT_THRESHOLD = 85


def normalize(text: str) -> str:
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def find_duplicate(text: str, corpus: list[str],
                   threshold: int = DEFAULT_THRESHOLD) -> tuple[str, float] | None:
    """Повертає найсхожіший текст із corpus, якщо схожість ≥ threshold."""
    norm = normalize(text)
    best: tuple[str, float] | None = None
    for candidate in corpus:
        score = fuzz.token_set_ratio(norm, normalize(candidate))
        if score >= threshold and (best is None or score > best[1]):
            best = (candidate, score)
    return best


def duplicate_flag(text: str, history: list[str], batch_seen: list[str],
                   threshold: int = DEFAULT_THRESHOLD) -> Flag | None:
    """Спершу шукаємо в історії (вже витрачений бюджет), потім у поточному батчі."""
    for source, corpus in (("історії", history), ("батчі", batch_seen)):
        match = find_duplicate(text, corpus, threshold)
        if match:
            similar, score = match
            return Flag(code="DUPLICATE", severity="block",
                        message=f"схоже на «{similar}» в {source} ({score:.0f}%)")
    return None
