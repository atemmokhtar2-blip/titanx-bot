"""
evidence_engine.py — Phase 2 Systems Only

SCOPE: Evidence Engine · Verification Layer · Project Understanding Core

MANDATORY FLOW (enforced by every Phase-2-compliant handler):
    Question → Analysis → Evidence Collection → Verification → Answer

FORBIDDEN:
    Guessing · Estimating · Assuming · Inferring without proof

If proof is missing → return NO_EVIDENCE_RESPONSE
"""
import os
import re
from pathlib import Path
from typing import Optional

# ── Project root (resolved at import time) ───────────────────────────────────
_HERE      = Path(__file__).parent           # control_panel/
_PROJ_ROOT = _HERE.parent                    # extracted_project/

# ── Subsystem classification ─────────────────────────────────────────────────
_SUBSYSTEM_MARKERS: list = [
    ("ai_engine",     ["ai_engine.py", "ai_assistant.py", "routers/ai_workspace"]),
    ("control_panel", ["control_panel/routers/", "control_panel/templates/",
                       "control_panel/static/", "control_panel/app.py",
                       "control_panel/config.py"]),
    ("support_bot",   ["support_bot/"]),
    ("telegram_bot",  ["bot.py", "handlers/", "locales"]),
    ("database",      ["database/", "db.py", ".db", "models.py"]),
    ("config",        ["config/settings.py", "config/__init__", "control_panel/config.py"]),
]

def detect_subsystem(file_path: str) -> str:
    """Classify which subsystem owns file_path — verified against known markers."""
    fp = file_path.replace("\\", "/")
    for system, markers in _SUBSYSTEM_MARKERS:
        if any(m in fp for m in markers):
            return system
    return "project"


# ── File existence (MUST be verified before citing) ─────────────────────────
def verify_file_exists(file_path: str) -> bool:
    """Return True only if the file is physically present on disk. No guessing."""
    p = Path(file_path)
    if p.is_absolute():
        return p.exists()
    for base in [_PROJ_ROOT, _PROJ_ROOT.parent, _HERE]:
        if (base / file_path).exists():
            return True
    return False

def _abs_path(file_path: str) -> Optional[Path]:
    """Resolve file_path → absolute Path, or None if not on disk."""
    p = Path(file_path)
    if p.is_absolute():
        return p if p.exists() else None
    for base in [_PROJ_ROOT, _PROJ_ROOT.parent, _HERE]:
        candidate = base / file_path
        if candidate.exists():
            return candidate
    return None


# ── Function / class verification (MUST grep real file content) ──────────────
def find_functions_in_file(file_path: str, query_terms: list) -> list:
    """
    Verify function existence by reading the actual file.
    Returns list of {"name": str, "line_no": int, "evidence": str}.
    Only returns entries confirmed in real file content — no inference.
    """
    abs_p = _abs_path(file_path)
    if abs_p is None:
        return []

    results: list = []
    try:
        file_lines = abs_p.read_text(errors="ignore").splitlines()
        for i, line in enumerate(file_lines, 1):
            stripped = line.strip()
            m = re.match(r"(?:async\s+)?def\s+(\w+)|class\s+(\w+)", stripped)
            if m:
                name = m.group(1) or m.group(2)
                line_lower = (stripped + " " + name).lower()
                for term in query_terms:
                    if len(term) > 2 and term.lower() in line_lower:
                        results.append({
                            "name": name,
                            "line_no": i,
                            "evidence": stripped[:120],
                        })
                        break
    except Exception:
        pass
    return results


