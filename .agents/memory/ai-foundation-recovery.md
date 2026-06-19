---
name: AI Foundation Recovery
description: 8-phase audit of ai_engine.py — 15 root causes found and all fixed; 43/43 verification tests pass.
---

## What was done
Full read + audit of all 5600+ lines of `extracted_project/control_panel/ai_engine.py` and `developer_bot/handlers/ai_assistant.py`. 15 root causes confirmed and fixed. Verified with 43 automated tests.

## Key rules for future work on ai_engine.py

**`_normalize_ar()` scope rule:**
- Apply in `_normalize_query()` (normalizes ALIASES lookup keys AND query string) ✓
- Apply in `ReasoningEngine.classify()` (normalizes before greeting regex match) ✓
- Apply in `search_project_files()` (normalizes query for filename comparison) ✓
- Do NOT apply globally to `ml` in `detect_intent()` — the existing Arabic intent patterns use hamza characters (أإآ) and would break if the input is normalized before matching.
- **Why:** The patterns in INTENTS were written with hamza (e.g. `r"من أنت"`) and match the raw input. Normalizing the input without also normalizing all patterns breaks them silently.

**Greeting gate rule:**
- `ReasoningEngine.classify()` uses `len(stripped.split()) <= 4` as the word-count gate.
- Any message longer than 4 words is never classified as a greeting, even if it starts with one.
- **Why:** `_GREETING.match()` anchors to start only — a 7-word message starting with "مرحبا" would otherwise silence the actual question.

**Self-test cache rule:**
- `run_self_tests()` runs 38 tests synchronously (~5 seconds). Never call it inline.
- Use `_SELF_TEST_CACHE` with `_SELF_TEST_TTL = 300.0` seconds (defined above `_r_status()`).
- **Why:** `_r_status()` is called on every `/ai/api/status` request — running 38 tests per request is a denial-of-service on the panel.

**`_r_conversation()` rule:**
- Steps 3 and 4 were identical `call_hf_assistant(msg)` calls — step 4 was removed.
- Only ONE HF call per conversation response cycle.

**`_r_general()` Layer 7 rule:**
- HF `call_hf_analyze` is only called if `len(msg.strip()) >= 10`.
- Short queries (< 10 chars) fall directly to LAST RESORT and get the rephrasing hint.

**`AIEngineerCore._classify()` scoring rule:**
- Uses weighted scoring, not first-match-wins.
- "bot status page" → `create_page` wins over `create_bot` because of noun-modifier detection.
- `modify_database` and `modify_auth` have weight 3 to prevent accidental triggers.

**`AIMemoryLayer` truncation:**
- Records up to 600 chars per turn (was 300 — too short for meaningful context).

**`_r_identity()` rule:**
- `hf_connected` uses live `hf_status().get("connected", False)` — never hardcoded True.

**`_SEMANTIC_MAP` new concepts added:**
- rate_limiter, rate_limit, subscription, subscription_gate, middleware
- lucky_wheel, achievements, referral, video_studio, video_tools, favorites, logo

**`_ALIASES` new Arabic entries:**
- حد التحميل/التقييد → rate_limiter; الاشتراك → subscription
- عجلة الحظ/العجلة → lucky_wheel; الإنجازات/الشارات → achievements
- الإحالة → referral; استوديو الفيديو → video_studio; المحفوظات/المفضلة → favorites; الشعار → logo

**`developer_bot/handlers/ai_assistant.py` rule:**
- Has its own local `_normalize_ar()` (same logic as ai_engine.py, standalone)
- `INTENTS` patterns are pre-normalized (no hamza in pattern strings)
- `handle_ai_command()` normalizes input before matching
- Dead "بوت الأدمن" intent removed (Admin Bot was removed in earlier session)
- `_COMPILED_INTENTS` list pre-compiles all patterns at module load

**`AIPlanner.plan()` fallback rule:**
- When HF is unreachable, fallback calls `ProjectBrain.get()` to get real module/router names.
- Returns `source="local_project"` with feature-specific steps (not 5 generic hardcoded steps).
