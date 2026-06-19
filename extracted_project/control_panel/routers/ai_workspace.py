"""AI Workspace — project analyzer, code reviewer, error detector, AI chat operator."""
import asyncio
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
from ..ai_engine import (
    process_chat, create_plan, create_backup, list_backups, restore_backup,
    load_memory, save_memory, full_analysis, analyze_structure as _eng_structure,
    detect_log_errors, detect_code_issues, security_scan, detect_routes,
    # Phase 1.5 — Intelligence Layer
    search_project_files, build_dependency_map, answer_file_question,
    get_file_role, run_self_tests, create_modification_plan,
    # Phase 2 — HF Space Integration
    call_hf_analyze, call_hf_assistant, call_hf_planner, call_hf_memory, hf_status,
    HF_SPACE_URL,
    # Phase 3 — Engineering Intelligence
    ProjectBrain, save_engineering_decision, list_engineering_decisions,
)

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


# ═══════════════════════════════════════════════════════════════════════════════
#  AI ENGINE API  — Real operator endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/chat")
async def api_chat(request: Request, session: dict = Depends(require_owner)):
    try:
        body = await request.json()
        msg  = str(body.get("message", "")).strip()
        if not msg:
            return JSONResponse({"ok": False, "error": "الرسالة فارغة"}, status_code=400)
        if len(msg) > 2000:
            return JSONResponse({"ok": False, "error": "الرسالة طويلة جداً"}, status_code=400)
        result = await asyncio.to_thread(process_chat, msg)
        return {"ok": True, **result}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.post("/api/plan")
async def api_plan(request: Request, session: dict = Depends(require_owner)):
    try:
        body = await request.json()
        desc = str(body.get("description", "")).strip()
        if not desc:
            return JSONResponse({"ok": False, "error": "الوصف فارغ"}, status_code=400)
        result = create_plan(desc)
        return result
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/backup/list")
async def api_backup_list(session: dict = Depends(require_owner)):
    return list_backups()


@router.post("/api/backup/create")
async def api_backup_create(request: Request, session: dict = Depends(require_owner)):
    try:
        body = await request.json()
        desc = str(body.get("description", "نسخة يدوية")).strip() or "نسخة يدوية"
        result = create_backup(desc)
        return result
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.post("/api/backup/restore")
async def api_backup_restore(request: Request, session: dict = Depends(require_owner)):
    try:
        body  = await request.json()
        bk_id = str(body.get("id", "")).strip()
        if not bk_id or ".." in bk_id or "/" in bk_id:
            return JSONResponse({"ok": False, "error": "معرف النسخة غير صالح"}, status_code=400)
        result = restore_backup(bk_id)
        return result
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/memory")
async def api_memory(session: dict = Depends(require_owner)):
    return load_memory()


@router.get("/api/full_analysis")
async def api_full_analysis(session: dict = Depends(require_owner)):
    return full_analysis()


@router.get("/api/security")
async def api_security(session: dict = Depends(require_owner)):
    issues   = security_scan()
    critical = [i for i in issues if i["severity"] == "critical"]
    high     = [i for i in issues if i["severity"] == "high"]
    medium   = [i for i in issues if i["severity"] == "medium"]
    low      = [i for i in issues if i["severity"] == "low"]
    return {
        "issues": issues, "total": len(issues),
        "critical": len(critical), "high": len(high),
        "medium": len(medium), "low": len(low),
        "score": max(0, 100 - len(critical)*25 - len(high)*10 - len(medium)*5 - len(low)*2),
    }


@router.get("/api/routes")
async def api_routes(session: dict = Depends(require_owner)):
    routes = detect_routes()
    by_file: dict = {}
    for r in routes:
        by_file.setdefault(r["file"], []).append(r["path"])
    return {"routes": routes, "total": len(routes), "by_file": by_file}


