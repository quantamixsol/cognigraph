"""CogniGraph — Graphs that think.

Turn any knowledge graph into a reasoning network where each node
is an autonomous agent powered by a model-agnostic backend.
"""

from cognigraph.__version__ import __version__
from cognigraph.core.graph import CogniGraph
from cognigraph.core.node import CogniNode
from cognigraph.core.edge import CogniEdge
from cognigraph.core.message import Message
from cognigraph.core.state import NodeState
from cognigraph.core.types import ReasoningType, NodeStatus, ReasoningResult

__all__ = [
    "__version__",
    "CogniGraph",
    "CogniNode",
    "CogniEdge",
    "Message",
    "NodeState",
    "ReasoningType",
    "NodeStatus",
    "ReasoningResult",
]
