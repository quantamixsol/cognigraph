"""Tests for GNIE model integration in graq init --backend ollama.

Unit tests: model registry entries match init command options
Route tests: init produces valid graqle.yaml for ollama
Chain tests: init → detection → enricher pipeline
"""

import pytest

from graqle.plugins.gnie.models import MODEL_REGISTRY


# ─── Unit Tests: Init models align with GNIE registry ───


class TestInitModelsAlignWithGNIE:
    """Init command models should be in the GNIE model registry."""

    def test_gnie_models_in_registry(self):
        """Key GNIE models should exist in MODEL_REGISTRY."""
        key_models = [
            "qwen2.5:3b", "deepseek-r1:7b", "gemma4:e4b",
            "llama3.3:8b", "phi4:14b",
        ]
        for model in key_models:
            assert model in MODEL_REGISTRY, f"{model} missing from GNIE registry"

    def test_init_ollama_has_gnie_enhanced_name(self):
        """Ollama backend should mention GNIE in its name."""
        from graqle.cli.commands.init import BACKENDS
        assert "GNIE" in BACKENDS["ollama"]["name"]

    def test_init_ollama_has_multiple_models(self):
        """Init command should offer multiple ollama models."""
        from graqle.cli.commands.init import BACKENDS
        models = BACKENDS["ollama"]["models"]
        assert len(models) >= 5

    def test_init_ollama_default_model_exists(self):
        """Default ollama model should be marked as default."""
        from graqle.cli.commands.init import BACKENDS
        models = BACKENDS["ollama"]["models"]
        defaults = [m for m in models if m[2] is True]
        assert len(defaults) == 1  # Exactly one default


# ─── Route Tests: graqle.yaml generation ───


class TestRouteGraqleYamlGeneration:

    def test_build_graqle_yaml_ollama(self):
        """_build_graqle_yaml produces valid config for ollama."""
        from graqle.cli.commands.init import _build_graqle_yaml
        yaml_str = _build_graqle_yaml(
            backend="ollama",
            model="qwen2.5:3b",
            api_key_ref="",
        )
        assert "ollama" in yaml_str
        assert "qwen2.5:3b" in yaml_str
        # Should NOT contain api_key for local backend
        assert "api_key" not in yaml_str


# ─── Chain Tests: Init → Detection → Enricher ───


class TestChainInitDetectionEnricher:

    def test_ollama_model_enricher_chain(self):
        """Models from init should create valid enrichers."""
        from graqle.plugins.gnie.enricher import GnieEnricher, CapabilityTier

        init_models = ["qwen2.5:3b", "deepseek-r1:7b", "phi4:14b"]
        for model in init_models:
            enricher = GnieEnricher.for_model(model)
            assert enricher.tier in (
                CapabilityTier.SMALL, CapabilityTier.MEDIUM, CapabilityTier.LARGE,
            ), f"Invalid tier for model {model}"

    def test_model_selector_recommends_from_init_models(self):
        """ModelSelector should work with models offered by init."""
        from graqle.plugins.gnie.models import ModelSelector

        init_models = ["qwen2.5:3b", "deepseek-r1:7b", "llama3.3:8b"]
        selector = ModelSelector(available_models=init_models, vram_gb=8.0)

        for task in ["reason", "code", "context"]:
            rec = selector.recommend(task)
            assert rec is not None, f"No recommendation for task '{task}'"
            assert rec in init_models, f"Recommended '{rec}' not in init models"
