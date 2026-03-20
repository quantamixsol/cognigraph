# ADR-105: Streaming Intelligence & Quality Gate — The Strategic Shift

**Date:** 2026-03-15 | **Status:** ACCEPTED
**Author:** Harish Kumar, Quantamix Solutions B.V.

## Context

### The Bypass Problem

GraQle v0.26 provides 22 MCP tools for knowledge graph reasoning. In practice, every AI coding
tool (Claude Code, Cursor, Copilot, Windsurf) **bypasses GraQle** in favor of `grep`, `read`,
and `bash`. This is not a bug — it is rational behavior:

| Factor | grep/read | GraQle MCP |
|--------|-----------|------------|
| Latency | 50ms | 2-15s |
| Predictability | Deterministic | Non-deterministic (LLM) |
| Control | AI chooses what to query | AI must trust opaque tool |
| Training prior | Millions of examples | Zero examples |
| Failure mode | Graceful (empty result) | Timeout, error, irrelevant |

**Root cause:** GraQle is positioned as a tool the AI *may choose to call*. Any voluntary tool
competes on latency and reliability against built-in tools. GraQle loses both competitions.

### The Validation Problem

The current scan pipeline (`graq scan`) produces knowledge graphs with systemic quality gaps:

1. **Dropped chunks** — JS/TS functions lose chunks when line-range boundaries don't align
   with chunk boundaries. Fixed partially in v0.25.1 (`_inherit_chunks` 3-tier fallback) but
   only for Python and JS functions with explicit line ranges.
2. **Half-built relationships** — CALLS edges depend on AST call-site extraction. Complex
   patterns (dynamic dispatch, decorators, HOCs) produce incomplete edge sets.
3. **Hollow nodes** — Nodes pass `validate()` at 88% quality with zero chunks (LESSON-094:
   CrawlQ POC 291 empty descriptions → 22% confidence). The `graq audit` command catches
   this post-hoc but doesn't prevent it.
4. **Batch validation** — Coverage is checked AFTER full scan completes. A 5-minute scan on a
   large repo can produce an unusable graph, and the user doesn't know until the end.
5. **No incremental recovery** — If scan fails mid-way (timeout, OOM), all progress is lost.

### The Adoption Problem

Current `graq scan` workflow:

```
pip install graqle     →  graq scan repo .     →  wait 2-5 minutes  →  see result
                                                   (user leaves)
```

Developer tools live or die by **time to first value**. 2-5 minutes of waiting with no
visible progress kills adoption. The user closes the terminal and never returns.

### The TAMR+ Precedent

Quantamix's TAMR+ (TraceGov) platform solved an analogous problem in the regulatory domain:

- **Audit trails** — SHA-256 hash-chained, immutable, 7-year retention
- **TRACE scoring** — 5-pillar transparency scoring (Transparency, Reasoning, Auditability,
  Compliance, Explainability) for every AI decision
- **Evidence chains** — DocumentChunk → Entity → GovRequirement → GovControl, fully
  traversable in Neo4j
- **Semantic SHACL gates** — Framework fidelity, scope boundary, cross-reference integrity
  validation at reasoning time
- **Visual tools** — AuditTrailViewer, DecisionBox, ComplianceHeatmap, GovernanceReportBuilder

These patterns apply directly to development governance. The shift: regulatory requirements →
development constraints; compliance assessment → code quality gate; governance framework →
team engineering standards.

## Decision

### The "Q" in GraQle

Redefine the Q in GraQle from **Query** to **Quality Gate**.

```
GraQle = Graph + Quality Gate for development
```

Every code change passes through the Q — a 3-layer intelligence system that provides context
(Layer B), enables deep reasoning (Layer A), and enforces constraints (Layer C).

