"""Debate configuration loader — runtime constants from .graqle/debate_config.json.

Loads trade-secret debate parameters from a gitignored JSON file at runtime.
Safe non-revealing defaults are used when the config file is absent.
"""

# ── graqle:intelligence ──
# module: graqle.orchestration.debate_config
# risk: LOW (impact radius: 1 module)
# consumers: orchestration.debate
# dependencies: __future__, json, logging, os, pathlib
# constraints: none
# ── /graqle:intelligence ──

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Union

logger = logging.getLogger("graqle.orchestration.debate_config")

# Safe non-revealing defaults — identity / neutral / disabled values only.
_DEFAULTS: dict[str, Union[float, int]] = {
    "decay_factor": 1.0,              # identity — no decay
    "convergence_threshold": 0.5,     # neutral midpoint
    "cost_per_panelist_usd": 0.0,     # cost tracking disabled
    "phases_per_round": 1,            # minimal single phase
    "debate_temperature": 1.0,        # standard LLM default
}

_DEFAULT_PATH = Path(".graqle") / "debate_config.json"

_cache: dict[str, Union[float, int]] | None = None


def _resolve_path() -> Path:
    """Return config file path, respecting ``GRAQLE_DEBATE_CONFIG`` env override."""
    override = os.environ.get("GRAQLE_DEBATE_CONFIG")
    if override:
        return Path(override)
    return _DEFAULT_PATH


def _load_config() -> dict[str, Union[float, int]]:
    """Load config from JSON, merging with defaults. Cached after first call.

    Follows the pattern of ``LicenseManager._load_license()`` and
    ``GraqleConfig.from_yaml()`` — attempt file load, fall back
    gracefully, cache the result.
    """
    global _cache  # noqa: PLW0603
    if _cache is not None:
        return _cache

    merged: dict[str, Union[float, int]] = dict(_DEFAULTS)
    path = _resolve_path()

    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                logger.warning("debate_config: expected JSON object, using defaults")
            else:
                for key, default_val in _DEFAULTS.items():
                    if key in raw and isinstance(raw[key], (int, float)):
                        merged[key] = type(default_val)(raw[key])
                logger.debug("Loaded debate config from %s", path)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "debate_config: failed to load %s (%s), using defaults", path, exc
            )
    else:
        logger.debug("debate_config: %s not found, using safe defaults", path)

    _cache = merged
    return _cache


def get(key: str) -> Union[float, int]:
    """Return a debate config value by *key*.

    Raises ``KeyError`` for unrecognised keys.
    """
    config = _load_config()
    if key not in _DEFAULTS:
        raise KeyError(f"Unknown debate config key: {key!r}")
    return config[key]


def invalidate_cache() -> None:
    """Clear the cached config — intended for testing."""
    global _cache  # noqa: PLW0603
    _cache = None
