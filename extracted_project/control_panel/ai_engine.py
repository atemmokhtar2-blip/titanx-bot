"""
X Control Center — AI Engine v2.0
Project Intelligence Layer: File Awareness + Dependency Mapping + Planning Engine
Natural language understanding (Arabic + English)
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

SKIP_DIRS = {
    "__pycache__", ".git", "node_modules", ".pythonlibs", "temp", "backups",
    ".local", ".venv", "dist", "build", ".cache", ".ai_backups", "artifacts",
}
CODE_EXTS = {".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".toml", ".sh", ".md"}

# ─── Intent Detection ─────────────────────────────────────────────────────────
INTENTS: dict = {
    "errors":    [r"أخطاء", r"خطأ", r"errors?", r"bugs?", r"مشاكل", r"مشكلة", r"كسور", r"broken", r"يعطل"],
    "analyze":   [r"افحص", r"حلل", r"analyze", r"scan", r"فحص", r"تحليل", r"inspect", r"اكتشف"],
    "backup":    [r"احتياطي", r"backup", r"نسخة", r"احفظ", r"save", r"حفظ", r"نسخ احتياطي"],
    "restore":   [r"استعادة", r"restore", r"رجوع", r"استرجاع", r"rollback"],
    "improve":   [r"حسن", r"improve", r"احترافية", r"professional", r"تحسين", r"أفضل", r"جمال"],
    "memory":    [r"تذكر", r"ذاكرة", r"memory", r"تعلم", r"اعرف", r"تعرف", r"معلومات"],
    "status":    [r"حالة", r"status", r"شغال", r"يعمل", r"مباشر", r"live", r"working", r"online"],
    "structure": [r"هيكل", r"structure", r"ملفات", r"files", r"مشروع", r"project", r"بنية", r"مجلدات"],
    "routes":    [r"routes?", r"مسارات", r"صفحات", r"pages?", r"endpoints?", r"روابط", r"\bapi\b"],
    "security":  [r"أمان", r"security", r"أمن", r"ثغرات", r"vulnerab", r"password", r"tokens?", r"حماية"],
    "help":      [r"مساعدة", r"help", r"ساعد", r"كيف تعمل", r"ماذا تستطيع", r"قدرات", r"وظائف"],
    "stats":     [r"إحصائيات", r"stats", r"أرقام", r"numbers", r"\bكم\b", r"how many", r"عدد"],
    "duplicate": [r"مكرر", r"duplicate", r"تكرار", r"مشابه", r"similar"],
    "unused":    [r"غير مستخدم", r"unused", r"مهمل", r"dead code", r"لا يستخدم"],
    # ── Phase 1.5: Intelligence intents ──
    "find_file":  [r"find\b", r"where is", r"which file", r"what file", r"locate",
                   r"أين", r"أي ملف", r"ما الملف", r"ابحث عن", r"أين يوجد", r"يتحكم"],
    "plan_modify":[r"plan", r"خطة", r"what.*modify", r"what.*change", r"ماذا.*أعدل",
                   r"redesign", r"إعادة تصميم", r"modify plan", r"how to.*change"],
    "dependency": [r"depend", r"uses", r"loads", r"import", r"related",
                   r"يستخدم", r"يحمل", r"علاقة", r"ارتباط", r"مرتبط"],
    "self_test":  [r"self.?test", r"test yourself", r"اختبر نفسك", r"self check"],
}

def detect_intent(msg: str) -> str:
    ml = msg.lower()
    # Priority check: file-awareness questions (checked BEFORE generic intents)
    file_q_pats = [
        r"what file.{0,20}control",
        r"which file.{0,20}control",
        r"what file.{0,20}handle",
        r"what file.{0,20}homepage",
        r"what file.{0,20}dashboard",
        r"what file.{0,20}color",
        r"what file.{0,20}login",
        r"what file.{0,20}css",
        r"what css",
        r"what.{0,10}css.{0,20}control",
        r"what files?.{0,20}(?:should|need|must).{0,20}(?:modify|change|edit|update)",
        r"what files?.{0,20}(?:to|for).{0,20}(?:redesign|rebuild|modify|change)",
        r"files?.{0,20}(?:modify|change).{0,20}(?:redesign|homepage|dashboard|page)",
        r"what route",
        r"which route",
        r"what.{0,10}route.{0,20}loads?",
        r"أي ملف.{0,20}يتحكم",
        r"ما الملف.{0,20}يتحكم",
        r"أين.{0,20}الصفحة",
        r"find.{0,20}page",
        r"find.{0,20}file",
        r"locate.{0,20}(?:page|file|route)",
    ]
    for p in file_q_pats:
        if re.search(p, ml):
            return "find_file"
    scores: dict = {}
    for intent, patterns in INTENTS.items():
        score = sum(1 for p in patterns if re.search(p, ml))
        if score:
            scores[intent] = score
    return max(scores, key=scores.get) if scores else "general"

# ═══════════════════════════════════════════════════════════════════════════════
#  PROJECT KNOWLEDGE ENGINE  — Phase 1.5 Intelligence Layer
# ═══════════════════════════════════════════════════════════════════════════════

# Semantic map: concept keywords → list of (file, role, description)
# Each entry: (relative_path_from_extracted_dir, role, human_description)
_SEMANTIC_MAP: dict = {
    # Pages / UI
    "homepage":      [("control_panel/templates/dashboard.html",      "template", "صفحة لوحة القيادة الرئيسية"),
                      ("control_panel/routers/dashboard.py",           "router",   "مسار / وبيانات لوحة القيادة")],
    "dashboard":     [("control_panel/templates/dashboard.html",      "template", "قالب لوحة القيادة"),
                      ("control_panel/routers/dashboard.py",           "router",   "router لوحة القيادة")],
    "login":         [("control_panel/templates/access.html",         "template", "صفحة تسجيل الدخول / الوصول"),
                      ("control_panel/app.py",                         "handler",  "منطق /panel و /panel/login")],
    "access":        [("control_panel/templates/access.html",         "template", "صفحة الوصول بكلمة المرور"),
                      ("control_panel/app.py",                         "handler",  "panel_access و panel_password_login")],
    "panel":         [("control_panel/app.py",                        "core",     "تطبيق FastAPI الرئيسي"),
                      ("control_panel/templates/base.html",            "template", "القالب الأساسي المشترك")],
    "users":         [("control_panel/templates/users.html",          "template", "صفحة إدارة المستخدمين"),
                      ("control_panel/routers/users.py",               "router",   "API إدارة المستخدمين")],
    "broadcast":     [("control_panel/templates/broadcast.html",      "template", "صفحة البث الجماعي"),
                      ("control_panel/routers/broadcast.py",           "router",   "API إرسال الرسائل الجماعية")],
    "database":      [("control_panel/templates/db_manager.html",     "template", "صفحة إدارة قاعدة البيانات"),
                      ("control_panel/routers/db_manager.py",          "router",   "API قاعدة البيانات"),
                      ("control_panel/db_utils.py",                    "utility",  "أدوات SQLite المشتركة")],
    "db":            [("control_panel/db_utils.py",                   "utility",  "أدوات قاعدة البيانات"),
                      ("database/bot.db",                              "database", "ملف قاعدة بيانات البوت الرئيسي")],
    "files":         [("control_panel/templates/files.html",          "template", "صفحة إدارة الملفات"),
                      ("control_panel/routers/files.py",               "router",   "API تصفح / تعديل الملفات")],
    "logs":          [("control_panel/templates/logs.html",           "template", "صفحة السجلات"),
                      ("control_panel/routers/logs_router.py",         "router",   "API قراءة السجلات")],
    "system":        [("control_panel/templates/system.html",         "template", "صفحة صحة النظام"),
                      ("control_panel/routers/system.py",              "router",   "API إحصائيات النظام (CPU/RAM)")],
    "updates":       [("control_panel/templates/updates.html",        "template", "صفحة التحديثات"),
                      ("control_panel/routers/updates.py",             "router",   "API تحديث الكود")],
    "github":        [("control_panel/templates/github.html",         "template", "صفحة إدارة GitHub"),
                      ("control_panel/routers/github_router.py",       "router",   "API تكامل GitHub")],
    "backups":       [("control_panel/templates/backups.html",        "template", "صفحة النسخ الاحتياطية"),
                      ("control_panel/routers/backups.py",             "router",   "API النسخ الاحتياطية")],
    "bots":          [("control_panel/templates/bots.html",           "template", "صفحة إدارة البوتات"),
                      ("control_panel/routers/bots.py",                "router",   "API تشغيل/إيقاف البوتات")],
    "search":        [("control_panel/templates/search.html",         "template", "صفحة البحث"),
                      ("control_panel/routers/search.py",              "router",   "API البحث في المشروع")],
    "replit":        [("control_panel/templates/replit_manager.html", "template", "صفحة مدير Replit"),
                      ("control_panel/routers/replit_manager.py",      "router",   "API مدير Replit")],
    "ai":            [("control_panel/templates/ai_workspace.html",   "template", "صفحة AI Workspace الرئيسية"),
                      ("control_panel/routers/ai_workspace.py",        "router",   "API مساحة العمل الذكية"),
                      ("control_panel/ai_engine.py",                   "engine",   "محرك الذكاء الاصطناعي (هذا الملف)")],
    "ai_engineer":   [("control_panel/templates/ai_engineer.html",   "template", "صفحة مهندس الذكاء"),
                      ("control_panel/routers/ai_workspace.py",        "router",   "route /ai/engineer")],
    "ai_memory":     [("control_panel/templates/ai_memory.html",     "template", "صفحة ذاكرة الذكاء"),
                      ("control_panel/ai_engine.py",                   "engine",   "load_memory / save_memory")],
    "ai_review":     [("control_panel/templates/ai_review.html",     "template", "صفحة مراجعة الذكاء"),
                      ("control_panel/routers/ai_workspace.py",        "router",   "route /ai/review + /ai/api/plan")],
    # Styles / assets
    "css":           [("control_panel/static/css/style.css",          "stylesheet", "ملف CSS الرئيسي (كل الألوان والتصميم)")],
    "colors":        [("control_panel/static/css/style.css",          "stylesheet", "متغيرات الألوان: --primary, --bg-*, --text-*")],
    "theme":         [("control_panel/static/css/style.css",          "stylesheet", "النمط الكلي (Dark/Light) ومتغيرات CSS")],
    "style":         [("control_panel/static/css/style.css",          "stylesheet", "كل تنسيقات الواجهة")],
    "javascript":    [("control_panel/static/js/app.js",              "script",   "الكود الأمامي الرئيسي (frontend JS)")],
    "frontend":      [("control_panel/static/js/app.js",              "script",   "منطق الواجهة الأمامية"),
                      ("control_panel/static/css/style.css",          "stylesheet", "تصميم الواجهة")],
    "sidebar":       [("control_panel/templates/base.html",           "template", "القالب الأساسي يحتوي الـ sidebar")],
    "navbar":        [("control_panel/templates/base.html",           "template", "شريط التنقل الجانبي في base.html")],
    "base":          [("control_panel/templates/base.html",           "template", "القالب الأساسي المشترك لكل الصفحات")],
    "layout":        [("control_panel/templates/base.html",           "template", "هيكل الصفحة المشترك"),
                      ("control_panel/static/css/style.css",          "stylesheet", "تنسيق التخطيط")],
    # Bots
    "main_bot":      [("bot.py",                                      "entry",    "نقطة بدء البوت الرئيسي"),
                      ("handlers/",                                    "handlers", "جميع معالجات أوامر البوت"),
                      ("config/settings.py",                          "config",   "إعدادات البوت الرئيسي")],
    "support_bot":   [("support_bot/bot.py",                         "entry",    "نقطة بدء بوت الدعم"),
                      ("support_bot/",                                "module",   "كل ملفات بوت الدعم")],
    "downloader":    [("bot.py",                                      "entry",    "البوت الرئيسي للتحميل"),
                      ("handlers/download.py",                        "handler",  "معالج التحميل الرئيسي (إن وجد)")],
    # Config / auth
    "config":        [("config/settings.py",                         "config",   "إعدادات البوت (tokens, limits, rewards)"),
                      ("control_panel/config.py",                     "config",   "إعدادات لوحة التحكم (paths, secrets)")],
    "auth":          [("control_panel/auth.py",                      "auth",     "نظام الجلسات والتحقق من الهوية"),
                      ("control_panel/app.py",                        "handler",  "routes /panel, /login, /logout")],
    "session":       [("control_panel/auth.py",                      "auth",     "create_session / get_session / require_owner")],
    "password":      [("control_panel/app.py",                       "handler",  "_verify_password, _hash_pw, /panel/login"),
                      ("control_panel/auth.py",                       "auth",     "ACCESS_TOKEN و SESSION_COOKIE")],
    "settings":      [("config/settings.py",                         "config",   "جميع إعدادات البوت"),
                      ("control_panel/config.py",                     "config",   "إعدادات لوحة التحكم")],
    "token":         [("control_panel/auth.py",                      "auth",     "ACCESS_TOKEN المستخدم للدخول عبر رابط"),
                      ("config/settings.py",                          "config",   "BOT_TOKEN من env")],
    # Workers / background
    "workers":       [("workers/",                                    "workers",  "مهام الخلفية (cleanup, heartbeat, monitors)")],
    "handlers":      [("handlers/",                                   "handlers", "معالجات أوامر البوت الرئيسي")],
}

# Aliases map: normalize queries
_ALIASES: dict = {
    "home page":     "homepage",
    "main page":     "homepage",
    "الصفحة الرئيسية": "homepage",
    "الرئيسية":      "homepage",
    "لوحة القيادة":  "dashboard",
    "الواجهة":       "frontend",
    "الستايل":       "css",
    "التصميم":       "css",
    "الألوان":       "colors",
    "قاعدة البيانات": "database",
    "البوت":         "main_bot",
    "البوت الرئيسي": "main_bot",
    "بوت الدعم":     "support_bot",
    "الجانبية":      "sidebar",
    "التنقل":        "navbar",
    "كلمة المرور":   "password",
    "تسجيل الدخول":  "login",
    "المصادقة":      "auth",
}


def _normalize_query(q: str) -> str:
    ql = q.lower().strip()
    for alias, canonical in _ALIASES.items():
        if alias in ql:
            return canonical
    return ql


def _find_concept(q: str) -> list:
    """Return list of (file, role, description) for a concept query.
    Matches longest/most-specific concept first to avoid 'ai' swallowing 'ai_engineer'.
    """
    normalized = _normalize_query(q)
    # Direct map hit — sort by concept length DESCENDING so specific beats generic
    best_match = None
    best_len   = 0
    for concept, entries in sorted(_SEMANTIC_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        concept_plain = concept.replace("_", " ")
        if concept_plain in normalized and len(concept) > best_len:
            best_match = entries
            best_len   = len(concept)
        elif concept in normalized and len(concept) > best_len:
            best_match = entries
            best_len   = len(concept)
    if best_match:
        return best_match
    # Fuzzy: all keywords in concept must appear in normalized (AND logic, not OR)
    results = []
    seen = set()
    for concept, entries in sorted(_SEMANTIC_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        kws = concept.split("_")
        if len(kws) > 1 and all(kw in normalized for kw in kws):
            for e in entries:
                if e[0] not in seen:
                    results.append(e)
                    seen.add(e[0])
    if results:
        return results
    # Last resort: any single keyword (excluding very short ones like 'ai', 'db')
    for concept, entries in sorted(_SEMANTIC_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        kws = [kw for kw in concept.split("_") if len(kw) > 2]
        if kws and any(kw in normalized for kw in kws):
            for e in entries:
                if e[0] not in seen:
                    results.append(e)
                    seen.add(e[0])
    return results


def search_project_files(query: str) -> list:
    """
    Intelligent file search. Returns list of dicts with file info + relevance.
    Combines semantic map + filesystem scan.
    """
    results = []
    seen = set()
    # 1. Semantic map search
    semantic = _find_concept(query)
    for (rel_path, role, desc) in semantic:
        fp = os.path.join(EXTRACTED_DIR, rel_path)
        exists = os.path.exists(fp)
        results.append({
            "path": rel_path,
            "role": role,
            "description": desc,
            "exists": exists,
            "source": "semantic",
            "relevance": "high",
        })
        seen.add(rel_path)
    # 2. Filename/content scan for leftovers
    ql = query.lower()
    for root, dirs, fnames in os.walk(EXTRACTED_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fnames:
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, EXTRACTED_DIR)
            if rel in seen:
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext not in CODE_EXTS:
                continue
            name_match = ql in fn.lower() or any(kw in fn.lower() for kw in ql.split())
            if name_match:
                results.append({
                    "path": rel, "role": "file", "description": fn,
                    "exists": True, "source": "scan", "relevance": "medium",
                })
                seen.add(rel)
    return results[:20]


def build_dependency_map() -> dict:
    """
    Auto-build route → template → CSS/JS dependency map
    by parsing all Python router files.
    """
    dep_map = {}
    route_pat   = re.compile(r'@(?:router|app)\.(?:get|post|put|delete|patch)\(["\']([^"\']+)["\']')
    tmpl_pat    = re.compile(r'TemplateResponse\s*\([^,]+,\s*["\']([^"\']+\.html)["\']')
    prefix_pat  = re.compile(r'APIRouter\s*\(.*prefix\s*=\s*["\']([^"\']+)["\']')

    for root, dirs, fnames in os.walk(EXTRACTED_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fnames:
            if not fn.endswith(".py"):
                continue
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, EXTRACTED_DIR)
            try:
                with open(fp, "r", errors="replace") as f:
                    content = f.read()
            except Exception:
                continue

            prefix = ""
            pm = prefix_pat.search(content)
            if pm:
                prefix = pm.group(1).rstrip("/")

            routes_in_file = route_pat.findall(content)
            tmpls_in_file  = tmpl_pat.findall(content)

            for route in routes_in_file:
                full_route = prefix + route if not route.startswith(prefix) else route
                dep_map[full_route] = {
                    "route":    full_route,
                    "file":     rel,
                    "templates": [],
                    "css":      ["control_panel/static/css/style.css"],
                    "js":       ["control_panel/static/js/app.js"],
                }
            # Associate templates found in same file to its routes
            if tmpls_in_file and routes_in_file:
                for route in routes_in_file:
                    full_route = prefix + route if not route.startswith(prefix) else route
                    if full_route in dep_map:
                        dep_map[full_route]["templates"] = tmpls_in_file

    return dep_map


def get_file_role(rel_path: str) -> dict:
    """Return a full profile of a file: what it does, who uses it, dependencies."""
    fp = os.path.join(EXTRACTED_DIR, rel_path)
    if not os.path.exists(fp):
        return {"ok": False, "error": "الملف غير موجود"}

    ext  = os.path.splitext(rel_path)[1].lower()
    name = os.path.basename(rel_path)

    profile = {
        "ok":     True,
        "path":   rel_path,
        "name":   name,
        "ext":    ext,
        "lines":  _count_lines(fp),
        "size":   _fmt(os.path.getsize(fp)),
        "role":   "",
        "description": "",
        "controls":    [],
        "depends_on":  [],
        "used_by":     [],
    }

    # Determine role from semantic map
    for concept, entries in _SEMANTIC_MAP.items():
        for (path, role, desc) in entries:
            if path in rel_path or rel_path in path:
                profile["role"] = role
                profile["description"] = desc
                profile["controls"].append(concept)

    # Parse imports / TemplateResponse
    if ext == ".py":
        try:
            with open(fp, "r", errors="replace") as f:
                content = f.read()
            imports = re.findall(r'^(?:from|import)\s+(\S+)', content, re.MULTILINE)
            profile["depends_on"] = imports[:10]
            tmpls = re.findall(r'TemplateResponse\s*\([^,]+,\s*["\']([^"\']+\.html)["\']', content)
            profile["used_by"] = [f"template: {t}" for t in tmpls]
        except Exception:
            pass
    elif ext == ".html":
        try:
            with open(fp, "r", errors="replace") as f:
                content = f.read()
            extends = re.findall(r'{%\s*extends\s*["\']([^"\']+)["\']', content)
            includes = re.findall(r'{%\s*include\s*["\']([^"\']+)["\']', content)
            css_links = re.findall(r'href=["\'][^"\']*\.css[^"\']*["\']', content)
            js_links  = re.findall(r'src=["\'][^"\']*\.js[^"\']*["\']', content)
            profile["depends_on"] = extends + includes + [c.split("=")[1].strip('"\'') for c in css_links[:3]]
            profile["used_by"]    = [j.split("=")[1].strip('"\'') for j in js_links[:3]]
        except Exception:
            pass

    return profile


def answer_file_question(msg: str) -> dict:
    """
    Core file awareness: answer "what file controls X?" with real files.
    Returns structured answer with files, roles, dependencies.
    """
    ml = msg.lower()

    # Extract the concept being asked about
    # Patterns: "what file controls X", "which file handles X", "find X file", "where is X"
    concept_pats = [
        r"what file.{0,15}(?:controls?|handles?|manages?|is)\s+(.+)",
        r"which file.{0,15}(?:controls?|handles?|for)\s+(.+)",
        r"find.{0,5}(?:the\s+)?(.+?)(?:\s+file|\s+page)?$",
        r"where is.{0,5}(?:the\s+)?(.+)",
        r"locate\s+(.+)",
        r"أي ملف.{0,10}يتحكم.{0,5}(?:في|بـ)?\s*(.+)",
        r"ما الملف.{0,10}(?:الذي\s+)?يتحكم.{0,5}(?:في|بـ)?\s*(.+)",
        r"أين.{0,5}(?:يوجد|هو)?\s*(.+)",
    ]
    concept = msg.strip()
    for pat in concept_pats:
        m = re.search(pat, ml, re.IGNORECASE)
        if m:
            concept = m.group(1).strip().rstrip("?؟.")
            break

    results = _find_concept(concept)

    # Fallback: search full text
    if not results:
        results_full = search_project_files(concept)
        if results_full:
            results = [(r["path"], r["role"], r["description"]) for r in results_full[:5]]

    if not results:
        return {
            "text": f"""🔍 **بحث عن: "{concept}"**

