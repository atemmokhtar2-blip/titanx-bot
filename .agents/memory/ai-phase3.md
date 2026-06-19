---
name: AI Phase 3 Core
description: Phase 3 implementation details — ReasoningEngine, Phase 3 classes, conversation mode, HTML interface, validation results.
---

## What was built

Phase 3 complete in `extracted_project/control_panel/ai_engine.py` (~3900 lines).

## Key architectural decision: ReasoningEngine Gate

Every message passes through `ReasoningEngine.classify(msg)` at the very TOP of `detect_intent()` — before any keyword/regex matching.

Returns one of:
- `"greeting"` — triggers `_r_greeting()` immediately
- `"conversational"` — triggers `_r_conversation(msg)` immediately, NEVER touches project files
- `"project"` — falls through to existing keyword-based intent detection

**Why:** Without this gate, "Explain FastAPI" or "Python vs JavaScript" would score on the existing keyword matches (arch, compare, general) and incorrectly search project files.

## ReasoningEngine._TECH_EXTRA

A SECOND regex specifically for plural/compound tech terms:
```python
_TECH_EXTRA = re.compile(
    r"\b(?:telegram|discord|whatsapp|slack)\s*bots?\b|"
    r"\brest\s+apis?\b|\bweb\s*sockets?\b|\bmicro\s*services?\b",
    re.IGNORECASE,
)
```

**Why:** The main `_TECH` regex is inside `\b(?:...)\b`, so `telegram.{0,5}bot` FAILS to match "Telegram Bots" (plural) because the trailing `\b` word boundary doesn't fire when "bot" is followed by "s". `_TECH_EXTRA` catches these.

## ReasoningEngine._PROJECT_CONCEPT override

If a message has a COMPARE signal AND contains project-level concepts (homepage, redesign, new page, bot creation, etc.), the compare is treated as project-mode NOT conversational.

**Why:** "Difference between Homepage Redesign and Bot Creation" is a project-planning question, not a general tech comparison. Without this, `_COMPARE` fires and routes to conversational.

## Phase 3 Classes

All classes are in ai_engine.py, inserted between `hf_status()` and `SKIP_DIRS`.

- `ReasoningEngine` — classify(), is_conversational(), _TECH, _EXPLAIN, _COMPARE, _GREETING, _PROJECT, _PROJECT_CONCEPT, _TECH_EXTRA
- `AIMemoryLayer` — session memory; record(), context(), status(); class-level lists (resets on restart)
- `AIPlanner` — plan(), risk(), status(); HF-backed with local fallback
- `AIEngineerCore` — understand(), _classify(), ACTION_MAP; maps high-level requests to files+restart flags
- `ProjectImpactAnalysis` — analyze(target), status(); scans rglob("*.py") for imports
- `FutureExecutionArchitecture` — infrastructure only; can_execute() always returns False

## _TECH_KNOWLEDGE & _COMPARE_MAP

Large dicts in ai_engine.py (after the Phase 3 classes) used by `_r_conversation()`:
- `_TECH_KNOWLEDGE` — 13 tech entries: python, javascript, typescript, fastapi, flask, django, telegram_bot, rest_api, graphql, docker, sql, nosql, async
- `_COMPARE_MAP` — 5 pairs: {python,javascript}, {fastapi,flask}, {fastapi,django}, {sql,nosql}, {rest_api,graphql}

## Conversation handlers

`_r_greeting()` and `_r_conversation(msg)` added BEFORE `_r_identity()` in the handlers section.

`_r_conversation()` flow:
1. Check all `_COMPARE_MAP` pairs → structured side-by-side comparison
2. Check `_TECH_PATTERNS` list → structured tech knowledge entry
3. Try HF assistant fallback
4. Generic "here's what you can ask" fallback

## process_chat() update

`AIMemoryLayer.record()` called for BOTH user turn (pre-dispatch) and assistant response (post-dispatch). Greeting and conversation added as FIRST entries in handlers dict.

## AI Workspace HTML

Rebuilt `ai_workspace.html`:
- Removed: 6-card capability grid, statistics (sb-chats/sb-analyses/sb-backups)
- Added: AI Identity Card, HF status indicator, Phase 3 badge grid (6 badges), 4 quick-action buttons, welcome message explains both modes
- Quick chips: FastAPI, Python vs JS, Create bot, افحص الأخطاء, هيكل المشروع

## Validation results (final)

18/18 spec tests ✅ | 13/13 self-tests ✅ | HF Space live ✅
Key cases verified: greeting (Hello/Hi/مرحبا), conversation (Python vs JS, Explain FastAPI, Telegram Bots plural, async await, Flask vs Django, Docker), project mode (Create bot, Fix button, Redesign), forbidden (no project files in conversational responses).
