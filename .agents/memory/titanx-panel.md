---
name: TitanX Control Panel
description: FastAPI panel setup, ports, auth, and key architectural decisions
---

# TitanX Control Panel

## Server & Ports
- **Server**: `extracted_project/control_panel/server.py` → uvicorn, port 5000
- **Auth**: Token-based `/panel?k=TOKEN` OR password login `/panel/login` (SHA256+salt in `.panel_settings.json`)
- **Password default**: `9,c4A,tw_Q!*iL` (DO NOT change in code — user manages via `/panel/api/change-password`)
- **PYTHONPATH**: `/home/runner/workspace/.pythonlibs/lib/python3.12/site-packages:$PYTHONPATH`

## Deployment
- **Target**: `vm` (always-running — bots need persistent processes)
- **Run command**: `bash /home/runner/workspace/scripts/start.sh`
- **Previously**: `autoscale` — changed to `vm` to support bot persistence in production

## Blur — PERMANENT FIX (2026-06-18)
Root causes identified and eliminated:
1. `.modal-overlay` base rule had `backdrop-filter: blur(8px)` — removed, now ONLY on `:not(.hidden)`
2. `.mobile-overlay { backdrop-filter: blur(3px) }` — my bad addition from prior session, removed
3. `bg-orb { filter: blur(50px) }` → reduced to `22px`; orb opacity further lowered (0.010–0.022)
4. `.loading-overlay` — explicitly `backdrop-filter: none !important`
5. `.layout { isolation: isolate }` — prevents stacking context blur bleed
6. Particles canvas opacity reduced from 0.6 → 0.45

**Why**: `backdrop-filter` on hidden elements (even `display:none`) can cause rendering artifacts in some browsers (Chrome/WebKit), especially with `opacity` transitions.

## Key Files
- `control_panel/app.py` — FastAPI app, routers registered
- `control_panel/static/css/style.css` — ~1900 lines, blur fixes at end
- `control_panel/static/js/app.js` — live stats, bot polling, particles, header clock
- `control_panel/templates/base.html` — header with live sys-pill + clock
- `control_panel/templates/dashboard.html` — AI control center, live activity feed
- `control_panel/routers/bots.py` — 4-state bot control (running/stopped/restarting/error)
