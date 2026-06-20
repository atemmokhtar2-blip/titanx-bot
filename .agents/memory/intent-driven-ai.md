---
name: Intent-Driven AI Upgrade
description: 5 root causes fixed; project_indexer.py created; 6 surgical edits to ai_engine.py completing the keyword→intent-driven transformation.
---

## Root Causes Fixed

### 1. Context not fed to AgentReasoningChain
- `_ctx_result` from ContextEngine was computed in `process_chat` but NEVER passed to `AgentReasoningChain.execute()`.
- Fix: `execute(msg, intent, ctx_result=None)` — `ctx_result` now flows all the way into `_step2_search`.

### 2. Telegram Priority Rule missing in _step2_search
- `_step2_search` used only keyword/semantic maps regardless of context.
- Fix: Step A in the new `_step2_search` calls `_PI.context_files(ctx_name)` when context confidence > 0.05. Results are prepended to the merged file list so bot files always come first when `ctx_name=telegram_bot`.

### 3. Self-Correction had no action
- `SelfCorrectionEngine.verify()` returned issues; code only did `_ai_log.warning(...)`.
- Fix: When `_correction["issues"]` is non-empty AND intent is a project intent, a correction notice (`ملاحظة تدقيق الاستجابة`) is appended to `resp["text"]` and `correction_issues` is stored in `resp["data"]`.

### 4. Engineering Mode Lock absent
- When `detect_intent` returned `"general"` or `"conversation"`, the agent bypassed all project-specific handlers even when ContextEngine detected `telegram_bot` or similar with high confidence.
- Fix: Lock block added in `process_chat` after ContextEngine detection. If intent ∈ {general, conversation} AND context confidence > 0.15 AND ctx_name ≠ general, intent is redirected via `_LOCK_REDIRECT` dict (e.g. telegram_bot → arch, router_layer → routes, frontend_layer → find_file).

### 5. No permanent disk index with classes/functions
- `ProjectBrain` re-scanned every 10min but had no disk persistence and no structured class/function/handler metadata.
- Fix: `extracted_project/control_panel/project_indexer.py` — Phase 1 permanent disk index.

## project_indexer.py Key Facts
- Location: `extracted_project/control_panel/project_indexer.py`
- Disk files: `.project_index.json` + `.project_index_mtimes.json` (in same directory)
- In-memory TTL: 600s (10 min)
- Incremental: only re-indexes files whose mtime changed
- Indexes: Python (classes, functions, async_functions, routes, handlers, imports), HTML (extends, blocks, api_calls), JS (functions, fetch calls), CSS (selectors, variables)
- 145 files indexed on first run (123 Python, 20 HTML + JS/CSS)

## ai_engine.py Edit Locations (approximate line numbers at time of edit, file ~7066 lines)
1. Import: after line 50 (after `_CE_OK = False`)
2. `AgentReasoningChain.execute()`: signature change at original line ~1668
3. `AgentReasoningChain._step2_search()`: full rewrite at original line ~1709
4. Engineering Mode Lock: added in `process_chat` between ContextEngine detection and Agent Gate 2
5. `AgentReasoningChain.execute()` call: `_ctx_result` now passed as 3rd arg
6. Self-Correction action: appends correction notice when issues found for project intents

**Why:** All 5 root causes caused the agent to answer project-specific questions with generic/wrong context (e.g., opening panel files when asked about Telegram bot, giving generic explanations instead of project-evidence-backed answers).

**How to apply:** Any future changes to `_step2_search` must preserve the ctx_files priority (Step A before Step B+C). Engineering Mode Lock thresholds: confidence > 0.15, `_LOCK_REDIRECT` dict covers all 10 context subsystems.
