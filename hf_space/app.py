import os
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

app = FastAPI()

# ══════════════════════════════════════════════════════════════════
#  PHASE 4 — PROJECT MEMORY V1
# ══════════════════════════════════════════════════════════════════

PROJECT_MEMORY = {
    "project_name": "X Control Center",
    "version": "v5.0",
    "components": [
        {"key": "main_bot",          "name": "البوت الرئيسي (PrimeDownloader)", "file": "extracted_project/bot.py",                                    "desc": "بوت تيليغرام للتحميل، الملفات الشخصية، الإنجازات، ومحرر الفيديو",   "tech": "python-telegram-bot 21.6", "port": None},
        {"key": "support_bot",       "name": "بوت الدعم",                        "file": "extracted_project/support_bot/bot.py",                         "desc": "نظام تذاكر الدعم الفني للمستخدمين",                                   "tech": "python-telegram-bot 21.6", "port": None},
        {"key": "control_panel",     "name": "لوحة التحكم",                      "file": "extracted_project/control_panel/app.py",                       "desc": "لوحة FastAPI لإدارة النظام، المستخدمين، البثوث والملفات",            "tech": "FastAPI + Uvicorn",        "port": 5000},
        {"key": "github_system",     "name": "نظام GitHub",                      "file": "extracted_project/control_panel/routers/github_router.py",     "desc": "مزامنة الكود مع GitHub، نشر التحديثات",                               "tech": "GitPython",                "port": None},
        {"key": "backup_system",     "name": "نظام النسخ الاحتياطية",            "file": "extracted_project/control_panel/routers/backups.py",            "desc": "أخذ نسخ احتياطية للقاعدة وإدارتها",                                   "tech": "Python + ZIP",             "port": None},
        {"key": "update_center",     "name": "مركز التحديثات",                   "file": "extracted_project/control_panel/routers/updates.py",           "desc": "تحديث الكود من GitHub وإعادة تشغيل الخدمات",                          "tech": "GitPython + subprocess",   "port": None},
        {"key": "monitoring_center", "name": "مركز المراقبة",                    "file": "extracted_project/control_panel/routers/system.py",            "desc": "مراقبة صحة النظام، CPU، RAM، القرص",                                  "tech": "psutil",                   "port": None},
        {"key": "ai_workspace",      "name": "مساحة عمل الذكاء الاصطناعي",      "file": "extracted_project/control_panel/routers/ai_workspace.py",      "desc": "7 نقاط نهاية AI للمساعدة والتحليل",                                   "tech": "FastAPI",                  "port": None},
    ]
}

# ══════════════════════════════════════════════════════════════════
#  PHASE 1 — ERROR ANALYZER
# ══════════════════════════════════════════════════════════════════

