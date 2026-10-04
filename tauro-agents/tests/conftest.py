import json
from pathlib import Path

import pytest

from tauro.schemas import Brief, Copy

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def load(name: str) -> tuple[Brief, Copy]:
    data = json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    return Brief.model_validate(data["brief"]), Copy.model_validate(data["copy"])


@pytest.fixture
def sample():
    return load
