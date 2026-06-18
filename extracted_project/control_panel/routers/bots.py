import os
import sys
import signal
import asyncio
import subprocess
import psutil
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from ..auth import require_owner
from ..config import CONTROL_PANEL_DIR, BOT_SCRIPTS, LOGS_DIR

router = APIRouter(prefix="/bots")
templates = Jinja2Templates(directory=os.path.join(CONTROL_PANEL_DIR, "templates"))

BOT_META = {
    "main":    {"label": "البوت الرئيسي",  "icon": "🤖", "color": "var(--accent)"},
    "admin":   {"label": "بوت الإدمن",      "icon": "🛡️", "color": "var(--purple)"},
    "support": {"label": "بوت الدعم",       "icon": "🎧", "color": "var(--green)"},
    "dev":     {"label": "بوت المطور",      "icon": "⚙️", "color": "var(--yellow)"},
}


def _find_bot_pids(script_path: str) -> list:
    pids = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmd = " ".join(proc.info["cmdline"] or [])
            if script_path and script_path in cmd:
                pids.append(proc.info["pid"])
        except Exception:
            pass
    return pids


def _get_bot_status(key: str) -> dict:
    script = BOT_SCRIPTS.get(key, "")
    meta = BOT_META.get(key, {"label": key, "icon": "🤖", "color": "var(--accent)"})
    pids = _find_bot_pids(script)
    running = len(pids) > 0
    return {
        "key": key,
        "label": meta["label"],
        "icon": meta["icon"],
        "color": meta["color"],
        "script": script,
        "running": running,
        "pids": pids,
        "pid": pids[0] if pids else None,
    }


@router.get("", response_class=HTMLResponse)
async def bots_page(request: Request, session: dict = Depends(require_owner)):
    bots = [_get_bot_status(k) for k in BOT_META]
    return templates.TemplateResponse(request, "bots.html", {
        "bots": bots, "active_page": "bots"
    })


@router.get("/api/status")
async def api_status(session: dict = Depends(require_owner)):
    return {"bots": [_get_bot_status(k) for k in BOT_META]}


@router.post("/api/stop/{key}")
async def api_stop(key: str, session: dict = Depends(require_owner)):
    if key not in BOT_META:
        return JSONResponse({"error": "بوت غير معروف"}, status_code=400)
    script = BOT_SCRIPTS.get(key, "")
    pids = _find_bot_pids(script)
    if not pids:
        return {"ok": True, "message": "البوت ليس يعمل أصلاً"}
    killed = []
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            killed.append(pid)
        except Exception:
            pass
    return {"ok": True, "message": f"تم إرسال إشارة إيقاف للـ PID: {killed}"}


@router.post("/api/start/{key}")
async def api_start(key: str, session: dict = Depends(require_owner)):
    if key not in BOT_META:
        return JSONResponse({"error": "بوت غير معروف"}, status_code=400)
    script = BOT_SCRIPTS.get(key, "")
    if not script or not os.path.exists(script):
        return JSONResponse({"error": "ملف البوت غير موجود"}, status_code=400)
    pids = _find_bot_pids(script)
    if pids:
        return {"ok": True, "message": f"البوت يعمل بالفعل (PID: {pids[0]})"}
    try:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        pythonpath = os.path.join(os.path.dirname(sys.executable), "..", "lib",
                                  f"python{sys.version_info.major}.{sys.version_info.minor}",
                                  "site-packages")
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = pythonpath + (":" + existing if existing else "")
        proc = subprocess.Popen(
            [sys.executable, script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        return {"ok": True, "message": f"تم تشغيل البوت (PID: {proc.pid})"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/restart/{key}")
async def api_restart(key: str, session: dict = Depends(require_owner)):
    stop_result = await api_stop(key, session)
    await asyncio.sleep(2)
    return await api_start(key, session)


@router.post("/api/restart_all")
async def api_restart_all(session: dict = Depends(require_owner)):
    for key in BOT_META:
        await api_stop(key, session)
    await asyncio.sleep(2.5)
    results = []
    for key in BOT_META:
        r = await api_start(key, session)
        label = BOT_META[key]["label"]
        msg = r.get("message", "خطأ") if isinstance(r, dict) else "خطأ"
        results.append(f"{label}: {msg}")
    return {"ok": True, "results": results}


@router.get("/api/logs/{key}")
async def api_logs(key: str, lines: int = 150, session: dict = Depends(require_owner)):
    if key not in BOT_META:
        return JSONResponse({"error": "بوت غير معروف"}, status_code=400)
    candidates = [
        os.path.join(LOGS_DIR, f"{key}_bot.log"),
        os.path.join(LOGS_DIR, f"{key}.log"),
        os.path.join(LOGS_DIR, f"bot_{key}.log"),
        os.path.join(LOGS_DIR, "bot.log"),
    ]
    log_file = next((p for p in candidates if os.path.exists(p)), None)
    if not log_file:
        return {"lines": [f"لا يوجد ملف سجل للبوت '{key}' في {LOGS_DIR}"]}
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
        return {"lines": [l.rstrip() for l in all_lines[-lines:]]}
    except Exception as e:
        return {"lines": [f"خطأ في قراءة السجل: {e}"]}
