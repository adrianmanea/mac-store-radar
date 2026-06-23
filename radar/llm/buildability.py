"""Buildability tagging (M6.2).

Classifies each app's build complexity from its name + description so the scorer's
buildability multiplier (M3.5) and the unbuildable gate become real signals instead of
the neutral default. Model: Haiku (cheap classification). Only ever runs on apps missing
`complexity_class` — never re-processes (cost control, PRD §6).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from radar.llm.client import HAIKU

log = logging.getLogger("radar.llm")

VALID = {"wrapper", "integration", "native_complex"}

PROMPT = """You classify how hard a Mac app is for a solo developer to build, from its \
store listing. Reply with EXACTLY ONE word, no punctuation, no explanation:

- wrapper: thin client over a web API / website, or a simple utility (e.g. a menu-bar \
app, a REST client, a webpage wrapper).
- integration: needs real OS or device integration (Finder/MTP/USB, filesystem sync, \
network protocols, media transcoding) but no deep native engine.
- native_complex: complex native engine (video editor, DAW, 3D, custom rendering, \
drivers, kernel extensions).

App: {name}
Description: {description}

One word:"""


def _coerce(text: str) -> str | None:
    """Pull a valid class label out of a model reply, defensively."""
    token = text.strip().lower().split()[0].strip(".,:;\"'") if text.strip() else ""
    if token in VALID:
        return token
    # tolerate the model echoing the word inside a sentence
    for v in VALID:
        if v in text.lower():
            return v
    return None


def classify_app(anthropic, name: str, description: str | None) -> str | None:
    """Classify one app. Returns a label or None if the reply can't be coerced."""
    resp = anthropic.messages.create(
        model=HAIKU,
        max_tokens=8,
        messages=[
            {
                "role": "user",
                "content": PROMPT.format(name=name, description=(description or "")[:2000]),
            }
        ],
    )
    text = resp.content[0].text if resp.content else ""
    label = _coerce(text)
    if label is None:
        log.warning("buildability: uncoercible reply %r for %s", text, name)
    return label


def _untagged_apps(db, cap: int) -> list[dict]:
    res = (
        db.table("apps")
        .select("app_id,name,description")
        .is_("complexity_class", "null")
        .limit(cap)
        .execute()
    )
    return res.data or []


def tag_untagged(db, anthropic, *, cap: int = 50) -> dict:
    """Tag up to `cap` untagged apps, write complexity_class + complexity_at. Returns counts."""
    apps = _untagged_apps(db, cap)
    tagged = 0
    for a in apps:
        label = classify_app(anthropic, a["name"], a.get("description"))
        if label is None:
            continue
        db.table("apps").update(
            {"complexity_class": label, "complexity_at": datetime.now(timezone.utc).isoformat()}
        ).eq("app_id", a["app_id"]).execute()
        tagged += 1
    log.info("buildability: tagged %d/%d apps", tagged, len(apps))
    return {"seen": len(apps), "tagged": tagged}
