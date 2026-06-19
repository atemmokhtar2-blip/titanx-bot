---
name: Context Engine v1
description: Phase 11/12/18/19 — 4 classes in context_engine.py wired into process_chat; detects 10 subsystem contexts; confidence scoring; self-correction; classification audit
---

## What was built

New file: `extracted_project/control_panel/context_engine.py`

### Classes

**ContextEngine** (Phase 12)
- Detects which project subsystem a message concerns
- 10 contexts: telegram_bot, control_panel, database, router_layer, api_layer,
  frontend_layer, infrastructure, ai_layer, deployment, support_system
- Each context has keyword signals + file_patterns
- Returns: detected, description, confidence (0.0–1.0), evidence, all_scores, rejected
- Key fix: removed "endpoint" from router_layer (too broad); added compound signals
  like "api endpoint", "endpoint في", "endpoint url" to api_layer to avoid collision

**IntentConfidence** (Phase 11)
- Scores how confidently an intent was selected (0.0–1.0)
- Strong signal lists per intent; default 0.7 for intents without a list
- Used in ClassificationAudit to flag low-confidence intent selections

**ClassificationAudit** (Phase 19)
- Runs intent + context + coherence check before every response
- _COHERENCE dict: (intent, context) → risk_level override
- project_mod + deployment/database → HIGH risk
- int_conf < 0.3 bumps overall_risk to MEDIUM
- Attaches full audit dict to resp["data"]["audit"]

**SelfCorrectionEngine** (Phase 18)
- 4 checks before response returns:
  1. Generic fallback marker detection (e.g. "لم أستطع تحديد") for project intents
  2. Evidence score: fraction of scanned files referenced in response text
  3. Short response warning for project intents (< 80 chars)
  4. Missing func/file evidence for deep intents (dependency, root_cause, impact, etc.)
- Returns: ok (bool), issues ([str]), warnings ([str]), evidence_score (float)
- Issues = critical failures; warnings = soft flags (response still sent)

## Surgical edits to ai_engine.py (3 changes)

1. **Import block** (after _KG_OK block): try/except for _CE, _CA, _SCE, _IC;
   sets _CE_OK flag; all callers guarded against None.

2. **process_chat, after detect_intent()**: ContextEngine.detect(msg) runs;
   result stored in _ctx_result; logged at DEBUG level; fail-safe try/except.

3. **process_chat, after resp = fn()**: SelfCorrectionEngine.verify() runs;
   ClassificationAudit.run() runs; both results attached to resp["data"]:
   - resp["data"]["context"]      → detected subsystem name
   - resp["data"]["ctx_conf"]     → confidence float
   - resp["data"]["ctx_evidence"] → matched signals (max 5)
   - resp["data"]["correction"]   → SelfCorrection result dict
   - resp["data"]["audit"]        → ClassificationAudit result dict

## Verification results (23/23)
- Context Engine: 10/10 subsystem detection
- Routing suite:  13/13 intent routing (no regressions)
- _CE_OK=True, _CALL_GRAPH_OK=True, _KG_OK=True all live

## Key design notes
- Context confidence values are LOW (0.05–0.17) by design — these are sparse signals
  from short user messages, not document classifiers. The top-ranked context is still
  useful for audit/risk even at low absolute confidence.
- "router_layer" vs "api_layer" ambiguity: solved by removing "endpoint" from
  router_layer and adding compound phrases to api_layer (2025-06-19).
- All 4 classes are fail-safe — _CE_OK=False degrades gracefully (no metadata attached,
  no crash).

## Why
Phases 11/12/18/19 required an explicit context layer separate from intent routing.
Without it, the agent cannot know *which subsystem* the user is asking about, cannot
score intent confidence, cannot verify that responses contain real evidence, and cannot
generate risk metadata for the frontend audit panel.
