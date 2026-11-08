"""Оркестрація пайплайну: аналіз → генерація → збирання скрипту → перевірки → дедуп → добір → експорт.
Тут немає власної логіки перевірок — лише послідовність кроків, яку видно з функції run()."""

import time
from datetime import datetime
from pathlib import Path

from . import prompts
from .checks import run_checks, status_from_flags
from .dedup import DEFAULT_THRESHOLD, duplicate_flag
from .history import plan_angles
from .io import append_run_log, write_brief
from .llm import LLMClient, estimate_cost
from .models import Brief, BrandGuide, HistoryRow, Variant, WinnerScript


def top_winners(history: list[HistoryRow], k: int = 5) -> list[HistoryRow]:
    winners = [r for r in history if r.status == "winner"]
    return sorted(winners, key=lambda r: r.ctr, reverse=True)[:k]


def evaluate(variants: list[Variant], script: WinnerScript, brand: BrandGuide,
             history_texts: list[str], batch_seen: list[str], threshold: int) -> None:
    """Збирає повний скрипт і проставляє прапорці та статус. batch_seen поповнюється на місці."""
    for v in variants:
        v.original_text = getattr(script, v.element_changed)
        v.full_script = script.with_element(v.element_changed, v.new_text).to_text()
        v.flags = run_checks(v.element_changed, v.new_text, brand)
        dup = duplicate_flag(v.new_text, history_texts, batch_seen, threshold)
        if dup:
            v.flags.append(dup)
        v.status = status_from_flags(v.flags)
        batch_seen.append(v.new_text)


def select(variants: list[Variant], n: int) -> list[Variant]:
    """Лишаємо не більше n готових (решту відкидаємо мовчки) і всі відхилені — для прозорості."""
    ready = [v for v in variants if v.status == "ready"][:n]
    return ready + [v for v in variants if v.status == "rejected"]


def build_brief(script: WinnerScript, brand: BrandGuide, history: list[HistoryRow], n: int,
                client: LLMClient, threshold: int = DEFAULT_THRESHOLD) -> Brief:
    started = time.monotonic()
    plan = plan_angles(history, n)
    analysis = client.analyze(prompts.analysis_prompt(script, brand))

    history_texts = [r.hook_text for r in history]
    base_prompt = prompts.generation_prompt(script, analysis, brand, plan,
                                            top_winners(history), history_texts)
    variants = client.variants(base_prompt)
    batch_seen: list[str] = []
    evaluate(variants, script, brand, history_texts, batch_seen, threshold)

    missing = n - sum(v.status == "ready" for v in variants)
    if missing > 0:
        rejected = [v for v in variants if v.status == "rejected"]
        extra = client.variants(prompts.refill_prompt(base_prompt, rejected, missing), refill=True)
        evaluate(extra, script, brand, history_texts, batch_seen, threshold)
        variants += extra

    variants = select(variants, n)
    for i, v in enumerate(variants, start=1):
        v.mod_id = f"{script.ad_id}-M{i:02d}"
    return Brief(
        parent_ad_id=script.ad_id, model=client.model,
        created_at=datetime.now().isoformat(timespec="seconds"),
        n_requested=n, angle_plan=plan, analysis=analysis, variants=variants,
        usage=client.usage, est_cost_usd=estimate_cost(client.usage, client.model),
        duration_sec=time.monotonic() - started,
    )


def run(script: WinnerScript, brand: BrandGuide, history: list[HistoryRow], n: int,
        out_root: Path, mock: bool = False,
        threshold: int = DEFAULT_THRESHOLD) -> tuple[Brief, dict[str, Path]]:
    """Повний запуск: бриф + файли в out/<timestamp>/ + рядок у out/runs.csv."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    brief = build_brief(script, brand, history, n, LLMClient(mock=mock), threshold)
    paths = write_brief(brief, Path(out_root) / timestamp)
    append_run_log(brief, timestamp, Path(out_root) / "runs.csv")
    return brief, paths
