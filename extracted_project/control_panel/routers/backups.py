import os
import zipfile
import datetime
import shutil
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from ..auth import require_owner
from ..config import CONTROL_PANEL_DIR, BACKUPS_DIR, EXTRACTED_DIR
from .. import activity_log

router = APIRouter(prefix="/backups")
templates = Jinja2Templates(directory=os.path.join(CONTROL_PANEL_DIR, "templates"))

_SKIP_DIRS = {"__pycache__", ".git", "temp", "backups", ".pythonlibs", "venv",
              ".venv", "node_modules", ".local", "artifacts"}
_SKIP_EXTS = {".pyc", ".pyo", ".pyd"}

# Backup categories: manual | daily | weekly
_STRATEGY_PREFIXES = {"daily": "daily_", "weekly": "weekly_", "manual": "backup_", "ai": "backup_"}


def _human_size(size: int) -> str:
    if size < 1024:         return f"{size} B"
    if size < 1_048_576:   return f"{size / 1024:.1f} KB"
    return f"{size / 1_048_576:.1f} MB"


def _verify_zip(path: str) -> dict:
    """Verify ZIP integrity and return report."""
    try:
        if not os.path.exists(path):
            return {"ok": False, "error": "الملف غير موجود", "file_count": 0}
        size = os.path.getsize(path)
        if size == 0:
            return {"ok": False, "error": "الملف فارغ", "file_count": 0}
        with zipfile.ZipFile(path, "r") as zf:
            bad = zf.testzip()
            if bad:
                return {"ok": False, "error": f"ملف تالف: {bad}", "file_count": 0}
            names = zf.namelist()
            file_count = len(names)
        if file_count == 0:
            return {"ok": False, "error": "الأرشيف فارغ", "file_count": 0}
        return {
            "ok": True,
            "file_count": file_count,
            "size": _human_size(size),
            "size_bytes": size,
        }
    except zipfile.BadZipFile:
        return {"ok": False, "error": "ملف ZIP تالف", "file_count": 0}
    except Exception as e:
        return {"ok": False, "error": str(e), "file_count": 0}


def _categorize(name: str) -> str:
    if name.startswith("daily_"):  return "daily"
    if name.startswith("weekly_"): return "weekly"
    if name.startswith("backup_") and "_ai" in name: return "ai"
    return "manual"


def _list_backups() -> list:
    if not os.path.exists(BACKUPS_DIR):
        return []
    items = []
    for name in sorted(os.listdir(BACKUPS_DIR), reverse=True):
        if not name.endswith(".zip"):
            continue
        path = os.path.join(BACKUPS_DIR, name)
        try:
            stat = os.stat(path)
            items.append({
                "name": name,
                "size": _human_size(stat.st_size),
                "size_bytes": stat.st_size,
                "created": datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
                "category": _categorize(name),
            })
        except Exception:
            pass
    return items


def _do_create(label: str = "", strategy: str = "manual") -> dict:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "daily_" if strategy == "daily" else "weekly_" if strategy == "weekly" else "backup_"
    suffix = f"_{label}" if label else ""
    name = f"{prefix}{ts}{suffix}.zip"
    dest = os.path.join(BACKUPS_DIR, name)
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(EXTRACTED_DIR):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in _SKIP_EXTS:
                    continue
                fpath = os.path.join(root, file)
                arcname = os.path.relpath(fpath, os.path.dirname(EXTRACTED_DIR))
                try:
                    zf.write(fpath, arcname)
                except Exception:
                    pass
    # Verify
    verification = _verify_zip(dest)
    if not verification["ok"]:
        os.remove(dest)
        raise Exception(f"فشل التحقق: {verification['error']}")
    size = _human_size(os.path.getsize(dest))
    return {
        "name": name,
        "size": size,
        "file_count": verification["file_count"],
        "verification": verification,
    }


@router.get("", response_class=HTMLResponse)
async def backups_page(request: Request, session: dict = Depends(require_owner)):
    backups = _list_backups()
    return templates.TemplateResponse(request, "backups.html", {
        "backups": backups, "active_page": "backups"
    })


@router.get("/api/list")
async def api_list(session: dict = Depends(require_owner)):
    return {"backups": _list_backups()}


@router.post("/api/create")
async def api_create(request: Request, session: dict = Depends(require_owner)):
    try:
        body = await request.json()
    except Exception:
        body = {}
    label = str(body.get("label", "")).strip()
    label = "".join(c for c in label if c.isalnum() or c in "_-")[:30]
    strategy = str(body.get("strategy", "manual"))
    try:
        result = _do_create(label, strategy)
        activity_log.log("backup_created",
                         f"نسخة احتياطية: {result['name']}",
                         f"الحجم: {result['size']} · الملفات: {result['file_count']}")
        return {"ok": True, **result}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/verify/{name:path}")
async def api_verify(name: str, session: dict = Depends(require_owner)):
    safe = os.path.basename(name)
    path = os.path.join(BACKUPS_DIR, safe)
    result = _verify_zip(path)
    return result


@router.get("/api/download/{name:path}")
async def api_download(name: str, session: dict = Depends(require_owner)):
    safe_name = os.path.basename(name)
    path = os.path.join(BACKUPS_DIR, safe_name)
    if not os.path.exists(path) or not safe_name.endswith(".zip"):
        return JSONResponse({"error": "الملف غير موجود"}, status_code=404)
    return FileResponse(path, filename=safe_name, media_type="application/zip")


@router.delete("/api/delete/{name:path}")
async def api_delete(name: str, session: dict = Depends(require_owner)):
    safe_name = os.path.basename(name)
    path = os.path.join(BACKUPS_DIR, safe_name)
    if not os.path.exists(path):
        return JSONResponse({"error": "الملف غير موجود"}, status_code=404)
    try:
        os.remove(path)
        activity_log.log("info", f"حُذفت النسخة الاحتياطية: {safe_name}")
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
