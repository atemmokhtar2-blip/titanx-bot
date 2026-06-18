import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
CONTROL_PANEL_DIR = _HERE
EXTRACTED_DIR = os.path.dirname(_HERE)
PROJECT_ROOT = os.path.dirname(EXTRACTED_DIR)

if EXTRACTED_DIR not in sys.path:
    sys.path.insert(0, EXTRACTED_DIR)

OWNER_ID = int(os.getenv("OWNER_ID", "0")) if os.getenv("OWNER_ID", "0").isdigit() else 0
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SECRET_KEY = os.getenv("SESSION_SECRET", "titanx-control-panel-secret-key-2026")

_dev_domain   = os.getenv("REPLIT_DEV_DOMAIN", "")
_prod_domains = os.getenv("REPLIT_DOMAINS", "")
_prod_primary = _prod_domains.split(",")[0].strip() if _prod_domains else ""
if _dev_domain:
    PUBLIC_URL = f"https://{_dev_domain}"
elif _prod_primary:
    PUBLIC_URL = f"https://{_prod_primary}"
else:
    PUBLIC_URL = os.getenv("PUBLIC_URL", "")

MAIN_DB    = os.path.join(EXTRACTED_DIR, "database", "bot.db")
SUPPORT_DB = os.path.join(EXTRACTED_DIR, "database", "support.db")

LOGS_DIR    = os.path.join(EXTRACTED_DIR, "logs")
TEMP_DIR    = os.path.join(EXTRACTED_DIR, "temp")
BACKUPS_DIR = os.path.join(EXTRACTED_DIR, "backups")

PROTECTED_NAMES = {".env", "bot.db", "support.db"}
PROTECTED_DIRS  = {"database"}

MAX_VIEW_BYTES = 100_000
MAX_EDIT_BYTES = 200_000

BOT_SCRIPTS = {
    "main":    os.path.join(EXTRACTED_DIR, "bot.py"),
    "support": os.path.join(EXTRACTED_DIR, "support_bot", "bot.py"),
}

os.makedirs(TEMP_DIR,    exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR,    exist_ok=True)
