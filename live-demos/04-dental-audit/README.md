# Demo 04: Dental Appointment System Audit

> **Graqle finds the bugs that linters miss — the ones that only appear when you reason across files.**

---

## The Scenario

You've inherited a Flask dental appointment system. It looks clean at first glance:
- Models, services, auth, notifications, utils — proper separation of concerns
- Each file has docstrings and comments
- No obvious syntax errors

But something is wrong. Run `pylint`, `flake8`, or `mypy` — they find nothing critical.

Graqle builds a knowledge graph of the six source files, maps the import relationships, and reasons across the full dependency chain. It surfaces 8 bugs — 2 critical, 3 high, 3 medium — that only exist in the **space between files**.

---

## The Bugs

| ID | Severity | File | Title |
|----|----------|------|-------|
| BUG-001 | CRITICAL | app.py | Cancel endpoint has no authentication |
| BUG-002 | CRITICAL | app.py | Patient search is unauthenticated; empty query dumps all records |
| BUG-003 | HIGH | models.py | MD5 used for password hashing |
| BUG-004 | HIGH | auth.py | Session tokens never expire |
| BUG-005 | HIGH | services.py | Double-booking not prevented |
| BUG-006 | MEDIUM | notifications.py | Notification layer bypasses the service layer |
| BUG-007 | MEDIUM | utils.py | `is_future_date()` crashes on malformed date strings |
| BUG-008 | MEDIUM | app.py | Error responses always return HTTP 200 |

### Why a linter can't catch these

- **BUG-001**: `cancel()` in app.py has no auth. `services.py:cancel_appointment()` has a comment that says "assumes app.py verified the user". Neither file is individually wrong — the bug lives in the **assumption gap** between them.
- **BUG-002**: `search_patients("")` is syntactically valid Python. The bug emerges from tracing: `app.py:search()` passes `q=""` straight to `services.py:search_patients()`, which returns all records for an empty string.
- **BUG-005**: `models.py` says overlap check is "assumed to be in services". `services.py` says it's "assumed to be in models". Neither implements it. A linter sees only one file at a time.
- **BUG-006**: `notifications.py` imports `appointments_db` directly from `models.py`. This is legal Python. Only cross-file architectural analysis reveals that it bypasses the service layer.

---

## Running the Demo

```bash
# From graqle-sdk/
python live-demos/04-dental-audit/run_demo.py

# With live LLM reasoning (optional — demo works without it)
export ANTHROPIC_API_KEY=sk-ant-...
python live-demos/04-dental-audit/run_demo.py
```

The script does NOT require Flask to be installed or running. It is a pure static analysis and patch tool.

**What you'll see:**

1. File scan — reads all 6 source files, counts lines
2. KG build — constructs a 6-node, 13-edge knowledge graph in milliseconds
3. Reasoning — Graqle's multi-agent reasoner queries the graph across 3 dimensions: security, validation gaps, architectural risks
4. Bug report — all 8 bugs printed with severity, file, cross-file chain, and fix summary
5. Fix application — each fix is applied to `dental_app_fixed/` with a before/after diff
6. Verification — 11 pattern checks confirm every fix was applied correctly

---

## Directory Layout

```
04-dental-audit/
├── README.md               <- this file
├── run_demo.py             <- main demo script (Part 2 + 3)
└── dental_app/             <- buggy app (Part 1)
    ├── app.py              <- Flask routes (BUG-001, BUG-002, BUG-008)
    ├── auth.py             <- session management (BUG-004)
    ├── models.py           <- data store (BUG-003)
    ├── services.py         <- business logic (BUG-005)
    ├── notifications.py    <- email reminders (BUG-006)
    └── utils.py            <- date helpers (BUG-007)
```

After running the demo, `dental_app_fixed/` is created with all patches applied.

---

## What Graqle Adds

```
Standard approach:          Graqle approach:
  File 1 → linter             File 1 ─┐
  File 2 → linter             File 2 ─┤→ Knowledge graph → Multi-agent reasoning
  File 3 → linter             File 3 ─┘       │
  File 4 → linter                              ▼
  File 5 → linter                    Cross-file bug detection
  File 6 → linter
                              Finds: assumption gaps, auth chains,
                              layer bypasses, validation dead zones
```

Graqle's graph captures which module assumes which other module does validation. When no module actually does it, the gap is visible in the graph topology — and the reasoner surfaces it.

---

## Key Graqle APIs Used

```python
from graqle import Graqle

g = Graqle()
g.add_node_simple("app_py", label="app.py", entity_type="MODULE",
                  description="Flask routes with auth gaps...")
g.add_edge_simple("app_py", "services_py", relation="DELEGATES_TO")
g.set_default_backend(backend)

result = g.reason(
    "Find all security vulnerabilities — cross-reference all files",
    strategy="full",   # all nodes active — appropriate for small apps
)
print(result.answer)      # the synthesised multi-agent answer
print(result.confidence)  # 0.0–1.0
```

The `strategy="full"` parameter activates all graph nodes, making it ideal for small codebases (< 20 modules) where you want comprehensive cross-file analysis. For larger codebases use `strategy="chunk"` (default) to activate only the most relevant subgraph.

---

## Extending the Demo

**Add your own app:**
1. Copy `dental_app/` to a new directory
2. Edit `run_demo.py` to point `APP_DIR` at your app
3. Update `build_dental_kg()` with your file nodes and import edges
4. Add your bugs to the `BUGS` list
5. Add fix functions to `ALL_FIXES`

**Use the real Graqle CLI for deeper analysis:**
```bash
graq scan repo live-demos/04-dental-audit/dental_app/
graq run "what authentication is missing from the dental appointment API?"
graq impact dental_app/app.py
```
