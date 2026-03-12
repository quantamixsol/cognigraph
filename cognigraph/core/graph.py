"""CogniGraph — the reasoning graph where every node is an agent."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

import networkx as nx

from cognigraph.config.settings import CogniGraphConfig
from cognigraph.core.edge import CogniEdge
from cognigraph.core.message import Message
from cognigraph.core.node import CogniNode
from cognigraph.core.state import NodeState
from cognigraph.core.types import (
    GraphStats,
    ModelBackend,
    NodeConfig,
    NodeStatus,
    ReasoningResult,
)

logger = logging.getLogger("cognigraph")


class CogniGraph:
    """The reasoning graph — a knowledge graph where every node is an agent.

    CogniGraph is the primary entry point for the SDK. It wraps a
    knowledge graph (from NetworkX, Neo4j, or other sources) and
    provides reasoning capabilities through distributed model agents.
    """

    def __init__(
        self,
        nodes: dict[str, CogniNode] | None = None,
        edges: dict[str, CogniEdge] | None = None,
        config: CogniGraphConfig | None = None,
    ) -> None:
        self.nodes: dict[str, CogniNode] = nodes or {}
        self.edges: dict[str, CogniEdge] = edges or {}
        self.config = config or CogniGraphConfig.default()
        self._default_backend: ModelBackend | None = None
        self._node_backends: dict[str, ModelBackend] = {}
        self._orchestrator: Any = None  # set lazily
        self._activator: Any = None  # set lazily
        self._nx_graph: nx.Graph | None = None

        # Mandatory quality gate: enrich + enforce descriptions
        if self.nodes:
            self._auto_enrich_descriptions()
            self._enforce_no_empty_descriptions()

    # --- Construction ---

    @classmethod
    def from_networkx(
        cls,
        G: nx.Graph,
        config: CogniGraphConfig | None = None,
        node_label_key: str = "label",
        node_type_key: str = "type",
        node_desc_key: str = "description",
        edge_rel_key: str = "relationship",
    ) -> CogniGraph:
        """Create a CogniGraph from a NetworkX graph."""
        nodes: dict[str, CogniNode] = {}
        edges: dict[str, CogniEdge] = {}

        # Build nodes
        for node_id, data in G.nodes(data=True):
            nid = str(node_id)
            props = {k: v for k, v in data.items()
                     if k not in (node_label_key, node_type_key, node_desc_key)}
            nodes[nid] = CogniNode(
                id=nid,
                label=data.get(node_label_key, nid),
                entity_type=data.get(node_type_key, "Entity"),
                description=data.get(node_desc_key, ""),
                properties=props,
            )

        # Build edges
        for i, (src, tgt, data) in enumerate(G.edges(data=True)):
            src_id, tgt_id = str(src), str(tgt)
            edge_id = f"e_{src_id}_{tgt_id}_{i}"
            rel = data.get(edge_rel_key, "RELATED_TO")
            weight = data.get("weight", 1.0)
            props = {k: v for k, v in data.items()
                     if k not in (edge_rel_key, "weight")}
            edge = CogniEdge(
                id=edge_id,
                source_id=src_id,
                target_id=tgt_id,
                relationship=rel,
                weight=weight,
                properties=props,
            )
            edges[edge_id] = edge
            nodes[src_id].outgoing_edges.append(edge_id)
            nodes[tgt_id].incoming_edges.append(edge_id)

        graph = cls(nodes=nodes, edges=edges, config=config)
        graph._nx_graph = G
        return graph

    @classmethod
    def from_json(cls, path: str, config: CogniGraphConfig | None = None) -> CogniGraph:
        """Create a CogniGraph from a JSON file."""
        import json
        from pathlib import Path

        data = json.loads(Path(path).read_text(encoding="utf-8"))
        G = nx.node_link_graph(data)
        return cls.from_networkx(G, config=config)

    # --- Node Enrichment & Validation ---

    def _enforce_no_empty_descriptions(self) -> None:
        """Enforce that no node has an empty description after enrichment.

        This is a mandatory quality gate. Nodes without descriptions produce
        agents that cannot reason, leading to low-confidence garbage answers.
        After auto-enrichment, any remaining empty nodes are a data quality
        issue that must be fixed by the KG builder.

        Raises:
            ValueError: If any nodes still have empty descriptions after
                auto-enrichment, listing the offending node IDs.
        """
        empty_nodes = [
            nid for nid, node in self.nodes.items()
            if not (node.description or "").strip()
        ]

        if empty_nodes:
            sample = empty_nodes[:10]
            remaining = len(empty_nodes) - len(sample)
            msg = (
                f"KG Quality Error: {len(empty_nodes)}/{len(self.nodes)} nodes have "
                f"empty descriptions. Agents cannot reason without descriptions.\n"
                f"Empty nodes: {sample}"
            )
            if remaining > 0:
                msg += f"\n... and {remaining} more"
            msg += (
                "\n\nFix: Add 'description' fields to your KG nodes. "
                "Example: {\"id\": \"svc::auth\", \"description\": \"Authentication "
                "service handling JWT tokens and session management\", ...}"
            )
            raise ValueError(msg)

    def _auto_enrich_descriptions(self) -> None:
        """Auto-generate descriptions for nodes that have empty descriptions.

        When a KG is loaded with nodes that have metadata/properties but no
        descriptions, the agents have nothing to reason from. This method
        synthesizes a description from all available node data so every agent
        has context.
        """
        enriched = 0
        empty_count = 0

        for nid, node in self.nodes.items():
            if node.description and node.description.strip():
                continue

            empty_count += 1
            parts = []

            # Start with type and label
            if node.entity_type and node.entity_type != "Entity":
                parts.append(f"[{node.entity_type}]")
            if node.label and node.label != nid:
                parts.append(node.label)

            # Add all properties as key-value context
            if node.properties:
                for key, val in node.properties.items():
                    if key in ("id", "label", "type", "description"):
                        continue
                    val_str = str(val)
                    if len(val_str) > 500:
                        val_str = val_str[:500] + "..."
                    if val_str:
                        parts.append(f"{key}: {val_str}")

            # Add edge context (what this node connects to)
            neighbors_out = []
            for eid in node.outgoing_edges:
                if eid in self.edges:
                    e = self.edges[eid]
                    target = self.nodes.get(e.target_id)
                    if target:
                        neighbors_out.append(
                            f"{e.relationship} -> {target.label or target.id}"
                        )
            neighbors_in = []
            for eid in node.incoming_edges:
                if eid in self.edges:
                    e = self.edges[eid]
                    source = self.nodes.get(e.source_id)
                    if source:
                        neighbors_in.append(
                            f"{source.label or source.id} -> {e.relationship}"
                        )

            if neighbors_out:
                parts.append(
                    "Connects to: " + "; ".join(neighbors_out[:5])
                )
            if neighbors_in:
                parts.append(
                    "Connected from: " + "; ".join(neighbors_in[:5])
                )

            if parts:
                node.description = ". ".join(parts)
                enriched += 1

        if empty_count > 0:
            pct = (empty_count / len(self.nodes)) * 100
            if pct > 50:
                logger.warning(
                    f"KG Quality Warning: {empty_count}/{len(self.nodes)} nodes "
                    f"({pct:.0f}%) had empty descriptions. Auto-enriched {enriched} "
                    f"from metadata/properties. For better reasoning quality, add "
                    f"rich descriptions to your nodes. See: "
                    f"https://cognigraph.dev/docs/kg-quality"
                )
            elif empty_count > 0:
                logger.info(
                    f"Auto-enriched {enriched}/{empty_count} nodes with "
                    f"empty descriptions from metadata."
                )

    def validate(self) -> dict:
        """Validate knowledge graph quality for reasoning.

        Returns a dict with quality metrics and warnings. Call this before
        reasoning to ensure your KG will produce good results.

        Returns:
            dict with keys: total_nodes, nodes_with_descriptions,
            nodes_without_descriptions, avg_description_length,
            warnings, quality_score (0-100)
        """
        total = len(self.nodes)
        with_desc = 0
        desc_lengths = []
        no_desc_ids = []

        for nid, node in self.nodes.items():
            desc = (node.description or "").strip()
            if desc and len(desc) > 20:
                with_desc += 1
                desc_lengths.append(len(desc))
            else:
                no_desc_ids.append(nid)

        avg_len = sum(desc_lengths) / len(desc_lengths) if desc_lengths else 0
        pct_with = (with_desc / total * 100) if total > 0 else 0

        warnings = []
        if pct_with < 50:
            warnings.append(
                f"CRITICAL: Only {pct_with:.0f}% of nodes have descriptions. "
                f"Agents will produce low-quality reasoning. Add descriptions "
                f"to your nodes or use auto-enrichment."
            )
        elif pct_with < 80:
            warnings.append(
                f"WARNING: {100 - pct_with:.0f}% of nodes lack descriptions. "
                f"Consider enriching them for better results."
            )

        if avg_len < 50 and avg_len > 0:
            warnings.append(
                f"WARNING: Average description length is only {avg_len:.0f} chars. "
                f"Richer descriptions (100+ chars) produce better reasoning."
            )

        # Quality score: 0-100
        score = min(100, int(
            (pct_with * 0.6) +
            (min(avg_len, 200) / 200 * 40)
        ))

        result = {
            "total_nodes": total,
            "total_edges": len(self.edges),
            "nodes_with_descriptions": with_desc,
            "nodes_without_descriptions": len(no_desc_ids),
            "avg_description_length": round(avg_len, 1),
            "quality_score": score,
            "warnings": warnings,
        }

        if warnings:
            for w in warnings:
                logger.warning(w)
        else:
            logger.info(
                f"KG quality: {score}/100 — {with_desc}/{total} nodes with "
                f"descriptions (avg {avg_len:.0f} chars)"
            )

        return result

    # --- Model Assignment ---

    def set_default_backend(self, backend: ModelBackend) -> None:
        """Set the default model backend for all nodes."""
        self._default_backend = backend

    def configure_nodes(self, configs: dict[str, NodeConfig]) -> None:
        """Configure per-node model assignments.

        Supports glob patterns: "art_5_*" matches all nodes starting with "art_5_".
        Use "*" for the default fallback.
        """
        import fnmatch

        for pattern, node_config in configs.items():
            if pattern == "*":
                if node_config.backend:
                    self._default_backend = node_config.backend
                continue

            for node_id, node in self.nodes.items():
                if fnmatch.fnmatch(node_id, pattern):
                    if node_config.backend:
                        self._node_backends[node_id] = node_config.backend
                    if node_config.adapter_id:
                        node.adapter_id = node_config.adapter_id
                    if node_config.system_prompt:
                        node.system_prompt = node_config.system_prompt
                    if node_config.max_tokens != 512:
                        node.max_tokens = node_config.max_tokens
                    if node_config.temperature != 0.3:
                        node.temperature = node_config.temperature

    def _get_backend_for_node(self, node_id: str) -> ModelBackend:
        """Get the model backend for a specific node."""
        if node_id in self._node_backends:
            return self._node_backends[node_id]
        if self._default_backend is not None:
            return self._default_backend
        raise RuntimeError(
            f"No backend assigned for node '{node_id}'. "
            "Call set_default_backend() or configure_nodes() first."
        )

    def assign_tiered_backends(
        self,
        hub_backend: ModelBackend,
        leaf_backend: ModelBackend,
        hub_threshold: int = 3,
    ) -> None:
        """Assign backends based on node connectivity (multi-tier model assignment).

        Hub nodes (degree > hub_threshold) get the stronger model.
        Leaf nodes get the faster model.
        """
        for node_id, node in self.nodes.items():
            if node.degree > hub_threshold:
                self._node_backends[node_id] = hub_backend
            else:
                self._node_backends[node_id] = leaf_backend
        # Set leaf as default fallback
        self._default_backend = leaf_backend

    # --- Reasoning ---

    def reason(
        self,
        query: str,
        *,
        max_rounds: int | None = None,
        strategy: str | None = None,
        node_ids: list[str] | None = None,
    ) -> ReasoningResult:
        """Run synchronous reasoning query (convenience wrapper)."""
        return asyncio.run(
            self.areason(
                query,
                max_rounds=max_rounds,
                strategy=strategy,
                node_ids=node_ids,
            )
        )

    async def areason(
        self,
        query: str,
        *,
        max_rounds: int | None = None,
        strategy: str | None = None,
        node_ids: list[str] | None = None,
    ) -> ReasoningResult:
        """Run async reasoning query — the core entry point."""
        from cognigraph.orchestration.orchestrator import Orchestrator

        max_rounds = max_rounds or self.config.orchestration.max_rounds
        strategy = strategy or self.config.activation.strategy

        # 1. Activate subgraph
        if node_ids is None:
            node_ids = self._activate_subgraph(query, strategy)

        # 2. Assign backends to activated nodes
        for nid in node_ids:
            backend = self._get_backend_for_node(nid)
            self.nodes[nid].activate(backend)

        # 3. Run orchestrator (with MasterObserver if configured)
        if self._orchestrator is None:
            # Create SkillAdmin with hybrid scoring (Titan V2 preferred)
            skill_admin = None
            try:
                from cognigraph.ontology.skill_admin import SkillAdmin
                # SkillAdmin auto-initializes Titan V2 -> sentence-transformers -> regex
                skill_admin = SkillAdmin(use_titan=True)
            except Exception:
                try:
                    from cognigraph.ontology.skill_admin import SkillAdmin
                    skill_admin = SkillAdmin(use_titan=False)
                except Exception:
                    pass

            self._orchestrator = Orchestrator(
                config=self.config.orchestration,
                observer_config=self.config.observer,
                skill_admin=skill_admin,
            )

        result = await self._orchestrator.run(self, query, node_ids, max_rounds)

        # 4. Deactivate nodes
        for nid in node_ids:
            self.nodes[nid].deactivate()

        # 5. Record metrics
        self._record_query_metrics(query, result, node_ids)

        return result

    async def areason_stream(
        self,
        query: str,
        *,
        max_rounds: int | None = None,
        strategy: str | None = None,
        node_ids: list[str] | None = None,
    ) -> AsyncIterator:
        """Stream reasoning results as they become available.

        Usage:
            async for chunk in graph.areason_stream("query"):
                print(chunk.content)
        """
        from cognigraph.orchestration.streaming import StreamingOrchestrator

        max_rounds = max_rounds or self.config.orchestration.max_rounds
        strategy = strategy or self.config.activation.strategy

        if node_ids is None:
            node_ids = self._activate_subgraph(query, strategy)

        for nid in node_ids:
            backend = self._get_backend_for_node(nid)
            self.nodes[nid].activate(backend)

        streamer = StreamingOrchestrator(self, max_rounds=max_rounds, strategy=strategy)
        async for chunk in streamer.stream(query, active_node_ids=node_ids):
            yield chunk

        for nid in node_ids:
            self.nodes[nid].deactivate()

    async def areason_batch(
        self,
        queries: list[str],
        *,
        max_rounds: int | None = None,
        strategy: str | None = None,
        max_concurrent: int = 5,
    ) -> list[ReasoningResult]:
        """Run multiple reasoning queries in parallel.

        Args:
            queries: List of queries to reason about
            max_concurrent: Max concurrent reasoning tasks

        Returns:
            List of ReasoningResult objects (one per query)
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _bounded_reason(q: str) -> ReasoningResult:
            async with semaphore:
                return await self.areason(
                    q, max_rounds=max_rounds, strategy=strategy
                )

        tasks = [_bounded_reason(q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final: list[ReasoningResult] = []
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Batch query failed: {r}")
                final.append(ReasoningResult(
                    answer=f"Error: {r}",
                    confidence=0.0,
                    rounds_completed=0,
                    node_count=0,
                    cost_usd=0.0,
                    latency_ms=0.0,
                ))
            else:
                final.append(r)
        return final

    def _record_query_metrics(
        self, query: str, result: ReasoningResult, node_ids: list[str]
    ) -> None:
        """Record query metrics for ROI tracking."""
        try:
            from cognigraph.metrics import get_metrics

            engine = get_metrics()

            # Start session if not active
            if not engine._session_active:
                engine.start_session()

            # Record the query — estimate result tokens from answer length
            result_tokens = len(result.answer) // 4  # ~4 chars per token
            engine.record_query(query, result_tokens)

            # Record node accesses
            for nid in node_ids:
                node = self.nodes.get(nid)
                label = node.label if node else nid
                tokens_returned = len(node.description) // 4 if node and node.description else 50
                engine.record_context_load(nid, tokens_returned)

            # Record graph stats
            from collections import Counter
            node_types = dict(Counter(n.entity_type for n in self.nodes.values()))
            edge_types = dict(Counter(e.relationship for e in self.edges.values()))
            engine.set_graph_stats(
                nodes=len(self.nodes),
                edges=len(self.edges),
                node_types=node_types,
                edge_types=edge_types,
            )

            # Record lessons applied (detect from answer content)
            import re
            lesson_refs = re.findall(r"LESSON[- ](\d+)", result.answer, re.IGNORECASE)
            for lesson_num in set(lesson_refs):
                engine.record_lesson_applied(
                    f"LESSON-{lesson_num}", query[:80]
                )

            # Record mistakes prevented (detect from answer content)
            mistake_refs = re.findall(r"MISTAKE[- ](\d+)", result.answer, re.IGNORECASE)
            for mistake_num in set(mistake_refs):
                engine.record_mistake_prevented(
                    f"MISTAKE-{mistake_num}", "detected-in-reasoning"
                )

            logger.debug(
                f"Metrics recorded: query tokens={result_tokens}, "
                f"nodes={len(node_ids)}, lessons={len(lesson_refs)}"
            )
        except Exception as e:
            logger.debug(f"Metrics recording skipped: {e}")

    def _activate_subgraph(self, query: str, strategy: str) -> list[str]:
        """Select nodes to activate for a query."""
        if strategy == "full":
            return list(self.nodes.keys())
        elif strategy == "manual":
            raise ValueError("Manual strategy requires explicit node_ids")
        elif strategy == "top_k":
            # Simple degree-based selection
            sorted_nodes = sorted(
                self.nodes.values(), key=lambda n: n.degree, reverse=True
            )
            k = min(self.config.activation.max_nodes, len(sorted_nodes))
            return [n.id for n in sorted_nodes[:k]]
        else:
            # PCST (default) — falls back to full if pcst_fast not available
            try:
                from cognigraph.activation.pcst import PCSTActivation

                if self._activator is None:
                    self._activator = PCSTActivation(
                        max_nodes=self.config.activation.max_nodes,
                        prize_scaling=self.config.activation.prize_scaling,
                        cost_scaling=self.config.activation.cost_scaling,
                    )
                return self._activator.activate(self, query)
            except ImportError:
                logger.warning("pcst_fast not installed, falling back to full activation")
                return list(self.nodes.keys())

    # --- Graph Operations ---

    def add_node(self, node: CogniNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node

    def add_edge(self, edge: CogniEdge) -> None:
        """Add an edge to the graph."""
        self.edges[edge.id] = edge
        if edge.source_id in self.nodes:
            self.nodes[edge.source_id].outgoing_edges.append(edge.id)
        if edge.target_id in self.nodes:
            self.nodes[edge.target_id].incoming_edges.append(edge.id)

    def get_neighbors(self, node_id: str) -> list[str]:
        """Get IDs of all neighbor nodes."""
        node = self.nodes[node_id]
        neighbors = set()
        for eid in node.outgoing_edges:
            neighbors.add(self.edges[eid].target_id)
        for eid in node.incoming_edges:
            neighbors.add(self.edges[eid].source_id)
        return list(neighbors)

    def get_edges_between(self, source_id: str, target_id: str) -> list[CogniEdge]:
        """Get all edges between two nodes."""
        return [
            e for e in self.edges.values()
            if (e.source_id == source_id and e.target_id == target_id)
            or (e.source_id == target_id and e.target_id == source_id)
        ]

    def get_incoming_edges(self, node_id: str) -> list[CogniEdge]:
        """Get all incoming edges for a node."""
        return [self.edges[eid] for eid in self.nodes[node_id].incoming_edges]

    def get_outgoing_edges(self, node_id: str) -> list[CogniEdge]:
        """Get all outgoing edges for a node."""
        return [self.edges[eid] for eid in self.nodes[node_id].outgoing_edges]

    def to_networkx(self) -> nx.Graph:
        """Export to NetworkX graph (preserves directed/undirected from source)."""
        if self._nx_graph is not None:
            return self._nx_graph

        G = nx.DiGraph()
        for nid, node in self.nodes.items():
            G.add_node(nid, label=node.label, type=node.entity_type,
                       description=node.description, **node.properties)
        for eid, edge in self.edges.items():
            G.add_edge(edge.source_id, edge.target_id,
                       relationship=edge.relationship, weight=edge.weight,
                       **edge.properties)
        return G

    # --- Inspection ---

    @property
    def stats(self) -> GraphStats:
        """Compute graph statistics."""
        G = self.to_networkx()
        degrees = [d for _, d in G.degree()]
        avg_deg = sum(degrees) / len(degrees) if degrees else 0.0

        # Find hub nodes (top 10% by degree)
        sorted_by_deg = sorted(
            self.nodes.values(), key=lambda n: n.degree, reverse=True
        )
        hub_count = max(1, len(sorted_by_deg) // 10)
        hubs = [n.id for n in sorted_by_deg[:hub_count]]

        return GraphStats(
            total_nodes=len(self.nodes),
            total_edges=len(self.edges),
            activated_nodes=sum(
                1 for n in self.nodes.values()
                if n.status != NodeStatus.IDLE
            ),
            avg_degree=avg_deg,
            density=nx.density(G) if len(G) > 1 else 0.0,
            connected_components=(
                nx.number_weakly_connected_components(G)
                if G.is_directed()
                else nx.number_connected_components(G)
            ),
            hub_nodes=hubs,
        )

    def __len__(self) -> int:
        return len(self.nodes)

    def __repr__(self) -> str:
        return (
            f"CogniGraph(nodes={len(self.nodes)}, edges={len(self.edges)}, "
            f"config={self.config.domain})"
        )
