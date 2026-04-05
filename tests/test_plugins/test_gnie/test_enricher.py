"""Tests for GNIE Prompt Enricher.

Unit tests: enrichment logic per capability tier
Route tests: enrichment adapts correctly for different model names
Chain tests: enricher + detection + node context pipeline
Integration tests: enriched prompts maintain correct structure
"""

import pytest

from graqle.plugins.gnie.enricher import (
    CapabilityTier,
    GnieEnricher,
    NodeContext,
    detect_capability_tier,
)


# ─── Fixtures ───


@pytest.fixture
def function_node():
    return NodeContext(
        node_id="graqle/core/graph.py::reason",
        node_type="Function",
        label="reason",
        description="Run synchronous reasoning query.",
        neighbor_count=5,
        neighbor_types={"Class": 2, "Function": 2, "PythonModule": 1},
    )


@pytest.fixture
def isolated_node():
    return NodeContext(
        node_id="standalone_util",
        node_type="Function",
        label="format_date",
        description="Format a date string.",
        neighbor_count=0,
        neighbor_types={},
    )


@pytest.fixture
def hub_node():
    return NodeContext(
        node_id="graqle/core/graph.py",
        node_type="PythonModule",
        label="graph",
        description="Core graph module with Graqle class.",
        neighbor_count=42,
        neighbor_types={"Function": 20, "Class": 8, "PythonModule": 10, "TestFile": 4},
    )


# ─── Unit Tests: Capability tier detection ───


class TestCapabilityTierDetection:

    @pytest.mark.parametrize("model,expected", [
        ("qwen2.5:0.5b", CapabilityTier.SMALL),
        ("qwen2.5:3b", CapabilityTier.SMALL),
        ("phi3:mini", CapabilityTier.SMALL),
        ("tinyllama", CapabilityTier.SMALL),
        ("gemma4:e4b", CapabilityTier.MEDIUM),
        ("deepseek-r1:7b", CapabilityTier.MEDIUM),
        ("llama3.3:8b", CapabilityTier.MEDIUM),
        ("gemma3:12b", CapabilityTier.LARGE),
        ("phi4:14b", CapabilityTier.LARGE),
        ("gemma4:31b", CapabilityTier.LARGE),
        ("llama3.3:70b", CapabilityTier.LARGE),
    ])
    def test_known_models(self, model, expected):
        assert detect_capability_tier(model) == expected

    def test_unknown_model_defaults_to_medium(self):
        assert detect_capability_tier("some-unknown-model") == CapabilityTier.MEDIUM

    def test_case_insensitive(self):
        assert detect_capability_tier("QWEN2.5:3B") == CapabilityTier.SMALL


# ─── Unit Tests: Enrichment per tier ───


class TestEnrichmentSmallTier:
    """Small models get maximum enrichment."""

    def test_includes_node_type(self, function_node):
        enricher = GnieEnricher(CapabilityTier.SMALL)
        result = enricher.enrich("Base prompt", function_node, "What does this do?")
        assert "Function" in result
        assert "reason" in result

    def test_includes_neighbor_topology(self, function_node):
        enricher = GnieEnricher(CapabilityTier.SMALL)
        result = enricher.enrich("Base prompt", function_node, "query")
        assert "Connected to 5 nodes" in result
        assert "Class" in result

    def test_includes_format_hints(self, function_node):
        enricher = GnieEnricher(CapabilityTier.SMALL)
        result = enricher.enrich("Base prompt", function_node, "query")
        assert "Be specific" in result
        assert "confidence" in result.lower()

    def test_includes_round_context(self, function_node):
        enricher = GnieEnricher(CapabilityTier.SMALL)
        result = enricher.enrich("Base prompt", function_node, "query", round_idx=1)
        assert "round 2" in result.lower()
        assert "Refine" in result

    def test_includes_prior_round_summary(self, function_node):
        enricher = GnieEnricher(CapabilityTier.SMALL)
        result = enricher.enrich(
            "Base prompt", function_node, "query",
            round_idx=1, prior_round_summary="Found auth module dependency",
        )
        assert "auth module" in result

    def test_isolated_node_message(self, isolated_node):
        enricher = GnieEnricher(CapabilityTier.SMALL)
        result = enricher.enrich("Base prompt", isolated_node, "query")
        assert "isolated" in result.lower()


class TestEnrichmentMediumTier:
    """Medium models get moderate enrichment."""

    def test_includes_node_type(self, function_node):
        enricher = GnieEnricher(CapabilityTier.MEDIUM)
        result = enricher.enrich("Base prompt", function_node, "query")
        assert "Function" in result

    def test_includes_neighbor_topology(self, function_node):
        enricher = GnieEnricher(CapabilityTier.MEDIUM)
        result = enricher.enrich("Base prompt", function_node, "query")
        assert "Connected to 5 nodes" in result

    def test_cite_evidence_hint(self, function_node):
        enricher = GnieEnricher(CapabilityTier.MEDIUM)
        result = enricher.enrich("Base prompt", function_node, "query")
        assert "cite" in result.lower()

    def test_no_prior_round_summary(self, function_node):
        """Medium models don't get prior round summary (only small)."""
        enricher = GnieEnricher(CapabilityTier.MEDIUM)
        result = enricher.enrich(
            "Base prompt", function_node, "query",
            round_idx=1, prior_round_summary="Some summary",
        )
        assert "Some summary" not in result


