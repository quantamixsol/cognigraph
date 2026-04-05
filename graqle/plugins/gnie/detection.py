"""GNIE local backend detection — 3-layer protocol.

Layer 1: Explicit ``is_local`` property (authoritative)
Layer 2: Cost heuristic (cost_per_1k_tokens < threshold)
Layer 3: Endpoint hostname inspection (localhost / 127.0.0.1 / ::1)

This module NEVER imports CogniNode or Graqle — dependency flows
one way: CogniNode -> GNIE, never reverse.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

# Cost threshold: anything below this is considered "local" (free).
# OllamaBackend reports $0.0001/1k.  Bedrock Haiku is $0.0008 — well above.
_LOCAL_COST_THRESHOLD = 0.0002

# 0.0.0.0 is intentionally excluded — it's a wildcard bind, not loopback.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def is_local_backend(backend: Any) -> bool:
    """Detect if a backend runs locally (GNIE should activate).

    Uses a 3-layer protocol:
    1. Explicit declaration via ``is_local`` property (most authoritative)
    2. Cost heuristic — near-zero cost implies local
    3. Endpoint hostname inspection — localhost-like hosts
    """
    # Layer 1: Explicit declaration (authoritative)
    try:
        return bool(backend.is_local)
    except AttributeError:
        pass

    # Layer 2: Cost heuristic (guard against non-numeric values)
    cost = getattr(backend, "cost_per_1k_tokens", None)
    if isinstance(cost, (int, float)) and 0 <= cost < _LOCAL_COST_THRESHOLD:
        return True

    # Layer 3: Endpoint/host heuristic
    # Check public attributes first, then private ones
    for attr in ("host", "endpoint", "base_url", "_host", "_endpoint"):
        url = getattr(backend, attr, None)
        if url and isinstance(url, str):
            try:
                hostname = urlparse(url).hostname or ""
                if hostname in _LOCAL_HOSTS:
                    return True
            except ValueError:
                continue

    return False
