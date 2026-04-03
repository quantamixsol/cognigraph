<div align="center">

<img alt="GraQle — AI writes code. GraQle makes it safe." src="https://raw.githubusercontent.com/quantamixsol/graqle/master/assets/hero-dark-hq.png" width="800">

# AI writes code. Gra**Q**le makes it safe.

> **We ran Graqle on a 6-file "vibe coded" app. 90 seconds. 8 bugs. 4 of them invisible to pylint, mypy, flake8, and Copilot combined. One was a HIPAA violation. All fixed. Cost: $0.001.**

**The mandatory infrastructure layer between your AI code generators and production.**
Scan any codebase into a persistent knowledge graph. Every module becomes a reasoning agent.
Every change is impact-analysed, gate-checked, and taught back — automatically.

> *"Bugs don't live in files. They live between files. Every other tool sees one file at a time. Graqle sees the relationships."*

[![PyPI](https://img.shields.io/pypi/v/graqle?color=%2306b6d4&label=PyPI)](https://pypi.org/project/graqle/)
[![Downloads](https://img.shields.io/pypi/dw/graqle?color=%2306b6d4&label=downloads%2Fweek)](https://pypi.org/project/graqle/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-06b6d4.svg)](https://python.org)
[![Tests: 1,569+](https://img.shields.io/badge/tests-1%2C569%2B%20passing-06b6d4.svg)]()
[![LLM Backends: 14](https://img.shields.io/badge/LLM%20backends-14-06b6d4.svg)]()
[![MCP Tools: 74](https://img.shields.io/badge/MCP%20tools-74-06b6d4.svg)]()
[![Model Agnostic](https://img.shields.io/badge/model-agnostic-06b6d4.svg)]()
[![VS Code Extension](https://img.shields.io/badge/VS%20Code-v0.3.0-06b6d4.svg)](https://marketplace.visualstudio.com/items?itemName=graqle.graqle-vscode)

```bash
pip install graqle && graq scan repo . && graq run "find every security bug in this codebase"
```

[Website](https://graqle.com) · [VS Code Extension](https://marketplace.visualstudio.com/items?itemName=graqle.graqle-vscode) · [Dashboard](https://graqle.com/dashboard) · [PyPI](https://pypi.org/project/graqle/) · [Changelog](https://github.com/quantamixsol/graqle/blob/master/CHANGELOG.md)

<!-- mcp-name: io.github.quantamixsol/graqle -->

</div>

---

## What's New

### SDK v0.40.7

- **R15 Multi-Backend Debate** — optional multi-LLM debate mode: propose/challenge/synthesize across providers. 4 patent claims. Governance-first design.
- **graq_review dogfooding** — GraQle's own code review tool found 4 BLOCKERs + 3 MAJORs in the debate module that unit tests missed. All fixed.
- **OT-018 file reader fix** — `graq_read` no longer truncates files on Windows. Environment variable fallback for Windows Store Python.
- **3 live OpenAI debates** — full evidence report demonstrating cross-provider reasoning with GPT-5.4 vs Claude Sonnet 4.6.
- **14,959 node KG** — largest production graph to date.

### VS Code Extension v0.3.0

- **Credential Forwarding** — AWS, Anthropic, and OpenAI credentials forwarded securely via allowlist-only environment
- **Project-Scoping** — each workspace loads its own knowledge graph; workspace changes restart MCP with correct config
- **Error Surfacing** — backend errors surface as actionable messages instead of silent swallowing
- **Security Hardening** — `shell:false` on all subprocess spawns, CSP nonce on WebView, secret redaction in logs

[Install VS Code Extension](https://marketplace.visualstudio.com/items?itemName=graqle.graqle-vscode) | See the full [Changelog](https://github.com/quantamixsol/graqle/blob/master/CHANGELOG.md)

---

## The problem with AI coding at scale

Copilot writes auth logic. Cursor generates your API layer. Claude Code refactors your service layer. All of it ships fast. None of it is checked at the architectural level.

**Bugs don't live in files. They live between files.**

In a 6-file dental appointment system we built as a demo, every single tool — pylint, mypy, flake8, Copilot — missed 4 of the 8 bugs. Because those bugs only exist in the relationship between files:

- `app.py` assumed `services.py` checks auth on the cancel endpoint
- `services.py` assumed `app.py` already checked it
- Neither did
- Any unauthenticated HTTP client could cancel any patient's appointment

That is a HIPAA violation. That is what vibe coding at scale produces. That is what Graqle catches.

---

## The 90-second proof

```bash
# 1. Scan any codebase into a knowledge graph
graq scan repo .
# → 5,579 nodes, 19,916 edges — full architecture mapped in seconds

# 2. Ask Graqle to audit it
graq run "find every security vulnerability in this codebase"
# → Graph-of-agents activates across 50 nodes
# → Traces cross-file attack chain: MD5 (models.py) → expired tokens
#    never checked (auth.py) → cancel endpoint with zero auth (app.py)
# → Confidence: 89% | Evidence: 3-file chain | Cost: ~$0.001

# 3. Fix it — Graqle shows exact before/after for each file
# 4. Teach it back — the graph never forgets
graq learn "cancel endpoint must always require auth token"
# → Lesson persists. Every future audit knows this rule.
# → Copilot forgot. Graqle remembered.
```

**Dental audit results (live, AWS Bedrock, 2026-03-28):**

| Metric | Result |
|:-------|:-------|
| Files scanned | 6 (410 lines) |
| Bugs found | **8 (2 CRITICAL, 3 HIGH, 3 MEDIUM)** |
| Cross-file bugs (invisible to linters) | **4** |
| Reasoning confidence | **89–90%** |
| Fixes applied | **8/8** |
| Verification checks | **12/12 PASSED** |
| Total cost | **~$0.001** |

---

## What makes Graqle structurally different

Every other AI tool works at the **file level**. Graqle works at the **relationship level**.

<table>
<tr>
<td width="50%">

### The graph IS the reasoning architecture

Every node is simultaneously a knowledge entity AND a reasoning agent. The graph topology determines *who* reasons. Edge weights encode *what was learned*. Ontological constraints govern *what reasoning is permitted*. Results mutate the same graph that governs future reasoning.

**This is a closed developmental loop.** No stateless tool can replicate it without rebuilding the entire persistent typed graph layer from scratch.

</td>
<td width="50%">

### Cross-file bugs. Found automatically.

```
app.py ──imports──> services.py
    |                    |
    └──assumes auth──────┘
         checked here

Neither checks. Graqle sees both.
Copilot sees one file at a time.
```

The assumption gap between `app.py` and `services.py` is invisible to any single-file tool. Graqle maps the relationship, activates both as agents, and surfaces the contradiction at 89% confidence.

</td>
</tr>
<tr>
<td>

### Persistent architectural memory

```bash
graq learn "auth must be in services layer"
# Written to graph as weighted LESSON edge
# Survives git ops, session resets, team changes
# Every future audit activates this lesson
```

Lessons compound. The longer your team uses Graqle, the more it knows about your specific architecture, your specific past mistakes, your specific safety rules. That compounding is the moat.

</td>
<td>

### Governance gates before code is written

```bash
graq preflight "refactor the auth layer"
# → 12 modules depend on auth
# → 3 have no tests
# → 2 past lessons activated
# → LESSON: cancel endpoint must require auth
# → Risk: HIGH — proceed with plan
```

The gate runs before a single line changes. Not a linter rule. The graph reasoning about the specific change in the context of your specific architecture.

</td>
</tr>
</table>

---

## How it works

```
Your Code                    Knowledge Graph                AI Reasoning
┌──────────────┐            ┌───────────────────┐         ┌──────────────────────┐
│ Python       │ graq scan  │ 13 node types      │  query  │ Graph-of-Agents      │
│ TypeScript   │ ─────────> │ 10 edge types      │ ──────> │ PCST activation      │
│ Config       │            │ Weighted lessons   │         │ Multi-round reasoning │
│ Docs / APIs  │            │ Dependency chains  │         │ Confidence-scored    │
└──────────────┘            └───────────────────┘         │ Audit-trailed        │
                                      │                    └──────────────────────┘
                               graq learn / graq grow              │
                                      │                            ▼
                            Graph evolves with every      graq preflight / graq impact
                            interaction and lesson        Gate every change before it ships
```

**6-gate validation pipeline** — every scanned node passes: parse integrity → completeness repair → chunk quality → edge deduplication → relationship inference → compilation verification. Hollow nodes are auto-repaired, never silently dropped.

---

## Model agnostic. Works everywhere.

Graqle is not tied to any AI provider. The knowledge graph and reasoning architecture are completely decoupled from the backend. One line in `graqle.yaml` switches providers.

| Backend | Best For | Cost |
|:--------|:---------|:-----|
| **Ollama** | Fully offline, air-gapped, zero cost | $0 |
| **AWS Bedrock** | Enterprise IAM, your own account | AWS pricing |
| **Anthropic** | Deepest reasoning, Claude Opus | ~$0.001/q |
| **OpenAI** | Broad compatibility | ~$0.001/q |
| **Groq** | Sub-second responses | ~$0.0005/q |
| **DeepSeek / Mistral / Gemini / Together / Fireworks / Cohere / OpenRouter / vLLM / Custom** | Various | Various |

```yaml
# graqle.yaml — smart task routing
model:
  backend: bedrock
  model: eu.anthropic.claude-sonnet-4-6
  region: eu-north-1

routing:
  rules:
    - task: reason
      provider: bedrock
      model: eu.anthropic.claude-opus-4-6-v1
      profile: your-aws-profile    # uses your existing AWS credentials
    - task: context
      provider: groq               # fast lookups on cheap model
```

**Works with every AI IDE:** Claude Code, Cursor, VS Code + Copilot, Windsurf, JetBrains — zero workflow change. Graqle adds 74 architecture-aware MCP tools your AI uses automatically.

---

## What Graqle does that competitors cannot

| | Copilot / Cursor | LangChain / CrewAI | LlamaIndex | **Graqle** |
|:--|:--|:--|:--|:--|
| **Sees cross-file relationships** | No | No | No | **Yes — typed graph** |
| **Finds cross-file bugs** | No | No | No | **Yes — 4/8 dental bugs** |
| **Persistent architectural memory** | No — resets | No — stateless | No — stateless | **Yes — compounds** |
| **Blast radius before change** | No | No | No | **Yes — BFS traversal** |
| **Governance gate** | No | Prompt rules | No | **Yes — graph-enforced** |
| **Learns from every audit** | No | No | No | **Yes — edge weights** |
| **Works offline / air-gapped** | No | No | No | **Yes — Ollama** |
| **Self-improves over time** | No | No | No | **Yes — closed loop** |

**The structural reason competitors cannot copy this:** They are stateless. Graqle's moat is a persistent typed knowledge graph where topology governs agent activation, ontological constraints bound reasoning, edge weights encode institutional memory, and results mutate the same structure that governs future cognition. You cannot replicate this with prompt engineering. You have to rebuild the entire layer.

---

## Use cases

<details>
<summary><b>Auditing an existing production application</b></summary>

Point Graqle at any codebase. It scans in minutes. You get:
- Full blast radius for every file — what breaks if this changes
- Cross-file vulnerability chains traced across auth, business logic, data layers
- Architectural coupling violations and assumption gaps between modules
- Security issues: auth bypass, injection vectors, insecure crypto, data exposure
- All findings with confidence scores and file-level evidence

No prior knowledge of the codebase required. The graph maps it for you.

```bash
graq scan repo .
graq run "find every security vulnerability"
graq run "what are the highest-risk files to change?"
graq impact auth.py    # blast radius: what breaks if auth changes
```

</details>

<details>
<summary><b>Building a new application with AI</b></summary>

Every function you add gets mapped to the graph immediately. Before writing the next function, run preflight: the graph tells you what this will affect, whether something similar already exists, whether this introduces a circular dependency.

```bash
graq preflight "add payment processing to checkout service"
# → 6 modules will be affected
# → LESSON: payment module must never call user service directly
# → Similar function exists in billing.py — consider reusing
```

You build with architectural awareness that accumulates as you build. By the time you ship, the graph is a complete living specification.

</details>

<details>
<summary><b>Maintaining a legacy codebase</b></summary>

Legacy systems are where Graqle is most valuable. No single developer has the full picture. Assumptions are buried across dozens of files. A change to one module silently breaks five others.

The graph maps hidden dependencies explicitly. A new engineer gets full architectural context for any module in seconds. A senior engineer validates that a refactor is safe before touching a single line.

```bash
graq context legacy_payments.py     # 500-token focused context
graq impact legacy_payments.py      # what depends on this
graq lessons payment                # what went wrong here before
```

</details>

<details>
<summary><b>CI/CD governance gate</b></summary>

Every PR runs `graq preflight`. The gate produces a confidence score. Below threshold: blocked.

```yaml
# .github/workflows/graqle-gate.yml
- name: Graqle governance gate
  run: |
    graq predict "$(git diff HEAD~1 --stat | head -20)" \
      --confidence-threshold 0.80 \
      --fail-below-threshold
```

Architecture-aware quality control that scales across teams without requiring every reviewer to understand every subsystem.

</details>

---

## PR Guardian — governance checks on every pull request

Automated blast radius analysis for PRs. PR Guardian analyses your diff
against the project knowledge graph and reports **blast radius**,
a **governance verdict**, and a **status badge** — directly on the PR.

### GitHub Action

```yaml
# .github/workflows/graq-guardian.yml
name: PR Guardian
on: [pull_request]
permissions:
  contents: read
  pull-requests: write
jobs:
  guardian:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: graqle/pr-guardian@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

### CLI

```bash
# Analyse a diff locally
graq pr-guardian --diff <(git diff main...HEAD)

# JSON output for CI integration
graq pr-guardian --diff <(git diff main...HEAD) --output-format json
```

### What it shows

- **Blast radius** — how many downstream modules are affected by the change
- **Governance verdict** — pass or block, with actionable reasoning
- **PR badge** — shields.io-compatible SVG posted as a PR comment
- **SARIF output** — optional integration with GitHub Code Scanning

PR Guardian runs the same analysis locally and in CI, so developers
catch governance issues before review.

---

## 74 MCP tools — your AI uses them automatically

```bash
graq init          # Claude Code — auto-wires all 74 tools
graq init --ide cursor
graq init --ide vscode
graq init --ide windsurf
```

**Core reasoning tools (free):**

| Tool | What it does |
|:-----|:------------|
| `graq_reason` | Graph-of-agents reasoning — 50 nodes, multi-round, confidence-scored |
| `graq_impact` | Blast radius — BFS traversal through dependency graph |
| `graq_preflight` | Pre-change gate — lessons + safety boundaries + risk level |
| `graq_context` | 500-token focused context for any module |
| `graq_learn` | Teach the graph — lesson persists across sessions and teams |
| `graq_lessons` | Surface relevant past mistakes for current query |
| `graq_predict` | Confidence-gated prediction — writes back if threshold met |
| `graq_gate` | Binary governance gate — PASS / FAIL with evidence |
| `graq_inspect` | Graph stats, node details, health status |

**SCORCH — UX audit engine (12 dimensions):**

| Tool | What it does |
|:-----|:------------|
| `graq_scorch_audit` | Full 12-dimension UX friction audit with Claude Vision |
| `graq_scorch_behavioral` | 12 behavioral UX tests — zero AI cost |
| `graq_scorch_security` | CSP, XSS, exposed API keys, auth flow |
| `graq_scorch_a11y` | WCAG 2.1 accessibility |
| `graq_scorch_perf` | Core Web Vitals |
| `graq_scorch_conversion` | CTA + trust signals |
| `graq_scorch_mobile` | Touch targets + viewport |
| + 5 more | seo, brand, i18n, diff, report |

**Phantom — browser computer skills (8 tools):**

| Tool | What it does |
|:-----|:------------|
| `graq_phantom_browse` | Open any URL, screenshot + full DOM summary |
| `graq_phantom_click` | Click elements by text, selector, or coordinates |
| `graq_phantom_type` | Type into forms, inputs, search boxes |
| `graq_phantom_audit` | Run 10 audit dimensions on any live page |
| `graq_phantom_flow` | Execute multi-step user journeys with assertions |
| `graq_phantom_discover` | Auto-crawl all pages from a starting URL |
| `graq_phantom_screenshot` | Capture + optional Claude Vision analysis |
| `graq_phantom_session` | Session + auth profile management |

`graq_*` tools have `kogni_*` aliases for backwards compatibility. All 74 tools, zero license checks.

---

## Real results

<details>
<summary><b>Dental appointment system — 8 bugs in 90 seconds (live demo, 2026-03-28)</b></summary>

A 6-file, 410-line Flask dental appointment system. Bugs planted as a realistic "vibe coded" application would produce them.

**What every standard tool missed:**
- BUG-001 CRITICAL: `cancel()` in `app.py` — no auth. Traces through `app.py → services.py`. Neither file checks auth. Only visible as a relationship.
- BUG-002 CRITICAL: `search()` — unauthenticated. Empty query returns all patients. HIPAA violation.
- BUG-005 HIGH: Double-booking not prevented. `services.py` assumes `models.py` checks overlap. `models.py` assumes `services.py` does. Neither does. Only visible as a cross-file assumption gap.
- BUG-006 MEDIUM: `notifications.py` bypasses service layer entirely. Schema change in `models.py` silently breaks it.

**Graqle found all 8. 89–90% confidence. AWS Bedrock. 3 minutes.**

</details>

<details>
<summary><b>17,418 nodes, 8 audits, $0.30</b></summary>

Three repos merged into one knowledge graph. 8 parallel SCORCH audits across the entire surface. Found a CTA button that was 20px tall (44px minimum for mobile touch targets). Fixed before a single prospect saw it.

**Scale:** 17,418 nodes | 70,545 edges | 8 audits | Total cost: $0.30

</details>

<details>
<summary><b>Graqle scores itself — from 6.4 to 8.5 across 5 releases</b></summary>

Graqle uses Graqle to manage its own development. From v0.12.3 (6.4/10) to v0.29.9 (8.5/10) — every improvement guided by the knowledge graph's own intelligence layer. 1,569+ tests. 5,579 compiled nodes. Graph-powered development, by the graph.

This is not a demo feature. This is proof the tool works at the scale and complexity of real software.

</details>

---

## Full CLI reference

<details>
<summary><b>Scan & Build</b></summary>

| Command | Description |
|---------|-------------|
| `graq init` | Scan repo, build graph, auto-wire IDE |
| `graq scan repo .` | Scan codebase — 13 node types, 10 edge types, AST-level |
| `graq scan docs ./docs` | Ingest PDF, DOCX, PPTX, Markdown into graph |
| `graq compile` | Risk scores, insights, CLAUDE.md auto-injection |
| `graq verify` | Run all governance gate checks |
| `graq doctor` | Health check — graph integrity, backend, config |

</details>

<details>
<summary><b>Reason & Audit</b></summary>

| Command | Description |
|---------|-------------|
| `graq run "question"` | Natural language query — auto-routed to best tool |
| `graq reason "question"` | Multi-agent graph reasoning — confidence + evidence |
| `graq context module` | 500-token focused context for any module |
| `graq impact module` | BFS blast radius — what breaks if this changes |
| `graq preflight "change"` | Pre-change gate — lessons + risk + safety boundaries |
| `graq predict "query"` | Confidence-gated prediction with optional write-back |
| `graq lessons topic` | Past mistakes relevant to current query |

</details>

<details>
<summary><b>Teach & Learn</b></summary>

| Command | Description |
|---------|-------------|
| `graq learn "fact"` | Teach the graph — persists across sessions and teams |
| `graq learn node "name"` | Add a named node |
| `graq learn edge "A" "B"` | Add a typed relationship |
| `graq learned` | List everything the graph has been taught |
| `graq grow` | Incremental rescan (runs on git commit via hook) |

</details>

<details>
<summary><b>Cloud & Sync</b></summary>

| Command | Description |
|---------|-------------|
| `graq login --api-key <YOUR_API_KEY>` | Authenticate with Graqle cloud |
| `graq cloud push` | Push graph to S3 — team sync |
| `graq cloud pull --merge` | Pull graph from S3 — preserves local lessons |
| `graq studio` | Visual dashboard |
| `graq serve` | REST API server |
| `graq mcp serve` | MCP server — auto-discovered by Claude Code, Cursor, Windsurf |

</details>

<details>
<summary><b>SCORCH — UX Friction Auditing</b></summary>

| Command | Description |
|---------|-------------|
| `graq scorch run` | Full 12-dimension audit with Claude Vision |
| `graq scorch behavioral` | 12 behavioral UX tests — zero AI cost |
| `graq scorch a11y` | WCAG 2.1 accessibility |
| `graq scorch perf` | Core Web Vitals |
| `graq scorch security` | CSP, XSS, exposed keys |
| `graq scorch mobile` | Touch targets + viewport |
| `graq scorch conversion` | CTA + trust signals |
| `graq scorch seo` | SEO + Open Graph |
| `graq scorch brand` | Visual consistency |
| `graq scorch diff` | Before/after regression detection |

</details>

<details>
<summary><b>Phantom — Browser Automation</b></summary>

```bash
pip install graqle[phantom] && python -m playwright install chromium
```

| Command | Description |
|---------|-------------|
| `graq phantom browse URL` | Open browser, screenshot + DOM summary |
| `graq phantom audit URL` | 10-dimension audit on any live page |
| `graq phantom discover URL` | Auto-crawl all navigable pages |
| `graq phantom flow file.json` | Execute multi-step user journey |

Works on any website. Results feed back into the knowledge graph automatically.

</details>

---

## Pricing

| | Free ($0) | Pro ($19/mo) | Team ($29/dev/mo) | Enterprise (Custom) |
|:--|:--:|:--:|:--:|:--:|
| CLI + SDK + MCP | Unlimited | Unlimited | Unlimited | Unlimited |
| All 14 backends | ✅ | ✅ | ✅ | ✅ |
| Graph nodes | 500 | 25,000 | Unlimited | Unlimited |
| Cloud projects | 1 | 3 | Unlimited | Unlimited |
| SCORCH Vision | — | ✅ | ✅ | ✅ |
| Phantom Computer Skills | — | ✅ | ✅ | ✅ |
| Cross-project graphs | — | ✅ | ✅ | ✅ |
| Team shared graphs | — | — | ✅ | ✅ |
| SSO + audit logs | — | — | — | ✅ |
| On-premise deployment | — | — | — | ✅ |

**[Start free →](https://graqle.com)**

---

## Security & Privacy

- **Local by default.** All processing runs on your machine. No telemetry.
- **Your API keys.** LLM calls go directly to your provider — never proxied.
- **Cloud is opt-in.** Uploads graph structure only — never source code.
- **Air-gapped mode.** `GRAQLE_OFFLINE=1` — full functionality, zero network calls.

### Supply-chain integrity (v0.35.0+)

| Protection | What it does |
|-----------|-------------|
| **PyPI Trusted Publishing** | No long-lived API tokens — GitHub Actions OIDC only |
| **Sigstore signatures** | Every wheel signed; bundle on every GitHub Release |
| **CycloneDX SBOM** | Full bill of materials for every release |
| **pip-audit in CI** | CVE scan on every PR — blocks on CRITICAL/HIGH |
| **.pth file guard** | Blocks publish if wheel contains `.pth` files |
| **Reproducible builds** | `SOURCE_DATE_EPOCH` pinned — rebuild and compare checksums |

```bash
pip install "graqle[security]"
graq trustctl verify    # verify installed version against Sigstore
```

---

## FAQ

<details>
<summary><b>How is this different from Copilot / Cursor?</b></summary>

Copilot and Cursor are file-level tools. They see what is written in one file. Graqle sees the relationships between files — the dependency graph, the assumption chains, the blast radius of every change. They generate code. Graqle makes generated code safe to ship. They are not competitors. Graqle is the layer beneath them.

</details>

<details>
<summary><b>How is this different from LangChain or CrewAI?</b></summary>

LangChain and CrewAI are orchestration frameworks — they chain agents and prompts. They are stateless: no persistent graph, no accumulated institutional memory, no topology-governed agent activation. Graqle is the persistent typed knowledge substrate that agentic frameworks are missing. If you are building agents that write code, Graqle is the memory and governance layer your agents need underneath.

</details>

<details>
<summary><b>Does my code leave my machine?</b></summary>

Never. All graph processing is local. Cloud sync uploads graph structure only — never source code. Use `GRAQLE_OFFLINE=1` for fully air-gapped operation.

</details>

<details>
<summary><b>Can I use my own LLM / AWS account?</b></summary>

Yes. 14 backends. One line in `graqle.yaml` switches providers. AWS Bedrock uses your existing IAM profile — no new credentials needed. Ollama runs fully offline on your own GPU at zero cost.

</details>

<details>
<summary><b>How long does scanning take?</b></summary>

Under 30 seconds for most codebases. 10K+ file monorepos take 1–2 minutes. The graph persists — subsequent scans are incremental.

</details>

<details>
<summary><b>Why not just use static analysis?</b></summary>

Static analysis tells you what code exists. Graqle tells you how it connects, what breaks when it changes, what your team has learned about it, and what the blast radius of the next change will be. Static analysis is a search tool. Graqle is a reasoning architecture.

</details>

---

## Patent & License

European Patent Applications EP26162901.8 and EP26166054.2 — Quantamix Solutions B.V.
Phantom browser automation plugin: Copyright 2026 Quantamix Solutions B.V.
Free to use under the [license terms](https://github.com/quantamixsol/graqle/blob/master/LICENSE). See [SECURITY.md](https://github.com/quantamixsol/graqle/blob/master/SECURITY.md) for supply-chain documentation.

```bibtex
@article{kumar2026graqle,
  title   = {GraQle: Governed Intelligence through Graph-of-Agents Reasoning},
  author  = {Kumar, Harish},
  year    = {2026},
  institution = {Quantamix Solutions B.V.},
  url     = {https://github.com/quantamixsol/graqle}
}
```

---

<div align="center">

**Your AI generates code at 10x speed. Graqle makes sure it's safe to ship.**

```bash
pip install graqle && graq init
```

⭐ **[Star this repo](https://github.com/quantamixsol/graqle)** — it helps other developers find it.

Built by [Quantamix Solutions B.V.](https://quantamixsolutions.com) · Uithoorn, The Netherlands 🇳🇱

*Copilot forgot. Graqle remembered.*

</div>
