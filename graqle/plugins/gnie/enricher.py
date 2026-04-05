"""GNIE Prompt Enricher — graph-structural context for local LLM backends.

Enriches per-node agent prompts with graph topology information that
helps smaller local models reason better about node relationships.

Adapts enrichment intensity based on model capability tier:
- small (<4B): maximum scaffolding, explicit CoT, response format hints
- medium (4-13B): moderate guidance, structural context
- large (13B+): minimal enrichment, node identity only

This module NEVER imports CogniNode or Graqle — dependency flows
one way: CogniNode -> GNIE, never reverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class CapabilityTier(Enum):
    """Model capability classification for enrichment intensity."""
    SMALL = "small"    # <4B params — heavy scaffolding
    MEDIUM = "medium"  # 4-13B params — moderate guidance
    LARGE = "large"    # 13B+ params — minimal enrichment


@dataclass(frozen=True)
class NodeContext:
    """Minimal node info needed for enrichment.

    Constructed by CogniNode at reason() time — GNIE never
    imports CogniNode directly (avoids circular deps).
    """
    node_id: str
    node_type: str
    label: str
    description: str
    neighbor_count: int
    neighbor_types: Dict[str, int]  # {type: count}


def detect_capability_tier(model_name: str) -> CapabilityTier:
    """Auto-detect capability tier from model name.

    Check ORDER matters — larger param patterns first to avoid
    substring matches (e.g. "12b" contains "2b").
    """
    name = model_name.lower()
    # Large: 12B+ or frontier — check FIRST (avoids "12b" matching "2b")
    if any(s in name for s in ("12b", "14b", "26b", "31b", "32b", "70b")):
        return CapabilityTier.LARGE
    # Medium: 4-13B range
    if any(s in name for s in ("4b", "e4b", "7b", "8b")):
        return CapabilityTier.MEDIUM
    # Small: explicit small param counts
    if any(s in name for s in ("0.5b", "1b", "2b", "3b")):
        return CapabilityTier.SMALL
    # Small: known tiny models
    if any(s in name for s in ("phi3:mini", "tinyllama")):
        return CapabilityTier.SMALL
    # Default: medium (safe middle ground)
    return CapabilityTier.MEDIUM


class GnieEnricher:
    """Enriches per-node agent prompts for local LLM backends.

    ONLY activates when backend is local (Ollama, custom local, etc.)
    DORMANT when backend is cloud (Bedrock, OpenAI, Anthropic)

    Adds:
    1. Node type and structural position
    2. Neighbor topology summary
    3. Round context (what happened in previous rounds)
    4. Response format hints (most helpful for small models)
    """

    def __init__(self, tier: CapabilityTier = CapabilityTier.MEDIUM):
        self.tier = tier

    @classmethod
    def for_model(cls, model_name: str) -> "GnieEnricher":
        """Auto-detect capability level from model name."""
        return cls(detect_capability_tier(model_name))

    def enrich(
        self,
        base_prompt: str,
        node: NodeContext,
        query: str,
        round_idx: int = 0,
        total_rounds: int = 3,
        prior_round_summary: Optional[str] = None,
    ) -> str:
        """Enrich a per-node agent prompt with graph-structural context.

        Returns the enriched prompt (prepends context before base_prompt).
        """
        parts: list[str] = []

        # 1. Node identity and type
        parts.append(f"[You are reasoning about a {node.node_type} node: '{node.label}']")

        # 2. Structural position (how connected is this node)
        if self.tier in (CapabilityTier.SMALL, CapabilityTier.MEDIUM):
            if node.neighbor_count > 0:
                type_summary = ", ".join(
                    f"{count} {ntype}" for ntype, count in
                    sorted(node.neighbor_types.items(), key=lambda x: -x[1])[:5]
                )
                parts.append(f"[Connected to {node.neighbor_count} nodes: {type_summary}]")
            else:
                parts.append("[This node is isolated — no direct connections]")

        # 3. Round context
        if round_idx > 0:
            parts.append(
                f"[Reasoning round {round_idx + 1}/{total_rounds}. "
                f"Refine and build on previous findings.]"
            )
            if prior_round_summary and self.tier == CapabilityTier.SMALL:
                parts.append(f"[Previous round found: {prior_round_summary[:200]}]")

        # 4. Response format hints (most helpful for small models)
        if self.tier == CapabilityTier.SMALL:
            parts.append(
                "[Instructions: Be specific. Use facts from your context. "
                "State your confidence (high/medium/low). Keep response under 200 words.]"
            )
        elif self.tier == CapabilityTier.MEDIUM:
            parts.append("[Be specific and cite your evidence.]")

        # Combine: enrichment prefix + original prompt
        enrichment = "\n".join(parts)
        return f"{enrichment}\n\n{base_prompt}"

    def enrich_synthesis(
        self,
        base_prompt: str,
        agent_count: int,
        task_type: str = "REASON",
    ) -> str:
        """Enrich the synthesis prompt (combines all agent outputs into final answer)."""
        parts: list[str] = []

        parts.append(f"[SYNTHESIS: Combine {agent_count} agent perspectives into one answer]")
        parts.append(f"[Task type: {task_type}]")

        if self.tier == CapabilityTier.SMALL:
            parts.append(
                "[Instructions: (1) Find areas of agreement across agents. "
                "(2) Flag contradictions. (3) Weight by agent confidence. "
                "(4) Produce a single coherent answer with confidence score.]"
            )

        enrichment = "\n".join(parts)
        return f"{enrichment}\n\n{base_prompt}"
