"""
🤖 مساعد التحديث الذكي
Arabic natural-language command router for the Developer Bot.
Parses Arabic text and routes to the correct action.
"""
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database.db import log_action
from utils.logger import action_logger

STATE_AI = "dv_ai_chat"

HELP_TEXT = (
    "🤖 <b>مساعد التحديث الذكي</b>\n\n"
    "أرسل أمرًا بالعربية وسأنفذه فورًا.\n\n"
    "<b>أمثلة على الأوامر:</b>\n"
    "• <code>أنشئ نسخة احتياطية</code>\n"
    "• <code>اعرض عدد المستخدمين</code>\n"
    "• <code>افحص المشروع</code>\n"
    "• <code>أعد تشغيل البوت الأساسي</code>\n"
    "• <code>أعد تشغيل جميع البوتات</code>\n"
    "• <code>اعرض آخر الأخطاء</code>\n"
    "• <code>اعرض حالة الخدمات</code>\n"
    "• <code>ابحث عن كلمة في المشروع</code>\n"
    "• <code>اعرض الملفات</code>\n"
    "• <code>وضع الطوارئ</code>\n\n"
    "💡 <i>أرسل أمرك الآن…</i>"
)


def _normalize_ar(text: str) -> str:
    """Normalize Arabic text: hamza variants → ا, remove tatweel and diacritics."""
    text = re.sub(r'[أإآٱ]', 'ا', text)
    text = re.sub(r'ى(?=\s|$)', 'ي', text)
    text = re.sub(r'[ـ]', '', text)
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)
    return text


# Intent patterns are matched against NORMALIZED text (applied at runtime)
# so hamza/tatweel/diacritic variants all resolve to the canonical form here.
INTENTS = [
    # Backup — create
    (r"(نسخة احتياطية|نسخ احتياطي|backup|احتياط|نسخ|خذ نسخة)",
     "dv_bkp_create", "إنشاء نسخة احتياطية"),

    # Health check
    (r"(افحص|فحص|health|سلامة|صحة المشروع|فحص المشروع|فحص النظام|تحقق|اختبر)",
     "dv_health", "فحص المشروع"),

    # Monitor / stats
    (r"(مستخدم|احصاء|احصائيات|مراقبة|monitor|تقرير النظام|عدد|كم مستخدم|اعرض الاحصاء)",
     "dv_monitor", "مراقبة النظام"),

    # Restart all
    (r"(جميع البوتات|كل البوتات|restart all|اعد تشغيل الكل|تشغيل الكل)",
     "dv_svc_restart_all_confirm", "إعادة تشغيل جميع البوتات"),

    # Restart main bot
    (r"(البوت الاساسي|الرئيسي|main bot|بوت الرئيسي)",
     "dv_svc_restart_main_confirm", "إعادة تشغيل البوت الأساسي"),

    # Restart support bot
    (r"(بوت الدعم|support bot|دعم فني)",
     "dv_svc_restart_support_confirm", "إعادة تشغيل بوت الدعم"),

    # Service status
    (r"(حالة الخدمات|حالة البوتات|service status|هل يعمل|الخدمات شغالة|حالة النظام)",
     "dv_svc_status", "حالة الخدمات"),

    # Errors / logs
    (r"(اخطاء|خطا|logs|سجل|error|آخر الاخطاء|اخر الاخطاء|سجل الاخطاء)",
     "dv_errors", "عرض سجل الأخطاء"),

    # Emergency
    (r"(طوارئ|emergency|استعادة طارئة|ازمة|وضع الطوارئ)",
     "dv_emergency", "وضع الطوارئ"),

    # File manager
    (r"(ملفات|مدير الملفات|files|استعرض|تصفح|اعرض الملفات)",
     "dv_files", "مدير الملفات"),

    # Search
    (r"(ابحث|بحث|search|ابحث عن|ابحث في)",
     "dv_search_prompt", "البحث في المشروع"),

    # Updates
    (r"(تحديث|updates|upload|رفع|تحديثات)",
     "dv_updates", "إدارة التحديثات"),

    # Backups list
    (r"(عرض النسخ|قائمة النسخ|list backups|اعرض النسخ|النسخ الاحتياطية)",
     "dv_bkp_list", "عرض النسخ الاحتياطية"),

    # Security log
    (r"(سجل الاجراءات|امان|security|نشاط|سجل النشاط)",
     "dv_sec_log", "سجل الأمان"),

    # Main menu
    (r"(القائمة الرئيسية|رجوع|menu|رئيسية|قائمة)",
     "dv_menu", "القائمة الرئيسية"),
]

