import os
import time
import json
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

HEARTBEAT_FILES = {
    "main":    "/tmp/bot_health.json",
    "support": "/tmp/support_bot_health.json",
}
HEARTBEAT_MAX_AGE = 360

BOT_META = {
    "main":    {"label": "البوت الرئيسي", "icon": "🤖", "color": "accent"},
    "support": {"label": "بوت الدعم",     "icon": "🎧", "color": "cyan"},
}

# Track in-progress restart actions {key: timestamp}
_restarting: dict[str, float] = {}
RESTARTING_TIMEOUT = 15  # seconds


def _check_heartbeat(key: str) -> tuple[bool, int | None]:
    hf = HEARTBEAT_FILES.get(key)
    if not hf or not os.path.exists(hf):
        return False, None
    try:
        with open(hf) as f:
            data = json.load(f)
        ts  = data.get("timestamp") or data.get("ts") or 0
        pid = data.get("pid")
        age = time.time() - float(ts)
        if age < HEARTBEAT_MAX_AGE:
            if pid:
                try:
                    os.kill(int(pid), 0)
                    return True, int(pid)
                except (ProcessLookupError, PermissionError, ValueError):
                    pass
            return True, None
    except Exception:
        pass
    return False, None


def _clear_heartbeat(key: str):
    """Delete heartbeat file so status reflects reality immediately after stop."""
    hf = HEARTBEAT_FILES.get(key)
    if hf and os.path.exists(hf):
        try:
            os.remove(hf)
        except Exception:
            pass


def _is_running(script_path: str):
    script_base = os.path.basename(script_path)
    best_pid = None
    for proc in psutil.process_iter(["pid", "cmdline", "status"]):
        try:
            info      = proc.info
            cmdline   = info.get("cmdline") or []
            cmdline_s = " ".join(cmdline)
            status    = info.get("status", "")
            matches   = script_path in cmdline_s or script_base in cmdline
            if matches and status not in ("zombie", "dead"):
                pid = info["pid"]
                try:
                    p = psutil.Process(pid)
                    if p.status() not in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                        return True, pid
                except Exception:
                    best_pid = pid
        except Exception:
            pass
    if best_pid:
        return True, best_pid
    return False, None


def _get_bot_status(key: str, script_path: str) -> tuple[str, int | None]:
    """
    Returns (state, pid) where state is one of:
      'running'    — green
      'stopped'    — red
      'restarting' — orange
    """
    # If a restart/stop action was recently triggered show restarting
    rt = _restarting.get(key)
    if rt and (time.time() - rt) < RESTARTING_TIMEOUT:
        return "restarting", None

    hb_alive, hb_pid = _check_heartbeat(key)
    if hb_alive:
        return "running", hb_pid

    ps_alive, ps_pid = _is_running(script_path)
    return ("running" if ps_alive else "stopped"), ps_pid


def _bot_status_all() -> list:
    result = []
    for key, meta in BOT_META.items():
        script = BOT_SCRIPTS.get(key, "")
        state, pid = _get_bot_status(key, script)
        result.append({
            "key":        key,
            "label":      meta["label"],
            "icon":       meta["icon"],
            "color":      meta["color"],
            "script":     os.path.basename(script),
            "state":      state,
            "running":    state == "running",
            "restarting": state == "restarting",
            "pid":        pid,
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
    env["PYTHONPATH"]              = PYTHONPATH
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"]        = "1"
    try:
        log_file = os.path.join(LOGS_DIR, f"{key}_bot.log")
        with open(log_file, "a") as lf:
            subprocess.Popen(
                ["python3", script], env=env,
                stdout=lf, stderr=lf, start_new_session=True
            )
        time.sleep(1.8)
        running, pid = _is_running(script)
        # Clear restarting flag once confirmed
        _restarting.pop(key, None)
        return {"ok": running, "pid": pid, "msg": "تم التشغيل" if running else "فشل التشغيل"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


def _stop_bot(key: str) -> dict:
    script = BOT_SCRIPTS.get(key)
    if not script:
        return {"ok": False, "msg": "بوت غير معروف"}
    script_base = os.path.basename(script)
    killed = 0
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline_s = " ".join(proc.info.get("cmdline") or [])
            cmdline_l = proc.info.get("cmdline") or []
            if script in cmdline_s or script_base in cmdline_l:
                os.kill(proc.info["pid"], signal.SIGTERM)
                killed += 1
        except Exception:
            pass
    # Immediately clear the heartbeat file so status shows "stopped" at once
    _clear_heartbeat(key)
    # Mark restarting state so UI shows orange briefly
    _restarting[key] = time.time()
    time.sleep(0.8)
    # If nothing is running anymore, clear the restarting flag immediately
    still_running, _ = _is_running(script)
    if not still_running:
        _restarting.pop(key, None)
    return {"ok": True, "msg": f"تم إيقاف {killed} عملية", "killed": killed}


def _restart_bot(key: str) -> dict:
    _restarting[key] = time.time()
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
async def api_logs(key: str, lines: int = 100, session: dict = Depends(require_owner)):
    log_file = os.path.join(LOGS_DIR, f"{key}_bot.log")
    if not os.path.exists(log_file):
        return {"lines": [], "msg": "لا يوجد ملف log"}
    try:
        with open(log_file, "r", errors="replace") as f:
            all_lines = f.readlines()
        return {"lines": [l.rstrip() for l in all_lines[-lines:]]}
    except Exception as e:
        return {"lines": [], "msg": str(e)}
