import os
import time
import zipfile
import shutil
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from ..auth import require_owner
from ..config import CONTROL_PANEL_DIR, EXTRACTED_DIR, BACKUPS_DIR

router = APIRouter(prefix="/backups")
templates = Jinja2Templates(directory=os.path.join(CONTROL_PANEL_DIR, "templates"))

EXCLUDE_DIRS  = {"__pycache__", ".git", "node_modules", ".pythonlibs", "temp", ".local"}
EXCLUDE_FILES = {".pyc"}


def _make_backup(label: str = "") -> dict:
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    ts  = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tag = f"_{label}" if label else ""
    fname = f"backup{tag}_{ts}.zip"
    fpath = os.path.join(BACKUPS_DIR, fname)
    try:
        count = 0
        with zipfile.ZipFile(fpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for root, dirs, files in os.walk(EXTRACTED_DIR):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for f in files:
                    if any(f.endswith(ext) for ext in EXCLUDE_FILES):
                        continue
                    fp = os.path.join(root, f)
                    arc = os.path.relpath(fp, EXTRACTED_DIR)
                    try:
                        zf.write(fp, arc)
                        count += 1
                    except Exception:
                        pass
        size = os.path.getsize(fpath)
        return {"ok": True, "name": fname, "size": size, "files": count}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _list_backups() -> list:
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    result = []
    for f in sorted(os.listdir(BACKUPS_DIR), reverse=True):
        if not f.endswith(".zip"):
            continue
        fpath = os.path.join(BACKUPS_DIR, f)
        try:
            stat = os.stat(fpath)
            result.append({
                "name": f,
                "size": stat.st_size,
                "size_h": _fmt(stat.st_size),
                "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "mtime_ts": int(stat.st_mtime),
            })
        except Exception:
            pass
    return result


def _verify_backup(name: str) -> dict:
    fpath = os.path.join(BACKUPS_DIR, name)
    if not os.path.exists(fpath):
        return {"ok": False, "error": "الملف غير موجود"}
    try:
        with zipfile.ZipFile(fpath, "r") as zf:
            bad = zf.testzip()
            count = len(zf.namelist())
        if bad:
            return {"ok": False, "error": f"ملف تالف: {bad}", "files": count}
        return {"ok": True, "files": count, "msg": f"سليم — {count} ملف"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _fmt(b: int) -> str:
    if b < 1024:       return f"{b} B"
    elif b < 1024**2:  return f"{b/1024:.1f} KB"
    elif b < 1024**3:  return f"{b/1024**2:.1f} MB"
    return f"{b/1024**3:.2f} GB"


@router.get("", response_class=HTMLResponse)
async def backups_page(request: Request, session: dict = Depends(require_owner)):
    backups = _list_backups()
    return templates.TemplateResponse(request, "backups.html", {
        "backups": backups, "active_page": "backups"
    })


@router.get("/api/list")
async def api_list(session: dict = Depends(require_owner)):
    return _list_backups()


@router.post("/api/create")
async def api_create(request: Request, session: dict = Depends(require_owner)):
    body = {}
    try: body = await request.json()
    except Exception: pass
    label = body.get("label", "").strip()[:30]
    result = _make_backup(label)
    return result


@router.get("/api/verify/{name}")
async def api_verify(name: str, session: dict = Depends(require_owner)):
    if ".." in name or "/" in name:
        return JSONResponse({"ok": False, "error": "اسم غير صالح"}, status_code=400)
    return _verify_backup(name)


@router.get("/api/download/{name}")
async def api_download(name: str, session: dict = Depends(require_owner)):
    if ".." in name or "/" in name:
        return JSONResponse({"ok": False, "error": "اسم غير صالح"}, status_code=400)
    fpath = os.path.join(BACKUPS_DIR, name)
    if not os.path.exists(fpath):
        return JSONResponse({"ok": False, "error": "غير موجود"}, status_code=404)
    return FileResponse(fpath, media_type="application/zip", filename=name)


@router.delete("/api/delete/{name}")
async def api_delete(name: str, session: dict = Depends(require_owner)):
    if ".." in name or "/" in name:
        return JSONResponse({"ok": False, "error": "اسم غير صالح"}, status_code=400)
    fpath = os.path.join(BACKUPS_DIR, name)
    if not os.path.exists(fpath):
        return JSONResponse({"ok": False, "error": "غير موجود"}, status_code=404)
    try:
        os.remove(fpath)
        return {"ok": True, "msg": "تم الحذف"}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