### Architecture: 3-Layer Quality Gate

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER B: Embedded Intelligence (0% bypass — AI reads files) │
│                                                               │
│  Intelligence injected INTO files the AI already reads:       │
│  • Inline headers in source files (bounded markers)           │
│  • Auto-generated CLAUDE.md / .cursorrules section            │
│  • Module risk map, dependency info, incident history          │
│                                                               │
│  AI reads the file → sees intelligence → makes better decision │
│  No tool call required. No latency added. Cannot be bypassed. │
├─────────────────────────────────────────────────────────────┤
│  LAYER A: Deep Reasoning (voluntary — for complex changes)    │
│                                                               │
│  graq_gate MCP tool reads pre-compiled intelligence packets.  │
│  Returns module context + impact radius + constraints in <500ms│
│  Escalates to multi-agent reasoning for 3+ module changes.    │
│                                                               │
│  Optional but compelling: faster than reading 15 files.       │
├─────────────────────────────────────────────────────────────┤
│  LAYER C: Enforcement (0% bypass — runs at commit/PR time)    │
│                                                               │
│  Pre-commit hook: graq verify --mode pre-commit               │
│  GitHub Action: graq verify --mode ci                         │
│  Checks impact radius, constraint compliance, KG staleness.  │
│                                                               │
│  AI cannot commit or merge without passing the quality gate.  │
└─────────────────────────────────────────────────────────────┘
```

**Bypass rates:**

| Layer | Bypass Rate | Why |
|-------|------------|-----|
| A alone (MCP tools) | 70-80% | Voluntary, fights training priors |
| B alone (inline intelligence) | 20-30% | AI reads files naturally |
| C alone (git hooks + CI) | 5-10% | Enforcement at commit/merge |
| **B + C together** | **3-5%** | Prevention + enforcement |
| **A + B + C together** | **1-2%** | Deep reasoning + prevention + enforcement |

### Architecture: Streaming Intelligence Pipeline

Replace the batch scan→compile pipeline with a streaming pipeline where each file scanned
immediately produces validated intelligence:

```
Traditional (batch):
  [scan all files ██████████████████] → validate → compile → done
  User waits ─────────────────────────────────────────────> value

Streaming:
  [file 1] → validate → emit packet → inject header → dashboard event
  [file 2] → validate → emit packet → inject header → dashboard event
  [file 3] → validate → emit packet → inject header → dashboard event
  User sees value ↑ from first file
```

### Architecture: Per-File Validation (The Quality Guarantee)

The critical design: validation is NOT a separate pass. It is FUSED into the per-file
processing step. No file exits the pipeline without passing validation.

```python
class FileIntelligenceUnit:
    """Atomic unit: one file's complete, validated intelligence.

    A file either produces a VALID FileIntelligenceUnit or it
    produces validation errors that are IMMEDIATELY surfaced and
    auto-repaired. Nothing passes through half-built.
    """
    file_path: str
    nodes: list[ValidatedNode]       # every node guaranteed: chunks, desc, edges
    edges: list[ValidatedEdge]       # every edge guaranteed: both endpoints exist
    module_packet: ModulePacket      # pre-compiled intelligence for this file
    coverage: CoverageReport         # chunk %, desc %, edge % for THIS file
    validation_status: Literal["PASS", "REPAIRED", "DEGRADED"]
```

#### The 6 Validation Gates (Per-File, Inline)

Every file passes through 6 sequential validation gates. If a gate fails, the pipeline
attempts auto-repair before moving to the next gate. No file exits without all 6 passing.

```
GATE 1: PARSE INTEGRITY
────────────────────────
  "Did we successfully parse this file?"

  Check: AST parsed (Python) or regex patterns matched (JS/TS)
  Fail mode: File marked as DEGRADED, raw-text chunking applied
  Auto-repair: Fall back to text-only chunking (guaranteed to produce chunks)

  GUARANTEE: Every file produces at least raw-text chunks.
  Current problem this solves: Files that fail AST parsing silently
  produce zero nodes.


