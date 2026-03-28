# GraQle — AI writes code. GraQle makes it safe.

**The missing layer between your AI code generators and production.**

```bash
pip install graqle && graq scan repo . && graq run "find every security bug"
```

---

## What just happened

You pointed Graqle at a 6-file dental appointment system. 90 seconds later:

- **8 bugs found** — 2 CRITICAL, 3 HIGH, 3 MEDIUM
- **4 of them invisible** to pylint, mypy, flake8, and Copilot
- **89–90% confidence** — with cross-file evidence chains
- **8/8 fixed** — before/after diff for every file
- **Cost: ~$0.001**

The 4 invisible bugs weren't hard. They were in the *relationships* between files.

`app.py` assumed `services.py` checked auth on the cancel endpoint.
`services.py` assumed `app.py` already did it.
Neither did.
Any unauthenticated HTTP client could cancel any patient's appointment.

**That's a HIPAA violation. That's what vibe coding at scale produces. That's what Graqle catches.**

---

## Why your current tools miss this

Copilot sees one file. Cursor sees one file. pylint sees one file.

Graqle sees the **relationships between files** — the dependency graph, the assumption chains, the blast radius of every change. Bugs that only exist between files are invisible to single-file tools. They are exactly what production incidents are made of.

```
app.py ──calls──> services.py ──calls──> models.py
   |                   |
   └── assumes auth ───┘
        checked here

Neither checks. Graqle activates all three as agents.
Surfaces the contradiction. 89% confidence. 47 seconds.
```

---

## Three commands. Full architectural intelligence.

```bash
# Scan any codebase — builds a typed knowledge graph
graq scan repo .
# → 5,579 nodes, 19,916 edges in seconds

# Ask anything — graph-of-agents reasoning
graq run "what are the riskiest files to change?"
graq run "find every auth vulnerability"
graq run "what breaks if I refactor the payment module?"

# Teach it — the graph never forgets
graq learn "payment module must never call user service directly"
# → Lesson persists. Every future audit activates it.
# → Your new hire inherits your team's 2 years of hard lessons. Instantly.
```

---

## Model agnostic. Works with your existing setup.

```yaml
# graqle.yaml
model:
  backend: bedrock        # or: anthropic, openai, ollama, groq, gemini...
  model: claude-sonnet-4-6
  profile: your-aws-profile   # uses your existing AWS credentials
```

**14 backends.** One line change. Including Ollama for fully offline, air-gapped, zero-cost operation. Your code never leaves your machine.

**Works with every AI IDE** — Claude Code, Cursor, VS Code + Copilot, Windsurf. Add 74 architecture-aware MCP tools your AI uses automatically.

```bash
graq init    # auto-detects your IDE, wires all 74 tools
```

---

## What you get — the full stack

| Capability | Command |
|:-----------|:--------|
| Cross-file security audit | `graq run "find every auth vulnerability"` |
| Blast radius before change | `graq impact auth.py` |
| Governance gate | `graq preflight "refactor the auth layer"` |
| Persistent lessons | `graq learn "validation must be in services layer"` |
| Past mistakes surface automatically | `graq lessons auth` |
| UX friction audit (12 dimensions) | `graq scorch run` |
| Live browser automation | `graq phantom audit https://yourapp.com` |
| CI/CD governance gate | `graq predict "..." --fail-below-threshold` |

---

## The compounding advantage

Every audit teaches the graph. Every lesson persists. Every fix is remembered.

The first time you use Graqle, it knows your codebase.
After a month, it knows your patterns.
After a year, it knows every mistake your team ever made — and blocks the next one before it's written.

**Copilot forgot. Graqle remembered.**

No other tool has this. You cannot replicate it with prompt engineering. It requires a persistent typed knowledge graph as the execution substrate — and that's exactly what Graqle is.

---

## Pricing

| | Free | Pro ($19/mo) | Team ($29/dev/mo) |
|:--|:--:|:--:|:--:|
| CLI + SDK + 74 MCP tools | Unlimited | Unlimited | Unlimited |
| 14 LLM backends | ✅ | ✅ | ✅ |
| Graph nodes | 500 | 25,000 | Unlimited |
| Cloud sync | 1 project | 3 projects | Unlimited |
| UX Vision audit | — | ✅ | ✅ |
| Browser automation | — | ✅ | ✅ |

[**graqle.com →**](https://graqle.com)

---

## Quick start

```bash
pip install graqle

# Scan your codebase
graq scan repo .

# Ask it anything
graq run "what's the riskiest file to change?"

# Wire it to your AI IDE
graq init
```

**Full docs:** [github.com/quantamixsol/graqle](https://github.com/quantamixsol/graqle)

---

*Built by Quantamix Solutions B.V. · Patent pending EP26162901.8 · Local by default · Your code never leaves your machine*