@router.get("/api/chat_history")
async def api_chat_history(session: dict = Depends(require_owner)):
    mem = load_memory()
    return mem.get("chat_history", [])


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 1.5 — PROJECT INTELLIGENCE LAYER
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/knowledge")
async def api_knowledge(session: dict = Depends(require_owner)):
    """Return the full semantic knowledge map of the project."""
    from ..ai_engine import _SEMANTIC_MAP, _ALIASES
    mapped_files = {}
    for concept, entries in _SEMANTIC_MAP.items():
        for (rel_path, role, desc) in entries:
            if rel_path not in mapped_files:
                mapped_files[rel_path] = {"path": rel_path, "role": role, "description": desc, "concepts": []}
            mapped_files[rel_path]["concepts"].append(concept)
    return {
        "ok": True,
        "total_concepts": len(_SEMANTIC_MAP),
        "total_mapped_files": len(mapped_files),
        "concepts": list(_SEMANTIC_MAP.keys()),
        "aliases": list(_ALIASES.keys()),
        "file_map": list(mapped_files.values()),
    }


@router.post("/api/search")
async def api_search(request: Request, session: dict = Depends(require_owner)):
    """Intelligent file search — returns files relevant to a concept/query."""
    body  = await request.json()
    query = str(body.get("query", "")).strip()
    if not query:
        return JSONResponse({"ok": False, "error": "query is required"}, status_code=400)
    results = search_project_files(query)
    return {"ok": True, "query": query, "total": len(results), "results": results}


@router.post("/api/file_question")
async def api_file_question(request: Request, session: dict = Depends(require_owner)):
    """Answer 'what file controls X?' with real file names and roles."""
    body = await request.json()
    msg  = str(body.get("message", "")).strip()
    if not msg:
        return JSONResponse({"ok": False, "error": "message is required"}, status_code=400)
    result = answer_file_question(msg)
    return {"ok": True, **result}


@router.get("/api/dependencies")
async def api_dependencies(session: dict = Depends(require_owner)):
    """Auto-built route → template → CSS/JS dependency map."""
    dep_map = build_dependency_map()
    return {
        "ok": True,
        "total_routes": len(dep_map),
        "shared_assets": {
            "css": "control_panel/static/css/style.css",
            "js":  "control_panel/static/js/app.js",
            "base_template": "control_panel/templates/base.html",
        },
        "routes": dep_map,
    }


@router.post("/api/file_role")
async def api_file_role(request: Request, session: dict = Depends(require_owner)):
    """Return a full profile of a file: what it does, dependencies, role."""
    body = await request.json()
    path = str(body.get("path", "")).strip()
    if not path or ".." in path:
        return JSONResponse({"ok": False, "error": "invalid path"}, status_code=400)
    return get_file_role(path)


@router.post("/api/plan_v2")
async def api_plan_v2(request: Request, session: dict = Depends(require_owner)):
    """Phase 1.5 planning engine — returns real file names, risks, rollback."""
    body = await request.json()
    desc = str(body.get("description", "")).strip()
    if not desc:
        return JSONResponse({"ok": False, "error": "description is required"}, status_code=400)
    return create_modification_plan(desc)


@router.get("/api/self_test")
async def api_self_test(session: dict = Depends(require_owner)):
    """Run Phase 1.5 + Phase 2 self-tests — verify AI intent classification."""
    return run_self_tests()


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Hugging Face Space Integration
# Space: https://huggingface.co/spaces/7atemmmmm/x-ai-core
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/hf/status")
async def api_hf_status(session: dict = Depends(require_owner)):
    """Check HF space connectivity and health."""
    status = hf_status()
    return {
        "ok": status["connected"],
        "space_url": HF_SPACE_URL,
        "connected": status["connected"],
        "memory_ok": status.get("memory_ok", False),
        "error": status.get("error"),
        "endpoints": ["/api/analyze", "/api/assistant", "/api/planner", "/api/memory"],
    }


@router.post("/api/hf/analyze")
async def api_hf_analyze(request: Request, session: dict = Depends(require_owner)):
    """Proxy to HF /api/analyze — error diagnosis and code analysis."""
    body = await request.json()
    text = str(body.get("text", "")).strip()
    if not text:
        return JSONResponse({"ok": False, "error": "text is required"}, status_code=400)
    result = call_hf_analyze(text)
    return result