ERROR_PATTERNS = [
    {
        "patterns": ["502","bad gateway","nginx"],
        "cause": "الخادم أُعيد تشغيله أو تعطّل — Nginx لا يجد العملية على المنفذ 5000",
        "file": "extracted_project/control_panel/server.py",
        "fix": "أعد تشغيل workflow «TitanX Control Panel» في Replit",
        "actions": ["تحقق من أن workflow «TitanX Control Panel» يعمل","تأكد من أن المنفذ 5000 مفتوح وغير مستخدم","راجع سجلات uvicorn في لوحة Replit","تأكد من صحة PYTHONPATH في scripts/start.sh"]
    },
    {
        "patterns": ["sidebar","الشريط الجانبي","قائمة جانبية","navbar"],
        "cause": "خطأ في JavaScript أو فشل تحميل ملف CSS/JS الجانبي",
        "file": "extracted_project/control_panel/static/js/app.js",
        "fix": "امسح كاش المتصفح (Ctrl+Shift+R) أو تحقق من console المتصفح",
        "actions": ["افتح أدوات المطور → Console وابحث عن خطأ JavaScript","تأكد من تحميل /static/js/app.js بشكل صحيح","تحقق من صحة ملف templates/layout.html","جرب Hard Refresh: Ctrl+Shift+R"]
    },
    {
        "patterns": ["github","sync failed","مزامنة","push","pull","git"],
        "cause": "فشل مصادقة GitHub أو مشكلة في GITHUB_TOKEN",
        "file": "extracted_project/control_panel/routers/github_router.py",
        "fix": "تحقق من صحة GITHUB_TOKEN في Replit Secrets",
        "actions": ["تحقق من وجود GITHUB_TOKEN في Replit Secrets","تأكد من أن التوكن لديه صلاحية repo","تحقق من اسم المستودع في إعدادات GitHub Router","اختبر الاتصال: git remote -v في terminal"]
    },
    {
        "patterns": ["backup","نسخة احتياطية","نسخ احتياطية","backup failed"],
        "cause": "مشكلة في مسار حفظ النسخة أو نقص في مساحة القرص",
        "file": "extracted_project/control_panel/routers/backups.py",
        "fix": "تحقق من وجود مجلد extracted_project/backups/ وصلاحياته",
        "actions": ["تأكد من وجود مجلد backups/: ls extracted_project/backups/","تحقق من مساحة القرص المتاحة","راجع صلاحيات الكتابة على المجلد","تحقق من سجلات الخطأ في لوحة التحكم"]
    },
    {
        "patterns": ["bot stopped","البوت توقف","bot offline","conflict","polling"],
        "cause": "تعارض بين نسختين من البوت تعملان في آنٍ واحد",
        "file": "extracted_project/bot.py",
        "fix": "أوقف جميع العمليات القديمة وأعد تشغيل workflow البوت فقط مرة واحدة",
        "actions": ["أوقف workflow «PrimeDownloader Bot»","انتظر 10 ثوانٍ حتى تنتهي جلسة Telegram القديمة","أعد تشغيل workflow مرة واحدة فقط","تأكد من عدم تشغيل أي نسخة أخرى للبوت خارج Replit"]
    },
    {
        "patterns": ["database","db error","sqlite","قاعدة بيانات","no such table"],
        "cause": "قاعدة البيانات غير موجودة أو تالفة",
        "file": "extracted_project/database/bot.db",
        "fix": "شغّل سكريبت التهيئة أو أعد تشغيل البوت ليُنشئ الجداول تلقائياً",
        "actions": ["أعد تشغيل البوت — يُنشئ الجداول عند بدء التشغيل","تأكد من وجود مجلد extracted_project/database/","تحقق من صلاحيات الكتابة","إذا تالفة: احذف bot.db وأعد تشغيل البوت"]
    },
    {
        "patterns": ["port","address already in use","eaddrinuse","منفذ","5000","8080"],
        "cause": "المنفذ مشغول بعملية أخرى لم تُوقف بشكل صحيح",
        "file": "scripts/start.sh",
        "fix": "نفّذ: fuser -k 5000/tcp ثم أعد تشغيل الـ workflow",
        "actions": ["في Replit Shell: fuser -k 5000/tcp","انتظر 5 ثوانٍ ثم أعد تشغيل workflow","تأكد من عدم تشغيل أكثر من نسخة واحدة","تحقق من لوحة Workflows في Replit"]
    },
    {
        "patterns": ["import error","module not found","importerror","modulenotfounderror"],
        "cause": "حزمة Python مفقودة أو PYTHONPATH غير صحيح",
        "file": "pyproject.toml",
        "fix": "تأكد من أن PYTHONPATH يشير إلى .pythonlibs أولاً في start.sh",
        "actions": ["تحقق من scripts/start.sh: export PYTHONPATH=.pythonlibs/...","شغّل: pip install -r requirements.txt","تأكد من تطابق إصدار Python مع pyproject.toml","راجع .pythonlibs/lib/python3.12/site-packages/"]
    },
    {
        "patterns": ["401","unauthorized","403","forbidden","غير مصرح","access denied"],
        "cause": "جلسة منتهية الصلاحية أو رمز وصول غير صحيح",
        "file": "extracted_project/control_panel/auth.py",
        "fix": "سجّل الخروج وأعد الدخول عبر /panel?k=TOKEN",
        "actions": ["اذهب إلى /logout ثم /panel","تحقق من صحة SESSION_SECRET في Replit Secrets","تأكد من رمز الوصول ACCESS_TOKEN في auth.py","امسح كوكيز المتصفح وحاول مجدداً"]
    },
    {
        "patterns": ["timeout","انتهت المهلة","timed out","connection refused","connection error"],
        "cause": "انتهت مهلة الاتصال بالخادم أو الخادم غير متاح",
        "file": "extracted_project/control_panel/server.py",
        "fix": "تحقق من أن الخادم يعمل وأن المنفذ 5000 مرتبط بـ 0.0.0.0",
        "actions": ["تحقق من حالة workflow «TitanX Control Panel»","تأكد من host=0.0.0.0 في server.py","اختبر محلياً: curl http://localhost:5000/healthz","تحقق من الجدار الناري في إعدادات Replit"]
    },
]

# ══════════════════════════════════════════════════════════════════
#  PHASE 2 — PROJECT ASSISTANT
# ══════════════════════════════════════════════════════════════════

