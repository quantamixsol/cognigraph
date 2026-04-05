"""Tests for HFCI-017: graq_context deep-level source snippet embedding.

Verifies that graq_context level=deep internally composes file reading,
returning embedded source snippets alongside KG node metadata.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest

from graqle.plugins.mcp_dev_server import KogniDevServer


# ---------------------------------------------------------------------------
# Mock objects (same pattern as test_mcp_dev_server.py)
# ---------------------------------------------------------------------------

@dataclass
class MockNode:
    id: str
    label: str
    entity_type: str
    description: str
    properties: dict = field(default_factory=dict)
    degree: int = 2
    status: str = "ACTIVE"


@dataclass
class MockStats:
    total_nodes: int = 3
    total_edges: int = 2
    avg_degree: float = 1.33
    density: float = 0.67
    connected_components: int = 1
    hub_nodes: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def server(tmp_path):
    """KogniDevServer with graph file inside tmp_path for path resolution."""
    srv = KogniDevServer.__new__(KogniDevServer)
    srv.config_path = "graqle.yaml"
    srv.read_only = False
    srv._graph = MagicMock()
    srv._graph.nodes = {}
    srv._graph.edges = {}
    srv._graph.stats = MockStats()
    srv._config = None
    graph_file = tmp_path / "graqle.json"
    graph_file.write_text("{}")
    srv._graph_file = str(graph_file)
    srv._graph_mtime = 9999999999.0
    return srv


@pytest.fixture
def sample_py_file(tmp_path):
    """Create a sample .py file with 10 numbered lines."""
    content = "\n".join(f"line_{i} = {i}" for i in range(1, 11))
    fp = tmp_path / "sample.py"
    fp.write_text(content, encoding="utf-8")
    return fp


@pytest.fixture
def long_py_file(tmp_path):
    """Create a .py file with content exceeding typical budgets."""
    content = "x = 1\n" * 500  # ~3000 chars
    fp = tmp_path / "long_module.py"
    fp.write_text(content, encoding="utf-8")
    return fp


# ---------------------------------------------------------------------------
# TestReadFileSnippet
# ---------------------------------------------------------------------------

class TestReadFileSnippet:
    def test_reads_full_file(self, server, sample_py_file):
        content, truncated = server._read_file_snippet(str(sample_py_file))
        assert "line_1 = 1" in content
        assert "line_10 = 10" in content
        assert truncated is False

    def test_line_range_scoping(self, server, sample_py_file):
        content, truncated = server._read_file_snippet(
            str(sample_py_file), start_line=3, end_line=5,
        )
        assert "line_3 = 3" in content
        assert "line_5 = 5" in content
        assert "line_1 = 1" not in content
        assert "line_6 = 6" not in content

    def test_max_chars_truncation(self, server, long_py_file):
        content, truncated = server._read_file_snippet(
            str(long_py_file), max_chars=50,
        )
        assert truncated is True
        assert content.endswith("\u2026[truncated]")
        # Content before marker should be at most 50 chars
        before_marker = content.split("\n\u2026[truncated]")[0]
        assert len(before_marker) <= 50

    def test_missing_file_raises(self, server):
        with pytest.raises(FileNotFoundError):
            server._read_file_snippet("/nonexistent/path/to/file.py")

    def test_was_truncated_flag_false(self, server, sample_py_file):
        _, truncated = server._read_file_snippet(
            str(sample_py_file), max_chars=10000,
        )
        assert truncated is False

    def test_was_truncated_flag_true(self, server, long_py_file):
        _, truncated = server._read_file_snippet(
            str(long_py_file), max_chars=20,
        )
        assert truncated is True


# ---------------------------------------------------------------------------
# TestEmbedSourceSnippets
# ---------------------------------------------------------------------------

class TestEmbedSourceSnippets:
    def test_embeds_python_module_snippets(self, server, sample_py_file):
        nodes = [
            MockNode(
                id="test_module",
                label="Test Module",
                entity_type="PythonModule",
                description="A test module",
                properties={"file_path": str(sample_py_file)},
            ),
        ]
        snippets, tokens_used = server._embed_source_snippets(nodes)
        assert len(snippets) == 1
        assert snippets[0]["node_id"] == "test_module"
        assert "line_1 = 1" in snippets[0]["content"]
        assert tokens_used > 0

    def test_skips_non_code_nodes(self, server):
        nodes = [
            MockNode(
                id="lesson-1",
                label="A Lesson",
                entity_type="LESSON",
                description="Some lesson",
            ),
            MockNode(
                id="db-table",
                label="Users DB",
                entity_type="database",
                description="A database table",
            ),
        ]
        snippets, tokens_used = server._embed_source_snippets(nodes)
        assert snippets == []
        assert tokens_used == 0

    def test_budget_distribution(self, server, tmp_path):
        files = []
        nodes = []
        for i in range(3):
            fp = tmp_path / f"mod_{i}.py"
            fp.write_text("y = 1\n" * 200, encoding="utf-8")  # ~1200 chars each
            files.append(fp)
            nodes.append(MockNode(
                id=f"mod_{i}",
                label=f"Module {i}",
                entity_type="PythonModule",
                description=f"Module {i}",
                properties={"file_path": str(fp)},
            ))
        # token_budget=300 → char_budget=1200 → ~400 per node
        snippets, tokens_used = server._embed_source_snippets(
            nodes, token_budget=300,
        )
        assert len(snippets) == 3
        for s in snippets:
            assert len(s["content"]) <= 500  # 400 + truncation marker slack

    def test_graceful_on_missing_file(self, server):
        nodes = [
            MockNode(
                id="missing_mod",
                label="Missing",
                entity_type="PythonModule",
                description="Does not exist",
                properties={"file_path": "/nonexistent/module.py"},
            ),
        ]
        snippets, tokens_used = server._embed_source_snippets(nodes)
        assert snippets == []
        assert tokens_used == 0

    def test_function_node_uses_line_range(self, server, sample_py_file):
        nodes = [
            MockNode(
                id="my_func",
                label="my_func",
                entity_type="Function",
                description="A function",
                properties={
                    "file_path": str(sample_py_file),
                    "line_start": 3,
                    "line_end": 5,
                },
            ),
        ]
        snippets, _ = server._embed_source_snippets(nodes)
        assert len(snippets) == 1
        assert snippets[0]["lines"] == [3, 5]
        assert "line_3 = 3" in snippets[0]["content"]
        assert "line_1 = 1" not in snippets[0]["content"]

    def test_respects_total_budget_cap(self, server, tmp_path):
        """Budget cap stops reading more nodes once exhausted."""
        nodes = []
        for i in range(10):
            fp = tmp_path / f"big_{i}.py"
            fp.write_text("z = 1\n" * 500, encoding="utf-8")
            nodes.append(MockNode(
                id=f"big_{i}",
                label=f"Big {i}",
                entity_type="PythonModule",
                description=f"Big module {i}",
                properties={"file_path": str(fp)},
            ))
        snippets, tokens_used = server._embed_source_snippets(
            nodes, token_budget=500,
        )
        # Should not read all 10 — budget limits it
        total_content = sum(len(s["content"]) for s in snippets)
        assert total_content <= 2200  # 500*4 + slack for truncation markers


# ---------------------------------------------------------------------------
# TestContextDeepSnippets (integration)
# ---------------------------------------------------------------------------

class TestContextDeepSnippets:
    @pytest.mark.asyncio
    async def test_deep_level_includes_snippets(self, server, sample_py_file):
        code_node = MockNode(
            id="ctx_module",
            label="Context Module",
            entity_type="PythonModule",
            description="Module for context test",
            properties={"file_path": str(sample_py_file)},
        )
        with patch.object(server, "_read_active_branch", return_value=None), \
             patch.object(server, "_find_nodes_matching", return_value=[code_node]), \
             patch.object(server, "_find_lesson_nodes", return_value=[]):
            result = await server._handle_context({"task": "test", "level": "deep"})

        data = json.loads(result)
        assert "embedded_snippets" in data
        assert len(data["embedded_snippets"]) == 1
        assert "line_1 = 1" in data["embedded_snippets"][0]["content"]
        assert data["snippet_budget_used"] > 0
        assert data["snippet_budget_total"] == 2000

    @pytest.mark.asyncio
    async def test_standard_level_no_snippets(self, server, sample_py_file):
        code_node = MockNode(
            id="ctx_module",
            label="Context Module",
            entity_type="PythonModule",
            description="Module for context test",
            properties={"file_path": str(sample_py_file)},
        )
        with patch.object(server, "_read_active_branch", return_value=None), \
             patch.object(server, "_find_nodes_matching", return_value=[code_node]), \
             patch.object(server, "_find_lesson_nodes", return_value=[]):
            result = await server._handle_context({"task": "test", "level": "standard"})

        data = json.loads(result)
        assert "embedded_snippets" not in data
        assert "snippet_budget_used" not in data

    @pytest.mark.asyncio
    async def test_minimal_level_no_snippets(self, server, sample_py_file):
        code_node = MockNode(
            id="ctx_module",
            label="Context Module",
            entity_type="PythonModule",
            description="Module for context test",
            properties={"file_path": str(sample_py_file)},
        )
        with patch.object(server, "_read_active_branch", return_value=None), \
             patch.object(server, "_find_nodes_matching", return_value=[code_node]), \
             patch.object(server, "_find_lesson_nodes", return_value=[]):
            result = await server._handle_context({"task": "test", "level": "minimal"})

        data = json.loads(result)
        assert "embedded_snippets" not in data

    @pytest.mark.asyncio
    async def test_snippet_budget_fields(self, server, sample_py_file):
        code_node = MockNode(
            id="ctx_module",
            label="Context Module",
            entity_type="PythonModule",
            description="Module for context test",
            properties={"file_path": str(sample_py_file)},
        )
        with patch.object(server, "_read_active_branch", return_value=None), \
             patch.object(server, "_find_nodes_matching", return_value=[code_node]), \
             patch.object(server, "_find_lesson_nodes", return_value=[]):
            result = await server._handle_context({"task": "test", "level": "deep"})

        data = json.loads(result)
        assert "snippet_budget_used" in data
        assert "snippet_budget_total" in data
        assert data["snippet_budget_used"] <= data["snippet_budget_total"]

    @pytest.mark.asyncio
    async def test_deep_no_snippets_when_no_code_nodes(self, server):
        lesson_node = MockNode(
            id="lesson-1",
            label="A Lesson",
            entity_type="LESSON",
            description="Some lesson about CORS",
        )
        with patch.object(server, "_read_active_branch", return_value=None), \
             patch.object(server, "_find_nodes_matching", return_value=[lesson_node]), \
             patch.object(server, "_find_lesson_nodes", return_value=[]):
            result = await server._handle_context({"task": "test", "level": "deep"})

        data = json.loads(result)
        # No code nodes → no snippets keys at all
        assert "embedded_snippets" not in data


# ---------------------------------------------------------------------------
# Security tests (from graq_review BLOCKERs)
# ---------------------------------------------------------------------------

class TestSnippetSecurity:
    def test_path_traversal_rejected(self, server):
        """Paths with .. segments are rejected by _resolve_file_path."""
        with pytest.raises((PermissionError, FileNotFoundError)):
            server._read_file_snippet("../../etc/passwd")

    def test_absolute_path_outside_workspace_rejected(self, server):
        """Absolute paths outside workspace root are rejected."""
        with pytest.raises((PermissionError, FileNotFoundError)):
            server._read_file_snippet("/etc/passwd")

    def test_node_without_file_path_skipped(self, server):
        """Nodes without explicit file_path property are skipped."""
        nodes = [
            MockNode(
                id="graqle.core.graph",
                label="Graph Module",
                entity_type="PythonModule",
                description="Core graph",
                properties={},  # No file_path
            ),
        ]
        snippets, tokens_used = server._embed_source_snippets(nodes)
        assert snippets == []
        assert tokens_used == 0


# ---------------------------------------------------------------------------
# Type validation tests (from graq_review MAJORs)
# ---------------------------------------------------------------------------

class TestSnippetTypeValidation:
    def test_non_integer_line_metadata_handled(self, server, sample_py_file):
        """Non-integer line_start/line_end values don't crash."""
        nodes = [
            MockNode(
                id="bad_lines",
                label="Bad Lines",
                entity_type="Function",
                description="Function with bad line metadata",
                properties={
                    "file_path": str(sample_py_file),
                    "line_start": "not_a_number",
                    "line_end": "also_not",
                },
            ),
        ]
        # Should not crash — falls back to reading full file
        snippets, _ = server._embed_source_snippets(nodes)
        assert len(snippets) == 1
        # lines should be None since validation failed
        assert snippets[0]["lines"] is None

    def test_string_integer_line_metadata_works(self, server, sample_py_file):
        """String-encoded integers (from JSON) are correctly cast."""
        nodes = [
            MockNode(
                id="str_lines",
                label="String Lines",
                entity_type="Function",
                description="Function with string line metadata",
                properties={
                    "file_path": str(sample_py_file),
                    "line_start": "3",
                    "line_end": "5",
                },
            ),
        ]
        snippets, _ = server._embed_source_snippets(nodes)
        assert len(snippets) == 1
        assert snippets[0]["lines"] == [3, 5]
        assert "line_3 = 3" in snippets[0]["content"]

    def test_inverted_line_range_handled(self, server, sample_py_file):
        """Inverted line range (start > end) falls back to full file."""
        nodes = [
            MockNode(
                id="inverted",
                label="Inverted",
                entity_type="Function",
                description="Inverted lines",
                properties={
                    "file_path": str(sample_py_file),
                    "line_start": 8,
                    "line_end": 3,
                },
            ),
        ]
        snippets, _ = server._embed_source_snippets(nodes)
        assert len(snippets) == 1
        # lines should be None since range was inverted
        assert snippets[0]["lines"] is None

    def test_non_string_file_path_skipped(self, server):
        """Non-string file_path values are skipped."""
        nodes = [
            MockNode(
                id="bad_path",
                label="Bad Path",
                entity_type="PythonModule",
                description="Has non-string file_path",
                properties={"file_path": 12345},
            ),
        ]
        snippets, _ = server._embed_source_snippets(nodes)
        assert snippets == []

    def test_directory_path_raises(self, server, tmp_path):
        """Directory paths raise FileNotFoundError (is_file check)."""
        with pytest.raises(FileNotFoundError):
            server._read_file_snippet(str(tmp_path))
"# HFCI-011d verification" 