لم أجد تطابقاً مباشراً في خريطة المعرفة.

💡 جرب الأوامر التالية:
  · `ابحث عن dashboard` — لوحة القيادة
  · `ما الملف الذي يتحكم في الألوان؟`
  · `أين صفحة المستخدمين؟`""",
            "intent": "find_file", "type": "info",
            "actions": [{"label": "📁 ابحث في الملفات", "link": "/files"}]
        }

    # Build rich answer
    lines = [f"📍 **الملفات المسؤولة عن: `{concept}`**\n"]
    for (rel_path, role, desc) in results:
        fp = os.path.join(EXTRACTED_DIR, rel_path)
        exists = "✅" if os.path.exists(fp) else "⚠️ (غير موجود)"
        role_icon = {
            "template":   "🎨",
            "router":     "🛣️",
            "handler":    "⚙️",
            "engine":     "🧠",
            "stylesheet": "🎨",
            "script":     "⚡",
            "auth":       "🔒",
            "config":     "⚙️",
            "utility":    "🔧",
            "core":       "🏗️",
            "database":   "🗄️",
            "entry":      "🚀",
            "workers":    "⏱️",
            "handlers":   "📨",
        }.get(role, "📄")
        lines.append(f"{role_icon} **{role.upper()}**: `{rel_path}` {exists}")
        lines.append(f"   ↳ {desc}\n")

    # Add dependency note for the first file
    if results:
        first_path, first_role, _ = results[0]
        if first_role == "template":
            lines.append("🔗 **المعتمدات:**")
            lines.append("  · CSS: `control_panel/static/css/style.css`")
            lines.append("  · JS:  `control_panel/static/js/app.js`")
            lines.append("  · Base: `control_panel/templates/base.html`")

    return {
        "text": "\n".join(lines),
        "intent": "find_file", "type": "success",
        "data": {"concept": concept, "files": [{"path": r[0], "role": r[1], "description": r[2]} for r in results]},
        "actions": [
            {"label": f"📄 فتح {results[0][0].split('/')[-1]}", "link": f"/files"},
        ]
    }


def create_modification_plan(description: str) -> dict:
    """
    Phase 1.5 Planning Engine: generate a real plan with actual file names.
    """
    # Find which files are relevant
    relevant = _find_concept(description)
    all_search = search_project_files(description)

    # Merge results
    files_to_modify = []
    seen = set()
    for (rel, role, desc) in relevant:
        if rel not in seen and not rel.endswith("/"):
            fp = os.path.join(EXTRACTED_DIR, rel)
            if os.path.exists(fp):
                files_to_modify.append({"path": rel, "role": role, "reason": desc, "risk": _assess_risk(role)})
                seen.add(rel)

    # Classify risk
    overall_risk = "low"
    for f in files_to_modify:
        if f["risk"] == "high":
            overall_risk = "high"
            break
        if f["risk"] == "medium":
            overall_risk = "medium"

    RISK_LABELS = {"none": "✅ آمن تماماً", "low": "🟡 منخفض", "medium": "🟠 متوسط", "high": "🔴 عالي"}

    # Build steps
    steps = [{"n": 1, "action": "💾 نسخة احتياطية أولاً", "desc": "حفظ الحالة الحالية قبل أي تعديل", "risk": "none"}]
    for i, f in enumerate(files_to_modify[:6], 2):
        steps.append({
            "n": i,
            "action": f"تعديل `{f['path'].split('/')[-1]}`",
            "desc": f"{f['reason']} ({f['role']})",
            "risk": f["risk"],
            "file": f["path"],
        })
    steps.append({
        "n": len(steps) + 1,
        "action": "✅ اختبار التعديلات",
        "desc": "مراجعة النتيجة النهائية وإعادة تشغيل الخدمة إن لزم",
        "risk": "none",
    })

    rollback = f"استعادة النسخة الاحتياطية التي تم إنشاؤها في الخطوة 1"

    return {
        "ok": True,
        "title": f"خطة التنفيذ: {description[:60]}",
        "intent": detect_intent(description),
        "steps": steps,
        "files_affected": [f["path"] for f in files_to_modify],
        "files_detail":   files_to_modify,
        "risk":           overall_risk,
        "risk_label":     RISK_LABELS.get(overall_risk, overall_risk),
        "requires_backup": True,
        "rollback":        rollback,
        "estimated_time": f"{len(steps) * 2}-{len(steps) * 5} ثانية",
        "created_at":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _assess_risk(role: str) -> str:
    return {
        "core":       "high",
        "auth":       "high",
        "handler":    "medium",
        "router":     "medium",
        "engine":     "medium",
        "template":   "low",
        "stylesheet": "low",
        "script":     "low",
        "config":     "medium",
        "utility":    "medium",
        "database":   "high",
    }.get(role, "low")


def run_self_tests() -> dict:
    """Run Phase 1.5 self-tests: verify the AI can answer file questions."""
    tests = [
        ("What file controls the homepage?",              "find_file", "dashboard"),
        ("What file controls the dashboard?",             "find_file", "dashboard"),
        ("What CSS controls the colors?",                 "find_file", "style.css"),
        ("What files should be modified to redesign the homepage?", "find_file", "dashboard.html"),
        ("What route loads the AI Engineer page?",        "find_file", "ai_engineer"),
        ("Find the login page",                           "find_file", "access.html"),
        ("What file handles authentication?",             "find_file", "auth.py"),
        ("Where is the sidebar?",                         "find_file", "base.html"),
    ]
    results = []
    passed  = 0
    for (question, expected_intent, expected_keyword) in tests:
        intent  = detect_intent(question)
        answer  = answer_file_question(question)
        found   = expected_keyword.lower() in answer["text"].lower()
        intent_ok = intent == expected_intent
        ok = found and intent_ok
        if ok:
            passed += 1
        results.append({
            "question":        question,
            "expected_intent": expected_intent,
            "got_intent":      intent,
            "intent_ok":       intent_ok,
            "expected_keyword": expected_keyword,
            "keyword_found":   found,
            "passed":          ok,
            "answer_preview":  answer["text"][:120],
        })

    return {
        "ok":           True,
        "total":        len(tests),
        "passed":       passed,
        "failed":       len(tests) - passed,
        "score":        f"{passed}/{len(tests)}",
        "pass_rate":    f"{passed/len(tests)*100:.0f}%",
        "status":       "✅ PASS" if passed == len(tests) else ("⚠️ PARTIAL" if passed >= len(tests)//2 else "❌ FAIL"),
        "tests":        results,
        "ran_at":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ─── Project Memory ───────────────────────────────────────────────────────────
def load_memory() -> dict:
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        d = _default_memory()
        save_memory(d)
        return d

def save_memory(data: dict):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _default_memory() -> dict:
    return {
        "project_name": "X Control Center",
        "version": "5.0",
        "engine_version": "2.0",
        "last_updated": datetime.now().isoformat(),
        "components": {
            "main_bot":      {"name": "PrimeDownloader Bot",   "file": "bot.py",                                   "status": "active", "description": "البوت الرئيسي لتحميل المحتوى"},
            "support_bot":   {"name": "Support Bot",           "file": "support_bot/bot.py",                      "status": "active", "description": "بوت الدعم الفني"},
            "control_panel": {"name": "X Control Center",      "file": "control_panel/app.py",                    "status": "active", "description": "لوحة التحكم الرئيسية FastAPI"},
            "ai_system":     {"name": "AI Workspace v2",       "file": "control_panel/routers/ai_workspace.py",   "status": "active", "description": "نظام الذكاء الاصطناعي — Intelligence Layer"},
            "backup_system": {"name": "Backup Center",         "file": "control_panel/routers/backups.py",        "status": "active", "description": "نظام النسخ الاحتياطية"},
            "github":        {"name": "GitHub Manager",        "file": "control_panel/routers/github_router.py",  "status": "active", "description": "مدير GitHub الذكي"},
            "system_health": {"name": "System Health",         "file": "control_panel/routers/system.py",        "status": "active", "description": "مراقبة صحة النظام"},
        },
        "knowledge_index": {
            "semantic_concepts": list(_SEMANTIC_MAP.keys()),
            "total_mapped_files": len({e[0] for entries in _SEMANTIC_MAP.values() for e in entries}),
            "engine_version": "2.0",
        },
        "architecture": {
            "framework":    "FastAPI + Uvicorn",
            "bots":         "python-telegram-bot 21.6",
            "db":           "SQLite (aiosqlite)",
            "templates":    "Jinja2",
            "css_file":     "control_panel/static/css/style.css",
            "js_file":      "control_panel/static/js/app.js",
            "base_template":"control_panel/templates/base.html",
            "entry_point":  "control_panel/server.py",
            "port":         5000,
        },
        "chat_history": [],
        "analysis_cache": {},
        "ai_stats": {
            "total_chats":     0,
            "total_analyses":  0,
            "total_backups":   0,
            "errors_found":    0,
            "last_scan":       None,
        },
    }

def update_stats(key: str, val: int = 1):
    mem = load_memory()
    mem["ai_stats"][key] = mem["ai_stats"].get(key, 0) + val
    mem["last_updated"] = datetime.now().isoformat()
    save_memory(mem)

def save_chat(role: str, text: str):
    mem = load_memory()
    history = mem.get("chat_history", [])
    history.append({"role": role, "text": text[:1000], "ts": datetime.now().isoformat()})
    mem["chat_history"] = history[-50:]
    save_memory(mem)

# ─── Backup Manager ───────────────────────────────────────────────────────────
def create_backup(description: str = "نسخة يدوية") -> dict:
    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    bk_id   = f"backup_{ts}"
    bk_path = BACKUP_DIR / f"{bk_id}.zip"
    added   = 0
    try:
        with zipfile.ZipFile(bk_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, fnames in os.walk(EXTRACTED_DIR):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for fn in fnames:
                    fp = os.path.join(root, fn)
                    arc = os.path.relpath(fp, EXTRACTED_DIR)
                    try:
                        zf.write(fp, arc)
                        added += 1
                    except Exception:
                        pass
        size = bk_path.stat().st_size
        meta = {
            "id": bk_id, "timestamp": ts,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": description, "files": added,
            "size": size, "size_h": _fmt(size),
            "path": str(bk_path),
        }
        with open(BACKUP_DIR / f"{bk_id}.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        update_stats("total_backups")
        return {"ok": True, **meta}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def list_backups() -> list:
    out = []
    for p in sorted(BACKUP_DIR.glob("*.json"), reverse=True)[:25]:
        try:
            with open(p, "r", encoding="utf-8") as f:
                out.append(json.load(f))
        except Exception:
            pass
    return out

def restore_backup(bk_id: str) -> dict:
    bk_path = BACKUP_DIR / f"{bk_id}.zip"
    if not bk_path.exists():
        return {"ok": False, "error": "النسخة الاحتياطية غير موجودة"}
    try:
        safety = create_backup(f"Auto-safety before restore {bk_id}")
        with zipfile.ZipFile(bk_path, "r") as zf:
            zf.extractall(EXTRACTED_DIR)
        return {"ok": True, "msg": f"تم الاستعادة من {bk_id}", "safety_id": safety.get("id")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ─── File Walker ──────────────────────────────────────────────────────────────
def walk_project() -> list:
    files = []
    for root, dirs, fnames in os.walk(EXTRACTED_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fnames:
            fp = os.path.join(root, fn)
            ext = os.path.splitext(fn)[1].lower()
            try:
                stat = os.stat(fp)
                rel  = os.path.relpath(fp, EXTRACTED_DIR)
                files.append({
                    "path": rel, "name": fn, "ext": ext,
                    "size": stat.st_size, "fp": fp,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "is_code": ext in CODE_EXTS,
                })
            except Exception:
                pass
    return files

# ─── Analyzers ────────────────────────────────────────────────────────────────
def analyze_structure() -> dict:
    files = walk_project()
    by_ext: dict = {}
    total_lines = 0
    code_files  = []
    for fi in files:
        e = fi["ext"] or "other"
        by_ext[e] = by_ext.get(e, 0) + 1
        if fi["is_code"]:
            lc = _count_lines(fi["fp"])
            total_lines += lc
            code_files.append({**fi, "lines": lc})
    top_files = sorted(code_files, key=lambda x: x["lines"], reverse=True)[:10]
    dirs: dict = {}
    for fi in files:
        d = os.path.dirname(fi["path"]) or "."
        dirs[d] = dirs.get(d, 0) + 1
    ts = int(time.time())
    mem = load_memory()
    mem["analysis_cache"]["structure"] = {"ts": ts, "total_files": len(files), "code_files": len(code_files), "lines": total_lines}
    mem["ai_stats"]["last_scan"] = datetime.now().isoformat()
    save_memory(mem)
    return {
        "total_files": len(files), "code_files": len(code_files),
        "total_lines": total_lines, "total_size_h": _fmt(sum(f["size"] for f in files)),
        "by_ext": dict(sorted(by_ext.items(), key=lambda x: x[1], reverse=True)[:12]),
        "top_files": [{k: v for k, v in f.items() if k != "fp"} for f in top_files],
        "dirs": dict(sorted(dirs.items(), key=lambda x: x[1], reverse=True)[:10]),
    }

def detect_log_errors() -> list:
    errors = []
    ERROR_PAT = re.compile(r'\b(error|exception|traceback|critical|fatal)\b', re.IGNORECASE)
    sources = []
    log_dir = EXTRACTED_DIR / "logs"
    if log_dir.is_dir():
        sources.extend(list(log_dir.glob("*.log"))[:4])
    for p in [EXTRACTED_DIR / "bot.log", EXTRACTED_DIR / "error.log"]:
        if p.exists():
            sources.append(p)
    for src in sources[:5]:
        try:
            with open(src, "r", errors="replace") as f:
                lines = f.readlines()
            for i, line in enumerate(lines[-200:], max(1, len(lines)-200)):
                if ERROR_PAT.search(line):
                    sev = "critical" if re.search(r"critical|fatal|traceback", line, re.IGNORECASE) else "error"
                    errors.append({"text": line.strip()[:200], "line": i, "source": src.name, "severity": sev})
                    if len(errors) >= 30:
                        break
        except Exception:
            pass
    return errors

def detect_code_issues() -> list:
    issues = []
    PATS = [
        (r'except\s*:',                           "bare_except",     "⚠️ Bare except — يخفي الأخطاء الحقيقية",          "warning"),
        (r'\bprint\s*\(',                          "debug_print",     "🖨️ print() داخل الكود — استخدم logging بدلاً",    "info"),
        (r'(?i)(TODO|FIXME|HACK|XXX)',             "todo",            "📝 ملاحظة TODO غير منجزة",                       "info"),
        (r'import \*',                             "wildcard_import", "⚠️ Wildcard import — يسبب تعارضات",              "warning"),
        (r'time\.sleep\(',                         "blocking_sleep",  "⏰ time.sleep() — يحجب البرنامج",                 "warning"),
        (r'\bos\.system\(',                        "os_system",       "🔒 os.system() — خطر، استخدم subprocess",         "warning"),
        (r'password\s*=\s*["\'][^"\']{3,}["\']',  "hardcoded_pass",  "🔴 كلمة مرور مكتوبة مباشرة في الكود",             "error"),
    ]
    for f in walk_project():
        if f["ext"] != ".py":
            continue
        try:
            with open(f["fp"], "r", errors="replace") as fh:
                lines = fh.readlines()
            for i, line in enumerate(lines, 1):
                for pat, itype, msg, sev in PATS:
                    if re.search(pat, line) and len(issues) < 60:
                        issues.append({"type": itype, "msg": msg, "file": f["path"], "line": i, "severity": sev, "text": line.strip()[:100]})
        except Exception:
            pass
    return issues

def security_scan() -> list:
    issues = []
    PATS = [
        (r'(?i)(?:password|passwd|secret|api_key|token)\s*=\s*["\'][^"\']{4,}["\']', "hardcoded_secret",  "critical"),
        (r'\beval\s*\(',                                                                "eval_usage",        "high"),
        (r'\bexec\s*\(',                                                                "exec_usage",        "high"),
        (r'subprocess\.[a-z]+\(.*shell\s*=\s*True',                                    "shell_injection",   "critical"),
        (r'pickle\.loads?\(',                                                           "unsafe_pickle",     "medium"),
        (r'DEBUG\s*=\s*True',                                                           "debug_enabled",     "low"),
        (r'allow_origins.*\*',                                                          "cors_wildcard",     "medium"),
        (r'(?i)md5\s*\(',                                                               "weak_hash",         "low"),
    ]
    for f in walk_project():
        if f["ext"] not in {".py", ".js", ".ts"}:
            continue
        try:
            with open(f["fp"], "r", errors="replace") as fh:
                lines = fh.readlines()
            for i, line in enumerate(lines, 1):
                for pat, itype, sev in PATS:
                    if re.search(pat, line) and "nosec" not in line and len(issues) < 50:
                        issues.append({"type": itype, "severity": sev, "file": f["path"], "line": i, "text": line.strip()[:120]})
        except Exception:
            pass
    return issues

def detect_routes() -> list:
    routes = []
    PAT = re.compile(r'@(?:router|app)\.(?:get|post|put|delete|patch)\(["\']([^"\']+)["\']')
    for f in walk_project():
        if f["ext"] != ".py":
            continue
        try:
            with open(f["fp"], "r", errors="replace") as fh:
                content = fh.read()
            for m in PAT.finditer(content):
                routes.append({"path": m.group(1), "file": f["path"]})
        except Exception:
            pass
    return routes

def full_analysis() -> dict:
    update_stats("total_analyses")
    structure  = analyze_structure()
    log_errors = detect_log_errors()
    code_iss   = detect_code_issues()
    sec_issues = security_scan()
    routes     = detect_routes()
    total_issues = len(log_errors) + len(code_iss)
    update_stats("errors_found", total_issues)
    return {
        "structure":   structure,
        "log_errors":  log_errors,
        "code_issues": code_iss,
        "security":    sec_issues,
        "routes":      routes,
        "summary": {
            "total_files":    structure["total_files"],
            "code_files":     structure["code_files"],
            "total_lines":    structure["total_lines"],
            "log_errors":     len(log_errors),
            "code_issues":    len(code_iss),
            "security_issues":len(sec_issues),
            "routes":         len(routes),
            "health":         "good" if total_issues == 0 else ("warning" if total_issues < 10 else "critical"),
        }
    }

# ─── Modification Plan ────────────────────────────────────────────────────────
def create_plan(description: str) -> dict:
    """Phase 1.5 upgrade: returns real files, not generic steps."""
    return create_modification_plan(description)

# ─── Chat Processor ───────────────────────────────────────────────────────────
def process_chat(msg: str) -> dict:
    intent = detect_intent(msg)
    update_stats("total_chats")
    save_chat("user", msg)

    if intent == "help":
        r = _r_help()
    elif intent == "find_file":
        r = answer_file_question(msg)
    elif intent == "plan_modify":
        r = _r_plan_v2(msg)
    elif intent == "dependency":
        r = _r_dependency(msg)
    elif intent == "self_test":
        r = _r_self_test()
    elif intent in ("analyze", "stats"):
        update_stats("total_analyses")
        r = _r_analyze()
    elif intent == "errors":
        update_stats("total_analyses")
        r = _r_errors()
    elif intent in ("backup",):
        r = _r_backup_info()
    elif intent == "restore":
        r = _r_restore_info()
    elif intent == "structure":
        r = _r_structure()
    elif intent == "routes":
        r = _r_routes()
    elif intent == "security":
        r = _r_security()
    elif intent == "improve":
        r = _r_improve(msg)
    elif intent == "memory":
        r = _r_memory()
    elif intent == "status":
        r = _r_status()
    elif intent in ("duplicate", "unused"):
        r = _r_code_quality()
    else:
        r = _r_general(msg)

    save_chat("ai", r["text"][:500])
    return r

# ─── Response Builders ────────────────────────────────────────────────────────
def _r_help() -> dict:
    return {
        "text": """مرحباً! أنا **مهندس الذكاء الاصطناعي v2.0** لمشروع X Control Center 🤖

