"""Tests for AdaptiveActivation — adaptive Kmax based on query complexity."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cognigraph.activation.adaptive import (
    AdaptiveActivation,
    AdaptiveConfig,
    ComplexityProfile,
    QueryComplexityScorer,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scorer() -> QueryComplexityScorer:
    return QueryComplexityScorer()


@pytest.fixture
def activator() -> AdaptiveActivation:
    return AdaptiveActivation()


# ---------------------------------------------------------------------------
# 1. Simple query → low Kmax
# ---------------------------------------------------------------------------

def test_simple_query_low_kmax(activator: AdaptiveActivation) -> None:
    query = "What is GDPR?"
    profile, kmax = activator.analyze(query)
    assert profile.tier == "simple"
    assert kmax == 4


# ---------------------------------------------------------------------------
# 2. Complex query → high Kmax
# ---------------------------------------------------------------------------

def test_complex_query_high_kmax(activator: AdaptiveActivation) -> None:
    query = (
        "How does the AI Act affect GDPR and DORA compliance frameworks "
        "across multiple regulatory domains while considering both NIS2 "
        "and MiCA requirements? Compare and contrast the combined impact "
        "of these overlapping directives on supply chain obligations "
        "in addition to eIDAS standards and PSD2 interoperability."
    )
    profile, kmax = activator.analyze(query)
    assert profile.tier in ("complex", "expert")
    assert kmax >= 12


# ---------------------------------------------------------------------------
# 3. Moderate query → mid Kmax
# ---------------------------------------------------------------------------

def test_moderate_query_mid_kmax(activator: AdaptiveActivation) -> None:
    query = (
        "How does GDPR affect the compliance framework "
        "and regulatory standard requirements under DORA?"
    )
    profile, kmax = activator.analyze(query)
    assert profile.tier == "moderate"
    assert kmax == 8


# ---------------------------------------------------------------------------
# 4. Complexity profile — verify each dimension scores correctly
# ---------------------------------------------------------------------------

def test_complexity_profile_scores(scorer: QueryComplexityScorer) -> None:
    # Long query with multiple entities, conjunctions, and multi-hop patterns
    query = (
        "How does GDPR affect DORA and NIS2 compliance frameworks "
        "across multiple regulatory domains while considering "
        "both AI Act and MiCA requirements?"
    )
    profile = scorer.score(query)

    # Token score: query has ~20 tokens, should be above 0
    assert profile.token_score > 0.0

    # Entity score: GDPR, DORA, NIS2, AI Act, MiCA = 5 entities → capped at 1.0
    assert profile.entity_score >= 0.75

    # Conjunction score: "and", "while", "both...and" → multiple hits
    assert profile.conjunction_score > 0.0

    # Depth score: "how does X affect" + "across multiple" + "both X and Y"
    assert profile.depth_score > 0.0

    # Composite should be high
    assert profile.composite > 0.5


# ---------------------------------------------------------------------------
# 5. Custom config overrides
# ---------------------------------------------------------------------------

def test_custom_config() -> None:
    config = AdaptiveConfig(
        simple_nodes=2,
        moderate_nodes=6,
        complex_nodes=10,
        expert_nodes=20,
        token_low=5,
        token_high=30,
    )
    activator = AdaptiveActivation(config=config)

    # Simple query
    _, kmax_simple = activator.analyze("What is GDPR?")
    assert kmax_simple == 2

    # Complex query
    _, kmax_complex = activator.analyze(
        "How does GDPR affect DORA and NIS2 compliance across multiple "
        "regulatory frameworks while considering both AI Act and MiCA?"
    )
    assert kmax_complex >= 10


# ---------------------------------------------------------------------------
# 6. Tier classification — test all 4 tier boundaries
# ---------------------------------------------------------------------------

def test_tier_classification() -> None:
    # Simple: composite < 0.3
    p_simple = ComplexityProfile(
        token_score=0.0, entity_score=0.0,
        conjunction_score=0.0, depth_score=0.0,
    )
    assert p_simple.tier == "simple"
    assert p_simple.composite < 0.3

    # Moderate: 0.3 <= composite < 0.6
    p_moderate = ComplexityProfile(
        token_score=0.5, entity_score=0.5,
        conjunction_score=0.5, depth_score=0.3,
    )
    assert p_moderate.tier == "moderate"
    assert 0.3 <= p_moderate.composite < 0.6

    # Complex: 0.6 <= composite < 0.8
    p_complex = ComplexityProfile(
        token_score=0.8, entity_score=0.8,
        conjunction_score=0.7, depth_score=0.7,
    )
    assert p_complex.tier == "complex"
    assert 0.6 <= p_complex.composite < 0.8

    # Expert: composite >= 0.8
    p_expert = ComplexityProfile(
        token_score=1.0, entity_score=1.0,
        conjunction_score=1.0, depth_score=1.0,
    )
    assert p_expert.tier == "expert"
    assert p_expert.composite >= 0.8


# ---------------------------------------------------------------------------
# 7. activate() delegates to PCSTActivation with correct max_nodes
# ---------------------------------------------------------------------------

def test_activate_delegates_to_pcst(activator: AdaptiveActivation) -> None:
    mock_graph = MagicMock()
    expected_nodes = ["node_1", "node_2", "node_3"]

    with patch(
        "cognigraph.activation.adaptive.PCSTActivation"
    ) as MockPCST:
        mock_instance = MockPCST.return_value
        mock_instance.activate.return_value = expected_nodes

        query = "What is GDPR?"
        result = activator.activate(mock_graph, query)

    # Should have created PCSTActivation with kmax=4 (simple tier)
    MockPCST.assert_called_once()
    call_kwargs = MockPCST.call_args[1]
    assert call_kwargs["max_nodes"] == 4

    # Should have delegated activate call
    mock_instance.activate.assert_called_once_with(mock_graph, query)
    assert result == expected_nodes


# ---------------------------------------------------------------------------
# 8. last_profile and last_kmax are accessible after activate
# ---------------------------------------------------------------------------

def test_last_profile_stored(activator: AdaptiveActivation) -> None:
    # Before any call, last_profile is None
    assert activator.last_profile is None
    assert activator.last_kmax == 0

    mock_graph = MagicMock()

    with patch(
        "cognigraph.activation.adaptive.PCSTActivation"
    ) as MockPCST:
        mock_instance = MockPCST.return_value
        mock_instance.activate.return_value = ["n1", "n2"]

        activator.activate(mock_graph, "What is GDPR?")

    # After activate, last_profile and last_kmax should be set
    assert activator.last_profile is not None
    assert isinstance(activator.last_profile, ComplexityProfile)
    assert activator.last_profile.tier == "simple"
    assert activator.last_kmax == 4