ASSISTANT_KB = [
    {
        "keywords": ["مراقبة","monitoring","realtime","لحظي","live"],
        "title": "إضافة مراقبة لحظية",
        "explanation": "يمكن إضافة مراقبة لحظية للنظام عبر Server-Sent Events لعرض CPU/RAM/Disk في الوقت الفعلي.",
        "plan": ["إنشاء endpoint /system/stream في system.py يبث بيانات psutil كل ثانية","استخدام SSE (EventSource) في JavaScript لاستقبال البيانات","إضافة مكوّنات ApexCharts لعرض الرسوم البيانية","إضافة تنبيهات عند تجاوز CPU 90% أو RAM 85%","ربط التنبيهات بالبوت لإرسال رسائل فورية"],
        "files": ["routers/system.py","static/js/app.js","templates/dashboard.html"],
        "difficulty": "متوسطة — 2-3 ساعات عمل"
    },
    {
        "keywords": ["github","تكامل","integration","مزامنة تلقائية","auto sync","webhook"],
        "title": "تحسين تكامل GitHub",
        "explanation": "يمكن تحسين نظام GitHub بإضافة webhooks للمزامنة التلقائية عند push، وعرض تاريخ commits.",
        "plan": ["إضافة endpoint /github/webhook لاستقبال أحداث GitHub","التحقق من توقيع HMAC للـ webhook","إضافة منطق auto-pull عند استقبال push event","عرض آخر 10 commits في واجهة GitHub","إضافة خيار rollback للـ commit السابق"],
        "files": ["routers/github_router.py","templates/github.html","static/js/app.js"],
        "difficulty": "متوسطة — 3-4 ساعات عمل"
    },
    {
        "keywords": ["backup","نسخ","احتياطي","جدولة","scheduled","تلقائي"],
        "title": "تحسين نظام النسخ الاحتياطية",
        "explanation": "يمكن تحسين النسخ الاحتياطية بإضافة جدولة تلقائية وإرسالها إلى Telegram.",
        "plan": ["إضافة APScheduler لجدولة نسخ احتياطية يومية","إرسال ملف النسخة الاحتياطية إلى البوت عبر Telegram","إضافة ضغط ZIP متعدد المستويات","عرض قائمة النسخ مع حجمها وتاريخها","إضافة خيار استعادة نسخة بنقرة واحدة"],
        "files": ["routers/backups.py","templates/backups.html","bot.py"],
        "difficulty": "منخفضة-متوسطة — 2 ساعات عمل"
    },
    {
        "keywords": ["logs","سجلات","logging","سجل","تتبع"],
        "title": "تحسين نظام السجلات",
        "explanation": "يمكن تحسين عرض السجلات بإضافة فلترة حسب المستوى وبحث نصي فوري.",
        "plan": ["تحديث logs_router.py لدعم فلترة INFO/WARNING/ERROR","إضافة بحث نصي فوري في السجلات","إضافة ترقيم صفحات للسجلات الطويلة","تلوين الأخطاء باللون الأحمر والتحذيرات بالأصفر","إضافة زر تحديث تلقائي كل 5 ثوانٍ"],
        "files": ["routers/logs_router.py","templates/logs.html","static/css/style.css"],
        "difficulty": "منخفضة — 1-2 ساعة عمل"
    },
    {
        "keywords": ["user","مستخدم","مستخدمين","إدارة","ban","حظر","إحصاء"],
        "title": "تحسين إدارة المستخدمين",
        "explanation": "يمكن تعزيز نظام المستخدمين بإضافة إحصاءات استخدام وفلترة متقدمة.",
        "plan": ["إضافة رسم بياني لنشاط المستخدمين اليومي","إضافة فلترة حسب: نشط/محظور/جديد","إضافة تصدير قائمة المستخدمين كـ CSV","إضافة نظام نقاط/مستويات للمستخدمين","ربط إجراءات الحظر/الرفع بإشعارات فورية للبوت"],
        "files": ["routers/users.py","templates/users.html","database/bot.db"],
        "difficulty": "متوسطة — 3 ساعات عمل"
    },
    {
        "keywords": ["broadcast","بث","إرسال","رسالة جماعية","إشعار"],
        "title": "تحسين نظام البث",
        "explanation": "يمكن تحسين البث بإضافة جدولة الرسائل ومعاينة قبل الإرسال.",
        "plan": ["إضافة معاينة الرسالة قبل إرسالها","إضافة جدولة البث في وقت محدد","إضافة إحصاءات التسليم (أُرسل/فشل/محظور)","دعم الأزرار التفاعلية InlineKeyboard","إضافة قوالب رسائل جاهزة"],
        "files": ["routers/broadcast.py","templates/broadcast.html","bot.py"],
        "difficulty": "منخفضة-متوسطة — 2 ساعات عمل"
    },
]