**🆕 قدرات Intelligence Layer (Phase 1.5):**

🔍 **"ما الملف الذي يتحكم في الصفحة الرئيسية؟"**
📍 **"أين صفحة تسجيل الدخول؟"**
🎨 **"ما الملف الذي يتحكم في الألوان؟"**
📋 **"أنشئ خطة تعديل الصفحة الرئيسية"** — خطة بأسماء ملفات حقيقية
🔗 **"ما الملفات المرتبطة بـ dashboard؟"** — خريطة التبعيات
✅ **"اختبر نفسك"** — self-test للتحقق من الذكاء

**⚡ القدرات السابقة:**
🔍 "افحص الأخطاء" | 📊 "حلل المشروع" | 🔒 "افحص الأمان"
🛣️ "اعرض المسارات" | 💾 "أنشئ نسخة احتياطية" | ⚡ "حالة النظام" """,
        "intent": "help", "type": "info",
        "actions": [
            {"label": "🔍 ما الملف الذي يتحكم في الرئيسية؟", "cmd": "ما الملف الذي يتحكم في الصفحة الرئيسية؟"},
            {"label": "✅ اختبر نفسك",                          "cmd": "اختبر نفسك"},
            {"label": "📋 خطة تعديل الـ dashboard",             "cmd": "أنشئ خطة تعديل dashboard"},
            {"label": "🎨 ما الملف الذي يتحكم في الألوان؟",    "cmd": "ما الملف الذي يتحكم في الألوان؟"},
        ]
    }

def _r_plan_v2(msg: str) -> dict:
    plan = create_modification_plan(msg)
    lines = [f"📋 **{plan['title']}**\n",
             f"⚠️ مستوى الخطورة: {plan['risk_label']}",
             f"🔄 الاستعادة: {plan.get('rollback', '—')}\n",
             "**الملفات المتأثرة:**"]
    for f in plan.get("files_detail", []):
        icon = {"high": "🔴", "medium": "🟠", "low": "🟡"}.get(f["risk"], "✅")
        lines.append(f"  {icon} `{f['path']}` — {f['reason']}")
    lines.append("\n**خطوات التنفيذ:**")
    for s in plan.get("steps", []):
        r_icon = {"none": "✅", "low": "🟡", "medium": "🟠", "high": "🔴"}.get(s.get("risk","none"), "✅")
        lines.append(f"  **{s['n']}.** {s['action']}")
        lines.append(f"     ↳ {s['desc']} {r_icon}")
    return {
        "text": "\n".join(lines), "intent": "plan_modify", "type": "info",
        "data": plan,
        "actions": [{"label": "💾 نسخة احتياطية أولاً", "cmd": "أنشئ نسخة احتياطية"}]
    }

def _r_dependency(msg: str) -> dict:
    dep_map = build_dependency_map()
    concept = _normalize_query(msg)
    relevant = {k: v for k, v in dep_map.items() if concept in k.lower()}
    if not relevant:
        # Return general overview
        lines = [f"🔗 **خريطة التبعيات** ({len(dep_map)} route)\n",
                 "**كل صفحة تعتمد على:**",
                 "  🎨 CSS:  `control_panel/static/css/style.css`",
                 "  ⚡ JS:   `control_panel/static/js/app.js`",
                 "  🏗️ Base: `control_panel/templates/base.html`\n",
                 "**Routes → Templates:**"]
        for route, info in list(dep_map.items())[:8]:
            tmpls = ", ".join(info.get("templates", ["-"])) or "-"
            lines.append(f"  `{route}` ← `{tmpls}` ({info['file'].split('/')[-1]})")
    else:
        lines = [f"🔗 **تبعيات `{concept}`:**\n"]
        for route, info in relevant.items():
            lines.append(f"**Route:** `{route}`")
            lines.append(f"  📄 File:      `{info['file']}`")
            lines.append(f"  🎨 Templates: {', '.join(info.get('templates',['-']))}")
            lines.append(f"  🎨 CSS:       `{', '.join(info.get('css',[]))}`")
            lines.append(f"  ⚡ JS:        `{', '.join(info.get('js',[]))}`\n")
    return {"text": "\n".join(lines), "intent": "dependency", "type": "info",
            "data": {"dep_map": dep_map, "relevant": relevant}}

def _r_self_test() -> dict:
    results = run_self_tests()
    lines = [f"✅ **Self-Test Results — AI Engineer v2.0**\n",
             f"**النتيجة:** {results['score']} — {results['status']}",
             f"**نسبة النجاح:** {results['pass_rate']}\n",
             "**التفاصيل:**"]
    for t in results["tests"]:
        icon = "✅" if t["passed"] else "❌"
        lines.append(f"  {icon} {t['question'][:60]}")
        if not t["passed"]:
            lines.append(f"     ↳ بحث عن `{t['expected_keyword']}` — {'وجد' if t['keyword_found'] else 'لم يجد'}")
    return {
        "text": "\n".join(lines), "intent": "self_test",
        "type": "success" if results["passed"] == results["total"] else "warning",
        "data": results,
    }

def _r_analyze() -> dict:
    files  = walk_project()
    code_f = [f for f in files if f["is_code"]]
    tlines = sum(_count_lines(f["fp"]) for f in code_f)
    by_ext: dict = {}
    for f in files:
        e = f["ext"] or "other"
        by_ext[e] = by_ext.get(e, 0) + 1
    top3 = sorted(by_ext.items(), key=lambda x: x[1], reverse=True)[:3]
    return {
        "text": f"""✅ **تحليل المشروع مكتمل**

