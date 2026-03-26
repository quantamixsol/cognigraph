"""Tests for GET /lessons Studio API route (P1 monetization feature)."""

# ── graqle:intelligence ──
# module: tests.test_studio.test_api_lessons_route
# risk: LOW (impact radius: 0 modules)
# dependencies: pytest, fastapi, dataclasses
# constraints: none
# ── /graqle:intelligence ──

from dataclasses import dataclass, field

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from graqle.studio.routes.api import router


# ── Helpers ──────────────────────────────────────────────────────────────────

@dataclass
class MockNode:
    id: str
    label: str
    entity_type: str
    description: str
    properties: dict = field(default_factory=dict)


@dataclass
class MockGraph:
    nodes: dict


def _make_app(graph=None):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.studio_state = {"graph": graph}
    return app


def _lesson_graph():
    return MockGraph(nodes={
        "lesson_001": MockNode(
            id="lesson_001",
            label="Never mock the DB in integration tests",
            entity_type="LESSON",
            description="Mocking the DB caused prod divergence in Q1. Always use real DB.",
            properties={"severity": "HIGH", "hit_count": 3},
        ),
        "mistake_001": MockNode(
            id="mistake_001",
            label="Duplicate CORS headers break browsers",
            entity_type="MISTAKE",
            description="Two Access-Control-Allow-Origin headers cause browser rejection.",
            properties={"severity": "CRITICAL", "hit_count": 7},
        ),
        "adr_001": MockNode(
            id="adr_001",
            label="ADR-056: Single CORS source",
            entity_type="ADR",
            description="Use Function URL CORS only, never add headers in Lambda code.",
            properties={"severity": "MEDIUM", "hit_count": 1},
        ),
        "func_001": MockNode(
            id="func_001",
            label="some_function",
            entity_type="Function",
            description="A regular function node, not a lesson.",
            properties={},
        ),
    })


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestLessonsRoute:

    def test_returns_only_lesson_types(self):
        """Only LESSON/MISTAKE/SAFETY/ADR/DECISION nodes are returned."""
        client = TestClient(_make_app(_lesson_graph()))
        resp = client.get("/api/lessons")
        assert resp.status_code == 200
        data = resp.json()
        ids = {l["id"] for l in data["lessons"]}
        assert "lesson_001" in ids
        assert "mistake_001" in ids
        assert "adr_001" in ids
        assert "func_001" not in ids  # regular function node must be excluded

    def test_count_matches_lessons(self):
        client = TestClient(_make_app(_lesson_graph()))
        resp = client.get("/api/lessons")
        data = resp.json()
        assert data["count"] == 3  # lesson + mistake + adr, not the Function node

    def test_severity_filter_critical_only(self):
        """severity=critical returns only CRITICAL nodes."""
        client = TestClient(_make_app(_lesson_graph()))
        resp = client.get("/api/lessons?severity=critical")
        data = resp.json()
        ids = {l["id"] for l in data["lessons"]}
        assert "mistake_001" in ids       # CRITICAL
        assert "lesson_001" not in ids    # HIGH
        assert "adr_001" not in ids       # MEDIUM

    def test_severity_filter_high_includes_critical(self):
        """severity=high returns CRITICAL + HIGH nodes."""
        client = TestClient(_make_app(_lesson_graph()))
        resp = client.get("/api/lessons?severity=high")
        data = resp.json()
        ids = {l["id"] for l in data["lessons"]}
        assert "mistake_001" in ids   # CRITICAL
        assert "lesson_001" in ids    # HIGH
        assert "adr_001" not in ids   # MEDIUM

    def test_operation_filter_narrows_results(self):
        """operation= filters by keyword match in label/description."""
        client = TestClient(_make_app(_lesson_graph()))
        resp = client.get("/api/lessons?operation=cors&severity=all")
        data = resp.json()
        ids = {l["id"] for l in data["lessons"]}
        assert "mistake_001" in ids   # contains "CORS"
        assert "adr_001" in ids       # contains "CORS"
        assert "lesson_001" not in ids  # no cors mention

    def test_critical_sorted_first(self):
        """CRITICAL lessons appear before HIGH before MEDIUM."""
        client = TestClient(_make_app(_lesson_graph()))
        resp = client.get("/api/lessons?severity=all")
        data = resp.json()
        severities = [l["severity"] for l in data["lessons"]]
        sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
        ranks = [sev_order[s] for s in severities]
        assert ranks == sorted(ranks), "Lessons not sorted by severity"

    def test_no_graph_returns_empty(self):
        """Returns empty list gracefully when no graph is loaded."""
        client = TestClient(_make_app(graph=None))
        resp = client.get("/api/lessons")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lessons"] == []
        assert data["count"] == 0

    def test_response_has_required_fields(self):
        """Each lesson has id, label, severity, description, hit_count."""
        client = TestClient(_make_app(_lesson_graph()))
        resp = client.get("/api/lessons")
        data = resp.json()
        for lesson in data["lessons"]:
            assert "id" in lesson
            assert "label" in lesson
            assert "severity" in lesson
            assert "description" in lesson
            assert "hit_count" in lesson
