---
name: TitanX Password System
description: How the panel password login works — storage, hashing, routes, and defaults.
---

## Rule
Password is stored as SHA256(salt:password) in `extracted_project/.panel_settings.json` under keys `password_hash` and `password_salt`.

## Default
`9,c4A,tw_Q!*iL` — initialized on first startup via `_init_password()` in app.py.

## Routes
- `POST /panel/login` — form-encoded `password` field; sets session cookie on success; returns 401 on failure.
- `POST /panel/api/change-password` — JSON `{"password": "new"}` — requires active session; updates the settings file.

## Functions (app.py)
`_hash_pw(password, salt)`, `_verify_password(password)`, `_init_password()`, `_load_settings()`, `_save_settings(data)`.

## Why
Persistent password that survives restarts (file-based, not env var), immune to secret rotation, supports user-changing from Replit Manager page.

## How to apply
Any future password feature should read/write `.panel_settings.json` via the same helpers. Never store plaintext.