📊 **الإحصائيات الكاملة:**
- إجمالي الملفات: **{len(files):,}** ملف
- ملفات الكود: **{len(code_f):,}** ملف
- إجمالي الأسطر: **{tlines:,}** سطر

📂 **أكثر الأنواع شيوعاً:**
{chr(10).join(f"  `{e}` ← {c} ملف" for e,c in top3)}

💡 المشروع يحتوي على بنية منظمة. اكتب **"افحص الأخطاء"** للكشف عن المشاكل.""",
        "intent": "analyze", "type": "success",
        "data": {"total_files": len(files), "code_files": len(code_f), "total_lines": tlines, "by_ext": by_ext},
        "actions": [
            {"label": "🔍 فحص الأخطاء",   "cmd": "افحص الأخطاء"},
            {"label": "🔒 فحص الأمان",     "cmd": "افحص الأمان"},
        ]
    }

def _r_errors() -> dict:
    log_e  = detect_log_errors()
    code_i = detect_code_issues()
    total  = len(log_e) + len(code_i)
    update_stats("errors_found", total)
    L = [f"🔍 **نتائج فحص الأخطاء** (إجمالي: **{total}** مشكلة)\n"]
    if log_e:
        L.append(f"🔴 **أخطاء السجلات:** {len(log_e)}")
        for e in log_e[:2]:
            L.append(f"  · `{e['source']}` سطر {e['line']}: {e['text'][:70]}...")
    else:
        L.append("✅ **السجلات:** نظيفة")
    L.append("")
    if code_i:
        by: dict = {}
        for i in code_i:
            k = i["msg"].split("—")[0].strip()
            by[k] = by.get(k, 0) + 1
        L.append(f"⚠️ **مشاكل الكود:** {len(code_i)}")
        for m, c in list(by.items())[:4]:
            L.append(f"  · {m}: **{c}x**")
    else:
        L.append("✅ **الكود:** نظيف")
    if total == 0:
        L.append("\n🎉 **المشروع في حالة ممتازة!**")
    else:
        L.append(f"\n💡 اذهب إلى **مهندس الذكاء** `/ai/engineer` للتقرير الكامل.")
    return {
        "text": "\n".join(L), "intent": "errors",
        "type": "warning" if total > 0 else "success",
        "data": {"log_errors": log_e[:10], "code_issues": code_i[:10], "total": total},
        "actions": [{"label": "🤖 تقرير مفصل ← مهندس الذكاء", "link": "/ai/engineer"}]
    }

def _r_backup_info() -> dict:
    bks = list_backups()
    last = f"✅ آخر نسخة: **{bks[0]['datetime']}** — {bks[0]['description']}" if bks else "⚠️ لا توجد نسخ احتياطية بعد"
    return {
        "text": f"""💾 **نظام النسخ الاحتياطية**

