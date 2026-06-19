---
name: Agent Foundation Enforcement v16
description: 5 targeted fixes applied to ai_engine.py for the 16-rule reasoning protocol; key architectural decisions a future agent needs.
---

## The Chain Injection Gap (Critical Fix)
The 7-step `AgentReasoningChain.execute()` was run in `process_chat()` but its result was stored in a local variable `_chain` and discarded — handlers never received it.

**Fix:** Module-level `_ACTIVE_CHAIN: dict = {}` cache (added after `FutureExecutionArchitecture` class). `process_chat()` assigns to `global _ACTIVE_CHAIN` at start (reset to `{}`), then stores the chain result there. Any handler can read it without parameter changes.

**Why:** Avoids refactoring ~30 handler signatures; module-level cache is safe because all processing is single-threaded within a request (FastAPI async, one coroutine at a time).

## Scan-Usage Verification (Rule 3)
After the handler returns, `process_chat()` checks if the answer text references any filename from `_ACTIVE_CHAIN["search"]["files"]`. If not, a scan evidence footer is appended listing those files + risk level. Chain metadata `{steps_done, files_scanned, risk}` is always injected into `resp["data"]["chain"]`.

**How to apply:** `scan_evidence_injected: True` in response data signals the footer was added. If `False`, the handler already used the evidence directly (correct behavior).

## Identity
`_r_identity()` → `"TitanX Engineering Agent — Agent Foundation v16"` (was "X AI Operator — المرحلة 3")
`_r_capabilities()` → same name, now includes live dep graph stats and `runtime_graph` in intents list.
`data["identity"]` = `"TitanX Engineering Agent"`, `data["phase"]` = `"Agent Foundation v16"`.

## Runtime Graph (Rule 5)
New intent `"runtime_graph"` — handler `_r_runtime_graph(msg)` builds live:
- **Startup Chain**: config → app.py → db init → ai_engine startup_recover → uvicorn → bots
- **Runtime Chain**: User → Telegram API → handler → service → DB → parallel FastAPI/AI paths
- **Failure Chain**: pulled from `ProjectBrain.RISKS` (top 4 SPOFs)

Intent patterns in `detect_intent()` cover both Arabic ("رسم بيان التشغيل") and English ("startup chain", "execution flow", "how does the server start", "failure chain").

## File Size
ai_engine.py went from 6,473 → 6,636 lines (+163 lines). 143 total functions/methods.

## Self-Test Note
`scan_evidence_injected = False` on a `who_depends` query is **correct** — means the handler already referenced the scanned files in its output, so no footer was needed.
