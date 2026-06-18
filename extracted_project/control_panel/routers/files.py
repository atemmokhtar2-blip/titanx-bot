import os
import shutil
import mimetypes
import difflib
import zipfile
import io
import base64
from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, Response
from fastapi.templating import Jinja2Templates
from ..auth import require_owner
from ..config import CONTROL_PANEL_DIR, PROJECT_ROOT, PROTECTED_NAMES, PROTECTED_DIRS, MAX_VIEW_BYTES, MAX_EDIT_BYTES

router = APIRouter(prefix="/files")
templates = Jinja2Templates(directory=os.path.join(CONTROL_PANEL_DIR, "templates"))

_ROOT = PROJECT_ROOT

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp"}
_TEXT_EXTS = {".py", ".txt", ".md", ".json", ".yaml", ".yml", ".cfg", ".ini",
              ".log", ".sh", ".js", ".ts", ".html", ".css", ".env", ".toml",
              ".xml", ".csv", ".sql", ".gitignore", ".dockerfile"}


def _safe_resolve(rel: str) -> str:
    full = os.path.normpath(os.path.join(_ROOT, rel.lstrip("/")))
    if not full.startswith(_ROOT):
        raise ValueError("مسار غير مسموح")
    return full


def _is_protected(path: str) -> bool:
    name = os.path.basename(path)
    rel = os.path.relpath(path, _ROOT)
    parts = rel.replace("\\", "/").split("/")
    return name in PROTECTED_NAMES or any(p in PROTECTED_DIRS for p in parts)


