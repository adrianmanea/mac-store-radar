"""Seed niches — the initial watched keywords (M2.5) and the M3.8 calibration set.

Arbitrage-shaped: existing demand ("<thing> mac") with potentially weak Mac incumbents.
Edit freely; `seed_niches` is idempotent so adding keywords here and re-running is safe.
"""

from __future__ import annotations

DEFAULT_NICHES: list[str] = [
    "android file transfer mac",
    "android messages mac",
    "whatsapp transfer mac",
    "google drive sync mac",
    "google photos mac",
    "screen recorder mac",
    "pdf editor mac",
    "menu bar calendar mac",
    "clipboard manager mac",
    "window manager mac",
    "markdown editor mac",
    "rss reader mac",
    "habit tracker mac",
    "screenshot annotation mac",
    "video compressor mac",
    "audio recorder mac",
    "icon changer mac",
    "battery health mac",
    "duplicate file finder mac",
    "color picker mac",
]
