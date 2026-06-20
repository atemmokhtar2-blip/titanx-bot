import os
import ast
import zipfile
import shutil
import subprocess
import sys
import importlib.metadata as _meta
from datetime import datetime
from fastapi import APIRouter, Request, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from ..auth import require_owner
from ..config import CONTROL_PANEL_DIR, PROJECT_ROOT, TEMP_DIR, BACKUPS_DIR, EXTRACTED_DIR, PROTECTED_NAMES

router = APIRouter(prefix="/updates")
templates = Jinja2Templates(directory=os.path.join(CONTROL_PANEL_DIR, "templates"))

_update_status = {"running": False, "step": "", "log": [], "done": False, "success": False}
SKIP_DIRS = {".git", "__pycache__", "temp", "backups", ".venv", "node_modules"}

# ── Deployment Tools ──────────────────────────────────────────────────────────

EXPORTS_DIR = os.path.join(EXTRACTED_DIR, "exports")
os.makedirs(EXPORTS_DIR, exist_ok=True)

_ZIP_EXCLUDE_DIRS = {
    "__pycache__", ".git", "node_modules", ".pythonlibs",
    "temp", "logs", "backups", "exports", ".local",
    ".venv", "venv", ".cache", "dist", "build",
}
_ZIP_EXCLUDE_EXTS = {".pyc", ".pyo", ".log", ".egg-info"}
_BASE_ZIP_NAME = "PrimeDownloader"

# Import name → pip package name (curated from actual project imports)
_IMPORT_TO_PIP = {
    "telegram":          "python-telegram-bot==21.6",
    "fastapi":           "fastapi",
    "uvicorn":           "uvicorn[standard]",
    "starlette":         "starlette",
    "pydantic":          "pydantic",
    "pydantic_core":     "pydantic-core",
    "jinja2":            "Jinja2",
    "aiohttp":           "aiohttp",
    "aiofiles":          "aiofiles",
    "aiosqlite":         "aiosqlite",
    "cachetools":        "cachetools",
    "dotenv":            "python-dotenv",
    "PIL":               "Pillow",
    "psutil":            "psutil",
    "git":               "gitpython",
    "httpx":             "httpx",
    "yt_dlp":            "yt-dlp",
    "itsdangerous":      "itsdangerous",
    "multipart":         "python-multipart",
    "requests":          "requests",
    "yaml":              "PyYAML",
    "bs4":               "beautifulsoup4",
    "lxml":              "lxml",
    "numpy":             "numpy",
    "pandas":            "pandas",
    "cryptography":      "cryptography",
    "chardet":           "chardet",
    "typing_extensions": "typing-extensions",
    "annotated_types":   "annotated-types",
}

_STDLIB: set = getattr(sys, "stdlib_module_names", set()) | {
    "os", "sys", "re", "io", "json", "time", "math", "enum", "abc",
    "ast", "copy", "csv", "glob", "hmac", "html", "http", "logging",
    "pathlib", "pickle", "queue", "random", "shutil", "signal",
    "socket", "sqlite3", "string", "struct", "subprocess", "tempfile",
    "threading", "traceback", "typing", "unittest", "urllib", "uuid",
    "warnings", "weakref", "zipfile", "zlib", "base64", "binascii",
    "builtins", "calendar", "codecs", "collections", "contextlib",
    "datetime", "decimal", "difflib", "email", "functools",
    "gc", "getpass", "gettext", "gzip", "hashlib", "inspect",
    "itertools", "keyword", "locale", "mimetypes", "numbers",
    "operator", "pprint", "secrets", "select", "stat", "textwrap",
    "types", "unicodedata", "xml", "__future__", "dataclasses",
    "asyncio", "concurrent", "importlib", "importlib.metadata",
    "control_panel", "config", "handlers", "utils", "database",
    "services", "workers", "middlewares",
}


def _fmt_size(b: int) -> str:
    if b < 1024:       return f"{b} B"
    elif b < 1024**2:  return f"{b/1024:.1f} KB"
    elif b < 1024**3:  return f"{b/1024**2:.1f} MB"
    return f"{b/1024**3:.2f} GB"


