"""
TitanX AI Command Center — Smart project operations and health checks.
"""
import os
import sys
import time
import signal
import zipfile
import asyncio
import subprocess
import psutil
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from ..auth import require_owner
from ..config import CONTROL_PANEL_DIR, EXTRACTED_DIR, BACKUPS_DIR, LOGS_DIR, BOT_SCRIPTS
from .. import activity_log

router = APIRouter(prefix="/ai")
templates = Jinja2Templates(directory=os.path.join(CONTROL_PANEL_DIR, "templates"))


def _human_size(b: int) -> str:
    if b < 1024: return f"{b} B"
    if b < 1_048_576: return f"{b/1024:.1f} KB"
    return f"{b/1_048_576:.1f} MB"


def _find_pid(script: str) -> int | None:
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            if script and script in " ".join(p.info["cmdline"] or []):
                return p.info["pid"]
        except Exception:
            pass
    return None


# ── Health Check ──────────────────────────────────────────────────────────────

def _check_health() -> dict:
    checks = []
    overall = True

    # 1. Bots
    bot_meta = {
        "main":    "البوت الرئيسي",
        "admin":   "بوت الإدمن",
        "support": "بوت الدعم",
        "dev":     "بوت المطور",
    }
    for key, label in bot_meta.items():
        script = BOT_SCRIPTS.get(key, "")
        pid = _find_pid(script)
        ok = pid is not None
        checks.append({
            "category": "البوتات",
            "name": label,
            "ok": ok,
            "msg": f"يعمل (PID {pid})" if ok else "متوقف",
        })
        if not ok:
            overall = False

    # 2. Bot script files exist
    for key, script in BOT_SCRIPTS.items():
        exists = os.path.exists(script)
        checks.append({
            "category": "الملفات",
            "name": f"ملف {key}_bot",
            "ok": exists,
            "msg": "موجود" if exists else f"مفقود: {script}",
        })
        if not exists:
            overall = False

    # 3. Database files
    from ..config import MAIN_DB, SUPPORT_DB, DEV_DB
    for label, path in [("Bot DB", MAIN_DB), ("Support DB", SUPPORT_DB), ("Dev DB", DEV_DB)]:
        exists = os.path.exists(path)
        checks.append({
            "category": "قواعد البيانات",
            "name": label,
            "ok": exists,
            "msg": f"{_human_size(os.path.getsize(path))}" if exists else "مفقود",
        })

    # 4. Logs directory
    logs_ok = os.path.isdir(LOGS_DIR)
    checks.append({
        "category": "السجلات",
        "name": "مجلد السجلات",
        "ok": logs_ok,
        "msg": "موجود" if logs_ok else "مفقود",
    })

    # 5. Backups directory
    bk_ok = os.path.isdir(BACKUPS_DIR)
    bk_count = len([f for f in os.listdir(BACKUPS_DIR) if f.endswith(".zip")]) if bk_ok else 0
    checks.append({
        "category": "النسخ الاحتياطية",
        "name": "مجلد النسخ الاحتياطية",
        "ok": True,
        "msg": f"{bk_count} نسخة متاحة",
    })

    # 6. Disk space
    disk = psutil.disk_usage(EXTRACTED_DIR)
    disk_ok = disk.percent < 90
    checks.append({
        "category": "النظام",
        "name": "مساحة القرص",
        "ok": disk_ok,
        "msg": f"{disk.percent:.1f}% مستخدم ({_human_size(disk.free)} متاح)",
    })
    if not disk_ok:
        overall = False

    # 7. Memory
    mem = psutil.virtual_memory()
    mem_ok = mem.percent < 90
    checks.append({
        "category": "النظام",
        "name": "الذاكرة (RAM)",
        "ok": mem_ok,
        "msg": f"{mem.percent:.1f}% مستخدم",
    })

    # 8. Error scan in recent logs
    error_count = 0
    try:
        for fname in os.listdir(LOGS_DIR) if os.path.isdir(LOGS_DIR) else []:
            if fname.endswith(".log"):
                fp = os.path.join(LOGS_DIR, fname)
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f.readlines()[-100:]:
                            if "ERROR" in line or "CRITICAL" in line:
                                error_count += 1
                except Exception:
                    pass
    except Exception:
        pass
    checks.append({
        "category": "السجلات",
        "name": "فحص الأخطاء",
        "ok": error_count < 10,
        "msg": f"{error_count} خطأ في السجلات الأخيرة" if error_count else "لا أخطاء",
    })

    passed = sum(1 for c in checks if c["ok"])
    total = len(checks)
    return {
        "overall": overall and passed >= total * 0.8,
        "passed": passed,
        "total": total,
        "score": int(passed / total * 100) if total else 0,
        "checks": checks,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def ai_page(request: Request, session: dict = Depends(require_owner)):
    return templates.TemplateResponse(request, "ai.html", {"active_page": "ai"})


@router.get("/api/health")
async def api_health(session: dict = Depends(require_owner)):
    result = _check_health()
    activity_log.log("health_check", "فحص صحة المشروع", f"النتيجة: {result['score']}%")
    return result


@router.post("/api/restart_bots")
async def api_restart_bots(session: dict = Depends(require_owner)):
    results = []
    for key, script in BOT_SCRIPTS.items():
        pid = _find_pid(script)
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                results.append(f"⏹️ أُوقف {key} (PID {pid})")
            except Exception as e:
                results.append(f"⚠️ فشل إيقاف {key}: {e}")
        else:
            results.append(f"ℹ️ {key} لم يكن يعمل")
    await asyncio.sleep(2.5)
    for key, script in BOT_SCRIPTS.items():
        if not script or not os.path.exists(script):
            results.append(f"❌ ملف {key} غير موجود")
            continue
        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            proc = subprocess.Popen(
                [sys.executable, script],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env, start_new_session=True,
            )
            results.append(f"▶️ شُغِّل {key} (PID {proc.pid})")
        except Exception as e:
            results.append(f"❌ فشل تشغيل {key}: {e}")
    activity_log.log("bot_restart", "إعادة تشغيل جميع البوتات عبر مركز AI")
    return {"ok": True, "results": results}


@router.post("/api/create_backup")
async def api_create_backup(session: dict = Depends(require_owner)):
    from .backups import _SKIP_DIRS, _SKIP_EXTS, _human_size as bk_size
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"backup_{ts}_ai.zip"
    dest = os.path.join(BACKUPS_DIR, name)
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    try:
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
        size = bk_size(os.path.getsize(dest))
        # Verify
        with zipfile.ZipFile(dest, "r") as zf:
            count = len(zf.namelist())
        activity_log.log("backup_created", f"نسخة احتياطية عبر AI: {name}", f"الحجم: {size} · الملفات: {count}")
        return {"ok": True, "name": name, "size": size, "files": count}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/scan_errors")
async def api_scan_errors(session: dict = Depends(require_owner)):
    results = []
    if not os.path.isdir(LOGS_DIR):
        return {"errors": [], "message": "مجلد السجلات غير موجود"}
    for fname in sorted(os.listdir(LOGS_DIR)):
        if not fname.endswith(".log"):
            continue
        fp = os.path.join(LOGS_DIR, fname)
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            errors = [(i + 1, l.rstrip()) for i, l in enumerate(lines[-500:])
                      if "ERROR" in l or "CRITICAL" in l or "Traceback" in l]
            if errors:
                results.append({
                    "file": fname,
                    "count": len(errors),
                    "samples": [{"line": ln, "text": txt} for ln, txt in errors[:5]],
                })
        except Exception:
            pass
    activity_log.log("health_check", "فحص أخطاء السجلات", f"{sum(r['count'] for r in results)} خطأ")
    return {"errors": results, "total": sum(r["count"] for r in results)}


@router.post("/api/fix_project")
async def api_fix_project(session: dict = Depends(require_owner)):
    steps = []

    # 1. Create directories if missing
    for d in [LOGS_DIR, BACKUPS_DIR]:
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
            steps.append(f"✅ أُنشئ المجلد: {os.path.basename(d)}")
        else:
            steps.append(f"ℹ️ المجلد موجود: {os.path.basename(d)}")

    # 2. Clean pycache
    cleaned = 0
    for root, dirs, _ in os.walk(EXTRACTED_DIR):
        for d in dirs:
            if d == "__pycache__":
                try:
                    import shutil
                    shutil.rmtree(os.path.join(root, d))
                    cleaned += 1
                except Exception:
                    pass
    steps.append(f"🧹 تم تنظيف {cleaned} مجلد __pycache__")

    # 3. Check and restart stopped bots
    restart_count = 0
    for key, script in BOT_SCRIPTS.items():
        if not os.path.exists(script):
            continue
        pid = _find_pid(script)
        if not pid:
            try:
                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"
                subprocess.Popen(
                    [sys.executable, script],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    env=env, start_new_session=True,
                )
                restart_count += 1
                steps.append(f"▶️ أُعيد تشغيل البوت: {key}")
            except Exception as e:
                steps.append(f"❌ فشل تشغيل {key}: {e}")
        else:
            steps.append(f"✅ البوت {key} يعمل بالفعل")

    # 4. Git status check
    try:
        r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True,
                           cwd=EXTRACTED_DIR, timeout=10)
        changed = len(r.stdout.strip().split("\n")) if r.stdout.strip() else 0
        steps.append(f"🐙 Git: {changed} ملف غير محفوظ")
    except Exception:
        steps.append("⚠️ Git: تعذّر الفحص")

    activity_log.log("recovery", "إصلاح المشروع الكامل", f"{len(steps)} خطوة")
    return {"ok": True, "steps": steps}
