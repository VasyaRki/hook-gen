"""Статистика кутів подачі з історії хуків і план розподілу N варіантів по кутах.
Більше варіантів отримують кути з вищим CTR, але кожен базовий кут має мінімум 1 — для дослідження."""

import pandas as pd

from .models import BASE_ANGLES, HistoryRow


def angle_stats(rows: list[HistoryRow]) -> pd.DataFrame:
    """Середні CTR/hook_rate і кількість winners по кутах, відсортовано за CTR."""
    if not rows:
        return pd.DataFrame(columns=["angle", "n_ads", "avg_ctr", "avg_hook_rate", "winners"])
    df = pd.DataFrame([r.model_dump() for r in rows])
    stats = df.groupby("angle").agg(
        n_ads=("ad_id", "count"),
        avg_ctr=("ctr", "mean"),
        avg_hook_rate=("hook_rate", "mean"),
        winners=("status", lambda s: int((s == "winner").sum())),
    ).reset_index()
    return stats.sort_values("avg_ctr", ascending=False, ignore_index=True)


def _split_proportionally(total: int, weights: dict[str, float]) -> dict[str, int]:
    """Метод найбільших залишків: цілі частки, сума яких рівно total."""
    weight_sum = sum(weights.values())
    raw = {k: total * w / weight_sum for k, w in weights.items()}
    result = {k: int(v) for k, v in raw.items()}
    leftover = total - sum(result.values())
    for k in sorted(raw, key=lambda k: raw[k] - result[k], reverse=True)[:leftover]:
        result[k] += 1
    return result


def plan_angles(rows: list[HistoryRow], n: int) -> dict[str, int]:
    """Скільки варіантів генерувати на кожен кут. Сума завжди дорівнює n."""
    if n <= 0:
        return {}
    if not rows:
        # Без історії нема на що спиратися — рівномірно по базових кутах.
        return _split_proportionally(n, {a: 1.0 for a in BASE_ANGLES})
    stats = angle_stats(rows)
    ctr = dict(zip(stats["angle"], stats["avg_ctr"]))
    if n < len(BASE_ANGLES):
        # Варіантів менше, ніж базових кутів: беремо найсильніші з них.
        best = sorted(BASE_ANGLES, key=lambda a: ctr.get(a, 0), reverse=True)[:n]
        return {a: 1 for a in best}
    plan = {a: 1 for a in BASE_ANGLES}
    extra = _split_proportionally(n - len(BASE_ANGLES), ctr)
    for angle, count in extra.items():
        plan[angle] = plan.get(angle, 0) + count
    return {a: c for a, c in plan.items() if c > 0}
