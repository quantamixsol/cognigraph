"""Orchestrator — controls the full message-passing reasoning process."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from cognigraph.config.settings import ObserverConfig, OrchestrationConfig
from cognigraph.core.message import Message
from cognigraph.core.types import ReasoningResult
from cognigraph.orchestration.aggregation import Aggregator
from cognigraph.orchestration.convergence import ConvergenceDetector
from cognigraph.orchestration.message_passing import MessagePassingProtocol
from cognigraph.orchestration.observer import MasterObserver

if TYPE_CHECKING:
    from cognigraph.core.graph import CogniGraph

logger = logging.getLogger("cognigraph.orchestrator")


class Orchestrator:
    """Controls the message-passing reasoning lifecycle.

    1. Receives a query + activated node list
    2. Runs message-passing rounds until convergence
    3. MasterObserver watches ALL traffic for transparency (if enabled)
    4. Aggregates final results
    5. Returns ReasoningResult with full provenance trace + observer report

    This is where emergent reasoning happens — the Orchestrator doesn't
    reason itself, it creates the CONDITIONS for emergence by managing
    the interaction protocol between node agents.
    """

    def __init__(
        self,
        config: OrchestrationConfig | None = None,
        message_protocol: MessagePassingProtocol | None = None,
        convergence_detector: ConvergenceDetector | None = None,
        aggregator: Aggregator | None = None,
        observer: MasterObserver | None = None,
        observer_config: ObserverConfig | None = None,
    ) -> None:
        config = config or OrchestrationConfig()
        self.config = config

        self.message_protocol = message_protocol or MessagePassingProtocol(
            parallel=not config.async_mode
        )
        self.convergence_detector = convergence_detector or ConvergenceDetector(
            max_rounds=config.max_rounds,
            min_rounds=config.min_rounds,
            similarity_threshold=config.convergence_threshold,
            confidence_threshold=config.confidence_threshold,
        )
        self.aggregator = aggregator or Aggregator(strategy=config.aggregation)

        # MasterObserver — optional transparency layer
        if observer is not None:
            self.observer = observer
        elif observer_config and observer_config.enabled:
            self.observer = MasterObserver(
                enabled=observer_config.enabled,
                report_per_round=observer_config.report_per_round,
                detect_conflicts=observer_config.detect_conflicts,
                detect_patterns=observer_config.detect_patterns,
                detect_anomalies=observer_config.detect_anomalies,
                use_llm_analysis=observer_config.use_llm_analysis,
            )
        else:
            self.observer = MasterObserver(enabled=False)

    async def run(
        self,
        graph: CogniGraph,
        query: str,
        active_node_ids: list[str],
        max_rounds: int | None = None,
    ) -> ReasoningResult:
        """Execute the full reasoning pipeline."""
        start_time = time.time()
        max_rounds = max_rounds or self.config.max_rounds

        logger.info(
            f"Starting reasoning: {len(active_node_ids)} nodes, "
            f"max {max_rounds} rounds"
        )

        # Reset convergence detector and observer
        self.convergence_detector.reset()
        self.convergence_detector.max_rounds = max_rounds
        self.observer.reset()

        # Cost budget enforcement
        cost_config = getattr(getattr(graph, "config", None), "cost", None)
        budget_limit = (
            cost_config.budget_per_query
            if cost_config and hasattr(cost_config, "budget_per_query")
            else float("inf")
        )
        cumulative_cost = 0.0

        # Message passing loop
        all_messages: list[dict[str, Message]] = []
        previous_messages: dict[str, Message] | None = None
        rounds_completed = 0
        per_round_observations: list[list[str]] = []
        budget_exceeded = False

        for round_num in range(max_rounds):
            # Run one round
            current_messages = await self.message_protocol.run_round(
                graph=graph,
                query=query,
                active_node_ids=active_node_ids,
                round_num=round_num,
                previous_messages=previous_messages,
            )

            all_messages.append(current_messages)
            rounds_completed = round_num + 1

            # Track cumulative cost per round
            round_tokens = sum(m.token_count for m in current_messages.values())
            round_cost_rate = 0.0001
            for nid in active_node_ids:
                node = graph.nodes[nid]
                if node.backend is not None:
                    round_cost_rate = node.backend.cost_per_1k_tokens / 1000
                    break
            cumulative_cost += round_tokens * round_cost_rate

            # Budget check — halt early with partial result
            if cumulative_cost >= budget_limit:
                logger.warning(
                    f"Cost budget exceeded: ${cumulative_cost:.4f} >= "
                    f"${budget_limit:.4f}. Halting after round {rounds_completed}."
                )
                budget_exceeded = True
                break

            # Observer watches this round
            round_obs = await self.observer.observe_round(
                query, round_num, current_messages, graph
            )
            if round_obs:
                per_round_observations.append(round_obs)
                logger.info(
                    f"Observer round {round_num}: {len(round_obs)} findings"
                )

            # Check convergence
            prev_list = (
                list(previous_messages.values()) if previous_messages else None
            )
            if self.convergence_detector.check(
                round_num + 1,
                list(current_messages.values()),
                prev_list,
            ):
                logger.info(f"Converged at round {rounds_completed}")
                break

            previous_messages = current_messages

        # Aggregate final answer
        final_messages = all_messages[-1] if all_messages else {}

        # Use the first available backend for aggregation
        agg_backend = None
        for nid in active_node_ids:
            node = graph.nodes[nid]
            if node.backend is not None:
                agg_backend = node.backend
                break

        answer = await self.aggregator.aggregate(
            query, final_messages, backend=agg_backend
        )

        # Compute cost
        total_tokens = sum(
            msg.token_count
            for round_msgs in all_messages
            for msg in round_msgs.values()
        )
        avg_cost = 0.0001  # default local cost
        if agg_backend:
            avg_cost = agg_backend.cost_per_1k_tokens / 1000
        cost_usd = total_tokens * avg_cost

        # Build message trace
        message_trace = [
            msg.to_dict()
            for round_msgs in all_messages
            for msg in round_msgs.values()
        ]

        # Compute confidence
        final_confidences = [m.confidence for m in final_messages.values()]
        avg_confidence = (
            sum(final_confidences) / len(final_confidences)
            if final_confidences
            else 0.0
        )

        elapsed_ms = (time.time() - start_time) * 1000

        # Generate observer report
        observer_report = None
        if self.observer.enabled:
            observer_report = self.observer.generate_report(query)
            logger.info(
                f"Observer: health={observer_report.health_score:.0%}, "
                f"conflicts={observer_report.conflict_count}, "
                f"anomalies={observer_report.anomaly_count}, "
                f"patterns={observer_report.pattern_count}"
            )

        # Build metadata
        metadata: dict = {
            "convergence_round": rounds_completed,
            "total_messages": len(message_trace),
            "total_tokens": total_tokens,
            "budget_exceeded": budget_exceeded,
            "cumulative_cost_usd": round(cumulative_cost, 6),
        }
        if observer_report:
            metadata["observer_report"] = observer_report.to_dict()
            metadata["observer_summary"] = observer_report.to_summary()
            metadata["health_score"] = observer_report.health_score
            cost_usd += observer_report.observer_cost_usd

        result = ReasoningResult(
            query=query,
            answer=answer,
            confidence=avg_confidence,
            rounds_completed=rounds_completed,
            active_nodes=active_node_ids,
            message_trace=message_trace,
            cost_usd=cost_usd,
            latency_ms=elapsed_ms,
            metadata=metadata,
        )

        logger.info(
            f"Reasoning complete: {rounds_completed} rounds, "
            f"{len(message_trace)} messages, {elapsed_ms:.0f}ms"
        )

        return result
