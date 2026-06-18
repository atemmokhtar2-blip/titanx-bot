---
name: TitanX Bot Cleanup
description: Admin Bot and Developer Bot were removed from the project; only Main Bot and Support Bot remain.
---

## Rule
Admin Bot and Developer Bot no longer exist. Only `main` and `support` bots are active.

## Files that define bot lists (keep in sync)
- `extracted_project/control_panel/config.py` — `BOT_SCRIPTS` dict: only `main` + `support`
- `extracted_project/control_panel/routers/bots.py` — `BOT_META` dict: only `main` + `support`
- `extracted_project/control_panel/routers/system.py` — `BOT_SCRIPTS` dict: only `main` + `support`

## Breaking pattern to avoid
`DEV_DB` and `dev_db()` were removed from `config.py` and `db_utils.py`. Any file that imports either will crash the control panel on startup. Always grep for `dev_db|DEV_DB` after any refactor.

**Why:** The admin_bot and developer_bot Replit workflows were deleted; their Telegram tokens still exist as secrets but are unused. The control panel previously used developer.db (dev_db) to store update history and backup records — that is now removed; those features simply return empty lists.

## GitHub persistent settings
`github_router.py` now saves git config (repo, name, email, branch, token) to `extracted_project/.panel_github_config.json`. Token from env var `GITHUB_TOKEN` always takes priority over saved token.