def _versioned_export_name() -> str:
    base = os.path.join(EXPORTS_DIR, f"{_BASE_ZIP_NAME}.zip")
    if not os.path.exists(base):
        return f"{_BASE_ZIP_NAME}.zip"
    v = 2
    while True:
        name = f"{_BASE_ZIP_NAME}_v{v}.zip"
        if not os.path.exists(os.path.join(EXPORTS_DIR, name)):
            return name
        v += 1


def _build_export_zip() -> dict:
    fname = _versioned_export_name()
    fpath = os.path.join(EXPORTS_DIR, fname)
    included, excluded = [], []
    with zipfile.ZipFile(fpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(EXTRACTED_DIR):
            dirs[:] = [d for d in dirs if d not in _ZIP_EXCLUDE_DIRS]
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                fp  = os.path.join(root, fn)
                arc = os.path.relpath(fp, EXTRACTED_DIR)
                if ext in _ZIP_EXCLUDE_EXTS:
                    excluded.append(arc)
                    continue
                try:
                    zf.write(fp, arc)
                    included.append(arc)
                except (OSError, PermissionError):
                    excluded.append(arc)
    size = os.path.getsize(fpath)
    return {
        "ok": True, "name": fname,
        "size": size, "size_h": _fmt_size(size),
        "included": len(included), "excluded": len(excluded),
    }


def _list_exports() -> list:
    result = []
    for f in sorted(os.listdir(EXPORTS_DIR), reverse=True):
        if not f.endswith(".zip"):
            continue
        fpath = os.path.join(EXPORTS_DIR, f)
        try:
            stat = os.stat(fpath)
            result.append({
                "name":   f,
                "size_h": _fmt_size(stat.st_size),
                "mtime":  datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
        except Exception:
            pass
    return result


def _collect_imports(root_dir: str) -> dict:
    """Walk all .py files; return {import_name: [source_files]}."""
    found: dict = {}
    for dirpath, dirnames, files in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in _ZIP_EXCLUDE_DIRS]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            fp  = os.path.join(dirpath, fn)
            rel = os.path.relpath(fp, root_dir)
            try:
                src  = open(fp, encoding="utf-8", errors="ignore").read()
                tree = ast.parse(src, filename=fp)
            except Exception:
                continue
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        names = [node.module.split(".")[0]]
                for name in names:
                    if name not in found:
                        found[name] = []
                    if rel not in found[name]:
                        found[name].append(rel)
    return found


def _generate_requirements(root_dir: str) -> dict:
    all_imports = _collect_imports(root_dir)
    detected, unmapped = [], []

    for imp_name in sorted(all_imports):
        sources = all_imports[imp_name]
        if imp_name in _STDLIB:
            continue
        pip_name = _IMPORT_TO_PIP.get(imp_name)
        if not pip_name:
            unmapped.append({"import": imp_name, "sources": sources[:3]})
            continue
        base_pkg = pip_name.split("[")[0].split("==")[0].strip()
        version  = None
        try:
            version = _meta.version(base_pkg)
        except Exception:
            pass
        detected.append({
            "import_name": imp_name,
            "pip_name":    pip_name,
            "version":     version,
            "sources":     sources[:4],
        })

    lines, seen = [], set()
    for pkg in detected:
        base = pkg["pip_name"].split("[")[0].split("==")[0].strip()
        if base in seen:
            continue
        seen.add(base)
        if "==" in pkg["pip_name"]:
            lines.append(pkg["pip_name"])
        elif pkg["version"]:
            lines.append(f"{pkg['pip_name'].split('[')[0].split('==')[0]}>={pkg['version']}")
        else:
            lines.append(pkg["pip_name"])

    lines.sort(key=str.lower)
    content  = "\n".join(lines) + "\n"
    out_path = os.path.join(TEMP_DIR, "requirements_generated.txt")
    with open(out_path, "w") as f:
        f.write(content)

    return {
        "ok": True,
        "detected":       detected,
        "unmapped":       unmapped,
        "total_packages": len(detected),
        "requirements":   content,
    }


def _analyze_zip(zip_path: str) -> dict:
    result = {"files": [], "protected": [], "new": [], "modified": [], "total": 0, "deps_changed": False}
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        result["total"] = len(names)
        for name in names:
            if name.endswith("/"):
                continue
            basename = os.path.basename(name)
            dest = os.path.join(PROJECT_ROOT, name)
            if basename in PROTECTED_NAMES:
                result["protected"].append(name)
                continue
            if "requirements" in name.lower():
                result["deps_changed"] = True
            result["files"].append(name)
            if os.path.exists(dest):
                result["modified"].append(name)
            else:
                result["new"].append(name)
    return result


def _create_backup(label: str) -> str:
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{label}_{ts}"
    path = os.path.join(BACKUPS_DIR, f"{name}.zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, files in os.walk(PROJECT_ROOT):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in files:
                fp = os.path.join(dirpath, fn)
                try:
                    zf.write(fp, os.path.relpath(fp, PROJECT_ROOT))
                except (OSError, PermissionError):
                    pass
    return name


async def _apply_zip_bg(zip_path: str, analysis: dict, version: str):
    global _update_status
    _update_status = {"running": True, "step": "backup", "log": [], "done": False, "success": False}

    def log(msg):
        _update_status["log"].append(msg)

    try:
        log("⏳ جارٍ إنشاء نسخة احتياطية…")
        backup_name = _create_backup("pre_update")
        log(f"✅ نسخة احتياطية: {backup_name}")

        _update_status["step"] = "apply"
        log("📦 جارٍ تطبيق الملفات…")
        applied = 0
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in analysis["files"]:
                dest = os.path.join(PROJECT_ROOT, name)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with zf.open(name) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                applied += 1
        log(f"✅ طُبِّق {applied} ملف")

        if analysis.get("deps_changed"):
            _update_status["step"] = "deps"
            log("📦 جارٍ تثبيت التبعيات…")
            req = os.path.join(PROJECT_ROOT, "extracted_project", "requirements.txt")
            if os.path.exists(req):
                r = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", req, "-q"],
                    capture_output=True, text=True, timeout=120)
                log("✅ تم تثبيت التبعيات" if r.returncode == 0 else f"⚠️ {r.stderr[:200]}")

        _update_status["step"] = "done"
        log("🎉 اكتمل التحديث بنجاح!")
        _update_status["success"] = True
    except Exception as e:
        log(f"❌ فشل: {e}")
        _update_status["success"] = False
    finally:
        _update_status["running"] = False
        _update_status["done"] = True
        try:
            os.remove(zip_path)
        except Exception:
            pass


@router.get("", response_class=HTMLResponse)
async def updates_page(request: Request, session: dict = Depends(require_owner)):
    return templates.TemplateResponse(request, "updates.html", {
        "history": [], "backups": [],
        "status": _update_status, "active_page": "updates"
    })


@router.post("/api/analyze")
async def api_analyze(file: UploadFile = File(...), session: dict = Depends(require_owner)):
    if not file.filename.endswith(".zip"):
        return JSONResponse({"error": "يجب أن يكون الملف ZIP"}, status_code=400)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(TEMP_DIR, f"upload_{ts}.zip")
    content  = await file.read()
    with open(zip_path, "wb") as f:
        f.write(content)
    try:
        analysis = _analyze_zip(zip_path)
        analysis["zip_path"] = zip_path
        return analysis
    except Exception as e:
        os.remove(zip_path)
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/apply")
async def api_apply(request: Request, background_tasks: BackgroundTasks,
                    session: dict = Depends(require_owner)):
    if _update_status.get("running"):
        return JSONResponse({"error": "تحديث جارٍ بالفعل"}, status_code=400)
    body     = await request.json()
    zip_path = body.get("zip_path", "")
    version  = body.get("version", datetime.now().strftime("%Y%m%d"))
    if not zip_path or not os.path.exists(zip_path):
        return JSONResponse({"error": "لم يتم رفع ملف"}, status_code=400)
    analysis = _analyze_zip(zip_path)
    background_tasks.add_task(_apply_zip_bg, zip_path, analysis, version)
    return {"ok": True, "total": len(analysis["files"])}


@router.get("/api/status")
async def api_status(session: dict = Depends(require_owner)):
    return _update_status


@router.post("/api/backup")
async def api_backup(session: dict = Depends(require_owner)):
    try:
        name = _create_backup("manual")
        return {"ok": True, "name": name}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/restore")
async def api_restore(request: Request, background_tasks: BackgroundTasks,
                      session: dict = Depends(require_owner)):
    body     = await request.json()
    zip_name = body.get("name", "")
    bpath    = os.path.join(BACKUPS_DIR, zip_name if zip_name.endswith(".zip") else zip_name + ".zip")
    if not os.path.exists(bpath):
        return JSONResponse({"error": "ملف النسخة غير موجود"}, status_code=404)
    analysis = {"files": [], "deps_changed": False}
    with zipfile.ZipFile(bpath, "r") as zf:
        for name in zf.namelist():
            if not name.endswith("/") and os.path.basename(name) not in PROTECTED_NAMES:
                analysis["files"].append(name)
    background_tasks.add_task(_apply_zip_bg, bpath, analysis, f"restore_{zip_name}")
    return {"ok": True}


# ── Feature 3: Hugging Face Readiness Check ───────────────────────────────────

def _hf_readiness_check() -> dict:
    checks = []
    score_pass = 0
    score_total = 0

    def _add(name: str, status: str, message: str, critical: bool = False):
        nonlocal score_pass, score_total
        weight = 2 if critical else 1
        score_total += weight
        if status == "ok":
            score_pass += weight
        elif status == "warning":
            score_pass += weight // 2
        checks.append({"name": name, "status": status, "message": message, "critical": critical})

    # ── 1. requirements.txt ───────────────────────────────────────────────────
    req_path = os.path.join(EXTRACTED_DIR, "requirements.txt")
    if os.path.exists(req_path):
        lines = [l.strip() for l in open(req_path) if l.strip() and not l.startswith("#")]
        _add("requirements.txt", "ok", f"موجود — {len(lines)} حزمة مدرجة", critical=True)
    else:
        _add("requirements.txt", "critical", "مفقود — مطلوب للنشر على HF", critical=True)

    # ── 2. Dockerfile ─────────────────────────────────────────────────────────
    df_path = os.path.join(EXTRACTED_DIR, "Dockerfile")
    if os.path.exists(df_path):
        content = open(df_path).read()
        missing = []
        if "FROM" not in content:      missing.append("FROM")
        if "EXPOSE" not in content:    missing.append("EXPOSE")
        if "CMD" not in content and "ENTRYPOINT" not in content: missing.append("CMD/ENTRYPOINT")
        if missing:
            _add("Dockerfile", "warning", f"موجود لكن ناقص: {', '.join(missing)}", critical=True)
        else:
            _add("Dockerfile", "ok", "موجود ✅ (FROM + EXPOSE + CMD)", critical=True)
    else:
        _add("Dockerfile", "critical", "مفقود — مطلوب للنشر على HF", critical=True)

    # ── 3. Entrypoint file ────────────────────────────────────────────────────
    server_path = os.path.join(EXTRACTED_DIR, "control_panel", "server.py")
    if os.path.exists(server_path):
        _add("نقطة الدخول", "ok", "control_panel/server.py موجود ✅", critical=True)
    else:
        _add("نقطة الدخول", "critical", "control_panel/server.py مفقود!", critical=True)

    # ── 4. Host binding ───────────────────────────────────────────────────────
    if os.path.exists(server_path):
        if "0.0.0.0" in open(server_path).read():
            _add("ربط المضيف (Host)", "ok", "الخادم مرتبط بـ 0.0.0.0 ✅")
        else:
            _add("ربط المضيف (Host)", "warning", "تحقق من host='0.0.0.0' في server.py")

    # ── 5. Port configuration ─────────────────────────────────────────────────
    if os.path.exists(df_path):
        if "7860" in open(df_path).read():
            _add("Port (7860)", "ok", "Dockerfile يكشف المنفذ 7860 (متطلب HF) ✅")
        else:
            _add("Port (7860)", "warning", "Dockerfile لا يذكر 7860 — قد يكون مشكلة على HF Spaces")
    else:
        _add("Port (7860)", "warning", "لا يمكن التحقق — Dockerfile مفقود")

    # ── 6. Python version ─────────────────────────────────────────────────────
    ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        _add("Python Version", "ok", f"Python {ver} — متوافق مع HF Spaces ✅")
    else:
        _add("Python Version", "warning", f"Python {ver} — يُفضَّل 3.10+")

    # ── 7. Templates directory ────────────────────────────────────────────────
    tpl_dir = os.path.join(EXTRACTED_DIR, "control_panel", "templates")
    if os.path.isdir(tpl_dir):
        count = len([f for f in os.listdir(tpl_dir) if f.endswith(".html")])
        _add("القوالب (Templates)", "ok", f"{count} ملف HTML في control_panel/templates/ ✅")
    else:
        _add("القوالب (Templates)", "critical", "مجلد templates مفقود!")

    # ── 8. Static assets ──────────────────────────────────────────────────────
    static_dir = os.path.join(EXTRACTED_DIR, "control_panel", "static")
    if os.path.isdir(static_dir):
        count = sum(len(files) for _, _, files in os.walk(static_dir))
        _add("الملفات الثابتة (Static)", "ok", f"{count} ملف في control_panel/static/ ✅")
    else:
        _add("الملفات الثابتة (Static)", "warning", "مجلد static مفقود أو فارغ")

    # ── 9. Required env vars ──────────────────────────────────────────────────
    required = ["TELEGRAM_BOT_TOKEN", "SUPPORT_BOT_TOKEN", "OWNER_ID"]
    missing_env = [k for k in required if not os.getenv(k)]
    if not missing_env:
        _add("المتغيرات البيئية", "ok", "الأسرار الأساسية مضبوطة في البيئة الحالية ✅")
    else:
        _add("المتغيرات البيئية", "warning",
             f"يجب إضافتها في HF Space Secrets: {', '.join(missing_env)}")

    # ── 10. SQLite persistence warning ───────────────────────────────────────
    _add("قاعدة البيانات (SQLite)", "warning",
         "البيانات مؤقتة على HF free tier — تُفقد عند إعادة تشغيل Space")

    pct = round(100 * score_pass / score_total) if score_total else 0
    grade = "ممتاز 🟢" if pct >= 85 else ("جيد 🟡" if pct >= 60 else "يحتاج إصلاح 🔴")
    return {
        "ok": True,
        "checks":         checks,
        "score":          pct,
        "grade":          grade,
        "ok_count":       sum(1 for c in checks if c["status"] == "ok"),
        "warning_count":  sum(1 for c in checks if c["status"] == "warning"),
        "critical_count": sum(1 for c in checks if c["status"] == "critical"),
    }


@router.post("/api/hf-readiness")
async def api_hf_readiness(session: dict = Depends(require_owner)):
    try:
        return _hf_readiness_check()
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ── Feature 1 / Feature 4: Deployment ZIP Export ──────────────────────────────

@router.post("/api/export/generate")
async def api_export_generate(session: dict = Depends(require_owner)):
    try:
        result = _build_export_zip()
        return result
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/export/list")
async def api_export_list(session: dict = Depends(require_owner)):
    return _list_exports()


@router.get("/api/export/download/{name}")
async def api_export_download(name: str, session: dict = Depends(require_owner)):
    if ".." in name or "/" in name:
        return JSONResponse({"ok": False, "error": "اسم غير صالح"}, status_code=400)
    fpath = os.path.join(EXPORTS_DIR, name)
    if not os.path.exists(fpath):
        return JSONResponse({"ok": False, "error": "الملف غير موجود"}, status_code=404)
    return FileResponse(fpath, media_type="application/zip", filename=name)


# ── Feature 2: Requirements Generator ─────────────────────────────────────────

@router.post("/api/requirements/generate")
async def api_requirements_generate(session: dict = Depends(require_owner)):
    try:
        result = _generate_requirements(EXTRACTED_DIR)
        return result
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/requirements/download")
async def api_requirements_download(session: dict = Depends(require_owner)):
    fpath = os.path.join(TEMP_DIR, "requirements_generated.txt")
    if not os.path.exists(fpath):
        return JSONResponse({"ok": False, "error": "لم يتم إنشاء الملف بعد، اضغط توليد أولاً"}, status_code=404)
    return FileResponse(fpath, media_type="text/plain", filename="requirements.txt")
