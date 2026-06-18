import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
OWNER_ID = int(os.getenv("OWNER_ID", "0")) if os.getenv("OWNER_ID", "").isdigit() else 0

SUPPORT_BOT_USERNAME = os.getenv("SUPPORT_BOT_USERNAME", "").strip().lstrip("@")
ADMIN_BOT_USERNAME   = os.getenv("ADMIN_BOT_USERNAME",  "").strip().lstrip("@")

DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "bot.db")
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp")
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "300"))
RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", "10"))
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "5"))

CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "86400"))
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "1000"))

POINTS_REGISTRATION    = 10
POINTS_DOWNLOAD        = 1
POINTS_REFERRAL        = 50
POINTS_FIRST_DOWNLOAD  = 50
POINTS_DAILY           = 5

REWARDS = {
    100: {"name": "Extra Downloads Pack", "type": "downloads", "value": 10},
    250: {"name": "VIP Day", "type": "vip", "value": 1},
    500: {"name": "VIP Week", "type": "vip", "value": 7},
}

ACHIEVEMENTS = [
    {"id": "first_download", "name": "🏆 First Download", "condition": "downloads", "threshold": 1},
    {"id": "ten_downloads", "name": "🏆 10 Downloads", "condition": "downloads", "threshold": 10},
    {"id": "fifty_downloads", "name": "🏆 50 Downloads", "condition": "downloads", "threshold": 50},
    {"id": "hundred_downloads", "name": "🏆 100 Downloads", "condition": "downloads", "threshold": 100},
    {"id": "first_referral", "name": "🏆 First Referral", "condition": "referrals", "threshold": 1},
    {"id": "five_referrals", "name": "🏆 5 Referrals", "condition": "referrals", "threshold": 5},
    {"id": "fifty_referrals", "name": "🏆 50 Referrals", "condition": "referrals", "threshold": 50},
]

COMMUNITY_GOALS = [
    {"threshold": 500, "reward": "Unlock TikTok Support"},
    {"threshold": 1000, "reward": "Unlock Instagram Support"},
    {"threshold": 2500, "reward": "Unlock Twitter/X Support"},
    {"threshold": 5000, "reward": "Unlock HD Priority Queue"},
]

SUPPORTED_DOMAINS = [
    "youtube.com", "youtu.be",
    "facebook.com", "fb.watch", "fb.com",
    "pinterest.com", "pin.it",
]

BROADCAST_BATCH_SIZE = 30
BROADCAST_DELAY = 0.3

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
