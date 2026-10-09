from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


PRESET_FILE = Path(__file__).resolve().parent.parent / "seed" / "coverage_presets.json"


@lru_cache
def get_coverage_presets() -> list[dict[str, Any]]:
    with PRESET_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_preset(code: str) -> dict[str, Any] | None:
    return next((item for item in get_coverage_presets() if item["code"] == code), None)

