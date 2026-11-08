"""Читання вхідних файлів (скрипт, бренд, історія) і запис результатів (CSV/MD/JSON, runs.csv).
Уся робота з диском тут, щоб решта модулів працювала з чистими об'єктами."""

import csv
import re
from pathlib import Path

import pandas as pd
import yaml

from .models import Brief, BrandGuide, HistoryRow, Variant, WinnerScript

SECTION_RE = re.compile(r"^##\s*(\w+)\s*$", re.IGNORECASE)
AD_ID_RE = re.compile(r"^#\s*AD_ID\s*:\s*(\S+)", re.IGNORECASE)


def parse_script(text: str) -> WinnerScript:
    """Розбирає markdown-скрипт на секції. Регістр заголовків не важливий."""
    ad_id, current, sections = "UNKNOWN", None, {}
    for line in text.splitlines():
        if m := AD_ID_RE.match(line.strip()):
            ad_id = m.group(1)
        elif m := SECTION_RE.match(line.strip()):
            current = m.group(1).lower()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    fields = {k: "\n".join(v).strip() for k, v in sections.items()}
    missing = [k for k in ("hook", "first_line", "on_screen") if not fields.get(k)]
    if missing:
        raise ValueError(f"У скрипті бракує секцій: {', '.join(missing).upper()}")
    return WinnerScript(ad_id=ad_id, **{k: v for k, v in fields.items()
                                         if k in WinnerScript.model_fields})


def read_script(path: str | Path) -> WinnerScript:
    return parse_script(Path(path).read_text(encoding="utf-8"))


def read_brand(path: str | Path) -> BrandGuide:
    return BrandGuide(**yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def read_history(source) -> list[HistoryRow]:
    """source — шлях або file-like (для streamlit uploader)."""
    df = pd.read_csv(source)
    return [HistoryRow(**row) for row in df.to_dict(orient="records")]


def flags_to_str(variant: Variant) -> str:
    return "; ".join(f"{f.code}({f.severity}): {f.message}" for f in variant.flags)


def brief_to_rows(brief: Brief) -> list[dict]:
    return [{
        "mod_id": v.mod_id, "parent_ad_id": brief.parent_ad_id,
        "element_changed": v.element_changed, "angle": v.angle,
        "original_text": v.original_text, "new_text": v.new_text,
        "full_script": v.full_script, "rationale": v.rationale,
        "flags": flags_to_str(v), "status": v.status,
    } for v in brief.variants]


def brief_to_markdown(brief: Brief) -> str:
    """Бриф для дизайнера: спершу ready, згруповані за кутами, наприкінці rejected."""
    a = brief.analysis
    lines = [
        f"# Бриф модифікацій для {brief.parent_ad_id}", "",
        f"Готових: **{len(brief.ready())}**, відхилених: {len(brief.rejected())}. "
        f"Модель: `{brief.model}`. Створено: {brief.created_at}.", "",
        "## Чому переможець працює",
        f"- Біль: {a.pain}", f"- Кут: {a.angle}",
        f"- Структура: {a.structure}", f"- Емоція: {a.key_emotion}", "",
    ]
    by_angle: dict[str, list[Variant]] = {}
    for v in brief.ready():
        by_angle.setdefault(v.angle, []).append(v)
    for angle, items in by_angle.items():
        lines.append(f"## Кут: {angle} ({len(items)})")
        for v in items:
            lines += [f"### {v.mod_id} — змінюємо `{v.element_changed}`",
                      f"- Було: {v.original_text}", f"- Стало: **{v.new_text}**",
                      f"- Чому: {v.rationale}"]
            if v.flags:
                lines.append(f"- ⚠️ {flags_to_str(v)}")
            lines.append("- [ ] Взято без правок")
            lines.append("")
    if brief.rejected():
        lines.append("## Відхилені (не брати в роботу)")
        for v in brief.rejected():
            lines.append(f"- {v.mod_id} `{v.element_changed}`: {v.new_text} — {flags_to_str(v)}")
    return "\n".join(lines) + "\n"


def write_brief(brief: Brief, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {name: out_dir / f"brief.{name}" for name in ("csv", "md", "json")}
    pd.DataFrame(brief_to_rows(brief)).to_csv(paths["csv"], index=False)
    paths["md"].write_text(brief_to_markdown(brief), encoding="utf-8")
    paths["json"].write_text(brief.model_dump_json(indent=2), encoding="utf-8")
    return paths


RUN_LOG_FIELDS = ["timestamp", "parent_ad_id", "model", "n_requested", "n_ready",
                  "n_rejected", "duration_sec", "input_tokens", "output_tokens", "est_cost_usd"]


def append_run_log(brief: Brief, timestamp: str, log_path: Path) -> None:
    """Дописує рядок у runs.csv — джерело метрик успіху (вартість, частка ready)."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not log_path.exists()
    with log_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RUN_LOG_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow({
            "timestamp": timestamp, "parent_ad_id": brief.parent_ad_id,
            "model": brief.model, "n_requested": brief.n_requested,
            "n_ready": len(brief.ready()), "n_rejected": len(brief.rejected()),
            "duration_sec": round(brief.duration_sec, 2),
            "input_tokens": brief.usage.input_tokens,
            "output_tokens": brief.usage.output_tokens,
            "est_cost_usd": round(brief.est_cost_usd, 4),
        })

