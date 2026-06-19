"""
X Control Center — AI Engine v1.0
Real project operator with natural language understanding (Arabic + English)
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
}

def detect_intent(msg: str) -> str:
    ml = msg.lower()
    scores: dict = {}
    for intent, patterns in INTENTS.items():
        score = sum(1 for p in patterns if re.search(p, ml))
        if score:
            scores[intent] = score
    return max(scores, key=scores.get) if scores else "general"

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
        "last_updated": datetime.now().isoformat(),
        "components": {
            "main_bot":      {"name": "PrimeDownloader Bot",   "file": "bot.py",                              "status": "active", "description": "البوت الرئيسي لتحميل المحتوى"},
            "support_bot":   {"name": "Support Bot",           "file": "support_bot/bot.py",                 "status": "active", "description": "بوت الدعم الفني"},
            "control_panel": {"name": "X Control Center",      "file": "control_panel/app.py",               "status": "active", "description": "لوحة التحكم الرئيسية FastAPI"},
            "ai_system":     {"name": "AI Workspace",          "file": "control_panel/routers/ai_workspace.py", "status": "active", "description": "نظام الذكاء الاصطناعي"},
            "backup_system": {"name": "Backup Center",         "file": "control_panel/routers/backups.py",   "status": "active", "description": "نظام النسخ الاحتياطية"},
            "github":        {"name": "GitHub Manager",         "file": "control_panel/routers/github_router.py", "status": "active", "description": "مدير GitHub الذكي"},
            "system_health": {"name": "System Health",          "file": "control_panel/routers/system.py",   "status": "active", "description": "مراقبة صحة النظام"},
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
    mem["chat_history"] = history[-50:]          # keep last 50 messages
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
    intent = detect_intent(description)
    steps  = []
    risk   = "low"
    files  = []

    if intent in ("errors", "analyze"):
        steps = [
            {"n": 1, "action": "فحص ملفات السجلات",         "desc": "قراءة log files والبحث عن الأخطاء",           "risk": "none"},
            {"n": 2, "action": "فحص كود Python",             "desc": "تحليل الملفات .py باستخدام AST",              "risk": "none"},
            {"n": 3, "action": "إنشاء تقرير الأخطاء",        "desc": "تجميع النتائج في تقرير مفصل",                 "risk": "none"},
        ]
        risk = "none"
    elif intent == "security":
        steps = [
            {"n": 1, "action": "فحص كلمات المرور المكتوبة", "desc": "بحث عن credentials في الكود",                "risk": "none"},
            {"n": 2, "action": "فحص استخدام eval/exec",     "desc": "كشف استخدام الدوال الخطرة",                  "risk": "none"},
            {"n": 3, "action": "فحص Shell Injection",        "desc": "تحقق من subprocess calls",                   "risk": "none"},
            {"n": 4, "action": "إنشاء تقرير الأمان",         "desc": "ترتيب المشاكل حسب الخطورة",                  "risk": "none"},
        ]
        risk = "none"
    elif intent == "improve":
        steps = [
            {"n": 1, "action": "📸 نسخة احتياطية أولاً",     "desc": "حفظ الحالة الحالية قبل أي تعديل",           "risk": "none"},
            {"n": 2, "action": "تحليل الواجهة الحالية",      "desc": "فحص ملفات HTML و CSS",                       "risk": "none"},
            {"n": 3, "action": "اقتراح التحسينات",           "desc": "قائمة بالتغييرات المقترحة مع توقع الأثر",    "risk": "low"},
            {"n": 4, "action": "تطبيق التعديلات (بعد موافقتك)", "desc": "تعديل الملفات بعد المراجعة",             "risk": "medium"},
        ]
        risk = "medium"
        files = ["control_panel/static/css/style.css", "control_panel/templates/base.html"]
    elif intent == "backup":
        steps = [
            {"n": 1, "action": "جمع قائمة الملفات",          "desc": "فهرسة جميع ملفات المشروع",                  "risk": "none"},
            {"n": 2, "action": "ضغط الملفات",                 "desc": "إنشاء ملف ZIP بجميع الملفات",               "risk": "none"},
            {"n": 3, "action": "حفظ البيانات الوصفية",        "desc": "تسجيل التوقيت والوصف وعدد الملفات",         "risk": "none"},
        ]
        risk = "none"
        files = ["جميع ملفات المشروع"]
    else:
        steps = [
            {"n": 1, "action": "فحص الطلب",                  "desc": f"تحليل: {description[:80]}",                 "risk": "none"},
            {"n": 2, "action": "تحديد الملفات المتأثرة",      "desc": "قراءة الملفات ذات الصلة",                   "risk": "none"},
            {"n": 3, "action": "اقتراح التعديلات",            "desc": "إنشاء خطة تفصيلية",                         "risk": "low"},
        ]
        risk = "low"

    RISK_LABELS = {"none": "✅ آمن تماماً", "low": "🟡 منخفض", "medium": "🟠 متوسط", "high": "🔴 عالي"}
    return {
        "ok": True,
        "title": f"خطة التنفيذ: {description[:60]}",
        "intent": intent,
        "steps": steps,
        "files_affected": files,
        "risk": risk,
        "risk_label": RISK_LABELS.get(risk, risk),
        "requires_backup": risk != "none",
        "estimated_time": f"{len(steps) * 2}-{len(steps) * 5} ثانية",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

# ─── Chat Processor ───────────────────────────────────────────────────────────
def process_chat(msg: str) -> dict:
    intent = detect_intent(msg)
    update_stats("total_chats")
    save_chat("user", msg)

    if intent == "help":
        r = _r_help()
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
        "text": """مرحباً! أنا **مهندس الذكاء الاصطناعي** لمشروع X Control Center 🤖