# Compile all patterns once at module load for speed
_COMPILED_INTENTS = [
    (re.compile(pat, re.IGNORECASE | re.UNICODE), action, label)
    for pat, action, label in INTENTS
]


def ai_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 إرسال أمر", callback_data="dv_ai_prompt")],
        [InlineKeyboardButton("📋 قائمة الأوامر", callback_data="dv_ai_help")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="dv_menu")],
    ])


async def show_ai_menu(query, context):
    await query.edit_message_text(
        "🤖 <b>مساعد التحديث الذكي</b>\n\n"
        "أرسل أمرك بالعربية وسأوجهك إلى الإجراء المناسب.\n\n"
        "اضغط <b>إرسال أمر</b> لبدء الحوار، أو <b>قائمة الأوامر</b> لعرض الأمثلة.",
        parse_mode="HTML",
        reply_markup=ai_menu_kb(),
    )


async def show_ai_help(query, context):
    await query.edit_message_text(
        HELP_TEXT,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 إرسال أمر", callback_data="dv_ai_prompt")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="dv_ai")],
        ]),
    )


async def prompt_ai_input(query, context):
    context.user_data["dv_state"] = STATE_AI
    await query.edit_message_text(
        "💬 <b>أرسل أمرك بالعربية الآن…</b>\n\n"
        "مثال: <code>أنشئ نسخة احتياطية</code>\n"
        "أو: <code>افحص المشروع</code>\n\n"
        "<i>أرسل /cancel للإلغاء</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ إلغاء", callback_data="dv_ai")]
        ]),
    )


async def handle_ai_command(update, context):
    """Process Arabic text commands and route to correct action."""
    text = (update.message.text or "").strip()
    uid = update.effective_user.id

    context.user_data.pop("dv_state", None)
    log_action(uid, "ai_command", text[:200], "processing")

    # Normalize Arabic before matching so hamza/tatweel variants always hit
    normalized = _normalize_ar(text)

    matched_action = None
    matched_label = None
    for pattern, action, label in _COMPILED_INTENTS:
        if pattern.search(normalized):
            matched_action = action
            matched_label = label
            break

    if not matched_action:
        await update.message.reply_text(
            f"🤖 <b>لم أفهم الأمر</b>\n\n"
            f"الأمر المُرسل: <code>{text[:100]}</code>\n\n"
            "جرّب أمرًا من القائمة:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 قائمة الأوامر", callback_data="dv_ai_help")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="dv_ai")],
            ]),
        )
        log_action(uid, "ai_command", text[:200], "no_match")
        return

    action_logger.info("AI command matched: '%s' → %s", text, matched_action)
    log_action(uid, "ai_command", text[:200], f"→ {matched_action}")

    # Handle special confirm-style actions
    if matched_action.endswith("_confirm"):
        real_action = matched_action[:-8]  # strip _confirm
        await update.message.reply_text(
            f"🤖 <b>تم فهم الأمر:</b> <code>{matched_label}</code>\n\n"
            "⚠️ هذا الإجراء يتطلب تأكيدًا. اضغط زر التأكيد أدناه:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ تأكيد: {matched_label}", callback_data=real_action)],
                [InlineKeyboardButton("❌ إلغاء", callback_data="dv_menu")],
            ]),
        )
        return

    await update.message.reply_text(
        f"🤖 <b>تم فهم الأمر:</b> <code>{matched_label}</code>\n\n"
        "⏳ جارٍ التنفيذ…",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"▶️ فتح: {matched_label}", callback_data=matched_action)],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="dv_menu")],
        ]),
    )