# ── Evidence line extraction (grep real file content) ───────────────────────
def grep_file_evidence(file_path: str, terms: list, max_hits: int = 3) -> list:
    """
    Find lines in a file containing any of the query terms.
    Returns list of {"line_no": int, "text": str}.
    Only returns real code lines — no inference.
    """
    abs_p = _abs_path(file_path)
    if abs_p is None:
        return []

    hits: list = []
    try:
        file_lines = abs_p.read_text(errors="ignore").splitlines()
        for i, line in enumerate(file_lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            line_lower = stripped.lower()
            for term in terms:
                if len(term) > 2 and term.lower() in line_lower:
                    hits.append({"line_no": i, "text": stripped[:150]})
                    break
            if len(hits) >= max_hits:
                break
    except Exception:
        pass
    return hits


# ── Import verification (verify actual import statement exists) ──────────────
def find_import_lines(file_path: str, target: str) -> list:
    """
    Find lines in file_path that import target module.
    Returns list of {"line_no": int, "text": str}.
    Only returns verified import statements from real file content.
    """
    abs_p = _abs_path(file_path)
    if abs_p is None:
        return []

    # Normalise target: "config/settings.py" → "settings", "config.settings"
    target_norm  = target.replace("/", ".").replace(".py", "").replace("\\", ".")
    target_short = target_norm.split(".")[-1]

    hits: list = []
    try:
        file_lines = abs_p.read_text(errors="ignore").splitlines()
        for i, line in enumerate(file_lines, 1):
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                if target_short in stripped or target_norm in stripped:
                    hits.append({"line_no": i, "text": stripped[:150]})
    except Exception:
        pass
    return hits


# ── Router evidence (verify which router file + function serves a concept) ───
def find_router_for_concept(concept: str) -> list:
    """
    Search all router files for @router.get/post/put/delete decorators
    matching concept.  Also checks app.py include_router calls.

    Returns list of {router_file, prefix, function, route, evidence_line,
                     line_no, include_evidence} — sorted by match score.
    Only returns entries verified in real file content.
    """
    routers_dir = _PROJ_ROOT / "control_panel" / "routers"
    if not routers_dir.exists():
        routers_dir = _PROJ_ROOT.parent / "control_panel" / "routers"
    app_py = _PROJ_ROOT / "control_panel" / "app.py"

    concept_lower = concept.lower().strip("/")
    concept_parts = [p for p in re.split(r"[\s/_\-]+", concept_lower) if len(p) > 2]
    results: list = []

    # ── Step 1: scan router files ────────────────────────────────────────────
    if routers_dir.exists():
        for rf in sorted(routers_dir.glob("*.py")):
            try:
                content    = rf.read_text(errors="ignore")
                file_lines = content.splitlines()

                # Router prefix from APIRouter definition
                prefix = ""
                pm = re.search(r'APIRouter\(.*?prefix=["\']([^"\']+)["\']', content)
                if pm:
                    prefix = pm.group(1)

                rel = f"control_panel/routers/{rf.name}"

                for i, line in enumerate(file_lines):
                    stripped = line.strip()
                    dm = re.match(
                        r'@router\.(get|post|put|delete|patch)\(["\']([^"\']*)["\']',
                        stripped,
                    )
                    if dm:
                        route_path = dm.group(2)
                        full_route = (prefix + "/" + route_path.lstrip("/")).rstrip("/") or "/"
                        route_norm = full_route.lower()

                        # Score: how many concept parts appear in route or filename?
                        fname_lower = rf.stem.lower()
                        score = sum(
                            1
                            for cp in concept_parts
                            if cp in route_norm or cp in fname_lower
                        )
                        if score == 0:
                            # Broader check: concept substring in route or file name
                            score = 1 if (concept_lower in route_norm
                                          or concept_lower in fname_lower
                                          or any(cp in fname_lower for cp in concept_parts)) else 0

                        if score > 0:
                            func_name = None
                            for j in range(i + 1, min(i + 6, len(file_lines))):
                                fm = re.match(r"\s*(?:async\s+)?def\s+(\w+)", file_lines[j])
                                if fm:
                                    func_name = fm.group(1)
                                    break

                            # Find include_router line in app.py for prefix evidence
                            include_ev = ""
                            if app_py.exists():
                                try:
                                    app_src = app_py.read_text(errors="ignore")
                                    stem    = rf.stem
                                    inc_m   = re.search(
                                        rf'app\.include_router\({stem}\.router[^)]*\)',
                                        app_src,
                                    )
                                    if inc_m:
                                        include_ev = inc_m.group(0)
                                except Exception:
                                    pass

                            results.append({
                                "router_file":      rel,
                                "prefix":           prefix,
                                "function":         func_name or "unknown",
                                "route":            full_route,
                                "evidence_line":    stripped[:120],
                                "line_no":          i + 1,
                                "include_evidence": include_ev,
                                "score":            score,
                            })
            except Exception:
                pass

    # ── Step 2: scan app.py for direct @app.get/post routes ─────────────────
    # Routes defined directly on the FastAPI `app` object (login, panel, etc.)
    # are invisible to the routers-directory scan above.  Scan app.py explicitly.
    if app_py.exists():
        try:
            content    = app_py.read_text(errors="ignore")
            file_lines = content.splitlines()
            rel_app    = "control_panel/app.py"

            for i, line in enumerate(file_lines):
                stripped = line.strip()
                dm = re.match(
                    r'@app\.(get|post|put|delete|patch)\(["\']([^"\']*)["\']',
                    stripped,
                )
                if dm:
                    route_path = dm.group(2)
                    route_norm = route_path.lower()

                    score = sum(
                        1
                        for cp in concept_parts
                        if cp in route_norm
                    )
                    if score == 0:
                        score = 1 if concept_lower in route_norm else 0

                    if score > 0:
                        func_name = None
                        for j in range(i + 1, min(i + 8, len(file_lines))):
                            fm = re.match(r"\s*(?:async\s+)?def\s+(\w+)", file_lines[j])
                            if fm:
                                func_name = fm.group(1)
                                break

                        results.append({
                            "router_file":      rel_app,
                            "prefix":           "",
                            "function":         func_name or "unknown",
                            "route":            route_path,
                            "evidence_line":    stripped[:120],
                            "line_no":          i + 1,
                            "include_evidence": f"direct @app route in {rel_app}",
                            "score":            score + 1,  # boost: direct app routes are authoritative
                        })
        except Exception:
            pass

    results.sort(key=lambda x: x["score"], reverse=True)
    # Deduplicate by router_file (keep highest-scored entry per file)
    seen: set = set()
    deduped: list = []
    for r in results:
        key = r["router_file"]
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


# ── Keyboard / button function finder ────────────────────────────────────────
_KEYBOARD_PATTERNS = [
    "InlineKeyboardMarkup",
    "InlineKeyboardButton",
    "ReplyKeyboardMarkup",
    "KeyboardButton",
    "ReplyKeyboardRemove",
]
_KEYBOARD_SKIP = {"control_panel", "__pycache__", ".git", "node_modules"}

def find_keyboard_functions() -> list:
    """
    Find all functions that create Telegram keyboards by reading real files.
    Returns list of {file, function, line_no, evidence, keyboard_type}.
    No inference — only confirmed by actual code content.
    """
    results: list = []

    for py_file in sorted(_PROJ_ROOT.rglob("*.py")):
        rel = str(py_file.relative_to(_PROJ_ROOT)) if _PROJ_ROOT in py_file.parents else str(py_file)

        # Skip control panel internal files
        if any(skip in rel for skip in _KEYBOARD_SKIP):
            continue

        try:
            content = py_file.read_text(errors="ignore")
        except Exception:
            continue

        # Quick pre-check — skip files without any keyboard pattern
        if not any(kp in content for kp in _KEYBOARD_PATTERNS):
            continue

        file_lines = content.splitlines()
        current_func       = None
        current_func_line  = 0
        current_func_ev    = ""
        func_has_keyboard  = False
        kb_type            = ""

        for i, line in enumerate(file_lines, 1):
            stripped = line.strip()
            fm = re.match(r"(?:async\s+)?def\s+(\w+)", stripped)
            if fm:
                # Save previous function if it contained a keyboard call
                if current_func and func_has_keyboard:
                    results.append({
                        "file":          rel,
                        "function":      current_func,
                        "line_no":       current_func_line,
                        "evidence":      current_func_ev,
                        "keyboard_type": kb_type,
                    })
                current_func      = fm.group(1)
                current_func_line = i
                current_func_ev   = stripped[:120]
                func_has_keyboard = False
                kb_type           = ""

            if current_func:
                for kp in _KEYBOARD_PATTERNS:
                    if kp in stripped:
                        func_has_keyboard = True
                        if not kb_type:
                            kb_type = kp
                        break

        # Final function in file
        if current_func and func_has_keyboard:
            results.append({
                "file":          rel,
                "function":      current_func,
                "line_no":       current_func_line,
                "evidence":      current_func_ev,
                "keyboard_type": kb_type,
            })

    return results


# ── HTML template button / link finder ──────────────────────────────────────
_TEMPLATE_SKIP = {"__pycache__", ".git", "node_modules"}

def find_template_buttons(concept: str) -> list:
    """
    Find HTML button/link elements in Jinja2 templates matching concept.

    Verified by reading real .html files — no inference.
    Returns list of {file, line_no, text, element_type}.

    Used when the question is about a web-UI button (control panel / HTML page),
    NOT a Telegram keyboard button.
    """
    templates_dir = _PROJ_ROOT / "control_panel" / "templates"
    if not templates_dir.exists():
        templates_dir = _PROJ_ROOT.parent / "control_panel" / "templates"

    concept_parts = [p for p in re.split(r"[\s/_\-]+", concept.lower()) if len(p) > 2]
    results: list = []

    if not templates_dir.exists():
        return results

    for html_file in sorted(templates_dir.glob("*.html")):
        try:
            content    = html_file.read_text(errors="ignore")
            file_lines = content.splitlines()
            rel        = f"control_panel/templates/{html_file.name}"

            for i, line in enumerate(file_lines, 1):
                stripped   = line.strip()
                is_element = re.search(
                    r"<(?:button|a\s|input[^>]*type=[\"']button[\"']|input[^>]*type=[\"']submit[\"'])",
                    stripped, re.IGNORECASE,
                )
                if not is_element:
                    continue
                line_lower = stripped.lower()
                if any(cp in line_lower for cp in concept_parts) or not concept_parts:
                    elem_type = "button" if "<button" in line_lower else "link"
                    results.append({
                        "file":         rel,
                        "line_no":      i,
                        "text":         stripped[:150],
                        "element_type": elem_type,
                    })
        except Exception:
            pass

    return results


# ── Confidence scoring ───────────────────────────────────────────────────────
def calculate_confidence(
    file_exists: bool,
    functions_found: list,
    evidence_lines: list,
    import_lines: list = None,
) -> float:
    """
    Confidence 0.0–1.0 based only on verified evidence.
    No points awarded for unverified claims.

    PHASE 2 ENFORCEMENT:
        evidence_lines is MANDATORY to reach 🟢 (≥ 0.75) status.
        Without actual source code lines the score is hard-capped at 0.45 —
        the system CANNOT claim VERIFIED without code evidence.

    Score breakdown (evidence present):
        0.30  file verified on disk
        0.20  function definition confirmed in file
        0.35  actual source code lines found  ← MANDATORY signal
        0.15  import chain verified
        ────
        1.00  max

    Score breakdown (no evidence_lines):
        0.25  file exists on disk
        0.15  function definition found
        0.05  import chain
        0.45  hard cap — never 🟢
    """
    if not file_exists:
        return 0.0
    # ── PHASE 2: evidence_lines required for VERIFIED status ─────────────────
    if not evidence_lines:
        score = 0.25                        # File on disk (unverified content)
        if functions_found:
            score += 0.15                   # Function def found — still no code proof
        if import_lines:
            score += 0.05                   # Import chain found
        return round(min(score, 0.45), 2)  # Hard cap: CANNOT reach 🟢 without code lines
    # ── Full scoring (evidence_lines present) ─────────────────────────────────
    score = 0.30                            # File verified on disk
    if functions_found:
        score += 0.20                       # Function definition confirmed in file
    score += 0.35                           # Actual source code lines — MANDATORY
    if import_lines:
        score += 0.15                       # Import chain verified
    return round(min(score, 1.0), 2)


# ── Mandatory answer format (Subsystem/File/Function/Evidence/Confidence) ────
_VERIFIED_LABELS: set = {
    "✅ VERIFIED",
    "VERIFIED FROM SOURCE",
    "VERIFIED FROM HTML SOURCE",
    "VERIFIED",
}

def format_verified_answer(
    subsystem: str,
    file_path: str,
    function_name: Optional[str],
    evidence_lines: list,
    confidence: float,
    extra_lines: list = None,
    label: str = "✅ VERIFIED",
) -> str:
    """
    Mandatory Phase-2 answer format — must be appended to every handler output.

    Required fields:
        Subsystem · File · Function · Evidence · Confidence Score

    PHASE 2 ENFORCEMENT:
        The VERIFIED label is FORBIDDEN unless evidence_lines contains at least
        one real source code entry.  If evidence_lines is empty the label is
        unconditionally overridden to NOT VERIFIED — no caller can bypass this.
    """
    # ── PHASE 2: Override VERIFIED when there is no code evidence ────────────
    if not evidence_lines and label in _VERIFIED_LABELS:
        label = "⛔ NOT VERIFIED — No source code lines extracted"

    icon = "🟢" if confidence >= 0.75 else "🟡" if confidence >= 0.50 else "🔴"

    lines: list = [
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🔍 **Verification Report** — {label}",
        f"",
        f"🏗️ **Subsystem:** `{subsystem}`",
        f"📁 **File:** `{file_path}`",
    ]

    if function_name:
        lines.append(f"⚙️ **Function:** `{function_name}()`")

    if evidence_lines:
        lines.append("📋 **Evidence (verified from source):**")
        for ev in evidence_lines[:3]:
            if isinstance(ev, dict):
                lines.append(f"  `L{ev['line_no']}:` `{ev['text']}`")
            elif isinstance(ev, str):
                lines.append(f"  `{ev}`")
    else:
        lines.append("⚠️ **Reason:** No source code lines found matching search terms.")
        lines.append("📌 **Next step:** Rephrase using the exact function name or keyword.")

    if extra_lines:
        lines.extend(extra_lines)

    lines.append(f"")
    lines.append(f"{icon} **Confidence:** `{int(confidence * 100)}%`")

    return "\n".join(lines)


# ── No-evidence sentinel ─────────────────────────────────────────────────────
NO_EVIDENCE_RESPONSE = (
    "⛔ **NO EVIDENCE FOUND**\n\n"
    "لا يوجد دليل موثق يدعم هذه الإجابة.\n"
    "النظام لا يخمن ولا يستنتج.\n\n"
    "أعد الصياغة أو استخدم: `structure` · `routes` · `arch`"
)
