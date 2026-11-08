# HookGen — MVP для SockLock

**Що це.** HookGen бере скрипт креативу-переможця і повертає готовий бриф із N модифікацій для motion-дизайнера. У кожному варіанті змінено рівно одну змінну (хук, першу фразу або текст на екрані), тому A/B-тест лишається чистим. Варіанти автоматично перевіряються на ліміти символів, заборонені фрази, ризики для політик Meta й повтори старих хуків.

**Навіщо.** Зараз команда робить ~240 модифікацій на місяць, а для $800k spend потрібно ~500. Половину з 3 годин на кожну модифікацію дизайнер витрачає на ручне переписування текстів. Ціль — скоротити час з ~3 год до ≤1,5 год на модифікацію.

## Встановлення та запуск

Потрібен Python 3.11+.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .

# Демо без API-ключа (відповіді LLM беруться з fixtures/)
hookgen generate --mock --script data/winner_script.md --brand data/brand.yaml \
                 --history data/hooks_history.csv -n 20

hookgen check --input data/sample_hooks.csv --brand data/brand.yaml --history data/hooks_history.csv
hookgen stats --history data/hooks_history.csv

streamlit run app.py      # веб-інтерфейс; без ключа Mock mode увімкнено автоматично
pytest -q                 # усі тести офлайн
```

**Справжній LLM.** Скопіюйте `.env.example` у `.env`, впишіть ключ і експортуйте змінні:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export HOOKGEN_MODEL=claude-sonnet-5     # за замовчуванням; дешевше — claude-haiku-4-5
hookgen generate --script data/winner_script.md --brand data/brand.yaml --history data/hooks_history.csv
```

Результати: `out/<timestamp>/brief.{csv,md,json}` і рядок у `out/runs.csv`.

## Формати вхідних файлів

| Файл | Формат |
|---|---|
| `data/winner_script.md` | `# AD_ID: ...`, далі секції `## HOOK`, `## FIRST_LINE`, `## ON_SCREEN`, `## BODY`, `## CTA` (регістр не важливий) |
| `data/hooks_history.csv` | `ad_id, hook_text, angle, ctr, hook_rate, spend, status`; `ctr` і `hook_rate` — частки (0.031 = 3,1%), `status` ∈ winner/loser/active |
| `data/brand.yaml` | `product.facts`, `tone`, `limits` (символи на елемент), `banned_phrases`, `allowed_claims` |
| CSV для `hookgen check` | колонка `text`, опційно `element` (`hook` / `first_line` / `on_screen`, за замовчуванням `hook`) |

## Як працює пайплайн

```
скрипт + бренд + історія
   │
   ├─1─ Статистика кутів → план: скільки варіантів на кожен кут (мін. 1 на pain/curiosity/social_proof/contrarian)
   ├─2─ LLM-виклик 1: чому переможець працює (біль, кут, структура, емоція)
   ├─3─ LLM-виклик 2: N варіантів, у кожному змінено рівно один елемент
   ├─4─ Код збирає повний скрипт і перевіряє: TOO_LONG, BANNED_PHRASE (block);
   │    UNVERIFIABLE_CLAIM, PERSONAL_ATTRIBUTE, OFF_BRAND_FACT (warn); DUPLICATE (block)
   ├─5─ Якщо ready < N → 1 дозапит із переліком відхилених і причин
   └─6─ Експорт brief.csv (для Airtable), brief.md (для дизайнера), brief.json + лог у runs.csv
```

Принцип: **LLM генерує, код перевіряє.** Усі перевірки — детермінований Python (`checks.py`, `dedup.py`). Відповідь LLM валідується Pydantic; на невалідний JSON робиться одна повторна спроба з текстом помилки.

## Метрики успіху

- **Час дизайнера на модифікацію:** 3 год → ≤1,5 год за 2 тижні пілоту. 1 дизайнер, ~30 модифікацій: половина з HookGen, половина вручну, з логами часу.
- **Модифікацій на місяць:** 240 → 400+ за 4–6 тижнів.
- **Guardrail:** win rate і ROMI модифікацій з HookGen не нижчі за ручні, ROMI ≥125%.
- **Частка варіантів, які дизайнер взяв без правок:** `n_ready` з `runs.csv` плюс чекбокс «Взято без правок» у `brief.md`.
- **Вартість:** $ токенів на одну модифікацію = `est_cost_usd / n_ready` з `runs.csv`.

## Наступна ітерація

- Імпорт переможців напряму з CSV-експорту Meta Ads.
- Локалізація тим самим пайплайном на DE/FR, з культурною адаптацією, а не дослівним перекладом.
- Генерація нових кутів з болів у коментарях Reddit.
- Фідбек-цикл: результати тестів повертаються в `hooks_history.csv` → кращий розподіл кутів.
