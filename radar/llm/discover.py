"""LLM candidate generation (M9 Discovery).

Claude proposes arbitrage-shaped niche keywords; iTunes + the scorer dispose. The model
is told the exact thesis (existing demand, weak/abandoned Mac incumbents, solo-buildable,
monetizable) and the keywords already tracked, so it expands the frontier instead of
repeating. Defensive JSON parsing — never trust the model to be well-formed.
"""

from __future__ import annotations

import json
import logging
import re

from radar.llm.client import SONNET

log = logging.getLogger("radar.llm")

PROMPT = """You generate candidate search keywords for a Mac App Store \
opportunity-discovery tool. The strategy is ASO arbitrage: find EXISTING search demand \
where the incumbent Mac apps are weak, abandoned, or low-rated, and a solo developer \
could build a better one that people will pay for.

Good candidates look like real things a Mac user would type into App Store search, \
often migration/utility intents, e.g.:
- "android file transfer mac"
- "google photos sync mac"
- "whatsapp backup mac"
- "heic to jpg converter mac"

Rules:
- Each keyword: 2-5 words, lowercase, usually ending in "mac".
- Aim for niches with PROVEN demand but likely WEAK incumbents (utilities, converters, \
transfer/sync tools, menu-bar apps, format viewers) — not categories owned by giants.
- Do NOT repeat any of these already-tracked keywords: {avoid}

Return ONLY a JSON array of {n} distinct keyword strings. No prose, no markdown."""


def _extract_json_array(text: str) -> list[str]:
    """Pull a JSON string array out of a model reply, tolerating fences/prose."""
    fenced = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = fenced.find("["), fenced.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        arr = json.loads(fenced[start : end + 1])
    except json.JSONDecodeError:
        return []
    out = []
    for item in arr:
        if isinstance(item, str) and item.strip():
            out.append(item.strip().lower())
    return out


def generate_candidates(anthropic, n: int = 30, *, avoid: list[str] | None = None) -> list[str]:
    """Ask Claude for `n` candidate keywords, excluding `avoid`. Returns deduped list."""
    avoid_str = ", ".join(sorted(avoid or [])[:200]) or "(none yet)"
    resp = anthropic.messages.create(
        model=SONNET,
        max_tokens=1024,
        messages=[{"role": "user", "content": PROMPT.format(n=n, avoid=avoid_str)}],
    )
    text = resp.content[0].text if resp.content else ""
    candidates = _extract_json_array(text)
    if not candidates:
        log.warning("discovery: model returned no parseable candidates")
    # de-dup while preserving order; drop anything already in avoid
    avoid_set = {a.lower() for a in (avoid or [])}
    seen: dict[str, None] = {}
    for c in candidates:
        if c not in avoid_set:
            seen.setdefault(c, None)
    return list(seen)
