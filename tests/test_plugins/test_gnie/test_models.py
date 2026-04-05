"""Tests for GNIE Model Registry and Selector.

Unit tests: model registry completeness, profile validation
Route tests: model selection per task type
Chain tests: selector + enricher tier consistency
Integration tests: auto-selection with varying available models
"""

import pytest

from graqle.plugins.gnie.enricher import CapabilityTier
from graqle.plugins.gnie.models import MODEL_REGISTRY, ModelProfile, ModelSelector


# ─── Unit Tests: Registry completeness ───


class TestModelRegistry:

    def test_registry_has_17_plus_models(self):
        assert len(MODEL_REGISTRY) >= 17

    def test_all_entries_are_model_profiles(self):
        for name, profile in MODEL_REGISTRY.items():
            assert isinstance(profile, ModelProfile)
            assert profile.name == name

    def test_all_profiles_have_required_fields(self):
        for name, profile in MODEL_REGISTRY.items():
            assert profile.family, f"{name} missing family"
            assert profile.params_b > 0, f"{name} invalid params_b"
            assert profile.disk_gb > 0, f"{name} invalid disk_gb"
            assert profile.min_vram_gb > 0, f"{name} invalid min_vram_gb"
            assert isinstance(profile.capability, CapabilityTier), f"{name} invalid capability"
            assert len(profile.best_for) > 0, f"{name} missing best_for"

    def test_capability_tiers_distributed(self):
        """Registry should have models across all capability tiers."""
        tiers = {p.capability for p in MODEL_REGISTRY.values()}
        assert CapabilityTier.SMALL in tiers
        assert CapabilityTier.MEDIUM in tiers
        assert CapabilityTier.LARGE in tiers

    def test_known_models_present(self):
        """Key models from the spec must be in registry."""
        assert "qwen2.5:3b" in MODEL_REGISTRY
        assert "deepseek-r1:7b" in MODEL_REGISTRY
        assert "gemma4:e4b" in MODEL_REGISTRY
        assert "llama3.3:8b" in MODEL_REGISTRY
        assert "phi4:14b" in MODEL_REGISTRY

    def test_profiles_are_frozen(self):
        """ModelProfile should be immutable."""
        profile = MODEL_REGISTRY["qwen2.5:3b"]
        with pytest.raises(AttributeError):
            profile.name = "modified"


# ─── Route Tests: Model selection per task ───


class TestModelSelection:

    @pytest.fixture
    def selector_8gb(self):
        """Selector with typical 8GB VRAM, common models available."""
        return ModelSelector(
            available_models=["qwen2.5:3b", "deepseek-r1:7b", "llama3.3:8b"],
            vram_gb=8.0,
        )

    def test_recommend_reason_task(self, selector_8gb):
        model = selector_8gb.recommend("reason")
        assert model is not None
        assert model in MODEL_REGISTRY

    def test_recommend_code_task(self, selector_8gb):
        model = selector_8gb.recommend("code")
        assert model is not None

    def test_recommend_nonexistent_task_fallback(self, selector_8gb):
        """Unknown task falls back to any available model."""
        model = selector_8gb.recommend("nonexistent_task")
        assert model is not None  # Should fallback

    def test_no_models_available(self):
        selector = ModelSelector(available_models=[], vram_gb=8.0)
        assert selector.recommend("reason") is None

    def test_vram_filtering(self):
        """Models requiring more VRAM than available should be excluded."""
        selector = ModelSelector(
            available_models=["qwen2.5:3b", "phi4:14b"],
            vram_gb=4.0,
        )
        model = selector.recommend("reason")
        # phi4:14b needs 10GB, qwen2.5:3b needs 3GB
        assert model == "qwen2.5:3b"

    def test_prefers_larger_capability(self):
        """Should prefer larger capability models when available and fit."""
        selector = ModelSelector(
            available_models=["qwen2.5:3b", "deepseek-r1:7b", "gemma3:12b"],
            vram_gb=16.0,
        )
        model = selector.recommend("reason")
        # gemma3:12b is LARGE tier, should be preferred
        profile = MODEL_REGISTRY[model]
        assert profile.capability == CapabilityTier.LARGE


# ─── Route Tests: recommend_all ───


class TestRecommendAll:

    def test_recommend_all_returns_all_tasks(self):
        selector = ModelSelector(
            available_models=["qwen2.5:3b", "deepseek-r1:7b"],
            vram_gb=8.0,
        )
        recs = selector.recommend_all()
        expected_tasks = [
            "reason", "predict", "impact", "govern", "code",
            "generate", "context", "preflight", "lessons", "docs",
        ]
        for task in expected_tasks:
            assert task in recs

    def test_all_recommendations_are_available(self):
        available = ["qwen2.5:3b", "llama3.3:8b"]
        selector = ModelSelector(available_models=available, vram_gb=8.0)
        recs = selector.recommend_all()
        for task, model in recs.items():
            if model is not None:
                assert model in available, f"Task {task} recommended unavailable model {model}"


# ─── Chain Tests: Selector → Enricher tier consistency ───


class TestChainSelectorEnricher:
    """ModelSelector capabilities should match enricher tier detection."""

    def test_registry_tier_matches_enricher_detection(self):
        from graqle.plugins.gnie.enricher import detect_capability_tier

        for name, profile in MODEL_REGISTRY.items():
            detected_tier = detect_capability_tier(name)
            # Small models detected as small or medium is acceptable
            # But large should never be detected as small
            if profile.capability == CapabilityTier.LARGE:
                assert detected_tier in (CapabilityTier.MEDIUM, CapabilityTier.LARGE), \
                    f"{name}: registry says LARGE but enricher detects {detected_tier}"


# ─── Integration Tests: Full auto-selection pipeline ───


class TestIntegrationAutoSelection:

    def test_select_then_enrich(self):
        """Full pipeline: select model → create enricher → enrich prompt."""
        from graqle.plugins.gnie.enricher import GnieEnricher, NodeContext

        selector = ModelSelector(
            available_models=["qwen2.5:3b", "deepseek-r1:7b"],
            vram_gb=8.0,
        )
        recommended = selector.recommend("reason")
        assert recommended is not None

        enricher = GnieEnricher.for_model(recommended)
        node = NodeContext(
            node_id="test", node_type="Function", label="test_fn",
            description="A test function", neighbor_count=3,
            neighbor_types={"Class": 2, "Function": 1},
        )
        result = enricher.enrich("Base prompt", node, "What does this do?")
        assert "Base prompt" in result
        assert len(result) > len("Base prompt")
