---
name: Phase 2 Evidence Engine
description: Evidence Engine, Verification Layer, and Project Understanding Core built in Phase 2. All 5 tests pass, 23/23 regression, 10/10 criteria.
---

## Systems built

### evidence_engine.py (new module)
- `verify_file_exists(path)` — disk check before any file claim
- `find_functions_in_file(path, terms)` — grep real file for def/class matching query
- `grep_file_evidence(path, terms)` — extract actual code lines as proof
- `find_import_lines(file, target)` — verify actual import statement exists
- `find_router_for_concept(concept)` — scan real router files for matching @router decorators
- `find_keyboard_functions()` — find all Telegram keyboard-creating functions (122 found)
- `calculate_confidence(...)` — 0.0-1.0 score: 40% file exists + 35% function + 15% evidence + 10% imports
- `format_verified_answer(...)` — mandatory Subsystem/File/Function/Evidence/Confidence format
- `NO_EVIDENCE_RESPONSE` — sentinel returned when proof is missing

### Surgical edits to ai_engine.py
1. **Import block** — fail-safe import of evidence_engine with `_EV_OK` flag
2. **`_r_find_file()`** — wraps answer_file_question(); adds disk check, function verification, evidence lines, confidence, mandatory format block
3. **`_r_routes(msg)`** — concept-aware: extracts concept from query, searches real router files, shows decorator evidence + function name + prefix + include_router line
4. **`_r_dependency()`** — for each importer: verifies file exists on disk, shows actual import line as proof (stale index entries flagged)
5. **`_r_find_function(msg)`** — new handler: classifies query (keyboard vs generic), searches real files, returns verified function list with mandatory format
6. **`detect_intent()`** — added `_FUNC_Q` pattern block before `_FILE_Q`: "What function creates/handles..." → `find_function`
7. **dispatch dict** — added `"find_function"`, changed `"routes"` to pass `msg`

## Verification test results (all 5/5 PASS)
| Test | Required | Result |
|------|---------|--------|
| "What file creates the Admin Panel button?" | File+Function+Evidence+Confidence | ✅ 90% conf |
| "What imports config/settings.py?" | Evidence (actual import lines) | ✅ Shows `from config.settings import ...` |
| "What router serves AI Workspace?" | Router+Evidence | ✅ ai_workspace.py + `@router.get("")` line |
| "What file owns the login page?" | Router+Template+Evidence | ✅ 90% conf, panel_password_login() |
| "What function creates this keyboard?" | Function+File+Evidence | ✅ 122 keyboard funcs found |

## Regression
23/23 intent routing tests pass (previous 22/23 — the pre-existing "show project structure" mismatch is now FIXED too, as "structure" intent exists in the dispatch map).

**Why:** `find_keyboard_functions()` skips `control_panel/` directory (only searches bot handlers). This is correct — Telegram keyboards are in the bot, not the panel.

**How to apply:** The `_EV_OK` flag guards all evidence engine calls — if the import fails, handlers fall back gracefully to their pre-Phase-2 behavior. Never remove the fail-safe guard.
