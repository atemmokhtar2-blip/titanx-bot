---
name: AI Phase 3 Core + Engineering Intelligence
description: Phase 3 complete — ProjectBrain, 4 new handlers, 5 new intents, 5 new API endpoints, 38/38 self-tests
---

## What was built

Phase 3 Engineering Intelligence Layer complete in `extracted_project/control_panel/ai_engine.py`.

## Key architectural decision: ReasoningEngine Gate

Every message passes through `ReasoningEngine.classify(msg)` at the very TOP of `detect_intent()` — before any keyword/regex matching.

Returns one of:
- `"greeting"` — triggers `_r_greeting()` immediately
- `"conversational"` — triggers `_r_conversation(msg)` immediately, NEVER touches project files
- `"project"` — falls through to existing keyword-based intent detection

**Why:** Without this gate, "Explain FastAPI" or "Python vs JavaScript" would score on the existing keyword matches (arch, compare, general) and incorrectly search project files.

## ProjectBrain (Phase 3 Core)

`ProjectBrain` class inserted after `FutureExecutionArchitecture`. 5-minute TTL cached project model.

- `RISKS` — 7-item ranked registry (CRITICAL→LOW) with title, detail, fix, files
- `TECH_DEBT` — 7-item registry (TD-001→TD-007) with impact, effort, priority
- `SCALING_PLAN` — 3-phase blueprint (0→10k, 10k→50k, 50k→100k+)
- `get()` — returns cached model, rebuilds if expired
- `status()` — returns active/built/age/ttl/counts

**Why:** Previously every handler re-scanned the filesystem. ProjectBrain builds once and all Phase 3 handlers read from it.

## Phase 3 handlers

- `_r_scale(msg)` → intent `scale` — scaling blueprint for N users using ProjectBrain.SCALING_PLAN
- `_r_tech_debt()` → intent `tech_debt` — 7-item debt registry + live TODO scan
- `_r_redesign()` → intent `redesign` — senior architect ideal-structure vision
- `_r_risk_full()` → intent (also routes through `weakness`) — 7-item ranked risk analysis

## Phase 3 intents added to detect_intent

- `scale` — catches "يتحمل 100,000", "scale to 100k", "توسع", "horizontal scaling"
- `tech_debt` — catches "technical debt", "ديون تقنية", "refactor", "إعادة كتابة"
- `redesign` (arch) — catches "كيف ستعيد تصميم", "how would you redesign", "from scratch"
- `_WEAKNESS_Q` fixed: added `r"(?:أكبر|أشد|أهم|أخطر).{0,10}(?:\d+\s+)?مخاطر"` pattern to catch "أكبر 5 مخاطر" BEFORE `_SECURITY_Q`

## Persistent engineering memory

- `_default_memory()` expanded with `decisions[]`, `upgrades[]`, `tech_debt_log[]`
- `save_engineering_decision(title, rationale, files_affected)` → appends to memory
- `list_engineering_decisions()` → reads from memory

## Phase 3 API endpoints (ai_workspace.py)

- `GET /ai/api/brain` — full ProjectBrain snapshot
- `GET /ai/api/risk` — ranked risk analysis
- `GET /ai/api/tech_debt` — tech debt registry
- `POST /ai/api/decision` — save engineering decision to persistent memory
- `GET /ai/api/decisions` — list all saved decisions

## Validation results (final)

**38/38 ✅ PASS** — P1(file): 16/16 | P2(intent A-E): 5/5 | P3(Arabic reasoning): 17/17

5 new Phase 3 canonical tests added to `_ARABIC_REASONING_TESTS`:
- "كيف يتحمل المشروع 100,000 مستخدم؟" → scale → "توسع"
- "ما هي الديون التقنية في المشروع؟" → tech_debt → "ديون"
- "كيف ستعيد تصميم TitanX من الصفر؟" → redesign → "تصميم"
- "ما أكبر 5 مخاطر في المشروع؟" → weakness → "ضعف"
- "ما الذي يحتاج إعادة كتابة في المشروع؟" → tech_debt → "ديون"

Arabic test keywords: use *actual* words from response text, not synonyms:
- scale response uses "توسع"
- tech_debt response uses "ديون"
- redesign response uses "تصميم"
- strategy response uses "استراتيج"
- arch response uses "معمارية"

## Phase 3 Classes Summary

All classes in ai_engine.py, in order:
- `ReasoningEngine` — classify, is_conversational, _TECH, _EXPLAIN, _COMPARE, _GREETING, _PROJECT
- `AIMemoryLayer` — session memory; record(), context(), last_intent(), status()
- `AIPlanner` — plan(), risk(), status(); HF-backed with local fallback
- `AIEngineerCore` — understand(), _classify(), ACTION_MAP
- `ProjectImpactAnalysis` — analyze(target), status(); scans rglob("*.py") for imports
- `FutureExecutionArchitecture` — infrastructure placeholder; can_execute() always False
- `ProjectBrain` — living cached project model; RISKS, TECH_DEBT, SCALING_PLAN, get(), status()
