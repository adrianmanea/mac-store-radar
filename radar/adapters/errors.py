"""Adapter error contract (M1.8).

One exception family so the pipeline can distinguish a transient rate-limit (retry /
back off) from a permanent schema break (degrade that signal, keep the run going —
TECH-PRD §9).
"""

from __future__ import annotations


class AdapterError(RuntimeError):
    """Base for all adapter failures."""


class RateLimitError(AdapterError):
    """HTTP 403 / throttle breach. Transient — caller backs off and retries."""


class TransientError(AdapterError):
    """Timeout / 5xx / network blip. Transient — retry with backoff."""


class SchemaError(AdapterError):
    """Response parsed but did not match the expected shape.

    Permanent for this run — the source likely changed (autocomplete/charts).
    Degrade the single signal, do not abort the whole scrape.
    """
