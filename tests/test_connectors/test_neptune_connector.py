"""Tests for NeptuneConnector — mocked Neptune (VPC-only in production)."""

# ── graqle:intelligence ──
# module: tests.test_connectors.test_neptune_connector
# risk: LOW (impact radius: 0 modules)
# dependencies: pytest, unittest.mock
# constraints: VPC-only connector — always use mocks, no live Neptune calls in CI
# ── /graqle:intelligence ──

from unittest.mock import patch

import pytest

from graqle.connectors.neptune_connector import NeptuneConnector


_MOCK_NODES = [
    {"id": "svc_auth", "label": "AuthService", "type": "Service", "description": "Auth", "degree": 3, "size": 12, "color": "#64748b", "properties": None},
    {"id": "mod_jwt", "label": "JwtModule", "type": "Module", "description": "JWT handling", "degree": 1, "size": 8, "color": "#3b82f6", "properties": '{"critical": true}'},
]

_MOCK_EDGES = [
    {"id": "e1", "source": "svc_auth", "target": "mod_jwt", "relationship": "USES", "weight": 1.0},
    {"id": "", "source": "svc_auth", "target": "mod_jwt", "relationship": "DEPENDS_ON", "weight": 0.5},  # no id
    {"id": "bad", "source": "", "target": "mod_jwt", "relationship": "BROKEN"},  # missing source
]


class TestNeptuneConnectorLoad:

    def test_load_returns_nodes_and_edges_dicts(self):
        with patch("graqle.connectors.neptune.get_nodes", return_value=_MOCK_NODES), \
             patch("graqle.connectors.neptune.get_edges", return_value=_MOCK_EDGES):
            connector = NeptuneConnector(project_id="test-project")
            nodes, edges = connector.load()

        assert "svc_auth" in nodes
        assert "mod_jwt" in nodes
        assert nodes["svc_auth"]["label"] == "AuthService"
        assert nodes["svc_auth"]["type"] == "Service"

    def test_load_parses_json_properties(self):
        """Properties stored as JSON strings are parsed to dicts."""
        with patch("graqle.connectors.neptune.get_nodes", return_value=_MOCK_NODES), \
             patch("graqle.connectors.neptune.get_edges", return_value=[]):
            connector = NeptuneConnector(project_id="test-project")
            nodes, _ = connector.load()

        assert nodes["mod_jwt"]["properties"] == {"critical": True}

    def test_load_skips_edges_with_missing_source_or_target(self):
        """Edges with empty source/target are excluded."""
        with patch("graqle.connectors.neptune.get_nodes", return_value=_MOCK_NODES), \
             patch("graqle.connectors.neptune.get_edges", return_value=_MOCK_EDGES):
            connector = NeptuneConnector(project_id="test-project")
            _, edges = connector.load()

        # bad edge (source="") must be excluded
        for eid, edge in edges.items():
            assert edge["source"] != ""
            assert edge["target"] != ""

    def test_load_generates_id_for_edges_without_id(self):
        """Edges with empty id get a synthetic id = source__target."""
        with patch("graqle.connectors.neptune.get_nodes", return_value=_MOCK_NODES), \
             patch("graqle.connectors.neptune.get_edges", return_value=_MOCK_EDGES):
            connector = NeptuneConnector(project_id="test-project")
            _, edges = connector.load()

        # Edge without id should get "svc_auth__mod_jwt" as synthetic id
        assert "svc_auth__mod_jwt" in edges or "e1" in edges

    def test_load_node_count_matches_input(self):
        with patch("graqle.connectors.neptune.get_nodes", return_value=_MOCK_NODES), \
             patch("graqle.connectors.neptune.get_edges", return_value=[]):
            nodes, edges = NeptuneConnector("p").load()

        assert len(nodes) == 2
        assert len(edges) == 0


class TestNeptuneConnectorValidate:

    def test_validate_returns_true_when_connected(self):
        with patch("graqle.connectors.neptune.neptune_health", return_value={"status": "connected"}):
            assert NeptuneConnector("p").validate() is True

    def test_validate_returns_false_when_unavailable(self):
        with patch("graqle.connectors.neptune.neptune_health", return_value={"status": "error"}):
            assert NeptuneConnector("p").validate() is False

    def test_validate_returns_false_on_exception(self):
        with patch("graqle.connectors.neptune.neptune_health", side_effect=RuntimeError("VPC timeout")):
            assert NeptuneConnector("p").validate() is False
