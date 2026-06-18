import os
import time
import signal
import subprocess
import psutil
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from ..auth import require_owner
from ..config import CONTROL_PANEL_DIR, BOT_SCRIPTS, LOGS_DIR

router = APIRouter(prefix="/bots")
templates = Jinja2Templates(directory=os.path.join(CONTROL_PANEL_DIR, "templates"))

PYTHONPATH = "/home/runner/workspace/.pythonlibs/lib/python3.12/site-packages"

BOT_META = {
    "main":    {"label": "البوت الرئيسي", "icon": "🤖", "color": "accent"},
    "support": {"label": "بوت الدعم",     "icon": "🎧", "color": "cyan"},
}


def _is_running(script_path: str):
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if script_path in cmdline:
                return True, proc.info["pid"]
        except Exception:
            pass
    return False, None


def _bot_status_all() -> list:
    result = []
    for key, meta in BOT_META.items():
        script = BOT_SCRIPTS.get(key, "")
        running, pid = _is_running(script)
        result.append({
            "key":     key,
            "label":   meta["label"],
            "icon":    meta["icon"],
            "color":   meta["color"],
            "script":  os.path.basename(script),
            "running": running,
            "pid":     pid,
        })
    return result


def _start_bot(key: str) -> dict:
    script = BOT_SCRIPTS.get(key)
    if not script:
        return {"ok": False, "msg": "بوت غير معروف"}
    running, _ = _is_running(script)
    if running:
        return {"ok": True, "msg": "البوت يعمل بالفعل"}
    env = os.environ.copy()
    env["PYTHONPATH"] = PYTHONPATH
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    try:
        log_file = os.path.join(LOGS_DIR, f"{key}_bot.log")
        with open(log_file, "a") as lf:
            subprocess.Popen(
                ["python3", script],
                env=env,
                stdout=lf, stderr=lf,
                start_new_session=True
            )
        time.sleep(1.5)
        running, pid = _is_running(script)
        return {"ok": running, "pid": pid, "msg": "تم التشغيل" if running else "فشل التشغيل"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


def _stop_bot(key: str) -> dict:
    script = BOT_SCRIPTS.get(key)
    if not script:
        return {"ok": False, "msg": "بوت غير معروف"}
    killed = 0
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if script in cmdline:
                os.kill(proc.info["pid"], signal.SIGTERM)
                killed += 1
        except Exception:
            pass
    time.sleep(0.8)
    return {"ok": True, "msg": f"تم إيقاف {killed} عملية"}


def _restart_bot(key: str) -> dict:
    _stop_bot(key)
    time.sleep(0.5)
    return _start_bot(key)


@router.get("", response_class=HTMLResponse)
async def bots_page(request: Request, session: dict = Depends(require_owner)):
    bots = _bot_status_all()
    return templates.TemplateResponse(request, "bots.html", {
        "bots": bots, "active_page": "bots"
    })


@router.get("/api/status")
async def api_status(session: dict = Depends(require_owner)):
    return _bot_status_all()


@router.post("/api/start/{key}")
async def api_start(key: str, session: dict = Depends(require_owner)):
    return _start_bot(key)


@router.post("/api/stop/{key}")
async def api_stop(key: str, session: dict = Depends(require_owner)):
    return _stop_bot(key)


@router.post("/api/restart/{key}")
async def api_restart(key: str, session: dict = Depends(require_owner)):
    return _restart_bot(key)


@router.post("/api/restart_all")
async def api_restart_all(session: dict = Depends(require_owner)):
    results = {}
    for key in BOT_META:
        results[key] = _restart_bot(key)
    return {"ok": True, "results": results}


@router.get("/api/logs/{key}")
async def api_logs(key: str, lines: int = 80, session: dict = Depends(require_owner)):
    log_file = os.path.join(LOGS_DIR, f"{key}_bot.log")
    if not os.path.exists(log_file):
        return {"lines": [], "msg": "لا يوجد ملف log"}
    try:
        with open(log_file, "r", errors="replace") as f:
            all_lines = f.readlines()
        return {"lines": [l.rstrip() for l in all_lines[-lines:]]}
    except Exception as e:
        return {"lines": [], "msg": str(e)}
