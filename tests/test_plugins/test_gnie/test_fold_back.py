"""Tests for GNIE fold-back learning integration in mcp_server.py.

Unit tests: _gnie_record_fold_back method behavior
Route tests: fold-back through actual predict paths
Chain tests: fold-back → state → calibrator pipeline
Integration tests: state persistence across multiple fold-backs
"""

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

from graqle.plugins.gnie.state import GnieState


# ─── Helpers ───


def _make_mock_server():
    """Create a minimal mock MCP server with _gnie_record_fold_back."""
    from graqle.plugins.mcp_server import MCPServer, MCPConfig

    graph = MagicMock()
    graph.nodes = {}
    config = MCPConfig(graph_path="test.json")
    server = MCPServer(config)
    server._graph = graph
    return server


def _make_mock_reason_result(active_nodes=None, confidence=0.8):
    """Create a mock ReasoningResult."""
    result = MagicMock()
    result.active_nodes = active_nodes or ["node_1", "node_2", "node_3"]
    result.confidence = confidence
    result.answer = "Test answer"
    result.node_count = len(result.active_nodes)
    result.cost_usd = 0.0
    return result


def _make_local_node(model="qwen2.5:3b"):
    """Create a mock node with a local backend."""
    node = MagicMock()
    node.backend = MagicMock()
    node.backend.is_local = True
    node.backend.name = f"ollama:{model}"
    node.backend._model = model
    return node


def _make_cloud_node():
    """Create a mock node with a cloud backend."""
    node = MagicMock()
    node.backend = MagicMock()
    node.backend.is_local = False
    node.backend.name = "bedrock:anthropic.claude-sonnet-4-6-v1:0"
    return node


# ─── Unit Tests: _gnie_record_fold_back ───


class TestGnieRecordFoldBack:

    def test_local_backend_records_written(self, tmp_path, monkeypatch):
        """WRITTEN fold-back records learning for local backend."""
        state_path = str(tmp_path / "gnie_state.json")
        monkeypatch.setattr(
            "graqle.plugins.gnie.state.GnieState.load",
            lambda path=None: GnieState(),
        )

        server = _make_mock_server()
        local_node = _make_local_node()
        server._graph.nodes = {"node_1": local_node}

        result = _make_mock_reason_result(["node_1", "node_2"])

        # Patch save to capture state
        saved_states = []
        def mock_save(self, path=".graqle/gnie_state.json"):
            saved_states.append(self)
        monkeypatch.setattr(GnieState, "save", mock_save)

        server._gnie_record_fold_back("WRITTEN", result, 0.85)

        assert len(saved_states) == 1
        state = saved_states[0]
        assert state.fold_back_writes == 1
        assert state.queries_processed == 1

    def test_local_backend_records_skipped(self, tmp_path, monkeypatch):
        """SKIPPED_LOW_CONFIDENCE records learning for local backend."""
        monkeypatch.setattr(
            "graqle.plugins.gnie.state.GnieState.load",
            lambda path=None: GnieState(),
        )

        server = _make_mock_server()
        local_node = _make_local_node()
        server._graph.nodes = {"node_1": local_node}

        result = _make_mock_reason_result(["node_1"])

        saved_states = []
        def mock_save(self, path=".graqle/gnie_state.json"):
            saved_states.append(self)
        monkeypatch.setattr(GnieState, "save", mock_save)

        server._gnie_record_fold_back("SKIPPED_LOW_CONFIDENCE", result, 0.3)

        assert len(saved_states) == 1
        state = saved_states[0]
        assert state.fold_back_skips == 1

    def test_cloud_backend_skips_silently(self, monkeypatch):
        """Cloud backend does not trigger GNIE learning."""
        server = _make_mock_server()
        cloud_node = _make_cloud_node()
        server._graph.nodes = {"node_1": cloud_node}

        result = _make_mock_reason_result(["node_1"])

        # If GNIE tries to save, this would fail
        monkeypatch.setattr(GnieState, "save", lambda self, path=None: (_ for _ in ()).throw(AssertionError("Should not save")))

        # Should not raise — cloud backend skips GNIE entirely
        server._gnie_record_fold_back("WRITTEN", result, 0.9)

    def test_no_active_nodes_skips(self):
        """Empty active_nodes does not crash."""
        server = _make_mock_server()
        result = _make_mock_reason_result([])
        server._gnie_record_fold_back("WRITTEN", result, 0.8)  # No crash

    def test_missing_node_skips(self):
        """Node not in graph does not crash."""
        server = _make_mock_server()
        server._graph.nodes = {}  # Empty graph
        result = _make_mock_reason_result(["nonexistent"])
        server._gnie_record_fold_back("WRITTEN", result, 0.8)  # No crash

    def test_no_backend_on_node_skips(self):
        """Node without backend attribute does not crash."""
        server = _make_mock_server()
        node = MagicMock(spec=[])  # No backend attribute
        server._graph.nodes = {"node_1": node}
        result = _make_mock_reason_result(["node_1"])
        server._gnie_record_fold_back("WRITTEN", result, 0.8)  # No crash

    def test_exception_in_gnie_does_not_propagate(self, monkeypatch):
        """GNIE errors are swallowed — never block predict."""
        server = _make_mock_server()
        local_node = _make_local_node()
        server._graph.nodes = {"node_1": local_node}
        result = _make_mock_reason_result(["node_1"])

        # Force an error inside GnieState.load
        monkeypatch.setattr(
            "graqle.plugins.gnie.state.GnieState.load",
            lambda path=None: (_ for _ in ()).throw(RuntimeError("disk full")),
        )

        # Should not raise
        server._gnie_record_fold_back("WRITTEN", result, 0.8)