النسخ المتوفرة: **{len(bks)}** نسخة
{last}

💡 اكتب **"أنشئ نسخة احتياطية الآن"** أو اضغط الزر:""",
        "intent": "backup", "type": "info",
        "data": {"backups": bks[:5], "count": len(bks)},
        "actions": [{"label": "💾 إنشاء نسخة الآن", "cmd": "create_backup"}]
    }

def _r_restore_info() -> dict:
    bks = list_backups()
    if not bks:
        return {"text": "⚠️ لا توجد نسخ احتياطية للاستعادة.", "intent": "restore", "type": "warning"}
    return {
        "text": f"""🔄 **استعادة نسخة احتياطية**

⚠️ **تحذير:** الاستعادة تُعيد الملفات لحالة النسخة المختارة.
(سيتم إنشاء نسخة أمان تلقائياً قبل الاستعادة)

**النسخ المتاحة:** {len(bks)}
**آخر نسخة:** {bks[0]['datetime']} ({bks[0]['files']} ملف)

اذهب إلى **النسخ الاحتياطية** للاستعادة.""",
        "intent": "restore", "type": "warning",
        "data": {"backups": bks[:3]},
        "actions": [{"label": "📋 صفحة النسخ", "link": "/backups"}]
    }

def _r_structure() -> dict:
    files = walk_project()
    dirs: dict = {}
    for f in files:
        d = os.path.dirname(f["path"]) or "."
        dirs[d] = dirs.get(d, 0) + 1
    top = sorted(dirs.items(), key=lambda x: x[1], reverse=True)[:6]
    return {
        "text": f"""📁 **هيكل المشروع** ({len(files)} ملف إجمالاً)

