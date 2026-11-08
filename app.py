"""Тонкий Streamlit-інтерфейс для демо HookGen. Уся логіка — у пакеті hookgen, тут лише UI."""

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from hookgen.generate import run
from hookgen.history import angle_stats
from hookgen.io import brief_to_rows, parse_script, read_brand, read_history
from hookgen.llm import LLMError

DATA = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "out"
BADGE = {"block": "🔴", "warn": "🟡"}

st.set_page_config(page_title="HookGen", layout="wide")
st.title("HookGen — модифікації креативу-переможця")

script_text = st.text_area("Скрипт переможця", (DATA / "winner_script.md").read_text(), height=260)
uploaded = st.file_uploader("Історія хуків (CSV)", type="csv")
history = read_history(uploaded if uploaded else DATA / "hooks_history.csv")
st.caption("Історія: " + (uploaded.name if uploaded else "data/hooks_history.csv (за замовчуванням)")
           + ". Бренд-гайд: data/brand.yaml.")

col1, col2 = st.columns(2)
n = col1.slider("Кількість варіантів (N)", 5, 40, 20)
mock = col2.checkbox("Mock mode", value=not os.getenv("ANTHROPIC_API_KEY"))

if st.button("Generate", type="primary"):
    try:
        with st.spinner("Генеруємо та перевіряємо варіанти…"):
            brief, paths = run(parse_script(script_text), read_brand(DATA / "brand.yaml"),
                               history, n, OUT, mock=mock)
        st.session_state["result"] = (brief, paths)
    except (LLMError, ValueError) as e:
        st.error(str(e))

if "result" in st.session_state:
    brief, paths = st.session_state["result"]
    st.success(f"Ready: {len(brief.ready())} / {brief.n_requested}, "
               f"rejected: {len(brief.rejected())}. Вартість ≈ ${brief.est_cost_usd:.4f}")
    show = st.radio("Показати", ["all", "ready", "rejected"], horizontal=True)
    df = pd.DataFrame(brief_to_rows(brief))
    df["flags"] = [" ".join(f"{BADGE[f.severity]} {f.code}" for f in v.flags)
                   for v in brief.variants]
    if show != "all":
        df = df[df["status"] == show]
    st.dataframe(df[["mod_id", "status", "element_changed", "angle", "new_text",
                     "flags", "rationale"]], hide_index=True, width="stretch")
    d1, d2 = st.columns(2)
    d1.download_button("brief.csv", paths["csv"].read_bytes(), "brief.csv", "text/csv")
    d2.download_button("brief.md", paths["md"].read_bytes(), "brief.md", "text/markdown")

st.subheader("Angle stats")
stats = angle_stats(history)
st.bar_chart(stats.set_index("angle")["avg_ctr"])
st.dataframe(stats, hide_index=True)
