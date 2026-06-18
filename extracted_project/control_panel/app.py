import os
import asyncio
from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import CONTROL_PANEL_DIR, SECRET_KEY, OWNER_ID, PUBLIC_URL
from .auth import (create_session, get_session, require_owner,
                   SESSION_COOKIE, SESSION_MAX_AGE, NotAuthenticated, ACCESS_TOKEN)
from .routers import (dashboard, users, broadcast, db_manager,
                      files, logs_router, system, updates, github_router, search,
                      bots, backups, ai_center, activity)
from . import activity_log

app = FastAPI(title="TitanX Control Panel", docs_url=None, redoc_url=None)

from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=SESSION_MAX_AGE)

_static = os.path.join(CONTROL_PANEL_DIR, "static")
_templates_dir = os.path.join(CONTROL_PANEL_DIR, "templates")
app.mount("/static", StaticFiles(directory=_static), name="static")
templates = Jinja2Templates(directory=_templates_dir)

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
app.include_router(ai_center.router)
app.include_router(activity.router)


def _is_https(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    return forwarded_proto == "https" or str(request.url).startswith("https")


def _public_base() -> str:
    return PUBLIC_URL or ""


def _access_url() -> str:
    base = _public_base()
    return f"{base}/panel?k={ACCESS_TOKEN}" if base else f"/panel?k={ACCESS_TOKEN}"


# ── Exception handlers ──────────────────────────────────────────────────────

@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(request: Request, exc: NotAuthenticated):
    return RedirectResponse(url="/login", status_code=302)


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
async def panel_access(request: Request, k: str = ""):
    session = get_session(request)
    if session and session.get("uid") == OWNER_ID:
        return RedirectResponse("/", status_code=302)
    if k:
        if k == ACCESS_TOKEN:
            token = create_session(OWNER_ID)
            response = RedirectResponse("/", status_code=302)
            _secure = _is_https(request)
            response.set_cookie(SESSION_COOKIE, token,
                                max_age=SESSION_MAX_AGE, httponly=True,
                                secure=_secure, samesite="lax")
            activity_log.log("user_login", "دخول عبر رمز الوصول")
            return response
        return templates.TemplateResponse(request, "access.html", {
            "owner_id": OWNER_ID, "access_url": _access_url(),
            "error": "رمز الدخول غير صحيح",
        })
    return templates.TemplateResponse(request, "access.html", {
        "owner_id": OWNER_ID, "access_url": _access_url(), "error": None,
    })


# ── Login ──────────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, error: str = ""):
    session = get_session(request)
    if session and session.get("uid") == OWNER_ID:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "access.html", {
        "owner_id": OWNER_ID, "access_url": _access_url(),
        "error": error or None, "show_password_form": True,
    })


@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, password: str = Form(...)):
    panel_password = os.getenv("PANEL_PASSWORD", "")
    if panel_password and password == panel_password:
        token = create_session(OWNER_ID)
        response = RedirectResponse("/", status_code=302)
        _secure = _is_https(request)
        response.set_cookie(SESSION_COOKIE, token,
                            max_age=SESSION_MAX_AGE, httponly=True,
                            secure=_secure, samesite="lax")
        activity_log.log("user_login", "دخول عبر كلمة المرور")
        return response
    return templates.TemplateResponse(request, "access.html", {
        "owner_id": OWNER_ID, "access_url": _access_url(),
        "error": "كلمة المرور غير صحيحة", "show_password_form": True,
    })


@app.get("/auth/callback")
async def auth_callback_redirect():
    return RedirectResponse("/panel", status_code=302)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "panel": "TitanX Control Panel"}


@app.get("/logout")
async def logout():
    activity_log.log("user_login", "تسجيل خروج")
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response
