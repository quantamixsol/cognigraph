"""Neo4j connector — production graph database integration."""

from __future__ import annotations

import logging
from typing import Any

from cognigraph.connectors.base import BaseConnector

logger = logging.getLogger("cognigraph.connectors.neo4j")


class Neo4jConnector(BaseConnector):
    """Load graph data from a Neo4j database.

    Requires: pip install cognigraph[neo4j]

    Supports custom Cypher queries for flexible graph extraction.
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "",
        database: str = "neo4j",
        node_query: str | None = None,
        edge_query: str | None = None,
    ) -> None:
        self._uri = uri
        self._username = username
        self._password = password
        self._database = database
        self._driver = None

        # Custom Cypher queries (or defaults)
        self._node_query = node_query or (
            "MATCH (n) RETURN "
            "elementId(n) AS id, "
            "labels(n)[0] AS type, "
            "n.name AS label, "
            "n.description AS description, "
            "properties(n) AS properties"
        )
        self._edge_query = edge_query or (
            "MATCH (a)-[r]->(b) RETURN "
            "elementId(r) AS id, "
            "elementId(a) AS source, "
            "elementId(b) AS target, "
            "type(r) AS relationship, "
            "properties(r) AS properties"
        )

    def _get_driver(self):
        if self._driver is None:
            try:
                from neo4j import GraphDatabase
                self._driver = GraphDatabase.driver(
                    self._uri, auth=(self._username, self._password)
                )
            except ImportError:
                raise ImportError(
                    "Neo4j connector requires 'neo4j'. "
                    "Install with: pip install cognigraph[neo4j]"
                )
        return self._driver

    def load(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Load graph from Neo4j."""
        driver = self._get_driver()
        nodes: dict[str, Any] = {}
        edges: dict[str, Any] = {}

        with driver.session(database=self._database) as session:
            # Load nodes
            result = session.run(self._node_query)
            for record in result:
                nid = str(record["id"])
                props = dict(record.get("properties", {}))
                nodes[nid] = {
                    "label": record.get("label") or nid,
                    "type": record.get("type") or "Entity",
                    "description": record.get("description") or "",
                    "properties": props,
                }

            # Load edges
            result = session.run(self._edge_query)
            for record in result:
                eid = str(record["id"])
                props = dict(record.get("properties", {}))
                edges[eid] = {
                    "source": str(record["source"]),
                    "target": str(record["target"]),
                    "relationship": record.get("relationship") or "RELATED_TO",
                    "weight": props.pop("weight", 1.0),
                    "properties": props,
                }

        logger.info(f"Loaded {len(nodes)} nodes, {len(edges)} edges from Neo4j")
        return nodes, edges

    def validate(self) -> bool:
        try:
            driver = self._get_driver()
            driver.verify_connectivity()
            return True
        except Exception:
            return False

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None
