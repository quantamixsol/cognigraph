"""Tests for GNIE State Manager.

Unit tests: state operations, fold-back recording, node scoring
Route tests: save/load round-trip, per-model tracking
Chain tests: state -> calibrator data flow
Integration tests: state persistence across simulated sessions
"""

import json
import pytest
from pathlib import Path

from graqle.plugins.gnie.state import GnieState


# ─── Unit Tests: State operations ───


class TestStateOperations:

    def test_fresh_state_defaults(self):
        state = GnieState()
        assert state.queries_processed == 0
        assert state.fold_back_writes == 0
        assert state.fold_back_skips == 0
        assert state.node_scores == {}
        assert state.model_stats == {}

    def test_record_query(self):
        state = GnieState()
        state.record_query(["n1", "n2"], "ollama:qwen2.5:3b")
        assert state.queries_processed == 1
        assert state.model_stats["ollama:qwen2.5:3b"]["queries"] == 1
        assert state.updated_at != ""

    def test_record_fold_back_written(self):
        state = GnieState()
        state.record_fold_back("WRITTEN", ["n1", "n2"], 0.8, "ollama:qwen2.5:3b")
        assert state.fold_back_writes == 1
        assert state.node_scores["n1"] == 0.55  # 0.5 + 0.05
        assert state.node_scores["n2"] == 0.55

    def test_record_fold_back_skipped(self):
        state = GnieState()
        state.record_fold_back("SKIPPED_LOW_CONFIDENCE", ["n1"], 0.3, "ollama:qwen2.5:3b")
        assert state.fold_back_skips == 1
        assert state.node_scores["n1"] == 0.48  # 0.5 - 0.02

    def test_node_score_capped_at_1(self):
        state = GnieState()
        state.node_scores["n1"] = 0.98
        state.record_fold_back("WRITTEN", ["n1"], 0.9, "model")
        assert state.node_scores["n1"] == 1.0

    def test_node_score_floored_at_01(self):
        state = GnieState()
        state.node_scores["n1"] = 0.11
        state.record_fold_back("SKIPPED_LOW_CONFIDENCE", ["n1"], 0.2, "model")
        assert state.node_scores["n1"] == 0.1  # Can't go below 0.1

    def test_dry_run_not_counted(self):
        state = GnieState()
        state.record_fold_back("DRY_RUN", ["n1"], 0.7, "model")
        assert state.fold_back_writes == 0
        assert state.fold_back_skips == 0

    def test_get_node_boost_default(self):
        state = GnieState()
        assert state.get_node_boost("unknown_node") == 0.5

    def test_get_calibration_data_unknown_model(self):
        state = GnieState()
        data = state.get_calibration_data("unknown_model")
        assert data == {"writes": 0, "skips": 0}


# ─── Route Tests: Save/load round-trip ───