GATE 2: NODE COMPLETENESS
──────────────────────────
  "Does every node have: label, type, description, ≥1 chunk?"

  Check per node:
    ✓ label is non-empty
    ✓ entity_type is a registered NODE_TYPE
    ✓ description length ≥ 30 chars
    ✓ chunks list is non-empty
    ✓ at least one chunk has text length ≥ 10 chars

  Auto-repair:
    - Missing description → synthesize from label + type + parent context
    - Missing chunks → apply _inherit_chunks (3-tier: strict → overlap → text match)
    - _inherit_chunks fails → synthesize chunk from description + file_path
    - Missing label → derive from file_path

  GUARANTEE: Zero hollow nodes. Every node has evidence.
  Current problem this solves: 88% validate() score with 0% chunks (LESSON-094).


GATE 3: CHUNK QUALITY
─────────────────────
  "Are chunks meaningful, not just boilerplate?"

  Check per chunk:
    ✓ text length ≥ 10 chars after stripping whitespace
    ✓ not 100% import statements (common failure: module chunks are just imports)
    ✓ chunk has type annotation (function, class, file, raw, etc.)
    ✓ chunk has line range if from source code (start_line, end_line)

  Auto-repair:
    - Import-only chunks → extend to include first non-import block
    - Missing type → infer from content (def/class/import patterns)
    - Missing line range → estimate from text position in file

  GUARANTEE: Every chunk has actionable content, not boilerplate.
  Current problem this solves: Module-level chunks containing only import
  statements, producing "this module imports X, Y, Z" reasoning.


GATE 4: EDGE INTEGRITY
──────────────────────
  "Do all edges connect existing nodes? Are relationships complete?"

  Check per edge:
    ✓ source node exists in current graph
    ✓ target node exists in current graph
    ✓ relationship is a registered EDGE_TYPE
    ✓ no self-loops
    ✓ no duplicate edges (same source, target, relationship)

  Auto-repair:
    - Dangling source/target → defer edge to pending queue (resolved when
      target file is scanned)
    - Unknown relationship → map to closest registered type
    - Duplicate edges → deduplicate, keep first

  Post-scan resolution:
    - Pending edges re-checked after all files scanned
    - Still-dangling edges → logged as warnings (cross-repo references)

  GUARANTEE: Zero dangling edges in final graph.
  Current problem this solves: IMPORTS edges pointing to unscanned files,
  CALLS edges referencing dynamic targets that don't exist as nodes.


GATE 5: RELATIONSHIP COMPLETENESS
──────────────────────────────────
  "Are expected relationships present?"

  Check per node:
    ✓ Module nodes have ≥1 CONTAINS edge (to functions/classes)
    ✓ Function nodes have ≥1 DEFINES edge (from parent module)
    ✓ Class nodes have DEFINES edges for their methods
    ✓ Import statements produced IMPORTS edges
    ✓ API decorators produced ROUTES_TO edges
    ✓ ORM models produced MODELS edges

  Auto-repair:
    - Missing CONTAINS → create from parent directory
    - Missing DEFINES → create from file-scope containment
    - Missing IMPORTS → re-scan import lines with regex fallback

  GUARANTEE: Structural relationships are complete.
  Current problem this solves: Functions defined inside classes not getting
  DEFINES edges, API endpoints without ROUTES_TO edges.


