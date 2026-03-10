"""CogniGraph API server — FastAPI application.

Exposes CogniGraph reasoning as a REST API with streaming support.
Start with: `kogni serve` or `uvicorn cognigraph.server.app:create_app`

Production features:
- API key authentication (X-API-Key or Bearer token)
- Per-client rate limiting (token bucket)
- Request validation (query length, max_rounds, batch size)
- CORS middleware
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("cognigraph.server")


def create_app(
    config_path: str = "cognigraph.yaml",
    graph_path: str | None = None,
) -> Any:
    """Create the FastAPI application.

    Args:
        config_path: Path to cognigraph.yaml configuration
        graph_path: Path to graph JSON file (overrides config)

    Returns:
        FastAPI application instance
    """
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import StreamingResponse
    except ImportError:
        raise ImportError(
            "FastAPI not installed. Install with: pip install cognigraph[server]"
        )

    from cognigraph.__version__ import __version__
    from cognigraph.config.settings import CogniGraphConfig
    from cognigraph.core.graph import CogniGraph
    from cognigraph.backends.mock import MockBackend
    from cognigraph.server.middleware import (
        setup_auth_middleware,
        setup_rate_limit_middleware,
        MAX_QUERY_LENGTH,
        MAX_ROUNDS,
        MAX_BATCH_SIZE,
    )
    from cognigraph.server.models import (
        ReasonRequest,
        ReasonResponse,
        BatchReasonRequest,
        GraphInfoResponse,
        HealthResponse,
        StreamChunkResponse,
    )

    app = FastAPI(
        title="CogniGraph API",
        description="Graph-of-Agents reasoning engine",
        version=__version__,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth + rate limiting middleware
    setup_auth_middleware(app)
    setup_rate_limit_middleware(app)

    # State
    state: dict[str, Any] = {"graph": None, "config": None}

    @app.on_event("startup")
    async def startup() -> None:
        # Load config
        if Path(config_path).exists():
            state["config"] = CogniGraphConfig.from_yaml(config_path)
        else:
            state["config"] = CogniGraphConfig.default()

        # Load graph
        gpath = graph_path or "cognigraph.json"
        if Path(gpath).exists():
            state["graph"] = CogniGraph.from_json(gpath, config=state["config"])
            # Set mock backend as default (user should configure real one)
            state["graph"].set_default_backend(MockBackend())
            logger.info(f"Loaded graph from {gpath}: {len(state['graph'])} nodes")
        else:
            logger.warning(f"No graph file found at {gpath}")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        graph = state.get("graph")
        return HealthResponse(
            status="ok",
            version=__version__,
            graph_loaded=graph is not None,
            node_count=len(graph) if graph else 0,
        )

    @app.post("/reason", response_model=ReasonResponse)
    async def reason(request: ReasonRequest) -> ReasonResponse | StreamingResponse:
        graph = state.get("graph")
        if graph is None:
            raise HTTPException(status_code=503, detail="No graph loaded")

        # T63: Request validation
        if len(request.query) > MAX_QUERY_LENGTH:
            raise HTTPException(
                status_code=422,
                detail=f"Query too long ({len(request.query)} chars). Max: {MAX_QUERY_LENGTH}",
            )
        if request.max_rounds > MAX_ROUNDS:
            raise HTTPException(
                status_code=422,
                detail=f"max_rounds={request.max_rounds} exceeds limit of {MAX_ROUNDS}",
            )
        if request.node_ids:
            missing = [nid for nid in request.node_ids if nid not in graph.nodes]
            if missing:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown node IDs: {missing[:5]}",
                )

        if request.stream:
            return StreamingResponse(
                _stream_reason(graph, request),
                media_type="text/event-stream",
            )

        result = await graph.areason(
            request.query,
            max_rounds=request.max_rounds,
            strategy=request.strategy,
            node_ids=request.node_ids,
        )

        return ReasonResponse(
            answer=result.answer,
            confidence=result.confidence,
            rounds_completed=result.rounds_completed,
            node_count=result.node_count,
            cost_usd=result.cost_usd,
            latency_ms=result.latency_ms,
            metadata=result.metadata,
        )

    @app.post("/reason/batch")
    async def reason_batch(request: BatchReasonRequest) -> list[ReasonResponse]:
        graph = state.get("graph")
        if graph is None:
            raise HTTPException(status_code=503, detail="No graph loaded")

        # T63: Batch validation
        if len(request.queries) > MAX_BATCH_SIZE:
            raise HTTPException(
                status_code=422,
                detail=f"Batch too large ({len(request.queries)}). Max: {MAX_BATCH_SIZE}",
            )
        for i, q in enumerate(request.queries):
            if len(q) > MAX_QUERY_LENGTH:
                raise HTTPException(
                    status_code=422,
                    detail=f"Query [{i}] too long ({len(q)} chars). Max: {MAX_QUERY_LENGTH}",
                )
        if request.max_rounds > MAX_ROUNDS:
            raise HTTPException(
                status_code=422,
                detail=f"max_rounds={request.max_rounds} exceeds limit of {MAX_ROUNDS}",
            )

        results = await graph.areason_batch(
            request.queries,
            max_rounds=request.max_rounds,
            strategy=request.strategy,
            max_concurrent=request.max_concurrent,
        )

        return [
            ReasonResponse(
                answer=r.answer,
                confidence=r.confidence,
                rounds_completed=r.rounds_completed,
                node_count=r.node_count,
                cost_usd=r.cost_usd,
                latency_ms=r.latency_ms,
                metadata=r.metadata,
            )
            for r in results
        ]

    @app.get("/graph/stats", response_model=GraphInfoResponse)
    async def graph_stats() -> GraphInfoResponse:
        graph = state.get("graph")
        if graph is None:
            raise HTTPException(status_code=503, detail="No graph loaded")

        s = graph.stats
        return GraphInfoResponse(
            total_nodes=s.total_nodes,
            total_edges=s.total_edges,
            avg_degree=s.avg_degree,
            density=s.density,
            connected_components=s.connected_components,
            hub_nodes=s.hub_nodes,
        )

    @app.get("/nodes/{node_id}")
    async def get_node(node_id: str) -> dict:
        graph = state.get("graph")
        if graph is None:
            raise HTTPException(status_code=503, detail="No graph loaded")

        node = graph.nodes.get(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

        return {
            "id": node.id,
            "label": node.label,
            "type": node.entity_type,
            "description": node.description,
            "degree": node.degree,
            "properties": node.properties,
            "neighbors": graph.get_neighbors(node_id),
        }

    async def _stream_reason(graph: CogniGraph, request: ReasonRequest):
        """SSE generator for streaming reasoning."""
        async for chunk in graph.areason_stream(
            request.query,
            max_rounds=request.max_rounds,
            strategy=request.strategy,
            node_ids=request.node_ids,
        ):
            data = json.dumps(chunk.to_dict())
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"

    return app
