"""Tests for GNIE local backend detection — 3-layer protocol.

Unit tests: each detection layer independently
Route tests: detection through actual backend classes
Chain tests: detection -> enricher activation chain
Integration tests: detection in full pipeline context
"""

import pytest
from unittest.mock import MagicMock, PropertyMock

from graqle.plugins.gnie.detection import is_local_backend, _LOCAL_COST_THRESHOLD


# ─── Unit Tests: Layer 1 — Explicit is_local property ───


class TestLayer1ExplicitProperty:
    """Layer 1: is_local property is authoritative."""

    def test_is_local_true(self):
        backend = MagicMock()
        backend.is_local = True
        assert is_local_backend(backend) is True

    def test_is_local_false(self):
        backend = MagicMock()
        backend.is_local = False
        assert is_local_backend(backend) is False

    def test_is_local_overrides_cost(self):
        """is_local=False should override even zero cost."""
        backend = MagicMock()
        backend.is_local = False
        backend.cost_per_1k_tokens = 0.0
        assert is_local_backend(backend) is False

    def test_is_local_overrides_host(self):
        """is_local=False should override localhost endpoint."""
        backend = MagicMock()
        backend.is_local = False
        backend._host = "http://localhost:11434"
        assert is_local_backend(backend) is False


# ─── Unit Tests: Layer 2 — Cost heuristic ───


class TestLayer2CostHeuristic:
    """Layer 2: cost_per_1k_tokens < threshold implies local."""

    def test_zero_cost_is_local(self):
        backend = MagicMock(spec=[])  # no is_local attribute
        backend.cost_per_1k_tokens = 0.0
        assert is_local_backend(backend) is True

    def test_very_low_cost_is_local(self):
        backend = MagicMock(spec=[])
        backend.cost_per_1k_tokens = 0.0001
        assert is_local_backend(backend) is True

    def test_above_threshold_not_local(self):
        backend = MagicMock(spec=[])
        backend.cost_per_1k_tokens = 0.001  # Bedrock Haiku range
        assert is_local_backend(backend) is False

    def test_no_cost_attribute_falls_through(self):
        """If no cost_per_1k_tokens and no is_local, fall to layer 3."""
        backend = MagicMock(spec=[])
        # Remove all attributes — should return False (no layers match)
        assert is_local_backend(backend) is False

    def test_threshold_boundary(self):
        """Exactly at threshold should NOT be local."""
        backend = MagicMock(spec=[])
        backend.cost_per_1k_tokens = _LOCAL_COST_THRESHOLD
        assert is_local_backend(backend) is False


# ─── Unit Tests: Layer 3 — Endpoint hostname inspection ───


class TestLayer3EndpointHeuristic:
    """Layer 3: localhost-like hostnames imply local."""

    @pytest.mark.parametrize("host", [
        "http://localhost:11434",
        "http://127.0.0.1:8080",
        "http://[::1]:5000",
    ])
    def test_local_hosts(self, host):
        backend = MagicMock(spec=[])
        backend._host = host
        assert is_local_backend(backend) is True

    @pytest.mark.parametrize("host", [
        "https://api.openai.com/v1",
        "https://bedrock-runtime.us-east-1.amazonaws.com",
        "http://gpu-server.internal:8080",
    ])
    def test_remote_hosts(self, host):
        backend = MagicMock(spec=[])
        backend._host = host
        assert is_local_backend(backend) is False

    def test_endpoint_attribute(self):
        """Detection checks multiple attribute names."""
        backend = MagicMock(spec=[])
        backend._endpoint = "http://localhost:8080/v1"
        assert is_local_backend(backend) is True

    def test_base_url_attribute(self):
        backend = MagicMock(spec=[])
        backend.base_url = "http://127.0.0.1:11434"
        assert is_local_backend(backend) is True

    def test_0000_not_local(self):
        """0.0.0.0 is wildcard bind, NOT loopback — security critical."""
        backend = MagicMock(spec=[])
        backend._host = "http://0.0.0.0:3000"
        assert is_local_backend(backend) is False


# ─── Edge Case Tests: Non-standard inputs ───