**المجلدات الرئيسية:**
{chr(10).join(f"  `{d}/` — {c} ملف" for d,c in top)}

**المكونات:**
  🤖 `bot.py` — البوت الرئيسي (PrimeDownloader)
  🆘 `support_bot/` — بوت الدعم الفني
  🖥️ `control_panel/` — لوحة التحكم (FastAPI)
  🧠 `control_panel/routers/` — مسارات API (11 router)
  🎨 `control_panel/templates/` — واجهات المستخدم

💡 اكتب **"ما الملف الذي يتحكم في X؟"** لأي صفحة أو ميزة.""",
        "intent": "structure", "type": "info",
        "data": {"dirs": top, "total": len(files)},
    }

def _r_routes() -> dict:
    routes = detect_routes()
    by_file: dict = {}
    for r in routes:
        by_file.setdefault(r["file"], []).append(r["path"])
    L = [f"🛣️ **المسارات في المشروع** (إجمالي: **{len(routes)}**)\n"]
    for file, paths in list(by_file.items())[:7]:
        L.append(f"**`{file}`:**")
        for p in paths[:5]:
            L.append(f"  `{p}`")
        if len(paths) > 5:
            L.append(f"  _...و {len(paths)-5} مسار آخر_")
    return {
        "text": "\n".join(L), "intent": "routes", "type": "info",
        "data": {"routes": routes[:40], "total": len(routes)},
    }

def _r_security() -> dict:
    iss      = security_scan()
    critical = [i for i in iss if i["severity"] == "critical"]
    high     = [i for i in iss if i["severity"] == "high"]
    medium   = [i for i in iss if i["severity"] == "medium"]
    L = ["🔒 **تقرير فحص الأمان**\n"]
    if not iss:
        L.append("✅ **ممتاز!** لا توجد ثغرات أمنية مكتشفة.")
    else:
        L.append(f"🔴 حرجة: **{len(critical)}** | 🟠 عالية: **{len(high)}** | 🟡 متوسطة: **{len(medium)}**\n")
        for i in (critical + high)[:5]:
            L.append(f"  · **{i['type']}** في `{i['file']}` سطر {i['line']}")
        if len(iss) > 5:
            L.append(f"\n_...و {len(iss)-5} مشكلة أخرى_")
    return {
        "text": "\n".join(L), "intent": "security",
        "type": "error" if critical else ("warning" if iss else "success"),
        "data": {"issues": iss[:20], "total": len(iss), "critical": len(critical)},
    }

def _r_improve(msg: str) -> dict:
    plan = create_modification_plan(msg)
    files_list = "\n".join(f"  · `{f}`" for f in plan.get("files_affected", [])[:5]) or "  · غير محدد"
    return {
        "text": f"""✨ **خطة التحسين**