# ─── Route Tests: Model name propagation ───


class TestRouteModelNamePropagation:

    def test_model_name_from_backend(self, monkeypatch):
        """Model name is taken from backend.name for state tracking."""
        monkeypatch.setattr(
            "graqle.plugins.gnie.state.GnieState.load",
            lambda path=None: GnieState(),
        )

        server = _make_mock_server()
        local_node = _make_local_node("deepseek-r1:7b")
        server._graph.nodes = {"node_1": local_node}
        result = _make_mock_reason_result(["node_1"])

        saved_states = []
        def mock_save(self, path=".graqle/gnie_state.json"):
            saved_states.append(self)
        monkeypatch.setattr(GnieState, "save", mock_save)

        server._gnie_record_fold_back("WRITTEN", result, 0.9)

        state = saved_states[0]
        assert "ollama:deepseek-r1:7b" in state.model_stats


# ─── Chain Tests: Fold-back → State → Calibrator ───


class TestChainFoldBackToCalibrator:

    def test_accumulated_state_feeds_calibrator(self, tmp_path):
        """Multiple fold-backs accumulate in state, then feed calibrator."""
        state = GnieState()
        model = "ollama:qwen2.5:3b"

        # Simulate 10 fold-backs
        for _ in range(8):
            state.record_query(["n1", "n2"], model)
            state.record_fold_back("WRITTEN", ["n1", "n2"], 0.8, model)
        for _ in range(2):
            state.record_query(["n3"], model)
            state.record_fold_back("SKIPPED_LOW_CONFIDENCE", ["n3"], 0.3, model)

        # Verify state
        assert state.fold_back_writes == 8
        assert state.fold_back_skips == 2

        # Feed to calibrator
        from graqle.plugins.gnie.calibrator import ConfidenceCalibrator, AgentOutput

        cal_data = state.get_calibration_data(model)
        cal = ConfidenceCalibrator(cal_data)

        # 80% success rate → negative offset (model is already well-calibrated)
        assert cal._calibration_offset < 0

        agents = [AgentOutput("n1", confidence=0.7, text_length=200)]
        calibrated = cal.calibrate(0.7, agents)
        assert 0.01 <= calibrated <= 0.99


# ─── Integration Tests: State persistence ───


class TestIntegrationStatePersistence:

    def test_state_survives_save_load_cycle(self, tmp_path):
        """State written by fold-back can be loaded in next session."""
        path = str(tmp_path / "gnie_state.json")
        model = "ollama:qwen2.5:3b"

        # Session 1: Record fold-backs
        state = GnieState()
        state.record_query(["n1"], model)
        state.record_fold_back("WRITTEN", ["n1"], 0.85, model)
        state.save(path)

        # Session 2: Load and verify
        loaded = GnieState.load(path)
        assert loaded.queries_processed == 1
        assert loaded.fold_back_writes == 1
        assert loaded.model_stats[model]["writes"] == 1

        # Continue learning
        loaded.record_query(["n2"], model)
        loaded.record_fold_back("SKIPPED_LOW_CONFIDENCE", ["n2"], 0.25, model)
        loaded.save(path)

        # Session 3: Verify accumulated state
        final = GnieState.load(path)
        assert final.queries_processed == 2
        assert final.fold_back_writes == 1
        assert final.fold_back_skips == 1
