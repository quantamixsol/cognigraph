from cognigraph.connectors.base import BaseConnector
from cognigraph.connectors.networkx import NetworkXConnector
from cognigraph.connectors.json_graph import JSONGraphConnector

__all__ = ["BaseConnector", "NetworkXConnector", "JSONGraphConnector"]

def __getattr__(name: str):
    if name == "Neo4jConnector":
        from cognigraph.connectors.neo4j import Neo4jConnector
        return Neo4jConnector
    raise AttributeError(f"module 'cognigraph.connectors' has no attribute {name!r}")
