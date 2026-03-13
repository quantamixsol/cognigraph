# GSD DISCUSS — v0.16.1 Feedback Fixes

## Problem
Graqle v0.16.0 scored 8.0/10. Four bugs remain from consolidated evaluation.

## In-Scope
1. **BUG 7:** Lessons hit_count always 0 — increment `properties.hits` when lessons surfaced via MCP
2. **BUG 8:** Unicode crash on Windows cp1252 — ASCII fallback for ✓✗→• symbols in CLI
3. **BUG 4:** Impact analysis too coarse — parse import/require statements in `graq scan repo` to create IMPORTS edges
4. **BUG 5:** MCP exe lock on Windows upgrade — `graq self-update` command

## Out-of-Scope (Deferred)
- Auto-skill detection
- Studio dashboard / API backend
- `--max-time` reasoning parameter
- Lesson-to-file mapping in preflight

## Constraints
- Repo: graqle (formerly cognigraph) at c:/Users/haris/CrawlQ/cognigraph
- Package: `graqle` on PyPI, CLI: `graq`
- Python module: `graqle/` directory
- 792 tests must continue passing
- Windows 11 + Python 3.10 compatibility

## Success Criteria (Binary)
- [ ] `graq_lessons` MCP tool increments hit_count on returned lessons
- [ ] CLI prints safely on Windows cp1252 console (no UnicodeEncodeError)
- [ ] `graq scan repo .` creates IMPORTS edges for Python/JS/TS imports
- [ ] `graq self-update` stops MCP server, upgrades, restarts
- [ ] All tests pass (792+)
- [ ] v0.16.1 deployed to PyPI
