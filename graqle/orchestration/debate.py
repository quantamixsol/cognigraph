# ──────────────────────────────────────────────────────────────────
# PATENT NOTICE — Quantamix Solutions B.V.
#
# This module implements methods covered by European Patent
# Applications EP26162901.8 and EP26166054.2, owned by
# Quantamix Solutions B.V.
#
# Use of this software is permitted under the graqle license.
# Reimplementation of the patented methods outside this software
# requires a separate patent license.
#
# Contact: support@quantamixsolutions.com
# ──────────────────────────────────────────────────────────────────

"""DebateOrchestrator — propose / challenge / synthesize debate rounds."""

from __future__ import annotations

import logging
import re
import time

from graqle.config.settings import DebateConfig
from graqle.core.types import DebateTrace, DebateTurn
from graqle.intelligence.governance.debate_citation import (
    CitationError,
    CitationValidator,
)
from graqle.intelligence.governance.debate_cost_gate import (
    BudgetExhaustedError,
    DebateCostGate,
)
from graqle.orchestration.backend_pool import BackendPool, PanelistResponse

logger = logging.getLogger(__name__)

_CONSENSUS_RE = re.compile(
    r"\b(agree|concur|no objection|fully aligned)\b",
    re.IGNORECASE,
)

_CONFIDENCE_RE = re.compile(
    r"[Cc]onfidence[:\s]+(\d+(?:\.\d+)?)(%)?",
)

_DEFAULT_CONFIDENCE = 0.5


def _parse_confidence(text: str) -> float:
    """Extract a confidence score from free-text response, default 0.5."""
    m = _CONFIDENCE_RE.search(text)
    if not m:
        return _DEFAULT_CONFIDENCE
    value = float(m.group(1))
    if m.group(2) or value > 1.0:
        value = value / 100.0
    return max(0.0, min(1.0, value))


def _check_consensus(challenges: list[PanelistResponse]) -> bool:
    """Heuristic: consensus if every challenge contains agreement language."""
    ok_challenges = [c for c in challenges if c.ok]
    if not ok_challenges:
        return False
    return all(_CONSENSUS_RE.search(c.response) for c in ok_challenges)


