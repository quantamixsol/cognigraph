"""Message passing protocol — the core reasoning loop of CogniGraph."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from cognigraph.core.message import Message

if TYPE_CHECKING:
    from cognigraph.core.graph import CogniGraph

logger = logging.getLogger("cognigraph.message_passing")


class MessagePassingProtocol:
    """Synchronous round-based message passing between CogniNode agents.

    Protocol:
    Round 0: Query broadcast → each node produces initial reasoning
    Round 1..N: Neighbor exchange → each node re-reasons with neighbor context
    Final: Collect all outputs for aggregation

    This is the mechanism through which emergent reasoning occurs — insights
    that exist in NO single agent emerge from their interactions.
    """

    def __init__(self, parallel: bool = True) -> None:
        self.parallel = parallel

    async def run_round(
        self,
        graph: CogniGraph,
        query: str,
        active_node_ids: list[str],
        round_num: int,
        previous_messages: dict[str, Message] | None = None,
    ) -> dict[str, Message]:
        """Execute one round of message passing.

        Args:
            graph: The CogniGraph instance
            query: The original query
            active_node_ids: IDs of nodes participating in this round
            round_num: Current round number (0-based)
            previous_messages: Dict of node_id -> Message from previous round

        Returns:
            Dict of node_id -> Message produced this round
        """
        logger.debug(f"Round {round_num}: {len(active_node_ids)} active nodes")

        if round_num == 0:
            # Initial round — no neighbor context
            return await self._initial_round(graph, query, active_node_ids)

        # Subsequent rounds — gather neighbor messages and re-reason
        return await self._exchange_round(
            graph, query, active_node_ids, round_num, previous_messages or {}
        )

    async def _initial_round(
        self,
        graph: CogniGraph,
        query: str,
        active_node_ids: list[str],
    ) -> dict[str, Message]:
        """Round 0: Each node reasons independently about the query."""

        async def _node_reason(node_id: str) -> tuple[str, Message]:
            node = graph.nodes[node_id]
            query_msg = Message.create_query_broadcast(query, node_id)
            result = await node.reason(query, [query_msg])
            result.source_node_id = node_id
            result.round = 0
            return node_id, result

        if self.parallel:
            tasks = [_node_reason(nid) for nid in active_node_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            results = []
            for nid in active_node_ids:
                results.append(await _node_reason(nid))

        output: dict[str, Message] = {}
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Node reasoning failed: {r}")
                continue
            node_id, message = r
            output[node_id] = message

        logger.debug(f"Round 0 complete: {len(output)} nodes responded")
        return output

    async def _exchange_round(
        self,
        graph: CogniGraph,
        query: str,
        active_node_ids: list[str],
        round_num: int,
        previous_messages: dict[str, Message],
    ) -> dict[str, Message]:
        """Round N: Exchange messages with neighbors and re-reason."""

        async def _node_exchange(node_id: str) -> tuple[str, Message]:
            node = graph.nodes[node_id]

            # Gather messages from neighbors
            neighbor_ids = graph.get_neighbors(node_id)
            incoming = [
                previous_messages[nid]
                for nid in neighbor_ids
                if nid in previous_messages
            ]

            # Re-reason with neighbor context
            result = await node.reason(query, incoming)
            result.source_node_id = node_id
            result.round = round_num
            return node_id, result

        if self.parallel:
            tasks = [_node_exchange(nid) for nid in active_node_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            results = []
            for nid in active_node_ids:
                results.append(await _node_exchange(nid))

        output: dict[str, Message] = {}
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Node exchange failed: {r}")
                continue
            node_id, message = r
            output[node_id] = message

        logger.debug(
            f"Round {round_num} complete: {len(output)} nodes responded"
        )
        return output