class TestEnrichmentLargeTier:
    """Large models get minimal enrichment."""

    def test_includes_node_type(self, function_node):
        enricher = GnieEnricher(CapabilityTier.LARGE)
        result = enricher.enrich("Base prompt", function_node, "query")
        assert "Function" in result

    def test_no_neighbor_topology(self, function_node):
        """Large models don't need neighbor topology."""
        enricher = GnieEnricher(CapabilityTier.LARGE)
        result = enricher.enrich("Base prompt", function_node, "query")
        assert "Connected to" not in result

    def test_no_format_hints(self, function_node):
        enricher = GnieEnricher(CapabilityTier.LARGE)
        result = enricher.enrich("Base prompt", function_node, "query")
        assert "Be specific" not in result
        assert "cite" not in result.lower()


# ─── Unit Tests: Prompt structure ───


class TestPromptStructure:
    """Enriched prompts maintain correct structure."""

    def test_base_prompt_preserved(self, function_node):
        """Original prompt text must appear unchanged."""
        enricher = GnieEnricher(CapabilityTier.SMALL)
        base = "You are agent for node 'reason'. Answer: What does this do?"
        result = enricher.enrich(base, function_node, "query")
        assert base in result

    def test_enrichment_prepended(self, function_node):
        """Enrichment appears BEFORE base prompt."""
        enricher = GnieEnricher(CapabilityTier.SMALL)
        base = "ORIGINAL_PROMPT_MARKER"
        result = enricher.enrich(base, function_node, "query")
        enrichment_end = result.index("ORIGINAL_PROMPT_MARKER")
        assert enrichment_end > 0  # Something before the marker

    def test_neighbor_types_sorted_by_count(self, hub_node):
        """Neighbor types should be sorted by count (most frequent first)."""
        enricher = GnieEnricher(CapabilityTier.SMALL)
        result = enricher.enrich("Base", hub_node, "query")
        # Function(20) should appear before Class(8)
        func_pos = result.index("Function")
        class_pos = result.index("Class")
        assert func_pos < class_pos

    def test_max_five_neighbor_types(self):
        """Only top 5 neighbor types shown."""
        node = NodeContext(
            node_id="x", node_type="X", label="x", description="x",
            neighbor_count=100,
            neighbor_types={
                "A": 20, "B": 15, "C": 10, "D": 8, "E": 5, "F": 3, "G": 1,
            },
        )
        enricher = GnieEnricher(CapabilityTier.SMALL)
        result = enricher.enrich("Base", node, "query")
        assert "F" not in result or "3 F" not in result  # 6th type excluded
        assert "G" not in result or "1 G" not in result  # 7th type excluded


# ─── Route Tests: for_model factory ───


class TestForModelFactory:
    """GnieEnricher.for_model() correctly creates enricher for model name."""

    def test_small_model(self):
        enricher = GnieEnricher.for_model("qwen2.5:3b")
        assert enricher.tier == CapabilityTier.SMALL

    def test_medium_model(self):
        enricher = GnieEnricher.for_model("deepseek-r1:7b")
        assert enricher.tier == CapabilityTier.MEDIUM

    def test_large_model(self):
        enricher = GnieEnricher.for_model("gemma4:31b")
        assert enricher.tier == CapabilityTier.LARGE


# ─── Unit Tests: Synthesis enrichment ───


class TestSynthesisEnrichment:

    def test_includes_agent_count(self):
        enricher = GnieEnricher(CapabilityTier.SMALL)
        result = enricher.enrich_synthesis("Synthesize:", agent_count=12)
        assert "12" in result

    def test_includes_task_type(self):
        enricher = GnieEnricher(CapabilityTier.SMALL)
        result = enricher.enrich_synthesis("Synthesize:", agent_count=5, task_type="PREDICT")
        assert "PREDICT" in result

    def test_small_gets_detailed_instructions(self):
        enricher = GnieEnricher(CapabilityTier.SMALL)
        result = enricher.enrich_synthesis("Synthesize:", agent_count=5)
        assert "agreement" in result.lower()
        assert "contradictions" in result.lower()

    def test_large_no_detailed_instructions(self):
        enricher = GnieEnricher(CapabilityTier.LARGE)
        result = enricher.enrich_synthesis("Synthesize:", agent_count=5)
        assert "agreement" not in result.lower()

    def test_base_prompt_preserved(self):
        enricher = GnieEnricher(CapabilityTier.MEDIUM)
        result = enricher.enrich_synthesis("ORIGINAL_SYNTH_PROMPT", agent_count=3)
        assert "ORIGINAL_SYNTH_PROMPT" in result
