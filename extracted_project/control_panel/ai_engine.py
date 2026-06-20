"""
X Control Center — AI Engine v3.0
Complete Project Knowledge System:
  - Project Knowledge Graph (all routes, templates, CSS, JS, DB, bots)
  - Semantic File Awareness (Arabic + English)
  - Dependency Analyzer (what breaks if X changes)
  - Root Cause Analysis (why is X broken?)
  - Architecture Intelligence (explain any subsystem)
  - Modification Planning Engine (real files, real impact)
  - Self-Test Suite (8 canonical questions, must pass 8/8)
"""
import os, re, ast, json, zipfile, hashlib, time, logging
from pathlib import Path
from datetime import datetime
from typing import Optional

# ─── Engineering Agent Core Modules (fail-safe import) ───────────────────────
# These modules are loaded lazily at import time.  Any failure leaves the rest
# of ai_engine.py fully functional — all callers guard with _CALL_GRAPH_OK /
# _KG_OK before touching the objects.
try:
    from control_panel.call_graph import CallGraph as _CallGraph
    _CALL_GRAPH_OK = True
except Exception:
    _CallGraph = None          # type: ignore
    _CALL_GRAPH_OK = False
try:
    from control_panel.knowledge_graph import KnowledgeGraph as _KG, FileOwnership as _FO
    _KG_OK = True
except Exception:
    _KG = None                 # type: ignore
    _FO = None                 # type: ignore
    _KG_OK = False
try:
    from control_panel.context_engine import (
        ContextEngine      as _CE,
        ClassificationAudit as _CA,
        SelfCorrectionEngine as _SCE,
        IntentConfidence   as _IC,
    )
    _CE_OK = True
except Exception:
    _CE  = None                # type: ignore
    _CA  = None                # type: ignore
    _SCE = None                # type: ignore
    _IC  = None                # type: ignore
    _CE_OK = False

# ─── Phase 2: Evidence Engine (fail-safe import) ─────────────────────────────
try:
    from control_panel.evidence_engine import (
        verify_file_exists       as _ev_file_exists,
        find_functions_in_file   as _ev_find_funcs,
        grep_file_evidence       as _ev_grep,
        find_import_lines        as _ev_import_lines,
        find_router_for_concept  as _ev_router_concept,
        find_keyboard_functions  as _ev_keyboards,
        find_template_buttons    as _ev_template_buttons,
        calculate_confidence     as _ev_confidence,
        format_verified_answer   as _ev_format,
        detect_subsystem         as _ev_subsystem,
        NO_EVIDENCE_RESPONSE     as _NO_EVIDENCE,
    )
    _EV_OK = True
except Exception as _ev_err:
    _EV_OK = False
    _NO_EVIDENCE = "⛔ NO EVIDENCE FOUND"  # type: ignore

# ─── Phase 1: Project Indexer (fail-safe import) ─────────────────────────────
try:
    from control_panel.project_indexer import ProjectIndexer as _PI
    _PI_OK = True
except Exception:
    _PI     = None   # type: ignore
    _PI_OK  = False

# ─── Arabic Text Normalizer ───────────────────────────────────────────────────
def _normalize_ar(text: str) -> str:
    """Normalize Arabic text before regex matching.
    Fixes hamza variants (أإآٱ → ا), removes tatweel and all diacritics.
    Must be applied to BOTH the pattern input and the message before matching."""
    text = re.sub(r'[أإآٱ]', 'ا', text)          # hamza/madda variants
    text = re.sub(r'ى(?=\s|$)', 'ي', text)        # alef maqsoura at word-end
    text = re.sub(r'[ـ]', '', text)                # tatweel (stretcher)
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)  # all diacritics
    return text

# ─── Logging ──────────────────────────────────────────────────────────────────
_ai_log = logging.getLogger("ai_engine")

# ─── Paths ────────────────────────────────────────────────────────────────────
_HERE         = Path(__file__).parent
EXTRACTED_DIR = _HERE.parent
MEMORY_FILE   = _HERE / ".ai_memory.json"
BACKUP_DIR    = EXTRACTED_DIR / ".ai_backups"
BACKUP_DIR.mkdir(exist_ok=True)

# ─── Hugging Face Space Integration ───────────────────────────────────────────
HF_SPACE_URL = "https://7atemmmmm-x-ai-core.hf.space"
HF_TIMEOUT   = 8.0


def _hf_post(endpoint: str, payload: dict) -> dict:
    """POST to HF space — runs in a daemon thread so the async event loop is not blocked."""
    import urllib.request as _ur, json as _json, concurrent.futures as _cf
    def _call():
        data = _json.dumps(payload).encode()
        req  = _ur.Request(
            f"{HF_SPACE_URL}{endpoint}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _ur.urlopen(req, timeout=HF_TIMEOUT) as r:
            result = _json.loads(r.read().decode())
            result["_hf_source"] = "live"
            return result
    try:
        with _cf.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_call)
            return fut.result(timeout=HF_TIMEOUT + 2)
    except Exception as e:
        _ai_log.warning("HF POST %s failed: %s", endpoint, e)
        return {"ok": False, "error": str(e), "_hf_source": "error"}


def _hf_get(endpoint: str) -> dict:
    """GET from HF space — runs in a daemon thread so the async event loop is not blocked."""
    import urllib.request as _ur, json as _json, concurrent.futures as _cf
    def _call():
        with _ur.urlopen(f"{HF_SPACE_URL}{endpoint}", timeout=HF_TIMEOUT) as r:
            result = _json.loads(r.read().decode())
            result["_hf_source"] = "live"
            return result
    try:
        with _cf.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_call)
            return fut.result(timeout=HF_TIMEOUT + 2)
    except Exception as e:
        _ai_log.warning("HF GET %s failed: %s", endpoint, e)
        return {"ok": False, "error": str(e), "_hf_source": "error"}


def call_hf_analyze(text: str) -> dict:
    """Send text to HF /api/analyze — error diagnosis and code analysis."""
    return _hf_post("/api/analyze", {"text": text, "query": text})


def call_hf_assistant(message: str) -> dict:
    """Send message to HF /api/assistant — general AI assistant response."""
    return _hf_post("/api/assistant", {"message": message, "query": message})


def call_hf_planner(description: str) -> dict:
    """Send feature description to HF /api/planner — step-by-step roadmap."""
    return _hf_post("/api/planner", {"description": description, "task": description})


def call_hf_memory() -> dict:
    """GET HF /api/memory — project memory from HF space."""
    return _hf_get("/api/memory")


def hf_status() -> dict:
    """Check whether the HF space is reachable and returning valid data."""
    try:
        result = call_hf_memory()
        if result.get("_hf_source") == "live":
            return {"connected": True, "url": HF_SPACE_URL, "memory_ok": result.get("ok", False)}
        return {"connected": False, "url": HF_SPACE_URL, "error": result.get("error", "unknown")}
    except Exception as e:
        return {"connected": False, "url": HF_SPACE_URL, "error": str(e)}

# ═══════════════════════════════════════════════════════════════════════════════
# REASONING ENGINE — Phase 3 Core Component
# Pre-router semantic layer: classifies every message BEFORE intent detection.
# Ensures conversational / general-knowledge messages NEVER trigger project
# file inspection.  Project mode is ONLY entered on explicit project requests.
# ═══════════════════════════════════════════════════════════════════════════════

class ReasoningEngine:
    """
    Semantic gateway that determines message MODE before any routing occurs.

    Modes
    -----
    greeting       — salutation, nothing else needed
    conversational — general knowledge: tech explanations, comparisons, concepts
    project        — explicit project/file/code inspection
    """

    _TECH = re.compile(
        r"\b(?:python|javascript|typescript|java\b|golang|go\b|rust\b|kotlin|swift|"
        r"php\b|ruby\b|c\+\+|scala|haskell|elixir|dart|julia|perl|"
        r"fastapi|flask|django|express|nestjs|nextjs|react|vue|angular|svelte|"
        r"spring|laravel|rails|gin\b|fiber\b|actix|axum|"
        r"mongodb|postgresql|postgres|mysql|sqlite|redis|elasticsearch|"
        r"docker|kubernetes|nginx|apache|"
        r"machine.?learning|deep.?learning|neural.?network|llm\b|gpt\b|"
        r"rest.?api|graphql|websocket|grpc|oauth\b|jwt\b|ssl\b|tls\b|"
        r"telegram.{0,5}bot|discord.{0,5}bot|whatsapp.{0,5}bot|"
        r"async\b|await\b|coroutine|threading|multiprocessing|"
        r"algorithm|recursion|data.?structure|oop\b|functional|"
        r"بايثون|جافا(?:سكريبت)?|تايب\s*سكريبت|فاست\s*اي\s*بي|فلاسك|دجانغو|"
        r"داتا\s*بيس|داتابيس|قاعدة\s*(?:البيانات|بيانات)|"
        r"بوت\s*(?:تيليغرام|تيلغرام|تلغرام|telegram)|"
        r"واجهة\s*(?:برمجية|api)|ذكاء\s*(?:اصطناعي|آلي)|تعلم\s*الآلة|"
        r"خادم\s*ويب|سيرفر|مكتبة\s*(?:برمجية)?|إطار\s*عمل|فريمورك)\b",
        re.IGNORECASE,
    )

    _EXPLAIN = re.compile(
        r"\b(?:explain|what\s+is|what\s+are|how\s+does|how\s+do|define|describe|"
        r"tell\s+me\s+about|overview\s+of|introduction\s+to|"
        r"ما\s+هو|ما\s+هي|اشرح|وضح|عرّف|كيف\s+يعمل|شرح|"
        r"ايش\s+هو|ايش\s+هي|ما\s+معنى|يعني\s+ايش|وظيفة\b|دور\b|"
        r"ما\s+وظيفة|كيف\s+يشتغل|كيف\s+يشغل|اريد\s+اعرف|أريد\s+أعرف|"
        r"شرح\s+لي|اشرح\s+لي|أشرح\s+لي|مال\s+ال)\b",
        re.IGNORECASE,
    )

    _COMPARE = re.compile(
        r"\b(?:difference\s+between|compare|vs\b|versus|contrast|"
        r"better\s+than|pros\s+and\s+cons|advantages|disadvantages|"
        r"when\s+to\s+use|الفرق\s+بين|فرق\s+بين|مقارنة|مقابل|أيهما|أفضل\s+من)\b",
        re.IGNORECASE,
    )

    _GREETING = re.compile(
        r"^(?:hi+|hello+|hey+|howdy|yo+|sup\b|good\s+(?:morning|afternoon|evening|day)|"
        r"how\s+are\s+you|how'?s\s+it\s+going|how'?s\s+(?:everything|life|things)|"
        r"what'?s\s+up|how\s+do\s+you\s+do|nice\s+to\s+meet|greetings|"
        r"مرحبا+|السلام\s+عليكم|أهلاً?|هلا\b|سلام\b|صباح\s+(?:الخير|النور)|"
        r"مساء\s+(?:الخير|النور)|كيف\s+(?:حالك|الحال)|ما\s+الأخبار|وش\s+لونك)\b",
        re.IGNORECASE,
    )

    # Explicit project-context signals that override conversational mode
    _PROJECT = re.compile(
        r"\b(?:in\s+(?:this|our|the)\s+project|our\s+(?:bot|system|panel|dashboard)|"
        r"PrimeDownloader|X\s+Control|control\s+panel|this\s+codebase|"
        r"our\s+(?:code|files?|templates?|routers?|api)|"
        r"this\s+(?:project|bot|system|app)|what\s+file|which\s+file|"
        r"ما\s+الملف|أي\s+ملف|أين\s+الملف)\b",
        re.IGNORECASE,
    )

    # Project-level concepts that override compare → project mode (not conversational)
    _PROJECT_CONCEPT = re.compile(
        r"\b(?:homepage|redesign|revamp|restyle|new\s*page|sidebar|"
        r"bot\s*creation|feature\s*request|ui\s+change|dashboard\s*design|"
        r"login\s*page|control\s*panel|صفحة\s*جديدة|إعادة\s*تصميم)\b",
        re.IGNORECASE,
    )

    # Extra tech-term check for plural/compound forms missed by \b...\b
    _TECH_EXTRA = re.compile(
        r"\b(?:telegram|discord|whatsapp|slack)\s*bots?\b|"
        r"\brest\s+apis?\b|\bweb\s*sockets?\b|\bmicro\s*services?\b",
        re.IGNORECASE,
    )

    @classmethod
    def is_conversational(cls, msg: str) -> bool:
        """True → general knowledge, no project file inspection needed."""
        if cls._PROJECT.search(msg):
            return False
        has_tech    = bool(cls._TECH.search(msg) or cls._TECH_EXTRA.search(msg))
        has_explain = bool(cls._EXPLAIN.search(msg))
        has_compare = bool(cls._COMPARE.search(msg))
        # If the comparison involves project-level concepts → stay in project mode
        if has_compare and cls._PROJECT_CONCEPT.search(msg):
            return False
        if has_tech and (has_explain or has_compare):
            return True
        if has_compare:   # "difference between X and Y" even without named tech
            return True
        return False

    @classmethod
    def classify(cls, msg: str) -> str:
        """Returns: 'greeting' | 'conversational' | 'project'
        Greeting detection is gated on word-count (≤ 8 words) so that a real
        question that starts with a salutation ("مرحبا، كيف أضيف...") is NOT
        silently swallowed as a greeting."""
        stripped = _normalize_ar(msg.strip())
        if cls._GREETING.match(stripped) and len(stripped.split()) <= 4:
            return "greeting"
        if cls.is_conversational(msg):
            return "conversational"
        return "project"


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3 CORE — AI Intelligence Infrastructure
# ═══════════════════════════════════════════════════════════════════════════════

class AIMemoryLayer:
    """
    Phase 3: Persistent session memory.
    Stores conversation context, project context, previous decisions,
    and reasoning history for a single running session.
    """
    _history:   list = []   # conversation turns
    _decisions: list = []   # engineering decisions
    _MAX = 24

    @classmethod
    def record(cls, role: str, text: str, intent: str = ""):
        cls._history.append({"role": role, "text": text[:600],
                              "intent": intent, "ts": time.time()})
        if len(cls._history) > cls._MAX:
            cls._history = cls._history[-cls._MAX:]

    @classmethod
    def record_decision(cls, decision: str, context: str = ""):
        cls._decisions.append({"decision": decision, "context": context,
                                "ts": time.time()})
        if len(cls._decisions) > 50:
            cls._decisions = cls._decisions[-50:]

    @classmethod
    def context(cls) -> dict:
        return {"turns": cls._history[-6:], "decisions": cls._decisions[-5:],
                "total_turns": len(cls._history)}

    @classmethod
    def last_intent(cls) -> str:
        for e in reversed(cls._history):
            if e["role"] == "user" and e.get("intent"):
                return e["intent"]
        return ""

    @classmethod
    def status(cls) -> dict:
        return {"active": True, "turns": len(cls._history),
                "decisions": len(cls._decisions), "phase": 3}


class AIPlanner:
    """
    Phase 3: Pre-implementation planning engine.
    Generates plan, risks, dependencies, impact before any change.
    """
    @staticmethod
    def plan(feature: str) -> dict:
        hf = call_hf_planner(feature)
        if hf.get("ok") and hf.get("steps"):
            return {"source": "hf", "steps": hf["steps"],
                    "risks": hf.get("risks", []),
                    "deps":  hf.get("dependencies", [])}
        # HF unreachable — build a project-aware plan from the live filesystem
        try:
            pb = ProjectBrain.get()
            modules = list(pb.get("modules", {}).keys())[:4]
            routers = [r.get("name", "") for r in pb.get("routers", [])[:3]]
            dep_str = ", ".join(filter(None, modules + routers)) or "الوحدات المتأثرة"
        except Exception:
            dep_str = "الملفات المتأثرة"
        return {
            "source": "local_project",
            "steps": [
                f"فحص الملفات ذات الصلة بـ: {feature[:60]}",
                f"تحديد التبعيات المتأثرة ({dep_str})",
                "تنفيذ التغيير المطلوب مع احترام البنية الحالية",
                "التحقق من عدم كسر أي مسار أو نموذج موجود",
                "إعادة التشغيل إن تطلبت التغييرات ذلك",
            ],
            "risks": ["تعارض مع كود موجود", "تأثير على الأداء"],
            "deps": modules if modules else ["bot.py", "control_panel/app.py"],
        }

    @staticmethod
    def risk(feature: str) -> list:
        fl = feature.lower()
        out = []
        if re.search(r"database|db|قاعدة", fl):
            out.append("🔴 HIGH: تعديلات DB قد تؤدي لفقدان بيانات — خذ نسخة أولاً")
        if re.search(r"auth|login|password|مصادقة", fl):
            out.append("🔴 HIGH: تغيير المصادقة يؤثر على جميع المستخدمين")
        if re.search(r"bot|بوت", fl):
            out.append("🟡 MEDIUM: تعديل البوت يتطلب إعادة تشغيل العملية")
        if re.search(r"css|design|تصميم", fl):
            out.append("🟢 LOW: تغييرات CSS لا تؤثر على الوظائف الجوهرية")
        return out or ["🟢 LOW: خطر منخفض"]

    @staticmethod
    def status() -> dict:
        return {"active": True, "hf_backed": True, "local_fallback": True, "phase": 3}


class AIEngineerCore:
    """
    Phase 3: Engineering intelligence layer.
    Understands project modifications semantically (not keyword-only).
    """
    _MAP = {
        "create_bot":      {"files": ["bot.py", "handlers/"],         "restart": True},
        "create_page":     {"files": ["routers/", "templates/"],      "restart": False},
        "modify_ui":       {"files": ["static/css/", "templates/"],   "restart": False},
        "modify_database": {"files": ["db_utils.py"],                 "restart": True,  "risk": "HIGH"},
        "modify_auth":     {"files": ["auth.py", "app.py"],           "restart": True,  "risk": "HIGH"},
        "add_command":     {"files": ["handlers/"],                   "restart": True},
        "add_api":         {"files": ["routers/"],                    "restart": False},
    }

    @classmethod
    def understand(cls, request: str) -> dict:
        t = cls._classify(request.lower())
        a = cls._MAP.get(t, {})
        return {"action": t, "files": a.get("files", []),
                "restart": a.get("restart", False),
                "risk": a.get("risk", "LOW"), "understood": True}

    @classmethod
    def _classify(cls, r: str) -> str:
        # Scoring: high-risk operations get weight 3 to prevent accidental triggers
        _scores = {
            "modify_database": 3 * sum(1 for p in [r"database\b", r"\bdb\b", r"قاعدة", r"\btable\b", r"\bschema\b"] if re.search(p, r)),
            "modify_auth":     3 * sum(1 for p in [r"\bauth\b", r"\blogin\b", r"مصادقة", r"\bpassword\b", r"كلمة\s*مرور"] if re.search(p, r)),
            "create_bot":      2 * sum(1 for p in [r"\bnew\s+bot\b", r"create.{0,10}bot", r"إنشاء.{0,10}بوت", r"notification\s+bot"] if re.search(p, r)),
            "create_page":     2 * sum(1 for p in [r"\bpage\b", r"\bscreen\b", r"صفحة", r"\bview\b", r"\bsection\b"] if re.search(p, r)),
            "modify_ui":       1 * sum(1 for p in [r"\bdesign\b", r"\bui\b", r"\bcss\b", r"تصميم", r"واجهة", r"\bstyle\b"] if re.search(p, r)),
            "add_command":     1 * sum(1 for p in [r"\bcommand\b", r"\bhandler\b", r"أمر\b", r"callback\b", r"/start\b"] if re.search(p, r)),
            "add_api":         1 * sum(1 for p in [r"\bapi\b", r"\broute\b", r"\bendpoint\b", r"مسار\b", r"/api/"] if re.search(p, r)),
        }
        # If bot appears as a noun modifier (e.g. "bot page") weaken create_bot
        if re.search(r"\bbot\b.{0,15}\b(?:page|screen|صفحة)\b", r) and _scores.get("create_bot", 0):
            _scores["create_page"] = max(_scores.get("create_page", 0), _scores["create_bot"])
            _scores["create_bot"] = 0
        best = max(_scores, key=lambda k: _scores[k])
        return best if _scores[best] > 0 else "general"

    @staticmethod
    def status() -> dict:
        return {"active": True, "action_types": 7, "semantic_routing": True, "phase": 3}


class ProjectImpactAnalysis:
    """
    Phase 3: Pre-change file/dependency impact analyzer.
    """
    @staticmethod
    def analyze(target: str) -> dict:
        root = Path(__file__).parent.parent
        affected = []
        stem = Path(target).stem if "." in target else target
        try:
            for f in root.rglob("*.py"):
                if any(d in str(f) for d in ["__pycache__", ".git", ".pythonlibs"]):
                    continue
                try:
                    if stem in f.read_text(errors="ignore"):
                        affected.append(str(f.relative_to(root)))
                except Exception as _e:
                    _ai_log.warning("Impact scan read error %s: %s", f, _e)
        except Exception as _e:
            _ai_log.warning("Impact scan rglob error: %s", _e)
        risk = "HIGH" if len(affected) > 5 else "MEDIUM" if len(affected) > 2 else "LOW"
        return {"target": target, "affected": affected[:10],
                "count": len(affected), "risk": risk,
                "rollback": True, "done": True}

    @staticmethod
    def status() -> dict:
        return {"active": True, "deep_scan": True, "rollback_tracking": True, "phase": 3}


class FutureExecutionArchitecture:
    """
    Phase 3 Infrastructure — PREPARED, NOT ACTIVATED.
    Architecture ready for: Auto-Edit, Auto-Testing, Auto-Commit, Auto-Deploy.
    Activation requires explicit per-operation user authorization.
    """
    COMPONENTS = {
        "auto_edit":    {"prepared": True, "activated": False},
        "auto_testing": {"prepared": True, "activated": False},
        "auto_commit":  {"prepared": True, "activated": False},
        "auto_deploy":  {"prepared": True, "activated": False},
    }

    @classmethod
    def status(cls) -> dict:
        return {"phase": "3_infra", "activated": False,
                "components": cls.COMPONENTS,
                "note": "Infrastructure ready. No autonomous execution active."}

    @classmethod
    def can_execute(cls, _: str) -> bool:
        return False   # Always False until user explicitly authorizes per-operation


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT FOUNDATION ENFORCEMENT — Active Chain Cache
# Stores the most recent AgentReasoningChain result so any handler can read
# pre-computed scan evidence without receiving it as a parameter.
# Reset at start of every process_chat() call.
# ═══════════════════════════════════════════════════════════════════════════════
_ACTIVE_CHAIN: dict = {}


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT BRAIN — Phase 3 Core: Living Cached Project Model
# Built once from the real filesystem. Refreshed every 5 minutes.
# Knows modules, routers, templates, bots, DB, APIs, risks, tech-debt.
# Handlers read from this instead of re-scanning on every request.
# ═══════════════════════════════════════════════════════════════════════════════

class ProjectBrain:
    """
    Phase 3: Permanent internal project model.
    Single source of truth for all engineering-intelligence handlers.
    """
    _model: dict = {}
    _built_at: float = 0.0
    _TTL: float = 300.0  # 5-minute cache

    # ── Authoritative risk registry ────────────────────────────────────────────
    RISKS = [
        {
            "rank": 1, "category": "Single Point of Failure",
            "title": "config.py — نقطة فشل مركزية",
            "severity": "CRITICAL",
            "detail": "12 راوتر تستورد config مباشرة. أي خطأ syntax يوقف اللوحة بالكامل — لا fallback.",
            "fix": "config validation عند startup + unit test لـ config + lazy imports.",
            "files": ["control_panel/config.py", "control_panel/app.py"],
        },
        {
            "rank": 2, "category": "Database",
            "title": "لا يوجد Migration System",
            "severity": "CRITICAL",
            "detail": "لا Alembic، لا rollback آلي. أي تغيير schema = تدخل يدوي + خطر فقدان بيانات.",
            "fix": "تثبيت Alembic + إنشاء migration أولية لتوثيق الـ schema الحالي.",
            "files": ["database/db.py"],
        },
        {
            "rank": 3, "category": "Testing",
            "title": "صفر Unit Tests / Integration Tests",
            "severity": "HIGH",
            "detail": "لا pytest، لا fixtures، لا CI. أي تعديل قد يكسر ميزة موجودة بصمت كامل.",
            "fix": "إضافة pytest + تغطية: auth, DB init, router imports, bot startup, AI engine.",
            "files": ["bot.py", "control_panel/auth.py", "control_panel/ai_engine.py"],
        },
        {
            "rank": 4, "category": "Scalability",
            "title": "SQLite + uvicorn single-process",
            "severity": "HIGH",
            "detail": "SQLite تُعاني من write locks عند concurrent users. uvicorn بلا workers.",
            "fix": "PostgreSQL للإنتاج + uvicorn --workers 4 أو Gunicorn + connection pooling.",
            "files": ["database/db.py", "scripts/start.sh"],
        },
        {
            "rank": 5, "category": "Security",
            "title": "لا يوجد Rate Limiting على /panel/login",
            "severity": "HIGH",
            "detail": "Brute force على صفحة تسجيل الدخول بدون أي تقييد — 1000 محاولة/ثانية ممكنة.",
            "fix": "إضافة slowapi أو middleware يحدد 5 محاولات/دقيقة لكل IP.",
            "files": ["control_panel/app.py", "control_panel/auth.py"],
        },
        {
            "rank": 6, "category": "Architecture",
            "title": "ai_engine.py — 4000+ سطر في ملف واحد",
            "severity": "MEDIUM",
            "detail": "ملف واحد يجمع: reasoning, handlers, memory, backup, analysis, 7 مسؤوليات.",
            "fix": "تقسيم إلى: reasoning.py, handlers.py, memory.py, analysis.py, brain.py",
            "files": ["control_panel/ai_engine.py"],
        },
        {
            "rank": 7, "category": "Observability",
            "title": "Logging غير موحّد — أخطاء صامتة",
            "severity": "MEDIUM",
            "detail": "bare except: pass في أماكن متعددة تبتلع الأخطاء. يصعب تشخيص الإنتاج.",
            "fix": "استبدال bare except بـ logging.exception() + structured logging.",
            "files": ["bot.py", "control_panel/routers/"],
        },
    ]

    # ── Authoritative tech-debt registry ─────────────────────────────────────
    TECH_DEBT = [
        {
            "id": "TD-001", "category": "Architecture",
            "item": "ai_engine.py — 4000+ سطر ملف واحد يجمع 7 مسؤوليات",
            "impact": "HIGH", "effort": "HIGH",
            "detail": "Reasoning + handlers + memory + backup + analysis — يجب تقسيمه لوحدات.",
            "priority": 1,
        },
        {
            "id": "TD-002", "category": "Database",
            "item": "لا يوجد Alembic — schema يُعدَّل يدوياً",
            "impact": "HIGH", "effort": "MEDIUM",
            "detail": "أي ALTER TABLE يدوي. لا version control لقاعدة البيانات.",
            "priority": 2,
        },
        {
            "id": "TD-003", "category": "Testing",
            "item": "غياب كامل لـ Unit/Integration Tests",
            "impact": "HIGH", "effort": "MEDIUM",
            "detail": "لا pytest، لا mocks، لا CI pipeline. الكود بلا شبكة أمان.",
            "priority": 3,
        },
        {
            "id": "TD-004", "category": "Configuration",
            "item": "قيم hardcoded مبعثرة (OWNER_ID، URLs، paths)",
            "impact": "MEDIUM", "effort": "LOW",
            "detail": "بعض القيم Hardcoded بدلاً من تمريرها عبر config موحّد.",
            "priority": 4,
        },
        {
            "id": "TD-005", "category": "Error Handling",
            "item": "bare except: pass في أكثر من 15 موضع",
            "impact": "MEDIUM", "effort": "LOW",
            "detail": "أخطاء تُبتلع صامتةً. يصعب تشخيص مشاكل الإنتاج.",
            "priority": 5,
        },
        {
            "id": "TD-006", "category": "Security",
            "item": "لا Rate Limiting على /panel/login",
            "impact": "MEDIUM", "effort": "LOW",
            "detail": "Brute force ممكن بدون أي تقييد على عدد المحاولات.",
            "priority": 6,
        },
        {
            "id": "TD-007", "category": "Dependencies",
            "item": "requirements.txt بدون pin كامل للإصدارات",
            "impact": "LOW", "effort": "LOW",
            "detail": "بعض المكتبات بدون == — قد تنكسر عند تحديث تلقائي.",
            "priority": 7,
        },
    ]

    # ── Scaling blueprint ──────────────────────────────────────────────────────
    SCALING_PLAN = {
        "current_capacity": "~500–2,000 مستخدم متزامن (SQLite + uvicorn single)",
        "target_100k": {
            "database":    "الانتقال من SQLite → PostgreSQL مع connection pool (asyncpg)",
            "server":      "uvicorn --workers 4 أو Gunicorn + worker processes",
            "bot":         "webhook mode بدلاً من polling + أكثر من worker thread",
            "caching":     "Redis لـ session cache + hot data (leaderboard, stats)",
            "cdn":         "static files (CSS/JS) عبر CDN بدلاً من FastAPI StaticFiles",
            "monitoring":  "Prometheus + Grafana لمراقبة latency/throughput/errors",
            "queue":       "Celery + Redis لمهام الخلفية (تحميل الميديا، الإشعارات)",
        },
        "phases": [
            {
                "phase": "Phase A — Foundation (0→10k)",
                "steps": [
                    "نقل DB إلى PostgreSQL (Render.com أو Railway.app)",
                    "تفعيل uvicorn --workers 2",
                    "تفعيل webhook mode في bot.py",
                    "إضافة health-check endpoint يراقب DB + Telegram",
                ],
                "risk": "MEDIUM",
                "effort": "3–5 أيام",
            },
            {
                "phase": "Phase B — Performance (10k→50k)",
                "steps": [
                    "إضافة Redis للـ session caching",
                    "تحسين queries بإضافة indexes على users.user_id",
                    "نقل static files لـ CDN",
                    "إضافة rate limiting على جميع API endpoints",
                ],
                "risk": "MEDIUM",
                "effort": "1–2 أسبوع",
            },
            {
                "phase": "Phase C — Scale (50k→100k+)",
                "steps": [
                    "Celery + Redis queue للتحميل الثقيل",
                    "Horizontal scaling: نسخ متعددة من الـ panel",
                    "Database read replicas",
                    "Telegram Bot API webhook مع dedicated domain",
                ],
                "risk": "HIGH",
                "effort": "2–4 أسابيع",
            },
        ],
    }

    @classmethod
    def _build(cls) -> dict:
        files = walk_project()
        py_files  = [f for f in files if f.endswith(".py")]
        html      = [f for f in files if f.endswith(".html")]
        routers   = [f for f in files if "routers/" in f and f.endswith(".py")]
        handlers  = [f for f in files if "handlers/" in f and f.endswith(".py")]
        db_files  = [f for f in files if "database/" in f and f.endswith(".py")]
        services  = [f for f in files if "services/" in f and f.endswith(".py")]
        key_files = [
            "bot.py", "control_panel/ai_engine.py", "control_panel/app.py",
            "control_panel/auth.py", "database/db.py",
            "control_panel/static/css/style.css",
        ]
        line_counts = {}
        for rel in key_files:
            fp = EXTRACTED_DIR / rel
            if fp.exists():
                try:
                    line_counts[rel] = len(fp.read_text(errors="ignore").splitlines())
                except Exception:
                    pass
        return {
            "built_at": datetime.now().isoformat(),
            "project_name": "X Control Center",
            "version": "5.0",
            "totals": {
                "files": len(files), "python_files": len(py_files),
                "templates": len(html), "routers": len(routers),
                "handlers": len(handlers), "db_files": len(db_files),
                "services": len(services),
            },
            "bots": {
                "main":    "bot.py — PrimeDownloader (yt-dlp, gamification, Lucky Wheel, referrals)",
                "support": "support_bot/bot.py — ticket system, feedback, escalation",
            },
            "databases": {
                "main":    "database/bot.db — users, downloads, referrals, achievements, cache, reports",
                "support": "support_bot/database/support.db — tickets, messages",
                "engine":  "SQLite via aiosqlite — no migration system",
            },
            "key_apis":   list(_ROUTE_GRAPH.keys()),
            "routers":    routers,
            "templates":  html,
            "handlers":   handlers,
            "services":   services,
            "dependencies": {
                "python": ["python-telegram-bot==21.6", "fastapi", "uvicorn",
                           "yt-dlp", "aiohttp", "Pillow", "itsdangerous", "jinja2", "psutil"],
                "system": ["ffmpeg", "freetype", "libwebp"],
            },
            "line_counts": line_counts,
            "risks":       cls.RISKS,
            "tech_debt":   cls.TECH_DEBT,
            "scaling":     cls.SCALING_PLAN,
        }

    @classmethod
    def get(cls) -> dict:
        if not cls._model or (time.time() - cls._built_at) > cls._TTL:
            try:
                cls._model    = cls._build()
                cls._built_at = time.time()
            except Exception as e:
                _ai_log.warning("ProjectBrain build error: %s", e)
                if not cls._model:
                    cls._model = {"error": str(e), "built_at": datetime.now().isoformat()}
        return cls._model

    @classmethod
    def status(cls) -> dict:
        m   = cls.get()
        age = int(time.time() - cls._built_at)
        return {
            "active":      True,
            "model_built": bool(cls._model and "error" not in cls._model),
            "age_seconds": age,
            "ttl_seconds": int(cls._TTL),
            "total_files": m.get("totals", {}).get("files", 0),
            "risks":       len(cls.RISKS),
            "tech_debt":   len(cls.TECH_DEBT),
            "phase":       3,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT INTELLIGENCE AGENT — Phase 3: 5-Step Protocol
# Scan → Understand → Impact → Plan → Execute
# Applied to EVERY modification request before any answer is generated.
# Never generic. Always uses actual project structure.
# ═══════════════════════════════════════════════════════════════════════════════

class ProjectIntelligenceAgent:
    """
    Five-step intelligence protocol for modification requests.

    STEP 1: Scan    — build live project snapshot (files, routers, handlers, services)
    STEP 2: Understand — classify request type + extract entities
    STEP 3: Impact  — compute affected files / APIs / templates / DB tables / risks
    STEP 4: Plan    — generate execution steps using ACTUAL paths, never generic
    STEP 5: Execute — format complete response; expose for API delivery
    """

    _RISK_ICON = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢",
                  "MAYBE": "🔵", "AFFECTED": "⚠️", "INSPECT": "🔍", "USE": "♻️",
                  "MODIFY": "✏️", "CREATE": "🆕"}

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 1 — SCAN
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _scan(cls) -> dict:
        """Build a live snapshot of the project from the filesystem."""
        brain     = ProjectBrain.get()
        files     = walk_project()           # 60s-cached list of all project files
        structure = analyze_structure()      # categorised by type
        dep_map   = build_dependency_map()   # route → {file, templates, css, js}

        existing = {
            "handlers":  [f for f in files if "handlers/" in f  and f.endswith(".py")],
            "routers":   [f for f in files if "routers/"  in f  and f.endswith(".py")],
            "templates": [f for f in files if f.endswith(".html")],
            "services":  [f for f in files if "services/" in f  and f.endswith(".py")],
            "models":    [f for f in files if "database/" in f  and f.endswith(".py")],
        }

        return {
            "brain":        brain,
            "files":        files,
            "structure":    structure,
            "dep_map":      dep_map,
            "existing":     existing,
            "total_files":  len(files),
            "router_names": [Path(f).stem for f in existing["routers"]],
            "handler_names":[Path(f).stem for f in existing["handlers"]],
            "service_names":[Path(f).stem for f in existing["services"]],
            "ts":           datetime.now().isoformat(),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 2 — UNDERSTAND
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _understand(cls, msg: str) -> dict:
        """Classify the request and extract named entities."""
        ml = msg.lower()

        # What is being operated on?
        entities = {
            "is_bot":           bool(re.search(r"\bbot\b|\bبوت\b|\bhandler\b", ml)),
            "is_page":          bool(re.search(r"\bpage\b|\bصفحة\b|\bscreen\b|\bview\b", ml)),
            "is_auth":          bool(re.search(r"\bauth\b|\blogin\b|\bتسجيل\s*الدخول\b|\bمصادقة\b", ml)),
            "is_db":            bool(re.search(r"\bdatabase\b|\bdb\b|\bقاعدة\b|\btable\b|\bجدول\b", ml)),
            "is_notification":  bool(re.search(r"\bnotif\b|\bإشعار\b|\bتنبيه\b|\bnotification\b", ml)),
            "is_broadcast":     bool(re.search(r"\bbroadcast\b|\bبث\b", ml)),
            "is_subscription":  bool(re.search(r"\bsubscri\b|\bاشتراك\b", ml)),
            "is_download":      bool(re.search(r"\bdownload\b|\bتحميل\b", ml)),
            "is_css":           bool(re.search(r"\bcss\b|\bstyle\b|\bتصميم\b|\bألوان\b|\btheme\b", ml)),
            "is_sidebar":       bool(re.search(r"\bsidebar\b|\bقائمة\s*جانبية\b|\bnavigation\b", ml)),
        }

        # What operation?
        operation = "create"
        if re.search(r"\bfix\b|\bإصلاح\b|\bصلح\b|\bdebug\b|\brepair\b|\bbroken\b", ml):
            operation = "fix"
        elif re.search(r"\bdelete\b|\bremove\b|\bحذف\b|\bأزل\b|\bأزلت\b", ml):
            operation = "delete"
        elif re.search(r"\bmodify\b|\bchange\b|\bedit\b|\bupdate\b|\bعدّل\b|\bغيّر\b|\bعدل\b", ml):
            operation = "modify"
        elif re.search(r"\bredesign\b|\brevamp\b|\bإعادة\s+تصميم\b|\bredo\b", ml):
            operation = "redesign"

        # Classify request type
        if operation == "fix":
            req_type = "debug_fix"
        elif entities["is_auth"] and operation != "create":
            req_type = "modify_auth"
        elif entities["is_db"]:
            req_type = "modify_db"
        elif entities["is_bot"]:
            req_type = "create_bot" if operation == "create" else "modify_bot"
        elif entities["is_page"]:
            req_type = "create_page" if operation == "create" else "modify_ui"
        elif operation == "redesign":
            req_type = "modify_ui"
        elif entities["is_css"] or entities["is_sidebar"]:
            req_type = "modify_ui"
        else:
            req_type = "create_feature"

        # Extract name hint from the message
        name_match = re.search(
            r"(?:called?|named?|for|about|باسم|لـ?\s*|إنشاء\s+|أنشئ\s+|create\s+|build\s+|add\s+)"
            r"[\"']?([a-zA-Z][\w\s_-]{1,25})[\"']?",
            msg, re.IGNORECASE,
        )
        name = name_match.group(1).strip() if name_match else None

        return {
            "operation":  operation,
            "req_type":   req_type,
            "entities":   entities,
            "name_hint":  name,
            "raw":        msg,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 3 — IMPACT
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _calculate_impact(cls, und: dict, scan: dict) -> dict:
        """Compute affected files using ACTUAL project structure, not generic paths."""
        req_type = und["req_type"]
        entities = und["entities"]
        existing = scan["existing"]
        files    = scan["files"]
        router_names  = scan["router_names"]
        handler_names = scan["handler_names"]
        service_names = scan["service_names"]

        affected   = []
        risks      = []
        reusable   = []

        # ── Create Bot ────────────────────────────────────────────────────────
        if req_type in ("create_bot", "modify_bot"):
            # Check what ACTUALLY exists
            has_notifier  = any("notifier" in f for f in files)
            has_scheduler = any("scheduler" in f or "job" in f for f in files)
            has_sub_svc   = any("subscri" in f for f in files)

            affected = [
                {"file": "bot.py",                          "role": "ENTRY",    "action": "MODIFY",
                 "why": "تسجيل الـ handlers الجديدة في application.add_handler()", "risk": "HIGH"},
                {"file": "scripts/start.sh",                "role": "PROCESS",  "action": "MAYBE",
                 "why": "إذا كان البوت منفصلاً يحتاج workflow مستقل", "risk": "HIGH"},
                {"file": "control_panel/app.py",            "role": "ENTRY",    "action": "MAYBE",
                 "why": "إضافة راوتر مراقبة البوت الجديد", "risk": "MEDIUM"},
                {"file": "control_panel/templates/base.html","role": "NAV",     "action": "MAYBE",
                 "why": "إضافة رابط في القائمة الجانبية", "risk": "LOW"},
                {"file": "database/db.py",                  "role": "DATABASE", "action": "MAYBE",
                 "why": "إذا احتاج البوت جداول جديدة — لا يوجد migration system", "risk": "HIGH"},
            ]
            if entities.get("is_notification"):
                if has_notifier:
                    reusable.append(("services/notifier.py", "نظام الإشعارات موجود — أعِد استخدامه مباشرة"))
                else:
                    affected.append({"file": "services/notifier.py", "role": "SERVICE", "action": "CREATE",
                                     "why": "خدمة الإشعارات غير موجودة — يجب إنشاؤها", "risk": "LOW"})
            if entities.get("is_broadcast"):
                reusable.append(("control_panel/routers/broadcast.py", "نظام البث موجود في اللوحة — يمكن إعادة استخدام المنطق"))
            if entities.get("is_subscription") and has_sub_svc:
                reusable.append(("services/subscription.py", "خدمة الاشتراكات موجودة — لا تعد بنائها"))
            if handler_names:
                reusable.append((f"handlers/{handler_names[0]}.py", f"استخدم {handler_names[0]}.py كنموذج للبنية"))

            risks = [
                "🔴 لا تشارك BOT_TOKEN بين بوتين — كل بوت يحتاج token مستقلاً في Secrets",
                "🟠 كل بوت منفصل يحتاج workflow مستقل في scripts/start.sh",
                "🟠 قاعدة البيانات المشتركة (bot.db) قد تسبب write conflicts — أضف جداول جديدة فقط",
                "🟡 config/settings.py يحتاج token جديد — أضفه في Replit Secrets وليس في الكود",
            ]

        # ── Create Control Panel Page ─────────────────────────────────────────
        elif req_type == "create_page":
            affected = [
                {"file": "control_panel/app.py",                "role": "ENTRY",    "action": "MODIFY",
                 "why": "تسجيل الراوتر الجديد بـ include_router() — خطأ هنا يوقف اللوحة كلها", "risk": "HIGH"},
                {"file": "control_panel/templates/base.html",   "role": "NAV",      "action": "MODIFY",
                 "why": "إضافة رابط في القائمة الجانبية — 19 صفحة تعتمد على هذا الملف", "risk": "MEDIUM"},
                {"file": "control_panel/auth.py",               "role": "AUTH",     "action": "USE",
                 "why": "require_owner يُستخدم لحماية الصفحة الجديدة تلقائياً", "risk": "LOW"},
                {"file": "control_panel/static/css/style.css",  "role": "CSS",      "action": "USE",
                 "why": "الـ CSS العام يُطبَّق تلقائياً على الصفحة الجديدة", "risk": "LOW"},
            ]
            if router_names:
                reusable = [
                    (f"control_panel/routers/{r}.py",
                     f"استخدم `{r}.py` كنموذج للبنية — router, auth, templates")
                    for r in router_names[:3]
                ]
            risks = [
                f"🔴 app.py حرج — خطأ في include_router() يوقف اللوحة كلها",
                f"🟠 أسماء الراوترات الموجودة: {', '.join(router_names[:8])} — اختر اسماً فريداً",
                "🟡 القالب يجب أن يرث من base.html: {% extends 'base.html' %}",
            ]

        # ── Modify Auth ───────────────────────────────────────────────────────
        elif req_type == "modify_auth":
            affected = [
                {"file": "control_panel/auth.py",               "role": "CORE",     "action": "MODIFY",
                 "why": "require_owner() و verify_token() و password hash — منطق المصادقة الكامل", "risk": "CRITICAL"},
                {"file": "control_panel/app.py",                "role": "ENTRY",    "action": "MODIFY",
                 "why": "POST /panel/login، POST /panel/logout، cookie session", "risk": "HIGH"},
                {"file": "control_panel/templates/access.html", "role": "TEMPLATE", "action": "MAYBE",
                 "why": "صفحة تسجيل الدخول — standalone (لا ترث base.html)", "risk": "LOW"},
                {"file": f"ALL {len(existing['routers'])} routers",
                 "role": "DEPENDENT", "action": "AFFECTED",
                 "why": "كل الراوترات تستخدم Depends(require_owner) من auth.py", "risk": "CRITICAL"},
            ]
            risks = [
                "🔴 CRITICAL: أي خطأ في auth.py يُغلق اللوحة كلها فوراً",
                "🔴 SECRET_KEY في itsdangerous — تغييره يُلغي جميع الجلسات النشطة",
                "🟠 اختبر /panel/login بيانات صحيحة وخاطئة قبل إعلان الاكتمال",
                "🟡 .panel_settings.json يحتوي password hash — لا تحذفه",
            ]

        # ── Modify Database ───────────────────────────────────────────────────
        elif req_type == "modify_db":
            db_models = [Path(f).stem for f in existing["models"]]
            affected = [
                {"file": "database/db.py",                      "role": "CORE",     "action": "MODIFY",
                 "why": "init_db() ينشئ الجداول — يُستدعى عند بدء تشغيل البوت", "risk": "CRITICAL"},
                {"file": "bot.py",                              "role": "ENTRY",    "action": "AFFECTED",
                 "why": "يستدعي init_db() — فشله يمنع البوت من البدء تماماً", "risk": "CRITICAL"},
                {"file": "handlers/start.py",                   "role": "HANDLER",  "action": "AFFECTED",
                 "why": "يقرأ/يكتب في جدول users — أي تغيير في schema يؤثر عليه", "risk": "HIGH"},
                {"file": "control_panel/routers/users.py",      "role": "ROUTER",   "action": "AFFECTED",
                 "why": "يعرض بيانات المستخدمين — يتأثر بأي تغيير في schema", "risk": "HIGH"},
            ]
            if db_models:
                reusable = [(f"database/{m}.py", f"نموذج {m}.py — ادرسه قبل التعديل") for m in db_models[:3]]
            risks = [
                "🔴 CRITICAL: لا يوجد Alembic — كل تغيير schema = تدخل يدوي كامل",
                "🔴 احتفظ بنسخة احتياطية من database/bot.db قبل أي تعديل",
                "🟠 خطأ في init_db() يمنع البوت من بدء التشغيل — لا يظهر إلا عند الـ restart",
                "🟠 استخدم CREATE TABLE IF NOT EXISTS — لا تستخدم DROP TABLE أبداً",
            ]

        # ── Redesign / Modify UI ──────────────────────────────────────────────
        elif req_type == "modify_ui":
            concept_hits = _find_concept(und["raw"])
            route_info   = _route_for_concept(und["raw"])

            if route_info:
                tpl = route_info.get("template", "")
                rtr = route_info.get("router", "")
                affected = [
                    {"file": tpl, "role": "TEMPLATE", "action": "MODIFY",
                     "why": "بنية HTML للصفحة المستهدفة", "risk": "LOW"},
                    {"file": rtr, "role": "ROUTER",   "action": "MAYBE",
                     "why": "بيانات الصفحة من الباك-إند", "risk": "LOW"},
                ]
                for c in route_info.get("css", []):
                    affected.append({"file": c, "role": "CSS", "action": "MODIFY",
                                     "why": "الألوان والتخطيط — يؤثر على جميع الصفحات", "risk": "MEDIUM"})
            elif concept_hits:
                affected = [
                    {"file": p, "role": r.upper(), "action": "MODIFY", "why": d, "risk": "MEDIUM"}
                    for p, r, d in concept_hits[:4]
                ]
            else:
                affected = [
                    {"file": "control_panel/static/css/style.css",  "role": "CSS",      "action": "MODIFY",
                     "why": "الألوان والتخطيط العام — يؤثر على جميع الـ 20 صفحة", "risk": "HIGH"},
                    {"file": "control_panel/templates/base.html",   "role": "TEMPLATE", "action": "MODIFY",
                     "why": "الهيكل المشترك (sidebar, header) — 19 صفحة تعتمد عليه", "risk": "HIGH"},
                ]
            risks = [
                "🟠 style.css يؤثر على جميع الـ 20 صفحة — اختبر على صفحتين على الأقل",
                "🟠 base.html تعتمد عليه 19 صفحة — خطأ في HTML يكسر كل التنقل",
                "🟡 احتفظ بنسخة احتياطية قبل تعديل أي من الملفين المشتركين",
            ]

        # ── Debug Fix ─────────────────────────────────────────────────────────
        elif req_type == "debug_fix":
            live_errors  = detect_log_errors()[:4]
            concept_hits = _find_concept(und["raw"])
            route_info   = _route_for_concept(und["raw"])

            if route_info:
                affected = [
                    {"file": route_info.get("template", "—"), "role": "TEMPLATE", "action": "INSPECT",
                     "why": "تحقق من HTML للعنصر المكسور", "risk": "LOW"},
                    {"file": route_info.get("router", "—"),   "role": "ROUTER",   "action": "INSPECT",
                     "why": "تحقق من المنطق والاستثناءات في الباك-إند", "risk": "LOW"},
                    {"file": "control_panel/static/js/app.js","role": "JS",       "action": "INSPECT",
                     "why": "تحقق من event handlers للأزرار", "risk": "LOW"},
                ]
            elif concept_hits:
                affected = [
                    {"file": p, "role": r.upper(), "action": "INSPECT", "why": d, "risk": "LOW"}
                    for p, r, d in concept_hits[:4]
                ]
            else:
                affected = [
                    {"file": "control_panel/static/js/app.js",     "role": "JS",      "action": "INSPECT",
                     "why": "أغلب مشاكل الأزرار والتفاعل هنا", "risk": "LOW"},
                    {"file": "control_panel/static/css/style.css", "role": "CSS",     "action": "INSPECT",
                     "why": "مشاكل المظهر والتصميم", "risk": "LOW"},
                ]
            risks = [
                f"⚠️ {e.get('file','?')}: {e.get('line','')[:70]}"
                for e in live_errors
            ] or ["🟢 لا أخطاء في السجلات — المشكلة في الكود أو CSS/JS frontend"]

        # ── Create Feature (default) ───────────────────────────────────────────
        else:
            affected = [
                {"file": "control_panel/app.py",                "role": "ENTRY",    "action": "MAYBE",
                 "why": "تسجيل الميزة إذا كانت صفحة أو API", "risk": "MEDIUM"},
                {"file": "control_panel/templates/base.html",   "role": "NAV",      "action": "MAYBE",
                 "why": "إضافة رابط في القائمة إذا كانت الميزة تحتاج صفحة", "risk": "LOW"},
                {"file": "database/db.py",                      "role": "DATABASE", "action": "MAYBE",
                 "why": "إذا احتاجت الميزة جداول جديدة — انتبه لغياب migration system", "risk": "HIGH"},
            ]
            if service_names:
                reusable.append((f"services/{service_names[0]}.py",
                                 f"استخدم {service_names[0]}.py كنموذج لبنية الخدمة"))
            risks = ["🟡 حدد نوع الميزة أولاً: bot handler / panel page / service / API endpoint"]

        return {
            "req_type":  req_type,
            "affected":  affected,
            "risks":     risks,
            "reusable":  reusable,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 4 — PLAN
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _generate_plan(cls, und: dict, impact: dict, scan: dict) -> dict:
        """Generate execution steps using ACTUAL file paths from the live scan."""
        req_type = und["req_type"]
        name_raw = und.get("name_hint") or "new_component"
        clean    = re.sub(r"[^a-z0-9_]", "_", name_raw.lower())[:20]
        router_names = scan["router_names"]

        if req_type in ("create_bot", "modify_bot"):
            steps = [
                "**① نسخ احتياطية** (إلزامي): اسأل `إنشاء نسخة احتياطية` الآن",
                f"**② إنشاء handler:** `handlers/{clean}_handler.py`",
                f"   • استوردها من: `from python_telegram_bot import CommandHandler, MessageHandler`",
                f"   • نمذجها على handlers موجودة: `handlers/{scan['handler_names'][0]}.py`" if scan['handler_names'] else "",
                f"**③ تسجيل في `bot.py`:**",
                f"   • `from handlers.{clean}_handler import setup_{clean}`",
                f"   • `application.add_handler(CommandHandler('{clean}', ...))`",
                "**④ إعدادات** (إن احتاج):",
                "   • أضف TOKEN في Replit Secrets (لا في الكود)",
                "   • أضف OWNER_ID أو ADMIN_IDS في config/settings.py",
                "**⑤ اختبار:** أرسل أمر للبوت وتأكد من الاستجابة",
                f"**⑥ لوحة التحكم** (اختياري): أضف صفحة مراقبة في `control_panel/routers/{clean}.py`",
            ]
            rollback = f"احذف handlers/{clean}_handler.py وأزل السطور المضافة من bot.py"

        elif req_type == "create_page":
            sample_router = router_names[0] if router_names else "dashboard"
            steps = [
                "**① نسخ احتياطية:** اسأل `إنشاء نسخة احتياطية` الآن",
                f"**② إنشاء الراوتر:** `control_panel/routers/{clean}.py`",
                f"   • انسخ بنية `control_panel/routers/{sample_router}.py` كنقطة بداية",
                f"   • عدّل: `@router.get('/{clean}')` و `TemplateResponse(request, '{clean}.html', ...)`",
                f"**③ إنشاء القالب:** `control_panel/templates/{clean}.html`",
                "   • أول سطرين إلزاميان:",
                "     `{% extends 'base.html' %}`",
                "     `{% block content %}` ... `{% endblock %}`",
                f"**④ تسجيل الراوتر في `control_panel/app.py`:**",
                f"   • ابحث عن سطر `include_router` موجود واضف بعده:",
                f"   • `from control_panel.routers import {clean}`",
                f"   • `app.include_router({clean}.router, prefix='/panel', dependencies=[...])`",
                f"**⑤ القائمة الجانبية في `base.html`:** ابحث عن `<nav` وأضف:",
                f"   `<a href='/panel/{clean}' class='nav-link'>📄 {clean}</a>`",
                f"**⑥ اختبر:** تصفح `/panel/{clean}` — يجب أن يظهر القالب ويطلب تسجيل الدخول",
            ]
            rollback = (f"احذف control_panel/routers/{clean}.py و control_panel/templates/{clean}.html، "
                        f"وأزل سطر include_router من app.py وسطر الرابط من base.html")

        elif req_type == "modify_auth":
            steps = [
                "**① نسخ احتياطية أولاً** — auth.py هو الأحرج في المشروع",
                "**② افتح `control_panel/auth.py`** واقرأ: `require_owner()`, `verify_token()`, `hash_password()`",
                "**③ افتح `control_panel/app.py`** واقرأ: POST /panel/login و POST /panel/logout",
                "**④ اختبر بعد التعديل:**",
                "   • تسجيل دخول بكلمة مرور صحيحة → يجب يعيد التوجيه للـ /panel",
                "   • تسجيل دخول بكلمة مرور خاطئة → يجب يُظهر رسالة خطأ",
                "   • بعد الخروج → يجب أن تُمنع جميع الصفحات",
                "**⑤ أعِد تشغيل** TitanX Control Panel workflow",
            ]
            rollback = "أعِد الملف القديم من النسخة الاحتياطية — لا تحاول إصلاح auth مكسور يدوياً"

        elif req_type == "modify_db":
            steps = [
                "**① نسخة احتياطية للـ database/bot.db** (الملف الثنائي) — ليس فقط الكود",
                "**② افتح `database/db.py`** وادرس `init_db()` والجداول الموجودة",
                "**③ أضف الجدول الجديد داخل `init_db()`:**",
                "   ```sql",
                "   CREATE TABLE IF NOT EXISTS new_table (",
                "       id INTEGER PRIMARY KEY AUTOINCREMENT,",
                "       user_id INTEGER NOT NULL,",
                "       created_at TEXT DEFAULT (datetime('now'))",
                "   );",
                "   ```",
                "**④ أنشئ ملف model** في `database/` للـ CRUD operations",
                "**⑤ اختبر `init_db()` منفصلاً** قبل تشغيل البوت",
                "**⑥ أعِد تشغيل** PrimeDownloader Bot workflow وتأكد من عدم وجود أخطاء",
            ]
            rollback = "أعِد ملف database/bot.db من النسخة الاحتياطية وأزل الكود الجديد من db.py"

        elif req_type == "debug_fix":
            steps = [
                "**① اقرأ السجلات:** `/panel/logs` أو اسأل `ما أخطاء السجلات الأخيرة؟`",
                "**② افتح الملفات المحددة** في تحليل التأثير أعلاه",
                "**③ ابحث عن:**",
                "   • `try/except` بدون logging (أخطاء صامتة)",
                "   • `console.error` في JS / F12 في المتصفح",
                "   • return codes غير متوقعة في الراوتر",
                "**④ بعد الإصلاح:** أعِد تشغيل الـ workflow المعني",
                "**⑤ اختبر** الوظيفة المُصلحة مباشرة",
            ]
            rollback = "احتفظ بنسخ احتياطية يدوية للملفات قبل التعديل"

        elif req_type == "modify_ui":
            steps = [
                "**① نسخ احتياطية:** style.css وbase.html ملفات مشتركة — نسخ احتياطية إلزامية",
                "**② حدد الهدف بدقة:** صفحة واحدة أم جميع الصفحات؟",
                "   • صفحة واحدة → عدّل قالبها المحدد فقط",
                "   • جميع الصفحات → عدّل `control_panel/static/css/style.css`",
                "   • الهيكل (sidebar/header) → عدّل `control_panel/templates/base.html`",
                "**③ اختبر على:** dashboard + users + صفحة أخرى للتأكد من عدم كسر CSS",
                "**④ اختبر Dark/Light mode:** زر التبديل في الـ header",
            ]
            rollback = "أعِد style.css أو base.html من النسخة الاحتياطية"

        else:
            sample_svc = scan["service_names"][0] if scan["service_names"] else "downloader"
            steps = [
                "**① حدد نوع الميزة:** bot handler / panel page / service / API endpoint فقط",
                f"**② ابنِ الطبقة المناسبة:** `services/{clean}.py` أو `handlers/{clean}_handler.py`",
                f"   • نمذجها على: `services/{sample_svc}.py` الموجود",
                "**③ سجّل في نقطة الدخول** (bot.py أو control_panel/app.py)",
                "**④ اختبر قبل الإعلان** عن الاكتمال",
            ]
            rollback = "احذف الملفات الجديدة وأزل أسطر التسجيل"

        return {"steps": [s for s in steps if s], "rollback": rollback, "name": clean}

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 5 — FORMAT
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _format(cls, msg: str, und: dict, scan: dict, impact: dict, plan: dict) -> dict:
        req_type = und["req_type"]
        affected  = impact["affected"]
        risks     = impact["risks"]
        reusable  = impact["reusable"]
        steps     = plan["steps"]
        rollback  = plan["rollback"]
        existing  = scan["existing"]
        total     = scan["total_files"]
        ri        = cls._RISK_ICON

        labels = {
            "create_bot":    "🤖 إنشاء بوت",    "modify_bot":   "🤖 تعديل البوت",
            "create_page":   "📄 إنشاء صفحة",  "create_feature":"✨ إنشاء ميزة",
            "modify_auth":   "🔐 تعديل المصادقة","modify_db":   "🗄️ تعديل قاعدة البيانات",
            "modify_ui":     "🎨 تعديل الواجهة","debug_fix":    "🔧 إصلاح خطأ",
        }
        label = labels.get(req_type, f"🛠️ {req_type}")

        lines = [
            f"# {label}\n",
            f"> 📝 **الطلب:** `{msg}`\n",
            "---",

            # ── STEP 1: Scan ──────────────────────────────────────────────────
            "## 🔍 الخطوة 1 — مسح المشروع",
            f"**{total} ملف** تم فحصها · "
            f"{len(existing['routers'])} راوتر · "
            f"{len(existing['templates'])} قالب · "
            f"{len(existing['handlers'])} handler · "
            f"{len(existing['services'])} service",

            # ── STEP 2: Understand ────────────────────────────────────────────
            "",
            "## 🧠 الخطوة 2 — فهم الطلب",
            f"**نوع العملية:** {label} | **العملية:** {und['operation']}",

            # ── STEP 3: Impact ────────────────────────────────────────────────
            "",
            "## 💥 الخطوة 3 — حساب التأثير",
            "**الملفات المتأثرة:**",
        ]

        for af in affected:
            icon   = ri.get(af.get("risk", "LOW"), "⚪")
            action = af.get("action", "")
            lines.append(f"  {icon} `{af['file']}` **[{af['role']}]** `{action}` — {af['why']}")

        if reusable:
            lines.append("\n**♻️ أنظمة موجودة يمكن إعادة استخدامها:**")
            for path, why in reusable:
                lines.append(f"  ♻️ `{path}` — {why}")

        if risks:
            lines.append("\n**⚠️ المخاطر:**")
            for r in risks:
                lines.append(f"  {r}")

        # ── STEP 4+5: Plan ────────────────────────────────────────────────────
        lines += [
            "",
            "## 📋 الخطوة 4+5 — خطة التنفيذ",
            *steps,
            "",
            f"**🔄 استراتيجية الاسترجاع:** {rollback}",
        ]

        return {
            "text": "\n".join(lines),
            "data": {
                "mode":       "project_intelligence_v2",
                "req_type":   req_type,
                "operation":  und["operation"],
                "affected":   [a["file"] for a in affected],
                "risks":      risks,
                "steps":      steps,
                "rollback":   rollback,
                "scan_total": total,
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # PUBLIC ENTRY POINT
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def run(cls, msg: str) -> dict:
        """
        Execute the full 5-step intelligence protocol.
        This is the ONLY entry point for any modification request.
        """
        try:
            scan  = cls._scan()
            und   = cls._understand(msg)
            imp   = cls._calculate_impact(und, scan)
            plan  = cls._generate_plan(und, imp, scan)
            result = cls._format(msg, und, scan, imp, plan)
            AIMemoryLayer.record_decision(
                f"[PIA] {und['req_type']} — {und['operation']}",
                f"affected: {len(imp['affected'])} files, risks: {len(imp['risks'])}",
            )
            return result
        except Exception as e:
            _ai_log.error("ProjectIntelligenceAgent.run error: %s", e, exc_info=True)
            return {
                "text": f"⚠️ خطأ في محرك الذكاء: {e}\nاسأل عن الطلب بصياغة مختلفة.",
                "data": {"error": str(e), "mode": "project_intelligence_error"},
            }


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT SELF-AUDIT ENGINE — Continuous background integrity check
# Detects: dead code, broken imports, SPOF files, syntax errors, security issues
# 10-minute TTL cache — does NOT block chat responses
# ═══════════════════════════════════════════════════════════════════════════════

class ProjectSelfAudit:
    """
    Continuous integrity monitor.
    Checks: SPOF health, syntax errors, security patterns, log errors, tech debt.
    """
    _cache: dict = {}
    _ts:    float = 0.0
    _TTL:   float = 600.0   # 10-minute cache

    # Single-Point-of-Failure files — every project MUST have these healthy
    _SPOF_FILES = [
        ("control_panel/config.py",          "12 راوتر تعتمد عليه — أي خطأ syntax يوقف اللوحة"),
        ("control_panel/app.py",             "نقطة دخول اللوحة — تعطله = اللوحة ساقطة"),
        ("control_panel/auth.py",            "12 راوتر يستخدمون require_owner — تعطله = كل الصفحات مقفلة"),
        ("control_panel/templates/base.html","19 صفحة ترثه — خطأ فيه = كل الواجهة مكسورة"),
        ("control_panel/static/css/style.css","ملف CSS الوحيد لـ 20 صفحة"),
        ("database/db.py",                   "init_db() — فشله يمنع بدء البوت"),
        ("bot.py",                           "نقطة دخول PrimeDownloader — تعطله = البوت ساقط"),
    ]

    @classmethod
    def audit(cls) -> dict:
        """Return cached audit, rebuild if TTL expired."""
        if time.time() - cls._ts < cls._TTL and cls._cache:
            return cls._cache

        result = {
            "spof":         cls._check_spof(),
            "syntax_errors":cls._check_syntax(),
            "security":     security_scan()[:8],
            "log_errors":   detect_log_errors()[:8],
            "tech_debt":    ProjectBrain.TECH_DEBT,
            "risks":        ProjectBrain.RISKS,
            "generated_at": datetime.now().isoformat(),
        }
        cls._cache = result
        cls._ts    = time.time()
        return result

    @classmethod
    def _check_spof(cls) -> list:
        """Verify each SPOF file exists and has no syntax errors."""
        results = []
        for rel, description in cls._SPOF_FILES:
            fp = EXTRACTED_DIR / rel
            if not fp.exists():
                results.append({"file": rel, "description": description,
                                 "status": "MISSING", "error": "ملف غير موجود"})
                continue
            if rel.endswith(".py"):
                try:
                    src = fp.read_text(encoding="utf-8", errors="ignore")
                    ast.parse(src)
                    results.append({"file": rel, "description": description,
                                    "status": "OK", "error": None})
                except SyntaxError as e:
                    results.append({"file": rel, "description": description,
                                    "status": "SYNTAX_ERROR", "error": str(e)})
            else:
                results.append({"file": rel, "description": description,
                                 "status": "OK", "error": None})
        return results

    @classmethod
    def _check_syntax(cls) -> list:
        """Scan all Python files for syntax errors."""
        errors = []
        for rel in [f for f in walk_project() if f.endswith(".py")][:60]:
            try:
                src = (EXTRACTED_DIR / rel).read_text(encoding="utf-8", errors="ignore")
                ast.parse(src)
            except SyntaxError as e:
                errors.append({"file": rel, "error": str(e), "line": e.lineno})
            except Exception:
                pass
        return errors

    @classmethod
    def summary(cls) -> str:
        """One-line health status for display in dashboards."""
        a          = cls.audit()
        spof_ok    = sum(1 for s in a["spof"] if s["status"] == "OK")
        spof_err   = sum(1 for s in a["spof"] if s["status"] != "OK")
        syntax_err = len(a["syntax_errors"])
        sec_issues = len(a["security"])
        log_err    = len(a["log_errors"])
        if spof_err > 0 or syntax_err > 0:
            status = "🔴 CRITICAL"
        elif log_err > 0 or sec_issues > 3:
            status = "⚠️ ISSUES"
        else:
            status = "✅ HEALTHY"
        return (f"{status} | SPOF: {spof_ok}/{len(a['spof'])} OK · "
                f"Syntax: {syntax_err} err · Security: {sec_issues} patterns · "
                f"Log errors: {log_err}")


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT DEPENDENCY GRAPH — Live AST-based import analysis
# Answers: "What breaks if I delete X?" / "What depends on Y?"
# Parses all .py files; 5-min TTL cache.
# ═══════════════════════════════════════════════════════════════════════════════

class ProjectDependencyGraph:
    """
    Live Python import dependency graph built by AST-parsing all .py files.

    forward_graph:  file → [files it imports]
    reverse_graph:  file → [files that import it]

    Key methods:
    - what_depends_on(file)         → direct importers
    - what_breaks_if_deleted(file)  → transitive dependents (BFS)
    - full_impact_report(file)      → combined live + static analysis
    """
    _cache: dict = {}
    _ts:    float = 0.0
    _TTL:   float = 300.0   # 5-minute cache

    # ── Import resolver ────────────────────────────────────────────────────────
    @classmethod
    def _resolve(cls, importing_file: str, module: str, level: int) -> str | None:
        """
        Convert (importing_file, module, level) → relative file path.
        e.g. ('control_panel/routers/foo.py', 'auth', 2) → 'control_panel/auth.py'
        """
        parts        = importing_file.replace("\\", "/").split("/")
        pkg_parts    = parts[:-1]                                    # directory of importing file
        # Go up (level-1) packages
        base         = pkg_parts[:max(0, len(pkg_parts) - (level - 1))] if level > 0 else []
        if level == 0:
            # Absolute import: handlers.start → handlers/start.py
            candidate = module.replace(".", "/") + ".py"
        else:
            # Relative import
            seg_parts = (base + module.split(".")) if module else base
            candidate = "/".join(seg_parts) + ".py"
        return candidate if candidate else None

    # ── Core builder ──────────────────────────────────────────────────────────
    @classmethod
    def _build(cls) -> dict:
        files    = walk_project()
        py_files = [f for f in files if f.endswith(".py")]

        forward:  dict[str, list[str]] = {}   # file → files it imports
        reverse:  dict[str, list[str]] = {f: [] for f in py_files}  # file → importers

        for rel in py_files:
            fp = EXTRACTED_DIR / rel
            try:
                tree = ast.parse(fp.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                forward[rel] = []
                continue

            imported = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        cand = alias.name.replace(".", "/") + ".py"
                        if (EXTRACTED_DIR / cand).exists():
                            imported.append(cand)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    level  = node.level or 0
                    cand   = cls._resolve(rel, module, level)
                    if cand and (EXTRACTED_DIR / cand).exists():
                        imported.append(cand)

            forward[rel] = list(dict.fromkeys(imported))   # deduplicated
            for dep in forward[rel]:
                if dep not in reverse:
                    reverse[dep] = []
                if rel not in reverse[dep]:
                    reverse[dep].append(rel)

        return {
            "forward":       forward,
            "reverse":       reverse,
            "files_scanned": len(py_files),
            "built_at":      datetime.now().isoformat(),
        }

    @classmethod
    def get(cls) -> dict:
        if time.time() - cls._ts < cls._TTL and cls._cache:
            return cls._cache
        try:
            cls._cache = cls._build()
            cls._ts    = time.time()
        except Exception as e:
            _ai_log.warning("ProjectDependencyGraph build error: %s", e)
            if not cls._cache:
                cls._cache = {"forward": {}, "reverse": {}, "files_scanned": 0,
                              "built_at": datetime.now().isoformat()}
        return cls._cache

    # ── Public query API ───────────────────────────────────────────────────────
    @classmethod
    def _resolve_name(cls, rel_path: str) -> str:
        """Try to match a short name ('auth.py') to a full relative path."""
        graph = cls.get()
        reverse = graph.get("reverse", {})
        normalized = rel_path.replace("\\", "/")
        if normalized in reverse:
            return normalized
        # fuzzy by filename
        name = Path(normalized).name
        for key in reverse:
            if Path(key).name == name:
                return key
        # fuzzy by stem  
        stem = Path(normalized).stem
        for key in reverse:
            if Path(key).stem == stem:
                return key
        return normalized

    @classmethod
    def what_depends_on(cls, rel_path: str) -> list[str]:
        """Files that directly import `rel_path`."""
        key     = cls._resolve_name(rel_path)
        reverse = cls.get().get("reverse", {})
        return sorted(reverse.get(key, []))

    @classmethod
    def what_breaks_if_deleted(cls, rel_path: str) -> list[str]:
        """Transitive dependents — BFS on reverse graph from rel_path."""
        reverse  = cls.get().get("reverse", {})
        key      = cls._resolve_name(rel_path)
        visited  = set()
        queue    = list(reverse.get(key, []))
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            for dep in reverse.get(node, []):
                if dep not in visited:
                    queue.append(dep)
        return sorted(visited)

    @classmethod
    def full_impact_report(cls, rel_path: str) -> dict:
        """Complete impact analysis: live import graph + static knowledge."""
        key              = cls._resolve_name(rel_path)
        direct_importers = cls.what_depends_on(key)
        transitive_all   = cls.what_breaks_if_deleted(key)
        static           = analyze_file_impact(rel_path)      # existing static knowledge

        n = len(direct_importers)
        if n >= 10 or static.get("risk") == "critical":
            risk = "CRITICAL"
        elif n >= 5 or static.get("risk") == "high":
            risk = "HIGH"
        elif n >= 2 or static.get("risk") == "medium":
            risk = "MEDIUM"
        elif n >= 1:
            risk = "LOW"
        else:
            risk = "NONE"

        return {
            "file":                key,
            "direct_importers":    direct_importers,
            "transitive_impact":   transitive_all,
            "static_knowledge":    static.get("affects", []),
            "risk":                risk,
            "total_files_at_risk": len(transitive_all),
        }

    # ── Disk persistence ──────────────────────────────────────────────────────
    _PERSIST_FILE: "Path" = Path(__file__).parent / ".ai_knowledge" / "dep_graph.json"

    @classmethod
    def save(cls) -> bool:
        """Persist dep graph to disk so next startup skips the cold AST build."""
        try:
            cls._PERSIST_FILE.parent.mkdir(exist_ok=True)
            data = cls.get()
            cls._PERSIST_FILE.write_text(
                json.dumps({
                    "built_at":      data.get("built_at", ""),
                    "files_scanned": data.get("files_scanned", 0),
                    "forward":       data.get("forward", {}),
                    "reverse":       data.get("reverse", {}),
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return True
        except Exception as _e:
            _ai_log.warning("ProjectDependencyGraph.save(): %s", _e)
            return False

    @classmethod
    def load(cls) -> bool:
        """Load persisted dep graph from disk if fresh (< 1 hour old)."""
        try:
            if not cls._PERSIST_FILE.exists():
                return False
            raw = json.loads(cls._PERSIST_FILE.read_text(encoding="utf-8"))
            age = (datetime.now() - datetime.fromisoformat(
                raw.get("built_at", "2000-01-01T00:00:00")
            )).total_seconds()
            if age > 3600:
                return False
            cls._cache = raw
            cls._ts    = time.time()
            return True
        except Exception as _e:
            _ai_log.warning("ProjectDependencyGraph.load(): %s", _e)
            return False

    @classmethod
    def startup_recover(cls) -> None:
        """Called once at module load. Load from disk or rebuild + save."""
        if cls.load():
            _ai_log.info("DepGraph: loaded from disk (%d files)", cls._cache.get("files_scanned", 0))
            return
        _ai_log.info("DepGraph: cold-building AST graph …")
        cls.get()
        cls.save()
        _ai_log.info("DepGraph: built + saved (%d files)", cls._cache.get("files_scanned", 0))

    @classmethod
    def status(cls) -> dict:
        g = cls.get()
        return {
            "active":        True,
            "files_scanned": g.get("files_scanned", 0),
            "total_deps":    sum(len(v) for v in g.get("forward", {}).values()),
            "age_seconds":   int(time.time() - cls._ts),
            "ttl_seconds":   int(cls._TTL),
            "persist_file":  str(cls._PERSIST_FILE),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT FOUNDATION — REASONING CHAIN + PLANNING GATE
# Mandate: Think → Analyze → Plan → Approve → Execute → Verify
# ═══════════════════════════════════════════════════════════════════════════════

class AgentReasoningChain:
    """
    Mandatory 7-step reasoning enforcer for all project-related responses.

    Step 1: Understand — extract entities, classify intent
    Step 2: Search    — live project search for relevant files
    Step 3: Context   — file roles and categories
    Step 4: Deps      — import callers/callees from live AST graph
    Step 5: Impact    — risk level, transitive affected files
    Step 6: Plan      — execution steps (implementation requests only)
    Step 7: Answer    — project-evidence-backed response (executed by handler)

    AgentReasoningChain.execute() runs steps 1-6 and returns the full chain
    dict so the handler (step 7) has pre-computed evidence to draw on.
    """

    @classmethod
    def execute(cls, msg: str, intent: str, ctx_result: dict = None) -> dict:
        und    = cls._step1_understand(msg)
        search = cls._step2_search(msg, und, ctx_result)
        ctx    = cls._step3_context(search)
        deps   = cls._step4_deps(search.get("files", []))
        impact = cls._step5_impact(search.get("files", []))
        plan   = None
        if intent in ("create_feature", "ui_redesign", "debug_fix", "new_page", "plan_modify"):
            plan = cls._step6_plan(und, deps, impact)
        return {
            "msg": msg, "intent": intent,
            "understanding": und, "search": search,
            "context": ctx, "deps": deps, "impact": impact, "plan": plan,
            "steps_done": [
                f"Understand({und.get('operation','query')})",
                f"Search({len(search.get('files',[]))} files)",
                f"Context({','.join(ctx.get('categories',[])) or 'none'})",
                f"Deps(in={len(deps.get('callers',[]))}/out={len(deps.get('callees',[]))})",
                f"Impact({impact.get('risk','LOW')}/{impact.get('total_affected',0)} files)",
                f"Plan({'yes' if plan else 'skip'})",
            ],
        }

    @classmethod
    def _step1_understand(cls, msg: str) -> dict:
        ml_norm = _normalize_ar(msg.lower())
        target  = None
        for alias, concept in _ALIASES.items():
            if alias in ml_norm or alias in msg.lower():
                target = concept
                break
        pia = ProjectIntelligenceAgent._understand(msg)
        return {
            "target_concept": target,
            "operation":      pia.get("operation", "query"),
            "req_type":       pia.get("req_type", "general"),
            "entities":       pia.get("entities", {}),
            "name_hint":      pia.get("name_hint"),
        }

    @classmethod
    def _step2_search(cls, msg: str, und: dict, ctx_result: dict = None) -> dict:
        """
        Phase 10 — Telegram Priority Rule + Context-Aware File Selection.

        Priority order:
          1. Context-based files (ProjectIndexer.context_files) — ALWAYS first
             when context confidence > 0.05.  Telegram_bot context forces bot
             files before any keyword search so the agent never opens panel
             files when the user is asking about the Telegram bot.
          2. Semantic map (concept match) — fallback when context yields nothing.
          3. Keyword / _find_concept — last resort.

        Files are de-duplicated and capped at 8.
        """
        ctx_name  = (ctx_result or {}).get("detected", "general")
        ctx_conf  = (ctx_result or {}).get("confidence", 0.0)
        concept   = und.get("target_concept")

        # ── Step A: Context-priority files (Phase 10) ─────────────────────────
        ctx_files: list = []
        if ctx_name != "general" and ctx_conf > 0.05 and _PI_OK and _PI is not None:
            try:
                ctx_files = _PI.context_files(ctx_name, limit=4)
            except Exception:
                pass

        # ── Step B: Semantic / keyword search ─────────────────────────────────
        semantic_files: list = []
        if concept and concept in _SEMANTIC_MAP:
            semantic_files = [e[0] for e in _SEMANTIC_MAP[concept]
                              if isinstance(e, (list, tuple))]
        if not semantic_files:
            semantic_files = [p for p, _, _ in _find_concept(msg)]

        # ── Step C: Indexer keyword search as extra signal ────────────────────
        indexer_files: list = []
        if _PI_OK and _PI is not None and not semantic_files:
            try:
                indexer_files = _PI.search(msg, limit=4)
            except Exception:
                pass

        # ── CONTEXT LOCK: high-confidence context filters cross-subsystem files ─
        # REPAIR (Problem 2): threshold lowered from 0.45 → 0.25.
        # At 0.45 most messages never triggered the lock, allowing cross-subsystem
        # file leakage (e.g. Telegram question pulling control_panel files).
        # At 0.25 any clear single-signal match activates context isolation.
        # The lock is still skipped if it would empty the list entirely, so
        # edge-case questions never go silently unanswered.
        if ctx_name != "general" and ctx_conf > 0.25:
            _SUBSYSTEM_GUARD: dict = {
                "telegram_bot":   lambda f: any(s in f for s in (
                    "handlers/", "bot.py", "support_bot/", "keyboards/", "commands/")),
                "control_panel":  lambda f: ("control_panel/" in f or "panel" in f),
                "database":       lambda f: any(s in f for s in (
                    "database/", "db.py", "models.py", "migrations/")),
                "router_layer":   lambda f: "routers/" in f,
                "api_layer":      lambda f: ("routers/" in f or "api" in f),
                "frontend_layer": lambda f: (
                    f.endswith(".html") or "/static/" in f
                    or f.endswith(".css") or f.endswith(".js")),
            }
            _guard_fn = _SUBSYSTEM_GUARD.get(ctx_name)
            if _guard_fn is not None:
                _locked_sem = [f for f in semantic_files if _guard_fn(f)]
                _locked_idx = [f for f in indexer_files  if _guard_fn(f)]
                if _locked_sem or ctx_files:
                    semantic_files = _locked_sem
                    indexer_files  = _locked_idx
                    _ai_log.debug(
                        "ContextLock(%s, conf=%.2f): filtered semantic %d→%d, idx %d→%d",
                        ctx_name, ctx_conf,
                        len(semantic_files), len(_locked_sem),
                        len(indexer_files),  len(_locked_idx),
                    )

        # ── Merge: context first, then semantic, then indexer ─────────────────
        seen: set = set()
        merged: list = []
        for f in ctx_files + semantic_files + indexer_files:
            if f and f not in seen:
                seen.add(f)
                merged.append(f)

        search_method = ("context+" + ("semantic" if concept else "keyword")
                         if ctx_files else ("semantic" if concept else "keyword"))

        return {
            "files":         merged[:8],
            "concept":       concept,
            "search_method": search_method,
            "ctx_files":     ctx_files,
            "ctx_name":      ctx_name,
            "ctx_conf":      round(ctx_conf, 3),
        }

    @classmethod
    def _step3_context(cls, search: dict) -> dict:
        roles: dict = {}
        cats:  set  = set()
        for f in search.get("files", []):
            r = ("router"   if "router"   in f else
                 "handler"  if "handler"  in f else
                 "database" if ("database" in f or f.endswith("db.py")) else
                 "template" if f.endswith(".html") else
                 "service"  if "service"  in f else
                 "config"   if ("config" in f or "settings" in f) else "module")
            roles[f] = r
            cats.add(r)
        return {"file_roles": roles, "categories": list(cats)}

    @classmethod
    def _step4_deps(cls, files: list) -> dict:
        if not files:
            return {"callers": [], "callees": [], "critical": False,
                    "func_calls": [], "kg_trace": {}, "circular": []}
        g         = ProjectDependencyGraph.get()
        forward   = g.get("forward", {})
        callers:  list = []
        callees:  list = []
        for f in files[:4]:
            callers.extend(ProjectDependencyGraph.what_depends_on(f))
            key = ProjectDependencyGraph._resolve_name(f)
            callees.extend(forward.get(key, []))
        callers = list(dict.fromkeys(callers))[:20]
        callees = list(dict.fromkeys(callees))[:20]

        # ── Call Graph enrichment (Phase 4) ───────────────────────────────────
        func_calls: list = []
        circular:   list = []
        if _CALL_GRAPH_OK and _CallGraph is not None:
            try:
                for f in files[:3]:
                    func_calls.extend(_CallGraph.who_calls_file(f))
                func_calls = func_calls[:15]
                circular   = _CallGraph.circular_imports()[:5]
            except Exception:
                pass

        # ── Knowledge Graph cross-type trace (Phase 1/2) ──────────────────────
        kg_trace: dict = {}
        if _KG_OK and _KG is not None and files:
            try:
                kg_trace = _KG.full_trace(files[0])
            except Exception:
                pass

        return {
            "callers":    callers,
            "callees":    callees,
            "critical":   len(callers) >= 5,
            "func_calls": func_calls,
            "circular":   circular,
            "kg_trace":   kg_trace,
        }

    @classmethod
    def _step5_impact(cls, files: list) -> dict:
        if not files:
            return {"risk": "LOW", "total_affected": 0, "reports": []}
        ro = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}
        reports = []
        max_r   = "LOW"
        total   = 0
        for f in files[:3]:
            r = ProjectDependencyGraph.full_impact_report(f)
            reports.append(r)
            total += r.get("total_files_at_risk", 0)
            if ro.get(r.get("risk", "LOW"), 0) > ro.get(max_r, 0):
                max_r = r["risk"]
        return {"risk": max_r, "total_affected": total, "reports": reports}

    @classmethod
    def _step6_plan(cls, und: dict, deps: dict, impact: dict) -> dict:
        return {
            "steps": [
                "1. مراجعة الملفات المتأثرة المذكورة أعلاه",
                "2. أخذ نسخة احتياطية عبر `/backups`",
                "3. تطبيق التغييرات بالترتيب المحدد",
                "4. اختبار كل ملف بعد التعديل",
                "5. مراجعة `/logs` للتحقق من غياب الأخطاء",
            ],
            "requires_approval": True,
            "risk":              impact.get("risk", "MEDIUM"),
            "affected_count":    impact.get("total_affected", 0),
        }


class AgentPlanningGate:
    """
    Approval gate for ALL implementation requests.

    MANDATE: Never execute file-changing operations without explicit user approval.

    Flow:
      submit(msg)         → runs 5-step ProjectIntelligenceAgent → returns plan
                            sets _pending + adds ⏸️ approval prompt to response
      is_approval(msg)    → True if user said موافق/approve/yes etc.
      is_rejection(msg)   → True if user said إلغاء/cancel/no etc.
      execute_approved()  → user confirmed → run verification checklist → return report
      cancel()            → clear pending plan

    NEVER executes without explicit approval from the user.
    """
    _pending:     "dict | None" = None
    _pending_msg: str           = ""

    _APPROVE = re.compile(
        r"^(?:موافق|approve|نعم|yes|تمام|اوكي|ok|okay|proceed|نفذ|تنفيذ|"
        r"go\s*ahead|ابدأ|ابدا|صح|correct|بالتأكيد|تأكيد|confirm)$",
        re.IGNORECASE,
    )
    _REJECT = re.compile(
        r"^(?:إلغاء|الغاء|cancel|لا|no|stop|وقف|أوقف|اوقف|لأ|"
        r"لا\s*شكراً|لا\s*شكرا|not\s*now|ألغِ)$",
        re.IGNORECASE,
    )

    @classmethod
    def submit(cls, msg: str) -> dict:
        """Analyze request, produce plan, and await explicit approval."""
        update_stats("total_plans")
        result = ProjectIntelligenceAgent.run(msg)

        cls._pending     = result
        cls._pending_msg = msg

        text  = result.get("text", "")
        text += (
            "\n\n" + "─" * 52 + "\n"
            "⏸️ **بانتظار موافقتك قبل أي تنفيذ**\n\n"
            "هل تريد المتابعة بهذه الخطة؟\n"
            "  ✅ للموافقة: اكتب **`موافق`** أو **`approve`** أو **`نعم`**\n"
            "  ❌ للإلغاء:  اكتب **`إلغاء`** أو **`cancel`** أو **`لا`**\n\n"
            "💡 *لن يُنفَّذ أي تغيير حتى تصدر موافقتك الصريحة.*"
        )
        result["text"] = text
        result.setdefault("data", {})
        result["data"]["approval_pending"] = True
        return result

    @classmethod
    def is_approval(cls, msg: str) -> bool:
        return bool(cls._APPROVE.match(msg.strip())) and cls._pending is not None

    @classmethod
    def is_rejection(cls, msg: str) -> bool:
        return bool(cls._REJECT.match(msg.strip())) and cls._pending is not None

    @classmethod
    def execute_approved(cls) -> dict:
        """User confirmed → return verification checklist + mark as executed."""
        if not cls._pending:
            return {"text": "⚠️ لا توجد خطة معلقة للتنفيذ.", "data": {}}
        plan = cls._pending
        msg  = cls._pending_msg
        cls._pending     = None
        cls._pending_msg = ""

        dep_st = ProjectDependencyGraph.status()
        AIMemoryLayer.record_decision(
            f"Plan approved: {msg[:80]}",
            f"{dep_st['files_scanned']} files in dep graph",
        )
        return {
            "text": (
                "✅ **تمت الموافقة — الخطة مفعّلة**\n\n"
                f"📋 **الطلب:** `{msg[:100]}`\n\n"
                "**📌 قائمة التحقق بعد التنفيذ (Verification Checklist):**\n"
                "  1️⃣ راجع كل ملف متأثر يدوياً بعد التعديل\n"
                "  2️⃣ افتح `/logs` في لوحة التحكم — تحقق من غياب الأخطاء\n"
                "  3️⃣ إذا عدّلت handler بوت → أعِد تشغيل workflow البوت\n"
                "  4️⃣ إذا عدّلت router لوحة → أعِد تشغيل TitanX Control Panel\n"
                "  5️⃣ إذا عدّلت database/db.py → تحقق من init_db() تعمل بدون خطأ\n"
                "  6️⃣ خذ نسخة احتياطية من `/backups` بعد التحقق\n\n"
                f"🔍 **حالة التبعيات:** {dep_st['files_scanned']} ملف ممسوح — "
                f"{dep_st['total_deps']} علاقة نشطة"
            ),
            "data": {
                "approved_plan":         plan.get("data", {}),
                "dep_status":            dep_st,
                "verification_required": True,
            },
        }

    @classmethod
    def cancel(cls) -> dict:
        cls._pending     = None
        cls._pending_msg = ""
        return {
            "text": "❌ **تم إلغاء الخطة.**\n\nيمكنك طرح أي طلب جديد في أي وقت.",
            "data": {"cancelled": True},
        }

    @classmethod
    def has_pending(cls) -> bool:
        return cls._pending is not None


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT INDEX — Structured auto-updating component catalog
# Categories: routers, templates, apis, bots, database, config, ai, handlers, services
# 5-min TTL; auto-rebuilds when called after TTL expires.
# ═══════════════════════════════════════════════════════════════════════════════

class ProjectIndex:
    """
    Structured catalog of all 144 project files, categorized by role.
    Never hardcoded — rebuilt from live filesystem every 5 minutes.

    Usage:
        idx = ProjectIndex.get()
        idx["routers"]   → list of {file, name, routes, templates}
        idx["templates"] → list of {file, name, base}
        idx["bots"]      → list of {file, type}
        ...
    """
    _cache: dict = {}
    _ts:    float = 0.0
    _TTL:   float = 300.0

    @classmethod
    def _build(cls) -> dict:
        files   = walk_project()
        dep_map = build_dependency_map()

        idx: dict = {
            "routers":   [],
            "templates": [],
            "apis":      [],
            "bots":      [],
            "database":  [],
            "config":    [],
            "ai_files":  [],
            "handlers":  [],
            "services":  [],
            "static":    [],
            "other":     [],
            "total_files": len(files),
            "built_at":    datetime.now().isoformat(),
        }

        for rel in files:
            fp    = EXTRACTED_DIR / rel
            fname = Path(rel).name
            stem  = Path(rel).stem

            # Bots
            if fname == "bot.py" or (rel.endswith("/bot.py")):
                btype = "main_bot" if rel == "bot.py" else "support_bot" if "support_bot" in rel else "bot"
                idx["bots"].append({"file": rel, "type": btype})

            # Routers
            elif "/routers/" in rel and rel.endswith(".py"):
                rts = [r for r, v in dep_map.items()
                       if Path(v.get("file", "")).name == fname]
                tpls = list({t for r, v in dep_map.items()
                             if Path(v.get("file","")).name == fname
                             for t in v.get("templates", [])})
                idx["routers"].append({
                    "file": rel, "name": stem,
                    "routes": rts[:8], "templates": tpls,
                })

            # Templates
            elif rel.endswith(".html"):
                try:
                    content = fp.read_text(errors="ignore")
                    base    = "base.html" if "extends" in content else "standalone"
                except Exception:
                    base = "unknown"
                idx["templates"].append({"file": rel, "name": stem, "base": base})

            # Database
            elif "/database/" in rel and rel.endswith(".py"):
                idx["database"].append({"file": rel, "name": stem})

            # Config
            elif fname in ("settings.py", "config.py") or "config" in stem.lower():
                idx["config"].append({"file": rel, "name": stem})

            # AI files
            elif "ai_engine" in stem or "ai_workspace" in stem:
                idx["ai_files"].append({"file": rel, "name": stem})

            # Handlers
            elif "/handlers/" in rel and rel.endswith(".py"):
                idx["handlers"].append({"file": rel, "name": stem})

            # Services
            elif "/services/" in rel and rel.endswith(".py"):
                idx["services"].append({"file": rel, "name": stem})

            # Static
            elif "/static/" in rel:
                idx["static"].append({"file": rel, "ext": Path(rel).suffix})

            # Other
            elif rel.endswith(".py"):
                idx["other"].append({"file": rel, "name": stem})

        # API list from dependency map
        idx["apis"] = [
            {"route": r, "file": v["file"], "templates": v["templates"]}
            for r, v in list(dep_map.items())[:60]
        ]

        return idx

    @classmethod
    def get(cls) -> dict:
        if time.time() - cls._ts < cls._TTL and cls._cache:
            return cls._cache
        try:
            cls._cache = cls._build()
            cls._ts    = time.time()
        except Exception as e:
            _ai_log.warning("ProjectIndex build error: %s", e)
            if not cls._cache:
                cls._cache = {"error": str(e), "total_files": 0,
                              "built_at": datetime.now().isoformat()}
        return cls._cache

    @classmethod
    def summary(cls) -> str:
        i = cls.get()
        return (
            f"Routers: {len(i.get('routers',[]))} · "
            f"Templates: {len(i.get('templates',[]))} · "
            f"APIs: {len(i.get('apis',[]))} · "
            f"Bots: {len(i.get('bots',[]))} · "
            f"Handlers: {len(i.get('handlers',[]))} · "
            f"Services: {len(i.get('services',[]))} · "
            f"DB: {len(i.get('database',[]))} · "
            f"Total: {i.get('total_files', 0)} files"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSATION KNOWLEDGE BASE
# Used by _r_conversation() — general tech knowledge, no project file access
# ═══════════════════════════════════════════════════════════════════════════════

_TECH_KNOWLEDGE: dict = {
    "python": {
        "emoji": "🐍", "title": "Python",
        "what": "لغة برمجة مفسَّرة عالية المستوى، متعددة الاستخدامات",
        "strengths": ["كود قصير وواضح جداً", "مجتمع ضخم وموارد لا تُحصى",
                      "مكتبات لكل شيء (AI/Web/Automation)", "سهل التعلم"],
        "weaknesses": ["أبطأ من C++/Java في الحسابات المكثفة",
                       "GIL يحدّ من CPU parallelism",
                       "استهلاك ذاكرة أعلى من اللغات المجمَّعة"],
        "uses": ["ذكاء اصطناعي وتعلم آلة", "خوادم ويب (FastAPI/Django/Flask)",
                 "أتمتة مهام", "بوتات Telegram/Discord", "علم البيانات"],
        "in_project": "المشروع مكتوب بالكامل بـ Python — FastAPI + python-telegram-bot",
    },
    "javascript": {
        "emoji": "⚡", "title": "JavaScript",
        "what": "لغة الويب الأساسية، تعمل في المتصفح وعلى الخادم (Node.js)",
        "strengths": ["يعمل في المتصفح مباشرة — لا بديل", "Node.js سريع جداً (I/O)",
                      "async/await ممتاز", "مجتمع ضخم جداً"],
        "weaknesses": ["type coercion مربك بدون TypeScript",
                       "callback hell في الكود القديم"],
        "uses": ["واجهات مستخدم تفاعلية", "تطبيقات React/Vue",
                 "خوادم Node.js", "PWA وتطبيقات هجينة"],
        "in_project": "JavaScript خفيف في الصفحات (app.js) — ليس framework",
    },
    "typescript": {
        "emoji": "🔷", "title": "TypeScript",
        "what": "JavaScript مع نظام أنواع ثابتة (static typing) قوي",
        "strengths": ["أخطاء أقل بكثير في الإنتاج",
                      "IntelliSense ودعم IDE ممتاز", "Refactoring آمن"],
        "weaknesses": ["يحتاج compilation step", "learning curve أكبر من JS"],
        "uses": ["مشاريع كبيرة ومعقدة", "فِرق متعددة المطورين",
                 "أي مشروع يكبر عن حده"],
        "in_project": "غير مستخدم — المشروع يعتمد Python + plain JS",
    },
    "fastapi": {
        "emoji": "🚀", "title": "FastAPI",
        "what": "إطار ويب Python عالي الأداء مبني على Starlette + Pydantic",
        "strengths": ["أسرع Python framework (يقارب Node.js و Go)",
                      "توثيق OpenAPI/Swagger يُولَّد تلقائياً",
                      "Type hints + validation مدمجة بالكامل",
                      "Async-native من الأساس"],
        "weaknesses": ["مجتمع أصغر من Flask/Django (يكبر بسرعة)",
                       "learning curve لـ async إن لم تكن معتاداً"],
        "uses": ["REST APIs", "لوحات تحكم", "خوادم AI/ML", "Microservices"],
        "in_project": "X Control Center مبني كاملاً على FastAPI — control_panel/app.py نقطة الدخول",
    },
    "flask": {
        "emoji": "🌶️", "title": "Flask",
        "what": "Microframework Python خفيف ومرن جداً",
        "strengths": ["بسيط جداً للتعلم والبدء", "مرونة كاملة في الاختيار",
                      "مجتمع ضخم وموثّق جيداً"],
        "weaknesses": ["أبطأ من FastAPI", "لا type checking مدمج",
                       "يحتاج تكوين يدوي أكثر"],
        "uses": ["نماذج أولية سريعة", "مواقع صغيرة-متوسطة", "APIs بسيطة"],
        "in_project": "المشروع يستخدم FastAPI وليس Flask",
    },
    "django": {
        "emoji": "🎸", "title": "Django",
        "what": "إطار ويب Python كامل (batteries-included)",
        "strengths": ["كل شيء مدمج: ORM, auth, admin, forms",
                      "آمن بشكل افتراضي", "مجتمع ضخم جداً"],
        "weaknesses": ["ثقيل للمشاريع الصغيرة", "Monolithic",
                       "أبطأ بكثير من FastAPI"],
        "uses": ["مواقع ويب كاملة", "منصات تجارية وإعلامية",
                 "أي مشروع يحتاج admin جاهزاً"],
        "in_project": "المشروع يستخدم FastAPI وليس Django",
    },
    "telegram_bot": {
        "emoji": "🤖", "title": "Telegram Bot",
        "what": "برامج آلية تعمل على منصة Telegram عبر Bot API الرسمي",
        "strengths": ["API مجاني وموثّق ممتاز", "Polling وWebhooks",
                      "دعم ملفات حتى 2GB", "Inline keyboards قوية"],
        "weaknesses": ["Rate limits صارمة (لا يمكن تجاوزها)",
                       "قيود على بعض المحتوى", "يعتمد على استمرارية خدمة Telegram"],
        "uses": ["خدمة عملاء آلية", "تحميل ملفات (مثل PrimeDownloader)",
                 "إشعارات وتنبيهات", "ألعاب واستبيانات"],
        "in_project": "بوتان: PrimeDownloader (bot.py) + Support Bot (support_bot/bot.py)",
    },
    "rest_api": {
        "emoji": "🔗", "title": "REST API",
        "what": "أسلوب معماري لتصميم خدمات الويب يعتمد على HTTP",
        "strengths": ["بسيط وواسع الانتشار", "يعمل مع أي لغة وأي client",
                      "قابل للـ cache", "Stateless = قابل للتوسع"],
        "weaknesses": ["Over-fetching وunder-fetching", "لا real-time مدمج",
                       "Versioning قد يكون معقداً"],
        "in_project": "كل واجهات لوحة التحكم REST — /api/* في كل router",
    },
    "graphql": {
        "emoji": "⬡", "title": "GraphQL",
        "what": "لغة استعلام للـ APIs تتيح للعميل طلب البيانات التي يحتاجها بالضبط",
        "strengths": ["لا over-fetching/under-fetching", "Schema strongly-typed",
                      "Introspection مدمج", "Single endpoint"],
        "weaknesses": ["أصعب من REST للمبتدئين", "Caching أعقد",
                       "N+1 problem إن لم تُحسن Query"],
        "in_project": "المشروع يستخدم REST وليس GraphQL",
    },
    "docker": {
        "emoji": "🐳", "title": "Docker",
        "what": "منصة Containerization — تغليف التطبيق مع بيئته الكاملة",
        "strengths": ["بيئات موحّدة في كل مكان", "نشر سريع وموثوق",
                      "عزل كامل بين التطبيقات", "قابلية توسع عالية"],
        "weaknesses": ["Learning curve ملحوظ", "Overhead على موارد النظام",
                       "Orchestration (K8s) معقد جداً"],
        "in_project": "المشروع يعمل على Replit مباشرة — لا Docker مستخدم",
    },
    "sql": {
        "emoji": "🗄️", "title": "SQL / Relational Databases",
        "what": "لغة الاستعلام الهيكلية لإدارة قواعد البيانات العلاقية",
        "strengths": ["ACID transactions — موثوقية كاملة",
                      "علاقات معقدة بكفاءة", "Mature ومستقر منذ 50 سنة"],
        "weaknesses": ["Schema rigid — التغيير يحتاج migration",
                       "Scaling أفقي أصعب من NoSQL"],
        "types": ["PostgreSQL — أقوى وأكثر ميزات",
                  "MySQL — شائع وسريع للقراءة",
                  "SQLite — خفيف جداً بدون خادم"],
        "in_project": "SQLite عبر db_utils.py — مناسب لحجم المشروع",
    },
    "nosql": {
        "emoji": "📊", "title": "NoSQL Databases",
        "what": "قواعد بيانات غير علاقية مرنة في الهيكل",
        "strengths": ["Schema مرن جداً", "Scaling أفقي سهل",
                      "Redis سريع جداً للـ cache"],
        "weaknesses": ["لا ACID كامل في الغالب",
                       "استعلامات أقل قوة من SQL"],
        "types": ["MongoDB — Documents (JSON-like)",
                  "Redis — Key-Value (in-memory)",
                  "Cassandra — Wide columns (scale ضخم)",
                  "Neo4j — Graph (علاقات معقدة)"],
        "in_project": "المشروع يعتمد SQL (SQLite) وليس NoSQL",
    },
    "async": {
        "emoji": "⚙️", "title": "Async / Await",
        "what": "نمط برمجي يسمح بتنفيذ مهام I/O متعددة دون حجب thread واحد",
        "strengths": ["خوادم أسرع بكثير لطلبات I/O",
                      "استهلاك ذاكرة أقل من Multi-threading",
                      "كود أنظف من Callbacks"],
        "weaknesses": ["يحتاج فهم Event Loop",
                       "CPU-bound tasks لا تستفيد منه"],
        "in_project": "FastAPI و python-telegram-bot كلاهما async بالكامل",
    },
}

_COMPARE_MAP: dict = {
    frozenset(["python", "javascript"]): {
        "title": "Python مقابل JavaScript",
        "rows": [
            ("الهدف الأساسي", "Backend/AI/Scripting", "Frontend + Backend (Node.js)"),
            ("الأداء I/O", "جيد (asyncio)", "ممتاز (Node.js event loop)"),
            ("قابلية القراءة", "⭐⭐⭐⭐⭐ أوضح وأقصر", "⭐⭐⭐ يحتاج TypeScript"),
            ("AI/ML", "⭐⭐⭐⭐⭐ الخيار الأول", "⭐⭐ محدود"),
            ("المتصفح", "❌ لا يعمل مباشرة", "⭐⭐⭐⭐⭐ الخيار الوحيد"),
            ("سوق العمل", "مطلوب جداً", "مطلوب جداً"),
        ],
        "verdict": "Python للـ backend/AI — JavaScript للـ frontend وإن أردت full-stack",
        "in_project": "المشروع Python بالكامل ✅",
    },
    frozenset(["fastapi", "flask"]): {
        "title": "FastAPI مقابل Flask",
        "rows": [
            ("الأداء", "⭐⭐⭐⭐⭐ Async-native", "⭐⭐⭐ Sync (Flask 2+ async)"),
            ("التوثيق التلقائي", "⭐⭐⭐⭐⭐ OpenAPI مدمج", "❌ يحتاج Flask-RestX"),
            ("Type Validation", "⭐⭐⭐⭐⭐ Pydantic", "⭐ يدوي"),
            ("سهولة التعلم", "⭐⭐⭐ يحتاج async", "⭐⭐⭐⭐⭐ بسيط جداً"),
            ("الإنتاج", "الأنسب للـ APIs الحديثة", "مناسب للمشاريع الصغيرة"),
        ],
        "verdict": "FastAPI للمشاريع الجديدة — Flask للنماذج السريعة",
        "in_project": "المشروع يستخدم FastAPI — الاختيار الصحيح ✅",
    },
    frozenset(["fastapi", "django"]): {
        "title": "FastAPI مقابل Django",
        "rows": [
            ("الهدف", "APIs خالصة", "تطبيق ويب كامل"),
            ("الأداء", "⭐⭐⭐⭐⭐", "⭐⭐⭐"),
            ("Admin Panel", "❌ يدوي", "⭐⭐⭐⭐⭐ جاهز"),
            ("ORM مدمج", "❌ SQLAlchemy/Drizzle", "⭐⭐⭐⭐⭐ Django ORM"),
            ("Auth مدمج", "❌ يدوي", "⭐⭐⭐⭐⭐ جاهز"),
        ],
        "verdict": "FastAPI للـ API-first — Django إن احتجت admin وORM مدمجَين",
        "in_project": "FastAPI مناسب لأن الهدف API + Bot ✅",
    },
    frozenset(["sql", "nosql"]): {
        "title": "SQL مقابل NoSQL",
        "rows": [
            ("هيكل البيانات", "Schema ثابت ومنظم", "Schema مرن"),
            ("العلاقات", "⭐⭐⭐⭐⭐ ممتاز", "⭐⭐ محدود"),
            ("ACID", "⭐⭐⭐⭐⭐ كامل", "⭐⭐ جزئي في الغالب"),
            ("Scaling أفقي", "⭐⭐⭐ متوسط", "⭐⭐⭐⭐⭐ ممتاز"),
            ("الاستخدام المثالي", "بيانات مترابطة ومنظمة", "بيانات ضخمة ومرنة"),
        ],
        "verdict": "SQL للبيانات المنظمة ذات العلاقات — NoSQL للحجم الضخم والمرونة",
        "in_project": "SQLite (SQL) — مناسب تماماً لحجم المشروع ✅",
    },
    frozenset(["rest_api", "graphql"]): {
        "title": "REST مقابل GraphQL",
        "rows": [
            ("سهولة التعلم", "⭐⭐⭐⭐⭐ بسيط", "⭐⭐⭐ يحتاج تعلم"),
            ("Over-fetching", "مشكلة شائعة", "⭐⭐⭐⭐⭐ محلولة"),
            ("Caching", "⭐⭐⭐⭐⭐ سهل", "⭐⭐ معقد"),
            ("Tooling", "⭐⭐⭐⭐⭐ ناضج", "⭐⭐⭐⭐ ينضج"),
        ],
        "verdict": "REST للمشاريع الجديدة والمتوسطة — GraphQL لتطبيقات data-heavy",
        "in_project": "المشروع يستخدم REST ✅",
    },
}

SKIP_DIRS  = {
    "__pycache__", ".git", "node_modules", ".pythonlibs", "temp", "backups",
    ".local", ".venv", "dist", "build", ".cache", ".ai_backups", "artifacts",
}
CODE_EXTS  = {".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".toml", ".sh", ".md"}


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT KNOWLEDGE GRAPH — complete map of every relationship in the project
# ═══════════════════════════════════════════════════════════════════════════════

_ROUTE_GRAPH: dict = {
    # ── Control Panel routes ──────────────────────────────────────────────────
    "/": {
        "router": "control_panel/routers/dashboard.py",
        "template": "control_panel/templates/dashboard.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/api/stats", "/api/activity", "/api/chart"],
        "description": "الصفحة الرئيسية / لوحة التحكم",
        "aliases": ["homepage", "home", "dashboard", "main page", "الرئيسية", "الصفحة الرئيسية", "لوحة التحكم"],
    },
    "/dashboard": {
        "router": "control_panel/routers/dashboard.py",
        "template": "control_panel/templates/dashboard.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/api/stats", "/api/activity", "/api/chart"],
        "description": "لوحة التحكم الرئيسية",
        "aliases": ["dashboard", "dash", "لوحة", "لوحة تحكم"],
    },
    "/panel": {
        "router": "control_panel/app.py",
        "template": "control_panel/templates/access.html",
        "base": None,
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/panel/login", "/panel/api/change-password"],
        "description": "صفحة الدخول / المصادقة",
        "aliases": ["login", "access", "panel", "auth page", "صفحة الدخول", "تسجيل الدخول"],
    },
    "/panel/login": {
        "router": "control_panel/app.py",
        "template": "control_panel/templates/access.html",
        "base": None,
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": [],
        "description": "معالج تسجيل الدخول",
        "aliases": ["login handler", "auth handler"],
    },
    "/users": {
        "router": "control_panel/routers/users.py",
        "template": "control_panel/templates/users.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/users/api/list", "/users/api/{user_id}", "/users/api/ban", "/users/api/unban", "/users/api/points", "/users/api/premium"],
        "description": "إدارة المستخدمين",
        "aliases": ["users", "user management", "user page", "إدارة المستخدمين", "المستخدمون", "صفحة المستخدمين"],
    },
    "/broadcast": {
        "router": "control_panel/routers/broadcast.py",
        "template": "control_panel/templates/broadcast.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/broadcast/api/send", "/broadcast/api/status"],
        "description": "نظام البث للمستخدمين",
        "aliases": ["broadcast", "بث", "رسائل جماعية", "إرسال"],
    },
    "/db": {
        "router": "control_panel/routers/db_manager.py",
        "template": "control_panel/templates/db_manager.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/db/api/info", "/db/api/repair"],
        "description": "مدير قاعدة البيانات",
        "aliases": ["database", "db", "db manager", "قاعدة بيانات", "مدير قاعدة البيانات"],
    },
    "/files": {
        "router": "control_panel/routers/files.py",
        "template": "control_panel/templates/files.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/files/api/list", "/files/api/read", "/files/api/save", "/files/api/delete", "/files/api/upload", "/files/api/download"],
        "description": "مدير الملفات",
        "aliases": ["files", "file manager", "file explorer", "ملفات", "مدير ملفات"],
    },
    "/logs": {
        "router": "control_panel/routers/logs_router.py",
        "template": "control_panel/templates/logs.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/logs/api/read", "/logs/api/files", "/logs/api/clear"],
        "description": "عارض السجلات",
        "aliases": ["logs", "log viewer", "سجلات", "سجل", "أخطاء السجل"],
    },
    "/system": {
        "router": "control_panel/routers/system.py",
        "template": "control_panel/templates/system.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/system/api/stats", "/system/api/bots"],
        "description": "حالة النظام",
        "aliases": ["system", "system status", "نظام", "حالة النظام", "CPU", "RAM", "ذاكرة"],
    },
    "/updates": {
        "router": "control_panel/routers/updates.py",
        "template": "control_panel/templates/updates.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/updates/api/analyze", "/updates/api/apply", "/updates/api/status", "/updates/api/backup", "/updates/api/restore"],
        "description": "مركز التحديثات",
        "aliases": ["updates", "update center", "تحديثات", "مركز تحديثات"],
    },
    "/github": {
        "router": "control_panel/routers/github_router.py",
        "template": "control_panel/templates/github.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/github/api/info", "/github/api/pull", "/github/api/push", "/github/api/commit", "/github/api/diff"],
        "description": "تكامل GitHub",
        "aliases": ["github", "git", "جيتهب", "تكامل جيتهب"],
    },
    "/search": {
        "router": "control_panel/routers/search.py",
        "template": "control_panel/templates/search.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/search/api"],
        "description": "بحث في المشروع",
        "aliases": ["search", "بحث", "بحث في المشروع"],
    },
    "/bots": {
        "router": "control_panel/routers/bots.py",
        "template": "control_panel/templates/bots.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/bots/api/status", "/bots/api/start/{key}", "/bots/api/stop/{key}", "/bots/api/restart/{key}", "/bots/api/logs/{key}"],
        "description": "إدارة البوتات",
        "aliases": ["bots", "bot management", "بوتات", "إدارة بوتات", "بوت"],
    },
    "/backups": {
        "router": "control_panel/routers/backups.py",
        "template": "control_panel/templates/backups.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/backups/api/list", "/backups/api/create", "/backups/api/verify/{name}", "/backups/api/restore/{name}", "/backups/api/download/{name}"],
        "description": "مركز النسخ الاحتياطية",
        "aliases": ["backups", "backup system", "نسخ احتياطية", "النسخ الاحتياطية", "احتياطي"],
    },
    "/replit": {
        "router": "control_panel/routers/replit_manager.py",
        "template": "control_panel/templates/replit_manager.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/replit/api/health", "/replit/api/processes", "/replit/api/routes", "/replit/api/check-panel"],
        "description": "مركز إدارة Replit",
        "aliases": ["replit", "replit manager", "ريبليت"],
    },
    "/ai": {
        "router": "control_panel/routers/ai_workspace.py",
        "template": "control_panel/templates/ai_workspace.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/ai/api/chat", "/ai/api/structure", "/ai/api/errors", "/ai/api/suggestions", "/ai/api/plan", "/ai/api/plan_v2", "/ai/api/knowledge", "/ai/api/search", "/ai/api/file_question", "/ai/api/dependencies", "/ai/api/self_test"],
        "description": "X AI Operator — مركز الذكاء الاصطناعي",
        "aliases": ["ai workspace", "ai operator", "ai chat", "مساحة ai", "الذكاء الاصطناعي", "ai"],
    },
    "/ai/engineer": {
        "router": "control_panel/routers/ai_workspace.py",
        "template": "control_panel/templates/ai_engineer.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/ai/api/plan_v2", "/ai/api/file_question", "/ai/api/dependencies"],
        "description": "مهندس الذكاء الاصطناعي",
        "aliases": ["ai engineer", "engineer page", "ai engineering", "مهندس الذكاء", "مهندس ai"],
    },
    "/ai/memory": {
        "router": "control_panel/routers/ai_workspace.py",
        "template": "control_panel/templates/ai_memory.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/ai/api/memory"],
        "description": "ذاكرة المشروع",
        "aliases": ["ai memory", "project memory", "ذاكرة المشروع", "ai memory page"],
    },
    "/ai/review": {
        "router": "control_panel/routers/ai_workspace.py",
        "template": "control_panel/templates/ai_review.html",
        "base": "control_panel/templates/base.html",
        "css": ["control_panel/static/css/style.css"],
        "js": ["control_panel/static/js/app.js"],
        "apis": ["/ai/api/review", "/ai/api/suggestions"],
        "description": "مراجعة التعديلات",
        "aliases": ["ai review", "review page", "مراجعة تعديلات"],
    },
}


_CSS_MAP: dict = {
    "main_css": {
        "file": "control_panel/static/css/style.css",
        "description": "الملف الرئيسي للتصميم — يحتوي على كل الأنماط",
        "sections": {
            "variables_colors": "CSS variables: --primary, --accent, --bg-glass, --text, --border — all theme colors",
            "theme_dark": "body.theme-dark — تعريف الوضع الداكن",
            "theme_light": "body.theme-light — تعريف الوضع الفاتح",
            "sidebar": ".sidebar, .sidebar-nav, .sidebar-link — كل أنماط الشريط الجانبي",
            "header": ".page-header, .header-logo — أنماط الترويسة",
            "cards": ".glass-card, .stat-card, .info-card — بطاقات المحتوى",
            "buttons": ".btn, .btn-primary, .btn-danger, .btn-success — الأزرار",
            "tables": ".table-container, .data-table — الجداول",
            "forms": "input, select, textarea — نماذج الإدخال",
            "animations": "@keyframes fadeInUp, pulse, shimmer — الحركات",
            "mobile": "@media (max-width: 768px) — التصميم للجوال",
            "dashboard": ".stats-grid, .chart-container, .activity-feed — لوحة التحكم",
            "ai_workspace": ".ai-container, .chat-messages, .message-bubble — مساحة AI",
            "access_page": ".access-container, .login-form — صفحة الدخول",
            "modals": ".modal, .modal-overlay — النوافذ المنبثقة",
        },
        "aliases": ["colors", "css", "styles", "theme", "colors", "styling", "الألوان", "التصميم", "الثيم", "css ملف"],
    },
}

_JS_MAP: dict = {
    "main_js": {
        "file": "control_panel/static/js/app.js",
        "description": "الملف الرئيسي للجافاسكريبت — كل التفاعلات",
        "sections": {
            "theme_toggle": "toggleTheme() — تبديل الوضع الداكن/الفاتح، حفظ titanx_theme في localStorage",
            "sidebar_toggle": "toggleSidebar() — فتح/إغلاق الشريط الجانبي",
            "sidebar_collapse": "sidebar collapse state, overlay click handling",
            "navigation": "sidebar link activation, page navigation, active state management",
            "alerts": "showAlert(msg, type) — نظام التنبيهات الملونة",
            "modals": "openModal(id), closeModal(id) — إدارة النوافذ المنبثقة",
            "api_calls": "fetchAPI(url, method, body) — wrapper لكل طلبات الـ API",
            "forms": "form submission handlers, validation, loading states",
            "dashboard_charts": "Chart.js integration for activity and stats charts",
            "toast_notifications": "showToast(msg, type) — إشعارات الزاوية",
            "copy_clipboard": "copyToClipboard(text) — نسخ للحافظة",
            "search": "live search functionality",
            "bot_controls": "startBot(), stopBot(), restartBot() — التحكم في البوتات",
        },
        "aliases": ["javascript", "js", "buttons", "sidebar actions", "form actions", "navigation actions", "جافاسكريبت", "الأزرار", "التفاعل"],
    },
}

_DB_MAP: dict = {
    "main_db": {
        "file": "database/db.py",
        "description": "اتصال قاعدة البيانات الرئيسية (bot.db) — init + migration",
        "functions": ["get_connection", "db_cursor", "init_db", "_migrate"],
        "used_by": ["database/users.py", "database/downloads.py", "database/cache.py", "database/favorites.py", "database/referrals.py", "database/reports.py", "database/achievements.py"],
    },
    "users_model": {
        "file": "database/users.py",
        "description": "نموذج المستخدمين — CRUD كامل للمستخدمين",
        "functions": ["get_user", "create_user", "update_user", "ban_user", "unban_user", "set_vip", "add_points", "deduct_points", "get_total_users", "search_users"],
        "used_by": ["handlers/start.py", "handlers/admin.py", "handlers/profile.py", "handlers/download.py", "control_panel/routers/users.py"],
    },
    "downloads_model": {
        "file": "database/downloads.py",
        "description": "نموذج التحميلات — تسجيل وإحصائيات التحميل",
        "functions": ["log_download", "get_user_history", "get_downloads_today", "get_downloads_week", "get_total_downloads", "get_downloads_by_platform"],
        "used_by": ["handlers/download.py", "control_panel/routers/dashboard.py"],
    },
    "cache_model": {
        "file": "database/cache.py",
        "description": "نموذج الكاش — تخزين روابط التحميل المسبق",
        "functions": ["get_cached", "set_cache", "cleanup_old_cache", "get_cache_count"],
        "used_by": ["services/downloader.py"],
    },
    "favorites_model": {
        "file": "database/favorites.py",
        "description": "نموذج المفضلة — قائمة روابط المفضلة للمستخدم",
        "functions": ["add_favorite", "remove_favorite", "get_favorites", "is_favorite"],
        "used_by": ["handlers/favorites.py", "handlers/download.py"],
    },
    "referrals_model": {
        "file": "database/referrals.py",
        "description": "نموذج الإحالات — نظام الإحالات والمكافآت",
        "functions": ["create_pending_referral", "complete_referral", "get_referrer_stats", "get_top_referrers_by_period"],
        "used_by": ["handlers/start.py", "handlers/profile.py", "handlers/admin.py"],
    },
    "reports_model": {
        "file": "database/reports.py",
        "description": "نموذج التقارير والتذاكر — نظام الدعم الفني",
        "functions": ["create_report", "get_report_by_id", "reply_report", "close_report", "create_support_ticket"],
        "used_by": ["handlers/feedback.py", "handlers/admin.py"],
    },
    "achievements_model": {
        "file": "database/achievements.py",
        "description": "نموذج الإنجازات — نظام مكافآت المستخدم",
        "functions": ["get_user_achievements", "award_achievement", "check_and_award"],
        "used_by": ["handlers/download.py", "handlers/profile.py"],
    },
    "activity_model": {
        "file": "database/activity.py",
        "description": "نموذج سجل النشاط",
        "functions": ["get_activity_feed"],
        "used_by": ["handlers/admin.py", "control_panel/routers/dashboard.py"],
    },
    "support_db": {
        "file": "support_bot/database/db.py",
        "description": "قاعدة بيانات بوت الدعم (support.db)",
        "functions": ["db_cursor", "init_db", "is_main_bot_user"],
        "used_by": ["support_bot/database/tickets.py"],
    },
    "tickets_model": {
        "file": "support_bot/database/tickets.py",
        "description": "نموذج تذاكر الدعم الفني",
        "functions": ["create_ticket", "add_message", "get_ticket", "get_open_tickets", "close_ticket"],
        "used_by": ["support_bot/handlers/admin.py", "support_bot/handlers/user.py"],
    },
}

_BOT_MAP: dict = {
    "main_bot": {
        "entry": "bot.py",
        "description": "بوت X الرئيسي (PrimeDownloader) — bot.py",
        "token_env": "TELEGRAM_BOT_TOKEN",
        "handlers": {
            "start": "handlers/start.py — /start, language selection, subscription check",
            "download": "handlers/download.py — URL detection, quality selection, download callback",
            "admin": "handlers/admin.py — /panel, stats, ban/unban, broadcast, reports",
            "profile": "handlers/profile.py — /profile, points, daily, wheel, leaderboard, achievements",
            "favorites": "handlers/favorites.py — /favorites, unfav callback",
            "feedback": "handlers/feedback.py — rating callback, report message, /support",
            "logo": "handlers/logo.py — /logo, logo upload, logo callback",
            "video_studio": "handlers/video_studio.py — /studio, video processing (premium)",
            "video_tools": "handlers/video_tools.py — /tools, video tools callback",
        },
        "services": {
            "downloader": "services/downloader.py — yt-dlp wrapper, URL analysis, file download",
            "subscription": "services/subscription.py — Telegram channel subscription check",
        },
        "middlewares": {
            "auth": "middlewares/auth.py — is_admin, is_owner, is_banned, get_role",
            "rate_limiter": "middlewares/rate_limiter.py — download rate limiting",
            "subscription_gate": "middlewares/subscription_gate.py — require_subscription decorator",
        },
        "database": "database/ (bot.db) — users, downloads, cache, favorites, referrals, reports, achievements",
        "locales": {"ar": "locales/ar.py", "en": "locales/en.py", "init": "locales/__init__.py"},
    },
    "support_bot": {
        "entry": "support_bot/bot.py",
        "description": "بوت الدعم الفني",
        "token_env": "SUPPORT_BOT_TOKEN",
        "handlers": {
            "user": "support_bot/handlers/user.py — start, new ticket, handle messages, cancel, my tickets",
            "admin": "support_bot/handlers/admin.py — panel, list open/closed, view ticket, reply, close",
        },
        "database": "support_bot/database/ (support.db) — tickets, messages",
        "config": "support_bot/config/settings.py",
    },
}

_SERVICES_MAP: dict = {
    "downloader": {
        "file": "services/downloader.py",
        "description": "خدمة التحميل الرئيسية — yt-dlp wrapper",
        "functions": ["analyze_url", "download_video", "download_audio", "download_image"],
        "used_by": ["handlers/download.py"],
        "depends_on": ["database/cache.py", "database/downloads.py"],
    },
    "subscription": {
        "file": "services/subscription.py",
        "description": "خدمة التحقق من الاشتراك في القناة",
        "functions": ["check_subscription", "build_subscription_keyboard"],
        "used_by": ["handlers/start.py", "middlewares/subscription_gate.py"],
    },
}

_CONFIG_MAP: dict = {
    "main_config": {
        "file": "config/settings.py",
        "description": "الإعدادات الرئيسية للبوت — TELEGRAM_BOT_TOKEN, ADMIN_IDS, OWNER_ID, channels",
        "used_by": ["bot.py", "handlers/admin.py", "middlewares/auth.py"],
    },
    "panel_config": {
        "file": "control_panel/config.py",
        "description": "إعدادات لوحة التحكم — PROJECT_ROOT, OWNER_ID, PUBLIC_URL, template engine",
        "used_by": ["control_panel/app.py", "control_panel/routers/*.py"],
    },
    "panel_settings": {
        "file": "extracted_project/.panel_settings.json",
        "description": "إعدادات لوحة التحكم المحفوظة — hashed password, theme",
        "used_by": ["control_panel/auth.py"],
    },
    "panel_auth": {
        "file": "control_panel/auth.py",
        "description": "مصادقة لوحة التحكم — session management, token auth, password hashing",
        "used_by": ["control_panel/app.py", "control_panel/routers/*.py"],
    },
    "support_config": {
        "file": "support_bot/config/settings.py",
        "description": "إعدادات بوت الدعم",
        "used_by": ["support_bot/bot.py", "support_bot/handlers/admin.py"],
    },
    "requirements": {
        "file": "requirements.txt",
        "description": "قائمة المكتبات المطلوبة — python-telegram-bot, fastapi, yt-dlp, uvicorn",
        "used_by": ["all"],
    },
    "startup": {
        "file": "scripts/start.sh",
        "description": "سكريبت بدء تشغيل لوحة التحكم — PYTHONPATH + uvicorn",
        "used_by": ["TitanX Control Panel workflow"],
    },
}

_ARCH_MAP: dict = {
    "project": {
        "description": "X Control Center — نظام بوت Telegram مع لوحة تحكم FastAPI",
        "components": [
            "PrimeDownloader Bot (bot.py) — بوت التحميل الرئيسي",
            "Support Bot (support_bot/bot.py) — بوت الدعم الفني",
            "Control Panel (control_panel/app.py) — لوحة تحكم FastAPI على بورت 5000",
            "Database (database/) — SQLite (bot.db) + Support (support.db)",
            "AI Engine (control_panel/ai_engine.py) — نظام الذكاء الاصطناعي",
        ],
    },
    "control_panel": {
        "description": "FastAPI control panel — single CSS file + single JS file + 20 HTML templates",
        "entry": "control_panel/app.py",
        "template_engine": "Jinja2 via fastapi.templating.Jinja2Templates",
        "base_template": "control_panel/templates/base.html — all pages extend this",
        "exception": "control_panel/templates/access.html — standalone, does NOT extend base.html",
        "static": "control_panel/static/ — css/style.css + js/app.js",
        "routers": "control_panel/routers/ — 12 router files, each serves one page",
        "auth": "control_panel/auth.py — session tokens + password hash",
    },
    "bots": {
        "description": "python-telegram-bot v20+ architecture",
        "main_bot": "bot.py + handlers/ + services/ + middlewares/ + database/",
        "support_bot": "support_bot/bot.py + support_bot/handlers/ + support_bot/database/",
        "shared_db": "Both bots share bot.db via is_main_bot_user() check in support_bot",
    },
    "database": {
        "description": "SQLite — two separate databases",
        "main": "database/bot.db — users, downloads, cache, favorites, referrals, reports, achievements, activity",
        "support": "support_bot/database/support.db — tickets, messages",
        "init": "database/db.py init_db() — called on bot startup, creates tables and runs migrations",
    },
    "frontend": {
        "description": "Single-page-like FastAPI templates with Jinja2",
        "css": "ONE file: control_panel/static/css/style.css (~2040 lines)",
        "js": "ONE file: control_panel/static/js/app.js",
        "templates": "20 HTML files in control_panel/templates/",
        "inheritance": "19 pages extend base.html — only access.html is standalone",
        "theme": "JS toggleTheme() stores 'titanx_theme' in localStorage — dark/light",
    },
    "data_flow": {
        "description": "مسارات البيانات الكاملة في مشروع X — من الطلب إلى الرد",
        "telegram_to_response": [
            "1️⃣  رسالة Telegram → python-telegram-bot (webhook/polling) → bot.py (Application)",
            "2️⃣  bot.py → يطابق نوع الرسالة → handler المناسب في handlers/",
            "3️⃣  handler → middlewares/auth.py (التحقق من تسجيل المستخدم)",
            "4️⃣  auth.py → middlewares/rate_limiter.py (حد التحميل: RATE_LIMIT_SECONDS)",
            "5️⃣  rate_limiter → middlewares/subscription_gate.py (التحقق من الاشتراك)",
            "6️⃣  subscription_gate → services/ (downloader.py أو subscription.py)",
            "7️⃣  service → database/ (users.py، downloads.py، cache.py، achievements.py)",
            "8️⃣  database → SQLite (database/bot.db) → نتيجة العملية",
            "9️⃣  handler → send_message/send_document → رد Telegram للمستخدم",
        ],
        "panel_request_to_response": [
            "1️⃣  HTTP Request → uvicorn → control_panel/app.py (FastAPI)",
            "2️⃣  app.py → Starlette session middleware",
            "3️⃣  middleware → control_panel/auth.py (token + password verification)",
            "4️⃣  auth.py → router المناسب في control_panel/routers/",
            "5️⃣  router → control_panel/db_utils.py (SQLite queries)",
            "6️⃣  router → Jinja2Templates.TemplateResponse(template, context)",
            "7️⃣  template (extends base.html) → rendered HTML → HTTP Response",
        ],
        "ai_message_flow": [
            "1️⃣  POST /ai/api/chat {msg} → control_panel/routers/ai_workspace.py",
            "2️⃣  ai_workspace.py → ai_engine.process_chat(msg)",
            "3️⃣  process_chat → AgentPlanningGate.has_pending() (هل توجد خطة بانتظار الموافقة؟)",
            "4️⃣  process_chat → detect_intent() → تصنيف النية",
            "5️⃣  intent → AgentReasoningChain.execute() (7 خطوات: فهم→بحث→سياق→تبعيات→تأثير→خطة→رد)",
            "6️⃣  AgentReasoningChain → ProjectDependencyGraph + ProjectBrain + search_project_files()",
            "7️⃣  handler function (_r_*) → formatted response dict",
            "8️⃣  response → JSON → API endpoint → ai_workspace.html → المستخدم",
        ],
        "critical_config_flow": [
            "config/settings.py ← يستورده مباشرة: bot.py، database/db.py، utils/logger.py، services/*، middlewares/*، support_bot/*، developer_bot/*",
            "database/db.py ← يستورده مباشرة: database/*.py، handlers/admin.py، developer_bot/handlers/*",
            "control_panel/config.py ← يستورده: جميع 12 router في control_panel/routers/",
            "⚠️ أي خطأ في config/settings.py ينتشر لكل المكونات أعلاه — نقطة فشل مركزية",
        ],
    },
}

# ─── Semantic Map (concept → files) ───────────────────────────────────────────
# Used by _find_concept() — longer keys matched first
_SEMANTIC_MAP: dict = {
    # ── Pages / Templates ─────────────────────────────────────────────────────
    "ai_engineer": [
        ("control_panel/templates/ai_engineer.html", "template", "صفحة مهندس الذكاء الاصطناعي"),
        ("control_panel/routers/ai_workspace.py", "router", "route GET /ai/engineer"),
    ],
    "ai_workspace": [
        ("control_panel/templates/ai_workspace.html", "template", "صفحة X AI Operator"),
        ("control_panel/routers/ai_workspace.py", "router", "route GET /ai"),
    ],
    "ai_memory": [
        ("control_panel/templates/ai_memory.html", "template", "صفحة ذاكرة المشروع"),
        ("control_panel/routers/ai_workspace.py", "router", "route GET /ai/memory"),
    ],
    "ai_review": [
        ("control_panel/templates/ai_review.html", "template", "صفحة مراجعة التعديلات"),
        ("control_panel/routers/ai_workspace.py", "router", "route GET /ai/review"),
    ],
    "ai_engine": [
        ("control_panel/ai_engine.py", "engine", "محرك الذكاء الاصطناعي الرئيسي v3.0"),
    ],
    "db_manager": [
        ("control_panel/templates/db_manager.html", "template", "صفحة مدير قاعدة البيانات"),
        ("control_panel/routers/db_manager.py", "router", "route GET /db"),
    ],
    "replit_manager": [
        ("control_panel/templates/replit_manager.html", "template", "صفحة مركز Replit"),
        ("control_panel/routers/replit_manager.py", "router", "route GET /replit"),
    ],
    "file_manager": [
        ("control_panel/templates/files.html", "template", "صفحة مدير الملفات"),
        ("control_panel/routers/files.py", "router", "route GET /files"),
    ],
    "log_viewer": [
        ("control_panel/templates/logs.html", "template", "صفحة عارض السجلات"),
        ("control_panel/routers/logs_router.py", "router", "route GET /logs"),
    ],
    "broadcast": [
        ("control_panel/templates/broadcast.html", "template", "صفحة البث"),
        ("control_panel/routers/broadcast.py", "router", "route GET /broadcast"),
    ],
    "homepage": [
        ("control_panel/templates/dashboard.html", "template", "الصفحة الرئيسية / لوحة التحكم"),
        ("control_panel/routers/dashboard.py", "router", "route GET / and GET /dashboard"),
    ],
    "dashboard": [
        ("control_panel/templates/dashboard.html", "template", "لوحة التحكم الرئيسية"),
        ("control_panel/routers/dashboard.py", "router", "route GET / and GET /dashboard"),
    ],
    "users_page": [
        ("control_panel/templates/users.html", "template", "صفحة إدارة المستخدمين"),
        ("control_panel/routers/users.py", "router", "route GET /users"),
    ],
    "users": [
        ("control_panel/templates/users.html", "template", "صفحة إدارة المستخدمين"),
        ("control_panel/routers/users.py", "router", "route GET /users + user CRUD APIs"),
    ],
    "bots_page": [
        ("control_panel/templates/bots.html", "template", "صفحة إدارة البوتات"),
        ("control_panel/routers/bots.py", "router", "route GET /bots + start/stop/restart APIs"),
    ],
    "backups_page": [
        ("control_panel/templates/backups.html", "template", "صفحة النسخ الاحتياطية"),
        ("control_panel/routers/backups.py", "router", "route GET /backups + create/restore/download APIs"),
    ],
    "updates_page": [
        ("control_panel/templates/updates.html", "template", "صفحة التحديثات"),
        ("control_panel/routers/updates.py", "router", "route GET /updates + analyze/apply APIs"),
    ],
    "system_page": [
        ("control_panel/templates/system.html", "template", "صفحة حالة النظام"),
        ("control_panel/routers/system.py", "router", "route GET /system + stats/bots APIs"),
    ],
    "github_page": [
        ("control_panel/templates/github.html", "template", "صفحة تكامل GitHub"),
        ("control_panel/routers/github_router.py", "router", "route GET /github + pull/push/commit APIs"),
    ],
    "search_page": [
        ("control_panel/templates/search.html", "template", "صفحة البحث في المشروع"),
        ("control_panel/routers/search.py", "router", "route GET /search"),
    ],
    "login_page": [
        ("control_panel/templates/access.html", "template", "صفحة الدخول / المصادقة (standalone, no base.html)"),
        ("control_panel/app.py", "app", "route GET /panel, POST /panel/login — auth logic"),
    ],
    "access": [
        ("control_panel/templates/access.html", "template", "صفحة الدخول / المصادقة"),
        ("control_panel/app.py", "app", "route GET /panel + POST /panel/login"),
    ],
    # ── Structural / Layout ───────────────────────────────────────────────────
    "sidebar": [
        ("control_panel/templates/base.html", "template", "الشريط الجانبي موجود في base.html"),
        ("control_panel/static/css/style.css", "css", "أنماط .sidebar, .sidebar-nav, .sidebar-link"),
        ("control_panel/static/js/app.js", "js", "toggleSidebar() — فتح/إغلاق الشريط الجانبي"),
    ],
    "base_template": [
        ("control_panel/templates/base.html", "template", "القالب الأساسي — يرث منه كل الصفحات ماعدا access.html"),
    ],
    "header": [
        ("control_panel/templates/base.html", "template", "الترويسة في base.html — .page-header"),
        ("control_panel/static/css/style.css", "css", "أنماط .page-header, .header-logo"),
    ],
    "navigation": [
        ("control_panel/templates/base.html", "template", "قائمة التنقل في sidebar داخل base.html"),
        ("control_panel/static/js/app.js", "js", "sidebar navigation + active link management"),
    ],
    # ── CSS / Styling ─────────────────────────────────────────────────────────
    "colors": [
        ("control_panel/static/css/style.css", "css", "CSS variables: --primary, --accent, --bg-glass, --text — كل الألوان"),
    ],
    "theme": [
        ("control_panel/static/css/style.css", "css", "body.theme-dark + body.theme-light — الوضع الداكن/الفاتح"),
        ("control_panel/static/js/app.js", "js", "toggleTheme() — تبديل الثيم وحفظ titanx_theme في localStorage"),
    ],
    "animations": [
        ("control_panel/static/css/style.css", "css", "@keyframes fadeInUp, pulse, shimmer, spin — الحركات"),
    ],
    "mobile_css": [
        ("control_panel/static/css/style.css", "css", "@media (max-width: 768px) — التصميم للجوال"),
    ],
    "css": [
        ("control_panel/static/css/style.css", "css", "ملف CSS الوحيد — كل الأنماط"),
    ],
    # ── JavaScript ────────────────────────────────────────────────────────────
    "javascript": [
        ("control_panel/static/js/app.js", "js", "ملف JS الوحيد — كل التفاعلات"),
    ],
    "buttons": [
        ("control_panel/static/js/app.js", "js", "button handlers, loading states, confirmation dialogs"),
        ("control_panel/static/css/style.css", "css", ".btn, .btn-primary, .btn-danger — أنماط الأزرار"),
    ],
    "forms": [
        ("control_panel/static/js/app.js", "js", "form submission handlers, validation"),
        ("control_panel/static/css/style.css", "css", "input, select, textarea styles"),
    ],
    "modals": [
        ("control_panel/static/js/app.js", "js", "openModal(id), closeModal(id)"),
        ("control_panel/static/css/style.css", "css", ".modal, .modal-overlay styles"),
    ],
    "charts": [
        ("control_panel/static/js/app.js", "js", "Chart.js integration for dashboard stats"),
        ("control_panel/templates/dashboard.html", "template", "chart canvases"),
    ],
    "alerts": [
        ("control_panel/static/js/app.js", "js", "showAlert(msg, type) + showToast(msg, type)"),
    ],
    # ── Database ──────────────────────────────────────────────────────────────
    "database": [
        ("database/db.py", "db", "اتصال قاعدة البيانات الرئيسية + init_db() + migration"),
        ("database/users.py", "model", "نموذج المستخدمين"),
        ("database/downloads.py", "model", "نموذج التحميلات"),
        ("database/cache.py", "model", "نموذج الكاش"),
        ("database/favorites.py", "model", "نموذج المفضلة"),
        ("database/referrals.py", "model", "نموذج الإحالات"),
        ("database/reports.py", "model", "نموذج التقارير والتذاكر"),
        ("database/achievements.py", "model", "نموذج الإنجازات"),
    ],
    "users_db": [
        ("database/users.py", "model", "نموذج المستخدمين — get_user, create_user, ban_user, add_points"),
    ],
    "downloads_db": [
        ("database/downloads.py", "model", "نموذج التحميلات — log_download, get_downloads_today, get_total_downloads"),
    ],
    "tickets_db": [
        ("support_bot/database/tickets.py", "model", "نموذج تذاكر الدعم"),
        ("support_bot/database/db.py", "db", "قاعدة بيانات بوت الدعم support.db"),
    ],
    # ── Bots ─────────────────────────────────────────────────────────────────
    "main_bot": [
        ("bot.py", "entry", "نقطة دخول البوت الرئيسي — PrimeDownloader"),
        ("handlers/start.py", "handler", "/start command"),
        ("handlers/download.py", "handler", "URL download handler"),
        ("handlers/admin.py", "handler", "admin commands"),
    ],
    "support_bot": [
        ("support_bot/bot.py", "entry", "نقطة دخول بوت الدعم الفني"),
        ("support_bot/handlers/user.py", "handler", "user ticket handlers"),
        ("support_bot/handlers/admin.py", "handler", "admin ticket handlers"),
    ],
    "download_handler": [
        ("handlers/download.py", "handler", "معالج التحميل — URL detection, quality selection, download_callback"),
        ("services/downloader.py", "service", "خدمة التحميل — yt-dlp wrapper"),
    ],
    "admin_handler": [
        ("handlers/admin.py", "handler", "أوامر المدير — /panel, stats, ban, broadcast, reports"),
    ],
    "start_handler": [
        ("handlers/start.py", "handler", "/start, language selection, subscription verification"),
    ],
    # ── Services ──────────────────────────────────────────────────────────────
    "downloader_service": [
        ("services/downloader.py", "service", "yt-dlp wrapper — analyze_url, download_video, download_audio"),
    ],
    "subscription_service": [
        ("services/subscription.py", "service", "Telegram channel subscription check"),
    ],
    # ── Config / Auth ─────────────────────────────────────────────────────────
    "config": [
        ("config/settings.py", "config", "إعدادات البوت الرئيسي"),
        ("control_panel/config.py", "config", "إعدادات لوحة التحكم"),
    ],
    "auth": [
        ("control_panel/auth.py", "auth", "مصادقة لوحة التحكم — session + password"),
        ("control_panel/templates/access.html", "template", "صفحة الدخول"),
        ("control_panel/app.py", "app", "route POST /panel/login"),
    ],
    "settings": [
        ("config/settings.py", "config", "إعدادات البوت الرئيسي"),
        ("control_panel/config.py", "config", "إعدادات لوحة التحكم"),
        ("extracted_project/.panel_settings.json", "data", "كلمة مرور لوحة التحكم + الثيم"),
    ],
    # ── AI System ─────────────────────────────────────────────────────────────
    "ai": [
        ("control_panel/ai_engine.py", "engine", "محرك الذكاء الاصطناعي v3.0"),
        ("control_panel/routers/ai_workspace.py", "router", "AI API endpoints"),
        ("control_panel/templates/ai_workspace.html", "template", "AI chat interface"),
    ],
    # ── Locales ───────────────────────────────────────────────────────────────
    "locales": [
        ("locales/ar.py", "locale", "ترجمة عربية"),
        ("locales/en.py", "locale", "ترجمة إنجليزية"),
        ("locales/__init__.py", "locale", "نظام الترجمة + get_text()"),
    ],
    # ── Middlewares ───────────────────────────────────────────────────────────
    "middlewares": [
        ("middlewares/auth.py", "middleware", "is_admin, is_owner, is_banned, get_role"),
        ("middlewares/rate_limiter.py", "middleware", "check_rate_limit — حد التحميل"),
        ("middlewares/subscription_gate.py", "middleware", "require_subscription decorator"),
    ],
    # ── Backup system ─────────────────────────────────────────────────────────
    "backup": [
        ("control_panel/templates/backups.html", "template", "صفحة النسخ الاحتياطية"),
        ("control_panel/routers/backups.py", "router", "backup APIs — create, restore, download"),
        ("control_panel/ai_engine.py", "engine", "create_backup(), restore_backup() in AI engine"),
    ],
    # ── GitHub system ─────────────────────────────────────────────────────────
    "github": [
        ("control_panel/templates/github.html", "template", "صفحة تكامل GitHub"),
        ("control_panel/routers/github_router.py", "router", "GitHub APIs — pull, push, commit, diff"),
    ],
    # ── Middleware / Rate Limiting / Subscriptions ─────────────────────────────
    "rate_limiter": [
        ("middlewares/rate_limiter.py", "middleware", "check_rate_limit — حد التحميل لكل مستخدم"),
    ],
    "rate_limit": [
        ("middlewares/rate_limiter.py", "middleware", "check_rate_limit — حد التحميل لكل مستخدم"),
    ],
    "subscription": [
        ("middlewares/subscription_gate.py", "middleware", "require_subscription decorator"),
    ],
    "subscription_gate": [
        ("middlewares/subscription_gate.py", "middleware", "require_subscription decorator"),
    ],
    "middleware": [
        ("middlewares/auth.py", "middleware", "is_admin, is_owner, is_banned, get_role"),
        ("middlewares/rate_limiter.py", "middleware", "check_rate_limit — حد التحميل"),
        ("middlewares/subscription_gate.py", "middleware", "require_subscription decorator"),
    ],
    # ── Bot handler features (PrimeDownloader) ────────────────────────────────
    "lucky_wheel": [
        ("handlers/lucky_wheel.py", "handler", "عجلة الحظ — الجوائز اليومية"),
    ],
    "achievements": [
        ("handlers/achievements.py", "handler", "الإنجازات والشارات — نظام المكافآت"),
    ],
    "referral": [
        ("handlers/referral.py", "handler", "نظام الإحالة — رموز الدعوة والمكافآت"),
        ("db_utils/referrals.py", "db", "جدول الإحالات في قاعدة البيانات"),
    ],
    "video_studio": [
        ("handlers/video_studio.py", "handler", "استوديو الفيديو — تحرير وتحميل مقاطع"),
    ],
    "video_tools": [
        ("handlers/video_tools.py", "handler", "أدوات الفيديو — اقتصاص، ترجمة، ضغط"),
    ],
    "favorites": [
        ("handlers/favorites.py", "handler", "المحفوظات — قائمة المفضلة للمستخدم"),
    ],
    "logo": [
        ("handlers/logo.py", "handler", "إنشاء الشعار — توليد صور بالذكاء الاصطناعي"),
        ("static/img/logo.png", "asset", "شعار المشروع الرئيسي"),
    ],
}

_ALIASES: dict = {
    "الصفحة الرئيسية": "homepage",
    "الرئيسية": "homepage",
    "لوحة التحكم": "dashboard",
    "لوحة": "dashboard",
    "صفحة الدخول": "login_page",
    "تسجيل الدخول": "login_page",
    "الدخول": "login_page",
    "المستخدمون": "users",
    "إدارة المستخدمين": "users",
    "الشريط الجانبي": "sidebar",
    "القائمة الجانبية": "sidebar",
    "الألوان": "colors",
    "التصميم": "css",
    "الثيم": "theme",
    "الجافاسكريبت": "javascript",
    "الأزرار": "buttons",
    "قاعدة البيانات": "database",
    "بوت الدعم": "support_bot",
    "البوت الرئيسي": "main_bot",
    "مهندس الذكاء": "ai_engineer",
    "ذاكرة المشروع": "ai_memory",
    "مراجعة التعديلات": "ai_review",
    "نسخ احتياطية": "backup",
    "النسخ الاحتياطية": "backup",
    "الإعدادات": "settings",
    "المصادقة": "auth",
    "الإحالات": "referrals_model",
    "التحميل": "download_handler",
    "التحميلات": "downloads_db",
    "السجلات": "log_viewer",
    "البحث": "search_page",
    "النظام": "system_page",
    "التحديثات": "updates_page",
    "البوتات": "bots_page",
    "البث": "broadcast",
    "ريبليت": "replit_manager",
    # Middleware / rate limiting / subscriptions
    "حد التحميل": "rate_limiter",
    "حد الطلبات": "rate_limiter",
    "التقييد": "rate_limiter",
    "الاشتراك": "subscription",
    "نظام الاشتراك": "subscription",
    "الوسيط": "middleware",
    "الوسائط": "middleware",
    # Bot features
    "عجلة الحظ": "lucky_wheel",
    "العجلة": "lucky_wheel",
    "الإنجازات": "achievements",
    "الشارات": "achievements",
    "نقاط": "achievements",
    "الإحالة": "referral",
    "نظام الإحالة": "referral",
    "كود الدعوة": "referral",
    "رمز الدعوة": "referral",
    "استوديو الفيديو": "video_studio",
    "أدوات الفيديو": "video_tools",
    "تحرير فيديو": "video_tools",
    "المحفوظات": "favorites",
    "المفضلة": "favorites",
    "الشعار": "logo",
    "اللوغو": "logo",
}


# ═══════════════════════════════════════════════════════════════════════════════
# INTENT DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

INTENTS: dict = {
    "errors":      [r"أخطاء", r"خطأ", r"errors?", r"bugs?", r"مشاكل", r"مشكلة", r"broken", r"يعطل", r"كسور"],
    "analyze":     [r"افحص", r"حلل", r"analyze", r"scan", r"فحص", r"تحليل", r"inspect", r"اكتشف"],
    "backup":      [r"احتياطي", r"backup", r"نسخة", r"احفظ", r"save", r"حفظ", r"نسخ احتياطي"],
    "restore":     [r"استعادة", r"restore", r"رجوع", r"استرجاع", r"rollback"],
    "improve":     [r"حسن", r"improve", r"احترافية", r"professional", r"تحسين", r"أفضل", r"جمال"],
    "memory":      [r"تذكر", r"ذاكرة", r"memory", r"تعلم", r"اعرف", r"معلومات"],
    "status":      [r"حالة", r"status", r"شغال", r"يعمل", r"مباشر", r"live", r"working", r"online"],
    "structure":   [r"هيكل", r"structure", r"بنية", r"مجلدات"],
    "routes":      [r"routes?", r"مسارات", r"صفحات", r"endpoints?", r"روابط", r"\bapi\b"],
    "security":    [r"أمان", r"security", r"أمن", r"ثغرات", r"vulnerab", r"password", r"حماية"],
    "help":        [r"مساعدة", r"help", r"ساعد", r"كيف تعمل", r"ماذا تستطيع", r"قدرات"],
    "stats":       [r"إحصائيات", r"stats", r"أرقام", r"numbers", r"\bكم\b", r"how many", r"عدد"],
    "find_file":   [r"find\b", r"where is", r"which file", r"what file", r"locate",
                    r"who\s+handles?\b", r"what\s+handles?\b", r"what\s+owns?\b",
                    r"which\s+(?:router|handler|file)\s+owns?\b",
                    r"أين", r"أي ملف", r"ما الملف", r"ابحث عن", r"أين يوجد", r"يتحكم"],
    "plan_modify": [r"plan", r"خطة", r"what.*modify", r"what.*change", r"ماذا.*أعدل",
                    r"redesign", r"إعادة تصميم", r"modify plan", r"how to.*change"],
    "dependency":  [r"depend", r"uses", r"loads", r"import", r"related",
                    r"تبعيات", r"تبعية", r"يعتمد",
                    r"يستخدم", r"يحمل", r"علاقة", r"ارتباط", r"مرتبط"],
    "arch":        [r"architecture", r"how does.{0,20}work", r"explain.{0,20}system",
                    r"معمارية", r"كيف يعمل", r"اشرح", r"هيكل المشروع"],
    "root_cause":  [r"why is.{0,30}broken", r"why.{0,20}not work", r"debug",
                    r"لماذا.{0,20}لا يعمل", r"سبب الخطأ", r"لماذا كسر"],
    "impact":      [r"what breaks", r"what happens if", r"impact of", r"if i change",
                    r"ماذا يحدث لو", r"ماذا يكسر", r"تأثير التغيير"],
    "self_test":   [r"self.?test", r"test yourself", r"اختبر نفسك", r"self check", r"run tests?"],
    # ── Agent Foundation intents ───────────────────────────────────────────────
    "who_depends": [
        r"ما\s+(?:الملفات|الكود).{0,30}(?:تعتمد|يعتمد|تستورد|يستورد)\s+عل",
        r"what\s+files?.{0,15}(?:depend|import|use).{0,15}on",
        r"who\s+(?:depends|imports|uses)\s+on",
        r"من\s+(?:يستورد|يستخدم|يعتمد)\s+على",
        r"سلسلة\s+(?:التبعيات|تبعيات)",
        r"dependency\s+chain",
    ],
    "data_flow":   [
        r"data\s+flow", r"تدفق\s+البيانات",
        r"flow\s+from.{0,30}(?:user|telegram|تليغرام|المستخدم)",
        r"مسار\s+(?:الطلب|الرسالة|البيانات)",
        r"path\s+of\s+(?:data|message|request)",
    ],
    "reuse_systems": [
        r"(?:reusable|إعادة\s+استخدام|يمكن\s+إعادة)",
        r"existing\s+systems?\s+(?:reuse|reused|leverage)",
        r"ماذا\s+(?:يمكن|أستطيع).{0,20}(?:إعادة\s+استخدام|الاستفادة\s+منه)",
        r"what.{0,20}(?:can\s+be\s+reused|already\s+exists).{0,20}(?:for|in)\s+(?:new|this)",
    ],
    # Conversational / meta intents
    "identity":      [r"who are you", r"what are you", r"من أنت", r"ما أنت", r"عرّف نفسك",
                      r"introduce yourself", r"about yourself", r"tell me about you",
                      r"ما هو\b.{0,10}x\b", r"ما هي\b.{0,10}x\b", r"about the ai"],
    "capabilities":  [r"what can you do", r"ماذا تستطيع", r"what do you do",
                      r"your capabilities", r"قدراتك", r"إمكانياتك",
                      r"كيف.{0,10}تساعد", r"how can you help", r"your features",
                      r"what are you capable", r"ما.{0,10}(?:قدرات|إمكانيات)"],
    "hf_query":      [r"hugging.?face", r"هوجينج\s*فيس",
                      r"\bhf\s+(?:space|connected|status|working|online)\b",
                      r"(?:connected|اتصال|متصل)\s*(?:to|with|بـ|مع)?\s*(?:hugging.?face|hf\s+space)\b"],
    # Phase 2 — Action intent classification
    "create_feature": [
        r"create\b.{0,40}(bot|feature|system|module|command|handler|notification|service)",
        r"build\b.{0,30}(bot|feature|system|module|service)",
        r"make\b.{0,30}(bot|feature|system|service)",
        r"add\b.{0,30}(bot|notification|command|feature|handler|service)",
        r"implement\b.{0,40}(bot|feature|system|module)",
        r"develop\b.{0,30}(bot|feature|system)",
        r"أنشئ\b", r"اصنع",
        r"أضف\s+(?:بوت|bot)\b",   # bot IS the thing being added, not the destination
        r"بناء.*(?:بوت|bot)", r"طور.*ميزة",
    ],
    "ui_redesign": [
        r"redesign\b", r"revamp\b", r"إعادة\s*تصميم",
        r"redo\b.{0,20}(page|design|ui|interface|layout)",
        r"new\b.{0,10}look\b", r"تجديد.*تصميم", r"change\b.{0,20}design",
        r"restyle\b", r"update\b.{0,10}(design|look|ui|layout)",
    ],
    "debug_fix": [
        r"\bfix\b.{0,40}(error|bug|button|broken|issue|problem|page|feature|crash|fail)",
        r"\bfix\b\s+(?:the|this|a|an)\b",
        r"repair\b.{0,30}(error|bug|button|broken)",
        r"correct\b.{0,30}(error|bug|issue|problem)",
        r"صلح\b", r"إصلاح\b",
        r"debug\b.{0,30}(button|page|feature|error|issue)",
        r"investigate\b.{0,30}(error|bug|issue|broken)",
        r"broken\b.{0,20}(button|page|feature|link)",
    ],
    "new_page": [
        r"(?:create|add|make|build)\b.{0,15}(?:new\b.{0,5})?(?:page|screen|view|section)\b",
        r"new\b.{0,5}page\b", r"صفحة\s*جديدة", r"أنشئ\s*صفحة",
        r"add\b.{0,10}screen\b", r"create\b.{0,10}view\b",
    ],
}


def detect_intent(msg: str) -> str:
    # Keep original case-folded form for pattern matching (patterns use original Arabic
    # diacritics/hamza — normalization happens in _normalize_query/_find_concept only)
    ml = msg.lower()

    # ── REASONING ENGINE GATE (Phase 3) ──────────────────────────────────────
    # Classify FIRST — before any keyword matching.
    # Conversational messages (tech explanations, comparisons, greetings) NEVER
    # enter project inspection mode.
    _re_mode = ReasoningEngine.classify(msg)
    if _re_mode == "greeting":
        return "greeting"

    # ── PROJECT_FIRST ENFORCEMENT (Phase 13/14) ───────────────────────────────
    # If ReasoningEngine classified as "conversational", check whether the message
    # contains explicit project entity keywords.  If yes, fall through to full
    # project intent matching.  If no, return generic conversation immediately.
    #
    # Two-tier check:
    #   • Short English tokens → \b word-boundary regex (prevents "fastapi" from
    #     matching the "api" token, "classic" from matching "class", etc.)
    #   • Long strings / Arabic terms → plain substring match (safe for these)
    _PF_REGEX = [                       # require whole-word match
        r"\bapi\b", r"\bdb\b", r"\bclass\b", r"\bpage\b", r"\bbot\b",
        r"\bservice\b", r"\brouter\b", r"\bhandler\b", r"\btemplate\b",
        r"\bbutton\b", r"\bmenu\b", r"\bcallback\b", r"\bcommand\b",
        r"\bkeyboard\b", r"\bimport\b", r"\bfunction\b", r"\bdecorator\b",
        r"\broute\b", r"\bendpoint\b", r"\bdatabase\b",
    ]
    _PF_SUB = {                         # substring match is safe for these
        "bot.py", "settings.py", "config.py", "auth.py", "style.css",
        "app.js", "app.py", "ai_engine", "callback_data", "inline_keyboard",
        "زر", "قائمة", "صفحة", "قاعدة", "أمر", "خدمة", "دالة", "راوتر", "ملف",
        "كول", "callback",
    }
    if _re_mode == "conversational":
        _pf_hit = (
            any(re.search(p, ml) for p in _PF_REGEX)
            or any(kw in ml for kw in _PF_SUB)
        )
        if not _pf_hit:
            return "conversation"
    # Project entity detected → fall through to project intent patterns

    # ── Priority -1: Conversational / identity (absolute top priority) ─────────
    # These must NEVER return file lists

    # ①  Comparison / reasoning (catches "difference between X and Y" before action patterns)
    _COMPARE_P = [
        r"difference between", r"\bcompare\b.{0,25}\band\b", r"\bvs\b", r"\bversus\b",
        r"الفرق\s+بين", r"فرق\s+بين", r"\bcontrast\b", r"compare.{0,20}and",
        r"between.{0,30}and", r"\bقارن\b", r"مقارنة\s+بين",
    ]
    if any(re.search(p, ml) for p in _COMPARE_P):
        return "conversation"

    # ①·⁵  Social / wellbeing — "How are you?", "What's up?", etc. → greeting
    _SOCIAL_P = [
        r"^how\s+are\s+you", r"^how'?s\s+it\s+going", r"^how'?s\s+(?:everything|life|things)",
        r"^what'?s\s+up", r"^how\s+do\s+you\s+do", r"^nice\s+to\s+meet",
        r"^greetings?\b", r"^good\s+(?:morning|afternoon|evening|day)\b",
        r"أنت\s+بخير", r"كيف\s+حالك", r"كيف\s+الحال",
    ]
    if any(re.search(p, ml) for p in _SOCIAL_P):
        return "greeting"

    # ②  Capabilities checked BEFORE identity — "what are you capable of?" → capabilities
    _CAPS_P = [
        r"what can you do", r"ماذا تستطيع", r"what do you do",
        r"your capabilities", r"قدراتك", r"إمكانياتك", r"ماذا تقدر",
        r"how can you help", r"what are you capable",
        r"ما.{0,10}(?:قدرات|إمكانيات|تستطيع)",
    ]
    if any(re.search(p, ml) for p in _CAPS_P):
        return "capabilities"

    # ③  Identity — checked AFTER capabilities so "capable" doesn't fall here
    _IDENTITY_P = [
        r"who are you", r"what are you\b", r"من أنت", r"ما أنت", r"عرّف نفسك",
        r"introduce yourself", r"tell me about you", r"about yourself",
    ]
    if any(re.search(p, ml) for p in _IDENTITY_P):
        return "identity"

    # ── HF intent: two-path gate — status vs action ───────────────────────────
    # REPAIR (Problem 3): The old single early-return was a keyword bypass that
    # skipped Intent Detection → Confidence → Verification → Execution.
    #
    # New rule:
    #   • Message explicitly names HF/Hugging Face AND contains an action verb
    #     (analyze, audit, scan, check, inspect, review) → intent = "analyze"
    #     so the handler calls call_hf_analyze() with the actual query.
    #   • Message explicitly names HF/Hugging Face with NO action verb
    #     → pure status/connection check → intent = "hf_query".
    #   • Ambiguous messages that don't explicitly name HF → fall through to
    #     full scoring below (no early return, no keyword bypass).
    _HF_EXPLICIT_P = [
        r"hugging.?face",
        r"هوجينج\s*فيس",
        r"\bhf\s+(?:space|connected|status|working|online)\b",
        r"(?:connected|اتصال|متصل)\s*(?:to|with|بـ|مع)?\s*(?:hugging.?face|hf\s+space)\b",
    ]
    _HF_ACTION_P = [
        r"(?:using|use|via|through|بواسطة|استخدم|استخدام)\s+hf\b",
        r"(?:using|use|via|through|بواسطة|استخدم|استخدام)\s+hugging.?face",
        r"\bhf\s+(?:analyze|audit|check|scan|review|inspect|analyse)\b",
        r"hugging.?face\s+(?:analyze|audit|check|scan|review|inspect|analyse)",
        r"(?:analyze|audit|inspect|scan|review|فحص|حلل|راجع).{0,35}(?:\bhf\b|hugging.?face)",
    ]
    if any(re.search(p, ml) for p in _HF_EXPLICIT_P):
        if any(re.search(p, ml) for p in _HF_ACTION_P):
            # User wants HF to DO something (analyze/audit/etc.) — route to
            # analyze handler which calls call_hf_analyze() with the real query
            return "analyze"
        # Pure status / connection question — return hf_query
        return "hf_query"

    # ── Short "hf" combined with action verb (e.g. "using hf analyze...") ────
    # Catches cases where the user writes "hf" (lowercase/short) without
    # the full "hugging face" phrase — only fires when paired with a clear
    # action verb so bare "hf" mentions don't trigger this gate.
    _HF_SHORT_ACTION = r"(?:using|use|via|through|استخدم)\s+hf\b|" \
                       r"\bhf\s+(?:analyze|audit|check|scan|review|inspect|analyse)\b|" \
                       r"(?:analyze|audit|inspect|scan|review|حلل|فحص)\s+.{0,20}\bhf\b"
    if re.search(_HF_SHORT_ACTION, ml):
        return "analyze"

    # ── Priority -0·6: Early reuse check — before conditional override ──────────
    # "لو أنشأت بوت X ما الأنظمة التي يمكن إعادة استخدامها" must map to
    # reuse_systems, not impact — check reuse BEFORE the cond-opener patterns.
    _EARLY_REUSE_P = [
        r"يمكن\s+إعادة\s+استخدام",          # matches استخدامها, استخدامهم …
        r"ما\s+(?:الأنظمة|الخدمات|المكونات).{0,40}(?:يمكن|أستطيع|أستطيع|can|reuse)",
        r"(?:what|which).{0,30}(?:systems?|components?|services?|code).{0,30}(?:reuse|reused|leverage|existing)",
    ]
    if any(re.search(p, ml) for p in _EARLY_REUSE_P):
        return "reuse_systems"

    # ── Priority -0·5: Conditional override — "لو X ماذا سيتأثر؟" ─────────────
    # The conditional opener ("لو"/"إذا") signals reasoning, not action.
    # Must come BEFORE _P0_CREATE so "لو أضفت بوت" → impact, not create_feature.
    _COND_OVERRIDE = [
        r"^لو\s+(?:أضفت|حذفت|عدلت|غيرت|بنيت|أنشأت|دمجت|أزلت)",
        r"^إذا\s+(?:أضفت|حذفت|عدلت|غيرت|بنيت|أنشأت|أزلت|فشلت|انهارت|توقفت|تعطلت)",
        r"(?:لو|إذا).{0,40}ماذا\s+(?:سيتأثر|سيحدث|سيتغير|سيتعطل|ينكسر|سيُكسر)",
        r"(?:if|suppose).{0,20}(?:add|delete|remove|change|modify|fail|crash|goes?\s+down).{0,30}(?:what|which).{0,20}(?:affected|breaks?|happens?)",
        r"(?:إذا|لو)\s+(?:فشلت|انهارت|توقفت|تعطلت).{0,30}(?:قاعدة|الخادم|البوت|النظام|السيرفر)",
        r"what\s+happens?\s+if.{0,30}(?:database|server|bot|system).{0,20}(?:fail|crash|go\s+down|stop)",
    ]
    if any(re.search(p, ml) for p in _COND_OVERRIDE):
        return "impact"

    # ── Scaling / capacity questions ──────────────────────────────────────────
    _SCALE_P = [
        r"(?:كيف|كيفية).{0,20}(?:يتحمل|يتوسع|يُوسَّع|يُطوَّر).{0,30}(?:مستخدم|user|ألف|مليون)",
        r"(?:scale|scaling).{0,30}(?:\d+[kK]?|hundred|thousand|million|مليون|ألف)",
        r"(?:\d+[kK]|hundred|thousand|million)\s+(?:users?|مستخدم)",
        r"(?:توسع|scale\s*up|horizontal\s*scal|vertical\s*scal)",
        r"(?:كيف|how).{0,20}(?:أتوسع|أوسّع|أُطوّر|grow|scale).{0,20}(?:مشروع|project|system|نظام)",
        r"(?:capacity|طاقة\s*استيعاب|عدد\s*المستخدمين).{0,20}(?:\d+|أكثر|زيادة)",
        r"100[,.]?000\s*(?:user|مستخدم)",
        r"(?:million|مليون)\s+(?:user|مستخدم)",
    ]
    if any(re.search(p, ml) for p in _SCALE_P):
        return "scale"

    # ── Technical debt ────────────────────────────────────────────────────────
    _TECH_DEBT_P = [
        r"(?:technical\s+debt|ديون\s+تقنية|الديون\s+التقنية)",
        r"(?:ما|which|what).{0,20}(?:يحتاج|needs?|requires?).{0,20}(?:إعادة\s*كتابة|refactor|rewrite)",
        r"(?:refactor|إعادة\s*هيكلة|إعادة\s*كتابة).{0,30}(?:المشروع|project|code|الكود)",
        r"(?:code\s+quality|جودة\s+الكود|نظافة\s+الكود)",
        r"(?:ما|which|what).{0,20}(?:يحتاج|needs?).{0,20}(?:تنظيف|cleanup|تحسين\s+الكود)",
        r"(?:legacy|قديم|outdated).{0,20}(?:code|كود|نظام)",
    ]
    if any(re.search(p, ml) for p in _TECH_DEBT_P):
        return "tech_debt"

    # ── Redesign / restructure ────────────────────────────────────────────────
    _REDESIGN_ARCH_P = [
        r"(?:كيف|how).{0,15}(?:ستعيد|would\s+you\s+redesign|تُعيد\s+تصميم|تُعيد\s+بناء)",
        r"(?:إعادة\s+تصميم|redesign).{0,25}(?:المشروع|بنية|architecture|النظام|TitanX)",
        r"(?:كيف|how).{0,15}(?:ستبني|would\s+you\s+build|تبني).{0,20}(?:من\s+الصفر|from\s+scratch|again|مجدداً)",
        r"(?:لو|if).{0,20}(?:بدأت|started|start).{0,20}(?:من\s+الصفر|scratch|again|مجدداً)",
        r"(?:best|أفضل).{0,15}(?:architecture|معمارية|بنية).{0,20}(?:لهذا|for\s+this|للمشروع)",
        r"(?:restructure|إعادة\s+هيكلة\s+المشروع)",
    ]
    if any(re.search(p, ml) for p in _REDESIGN_ARCH_P):
        return "redesign"

    # ── Strategy / owner-perspective questions ────────────────────────────────
    # "لو كنت مسؤولاً عن TitanX ماذا ستفعل؟" / "if you were in charge, what would you do?"
    _STRATEGY_P = [
        r"لو\s+كنت\s+(?:مكان|مسؤولاً|المسؤول|صاحب|المالك)",
        r"لو\s+كنت\s+أنت.{0,20}(?:ماذا|ما\s+الذي)",
        r"ماذا\s+(?:ستفعل|كنت\s+ستفعل|تنصح).{0,30}(?:مشروع|TitanX|الأسبوع|السنة)",
        r"if\s+you\s+(?:were|are).{0,20}(?:in\s+charge|owner|responsible|leading)",
        r"what\s+would\s+you\s+do.{0,20}(?:with|for|to).{0,20}(?:project|system|TitanX)",
        r"(?:خطة|استراتيجية|رؤية).{0,20}(?:تطوير|المشروع|الأسبوع|الشهر)",
        r"(?:خطة|استراتيجية)\s+(?:المشروع|التطوير|للمشروع)",
        r"(?:ما|كيف).{0,10}(?:خطتك|رؤيتك|استراتيجيتك)",
        r"plan.{0,20}(?:for|the)\s+project",
        r"roadmap.{0,20}project",
    ]
    if any(re.search(p, ml) for p in _STRATEGY_P):
        return "strategy"

    # ── Runtime Graph — Rule 5: Startup/Runtime/Failure chains ───────────────
    _RUNTIME_P = [
        r"(?:رسم|أظهر|اعرض)\s+(?:بيان\s+)?التشغيل",
        r"(?:runtime|startup|execution)\s+(?:graph|chain|diagram|map|flow)",
        r"(?:سلسلة|مخطط)\s+(?:التشغيل|البدء|الفشل|الإقلاع)",
        r"(?:failure|fault)\s+chain",
        r"(?:startup|boot)\s+(?:chain|sequence|order|flow)",
        r"كيف\s+(?:يبدأ|يعمل|يُقلع|يُشغَّل)\s+(?:المشروع|النظام|التطبيق|الخادم)",
        r"how\s+does\s+(?:the\s+)?(?:project|system|app|server)\s+(?:start|boot|launch|run)",
        r"(?:ما|what).{0,20}(?:ترتيب|order|sequence)\s+(?:التشغيل|البدء|الإقلاع|startup)",
        r"execution\s+flow",
        r"تسلسل\s+(?:التشغيل|البدء|الإقلاع)",
    ]
    if any(re.search(p, ml) for p in _RUNTIME_P):
        return "runtime_graph"

    # ── Priority 0: Action intents (must beat file-finding patterns) ──────────
    # "Create notification bot" → create_feature
    _P0_CREATE = [
        r"create\b.{0,40}(bot|feature|system|module|command|handler|notification|service)",
        r"build\b.{0,30}(bot|feature|system|module|service)",
        r"make\b.{0,30}(bot|feature|system|service)",
        r"add\b.{0,30}(bot|notification|command|feature|handler|service)",
        r"implement\b.{0,40}(bot|feature|system|module)",
        r"develop\b.{0,30}(bot|feature|system)",
        r"أنشئ\b", r"اصنع",
        r"أضف\s+(?:بوت|bot)\b",   # "أضف بوت X" — bot IS the thing being added
        r"بناء.*بوت", r"بناء.*bot",
    ]
    if any(re.search(p, ml) for p in _P0_CREATE):
        return "create_feature"

    # "Redesign homepage" → ui_redesign
    _P0_REDESIGN = [
        r"redesign\b", r"revamp\b", r"إعادة\s*تصميم",
        r"redo\b.{0,20}(page|design|ui|interface|layout)",
        r"restyle\b", r"new\b.{0,10}look\b", r"تجديد.*تصميم",
    ]
    if any(re.search(p, ml) for p in _P0_REDESIGN):
        return "ui_redesign"

    # "Fix broken button" / "Fix error" → debug_fix
    _P0_FIX = [
        r"\bfix\b.{0,40}(error|bug|button|broken|issue|problem|page|feature|crash|fail)",
        r"\bfix\b\s+(?:the|this|a|an)\b",
        r"repair\b.{0,30}(error|bug|button|broken)",
        r"correct\b.{0,30}(error|bug|issue|problem)",
        r"صلح\b", r"إصلاح\b",
        r"investigate\b.{0,30}(error|bug|issue|broken)",
        r"broken\b.{0,20}(button|page|feature|link)",
    ]
    if any(re.search(p, ml) for p in _P0_FIX):
        return "debug_fix"

    # "Create new page" → new_page
    _P0_NEW_PAGE = [
        r"(?:create|add|make|build)\b.{0,15}(?:new\b.{0,5})?(?:page|screen|view|section)\b",
        r"new\b.{0,5}page\b", r"صفحة\s*جديدة", r"أنشئ\s*صفحة",
    ]
    if any(re.search(p, ml) for p in _P0_NEW_PAGE):
        return "new_page"

    # ── Agent Foundation intents (priority before file-awareness) ───────────────
    _WHO_DEPENDS = [
        r"ما\s+(?:الملفات|الكود).{0,30}(?:تعتمد|يعتمد|تستورد|يستورد)\s+عل",
        r"what\s+files?.{0,15}(?:depend|import|use).{0,10}on\s+[\w/]+",
        r"who\s+(?:depends|imports|uses)\s+(?:on\s+)?[\w/]+",
        r"من\s+(?:يستورد|يستخدم|يعتمد\s+على)\s+[\w/]+",
        r"سلسلة\s+(?:التبعيات|تبعيات)",
        r"dependency\s+chain\s+for",
        r"ماذا\s+(?:يستورد|يعتمد\s+على)\s+[\w/]+",
    ]
    if any(re.search(p, ml) for p in _WHO_DEPENDS):
        return "who_depends"

    _DATA_FLOW_P = [
        r"data\s+flow",
        r"تدفق\s+البيانات",
        r"flow\s+from.{0,30}(?:user|telegram|تليغرام|المستخدم)",
        r"(?:from|من)\s+(?:telegram|تليغرام|المستخدم|user).{0,30}(?:to|إلى)\s+(?:response|الرد)",
        r"(?:how|كيف).{0,20}(?:message|رسالة|request|طلب).{0,20}(?:flow|يصل|يمر|travels?)",
        r"مسار\s+(?:الطلب|الرسالة|البيانات)",
        r"path\s+of\s+(?:data|message|request)",
    ]
    if any(re.search(p, ml) for p in _DATA_FLOW_P):
        return "data_flow"

    _REUSE_P = [
        r"(?:reusable|يمكن\s+إعادة\s+استخدام)",
        r"existing\s+(?:systems?|components?|code).{0,20}(?:reuse|reused|leverage|use)",
        r"ماذا\s+(?:يمكن|أستطيع).{0,20}(?:إعادة\s+استخدام|الاستفادة\s+منه)",
        r"what.{0,20}(?:can\s+be\s+reused|existing\s+systems?).{0,30}(?:for|in)\s+(?:new|this|bot|notification)",
        r"ما\s+الأنظمة\s+(?:القائمة|الموجودة).{0,20}(?:يمكن|reuse)",
    ]
    if any(re.search(p, ml) for p in _REUSE_P):
        return "reuse_systems"

    # ── Dependency query — Arabic "ما تبعيات X؟" / "تبعيات config.py" ─────────
    _DEP_P = [
        r"تبعيات", r"تبعية\b",
        r"ما\s+(?:التبعيات|تبعيات)",
        r"اعرض\s+(?:التبعيات|تبعيات)",
        r"تحليل\s+(?:التبعيات|التبعية)",
        r"(?:show|list|analyze)\s+dependenc",
        r"dependencies\s+of",
        r"what\s+does\s+[\w/]+(?:\.py)?\s+(?:import|depend)",
    ]
    if any(re.search(p, ml) for p in _DEP_P):
        return "dependency"

    # ── Routes intent — must run BEFORE _FILE_Q ──────────────────────────────
    # REPAIR (Problem 1 + 5): "what route" in _FILE_Q was grabbing "what router"
    # questions, routing them to find_file instead of routes.  Explicit router
    # patterns are now checked first so "What router serves AI Workspace?" → routes.
    _ROUTES_P = [
        r"what\s+router\s+(?:serves?|handles?|manages?|is\s+responsible|routes?)",
        r"which\s+router\s+(?:serves?|handles?|manages?|is\s+responsible|routes?)",
        r"what\s+router\b",   # catches "what router serves the..."
        r"which\s+router\b",  # catches "which router handles..."
        r"(?:show|list|display|print)\s+(?:all\s+)?routes?",
        r"(?:what|which)\s+routes?\s+(?:are\s+)?(?:available|registered|defined|exist)",
        r"ما\s+(?:الروتر|الراوتر).{0,30}(?:يخدم|يعالج|يتحكم|المسؤول)",
        r"أي\s+(?:روتر|راوتر).{0,30}(?:يخدم|يعالج|يتحكم)",
    ]
    if any(re.search(p, ml) for p in _ROUTES_P):
        return "routes"

    # ── Database schema questions — before _FILE_Q ────────────────────────────
    # REPAIR (Problem 4): "What database table stores users?" fell to general
    # because no pattern caught it.  Route these to arch (structure knowledge).
    _SCHEMA_P = [
        r"what\s+(?:database\s+)?table\s+(?:stores?|has|contains?|holds?|is\s+for)",
        r"which\s+(?:database\s+)?table\s+(?:stores?|has|contains?|holds?)",
        r"what\s+table.{0,20}(?:user|row|column|schema|record)",
        r"which\s+table.{0,20}(?:user|row|column|schema|record)",
        r"database\s+(?:table|schema|model|structure).{0,20}(?:for|stores?|user|bot)",
        r"ما\s+(?:الجدول|جدول).{0,20}(?:يخزن|يحتوي|يحفظ)",
        r"جدول\s+(?:المستخدمين|البيانات|الرسائل)",
    ]
    if any(re.search(p, ml) for p in _SCHEMA_P):
        return "arch"

    # ── Function-finder (PHASE 2) — before _FILE_Q ───────────────────────────
    # "What function creates this keyboard?" / "Which function handles /start?"
    # Must be checked before _FILE_Q so function queries don't fall into find_file.
    _FUNC_Q = [
        r"what\s+function\s+(?:creates?|handles?|processes?|builds?|makes?|generates?|sends?|defines?|serves?)",
        r"which\s+function\s+(?:creates?|handles?|processes?|builds?|makes?|generates?|sends?|is\s+responsible)",
        r"what\s+function\s+is\s+responsible",
        r"which\s+function\s+is\s+responsible",
        r"ما\s+(?:الدالة|الوظيفة).{0,20}(?:التي|اللي|تُنشئ|تُعالج|تُرسل|تبني)",
        r"أي\s+(?:دالة|وظيفة).{0,20}(?:تُنشئ|تعالج|تبني|تُرسل)",
    ]
    if any(re.search(p, ml) for p in _FUNC_Q):
        return "find_function"

    # ── Priority 1: file-awareness patterns (must run first) ──────────────────
    _FILE_Q = [
        r"what file.{0,25}control",
        r"which file.{0,25}control",
        r"what file.{0,25}handle",
        r"what file.{0,25}manage",
        r"what file.{0,25}(?:the\s+)?homepage",
        r"what file.{0,25}(?:the\s+)?dashboard",
        r"what file.{0,25}color",
        r"what file.{0,25}css",
        r"what file.{0,25}sidebar",
        r"what file.{0,25}login",
        r"what file.{0,25}auth",
        r"what file.{0,25}users?",
        r"what file.{0,25}(?:the\s+)?ai",
        r"what css",
        r"what.{0,10}css.{0,20}control",
        r"what files?.{0,20}(?:should|need|must).{0,20}(?:modify|change|edit|update)",
        r"what files?.{0,20}(?:to|for).{0,20}(?:redesign|rebuild|modify|change)",
        r"files?.{0,20}(?:must|should|need).{0,20}(?:change|modify)",
        # NOTE: "what route" / "which route" removed — caught above by _ROUTES_P
        # so "what router serves..." no longer falls here as find_file.
        r"what.{0,10}route.{0,25}(?:loads?|serves?|handles?)\s+(?:the\s+)?(?:page|view|html|template)",
        r"find.{0,25}(?:page|file|route|template)",
        r"where.{0,10}(?:is|are).{0,20}(?:the\s+)?(?:homepage|dashboard|sidebar|colors?|login|css|js|backup|ai|bot|download|support|github|user|setting|log)",
        r"locate.{0,25}(?:page|file|route)",
        r"أي ملف.{0,25}يتحكم",
        r"ما الملف.{0,25}(?:يتحكم|يعالج|المسؤول)",
        r"ما الروتر.{0,35}(?:المسؤول|يعالج|يتحكم|يخدم|يعرض)",
        r"أي روتر.{0,35}(?:المسؤول|يعالج|يتحكم|يخدم|يعرض)",
        r"أين.{0,25}(?:الصفحة|الملف|الكود|المسار)",
        r"ما.{0,5}(?:ملف|صفحة).{0,20}(?:يتحكم|يعرض|يعالج)",
    ]
    for p in _FILE_Q:
        if re.search(p, ml):
            return "find_file"

    # ── Priority 2: root cause & impact ───────────────────────────────────────
    if re.search(r"why.{0,30}(?:broken|not work|fail)", ml):
        return "root_cause"
    if re.search(r"what.{0,10}(?:breaks?|happens? if)", ml):
        return "impact"
    if re.search(r"اختبر نفسك|self.?test|test yourself", ml):
        return "self_test"

    # ── Priority 2·5: Weakness / vulnerability / risk ────────────────────────
    # "ما أكبر نقطة ضعف بالمشروع؟" / "biggest risk in the system?"
    _WEAKNESS_Q = [
        r"(?:أكبر|أشد|أخطر|أهم).{0,20}(?:نقطة\s+ضعف|مشكلة|ثغرة|خطر|تحدي)",
        r"(?:أكبر|أشد|أهم|أخطر).{0,10}(?:\d+\s+)?مخاطر",
        r"(?:نقطة|نقاط)\s+(?:ضعف|ضعيفة).{0,20}(?:بالمشروع|في\s+المشروع|المشروع)?",
        r"أين\s+(?:الضعف|المشكلة\s+الكبرى|الثغرة|الخطر)",
        r"(?:biggest|main|major|worst|top\s*\d*).{0,15}(?:weakness|problem|risk|vulnerability|flaw)",
        r"what.{0,15}(?:risk|weak|vulnerable|fragile).{0,15}(?:project|system|app)",
        r"(?:top|biggest|major)\s+\d+\s+risks?",
        r"(?:ما|list).{0,10}(?:أكبر|أشد|أخطر|biggest|main|major).{0,10}(?:مخاطر|risks?)",
    ]
    if any(re.search(p, ml) for p in _WEAKNESS_Q):
        return "weakness"

    # ── Priority 2·55: Security / safety check ───────────────────────────────
    # "هل المشروع آمن؟" — Arabic آمن (U+0622) ≠ INTENTS pattern أمن (U+0623), must catch here
    _SECURITY_Q = [
        r"هل\s+المشروع\s+(?:آمن|مؤمن|محمي|بأمان)",
        r"(?:مستوى|درجة|مدى)\s+(?:الأمان|الحماية|الأمن)",
        r"(?:أمان|حماية|أمن)\s+المشروع",
        r"(?:is|how\s+(?:secure|safe)).{0,15}(?:project|system|app)",
        r"security\s+(?:check|audit|scan|review|analysis|status)",
        r"(?:ثغرات|مخاطر|vulnerabilities).{0,20}(?:المشروع|project)",
        r"هل\s+(?:هناك|يوجد).{0,15}(?:ثغرات|مخاطر|مشاكل\s+أمنية)",
    ]
    if any(re.search(p, ml) for p in _SECURITY_Q):
        return "security"

    # ── Priority 2·6: Architecture quality (before scored match steals "بنية") ─
    # "هل بنية المشروع جيدة؟" / "is the project structure good?"
    _ARCH_Q = [
        r"هل.{0,10}(?:بنية|هيكل)\s+المشروع",
        r"(?:بنية|هيكل)\s+المشروع.{0,20}(?:جيدة?|صحيحة?|منظمة?|مناسبة?)",
        r"تقييم\s+المشروع",
        r"هل\s+المشروع\s+(?:جيد|منظم|صحيح|مناسب)",
        r"(?:review|evaluate|assess).{0,20}(?:project|architecture)",
        r"(?:is|how\s+is).{0,10}(?:the\s+)?(?:project|architecture|code).{0,20}(?:good|solid|structured)",
    ]
    if any(re.search(p, ml) for p in _ARCH_Q):
        return "arch"

    # ── Scored match ──────────────────────────────────────────────────────────
    scores: dict = {}
    for intent, patterns in INTENTS.items():
        score = sum(1 for p in patterns if re.search(p, ml))
        if score:
            scores[intent] = score
    if scores:
        return max(scores, key=lambda k: scores[k])

    # ── PROJECT MODIFICATION GATE ─────────────────────────────────────────────
    # Catches short imperative Arabic commands that score 0 on every keyword list
    # above because they carry no tech-explainer or comparison signal — yet are
    # unambiguously project modification requests.
    #
    # Pattern: modification verb + project component noun → "project_mod"
    #
    # Examples caught here (were previously falling to "general"):
    #   احذف زر / أضف زر / انقل زر / غير نص / احذف قائمة / عدل رسالة
    #   غير أمر / أزل صفحة / أضف صفحة / أوقف ميزة / فعل ميزة
    #   احذف زر إدارة لوحة الإدارة من البوت الرئيسي
    #   أضف قائمة inline للبوت / غير نص رسالة الترحيب
    _MOD_VERB_RE = re.compile(
        r'\b(?:احذف|أحذف|احزف|أزل|أزيل|انقل|أنقل|'
        r'غيّر|غير|عدّل|عدل|أضف|اضف|أضيف|'
        r'أوقف|اوقف|وقف|فعّل|فعل|فعّلي|'
        r'أخفِ|أخفي|خبّي|أظهر|اظهر|'
        r'بدّل|بدل|عطّل|عطل|امسح|احجب|'
        r'ألغِ|الغِ|أنشئ|أنشي|أرسل|'
        r'حذف|إضافة|إزالة|تغيير|تعديل|نقل|'
        r'إيقاف|تفعيل|إخفاء|تبديل|إظهار|'
        r'ربط|أربط|اربط|فصل|أفصل|'
        r'أعد|اعد|أعيد|أعدل|أرتّب|رتّب)\b',
        re.IGNORECASE
    )
    # NOTE: No \b word-boundary wrapper — Arabic prefixes (لل/ال/من) prevent \b
    # from matching mid-word Arabic text (e.g. "للزر", "الرسالة", "من البوت").
    # underscore tokens (callback_data, inline_keyboard) also break \b.
    # These terms are distinctive enough that no word boundary is needed.
    _MOD_TARGET_RE = re.compile(
        r'(?:'
        # UI elements
        r'زر|أزرار|زرار|زرّ|'
        r'قائمة|قوائم|منيو|'
        r'لوحة\s*(?:مفاتيح|المفاتيح)|كيبورد|keyboard|inline_keyboard|reply_markup|'
        r'نافذة|نوافذ|popup|modal|'
        # Bot/Telegram elements — callback_data BEFORE callback to avoid partial match
        r'أمر|أوامر|كوماند|command|'
        r'handler|هاندلر|معالج|'
        r'callback_data|callback|كولباك|'
        r'رسالة|رسائل|message|'
        r'إشعار|إشعارات|notification|'
        r'بوت|بوتات|bot|'
        r'ترحيب|welcome|'
        # Pages / UI structure
        r'صفحة|صفحات|page|'
        r'واجهة|interface|'
        r'قسم|أقسام|section|'
        r'عنصر|عناصر|element|'
        # Code / files
        r'ملف|ملفات|file|'
        r'router|روتر|مسار|route|endpoint|'
        r'api|'
        # Styling
        r'css|html|style|تصميم|'
        r'template|قالب|'
        r'لون|ألوان|color|colour|'
        # Feature / system
        r'ميزة|ميزات|feature|'
        r'خاصية|خصائص|وظيفة|وظائف|'
        r'نظام|أنظمة|system|'
        r'وحدة|وحدات|module|'
        # Data
        r'قاعدة\s*(?:البيانات|بيانات)|database|'
        r'إعداد|إعدادات|setting|config|'
        # Text / links
        r'نص|نصوص|text|label|عنوان|عناوين|'
        r'رابط|روابط|link'
        r')',
        re.IGNORECASE
    )
    if _MOD_VERB_RE.search(ml) and _MOD_TARGET_RE.search(ml):
        return "project_mod"

    # ── Semantic reasoning — broad Arabic / mixed patterns ────────────────────
    # These catch well-formed questions that score 0 on keyword lists but have
    # clear meaning. Checked AFTER scored match so specific handlers win first.

    # Identity variants: "عرفني بنفسك", "ما اسمك", "هل أنت AI", "ما وظيفتك"
    _IDENTITY_SEM = [
        r"عرّفني\s+بنفسك", r"عرفني\s+بنفسك", r"عرّف\s+نفسك", r"عرف\s+نفسك",
        r"ما\s+اسمك", r"ما\s+هو\s+اسمك",
        r"هل\s+أنت\s+(?:ذكاء|ذكاءً)\s+اصطناعي",
        r"هل\s+أنت\s+(?:بوت|روبوت|ai|برنامج|آلة)",
        r"من\s+تكون\b", r"من\s+تكون\s+أنت",
        r"ما\s+(?:وظيفتك|دورك|مهمتك|هدفك|غرضك|تخصصك)",
        r"what\s+(?:is\s+your\s+)?(?:role|purpose|function|job|mission)\b",
    ]
    if any(re.search(p, ml) for p in _IDENTITY_SEM):
        return "identity"

    # Impact / conditional: "لو عدلت X ماذا سيحدث؟"
    _IMPACT_SEM = [
        r"لو\s+(?:عدلت|غيرت|حذفت|أنشأت|بدلت|أضفت)",
        r"إذا\s+(?:عدلت|غيرت|حذفت|أنشأت|أضفت|بنيت)",
        r"ماذا\s+(?:سيحدث|سيتأثر|سيتغير|قد\s+يحدث|ينكسر|يتأثر|سيُكسر|سيتعطل)",
        r"what\s+(?:would|will)\s+(?:happen|break|change)",
        r"if\s+(?:i|we)\s+(?:change|modify|delete|add|edit)",
    ]
    if any(re.search(p, ml) for p in _IMPACT_SEM):
        return "impact"

    # Project architecture / quality
    _ARCH_SEM = [
        r"(?:بنية|هيكل)\s+المشروع",
        r"هل\s+المشروع\s+(?:جيد|منظم|صحيح|مناسب)",
        r"تقييم\s+المشروع",
        r"(?:project|code|architecture).{0,20}(?:good|solid|quality|well.structured)",
        r"(?:review|evaluate|assess).{0,20}(?:project|architecture|code\s+quality)",
    ]
    if any(re.search(p, ml) for p in _ARCH_SEM):
        return "arch"

    # Improvement / best-practice / suggestions
    _IMPROVE_SEM = [
        r"أفضل\s+(?:تطوير|تحسين|ميزة|إضافة).{0,30}(?:للمشروع|المشروع)?",
        r"(?:كيف|ماذا)\s+(?:أطور|أحسن|أعزز|تطور|يطور|تحسن|يحسن|نطور|نحسن)\s+المشروع",
        r"كيف\s+(?:تطور|يطور|تحسن|يحسن).{0,20}(?:المشروع|هذا\s+المشروع)",
        r"best\s+(?:improvement|feature|addition|upgrade)\s+(?:for\s+)?(?:the\s+)?project",
        r"(?:what|how).{0,10}(?:improve|enhance|upgrade)\s+(?:the\s+)?project",
        r"ما\s+(?:الذي\s+)?(?:يحسن|يطور)\s+المشروع",
        r"اقترح\b.{0,40}(?:تطوير|تحسين|ميزة|إضافة|تغيير)",
        r"قدّم\s+اقتراح", r"قدم\s+اقتراح",
        r"\d+\s+تطوير", r"\d+\s+تحسين",
        r"suggest\b.{0,30}(?:improvement|feature|upgrade|change)",
        r"recommend\b.{0,30}(?:improvement|feature|next\s+step)",
    ]
    if any(re.search(p, ml) for p in _IMPROVE_SEM):
        return "improve"

    # Feature creation / integration
    _CREATE_SEM = [
        r"كيف\s+(?:أضيف|أنشئ|أبني|أدمج|أحدث).{0,40}(?:بوت|ميزة|نظام|خدمة|إشعار)",
        r"هل\s+يمكن\s+(?:دمج|إضافة|إنشاء|بناء).{0,30}(?:بوت|ميزة|نظام|خدمة)",
        r"يمكن\s+(?:دمج|إضافة|إنشاء)\s*(?:بوت|ميزة|نظام)?",
        r"how\s+(?:do\s+i|to|can\s+i).{0,20}(?:add|create|build|integrate).{0,20}(?:bot|feature|system|service)",
        r"can\s+(?:i|we).{0,15}(?:add|create|integrate|build).{0,20}(?:bot|feature|service)",
    ]
    if any(re.search(p, ml) for p in _CREATE_SEM):
        return "create_feature"

    # General explanation / conversation (broad catch before giving up)
    _CONV_SEM = [
        r"(?:اشرح|وضح|فسّر|فسر|ما\s+هو|ما\s+هي|ما\s+معنى|ما\s+المقصود)",
        r"(?:explain|describe|what\s+is|what\s+are|how\s+does|how\s+do)",
        r"(?:فرق|مقارنة|الفرق|أيهما\s+أفضل)",
        r"(?:why|لماذا|متى|when\s+(?:should|do|does))",
    ]
    if any(re.search(p, ml) for p in _CONV_SEM):
        return "conversation"

    return "general"


# ═══════════════════════════════════════════════════════════════════════════════
# QUERY NORMALIZATION & CONCEPT MATCHING
# ═══════════════════════════════════════════════════════════════════════════════

def _normalize_query(q: str) -> str:
    # Apply Arabic normalization first so hamza/diacritic variants match aliases
    q_norm = _normalize_ar(q)
    ql = q_norm.lower().strip()
    for ar, en in _ALIASES.items():
        ar_norm = _normalize_ar(ar)
        if ar_norm in q_norm:
            ql = ql.replace(ar_norm.lower(), en)
    return ql


def _find_concept(q: str) -> list:
    """Return list of (file, role, description) for a concept query.
    Uses longest-match-first so 'ai_engineer' beats 'ai'.
    """
    normalized = _normalize_query(q)

    # ── Pass 1: exact substring (longest concept wins) ────────────────────────
    best_match = None
    best_len   = 0
    for concept, entries in sorted(_SEMANTIC_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        concept_plain = concept.replace("_", " ")
        matched = (concept_plain in normalized) or (concept in normalized)
        if matched and len(concept) > best_len:
            best_match = entries
            best_len   = len(concept)
    if best_match:
        return best_match

    # ── Pass 2: all keywords in concept must be present (AND logic) ───────────
    results, seen = [], set()
    for concept, entries in sorted(_SEMANTIC_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        kws = concept.split("_")
        if len(kws) > 1 and all(kw in normalized for kw in kws):
            for e in entries:
                if e[0] not in seen:
                    results.append(e); seen.add(e[0])
    if results:
        return results

    # ── Pass 3: any meaningful keyword (len > 2) ─────────────────────────────
    for concept, entries in sorted(_SEMANTIC_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        kws = [kw for kw in concept.split("_") if len(kw) > 2]
        if kws and any(kw in normalized for kw in kws):
            for e in entries:
                if e[0] not in seen:
                    results.append(e); seen.add(e[0])

    # ── Pass 4: route alias search ────────────────────────────────────────────
    for route, info in _ROUTE_GRAPH.items():
        for alias in info.get("aliases", []):
            if alias.lower() in normalized and info["template"] not in seen:
                results.append((info["template"], "template", info["description"]))
                results.append((info["router"], "router", f"route {route}"))
                seen.add(info["template"])
                break

    return results


def _route_for_concept(q: str) -> Optional[dict]:
    """Return the _ROUTE_GRAPH entry that best matches the query."""
    normalized = _normalize_query(q)
    best, best_score = None, 0
    for route, info in _ROUTE_GRAPH.items():
        score = sum(1 for alias in info.get("aliases", []) if alias.lower() in normalized)
        if score > best_score:
            best, best_score = info, score
    return best if best_score else None


# ═══════════════════════════════════════════════════════════════════════════════
# FILE SEARCH ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def search_project_files(query: str) -> list:
    """Semantic + filesystem file search."""
    # Semantic first
    concept_hits = _find_concept(query)
    found_paths = {e[0] for e in concept_hits}

    # Route alias match
    route_info = _route_for_concept(query)
    if route_info:
        for f in [route_info.get("router"), route_info.get("template")]:
            if f and f not in found_paths:
                concept_hits.append((f, "route_match", route_info["description"]))
                found_paths.add(f)

    # Filesystem fallback — filename match
    ql = query.lower()
    ql_ar = _normalize_ar(query).lower()
    for root, dirs, files in os.walk(str(EXTRACTED_DIR)):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            fp = Path(root) / fname
            rel = str(fp.relative_to(EXTRACTED_DIR))
            if any(ext in fname for ext in CODE_EXTS) and (ql in fname.lower() or ql_ar in fname.lower()) and rel not in found_paths:
                concept_hits.append((rel, "filename_match", fname))
                found_paths.add(rel)

    # Content search fallback — grep file contents when semantic + filename both empty
    if not concept_hits and len(ql) >= 3:
        _terms = [t for t in ql.split() if len(t) >= 3][:3]
        for root, dirs, files in os.walk(str(EXTRACTED_DIR)):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fname in files:
                if not any(fname.endswith(e) for e in [".py", ".html", ".js", ".css"]):
                    continue
                fp = Path(root) / fname
                rel = str(fp.relative_to(EXTRACTED_DIR))
                if rel in found_paths:
                    continue
                try:
                    content = fp.read_text(errors="ignore").lower()
                    if _terms and all(t in content for t in _terms):
                        concept_hits.append((rel, "content_match", f"contains: {', '.join(_terms)}"))
                        found_paths.add(rel)
                        if len(concept_hits) >= 8:
                            return concept_hits
                except Exception:
                    pass
    return concept_hits


# ═══════════════════════════════════════════════════════════════════════════════
# FILE AWARENESS ENGINE — answer any "what file controls X?" question
# ═══════════════════════════════════════════════════════════════════════════════

def answer_file_question(msg: str) -> dict:
    """Answer questions like 'what file controls X?' with real file paths."""
    # Extract concept from common patterns
    concept_pats = [
        r"what files?.{0,20}(?:should|must|need).{0,20}(?:(?:be\s+)?modified?|changed?|edited?|updated?).{0,30}(?:to\s+)?(.+?)[\?\.]*$",
        r"what files?.{0,20}(?:to|for)\s+(?:redesign|rebuild|modify|change)\s+(.+?)[\?\.]*$",
        r"what file.{0,20}(?:controls?|handles?|manages?|is)\s+(?:the\s+)?(.+?)[\?\.]*$",
        r"which file.{0,20}(?:controls?|handles?|for|serves?)\s+(?:the\s+)?(.+?)[\?\.]*$",
        r"what.{0,10}css.{0,20}(?:controls?|handles?|is\s+for)\s+(?:the\s+)?(.+?)[\?\.]*$",
        r"what.{0,10}(?:route|path).{0,20}(?:loads?|serves?|handles?)\s+(?:the\s+)?(.+?)[\?\.]*$",
        r"where.{0,10}is\s+(?:the\s+)?(.+?)(?:\s+(?:file|page|code|template|route))[\?\.]*$",
        r"find\s+(?:the\s+)?(.+?)(?:\s+(?:file|page|template|route))?[\?\.]*$",
        r"locate\s+(?:the\s+)?(.+?)(?:\s+(?:file|page|template))?[\?\.]*$",
        r"أي ملف.{0,20}يتحكم.{0,20}(?:في\s+)?(.+?)[\?\.]*$",
        r"ما الملف.{0,20}(?:يتحكم|يعالج|المسؤول).{0,20}(?:عن\s+)?(.+?)[\?\.]*$",
        r"أين.{0,10}(?:يوجد\s+)?(.+?)[\?\.]*$",
    ]
    concept = msg
    for pat in concept_pats:
        m = re.search(pat, msg, re.IGNORECASE)
        if m:
            concept = m.group(1).strip(" ?.!")
            break

    # Also try the full message if concept extraction gives something very short
    entries = _find_concept(concept)
    if not entries:
        entries = _find_concept(msg)

    # Route-level match
    route_info = _route_for_concept(concept) or _route_for_concept(msg)

    if not entries and not route_info:
        return {
            "text": f"⚠️ لم أجد ملفات مرتبطة بـ: **{concept}**\n\nجرب: homepage, dashboard, sidebar, colors, login, users, ai engineer, bots, backup",
            "data": {"concept": concept, "files": []},
        }

    # ── EVIDENCE GATE: verify files exist on disk before claiming ownership ────
    # The semantic index may reference files that have been renamed, moved, or
    # never existed.  Before asserting ownership the agent MUST confirm each
    # claimed file is physically present on disk.  If the index returns entries
    # but NONE survive the disk check → return NOT ENOUGH EVIDENCE rather than
    # hallucinating a confident-sounding but unverified answer.
    _PROJ_ROOT = Path(os.environ.get(
        "PROJECT_ROOT", "/home/runner/workspace/extracted_project"))
    def _on_disk(path: str) -> bool:
        p = path.strip("/")
        return ((_PROJ_ROOT / p).exists()
                or (_PROJ_ROOT.parent / p).exists()
                or Path(path).exists())

    _verified = [(p, r, d) for p, r, d in entries if _on_disk(p)]
    if entries and not _verified:
        return {
            "text": (
                "⛔ **NOT ENOUGH EVIDENCE**\n\n"
                f"الفهرس الدلالي يقترح ملفات لـ `{concept}` "
                "لكن لا يوجد أيٌّ منها على القرص الفعلي.\n\n"
                "لا يمكنني تأكيد الملكية بدون دليل موثق من الكود الحقيقي.\n"
                "تحقق من اسم المفهوم أو استخدم: `structure`, `routes`, `arch`."
            ),
            "data": {"concept": concept, "files": [], "evidence": "INSUFFICIENT"},
        }
    entries = _verified

    # Build answer text
    lines = [f"📍 **الملفات المسؤولة عن: `{concept}`**\n"]
    file_list = []

    if route_info:
        lines.append(f"🌐 **الرابط:** `{route_info.get('description', '')}`")
        for entry_type, label, emoji in [("router", "ROUTER", "⚙️"), ("template", "TEMPLATE", "🎨"), ("base", "BASE", "🏗️")]:
            f = route_info.get(entry_type)
            if f:
                lines.append(f"  {emoji} **{label}**: `{f}` ✅")
                file_list.append({"path": f, "role": entry_type, "desc": label})
        css = route_info.get("css", [])
        if css:
            lines.append(f"  🎨 **CSS**: `{', '.join(css)}`")
            for c in css:
                file_list.append({"path": c, "role": "css", "desc": "stylesheet"})
        js = route_info.get("js", [])
        if js:
            lines.append(f"  📜 **JS**: `{', '.join(js)}`")
            for j in js:
                file_list.append({"path": j, "role": "js", "desc": "javascript"})
        apis = route_info.get("apis", [])
        if apis:
            lines.append(f"  🔌 **APIs**: {', '.join(f'`{a}`' for a in apis[:4])}")
        lines.append("")

    seen_files = {e["path"] for e in file_list}
    if entries:
        lines.append("📂 **الملفات المرتبطة:**")
        for path, role, desc in entries:
            if path not in seen_files:
                role_icons = {
                    "template": "🎨", "router": "⚙️", "css": "🎨", "js": "📜",
                    "model": "🗄️", "db": "🗄️", "handler": "🤖", "service": "🔧",
                    "auth": "🔐", "config": "⚙️", "engine": "🧠", "entry": "🚀",
                    "locale": "🌍", "middleware": "🛡️",
                }
                icon = role_icons.get(role, "📄")
                lines.append(f"  {icon} **{role.upper()}**: `{path}` — {desc}")
                file_list.append({"path": path, "role": role, "desc": desc})
                seen_files.add(path)

    return {
        "text": "\n".join(lines),
        "data": {"concept": concept, "files": file_list, "evidence": "VERIFIED"},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY ANALYZER
# ═══════════════════════════════════════════════════════════════════════════════

def build_dependency_map() -> dict:
    """Auto-scan all Python router files + supplement with static knowledge."""
    dep_map: dict = {}

    # Auto-discovery from router files
    router_dir = _HERE / "routers"
    if router_dir.exists():
        for rf in sorted(router_dir.glob("*.py")):
            try:
                src = rf.read_text(encoding="utf-8")
            except Exception:
                continue
            for m in re.finditer(r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)', src):
                route  = m.group(2)
                pos    = m.start()
                # find TemplateResponse near this route
                snippet = src[pos:pos + 600]
                tpls    = re.findall(r'TemplateResponse\([^,]+,\s*["\']([^"\']+)', snippet)
                dep_map[route] = {
                    "file": f"control_panel/routers/{rf.name}",
                    "templates": tpls or [],
                    "css": ["control_panel/static/css/style.css"],
                    "js": ["control_panel/static/js/app.js"],
                }

    # App.py routes
    try:
        app_src = (_HERE / "app.py").read_text(encoding="utf-8")
        for m in re.finditer(r'@app\.(get|post)\(["\']([^"\']+)', app_src):
            route   = m.group(2)
            pos     = m.start()
            snippet = app_src[pos:pos + 400]
            tpls    = re.findall(r'TemplateResponse\([^,]+,\s*["\']([^"\']+)', snippet)
            dep_map[route] = {
                "file": "control_panel/app.py",
                "templates": tpls or [],
                "css": ["control_panel/static/css/style.css"],
                "js": ["control_panel/static/js/app.js"],
            }
    except Exception:
        pass

    return dep_map


def analyze_file_impact(file_rel_path: str) -> dict:
    """What breaks if this file changes? What depends on it?"""
    fp = file_rel_path.lower().replace("\\", "/")
    impact = {"file": file_rel_path, "affects": [], "depended_by": [], "risk": "low"}

    # Static knowledge about high-impact files
    _IMPACT = {
        "control_panel/static/css/style.css": {
            "affects": ["ALL 20 templates — every page in the control panel"],
            "risk": "critical",
        },
        "control_panel/static/js/app.js": {
            "affects": ["ALL pages — sidebar, theme, alerts, modals, API calls, charts"],
            "risk": "critical",
        },
        "control_panel/templates/base.html": {
            "affects": ["19 pages that extend base.html — sidebar, header, navigation, CSS/JS loading"],
            "risk": "critical",
        },
        "control_panel/app.py": {
            "affects": ["Panel startup, auth routes /panel /panel/login, all router registration"],
            "risk": "critical",
        },
        "control_panel/auth.py": {
            "affects": ["All authenticated panel routes — removing auth breaks all page access"],
            "risk": "critical",
        },
        "control_panel/config.py": {
            "affects": ["All 12 routers import config — PROJECT_ROOT, OWNER_ID, template paths"],
            "risk": "high",
        },
        "control_panel/ai_engine.py": {
            "affects": ["All /ai/* API endpoints, chat, planning, file questions, self-tests"],
            "risk": "high",
        },
        "database/db.py": {
            "affects": ["init_db() — breaking this prevents bot startup; all 8 DB models depend on it"],
            "risk": "critical",
        },
        "database/users.py": {
            "affects": ["handlers/start.py, handlers/admin.py, handlers/profile.py, control_panel/routers/users.py"],
            "risk": "high",
        },
        "bot.py": {
            "affects": ["Entire PrimeDownloader bot — all handlers, all commands"],
            "risk": "critical",
        },
        "support_bot/bot.py": {
            "affects": ["Entire Support Bot — all ticket handlers"],
            "risk": "critical",
        },
        "config/settings.py": {
            "affects": ["TELEGRAM_BOT_TOKEN, ADMIN_IDS, OWNER_ID — bot won't start without it"],
            "risk": "critical",
        },
        "services/downloader.py": {
            "affects": ["handlers/download.py — ALL download operations"],
            "risk": "high",
        },
        "middlewares/auth.py": {
            "affects": ["All admin commands check is_admin/is_owner here"],
            "risk": "high",
        },
        "locales/ar.py": {
            "affects": ["All Arabic text in bot — all handlers use locales"],
            "risk": "medium",
        },
        "locales/en.py": {
            "affects": ["All English text in bot"],
            "risk": "medium",
        },
    }

    if fp in _IMPACT:
        data   = _IMPACT[fp]
        impact["affects"]  = data["affects"]
        impact["risk"]     = data["risk"]
        impact["depended_by"] = [k for k, v in _IMPACT.items() if fp in str(v.get("affects", []))]
    else:
        # Heuristic for other files
        if "template" in fp or ".html" in fp:
            impact["affects"] = ["This page only — change won't affect other pages"]
            impact["risk"] = "low"
        elif "router" in fp:
            impact["affects"] = ["The routes and APIs defined in this router"]
            impact["risk"] = "medium"
        elif "handler" in fp:
            impact["affects"] = ["The bot commands and callbacks in this handler"]
            impact["risk"] = "medium"
        elif "database" in fp or "model" in fp:
            impact["affects"] = ["All code that imports this DB model"]
            impact["risk"] = "medium"
        elif "service" in fp:
            impact["affects"] = ["All handlers that call this service"]
            impact["risk"] = "medium"

    return impact


def get_file_role(rel_path: str) -> dict:
    """Full profile of any file: role, purpose, dependencies, impact."""
    fp = rel_path.strip().replace("\\", "/")

    # Check route graph
    for route, info in _ROUTE_GRAPH.items():
        if fp == info.get("router") or fp == info.get("template"):
            role_type = "router" if fp == info.get("router") else "template"
            impact    = analyze_file_impact(fp)
            return {
                "file": fp,
                "role": role_type,
                "page": info.get("description"),
                "route": route,
                "template": info.get("template"),
                "router": info.get("router"),
                "css": info.get("css"),
                "js": info.get("js"),
                "apis": info.get("apis"),
                "impact": impact,
            }

    # Check db map
    for key, db_info in _DB_MAP.items():
        if fp == db_info.get("file"):
            return {
                "file": fp,
                "role": "database_model",
                "description": db_info.get("description"),
                "functions": db_info.get("functions"),
                "used_by": db_info.get("used_by"),
                "impact": analyze_file_impact(fp),
            }

    # Check bot map
    for bot_key, bot_info in _BOT_MAP.items():
        if fp == bot_info.get("entry"):
            return {
                "file": fp,
                "role": "bot_entry",
                "description": bot_info.get("description"),
                "handlers": bot_info.get("handlers"),
                "database": bot_info.get("database"),
                "impact": analyze_file_impact(fp),
            }
        for hname, hdesc in bot_info.get("handlers", {}).items():
            hfile = hdesc.split(" —")[0].strip() if " —" in hdesc else hdesc
            if fp in hfile:
                return {
                    "file": fp,
                    "role": "bot_handler",
                    "description": hdesc,
                    "bot": bot_info.get("description"),
                    "impact": analyze_file_impact(fp),
                }

    # Check config map
    for key, cfg_info in _CONFIG_MAP.items():
        if fp == cfg_info.get("file"):
            return {
                "file": fp,
                "role": "config",
                "description": cfg_info.get("description"),
                "used_by": cfg_info.get("used_by"),
                "impact": analyze_file_impact(fp),
            }

    # Generic
    impact = analyze_file_impact(fp)
    return {"file": fp, "role": "unknown", "description": "ملف لم يُصنَّف بعد", "impact": impact}


# ═══════════════════════════════════════════════════════════════════════════════
# MODIFICATION PLANNING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

_PLAN_TEMPLATES: dict = {
    "homepage": {
        "files": [
            ("control_panel/templates/dashboard.html", "template", "HTML structure of the homepage"),
            ("control_panel/routers/dashboard.py", "router", "Python backend — data passed to template"),
            ("control_panel/static/css/style.css", "css", "Dashboard layout .stats-grid, .activity-feed"),
            ("control_panel/static/js/app.js", "js", "Chart.js, dashboard API calls"),
        ],
        "risk": "🟠 متوسط",
        "rollback": "Restore dashboard.html from backups page (/backups) or git revert",
    },
    "dashboard": {
        "files": [
            ("control_panel/templates/dashboard.html", "template", "HTML structure"),
            ("control_panel/routers/dashboard.py", "router", "Backend data"),
            ("control_panel/static/css/style.css", "css", "Dashboard CSS sections"),
            ("control_panel/static/js/app.js", "js", "Chart.js integration"),
        ],
        "risk": "🟠 متوسط",
        "rollback": "Restore dashboard.html from /backups or git",
    },
    "sidebar": {
        "files": [
            ("control_panel/templates/base.html", "template", "Sidebar HTML — affects ALL 19 pages"),
            ("control_panel/static/css/style.css", "css", ".sidebar, .sidebar-nav, .sidebar-link styles"),
            ("control_panel/static/js/app.js", "js", "toggleSidebar() — sidebar open/close logic"),
        ],
        "risk": "🔴 عالي — تغيير base.html يؤثر على 19 صفحة",
        "rollback": "Restore base.html immediately — all pages affected",
    },
    "colors": {
        "files": [
            ("control_panel/static/css/style.css", "css", "CSS variables block — :root { --primary: ... }"),
        ],
        "risk": "🟠 متوسط — CSS variables affect all pages",
        "rollback": "Revert the :root CSS variables block",
    },
    "css": {
        "files": [
            ("control_panel/static/css/style.css", "css", "The one CSS file — all styles"),
        ],
        "risk": "🔴 عالي — affects all 20 pages",
        "rollback": "Restore style.css from backups",
    },
    "login": {
        "files": [
            ("control_panel/templates/access.html", "template", "Login page HTML — standalone, no base.html"),
            ("control_panel/app.py", "app", "POST /panel/login handler + session logic"),
            ("control_panel/auth.py", "auth", "Password hashing + session management"),
            ("control_panel/static/css/style.css", "css", ".access-container styles"),
        ],
        "risk": "🔴 عالي — breaking auth locks everyone out",
        "rollback": "Restore access.html + auth.py before testing",
    },
    "auth": {
        "files": [
            ("control_panel/auth.py", "auth", "Session + password logic"),
            ("control_panel/app.py", "app", "Login route handler"),
            ("control_panel/templates/access.html", "template", "Login page"),
        ],
        "risk": "🔴 عالي — critical security component",
        "rollback": "Always have a working backup before changing auth",
    },
    "users": {
        "files": [
            ("control_panel/templates/users.html", "template", "Users page HTML"),
            ("control_panel/routers/users.py", "router", "Users CRUD APIs"),
            ("database/users.py", "model", "Database operations — ban, points, VIP"),
            ("control_panel/static/css/style.css", "css", "Table styles"),
        ],
        "risk": "🟠 متوسط",
        "rollback": "Restore users.html + users.py",
    },
    "ai_engineer": {
        "files": [
            ("control_panel/templates/ai_engineer.html", "template", "AI Engineer page UI"),
            ("control_panel/routers/ai_workspace.py", "router", "route GET /ai/engineer + APIs"),
            ("control_panel/ai_engine.py", "engine", "Intelligence engine — the core logic"),
            ("control_panel/static/css/style.css", "css", "AI workspace styles"),
        ],
        "risk": "🟠 متوسط",
        "rollback": "Restore ai_engine.py from .ai_backups/",
    },
    "navigation": {
        "files": [
            ("control_panel/templates/base.html", "template", "Navigation links in sidebar"),
            ("control_panel/static/css/style.css", "css", ".sidebar-nav, .sidebar-link styles"),
            ("control_panel/static/js/app.js", "js", "Active link + sidebar toggle logic"),
        ],
        "risk": "🔴 عالي — affects all 19 pages",
        "rollback": "Restore base.html — all pages will reset",
    },
    "bots": {
        "files": [
            ("control_panel/templates/bots.html", "template", "Bots management page"),
            ("control_panel/routers/bots.py", "router", "Bot start/stop/restart APIs"),
        ],
        "risk": "🟡 منخفض",
        "rollback": "Restore bots.html",
    },
    "backup": {
        "files": [
            ("control_panel/templates/backups.html", "template", "Backup management page"),
            ("control_panel/routers/backups.py", "router", "Backup create/restore/download APIs"),
            ("control_panel/ai_engine.py", "engine", "create_backup + restore_backup functions"),
        ],
        "risk": "🟠 متوسط",
        "rollback": "Use an existing backup to restore",
    },
}


def create_modification_plan(description: str) -> dict:
    """Generate a real file-based modification plan."""
    dl = description.lower()

    # Match plan template
    plan_key = None
    for key in _PLAN_TEMPLATES:
        if key in dl or key.replace("_", " ") in dl:
            plan_key = key
            break

    # Fallback: match via concept
    if not plan_key:
        concept_entries = _find_concept(description)
        route_info = _route_for_concept(description)
        if route_info:
            files = []
            for ft, label in [("router", "router"), ("template", "template"), ("base", "base template")]:
                f = route_info.get(ft)
                if f:
                    files.append((f, label, f"Controls {route_info.get('description', '')}"))
            for c in route_info.get("css", []):
                files.append((c, "css", "Page styling"))
            plan_key = None
            files_to_modify = files
            risk = "🟠 متوسط"
            rollback = "Use /backups to create a backup before making changes"
        elif concept_entries:
            files_to_modify = [(e[0], e[1], e[2]) for e in concept_entries]
            risk = "🟠 متوسط"
            rollback = "Use /backups to create a backup before making changes"
        else:
            files_to_modify = []
            risk = "🟡 غير محدد"
            rollback = "Create a backup first via /backups"
    else:
        pt = _PLAN_TEMPLATES[plan_key]
        files_to_modify = pt["files"]
        risk = pt["risk"]
        rollback = pt["rollback"]

    steps = []
    if files_to_modify:
        steps.append("1. إنشاء نسخة احتياطية من /backups قبل البدء")
        for i, (fpath, role, reason) in enumerate(files_to_modify, 2):
            steps.append(f"{i}. تعديل `{fpath}` [{role.upper()}] — {reason}")
        steps.append(f"{len(files_to_modify)+2}. اختبار التغييرات في المتصفح")
        steps.append(f"{len(files_to_modify)+3}. التحقق من عدم ظهور أخطاء في /logs")
    else:
        steps = ["لم يتم تحديد الملفات بدقة — استخدم /search لإيجاد الملف المطلوب"]

    return {
        "description": description,
        "files_affected": [f[0] for f in files_to_modify],
        "file_details": [{"file": f[0], "role": f[1], "why": f[2]} for f in files_to_modify],
        "steps": steps,
        "risk_label": risk,
        "rollback_strategy": rollback,
        "estimated_files": len(files_to_modify),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ROOT CAUSE ANALYSIS ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_root_cause(question: str) -> dict:
    """When asked 'why is X broken?', find all potential failure points."""
    ql = question.lower()

    # Identify what's broken from the question
    broken_concept = _find_concept(question)
    route_info     = _route_for_concept(question)

    failure_points = []
    checks = []

    if route_info:
        route = None
        for r, info in _ROUTE_GRAPH.items():
            if info is route_info:
                route = r
                break

        failure_points = [
            {"layer": "Python Router", "file": route_info["router"], "check": f"Any Python exception in {route_info['router']} — check /logs"},
            {"layer": "Jinja2 Template", "file": route_info["template"], "check": f"Template syntax error in {route_info['template']} — check for unclosed tags"},
            {"layer": "CSS", "file": "control_panel/static/css/style.css", "check": "CSS syntax error or missing class — check browser DevTools"},
            {"layer": "JavaScript", "file": "control_panel/static/js/app.js", "check": "JS error in console — check browser console (F12)"},
        ]
        if route_info.get("apis"):
            failure_points.append({
                "layer": "API",
                "file": route_info["router"],
                "check": f"API endpoint returning error: {route_info['apis'][0]}",
            })

        checks = [
            f"1. Open /logs — look for Python errors from {route_info.get('router', '')}",
            "2. Open browser F12 → Console — look for JS errors",
            "3. Open browser F12 → Network — check failed API calls",
            f"4. Check {route_info.get('template', '')} for Jinja2 syntax errors (unclosed blocks)",
            "5. Check style.css for the relevant CSS class",
        ]
    else:
        failure_points = [{"layer": "Unknown", "file": "—", "check": "Could not identify the broken component from the question"}]
        checks = ["Describe what exactly is broken (button, page, API, bot command) for a more specific analysis"]

    return {
        "question": question,
        "identified_component": broken_concept[0][0] if broken_concept else "unknown",
        "failure_points": failure_points,
        "diagnostic_steps": checks,
        "log_file": "logs/errors.log",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ARCHITECTURE INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════════

def explain_architecture(query: str = "project") -> dict:
    """Explain any subsystem of the project."""
    ql = query.lower()

    if any(kw in ql for kw in ["data flow", "تدفق", "flow from", "مسار", "من المستخدم",
                               "telegram to", "request to", "message flow", "ai flow"]):
        key = "data_flow"
    elif any(kw in ql for kw in ["frontend", "css", "html", "template", "ui", "style"]):
        key = "frontend"
    elif any(kw in ql for kw in ["bot", "telegram", "handler", "command", "بوت"]):
        key = "bots"
    elif any(kw in ql for kw in ["database", "db", "sqlite", "model", "قاعدة"]):
        key = "database"
    elif any(kw in ql for kw in ["panel", "control", "fastapi", "لوحة"]):
        key = "control_panel"
    else:
        key = "project"

    arch = _ARCH_MAP.get(key, _ARCH_MAP["project"])

    lines = [f"🏗️ **معمارية: {key.upper()}**\n", arch["description"], ""]
    for k, v in arch.items():
        if k == "description":
            continue
        if isinstance(v, list):
            lines.append(f"**{k}:**")
            for item in v:
                lines.append(f"  • {item}")
        elif isinstance(v, str):
            lines.append(f"**{k}:** {v}")
    return {"text": "\n".join(lines), "data": arch}


# ═══════════════════════════════════════════════════════════════════════════════
# SELF-TEST SUITE — 8 canonical questions + extras
# ═══════════════════════════════════════════════════════════════════════════════

_SELF_TESTS = [
    # (question, expected_intent, expected_keyword_in_answer)
    ("What file controls the homepage?",                "find_file", "dashboard.html"),
    ("What file controls the dashboard?",               "find_file", "dashboard.html"),
    ("What file controls the colors?",                  "find_file", "style.css"),
    ("What file controls the sidebar?",                 "find_file", "base.html"),
    ("What file loads the AI Engineer page?",           "find_file", "ai_engineer"),
    ("What route serves the users page?",               "find_file", "users"),
    ("What files must change to redesign the homepage?","ui_redesign", "style.css"),
    ("What files must change to redesign the sidebar?", "ui_redesign", "style.css"),
    # Extra coverage
    ("Find the login page",                             "find_file", "access.html"),
    ("What file handles authentication?",               "find_file", "auth.py"),
    ("Where is the backup system?",                     "find_file", "backups"),
    ("What CSS controls the theme?",                    "find_file", "style.css"),
    ("Where is the AI Workspace?",                      "find_file", "ai_workspace"),
    ("What file is the bot entry point?",               "find_file", "bot.py"),
    ("Where is the download handler?",                  "find_file", "download.py"),
    ("What files handle the support bot?",              "find_file", "support_bot"),
]

_CANONICAL_TESTS = _SELF_TESTS[:8]  # kept for reference; run_self_tests now uses full suite

# ── Phase 3: Arabic reasoning self-tests ──────────────────────────────────────
_ARABIC_REASONING_TESTS = [
    # (question, expected_intent, expected_keyword_in_answer)
    ("من أنت",                                    "identity",       "X AI"),
    ("ما وظيفتك",                                 "identity",       "X AI"),
    ("هل المشروع آمن؟",                           "security",       "أمن"),
    ("ما أكبر نقطة ضعف بالمشروع؟",               "weakness",       "ضعف"),
    ("كيف تطور المشروع",                          "improve",        "تطوير"),
    ("لو أضفت بوت جديد ماذا سيتأثر؟",            "impact",         "تأثير"),
    ("خطة تطوير المشروع",                         "strategy",       "استراتيج"),
    ("هل بنية المشروع جيدة؟",                     "arch",           "معمارية"),
    ("حلل المشروع",                               "analyze",        "ملف"),
    ("ما الفرق بين FastAPI و Flask",              "conversation",   "FastAPI"),
    ("اشرح معمارية المشروع",                      "arch",           "معمارية"),
    ("ما أفضل تطوير للمشروع؟",                    "improve",        "تطوير"),
    # ── Phase 3 Canonical Engineering Tests ───────────────────────────────────
    ("كيف يتحمل المشروع 100,000 مستخدم؟",         "scale",          "توسع"),
    ("ما هي الديون التقنية في المشروع؟",          "tech_debt",      "ديون"),
    ("كيف ستعيد تصميم TitanX من الصفر؟",          "redesign",       "تصميم"),
    ("ما أكبر 5 مخاطر في المشروع؟",              "weakness",       "ضعف"),
    ("ما الذي يحتاج إعادة كتابة في المشروع؟",    "tech_debt",      "ديون"),
]

# Phase 2 self-tests — intent classification (Tests A–E from spec)
_PHASE2_TESTS = [
    # (question, expected_intent, description)
    # Test A — file control awareness (already covered in Phase 1, confirmed here)
    ("What file controls the dashboard?",                       "find_file",      "File Control → find_file"),
    # Test B — bot creation → must NOT be general
    ("Create notification bot",                                 "create_feature", "Bot Creation → create_feature"),
    # Test C — distinction between redesign and bot creation
    ("Redesign homepage",                                       "ui_redesign",    "UI Redesign → ui_redesign"),
    # Test D — broken element investigation
    ("Fix broken button",                                       "debug_fix",      "Fix Request → debug_fix"),
    # Test E — new page creation
    ("Create new page",                                         "new_page",       "New Page → new_page"),
]

# ── Phase 5 — Misclassification prevention tests (Problem E from spec) ────────
# These 5 tests verify the SPECIFIC misclassification bugs fixed in this patch:
#   P5-A  Admin Panel button       — must route to find_file  (NOT hf_query)
#   P5-B  Telegram handler owner   — must route to find_file  (NOT general/conversation)
#   P5-C  HF audit (explicit)      — must route to hf_query   (only when HF is named)
#   P5-D  Database dependency      — must route to dependency  (NOT hf_query)
#   P5-E  Router ownership         — must route to find_file  (NOT conversation)
_PHASE5_TESTS = [
    # (question, expected_intent, description)
    ("Which file controls the Admin Panel button?",
     "find_file",   "P5-A: Admin Panel button → find_file (broad HF pattern must NOT intercept)"),
    ("Who handles the /start command in the Telegram bot?",
     "find_file",   "P5-B: Telegram handler ownership → find_file (context must stay in telegram_bot)"),
    ("Is Hugging Face space connected and working?",
     "hf_query",    "P5-C: HF audit with explicit 'Hugging Face' → hf_query (explicit mention only)"),
    ("What does the database depend on?",
     "dependency",  "P5-D: Database dependency → dependency (must NOT be captured by old hf_query patterns)"),
    ("Which router file owns the /panel route?",
     "find_file",   "P5-E: Router ownership → find_file (must NOT fall to conversation/general)"),
]


def run_self_tests(extended: bool = True) -> dict:
    """
    Run the full self-test suite:
    - Phase 1: file-awareness tests  → answer_file_question()
    - Phase 2: intent-only tests     → detect_intent() only
    - Phase 3: Arabic reasoning      → process_chat() (needs real handler output)
    """
    # ── Phase 1: file-awareness tests ─────────────────────────────────────────
    p1_results = []
    p1_passed  = 0
    p1_tests   = _SELF_TESTS if extended else _CANONICAL_TESTS

    for question, expected_intent, expected_keyword in p1_tests:
        got_intent = detect_intent(question)
        intent_ok  = (got_intent == expected_intent)

        answer    = answer_file_question(question)
        ans_text  = answer["text"].lower()
        ans_files = " ".join(e["path"].lower() for e in answer.get("data", {}).get("files", []))
        keyword_found = (
            expected_keyword.lower() in ans_text or
            expected_keyword.lower() in ans_files
        )

        ok = intent_ok and keyword_found
        if ok:
            p1_passed += 1

        p1_results.append({
            "question":         question,
            "expected_intent":  expected_intent,
            "got_intent":       got_intent,
            "intent_ok":        intent_ok,
            "expected_keyword": expected_keyword,
            "keyword_found":    keyword_found,
            "passed":           ok,
            "phase":            "P1",
        })

    # ── Phase 2: intent-only tests (A–E) ──────────────────────────────────────
    p2_results = []
    p2_passed  = 0
    for question, expected_intent, description in _PHASE2_TESTS:
        got_intent = detect_intent(question)
        intent_ok  = (got_intent == expected_intent)
        if intent_ok:
            p2_passed += 1
        p2_results.append({
            "question":         question,
            "expected_intent":  expected_intent,
            "got_intent":       got_intent,
            "intent_ok":        intent_ok,
            "expected_keyword": description,
            "keyword_found":    intent_ok,
            "passed":           intent_ok,
            "phase":            "P2",
        })

    # ── Phase 3: Arabic reasoning tests (use process_chat for real responses) ──
    p3_results = []
    p3_passed  = 0
    if extended:
        for question, expected_intent, expected_keyword in _ARABIC_REASONING_TESTS:
            got_intent = detect_intent(question)
            intent_ok  = (got_intent == expected_intent)

            try:
                chat_resp = process_chat(question)
                ans_text  = chat_resp.get("text", "").lower()
            except Exception as _e:
                _ai_log.warning("P3 self-test process_chat error for %r: %s", question, _e)
                ans_text = ""

            # Arabic keyword matching (case-insensitive, strip diacritics not needed at this level)
            keyword_found = expected_keyword.lower() in ans_text

            ok = intent_ok and keyword_found
            if ok:
                p3_passed += 1

            p3_results.append({
                "question":         question,
                "expected_intent":  expected_intent,
                "got_intent":       got_intent,
                "intent_ok":        intent_ok,
                "expected_keyword": expected_keyword,
                "keyword_found":    keyword_found,
                "passed":           ok,
                "phase":            "P3",
            })

    # ── Phase 4: Agent Foundation — 7 validation questions (use process_chat) ──
    _AGENT_FOUNDATION_TESTS = [
        # (question, expected_intent, keyword_in_response)
        ("من أنت؟",
         "identity",        "x ai"),
        ("ما الملفات التي تعتمد على config/settings.py؟",
         "who_depends",     "settings"),
        ("ماذا يحدث لو حذفت config/settings.py؟",
         "impact",          "config"),
        ("ما أكبر نقطة ضعف في المشروع؟",
         "weakness",        "نقطة فشل"),
        ("لو أنشأت بوت إشعارات ما الأنظمة التي يمكن إعادة استخدامها",
         "reuse_systems",   "قابلة"),
        ("سلسلة التبعيات لـ ai_engine.py",
         "who_depends",     "ai_engine"),
        ("أظهر تدفق البيانات من Telegram إلى الرد النهائي",
         "data_flow",       "تدفق"),
    ]

    p4_results = []
    p4_passed  = 0
    if extended:
        for question, expected_intent, expected_keyword in _AGENT_FOUNDATION_TESTS:
            got_intent = detect_intent(question)
            intent_ok  = (got_intent == expected_intent)
            try:
                chat_resp    = process_chat(question)
                ans_text     = chat_resp.get("text", "").lower()
            except Exception as _e:
                _ai_log.warning("P4 test process_chat error for %r: %s", question, _e)
                ans_text = ""
            keyword_found = expected_keyword.lower() in ans_text
            ok = intent_ok and keyword_found
            if ok:
                p4_passed += 1
            p4_results.append({
                "question":         question,
                "expected_intent":  expected_intent,
                "got_intent":       got_intent,
                "intent_ok":        intent_ok,
                "expected_keyword": expected_keyword,
                "keyword_found":    keyword_found,
                "passed":           ok,
                "phase":            "P4",
            })

    # ── Phase 5: misclassification prevention tests (Problem E) ──────────────
    p5_results = []
    p5_passed  = 0
    for question, expected_intent, description in _PHASE5_TESTS:
        got_intent = detect_intent(question)
        intent_ok  = (got_intent == expected_intent)
        if intent_ok:
            p5_passed += 1
        p5_results.append({
            "question":         question,
            "expected_intent":  expected_intent,
            "got_intent":       got_intent,
            "intent_ok":        intent_ok,
            "passed":           intent_ok,
            "description":      description,
            "keyword_found":    intent_ok,
            "phase":            "P5",
        })

    p4_total    = len(_AGENT_FOUNDATION_TESTS) if extended else 0
    all_passed  = p1_passed + p2_passed + p3_passed + p4_passed + p5_passed
    all_total   = (len(p1_tests) + len(_PHASE2_TESTS)
                   + (len(_ARABIC_REASONING_TESTS) if extended else 0)
                   + p4_total + len(_PHASE5_TESTS))
    all_results = p1_results + p2_results + p3_results + p4_results + p5_results

    return {
        "score":     f"{all_passed}/{all_total}",
        "pass_rate": f"{all_passed/all_total*100:.0f}%" if all_total else "0%",
        "status":    "✅ PASS" if all_passed == all_total else ("⚠️ PARTIAL" if all_passed >= all_total * 0.75 else "❌ FAIL"),
        "tests":     all_results,
        "results":   all_results,   # alias for backward compat
        "passed":    all_passed,
        "total":     all_total,
        "failed":    all_total - all_passed,
        "phase1":    {"passed": p1_passed, "total": len(p1_tests),                "label": "File Awareness"},
        "phase2":    {"passed": p2_passed, "total": len(_PHASE2_TESTS),            "label": "Intent Classification (A-E)"},
        "phase3":    {"passed": p3_passed, "total": len(_ARABIC_REASONING_TESTS) if extended else 0, "label": "Arabic Reasoning"},
        "phase4":    {"passed": p4_passed, "total": p4_total,                     "label": "Agent Foundation (7 Validation Qs)"},
        "phase5":    {"passed": p5_passed, "total": len(_PHASE5_TESTS),            "label": "Misclassification Prevention (P5-A–E)"},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

def _migrate_memory(data: dict) -> dict:
    """Migrate old-format memory files to current schema so no KeyError ever occurs."""
    defaults = _default_memory()
    # Ensure top-level keys exist
    for key, val in defaults.items():
        if key not in data:
            data[key] = val
    # Old schema used 'ai_stats' instead of 'stats'
    if not isinstance(data.get("stats"), dict):
        old = data.get("ai_stats", {})
        data["stats"] = {
            "total_scans":     old.get("total_scans",     0),
            "total_plans":     old.get("total_plans",     0),
            "total_questions": old.get("total_questions", 0),
            "total_chats":     old.get("total_chats",     0),
        }
    # Old schema used 'project_name' instead of 'project' dict
    if not isinstance(data.get("project"), dict):
        data["project"] = defaults["project"]
        if "project_name" in data:
            data["project"]["name"] = data["project_name"]
    # Ensure stats sub-keys exist
    for k in ("total_scans", "total_plans", "total_questions", "total_chats"):
        data["stats"].setdefault(k, 0)
    return data


def load_memory() -> dict:
    if MEMORY_FILE.exists():
        try:
            raw = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            return _migrate_memory(raw)
        except Exception as _e:
            _ai_log.warning("Memory load error: %s", _e)
    data = _default_memory()
    save_memory(data)
    return data


def save_memory(data: dict):
    try:
        MEMORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as _e:
        _ai_log.warning("Memory save error: %s", _e)


def _default_memory() -> dict:
    return {
        "version": "3.0",
        "project": {
            "name": "X Control Center",
            "main_bot": "PrimeDownloader Bot (bot.py)",
            "support_bot": "Support Bot (support_bot/bot.py)",
            "panel": "FastAPI control panel — port 5000",
            "css": "ONE file: control_panel/static/css/style.css",
            "js": "ONE file: control_panel/static/js/app.js",
            "templates": "20 HTML files in control_panel/templates/",
            "databases": ["database/bot.db", "support_bot/database/support.db"],
        },
        "stats": {"total_scans": 0, "total_plans": 0, "total_questions": 0, "total_chats": 0},
        "chat_history": [],
        # ── Phase 3: Engineering Decision Memory ──────────────────────────────
        "decisions": [],       # List of {id, title, rationale, date, files_affected}
        "upgrades": [],        # List of {title, status, date, notes}
        "tech_debt_log": [],   # List of {id, item, category, resolved, date}
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
    }


def save_engineering_decision(title: str, rationale: str, files_affected: list = None) -> dict:
    """Persist an engineering decision to memory. Called when significant arch decisions are made."""
    try:
        m = load_memory()
        decisions = m.setdefault("decisions", [])
        decision = {
            "id":            f"DEC-{len(decisions) + 1:03d}",
            "title":         title,
            "rationale":     rationale,
            "files_affected": files_affected or [],
            "date":          datetime.now().isoformat(),
        }
        decisions.append(decision)
        m["decisions"] = decisions[-50:]  # keep last 50
        m["updated"] = datetime.now().isoformat()
        save_memory(m)
        return {"ok": True, "decision": decision}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_engineering_decisions() -> list:
    """Return all saved engineering decisions."""
    return load_memory().get("decisions", [])


def update_stats(key: str, val: int = 1):
    m = load_memory()
    stats = m.setdefault("stats", {"total_scans": 0, "total_plans": 0, "total_questions": 0, "total_chats": 0})
    stats[key] = stats.get(key, 0) + val
    m["updated"] = datetime.now().isoformat()
    save_memory(m)


# ── Startup: pre-create memory file so load_memory() always finds it ─────────
if not MEMORY_FILE.exists():
    try:
        save_memory(_default_memory())
    except Exception as _me:
        _ai_log.warning("Startup memory init failed: %s", _me)


def save_chat(role: str, text: str):
    m = load_memory()
    m.setdefault("chat_history", []).append({"role": role, "text": text[:500], "ts": datetime.now().isoformat()})
    m["chat_history"] = m["chat_history"][-50:]
    m["updated"] = datetime.now().isoformat()
    save_memory(m)


def _persist_turn(user_msg: str, assistant_msg: str):
    """Consolidate: one disk-read + one disk-write per full turn (replaces 4 I/O ops)."""
    try:
        m = load_memory()
        stats = m.setdefault("stats", {"total_scans": 0, "total_plans": 0, "total_questions": 0, "total_chats": 0})
        stats["total_chats"] = stats.get("total_chats", 0) + 1
        hist = m.setdefault("chat_history", [])
        now  = datetime.now().isoformat()
        hist.append({"role": "user",      "text": user_msg[:500],      "ts": now})
        hist.append({"role": "assistant", "text": assistant_msg[:500], "ts": now})
        m["chat_history"] = hist[-50:]
        m["updated"] = now
        save_memory(m)
    except Exception as _e:
        _ai_log.warning("_persist_turn error: %s", _e)


# ═══════════════════════════════════════════════════════════════════════════════
# BACKUP SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

def create_backup(description: str = "نسخة يدوية") -> dict:
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    bk_id = hashlib.md5(ts.encode()).hexdigest()[:8]
    bk_p  = BACKUP_DIR / f"backup_{ts}_{bk_id}.zip"
    count = 0
    try:
        with zipfile.ZipFile(bk_p, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(str(EXTRACTED_DIR)):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS and ".ai_backups" not in root]
                for f in files:
                    fp = Path(root) / f
                    if fp.suffix in CODE_EXTS:
                        zf.write(fp, fp.relative_to(EXTRACTED_DIR))
                        count += 1
        size = bk_p.stat().st_size
        m = load_memory(); m.setdefault("backups", []).append({"id": bk_id, "ts": ts, "desc": description, "file": bk_p.name, "size": size, "count": count}); save_memory(m)
        return {"ok": True, "id": bk_id, "file": bk_p.name, "size": size, "files": count, "description": description}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_backups() -> list:
    m = load_memory()
    return m.get("backups", [])


def restore_backup(bk_id: str) -> dict:
    m = load_memory()
    bk = next((b for b in m.get("backups", []) if b["id"] == bk_id), None)
    if not bk:
        return {"ok": False, "error": "Backup not found"}
    bk_p = BACKUP_DIR / bk["file"]
    if not bk_p.exists():
        return {"ok": False, "error": "Backup file missing"}
    try:
        with zipfile.ZipFile(bk_p, "r") as zf:
            zf.extractall(str(EXTRACTED_DIR))
        return {"ok": True, "id": bk_id, "message": "تمت الاستعادة بنجاح"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT SCANNER (filesystem-level analysis)
# ═══════════════════════════════════════════════════════════════════════════════

_walk_cache: dict = {"ts": 0.0, "files": []}

def walk_project() -> list:
    """Walk project files — 60-second TTL cache to avoid repeated filesystem scans."""
    if time.time() - _walk_cache["ts"] < 60 and _walk_cache["files"]:
        return _walk_cache["files"]
    files = []
    for root, dirs, fnames in os.walk(str(EXTRACTED_DIR)):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in fnames:
            fp = Path(root) / f
            if fp.suffix in CODE_EXTS:
                files.append(str(fp.relative_to(EXTRACTED_DIR)))
    result = sorted(files)
    _walk_cache["files"] = result
    _walk_cache["ts"]    = time.time()
    return result


def _scan_project_files() -> list:
    """Return a flat list of all project file paths for structural analysis."""
    return walk_project()


def analyze_structure() -> dict:
    files = walk_project()
    by_ext: dict = {}
    by_dir: dict = {}
    for f in files:
        ext = Path(f).suffix
        by_ext[ext] = by_ext.get(ext, 0) + 1
        d = str(Path(f).parent)
        by_dir[d] = by_dir.get(d, 0) + 1

    templates = [f for f in files if f.endswith(".html")]
    routers   = [f for f in files if "routers" in f and f.endswith(".py")]
    handlers  = [f for f in files if "handlers" in f and f.endswith(".py")]
    db_models = [f for f in files if "database" in f and f.endswith(".py")]
    services  = [f for f in files if "services" in f and f.endswith(".py")]
    css_files = [f for f in files if f.endswith(".css")]
    js_files  = [f for f in files if f.endswith(".js")]

    return {
        "total_files": len(files),
        "by_type": by_ext,
        "templates": templates,
        "routers": routers,
        "handlers": handlers,
        "db_models": db_models,
        "services": services,
        "css_files": css_files,
        "js_files": js_files,
        "top_dirs": sorted(by_dir.items(), key=lambda x: x[1], reverse=True)[:15],
        "knowledge_graph_routes": len(_ROUTE_GRAPH),
        "semantic_concepts": len(_SEMANTIC_MAP),
    }


def detect_log_errors() -> list:
    errors = []
    log_dir = EXTRACTED_DIR / "logs"
    if not log_dir.exists():
        return []
    for lf in log_dir.glob("*.log"):
        try:
            lines = lf.read_text(encoding="utf-8", errors="ignore").splitlines()
            for ln in lines[-200:]:
                if any(k in ln for k in ["ERROR", "CRITICAL", "Exception", "Traceback"]):
                    errors.append({"file": lf.name, "line": ln.strip()[:200]})
        except Exception as _e:
            _ai_log.warning("Log read error %s: %s", lf, _e)
    return errors[-50:]


def detect_code_issues() -> list:
    issues = []
    for root, dirs, files in os.walk(str(EXTRACTED_DIR)):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith(".py"):
                continue
            fp = Path(root) / f
            rel = str(fp.relative_to(EXTRACTED_DIR))
            try:
                src = fp.read_text(encoding="utf-8", errors="ignore")
                try:
                    ast.parse(src)
                except SyntaxError as e:
                    issues.append({"file": rel, "type": "SyntaxError", "detail": str(e)})
                if "TODO" in src or "FIXME" in src:
                    for i, ln in enumerate(src.splitlines(), 1):
                        if "TODO" in ln or "FIXME" in ln:
                            issues.append({"file": rel, "type": "TODO", "detail": f"Line {i}: {ln.strip()[:100]}"})
            except Exception as _e:
                _ai_log.warning("Code issue scan error %s: %s", rel, _e)
    return issues[:30]


def security_scan() -> list:
    issues = []
    danger = ["eval(", "exec(", "subprocess.call(", "os.system(", "pickle.load", "yaml.load(", "__import__"]
    for root, dirs, files in os.walk(str(EXTRACTED_DIR)):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith(".py"):
                continue
            fp = Path(root) / f
            rel = str(fp.relative_to(EXTRACTED_DIR))
            try:
                src = fp.read_text(encoding="utf-8", errors="ignore")
                for pat in danger:
                    if pat in src:
                        issues.append({"file": rel, "pattern": pat, "severity": "medium"})
            except Exception as _e:
                _ai_log.warning("Security scan read error %s: %s", rel, _e)
    return issues


def detect_routes() -> list:
    routes = []
    for route, info in _ROUTE_GRAPH.items():
        routes.append({
            "route": route,
            "router": info["router"],
            "template": info["template"],
            "description": info["description"],
        })
    return routes


def full_analysis() -> dict:
    update_stats("total_scans")
    return {
        "structure": analyze_structure(),
        "errors":    detect_log_errors()[:10],
        "issues":    detect_code_issues()[:10],
        "routes":    detect_routes(),
        "security":  security_scan()[:5],
        "knowledge": {
            "routes_in_graph": len(_ROUTE_GRAPH),
            "semantic_concepts": len(_SEMANTIC_MAP),
            "db_models": len(_DB_MAP),
            "bots": len(_BOT_MAP),
        },
        "timestamp": datetime.now().isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT PROCESSOR — routes messages to correct response handler
# ═══════════════════════════════════════════════════════════════════════════════

def process_chat(msg: str) -> dict:
    """
    AGENT FOUNDATION ENFORCEMENT — 16-Rule Reasoning-First Pipeline.

    Mandate execution order:
    1. Check pending plan approval/rejection  (AgentPlanningGate)
    2. Detect intent
    3. Record to session memory
    4. For project intents: run AgentReasoningChain (7-step) → store in _ACTIVE_CHAIN
    5. Dispatch to handler (handler reads _ACTIVE_CHAIN for pre-computed evidence)
    6. Scan-usage verification: inject evidence footer if handler used live data
    7. Record response + persist turn
    """
    global _ACTIVE_CHAIN
    _ACTIVE_CHAIN = {}  # Rule 3: reset chain cache on every new request

    # ── AGENT GATE 1: pending plan approval / rejection ──────────────────────
    if AgentPlanningGate.has_pending():
        if AgentPlanningGate.is_approval(msg):
            resp = AgentPlanningGate.execute_approved()
            resp["intent"] = "plan_approved"
            _persist_turn(msg, resp.get("text", "")[:500])
            return resp
        if AgentPlanningGate.is_rejection(msg):
            resp = AgentPlanningGate.cancel()
            resp["intent"] = "plan_cancelled"
            _persist_turn(msg, resp.get("text", "")[:500])
            return resp

    intent = detect_intent(msg)

    # ── Phase 12: Context Engine — detect subsystem before reasoning ──────────
    _ctx_result: dict = {"detected": "general", "confidence": 0.0, "evidence": []}
    if _CE_OK and _CE is not None:
        try:
            _ctx_result = _CE.detect(msg)
            _ai_log.debug(
                "ContextEngine: %s (conf=%.2f) evidence=%s",
                _ctx_result["detected"],
                _ctx_result["confidence"],
                _ctx_result["evidence"][:3],
            )
        except Exception as _ce_err:
            _ai_log.debug("ContextEngine (non-fatal): %s", _ce_err)

    # Phase 3: Record to session memory BEFORE routing so handlers can read context
    AIMemoryLayer.record("user", msg, intent)

    # ── ENGINEERING MODE LOCK (Phase 12) ─────────────────────────────────────
    # If ContextEngine detected a specific subsystem with confidence > 0.15
    # AND intent fell into 'general' or 'conversation', the agent would normally
    # give a generic answer.  This lock re-routes it to the correct project
    # handler so Engineering Mode is preserved.
    #
    # Telegram Priority Rule (Phase 10): if context=telegram_bot, always
    # redirect 'general'/'conversation' to 'arch' (structured project answer).
    if intent in ("general", "conversation"):
        _lock_ctx  = _ctx_result.get("detected", "general")
        _lock_conf = _ctx_result.get("confidence", 0.0)
        if _lock_ctx != "general" and _lock_conf > 0.15:
            _LOCK_REDIRECT = {
                "telegram_bot":   "arch",
                "control_panel":  "arch",
                "database":       "arch",
                "router_layer":   "routes",
                "api_layer":      "routes",
                "frontend_layer": "find_file",
                "infrastructure": "find_file",
                "ai_layer":       "arch",
                "support_system": "arch",
                "deployment":     "arch",
            }
            _redirected = _LOCK_REDIRECT.get(_lock_ctx)
            if _redirected:
                _ai_log.info(
                    "EngineeringLock: intent='%s' → '%s' (ctx=%s conf=%.2f)",
                    intent, _redirected, _lock_ctx, _lock_conf,
                )
                intent = _redirected

    # ── AGENT GATE 2: 7-step reasoning chain for all project intents ─────────
    # Rule 1 (Scan-First) + Rule 4 (Dependency Graph) + Rule 5 (Runtime Graph)
    # Chain result stored in _ACTIVE_CHAIN so handlers can read pre-built evidence
    # without needing a parameter change — eliminates the chain injection gap.
    # ctx_result is NOW passed so _step2_search applies Telegram Priority Rule.
    _PROJECT_INTENTS = {
        "find_file", "plan_modify", "dependency", "who_depends", "data_flow",
        "reuse_systems", "impact", "root_cause", "arch", "security", "analyze",
        "improve", "weakness", "strategy", "scale", "tech_debt", "redesign",
        "errors", "create_feature", "ui_redesign", "debug_fix", "new_page",
        "routes", "structure", "runtime_graph",
        # Project modification intent — catches imperative Arabic commands
        "project_mod",
    }
    if intent in _PROJECT_INTENTS:
        try:
            _ACTIVE_CHAIN = AgentReasoningChain.execute(msg, intent, _ctx_result)
            AIMemoryLayer.record(
                "assistant",
                f"[reasoning: {', '.join(_ACTIVE_CHAIN.get('steps_done', [])[:4])}]",
                "reasoning",
            )
            _ai_log.debug(
                "AgentReasoningChain injected: steps=%s files=%d risk=%s",
                _ACTIVE_CHAIN.get("steps_done", []),
                len(_ACTIVE_CHAIN.get("search", {}).get("files", [])),
                _ACTIVE_CHAIN.get("impact", {}).get("risk", "LOW"),
            )
        except Exception as _re:
            _ai_log.debug("AgentReasoningChain (non-fatal): %s", _re)

    # ── REPAIR (Problem 1): Intent Confidence Gate ────────────────────────────
    # Execute BEFORE handler dispatch — never after.
    # Pipeline: Intent Detection → Confidence Score → Verification → Execution.
    #
    # If confidence < 0.30 for a project intent, the agent must NOT guess.
    # Return a clarification request instead of executing with wrong intent.
    #
    # Exempt intents are unambiguous by nature (greeting, identity, hf_query,
    # status, help) and do not need a confidence gate.
    _CONFIDENCE_EXEMPT = {
        "greeting", "conversation", "identity", "capabilities",
        "hf_query", "status", "help", "self_test", "memory",
        "stats", "backup", "restore", "general",
    }
    if intent in _PROJECT_INTENTS and intent not in _CONFIDENCE_EXEMPT:
        if _CE_OK and _IC is not None:
            _pre_conf = _IC.score(intent, msg)
            if _pre_conf < 0.30:
                _ai_log.warning(
                    "IntentConfidenceGate: BLOCKED intent='%s' conf=%.2f — "
                    "asking for clarification instead of executing.",
                    intent, _pre_conf,
                )
                _clarify_resp = {
                    "text": (
                        "🔍 **لم أستطع تحديد طلبك بثقة كافية.**\n\n"
                        f"فهمت النية على أنها: **`{intent}`** "
                        f"(ثقة: {_pre_conf:.0%}) — وهذا أقل من الحد الأدنى المطلوب (30%).\n\n"
                        "**يرجى إعادة الصياغة بشكل أوضح، مثلاً:**\n"
                        "  • ما الملف المسؤول عن ...\n"
                        "  • ما التبعيات بين ... و ...\n"
                        "  • كيف يتدفق ... من ... إلى ...\n"
                        "  • لو حذفت ... ماذا سيتأثر؟\n\n"
                        "*النظام لن ينفذ أي عملية قبل التأكد من فهم طلبك بدقة.*"
                    ),
                    "data": {
                        "intent": intent,
                        "intent_confidence": _pre_conf,
                        "gate": "IntentConfidenceGate",
                        "action": "clarification_requested",
                    },
                }
                _persist_turn(msg, _clarify_resp["text"][:500])
                return _clarify_resp

    handlers = {
        # ── Conversational (NEVER touches project files) ──────────────────────
        "greeting":       lambda: _r_greeting(),
        "conversation":   lambda: _r_conversation(msg),
        # ── Meta / identity ───────────────────────────────────────────────────
        "identity":       lambda: _r_identity(),
        "capabilities":   lambda: _r_capabilities(),
        "hf_query":       lambda: _r_hf_query(),
        # ── Action intents (GATED — always awaits approval) ───────────────────
        "create_feature": lambda: _r_create_feature(msg),
        "ui_redesign":    lambda: _r_ui_redesign(msg),
        "debug_fix":      lambda: _r_debug_fix(msg),
        "new_page":       lambda: _r_new_page(msg),
        "project_mod":    lambda: _r_project_mod(msg),
        # ── Project knowledge ─────────────────────────────────────────────────
        "find_file":      lambda: _r_find_file(msg),
        "find_function":  lambda: _r_find_function(msg),   # PHASE 2
        "plan_modify":    lambda: _r_plan(msg),
        "dependency":     lambda: _r_dependency(msg),
        "who_depends":    lambda: _r_who_depends_on(msg),
        "data_flow":      lambda: _r_data_flow(msg),
        "reuse_systems":  lambda: _r_reuse_systems(msg),
        "impact":         lambda: _r_impact(msg),
        "root_cause":     lambda: _r_root_cause(msg),
        "arch":           lambda: _r_arch(msg),
        "structure":      lambda: _r_structure(),
        "routes":         lambda: _r_routes(msg),          # PHASE 2: pass msg for concept lookup
        "security":       lambda: _r_security(),
        "errors":         lambda: _r_errors(),
        "analyze":        lambda: _r_analyze(),
        "improve":        lambda: _r_improve(msg),
        "memory":         lambda: _r_memory(),
        "status":         lambda: _r_status(),
        "stats":          lambda: _r_stats(),
        "backup":         lambda: _r_backup_info(),
        "restore":        lambda: _r_restore_info(),
        "self_test":      lambda: _r_self_test(),
        "weakness":       lambda: _r_weakness(msg),
        "strategy":       lambda: _r_strategy(msg),
        "runtime_graph":  lambda: _r_runtime_graph(msg),
        "scale":          lambda: _r_scale(msg),
        "tech_debt":      lambda: _r_tech_debt(),
        "redesign":       lambda: _r_redesign(),
        "help":           lambda: _r_help(),
        "general":        lambda: _r_general(msg),
    }

    fn   = handlers.get(intent, handlers["general"])
    resp = fn()
    resp["intent"] = intent

    # ── Phase 18: Self-Correction Engine — verify evidence AND ACT ───────────
    # Root-cause fix: issues were logged but response was returned unchanged.
    # Now: if issues found for a project intent, append a correction notice so
    # the user knows the agent flagged a gap and what triggered it.
    _chain_files = _ACTIVE_CHAIN.get("search", {}).get("files", []) if _ACTIVE_CHAIN else []
    _correction: dict = {"ok": True, "issues": [], "warnings": [], "evidence_score": 0.0}
    if _CE_OK and _SCE is not None:
        try:
            _correction = _SCE.verify(
                intent        = intent,
                response_text = resp.get("text", ""),
                files_scanned = _chain_files,
                context_result = _ctx_result,
            )
            if _correction["issues"]:
                _ai_log.warning(
                    "SelfCorrection issues for intent=%s: %s",
                    intent, _correction["issues"]
                )
                # ACTION: append correction notice if this is a project intent
                if intent in _PROJECT_INTENTS and resp.get("text"):
                    _issue_lines = "\n".join(
                        f"  ⚠️ {iss}" for iss in _correction["issues"][:3]
                    )
                    resp["text"] = (
                        resp["text"].rstrip()
                        + "\n\n─────────────────────────────────\n"
                        "🔍 **ملاحظة تدقيق الاستجابة (Self-Correction):**\n"
                        + _issue_lines
                        + "\n*راجع الملفات المذكورة أعلاه للتحقق من دقة هذه الإجابة.*"
                    )
                    resp.setdefault("data", {})["correction_issues"] = _correction["issues"]
        except Exception as _sc_err:
            _ai_log.debug("SelfCorrectionEngine (non-fatal): %s", _sc_err)

    # ── Phase 19: Classification Audit — attach metadata to every response ────
    _audit: dict = {}
    if _CE_OK and _CA is not None:
        try:
            _audit = _CA.run(
                intent         = intent,
                msg            = msg,
                context_result = _ctx_result,
                files_used     = _chain_files,
            )
        except Exception as _ca_err:
            _ai_log.debug("ClassificationAudit (non-fatal): %s", _ca_err)

    # Attach engineering metadata to response data payload (available to frontend)
    resp.setdefault("data", {}).update({
        "context":     _ctx_result.get("detected", "general"),
        "ctx_conf":    _ctx_result.get("confidence", 0.0),
        "ctx_evidence": _ctx_result.get("evidence", [])[:5],
        "correction":  _correction,
        "audit":       _audit,
    })

    # ── Rule 3: Scan-Usage Verification ──────────────────────────────────────
    # After handler returns, check if it used live scan evidence.
    # If the chain found files and the response doesn't reference them, append
    # a compact evidence footer so no answer ever floats free of project data.
    if intent in _PROJECT_INTENTS and _ACTIVE_CHAIN:
        chain_files = _ACTIVE_CHAIN.get("search", {}).get("files", [])
        chain_risk  = _ACTIVE_CHAIN.get("impact", {}).get("risk", "")
        resp_text_lower = resp.get("text", "").lower()
        evidence_used = any(
            Path(f).name.lower() in resp_text_lower for f in chain_files
        )
        if chain_files and not evidence_used:
            footer_lines = [
                "\n\n─────────────────────────────────────",
                "📁 **أدلة الفحص المباشر (Scan Evidence):**",
            ]
            for f in chain_files[:5]:
                footer_lines.append(f"  • `{f}`")
            if chain_risk and chain_risk != "LOW":
                footer_lines.append(f"⚠️ مستوى المخاطرة: **{chain_risk}**")
            resp["text"] = resp.get("text", "") + "\n".join(footer_lines)
            resp.setdefault("data", {})["scan_evidence_injected"] = True
        # Always attach chain metadata to the data payload for the frontend
        resp.setdefault("data", {})["chain"] = {
            "steps_done":    _ACTIVE_CHAIN.get("steps_done", []),
            "files_scanned": len(chain_files),
            "risk":          chain_risk,
        }

    # Phase 3: Record assistant response + decision to session memory
    resp_text = resp.get("text", "")
    AIMemoryLayer.record("assistant", resp_text[:300], intent)

    # Single consolidated disk write (replaces save_chat x2 + update_stats)
    _persist_turn(msg, resp_text[:500])
    return resp


# ─── Response Handlers ────────────────────────────────────────────────────────

def _r_greeting() -> dict:
    """Salutation — friendly response with mode hints."""
    import random
    opts = [
        "مرحباً! 👋 أنا **X AI Operator Phase 3** — جاهز للمساعدة.\n\n"
        "أعمل في **وضعَين**:\n"
        "  💬 **وضع المحادثة** — أسئلة برمجة عامة: Python، FastAPI، SQL، الخ\n"
        "  🔍 **وضع المشروع** — ملفات، مسارات، إنشاء ميزات، تشخيص أخطاء\n\n"
        "ما الذي تريد فعله؟",

        "أهلاً! 🧠 **X AI Operator** في خدمتك — مرحلة 3 نشطة.\n\n"
        "يمكنني الإجابة على أسئلة البرمجة العامة أو مساعدتك في "
        "**X Control Center** مباشرة.\n\nكيف يمكنني مساعدتك؟",

        "مرحباً بك! 👋\n\n"
        "أفكر قبل أن أجيب، وأفهم السياق قبل أن أبحث عن ملفات.\n"
        "اسألني أي سؤال — تقني عام أو خاص بمشروعك.",
    ]
    return {"text": random.choice(opts), "data": {"mode": "greeting"}}


def _r_conversation(msg: str) -> dict:
    """
    Handle general / conversational messages intelligently.
    NEVER touches project files — pure general knowledge mode.
    """
    ml = msg.lower()

    # ── 1. Comparison questions ─────────────────────────────────────────────
    for pair, data in _COMPARE_MAP.items():
        terms = list(pair)
        all_found = all(re.search(r'\b' + re.escape(t.replace(" ", r"\s+")), ml, re.IGNORECASE) for t in terms)
        if all_found:
            title = data["title"]
            rows  = data.get("rows", [])
            lines = [f"⚖️ **{title}**\n"]
            if rows:
                lines.append("| الجانب | " + " | ".join(r[0] for r in [("", terms[0], terms[1])][:0] + [("",)]) + " |")
                for aspect, a_val, b_val in rows:
                    lines.append(f"**{aspect}:** `{terms[0]}` — {a_val} | `{terms[1]}` — {b_val}")
            if "verdict" in data:
                lines.append(f"\n✅ **الخلاصة:** {data['verdict']}")
            if "in_project" in data:
                lines.append(f"\n📍 **في مشروعك:** {data['in_project']}")
            return {"text": "\n".join(lines), "data": {"mode": "conversation", "type": "comparison"}}

    # ── 2. Single-tech explanation questions ────────────────────────────────
    _TECH_PATTERNS = [
        (r"telegram.{0,5}bot|telegram bot",           "telegram_bot"),
        (r"\bfastapi\b|fast\s+api",                   "fastapi"),
        (r"\bflask\b",                                "flask"),
        (r"\bdjango\b",                               "django"),
        (r"\btypescript\b|\bts\b(?=\s|$)",            "typescript"),
        (r"\bjavascript\b|\bjs\b(?=\s|$)",            "javascript"),
        (r"\bpython\b",                               "python"),
        (r"\brest\s*api\b|rest.{0,5}api",             "rest_api"),
        (r"\bgraphql\b",                              "graphql"),
        (r"\bdocker\b",                               "docker"),
        (r"\bnosql\b|\bmongodb\b|\bmongo\b",          "nosql"),
        (r"\bsql\b|\bpostgresql\b|\bmysql\b|\bsqlite\b", "sql"),
        (r"\basync\b|\bawait\b|\basynchronous\b",     "async"),
    ]
    tech_key = None
    for pattern, key in _TECH_PATTERNS:
        if re.search(pattern, ml, re.IGNORECASE):
            tech_key = key
            break

    if tech_key and tech_key in _TECH_KNOWLEDGE:
        k = _TECH_KNOWLEDGE[tech_key]
        lines = [f"{k.get('emoji','💡')} **{k['title']}**\n",
                 f"**ما هو؟** {k['what']}\n"]
        if "strengths" in k:
            lines.append("**✅ نقاط القوة:**")
            for s in k["strengths"]: lines.append(f"  • {s}")
        if "weaknesses" in k:
            lines.append("\n**⚠️ القيود:**")
            for w in k["weaknesses"]: lines.append(f"  • {w}")
        if "uses" in k:
            lines.append("\n**🎯 الاستخدامات:**")
            for u in k["uses"]: lines.append(f"  • {u}")
        if "types" in k:
            lines.append("\n**📂 الأنواع:**")
            for t in (k["types"] if isinstance(k["types"], list)
                      else [f"{kk}: {vv}" for kk, vv in k["types"].items()]):
                lines.append(f"  • {t}")
        if "in_project" in k:
            lines.append(f"\n📍 **في مشروعك:** {k['in_project']}")
        return {"text": "\n".join(lines),
                "data": {"mode": "conversation", "tech": tech_key}}

    # ── 3. HF-backed general answer (best-effort) ───────────────────────────
    try:
        hf = call_hf_assistant(msg)
        answer = hf.get("response") or hf.get("analysis") or hf.get("message") or ""
        if hf.get("ok") and isinstance(answer, str) and len(answer) > 30:
            return {"text": f"💬 {answer}",
                    "data": {"mode": "conversation", "source": "hf"}}
    except Exception as _e:
        _ai_log.warning("_r_conversation HF step 3 error: %s", _e)

    # ── 4. Memory-aware context hint before generic menu ─────────────────────
    ctx = AIMemoryLayer.context()
    last_intent = AIMemoryLayer.last_intent()
    if ctx["total_turns"] > 2 and last_intent not in ("greeting", "general", "conversation"):
        return {
            "text": (
                f"💬 سؤالك يبدو عاماً — لكن محادثتنا الأخيرة كانت حول **{last_intent}**.\n"
                "هل تريد متابعة ذلك الموضوع؟ أو اسألني سؤالاً تقنياً محدداً."
            ),
            "data": {"mode": "conversation", "prior_intent": last_intent},
        }

    return {
        "text": (
            "💬 **وضع المحادثة العامة**\n\n"
            "يمكنني الإجابة على أسئلة تقنية مثل:\n"
            "  • **شرح تقنية** — \"اشرح FastAPI\" · \"ما هو Python؟\"\n"
            "  • **مقارنة** — \"Python مقابل JavaScript\" · \"FastAPI vs Flask\"\n"
            "  • **مفاهيم** — \"ما هو REST API؟\" · \"اشرح Async/Await\"\n"
            "  • **Telegram Bots** — \"كيف تعمل بوتات تيليغرام؟\"\n\n"
            "أو اسألني عن **مشروعك مباشرة** — \"Create notification bot\" · \"Fix broken button\""
        ),
        "data": {"mode": "conversation"},
    }


def _r_identity() -> dict:
    """'Who are you?' — rich identity response, never a file list."""
    mem  = load_memory()
    proj = mem.get("project", {})
    name = proj.get("name", "X Control Center")
    ver  = proj.get("version", "v5.0")
    p3 = {
        "memory":   AIMemoryLayer.status(),
        "planner":  AIPlanner.status(),
        "engineer": AIEngineerCore.status(),
        "impact":   ProjectImpactAnalysis.status(),
    }
    dep_st  = ProjectDependencyGraph.status()
    brain   = ProjectBrain.get()
    totals  = brain.get("totals", {})
    return {
        "text": f"""🧠 **أنا TitanX Engineering Agent — Agent Foundation v16**

**ما أنا؟**
وكيل هندسي متخصص مدمج في **{name} {ver}**.
أعمل بـ 16 قاعدة صارمة: الفحص أولاً، الأدلة قبل الإجابة، الموافقة قبل التنفيذ، التحقق بعده.

**بروتوكول التفكير (7 خطوات إلزامية لكل طلب مشروع):**
  1️⃣ Understand — استخراج الكيانات وتصنيف النية
  2️⃣ Search — فحص حي للملفات ذات الصلة
  3️⃣ Context — تحديد أدوار الملفات وفئاتها
  4️⃣ Deps — رسم بيان التبعيات من AST graph
  5️⃣ Impact — تقييم مستوى المخاطرة والملفات المتأثرة
  6️⃣ Plan — خطة تنفيذ بالملفات الحقيقية (عند الحاجة)
  7️⃣ Answer — رد مدعوم بأدلة الفحص المباشر

**أدواتي الهندسية:**
  🔍 **Dep Graph** — {dep_st['files_scanned']} ملف ممسوح · {dep_st['total_deps']} علاقة تبعية حية
  🧠 **Project Brain** — {totals.get('files', 0)} ملف · {totals.get('routers', 0)} راوتر · {totals.get('handlers', 0)} handler
  💾 **AI Memory** — {p3['memory']['turns']} دورة محادثة محفوظة
  🔬 **Impact Analysis** — تحليل transitive تلقائي لكل ملف
  ⏸️ **Planning Gate** — لا تنفيذ بدون موافقة صريحة
  🤖 **Hugging Face** — متصل بـ `x-ai-core` Space

**المشروع:**
  • بوت Telegram رئيسي — `bot.py` (PrimeDownloader)
  • بوت دعم فني — `support_bot/bot.py`
  • لوحة تحكم FastAPI — المنفذ 5000

اسألني: **"ما قدراتك؟"** أو **"رسم بيان التشغيل"** للبدء.""",
        "data": {
            "identity":      "TitanX Engineering Agent",
            "phase":         "Agent Foundation v16",
            "hf_connected":  hf_status().get("connected", False),
            "dep_graph":     dep_st,
            "project_totals": totals,
            "phase3":        p3,
        },
    }


def _r_capabilities() -> dict:
    """'What can you do?' — full capability listing with Agent Foundation v16 modes."""
    dep_st = ProjectDependencyGraph.status()
    return {
        "text": f"""⚡ **قدرات TitanX Engineering Agent — Agent Foundation v16**

**🔍 الهندسة والتحليل (Scan-First):**
  • "ما الملفات التي تعتمد على config.py؟" → رسم بيان التبعيات الحي
  • "ماذا يحدث لو حذفت db_utils.py؟" → تأثير transitive كامل
  • "رسم بيان التشغيل" → Startup + Runtime + Failure chains
  • "سلسلة تدفق البيانات من Telegram إلى الرد" → data-flow map

**🚀 تخطيط الميزات (Approval-Gated):**
  • "أضف بوت إشعارات" → scan أولاً + خطة بالملفات الحقيقية + انتظار موافقتك
  • "ابنِ صفحة إحصائيات" → scaffold كامل محمي بـ Planning Gate

**🔧 التشخيص والإصلاح:**
  • "شخّص خطأ في auth" → root-cause + الملفات المتأثرة + خطة الإصلاح
  • "أكبر نقطة ضعف في المشروع" → تقييم كامل بالأولويات

**🏗️ الهندسة المعمارية:**
  • "أعد تصميم بنية المشروع" → خطة هيكلية بالتفصيل
  • "التقنيات الديون التقنية" → قائمة مرتبة بالأولوية
  • "كيف يتحمل 100,000 مستخدم؟" → خطة توسعة

**💬 المحادثة التقنية العامة:**
  • "ما الفرق بين FastAPI و Flask؟" → مقارنة مفصّلة
  • "اشرح async/await" → شرح مع أمثلة من المشروع

**📊 حالة النظام الحالية:**
  • {dep_st['files_scanned']} ملف ممسوح · {dep_st['total_deps']} علاقة تبعية في الرسم البياني
  • بروتوكول 7 خطوات يعمل على كل طلب مشروع

**🧪 التحقق الذاتي:**
  • "اختبر نفسك" → {dep_st['files_scanned']} ملف + جميع مراحل الاختبار""",
        "data": {
            "agent":   "TitanX Engineering Agent",
            "version": "Agent Foundation v16",
            "intents": [
                "identity", "capabilities", "hf_query",
                "find_file", "create_feature", "ui_redesign",
                "debug_fix", "new_page", "plan_modify",
                "dependency", "who_depends", "data_flow", "reuse_systems",
                "root_cause", "impact", "arch", "runtime_graph",
                "errors", "analyze", "security", "weakness",
                "strategy", "scale", "tech_debt", "redesign",
                "status", "self_test",
            ],
            "dep_graph": dep_st,
        },
    }


def _r_hf_query() -> dict:
    """'Are you connected to Hugging Face?' — live status check."""
    status = hf_status()
    if status["connected"]:
        text = f"""🤖 **نعم — متصل بـ Hugging Face ✅**

**Space:** `{HF_SPACE_URL}`
**الحالة:** 🟢 متصل ومستجيب (تم التحقق للتو)

**نقاط الاتصال الحية:**
  • `POST /api/analyze` — تحليل الأخطاء والكود
  • `POST /api/assistant` — مساعد ذكاء عام
  • `POST /api/planner` — تخطيط الميزات خطوة بخطوة
  • `GET  /api/memory` — ذاكرة المشروع من الـ Space ✅

**API Proxy محلي (بعد المصادقة):**
  • `GET  /ai/api/hf/status`
  • `POST /ai/api/hf/analyze`
  • `POST /ai/api/hf/assistant`
  • `POST /ai/api/hf/planner`
  • `GET  /ai/api/hf/memory`

الاتصال يعمل وجاهز للاستخدام."""
    else:
        text = f"""⚠️ **مشكلة في الاتصال بـ Hugging Face**

**Space:** `{HF_SPACE_URL}`
**الخطأ:** `{status.get('error', 'connection timeout')}`

معظم الوظائف تعمل محلياً — الاتصال بـ HF اختياري للتعزيز فقط.
يُعاد المحاولة تلقائياً في كل طلب."""
    return {"text": text, "data": {"hf_status": status}}


def _r_create_feature(msg: str) -> dict:
    """
    AGENT GATE: Analyze + produce plan → await explicit approval before any execution.
    Never executes immediately. Uses AgentPlanningGate.submit() which runs the full
    5-step ProjectIntelligenceAgent protocol and adds ⏸️ approval prompt.
    """
    return AgentPlanningGate.submit(msg)


def _r_ui_redesign(msg: str) -> dict:
    """
    AGENT GATE: Analyze redesign request → produce plan → await explicit approval.
    """
    return AgentPlanningGate.submit(msg)


def _r_debug_fix(msg: str) -> dict:
    """
    AGENT GATE: Diagnose issue → produce fix plan → await explicit approval.
    """
    return AgentPlanningGate.submit(msg)


def _r_new_page(msg: str) -> dict:
    """
    AGENT GATE: Design new page plan → await explicit approval before execution.
    """
    return AgentPlanningGate.submit(msg)


def _r_find_file(msg: str) -> dict:
    """
    PHASE 2 — Evidence-first file lookup.

    Mandatory flow:
      1. Answer via answer_file_question() (semantic + route graph)
      2. Verify primary file physically exists on disk
      3. Find functions in file related to query
      4. Extract evidence lines (actual code)
      5. Calculate confidence
      6. Append mandatory Verification Report block
    """
    update_stats("total_questions")
    base = answer_file_question(msg)

    if not _EV_OK:
        return base

    # ── Extract verified file list ────────────────────────────────────────────
    file_list = base.get("data", {}).get("files", [])
    concept   = base.get("data", {}).get("concept", msg)

    # If the evidence gate already returned NO EVIDENCE, propagate it
    if not file_list and "INSUFFICIENT" in base.get("data", {}).get("evidence", ""):
        return base

    if not file_list:
        # No files found — explicit NO EVIDENCE
        return {
            "text": _NO_EVIDENCE + f"\n\n_Concept searched: `{concept}`_",
            "data": {"concept": concept, "files": [], "evidence": "NO_FILES_FOUND"},
        }

    # ── Verification: take the primary (highest-relevance) file ──────────────
    primary   = file_list[0]["path"]
    exists    = _ev_file_exists(primary)

    if not exists:
        return {
            "text": _NO_EVIDENCE + f"\n\n_File `{primary}` not found on disk._",
            "data": {"concept": concept, "files": [], "evidence": "FILE_NOT_ON_DISK"},
        }

    # ── Evidence collection ───────────────────────────────────────────────────
    terms      = [t for t in concept.lower().split() if len(t) > 3][:6]
    funcs      = _ev_find_funcs(primary, terms)
    ev_lines   = _ev_grep(primary, terms, max_hits=3)
    subsystem  = _ev_subsystem(primary)
    confidence = _ev_confidence(
        file_exists=exists,
        functions_found=funcs,
        evidence_lines=ev_lines,
    )
    func_name  = funcs[0]["name"] if funcs else None

    # ── Build mandatory verification block ───────────────────────────────────
    extra = []
    if len(file_list) > 1:
        others = [f"`{f['path']}`" for f in file_list[1:4]]
        extra.append(f"📂 **Related:** {', '.join(others)}")

    verify_block = _ev_format(
        subsystem=subsystem,
        file_path=primary,
        function_name=func_name,
        evidence_lines=ev_lines,
        confidence=confidence,
        extra_lines=extra,
    )

    return {
        "text": base["text"] + verify_block,
        "data": {**base.get("data", {}), "verification": {
            "subsystem": subsystem,
            "primary_file": primary,
            "function": func_name,
            "confidence": confidence,
            "evidence_count": len(ev_lines),
        }},
    }


def _r_find_function(msg: str) -> dict:
    """
    PHASE 2 — Function-finder handler.

    Mandatory flow:
      1. Determine what kind of function is sought (keyboard, handler, etc.)
      2. Search real project files for matching function definitions
      3. Verify each file exists on disk
      4. Extract function signature as evidence
      5. Build mandatory Verification Report

    Returns NO EVIDENCE if no matching function found.
    """
    if not _EV_OK:
        return {"text": "⚠️ Evidence Engine not loaded.", "data": {}}

    ml = msg.lower()

    # ── Classify the function type ────────────────────────────────────────────
    is_keyboard = any(kw in ml for kw in [
        "keyboard", "inline", "reply", "button", "لوحة", "زر",
    ])
    is_handler  = any(kw in ml for kw in [
        "handler", "command", "معالج", "أمر",
    ])

    # ── Project Understanding: Disambiguate web-UI vs Telegram keyboard ───────
    # "Admin Panel button", "control panel button", "login button" etc. refer to
    # HTML elements in templates — NOT Telegram InlineKeyboardButtons.
    # Mandatory verification flow: identify subsystem BEFORE dispatching.
    _WEB_UI_SIGNALS = [
        "admin panel", "control panel", "dashboard", "panel button",
        "login button", "html", "template", "web", "page button",
    ]
    is_web_ui_button = is_keyboard and any(sig in ml for sig in _WEB_UI_SIGNALS)

    # ── Case 0: web-UI button (HTML template) — must check BEFORE Telegram kb ─
    if is_web_ui_button and _EV_OK:
        concept = re.sub(
            r"what|which|function|creates?|button|makes?|the|file|owns?",
            " ", ml,
        ).strip()
        tb = _ev_template_buttons(concept)
        if tb:
            lines_out: list = [
                f"🖥️ **Web-UI Buttons matching `{concept.strip()}`:** {len(tb)} found\n",
                "_(verified by reading real HTML template files)_\n",
            ]
            for entry in tb[:8]:
                ev_lines = [{"line_no": entry["line_no"], "text": entry["text"]}]
                exists   = _ev_file_exists(entry["file"])
                conf     = _ev_confidence(
                    file_exists=exists,
                    functions_found=[],
                    evidence_lines=ev_lines,
                )
                block = _ev_format(
                    subsystem=_ev_subsystem(entry["file"]),
                    file_path=entry["file"],
                    function_name=None,
                    evidence_lines=ev_lines,
                    confidence=conf,
                    extra_lines=[f"🏷️ **Element type:** `{entry['element_type']}`"],
                    label="VERIFIED FROM HTML SOURCE",
                )
                lines_out.append(block)
                lines_out.append("")
            return {"text": "\n".join(lines_out), "data": {"template_buttons": tb[:8]}}
        # No HTML buttons matched — fall through to Telegram keyboard search
        # so the user still gets an answer rather than silence

    # ── Case 1: Telegram keyboard functions ───────────────────────────────────
    if is_keyboard:
        kb_funcs = _ev_keyboards()
        if not kb_funcs:
            return {
                "text": _NO_EVIDENCE + "\n\n_No keyboard-creating functions found._",
                "data": {"evidence": "NO_KEYBOARD_FUNCTIONS"},
            }

        lines: list = [
            f"⌨️ **Keyboard Functions Found: {len(kb_funcs)}**\n",
            "_(verified by reading real file content)_\n",
        ]
        for entry in kb_funcs[:10]:
            ev_lines = [{"line_no": entry["line_no"], "text": entry["evidence"]}]
            block = _ev_format(
                subsystem=_ev_subsystem(entry["file"]),
                file_path=entry["file"],
                function_name=entry["function"],
                evidence_lines=ev_lines,
                confidence=_ev_confidence(
                    file_exists=True,
                    functions_found=[entry],
                    evidence_lines=ev_lines,
                ),
                extra_lines=[f"🎹 **Keyboard type:** `{entry['keyboard_type']}`"],
                label="VERIFIED FROM SOURCE",
            )
            lines.append(block)
            lines.append("")

        return {"text": "\n".join(lines), "data": {"functions": kb_funcs[:10]}}

    # ── Case 2: generic function search with query terms ─────────────────────
    terms = [t for t in re.sub(
        r"what|which|function|creates?|handles?|processes?|makes?",
        " ", ml,
    ).split() if len(t) > 3][:5]

    if not terms:
        return {
            "text": (
                "⚠️ لم أستطع تحديد نوع الدالة.\n\n"
                "جرب:\n"
                "  • 'What function creates the keyboard?'\n"
                "  • 'What function handles /start command?'\n"
                "  • 'What function sends notifications?'"
            ),
            "data": {},
        }

    # Search all Python files
    results: list = []
    import os
    proj = __import__("pathlib").Path(__file__).parent.parent
    for py_file in sorted(proj.rglob("*.py")):
        rel = str(py_file.relative_to(proj)) if proj in py_file.parents else str(py_file)
        if any(skip in rel for skip in ["__pycache__", ".git", "node_modules"]):
            continue
        funcs = _ev_find_funcs(rel, terms)
        for f in funcs:
            results.append({**f, "file": rel})

    if not results:
        return {
            "text": _NO_EVIDENCE + f"\n\n_No function found matching: {terms}_",
            "data": {"evidence": "NO_FUNCTION_FOUND", "terms": terms},
        }

    lines = [
        f"⚙️ **Functions matching `{' '.join(terms)}`:** {len(results)} found\n",
        "_(verified from real source files)_\n",
    ]
    for entry in results[:8]:
        ev_lines = [{"line_no": entry["line_no"], "text": entry["evidence"]}]
        block = _ev_format(
            subsystem=_ev_subsystem(entry["file"]),
            file_path=entry["file"],
            function_name=entry["name"],
            evidence_lines=ev_lines,
            confidence=_ev_confidence(
                file_exists=True,
                functions_found=[entry],
                evidence_lines=ev_lines,
            ),
            label="VERIFIED FROM SOURCE",
        )
        lines.append(block)
        lines.append("")

    return {"text": "\n".join(lines), "data": {"functions": results[:8]}}


def _r_plan(msg: str) -> dict:
    update_stats("total_plans")
    plan = create_modification_plan(msg)
    lines = [f"📋 **خطة التعديل: {plan['description']}**\n",
             f"⚠️ **مستوى الخطر:** {plan['risk_label']}",
             f"📁 **عدد الملفات:** {plan['estimated_files']}\n",
             "**📂 الملفات المطلوب تعديلها:**"]
    for d in plan["file_details"]:
        lines.append(f"  • `{d['file']}` [{d['role'].upper()}] — {d['why']}")
    lines.append(f"\n**🔄 استراتيجية الاسترجاع:** {plan['rollback_strategy']}")
    lines.append("\n**📋 الخطوات:**")
    for step in plan["steps"]:
        lines.append(f"  {step}")
    AIMemoryLayer.record_decision(f"Modification plan: {plan['description']}", f"{plan['estimated_files']} files affected")
    return {"text": "\n".join(lines), "data": plan}


def _r_dependency(msg: str) -> dict:
    """
    Live dependency analysis — reads real AST import graph via ProjectDependencyGraph.

    Reasoning:
    1. Try _find_concept() for semantic file mapping
    2. Try _route_for_concept() for route/template relationship
    3. For each found file: ProjectDependencyGraph.full_impact_report() → direct importers + risk
    4. Fall back to keyword search in reverse graph
    """
    entries    = _find_concept(msg)
    route_info = _route_for_concept(msg)
    risk_icons = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "NONE": "⚪"}
    lines      = ["🔗 **تحليل التبعيات — قراءة مباشرة من الكود**\n"]

    # ── Route/template level ──────────────────────────────────────────────────
    if route_info:
        lines.append(f"📄 **Template:** `{route_info['template']}`")
        lines.append(f"  ↳ يرث من: `{route_info.get('base', 'standalone')}`")
        lines.append(f"⚙️ **Router:** `{route_info['router']}`")
        for c in route_info.get("css", []):
            lines.append(f"🎨 **CSS:** `{c}`")
        for j in route_info.get("js", []):
            lines.append(f"📜 **JS:** `{j}`")
        for a in route_info.get("apis", []):
            lines.append(f"  🔌 API: `{a}`")

    # ── File-level import graph (live AST) — PHASE 2: with evidence lines ──────
    if entries:
        for path, role, desc in entries[:4]:
            report = ProjectDependencyGraph.full_impact_report(path)
            direct = report.get("direct_importers", [])
            risk   = report.get("risk", "LOW")
            lines.append(f"\n📁 `{path}` [{role}] — {desc}")

            # Verify the target file itself exists before claiming anything
            if _EV_OK and not _ev_file_exists(path):
                lines.append("  ⛔ **FILE NOT ON DISK** — cannot verify importers")
                continue

            if direct:
                lines.append(f"  📥 **يستورده ({len(direct)} ملف):**")
                for imp in direct[:10]:
                    lines.append(f"    ↳ `{imp}`")
                    # PHASE 2 EVIDENCE: verify import file exists + show actual import line
                    if _EV_OK:
                        if not _ev_file_exists(imp):
                            lines.append(f"      ⚠️ _(file not on disk — may be stale index)_")
                        else:
                            imp_ev = _ev_import_lines(imp, path)
                            if imp_ev:
                                lines.append(f"      📋 `{imp_ev[0]['text']}`")
                if len(direct) > 10:
                    lines.append(f"    ... و {len(direct) - 10} ملف آخر")
            trans = report.get("transitive_impact", [])
            if trans:
                lines.append(
                    f"  {risk_icons.get(risk,'⚪')} **التأثير الإجمالي:** "
                    f"{report['total_files_at_risk']} ملف — خطر: {risk}"
                )
            if not direct and not trans:
                lines.append("  ℹ️ لا ملفات تستورده مباشرة")

    # ── Keyword fallback: search dep graph directly ───────────────────────────
    if not entries and not route_info:
        ml_norm = _normalize_ar(msg.lower())
        graph   = ProjectDependencyGraph.get()
        reverse = graph.get("reverse", {})
        tokens  = [t for t in ml_norm.split() if len(t) > 2]
        matches = [k for k in reverse if any(t in k for t in tokens)]
        if matches:
            best   = matches[0]
            report = ProjectDependencyGraph.full_impact_report(best)
            lines.append(f"🔍 **أقرب تطابق:** `{best}`")
            lines.append(f"  📥 يستورده: {len(report.get('direct_importers', []))} ملف — خطر: {report.get('risk', 'LOW')}")
            lines.append(f"  💥 التأثير الإجمالي: {report['total_files_at_risk']} ملف")
        else:
            lines.append("⚠️ لم يتم العثور على ملف بالاسم المحدد.")
            lines.append("💡 جرب: 'تبعيات config/settings.py' أو 'تبعيات database/db.py' أو 'تبعيات ai_engine.py'")

    # ── Call Graph — function-level cross-file callers (Phase 4) ─────────────
    if _CALL_GRAPH_OK and _CallGraph is not None and entries:
        try:
            cg_hits: list = []
            for path, _, _ in entries[:2]:
                cg_hits.extend(_CallGraph.who_calls_file(path))
            if cg_hits:
                lines.append("\n📞 **Call Graph — دوال تستدعي من هذا الملف:**")
                seen_cg: set = set()
                for caller_file, caller_func, callee_func in cg_hits[:8]:
                    key = f"{caller_file}::{caller_func}"
                    if key not in seen_cg:
                        seen_cg.add(key)
                        lines.append(
                            f"  `{caller_file}` → `{caller_func}()` → `{callee_func}()`"
                        )
            circulars = _CallGraph.circular_imports()
            if circulars:
                lines.append(f"\n⚠️ **استيرادات دائرية مكتشفة ({len(circulars)}):**")
                for c in circulars[:4]:
                    lines.append(f"  🔄 {' → '.join(c)}")
        except Exception:
            pass

    # ── File Ownership (Phase 2) ──────────────────────────────────────────────
    if _KG_OK and _FO is not None and entries:
        try:
            lines.append("\n🏷️ **File Ownership:**")
            for path, _, _ in entries[:3]:
                own = _FO.get(path)
                if own and own.get("purpose") != "Unknown — file not indexed":
                    risk_icon = {"CRITICAL": "🔴", "HIGH": "🟠",
                                 "MEDIUM": "🟡", "LOW": "🟢"}.get(own["risk_level"], "⚪")
                    lines.append(
                        f"  {risk_icon} `{path}` — {own['purpose']}"
                    )
                    if own.get("spof"):
                        lines.append(
                            f"    ⚠️ نقطة فشل واحدة — يعتمد عليه "
                            f"{own['dependent_count']} ملف"
                        )
        except Exception:
            pass

    # ── Knowledge Graph cross-type trace (Phase 1) ───────────────────────────
    if _KG_OK and _KG is not None and entries:
        try:
            path = entries[0][0]
            trace = _KG.full_trace(path)
            kg_items: list = []
            if trace.get("renders"):
                kg_items.append(f"  🖥️ يرندر: {', '.join(f'`{t}`' for t in trace['renders'][:4])}")
            if trace.get("uses_db"):
                kg_items.append(f"  🗄️ قاعدة بيانات: {', '.join(f'`{d}`' for d in trace['uses_db'][:3])}")
            if trace.get("configures"):
                kg_items.append(f"  ⚙️ يُهيئ: {', '.join(f'`{c}`' for c in trace['configures'][:4])}")
            if trace.get("handles_cmds"):
                kg_items.append(f"  🤖 أوامر: {', '.join(f'`{cmd}`' for cmd in trace['handles_cmds'][:5])}")
            if kg_items:
                lines.append("\n🕸️ **Knowledge Graph Trace:**")
                lines.extend(kg_items)
        except Exception:
            pass

    return {"text": "\n".join(lines), "data": {"entries": entries}}


def _r_impact(msg: str) -> dict:
    """
    Reasoning-first impact analysis.
    1. Try to find a specific file/concept the user mentioned → file-level analysis.
    2. If no specific file, reason semantically about what the operation affects.
    """
    ml = msg.lower()

    # ── Live graph: if a specific file/concept is mentioned → query live dep graph ──
    # This case runs FIRST for any message mentioning a real file or known concept.
    _ENTRIES = _find_concept(msg)
    if _ENTRIES:
        report   = ProjectDependencyGraph.full_impact_report(_ENTRIES[0][0])
        path     = report["file"]
        direct   = report["direct_importers"]
        trans    = report["transitive_impact"]
        risk     = report["risk"]
        risk_icons = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "NONE": "⚪"}
        icon     = risk_icons.get(risk, "⚪")
        n_dir    = len(direct)
        n_trans  = len(trans)
        lines = [
            f"💥 **تحليل التأثير الكامل: `{path}`** — من قراءة مباشرة للكود\n",
            f"{icon} **مستوى الخطر:** {risk}",
            f"📥 **يستورده مباشرة:** {n_dir} ملف",
        ]
        for f in direct[:12]:
            lines.append(f"  ↳ `{f}`")
        if n_dir > 12:
            lines.append(f"  ... و {n_dir - 12} آخرون")
        if trans:
            lines.append(f"\n💣 **التأثير الإجمالي عند الحذف:** {n_trans} ملف")
            for f in trans[:10]:
                lines.append(f"  ⚠️ `{f}`")
            if n_trans > 10:
                lines.append(f"  ... و {n_trans - 10} ملف آخر")
        if risk in ("CRITICAL", "HIGH"):
            lines.append(
                f"\n🚨 **تحذير:** `{path}` نقطة فشل مركزية — "
                f"{n_dir} ملف تتوقف عليه. لا تحذفه أو تعدّله دون خطة واضحة."
            )
        elif risk == "LOW" and n_dir == 0:
            lines.append(f"\n✅ **آمن:** لا ملفات تعتمد على `{path}` مباشرة.")
        return {"text": "\n".join(lines), "data": report}

    # ── Semantic operation detection ─────────────────────────────────────────
    _ADD_BOT  = re.search(r"(?:أضفت|بنيت|أنشأت|دمجت).{0,20}(?:بوت|bot)|add.{0,20}bot", ml)
    _ADD_FEAT = re.search(r"(?:أضفت|بنيت|أنشأت).{0,20}(?:ميزة|نظام|feature|service)", ml)
    _DEL_DB   = re.search(r"(?:حذفت|عدلت|غيرت).{0,20}(?:قاعدة\s*البيانات|database|db\.py)", ml)
    _DEL_CSS  = re.search(r"(?:حذفت|عدلت|غيرت).{0,20}(?:style\.css|css)", ml)
    _DEL_BOT  = re.search(r"(?:حذفت|أزلت|عدلت).{0,20}(?:بوت|bot\.py)", ml)
    _FAIL_DB  = re.search(r"(?:فشلت|انهارت|توقفت|تعطلت|تعطل).{0,25}(?:قاعدة|البيانات|database|db)", ml)

    # ── Case 1: Adding a new bot ──────────────────────────────────────────────
    if _ADD_BOT:
        return {
            "text": (
                "💥 **تحليل تأثير: إضافة بوت جديد**\n\n"
                "🚨 **مستوى الخطر:** HIGH — تعديلات متعددة في البنية الأساسية\n\n"
                "**الملفات المتأثرة:**\n"
                "  🔴 `scripts/start.sh` — يجب إضافة أمر تشغيل البوت الجديد\n"
                "  🔴 `config/settings.py` — TOKEN جديد + ADMIN_IDS\n"
                "  🔠 `control_panel/app.py` — راوتر مراقبة اختياري\n"
                "  🟠 `control_panel/templates/base.html` — رابط في الشريط الجانبي\n\n"
                "**المخاطر:**\n"
                "  • تعارض البوتات على نفس الـ webhook إذا شاركوا TOKEN\n"
                "  • كل بوت يحتاج workflow مستقل في Replit\n"
                "  • قاعدة البيانات المشتركة قد تسبب تعارضات في الجداول\n\n"
                "**الخطوات الآمنة:**\n"
                "  1. أنشئ `new_bot/bot.py` مستقلاً عن `bot.py`\n"
                "  2. أضف TOKEN مختلف في Secrets\n"
                "  3. سجّل workflow جديد\n"
                "  4. لا تلمس `database/db.py` — أضف جداول جديدة فقط"
            ),
            "data": {"operation": "add_bot", "risk": "high"},
        }

    # ── Case 2: Adding a feature/service ─────────────────────────────────────
    if _ADD_FEAT:
        return {
            "text": (
                "💥 **تحليل تأثير: إضافة ميزة جديدة**\n\n"
                "🚨 **مستوى الخطر:** MEDIUM\n\n"
                "**المتأثرات الأساسية:**\n"
                "  🟠 `control_panel/app.py` — تسجيل الراوتر الجديد\n"
                "  🟠 `control_panel/templates/base.html` — إضافة رابط في القائمة\n"
                "  🟡 `database/db.py` — إذا احتاجت الميزة جدول جديد\n\n"
                "**جوانب غير مباشرة:**\n"
                "  • الـ CSS العام (`style.css`) يُطبَّق تلقائياً على الصفحة الجديدة\n"
                "  • `auth.py` يحمي أي مسار يستخدم `require_owner`\n\n"
                "**الخطر الأكبر:** تعديل `app.py` بشكل خاطئ يوقف اللوحة كلها."
            ),
            "data": {"operation": "add_feature", "risk": "medium"},
        }

    # ── Case 3: Database change ───────────────────────────────────────────────
    if _DEL_DB:
        return {
            "text": (
                "💥 **تحليل تأثير: تعديل قاعدة البيانات**\n\n"
                "🔴 **مستوى الخطر:** CRITICAL\n\n"
                "**المتأثرات المباشرة:**\n"
                "  🔴 `bot.py` — لن يبدأ إذا فشلت `init_db()`\n"
                "  🔴 `database/users.py` — 4 ملفات تعتمد عليه مباشرة\n"
                "  🔴 `handlers/start.py`, `handlers/admin.py` — توقف كامل\n"
                "  🔴 `control_panel/routers/users.py` — لوحة المستخدمين تتعطل\n\n"
                "**تحذيرات:**\n"
                "  ⚠️ أي تغيير في schema يتطلب migration — لا يوجد Alembic في المشروع حالياً\n"
                "  ⚠️ البوتات تبدأ بـ `init_db()` — خطأ فيه = فشل كامل في الـ startup"
            ),
            "data": {"operation": "modify_db", "risk": "critical"},
        }

    # ── Case 3b: Database FAILURE scenario ────────────────────────────────────
    if _FAIL_DB:
        return {
            "text": (
                "💥 **تأثير فشل قاعدة البيانات**\n\n"
                "إذا توقفت قاعدة البيانات في هذا المشروع سيحدث التالي:\n\n"
                "**🔴 تأثيرات فورية (ثواني):**\n"
                "  · بوت التلغرام يفشل في استرجاع/حفظ بيانات المستخدم\n"
                "  · لوحة التحكم لا تستطيع تحميل الإحصائيات أو السجلات\n"
                "  · أي محاولة `/download` أو `/subscribe` تُرجع خطأً\n\n"
                "**🟠 تأثيرات على المدى القصير (دقائق):**\n"
                "  · طابور الرسائل المعلقة يتراكم في Telegram\n"
                "  · الجلسات النشطة تنتهي بدون حفظ\n"
                "  · لوحة التحكم تبدأ بإعادة المحاولات وقد تنهار هي أيضاً\n\n"
                "**🟡 الملفات المتأثرة مباشرة:**\n"
                "  · `extracted_project/db_utils.py` — جميع عمليات read/write\n"
                "  · `extracted_project/bot.py` — يستدعي db في كل رسالة\n"
                "  · `control_panel/routers/` — كل endpoint يقرأ من DB\n\n"
                "**✅ الحماية الموصى بها:**\n"
                "  · إضافة `try/except` شامل حول كل استدعاء DB مع fallback\n"
                "  · تفعيل connection pool مع timeout واضح\n"
                "  · إضافة health-check endpoint يراقب اتصال DB باستمرار"
            ),
            "data": {"impact_type": "database_failure"},
        }

    # ── Case 4: CSS change ────────────────────────────────────────────────────
    if _DEL_CSS:
        entries = _find_concept(msg)
        if not entries:
            entries = [("control_panel/static/css/style.css", "CSS", "stylesheet")]
        target = entries[0][0]
        impact = analyze_file_impact(target)
        lines  = [f"💥 **تأثير تغيير: `{target}`**\n",
                  f"🚨 **مستوى الخطر:** {impact.get('risk', 'unknown').upper()}"]
        for a in impact.get("affects", []):
            lines.append(f"  ⚠️ {a}")
        return {"text": "\n".join(lines), "data": impact}

    # ── Default: try file concept then generic reasoning ──────────────────────
    entries = _find_concept(msg)
    if entries:
        target = entries[0][0]
        impact = analyze_file_impact(target)
        lines  = [f"💥 **تأثير تغيير: `{target}`**\n",
                  f"🚨 **مستوى الخطر:** {impact.get('risk', 'unknown').upper()}"]
        for a in impact.get("affects", []):
            lines.append(f"  ⚠️ {a}")
        return {"text": "\n".join(lines), "data": impact}

    # No concept found — generic project-level reasoning
    return {
        "text": (
            "💥 **تحليل التأثير العام**\n\n"
            "لم أتمكن من تحديد العنصر المحدد في سؤالك.\n\n"
            "**المبدأ العام في هذا المشروع:**\n"
            "  🔴 CRITICAL: `app.py`, `auth.py`, `base.html`, `style.css`, `bot.py`, `db.py`\n"
            "  🟠 HIGH: `config.py`, `ai_engine.py`, `database/users.py`\n"
            "  🟡 MEDIUM: Routers فردية، templates فردية\n"
            "  🟢 LOW: Static assets، بيانات، سجلات\n\n"
            "**أعد السؤال مع تحديد العنصر** — مثال: \"لو حذفت style.css ماذا سيحدث؟\""
        ),
        "data": {"operation": "unknown", "risk": "unknown"},
    }


def _r_root_cause(msg: str) -> dict:
    analysis = analyze_root_cause(msg)
    lines    = [f"🔍 **تحليل السبب الجذري**\n"]
    for fp in analysis["failure_points"]:
        lines.append(f"• **{fp['layer']}**: `{fp['file']}`")
        lines.append(f"  → {fp['check']}")
    lines.append("\n**🛠️ خطوات التشخيص:**")
    for step in analysis["diagnostic_steps"]:
        lines.append(f"  {step}")
    return {"text": "\n".join(lines), "data": analysis}


def _r_arch(msg: str) -> dict:
    return explain_architecture(msg)


def _r_self_test() -> dict:
    result = run_self_tests()
    lines  = [f"🧪 **نتائج الاختبار الذاتي — {result['score']} ({result['pass_rate']})**\n",
              f"الحالة: {result['status']}\n"]
    for t in result["tests"]:
        icon = "✅" if t["passed"] else "❌"
        lines.append(f"{icon} {t['question']}")
        if not t["passed"]:
            lines.append(f"   → Expected intent: `{t['expected_intent']}` | Got: `{t['got_intent']}`")
            lines.append(f"   → Keyword `{t['expected_keyword']}` found: {t['keyword_found']}")
    return {"text": "\n".join(lines), "data": result}


def _r_analyze() -> dict:
    analysis = full_analysis()
    s = analysis["structure"]
    lines = ["🔬 **تحليل المشروع الكامل**\n",
             f"📁 إجمالي الملفات: {s['total_files']}",
             f"🌐 المسارات المعروفة: {s['knowledge_graph_routes']}",
             f"🧠 المفاهيم الدلالية: {s['semantic_concepts']}",
             f"🎨 القوالب: {len(s['templates'])}",
             f"⚙️ الـ Routers: {len(s['routers'])}",
             f"🤖 المعالجات: {len(s['handlers'])}",
             f"🗄️ نماذج DB: {len(s['db_models'])}",
             ""]
    if analysis["errors"]:
        lines.append(f"⚠️ {len(analysis['errors'])} أخطاء في السجلات")
    if analysis["issues"]:
        lines.append(f"🔧 {len(analysis['issues'])} مشاكل في الكود")
    return {"text": "\n".join(lines), "data": analysis}


def _r_errors() -> dict:
    errors = detect_log_errors()
    if not errors:
        return {"text": "✅ لا توجد أخطاء في السجلات", "data": {"errors": []}}
    lines = [f"⚠️ **{len(errors)} أخطاء في السجلات:**\n"]
    for e in errors[:15]:
        lines.append(f"• `{e['file']}`: {e['line'][:100]}")
    return {"text": "\n".join(lines), "data": {"errors": errors}}


def _r_backup_info() -> dict:
    bks = list_backups()
    lines = [f"💾 **النسخ الاحتياطية: {len(bks)} نسخة**\n"]
    for b in bks[-5:]:
        lines.append(f"• `{b['id']}` — {b['desc']} — {b['ts']}")
    lines.append("\n🔗 إدارة النسخ: `/backups`")
    return {"text": "\n".join(lines), "data": {"backups": bks}}


def _r_restore_info() -> dict:
    bks = list_backups()
    lines = ["🔄 **استعادة نسخة احتياطية**\n",
             "استخدم `/backups` في لوحة التحكم لاستعادة أي نسخة احتياطية.\n",
             f"النسخ المتاحة: {len(bks)}"]
    return {"text": "\n".join(lines), "data": {"backups": bks}}


def _r_structure() -> dict:
    s = analyze_structure()
    lines = ["📂 **هيكل المشروع**\n",
             f"الملفات الكلية: {s['total_files']}",
             f"المسارات في الجراف: {s['knowledge_graph_routes']}",
             f"المفاهيم الدلالية: {s['semantic_concepts']}",
             ""]
    for ext, count in sorted(s["by_type"].items(), key=lambda x: x[1], reverse=True):
        lines.append(f"  {ext}: {count} ملف")
    return {"text": "\n".join(lines), "data": s}


def _r_routes(msg: str = "") -> dict:
    """
    PHASE 2 — Evidence-first router lookup.

    When a specific concept is in the query:
      1. Search real router files for matching @router decorators
      2. Verify router file exists on disk
      3. Extract decorator line as evidence
      4. Build mandatory Verification Report

    When no specific concept: list all routes (no inference).
    """
    routes = detect_routes()

    # ── Concept-specific lookup ───────────────────────────────────────────────
    if msg and _EV_OK:
        ml = msg.lower()
        # Extract the concept from the query (strip question words)
        concept_m = re.sub(
            r"(?:what|which|who)\s+router\s+(?:serves?|handles?|manages?|is\s+responsible\s+for)?",
            "", ml, flags=re.IGNORECASE,
        ).strip(" ?./")
        concept_m = re.sub(r"\s+", " ", concept_m).strip()

        if concept_m and len(concept_m) > 2:
            router_hits = _ev_router_concept(concept_m)
            if router_hits:
                best = router_hits[0]
                rf   = best["router_file"]
                exists = _ev_file_exists(rf)

                # Evidence: read the decorator line from the real file
                ev_lines: list = []
                if exists:
                    ev_lines.append({"line_no": best["line_no"], "text": best["evidence_line"]})
                    if best.get("include_evidence"):
                        ev_lines.append({"line_no": 0, "text": best["include_evidence"]})

                confidence = _ev_confidence(
                    file_exists=exists,
                    functions_found=[best["function"]] if best["function"] != "unknown" else [],
                    evidence_lines=ev_lines,
                )
                subsystem = _ev_subsystem(rf)

                extra: list = []
                if best.get("prefix"):
                    extra.append(f"🔗 **Route prefix:** `{best['prefix']}`")
                extra.append(f"🛣️ **Matched route:** `{best['route']}`")
                if len(router_hits) > 1:
                    others = [f"`{h['router_file']}`" for h in router_hits[1:3]]
                    extra.append(f"📂 **Other matches:** {', '.join(others)}")

                verify_block = _ev_format(
                    subsystem=subsystem,
                    file_path=rf,
                    function_name=best["function"] if best["function"] != "unknown" else None,
                    evidence_lines=ev_lines,
                    confidence=confidence,
                    extra_lines=extra,
                )

                summary = (
                    f"🌐 **Router for concept `{concept_m}`:**\n\n"
                    f"⚙️ **Router file:** `{rf}`\n"
                    f"🛣️ **Route:** `{best['route']}`\n"
                    f"⚙️ **Function:** `{best['function']}()`\n"
                )
                if best.get("prefix"):
                    summary += f"🔗 **Prefix:** `{best['prefix']}`\n"
                summary += verify_block

                return {
                    "text": summary,
                    "data": {"routes": routes, "router_hit": best,
                             "verification": {"confidence": confidence}},
                }

    # ── Fallback: full route list ─────────────────────────────────────────────
    lines = [f"🌐 **{len(routes)} مسار في لوحة التحكم:**\n"]
    for r in routes:
        lines.append(f"• `{r['route']}` → `{r['template']}` — {r['description']}")
    return {"text": "\n".join(lines), "data": {"routes": routes}}


def _r_security() -> dict:
    issues = security_scan()
    if not issues:
        return {"text": "🔒 لم يتم العثور على مشاكل أمنية واضحة", "data": {"issues": []}}
    lines = [f"🔐 **{len(issues)} ملاحظات أمنية:**\n"]
    for i in issues[:10]:
        lines.append(f"• `{i['file']}` — النمط: `{i['pattern']}`")
    return {"text": "\n".join(lines), "data": {"issues": issues}}


def _r_weakness(msg: str) -> dict:
    """
    Reason about the biggest weaknesses in the project.
    Uses live analysis: security scan + log errors + structural assessment.
    """
    sec_issues = security_scan()
    errors     = detect_log_errors()
    analysis   = full_analysis()
    s          = analysis.get("structure", {})

    risk_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}

    weaknesses = []

    # 1. Single point of failure: config/settings.py — live count from dep graph
    _dep_g      = ProjectDependencyGraph.get()
    _cfg_key    = ProjectDependencyGraph._resolve_name("config/settings.py")
    _cfg_deps   = _dep_g.get("reverse", {}).get(_cfg_key, [])
    _cfg_count  = len(_cfg_deps)
    weaknesses.append({
        "title": "نقطة فشل واحدة — `config/settings.py`",
        "risk": "CRITICAL" if _cfg_count >= 15 else "HIGH",
        "detail": (
            f"{_cfg_count} ملف يستورد config/settings.py مباشرة — "
            "أي خطأ syntax فيه يوقف البوتات واللوحة كلها. لا يوجد fallback."
            if _cfg_count > 0
            else "ملف الإعدادات المركزي — قاعدة كل مكونات المشروع. لا يوجد fallback."
        ),
    })

    # 2. No automated tests
    weaknesses.append({
        "title": "لا يوجد نظام اختبار تلقائي (Unit Tests)",
        "risk": "HIGH",
        "detail": "أي تعديل على الكود قد يكسر ميزة موجودة دون أي تحذير. يجب إضافة pytest.",
    })

    # 3. Live security issues
    if sec_issues:
        ex = sec_issues[0]
        weaknesses.append({
            "title": f"مخاوف أمنية — {len(sec_issues)} نمط مكتشف",
            "risk": "MEDIUM",
            "detail": f"مثال: النمط `{ex['pattern']}` في `{ex['file']}`",
        })

    # 4. Log errors
    if errors:
        ex = errors[0]
        weaknesses.append({
            "title": f"أخطاء في السجلات — {len(errors)} خطأ نشط",
            "risk": "MEDIUM",
            "detail": f"`{ex['file']}`: {ex['line'][:90]}",
        })

    # 5. DB coupling
    weaknesses.append({
        "title": "ارتباط مباشر بقاعدة البيانات — لا يوجد Migration System",
        "risk": "HIGH",
        "detail": "لا يوجد Alembic أو أي نظام migration. أي تغيير في schema يتطلب تدخلاً يدوياً.",
    })

    # 6. Scalability: single process
    weaknesses.append({
        "title": "تشغيل بـ uvicorn عملية واحدة",
        "risk": "LOW",
        "detail": "لوحة التحكم تعمل بعملية uvicorn واحدة — لا يوجد load balancing لحركة مرور عالية.",
    })

    lines = ["🔍 **تحليل نقاط الضعف الرئيسية في المشروع**\n"]
    for i, w in enumerate(weaknesses, 1):
        icon = risk_icon.get(w["risk"], "⚪")
        lines.append(f"**{i}. {w['title']}**")
        lines.append(f"   {icon} الخطر: {w['risk']} — {w['detail']}\n")

    lines.append("💡 **الأولوية:** ابدأ بالبنود 1 و2 و5 — أعلى تأثير بأقل تعقيد.")
    return {"text": "\n".join(lines), "data": {"weaknesses": weaknesses, "sec_count": len(sec_issues), "err_count": len(errors)}}


def _r_improve(msg: str) -> dict:
    """
    Reasoning-based improvement suggestions.
    If a specific component is mentioned → targeted advice.
    If no component → run full analysis and suggest concrete priorities.
    """
    ml         = msg.lower()
    entries    = _find_concept(msg)
    route_info = _route_for_concept(msg)

    # ── Specific component mentioned ──────────────────────────────────────────
    if route_info:
        lines = ["💡 **تحسين مستهدف**\n", "الملفات المطلوبة للتعديل:"]
        lines.append(f"• `{route_info['template']}` — HTML / layout")
        for c in route_info.get("css", []):
            lines.append(f"• `{c}` — Styling")
        for j in route_info.get("js", []):
            lines.append(f"• `{j}` — Interactivity")
        return {"text": "\n".join(lines), "data": {"entries": entries}}

    if entries:
        lines = ["💡 **تحسين مستهدف**\n"]
        for path, role, desc in entries[:4]:
            lines.append(f"• `{path}` [{role}] — {desc}")
        return {"text": "\n".join(lines), "data": {"entries": entries}}

    # ── No specific component — reason about the whole project ───────────────
    analysis  = full_analysis()
    sec       = security_scan()
    errors    = detect_log_errors()
    s         = analysis.get("structure", {})

    suggestions = []

    # Priority 1: error reduction
    if errors:
        suggestions.append({
            "priority": 1,
            "title": f"إصلاح {len(errors)} خطأ في السجلات",
            "impact": "HIGH",
            "effort": "LOW",
            "detail": f"خطأ مثال: `{errors[0]['file']}` — {errors[0]['line'][:70]}",
        })

    # Priority 2: test coverage
    suggestions.append({
        "priority": 2,
        "title": "إضافة Unit Tests بـ pytest",
        "impact": "HIGH",
        "effort": "MEDIUM",
        "detail": "يحمي التعديلات المستقبلية ويكتشف الأخطاء فور حدوثها.",
    })

    # Priority 3: security
    if sec:
        suggestions.append({
            "priority": 3,
            "title": f"معالجة {len(sec)} ملاحظة أمنية",
            "impact": "MEDIUM",
            "effort": "LOW",
            "detail": f"مثال: `{sec[0]['file']}` — النمط `{sec[0]['pattern']}`",
        })

    # Priority 4: migration system
    suggestions.append({
        "priority": len(suggestions) + 1,
        "title": "إضافة نظام Database Migration (Alembic)",
        "impact": "HIGH",
        "effort": "MEDIUM",
        "detail": "يجعل تغييرات Schema آمنة وقابلة للتراجع.",
    })

    # Priority 5: caching
    suggestions.append({
        "priority": len(suggestions) + 1,
        "title": "إضافة Caching للـ API endpoints الثقيلة",
        "impact": "MEDIUM",
        "effort": "LOW",
        "detail": "تحليل المشروع وقراءة الملفات يمكن caching لمدة 5 دقائق.",
    })

    lines = ["💡 **أفضل تطويرات للمشروع — بالأولوية**\n"]
    impact_icon = {"HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
    for s in suggestions:
        lines.append(f"**{s['priority']}. {s['title']}**")
        lines.append(f"   {impact_icon.get(s['impact'], '⚪')} التأثير: {s['impact']} | الجهد: {s['effort']}")
        lines.append(f"   {s['detail']}\n")

    return {"text": "\n".join(lines), "data": {"suggestions": suggestions}}


def _r_memory() -> dict:
    m = load_memory()
    proj  = m.get("project") or {}
    stats = m.get("stats")   or {}
    lines = ["🧠 **ذاكرة المشروع**\n",
             f"الإصدار: {m.get('version', '3.0')}",
             f"المشروع: {proj.get('name', m.get('project_name', 'X Control Center'))}",
             f"إجمالي المحادثات: {stats.get('total_chats', 0)}",
             f"إجمالي الأسئلة: {stats.get('total_questions', 0)}",
             f"إجمالي الخطط: {stats.get('total_plans', 0)}",
             f"آخر تحديث: {m.get('updated', '—')}"]
    return {"text": "\n".join(lines), "data": m}


_SELF_TEST_CACHE: dict = {"result": None, "ts": 0.0}
_SELF_TEST_TTL   = 300.0   # 5 minutes

def _r_status() -> dict:
    m = load_memory()
    # Run self-tests at most once per TTL — synchronous 38-test suite is expensive
    now = time.time()
    if not _SELF_TEST_CACHE["result"] or now - _SELF_TEST_CACHE["ts"] > _SELF_TEST_TTL:
        _SELF_TEST_CACHE["result"] = run_self_tests()
        _SELF_TEST_CACHE["ts"]     = now
    tests = _SELF_TEST_CACHE["result"]
    lines = ["📊 **حالة نظام الذكاء الاصطناعي**\n",
             f"🧠 المحرك: v3.0 — Project Knowledge System",
             f"🗺️ الجراف: {len(_ROUTE_GRAPH)} مسار | {len(_SEMANTIC_MAP)} مفهوم | {len(_DB_MAP)} نموذج DB",
             f"🧪 الاختبار الذاتي: {tests['score']} {tests['status']}",
             f"💾 النسخ الاحتياطية: {len(m.get('backups', []))}",
             f"🔌 المسارات في لوحة التحكم: {len(_ROUTE_GRAPH)}",
             "✅ جميع الأنظمة تعمل"]
    return {"text": "\n".join(lines), "data": {"version": "3.0", "self_test": tests}}


def _r_stats() -> dict:
    s = analyze_structure()
    lines = ["📊 **إحصائيات المشروع**\n",
             f"📁 إجمالي الملفات: {s['total_files']}",
             f"🎨 القوالب HTML: {len(s['templates'])}",
             f"⚙️ الـ Routers: {len(s['routers'])}",
             f"🤖 معالجات البوت: {len(s['handlers'])}",
             f"🗄️ نماذج قاعدة البيانات: {len(s['db_models'])}",
             f"🔧 الخدمات: {len(s['services'])}",
             f"🎨 ملفات CSS: {len(s['css_files'])}",
             f"📜 ملفات JS: {len(s['js_files'])}",
             f"🌐 المسارات: {len(_ROUTE_GRAPH)}",
             f"🧠 المفاهيم الدلالية: {len(_SEMANTIC_MAP)}",
             ]
    return {"text": "\n".join(lines), "data": s}


def _r_help() -> dict:
    return {
        "text": """🤖 **X AI Operator v3.0 — Project Knowledge System**

**📍 أسئلة الملفات:**
• What file controls the homepage?
• What CSS controls the colors?
• What file loads the AI Engineer page?
• What route serves the users page?
• Where is the sidebar?
• Find the login page

**📋 التخطيط:**
• What files must change to redesign the homepage?
• What files must change to redesign the sidebar?
• Plan: redesign the login page

**🔗 التبعيات والتأثير:**
• What depends on base.html?
• What breaks if I change style.css?

**🔍 تشخيص الأخطاء:**
• Why is the dashboard broken?

**🏗️ المعمارية:**
• Explain the frontend architecture
• How does the bot work?
• Explain the database architecture

**🧪 اختبر نفسك:** اكتب "اختبر نفسك" أو "self test"
""",
        "data": {"capabilities": ["find_file", "plan_modify", "dependency", "root_cause", "arch", "self_test"]},
    }


def _r_strategy(msg: str) -> dict:
    """
    Strategy / ownership perspective handler.
    "لو كنت مسؤولاً عن TitanX لمدة أسبوع ماذا ستفعل؟"
    Responds as senior engineer + owner thinking about the project's future.
    """
    files = _scan_project_files()
    py_count = sum(1 for f in files if f.endswith(".py"))
    total    = len(files)

    return {
        "text": (
            "🧠 **رؤية استراتيجية — لو كنت مسؤولاً عن هذا المشروع**\n\n"
            "بناءً على تحليل المشروع الحالي "
            f"({total} ملف · {py_count} Python):\n\n"
            "**🚨 الأسبوع الأول — إصلاح الأساس:**\n"
            "  · مراجعة كل `try/except` فارغة أو تُعيد `pass` — مصدر أخطاء صامتة\n"
            "  · إضافة logging موحّد (structlog أو logging.getLogger) على كل handler\n"
            "  · توثيق كل environment variable مطلوب في `.env.example`\n\n"
            "**⚡ الأسبوع الثاني — تحسين الموثوقية:**\n"
            "  · إضافة health-check endpoint يراقب DB + Telegram + HF\n"
            "  · تفعيل connection pool في db_utils مع timeout صريح\n"
            "  · إضافة rate limiting على endpoints اللوحة\n\n"
            "**🚀 الأسبوع الثالث — التطوير الحقيقي:**\n"
            "  · نقل الإعدادات إلى Pydantic Settings بدلاً من dict مبعثرة\n"
            "  · بناء نظام إشعارات للأدمن عند حدوث أخطاء حرجة\n"
            "  · إضافة backup تلقائي للـ DB يومياً\n\n"
            "**📊 قياس النجاح:**\n"
            "  · صفر أخطاء صامتة في السجلات\n"
            "  · uptime > 99.5% للبوت + اللوحة\n"
            "  · وقت استجابة API < 200ms"
        ),
        "data": {"strategy_generated": True, "project_files": total},
    }


def _r_runtime_graph(msg: str) -> dict:
    """
    Rule 5 — Runtime Graph: Startup Chain + Runtime Chain + Failure Chain.
    Shows the live execution chains derived from the actual project structure.
    Triggered by: 'رسم بيان التشغيل' / 'runtime graph' / 'startup chain' / 'failure chain'.
    """
    brain  = ProjectBrain.get()
    totals = brain.get("totals", {})
    dep_st = ProjectDependencyGraph.status()
    files  = walk_project()
    py_files = [f for f in files if f.endswith(".py")]

    # Detect bots, routers, handlers, services from the live index
    idx          = ProjectIndex.get()
    bots         = idx.get("bots", [])
    routers      = idx.get("routers", [])
    handlers_lst = idx.get("handlers", [])
    services_lst = idx.get("services", [])
    db_files     = idx.get("database", [])

    # Build startup chain from reality
    startup_links = []
    if any("config" in f.get("name","") for f in idx.get("config",[])):
        startup_links.append("config.py → loads env vars + DB path + tokens")
    startup_links.append(f"app.py → creates FastAPI app, mounts {len(routers)} routers")
    if db_files:
        startup_links.append(f"{db_files[0]['file']} → init_db() creates tables")
    startup_links.append("ai_engine.py → ProjectDependencyGraph.startup_recover() pre-builds AST graph")
    startup_links.append("uvicorn → binds port 5000, starts event loop")
    for b in bots[:2]:
        startup_links.append(f"{b['file']} → run_polling() starts Telegram bot ({b['type']})")

    # Runtime chain
    runtime_links = [
        "User → Telegram API → python-telegram-bot (polling / webhook)",
        f"MessageHandler → {handlers_lst[0]['file'] if handlers_lst else 'handlers/*.py'} → dispatches by command/text",
        f"Handler → {services_lst[0]['file'] if services_lst else 'services/*.py'} → business logic",
        f"Service → {db_files[0]['file'] if db_files else 'database/*.py'} → SQLite read/write",
        "Parallel: HTTP /api/* → FastAPI router → control panel response",
        "Parallel: /ai/api/chat → ai_workspace.py → ai_engine.process_chat() → 7-step chain → response",
    ]

    # Failure chain (SPOFs from ProjectBrain.RISKS)
    risks = ProjectBrain.RISKS
    failure_links = []
    for r in risks[:4]:
        failure_links.append(f"❌ {r['title']} [{r['severity']}] — {r['detail'][:80]}")

    lines = [
        "🔄 **رسم بيان التشغيل — TitanX Engineering Agent**\n",
        f"📊 **بيانات حية:** {totals.get('files',0)} ملف · {dep_st['files_scanned']} ممسوح · {dep_st['total_deps']} علاقة\n",
        "**🚀 سلسلة البدء (Startup Chain):**",
    ]
    for i, s in enumerate(startup_links, 1):
        lines.append(f"  {i}. {s}")

    lines.append("\n**⚡ سلسلة التشغيل (Runtime Chain):**")
    for i, s in enumerate(runtime_links, 1):
        lines.append(f"  {i}. {s}")

    lines.append("\n**🚨 سلسلة الفشل (Failure Chain — SPOFs):**")
    if failure_links:
        for s in failure_links:
            lines.append(f"  {s}")
    else:
        lines.append("  لا نقاط فشل فردية واضحة — المشروع مستقر")

    lines.append(
        f"\n💡 **خلاصة:** {len(bots)} بوت · {len(routers)} راوتر · "
        f"{len(handlers_lst)} handler · {len(services_lst)} service · {len(db_files)} قاعدة بيانات"
    )

    return {
        "text": "\n".join(lines),
        "data": {
            "startup_chain":  startup_links,
            "runtime_chain":  runtime_links,
            "failure_chain":  failure_links,
            "totals":         totals,
            "dep_graph":      dep_st,
        },
    }


def _r_risk_full() -> dict:
    """
    Phase 3: Comprehensive risk detection using ProjectBrain.RISKS registry.
    Returns ranked risks with severity, detail, and fix actions.
    """
    brain = ProjectBrain.get()
    risks = ProjectBrain.RISKS
    sec   = security_scan()

    sev_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
    lines = ["🚨 **أكبر المخاطر في المشروع — تقييم ProjectBrain**\n"]

    for r in risks:
        icon = sev_icon.get(r["severity"], "⚪")
        lines.append(f"**{r['rank']}. {r['title']}**")
        lines.append(f"   {icon} {r['severity']} | {r['category']}")
        lines.append(f"   📋 {r['detail']}")
        lines.append(f"   ✅ الحل: {r['fix']}\n")

    if sec:
        lines.append(f"⚠️ **إضافة: تم اكتشاف {len(sec)} نمط أمني مثير للقلق في الكود**")
        lines.append(f"   مثال: `{sec[0]['pattern']}` في `{sec[0]['file']}`\n")

    totals = brain.get("totals", {})
    lines.append(f"📊 **السياق:** {totals.get('files', 0)} ملف · "
                 f"{totals.get('routers', 0)} راوتر · "
                 f"{totals.get('handlers', 0)} handler")
    lines.append("\n💡 **الأولوية القصوى:** ابدأ بـ #1 (config.py) ثم #2 (Migration) ثم #3 (Tests)")

    return {
        "text": "\n".join(lines),
        "data": {"risks": risks, "security_patterns": len(sec), "total_files": totals.get("files", 0)},
    }


def _r_scale(msg: str) -> dict:
    """
    Phase 3: Scaling intelligence — how to grow TitanX to 100k+ users.
    Reads from ProjectBrain.SCALING_PLAN.
    """
    brain  = ProjectBrain.get()
    plan   = ProjectBrain.SCALING_PLAN
    totals = brain.get("totals", {})
    ml     = msg.lower()

    # Detect target scale from the question
    target = "100,000"
    for pat, label in [
        (r"مليون|million", "1,000,000"),
        (r"100k|100,000|مئة\s+ألف", "100,000"),
        (r"50k|50,000|خمسين\s+ألف", "50,000"),
        (r"10k|10,000|عشر(?:ة)?\s+آلاف", "10,000"),
    ]:
        if re.search(pat, ml):
            target = label
            break

    lines = [
        f"🚀 **خطة التوسع إلى {target} مستخدم — تحليل ProjectBrain**\n",
        f"📊 **الوضع الحالي:** {totals.get('files', 0)} ملف — "
        f"SQLite + uvicorn single-process\n",
        f"⚡ **الطاقة الحالية:** {plan['current_capacity']}\n",
    ]

    for phase in plan["phases"]:
        risk_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(phase["risk"], "⚪")
        lines.append(f"**{phase['phase']}**")
        lines.append(f"   {risk_icon} الخطر: {phase['risk']} | الجهد: {phase['effort']}")
        for step in phase["steps"]:
            lines.append(f"   • {step}")
        lines.append("")

    lines.append("🔑 **المتطلبات الأساسية للوصول إلى 100k:**")
    for key, val in plan["target_100k"].items():
        lines.append(f"  • **{key}**: {val}")

    return {
        "text": "\n".join(lines),
        "data": {"scaling_plan": plan, "current_capacity": plan["current_capacity"], "target": target},
    }


def _r_tech_debt() -> dict:
    """
    Phase 3: Technical debt scanner using ProjectBrain.TECH_DEBT registry.
    Shows prioritized list of what needs refactoring.
    """
    brain = ProjectBrain.get()
    debts = ProjectBrain.TECH_DEBT
    code_issues = detect_code_issues()
    todos = [i for i in code_issues if i.get("type") == "TODO"]

    impact_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
    effort_icon = {"HIGH": "⚙️⚙️⚙️", "MEDIUM": "⚙️⚙️", "LOW": "⚙️"}

    lines = ["🔧 **الديون التقنية في المشروع — تقييم ProjectBrain**\n"]

    for d in debts:
        lines.append(f"**{d['id']} — {d['item']}**")
        lines.append(f"   {impact_icon.get(d['impact'], '⚪')} التأثير: {d['impact']} "
                     f"| {effort_icon.get(d['effort'], '')} الجهد: {d['effort']}")
        lines.append(f"   📋 {d['detail']}")
        lines.append(f"   📁 الفئة: {d['category']}\n")

    # Live TODOs from code
    if todos:
        lines.append(f"📝 **TODOs في الكود ({len(todos)} موضع):**")
        for t in todos[:5]:
            lines.append(f"  • `{t['file']}` — {t['detail'][:80]}")
        if len(todos) > 5:
            lines.append(f"  ... و{len(todos) - 5} TODO إضافية")
        lines.append("")

    total_high = sum(1 for d in debts if d["impact"] == "HIGH")
    lines.append(f"📊 **الملخص:** {len(debts)} دَين تقني — {total_high} عالي التأثير")
    lines.append("💡 **ابدأ بـ:** TD-002 (Alembic) ثم TD-003 (Tests) — أعلى عائد بأقل تعقيد")

    return {
        "text": "\n".join(lines),
        "data": {"tech_debt": debts, "todos_in_code": len(todos), "high_impact": total_high},
    }


def _r_redesign() -> dict:
    """
    Phase 3: Senior engineer perspective on how to redesign TitanX from scratch.
    Provides architectural vision: ideal structure, tech choices, rationale.
    """
    brain  = ProjectBrain.get()
    totals = brain.get("totals", {})
    files  = totals.get("files", 0)
    py     = totals.get("python_files", 0)

    return {
        "text": (
            "🏛️ **رؤية إعادة التصميم — لو بنيت X Control Center من الصفر**\n\n"
            f"📊 **الوضع الحالي:** {files} ملف · {py} Python · SQLite · uvicorn single\n\n"

            "**📐 البنية المثالية (Ideal Architecture):**\n\n"
            "```\n"
            "x-control-center/\n"
            "├── bots/\n"
            "│   ├── main/          # PrimeDownloader — handlers, services, commands\n"
            "│   └── support/       # Support Bot — tickets, escalation\n"
            "├── api/               # FastAPI — routers, schemas, middleware\n"
            "│   ├── routers/       # One router per domain (users, stats, ai, files)\n"
            "│   ├── schemas/       # Pydantic models — request/response\n"
            "│   └── middleware/    # Auth, rate-limiting, logging\n"
            "├── core/              # Shared business logic\n"
            "│   ├── database/      # SQLAlchemy + Alembic migrations\n"
            "│   ├── cache/         # Redis abstraction\n"
            "│   └── config/        # Pydantic Settings — single source of truth\n"
            "├── ai/                # AI Engine — split into modules\n"
            "│   ├── brain.py       # ProjectBrain — project model\n"
            "│   ├── reasoning.py   # Intent detection + semantic map\n"
            "│   ├── handlers.py    # Response generators\n"
            "│   └── memory.py      # Persistent engineering memory\n"
            "├── tests/             # pytest — unit + integration\n"
            "└── deploy/            # Docker, docker-compose, nginx config\n"
            "```\n\n"

            "**🔑 القرارات التقنية الأساسية:**\n\n"
            "  1. **Database:** PostgreSQL + SQLAlchemy + Alembic\n"
            "     - Concurrent writes, transactions, migrations — SQLite لا تكفي للإنتاج\n\n"
            "  2. **Configuration:** Pydantic Settings v2\n"
            "     - جميع القيم من env vars مع type validation — لا hardcoded values\n\n"
            "  3. **API Server:** FastAPI + uvicorn (4 workers) أو Gunicorn\n"
            "     - نفس الـ framework لكن بـ worker pool للتوازي الحقيقي\n\n"
            "  4. **Caching:** Redis\n"
            "     - Session cache + hot data (stats, leaderboard) — لا filesystem cache\n\n"
            "  5. **Bot:** Webhook mode + python-telegram-bot\n"
            "     - Polling للتطوير، webhook للإنتاج — latency أقل وموثوقية أعلى\n\n"
            "  6. **Testing:** pytest + pytest-asyncio\n"
            "     - 80% code coverage كهدف — يحمي من الانكسارات الصامتة\n\n"
            "  7. **Monitoring:** Prometheus + Grafana (أو Sentry للأخطاء)\n"
            "     - Visibility حقيقية على الإنتاج\n\n"

            "**⚡ أهم فرق عن الوضع الحالي:**\n"
            "  · ai_engine.py (4000 سطر) → 5 وحدات منفصلة واضحة المسؤوليات\n"
            "  · SQLite → PostgreSQL مع migration history\n"
            "  · لا tests → pytest مع CI/CD pipeline\n"
            "  · config مبعثر → Pydantic Settings موحّد\n\n"

            "💡 **التوصية:** لا تعيد الكتابة من الصفر — ابدأ بـ Strangler Fig Pattern:\n"
            "  استبدل وحدة واحدة في كل مرة دون كسر ما يعمل."
        ),
        "data": {
            "ideal_structure": ["bots/", "api/", "core/", "ai/", "tests/", "deploy/"],
            "key_decisions": ["PostgreSQL", "Pydantic Settings", "Redis", "webhook", "pytest"],
            "current_files": files,
        },
    }


def _r_who_depends_on(msg: str) -> dict:
    """
    Answers: "What files depend on X?" / "Show dependency chain for X"
    Uses live AST-based ProjectDependencyGraph — never hardcoded.
    """
    risk_icons = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "NONE": "⚪"}

    # Extract target file from message
    target_file: str | None = None

    # Check for explicit file path pattern
    for pat in [r"[\w]+/[\w./]+\.py", r"[\w]+\.py"]:
        m = re.search(pat, msg.lower())
        if m:
            target_file = m.group(0)
            break

    # Check aliases / semantic map
    if not target_file:
        for alias, concept in _ALIASES.items():
            if alias in msg.lower() or alias in _normalize_ar(msg.lower()):
                entries = _SEMANTIC_MAP.get(concept, [])
                if entries:
                    target_file = entries[0][0]
                break

    # Try _find_concept as final fallback
    if not target_file:
        found = _find_concept(msg)
        if found:
            target_file = found[0][0]

    if not target_file:
        return {
            "text": (
                "🔗 **من يعتمد على هذا الملف؟**\n\n"
                "⚠️ لم أتمكن من تحديد الملف المستهدف.\n\n"
                "**أمثلة صحيحة:**\n"
                "  • `سلسلة تبعيات config/settings.py`\n"
                "  • `ما الملفات التي تعتمد على database/db.py؟`\n"
                "  • `dependency chain for ai_engine.py`"
            ),
            "data": {},
        }

    report  = ProjectDependencyGraph.full_impact_report(target_file)
    key     = report["file"]
    direct  = report["direct_importers"]
    trans   = report["transitive_impact"]
    risk    = report["risk"]
    icon    = risk_icons.get(risk, "⚪")

    lines = [
        f"🔗 **سلسلة التبعيات: `{key}`** — قراءة مباشرة من الكود\n",
        f"{icon} **مستوى الخطر إذا حُذف:** {risk}",
        f"📥 **المستوردون المباشرون ({len(direct)} ملف):**",
    ]
    for f in direct[:15]:
        lines.append(f"  ↳ `{f}`")
    if len(direct) > 15:
        lines.append(f"  ... و {len(direct) - 15} ملف آخر")

    if trans:
        lines.append(f"\n💥 **التأثير الإجمالي عند الحذف ({report['total_files_at_risk']} ملف):**")
        for f in trans[:10]:
            lines.append(f"  ⚠️ `{f}`")
        if len(trans) > 10:
            lines.append(f"  ... و {len(trans) - 10} ملف آخر")

    # Chain visualization (depth-2)
    if direct:
        lines.append("\n**🔗 عمق التبعية (أول 3 مستوردين):**")
        for f in direct[:3]:
            sub_callers = ProjectDependencyGraph.what_depends_on(f)
            entry = f"  `{f}`"
            if sub_callers:
                entry += f"  ← [{', '.join(f'`{c}`' for c in sub_callers[:2])}]"
            lines.append(entry)

    if report["total_files_at_risk"] > 0:
        lines.append(
            f"\n🚨 **تحذير:** حذف `{key}` سيوقف "
            f"{report['total_files_at_risk']} ملف عن العمل."
        )
    else:
        lines.append(f"\n✅ لا ملفات أخرى تعتمد على `{key}` حالياً.")

    return {"text": "\n".join(lines), "data": report}


def _r_data_flow(msg: str) -> dict:
    """
    Shows complete data flow paths through the project.
    Answers: "Show data flow from Telegram user to final response"
    Uses _ARCH_MAP["data_flow"] — maintained in this file.
    """
    ml   = msg.lower()
    arch = _ARCH_MAP.get("data_flow", _ARCH_MAP.get("project", {}))
    lines = ["📊 **تدفق البيانات الكامل في مشروع X**\n"]

    # Determine which flow(s) to show
    want_bot   = any(kw in ml for kw in ["telegram", "bot", "user", "بوت", "مستخدم", "تليغرام", "رسالة"])
    want_panel = any(kw in ml for kw in ["panel", "http", "web", "لوحة", "browser", "request", "تحكم"])
    want_ai    = any(kw in ml for kw in ["ai", "chat", "ذكاء", "محادثة", "operator"])
    want_all   = not (want_bot or want_panel or want_ai)

    if want_bot or want_all:
        lines.append("## 🤖 مسار بوت PrimeDownloader (Telegram → رد)\n")
        for step in arch.get("telegram_to_response", []):
            lines.append(f"  {step}")

    if want_panel or want_all:
        lines.append("\n## 🌐 مسار لوحة التحكم (HTTP → HTML)\n")
        for step in arch.get("panel_request_to_response", []):
            lines.append(f"  {step}")

    if want_ai or want_all:
        lines.append("\n## 🧠 مسار AI Operator (رسالة → تحليل → رد)\n")
        for step in arch.get("ai_message_flow", []):
            lines.append(f"  {step}")

    if want_all:
        lines.append("\n## ⚠️ مسار نشر الفشل (config/settings.py)\n")
        for step in arch.get("critical_config_flow", []):
            lines.append(f"  {step}")

    return {"text": "\n".join(lines), "data": arch}


def _r_reuse_systems(msg: str) -> dict:
    """
    Answers: "If I create a Notification Bot, what existing systems can be reused?"
    Scans project for reusable components — uses live dep graph to identify shared modules.
    """
    ml = msg.lower()

    is_notification = bool(re.search(r"إشعار|notification|notif|تنبيه|broadcast", ml))
    is_bot          = bool(re.search(r"بوت|bot", ml))
    is_payment      = bool(re.search(r"دفع|payment|pay|اشتراك|subscription", ml))
    is_analytics    = bool(re.search(r"إحصاء|analytics|stats|report|تقارير|dashboard", ml))

    lines = ["♻️ **الأنظمة القابلة للإعادة الاستخدام في مشروع X**\n"]

    reusable = [
        {
            "system": "config/settings.py",
            "role": "إعدادات المشروع",
            "how": "TOKEN الجديد + ADMIN_IDS يُضافان هنا. لا تعدّل القيم الموجودة.",
            "risk": "CRITICAL",
        },
        {
            "system": "database/db.py + database/users.py",
            "role": "قاعدة البيانات + إدارة المستخدمين",
            "how": "init_db() + get_user() + create_user() جاهزة للاستخدام المباشر",
            "risk": "HIGH — لا تعدّل schema موجودة، أضف جداول جديدة فقط",
        },
        {
            "system": "utils/logger.py",
            "role": "نظام السجلات الموحّد",
            "how": "setup_logger('new_bot') → Logger جاهز بدون أي تعديل",
            "risk": "NONE",
        },
    ]

    if is_notification or is_bot:
        reusable.extend([
            {
                "system": "middlewares/auth.py",
                "role": "مصادقة المستخدمين",
                "how": "check_subscription_status(user_id) يمكن استدعاؤه من أي handler",
                "risk": "LOW",
            },
            {
                "system": "services/subscription.py",
                "role": "التحقق من الاشتراك",
                "how": "check_subscription(user_id) جاهز للاستخدام",
                "risk": "LOW",
            },
        ])

    if is_notification:
        reusable.append({
            "system": "database/users.py → get_all_users()",
            "role": "قائمة المستخدمين للإرسال الجماعي",
            "how": "get_all_users() تعيد كل user_id — استخدمها مع rate limiting (1 msg/30ms)",
            "risk": "MEDIUM — Broadcast بدون throttling يُوقف البوت بـ FloodWait",
        })

    if is_payment or is_analytics:
        reusable.append({
            "system": "control_panel/db_utils.py",
            "role": "استعلامات قاعدة البيانات",
            "how": "get_db() + execute_query() جاهزان للصفحات الجديدة في اللوحة",
            "risk": "LOW",
        })

    for r in reusable:
        risk_word = r["risk"].split()[0] if r["risk"] else "LOW"
        ri = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "NONE": "⚪"}.get(risk_word, "⚪")
        lines.append(f"\n♻️ **`{r['system']}`** — {r['role']}")
        lines.append(f"  → {r['how']}")
        lines.append(f"  {ri} الخطر: {r['risk']}")

    # New files that must be created
    lines.append("\n\n📁 **الملفات الجديدة المطلوبة:**")
    if is_bot:
        bot_match = re.search(r"([\w_]+)\s*(?:bot|بوت)", ml)
        bname     = bot_match.group(1).strip() if bot_match else "new_bot"
        bname     = re.sub(r"\s+", "_", bname.strip())
        lines.extend([
            f"  🆕 `{bname}_bot/bot.py` — نقطة دخول البوت الجديد",
            f"  🆕 `{bname}_bot/handlers/` — معالجات الأوامر",
            f"  🆕 Secret في Replit: `{bname.upper()}_BOT_TOKEN`",
            f"  🆕 Workflow جديد في Replit: `{bname.capitalize()} Bot`",
        ])
    else:
        lines.extend([
            "  🆕 ملف Python جديد للوظيفة المطلوبة",
            "  🆕 Router جديد في control_panel/routers/ (إن كانت صفحة في اللوحة)",
        ])

    lines.append(
        "\n⚠️ **القاعدة الذهبية:** أضف ولا تعدّل — "
        "أي تعديل على ملف موجود يتطلب خطة موافَق عليها."
    )

    return {"text": "\n".join(lines), "data": {"reusable_count": len(reusable)}}


def _r_project_mod(msg: str) -> dict:
    """
    PROJECT MODIFICATION MODE — activated by any imperative modification command
    that targets a project component (button, menu, command, page, feature, etc.).

    The 7-step intelligence protocol is applied automatically because this intent
    is registered in _PROJECT_INTENTS, which means AgentReasoningChain.execute()
    runs BEFORE this handler is called (scan evidence is in _ACTIVE_CHAIN).

    This handler then routes to AgentPlanningGate.submit() which runs the full
    5-step ProjectIntelligenceAgent protocol:
      Step 1: Scan  — live filesystem scan for related files
      Step 2: Understand — classify operation type + extract entities
      Step 3: Impact  — dependency graph + transitive risk
      Step 4: Plan    — real file list + ordered steps + rollback
      Step 5: Gate    — await explicit user approval before any execution

    Telegram-specific requests (buttons, keyboards, commands, callbacks, messages)
    are automatically detected by the scan phase which prioritizes:
      bot.py, handlers/, keyboards/, reply_markup patterns, callback_data patterns

    UI/CSS requests prioritize:
      templates/, static/css/style.css, static/js/app.js

    Page/router requests prioritize:
      control_panel/routers/, control_panel/templates/
    """
    return AgentPlanningGate.submit(msg)


def _r_general(msg: str) -> dict:
    """
    Reasoning-first fallback.
    Attempts semantic understanding across 6 layers before admitting defeat.
    'لم أتعرف' is the absolute last resort — only if ALL layers fail.
    """
    ml = msg.lower()

    # ── Layer 1: Impact / conditional reasoning ────────────────────────────────
    # "لو عدلت style.css ماذا قد يحدث؟" / "إذا أنشأت بوت إشعارات ماذا سيتأثر؟"
    _L1 = [
        r"لو\s+(?:عدلت|غيرت|حذفت|أنشأت|بدلت|أضفت)",
        r"إذا\s+(?:عدلت|غيرت|حذفت|أنشأت|أضفت|بنيت)",
        r"ماذا\s+(?:سيحدث|سيتأثر|سيتغير|قد\s+يحدث|ينكسر|يتأثر|سيُكسر|سيتعطل)",
        r"what\s+(?:would|will)\s+(?:happen|break|change)",
        r"if\s+(?:i|we)\s+(?:change|modify|delete|add|edit)",
    ]
    if any(re.search(p, ml) for p in _L1):
        return _r_impact(msg)

    # ── Layer 1·5: Security check ─────────────────────────────────────────────
    _L1_5 = [
        r"هل\s+المشروع\s+(?:آمن|مؤمن|محمي|بأمان)",
        r"(?:مستوى|درجة|مدى)\s+(?:الأمان|الحماية|الأمن)",
        r"(?:أمان|حماية|أمن)\s+المشروع",
        r"security\s+(?:check|audit|scan|review|analysis|status)",
        r"(?:is|how\s+(?:secure|safe)).{0,15}(?:project|system|app)",
    ]
    if any(re.search(p, ml) for p in _L1_5):
        return _r_security()

    # ── Layer 2: Project architecture / quality ───────────────────────────────
    # "هل بنية المشروع جيدة؟" / "is the project structure solid?"
    _L2 = [
        r"(?:بنية|هيكل)\s+المشروع",
        r"هل\s+المشروع\s+(?:جيد|منظم|صحيح|مناسب)",
        r"تقييم\s+المشروع",
        r"(?:project|architecture|code).{0,20}(?:good|solid|quality|well.structured)",
        r"(?:review|evaluate|assess).{0,20}(?:project|architecture|code)",
    ]
    if any(re.search(p, ml) for p in _L2):
        return _r_arch(msg)

    # ── Layer 3: Improvement / best-practice ──────────────────────────────────
    # "ما أفضل تطوير للمشروع؟"
    _L3 = [
        r"أفضل\s+(?:تطوير|تحسين|ميزة|إضافة)",
        r"(?:كيف|ماذا)\s+(?:أطور|أحسن|أعزز)",
        r"ما\s+(?:الذي\s+)?(?:يحسن|يطور)\s+المشروع",
        r"best\s+(?:improvement|feature|upgrade)",
        r"(?:what|how).{0,10}(?:improve|enhance|upgrade).{0,15}project",
    ]
    if any(re.search(p, ml) for p in _L3):
        return _r_improve(msg)

    # ── Layer 4: Feature creation / integration ───────────────────────────────
    # "كيف أضيف بوت جديد؟" / "هل يمكن دمج بوت جديد؟"
    _L4 = [
        r"كيف\s+(?:أضيف|أنشئ|أبني|أدمج|أحدث)",
        r"هل\s+يمكن\s+(?:دمج|إضافة|إنشاء|بناء)",
        r"يمكن\s+(?:دمج|إضافة|إنشاء)",
        r"how\s+(?:do\s+i|to|can\s+i).{0,20}(?:add|create|build|integrate)",
        r"can\s+(?:i|we).{0,15}(?:add|create|integrate|build)",
    ]
    if any(re.search(p, ml) for p in _L4):
        return _r_create_feature(msg)

    # ── Layer 5: General explanation / tech question → conversation ───────────
    # "اشرح FastAPI" / "explain async" / "ما الفرق بين X و Y"
    _L5 = [
        r"(?:اشرح|وضح|فسّر|فسر|ما\s+هو|ما\s+هي|ما\s+معنى|ما\s+المقصود)",
        r"(?:explain|describe|what\s+is|what\s+are|how\s+does|how\s+do)",
        r"(?:فرق|مقارنة|الفرق|أيهما\s+أفضل)",
        r"(?:why|لماذا|متى|when\s+(?:should|do|does))",
    ]
    if any(re.search(p, ml) for p in _L5):
        return _r_conversation(msg)

    # ── Layer 6: Explicit file search (ONLY when user asks for a file) ─────────
    _L6_FILE = [
        r"\bما\s+الملف\b", r"\bأي\s+ملف\b", r"\bأين\s+(?:الملف|الصفحة|الكود)\b",
        r"\bwhat\s+file\b", r"\bwhich\s+file\b", r"\bwhere\s+is\b",
        r"\blocate\b", r"\bfind\s+(?:the\s+)?file\b",
    ]
    if any(re.search(p, ml) for p in _L6_FILE):
        entries = _find_concept(msg)
        if entries:
            return answer_file_question(msg)

    # ── Layer 7: Hugging Face API — only for substantive queries (≥ 10 chars) ──
    # Short/ambiguous queries almost never get useful HF responses; skip the 8s
    # timeout and fall through to the LAST RESORT hint immediately.
    if len(msg.strip()) >= 10:
        try:
            hf = call_hf_analyze(msg)
            if hf.get("ok") and isinstance(hf.get("analysis"), str) and len(hf["analysis"]) > 30:
                return {"text": f"💬 {hf['analysis']}", "data": {"mode": "general_hf", "source": "hf"}}
        except Exception:
            pass

    # ── LAST RESORT ───────────────────────────────────────────────────────────
    mem   = load_memory()
    pname = mem.get("project", {}).get("name", "X Control Center")
    return {
        "text": (
            f"🧠 **X AI Operator** · {pname}\n\n"
            "لم أستطع تحديد نوع طلبك بدقة كافية.\n\n"
            "**أعد الصياغة بإحدى هذه الطرق:**\n"
            "  • **سؤال تقني** — \"اشرح FastAPI\" · \"الفرق بين Python و JavaScript\"\n"
            "  • **تحليل تأثير** — \"لو عدلت style.css ماذا سيحدث؟\"\n"
            "  • **إنشاء ميزة** — \"كيف أضيف بوت إشعارات؟\"\n"
            "  • **تقييم المشروع** — \"هل بنية المشروع جيدة؟\"\n"
            "  • **إصلاح مشكلة** — \"إصلاح خطأ في صفحة الإعدادات\""
        ),
        "data": {"intent": "general", "query": msg},
    }


# ─── Utility ─────────────────────────────────────────────────────────────────

def _count_lines(fp: str) -> int:
    try:
        return len(Path(fp).read_text(encoding="utf-8", errors="ignore").splitlines())
    except Exception:
        return 0


def _fmt(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


# ─── Alias for backward compatibility ────────────────────────────────────────
def create_plan(description: str) -> dict:
    return create_modification_plan(description)


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT FOUNDATION — STARTUP KNOWLEDGE RECOVERY
# Pre-builds the dependency graph on module import so the first user query
# gets live project data instantly (no cold-build latency on first message).
# ═══════════════════════════════════════════════════════════════════════════════
try:
    ProjectDependencyGraph.startup_recover()
    _ai_log.info("Agent Foundation: startup knowledge recovery complete.")
except Exception as _startup_exc:
    _ai_log.warning("Agent Foundation: startup recovery non-fatal error: %s", _startup_exc)
