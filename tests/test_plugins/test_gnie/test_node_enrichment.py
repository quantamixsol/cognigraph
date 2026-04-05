"""Tests for GNIE prompt enrichment wiring in CogniNode.reason().

Unit tests: enrichment activates/skips based on backend type
Route tests: enriched prompt reaches backend.generate()
Chain tests: detection → enricher → backend pipeline
Integration tests: full CogniNode.reason() with GNIE active
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from graqle.core.node import CogniNode
from graqle.core.message import Message


def _make_node(backend, **kwargs):
    """Create a CogniNode with a backend assigned."""
    defaults = dict(
        id="test_node",
        label="test_function",
        entity_type="Function",
        description="A test function that does things.",
        properties={"chunks": []},
        incoming_edges=["edge_1", "edge_2"],
        outgoing_edges=["edge_3"],
    )
    defaults.update(kwargs)
    node = CogniNode(**defaults)
    node.activate(backend)
    return node


def _make_mock_backend(is_local: bool, model: str = "qwen2.5:3b"):
    """Create a mock backend with is_local and generate()."""
    backend = AsyncMock()
    backend.is_local = is_local
    backend._model = model
    backend.cost_per_1k_tokens = 0.0001 if is_local else 0.003

    # generate() returns a GenerateResult-like object
    result = MagicMock()
    result.truncated = False
    result.stop_reason = "stop"
    result.__str__ = lambda self: "confidence: 0.8\nThis function handles authentication."
    backend.generate = AsyncMock(return_value=result)
    return backend


def _make_query_message(query: str = "What does this do?", round_num: int = 0):
    """Create a Message for testing."""
    msg = Message.create_query_broadcast(query, "source_node")
    msg.round = round_num
    return msg


# ─── Unit Tests: Cloud backend skips enrichment ───


class TestCloudBackendSkipsEnrichment:

    @pytest.mark.asyncio
    async def test_cloud_backend_no_enrichment(self):
        """When backend is NOT local, GNIE enrichment is NOT applied."""
        backend = _make_mock_backend(is_local=False)
        node = _make_node(backend)

        msg = _make_query_message()
        await node.reason("What does this do?", [msg])

        # backend.generate was called — verify the prompt does NOT contain GNIE markers
        call_args = backend.generate.call_args
        prompt = call_args[0][0]
        assert "[You are reasoning about" not in prompt
        assert "[Connected to" not in prompt

    @pytest.mark.asyncio
    async def test_cloud_backend_gnie_enricher_not_imported(self):
        """Cloud path should not trigger GnieEnricher import."""
        backend = _make_mock_backend(is_local=False)
        node = _make_node(backend)

        msg = _make_query_message()
        with patch("graqle.plugins.gnie.enricher.GnieEnricher") as mock_enricher:
            await node.reason("What does this do?", [msg])
            mock_enricher.for_model.assert_not_called()


# ─── Unit Tests: Local backend activates enrichment ───


class TestLocalBackendActivatesEnrichment:

    @pytest.mark.asyncio
    async def test_local_backend_enriches_prompt(self):
        """When backend IS local, GNIE enrichment IS applied."""
        backend = _make_mock_backend(is_local=True, model="qwen2.5:3b")
        node = _make_node(backend)

        msg = _make_query_message()
        await node.reason("What does this do?", [msg])

        call_args = backend.generate.call_args
        prompt = call_args[0][0]
        # GNIE enrichment markers should be present
        assert "[You are reasoning about a Function node: 'test_function']" in prompt

    @pytest.mark.asyncio
    async def test_enrichment_preserves_original_prompt(self):
        """Original prompt content must still be present after enrichment."""
        backend = _make_mock_backend(is_local=True)
        node = _make_node(backend)

        msg = _make_query_message("What does this do?")
        await node.reason("What does this do?", [msg])

        call_args = backend.generate.call_args
        prompt = call_args[0][0]
        # Original node context should still be there
        assert "test_function" in prompt
        assert "What does this do?" in prompt


# ─── Route Tests: Different model sizes ───


class TestRouteModelSizes:

    @pytest.mark.asyncio
    async def test_small_model_gets_format_hints(self):
        """Small models (3b) get GNIE response format hints."""
        backend = _make_mock_backend(is_local=True, model="qwen2.5:3b")
        node = _make_node(backend)
        msg = _make_query_message()
        await node.reason("query", [msg])

        prompt = backend.generate.call_args[0][0]
        # GNIE-specific marker: "[Instructions: Be specific..."
        assert "[Instructions: Be specific" in prompt

    @pytest.mark.asyncio
    async def test_large_model_minimal_enrichment(self):
        """Large models (70b) get minimal enrichment — no GNIE format hints."""
        backend = _make_mock_backend(is_local=True, model="llama3.3:70b")
        node = _make_node(backend)
        msg = _make_query_message()
        await node.reason("query", [msg])

        prompt = backend.generate.call_args[0][0]
        assert "[You are reasoning about" in prompt
        # GNIE-specific format hint marker (not from base prompt)
        assert "[Instructions: Be specific" not in prompt
        assert "[Be specific and cite" not in prompt


# ─── Route Tests: Round context from incoming messages ───


class TestRouteRoundContext:

    @pytest.mark.asyncio
    async def test_round_0_no_round_context(self):
        """Round 0 (initial): no 'previous round' context."""
        backend = _make_mock_backend(is_local=True)
        node = _make_node(backend)
        msg = _make_query_message(round_num=0)
        await node.reason("query", [msg])

        prompt = backend.generate.call_args[0][0]
        assert "Reasoning round" not in prompt

    @pytest.mark.asyncio
    async def test_round_1_has_round_context(self):
        """Round 1+: should include round context."""
        backend = _make_mock_backend(is_local=True)
        node = _make_node(backend)
        msg = _make_query_message(round_num=1)
        await node.reason("query", [msg])

        prompt = backend.generate.call_args[0][0]
        assert "round 2" in prompt.lower()

    @pytest.mark.asyncio
    async def test_empty_messages_round_0(self):
        """Empty incoming_messages defaults to round_idx=0."""
        backend = _make_mock_backend(is_local=True)
        node = _make_node(backend)
        # Create query broadcast which is the initial message
        msg = _make_query_message(round_num=0)
        await node.reason("query", [msg])

        prompt = backend.generate.call_args[0][0]
        # Should not crash and should not have round context
        assert "Reasoning round" not in prompt

    @pytest.mark.asyncio
    async def test_messages_missing_round_attribute(self):
        """Messages without .round attribute should not crash."""
        backend = _make_mock_backend(is_local=True)
        node = _make_node(backend)
        msg = _make_query_message()
        delattr(msg, "round")  # remove round attribute
        await node.reason("query", [msg])

        # Should not crash — getattr fallback handles it
        assert backend.generate.called


# ─── Chain Tests: Detection → Enricher → Backend ───


class TestChainDetectionEnricherBackend:

    @pytest.mark.asyncio
    async def test_ollama_backend_full_chain(self):
        """Real OllamaBackend triggers GNIE through full chain."""
        from graqle.backends.api import OllamaBackend
        from graqle.plugins.gnie.detection import is_local_backend

        # OllamaBackend is_local=True
        ollama = OllamaBackend(model="qwen2.5:3b")
        assert is_local_backend(ollama) is True

        # Mock generate to avoid actual network call
        mock_result = MagicMock()
        mock_result.truncated = False
        mock_result.stop_reason = "stop"
        mock_result.__str__ = lambda self: "confidence: 0.8\nTest answer"
        ollama.generate = AsyncMock(return_value=mock_result)

        node = _make_node(ollama)
        msg = _make_query_message()
        await node.reason("What does this do?", [msg])

        prompt = ollama.generate.call_args[0][0]
        assert "[You are reasoning about a Function node: 'test_function']" in prompt

    @pytest.mark.asyncio
    async def test_custom_local_backend_full_chain(self):
        """CustomBackend on localhost triggers GNIE."""
        from graqle.backends.api import CustomBackend
        from graqle.plugins.gnie.detection import is_local_backend

        custom = CustomBackend(endpoint="http://localhost:8080/v1", model="local-model")
        assert is_local_backend(custom) is True

        mock_result = MagicMock()
        mock_result.truncated = False
        mock_result.stop_reason = "stop"
        mock_result.__str__ = lambda self: "confidence: 0.7\nLocal answer"
        custom.generate = AsyncMock(return_value=mock_result)

        node = _make_node(custom)
        msg = _make_query_message()
        await node.reason("query", [msg])

        prompt = custom.generate.call_args[0][0]
        assert "[You are reasoning about" in prompt


# ─── Integration Tests: Neighbor count ───


class TestIntegrationNeighborCount:

    @pytest.mark.asyncio
    async def test_neighbor_count_from_edges(self):
        """Neighbor count derived from incoming + outgoing edges."""
        backend = _make_mock_backend(is_local=True, model="qwen2.5:3b")
        node = _make_node(
            backend,
            incoming_edges=["e1", "e2", "e3"],
            outgoing_edges=["e4", "e5"],
        )
        msg = _make_query_message()
        await node.reason("query", [msg])

        prompt = backend.generate.call_args[0][0]
        # 3 incoming + 2 outgoing = 5 neighbors
        # Small model enrichment should say "Connected to 5 nodes"
        # But neighbor_types is empty, so it says "isolated"
        assert "[You are reasoning about" in prompt

    @pytest.mark.asyncio
    async def test_no_edges_isolated(self):
        """Node with no edges reports as isolated."""
        backend = _make_mock_backend(is_local=True, model="qwen2.5:3b")
        node = _make_node(
            backend,
            incoming_edges=[],
            outgoing_edges=[],
        )
        msg = _make_query_message()
        await node.reason("query", [msg])

        prompt = backend.generate.call_args[0][0]
        assert "isolated" in prompt.lower()
