from .db import db_cursor
from config.settings import ACHIEVEMENTS


def get_user_achievements(user_id: int) -> list[str]:
    with db_cursor() as c:
        c.execute("SELECT achievement_id FROM achievements WHERE user_id = ?", (user_id,))
        return [row["achievement_id"] for row in c.fetchall()]


def award_achievement(user_id: int, achievement_id: str) -> bool:
    with db_cursor() as c:
        try:
            c.execute("""
                INSERT OR IGNORE INTO achievements (user_id, achievement_id)
                VALUES (?, ?)
            """, (user_id, achievement_id))
            return c.rowcount > 0
        except Exception:
            return False


def check_and_award(user_id: int, downloads: int, referrals: int) -> list[str]:
    existing = get_user_achievements(user_id)
    newly_earned = []
    for ach in ACHIEVEMENTS:
        if ach["id"] in existing:
            continue
        if ach["condition"] == "downloads" and downloads >= ach["threshold"]:
            if award_achievement(user_id, ach["id"]):
                newly_earned.append(ach["name"])
        elif ach["condition"] == "referrals" and referrals >= ach["threshold"]:
            if award_achievement(user_id, ach["id"]):
                newly_earned.append(ach["name"])
    return newly_earned
