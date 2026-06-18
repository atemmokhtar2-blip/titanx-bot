---
name: TitanX Replit Manager
description: The /replit section — what it does, how it's wired, key dependencies.
---

## Rule
`routers/replit_manager.py` handles all `/replit` routes. Template: `templates/replit_manager.html`. Must import `PROJECT_ROOT` from `..config` for disk usage calls.

## APIs
- `GET /replit` — HTML page (health, procs, routes)
- `GET /replit/api/health` — live resource stats
- `GET /replit/api/processes` — Python/uvicorn process list via psutil
- `GET /replit/api/routes` — static route manifest
- `POST /replit/api/check-panel` — httpx self-check to localhost:5000/healthz
- `POST /replit/api/check-routes` — httpx checks /healthz, /panel, /system/api/stats

## Dependencies
- `httpx` (already installed in .pythonlibs)
- `psutil` (already installed)

## Navigation
Added "إدارة Replit" section in base.html sidebar → `/replit` with 🔧 icon. `active_page='replit'` must be passed from the router.

## Password change
The Replit Manager page also contains the password-change form (calls `POST /panel/api/change-password`).
