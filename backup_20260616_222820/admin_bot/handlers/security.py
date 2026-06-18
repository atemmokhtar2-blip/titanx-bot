from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database.db import (
    get_banned_users, get_reports,
    get_suspicious_users, get_spam_reporters
)
from utils.logger import error_logger


def security_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚫 Banned Users",      callback_data="adm_sec_banned"),
            InlineKeyboardButton("📋 Abuse Reports",     callback_data="adm_sec_reports"),
        ],
        [
            InlineKeyboardButton("⚠️ Suspicious Activity", callback_data="adm_sec_susp"),
            InlineKeyboardButton("🔁 Spam Reporters",      callback_data="adm_sec_spam"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="adm_menu")],
    ])


async def show_security_menu(query, context):
    await query.edit_message_text(
        "🔒 <b>Security</b>\n\nMonitor and manage security:",
        parse_mode="HTML",
        reply_markup=security_menu_keyboard()
    )


async def show_banned_users(query, context):
    users = get_banned_users(limit=20)
    if not users:
        text = "🚫 <b>Banned Users</b>\n\n✅ No banned users."
    else:
        lines = [f"🚫 <b>Banned Users ({len(users)})</b>\n"]
        for u in users:
            uname = f"@{u['username']}" if u.get("username") else "no username"
            name  = u.get("first_name", "?")
            lines.append(
                f"• <code>{u['user_id']}</code> — {name} ({uname})"
            )
        text = "\n".join(lines)

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="adm_sec_banned")],
            [InlineKeyboardButton("⬅️ Back",    callback_data="adm_sec")],
        ])
    )


async def show_abuse_reports(query, context):
    reports = get_reports(status="open", limit=20)
    if not reports:
        text = "📋 <b>Abuse Reports</b>\n\n✅ No open reports."
    else:
        lines = [f"📋 <b>Open Abuse Reports ({len(reports)})</b>\n"]
        for r in reports:
            uname = f"@{r.get('username','?')}"
            plat  = r.get("platform", "?")
            date  = (r.get("created_at") or "")[:10]
            msg   = (r.get("message") or "")[:60]
            lines.append(
                f"🔴 <b>#{r['id']}</b> | {uname} | {plat} | {date}\n"
                f"   <i>{msg}</i>\n"
            )
        text = "\n".join(lines)

    if len(text) > 4000:
        text = text[:4000] + "\n…"
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="adm_sec_reports")],
            [InlineKeyboardButton("⬅️ Back",    callback_data="adm_sec")],
        ])
    )


async def show_suspicious_activity(query, context):
    users = get_suspicious_users(limit=10)
    if not users:
        text = "⚠️ <b>Suspicious Activity</b>\n\n✅ No suspicious activity detected."
    else:
        lines = [f"⚠️ <b>Suspicious Activity (last 24h)</b>\n"]
        for u in users:
            lines.append(
                f"• <code>{u['user_id']}</code> — <b>{u['cnt']}</b> downloads in 24h"
            )
        text = "\n".join(lines)

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="adm_sec_susp")],
            [InlineKeyboardButton("⬅️ Back",    callback_data="adm_sec")],
        ])
    )


async def show_spam_reporters(query, context):
    users = get_spam_reporters(limit=10)
    if not users:
        text = "🔁 <b>Spam Reporters</b>\n\n✅ No repeat reporters."
    else:
        lines = [f"🔁 <b>Repeat Reporters ({len(users)})</b>\n"]
        for u in users:
            uname = f"@{u.get('username','?')}"
            lines.append(
                f"• <code>{u['user_id']}</code> ({uname}) — <b>{u['cnt']}</b> reports"
            )
        text = "\n".join(lines)

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="adm_sec_spam")],
            [InlineKeyboardButton("⬅️ Back",    callback_data="adm_sec")],
        ])
    )
