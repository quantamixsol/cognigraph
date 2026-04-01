"""Clearance filter for multi-backend debate (ADR-139).

Filters KG context based on backend clearance level before prompt
assembly.  Pure logic — no logging, no LLM calls.
"""

from __future__ import annotations

from graqle.core.types import ClearanceLevel


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
        the key default to ``PUBLIC``.
        """
        filtered: list[dict] = []
        for node in nodes:
            node_level = self._parse_clearance(node.get("clearance"))
            if node_level <= clearance:
                filtered.append(node)
        return filtered

    def get_effective_clearance(
        self,
        panelist: str,
        clearance_levels: dict[str, str],
    ) -> ClearanceLevel:
        """Look up a panelist's clearance, defaulting to PUBLIC."""
        raw = clearance_levels.get(panelist)
        return self._parse_clearance(raw)

    def check_output_clearance(
        self,
        max_clearance_seen: ClearanceLevel,
        output_clearance: ClearanceLevel,
    ) -> None:
        """Raise if synthesis saw higher-clearance context than output allows.

        Prevents clearance laundering: CONFIDENTIAL context processed by
        a trusted backend must not be returned through a PUBLIC channel.
        """
        if max_clearance_seen > output_clearance:
            raise ClearanceViolationError(
                f"Synthesis saw {max_clearance_seen.name} context "
                f"but output clearance is {output_clearance.name}. "
                f"Cannot downgrade clearance.",
                max_seen=max_clearance_seen,
                output_level=output_clearance,
            )

    @staticmethod
    def _parse_clearance(raw: str | None) -> ClearanceLevel:
        """Parse a raw clearance string, defaulting to PUBLIC."""
        if raw is None:
            return ClearanceLevel.PUBLIC
        try:
            return ClearanceLevel[raw.upper()] if isinstance(raw, str) else raw
        except (KeyError, ValueError, AttributeError):
            return ClearanceLevel.PUBLIC


class ClearanceViolationError(Exception):
    """Raised when synthesis output would launder clearance levels."""

    def __init__(
        self,
        message: str,
        *,
        max_seen: ClearanceLevel,
        output_level: ClearanceLevel,
    ) -> None:
        super().__init__(message)
        self.max_seen = max_seen
        self.output_level = output_level
