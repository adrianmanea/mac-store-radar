"""Loader for the shared weights spec (M0.4).

Single source of truth lives in radar/weights.json so the Python scorer and the TS
live probe never drift (TECH-PRD §5).
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any


@lru_cache(maxsize=1)
def load_weights() -> dict[str, Any]:
    """Load and cache the weights spec bundled with the package."""
    raw = files("radar").joinpath("weights.json").read_text(encoding="utf-8")
    return json.loads(raw)
