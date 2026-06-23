"""Config loader (M0.3).

Reads secrets/settings from env (.env locally via python-dotenv, Actions secrets in CI).
Fails loud when a required secret is missing in a run context that needs it — never
silently degrades to a half-configured run.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # no-op in CI where vars come from the environment directly


class ConfigError(RuntimeError):
    """Raised when a required config value is absent."""


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise ConfigError(
            f"Missing required env var {name!r}. "
            f"Set it in .env (local) or GitHub Actions secrets (CI). See .env.example."
        )
    return val


def _opt(name: str, default: str) -> str:
    return os.environ.get(name) or default


@dataclass(frozen=True)
class Config:
    supabase_url: str
    supabase_service_key: str
    rate_limit_per_min: int
    storefront: str
    # Optional: only the LLM jobs (M6) need it. DB/scrape/score paths run without it.
    anthropic_api_key: str | None = None

    @classmethod
    def load(cls) -> Config:
        """Load config. Requires Supabase creds; Anthropic key is optional until M6."""
        return cls(
            supabase_url=_require("SUPABASE_URL"),
            supabase_service_key=_require("SUPABASE_SERVICE_KEY"),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
            rate_limit_per_min=int(_opt("RADAR_RATE_LIMIT_PER_MIN", "18")),
            storefront=_opt("RADAR_STOREFRONT", "us"),
        )

    def require_anthropic(self) -> str:
        """Fetch the Anthropic key or fail loud — called by LLM jobs only (M6)."""
        if not self.anthropic_api_key:
            raise ConfigError(
                "ANTHROPIC_API_KEY is required for LLM jobs. Set it in .env / Actions secrets."
            )
        return self.anthropic_api_key


def runtime_settings() -> dict[str, str | int]:
    """Non-secret settings safe to read without requiring credentials.

    Useful for adapter-only / scoring-only invocations (e.g. the live keyword probe
    path) that hit iTunes but never touch Supabase or Claude.
    """
    return {
        "rate_limit_per_min": int(_opt("RADAR_RATE_LIMIT_PER_MIN", "18")),
        "storefront": _opt("RADAR_STOREFRONT", "us"),
    }
