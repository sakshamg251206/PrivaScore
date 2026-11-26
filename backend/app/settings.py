"""Backend configuration from PRIVASCORE_* environment variables (and the repo-root .env).

GEMINI_API_KEY is deliberately NOT a field here: privascore reads it from the environment
itself, so it can never leak through a Settings repr or a /meta response.
"""
from __future__ import annotations

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from privascore.flags import REPO_ROOT


def _csv(v):
    """pydantic-settings parses list fields as JSON by default; we want plain comma-separated."""
    if isinstance(v, str):
        return [p.strip() for p in v.split(",") if p.strip()]
    return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PRIVASCORE_", env_file=REPO_ROOT / ".env",
                                      extra="ignore", case_sensitive=False)

    env: Literal["dev", "prod"] = "dev"

    llm_provider: str = ""          # empty -> whatever privascore.toml says
    llm_model: str = ""
    # A second model to try once when the primary one has no quota left. Empty disables it.
    # The provider's daily cap is per model, so a different model has its own allowance.
    # NOT a free win: gold-set accuracy differs by model (README "Results"), so whatever
    # answers is named in meta.model and shown in the UI. Never fall back silently.
    llm_fallback_model: str = ""

    bert: Literal["on", "off"] = "on"
    bert_required: bool = True
    bert_sanity: Literal["on", "off"] = "off"

    min_chars: int = 1000
    max_chars: int = 200_000
    max_body_bytes: int = 1_000_000
    max_concurrent: int = 1

    cors_origins: list[str] = ["http://localhost:5173"]

    # /evaluate spends a real provider call, so it is rate limited by default. 0 disables.
    # The daily budget is the figure that actually bounds the key's spend: a per-client limit
    # alone does not stop many clients each staying politely under their own allowance.
    rate_limit_per_client: int = 10
    rate_limit_window_s: int = 3600
    rate_limit_daily_budget: int = 200
    # Only enable behind a reverse proxy that sets X-Forwarded-For. Believing that header
    # without one lets any client mint a fresh identity per request. `hops` is how many proxies
    # of OUR OWN sit in front: the client's address is that many entries from the right, because
    # anything the client put in the header survives on the left.
    trust_proxy: bool = False
    trusted_proxy_hops: int = 1

    # Path to frontend/dist. When set, the API also serves the built app, so a deployment is a
    # single origin with no CORS. Empty in development, where Vite serves the frontend.
    static_dir: str = ""

    llm_max_rate_limit_waits: int = 0
    llm_overload_waits: list[float] = [10.0]
    llm_max_http_retries: int = 1

    examples: Literal["on", "off"] = "on"
    examples_run: str = "gemini36_batch_v1.1"   # runs/<name>/, must match the saved metrics

    _split = field_validator("cors_origins", "llm_overload_waits", mode="before")(_csv)

    @property
    def bert_enabled(self) -> bool:
        return self.bert == "on"