@router.post("/api/hf/assistant")
async def api_hf_assistant(request: Request, session: dict = Depends(require_owner)):
    """Proxy to HF /api/assistant — general AI assistant for project questions."""
    body = await request.json()
    message = str(body.get("message", "")).strip()
    if not message:
        return JSONResponse({"ok": False, "error": "message is required"}, status_code=400)
    result = call_hf_assistant(message)
    return result


@router.post("/api/hf/planner")
async def api_hf_planner(request: Request, session: dict = Depends(require_owner)):
    """Proxy to HF /api/planner — step-by-step feature roadmap."""
    body = await request.json()
    description = str(body.get("description", "")).strip()
    if not description:
        return JSONResponse({"ok": False, "error": "description is required"}, status_code=400)
    result = call_hf_planner(description)
    return result


@router.get("/api/hf/memory")
async def api_hf_memory(session: dict = Depends(require_owner)):
    """GET HF /api/memory — project memory stored in the HF space."""
    result = call_hf_memory()
    return result


# ─── Phase 3: Engineering Intelligence API ───────────────────────────────────

@router.get("/api/brain")
async def api_brain(session: dict = Depends(require_owner)):
    """
    GET /ai/api/brain — Full ProjectBrain snapshot.
    Returns the living cached project model: modules, totals, risks, tech-debt, scaling.
    """
    brain  = ProjectBrain.get()
    status = ProjectBrain.status()
    return {
        "ok":     True,
        "status": status,
        "brain":  brain,
    }


@router.get("/api/risk")
async def api_risk(session: dict = Depends(require_owner)):
    """
    GET /ai/api/risk — Full risk analysis from ProjectBrain.RISKS.
    Returns ranked risks with severity, detail, and fix actions.
    """
    risks   = ProjectBrain.RISKS
    totals  = ProjectBrain.get().get("totals", {})
    critical = [r for r in risks if r["severity"] == "CRITICAL"]
    high     = [r for r in risks if r["severity"] == "HIGH"]
    medium   = [r for r in risks if r["severity"] == "MEDIUM"]
    return {
        "ok":           True,
        "total_risks":  len(risks),
        "critical":     len(critical),
        "high":         len(high),
        "medium":       len(medium),
        "risks":        risks,
        "project_size": totals,
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/api/tech_debt")
async def api_tech_debt(session: dict = Depends(require_owner)):
    """
    GET /ai/api/tech_debt — Technical debt registry from ProjectBrain.TECH_DEBT.
    Returns prioritized list of refactoring items with impact/effort ratings.
    """
    debts    = ProjectBrain.TECH_DEBT
    high     = [d for d in debts if d["impact"] == "HIGH"]
    medium   = [d for d in debts if d["impact"] == "MEDIUM"]
    low      = [d for d in debts if d["impact"] == "LOW"]
    return {
        "ok":          True,
        "total":       len(debts),
        "high_impact": len(high),
        "medium":      len(medium),
        "low":         len(low),
        "tech_debt":   debts,
        "generated_at": datetime.now().isoformat(),
    }


@router.post("/api/decision")
async def api_save_decision(request: Request, session: dict = Depends(require_owner)):
    """
    POST /ai/api/decision — Save an engineering decision to persistent memory.
    Body: { "title": str, "rationale": str, "files_affected": list[str] }
    """
    body          = await request.json()
    title         = str(body.get("title", "")).strip()
    rationale     = str(body.get("rationale", "")).strip()
    files_affected = body.get("files_affected", [])
    if not title or not rationale:
        return JSONResponse({"ok": False, "error": "title and rationale are required"}, status_code=400)
    result = save_engineering_decision(title, rationale, files_affected)
    return result


@router.get("/api/decisions")
async def api_list_decisions(session: dict = Depends(require_owner)):
    """
    GET /ai/api/decisions — List all saved engineering decisions from memory.
    """
    decisions = list_engineering_decisions()
    return {
        "ok":        True,
        "total":     len(decisions),
        "decisions": decisions,
    }
