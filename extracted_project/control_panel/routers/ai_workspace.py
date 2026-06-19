"""AI Workspace — project analyzer, code reviewer, error detector."""
import os
import json
import time
import re
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from ..auth import require_owner
from ..config import CONTROL_PANEL_DIR, EXTRACTED_DIR, PROJECT_ROOT, LOGS_DIR

router = APIRouter(prefix="/ai")
templates = Jinja2Templates(directory=os.path.join(CONTROL_PANEL_DIR, "templates"))

SKIP_DIRS  = {"__pycache__", ".git", "node_modules", ".pythonlibs", "temp", "backups",
               ".local", ".venv", "dist", "build", ".cache"}
CODE_EXTS  = {".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".toml", ".sh", ".md"}
MAX_READ   = 8000


def _walk_project():
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
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "is_code": ext in CODE_EXTS,
                })
            except Exception:
                pass
    return files


def _count_lines(fp: str) -> int:
    try:
        with open(fp, "r", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _read_snippet(fp: str, max_bytes: int = MAX_READ) -> str:
    try:
        with open(fp, "r", errors="replace") as f:
            return f.read(max_bytes)
    except Exception:
        return ""


def _analyze_structure() -> dict:
    files = _walk_project()
    by_ext: dict[str, int] = {}
    total_lines = 0
    total_size  = 0
    code_files  = []
    for fi in files:
        ext = fi["ext"] or "other"
        by_ext[ext] = by_ext.get(ext, 0) + 1
        total_size += fi["size"]
        if fi["is_code"]:
            fp = os.path.join(EXTRACTED_DIR, fi["path"])
            lc = _count_lines(fp)
            total_lines += lc
            code_files.append({**fi, "lines": lc})
    top_files = sorted(code_files, key=lambda x: x["lines"], reverse=True)[:10]
    return {
        "total_files":  len(files),
        "code_files":   len(code_files),
        "total_lines":  total_lines,
        "total_size_h": _fmt(total_size),
        "by_ext":       dict(sorted(by_ext.items(), key=lambda x: x[1], reverse=True)[:12]),
        "top_files":    top_files,
        "ts":           datetime.utcnow().strftime("%H:%M:%S"),
    }


def _analyze_errors() -> dict:
    issues = []
    # Scan log files
    for fn in ["main_bot.log", "support_bot.log"]:
        lf = os.path.join(LOGS_DIR, fn)
        if not os.path.exists(lf):
            continue
        try:
            with open(lf, "r", errors="replace") as f:
                lines = f.readlines()[-200:]
            for i, line in enumerate(lines):
                if any(k in line.upper() for k in ["ERROR", "TRACEBACK", "EXCEPTION", "CRITICAL", "FAILED"]):
                    issues.append({
                        "source": fn,
                        "line": i + max(0, len(lines) - 200) + 1,
                        "text": line.strip()[:200],
                        "severity": "critical" if "CRITICAL" in line.upper() else "error",
                    })
        except Exception:
            pass
    # Check Python files for common issues
    py_issues = []
    for root, dirs, fnames in os.walk(EXTRACTED_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fnames:
            if not fn.endswith(".py"):
                continue
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, EXTRACTED_DIR)
            content = _read_snippet(fp, 4000)
            if "os.system(" in content:
                py_issues.append({"file": rel, "type": "security", "msg": "استخدام os.system() — يُفضل subprocess"})
            if "except:" in content and "except Exception" not in content:
                py_issues.append({"file": rel, "type": "warning", "msg": "bare except — يُفضل تحديد نوع الاستثناء"})
            if "TODO" in content or "FIXME" in content:
                todos = re.findall(r"#\s*(TODO|FIXME)[^\n]*", content)
                for t in todos[:3]:
                    py_issues.append({"file": rel, "type": "info", "msg": t.strip()})
    return {
        "log_errors":  issues[-30:],
        "code_issues": py_issues[:20],
        "total_log_errors": len(issues),
        "total_code_issues": len(py_issues),
    }


def _generate_suggestions() -> list:
    suggestions = []
    # Check requirements vs installed
    req_path = os.path.join(EXTRACTED_DIR, "requirements.txt")
    if os.path.exists(req_path):
        with open(req_path) as f:
            reqs = [l.strip().split("==")[0].split(">=")[0] for l in f if l.strip() and not l.startswith("#")]
        suggestions.append({
            "category": "التبعيات",
            "title": f"تم تحديد {len(reqs)} تبعية في requirements.txt",
            "detail": ", ".join(reqs[:8]) + ("..." if len(reqs) > 8 else ""),
            "priority": "info",
            "action": None,
        })
    # Check database size
    from ..config import MAIN_DB, SUPPORT_DB
    for db_name, db_path in [("قاعدة البيانات الرئيسية", MAIN_DB), ("قاعدة الدعم", SUPPORT_DB)]:
        if os.path.exists(db_path):
            size = os.path.getsize(db_path)
            if size > 100 * 1024 * 1024:
                suggestions.append({
                    "category": "قاعدة البيانات",
                    "title": f"{db_name} حجمها {_fmt(size)}",
                    "detail": "يُنصح بتنظيف البيانات القديمة أو أرشفتها",
                    "priority": "warning",
                    "action": "cleanup_db",
                })
    # Check temp dir
    temp_files = []
    from ..config import TEMP_DIR
    if os.path.exists(TEMP_DIR):
        for fn in os.listdir(TEMP_DIR):
            fp = os.path.join(TEMP_DIR, fn)
            try:
                if os.path.getsize(fp) > 1024:
                    temp_files.append(fn)
            except Exception:
                pass
    if temp_files:
        suggestions.append({
            "category": "الملفات المؤقتة",
            "title": f"يوجد {len(temp_files)} ملف مؤقت",
            "detail": "يمكن حذفها لتوفير مساحة",
            "priority": "info",
            "action": "clear_temp",
        })
    suggestions.append({
        "category": "الأمان",
        "title": "النسخ الاحتياطية التلقائية",
        "detail": "يُنصح بجدولة نسخة احتياطية يومية لحماية البيانات",
        "priority": "info",
        "action": None,
    })
    return suggestions


def _review_file(rel_path: str) -> dict:
    fp = os.path.join(EXTRACTED_DIR, rel_path)
    if not os.path.exists(fp):
        return {"ok": False, "error": "الملف غير موجود"}
    ext = os.path.splitext(fp)[1].lower()
    content = _read_snippet(fp, MAX_READ)
    lines   = content.count("\n") + 1
    chars   = len(content)
    issues  = []
    suggestions = []
    if ext == ".py":
        if len(content) > 5000 and content.count("def ") < 3:
            issues.append("الملف طويل جداً بدون تقسيم كافٍ للدوال")
        imports = [l.strip() for l in content.split("\n") if l.startswith("import ") or l.startswith("from ")]
        if "print(" in content:
            suggestions.append("استبدل print() بـ logging للإنتاج")
        todos = re.findall(r"#\s*(TODO|FIXME)[^\n]*", content)
        if todos:
            issues.extend(todos[:3])
    truncated = len(content) >= MAX_READ
    return {
        "ok": True,
        "path": rel_path,
        "lines": lines,
        "chars": chars,
        "ext": ext,
        "issues": issues,
        "suggestions": suggestions,
        "snippet": content[:2000],
        "truncated": truncated,
    }


def _fmt(b: int) -> str:
    if b < 1024:       return f"{b} B"
    elif b < 1024**2:  return f"{b/1024:.1f} KB"
    elif b < 1024**3:  return f"{b/1024**2:.1f} MB"
    return f"{b/1024**3:.2f} GB"


@router.get("", response_class=HTMLResponse)
async def ai_page(request: Request, session: dict = Depends(require_owner)):
    return templates.TemplateResponse(request, "ai_workspace.html", {
        "active_page": "ai"
    })


@router.get("/engineer", response_class=HTMLResponse)
async def ai_engineer_page(request: Request, session: dict = Depends(require_owner)):
    return templates.TemplateResponse(request, "ai_engineer.html", {
        "active_page": "ai_engineer"
    })


@router.get("/memory", response_class=HTMLResponse)
async def ai_memory_page(request: Request, session: dict = Depends(require_owner)):
    return templates.TemplateResponse(request, "ai_memory.html", {
        "active_page": "ai_memory"
    })


@router.get("/review", response_class=HTMLResponse)
async def ai_review_page(request: Request, session: dict = Depends(require_owner)):
    return templates.TemplateResponse(request, "ai_review.html", {
        "active_page": "ai_review"
    })


@router.get("/api/structure")
async def api_structure(session: dict = Depends(require_owner)):
    return _analyze_structure()


@router.get("/api/errors")
async def api_errors(session: dict = Depends(require_owner)):
    return _analyze_errors()


@router.get("/api/suggestions")
async def api_suggestions(session: dict = Depends(require_owner)):
    return _generate_suggestions()


@router.get("/api/files")
async def api_files(session: dict = Depends(require_owner)):
    return _walk_project()


@router.post("/api/review")
async def api_review(request: Request, session: dict = Depends(require_owner)):
    body = await request.json()
    path = body.get("path", "").strip()
    if not path or ".." in path:
        return JSONResponse({"ok": False, "error": "مسار غير صالح"}, status_code=400)
    return _review_file(path)


@router.post("/api/clear_temp")
async def api_clear_temp(session: dict = Depends(require_owner)):
    from ..config import TEMP_DIR
    removed = 0
    try:
        for fn in os.listdir(TEMP_DIR):
            fp = os.path.join(TEMP_DIR, fn)
            try:
                os.remove(fp)
                removed += 1
            except Exception:
                pass
        return {"ok": True, "removed": removed, "msg": f"تم حذف {removed} ملف مؤقت"}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
