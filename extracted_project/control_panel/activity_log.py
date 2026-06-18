"""
Shared in-memory activity log for TitanX Control Panel.
Import and call log() from any router to record events.
"""
from collections import deque
import datetime

_events: deque = deque(maxlen=200)

_ICONS = {
    "bot_start":      "▶️",
    "bot_stop":       "⏹️",
    "bot_restart":    "🔄",
    "backup_created": "💾",
    "backup_verified":"✅",
    "github_push":    "⬆️",
    "github_pull":    "⬇️",
    "user_login":     "🔑",
    "system_restart": "🔄",
    "file_saved":     "✏️",
    "file_deleted":   "🗑️",
    "error":          "❌",
    "warning":        "⚠️",
    "success":        "✅",
    "info":           "ℹ️",
    "recovery":       "🛠️",
    "health_check":   "🩺",
}

_COLORS = {
    "bot_start":      "green",
    "bot_stop":       "red",
    "bot_restart":    "yellow",
    "backup_created": "blue",
    "backup_verified":"green",
    "github_push":    "purple",
    "github_pull":    "cyan",
    "user_login":     "blue",
    "system_restart": "yellow",
    "file_saved":     "blue",
    "file_deleted":   "red",
    "error":          "red",
    "warning":        "yellow",
    "success":        "green",
    "info":           "blue",
    "recovery":       "orange",
    "health_check":   "cyan",
}

_counter = 0


def log(event_type: str, message: str, detail: str = "") -> None:
    global _counter
    _counter += 1
    now = datetime.datetime.now()
    _events.appendleft({
        "id": _counter,
        "type": event_type,
        "icon": _ICONS.get(event_type, "ℹ️"),
        "color": _COLORS.get(event_type, "blue"),
        "message": message,
        "detail": detail,
        "time": now.strftime("%H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
    })


def get_events(n: int = 50) -> list:
    return list(_events)[:n]


def clear() -> None:
    _events.clear()
