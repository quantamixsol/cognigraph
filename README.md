# CogniGraph — Graphs That Think

> Turn any knowledge graph into a distributed reasoning network where each node is an autonomous agent.

[![PyPI version](https://badge.fury.io/py/cognigraph.svg)](https://pypi.org/project/cognigraph/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

## What is CogniGraph?

CogniGraph is a **Graph-of-Agents (GoA)** SDK that transforms knowledge graphs into reasoning networks. Each node becomes an autonomous Small Language Model (SLM) agent that reasons locally, exchanges messages with neighbors, and collectively produces emergent insights that exist in *no single agent*.

**Key insight:** Traditional retrieval systems find information. CogniGraph *reasons* over it — using the structure of your knowledge graph as the topology for multi-agent debate, synthesis, and convergence.

## Install

```bash
# Core (CPU-only, local models)
pip install cognigraph

# With API backends (Anthropic, OpenAI, Bedrock, Ollama)
pip install cognigraph[api]

# With GPU acceleration (vLLM, LoRA adapters)
pip install cognigraph[gpu]

# Full stack (API + GPU + Neo4j + FastAPI server)
pip install cognigraph[all]

# Server only
pip install cognigraph[server]
```

## Quickstart

### 1. From Python

```python
from cognigraph import CogniGraph
from cognigraph.backends.api import AnthropicBackend

# Load a knowledge graph (NetworkX, JSON, or Neo4j)
graph = CogniGraph.from_json("my_graph.json")
graph.set_default_backend(AnthropicBackend(model="claude-haiku-4-5-20251001"))

# Reason over the graph
result = graph.reason("How does GDPR conflict with the AI Act?")

print(result.answer)       # Synthesized multi-agent answer
print(result.confidence)   # Aggregated confidence score
print(result.cost_usd)     # Total inference cost
```

### 2. Streaming

```python
async for chunk in graph.areason_stream("Explain Article 5 implications"):
    if chunk.chunk_type == "node_result":
        print(f"[{chunk.node_id}] {chunk.content[:80]}...")
    elif chunk.chunk_type == "final_answer":
        print(f"\nFinal: {chunk.content}")
```

### 3. Batch Processing

```python
results = await graph.areason_batch(
    ["Query 1", "Query 2", "Query 3"],
    max_concurrent=5,
)
```

### 4. CLI

```bash
# Run a query
kogni run --graph my_graph.json --query "What are the key conflicts?"

# Start API server
kogni serve --config cognigraph.yaml

# Benchmark performance
kogni bench --graph my_graph.json --queries queries.txt
```

## Configuration (YAML)

```yaml
model:
  backend: api
  model: claude-haiku-4-5-20251001

graph:
  connector: json
  # Or: connector: neo4j, uri: bolt://localhost:7687

activation:
  strategy: pcst          # Prize-Collecting Steiner Tree
  max_nodes: 16           # Only 4-16 relevant nodes activate

orchestration:
  max_rounds: 5           # Message-passing rounds
  convergence_threshold: 0.95
  aggregation: weighted_synthesis

observer:
  enabled: true           # MasterObserver watches all traffic
  detect_conflicts: true
  detect_anomalies: true

cost:
  budget_per_query: 0.05  # USD — halts if exceeded
  prefer_local: true
  fallback_to_api: true
```

## Architecture

```
Query → PCST Activation → Message Passing → Convergence → Aggregation → Answer
         (4-16 nodes)      (rounds 0..N)    (similarity)   (synthesis)
                                ↑
                          MasterObserver
                       (transparency layer)
```

1. **PCST Subgraph Activation** — Only query-relevant nodes activate (Prize-Collecting Steiner Tree)
2. **Message Passing** — Nodes reason independently, then exchange insights with neighbors
3. **Convergence Detection** — Stops when agent outputs stabilize (cosine similarity > threshold)
4. **Aggregation** — Weighted synthesis of all node perspectives into final answer
5. **MasterObserver** — Watches ALL inter-node traffic for conflicts, anomalies, and patterns

## Backends

| Backend | Model | Install |
|---------|-------|---------|
| Anthropic | Claude Haiku/Sonnet/Opus | `pip install cognigraph[api]` |
| OpenAI | GPT-4o / GPT-4o-mini | `pip install cognigraph[api]` |
| AWS Bedrock | Any Bedrock model | `pip install cognigraph[api]` |
| Ollama | Any local model | `pip install cognigraph[api]` |
| vLLM | GPU inference + LoRA | `pip install cognigraph[gpu]` |
| llama.cpp | CPU GGUF models | `pip install cognigraph[cpu]` |
| Mock | Testing | Built-in |

### Fallback Chain

```python
from cognigraph.backends.fallback import BackendFallbackChain

chain = BackendFallbackChain([
    AnthropicBackend(model="claude-haiku-4-5-20251001"),
    OpenAIBackend(model="gpt-4o-mini"),
    OllamaBackend(model="qwen2.5:0.5b"),
])
graph.set_default_backend(chain)
# Tries Anthropic → OpenAI → Ollama automatically
```

## REST API Server

```bash
# Start server (with optional API key auth)
COGNIGRAPH_API_KEY=my-secret kogni serve --port 8000

# Query
curl -X POST http://localhost:8000/reason \
  -H "X-API-Key: my-secret" \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain GDPR conflicts", "max_rounds": 3}'
```

**Endpoints:**
- `POST /reason` — Single query (sync or SSE streaming)
- `POST /reason/batch` — Batch queries
- `GET /health` — Health check
- `GET /graph/stats` — Graph statistics
- `GET /nodes/{id}` — Node details

**Production features:** API key auth, per-client rate limiting, request validation, CORS.

## TAMR+ Integration

CogniGraph is the **reasoning engine** that complements [TAMR+](https://tracegov.ai) (Topology-Aware Multi-Resolution Retrieval). Together they form a complete pipeline:

1. **TAMR+** builds and maintains the knowledge graph, performs adaptive retrieval
2. **CogniGraph** reasons over the retrieved subgraph using multi-agent message passing
3. Both share the **PCST algorithm** — TAMR+ for retrieval activation, CogniGraph for reasoning activation
4. TAMR+ **TRACE scores** feed into CogniGraph node priors; CogniGraph's **MasterObserver** monitors reasoning quality

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `No backend assigned` | Call `graph.set_default_backend(backend)` before reasoning |
| `ImportError: anthropic` | Install API extras: `pip install cognigraph[api]` |
| `Budget exceeded` | Increase `cost.budget_per_query` in config or use cheaper model |
| `No graph loaded` (server) | Ensure `cognigraph.json` exists in working directory |
| Slow convergence | Reduce `max_rounds` or increase `convergence_threshold` |

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Citation

```bibtex
@software{cognigraph2026,
  title={CogniGraph: Graph-of-Agents Distributed Reasoning SDK},
  author={CrawlQ AI},
  year={2026},
  url={https://github.com/crawlq-ai/cognigraph}
}
```