GATE 6: INTELLIGENCE COMPILATION
─────────────────────────────────
  "Can we produce a useful intelligence packet from this file?"

  Compile per file:
    ✓ Module packet with: consumers, dependencies, public interfaces
    ✓ Risk score (based on import count + edge degree)
    ✓ Inline intelligence header (ready to inject)

  Check:
    ✓ Module packet has ≥1 consumer OR ≥1 dependency (not isolated)
    ✓ Inline header is <500 bytes (won't bloat source files)

  GUARANTEE: Every file has an intelligence packet ready for Layer B injection.
  Current problem this solves: graq compile as separate step that can go stale.
```

#### Coverage Guarantee: The Running Scorecard

As each file passes through the 6 gates, the pipeline maintains a **running coverage
scorecard** that is displayed live and must meet thresholds before scan completes:

```
┌─ COVERAGE SCORECARD (live, updates per file) ──────────────┐
│                                                              │
│  Files scanned:     34/47 (72%)                             │
│  Parse success:     34/34 (100%) ✓                          │
│  Node completeness: 187/189 (98.9%) ✓  [2 auto-repaired]   │
│  Chunk coverage:    184/189 (97.4%) ✓  [5 synthesized]     │
│  Edge integrity:    412/415 (99.3%) ✓  [3 pending]         │
│  Relationship:      189/189 (100%) ✓                        │
│  Intelligence:      34/34 (100%) ✓                          │
│                                                              │
│  Health: HEALTHY   Quality: 97.8%                           │
│  Auto-repairs: 10   Degraded: 0   Warnings: 3              │
└──────────────────────────────────────────────────────────────┘
```

**Completion thresholds (configurable in graqle.yaml):**

| Metric | HEALTHY | WARNING | CRITICAL | Default |
|--------|---------|---------|----------|---------|
| Chunk coverage | ≥95% | ≥80% | <80% | 95% |
| Description coverage | ≥95% | ≥80% | <80% | 95% |
| Edge integrity | ≥99% | ≥95% | <95% | 99% |
| Parse success | ≥98% | ≥90% | <90% | 98% |

If scan completes below HEALTHY thresholds, `graq scan` exits with a warning and suggests
`graq audit --fix` for auto-repair of remaining issues.

### The 60-Second First Value Experience

The streaming pipeline is designed for viral adoption. The user must see value within
60 seconds of running `graq init`:

```
SECOND 0-3: Structural Analysis (instant — file listing only)
─────────────────────────────────────────────────────────────
  $ graq init

  ⚡ GraQle Quality Gate — initializing...

  Project shape: 47 Python files, 12 JS/TS, 3 configs
  Detected: Python package, CLI (typer), FastAPI, pytest (1,655 tests)

  [Already useful: user sees GraQle understands their project]


SECOND 3-10: Import Graph (fast — regex on imports only)
────────────────────────────────────────────────────────
  🔍 Dependency graph (import-level)...
    core/graph.py — imported by 14 modules (CRITICAL)
    config/settings.py — imported by 11 modules (HIGH)
    cli/commands/scan.py — imports 8 modules (HIGH complexity)

  CLAUDE.md intelligence section written ✓

  [Already useful: AI tools get module risk map on next session start]


SECOND 10-30: Progressive Deep Scan (streaming per file)
────────────────────────────────────────────────────────
  🧠 Deep scan (validated per file)...
    ✓ core/graph.py — 42 fns, 3 classes, 100% coverage  [header injected]
    ✓ config/settings.py — 14 classes, 100% coverage     [header injected]
    ✓ cli/commands/scan.py — 66 fns, 98% coverage        [2 auto-repaired]
    ⟳ activation/chunk_scorer.py — scanning...

  Progress: ████████░░░░░░░░ 12/47 files
  📡 Dashboard: http://localhost:8077/intelligence

  [Already useful: graq_gate works for scanned modules]


SECOND 30-60: Intelligence Compilation + Remaining Files
────────────────────────────────────────────────────────
  📦 Intelligence compiled for 47 modules
  ✓ Impact matrix: cross-module dependencies computed
  ✓ Inline headers injected in 47 files
  ✓ CLAUDE.md section updated with full module map
  ✓ graq_gate ready

  Coverage: 97.8% chunks, 99.1% descriptions, 99.5% edges
  Health: HEALTHY

  ⚡ Quality Gate active.
```

**Scan priority order:** Most-imported files first. The top 10 most-connected modules scan
in the first 10 seconds, providing ~80% of intelligence value.

**Budget model:** If deep scan exceeds 60 seconds (large repos), stop and emit partial
intelligence. Print: "Core intelligence ready. Run `graq compile --full` for complete
analysis (runs in background)."

### Intelligence Outputs (What `graq compile` Produces)

```
.graqle/
├── intelligence/
│   ├── modules/                    # Layer A: per-module packets
│   │   ├── core__graph.json
│   │   ├── cli__commands__scan.json
│   │   ├── activation__chunk_scorer.json
│   │   └── ...
│   ├── impact_matrix.json          # "if X changes, Y breaks"
│   ├── constraint_registry.json    # active governance rules
│   ├── incident_index.json         # past failures by module
│   └── module_index.json           # master index
│
├── headers/                        # Layer B: pre-generated headers
│   ├── core__graph.txt             # ready to inject into source
│   └── ...
│
├── hooks/                          # Layer C: git hook scripts
│   ├── pre-commit
│   └── prepare-commit-msg
│
└── scorecard.json                  # latest validation scorecard
```

**Module packet format:**

```json
{
  "module": "graqle.activation.chunk_scorer",
  "files": ["graqle/activation/chunk_scorer.py"],
  "node_count": 12,
  "public_interfaces": [
    {"name": "ChunkScorer", "type": "Class"},
    {"name": "ChunkScorer.activate", "type": "Function"},
    {"name": "ChunkScorer.score", "type": "Function"}
  ],
  "consumers": [
    {"module": "graqle.core.graph", "via": "IMPORTS"},
    {"module": "graqle.cli.commands.scan", "via": "IMPORTS"}
  ],
  "dependencies": [
    {"module": "graqle.activation.embeddings", "via": "IMPORTS"},
    {"module": "numpy", "type": "external"}
  ],
  "risk_score": 0.65,
  "risk_level": "MEDIUM",
  "impact_radius": 4,
  "chunk_coverage": 100.0,
  "constraints": [],
  "incidents": [],
  "last_compiled": "2026-03-15T14:32:00Z"
}
```

**Inline intelligence header format (Layer B):**

```python
# ── graqle:intelligence ──────────────────────────────────────
# module: graqle.activation.chunk_scorer
# risk: MEDIUM (impact radius: 4 modules)
# consumers: core.graph, cli.commands.scan
# dependencies: activation.embeddings, numpy
# constraints: none
# incidents: v0.25.0 chunk coverage regression (27.3% → fixed v0.25.1)
# ── /graqle:intelligence ─────────────────────────────────────
```

**CLAUDE.md auto-section format:**

```markdown
<!-- graqle:intelligence -->
## GraQle Quality Gate (auto-generated)

### Module Risk Map
| Module | Risk | Impact | Constraints |
|--------|------|--------|-------------|
| cli.commands.scan | HIGH | 8 | — |
| core.graph | HIGH | 12 | — |
| activation.chunk_scorer | MEDIUM | 4 | — |

### Recent Incidents
- v0.25.0: chunk coverage regression (27.3%) — strict containment in _inherit_chunks
- v0.25.0: f-string syntax error — nested brackets in Python 3.10 f-strings

### Quality Gate Status
Coverage: 97.8% | Health: HEALTHY | Last compiled: 2026-03-15
<!-- /graqle:intelligence -->
```

### AI Tool Auto-Detection

```python
AI_TOOL_SIGNATURES = {
    "claude": [Path("CLAUDE.md"), Path(".claude/")],
    "cursor": [Path(".cursorrules"), Path(".cursor/")],
    "copilot": [Path(".github/copilot-instructions.md")],
    "windsurf": [Path(".windsurfrules")],
    "codex": [Path(".codex/")],
}

def detect_ai_tools(root: Path) -> list[str]:
    """Auto-detect which AI tools this project uses."""
    tools = []
    for tool, markers in AI_TOOL_SIGNATURES.items():
        if any((root / m).exists() for m in markers):
            tools.append(tool)
    return tools or ["generic"]
```

`graq compile --inject` writes intelligence to the appropriate config file for each
detected AI tool. Zero user configuration required.

### Governance Layer (Mapped from TAMR+)

| TAMR+ Component | GraQle Equivalent | Purpose |
|-----------------|-------------------|---------|
| `audit_trail.py` (SHA-256 chain) | `governance/audit.py` | Immutable reasoning session logs |
| TRACE scoring (T+R+A+C+E) | DRACE scoring (D+R+A+C+E) | Per-session quality scoring |
| `evidence_chains.py` | `governance/evidence.py` | Decision → Agent → Evidence → Code |
| `semantic_shacl_gate.py` | `governance/scope_gate.py` | Scope boundary validation |
| AuditTrailViewer | ReasoningTrailViewer | Visual reasoning chain inspector |
| DecisionBox | ChangeApprovalBox | Human sign-off for high-risk changes |
| ComplianceHeatmap | GovernanceHeatmap | Module × governance coverage matrix |
| GovernanceReportBuilder | ChangeReportBuilder | Sprint-level governance report |

**DRACE Scoring:**

| Pillar | What It Measures | Score Source |
|--------|-----------------|-------------|
| **D** — Dependency | Did reasoning consider all impacted modules? | impact_matrix coverage |
| **R** — Reasoning | Was the reasoning chain deep and evidenced? | evidence chain depth |
| **A** — Auditability | Is the full decision trail recorded? | audit log completeness |
| **C** — Constraint | Were all governance rules checked? | constraint registry coverage |
| **E** — Explainability | Can a human understand why this decision was made? | reasoning clarity score |

### Studio Dashboard (Real-Time Intelligence)

`graq init` auto-starts the Studio dashboard at `http://localhost:8077/intelligence`:

```
┌─────────────────────────────────────────────────────────────┐
│  GRAQLE QUALITY GATE — project-name                          │
│                                                               │
│  ┌─ LIVE SCAN ──────────────┐  ┌─ MODULE MAP ──────────────┐ │
│  │ ████████████░░░ 72%      │  │      [core/graph]          │ │
│  │ 34/47 files              │  │       ↙  ↓  ↘             │ │
│  │ 187 functions            │  │    [cli] [act] [cfg]       │ │
│  │ 97.8% coverage           │  │     ↓     ↓               │ │
│  └──────────────────────────┘  │   [mcp] [embed]           │ │
│                                 └────────────────────────────┘ │
│  ┌─ VALIDATION SCORECARD ──────────────────────────────────┐ │
│  │ Parse:   ██████████ 100%  Chunks: █████████░ 97.8%      │ │
│  │ Edges:   █████████░ 99.3% Desc:   █████████░ 99.1%      │ │
│  │ Auto-repairs: 10  │  Degraded: 0  │  Health: HEALTHY    │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─ INTELLIGENCE FEED (live) ──────────────────────────────┐ │
│  │ [now]  scan.py: 66 functions, 8 deps. HIGH risk.        │ │
│  │ [2s]   graph.py: 42 functions, 14 consumers. CRITICAL.  │ │
│  │ [5s]   chunk_scorer.py: 12 fns, incident history found. │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─ REASONING TRAIL (when graq_gate is used) ──────────────┐ │
│  │ Session: "Modify auth middleware" — DRACE: 0.91          │ │
│  │ ▸ Gate 1: Context (142ms) — 12 nodes, 3 constraints     │ │
│  │ ▸ Gate 2: Reasoning (2.3s) — 2 rounds, convergence 0.96 │ │
│  │ ▸ Gate 3: Verification — pending                         │ │
│  └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

Updates in real-time via WebSocket. Nodes appear on the module map as they're scanned.
The scorecard fills in. The intelligence feed scrolls. This is the shareable screenshot
that drives viral adoption.

## Implementation Plan

### Phase 1: "The 60-Second Wow" (v0.27)

Build the streaming pipeline + dashboard. This is the viral adoption moment.

| Task | Component | Depends On |
|------|-----------|-----------|
| 1a | `graqle/intelligence/pipeline.py` — streaming per-file processor | — |
| 1b | `graqle/intelligence/validators.py` — 6 validation gates | — |
| 1c | `graqle/intelligence/compiler.py` — module packet generator | 1a |
| 1d | `graqle/intelligence/emitter.py` — output to all layers | 1c |
| 1e | Fast structural pass (file listing → project shape) | — |
| 1f | Import graph pass (regex imports → dependency map) | 1e |
| 1g | Priority scan order (most-imported first) | 1f |
| 1h | Studio WebSocket endpoint for live scan events | 1d |
| 1i | Studio intelligence dashboard page | 1h |
| 1j | `graq init` command (replaces raw `graq scan`) | 1a-1g |

**Evidence checkpoint:** Run `graq init` on GraQle SDK. Record the 60-second experience.
Show module packets, validation scorecard, dashboard screenshot. Demonstrate Claude Code
using intelligence headers in a real coding session.

### Phase 2: "The Intelligence Layer" (v0.27 continued)

Layer B: inject intelligence into files the AI already reads.

| Task | Component | Depends On |
|------|-----------|-----------|
| 2a | Inline intelligence header injection (`--inject`) | Phase 1 |
| 2b | Bounded marker system (graqle:intelligence / /graqle:intelligence) | 2a |
| 2c | CLAUDE.md auto-section generator | Phase 1 |
| 2d | AI tool auto-detection (Claude, Cursor, Copilot, Windsurf) | — |
| 2e | .cursorrules / copilot-instructions auto-section | 2c, 2d |
| 2f | `graq_gate` MCP tool (reads pre-compiled packets, <100ms) | Phase 1 |
| 2g | `graq compile --eject` (clean removal of all injections) | 2a, 2c |

**Evidence checkpoint:** Start a fresh Claude Code session on GraQle SDK. Compare reasoning
quality with and without intelligence headers. Document: "Claude read chunk_scorer.py, saw
the inline header, and immediately knew about the v0.25.0 incident without calling any tool."

### Phase 3: "The Quality Gate" (v0.28)

Layer C: enforcement at commit and PR time.

| Task | Component | Depends On |
|------|-----------|-----------|
| 3a | `graq verify` command (check changes against intelligence) | Phase 1 |
| 3b | Pre-commit hook generator (`graq compile --hooks`) | 3a |
| 3c | `graq unhook` command (clean removal) | 3b |
| 3d | GitHub Action template (`graqle-verify.yml`) | 3a |
| 3e | PR comment generator (impact analysis summary) | 3a |
| 3f | `graq learn` → incident memory integration | Phase 1 |
| 3g | `governance.yaml` schema + rule engine | — |
| 3h | `graq constrain` command (add/remove constraints) | 3g |

**Evidence checkpoint:** Make a real code change to GraQle SDK, commit, push PR. Show:
hook output with impact analysis, GitHub Action comment on PR, full governance loop.

### Phase 4: "The Transparency Layer" (v0.28 continued)

Governance visualization in Studio, mapped from TAMR+ patterns.

| Task | Component | Depends On |
|------|-----------|-----------|
| 4a | `governance/audit.py` — immutable reasoning session logs | Phase 3 |
| 4b | `governance/drace.py` — DRACE scoring engine | 4a |
| 4c | `governance/evidence.py` — decision chain builder | 4a |
| 4d | Studio: ReasoningTrailViewer component | 4a, 4c |
| 4e | Studio: GovernanceHeatmap component | Phase 2, 3g |
| 4f | Studio: ChangeApprovalBox component | 4a |
| 4g | Studio: ChangeReportBuilder (PDF/DOCX export) | 4a-4c |

**Evidence checkpoint:** Run a multi-module reasoning session on GraQle SDK. Show the full
reasoning trail in Studio — which nodes activated, what each agent said, how consensus was
reached, DRACE score, evidence chain. Export a change report.

### Phase 5: "The Protocol" (v0.29)

Universal Dev Governance Protocol specification.

| Task | Component | Depends On |
|------|-----------|-----------|
| 5a | DGP protocol specification (dgp/pre-change, dgp/reason, dgp/verify) | Phase 2, 3 |
| 5b | `graq_gate` as DGP endpoint | 5a |
| 5c | Reference templates for Cursor, Copilot, Windsurf | 2d, 5a |
| 5d | VS Code extension (governance gutter annotations) | 5a |
| 5e | `graq protocol serve` (HTTP DGP server for non-MCP tools) | 5a |

## Safety: Nothing Breaks

Every component is **additive only**. Nothing modifies existing scan, reasoning, or MCP behavior.

| Component | Adds | Modifies | Rollback |
|-----------|------|----------|----------|
| `.graqle/intelligence/` | New directory | Nothing | `rm -rf .graqle/intelligence/` |
| Inline headers | Comment blocks (bounded markers) | Nothing outside markers | `graq compile --eject` |
| CLAUDE.md section | Section (bounded markers) | Nothing outside markers | Remove between markers |
| `graq_gate` MCP tool | New tool | No existing tools | Remove from MCP config |
| Pre-commit hook | New file | Nothing | `graq unhook` |
| GitHub Action | New workflow file | Nothing | Delete the file |
| `governance.yaml` | New config file | Nothing | Delete the file |
| DRACE scoring | New module | Nothing | Don't import it |

**Existing test guarantee:** All 1,655+ existing tests must pass after each phase. The
streaming pipeline is tested by running `graq init` on GraQle SDK and verifying the
output matches or exceeds current `graq scan` quality.

## Consequences

### Positive

1. **Adoption**: 60-second first value transforms `graq init` from "wait and see" to
   "immediate wow." The live dashboard is the viral screenshot moment.

2. **Quality guarantee**: Per-file validation with 6 gates eliminates dropped chunks,
   hollow nodes, and dangling edges. Coverage is guaranteed by construction, not checked
   after the fact.

3. **AI tool independence**: Layer B (inline intelligence) works with ANY AI tool that
   reads source files — Claude, Cursor, Copilot, Windsurf, Codex, future tools. No MCP
   integration required for basic intelligence delivery.

4. **Bypass-proof**: Layer C (git hooks + CI) catches everything that Layers A and B miss.
   Combined bypass rate: 1-2%.

5. **Transparency**: TAMR+-grade audit trails and evidence chains for development decisions.
   Teams get full visibility into how AI made every change.

6. **Dogfooding**: GraQle SDK itself is the first proof case. Every claim is backed by
   evidence from the SDK's own codebase.

### Negative

1. **Inline headers add noise**: Developers may find intelligence comments distracting.
   Mitigation: `graq compile --no-inject` disables Layer B. Headers are also bounded by
   markers and collapsible in most editors.

2. **Hook friction**: Pre-commit hooks slow down the commit flow. Mitigation: advisory mode
   by default (warnings only, never blocks). `--strict` mode is opt-in.

3. **Stale intelligence**: If user modifies code without running `graq compile`, headers
   become stale. Mitigation: timestamp in headers, `graq verify` warns about staleness,
   git hook can auto-run `graq compile` on commit.

4. **Dashboard startup cost**: Studio requires FastAPI server. Mitigation: dashboard is
   optional. `graq init --no-dashboard` skips it. All intelligence outputs work without it.

5. **Complexity**: The streaming pipeline + 6 validation gates + 3 layers is significantly
   more complex than current batch scan. Mitigation: phased rollout, each phase independently
   valuable. Phase 1 alone (streaming + validation) improves scan quality without any
   intelligence layer.

## References

- **LESSON-094:** CrawlQ POC — 88% validate() with 0% chunks → 22% reasoning confidence
- **ADR-103:** Content-Aware PCST Activation (chunk-presence weighting)
- **ADR-104:** Query Reformulator (AI tool context integration)
- **TAMR+:** TraceGov governance architecture (audit trails, TRACE scoring, evidence chains)
- **v0.25.0 incidents:** Chunk regression (27.3%), f-string syntax error, multi-repo reasoning failure
- **v0.26.0 fixes:** Property-based activation fallback, `graq link infer`, max_nodes scaling
