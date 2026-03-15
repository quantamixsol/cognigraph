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

## Open Issues (from CrawlQ Studio project — v0.21.1)

### DF-007: `exclude_patterns` not respected during `graq init` scan
- **Severity:** P1
- **Found:** 2026-03-14
- **Version:** v0.21.1
- **Status:** OPEN
- **Repro:** Set `scan.docs.exclude_patterns: ["crawlq-ui/", "crawlq-lambda/"]` in graqle.yaml, run `graq init`
- **Expected:** Excluded directories skipped
- **Actual:** Both excluded dirs scanned (95% of 3,939 nodes were from excluded sources)
- **Root cause:** CLI commands never read `config.scan.docs.exclude_patterns`. DocumentScanner supports it, but CLI never passes it.

### DF-008: `scan_dirs` config field is dead code
- **Severity:** P1
- **Found:** 2026-03-14
- **Version:** v0.21.1
- **Status:** OPEN
- **Repro:** Set `scan.docs.scan_dirs: [".", "../sibling-repo"]` — sibling repo produces 0 nodes
- **Root cause:** `scan_dirs` defined in DocScanConfig but never read by any CLI command. All scanner invocations hardcode path from CLI arguments.

### DF-009: `graq scan docs` ignores `exclude_patterns` from config
- **Severity:** P1
- **Found:** 2026-03-14
- **Version:** v0.21.1
- **Status:** OPEN
- **Repro:** `graq scan docs --verbose` with exclude_patterns set in graqle.yaml
- **Root cause:** `scan_docs()` creates DocScanOptions without reading config exclude_patterns (defaults to empty list). No `--exclude` CLI flag exists either.

### DF-010: `graq link merge` overwrites target instead of merging into existing
- **Severity:** P2
- **Found:** 2026-03-14
- **Version:** v0.21.1
- **Status:** OPEN
- **Repro:** `graq link merge a.json b.json --output graqle.json` (where graqle.json has learned/enriched data)
- **Expected:** New nodes merged INTO existing enriched graph
- **Actual:** `Path.write_text()` truncates and overwrites — all learned knowledge lost
- **Impact:** Lost ~796 knowledge nodes and learned edges

### DF-011: `graq ingest` extracts 0 entities from ADR markdown files
- **Severity:** P2
- **Found:** 2026-03-14
- **Version:** v0.21.1
- **Status:** OPEN
- **Repro:** `graq ingest --sources ".gsm/decisions/*.md" --merge --verbose`
- **Root cause:** Markdown KG parser only recognizes `## Nodes` / `## Edges` table format, not ADR-style (Context/Decision/Consequences)

### DF-012: `graq doctor` shows wrong backend
- **Severity:** P3
- **Found:** 2026-03-14
- **Version:** v0.21.1
- **Status:** OPEN
- **Repro:** Config says `backend: bedrock`, doctor shows "Backend: GPT (OpenAI)"
- **Root cause:** Doctor checks installed packages via `importlib.import_module()` not configured backend from graqle.yaml

### DF-013: `graq metrics` shows stale graph stats
- **Severity:** P3
- **Found:** 2026-03-14
- **Version:** v0.21.1
- **Status:** OPEN
- **Repro:** After scan/learn/ingest, `graq metrics` still shows node counts from initial init
- **Root cause:** Graph stats only captured during `graq init`, not updated after subsequent operations

### DF-014: `graq init` modifies graqle.yaml despite `--no-*` flags
- **Severity:** P3
- **Found:** 2026-03-14
- **Version:** v0.21.1
- **Status:** OPEN
- **Root cause:** Init merges its own defaults into existing graqle.yaml, replacing user comments and formatting

### DF-015: `graq learn discover --semantic` hangs on large graphs
- **Severity:** P3
- **Found:** 2026-03-14
- **Version:** v0.21.1
- **Status:** OPEN
- **Repro:** `graq learn discover --from handler.py --depth 3 --semantic` on 6K+ node graph
- **Root cause:** No progress indicator or timeout mechanism. Users think tool is frozen.

---

## Resolved Issues

### DF-005: `_save_graph_data` doesn't validate before overwriting
- **Severity:** P1
- **Found:** 2026-03-14
- **Version:** v0.21.1
- **Status:** FIXED (v0.21.2)
- **Root cause:** No guard rails on `_save_graph_data()` — any caller can write garbage. Test mock contamination wrote MagicMock strings into `directed`/`multigraph` fields, wiping all 3,991 nodes.
- **Fix:** Added `_validate_graph_data()` in `graph.py` — checks types, refuses save if node count drops >50%. Called from `to_json()` and `_save_graph_data` in `scan.py`.

### DF-006: Concurrent `graq learn knowledge` writes cause data loss
- **Severity:** P2
- **Found:** 2026-03-14
- **Version:** v0.21.1
- **Status:** FIXED (v0.21.2)
- **Root cause:** No file-level locking on `graqle.json` writes. Multiple processes read same state, add their node, write back — last write wins.
- **Fix:** Implemented `_graph_lock` context manager with cross-platform file locking (`msvcrt.locking` on Windows, `fcntl.flock` on Unix). `learn knowledge` now uses atomic read-modify-write.

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
