import asyncio
import logging
import sys
import os

# Put .pythonlibs FIRST and remove conflicting Nix-store versions
_pythonlibs = "/home/runner/workspace/.pythonlibs/lib/python3.12/site-packages"
_conflict_pkgs = [
    "typing-extensions", "typing_extensions",
    "pydantic", "pydantic_core",
    "starlette", "fastapi",
    "annotated_types", "annotated-types",
]
sys.path = [_pythonlibs] + [
    p for p in sys.path
    if not (p.startswith("/nix/store") and any(pkg in p for pkg in _conflict_pkgs))
]
sys.path.insert(1, os.path.dirname(__file__))

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters
)

from config.settings import BOT_TOKEN
from database.db import init_db
from utils.logger import system_logger

from handlers.start import (
    start_command, language_callback, verify_subscription_callback,
    help_command, settings_command, settings_callback, CHOOSING_LANGUAGE
)
from handlers.download import handle_url, download_callback
from handlers.profile import (
    profile_command, profile_callback, history_command, referral_command,
    points_command, redeem_callback, daily_command, wheel_command, wheel_callback,
    achievements_command, leaderboard_command, leaderboard_callback,
    goals_command, top_command
)
from handlers.feedback import (
    feedback_callback, handle_report_message,
    support_command, handle_support_message
)
from handlers.favorites import favorites_command, unfav_callback
from handlers.video_tools import video_tools_command, handle_video_file, video_tools_callback
from handlers.video_studio import (
    studio_command, handle_video_for_studio, studio_callback,
    handle_studio_text_input, STATE_VS_TEXT,
)
from handlers.logo import (
    logo_command, logo_callback, handle_logo_upload, init_logo_table,
    STATE_LOGO_UPLOAD,
)
from handlers.admin import (
    panel_command, admin_panel_callback, stats_command, users_command, topusers_command,
    broadcast_command, cancelbroadcast_command, ban_command, unban_command,
    reports_command, referrals_command, status_command,
    reply_command, report_reply_command, closereport_command,
    maintenance_command, rpt_inline_callback,
    addpoints_command, removepoints_command, search_command,
    admin_search_handler, activity_feed_command,
)
from workers.cleanup import cleanup_temp_files, cleanup_old_cache
from workers.heartbeat import run_heartbeat
from workers.crash_monitor import record_startup, record_crash

# All main-menu button texts (EN + AR) for routing
MENU_BUTTONS = {
    "📥 Download",    "📥 تحميل",
    "👤 Profile",     "👤 حسابي",
    "🎁 Referrals",   "🎁 الدعوات",
    "🏆 Achievements","🏆 الإنجازات",
    "⭐ Favorites",   "⭐ المفضلة",
    "📞 Support",     "📞 الدعم",
    "👑 Admin Panel", "👑 لوحة الإدارة",
    "🎰 Lucky Wheel", "🎰 عجلة الحظ",
}


async def _handle_pending_rpt_reply(update: Update, context) -> bool:
    """Send admin's inline-reply text to the report author and close the report."""
    pending = context.user_data.get("pending_rpt_reply")
    if not pending:
        return False
    from middlewares.auth import is_admin
    if not is_admin(update.effective_user.id):
        return False
    context.user_data.pop("pending_rpt_reply", None)
    report_id      = pending["report_id"]
    target_user_id = pending["target_user_id"]
    reply_text     = (update.message.text or "").strip()
    if not reply_text:
        return False
    from database.reports import reply_report, get_report_by_id
    from database.users import get_user
    from locales import t
    db_user = get_user(target_user_id)
    lang    = db_user.get("language", "en") if db_user else "en"
    try:
        await context.bot.send_message(
            target_user_id,
            t(lang, "report_reply_header") + reply_text,
            parse_mode="HTML"
        )
    except Exception:
        pass
    reply_report(report_id, update.effective_user.id, reply_text)
    admin_db  = get_user(update.effective_user.id)
    admin_lang = admin_db.get("language", "en") if admin_db else "en"
    await update.message.reply_text(t(admin_lang, "admin_report_replied_ok"))
    return True


async def message_router(update: Update, context):
    """Route text messages — handle admin pending replies, support/report replies, menu buttons, URLs."""
    if await _handle_pending_rpt_reply(update, context):
        return


async def past_init(application: Application):
    system_logger.info("Support Bot starting up..")


def build_application() -> Application:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set.")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .base_url("https://teleapi.com/bot")
        .post_init(past_init)
        .build()
    )
    return app