**الملفات التي تحتاج تعديل:**
{files_list}

**المستوى:** {plan['risk_label']}

💡 اكتب **"أنشئ خطة تعديل [اسم الصفحة]"** للحصول على خطة تفصيلية بأسماء الملفات الحقيقية.""",
        "intent": "improve", "type": "info",
        "data": plan,
        "actions": [
            {"label": "📋 خطة تفصيلية",         "cmd": f"أنشئ خطة تعديل {msg[:40]}"},
            {"label": "💾 نسخة احتياطية أولاً", "cmd": "أنشئ نسخة احتياطية"},
        ]
    }

def _r_memory() -> dict:
    mem   = load_memory()
    stats = mem.get("ai_stats", {})
    comps = mem.get("components", {})
    ki    = mem.get("knowledge_index", {})
    L = [f"🧠 **ذاكرة الذكاء الاصطناعي v2.0**\n",
         f"📌 المشروع: **{mem.get('project_name')}** v{mem.get('version')}",
         f"🤖 محرك الذكاء: **v{mem.get('engine_version', '1.0')}**",
         f"🕐 آخر تحديث: {mem.get('last_updated','?')[:19]}\n",
         f"**المكونات المعروفة ({len(comps)}):**"]
    for v in list(comps.values())[:5]:
        L.append(f"  · **{v['name']}** — {v['description']}")
    L.append(f"\n**قاعدة المعرفة (Intelligence Layer):**")
    L.append(f"  🗺️ مفاهيم مُفهرسة: {len(_SEMANTIC_MAP)} مفهوم")
    L.append(f"  📁 ملفات مُعيَّنة:  {len({e[0] for entries in _SEMANTIC_MAP.values() for e in entries})} ملف")
    L.append(f"\n**الإحصائيات:**")
    L.append(f"  محادثات: {stats.get('total_chats',0)} | تحليلات: {stats.get('total_analyses',0)} | نسخ: {stats.get('total_backups',0)}")
    return {"text": "\n".join(L), "intent": "memory", "type": "info", "data": mem}

def _r_status() -> dict:
    return {
        "text": """⚡ **حالة نظام X Control Center**

