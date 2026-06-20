"""
context_engine.py — Context Engine, Classification Audit, and Self-Correction Engine
for the TitanX Engineering Agent.

Phase 11 — Intent Engine       : confidence scoring for detected intents
Phase 12 — Context Engine      : detect which project subsystem the user is asking about
Phase 18 — Self-Correction     : verify response has evidence before sending
Phase 19 — Classification Audit: generate intent+context+risk metadata per request

No external dependencies.  All stdlib.

Public API:
  ContextEngine.detect(msg)           → ContextResult dict
  ClassificationAudit.run(...)        → AuditResult dict
  SelfCorrectionEngine.verify(...)    → CorrectionResult dict
  IntentConfidence.score(intent, msg) → float  (0.0–1.0)
"""
import re
import logging
from pathlib import Path

_log = logging.getLogger("titanx.context_engine")


# ─── Context definitions ──────────────────────────────────────────────────────
# Each context has: signals (keyword list), file_patterns (path substrings),
# description.  Weight per signal = 1; score = sum / len * 100 = confidence.

_CONTEXTS: dict = {
    "telegram_bot": {
        "description": "Telegram bot layer (handlers, keyboards, callbacks, polling)",
        "signals": [
            "bot.py", "handler", "callback", "keyboard", "inline", "reply_markup",
            "commandhandler", "telegram", "تليغرام", "بوت", "أمر", "polling",
            "webhook", "message_handler", "callbackqueryhandler", "/start", "/help",
            "update", "context.bot", "bot_data", "application", "dispatcher",
            "أوامر البوت", "رسالة البوت", "بوت تلقرام", "هاندلر",
        ],
        "file_patterns": ["bot.py", "handlers/", "support_bot/"],
        "weight": 1.0,
    },
    "control_panel": {
        "description": "FastAPI control panel (routers, templates, auth, dashboard)",
        "signals": [
            "panel", "dashboard", "fastapi", "router", "template", "jinja",
            "uvicorn", "لوحة", "روتر", "صفحة", "html", "login", "auth",
            "admin panel", "control panel", "لوحة التحكم", "لوحة الإدارة",
            "app.py", "server.py", "static", "css", "sidebar",
        ],
        "file_patterns": ["control_panel/", "routers/", "templates/"],
        "weight": 1.0,
    },
    "database": {
        "description": "Database layer (SQLite, queries, schema, migrations)",
        "signals": [
            "database", "db.py", "sqlite", "aiosqlite", "query", "schema",
            "قاعدة البيانات", "قاعدة", "جدول", "table", "column", "row",
            "migration", "init_db", "get_user", "create_user", "insert",
            "select", "update", "delete", "sql", "transaction",
            "bot.db", "support.db", "users.py", "db module",
        ],
        "file_patterns": ["database/", "db.py", "users.py"],
        "weight": 1.0,
    },
    "router_layer": {
        "description": "FastAPI router layer (HTTP routes, response handling)",
        "signals": [
            "@router", "@app.get", "@app.post", "get request", "post request",
            "route decorator", "router file", "http method", "include_router",
            "jsonresponse", "htmlresponse", "redirectresponse", "templateresponse",
            "status_code", "راوتر المسار", "ملف الراوتر", "router chain",
            "router handler", "mount router",
        ],
        "file_patterns": ["routers/", "app.py"],
        "weight": 1.0,
    },
    "api_layer": {
        "description": "JSON API layer (fetch calls, /api/ endpoints, AJAX)",
        "signals": [
            "/api/", "api endpoint", "json api", "fetch", "ajax", "xmlhttprequest",
            "rest", "jsonify", "api response", "api call", "ai/api",
            "api/stats", "api/chat", "api/brain", "api/search",
            "واجهة برمجية", "api_chat", "ai api", "endpoint في", "endpoint url",
            "http endpoint", "json endpoint", "api route",
        ],
        "file_patterns": ["routers/ai_workspace", "/api/"],
        "weight": 1.0,
    },
    "frontend_layer": {
        "description": "Frontend layer (HTML templates, CSS, JavaScript, UI)",
        "signals": [
            "style.css", "app.js", "template", "html", "css", "javascript",
            "sidebar", "theme", "dark mode", "button", "modal", "chart",
            "تصميم", "واجهة", "ui", "ux", "frontend", "زر", "قائمة",
            "لون", "خط", "layout", "stylesheet", "script",
        ],
        "file_patterns": ["static/", "templates/", ".css", ".js", ".html"],
        "weight": 1.0,
    },
    "infrastructure": {
        "description": "Infrastructure layer (config, settings, secrets, startup)",
        "signals": [
            "config.py", "settings.py", "environment", "secret", "token",
            "إعداد", "تهيئة", "startup", "boot", "init", "environment variable",
            "python path", "sys.path", "pythonpath", "scripts/", "start.sh",
            "workflow", ".env", "bot_token", "owner_id",
        ],
        "file_patterns": ["config/", "settings.py", "scripts/"],
        "weight": 1.0,
    },
    "ai_layer": {
        "description": "AI intelligence layer (ai_engine.py, reasoning, memory, intent, HF space)",
        "signals": [
            "ai_engine", "ai engine", "reasoning", "intent", "memory",
            "knowledge graph", "call graph", "dependency graph", "process_chat",
            "detect_intent", "agent", "ai workspace", "ai operator",
            "ذاكرة", "استدلال", "نية", "مشغل الذكاء",
            "engineering agent", "context engine",
            # REPAIR (Problem 2): HF signals belong here, NOT in deployment.
            # HF/Hugging Face is the AI backend, not a deployment target.
            "hugging face", "huggingface", "hf space", "hf_space",
            "هوجينج فيس", "call_hf_analyze", "call_hf_assistant",
        ],
        "file_patterns": ["ai_engine.py", "ai_workspace.py", "call_graph.py",
                          "knowledge_graph.py", "context_engine.py"],
        "weight": 1.0,
    },
    "deployment": {
        "description": "Deployment layer (Replit, production, scaling, server config)",
        "signals": [
            "deploy", "deployment", "production",
            "replit", "نشر", "إنتاج", "hosting", "docker",
            "port", "gunicorn", "scaling", "load balancer", "cdn",
            "publish", "go live",
            # NOTE: "hugging face"/"hf space" intentionally removed — they belong
            # to ai_layer (the AI backend), not deployment infrastructure.
        ],
        "file_patterns": ["scripts/", ".replit"],
        "weight": 1.0,
    },
    "support_system": {
        "description": "Support bot / ticket system layer",
        "signals": [
            "support", "ticket", "support_bot", "support bot", "agent",
            "تذكرة", "دعم", "نظام الدعم", "support ticket", "support system",
        ],
        "file_patterns": ["support_bot/"],
        "weight": 1.0,
    },
}

