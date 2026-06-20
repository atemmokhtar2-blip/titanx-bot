---
name: Phase 1 Root-Cause Repair
description: Three specific bugs fixed in ai_engine.py + context_engine.py; all 5 verification tests pass.
---

## Repairs completed

### Problem 1 — Intent Engine false-positive blocks
**Root cause:** `IntentConfidence.score()` divided hits by total signal count.
A single match on a 7-signal list gave 1/7 = 0.14, below the 0.30 gate → valid questions blocked.

**Fix (context_engine.py `IntentConfidence.score()`):**
```python
# OLD: hits / max(len(signals), 3)  — 1 hit on 7-signal list → 0.14 (blocked)
# NEW: max(hits / max(len(signals), 3), 0.35) if hits > 0 else 0.0
```
Any single strong-signal match now floors at 0.35.

### Problem 2 — Context Engine HF signal misclassification
**Root cause:** HF signals ("hugging face", "hf space") were listed under `deployment` context
instead of `ai_layer`, so HF questions pulled deployment-context files.

**Fix (context_engine.py `_CONTEXTS`):** Moved HF signals to `ai_layer`.
Context Lock threshold lowered from 0.45 → 0.25 in `ai_engine.py`.

### Problem 3 — HF Router single-path override
**Root cause:** A single early-return gate sent ALL HF mentions to `hf_query` regardless of
whether the user wanted an action (analyze/audit) or a status check.

**Fixes (ai_engine.py `detect_intent()`):**
- Two-path gate: explicit HF + action verb → `analyze`; explicit HF alone → `hf_query`
- Added `_HF_SHORT_ACTION` pattern for short `\bhf\b` + action verb (e.g. "using HF analyze")

### Problem 4 (follow-on) — "What database table stores users?" fell to general
**Fix:** Added `_SCHEMA_P` patterns in `detect_intent()` BEFORE `_FILE_Q`, routing database
table questions to `arch` intent.

### Problem 5 (follow-on) — "What router serves AI Workspace?" got find_file
**Root cause:** `_FILE_Q` contained `r"what route"` which captured "what router" (starts with "what route").

**Fix:** Added `_ROUTES_P` check BEFORE `_FILE_Q`; removed bare `"what route"` / `"which route"`
from `_FILE_Q`.

## Verification test results (all 5/5 PASS)
| Test | Expected | Got |
|------|----------|-----|
| "What file creates the Admin Panel button?" | find_file + content | ✅ |
| "If I delete Admin Panel button what would break?" | impact + analysis | ✅ |
| "Using HF analyze this project" | analyze (not status) | ✅ |
| "What database table stores users?" | arch + db schema info | ✅ |
| "What router serves AI Workspace?" | routes + route list | ✅ |

## Regression
22/23 pass. 1 failure: "show project structure" → `structure` (pre-existing, out of scope).

**Why:** `_STRONG_SIGNALS` list size determines per-hit weight. Any future intent with many signals
should use at least 3 entries to take advantage of the 0.35 floor — adding signals beyond 3
only raises the ceiling, not the floor.

**How to apply:** When adding signals to `_STRONG_SIGNALS`, the 0.35 floor still applies for any
single match. Keep router patterns in `_ROUTES_P` (before `_FILE_Q`) and database schema patterns
in `_SCHEMA_P` (before `_FILE_Q`) to prevent `_FILE_Q` from stealing them.
