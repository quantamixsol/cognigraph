"""Tests for GNIE Confidence Calibrator.

Unit tests: calibration logic, offset computation, edge cases
Route tests: calibration with different fold-back histories
Chain tests: calibrator + state integration
Integration tests: calibration output ranges
"""

import pytest

from graqle.plugins.gnie.calibrator import AgentOutput, ConfidenceCalibrator


# ─── Unit Tests: Calibration offset computation ───


class TestCalibrationOffset:

    def test_cold_start_no_offset(self):
        """Less than 5 samples: no adjustment."""
        cal = ConfidenceCalibrator({"writes": 2, "skips": 1})
        assert cal._calibration_offset == 0.0

    def test_good_history_negative_offset(self):
        """High success rate: offset is negative (model already calibrated)."""
        cal = ConfidenceCalibrator({"writes": 80, "skips": 20})
        assert cal._calibration_offset < 0

    def test_bad_history_positive_offset(self):
        """Low success rate: offset is positive (boost confidence)."""
        cal = ConfidenceCalibrator({"writes": 10, "skips": 90})
        assert cal._calibration_offset > 0

    def test_balanced_history_small_offset(self):
        """50/50: offset near zero."""
        cal = ConfidenceCalibrator({"writes": 50, "skips": 50})
        assert abs(cal._calibration_offset) < 0.01

    def test_offset_range(self):
        """Offset should be bounded between -0.1 and +0.1."""
        # Best case: all writes
        cal = ConfidenceCalibrator({"writes": 100, "skips": 0})
        assert -0.1 <= cal._calibration_offset <= 0.1
        # Worst case: all skips
        cal = ConfidenceCalibrator({"writes": 0, "skips": 100})
        assert -0.1 <= cal._calibration_offset <= 0.1


# ─── Unit Tests: Calibration logic ───


class TestCalibrationLogic:

    def test_empty_agents_returns_raw(self):
        cal = ConfidenceCalibrator()
        assert cal.calibrate(0.7, []) == 0.7

    def test_all_agents_agree_boosts_confidence(self):
        """When all agents produce substantive output, confidence boosted."""
        agents = [
            AgentOutput("n1", confidence=0.8, text_length=200),
            AgentOutput("n2", confidence=0.7, text_length=150),
            AgentOutput("n3", confidence=0.9, text_length=180),
        ]
        cal = ConfidenceCalibrator()
        result = cal.calibrate(0.5, agents)
        # Agreement ratio = 3/3 = 1.0
        # Raw contribution = 0.5 * 0.5 = 0.25
        # Agreement contribution = 1.0 * 0.4 = 0.4
        # Total ~0.65 minus small spread penalty
        assert result > 0.5  # Boosted

    def test_no_agents_substantive_lowers_confidence(self):
        """When no agents produce substantive output, confidence lowered."""
        agents = [
            AgentOutput("n1", confidence=0.1, text_length=10),
            AgentOutput("n2", confidence=0.2, text_length=20),
        ]
        cal = ConfidenceCalibrator()
        result = cal.calibrate(0.8, agents)
        # Agreement ratio = 0/2 = 0.0
        # Raw contribution = 0.8 * 0.5 = 0.4
        # Agreement contribution = 0.0 * 0.4 = 0.0
        assert result < 0.8  # Lowered

    def test_wide_spread_penalizes(self):
        """Wide confidence spread across agents reduces confidence."""
        agents_spread = [
            AgentOutput("n1", confidence=0.9, text_length=200),
            AgentOutput("n2", confidence=0.1, text_length=200),
        ]
        agents_tight = [
            AgentOutput("n1", confidence=0.7, text_length=200),
            AgentOutput("n2", confidence=0.8, text_length=200),
        ]
        cal = ConfidenceCalibrator()
        result_spread = cal.calibrate(0.7, agents_spread)
        result_tight = cal.calibrate(0.7, agents_tight)
        assert result_tight > result_spread  # Tight agreement wins

    def test_output_clamped_to_range(self):
        """Output always between 0.01 and 0.99."""
        cal = ConfidenceCalibrator()
        # Very low input
        agents = [AgentOutput("n1", confidence=0.0, text_length=5)]
        result = cal.calibrate(0.0, agents)
        assert 0.01 <= result <= 0.99

        # Very high input
        agents = [AgentOutput("n1", confidence=1.0, text_length=500)]
        result = cal.calibrate(1.0, agents)
        assert 0.01 <= result <= 0.99


