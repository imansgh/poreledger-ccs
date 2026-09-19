"""Deployment-time configuration for the HTTP layer.

Everything here is read from the environment so the same image can run in
development and behind a reverse proxy without code changes. Defaults are
deliberately restrictive: an unset variable must never widen access.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

#: Maximum JSON request body. The endpoints accept a handful of numbers; a body
#: larger than this is either a mistake or an attempt to make the server do
#: parsing work. Starlette does not cap body size by default.
DEFAULT_MAX_BODY_BYTES = 16 * 1024


def _origins_from_env(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(o.strip() for o in raw.split(",") if o.strip())


@dataclass(frozen=True)
class Settings:
    """Resolved configuration for one process."""

    data_dir: str = "data"
    #: Allowed CORS origins. Empty by default: cross-origin browser access is
    #: off until an operator names the origins explicitly. There is no wildcard
    #: default, because a public demo that reflects any Origin is a footgun.
    cors_origins: tuple[str, ...] = ()
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES
    #: Warm the normalization cache during startup. Without it the first
    #: request pays for reading a workbook and three CSVs.
    warm_cache_on_startup: bool = True
    docs_enabled: bool = True

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        return cls(
            data_dir=source.get("CCS_DATA_DIR", "data"),
            cors_origins=_origins_from_env(source.get("CCS_CORS_ORIGINS")),
            max_body_bytes=int(source.get("CCS_MAX_BODY_BYTES", DEFAULT_MAX_BODY_BYTES)),
            warm_cache_on_startup=source.get("CCS_WARM_CACHE", "1") not in ("0", "false", "False"),
            docs_enabled=source.get("CCS_DOCS", "1") not in ("0", "false", "False"),
        )

    @property
    def cors_enabled(self) -> bool:
        return bool(self.cors_origins)
