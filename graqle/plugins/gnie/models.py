"""GNIE Supported Models Registry — local model profiles and auto-selection.

Complete reference of local models compatible with GNIE.
Auto-detects installed models and recommends the best one
for each task type based on capability profiles.

Generic: works with any local backend (Ollama, llama.cpp, vLLM, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from graqle.plugins.gnie.enricher import CapabilityTier


@dataclass(frozen=True)
class ModelProfile:
    """Profile for a supported local model."""
    name: str               # Model identifier (e.g. "qwen2.5:3b")
    family: str             # Model family (qwen, deepseek, gemma, llama, phi, mistral)
    params_b: float         # Billion parameters
    disk_gb: float          # Approximate disk size
    min_vram_gb: float      # Minimum VRAM to run entirely on GPU
    capability: CapabilityTier
    strengths: tuple[str, ...] = ()
    best_for: tuple[str, ...] = ()
    license: str = ""
    notes: str = ""


# Complete registry of supported models (April 2026)
MODEL_REGISTRY: Dict[str, ModelProfile] = {
    # === SMALL (<4B, runs on any GPU) ===
    "qwen2.5:0.5b": ModelProfile(
        name="qwen2.5:0.5b", family="qwen", params_b=0.5, disk_gb=0.4,
        min_vram_gb=1, capability=CapabilityTier.SMALL,
        strengths=("ultra-fast", "low memory"),
        best_for=("context", "lessons"),
        license="Apache 2.0",
        notes="Smoke tests and ultra-fast lookups only",
    ),
    "qwen2.5:3b": ModelProfile(
        name="qwen2.5:3b", family="qwen", params_b=3.1, disk_gb=1.9,
        min_vram_gb=3, capability=CapabilityTier.SMALL,
        strengths=("fast", "reliable", "structured output"),
        best_for=("context", "preflight", "lessons", "docs"),
        license="Apache 2.0",
    ),
    "gemma3:4b": ModelProfile(
        name="gemma3:4b", family="gemma", params_b=4.0, disk_gb=3.0,
        min_vram_gb=4, capability=CapabilityTier.SMALL,
        strengths=("multilingual", "128K context"),
        best_for=("context", "docs", "preflight"),
        license="Apache 2.0",
    ),
    "phi3:mini": ModelProfile(
        name="phi3:mini", family="phi", params_b=3.8, disk_gb=2.5,
        min_vram_gb=4, capability=CapabilityTier.SMALL,
        strengths=("reasoning per GB", "math"),
        best_for=("reason", "predict"),
        license="MIT",
    ),

    # === MEDIUM (4-13B, fits most GPUs) ===
    "gemma4:e4b": ModelProfile(
        name="gemma4:e4b", family="gemma", params_b=4.5, disk_gb=9.6,
        min_vram_gb=6, capability=CapabilityTier.MEDIUM,
        strengths=("PLE architecture", "function calling", "thinking mode"),
        best_for=("reason", "code", "predict"),
        license="Apache 2.0",
    ),
    "deepseek-r1:7b": ModelProfile(
        name="deepseek-r1:7b", family="deepseek", params_b=7.6, disk_gb=4.7,
        min_vram_gb=6, capability=CapabilityTier.MEDIUM,
        strengths=("chain-of-thought", "reasoning traces"),
        best_for=("reason", "govern", "predict"),
        license="MIT",
    ),
    "qwen3:7b": ModelProfile(
        name="qwen3:7b", family="qwen", params_b=7.0, disk_gb=4.5,
        min_vram_gb=6, capability=CapabilityTier.MEDIUM,
        strengths=("high HumanEval", "fast"),
        best_for=("code", "reason"),
        license="Apache 2.0",
    ),
    "llama3.3:8b": ModelProfile(
        name="llama3.3:8b", family="llama", params_b=8.0, disk_gb=5.0,
        min_vram_gb=6, capability=CapabilityTier.MEDIUM,
        strengths=("general purpose", "instruction following"),
        best_for=("reason", "code", "docs"),
        license="Llama 3.3 Community",
    ),
    "mistral:7b": ModelProfile(
        name="mistral:7b", family="mistral", params_b=7.0, disk_gb=4.1,
        min_vram_gb=6, capability=CapabilityTier.MEDIUM,
        strengths=("speed", "efficiency", "low memory"),
        best_for=("context", "code"),
        license="Apache 2.0",
    ),
    "qwen2.5-coder:7b": ModelProfile(
        name="qwen2.5-coder:7b", family="qwen", params_b=7.0, disk_gb=4.5,
        min_vram_gb=6, capability=CapabilityTier.MEDIUM,
        strengths=("code-specialized",),
        best_for=("code", "generate"),
        license="Apache 2.0",
    ),
    "codellama:7b": ModelProfile(
        name="codellama:7b", family="llama", params_b=7.0, disk_gb=3.8,
        min_vram_gb=5, capability=CapabilityTier.MEDIUM,
        strengths=("code generation", "code review"),
        best_for=("code", "generate"),
        license="Llama 2 Community",
    ),

    # === LARGE (12-14B, needs 8GB+ VRAM) ===
    "gemma3:12b": ModelProfile(
        name="gemma3:12b", family="gemma", params_b=12.0, disk_gb=6.6,
        min_vram_gb=8, capability=CapabilityTier.LARGE,
        strengths=("strong general", "128K context", "multilingual"),
        best_for=("reason", "govern", "docs"),
        license="Apache 2.0",
    ),
    "phi4:14b": ModelProfile(
        name="phi4:14b", family="phi", params_b=14.0, disk_gb=9.0,
        min_vram_gb=10, capability=CapabilityTier.LARGE,
        strengths=("best reasoning per GB", "MATH 80.4%", "logic"),
        best_for=("reason", "predict", "govern"),
        license="MIT",
    ),
    "qwen2.5-coder:14b": ModelProfile(
        name="qwen2.5-coder:14b", family="qwen", params_b=14.0, disk_gb=9.0,
        min_vram_gb=10, capability=CapabilityTier.LARGE,
        strengths=("code-specialized", "85% HumanEval"),
        best_for=("code", "generate"),
        license="Apache 2.0",
    ),

    # === FRONTIER (24B+, needs 16GB+ VRAM) ===
    "gemma4:26b": ModelProfile(
        name="gemma4:26b", family="gemma", params_b=26.0, disk_gb=16.0,
        min_vram_gb=16, capability=CapabilityTier.LARGE,
        strengths=("MoE architecture", "near-frontier quality"),
        best_for=("reason", "govern", "code", "predict"),
        license="Apache 2.0",
    ),
    "gemma4:31b": ModelProfile(
        name="gemma4:31b", family="gemma", params_b=31.0, disk_gb=20.0,
        min_vram_gb=20, capability=CapabilityTier.LARGE,
        strengths=("frontier quality", "256K context"),
        best_for=("reason", "govern", "code", "predict"),
        license="Apache 2.0",
    ),
    "deepseek-r1:32b": ModelProfile(
        name="deepseek-r1:32b", family="deepseek", params_b=32.0, disk_gb=20.0,
        min_vram_gb=20, capability=CapabilityTier.LARGE,
        strengths=("deep reasoning", "chain-of-thought"),
        best_for=("reason", "govern", "predict"),
        license="MIT",
    ),
    "llama3.3:70b": ModelProfile(
        name="llama3.3:70b", family="llama", params_b=70.0, disk_gb=40.0,
        min_vram_gb=40, capability=CapabilityTier.LARGE,
        strengths=("near-GPT-4 quality", "general purpose"),
        best_for=("reason", "govern", "code", "predict"),
        license="Llama 3.3 Community",
    ),
}


class ModelSelector:
    """Auto-selects the best model for each GraQle task type
    based on what's installed and the hardware available.
    """

    def __init__(self, available_models: List[str], vram_gb: float = 8.0):
        self.available = set(available_models)
        self.vram_gb = vram_gb

    def recommend(self, task_type: str) -> Optional[str]:
        """Recommend the best available model for a task type.
        Returns model name or None if nothing suitable is available.
        """
        candidates: list[tuple[str, ModelProfile]] = []
        for name, profile in MODEL_REGISTRY.items():
            if name in self.available and task_type in profile.best_for:
                if profile.min_vram_gb <= self.vram_gb:
                    candidates.append((name, profile))

        if not candidates:
            # Fallback: any available model that fits VRAM
            for name, profile in MODEL_REGISTRY.items():
                if name in self.available and profile.min_vram_gb <= self.vram_gb:
                    candidates.append((name, profile))

        if not candidates:
            return None

        # Rank: prefer larger capability, then lower disk size (efficiency)
        capability_order = {
            CapabilityTier.LARGE: 3,
            CapabilityTier.MEDIUM: 2,
            CapabilityTier.SMALL: 1,
        }
        candidates.sort(key=lambda x: (
            -capability_order.get(x[1].capability, 0),
            x[1].disk_gb,
        ))
        return candidates[0][0]

    def recommend_all(self) -> Dict[str, Optional[str]]:
        """Recommend best model for each GraQle task type."""
        tasks = [
            "reason", "predict", "impact", "govern", "code",
            "generate", "context", "preflight", "lessons", "docs",
        ]
        return {task: self.recommend(task) for task in tasks}
