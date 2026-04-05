"""GNIE Confidence Calibrator — adjusts confidence for local models.

Local models produce different confidence distributions than cloud models.
This calibrator adjusts confidence scores based on:
1. Agent agreement ratio (structural signal)
2. Confidence spread penalty (disagreement detection)
3. Learned calibration from graq_predict fold-back history

This module NEVER imports CogniNode or Graqle — dependency flows
one way: CogniNode -> GNIE, never reverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class AgentOutput:
    """Minimal agent output for calibration."""
    node_id: str
    confidence: float
    text_length: int


class ConfidenceCalibrator:
    """Calibrates confidence scores for local LLM backends.

    Cloud models (Sonnet, Opus) have well-calibrated confidence.
    Local models (qwen, deepseek) tend to be miscalibrated.
    This adjusts based on structural signals, not model internals.
    """

    def __init__(self, fold_back_history: Optional[Dict] = None):
        """
        fold_back_history: {
            "writes": int,  # successful fold-backs (high confidence was correct)
            "skips": int,   # skipped fold-backs (high confidence was wrong)
        }
        """
        self.history = fold_back_history or {"writes": 0, "skips": 0}
        self._calibration_offset = self._compute_offset()

    def _compute_offset(self) -> float:
        """Compute calibration offset from fold-back history.

        If most fold-backs succeed: model is well-calibrated, small offset.
        If many fold-backs fail: model is miscalibrated, larger offset.
        """
        total = self.history["writes"] + self.history["skips"]
        if total < 5:
            return 0.0  # Not enough data — don't adjust
        success_rate = self.history["writes"] / total
        # If success rate > 0.7: model is well-calibrated, reduce offset
        # If success rate < 0.3: model is poorly calibrated, increase offset
        return (0.5 - success_rate) * 0.2  # Range: -0.1 to +0.1

    def calibrate(
        self,
        raw_confidence: float,
        agent_outputs: List[AgentOutput],
    ) -> float:
        """Calibrate confidence score.

        Combines:
        1. Raw confidence from synthesis
        2. Agent agreement ratio (structural signal)
        3. Learned calibration offset from fold-back history
        """
        if not agent_outputs:
            return raw_confidence

        # Agreement ratio: what fraction of agents produced substantive output
        substantive = sum(
            1 for a in agent_outputs
            if a.text_length > 50 and a.confidence > 0.3
        )
        agreement_ratio = substantive / len(agent_outputs)

        # Confidence spread: if agents disagree widely, reduce confidence
        confidences = [a.confidence for a in agent_outputs if a.confidence > 0]
        if len(confidences) >= 2:
            spread = max(confidences) - min(confidences)
            spread_penalty = spread * 0.1  # Wide spread = less confident
        else:
            spread_penalty = 0.0

        # Calibrated confidence
        calibrated = (
            raw_confidence * 0.5          # Base: model's own confidence
            + agreement_ratio * 0.4       # Structural: agent agreement
            + self._calibration_offset    # Learned: fold-back history
            - spread_penalty              # Penalty: disagreement
        )

        return max(0.01, min(0.99, calibrated))