class TestSaveLoadRoundTrip:

    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "gnie_state.json")

        # Create and populate state
        state = GnieState()
        state.record_query(["n1", "n2"], "ollama:qwen2.5:3b")
        state.record_fold_back("WRITTEN", ["n1"], 0.8, "ollama:qwen2.5:3b")
        state.record_fold_back("SKIPPED_LOW_CONFIDENCE", ["n2"], 0.3, "ollama:qwen2.5:3b")
        state.save(path)

        # Load and verify
        loaded = GnieState.load(path)
        assert loaded.queries_processed == 1
        assert loaded.fold_back_writes == 1
        assert loaded.fold_back_skips == 1
        assert loaded.node_scores["n1"] == 0.55
        assert loaded.model_stats["ollama:qwen2.5:3b"]["writes"] == 1

    def test_load_missing_file_returns_fresh(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        state = GnieState.load(path)
        assert state.queries_processed == 0
        assert state.created_at != ""

    def test_save_creates_directory(self, tmp_path):
        path = str(tmp_path / "nested" / "dir" / "state.json")
        state = GnieState()
        state.save(path)
        assert Path(path).exists()

    def test_save_limits_node_scores_to_500(self, tmp_path):
        path = str(tmp_path / "state.json")
        state = GnieState()
        # Add 600 nodes
        for i in range(600):
            state.node_scores[f"node_{i}"] = 0.5 + (i % 10) * 0.05
        state.save(path)

        # Reload — should only have top 500
        with open(path) as f:
            data = json.load(f)
        assert len(data["node_scores"]) <= 500


# ─── Route Tests: Per-model tracking ───


class TestPerModelTracking:

    def test_multiple_models_tracked_separately(self):
        state = GnieState()
        state.record_query(["n1"], "ollama:qwen2.5:3b")
        state.record_query(["n1"], "ollama:deepseek-r1:7b")
        state.record_query(["n1"], "ollama:qwen2.5:3b")

        assert state.model_stats["ollama:qwen2.5:3b"]["queries"] == 2
        assert state.model_stats["ollama:deepseek-r1:7b"]["queries"] == 1

    def test_calibration_data_per_model(self):
        state = GnieState()
        state.record_fold_back("WRITTEN", ["n1"], 0.8, "ollama:qwen2.5:3b")
        state.record_fold_back("SKIPPED_LOW_CONFIDENCE", ["n1"], 0.3, "ollama:deepseek-r1:7b")

        qwen_data = state.get_calibration_data("ollama:qwen2.5:3b")
        assert qwen_data == {"writes": 1, "skips": 0}

        ds_data = state.get_calibration_data("ollama:deepseek-r1:7b")
        assert ds_data == {"writes": 0, "skips": 1}

    def test_model_stats_persist_through_save_load(self, tmp_path):
        path = str(tmp_path / "state.json")
        state = GnieState()
        state.record_query(["n1"], "ollama:qwen2.5:3b")
        state.record_fold_back("WRITTEN", ["n1"], 0.8, "ollama:qwen2.5:3b")
        state.save(path)

        loaded = GnieState.load(path)
        assert loaded.model_stats["ollama:qwen2.5:3b"]["queries"] == 1
        assert loaded.model_stats["ollama:qwen2.5:3b"]["writes"] == 1


# ─── Chain Tests: State → Calibrator ───


class TestChainStateToCalibrator:

    def test_state_calibration_feeds_calibrator(self):
        from graqle.plugins.gnie.calibrator import ConfidenceCalibrator

        state = GnieState()
        model = "ollama:qwen2.5:3b"
        for _ in range(10):
            state.record_fold_back("WRITTEN", ["n1"], 0.8, model)

        cal_data = state.get_calibration_data(model)
        cal = ConfidenceCalibrator(cal_data)
        # All writes, no skips → good track record
        assert cal._calibration_offset < 0


# ─── Integration Tests: Simulated multi-session learning ───


class TestIntegrationMultiSession:

    def test_learning_across_sessions(self, tmp_path):
        """Simulate 3 sessions of learning."""
        path = str(tmp_path / "state.json")
        model = "ollama:qwen2.5:3b"

        # Session 1: 5 queries, 3 written, 2 skipped
        s1 = GnieState()
        for _ in range(3):
            s1.record_query(["n1", "n2"], model)
            s1.record_fold_back("WRITTEN", ["n1", "n2"], 0.8, model)
        for _ in range(2):
            s1.record_query(["n3"], model)
            s1.record_fold_back("SKIPPED_LOW_CONFIDENCE", ["n3"], 0.3, model)
        s1.save(path)

        # Session 2: Load and continue
        s2 = GnieState.load(path)
        assert s2.queries_processed == 5
        s2.record_query(["n1"], model)
        s2.record_fold_back("WRITTEN", ["n1"], 0.9, model)
        s2.save(path)

        # Session 3: Load final state
        s3 = GnieState.load(path)
        assert s3.queries_processed == 6
        assert s3.fold_back_writes == 4
        assert s3.fold_back_skips == 2
        # n1 was in 4 successful writes: 0.5 + 4*0.05 = 0.7
        assert s3.node_scores["n1"] == pytest.approx(0.7, abs=0.01)
        # n3 was in 2 skips: 0.5 - 2*0.02 = 0.46
        assert s3.node_scores["n3"] == pytest.approx(0.46, abs=0.01)