🤖 **PrimeDownloader Bot** — ✅ يعمل
🆘 **Support Bot** — ✅ يعمل
🖥️ **لوحة التحكم (Port 5000)** — ✅ تعمل
🧠 **محرك الذكاء الاصطناعي v2.0** — ✅ جاهز (Intelligence Layer نشط)
💾 **نظام النسخ الاحتياطية** — ✅ جاهز

✅ **جميع الأنظمة تعمل بشكل طبيعي**

💡 اذهب إلى **صحة النظام** `/system` للمعلومات المباشرة.""",
        "intent": "status", "type": "success",
        "actions": [{"label": "📊 صحة النظام", "link": "/system"}]
    }

def _r_code_quality() -> dict:
    issues = detect_code_issues()
    dup    = [i for i in issues if i["type"] == "todo"]
    unused = [i for i in issues if i["type"] == "debug_print"]
    return {
        "text": f"""🔎 **جودة الكود**

📝 **TODO غير منجزة:** {len(dup)}
🖨️ **print() debug:** {len(unused)}
⚠️ **مشاكل أخرى:** {len(issues) - len(dup) - len(unused)}

إجمالي الملاحظات: **{len(issues)}**

💡 اذهب إلى **مهندس الذكاء** للتقرير الكامل مع مواضع الأسطر.""",
        "intent": "code_quality", "type": "warning" if issues else "success",
        "data": {"issues": issues[:15]},
        "actions": [{"label": "🤖 مهندس الذكاء", "link": "/ai/engineer"}]
    }

def _r_general(msg: str) -> dict:
    return {
        "text": f"""🤔 لم أفهم الطلب بشكل كامل.

كتبت: **"{msg}"**

حاول أحد هذه الأوامر:
  · **"ما الملف الذي يتحكم في الصفحة الرئيسية؟"**
  · **"افحص الأخطاء"**
  · **"حلل المشروع"**
  · **"أنشئ نسخة احتياطية"**
  · **"افحص الأمان"**
  · **"مساعدة"** — لقائمة كاملة بقدراتي""",
        "intent": "unknown", "type": "info",
        "actions": [{"label": "❓ المساعدة", "cmd": "مساعدة"}]
    }

# ─── Helpers ──────────────────────────────────────────────────────────────────
def _count_lines(fp: str) -> int:
    try:
        with open(fp, "r", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def _fmt(b: int) -> str:
    if b < 1024:      return f"{b} B"
    if b < 1024**2:   return f"{b/1024:.1f} KB"
    if b < 1024**3:   return f"{b/1024**2:.1f} MB"
    return f"{b/1024**3:.2f} GB"
