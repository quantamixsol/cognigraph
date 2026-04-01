"""Clearance filter for multi-backend debate (ADR-139).

Filters KG context based on backend clearance level before prompt
assembly.  Pure logic — no logging, no LLM calls.
"""

from __future__ import annotations

from graqle.core.types import ClearanceLevel

# Rank ordering: higher rank grants access to more sensitive nodes.
CLEARANCE_HIERARCHY: dict[ClearanceLevel, int] = {
    ClearanceLevel.PUBLIC: 0,
    ClearanceLevel.INTERNAL: 1,
    ClearanceLevel.CONFIDENTIAL: 2,
}


class ClearanceFilter:
    """Filter KG nodes by backend clearance level."""

    def filter_nodes(
        self,
        nodes: list[dict],
        clearance: ClearanceLevel,
    ) -> list[dict]:
        """Return only nodes whose clearance rank <= the backend's rank.

        Each node dict may carry a ``"clearance"`` key whose value is a
        :class:`ClearanceLevel` name (case-insensitive).  Nodes without
        the key default to ``"public"``.
        """
        max_rank = CLEARANCE_HIERARCHY.get(clearance, 0)
        filtered: list[dict] = []
        for node in nodes:
            raw = node.get("clearance", "public")
            try:
                node_level = ClearanceLevel(raw.lower()) if isinstance(raw, str) else raw
            except (ValueError, AttributeError):
                node_level = ClearanceLevel.PUBLIC
            if CLEARANCE_HIERARCHY.get(node_level, 0) <= max_rank:
                filtered.append(node)
        return filtered

    def get_effective_clearance(
        self,
        panelist: str,
        clearance_levels: dict[str, str],
    ) -> ClearanceLevel:
        """Look up a panelist's clearance, defaulting to PUBLIC."""
        raw = clearance_levels.get(panelist)
        if raw is None:
            return ClearanceLevel.PUBLIC
        try:
            return ClearanceLevel(raw.lower()) if isinstance(raw, str) else raw
        except (ValueError, AttributeError):
            return ClearanceLevel.PUBLIC
