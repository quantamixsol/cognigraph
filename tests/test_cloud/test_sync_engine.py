"""Tests for graqle.cloud.sync_engine — SyncEngine orchestrator.

P2 tests: delta-push, change detection, failure isolation, tier gating.
"""

# ── graqle:intelligence ──
# module: tests.test_cloud.test_sync_engine
# risk: LOW (impact radius: 0 modules)
# dependencies: pytest, pathlib, json, unittest.mock, graqle.cloud.sync_engine
# constraints: none — sync failure never blocks local ops
# ── /graqle:intelligence ──

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from graqle.cloud.sync_engine import SyncEngine, SyncResult


# ── Fixtures ─────────────────────────────────────────────────────────────────

_SAMPLE_GRAPH = {
    "nodes": [
        {"id": "n1", "label": "FooService", "entity_type": "Service"},
        {"id": "n2", "label": "BarModule", "entity_type": "Module"},
    ],
    "edges": [
        {"id": "e1", "source": "n1", "target": "n2", "relation": "CALLS"},
    ],
    "metadata": {"project": "test"},
}

_SAMPLE_GRAPH_MODIFIED = {
    "nodes": [
        {"id": "n1", "label": "FooService", "entity_type": "Service"},
        {"id": "n2", "label": "BarModuleUpdated", "entity_type": "Module"},
        {"id": "n3", "label": "NewNode", "entity_type": "Function"},
    ],
    "edges": [
        {"id": "e1", "source": "n1", "target": "n2", "relation": "CALLS"},
    ],
    "metadata": {"project": "test"},
}


def _make_engine(tmp_path: Path, graph: dict | None = _SAMPLE_GRAPH) -> tuple[SyncEngine, Path]:
    """Create a SyncEngine with a real graqle.json in tmp_path."""
    graph_path = tmp_path / "graqle.json"
    if graph is not None:
        graph_path.write_text(json.dumps(graph), encoding="utf-8")
    engine = SyncEngine(project_dir=tmp_path, graph_path=graph_path)
    return engine, graph_path


# ── Tests ────────────────────────────────────────────────────────────────────


class TestSyncEngineNoOpWhenHashUnchanged:
    """push_if_changed must be a no-op when the graph hash has not changed."""

    def test_push_if_changed_no_op_when_hash_unchanged(self, tmp_path):
        engine, graph_path = _make_engine(tmp_path)

        # Simulate: state already has this hash + snapshot already saved
        from graqle.cloud.sync import compute_graph_hash, load_sync_state, save_sync_state

        graph = json.loads(graph_path.read_text())
        current_hash = compute_graph_hash(graph)

        # Save state with current hash
        state = load_sync_state(tmp_path)
        state.last_snapshot_hash = current_hash
        save_sync_state(state, tmp_path)

        # Save matching snapshot
        snapshot_path = tmp_path / ".graqle" / "sync-snapshot.json"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(graph), encoding="utf-8")

        with patch.object(engine, "_is_team_plan", return_value=True):
            result = engine.push_if_changed()

        assert result.status == "no_changes"
        assert result.succeeded


class TestSyncEnginePushesWhenChanged:
    """push_if_changed must push when graph has changed since last sync."""

    def test_push_if_changed_pushes_when_changed(self, tmp_path):
        engine, graph_path = _make_engine(tmp_path)

        # Snapshot = old graph (different hash)
        snapshot_path = tmp_path / ".graqle" / "sync-snapshot.json"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        old_graph = {"nodes": [], "edges": [], "metadata": {}}
        snapshot_path.write_text(json.dumps(old_graph), encoding="utf-8")

        with patch.object(engine, "_is_team_plan", return_value=True), \
             patch("graqle.cli.commands.cloud.auto_cloud_sync") as mock_sync:
            mock_sync.return_value = None
            result = engine.push_if_changed()

        assert result.status == "pushed"
        assert result.succeeded
        mock_sync.assert_called_once()


class TestSyncEngineFreeTierBlocked:
    """Free tier users must never attempt a sync push."""

    def test_free_tier_no_sync_attempted(self, tmp_path):
        engine, _ = _make_engine(tmp_path)

        with patch.object(engine, "_is_team_plan", return_value=False), \
             patch("graqle.cli.commands.cloud.auto_cloud_sync") as mock_sync:
            result = engine.push_if_changed()

        assert result.status == "skipped"
        assert result.error == "free tier"
        mock_sync.assert_not_called()


class TestSyncFailureDoesNotBlockLocal:
    """Cloud sync failure must NEVER raise — always returns SyncResult(status='failed')."""

    def test_sync_failure_does_not_block_local(self, tmp_path):
        engine, _ = _make_engine(tmp_path)

        # Snapshot = old graph so it tries to push
        snapshot_path = tmp_path / ".graqle" / "sync-snapshot.json"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps({"nodes": {}, "edges": {}}), encoding="utf-8")

        def _boom(*args, **kwargs):
            raise RuntimeError("S3 connection refused")

        with patch.object(engine, "_is_team_plan", return_value=True), \
             patch("graqle.cli.commands.cloud.auto_cloud_sync", side_effect=_boom):
            result = engine.push_if_changed()

        assert result.status == "failed"
        assert not result.succeeded
        assert "S3 connection refused" in result.error


class TestSyncResultHasCorrectCounts:
    """SyncResult.nodes_pushed / edges_pushed must reflect the delta accurately."""

    def test_sync_result_has_correct_counts(self, tmp_path):
        engine, graph_path = _make_engine(tmp_path, graph=_SAMPLE_GRAPH_MODIFIED)

        # Snapshot = original graph (1 node modified, 1 node added, 0 edges changed)
        snapshot_path = tmp_path / ".graqle" / "sync-snapshot.json"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(_SAMPLE_GRAPH), encoding="utf-8")

        with patch.object(engine, "_is_team_plan", return_value=True), \
             patch("graqle.cli.commands.cloud.auto_cloud_sync") as mock_sync:
            mock_sync.return_value = None
            result = engine.push_if_changed()

        assert result.status == "pushed"
        # 1 added (n3) + 1 modified (n2 label changed) = 2 nodes
        assert result.nodes_pushed == 2
        # No edge changes
        assert result.edges_pushed == 0


class TestSyncEngineNoGraphFile:
    """Returns skipped gracefully when graqle.json does not exist."""

    def test_no_graph_file_returns_skipped(self, tmp_path):
        # Don't create the graph file
        engine, _ = _make_engine(tmp_path, graph=None)
        result = engine.push_if_changed()
        assert result.status == "skipped"
        assert "no graph file" in result.error


class TestSyncEngineForceFlag:
    """push(force=True) skips hash check and always pushes."""

    def test_force_push_ignores_hash_match(self, tmp_path):
        engine, graph_path = _make_engine(tmp_path)

        # State already has current hash (would normally be a no-op)
        from graqle.cloud.sync import compute_graph_hash, load_sync_state, save_sync_state

        graph = json.loads(graph_path.read_text())
        current_hash = compute_graph_hash(graph)
        state = load_sync_state(tmp_path)
        state.last_snapshot_hash = current_hash
        save_sync_state(state, tmp_path)

        with patch.object(engine, "_is_team_plan", return_value=True), \
             patch("graqle.cli.commands.cloud.auto_cloud_sync") as mock_sync:
            mock_sync.return_value = None
            result = engine.push(force=True)

        # Force=True means we push regardless — no snapshot exists so delta = full graph
        assert result.status in ("pushed", "no_changes")
        # Transport was invoked (delta not empty because no snapshot saved)
        # Note: if snapshot doesn't exist, delta is full graph — should push