class TestEdgeCases:
    """GraQle review flagged edge cases."""

    def test_non_numeric_cost(self):
        """Non-numeric cost should not crash or misclassify."""
        backend = MagicMock(spec=[])
        backend.cost_per_1k_tokens = "free"
        assert is_local_backend(backend) is False

    def test_negative_cost(self):
        """Negative cost sentinel should not classify as local."""
        backend = MagicMock(spec=[])
        backend.cost_per_1k_tokens = -1
        assert is_local_backend(backend) is False

    def test_none_cost(self):
        backend = MagicMock(spec=[])
        backend.cost_per_1k_tokens = None
        assert is_local_backend(backend) is False

    def test_malformed_url(self):
        """Malformed URL should not crash."""
        backend = MagicMock(spec=[])
        backend._host = "not-a-url-at-all"
        assert is_local_backend(backend) is False

    def test_empty_string_url(self):
        backend = MagicMock(spec=[])
        backend._host = ""
        assert is_local_backend(backend) is False

    def test_backend_with_no_attributes(self):
        """Completely bare object should return False."""
        backend = object()
        assert is_local_backend(backend) is False


# ─── Route Tests: Actual backend classes ───


class TestRouteActualBackends:
    """Detection works correctly with real SDK backend classes."""

    def test_ollama_backend_is_local(self):
        from graqle.backends.api import OllamaBackend
        backend = OllamaBackend(model="qwen2.5:3b")
        assert is_local_backend(backend) is True

    def test_custom_backend_localhost_is_local(self):
        from graqle.backends.api import CustomBackend
        backend = CustomBackend(endpoint="http://localhost:8080/v1")
        assert is_local_backend(backend) is True

    def test_custom_backend_remote_not_local(self):
        from graqle.backends.api import CustomBackend
        backend = CustomBackend(endpoint="https://api.openai.com/v1")
        assert is_local_backend(backend) is False

    def test_anthropic_backend_not_local(self):
        from graqle.backends.api import AnthropicBackend
        backend = AnthropicBackend(model="claude-sonnet-4-6")
        assert is_local_backend(backend) is False

    def test_openai_backend_not_local(self):
        from graqle.backends.api import OpenAIBackend
        backend = OpenAIBackend(model="gpt-4o-mini")
        assert is_local_backend(backend) is False

    def test_bedrock_backend_not_local(self):
        from graqle.backends.api import BedrockBackend
        backend = BedrockBackend(model="anthropic.claude-sonnet-4-6-v1:0")
        assert is_local_backend(backend) is False


# ─── Chain Tests: Detection → Enricher activation ───


class TestChainDetectionToEnricher:
    """Detection result correctly gates GNIE enricher activation."""

    def test_local_backend_activates_enricher(self):
        from graqle.backends.api import OllamaBackend
        from graqle.plugins.gnie.enricher import GnieEnricher, NodeContext

        backend = OllamaBackend(model="qwen2.5:3b")
        assert is_local_backend(backend) is True

        # Enricher should be creatable from model name
        enricher = GnieEnricher.for_model(backend._model)
        ctx = NodeContext(
            node_id="test_node",
            node_type="Function",
            label="test_function",
            description="A test function",
            neighbor_count=3,
            neighbor_types={"Class": 2, "Function": 1},
        )
        enriched = enricher.enrich("Original prompt", ctx, "What does this do?")
        assert "Function" in enriched
        assert "test_function" in enriched
        assert "Original prompt" in enriched

    def test_cloud_backend_skips_enricher(self):
        from graqle.backends.api import AnthropicBackend

        backend = AnthropicBackend(model="claude-sonnet-4-6")
        assert is_local_backend(backend) is False
        # Enricher should NOT be activated — no enrichment needed


# ─── Integration Tests: BaseBackend.is_local contract ───


class TestIntegrationBaseBackendContract:
    """BaseBackend.is_local property contract across all backends."""

    def test_base_backend_default_is_false(self):
        from graqle.backends.base import BaseBackend
        # All backends that don't override should return False
        # We can't instantiate ABC directly, but we verify through subclasses

    def test_all_cloud_backends_return_false(self):
        """Every cloud backend should have is_local == False."""
        from graqle.backends.api import (
            AnthropicBackend, OpenAIBackend, BedrockBackend,
        )
        assert AnthropicBackend(model="claude-sonnet-4-6").is_local is False
        assert OpenAIBackend(model="gpt-4o").is_local is False
        assert BedrockBackend(model="anthropic.claude-sonnet-4-6-v1:0").is_local is False

    def test_ollama_backend_returns_true(self):
        from graqle.backends.api import OllamaBackend
        assert OllamaBackend(model="qwen2.5:3b").is_local is True

    def test_custom_backend_localhost(self):
        from graqle.backends.api import CustomBackend
        assert CustomBackend(endpoint="http://localhost:8080/v1").is_local is True
        assert CustomBackend(endpoint="http://127.0.0.1:11434").is_local is True

    def test_custom_backend_remote(self):
        from graqle.backends.api import CustomBackend
        assert CustomBackend(endpoint="https://api.openai.com/v1").is_local is False