# ══════════════════════════════════════════════════════════════════
#  PHASE 3 — UPDATE PLANNER
# ══════════════════════════════════════════════════════════════════

ROADMAPS = [
    {
        "keywords": ["live monitoring","مراقبة","monitoring","لحظي","realtime","dashboard"],
        "title": "🖥️ نظام المراقبة اللحظية",
        "description": "مراقبة كاملة للنظام مع رسوم بيانية حية وتنبيهات فورية",
        "components": ["SSE Server في FastAPI","Chart.js / ApexCharts لرسوم CPU/RAM/Disk","نظام تنبيهات عتبة (Threshold Alerts)","ربط التنبيهات بالبوت","لوحة عرض العمليات الجارية"],
        "complexity": "⭐⭐⭐ متوسطة",
        "order": ["المرحلة 1: إنشاء /system/stream endpoint (SSE)","المرحلة 2: بناء مكوّنات الرسوم البيانية","المرحلة 3: نظام التنبيهات مع عتبات قابلة للضبط","المرحلة 4: ربط التنبيهات بإشعارات Telegram","المرحلة 5: اختبار الأداء تحت الحمل"]
    },
    {
        "keywords": ["ai workspace","ذكاء اصطناعي","ai","مساحة عمل","workspace"],
        "title": "🤖 مساحة عمل الذكاء الاصطناعي V2",
        "description": "تحسين مساحة العمل الحالية بإضافة نماذج متعددة ومحادثة تفاعلية",
        "components": ["دعم نماذج Hugging Face المتعددة","واجهة محادثة تفاعلية (Chat UI)","تحليل الأكواد البرمجية","اقتراحات تلقائية للتحسينات","تاريخ المحادثات المحفوظ"],
        "complexity": "⭐⭐⭐⭐ عالية",
        "order": ["المرحلة 1: تصميم واجهة Chat في templates","المرحلة 2: دمج Hugging Face Inference API","المرحلة 3: إضافة ذاكرة السياق للمحادثة","المرحلة 4: إضافة أدوات تحليل الكود","المرحلة 5: اختبار ونشر"]
    },
    {
        "keywords": ["emergency recovery","طوارئ","استعادة","recovery","rollback"],
        "title": "🚨 نظام الاسترداد الطارئ",
        "description": "نظام استعادة كامل عند حدوث أعطال حرجة مع rollback تلقائي",
        "components": ["لقطات تلقائية قبل كل تحديث (Auto-Snapshot)","نظام Rollback بنقرة واحدة","اختبار صحة النظام بعد الاستعادة","إشعارات فورية عبر Telegram","سجل تدقيق لكل عملية استعادة"],
        "complexity": "⭐⭐⭐⭐ عالية",
        "order": ["المرحلة 1: بناء نظام Snapshot قبل التحديثات","المرحلة 2: واجهة اختيار نسخة الاستعادة","المرحلة 3: منطق الاستعادة مع التحقق","المرحلة 4: نظام اختبار ما بعد الاستعادة","المرحلة 5: ربط التنبيهات وسجل التدقيق"]
    },
    {
        "keywords": ["security","أمان","حماية","2fa","firewall","تشفير"],
        "title": "🔐 تعزيز الأمان",
        "description": "إضافة طبقات حماية متقدمة للوحة التحكم والبوتات",
        "components": ["المصادقة الثنائية (2FA) عبر Telegram","تقييد IP للوصول للوحة","تشفير جلسات أقوى","سجل محاولات الدخول","إشعار فوري عند دخول غير مألوف"],
        "complexity": "⭐⭐⭐ متوسطة",
        "order": ["المرحلة 1: إضافة سجل محاولات الدخول","المرحلة 2: تطبيق IP Allowlist","المرحلة 3: بناء 2FA عبر Telegram Bot","المرحلة 4: تشفير الجلسات بمفتاح أقوى","المرحلة 5: اختبار الاختراق الأساسي"]
    },
    {
        "keywords": ["notification","إشعار","telegram alert","تنبيه","alert"],
        "title": "🔔 نظام الإشعارات الذكية",
        "description": "نظام إشعارات شامل يُرسل تنبيهات فورية عبر Telegram لكل حدث مهم",
        "components": ["تنبيهات أخطاء النظام الحرجة","إشعارات دخول مستخدم جديد","تقارير يومية/أسبوعية تلقائية","تنبيهات استهلاك الموارد","لوحة ضبط الإشعارات"],
        "complexity": "⭐⭐ منخفضة-متوسطة",
        "order": ["المرحلة 1: بناء NotificationService مركزي","المرحلة 2: ربطه بجميع routers الموجودة","المرحلة 3: إضافة قوالب رسائل جاهزة","المرحلة 4: لوحة ضبط في واجهة المستخدم","المرحلة 5: اختبار جميع الأحداث"]
    },
]

