---
name: TitanX Control Panel
description: Key decisions and quirks for the TitanX bot suite + control panel on Replit.
---

## Auth
- Token = HMAC-SHA256(SECRET_KEY, OWNER_ID)[:18] encoded base64url — deterministic, no DB needed.
- Access URL: `/panel?k=<TOKEN>` → sets session cookie → redirects to `/dashboard`.
- OWNER_ID from env `OWNER_ID` (set in .replit userenv). Token is `uoLVbwho9geilbVaeKciWWbZ`.

## Port / Deployment
- Control panel runs on port 5000, maps to externalPort 80.
- Deployment: autoscale, run = ["bash", "-c", "PYTHONPATH=.../.pythonlibs/lib/python3.12/site-packages:$PYTHONPATH python3 /home/runner/workspace/extracted_project/control_panel/server.py"]
- gunicorn is NOT installed; uvicorn is in `.pythonlibs`.

## Production domain
- Dev: REPLIT_DEV_DOMAIN; Production: REPLIT_DOMAINS (comma-separated, use first entry).
- config.py already handles both.

**Why:** Replit dev containers expose REPLIT_DEV_DOMAIN; deployed apps expose REPLIT_DOMAINS instead.

## File management
- All API routes exist: /files/api/{list,read,save,delete,rename,mkdir,upload,download}
- renameFile() JS added to app.js; rename button (✍️) in renderDir() for each item.

## Update center
- /updates/api/{analyze,apply,status,backup,restore} all implemented in updates.py.
- Apply runs as background task (BackgroundTasks). Poll /api/status for progress.
