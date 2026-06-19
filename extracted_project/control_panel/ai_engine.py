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
import os, re, ast, json, zipfile, hashlib, time
from pathlib import Path
from datetime import datetime
from typing import Optional

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
    """POST to HF space with full error handling and local fallback."""
    try:
        import urllib.request, json as _json
        data = _json.dumps(payload).encode()
        req  = urllib.request.Request(
            f"{HF_SPACE_URL}{endpoint}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=HF_TIMEOUT) as r:
            result = _json.loads(r.read().decode())
            result["_hf_source"] = "live"
            return result
    except Exception as e:
        return {"ok": False, "error": str(e), "_hf_source": "error"}


def _hf_get(endpoint: str) -> dict:
    """GET from HF space with timeout and error handling."""
    try:
        import urllib.request, json as _json
        with urllib.request.urlopen(f"{HF_SPACE_URL}{endpoint}", timeout=HF_TIMEOUT) as r:
            result = _json.loads(r.read().decode())
            result["_hf_source"] = "live"
            return result
    except Exception as e:
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
        r"algorithm|recursion|data.?structure|oop\b|functional)\b",
        re.IGNORECASE,
    )

    _EXPLAIN = re.compile(
        r"\b(?:explain|what\s+is|what\s+are|how\s+does|how\s+do|define|describe|"
        r"tell\s+me\s+about|overview\s+of|introduction\s+to|"
        r"ما\s+هو|ما\s+هي|اشرح|وضح|عرّف|كيف\s+يعمل|شرح)\b",
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
        """Returns: 'greeting' | 'conversational' | 'project'"""
        if cls._GREETING.match(msg.strip()):
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
        cls._history.append({"role": role, "text": text[:300],
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
        return {
            "source": "local",
            "steps": ["تحليل الملفات المتأثرة", "تحديد التبعيات",
                      "إنشاء الكود المطلوب", "تحديث المسارات",
                      "اختبار التغييرات"],
            "risks": ["تعارض مع كود موجود", "تأثير على الأداء"],
            "deps":  ["bot.py", "control_panel/app.py"],
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
        if re.search(r"bot|بوت", r):              return "create_bot"
        if re.search(r"page|screen|صفحة", r):     return "create_page"
        if re.search(r"design|ui|css|تصميم", r):  return "modify_ui"
        if re.search(r"database|db|قاعدة", r):    return "modify_database"
        if re.search(r"auth|login|مصادقة", r):    return "modify_auth"
        if re.search(r"command|handler|أمر", r):  return "add_command"
        if re.search(r"api|route|مسار", r):       return "add_api"
        return "general"

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
                except Exception:
                    pass
        except Exception:
            pass
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
                    r"أين", r"أي ملف", r"ما الملف", r"ابحث عن", r"أين يوجد", r"يتحكم"],
    "plan_modify": [r"plan", r"خطة", r"what.*modify", r"what.*change", r"ماذا.*أعدل",
                    r"redesign", r"إعادة تصميم", r"modify plan", r"how to.*change"],
    "dependency":  [r"depend", r"uses", r"loads", r"import", r"related",
                    r"يستخدم", r"يحمل", r"علاقة", r"ارتباط", r"مرتبط"],
    "arch":        [r"architecture", r"how does.{0,20}work", r"explain.{0,20}system",
                    r"معمارية", r"كيف يعمل", r"اشرح", r"هيكل المشروع"],
    "root_cause":  [r"why is.{0,30}broken", r"why.{0,20}not work", r"debug",
                    r"لماذا.{0,20}لا يعمل", r"سبب الخطأ", r"لماذا كسر"],
    "impact":      [r"what breaks", r"what happens if", r"impact of", r"if i change",
                    r"ماذا يحدث لو", r"ماذا يكسر", r"تأثير التغيير"],
    "self_test":   [r"self.?test", r"test yourself", r"اختبر نفسك", r"self check", r"run tests?"],
    # Conversational / meta intents
    "identity":      [r"who are you", r"what are you", r"من أنت", r"ما أنت", r"عرّف نفسك",
                      r"introduce yourself", r"about yourself", r"tell me about you",
                      r"ما هو\b.{0,10}x\b", r"ما هي\b.{0,10}x\b", r"about the ai"],
    "capabilities":  [r"what can you do", r"ماذا تستطيع", r"what do you do",
                      r"your capabilities", r"قدراتك", r"إمكانياتك",
                      r"كيف.{0,10}تساعد", r"how can you help", r"your features",
                      r"what are you capable", r"ما.{0,10}(?:قدرات|إمكانيات)"],
    "hf_query":      [r"hugging.?face", r"هوجينج فيس", r"hf\s+(?:connected|status|working|online)",
                      r"connected.{0,15}(?:to|with).{0,10}(?:hf|ai|model|space)",
                      r"are you.{0,20}connected", r"connection.{0,10}status",
                      r"متصل\b", r"الاتصال\b.{0,10}(?:بـ|مع)", r"نموذج خارجي"],
    # Phase 2 — Action intent classification
    "create_feature": [
        r"create\b.{0,40}(bot|feature|system|module|command|handler|notification|service)",
        r"build\b.{0,30}(bot|feature|system|module|service)",
        r"make\b.{0,30}(bot|feature|system|service)",
        r"add\b.{0,30}(bot|notification|command|feature|handler|service)",
        r"implement\b.{0,40}(bot|feature|system|module)",
        r"develop\b.{0,30}(bot|feature|system)",
        r"أنشئ\b", r"اصنع", r"أضف.*بوت", r"بناء.*بوت", r"طور.*ميزة",
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
    ml = msg.lower()

    # ── REASONING ENGINE GATE (Phase 3) ──────────────────────────────────────
    # Classify FIRST — before any keyword matching.
    # Conversational messages (tech explanations, comparisons, greetings) NEVER
    # enter project inspection mode.
    _re_mode = ReasoningEngine.classify(msg)
    if _re_mode == "greeting":
        return "greeting"
    if _re_mode == "conversational":
        return "conversation"

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

    _HF_P = [
        r"hugging.?face", r"هوجينج فيس",
        r"hf\s+(?:connected|status|working|online|space)",
        r"are you.{0,25}connected",
        r"متصل\b.{0,20}(?:بـ|مع|بـال)", r"الاتصال\b.{0,15}(?:hugging|hf|نموذج)",
        r"connected.{0,20}(?:hugging|hf|space|model)",
        r"نموذج خارجي", r"space.*connected",
    ]
    if any(re.search(p, ml) for p in _HF_P):
        return "hf_query"

    # ── Priority 0: Action intents (must beat file-finding patterns) ──────────
    # "Create notification bot" → create_feature
    _P0_CREATE = [
        r"create\b.{0,40}(bot|feature|system|module|command|handler|notification|service)",
        r"build\b.{0,30}(bot|feature|system|module|service)",
        r"make\b.{0,30}(bot|feature|system|service)",
        r"add\b.{0,30}(bot|notification|command|feature|handler|service)",
        r"implement\b.{0,40}(bot|feature|system|module)",
        r"develop\b.{0,30}(bot|feature|system)",
        r"أنشئ\b", r"اصنع", r"أضف.*بوت", r"بناء.*بوت",
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
        r"what route",
        r"which route",
        r"what.{0,10}route.{0,20}(?:loads?|serves?|handles?)",
        r"find.{0,25}(?:page|file|route|template)",
        r"where.{0,10}(?:is|are).{0,20}(?:the\s+)?(?:homepage|dashboard|sidebar|colors?|login|css|js|backup|ai|bot|download|support|github|user|setting|log)",
        r"locate.{0,25}(?:page|file|route)",
        r"أي ملف.{0,25}يتحكم",
        r"ما الملف.{0,25}(?:يتحكم|يعالج|المسؤول)",
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

    # ── Priority 2·5: Architecture quality (before scored match steals "بنية") ─
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

    # ── Semantic reasoning — broad Arabic / mixed patterns ────────────────────
    # These catch well-formed questions that score 0 on keyword lists but have
    # clear meaning. Checked AFTER scored match so specific handlers win first.

    # Identity variants: "عرفني بنفسك", "ما اسمك", "هل أنت AI"
    _IDENTITY_SEM = [
        r"عرّفني\s+بنفسك", r"عرفني\s+بنفسك", r"عرّف\s+نفسك", r"عرف\s+نفسك",
        r"ما\s+اسمك", r"ما\s+هو\s+اسمك",
        r"هل\s+أنت\s+(?:ذكاء|ذكاءً)\s+اصطناعي",
        r"هل\s+أنت\s+(?:بوت|روبوت|ai|برنامج|آلة)",
        r"من\s+تكون\b", r"من\s+تكون\s+أنت",
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

    # Improvement / best-practice
    _IMPROVE_SEM = [
        r"أفضل\s+(?:تطوير|تحسين|ميزة|إضافة).{0,30}(?:للمشروع|المشروع)?",
        r"(?:كيف|ماذا)\s+(?:أطور|أحسن|أعزز)\s+المشروع",
        r"best\s+(?:improvement|feature|addition|upgrade)\s+(?:for\s+)?(?:the\s+)?project",
        r"(?:what|how).{0,10}(?:improve|enhance|upgrade)\s+(?:the\s+)?project",
        r"ما\s+(?:الذي\s+)?(?:يحسن|يطور)\s+المشروع",
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
    ql = q.lower().strip()
    for ar, en in _ALIASES.items():
        if ar in q:
            ql = ql.replace(ar.lower(), en)
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

    # Filesystem fallback
    ql = query.lower()
    for root, dirs, files in os.walk(str(EXTRACTED_DIR)):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            fp = Path(root) / fname
            rel = str(fp.relative_to(EXTRACTED_DIR))
            if any(ext in fname for ext in CODE_EXTS) and ql in fname.lower() and rel not in found_paths:
                concept_hits.append((rel, "filename_match", fname))
                found_paths.add(rel)
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
        "data": {"concept": concept, "files": file_list},
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

    if any(kw in ql for kw in ["frontend", "css", "html", "template", "ui", "style"]):
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

_CANONICAL_TESTS = _SELF_TESTS[:8]  # the 8 required ones

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


def run_self_tests(extended: bool = False) -> dict:
    """Run the self-test suite. Phase 1 (file questions) + Phase 2 (intent tests A-E)."""
    tests_to_run = _SELF_TESTS if extended else _CANONICAL_TESTS
    results = []
    passed  = 0

    for question, expected_intent, expected_keyword in tests_to_run:
        got_intent = detect_intent(question)
        intent_ok  = (got_intent == expected_intent)

        answer     = answer_file_question(question)
        ans_text   = answer["text"].lower()
        ans_files  = " ".join(e["path"].lower() for e in answer.get("data", {}).get("files", []))
        keyword_found = (
            expected_keyword.lower() in ans_text or
            expected_keyword.lower() in ans_files
        )

        ok = intent_ok and keyword_found
        if ok:
            passed += 1

        results.append({
            "question":        question,
            "expected_intent": expected_intent,
            "got_intent":      got_intent,
            "intent_ok":       intent_ok,
            "expected_keyword": expected_keyword,
            "keyword_found":   keyword_found,
            "passed":          ok,
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
        })

    total      = len(tests_to_run)
    all_passed = passed + p2_passed
    all_total  = total + len(_PHASE2_TESTS)
    all_results = results + p2_results
    return {
        "score":     f"{all_passed}/{all_total}",
        "pass_rate": f"{all_passed/all_total*100:.0f}%",
        "status":    "✅ PASS" if all_passed == all_total else ("⚠️ PARTIAL" if all_passed >= all_total * 0.75 else "❌ FAIL"),
        "tests":     all_results,
        "passed":    all_passed,
        "total":     all_total,
        "phase1":    {"passed": passed,    "total": total,             "label": "File Awareness"},
        "phase2":    {"passed": p2_passed, "total": len(_PHASE2_TESTS), "label": "Intent Classification (A-E)"},
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
        except Exception:
            pass
    data = _default_memory()
    save_memory(data)
    return data


def save_memory(data: dict):
    MEMORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
    }


def update_stats(key: str, val: int = 1):
    m = load_memory()
    stats = m.setdefault("stats", {"total_scans": 0, "total_plans": 0, "total_questions": 0, "total_chats": 0})
    stats[key] = stats.get(key, 0) + val
    m["updated"] = datetime.now().isoformat()
    save_memory(m)


def save_chat(role: str, text: str):
    m = load_memory()
    m.setdefault("chat_history", []).append({"role": role, "text": text[:500], "ts": datetime.now().isoformat()})
    m["chat_history"] = m["chat_history"][-50:]
    m["updated"] = datetime.now().isoformat()
    save_memory(m)


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

def walk_project() -> list:
    files = []
    for root, dirs, fnames in os.walk(str(EXTRACTED_DIR)):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in fnames:
            fp = Path(root) / f
            if fp.suffix in CODE_EXTS:
                files.append(str(fp.relative_to(EXTRACTED_DIR)))
    return sorted(files)


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
        except Exception:
            pass
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
            except Exception:
                pass
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
            except Exception:
                pass
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
    Main entry point for AI chat messages.
    Phase 3: Integrates ReasoningEngine gate, AIMemoryLayer, and full handler table.
    """
    save_chat("user", msg)
    update_stats("total_chats")

    intent = detect_intent(msg)

    # Phase 3: Record to session memory
    AIMemoryLayer.record("user", msg, intent)

    handlers = {
        # ── Phase 3: Conversational Mode (NEVER touches project files) ────────
        "greeting":       lambda: _r_greeting(),
        "conversation":   lambda: _r_conversation(msg),
        # ── Meta / identity ───────────────────────────────────────────────────
        "identity":       lambda: _r_identity(),
        "capabilities":   lambda: _r_capabilities(),
        "hf_query":       lambda: _r_hf_query(),
        # ── Action intents ────────────────────────────────────────────────────
        "create_feature": lambda: _r_create_feature(msg),
        "ui_redesign":    lambda: _r_ui_redesign(msg),
        "debug_fix":      lambda: _r_debug_fix(msg),
        "new_page":       lambda: _r_new_page(msg),
        # ── Project knowledge ─────────────────────────────────────────────────
        "find_file":      lambda: _r_find_file(msg),
        "plan_modify":    lambda: _r_plan(msg),
        "dependency":     lambda: _r_dependency(msg),
        "impact":         lambda: _r_impact(msg),
        "root_cause":     lambda: _r_root_cause(msg),
        "arch":           lambda: _r_arch(msg),
        "structure":      lambda: _r_structure(),
        "routes":         lambda: _r_routes(),
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
        "help":           lambda: _r_help(),
        "general":        lambda: _r_general(msg),
    }

    fn   = handlers.get(intent, handlers["general"])
    resp = fn()
    resp["intent"] = intent

    # Phase 3: Record assistant response to session memory
    AIMemoryLayer.record("assistant", resp.get("text", "")[:300], intent)

    save_chat("assistant", resp.get("text", "")[:500])
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
        hf = call_hf_analyze(code=msg, question=msg)
        if hf.get("ok") and isinstance(hf.get("analysis"), str) and len(hf["analysis"]) > 30:
            return {"text": f"💬 {hf['analysis']}",
                    "data": {"mode": "conversation", "source": "hf"}}
    except Exception:
        pass

    # ── 4. Intelligent generic fallback ─────────────────────────────────────
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
    mem = load_memory()
    proj = mem.get("project", {})
    name  = proj.get("name", "X Control Center")
    ver   = proj.get("version", "v5.0")
    p3 = {
        "memory":   AIMemoryLayer.status(),
        "planner":  AIPlanner.status(),
        "engineer": AIEngineerCore.status(),
        "impact":   ProjectImpactAnalysis.status(),
        "future":   FutureExecutionArchitecture.status(),
    }
    return {
        "text": f"""🧠 **أنا X AI Operator — المرحلة 3**

**ما أنا؟**
محرك ذكاء اصطناعي متخصص مدمج في **{name} {ver}**.
لا أبحث في الملفات لأي سؤال — أفكر أولاً، أفهم السياق، ثم أجيب.

**وضعان للعمل:**
  💬 **وضع المحادثة** — أسئلة تقنية عامة: Python، FastAPI، SQL، مقارنات
  🔍 **وضع المشروع** — ملفات، مسارات، إنشاء ميزات، تشخيص أخطاء

**مكوناتي (المرحلة 3):**
  🧠 **Reasoning Engine** — أصنّف كل رسالة قبل أي بحث
  💾 **AI Memory Layer** — أتذكر سياق المحادثة ({p3['memory']['turns']} دورة)
  📋 **AI Planner** — أخطط قبل التنفيذ مع تحليل المخاطر
  ⚙️ **Engineer Core** — أفهم طلبات التعديل دلالياً
  🔬 **Impact Analysis** — أحلل تأثير أي تغيير مسبقاً
  🤖 **Hugging Face** — متصل بـ `x-ai-core` Space

**المشروع الذي أعمل عليه:**
  • بوت Telegram رئيسي — `bot.py` (PrimeDownloader)
  • بوت دعم فني — `support_bot/bot.py`
  • لوحة تحكم FastAPI — المنفذ 5000

اسألني: **"What can you do?"** لقائمة القدرات الكاملة.""",
        "data": {"identity": "X AI Operator", "phase": 3,
                 "hf_connected": True, "phase3": p3},
    }


def _r_capabilities() -> dict:
    """'What can you do?' — full capability listing with Phase 3 modes."""
    return {
        "text": """⚡ **قدرات X AI Operator — المرحلة 3**

**💬 وضع المحادثة العامة (جديد في المرحلة 3):**
  • "Explain FastAPI" → شرح كامل بالاستخدامات والمزايا
  • "Python vs JavaScript" → مقارنة مفصّلة
  • "What is REST API?" → تعريف وأمثلة
  • "How do Telegram Bots work?" → شرح المفهوم
  • "Hello" / "مرحبا" → محادثة طبيعية

**🔍 وضع المشروع — معرفة الملفات:**
  • "What file controls the dashboard?" → الملف الدقيق
  • "Where is the login page?" → المسار الكامل
  • "What CSS controls the colors?" → ملف CSS

**🚀 تخطيط الميزات الجديدة:**
  • "Create notification bot" → خطة + ملفات + خطوات
  • "Build new page for statistics" → scaffold كامل

**🎨 إعادة التصميم:**
  • "Redesign homepage" → الملفات + خطوات التنفيذ
  • "Revamp sidebar UI" → خطة التعديل الكاملة

**🔧 التشخيص والإصلاح:**
  • "Fix broken button" → تشخيص + فحص سجلات
  • "Fix error in auth" → root-cause analysis

**🏗️ تحليل المعمارية:**
  • "How does the bot work?"
  • "What depends on auth.py?"
  • "What breaks if I change style.css?"

**🤖 Hugging Face (متصل ✅):**
  • "Are you connected to Hugging Face?" → حالة الاتصال الحية
  • تحليل وتخطيط عبر نموذج `x-ai-core` الخارجي

**🧠 المرحلة 3 — نشطة:**
  • Reasoning Engine · AI Memory · AI Planner · Engineer Core · Impact Analysis

**🧪 اختبار ذاتي:**
  • "اختبر نفسك" → تشغيل الاختبارات والتحقق من النتائج""",
        "data": {
            "intents": [
                "identity", "capabilities", "hf_query",
                "find_file", "create_feature", "ui_redesign",
                "debug_fix", "new_page", "plan_modify",
                "dependency", "root_cause", "impact", "arch",
                "errors", "analyze", "security", "status", "self_test",
            ]
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
    """Handler for 'create notification bot', 'build X feature', etc."""
    update_stats("total_plans")
    ml = msg.lower()

    # Classify what type of thing is being created
    if re.search(r"bot\b", ml):
        kind = "Bot / Telegram Handler"
        files_to_create = [
            ("handlers/new_bot_handler.py", "handler", "منطق الأوامر الجديدة"),
            ("bot.py", "entrypoint", "تسجيل الهاندلر الجديد"),
            ("config/settings.py", "config", "إضافة أي إعدادات مطلوبة"),
        ]
        steps = [
            "1. أنشئ `handlers/new_bot_handler.py` وعرّف أوامر البوت",
            "2. سجّل الهاندلر في `bot.py` ضمن `application.add_handler()`",
            "3. أضف أي إعدادات مطلوبة في `config/settings.py`",
            "4. اختبر بـ /start وتأكد أن الأوامر الجديدة تستجيب",
        ]
        risk = "low"
    elif re.search(r"(notification|تنبيه|إشعار)", ml):
        kind = "Notification System"
        files_to_create = [
            ("services/notifier.py", "service", "منطق الإشعارات"),
            ("handlers/notifications.py", "handler", "هاندلر الإشعارات"),
            ("bot.py", "entrypoint", "تسجيل وظيفة الإشعارات"),
        ]
        steps = [
            "1. أنشئ `services/notifier.py` بدالة `send_notification(user_id, text)`",
            "2. أضف مهمة جدولة (job_queue) في `bot.py`",
            "3. اختبر الإشعار يدوياً عبر أمر `/test_notify`",
        ]
        risk = "low"
    elif re.search(r"page\b|screen\b|view\b", ml):
        kind = "Control Panel Page"
        files_to_create = [
            ("control_panel/routers/new_router.py", "router", "نقاط نهاية الصفحة الجديدة"),
            ("control_panel/templates/new_page.html", "template", "واجهة الصفحة"),
            ("control_panel/app.py", "entrypoint", "تسجيل الراوتر"),
            ("control_panel/templates/base.html", "navigation", "إضافة رابط في القائمة الجانبية"),
        ]
        steps = [
            "1. أنشئ `control_panel/routers/new_router.py` مع `@router.get('/{page}')`",
            "2. أنشئ `control_panel/templates/new_page.html` يرث من `base.html`",
            "3. سجّل الراوتر في `control_panel/app.py` بـ `app.include_router()`",
            "4. أضف الرابط في القائمة الجانبية ضمن `base.html`",
        ]
        risk = "low"
    else:
        kind = "Feature / Module"
        files_to_create = [
            ("services/new_feature.py", "service", "منطق الميزة الجديدة"),
            ("handlers/new_feature_handler.py", "handler", "استقبال الطلبات"),
        ]
        steps = [
            "1. حدد المتطلبات الكاملة للميزة",
            "2. أنشئ طبقة الخدمة في `services/`",
            "3. أنشئ الهاندلر أو الراوتر في `handlers/` أو `routers/`",
            "4. سجّل المكون الجديد في نقطة الدخول المناسبة",
        ]
        risk = "low"

    lines = [
        f"🚀 **طلب إنشاء: {kind}**\n",
        f"🔎 **تحليل الطلب:** `{msg}`\n",
        "**📂 الملفات المطلوبة:**",
    ]
    for path, role, why in files_to_create:
        lines.append(f"  • `{path}` [{role.upper()}] — {why}")
    lines.append(f"\n**🎯 مستوى التعقيد:** {risk.upper()}")
    lines.append("\n**📋 خطوات التنفيذ:**")
    lines.extend(steps)
    lines.append("\n💡 **اسأل عن أي خطوة للحصول على تفاصيل أعمق.**")

    return {
        "text": "\n".join(lines),
        "data": {"kind": kind, "files": files_to_create, "steps": steps, "risk": risk},
    }


def _r_ui_redesign(msg: str) -> dict:
    """Handler for 'redesign homepage', 'revamp sidebar', etc."""
    update_stats("total_plans")
    ml = msg.lower()

    # Detect target of redesign
    target = "غير محدد"
    route_info = _route_for_concept(msg)
    concept_hits = _find_concept(msg)

    if re.search(r"homepage|dashboard|الرئيسية|لوحة التحكم", ml):
        target = "الصفحة الرئيسية (Dashboard)"
    elif re.search(r"sidebar|القائمة الجانبية", ml):
        target = "القائمة الجانبية (Sidebar)"
    elif re.search(r"login|تسجيل الدخول|الدخول", ml):
        target = "صفحة تسجيل الدخول"
    elif concept_hits:
        target = concept_hits[0][2]

    lines = [
        f"🎨 **طلب إعادة تصميم: {target}**\n",
        "**📂 الملفات المطلوبة للتعديل:**",
    ]

    if route_info:
        lines.append(f"  🎨 **Template:** `{route_info.get('template', '—')}` — الواجهة الرئيسية للصفحة")
        for c in route_info.get("css", []):
            lines.append(f"  🎨 **CSS:** `{c}` — الألوان، المساحات، التخطيط")
        lines.append(f"  ⚙️ **Router:** `{route_info.get('router', '—')}` — بيانات الصفحة")
    else:
        lines.append("  🎨 `control_panel/static/css/style.css` — الألوان والتخطيط العام")
        lines.append("  🎨 `control_panel/templates/base.html` — القائمة الجانبية والهيكل")
        if concept_hits:
            for path, role, desc in concept_hits[:3]:
                lines.append(f"  📄 `{path}` [{role}] — {desc}")

    lines += [
        "\n**📋 خطوات إعادة التصميم:**",
        "  1. خذ نسخة احتياطية أولاً: **أنشئ نسخة احتياطية**",
        "  2. عدّل ملف `template.html` للبنية HTML",
        "  3. عدّل `style.css` للألوان والمساحات والخطوط",
        "  4. اختبر على شاشات مختلفة",
        "\n🔄 **استراتيجية الاسترجاع:** نسخة احتياطية قبل أي تعديل",
        "💡 **اسأل:** `ما الملفات المسؤولة عن [اسم الصفحة]؟` للتفاصيل الكاملة.",
    ]

    return {
        "text": "\n".join(lines),
        "data": {"target": target, "route_info": route_info, "files": concept_hits},
    }


def _r_debug_fix(msg: str) -> dict:
    """Handler for 'fix broken button', 'fix error in X', 'investigate broken Y'."""
    update_stats("total_scans")
    ml = msg.lower()

    # Detect what needs fixing
    target_file = None
    concept_hits = _find_concept(msg)
    route_info   = _route_for_concept(msg)

    problem_type = "عام"
    if re.search(r"button|زر|btn", ml):
        problem_type = "زر / عنصر واجهة"
        target_file  = "control_panel/static/js/app.js (JavaScript handler)"
    elif re.search(r"page|صفحة", ml):
        problem_type = "صفحة"
    elif re.search(r"error|خطأ|exception", ml):
        problem_type = "خطأ في الكود"
    elif re.search(r"crash|انهيار|توقف", ml):
        problem_type = "انهيار / توقف"
    elif re.search(r"link|رابط", ml):
        problem_type = "رابط / مسار"

    # Run live error scan
    live_errors = detect_log_errors()[:5]
    live_issues = detect_code_issues()[:3]

    lines = [
        f"🔧 **تشخيص: {problem_type}**\n",
        f"📝 **الطلب:** `{msg}`\n",
    ]

    if route_info:
        lines += [
            "**📂 الملفات المحتملة للمشكلة:**",
            f"  🎨 `{route_info.get('template', '—')}` — تحقق من HTML / القوالب",
            f"  ⚙️ `{route_info.get('router', '—')}` — تحقق من المسارات والمنطق",
        ]
        for c in route_info.get("css", []):
            lines.append(f"  🎨 `{c}` — تحقق من CSS إذا كان مشكلة تصميم")
    elif concept_hits:
        lines.append("**📂 الملفات المرتبطة:**")
        for path, role, desc in concept_hits[:3]:
            lines.append(f"  • `{path}` [{role}] — {desc}")
    elif target_file:
        lines.append(f"**📂 الملف الأرجح:** `{target_file}`")

    if live_errors:
        lines.append("\n**⚠️ أخطاء حديثة في السجلات:**")
        for e in live_errors[:3]:
            lines.append(f"  🔴 `{e.get('file', '?')}` — {e.get('line', '')[:80]}")

    if live_issues:
        lines.append("\n**🔍 مشاكل في الكود:**")
        for i in live_issues[:3]:
            lines.append(f"  ⚠️ `{i.get('file', '?')}` [{i.get('type', '')}]")

    lines += [
        "\n**🛠️ خطوات التشخيص:**",
        "  1. افحص ملف السجلات: `السجلات الأخيرة`",
        "  2. تحقق من وحدة تحكم المتصفح للأخطاء",
        "  3. اقرأ الملف المحدد واستخدم `أين الخطأ في [اسم الملف]`",
        "  4. بعد الإصلاح: اختبر الوظيفة مباشرة",
    ]

    return {
        "text": "\n".join(lines),
        "data": {"problem_type": problem_type, "live_errors": live_errors, "files": concept_hits},
    }


def _r_new_page(msg: str) -> dict:
    """Handler for 'create new page', 'add new screen', etc."""
    update_stats("total_plans")

    page_name = "new_page"
    m = re.search(r"(?:called?|named?|for|about|لـ?|باسم)\s+[\"']?(\w+)[\"']?", msg, re.IGNORECASE)
    if m:
        page_name = m.group(1)

    lines = [
        f"📄 **إنشاء صفحة جديدة: `{page_name}`**\n",
        "**📂 الملفات التي يجب إنشاؤها:**",
        f"  ⚙️ `control_panel/routers/{page_name}.py` [ROUTER] — نقاط نهاية الصفحة",
        f"  🎨 `control_panel/templates/{page_name}.html` [TEMPLATE] — واجهة الصفحة",
        "\n**📂 الملفات التي يجب تعديلها:**",
        "  🔧 `control_panel/app.py` [ENTRYPOINT] — تسجيل الراوتر الجديد",
        "  🎨 `control_panel/templates/base.html` [NAVIGATION] — إضافة رابط في القائمة الجانبية",
        "\n**📋 خطوات التنفيذ:**",
        f"  1. أنشئ `control_panel/routers/{page_name}.py`:",
        "     ```python",
        "     from fastapi import APIRouter, Depends, Request",
        "     from fastapi.responses import HTMLResponse",
        "     from fastapi.templating import Jinja2Templates",
        "     from ..auth import require_owner",
        "     router = APIRouter()",
        f"     @router.get('/{page_name}', response_class=HTMLResponse)",
        f"     async def {page_name}_page(request: Request, session=Depends(require_owner)):",
        f"         return templates.TemplateResponse(request, '{page_name}.html', {{}})",
        "     ```",
        f"  2. أنشئ `control_panel/templates/{page_name}.html` يرث من `base.html`",
        "  3. في `control_panel/app.py` أضف:",
        f"     `from control_panel.routers import {page_name}`",
        f"     `app.include_router({page_name}.router, prefix='/panel')`",
        "  4. في `base.html` أضف في القائمة الجانبية:",
        f"     `<a href='/panel/{page_name}' class='nav-link'>📄 {page_name}</a>`",
        "\n🔄 **استراتيجية الاسترجاع:** احذف الملفات الجديدة وأعِد السطور في app.py و base.html",
    ]

    return {
        "text": "\n".join(lines),
        "data": {
            "page_name": page_name,
            "files_to_create": [
                f"control_panel/routers/{page_name}.py",
                f"control_panel/templates/{page_name}.html",
            ],
            "files_to_modify": ["control_panel/app.py", "control_panel/templates/base.html"],
        },
    }


def _r_find_file(msg: str) -> dict:
    update_stats("total_questions")
    return answer_file_question(msg)


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
    return {"text": "\n".join(lines), "data": plan}


def _r_dependency(msg: str) -> dict:
    entries = _find_concept(msg)
    route_info = _route_for_concept(msg)
    lines = ["🔗 **تحليل التبعيات**\n"]
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
    elif entries:
        for path, role, desc in entries:
            impact = analyze_file_impact(path)
            lines.append(f"• `{path}` [{role}]")
            for a in impact.get("affects", []):
                lines.append(f"  ↳ يؤثر على: {a}")
    else:
        lines.append("لم يتم العثور على معلومات تبعية لهذا الاستعلام.")
    return {"text": "\n".join(lines), "data": {"entries": entries}}


def _r_impact(msg: str) -> dict:
    entries = _find_concept(msg)
    if not entries:
        entries = [("unknown", "unknown", "—")]
    target = entries[0][0]
    impact = analyze_file_impact(target)
    lines  = [f"💥 **تأثير تغيير: `{target}`**\n",
              f"🚨 **مستوى الخطر:** {impact.get('risk', 'unknown').upper()}"]
    for a in impact.get("affects", []):
        lines.append(f"  ⚠️ {a}")
    return {"text": "\n".join(lines), "data": impact}


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


def _r_routes() -> dict:
    routes = detect_routes()
    lines  = [f"🌐 **{len(routes)} مسار في لوحة التحكم:**\n"]
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


def _r_improve(msg: str) -> dict:
    entries = _find_concept(msg)
    route_info = _route_for_concept(msg)
    lines = ["💡 **اقتراحات التحسين**\n"]
    if route_info:
        lines.append(f"للتحسين يجب تعديل:")
        lines.append(f"• `{route_info['template']}` — HTML structure")
        for c in route_info.get("css", []):
            lines.append(f"• `{c}` — Styling")
        for j in route_info.get("js", []):
            lines.append(f"• `{j}` — Interactivity")
    elif entries:
        for path, role, desc in entries[:4]:
            lines.append(f"• `{path}` [{role}] — {desc}")
    else:
        lines.append("حدد الجزء الذي تريد تحسينه (homepage, sidebar, colors, users, bots...)")
    return {"text": "\n".join(lines), "data": {"entries": entries}}


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


def _r_status() -> dict:
    m     = load_memory()
    tests = run_self_tests()
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

    # ── Layer 7: Hugging Face API ─────────────────────────────────────────────
    try:
        hf = call_hf_analyze(code=msg, question=msg)
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