# ─── Route Tests: Different fold-back histories ───


class TestRouteFoldBackHistories:

    def test_model_with_good_track_record(self):
        """Model that often succeeds should get slight negative offset."""
        cal = ConfidenceCalibrator({"writes": 90, "skips": 10})
        agents = [
            AgentOutput("n1", confidence=0.7, text_length=200),
            AgentOutput("n2", confidence=0.8, text_length=200),
        ]
        result = cal.calibrate(0.7, agents)
        # Good track record: negative offset slightly reduces already-good confidence
        assert 0.4 < result < 0.9

    def test_model_with_bad_track_record(self):
        """Model that often fails should get positive offset boost."""
        cal = ConfidenceCalibrator({"writes": 10, "skips": 90})
        agents = [
            AgentOutput("n1", confidence=0.7, text_length=200),
            AgentOutput("n2", confidence=0.8, text_length=200),
        ]
        result = cal.calibrate(0.5, agents)
        # Bad track record: positive offset boosts confidence
        assert result > 0.5  # Should be boosted

    def test_fresh_model_no_history(self):
        """New model with no history: no offset applied."""
        cal = ConfidenceCalibrator({"writes": 0, "skips": 0})
        agents = [
            AgentOutput("n1", confidence=0.7, text_length=200),
        ]
        result = cal.calibrate(0.7, agents)
        assert abs(result - 0.75) < 0.15  # Close to blend of raw + agreement


# ─── Chain Tests: Calibrator + State ───


class TestChainCalibratorState:

    def test_state_feeds_calibrator(self):
        """GnieState.get_calibration_data() output feeds ConfidenceCalibrator."""
        from graqle.plugins.gnie.state import GnieState

        state = GnieState()
        model = "ollama:qwen2.5:3b"
        # Simulate fold-back history (record_query first to init model_stats)
        for _ in range(8):
            state.record_query(["n1"], model)
            state.record_fold_back("WRITTEN", ["n1"], 0.8, model)
        for _ in range(2):
            state.record_query(["n1"], model)
            state.record_fold_back("SKIPPED_LOW_CONFIDENCE", ["n1"], 0.3, model)

        cal_data = state.get_calibration_data(model)
        cal = ConfidenceCalibrator(cal_data)

        # Should have learned from 10 samples
        assert cal._calibration_offset != 0.0

        agents = [AgentOutput("n1", confidence=0.7, text_length=200)]
        result = cal.calibrate(0.7, agents)
        assert 0.01 <= result <= 0.99


# ─── Integration Tests: Full calibration pipeline ───


class TestIntegrationCalibrationPipeline:

    def test_calibration_is_deterministic(self):
        """Same inputs always produce same output."""
        cal = ConfidenceCalibrator({"writes": 50, "skips": 50})
        agents = [
            AgentOutput("n1", confidence=0.7, text_length=200),
            AgentOutput("n2", confidence=0.6, text_length=150),
        ]
        r1 = cal.calibrate(0.65, agents)
        r2 = cal.calibrate(0.65, agents)
        assert r1 == r2

    def test_single_agent_no_spread_penalty(self):
        """Single agent: no spread penalty applied."""
        cal = ConfidenceCalibrator()
        agents = [AgentOutput("n1", confidence=0.9, text_length=300)]
        result = cal.calibrate(0.8, agents)
        # Single agent, confidence > 0.3, length > 50: agreement_ratio = 1.0
        # raw * 0.5 + 1.0 * 0.4 = 0.4 + 0.4 = 0.8, no penalty
        assert 0.7 < result < 0.9
