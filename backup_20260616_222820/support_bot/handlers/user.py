from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from database.db import is_main_bot_user
from database.tickets import (
    create_ticket, add_message, get_user_open_ticket,
    get_user_tickets, get_ticket_messages
)
from config.settings import ADMIN_IDS, OWNER_ID
from utils.logger import system_logger, tickets_logger, error_logger

BTN_NEW    = "📩 New Ticket"
BTN_STATUS = "📋 My Tickets"


def _all_admins() -> list[int]:
    return list(set(ADMIN_IDS + ([OWNER_ID] if OWNER_ID else [])))


def _main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[BTN_NEW, BTN_STATUS]],
        resize_keyboard=True
    )


def _ticket_admin_keyboard(ticket_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📩 Reply",    callback_data=f"sup_reply_{ticket_id}_{user_id}"),
        InlineKeyboardButton("✅ Close",    callback_data=f"sup_close_{ticket_id}_{user_id}"),
    ]])


async def _notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str,
                          keyboard: InlineKeyboardMarkup | None = None):
    for admin_id in _all_admins():
        try:
            await context.bot.send_message(
                admin_id, text, parse_mode="HTML", reply_markup=keyboard
            )
        except Exception as exc:
            error_logger.error("Failed to notify admin %s: %s", admin_id, exc)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args or []

    if not is_main_bot_user(user.id):
        await update.message.reply_text(
            "🚫 <b>Access Denied</b>\n\n"
            "You must use the main bot first before accessing support.\n"
            "Please start the main bot and try again.",
            parse_mode="HTML"
        )
        system_logger.warning("Blocked unauthorized access: user_id=%s", user.id)
        return

    context.user_data.pop("state", None)

    open_ticket = get_user_open_ticket(user.id)
    if open_ticket:
        ticket_id = open_ticket["id"]
        await update.message.reply_text(
            f"👋 <b>Welcome back!</b>\n\n"
            f"You have an open ticket <b>#{ticket_id}</b>.\n"
            f"Any message you send will be added to it.\n\n"
            f"Use <b>{BTN_STATUS}</b> to see all your tickets.",
            parse_mode="HTML",
            reply_markup=_main_keyboard()
        )
    else:
        await update.message.reply_text(
            "👋 <b>Welcome to Support</b>\n\n"
            "How can we help you today?\n\n"
            f"Tap <b>{BTN_NEW}</b> to open a support ticket.",
            parse_mode="HTML",
            reply_markup=_main_keyboard()
        )


async def new_ticket_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not is_main_bot_user(user.id):
        await update.message.reply_text("🚫 Access denied. Please use the main bot first.")
        return

    open_ticket = get_user_open_ticket(user.id)
    if open_ticket:
        await update.message.reply_text(
            f"⚠️ You already have an open ticket <b>#{open_ticket['id']}</b>.\n\n"
            f"Any message you send will be added to it. "
            f"Please wait for an admin reply before opening a new one.",
            parse_mode="HTML",
            reply_markup=_main_keyboard()
        )
        return

    context.user_data["state"] = "creating_ticket"
    await update.message.reply_text(
        "📝 <b>New Support Ticket</b>\n\n"
        "Please describe your issue in detail.\n"
        "Send /cancel to go back.",
        parse_mode="HTML"
    )


async def create_ticket_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not is_main_bot_user(user.id):
        context.user_data.pop("state", None)
        await update.message.reply_text(
            "🚫 <b>Access Denied</b>\n\n"
            "You must use the main bot before accessing support.\n"
            "Please start the main bot and try again.",
            parse_mode="HTML"
        )
        system_logger.warning("Blocked ticket creation attempt: user_id=%s", user.id)
        return

    text = (update.message.text or "").strip()

    if not text:
        await update.message.reply_text("❌ Please send a text message.")
        return

    context.user_data.pop("state", None)

    ticket_id = create_ticket(
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        message=text
    )

    tickets_logger.info("Ticket #%s created by user_id=%s", ticket_id, user.id)

    uname = f"@{user.username}" if user.username else "no username"
    now   = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    admin_text = (
        f"🎫 <b>New Support Ticket #{ticket_id}</b>\n\n"
        f"👤 User: {user.first_name} ({uname})\n"
        f"🆔 User ID: <code>{user.id}</code>\n"
        f"🕐 Time: {now}\n\n"
        f"📝 <b>Message:</b>\n{text}\n\n"
        f"━━━━━━━━━━━━━━━━"
    )
    await _notify_admins(context, admin_text, _ticket_admin_keyboard(ticket_id, user.id))

    await update.message.reply_text(
        f"✅ <b>Ticket #{ticket_id} Created</b>\n\n"
        f"Your message has been sent to our support team.\n"
        f"We'll reply here as soon as possible.\n\n"
        f"You can continue sending messages — they'll all be added to this ticket.",
        parse_mode="HTML",
        reply_markup=_main_keyboard()
    )


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.message.text or "").strip()

    if not is_main_bot_user(user.id):
        await update.message.reply_text("🚫 Access denied. Please use the main bot first.")
        return

    open_ticket = get_user_open_ticket(user.id)
    if not open_ticket:
        await update.message.reply_text(
            f"💬 You don't have an open ticket.\n\nTap <b>{BTN_NEW}</b> to start one.",
            parse_mode="HTML",
            reply_markup=_main_keyboard()
        )
        return

    ticket_id = open_ticket["id"]
    add_message(ticket_id, user.id, "user", text)
    tickets_logger.info("User %s added message to ticket #%s", user.id, ticket_id)

    uname = f"@{user.username}" if user.username else "no username"
    admin_text = (
        f"💬 <b>New Message on Ticket #{ticket_id}</b>\n\n"
        f"👤 {user.first_name} ({uname})\n"
        f"🆔 <code>{user.id}</code>\n\n"
        f"📝 {text}\n\n"
        f"━━━━━━━━━━━━━━━━"
    )
    await _notify_admins(context, admin_text, _ticket_admin_keyboard(ticket_id, user.id))

    await update.message.reply_text("📨 Message added to your open ticket.")


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_main_bot_user(user.id):
        await update.message.reply_text(
            "🚫 <b>Access Denied</b>\n\n"
            "You must use the main bot before accessing support.",
            parse_mode="HTML"
        )
        return
    context.user_data.pop("state", None)
    await update.message.reply_text(
        "❌ Cancelled.",
        reply_markup=_main_keyboard()
    )


async def my_tickets_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not is_main_bot_user(user.id):
        await update.message.reply_text("🚫 Access denied.")
        return

    tickets = get_user_tickets(user.id, limit=10)
    if not tickets:
        await update.message.reply_text(
            "📭 You have no tickets yet.\n\n"
            f"Tap <b>{BTN_NEW}</b> to open one.",
            parse_mode="HTML",
            reply_markup=_main_keyboard()
        )
        return

    status_emoji = {"open": "🟢", "closed": "✅"}
    lines = ["📋 <b>Your Tickets</b>\n"]
    for t in tickets:
        emoji = status_emoji.get(t["status"], "⚪")
        date  = t["created_at"][:10]
        msgs  = get_ticket_messages(t["id"])
        lines.append(
            f"{emoji} <b>Ticket #{t['id']}</b> — {t['status'].upper()} — {date}\n"
            f"   💬 {len(msgs)} message(s)"
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_main_keyboard()
    )
