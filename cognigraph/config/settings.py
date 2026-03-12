"""CogniGraph configuration system — Pydantic settings + YAML loading."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """Model backend configuration."""

    backend: str = "local"
    model: str = "Qwen/Qwen2.5-0.5B-Instruct"
    quantization: str = "none"
    device: str = "auto"
    max_concurrent_adapters: int = 16
    api_key: str | None = None


class GraphConfig(BaseModel):
    """Graph connector configuration."""

    connector: str = "networkx"
    uri: str | None = None
    username: str | None = None
    password: str | None = None
    database: str | None = None


class ActivationConfig(BaseModel):
    """Subgraph activation configuration."""

    strategy: str = "pcst"
    max_nodes: int = 50
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    pcst_pruning: str = "strong"
    prize_scaling: float = 1.0
    cost_scaling: float = 1.0


class OrchestrationConfig(BaseModel):
    """Message passing orchestration configuration."""

    max_rounds: int = 5
    min_rounds: int = 2
    convergence_threshold: float = 0.95
    aggregation: str = "weighted_synthesis"
    async_mode: bool = False
    confidence_threshold: float = 0.8


class ObserverConfig(BaseModel):
    """MasterObserver configuration."""

    enabled: bool = False
    report_per_round: bool = False
    detect_conflicts: bool = True
    detect_patterns: bool = True
    detect_anomalies: bool = True
    use_llm_analysis: bool = False
    backend: str | None = None  # named model profile for observer


class CostConfig(BaseModel):
    """Cost control configuration."""

    budget_per_query: float = 0.01
    prefer_local: bool = True
    fallback_to_api: bool = True


class LoggingConfig(BaseModel):
    """Logging and tracing configuration."""

    level: str = "INFO"
    trace_messages: bool = True
    trace_dir: str = "./traces"


class NamedModelConfig(BaseModel):
    """Named model profile for node-to-model mapping."""

    backend: str
    model: str
    quantization: str = "none"
    api_key: str | None = None


class CogniGraphConfig(BaseModel):
    """Root configuration for a CogniGraph instance."""

    model: ModelConfig = Field(default_factory=ModelConfig)
    graph: GraphConfig = Field(default_factory=GraphConfig)
    activation: ActivationConfig = Field(default_factory=ActivationConfig)
    orchestration: OrchestrationConfig = Field(default_factory=OrchestrationConfig)
    observer: ObserverConfig = Field(default_factory=ObserverConfig)
    cost: CostConfig = Field(default_factory=CostConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    domain: str = "custom"
    models: dict[str, NamedModelConfig] = Field(default_factory=dict)
    node_models: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> CogniGraphConfig:
        """Load configuration from a YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        # Interpolate environment variables
        raw = _interpolate_env(raw)
        return cls.model_validate(raw)

    @classmethod
    def default(cls) -> CogniGraphConfig:
        """Return default configuration."""
        return cls()


def _interpolate_env(obj: Any) -> Any:
    """Recursively interpolate ${ENV_VAR} patterns in config values."""
    if isinstance(obj, str):
        if obj.startswith("${") and obj.endswith("}"):
            var_name = obj[2:-1]
            return os.environ.get(var_name, obj)
        return obj
    elif isinstance(obj, dict):
        return {k: _interpolate_env(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_interpolate_env(item) for item in obj]
    return obj
