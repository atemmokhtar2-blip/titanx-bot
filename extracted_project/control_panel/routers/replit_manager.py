import os
import time
import subprocess
import psutil
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from ..auth import require_owner
from ..config import CONTROL_PANEL_DIR, PROJECT_ROOT

router = APIRouter(prefix="/replit")
templates = Jinja2Templates(directory=os.path.join(CONTROL_PANEL_DIR, "templates"))

_START_TIME = time.time()


def _fmt_bytes(b: int) -> str:
    if b < 1024:       return f"{b} B"
    elif b < 1024**2:  return f"{b/1024:.1f} KB"
    elif b < 1024**3:  return f"{b/1024**2:.1f} MB"
    return f"{b/1024**3:.2f} GB"


def _get_health() -> dict:
    cpu = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(PROJECT_ROOT)
    uptime_sec = int(time.time() - psutil.boot_time())
    panel_uptime = int(time.time() - _START_TIME)
    return {
        "status": "online",
        "cpu_percent": cpu,
        "mem_percent": mem.percent,
        "mem_used_h": _fmt_bytes(mem.used),
        "mem_total_h": _fmt_bytes(mem.total),
        "disk_percent": disk.percent,
        "disk_used_h": _fmt_bytes(disk.used),
        "disk_total_h": _fmt_bytes(disk.total),
        "system_uptime": f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m",
        "panel_uptime": f"{panel_uptime // 3600}h {(panel_uptime % 3600) // 60}m",
        "ts": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    }


def _get_python_processes() -> list:
    procs = []
    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline", "status", "memory_percent", "create_time"]):
            try:
                name = proc.info.get("name", "")
                cmdline = " ".join(proc.info.get("cmdline") or [])
                if "python" in name.lower() or "uvicorn" in cmdline:
                    ct = proc.info.get("create_time", 0)
                    age = int(time.time() - ct) if ct else 0
                    procs.append({
                        "pid": proc.info["pid"],
                        "name": name,
                        "cmdline": cmdline[:90],
                        "status": proc.info.get("status", ""),
                        "mem": round(proc.info.get("memory_percent") or 0, 1),
                        "age": f"{age // 60}m {age % 60}s",
                    })
            except Exception:
                pass
    except Exception:
        pass
    return procs[:15]


def _check_routes() -> list:
    routes = [
        ("/healthz",   "GET",  "فحص الصحة"),
        ("/",          "GET",  "لوحة التحكم"),
        ("/panel",     "GET",  "صفحة الدخول"),
        ("/system",    "GET",  "حالة النظام"),
        ("/bots",      "GET",  "البوتات"),
        ("/users",     "GET",  "المستخدمون"),
        ("/backups",   "GET",  "النسخ الاحتياطية"),
        ("/github",    "GET",  "GitHub"),
        ("/files",     "GET",  "مدير الملفات"),
        ("/logs",      "GET",  "السجلات"),
        ("/replit",    "GET",  "مركز Replit"),
        ("/broadcast", "GET",  "البث الجماعي"),
    ]
    return [{"path": r[0], "method": r[1], "label": r[2]} for r in routes]


@router.get("", response_class=HTMLResponse)
async def replit_page(request: Request, session: dict = Depends(require_owner)):
    health = _get_health()
    procs  = _get_python_processes()
    routes = _check_routes()
    return templates.TemplateResponse(request, "replit_manager.html", {
        "health": health, "procs": procs, "routes": routes,
        "active_page": "replit",
    })


@router.get("/api/health")
async def api_health(session: dict = Depends(require_owner)):
    return _get_health()


@router.get("/api/processes")
async def api_processes(session: dict = Depends(require_owner)):
    return _get_python_processes()


@router.get("/api/routes")
async def api_routes(session: dict = Depends(require_owner)):
    return _check_routes()


@router.post("/api/check-panel")
async def api_check_panel(session: dict = Depends(require_owner)):
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get("http://localhost:5000/healthz")
            if r.status_code == 200:
                return {"ok": True, "msg": "لوحة التحكم تعمل بشكل طبيعي ✅", "status": r.status_code}
            return {"ok": False, "msg": f"استجابة غير متوقعة: {r.status_code}"}
    except Exception as e:
        return {"ok": False, "msg": f"خطأ: {str(e)[:80]}"}


@router.post("/api/check-routes")
async def api_check_routes_live(session: dict = Depends(require_owner)):
    import httpx
    results = []
    routes_to_check = ["/healthz", "/panel", "/system/api/stats"]
    async with httpx.AsyncClient(timeout=5) as client:
        for path in routes_to_check:
            try:
                r = await client.get(f"http://localhost:5000{path}")
                results.append({"path": path, "status": r.status_code, "ok": r.status_code < 400})
            except Exception as e:
                results.append({"path": path, "status": 0, "ok": False, "error": str(e)[:50]})
    all_ok = all(r["ok"] for r in results)
    return {"ok": all_ok, "results": results}