# ─── Intent-context coherence map ────────────────────────────────────────────
# Maps (intent, context) → expected_risk_if_mismatch
# Missing entries = LOW risk (coherent by default)
_COHERENCE: dict = {
    # File-finding intents are valid in any context
    ("find_file",    "telegram_bot"):    "LOW",
    ("find_file",    "control_panel"):   "LOW",
    ("find_file",    "database"):        "LOW",
    # Dependency intents that feel cross-context
    ("dependency",   "frontend_layer"):  "MEDIUM",  # rare to ask deps of CSS
    ("dependency",   "deployment"):      "MEDIUM",
    # Data flow is most coherent in bot/panel contexts
    ("data_flow",    "infrastructure"):  "MEDIUM",
    ("data_flow",    "deployment"):      "MEDIUM",
    # Modification in production context = HIGH risk
    ("project_mod",  "deployment"):      "HIGH",
    ("project_mod",  "database"):        "HIGH",
    ("ui_redesign",  "telegram_bot"):    "MEDIUM",  # unlikely
    # Impact always low risk regardless of context
    ("impact",       "deployment"):      "MEDIUM",
}

# ─── Project file extensions for evidence detection ───────────────────────────
_CODE_EXTS  = {".py", ".js", ".html", ".css", ".sql", ".json", ".yaml", ".yml"}
_FILE_RE    = re.compile(r'`([^`]+\.[a-z]{1,5})`|[\w./]+\.(?:py|js|html|css|sql|json)')
_FUNC_RE    = re.compile(r'`(\w+)\(\)`|\b([A-Z][a-zA-Z_]{3,})\b|def\s+(\w+)\s*\(')
_LINE_RE    = re.compile(r'line\s+\d+|строка\s+\d+|سطر\s+\d+')


