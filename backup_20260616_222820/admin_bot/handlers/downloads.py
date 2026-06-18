from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database.db import (
    get_recent_downloads, get_incomplete_downloads,
    get_platform_stats, get_top_content
)
from utils.logger import error_logger

PLATFORM_EMOJI = {
    "youtube": "▶️", "tiktok": "🎵", "instagram": "📸",
    "twitter": "🐦", "facebook": "👤", "reddit": "🤖",
    "soundcloud": "🎵", "vimeo": "🎬",
}


def downloads_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🕐 Last 50 Downloads",  callback_data="adm_dl_last"),
            InlineKeyboardButton("⚠️ Incomplete",         callback_data="adm_dl_fail"),
        ],
        [
            InlineKeyboardButton("📊 By Platform",        callback_data="adm_dl_plat"),
            InlineKeyboardButton("🔥 Top Content",        callback_data="adm_dl_top"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="adm_menu")],
    ])


async def show_downloads_menu(query, context):
    await query.edit_message_text(
        "📥 <b>Downloads</b>\n\nSelect a view:",
        parse_mode="HTML",
        reply_markup=downloads_menu_keyboard()
    )


async def show_recent_downloads(query, context):
    rows = get_recent_downloads(limit=50)
    if not rows:
        text = "📥 <b>Last 50 Downloads</b>\n\n📭 No downloads yet."
    else:
        lines = [f"📥 <b>Last {len(rows)} Downloads</b>\n"]
        for d in rows[:50]:
            uname  = f"@{d['username']}" if d.get("username") else f"uid:{d['user_id']}"
            title  = (d.get("title") or "?")[:35]
            plat   = (d.get("platform") or "?").lower()
            emoji  = PLATFORM_EMOJI.get(plat, "🔗")
            date   = (d.get("created_at") or "")[:10]
            lines.append(f"{emoji} <b>{title}</b>  — {uname}  [{date}]")
        text = "\n".join(lines)

    if len(text) > 4000:
        text = text[:4000] + "\n…"
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="adm_dl_last")],
            [InlineKeyboardButton("⬅️ Back",    callback_data="adm_dl")],
        ])
    )


async def show_incomplete_downloads(query, context):
    rows = get_incomplete_downloads(limit=30)
    if not rows:
        text = "⚠️ <b>Incomplete / Failed Downloads</b>\n\n✅ None found."
    else:
        lines = [f"⚠️ <b>Incomplete Downloads ({len(rows)})</b>\n"]
        for d in rows:
            uname = f"@{d['username']}" if d.get("username") else f"uid:{d['user_id']}"
            url   = (d.get("url") or "?")[:50]
            date  = (d.get("created_at") or "")[:10]
            lines.append(f"• {uname} — <code>{url}</code> [{date}]")
        text = "\n".join(lines)

    if len(text) > 4000:
        text = text[:4000] + "\n…"
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_dl")]])
    )


async def show_platform_stats(query, context):
    rows = get_platform_stats()
    if not rows:
        text = "📊 <b>Downloads by Platform</b>\n\n📭 No data."
    else:
        total = sum(r["cnt"] for r in rows)
        lines = ["📊 <b>Downloads by Platform</b>\n"]
        for r in rows:
            plat  = (r.get("platform") or "unknown").lower()
            emoji = PLATFORM_EMOJI.get(plat, "🔗")
            pct   = (r["cnt"] / total * 100) if total else 0
            bar   = "█" * int(pct / 5)
            lines.append(f"{emoji} <b>{plat.capitalize()}</b>: {r['cnt']:,} ({pct:.1f}%) {bar}")
        lines.append(f"\n📦 Total: <b>{total:,}</b>")
        text = "\n".join(lines)

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="adm_dl_plat")],
            [InlineKeyboardButton("⬅️ Back",    callback_data="adm_dl")],
        ])
    )


async def show_top_content(query, context):
    rows = get_top_content(limit=20)
    if not rows:
        text = "🔥 <b>Most Downloaded Content</b>\n\n📭 No data."
    else:
        lines = ["🔥 <b>Most Downloaded Content</b>\n"]
        for i, r in enumerate(rows, 1):
            plat  = (r.get("platform") or "?").lower()
            emoji = PLATFORM_EMOJI.get(plat, "🔗")
            title = (r.get("title") or "?")[:40]
            lines.append(f"{i}. {emoji} <b>{title}</b> — {r['cnt']:,}x")
        text = "\n".join(lines)

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_dl")]])
    )
