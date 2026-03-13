# GSD PLAN — v0.16.1 Feedback Fixes

## Task Order (dependencies noted)

### Phase 1: Quick Fixes (no dependencies)
- [T1] **BUG 8: Unicode safe console** (S)
  - Create `graqle/cli/console.py` with `safe_symbol()` helper
  - Replace all ✓✗→• in CLI commands with safe_symbol() calls
  - Verify: `graq learn entity` on cp1252 console prints without crash
  - Test: unit test for safe_symbol fallback

- [T2] **BUG 7: Lessons hit_count** (S)
  - In `_handle_lessons()`: after finding lessons, increment `node.properties["hits"]`
  - In `_handle_preflight()`: same increment on matched lessons
  - Call `self._save_graph()` after increment
  - Test: hit_count increments, persists across calls

### Phase 2: Medium Feature (depends on understanding scan code)
- [T3] **BUG 4: IMPORTS edge parsing** (M)
  - Read current `graq scan repo` implementation
  - Add import parser for Python (`import X`, `from X import Y`)
  - Add import parser for JS/TS (`import ... from`, `require(...)`)
  - Create IMPORTS edges between file nodes
  - Impact analysis now follows IMPORTS chains, not just CONTAINS
  - Test: scan a small test project, verify IMPORTS edges created

### Phase 3: Windows-specific
- [T4] **BUG 5: Self-update command** (M)
  - Create `graqle/cli/commands/selfupdate.py`
  - `graq self-update`: detect running MCP, stop it, pip upgrade, restart
  - Test: unit test for the upgrade flow (mocked pip)

### Phase 4: Ship
- [T5] **Version bump + deploy** (S)
  - Bump to 0.16.1
  - Run full test suite
  - Build + upload to PyPI
  - Push to GitHub

## Complexity: S=small (<30 min), M=medium (30-90 min)
## Total estimated: ~4 tasks, parallelizable: T1+T2 (no deps)
