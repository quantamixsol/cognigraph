# Graqle Dogfood Issues — "Evolving Graqle with Graqle"

> Track all issues found while dogfooding Graqle on its own codebase.
> Each issue gets a severity, repro, and is passed to the SDK team for resolution.
> DO NOT mix these with product/feature work — these are SDK bugs/improvements only.

---

## Issue Format

```
### DF-NNN: [Title]
- **Severity:** P1 (blocks work) | P2 (workaround exists) | P3 (cosmetic/nice-to-have)
- **Found:** YYYY-MM-DD
- **Version:** v0.X.Y
- **Status:** OPEN | INVESTIGATING | FIXED (vX.Y.Z) | WONTFIX
- **Repro:** [exact command or steps]
- **Expected:** [what should happen]
- **Actual:** [what happened]
- **Workaround:** [if any]
- **Fix PR/Commit:** [link when fixed]
```

---

## Setup Notes (v0.21.0 — 2026-03-14)

- Graph: 3,926 nodes, 7,293 edges (code + JSON + docs + ADRs)
- Scan time: ~3s code, <1s JSON, <1s docs
- Platform: Windows 11, Python 3.10
- Config: graqle.yaml (anthropic backend, haiku, simple embeddings)

---

## Open Issues

### DF-005: `_save_graph_data` doesn't validate before overwriting
- **Severity:** P1
- **Found:** 2026-03-14
- **Version:** v0.21.1
- **Status:** OPEN
- **Repro:** MagicMock leak from test wrote mock strings into `graqle.json` `directed`/`multigraph` fields, wiping all 3,991 nodes to empty arrays.
- **Expected:** Save function validates graph data before overwriting — checks directed/multigraph are booleans, nodes list is non-empty.
- **Actual:** Save blindly overwrites. Corrupted graph saved with MagicMock strings and 0 nodes.
- **Workaround:** Restore from git: `git checkout HEAD -- graqle.json`
- **Root cause:** No guard rails on `_save_graph_data()` — any caller can write garbage. Test mock contamination reached production save path.
- **Proposed fix:** Add pre-write validation: (1) check types, (2) refuse to save if node count drops >50% without `--force`, (3) write to `.tmp` then atomic rename.

### DF-006: Concurrent `graq learn knowledge` writes cause data loss
- **Severity:** P2
- **Found:** 2026-03-14
- **Version:** v0.21.1
- **Status:** OPEN
- **Repro:** Run 4+ `graq learn knowledge` commands in parallel (background processes)
- **Expected:** All knowledge nodes saved to graph
- **Actual:** Race condition — concurrent reads and writes to graqle.json cause some nodes to be lost (22 → 20 in one test)
- **Workaround:** Run `graq learn knowledge` commands sequentially, not in parallel
- **Root cause:** No file-level locking on `graqle.json` writes. Multiple processes read same state, add their node, write back — last write wins, losing earlier additions.
- **Proposed fix:** Implement cross-platform file locking (Windows: `msvcrt.locking`, Unix: `fcntl.flock`) as noted in ADR-108.

---

## Resolved Issues

### DF-001: Background scan duration_seconds is wildly wrong
- **Severity:** P2
- **Found:** 2026-03-14
- **Version:** v0.21.0
- **Status:** FIXED (v0.21.1)
- **Repro:** `graq scan all .` then `graq scan status`
- **Expected:** Duration shows ~1s (doc scan took <1s)
- **Actual:** Duration shows 3601.7s (1 hour off — UTC vs local time bug)
- **Root cause:** `background.py` used `time.mktime(time.strptime(...))` which interprets UTC string as local time. `calendar.timegm()` is the correct function for UTC parsing.
- **Fix:** Replaced `time.mktime()` with `calendar.timegm()` in `background.py`.

### DF-002: No `graq inspect --stats` command
- **Severity:** P2
- **Found:** 2026-03-14
- **Version:** v0.21.0
- **Status:** WONTFIX (user error)
- **Resolution:** Command exists as `graq inspect --stats` (top-level command). Was tested as `graq scan inspect --stats` which doesn't exist. Correct usage: `graq inspect` or `graq inspect --stats`.

### DF-003: `graq learn doc` accepts only one path
- **Severity:** P3
- **Found:** 2026-03-14
- **Version:** v0.21.0
- **Status:** FIXED (v0.21.1)
- **Repro:** `graq learn doc file1.md file2.md file3.md`
- **Expected:** Ingests all 3 files
- **Actual:** "Got unexpected extra arguments"
- **Fix:** Changed `path: str` argument to `paths: list[str]` — now accepts multiple file and directory paths. Results are merged across all inputs.

### DF-004: `graq init` has no non-interactive mode
- **Severity:** P3
- **Found:** 2026-03-14
- **Version:** v0.21.0
- **Status:** WONTFIX (already implemented)
- **Resolution:** `graq init --no-interactive` already exists (with `--backend`, `--model` flags). Also auto-detects non-TTY stdin and switches to non-interactive mode automatically.

---

## Feature Requests (from dogfooding)

_Captured here, triaged to plan phases._

---

## Observations

_Running notes on UX, performance, surprises._

- 2026-03-14: Initial setup required manual graqle.yaml creation — `graq init` is interactive-only, no `--non-interactive` flag. (Potential P3: add `graq init --defaults` for CI/dogfood scenarios)
- 2026-03-14: `graq learn doc` accepts only one path arg — had to loop for multiple files. (Potential P3: accept multiple paths)
- 2026-03-14: `graq scan all` duration field shows 3601.7s for a 1s scan — time calculation bug in background scan? (Potential P2: investigate `duration_seconds` computation)
- 2026-03-14: `graq scan inspect --stats` doesn't exist — no built-in way to see graph stats from CLI. (Potential P2: add `graq inspect --stats`)
