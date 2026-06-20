import os
import time
import asyncio
import hashlib
import hmac as _hmac
import secrets
import json
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from .config import CONTROL_PANEL_DIR, SECRET_KEY, OWNER_ID, PUBLIC_URL, EXTRACTED_DIR
from .auth import (create_session, get_session, require_owner,
                   SESSION_COOKIE, SESSION_MAX_AGE, NotAuthenticated, ACCESS_TOKEN)
from .routers import (dashboard, users, broadcast, db_manager,
                      files, logs_router, system, updates, github_router, search)
from .routers import bots, backups, replit_manager, ai_workspace
from . import env_validator as _ev

# Run env validation at import time — logs warnings, never crashes
_ev.log_startup_summary()

# ── Panel settings (persistent password store) ──────────────────────────────
SETTINGS_FILE = os.path.join(EXTRACTED_DIR, ".panel_settings.json")
_DEFAULT_PASSWORD = "9,c4A,tw_Q!*iL"


def _load_settings() -> dict:
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_settings(data: dict):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _hash_pw(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def _verify_password(password: str) -> bool:
    s = _load_settings()
    salt = s.get("password_salt", "")
    stored = s.get("password_hash", "")
    if not stored or not salt:
        return False
    return _hmac.compare_digest(_hash_pw(password, salt), stored)


def _init_password():
    s = _load_settings()
    if not s.get("password_hash"):
        salt = secrets.token_hex(16)
        s["password_hash"] = _hash_pw(_DEFAULT_PASSWORD, salt)
        s["password_salt"] = salt
        _save_settings(s)


_init_password()

# Build-time version stamp — changes every restart, forces browser cache-bust
_BUILD_TS = str(int(time.time()))

app = FastAPI(title="X Control Center", docs_url=None, redoc_url=None)

# ── No-cache middleware for static assets ────────────────────────────────────
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        elif not path.startswith("/static"):
            response.headers["Cache-Control"] = "no-store"
        return response

app.add_middleware(NoCacheMiddleware)
from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=SESSION_MAX_AGE)

_static = os.path.join(CONTROL_PANEL_DIR, "static")
_templates_dir = os.path.join(CONTROL_PANEL_DIR, "templates")
app.mount("/static", StaticFiles(directory=_static), name="static")
templates = Jinja2Templates(directory=_templates_dir)
# Inject build timestamp into every template so ?v= busts the browser cache
templates.env.globals["VER"] = _BUILD_TS
templates.env.globals["UI_VERSION"] = "v5.0"
templates.env.globals["BRAND_NAME"] = "X"

app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(broadcast.router)
app.include_router(db_manager.router)
app.include_router(files.router)
app.include_router(logs_router.router)
app.include_router(system.router)
app.include_router(updates.router)
app.include_router(github_router.router)
app.include_router(search.router)
app.include_router(bots.router)
app.include_router(backups.router)
app.include_router(replit_manager.router)
app.include_router(ai_workspace.router)


def _public_base() -> str:
    return PUBLIC_URL or ""


def _access_url() -> str:
    base = _public_base()
    return f"{base}/panel?k={ACCESS_TOKEN}" if base else f"/panel?k={ACCESS_TOKEN}"


# ── Exception handlers ──────────────────────────────────────────────────────

@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(request: Request, exc: NotAuthenticated):
    return RedirectResponse(url="/panel", status_code=302)


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    return templates.TemplateResponse(request, "access.html", {
        "owner_id": OWNER_ID,
        "access_url": _access_url(),
        "error": str(getattr(exc, "detail", "وصول مرفوض")),
    }, status_code=403)


# ── Access route (token-based) ──────────────────────────────────────────────

@app.get("/panel", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def panel_access(request: Request, k: str = ""):
    session = get_session(request)
    if session and session.get("uid") == OWNER_ID:
        return RedirectResponse("/", status_code=302)
    if k:
        if k == ACCESS_TOKEN:
            token = create_session(OWNER_ID)
            response = RedirectResponse("/", status_code=302)
            response.set_cookie(SESSION_COOKIE, token,
                                max_age=SESSION_MAX_AGE, httponly=True,
                                secure=True, samesite="lax")
            return response
        return templates.TemplateResponse(request, "access.html", {
            "owner_id": OWNER_ID,
            "access_url": _access_url(),
            "error": "رمز الدخول غير صحيح",
        })
    return templates.TemplateResponse(request, "access.html", {
        "owner_id": OWNER_ID,
        "access_url": _access_url(),
        "error": None,
    })


@app.post("/panel/login", response_class=HTMLResponse)
async def panel_password_login(request: Request):
    form = await request.form()
    password = str(form.get("password", ""))
    if password and _verify_password(password):
        token = create_session(OWNER_ID)
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(SESSION_COOKIE, token,
                            max_age=SESSION_MAX_AGE, httponly=True,
                            secure=True, samesite="lax")
        return response
    return templates.TemplateResponse(request, "access.html", {
        "owner_id": OWNER_ID,
        "access_url": _access_url(),
        "error": "كلمة المرور غير صحيحة ⚠️",
    }, status_code=401)


@app.post("/panel/api/change-password")
async def api_change_password(request: Request, session: dict = Depends(require_owner)):
    body = await request.json()
    new_pw = body.get("password", "").strip()
    if len(new_pw) < 6:
        return JSONResponse({"ok": False, "error": "كلمة المرور قصيرة جداً (6 أحرف على الأقل)"}, status_code=400)
    s = _load_settings()
    salt = secrets.token_hex(16)
    s["password_hash"] = _hash_pw(new_pw, salt)
    s["password_salt"] = salt
    _save_settings(s)
    return {"ok": True, "msg": "تم تغيير كلمة المرور بنجاح ✅"}


# ── Legacy login redirect ───────────────────────────────────────────────────

@app.get("/login")
async def login_redirect():
    return RedirectResponse("/panel", status_code=302)


@app.get("/auth/callback")
async def auth_callback_redirect():
    return RedirectResponse("/panel", status_code=302)


# ── Logout ──────────────────────────────────────────────────────────────────

@app.get("/logout")
async def logout():
    response = RedirectResponse("/panel", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response


# ── Health / Readiness endpoints ─────────────────────────────────────────────

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "panel": "X Control Center", "version": "5.0"}


@app.get("/health")
async def health():
    """Production health endpoint — used by HF Spaces and Docker health checks."""
    import time as _time
    from . import env_validator as _ev
    ev = _ev.validate()
    return {
        "status":            "ok",
        "panel":             "X Control Center",
        "version":           "5.0",
        "env_score":         ev["score"],
        "deploy_blocked":    ev["deploy_blocked"],
        "missing_critical":  ev["missing_critical"],
        "timestamp":         int(_time.time()),
    }


@app.get("/ping")
async def ping():
    """Minimal liveness probe."""
    return {"ok": True}
