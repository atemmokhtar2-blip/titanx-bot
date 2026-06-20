---
name: Phase 2 Maturity Repair
description: AI Maturity Phase 2 — Evidence Extraction + Verification Layer root-cause repairs in evidence_engine.py and _r_find_file(). 17/17 tests pass.
---

## Root Causes Fixed

### RC1: `calculate_confidence()` — false 🟢 without code evidence
**Problem:** `file_exists(0.40) + functions_found(0.35) = 0.75 → 🟢 VERIFIED` even when `evidence_lines=[]`.
**Fix:** Hard-cap at 0.45 when `evidence_lines` is empty.  Evidence lines are now a **mandatory** signal to reach 🟢.
- No evidence: max 0.45 (file=0.25 + func=0.15 + import=0.05)
- With evidence: file=0.30 + func=0.20 + evidence=0.35 + import=0.15 = max 1.00

### RC2: `format_verified_answer()` — VERIFIED label without proof
**Problem:** Output "✅ VERIFIED" regardless of whether `evidence_lines` has content.
**Fix:** `_VERIFIED_LABELS` set guards the label — if `evidence_lines=[]` AND label is in the set, override to `"⛔ NOT VERIFIED — No source code lines extracted"`. Adds ⚠️ Reason + Next step lines instead of evidence block.

### RC3: `_r_find_file()` — ownership text instead of source code evidence
**Problem:** Only searched primary file; terms from concept words only (too narrow); returned ownership list + empty verification block.
**Fix (multiple sub-fixes):**
1. **Stop-word filtering** — `_STOP_WORDS` set removes "file", "what", "html", "render" etc. so only domain keywords survive (e.g. "admin", "panel", "button")
2. **Multi-file search** — loops up to 5 candidate files instead of just primary
3. **HTML filename injection** — for `.html` questions injects full filename ("access.html") + stem + "TemplateResponse" as terms; direct substring match finds `TemplateResponse(request, "access.html", ...)`
4. **TemplateResponse float** — for template questions, re-orders ev_lines to put TemplateResponse/.html matches first before display truncation ([:4])
5. **Route decorator search** — for route questions, extra grep for `@app.post`, `@router.` etc.
6. **Clean template_buttons concept** — passes filtered terms (not full question) to `_ev_template_buttons()`
7. **NO EVIDENCE gate** — if zero code lines across ALL files → returns explicit `⛔ NO SOURCE CODE EVIDENCE` with list of files searched + terms used

## Files Modified
- `extracted_project/control_panel/evidence_engine.py` (calculate_confidence, format_verified_answer, _VERIFIED_LABELS set)
- `extracted_project/control_panel/ai_engine.py` (_r_find_file rewrite)

## Test Results
- 17/17 mandatory checks PASS
- All 5 mandatory scenario tests verified
- Both files AST-parse clean

**Why:** VERIFIED without proof is worse than NO ANSWER — users make wrong decisions based on false confidence. The enforcement is intentionally strict: any caller that passes an empty evidence_lines list cannot claim VERIFIED regardless of confidence score.

**How to apply:** If adding a new handler that uses _ev_format(), always ensure evidence_lines is populated before calling. If ev_lines=[], return _NO_EVIDENCE explicitly rather than appending an empty verification block.
