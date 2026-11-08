"""CLI HookGen: generate (бриф), check (перевірка готових текстів), stats (ефективність кутів)."""

from collections import Counter
from pathlib import Path

import pandas as pd
import typer

from .checks import run_checks, status_from_flags
from .dedup import DEFAULT_THRESHOLD, duplicate_flag
from .generate import run
from .history import angle_stats
from .io import read_brand, read_history, read_script
from .llm import LLMError

app = typer.Typer(help="HookGen: модифікації креативів-переможців для SockLock.",
                  no_args_is_help=True)


@app.command()
def generate(
    script: Path = typer.Option(..., help="Скрипт переможця (.md)"),
    brand: Path = typer.Option(..., help="Бренд-гайд (.yaml)"),
    history: Path | None = typer.Option(None, help="Історія хуків (.csv)"),
    n: int = typer.Option(20, "-n", help="Скільки готових варіантів потрібно"),
    out: Path = typer.Option(Path("out"), help="Папка для результатів"),
    mock: bool = typer.Option(False, help="Без API: відповіді з fixtures/"),
    dedup_threshold: int = typer.Option(DEFAULT_THRESHOLD, help="Поріг схожості 0–100"),
):
    """Згенерувати бриф із N варіантів модифікацій."""
    rows = read_history(history) if history else []
    try:
        brief, paths = run(read_script(script), read_brand(brand), rows, n, out,
                           mock=mock, threshold=dedup_threshold)
    except LLMError as e:
        typer.secho(f"Помилка: {e}", fg="red", err=True)
        raise typer.Exit(1)
    typer.echo(f"Ready: {len(brief.ready())} / {n} запитано, rejected: {len(brief.rejected())}")
    angles = Counter(v.angle for v in brief.ready())
    typer.echo("Кути (ready): " + ", ".join(f"{a}={c}" for a, c in angles.most_common()))
    typer.echo(f"Файли: {paths['csv'].parent}/brief.{{csv,md,json}}")
    typer.echo(f"Час: {brief.duration_sec:.1f} с, модель: {brief.model}, "
               f"токени: {brief.usage.input_tokens}+{brief.usage.output_tokens}, "
               f"вартість ≈ ${brief.est_cost_usd:.4f}")


@app.command()
def check(
    input: Path = typer.Option(..., help="CSV з колонкою text (і опційно element)"),
    brand: Path = typer.Option(..., help="Бренд-гайд (.yaml)"),
    history: Path | None = typer.Option(None, help="Історія хуків для дедупу (.csv)"),
    dedup_threshold: int = typer.Option(DEFAULT_THRESHOLD, help="Поріг схожості 0–100"),
):
    """Прогнати існуючі тексти через ті самі перевірки та дедуп."""
    guide = read_brand(brand)
    history_texts = [r.hook_text for r in read_history(history)] if history else []
    df = pd.read_csv(input)
    if "element" not in df.columns:
        df["element"] = "hook"
    seen: list[str] = []
    results = []
    for text, element in zip(df["text"], df["element"]):
        flags = run_checks(element, text, guide)
        dup = duplicate_flag(text, history_texts, seen, dedup_threshold)
        flags += [dup] if dup else []
        seen.append(text)
        results.append({"element": element, "text": text,
                        "status": status_from_flags(flags),
                        "flags": ", ".join(f"{f.code}({f.severity})" for f in flags)})
    typer.echo(pd.DataFrame(results).to_string(index=False))


@app.command()
def stats(history: Path = typer.Option(..., help="Історія хуків (.csv)")):
    """Таблиця ефективності кутів подачі."""
    table = angle_stats(read_history(history))
    typer.echo(table.to_string(index=False, formatters={
        "avg_ctr": "{:.2%}".format, "avg_hook_rate": "{:.1%}".format}))


if __name__ == "__main__":
    app()
