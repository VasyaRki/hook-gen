"""Розподіл кутів: сума = N, мінімум 1 на базовий кут, рівномірно без історії."""

import pytest

from hookgen.history import angle_stats, plan_angles
from hookgen.io import read_history
from hookgen.models import BASE_ANGLES

from .conftest import DATA


@pytest.fixture
def rows():
    return read_history(DATA / "hooks_history.csv")


@pytest.mark.parametrize("n", [4, 5, 7, 20, 23, 40])
def test_plan_sums_to_n(rows, n):
    assert sum(plan_angles(rows, n).values()) == n


@pytest.mark.parametrize("n", [4, 20, 40])
def test_min_one_per_base_angle(rows, n):
    plan = plan_angles(rows, n)
    assert all(plan.get(a, 0) >= 1 for a in BASE_ANGLES)


def test_better_angles_get_more(rows):
    plan = plan_angles(rows, 20)
    assert plan["pain"] > plan["social_proof"]
    assert plan["curiosity"] > plan["contrarian"]


def test_fewer_than_base_angles(rows):
    plan = plan_angles(rows, 2)
    assert sum(plan.values()) == 2 and set(plan) == {"pain", "curiosity"}


def test_uniform_without_history():
    assert plan_angles([], 20) == {a: 5 for a in BASE_ANGLES}
    plan = plan_angles([], 6)
    assert sum(plan.values()) == 6 and max(plan.values()) - min(plan.values()) <= 1


def test_sample_data_has_pain_and_curiosity_on_top(rows):
    stats = angle_stats(rows)
    assert set(stats["angle"][:2]) == {"pain", "curiosity"}
    assert stats["n_ads"].sum() == len(rows)
