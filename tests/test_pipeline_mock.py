"""Наскрізний прогін generate --mock: 3 файли, рядок у runs.csv, правильні статуси проблемних варіантів."""

import csv
import json

import pytest
from typer.testing import CliRunner

from hookgen.cli import app
from hookgen.llm import LLMClient, LLMError
from hookgen.models import WinnerAnalysis

from .conftest import DATA


def run_mock(out_dir, n=20):
    result = CliRunner().invoke(app, [
        "generate", "--mock", "--script", str(DATA / "winner_script.md"),
        "--brand", str(DATA / "brand.yaml"), "--history", str(DATA / "hooks_history.csv"),
        "-n", str(n), "--out", str(out_dir)])
    assert result.exit_code == 0, result.output
    run_dir = next(p for p in out_dir.iterdir() if p.is_dir())
    return run_dir, json.loads((run_dir / "brief.json").read_text())


def by_code(brief, code):
    return [v for v in brief["variants"] if any(f["code"] == code for f in v["flags"])]


def test_creates_files_and_run_log(tmp_path):
    run_dir, brief = run_mock(tmp_path)
    assert {p.name for p in run_dir.iterdir()} == {"brief.csv", "brief.md", "brief.json"}
    rows = list(csv.DictReader((tmp_path / "runs.csv").open()))
    assert len(rows) == 1
    assert rows[0]["n_requested"] == "20" and rows[0]["n_ready"] == "20"
    assert rows[0]["input_tokens"] == "0" and rows[0]["model"] == "mock"


def test_problem_variants_are_rejected(tmp_path):
    _, brief = run_mock(tmp_path)
    assert len(by_code(brief, "TOO_LONG")) == 2
    assert len(by_code(brief, "BANNED_PHRASE")) == 1
    assert len(by_code(brief, "DUPLICATE")) == 1
    for code in ("TOO_LONG", "BANNED_PHRASE", "DUPLICATE"):
        assert all(v["status"] == "rejected" for v in by_code(brief, code))


def test_warnings_do_not_reject(tmp_path):
    _, brief = run_mock(tmp_path)
    wrong_price = by_code(brief, "OFF_BRAND_FACT")
    assert len(wrong_price) == 1 and "$19" in wrong_price[0]["new_text"]
    assert wrong_price[0]["status"] == "ready"
    assert all(v["status"] == "ready" for v in by_code(brief, "PERSONAL_ATTRIBUTE"))


def test_exactly_one_element_changed(tmp_path):
    _, brief = run_mock(tmp_path)
    for v in brief["variants"]:
        assert f"{v['element_changed'].upper()}: {v['new_text']}" in v["full_script"]
        assert "CTA: Take the 30-second quiz" in v["full_script"]


def test_refill_when_not_enough_ready(tmp_path):
    _, brief = run_mock(tmp_path, n=25)
    assert sum(v["status"] == "ready" for v in brief["variants"]) == 25


def make_client(answers):
    """LLMClient без мережі: _call повертає заздалегідь задані відповіді."""
    client = LLMClient.__new__(LLMClient)
    client.mock, client.model = False, "test"
    client._call = lambda messages: answers.pop(0)
    return client


GOOD = '{"pain": "p", "angle": "pain", "structure": "s", "key_emotion": "e"}'


def test_retry_once_on_invalid_json():
    assert make_client(["not json", GOOD]).analyze("x") == WinnerAnalysis.model_validate_json(GOOD)
    assert make_client(["```json\n" + GOOD + "\n```"]).analyze("x").pain == "p"


def test_clear_error_after_second_invalid_json():
    with pytest.raises(LLMError):
        make_client(["not json", '{"pain": "only"}']).analyze("x")