def _is_text(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in _TEXT_EXTS


def _is_image(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in _IMAGE_EXTS


def _fmt_size(b: int) -> str:
    if b < 1024:       return f"{b} B"
    elif b < 1024**2:  return f"{b/1024:.1f} KB"
    elif b < 1024**3:  return f"{b/1024**2:.1f} MB"
    return f"{b/1024**3:.2f} GB"


def _list_dir(rel: str) -> dict:
    full = _safe_resolve(rel)
    if not os.path.isdir(full):
        raise ValueError("ليس مجلداً")
    items = []
    try:
        for name in sorted(os.listdir(full)):
            if name.startswith(".git") or name in {"__pycache__", ".cache"}:
                continue
            child = os.path.join(full, name)
            child_rel = os.path.relpath(child, _ROOT).replace("\\", "/")
            is_dir = os.path.isdir(child)
            size = 0
            mtime = ""
            try:
                st = os.stat(child)
                size = st.st_size if not is_dir else 0
                mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
            items.append({
                "name": name, "rel": child_rel, "is_dir": is_dir,
                "size": _fmt_size(size) if not is_dir else "",
                "mtime": mtime,
                "protected": _is_protected(child),
                "is_text": _is_text(child) if not is_dir else False,
                "is_image": _is_image(child) if not is_dir else False,
                "is_zip": child.endswith(".zip") if not is_dir else False,
            })
    except PermissionError:
        pass
    parts = rel.strip("/").split("/") if rel.strip("/") else []
    breadcrumbs = [{"name": "الجذر", "rel": ""}]
    for i, p in enumerate(parts):
        breadcrumbs.append({"name": p, "rel": "/".join(parts[:i+1])})
    return {"items": items, "rel": rel, "breadcrumbs": breadcrumbs}


@router.get("", response_class=HTMLResponse)
async def files_page(request: Request, path: str = "", session: dict = Depends(require_owner)):
    try:
        listing = _list_dir(path)
    except Exception as e:
        listing = {"items": [], "rel": "", "breadcrumbs": [], "error": str(e)}
    return templates.TemplateResponse(request, "files.html", {
        "listing": listing, "active_page": "files"
    })


@router.get("/api/list")
async def api_list(path: str = "", session: dict = Depends(require_owner)):
    try:
        return _list_dir(path)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.get("/api/read")
async def api_read(path: str, session: dict = Depends(require_owner)):
    try:
        full = _safe_resolve(path)
        if not os.path.isfile(full):
            return JSONResponse({"error": "ليس ملفاً"}, status_code=400)
        size = os.path.getsize(full)
        if size > MAX_VIEW_BYTES:
            return JSONResponse({"error": f"الملف كبير جداً ({_fmt_size(size)})"}, status_code=400)
        if not _is_text(full):
            return JSONResponse({"error": "الملف غير نصي"}, status_code=400)
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {"content": content, "path": path, "size": _fmt_size(size),
                "protected": _is_protected(full), "is_json": path.endswith(".json")}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.get("/api/preview_image")
async def api_preview_image(path: str, session: dict = Depends(require_owner)):
    """Return base64-encoded image for preview."""
    try:
        full = _safe_resolve(path)
        if not os.path.isfile(full) or not _is_image(full):
            return JSONResponse({"error": "ليس صورة"}, status_code=400)
        size = os.path.getsize(full)
        if size > 5 * 1024 * 1024:
            return JSONResponse({"error": "الصورة كبيرة جداً للمعاينة"}, status_code=400)
        with open(full, "rb") as f:
            data = f.read()
        ext = os.path.splitext(full)[1].lower().strip(".")
        mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif",
                    "webp": "webp", "svg": "svg+xml", "ico": "x-icon", "bmp": "bmp"}
        mime = "image/" + mime_map.get(ext, ext)
        b64 = base64.b64encode(data).decode()
        return {"data_url": f"data:{mime};base64,{b64}", "size": _fmt_size(size)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/save")
async def api_save(request: Request, session: dict = Depends(require_owner)):
    body = await request.json()
    path = body.get("path", "")
    new_content = body.get("content", "")
    try:
        full = _safe_resolve(path)
        if _is_protected(full):
            return JSONResponse({"error": "الملف محمي"}, status_code=403)
        if len(new_content.encode()) > MAX_EDIT_BYTES:
            return JSONResponse({"error": "المحتوى كبير جداً"}, status_code=400)
        if full.endswith(".py"):
            try:
                compile(new_content, full, "exec")
            except SyntaxError as e:
                return JSONResponse({"error": f"خطأ في الصياغة: {e}", "syntax_error": True}, status_code=422)
        old_content = ""
        if os.path.exists(full):
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                old_content = f.read()
        diff = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path}", tofile=f"b/{path}", n=3))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(new_content)
        return {"ok": True, "diff": "".join(diff[:200])}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/delete")
async def api_delete(request: Request, session: dict = Depends(require_owner)):
    body = await request.json()
    path = body.get("path", "")
    try:
        full = _safe_resolve(path)
        if _is_protected(full):
            return JSONResponse({"error": "محمي ولا يمكن حذفه"}, status_code=403)
        if os.path.isdir(full):
            shutil.rmtree(full)
        else:
            os.remove(full)
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/rename")
async def api_rename(request: Request, session: dict = Depends(require_owner)):
    body = await request.json()
    old = body.get("old", "")
    new_name = os.path.basename(body.get("new", ""))
    try:
        full_old = _safe_resolve(old)
        full_new = os.path.join(os.path.dirname(full_old), new_name)
        if _is_protected(full_old):
            return JSONResponse({"error": "محمي"}, status_code=403)
        os.rename(full_old, full_new)
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/copy")
async def api_copy(request: Request, session: dict = Depends(require_owner)):
    body = await request.json()
    src = body.get("src", "")
    dst_dir = body.get("dst_dir", "")
    try:
        full_src = _safe_resolve(src)
        full_dst_dir = _safe_resolve(dst_dir) if dst_dir else os.path.dirname(full_src)
        if not os.path.exists(full_src):
            return JSONResponse({"error": "المصدر غير موجود"}, status_code=400)
        base = os.path.basename(full_src)
        name, ext = os.path.splitext(base)
        dest = os.path.join(full_dst_dir, f"{name}_copy{ext}")
        if os.path.isdir(full_src):
            shutil.copytree(full_src, dest)
        else:
            shutil.copy2(full_src, dest)
        return {"ok": True, "dest": os.path.relpath(dest, _ROOT)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/move")
async def api_move(request: Request, session: dict = Depends(require_owner)):
    body = await request.json()
    src = body.get("src", "")
    dst_dir = body.get("dst_dir", "")
    try:
        full_src = _safe_resolve(src)
        full_dst_dir = _safe_resolve(dst_dir)
        if _is_protected(full_src):
            return JSONResponse({"error": "محمي"}, status_code=403)
        if not os.path.exists(full_src):
            return JSONResponse({"error": "المصدر غير موجود"}, status_code=400)
        dest = os.path.join(full_dst_dir, os.path.basename(full_src))
        shutil.move(full_src, dest)
        return {"ok": True, "dest": os.path.relpath(dest, _ROOT)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/compress")
async def api_compress(request: Request, session: dict = Depends(require_owner)):
    """Compress a file/directory to ZIP."""
    body = await request.json()
    path = body.get("path", "")
    try:
        full = _safe_resolve(path)
        if not os.path.exists(full):
            return JSONResponse({"error": "المسار غير موجود"}, status_code=400)
        zip_path = full + ".zip"
        if os.path.isdir(full):
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for dp, _, files in os.walk(full):
                    for fname in files:
                        fp = os.path.join(dp, fname)
                        zf.write(fp, os.path.relpath(fp, full))
        else:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(full, os.path.basename(full))
        return {"ok": True, "zip": os.path.relpath(zip_path, _ROOT),
                "size": _fmt_size(os.path.getsize(zip_path))}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/extract")
async def api_extract(request: Request, session: dict = Depends(require_owner)):
    """Extract a ZIP file."""
    body = await request.json()
    path = body.get("path", "")
    try:
        full = _safe_resolve(path)
        if not full.endswith(".zip") or not os.path.isfile(full):
            return JSONResponse({"error": "ليس ملف ZIP"}, status_code=400)
        out_dir = full[:-4]
        os.makedirs(out_dir, exist_ok=True)
        with zipfile.ZipFile(full, "r") as zf:
            zf.extractall(out_dir)
        return {"ok": True, "extracted_to": os.path.relpath(out_dir, _ROOT)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/mkdir")
async def api_mkdir(request: Request, session: dict = Depends(require_owner)):
    body = await request.json()
    path = body.get("path", "")
    try:
        full = _safe_resolve(path)
        os.makedirs(full, exist_ok=True)
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/upload")
async def api_upload(path: str = Form(""), file: UploadFile = File(...),
                     session: dict = Depends(require_owner)):
    try:
        full_dir = _safe_resolve(path)
        if not os.path.isdir(full_dir):
            return JSONResponse({"error": "المجلد غير موجود"}, status_code=400)
        dest = os.path.join(full_dir, file.filename)
        content = await file.read()
        with open(dest, "wb") as f:
            f.write(content)
        return {"ok": True, "name": file.filename, "size": _fmt_size(len(content))}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.get("/api/download")
async def api_download(path: str, session: dict = Depends(require_owner)):
    try:
        full = _safe_resolve(path)
        if not os.path.exists(full):
            return JSONResponse({"error": "غير موجود"}, status_code=404)
        if os.path.isdir(full):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for dp, _, files in os.walk(full):
                    for fname in files:
                        fp = os.path.join(dp, fname)
                        zf.write(fp, os.path.relpath(fp, full))
            buf.seek(0)
            name = os.path.basename(full) + ".zip"
            return StreamingResponse(buf, media_type="application/zip",
                                     headers={"Content-Disposition": f"attachment; filename={name}"})
        with open(full, "rb") as f:
            data = f.read()
        mime, _ = mimetypes.guess_type(full)
        name = os.path.basename(full)
        return Response(content=data, media_type=mime or "application/octet-stream",
                        headers={"Content-Disposition": f"attachment; filename={name}"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
