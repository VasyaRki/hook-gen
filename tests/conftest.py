"""Спільні фікстури тестів: шляхи до sample-даних і завантажений бренд-гайд."""

from pathlib import Path

import pytest

from hookgen.io import read_brand

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


@pytest.fixture
def brand():
    return read_brand(DATA / "brand.yaml")
