### COMMIT 1 — 2026-03-13T18:00:00Z
**Milestone:** All 4 feedback bugs fixed, 866 tests passing
**State:** WORKING (awaiting deploy — parallel session must finish first)
**Files Changed:**
- MODIFIED: graqle/plugins/mcp_dev_server.py — BFS impact filtering (skip CONTAINS/DEFINES edges), lesson hit_count increment
- CREATED: graqle/cli/console.py — safe_symbol() Unicode fallback helper
- CREATED: graqle/cli/commands/selfupdate.py — graq self-update command
- MODIFIED: graqle/cli/main.py — wire self-update command
- MODIFIED: graqle/cli/commands/learn.py — use safe_symbol for console output
- CREATED: tests/test_plugins/test_impact_filtering.py — 4 tests
- CREATED: tests/test_plugins/test_lesson_hit_count.py — 9 tests
- CREATED: tests/test_cli/test_console_unicode.py — 6 tests
- CREATED: tests/test_cli/test_selfupdate.py — 4 tests
**Key Decisions:**
- Impact BFS: filter by edge type rather than rewriting scanner (simpler, same effect)
- Unicode: safe_symbol() with pre-computed constants (CHECK, CROSS, ARROW, BULLET)
- Self-update: detect+stop running graq processes, pip upgrade, optional restart
**Next:**
- [ ] Wait for parallel session to finish
- [ ] Bump version to 0.16.1
- [ ] Deploy to PyPI + push to GitHub
**Blockers:** Parallel session must complete before deploy
