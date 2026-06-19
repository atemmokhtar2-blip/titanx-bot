---
name: Project Intelligence Mode (Phase 3.5)
description: 5-step protocol replacing all 4 generic modification handlers; ProjectSelfAudit engine
---

## What changed

`ProjectIntelligenceAgent` and `ProjectSelfAudit` inserted in `ai_engine.py` after `ProjectBrain` (~line 656).

## ProjectIntelligenceAgent.run(msg) — the single entry point

All 4 modification handlers now just call `ProjectIntelligenceAgent.run(msg)`:
- `_r_create_feature` → `ProjectIntelligenceAgent.run(msg)`
- `_r_ui_redesign`    → `ProjectIntelligenceAgent.run(msg)`
- `_r_debug_fix`      → `ProjectIntelligenceAgent.run(msg)`
- `_r_new_page`       → `ProjectIntelligenceAgent.run(msg)`

## 5-step protocol

1. `_scan()` — live filesystem scan: walk_project, analyze_structure, build_dependency_map → `existing` dict of real routers/handlers/templates/services
2. `_understand(msg)` — classifies: req_type ∈ {create_bot, create_page, modify_auth, modify_db, modify_ui, debug_fix, create_feature} + operation + entities + name_hint
3. `_calculate_impact(und, scan)` — uses ACTUAL file lists to: list affected files, find reusable systems, list risks
4. `_generate_plan(und, imp, scan)` — uses scan["router_names"][0] as template example; generates real steps with real paths
5. `_format(...)` — 5-section response: Scan → Understand → Impact → Plan+Execute

## Key design rules

- `_scan()` uses `walk_project()` (60s TTL cached) — never re-walks unnecessarily
- `_calculate_impact` checks ACTUAL existing files before recommending creation (e.g. notifier.py exists → reuse it)
- `_generate_plan` uses first real router as template example, never "new_router.py"
- Response includes rollback strategy in every plan

## ProjectSelfAudit

- 10-min TTL cache; `audit()` returns: spof, syntax_errors, security, log_errors, tech_debt, risks
- `_check_spof()` — verifies 7 critical SPOF files exist and have no syntax errors
- `_check_syntax()` — ast.parse on all .py files (up to 60)
- `summary()` → "✅ HEALTHY / ⚠️ ISSUES / 🔴 CRITICAL | SPOF: N/N OK · Syntax: N err · ..."

## New API endpoints

- `GET  /ai/api/audit`        — full integrity audit (10-min TTL)
- `POST /ai/api/intelligence` — direct access to 5-step pipeline with {msg: str}

## Validation

- 38/38 self-tests PASS (unchanged from Phase 3)
- Direct tests: create_bot / create_page / debug_fix / self-audit / Arabic — all PASS
- SPOF: 7/7 OK · Syntax: 0 errors · Mode: project_intelligence_v2

**Why:** The previous handlers used hardcoded generic paths (new_bot_handler.py, new_router.py) that bore no relation to the actual project. Now every answer is grounded in a live filesystem scan.
