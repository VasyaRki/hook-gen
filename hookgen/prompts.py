"""Усі промпти HookGen в одному місці, щоб їх було легко читати й правити без пошуку по коду."""

from .models import BrandGuide, HistoryRow, Variant, WinnerAnalysis, WinnerScript

SYSTEM = (
    "You are a senior direct-response copywriter for US Meta Ads. "
    "You write short, scroll-stopping video ad copy. "
    "Always answer with a single JSON object and nothing else: no markdown fences, no comments."
)

VARIANT_SCHEMA = (
    '{"variants": [{"element_changed": "hook" | "first_line" | "on_screen", '
    '"angle": "pain" | "curiosity" | "social_proof" | "contrarian" | "humor" | '
    '"problem_solution" | "ugc_testimonial", "new_text": "...", "rationale": "one sentence"}]}'
)


def analysis_prompt(script: WinnerScript, brand: BrandGuide) -> str:
    return f"""Analyze why this winning video ad script works for {brand.product.name}.

<script>
{script.to_text()}
</script>

Return JSON with exactly these keys, each a short sentence:
{{"pain": "...", "angle": "...", "structure": "...", "key_emotion": "..."}}"""


def _brand_block(brand: BrandGuide) -> str:
    limits = brand.limits
    return f"""Product: {brand.product.name}
Facts (the ONLY prices/quantities you may mention): {"; ".join(brand.product.facts)}
Tone: {brand.tone}
Allowed claims: {"; ".join(brand.allowed_claims)}
Banned phrases (never use): {", ".join(brand.banned_phrases)}
Character limits: hook <= {limits.hook_chars}, first_line <= {limits.first_line_chars}, on_screen <= {limits.on_screen_chars}"""


def generation_prompt(script: WinnerScript, analysis: WinnerAnalysis, brand: BrandGuide,
                      plan: dict[str, int], examples: list[HistoryRow],
                      used_hooks: list[str]) -> str:
    n = sum(plan.values())
    plan_text = "\n".join(f"- {angle}: {count}" for angle, count in plan.items())
    examples_text = "\n".join(f"- [{r.angle}] {r.hook_text}" for r in examples) or "- (none)"
    used_text = "\n".join(f"- {h}" for h in used_hooks) or "- (none)"
    return f"""We need {n} modifications of a winning ad for a clean A/B test.
Each modification changes EXACTLY ONE element of the script: "hook", "first_line" or "on_screen".
Everything else stays as in the original. Mix elements, but most should be hooks.

<winner_script>
{script.to_text()}
</winner_script>

<why_it_works>
{analysis.model_dump_json()}
</why_it_works>

<brand_guide>
{_brand_block(brand)}
</brand_guide>

Angle plan (number of variants per angle):
{plan_text}

Top winning hooks from history, as style references (do not copy them):
{examples_text}

Already used hooks — do NOT repeat or closely paraphrase any of them:
{used_text}

Rules:
- US English, natural spoken style.
- new_text contains only the changed element, not the whole script.
- No absolute or unverifiable promises (always, never, forever, %, #1, proven, clinically).
- Do not assert personal attributes of the viewer (avoid "Are you...?", "You have...", "Your ... problem").
- rationale: one sentence on why this variant could beat the winner.

Return JSON: {VARIANT_SCHEMA}"""


def refill_prompt(base_prompt: str, rejected: list[Variant], missing: int) -> str:
    """Дозапит: той самий контекст + що відхилено й чому, щоб модель не повторила помилки."""
    rejected_text = "\n".join(
        f"- {v.new_text!r}: {'; '.join(f.message for f in v.flags)}" for v in rejected)
    return f"""{base_prompt}

Some variants from the previous attempt were rejected by automated checks:
{rejected_text}

Now write {missing} NEW variants that avoid these problems and differ from all previous ones.
Return JSON: {VARIANT_SCHEMA}"""


def fix_json_prompt(error: str) -> str:
    return (f"Your previous answer was not valid for the required schema:\n{error}\n"
            "Return the corrected answer as a single JSON object only.")

