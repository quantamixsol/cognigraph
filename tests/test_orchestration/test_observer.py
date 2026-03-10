"""Tests for MasterObserver — transparency intelligence layer."""

import pytest

from cognigraph.core.message import Message
from cognigraph.core.types import ReasoningType
from cognigraph.orchestration.observer import MasterObserver


def _make_msg(node_id: str, content: str, confidence: float = 0.7,
              reasoning_type: ReasoningType = ReasoningType.ASSERTION) -> Message:
    return Message(
        source_node_id=node_id,
        target_node_id="broadcast",
        round=0,
        content=content,
        reasoning_type=reasoning_type,
        confidence=confidence,
        evidence=[node_id],
    )


@pytest.mark.asyncio
async def test_observer_disabled():
    """Disabled observer returns None and collects nothing."""
    obs = MasterObserver(enabled=False)
    result = await obs.observe_round("q", 0, {"n1": _make_msg("n1", "hello")})
    assert result is None
    report = obs.generate_report("q")
    assert report.total_rounds == 0


@pytest.mark.asyncio
async def test_conflict_detection_by_reasoning_type():
    """Detects conflicts when a node uses ReasoningType.CONTRADICTION."""
    obs = MasterObserver(detect_conflicts=True)
    msgs = {
        "n1": _make_msg("n1", "X is true", reasoning_type=ReasoningType.ASSERTION),
        "n2": _make_msg("n2", "X is false", reasoning_type=ReasoningType.CONTRADICTION),
    }
    await obs.observe_round("q", 0, msgs)
    report = obs.generate_report("q")
    assert report.conflict_count >= 1
    assert report.conflicts[0].severity == "high"


@pytest.mark.asyncio
async def test_conflict_detection_by_keywords():
    """Detects conflicts from keyword signals like 'contradict'."""
    obs = MasterObserver(detect_conflicts=True)
    msgs = {
        "n1": _make_msg("n1", "n2 is incorrect in saying tariffs are low"),
        "n2": _make_msg("n2", "Tariffs are low based on data"),
    }
    await obs.observe_round("q", 0, msgs)
    report = obs.generate_report("q")
    assert report.conflict_count >= 1
    assert report.conflicts[0].severity == "medium"


@pytest.mark.asyncio
async def test_anomaly_empty_response():
    """Detects empty/very short responses."""
    obs = MasterObserver(detect_anomalies=True, detect_conflicts=False)
    msgs = {"n1": _make_msg("n1", "ok")}
    await obs.observe_round("q", 0, msgs)
    report = obs.generate_report("q")
    assert report.anomaly_count >= 1
    assert report.anomalies[0].anomaly_type == "empty_response"


@pytest.mark.asyncio
async def test_anomaly_confidence_spike():
    """Detects large confidence changes between rounds."""
    obs = MasterObserver(detect_anomalies=True, detect_conflicts=False,
                         detect_patterns=False)
    # Round 0
    await obs.observe_round("q", 0, {
        "n1": _make_msg("n1", "Initial analysis of the topic at hand here.", confidence=0.3),
    })
    # Round 1: big spike
    await obs.observe_round("q", 1, {
        "n1": _make_msg("n1", "Now I am very confident about this topic.", confidence=0.9),
    })
    report = obs.generate_report("q")
    spikes = [a for a in report.anomalies if a.anomaly_type == "confidence_spike"]
    assert len(spikes) >= 1


@pytest.mark.asyncio
async def test_pattern_echo_chamber():
    """Detects echo chamber when nodes produce nearly identical output."""
    obs = MasterObserver(detect_patterns=True, detect_conflicts=False,
                         detect_anomalies=False)
    # Need round 0 first (patterns start at round >= 1)
    await obs.observe_round("q", 0, {
        "n1": _make_msg("n1", "setup round zero message here for initialization"),
        "n2": _make_msg("n2", "another setup message for round zero init"),
    })
    # Round 1: near-identical output
    same_text = "The regulatory framework requires compliance with GDPR articles 5 through 12 for data processing."
    await obs.observe_round("q", 1, {
        "n1": _make_msg("n1", same_text),
        "n2": _make_msg("n2", same_text),
    })
    report = obs.generate_report("q")
    echoes = [p for p in report.patterns if p.pattern_type == "echo_chamber"]
    assert len(echoes) >= 1