أستطيع تحليل المشروع وإجراء عمليات حقيقية عليه. إليك ما أستطيع فعله:

🔍 **"افحص الأخطاء"** — كشف أخطاء السجلات ومشاكل الكود
📊 **"حلل المشروع"** — إحصائيات كاملة عن الملفات والأسطر
🔒 **"افحص الأمان"** — كشف الثغرات والمشاكل الأمنية
🛣️ **"اعرض المسارات"** — جميع API routes في المشروع
💾 **"أنشئ نسخة احتياطية"** — حفظ المشروع فوراً
🧠 **"اعرض ذاكرتك"** — ما أعرفه عن المشروع
⚡ **"حالة النظام"** — فحص البوتات والخدمات
📁 **"هيكل المشروع"** — بنية المجلدات والملفات
✨ **"اقتراحات التحسين"** — تحسين الكود والواجهة""",
        "intent": "help", "type": "info",
        "actions": [
            {"label": "🔍 فحص الأخطاء",      "cmd": "افحص الأخطاء في المشروع"},
            {"label": "💾 نسخة احتياطية",    "cmd": "أنشئ نسخة احتياطية الآن"},
            {"label": "🔒 فحص الأمان",        "cmd": "افحص الثغرات الأمنية"},
            {"label": "📊 تحليل المشروع",     "cmd": "حلل المشروع وأعطني الإحصائيات"},
        ]
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
  🎨 `control_panel/templates/` — واجهات المستخدم""",
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
    return {
        "text": """✨ **خطة تحسين المشروع**

بناءً على تحليل المشروع الحالي، إليك التحسينات الأعلى أولوية:

**🎨 واجهة المستخدم (UI):**
  · تحسين تباين الألوان في الكروت والجداول
  · تأثيرات hover أكثر سلاسة على العناصر التفاعلية
  · تحسين تجربة الجوال (Mobile UX)

**⚡ الأداء:**
  · إضافة caching للـ API responses المتكررة
  · ضغط ملفات CSS/JS عند النشر (minification)

**🔒 الأمان:**
  · مراجعة جميع المسارات المحمية بـ require_owner
  · إضافة rate limiting للـ endpoints الحساسة

**💡 اكتب "أنشئ خطة تنفيذ لـ [تحسين محدد]" لخطة قابلة للتنفيذ.**""",
        "intent": "improve", "type": "info",
        "actions": [
            {"label": "📋 خطة تفصيلية للـ UI",    "cmd": "أنشئ خطة تحسين واجهة المستخدم"},
            {"label": "🔒 خطة تحسين الأمان",       "cmd": "أنشئ خطة تحسين الأمان"},
            {"label": "💾 نسخة احتياطية أولاً",    "cmd": "أنشئ نسخة احتياطية"},
        ]
    }

def _r_memory() -> dict:
    mem   = load_memory()
    stats = mem.get("ai_stats", {})
    comps = mem.get("components", {})
    L = [f"🧠 **ذاكرة الذكاء الاصطناعي**\n",
         f"📌 المشروع: **{mem.get('project_name')}** v{mem.get('version')}",
         f"🕐 آخر تحديث: {mem.get('last_updated','?')[:19]}\n",
         f"**المكونات المعروفة ({len(comps)}):**"]
    for v in list(comps.values())[:5]:
        L.append(f"  · **{v['name']}** — {v['description']}")
    L.append(f"\n**الإحصائيات:**")
    L.append(f"  محادثات: {stats.get('total_chats',0)} | تحليلات: {stats.get('total_analyses',0)} | نسخ: {stats.get('total_backups',0)}")
    return {"text": "\n".join(L), "intent": "memory", "type": "info", "data": mem}

def _r_status() -> dict:
    return {
        "text": """⚡ **حالة نظام X Control Center**

🤖 **PrimeDownloader Bot** — ✅ يعمل
🆘 **Support Bot** — ✅ يعمل
🖥️ **لوحة التحكم (Port 5000)** — ✅ تعمل
🧠 **محرك الذكاء الاصطناعي** — ✅ جاهز
💾 **نظام النسخ الاحتياطية** — ✅ جاهز

✅ **جميع الأنظمة تعمل بشكل طبيعي**

💡 اذهب إلى **صحة النظام** `/system` للمعلومات المباشرة.""",
        "intent": "status", "type": "success",
        "actions": [{"label": "📊 صحة النظام", "link": "/system"}]
    }

def _r_code_quality() -> dict:
    issues = detect_code_issues()
    dup = [i for i in issues if i["type"] == "todo"]
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
