# CogniGraph — Graphs That Think

> Turn any knowledge graph into a governed, self-improving reasoning network where each node is an autonomous agent.

[![PyPI version](https://badge.fury.io/py/cognigraph.svg)](https://pypi.org/project/cognigraph/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-332%20passing-brightgreen.svg)]()

## What is CogniGraph?

CogniGraph is a **Graph-of-Agents (GoA)** SDK with **13 innovations** that transforms knowledge graphs into governed reasoning networks. Each node becomes an autonomous language model agent that reasons locally, exchanges messages with neighbors, and collectively produces emergent insights — all under OWL+SHACL semantic governance.

**Key results:** Constrained F1 of **0.757** vs 0.328 for single-agent (+131%), with **99.7% governance accuracy** on MultiGov-30 benchmark.

## 13 Innovations

| # | Innovation | Module |
|---|-----------|--------|
| 1 | **PCST Activation** — sublinear subgraph selection | `cognigraph.activation.pcst` |
| 2 | **MasterObserver** — zero-cost transparency layer | `cognigraph.orchestration.observer` |
| 3 | **Convergent Message Passing** — similarity-based termination | `cognigraph.orchestration.convergence` |
| 4 | **Backend Fallback Chain** — heterogeneous inference with cost budgets | `cognigraph.backends.fallback` |
| 5 | **Hierarchical Aggregation** — centrality-based topology-aware synthesis | `cognigraph.orchestration.aggregation` |
| 6 | **SemanticSHACLGate** — 3-layer OWL-aware governance validation | `cognigraph.ontology.semantic_shacl_gate` |
| 7 | **Constrained F1** — joint answer quality + governance metric | `cognigraph.benchmarks.constrained_f1` |
| 8 | **OntologyGenerator** — automated OWL+SHACL from regulation text | `cognigraph.ontology.generator` |
| 9 | **Adaptive Activation** — dynamic Kmax from query complexity | `cognigraph.activation.adaptive` |
| 10 | **Online Graph Learning** — Bayesian edge weight updates | `cognigraph.learning.graph_learner` |
| 11 | **LoRA Auto-Selection** — per-entity adapter matching | `cognigraph.adapters.auto_select` |
| 12 | **TAMR+ Connector** — retrieval-to-reasoning pipeline | `cognigraph.connectors.tamr` |
| 13 | **MCP Plugin** — governed context engineering for Claude Code | `cognigraph.plugins.mcp_server` |

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

# Development
pip install cognigraph[dev]
```

## Quickstart

### Python

```python
from cognigraph import CogniGraph
from cognigraph.backends.api import AnthropicBackend

graph = CogniGraph.from_json("my_graph.json")
graph.set_default_backend(AnthropicBackend(model="claude-haiku-4-5-20251001"))

result = graph.reason("How does GDPR conflict with the AI Act?")
print(result.answer)
print(f"Cost: ${result.cost_usd:.4f}")
```

### Adaptive Activation

```python
from cognigraph.activation import AdaptiveActivation

activator = AdaptiveActivation()
profile, kmax = activator.analyze("How does GDPR affect DORA compliance?")
print(f"Tier: {profile.tier}, Kmax: {kmax}")  # moderate, 8
```

### Online Graph Learning

```python
from cognigraph.learning import GraphLearner, LearningConfig

learner = GraphLearner(graph, LearningConfig(learning_rate=0.1))
updates = learner.update_from_reasoning(node_messages)
# Edges between converging agents strengthened, diverging weakened
```

### TAMR+ Integration

```python
from cognigraph.connectors import TAMRConnector

connector = TAMRConnector()
subgraph = connector.load_from_json("tamr_output.json")
cogni_graph = connector.to_cognigraph(subgraph)
# TRACE scores automatically initialize PCST node priors
```

### MCP Plugin (Claude Code)

```bash
kogni mcp serve --graph knowledge_graph.json --port 8765
```

### CLI

```bash
kogni run --graph my_graph.json --query "What are the key conflicts?"
kogni serve --config cognigraph.yaml
```

## Architecture

```
Query → Adaptive PCST Activation → Agent Deployment → Message Passing → Convergence → Aggregation → Answer
              (4-16 nodes)                              (rounds 0..N)    (similarity)   (synthesis)
                                                              ↑                              ↓
                                                        MasterObserver              Online Graph Learning
                                                     (transparency layer)          (Bayesian weight updates)
```

## Backends

| Backend | Model | Install |
|---------|-------|---------|
| Anthropic | Claude Haiku/Sonnet/Opus | `pip install cognigraph[api]` |
| OpenAI | GPT-4o / GPT-4o-mini | `pip install cognigraph[api]` |
| AWS Bedrock | Any Bedrock model | `pip install cognigraph[api]` |
| Ollama | Any local model | `pip install cognigraph[api]` |
| vLLM | GPU inference + LoRA | `pip install cognigraph[gpu]` |
| llama.cpp | CPU GGUF models | `pip install cognigraph[cpu]` |

### Fallback Chain

```python
from cognigraph.backends.fallback import BackendFallbackChain

chain = BackendFallbackChain([
    AnthropicBackend(model="claude-haiku-4-5-20251001"),
    OllamaBackend(model="qwen2.5:0.5b"),
])
graph.set_default_backend(chain)  # Tries Anthropic → Ollama automatically
```

## Governance

The **SemanticSHACLGate** enforces 3-layer semantic governance:

1. **Framework Fidelity** — agents cite correct regulatory frameworks
2. **Scope Boundary** — responses stay within assigned domain
3. **Cross-Reference Integrity** — proper attribution for cross-framework mentions

Results on MultiGov-30: **99.7% governance accuracy** (FF: 100%, SB: 100%, CR: 98.3%).

## REST API

```bash
COGNIGRAPH_API_KEY=my-secret kogni serve --port 8000

curl -X POST http://localhost:8000/reason \
  -H "X-API-Key: my-secret" \
  -d '{"query": "Explain GDPR conflicts", "max_rounds": 3}'
```

## Patent & IP Notice

CogniGraph implements methods described in **European Patent Application EP26162901.8** (filed 6 March 2026, Quantamix Solutions B.V.). See [NOTICE](NOTICE) for details. Academic and research use is freely permitted.

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Citation

```bibtex
@article{kumar2026cognigraph,
  title={CogniGraph: Governed Intelligence through Graph-of-Agents Reasoning
         over Knowledge Graph Topologies with Semantic SHACL Validation},
  author={Kumar, Harish},
  year={2026},
  institution={Quantamix Solutions B.V.},
  note={European Patent Application EP26162901.8},
  url={https://github.com/quantamixsol/cognigraph}
}
```