# ══════════════════════════════════════════════════════════════════
#  API ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@app.post("/api/analyze")
async def analyze(request: Request):
    body = await request.json()
    text = body.get("text", "").lower()
    if not text.strip():
        return JSONResponse({"ok": False, "error": "empty"})
    matched = [p for p in ERROR_PATTERNS if any(k in text for k in p["patterns"])]
    return JSONResponse({"ok": True, "results": matched})

@app.post("/api/assistant")
async def assistant(request: Request):
    body = await request.json()
    text = body.get("text", "").lower()
    if not text.strip():
        return JSONResponse({"ok": False, "error": "empty"})
    matched = [item for item in ASSISTANT_KB if any(k.lower() in text for k in item["keywords"])]
    return JSONResponse({"ok": True, "results": matched, "memory": PROJECT_MEMORY})

@app.post("/api/planner")
async def planner(request: Request):
    body = await request.json()
    text = body.get("text", "").lower()
    if not text.strip():
        return JSONResponse({"ok": False, "error": "empty"})
    matched = [r for r in ROADMAPS if any(k.lower() in text for k in r["keywords"])]
    return JSONResponse({"ok": True, "results": matched})

@app.get("/api/memory")
async def memory():
    return JSONResponse({"ok": True, "memory": PROJECT_MEMORY})

# ══════════════════════════════════════════════════════════════════
#  FULL HTML PAGE (single-file, no external deps beyond CDN fonts)
# ══════════════════════════════════════════════════════════════════

HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>X AI Core — V1</title>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Tajawal',sans-serif}
:root{
  --bg:#07080f;--bg2:#0d1117;--card:rgba(13,14,26,.95);
  --border:rgba(99,102,241,.22);--accent:#8b5cf6;--accent2:#6366f1;
  --text:#e2e8f0;--muted:#64748b;--green:#86efac;--yellow:#fcd34d;
}
html,body{background:linear-gradient(135deg,var(--bg) 0%,var(--bg2) 100%);color:var(--text);min-height:100vh;overflow-x:hidden}

/* ── scrollbar ── */
::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-track{background:rgba(15,15,30,.4)}
::-webkit-scrollbar-thumb{background:rgba(99,102,241,.35);border-radius:3px}

