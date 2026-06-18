---
name: TitanX Control Panel
description: FastAPI Arabic control panel — startup, auth, workflow, and Python path quirks.
---

## 502 Root Cause & Fix (critical)
Replit's `.replit` has TWO local ports both mapped to `externalPort = 80`:
- `localPort = 5000` (the panel)
- `localPort = 8081` (artifacts/api-server — CANNOT be deleted, managed by artifact system)

Replit's proxy routes to port 8081 first. With nothing on 8081, it returns 502 for ALL requests.

**Fix:** Run `server.py` on BOTH port 5000 AND port 8081 via `asyncio.gather()` with two `uvicorn.Server` instances. See `extracted_project/control_panel/server.py`.

**Why:** The artifact port mapping in `.replit` cannot be removed (artifact workflows are protected). The only fix is to serve on both ports.

## Startup command (must include PYTHONPATH)
```
PYTHONPATH=/home/runner/workspace/.pythonlibs/lib/python3.12/site-packages PYTHONDONTWRITEBYTECODE=1 python3 extracted_project/control_panel/server.py
```
**Why:** Nix ships typing_extensions 4.13.2 which lacks `Sentinel`; pydantic_core needs 4.15+. Must be in env var before Python starts.

## Auth system
- Primary login: POST /login with form field `password` checked against `PANEL_PASSWORD` env var.
- Secondary: GET /panel?k=ACCESS_TOKEN (deterministic HMAC of SECRET_KEY + OWNER_ID).
- Session cookie: `titanx_session`, 7-day TTL, `secure` flag dynamic from x-forwarded-proto header.
- Unauthenticated requests → redirect to /login.

## Key env vars (all in [userenv.shared])
- `PANEL_PASSWORD` — panel login password
- `OWNER_ID` = 7631249810
- `TELEGRAM_BOT_TOKEN`, `ADMIN_BOT_TOKEN`, `SUPPORT_BOT_TOKEN`, `DEVELOPER_BOT_TOKEN` — all set
- `SESSION_SECRET` — Replit Secret (cannot use setEnvVars, already exists)

## Bot workflow commands
All bots need the same PYTHONPATH prefix:
- Main Bot: `extracted_project/bot.py`
- Admin Bot: `extracted_project/admin_bot/bot.py`
- Support Bot: `extracted_project/support_bot/bot.py`
- Developer Bot: `extracted_project/developer_bot/bot.py`

## Phase 3 Routers (all registered in app.py)
dashboard, users, broadcast, db_manager, files, logs_router, system, updates,
github_router, search, bots, backups, ai_center, activity

## Activity Log
`extracted_project/control_panel/activity_log.py` — shared in-memory deque (maxlen=200).
Call `activity_log.log(event_type, message, detail)` from any router. API: GET /activity/api/events.

## Key Phase 3 API endpoints
- `/system/api/chart_history` — time-series for Chart.js (last 20 readings, built up via /api/stats calls)
- `/ai/api/health` — comprehensive health check (score 0-100, per-category checks)
- `/ai/api/restart_bots`, `/ai/api/create_backup`, `/ai/api/scan_errors`, `/ai/api/fix_project`
- `/backups/api/create` POST {label, strategy}, `/verify/{name}`, `/download/{name}`, `/delete/{name}` DELETE
- `/files/api/copy`, `/move`, `/compress`, `/extract`, `/preview_image`
- `/bots/api/status`, `/start/{key}`, `/stop/{key}`, `/restart/{key}`, `/restart_all`, `/logs/{key}`

## Back button
In base.html: JS shows `#back-btn` on all pages except `/`.

## Chart.js
Loaded via CDN only on system.html (not base.html) to avoid loading on every page.
Dashboard uses CSS bars and metric-pill bars (no Chart.js dependency).

## GitHub remote
origin: https://github.com/atemmokhtar2-blip/my-downlsx-bot