@pytest.mark.asyncio
async def test_pattern_dominance():
    """Detects when one node dominates with much higher confidence."""
    obs = MasterObserver(detect_patterns=True, detect_conflicts=False,
                         detect_anomalies=False)
    await obs.observe_round("q", 0, {
        "n1": _make_msg("n1", "I know this very well and here is my analysis.", confidence=0.95),
        "n2": _make_msg("n2", "Not sure about this topic area honestly.", confidence=0.3),
        "n3": _make_msg("n3", "My analysis is limited on this subject.", confidence=0.35),
    })
    await obs.observe_round("q", 1, {
        "n1": _make_msg("n1", "Reaffirming my strong position on this.", confidence=0.95),
        "n2": _make_msg("n2", "Still uncertain about the right answer here.", confidence=0.3),
        "n3": _make_msg("n3", "Leaning towards what n1 said but unsure.", confidence=0.35),
    })
    report = obs.generate_report("q")
    dom = [p for p in report.patterns if p.pattern_type == "dominance"]
    assert len(dom) >= 1
    assert "n1" in dom[0].involved_nodes


@pytest.mark.asyncio
async def test_report_per_round():
    """Returns per-round findings when configured."""
    obs = MasterObserver(report_per_round=True, detect_anomalies=True,
                         detect_conflicts=False)
    findings = await obs.observe_round("q", 0, {
        "n1": _make_msg("n1", "ok"),  # too short → anomaly
    })
    assert findings is not None
    assert any("ANOMALY" in f for f in findings)


@pytest.mark.asyncio
async def test_observer_report_health_score():
    """Health score penalizes conflicts and anomalies."""
    obs = MasterObserver()
    # Clean round
    await obs.observe_round("q", 0, {
        "n1": _make_msg("n1", "Good analysis with full reasoning and evidence provided.", confidence=0.8),
        "n2": _make_msg("n2", "Complementary analysis that adds new perspective.", confidence=0.75),
    })
    report = obs.generate_report("q")
    assert report.health_score > 0.8

    # Now add a conflict
    obs2 = MasterObserver()
    await obs2.observe_round("q", 0, {
        "n1": _make_msg("n1", "X is true", reasoning_type=ReasoningType.ASSERTION),
        "n2": _make_msg("n2", "X is false", reasoning_type=ReasoningType.CONTRADICTION),
    })
    report2 = obs2.generate_report("q")
    assert report2.health_score < report.health_score


@pytest.mark.asyncio
async def test_observer_reset():
    """Reset clears all state."""
    obs = MasterObserver()
    await obs.observe_round("q", 0, {
        "n1": _make_msg("n1", "test message for observer reset verification"),
    })
    obs.reset()
    report = obs.generate_report("q")
    assert report.total_rounds == 0
    assert report.total_messages == 0


@pytest.mark.asyncio
async def test_observer_report_to_summary():
    """to_summary() returns non-empty string."""
    obs = MasterObserver()
    await obs.observe_round("q", 0, {
        "n1": _make_msg("n1", "Some analysis on the topic of interest here."),
    })
    report = obs.generate_report("q")
    summary = report.to_summary()
    assert "Observer Report" in summary
    assert "Health" in summary


@pytest.mark.asyncio
async def test_observer_report_to_dict():
    """to_dict() returns serializable dict."""
    obs = MasterObserver()
    await obs.observe_round("q", 0, {
        "n1": _make_msg("n1", "Analysis content for dict serialization test."),
    })
    report = obs.generate_report("q")
    d = report.to_dict()
    assert "health_score" in d
    assert "contributions" in d
    assert isinstance(d["confidence_trajectory"], list)