/* ── header ── */
.header{text-align:center;padding:44px 20px 32px;background:linear-gradient(180deg,rgba(99,102,241,.12),transparent);border-bottom:1px solid var(--border);animation:fadeDown .6s ease}
.header h1{font-size:2.5rem;font-weight:900;background:linear-gradient(135deg,#818cf8,#a78bfa,#c084fc);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-0.5px}
.header p{color:var(--muted);margin-top:8px;font-size:1rem}
.ver{display:inline-block;background:linear-gradient(135deg,var(--accent2),var(--accent));color:#fff;padding:4px 16px;border-radius:20px;font-size:.78rem;font-weight:700;margin-top:12px;letter-spacing:1px}

/* ── tabs ── */
.tabs{display:flex;justify-content:center;gap:4px;padding:20px 20px 0;flex-wrap:wrap}
.tab{padding:10px 22px;border-radius:10px 10px 0 0;border:1px solid transparent;border-bottom:none;cursor:pointer;color:var(--muted);font-weight:600;font-size:.92rem;transition:all .25s;background:rgba(15,15,30,.5)}
.tab.active,.tab:hover{color:#a78bfa;background:var(--card);border-color:var(--border)}
.tab.active{border-bottom:2px solid var(--accent)}

/* ── panels ── */
.container{max-width:960px;margin:0 auto;padding:0 16px 60px}
.panel{display:none;animation:fadeUp .35s ease}
.panel.active{display:block}
.panel-inner{background:var(--card);border:1px solid var(--border);border-radius:0 16px 16px 16px;padding:28px}

/* ── inputs ── */
.field-label{font-size:.82rem;font-weight:700;color:var(--accent2);text-transform:uppercase;letter-spacing:.7px;margin-bottom:8px}
textarea,input[type=text]{width:100%;background:rgba(10,10,25,.9);border:1px solid var(--border);color:var(--text);border-radius:12px;padding:14px 16px;font-size:.97rem;resize:vertical;transition:border-color .25s;font-family:'Tajawal',sans-serif}
textarea:focus,input[type=text]:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(139,92,246,.12)}
textarea{min-height:110px}
.hint{color:var(--muted);font-size:.82rem;margin-top:6px}

/* ── button ── */
.btn{display:inline-flex;align-items:center;gap:8px;background:linear-gradient(135deg,var(--accent2),var(--accent));color:#fff;border:none;border-radius:12px;padding:12px 28px;font-size:1rem;font-weight:700;cursor:pointer;transition:all .25s;margin-top:16px;font-family:'Tajawal',sans-serif}
.btn:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(99,102,241,.35)}
.btn:active{transform:translateY(0)}

/* ── results ── */
.results{margin-top:22px}
.result-card{background:rgba(10,10,22,.8);border:1px solid var(--border);border-radius:14px;padding:22px;margin-bottom:14px;animation:fadeUp .3s ease}
.r-header{font-size:1.1rem;font-weight:800;color:#a78bfa;border-bottom:1px solid var(--border);padding-bottom:12px;margin-bottom:16px}
.r-row{margin-bottom:12px}
.r-label{font-size:.78rem;font-weight:700;color:var(--accent2);letter-spacing:.8px;text-transform:uppercase;margin-bottom:5px}
.r-val{color:#cbd5e1;font-size:.94rem;line-height:1.7}
.r-val ol,.r-val ul{padding-right:20px}
.r-val li{margin-bottom:4px}
.code{background:rgba(0,0,0,.4);border:1px solid rgba(99,102,241,.18);border-radius:7px;padding:4px 12px;font-family:monospace;color:#818cf8;font-size:.85rem;direction:ltr;display:inline-block}
.fix{background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.2);border-radius:9px;padding:9px 14px;color:var(--green);font-weight:600}
.diff{display:inline-block;background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.25);color:var(--yellow);padding:4px 14px;border-radius:20px;font-weight:700;font-size:.88rem}
.files{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
.ftag{background:rgba(99,102,241,.12);border:1px solid rgba(99,102,241,.22);color:#818cf8;padding:3px 11px;border-radius:7px;font-size:.8rem;font-family:monospace;direction:ltr}
.empty{background:rgba(245,158,11,.07);border:1px solid rgba(245,158,11,.18);border-radius:11px;padding:16px 20px;color:var(--yellow);text-align:center;font-weight:600;margin-top:16px}
.loading{color:var(--muted);text-align:center;padding:20px;animation:pulse 1.4s infinite}

/* ── memory grid ── */
.mem-badge{background:linear-gradient(135deg,rgba(99,102,241,.18),rgba(139,92,246,.12));border:1px solid var(--border);border-radius:9px;padding:10px 16px;color:#a78bfa;font-size:.87rem;font-weight:600;margin-bottom:18px}
.mem-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.mem-card{background:rgba(10,10,22,.8);border:1px solid var(--border);border-radius:12px;padding:16px;transition:border-color .25s,transform .2s}
.mem-card:hover{border-color:rgba(139,92,246,.45);transform:translateY(-2px)}
.mc-name{color:#c4b5fd;font-weight:700;font-size:.93rem;margin-bottom:6px}
.mc-desc{color:#94a3b8;font-size:.82rem;line-height:1.5;margin-bottom:8px}
.mc-file{color:var(--accent2);font-size:.75rem;font-family:monospace;direction:ltr;margin-bottom:3px}
.mc-tech{color:var(--muted);font-size:.75rem}
.port{background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.25);color:var(--green);padding:1px 8px;border-radius:8px;font-size:.73rem;font-family:monospace}
.db-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px}

/* ── footer ── */
.footer{text-align:center;padding:24px;color:var(--muted);font-size:.82rem;border-top:1px solid var(--border);margin-top:20px}

/* ── animations ── */
@keyframes fadeDown{from{opacity:0;transform:translateY(-16px)}to{opacity:1;transform:translateY(0)}}
@keyframes fadeUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.45}}

/* ── mobile ── */
@media(max-width:600px){
  .header h1{font-size:1.8rem}
  .tab{padding:8px 14px;font-size:.85rem}
  .panel-inner{padding:18px}
}
</style>
</head>
<body>

<div class="header">
  <h1>⚡ X AI Core</h1>
  <p>المساعد الذكي للوحة تحكم X Control Center</p>
  <div class="ver">V1 &nbsp;·&nbsp; Phases 1–4</div>
</div>

<div class="container">
  <div class="tabs">
    <div class="tab active" onclick="switchTab('analyzer')">🔍 محلل الأخطاء</div>
    <div class="tab" onclick="switchTab('assistant')">🤖 مساعد المشروع</div>
    <div class="tab" onclick="switchTab('planner')">🗺️ مخطط التحديثات</div>
    <div class="tab" onclick="switchTab('memory')">🧠 ذاكرة المشروع</div>
  </div>

  <!-- PHASE 1 -->
  <div class="panel active" id="panel-analyzer">
    <div class="panel-inner">
      <div class="field-label">رسالة الخطأ أو وصف المشكلة</div>
      <textarea id="inp-analyzer" placeholder="مثال: HTTP 502 Bad Gateway&#10;أو: البوت توقف فجأة&#10;أو: GitHub sync failed"></textarea>
      <div class="hint">أمثلة: HTTP 502 · البوت توقف · GitHub sync failed · backup failed · Port already in use</div>
      <button class="btn" onclick="runAnalyzer()">🔍 تحليل المشكلة</button>
      <div class="results" id="out-analyzer"></div>
    </div>
  </div>

  <!-- PHASE 2 -->
  <div class="panel" id="panel-assistant">
    <div class="panel-inner">
      <div class="field-label">سؤالك حول المشروع</div>
      <textarea id="inp-assistant" placeholder="مثال: كيف أضيف مراقبة لحظية؟&#10;أو: كيف أحسّن تكامل GitHub؟&#10;أو: كيف أحسّن النسخ الاحتياطية؟"></textarea>
      <div class="hint">أمثلة: مراقبة لحظية · تكامل GitHub · النسخ الاحتياطية · إدارة المستخدمين · نظام البث</div>
      <button class="btn" onclick="runAssistant()">🤖 احصل على الإجابة</button>
      <div class="results" id="out-assistant"></div>
    </div>
  </div>

  <!-- PHASE 3 -->
  <div class="panel" id="panel-planner">
    <div class="panel-inner">
      <div class="field-label">الميزة أو التحديث المطلوب</div>
      <textarea id="inp-planner" placeholder="مثال: أنشئ نظام مراقبة لحظية&#10;أو: أضف نظام استرداد طارئ&#10;أو: حسّن نظام الأمان"></textarea>
      <div class="hint">أمثلة: مراقبة لحظية · استرداد طارئ · نظام الأمان · إشعارات ذكية · AI Workspace</div>
      <button class="btn" onclick="runPlanner()">🗺️ إنشاء خارطة الطريق</button>
      <div class="results" id="out-planner"></div>
    </div>
  </div>

  <!-- PHASE 4 -->
  <div class="panel" id="panel-memory">
    <div class="panel-inner">
      <div id="out-memory"><div class="loading">جارٍ تحميل ذاكرة المشروع…</div></div>
    </div>
  </div>

  <div class="footer">X AI Core V1 &nbsp;·&nbsp; Phases 1–4 &nbsp;·&nbsp; X Control Center v5.0</div>
</div>

<script>
/* ── Tab switching ── */
function switchTab(id){
  document.querySelectorAll('.tab').forEach((t,i)=>{
    const ids=['analyzer','assistant','planner','memory'];
    t.classList.toggle('active',ids[i]===id);
  });
  document.querySelectorAll('.panel').forEach(p=>{
    p.classList.toggle('active',p.id==='panel-'+id);
  });
  if(id==='memory') loadMemory();
}

/* ── Generic fetch ── */
async function post(url,text){
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
  return r.json();
}

/* ── Render helpers ── */
function card(headerIcon,header,rows){
  const inner=rows.map(([label,html])=>`
    <div class="r-row">
      <div class="r-label">${label}</div>
      <div class="r-val">${html}</div>
    </div>`).join('');
  return `<div class="result-card"><div class="r-header">${headerIcon} ${header}</div>${inner}</div>`;
}
function ol(items){return '<ol>'+items.map(i=>`<li>${i}</li>`).join('')+'</ol>'}
function ul(items){return '<ul>'+items.map(i=>`<li>${i}</li>`).join('')+'</ul>'}
function tags(items){return '<div class="files">'+items.map(f=>`<span class="ftag">${f}</span>`).join('')+'</div>'}
function empty(msg){return `<div class="empty">${msg}</div>`}

/* ── Phase 1 ── */
async function runAnalyzer(){
  const txt=document.getElementById('inp-analyzer').value.trim();
  const out=document.getElementById('out-analyzer');
  if(!txt){out.innerHTML=empty('⚠️ الرجاء إدخال وصف المشكلة أو رسالة الخطأ');return}
  out.innerHTML='<div class="loading">⏳ جارٍ التحليل…</div>';
  const data=await post('/api/analyze',txt);
  if(!data.ok||!data.results.length){
    out.innerHTML=empty('🔍 لم يُعثر على نمط مطابق. جرّب: HTTP 502 · البوت توقف · GitHub sync failed');
    return;
  }
  out.innerHTML=data.results.map(m=>card('🔍','التشخيص',[
    ['📌 السبب المحتمل', m.cause],
    ['📁 الملف المرجّح', `<span class="code">${m.file}</span>`],
    ['💡 الإصلاح المقترح', `<div class="fix">${m.fix}</div>`],
    ['⚡ الإجراءات الموصى بها', ol(m.actions)],
  ])).join('');
}
document.getElementById('inp-analyzer').addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter')runAnalyzer()});

/* ── Phase 2 ── */
async function runAssistant(){
  const txt=document.getElementById('inp-assistant').value.trim();
  const out=document.getElementById('out-assistant');
  if(!txt){out.innerHTML=empty('⚠️ الرجاء إدخال سؤالك حول المشروع');return}
  out.innerHTML='<div class="loading">⏳ جارٍ البحث في قاعدة المعرفة…</div>';
  const data=await post('/api/assistant',txt);
  if(!data.ok||!data.results.length){
    out.innerHTML=empty('🤖 لم أجد إجابة مباشرة. جرّب: مراقبة لحظية · تكامل GitHub · النسخ الاحتياطية');
    return;
  }
  const mem=data.memory;
  const badge=`<div class="mem-badge">🧠 الذاكرة نشطة: ${mem.project_name} ${mem.version} — ${mem.components.length} مكوّنات</div>`;
  out.innerHTML=badge+data.results.map(item=>card('🤖',item.title,[
    ['📖 الشرح', item.explanation],
    ['🗺️ خطة التنفيذ', ol(item.plan)],
    ['📁 الملفات المطلوبة', tags(item.files)],
    ['⚙️ تقدير الصعوبة', `<span class="diff">${item.difficulty}</span>`],
  ])).join('');
}
document.getElementById('inp-assistant').addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter')runAssistant()});

/* ── Phase 3 ── */
async function runPlanner(){
  const txt=document.getElementById('inp-planner').value.trim();
  const out=document.getElementById('out-planner');
  if(!txt){out.innerHTML=empty('⚠️ الرجاء وصف الميزة أو التحديث المطلوب');return}
  out.innerHTML='<div class="loading">⏳ جارٍ إنشاء خارطة الطريق…</div>';
  const data=await post('/api/planner',txt);
  if(!data.ok||!data.results.length){
    out.innerHTML=empty('🗺️ لم أجد خارطة مطابقة. جرّب: مراقبة لحظية · استرداد طارئ · نظام الأمان');
    return;
  }
  out.innerHTML=data.results.map(rm=>card(rm.title.split(' ')[0],rm.title.slice(rm.title.indexOf(' ')+1),[
    ['📋 الوصف', rm.description],
    ['🧩 المكوّنات المطلوبة', ul(rm.components)],
    ['⚙️ التعقيد التقديري', `<span class="diff">${rm.complexity}</span>`],
    ['📐 الترتيب الموصى به', ol(rm.order)],
  ])).join('');
}
document.getElementById('inp-planner').addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter')runPlanner()});

/* ── Phase 4 ── */
async function loadMemory(){
  const out=document.getElementById('out-memory');
  out.innerHTML='<div class="loading">⏳ جارٍ تحميل الذاكرة…</div>';
  const data=await fetch('/api/memory').then(r=>r.json());
  const m=data.memory;
  const cards=m.components.map(c=>`
    <div class="mem-card">
      <div class="mc-name">${c.name}${c.port?` <span class="port">:${c.port}</span>`:''}</div>
      <div class="mc-desc">${c.desc}</div>
      <div class="mc-file">${c.file}</div>
      <div class="mc-tech">🔧 ${c.tech}</div>
    </div>`).join('');
  out.innerHTML=`
    <div class="r-header">🧠 ذاكرة المشروع — ${m.project_name} ${m.version}</div>
    <div class="r-row">
      <div class="r-label">🛠️ التقنيات</div>
      <div class="db-row">
        <span class="ftag">Backend: Python 3.12 + FastAPI</span>
        <span class="ftag">Bots: python-telegram-bot 21.6</span>
        <span class="ftag">Media: yt-dlp + ffmpeg</span>
      </div>
    </div>
    <div class="r-row" style="margin-top:16px">
      <div class="r-label">🧩 المكوّنات (${m.components.length})</div>
      <div class="mem-grid" style="margin-top:10px">${cards}</div>
    </div>`;
}

/* Auto-load memory on first open */
window.addEventListener('DOMContentLoaded',()=>loadMemory());
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content=HTML)


if __name__ == "__main__":
    port = int(os.environ.get("GRADIO_SERVER_PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
