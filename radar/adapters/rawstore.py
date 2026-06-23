"""Raw-response persistence (M1.2).

Every external response is written before parse, keyed by url. Re-scoring never
re-fetches (TECH-PRD §0 mitigation 3). Local dev uses a filesystem store under
.raw_cache/; the pipeline can swap in a DB-backed store later without touching adapters.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Protocol


class RawStore(Protocol):
    """Persist a raw response body keyed by its request url."""

    def put(self, url: str, body: bytes, *, meta: dict | None = None) -> None: ...


class FileRawStore:
    """Filesystem raw store. One file per (url, day) under `root`.

    Keyed by a hash of the url so re-fetching the same url the same day overwrites
    rather than piling up — matches "each app fetched at most once per day".
    """

    def __init__(self, root: str | Path = ".raw_cache") -> None:
        self.root = Path(root)

    def _path(self, url: str) -> Path:
        day = time.strftime("%Y-%m-%d")
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        d = self.root / day
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{digest}.json"

    def put(self, url: str, body: bytes, *, meta: dict | None = None) -> None:
        path = self._path(url)
        path.write_bytes(body)
        if meta is not None:
            path.with_suffix(".meta.json").write_text(
                json.dumps({"url": url, **meta}), encoding="utf-8"
            )


class NullRawStore:
    """No-op store — for tests and the client-side live probe (nothing to persist)."""

    def put(self, url: str, body: bytes, *, meta: dict | None = None) -> None:
        return None
