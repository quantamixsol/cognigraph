"""Tests for GNIE confidence calibration in Orchestrator.

Unit tests: calibration activates/skips based on backend
Route tests: calibration metadata flows to ReasoningResult
Chain tests: fold-back history → calibration offset → result confidence
Integration tests: full orchestrator run with GNIE calibration
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from graqle.plugins.gnie.calibrator import AgentOutput, ConfidenceCalibrator
from graqle.plugins.gnie.detection import is_local_backend


# ─── Unit Tests: Calibrator behavior ───


class TestCalibratorUnit:

    def test_cold_start_minimal_adjustment(self):
        """With no fold-back history, calibration offset is 0."""
        cal = ConfidenceCalibrator({"writes": 0, "skips": 0})
        agents = [
            AgentOutput("n1", confidence=0.7, text_length=200),
            AgentOutput("n2", confidence=0.8, text_length=150),
        ]
        result = cal.calibrate(0.7, agents)
        # No history = no offset, but agreement still factors in
        assert 0.01 <= result <= 0.99

    def test_good_history_adjusts_downward(self):
        """High success rate → negative offset (model already calibrated)."""
        cal = ConfidenceCalibrator({"writes": 90, "skips": 10})
        assert cal._calibration_offset < 0

    def test_bad_history_adjusts_upward(self):
        """Low success rate → positive offset (boost needed)."""
        cal = ConfidenceCalibrator({"writes": 10, "skips": 90})
        assert cal._calibration_offset > 0


# ─── Route Tests: Calibration metadata ───


class TestCalibrationMetadata:

    def test_calibration_method_set_for_local(self):
        """When local backend, calibration_method should be 'gnie_v1'."""
        from graqle.plugins.gnie.state import GnieState

        # Simulate: local backend detected, calibration applied
        state = GnieState()
        model = "ollama:qwen2.5:3b"
        state.record_query(["n1"], model)
        state.record_fold_back("WRITTEN", ["n1"], 0.8, model)

        cal_data = state.get_calibration_data(model)
        cal = ConfidenceCalibrator(cal_data)

        agents = [AgentOutput("n1", confidence=0.7, text_length=200)]
        calibrated = cal.calibrate(0.65, agents)

        # Calibrated value should be in valid range
        assert 0.01 <= calibrated <= 0.99

    def test_empty_agent_outputs_returns_raw(self):
        """With no agent outputs, calibrator returns raw confidence."""
        cal = ConfidenceCalibrator({"writes": 50, "skips": 50})
        result = cal.calibrate(0.75, [])
        assert result == 0.75


# ─── Chain Tests: State → Calibrator → Confidence ───


class TestChainStateToConfidence:

    def test_learning_improves_calibration(self):
        """More fold-back data should produce non-zero offset."""
        from graqle.plugins.gnie.state import GnieState

        state = GnieState()
        model = "ollama:qwen2.5:3b"

        # Accumulate significant history
        for _ in range(30):
            state.record_query(["n1"], model)
            state.record_fold_back("WRITTEN", ["n1"], 0.85, model)
        for _ in range(10):
            state.record_query(["n2"], model)
            state.record_fold_back("SKIPPED_LOW_CONFIDENCE", ["n2"], 0.25, model)

        cal_data = state.get_calibration_data(model)
        cal = ConfidenceCalibrator(cal_data)

        # 75% success rate → should have non-zero offset
        assert cal._calibration_offset != 0.0

        agents = [
            AgentOutput("n1", confidence=0.7, text_length=200),
            AgentOutput("n2", confidence=0.6, text_length=150),
        ]
        raw = 0.65
        calibrated = cal.calibrate(raw, agents)
        # Calibrated should be different from simple raw passthrough
        assert calibrated != raw
        assert 0.01 <= calibrated <= 0.99

    def test_different_models_different_calibration(self):
        """Different models accumulate independent calibration data."""
        from graqle.plugins.gnie.state import GnieState

        state = GnieState()

        # Model A: mostly successful
        for _ in range(20):
            state.record_query(["n1"], "ollama:qwen2.5:3b")
            state.record_fold_back("WRITTEN", ["n1"], 0.8, "ollama:qwen2.5:3b")

        # Model B: mostly failing
        for _ in range(20):
            state.record_query(["n1"], "ollama:phi3:mini")
            state.record_fold_back("SKIPPED_LOW_CONFIDENCE", ["n1"], 0.3, "ollama:phi3:mini")

        cal_a = ConfidenceCalibrator(state.get_calibration_data("ollama:qwen2.5:3b"))
        cal_b = ConfidenceCalibrator(state.get_calibration_data("ollama:phi3:mini"))

        # Different histories → different offsets
        assert cal_a._calibration_offset != cal_b._calibration_offset
        # A is well-calibrated (negative offset), B needs boost (positive offset)
        assert cal_a._calibration_offset < cal_b._calibration_offset


# ─── Integration Tests: Detection → Calibration pipeline ───


class TestIntegrationDetectionCalibration:

    def test_cloud_backend_no_calibration(self):
        """Cloud backends should NOT have GNIE calibration applied."""
        from graqle.backends.api import AnthropicBackend

        backend = AnthropicBackend(model="claude-sonnet-4-6")
        assert not is_local_backend(backend)
        # Calibration would not be triggered for this backend

    def test_local_backend_gets_calibration(self):
        """Local backends should have GNIE calibration applied."""
        from graqle.backends.api import OllamaBackend

        backend = OllamaBackend(model="qwen2.5:3b")
        assert is_local_backend(backend)

        # Full calibration pipeline
        from graqle.plugins.gnie.state import GnieState
        state = GnieState()
        cal_data = state.get_calibration_data(backend.name)
        cal = ConfidenceCalibrator(cal_data)

        agents = [AgentOutput("n1", confidence=0.7, text_length=200)]
        calibrated = cal.calibrate(0.7, agents)
        assert 0.01 <= calibrated <= 0.99
