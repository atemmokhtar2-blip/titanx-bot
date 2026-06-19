---
name: AI Intelligence Layer
description: Phase 1.5 upgrade — Project Knowledge Engine in ai_engine.py v2.0. Semantic file awareness, dependency mapping, planning engine, self-tests.
---

# AI Intelligence Layer — Phase 1.5

## What was built
`extracted_project/control_panel/ai_engine.py` upgraded from v1.0 → v2.0.

## Key components added

### `_SEMANTIC_MAP`
Dict mapping ~35 concept keywords (homepage, dashboard, css, colors, login, auth, sidebar, bots, etc.) to `[(rel_path, role, description)]` tuples. This is the core knowledge index.

### `_ALIASES`
Arabic + English aliases that normalize before lookup (e.g. "الصفحة الرئيسية" → "homepage").

### `_find_concept(q)`
**Critical rule:** Sort concepts by length DESCENDING before matching, so "ai_engineer" beats "ai". Short concept keys like "ai", "db" caused false-first matches before this fix.

### `answer_file_question(msg)`
Answers "what file controls X?" with real file paths, roles, and descriptions.

### `build_dependency_map()`
Auto-scans all Python router files, extracts `@router.get/post` + `TemplateResponse` pairs to build route→template→CSS/JS map. Found 95 routes.

### `create_modification_plan(description)` (replaces old `create_plan`)
Returns real file names, roles, risk levels, rollback strategy — not generic steps.

### `run_self_tests()`
8 canonical questions tested (English). Must pass 8/8. Tests intent detection + keyword presence in answer.

## New API endpoints (added to routers/ai_workspace.py)
- `GET  /ai/api/knowledge` — full semantic map
- `POST /ai/api/search` — intelligent file search
- `POST /ai/api/file_question` — answer "what file controls X?"
- `GET  /ai/api/dependencies` — route→template dependency map
- `POST /ai/api/file_role` — full profile of a specific file
- `POST /ai/api/plan_v2` — real planning engine with actual files
- `GET  /ai/api/self_test` — run 8/8 self-tests

## Self-test results
8/8 — 100% PASS rate (verified after fix)

## Why: longest-match-first matters
Before fix: `_find_concept("ai engineer page")` matched "ai" concept first (insertion order) → returned ai_workspace.html instead of ai_engineer.html. Fix: sort by `len(concept)` descending before iterating.