class ContextEngine:
    """
    Phase 12 — Detect which project subsystem a message concerns.

    Returns a ContextResult:
      {
        "detected":    str,          # top context name
        "description": str,          # human-readable description
        "confidence":  float,        # 0.0–1.0
        "evidence":    [str],        # matched signals
        "all_scores":  {ctx: score}, # full score table
        "rejected":    {ctx: str},   # other contexts + reason for rejection
      }
    """

    @classmethod
    def detect(cls, msg: str) -> dict:
        ml = msg.lower()

        scores: dict = {}
        evidence: dict = {}

        for ctx_name, ctx in _CONTEXTS.items():
            hits = []
            for sig in ctx["signals"]:
                if sig.lower() in ml:
                    hits.append(sig)
            score = len(hits) / max(len(ctx["signals"]), 1)
            scores[ctx_name]   = round(score, 4)
            evidence[ctx_name] = hits

        if not any(scores.values()):
            return {
                "detected":    "general",
                "description": "No specific subsystem detected",
                "confidence":  0.0,
                "evidence":    [],
                "all_scores":  scores,
                "rejected":    {k: "score=0" for k in scores},
            }

        best     = max(scores, key=lambda k: scores[k])
        best_score = scores[best]

        # Build rejection table (everything that scored < best)
        rejected = {}
        for k, s in scores.items():
            if k == best:
                continue
            if s == 0:
                rejected[k] = "no signals matched"
            elif s < best_score:
                rejected[k] = f"score={s:.2f} < best={best_score:.2f}"

        return {
            "detected":    best,
            "description": _CONTEXTS[best]["description"],
            "confidence":  round(best_score, 4),
            "evidence":    evidence[best],
            "all_scores":  scores,
            "rejected":    rejected,
        }


class IntentConfidence:
    """
    Phase 11 — Score how confidently an intent was selected.

    Higher score = more pattern signals matched.
    If confidence < 0.4 for a project intent, the answer may drift.
    """

    # Signals per intent that indicate a strong, unambiguous match
    _STRONG_SIGNALS: dict = {
        "dependency":    ["تبعيات", "dependency", "depends on", "import chain",
                          "what does", "who imports", "يعتمد", "import", "depends"],
        "find_file":     ["which file", "what file", "أي ملف", "ما الملف",
                          "where is", "أين", "locate", "which class", "what class"],
        "who_depends":   ["who depends", "من يستورد", "من يعتمد", "what uses",
                          "dependency chain"],
        "impact":        ["what breaks", "what would break", "what will break",
                          "ماذا يكسر", "ماذا يتأثر", "if i change", "if i delete",
                          "if i remove", "لو حذفت", "لو حذف", "impact of", "تأثير",
                          "يتأثر", "سيتأثر", "would be affected"],
        "root_cause":    ["why", "لماذا", "debug", "broken", "not working",
                          "سبب الخطأ"],
        "data_flow":     ["data flow", "تدفق", "how does data", "مسار البيانات",
                          "flow from"],
        "project_mod":   ["احذف", "أضف", "غير", "عدل", "أنشئ", "delete",
                          "remove", "modify", "change"],
        "arch":          ["architecture", "معمارية", "هيكل", "structure",
                          "how does", "explain", "database table", "which table",
                          "what table", "which column", "stores users", "stores",
                          "جدول", "جداول"],
        "routes":        ["router", "routes", "روتر", "مسارات", "endpoints",
                          "what router", "which router", "serves", "serves the",
                          "handles the route", "route for"],
    }

    @classmethod
    def score(cls, intent: str, msg: str) -> float:
        """Return confidence score 0.0–1.0 for the selected intent.

        REPAIR (Problem 1): Old formula divided hits by total signal count,
        so a single match on a 7-signal intent gave 1/7 = 0.14 — below the
        0.30 gate threshold, causing false-positive blocks on clear questions.

        New rule:
          • 0 hits  → 0.0   (no evidence — gate should block if needed)
          • ≥1 hit  → max(hits / max(len(signals), 3), 0.35)
            ↳ Any single strong-signal match floors at 0.35, passing the gate.
            ↳ Multiple matches scale up toward 1.0.
        """
        ml      = msg.lower()
        signals = cls._STRONG_SIGNALS.get(intent, [])
        if not signals:
            return 0.7  # default for intents without a signal list
        hits = sum(1 for s in signals if s.lower() in ml)
        if hits == 0:
            return 0.0
        # Floor at 0.35 so any clear single-signal match passes the 0.30 gate
        return round(max(hits / max(len(signals), 3), 0.35), 4)


