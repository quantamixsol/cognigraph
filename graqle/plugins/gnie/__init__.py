"""GNIE — GraQle-Native Inference Enhancement.

A quality amplifier for local LLM backends in GraQle.
Activates automatically when users connect any local model backend
(Ollama, custom local endpoints, llama.cpp, vLLM, etc.).

Makes local reasoning quality approach cloud quality, improves over time
through fold-back learning from graq_predict.

Generic: works with ANY local backend, not just Ollama.
"""

__version__ = "0.1.0"

from graqle.plugins.gnie.detection import is_local_backend
from graqle.plugins.gnie.enricher import (
    CapabilityTier,
    GnieEnricher,
    NodeContext,
    detect_capability_tier,
)
from graqle.plugins.gnie.calibrator import AgentOutput, ConfidenceCalibrator
from graqle.plugins.gnie.state import GnieState
from graqle.plugins.gnie.models import ModelProfile, ModelSelector

__all__ = [
    "is_local_backend",
    "CapabilityTier",
    "GnieEnricher",
    "NodeContext",
    "detect_capability_tier",
    "AgentOutput",
    "ConfidenceCalibrator",
    "GnieState",
    "ModelProfile",
    "ModelSelector",
]