class DebateOrchestrator:
    """Run multi-round propose / challenge / synthesize debates.

    Each round dispatches prompts to all panelists via a
    :class:`BackendPool`, collects :class:`DebateTurn` records, checks
    the cost gate, and optionally validates citations.
    """

    def __init__(
        self,
        config: DebateConfig,
        pool: BackendPool,
        cost_gate: DebateCostGate,
        citation_validator: CitationValidator | None = None,
    ) -> None:
        self._config = config
        self._pool = pool
        self._cost_gate = cost_gate
        self._citation_validator = citation_validator

    async def run(self, query: str, context: str = "") -> DebateTrace:
        """Execute the full debate and return a :class:`DebateTrace`."""
        turns: list[DebateTurn] = []
        total_cost = 0.0
        total_latency = 0.0
        consensus_reached = False
        synthesis_text = ""
        rounds_completed = 0
        t_start = time.monotonic()

        proposals: list[PanelistResponse] = []
        challenges: list[PanelistResponse] = []

        for round_idx in range(1, self._config.max_rounds + 1):
            # ── budget guard ────────────────────────────────────
            round_estimate = 0.01 * len(self._pool.panelist_names) * 3
            try:
                self._cost_gate.check_round(round_estimate)
            except BudgetExhaustedError:
                logger.warning("Budget exhausted before round %d.", round_idx)
                break

            # ── Phase 1: Propose ────────────────────────────────
            propose_prompt = self._build_propose_prompt(query, context)
            proposals = await self._pool.dispatch_all(propose_prompt)
            phase_cost = sum(p.cost_usd for p in proposals)
            total_cost += phase_cost

            for p in proposals:
                if p.ok:
                    turns.append(DebateTurn(
                        round_number=round_idx,
                        panelist=p.panelist,
                        position="propose",
                        argument=p.response,
                        evidence_refs=[],
                        confidence=_parse_confidence(p.response),
                        cost_usd=p.cost_usd,
                        latency_ms=p.latency_ms,
                    ))

            # ── Phase 2: Challenge ──────────────────────────────
            challenge_prompt = self._build_challenge_prompt(query, proposals)
            challenges = await self._pool.dispatch_all(challenge_prompt)
            phase_cost = sum(c.cost_usd for c in challenges)
            total_cost += phase_cost

            for c in challenges:
                if c.ok:
                    turns.append(DebateTurn(
                        round_number=round_idx,
                        panelist=c.panelist,
                        position="challenge",
                        argument=c.response,
                        evidence_refs=[],
                        confidence=_parse_confidence(c.response),
                        cost_usd=c.cost_usd,
                        latency_ms=c.latency_ms,
                    ))

            # ── Convergence heuristic ───────────────────────────
            if _check_consensus(challenges):
                consensus_reached = True

            # ── Phase 3: Synthesize ─────────────────────────────
            synth_prompt = self._build_synthesize_prompt(
                query, proposals, challenges,
            )
            synth_responses = await self._pool.dispatch_all(synth_prompt)
            phase_cost = sum(s.cost_usd for s in synth_responses)
            total_cost += phase_cost

            synth = synth_responses[0] if synth_responses else None
            synthesis_text = synth.response if (synth and synth.ok) else ""

            if synth and synth.ok:
                turns.append(DebateTurn(
                    round_number=round_idx,
                    panelist=synth.panelist,
                    position="synthesize",
                    argument=synth.response,
                    evidence_refs=[],
                    confidence=_parse_confidence(synth.response),
                    cost_usd=synth.cost_usd,
                    latency_ms=synth.latency_ms,
                ))

            self._cost_gate.record_and_decay(phase_cost)
            rounds_completed = round_idx

            if consensus_reached:
                logger.info("Consensus reached after round %d.", round_idx)
                break

        # ── Compute final confidence ────────────────────────────
        propose_turns = [t for t in turns if t.position == "propose"]
        confidences = [t.confidence for t in propose_turns]
        final_confidence = (
            sum(confidences) / len(confidences)
            if confidences
            else _DEFAULT_CONFIDENCE
        )

        total_latency = (time.monotonic() - t_start) * 1000.0

        return DebateTrace(
            query=query,
            turns=turns,
            synthesis=synthesis_text,
            final_confidence=final_confidence,
            total_cost_usd=total_cost,
            total_latency_ms=total_latency,
            consensus_reached=consensus_reached,
            rounds_completed=rounds_completed,
            panelist_names=self._pool.panelist_names,
        )

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_propose_prompt(self, query: str, context: str) -> str:
        parts = [
            "You are a debate panelist. Propose a well-reasoned answer.",
            f"\nQuery: {query}",
        ]
        if context:
            parts.append(f"\nContext:\n{context}")
        parts.append(
            "\nProvide your proposal. End with 'Confidence: X.XX' "
            "where X.XX is a value between 0 and 1."
        )
        return "\n".join(parts)

    def _build_challenge_prompt(
        self, query: str, proposals: list[PanelistResponse],
    ) -> str:
        proposal_block = "\n---\n".join(
            f"[{p.panelist}]: {p.response}" for p in proposals if p.ok
        )
        return (
            "You are a debate panelist in the challenge phase. "
            "Review the proposals below and critique them. "
            "If you fully agree, say 'I concur'. Otherwise raise "
            "specific objections.\n\n"
            f"Original query: {query}\n\n"
            f"Proposals:\n{proposal_block}"
        )

    def _build_synthesize_prompt(
        self,
        query: str,
        proposals: list[PanelistResponse],
        challenges: list[PanelistResponse],
    ) -> str:
        proposal_block = "\n---\n".join(
            f"[{p.panelist}]: {p.response}" for p in proposals if p.ok
        )
        challenge_block = "\n---\n".join(
            f"[{c.panelist}]: {c.response}" for c in challenges if c.ok
        )
        return (
            "You are the debate judge. Synthesize the proposals and "
            "challenges into a single, well-supported answer.\n\n"
            f"Query: {query}\n\n"
            f"Proposals:\n{proposal_block}\n\n"
            f"Challenges:\n{challenge_block}\n\n"
            "Provide a final synthesized answer. End with "
            "'Confidence: X.XX' where X.XX is between 0 and 1."
        )