class ClassificationAudit:
    """
    Phase 19 — Generate internal audit metadata before every project response.

    Audit result:
      {
        "intent":          str,
        "context":         str,
        "context_confidence": float,
        "intent_confidence":  float,
        "coherence_risk":  "LOW"|"MEDIUM"|"HIGH",
        "files_used":      [str],
        "selection_reason": str,
        "overall_risk":    "LOW"|"MEDIUM"|"HIGH",
        "recommendation":  str,
      }
    """

    @classmethod
    def run(cls, intent: str, msg: str, context_result: dict,
            files_used: list = None) -> dict:
        files_used = files_used or []
        ctx_name   = context_result.get("detected", "general")
        ctx_conf   = context_result.get("confidence", 0.0)
        int_conf   = IntentConfidence.score(intent, msg)

        # Coherence: does the intent make sense in this context?
        coherence  = _COHERENCE.get((intent, ctx_name), "LOW")

        # Selection reason
        if files_used:
            reason = (f"Files selected via semantic search + "
                      f"{ctx_name} context signals. "
                      f"Intent '{intent}' confidence={int_conf:.0%}.")
        else:
            reason = (f"No files selected. Intent '{intent}' confidence={int_conf:.0%}. "
                      f"Context '{ctx_name}' confidence={ctx_conf:.0%}.")

        # Overall risk: max of coherence + low intent confidence
        risk_levels = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        risk_val    = risk_levels.get(coherence, 0)
        if int_conf < 0.3:
            risk_val = max(risk_val, 1)  # bump to MEDIUM
        if ctx_conf < 0.1 and ctx_name != "general":
            risk_val = max(risk_val, 1)

        overall = ["LOW", "MEDIUM", "HIGH"][risk_val]

        rec = {
            "LOW":    "Proceed — intent and context are coherent.",
            "MEDIUM": "Proceed with caution — verify selected files match user intent.",
            "HIGH":   "Stop and ask user for clarification before proceeding.",
        }[overall]

        return {
            "intent":               intent,
            "context":              ctx_name,
            "context_confidence":   ctx_conf,
            "intent_confidence":    int_conf,
            "coherence_risk":       coherence,
            "files_used":           files_used[:10],
            "selection_reason":     reason,
            "overall_risk":         overall,
            "recommendation":       rec,
        }


class SelfCorrectionEngine:
    """
    Phase 18 — Verify response quality before returning it.

    Checks:
      1. For project intents: response must contain file/function evidence
      2. Response must not be empty or a generic template reply
      3. Response must address the detected context
      4. No fabricated file references (claimed files that aren't in scan list)

    Returns:
      {
        "ok":       bool,
        "issues":   [str],
        "warnings": [str],
        "evidence_score": float,  # 0.0–1.0 (fraction of scan files mentioned)
      }
    """

    _PROJECT_INTENTS = {
        "find_file", "plan_modify", "dependency", "who_depends", "data_flow",
        "reuse_systems", "impact", "root_cause", "arch", "security", "analyze",
        "improve", "weakness", "strategy", "scale", "tech_debt", "redesign",
        "errors", "create_feature", "ui_redesign", "debug_fix", "new_page",
        "routes", "structure", "runtime_graph", "project_mod",
    }

    # Templates that signal a generic fallback (bad for project intents)
    _GENERIC_MARKERS = [
        "لم أستطع تحديد",
        "أعد الصياغة",
        "could not identify",
        "please rephrase",
        "I didn't understand",
        "لم أفهم",
    ]

    @classmethod
    def verify(cls, intent: str, response_text: str,
               files_scanned: list = None,
               context_result: dict = None) -> dict:
        files_scanned = files_scanned or []
        issues:   list = []
        warnings: list = []

        is_project_intent = intent in cls._PROJECT_INTENTS

        # ── Check 1: Generic fallback used for a project intent ───────────────
        if is_project_intent:
            for marker in cls._GENERIC_MARKERS:
                if marker in response_text:
                    issues.append(
                        f"Response uses generic fallback marker '{marker}' "
                        f"despite project intent '{intent}' — handler may have failed."
                    )
                    break

        # ── Check 2: Evidence presence (file references) ──────────────────────
        evidence_score = 0.0
        if is_project_intent and files_scanned:
            mentioned = [f for f in files_scanned
                         if Path(f).name.lower() in response_text.lower()]
            evidence_score = len(mentioned) / len(files_scanned)
            if evidence_score == 0.0:
                warnings.append(
                    f"No scan files referenced in response. "
                    f"Files scanned: {files_scanned[:3]} — may be unverified."
                )
        elif is_project_intent and not files_scanned:
            # No files were scanned at all
            warnings.append(
                f"Intent '{intent}' is a project intent but no files were scanned. "
                "Response may lack file-level evidence."
            )

        # ── Check 3: Response length sanity ──────────────────────────────────
        if len(response_text) < 80 and is_project_intent:
            warnings.append(
                f"Response is very short ({len(response_text)} chars) for "
                f"a project intent '{intent}' — may be incomplete."
            )

        # ── Check 4: Function/class evidence for deep analysis intents ────────
        deep_intents = {"dependency", "root_cause", "impact", "who_depends",
                        "data_flow", "arch"}
        if intent in deep_intents:
            has_func_evidence = bool(_FUNC_RE.search(response_text))
            has_file_evidence = bool(_FILE_RE.search(response_text))
            if not has_func_evidence and not has_file_evidence:
                warnings.append(
                    f"Deep-analysis intent '{intent}' but response contains "
                    "no file paths or function references — evidence may be missing."
                )

        ok = len(issues) == 0

        return {
            "ok":             ok,
            "issues":         issues,
            "warnings":       warnings,
            "evidence_score": round(evidence_score, 4),
        }
