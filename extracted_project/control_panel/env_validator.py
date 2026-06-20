"""
Centralized environment variable validation for HF/Docker deployment.
Imported at startup — logs warnings but does NOT crash the panel for missing bot tokens.
"""
import os
import logging

logger = logging.getLogger(__name__)

# ── Variable registry ─────────────────────────────────────────────────────────

_VARS = [
    # (name, severity, format_hint, description)
    ("TELEGRAM_BOT_TOKEN",  "CRITICAL", "digits:letters from @BotFather",      "Main bot token — bot.py raises ValueError without this"),
    ("SUPPORT_BOT_TOKEN",   "CRITICAL", "digits:letters from @BotFather",       "Support bot token — support_bot crashes without this"),
    ("OWNER_ID",            "CRITICAL", "integer (Telegram user ID)",            "Your Telegram numeric user ID — panel token URL broken without this"),
    ("SESSION_SECRET",      "HIGH",     "random string ≥32 chars",               "Signs session cookies — defaults to public hardcoded string if missing"),
    ("PUBLIC_URL",          "MEDIUM",   "https://your-space.hf.space",          "Public URL of the deployment — link generation returns empty string if missing"),
    ("REQUIRED_CHANNEL",    "LOW",      "@channel_username",                     "Channel subscription gate — disabled if missing"),
    ("ADMIN_IDS",           "LOW",      "comma-separated integers",              "Additional admin Telegram IDs — empty if missing"),
    ("SUPPORT_BOT_USERNAME","LOW",      "@username without @",                   "Support bot username — cosmetic only"),
    ("GITHUB_TOKEN",        "INFO",     "ghp_xxxx personal access token",        "GitHub integration — non-functional if missing"),
    ("GITHUB_REPO",         "INFO",     "owner/repo",                            "GitHub repo — non-functional if missing"),
]

REQUIRED   = [v[0] for v in _VARS if v[1] in ("CRITICAL",)]
HIGH_RISK  = [v[0] for v in _VARS if v[1] == "HIGH"]
OPTIONAL   = [v[0] for v in _VARS if v[1] not in ("CRITICAL", "HIGH")]


def validate() -> dict:
    """Run validation and return structured result. Does not raise."""
    results = []
    for name, severity, fmt, desc in _VARS:
        val = os.environ.get(name, "")
        present = bool(val.strip())

        # Format checks
        format_ok = True
        format_msg = ""
        if present:
            if name in ("OWNER_ID",) and not val.strip().lstrip("-").isdigit():
                format_ok = False
                format_msg = "must be an integer"
            if name in ("TELEGRAM_BOT_TOKEN", "SUPPORT_BOT_TOKEN") and ":" not in val:
                format_ok = False
                format_msg = "expected format: 123456789:ABC-DEF..."

        status = "ok" if (present and format_ok) else (
            "format_error" if (present and not format_ok) else "missing"
        )
        results.append({
            "name":       name,
            "severity":   severity,
            "present":    present,
            "format_ok":  format_ok,
            "format_msg": format_msg,
            "status":     status,
            "hint":       fmt,
            "description": desc,
        })

    missing_critical = [r["name"] for r in results if r["severity"] == "CRITICAL" and r["status"] != "ok"]
    missing_high     = [r["name"] for r in results if r["severity"] == "HIGH"     and r["status"] != "ok"]
    ok_count         = sum(1 for r in results if r["status"] == "ok")
    total            = len(results)
    score            = round(100 * ok_count / total) if total else 0

    return {
        "results":          results,
        "missing_critical": missing_critical,
        "missing_high":     missing_high,
        "ok_count":         ok_count,
        "total":            total,
        "score":            score,
        "deploy_blocked":   bool(missing_critical),
    }


def log_startup_summary():
    """Log a startup summary — called once when the panel starts."""
    result = validate()
    logger.info("=" * 60)
    logger.info("ENV VALIDATION — startup check")
    for r in result["results"]:
        icon = "✅" if r["status"] == "ok" else ("⚠️" if r["severity"] not in ("CRITICAL",) else "❌")
        msg  = f"  {icon} {r['name']:30s} [{r['severity']:8s}] {'SET' if r['present'] else 'MISSING'}"
        if r["format_msg"]:
            msg += f" — format error: {r['format_msg']}"
        logger.info(msg)
    if result["missing_critical"]:
        logger.warning("DEPLOYMENT BLOCKED — missing critical vars: %s", ", ".join(result["missing_critical"]))
    else:
        logger.info("All critical variables are set ✅")
    logger.info("=" * 60)


def get_secrets_guide() -> list[dict]:
    """Return structured guide for HF Space Secrets setup."""
    guide = []
    for name, severity, fmt, desc in _VARS:
        val     = os.environ.get(name, "")
        present = bool(val.strip())
        guide.append({
            "name":        name,
            "required":    severity in ("CRITICAL", "HIGH"),
            "severity":    severity,
            "format":      fmt,
            "description": desc,
            "set":         present,
        })
    return guide
