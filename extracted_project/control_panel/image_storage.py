"""
Image Storage — disk-based storage for AI workspace uploads.
Files stored on disk with UUID names. Only references tracked in SQLite.
FORBIDDEN: No binary blobs in database. No base64 in database.
"""
import io
import os
import uuid
import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Optional
from PIL import Image

logger = logging.getLogger(__name__)

THUMB_MAX_PX = 320   # max side for thumbnails


# ── Path helpers ──────────────────────────────────────────────────────────────

def _uploads_root() -> str:
    from .config import CONTROL_PANEL_DIR
    p = os.path.join(CONTROL_PANEL_DIR, "uploads")
    os.makedirs(p, exist_ok=True)
    return p


def _thumbs_dir() -> str:
    p = os.path.join(_uploads_root(), "thumbs")
    os.makedirs(p, exist_ok=True)
    return p


def _db_path() -> str:
    from .config import EXTRACTED_DIR
    db_dir = os.path.join(EXTRACTED_DIR, "database")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "ai_uploads.db")


# ── Database ──────────────────────────────────────────────────────────────────

@contextmanager
def _db():
    conn = sqlite3.connect(_db_path(), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_uploads_db() -> None:
    with _db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS ai_uploads (
                id              TEXT PRIMARY KEY,
                filename        TEXT NOT NULL,
                stored_name     TEXT NOT NULL,
                stored_path     TEXT NOT NULL,
                thumb_path      TEXT,
                mime_type       TEXT NOT NULL,
                file_size       INTEGER NOT NULL,
                width           INTEGER,
                height          INTEGER,
                session_id      TEXT,
                vision_caption  TEXT,
                vision_status   TEXT NOT NULL DEFAULT 'pending',
                vision_model    TEXT,
                vision_error    TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                used_in_message INTEGER NOT NULL DEFAULT 0,
                deleted         INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_ai_uploads_session  ON ai_uploads(session_id);
            CREATE INDEX IF NOT EXISTS idx_ai_uploads_created  ON ai_uploads(created_at);
            CREATE INDEX IF NOT EXISTS idx_ai_uploads_deleted  ON ai_uploads(deleted);
            CREATE INDEX IF NOT EXISTS idx_ai_uploads_used     ON ai_uploads(used_in_message);
        """)
    logger.info("ai_uploads DB initialised.")


# Initialise on first import
try:
    init_uploads_db()
except Exception as _e:
    logger.error(f"ai_uploads DB init failed at import time: {_e}")


# ── Store ─────────────────────────────────────────────────────────────────────

def store_image(
    file_bytes:        bytes,
    original_filename: str,
    mime_type:         str,
    width:             int,
    height:            int,
    ext:               str,
    session_id:        Optional[str] = None,
) -> dict:
    """
    Write image + thumbnail to disk; record reference in DB.
    Returns the full upload record as a dict.
    """
    upload_id   = str(uuid.uuid4())
    stored_name = f"{upload_id}{ext}"
    stored_path = os.path.join(_uploads_root(), stored_name)
    thumb_name  = f"{upload_id}_thumb.webp"
    thumb_path  = os.path.join(_thumbs_dir(), thumb_name)

    # Write original file
    with open(stored_path, "wb") as fh:
        fh.write(file_bytes)

    # Generate thumbnail
    _thumb_ok = False
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            img.thumbnail((THUMB_MAX_PX, THUMB_MAX_PX), Image.LANCZOS)
            img.save(thumb_path, "WEBP", quality=82, optimize=True)
        _thumb_ok = True
    except Exception as exc:
        logger.warning(f"Thumbnail generation failed for {upload_id}: {exc}")
        thumb_path = None

    record = {
        "id":            upload_id,
        "filename":      original_filename,
        "stored_name":   stored_name,
        "stored_path":   stored_path,
        "thumb_path":    thumb_path,
        "mime_type":     mime_type,
        "file_size":     len(file_bytes),
        "width":         width,
        "height":        height,
        "session_id":    session_id,
        "vision_status": "pending",
        "created_at":    datetime.utcnow().isoformat(),
    }

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO ai_uploads
                (id, filename, stored_name, stored_path, thumb_path,
                 mime_type, file_size, width, height, session_id, vision_status, created_at)
            VALUES
                (:id, :filename, :stored_name, :stored_path, :thumb_path,
                 :mime_type, :file_size, :width, :height, :session_id, :vision_status, :created_at)
            """,
            record,
        )

    logger.info(
        f"Stored upload {upload_id}: {original_filename} "
        f"({len(file_bytes)} bytes, {width}×{height}, thumb={'ok' if _thumb_ok else 'failed'})"
    )
    return record


# ── Retrieve ──────────────────────────────────────────────────────────────────

def get_upload(upload_id: str) -> Optional[dict]:
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM ai_uploads WHERE id=? AND deleted=0", (upload_id,)
        ).fetchone()
    return dict(row) if row else None


def get_image_bytes(upload_id: str) -> Optional[bytes]:
    rec = get_upload(upload_id)
    if not rec:
        return None
    fp = rec["stored_path"]
    if not os.path.exists(fp):
        logger.warning(f"Stored file missing for upload {upload_id}: {fp}")
        return None
    with open(fp, "rb") as fh:
        return fh.read()


def get_thumb_bytes(upload_id: str) -> Optional[bytes]:
    rec = get_upload(upload_id)
    if not rec:
        return None
    tp = rec.get("thumb_path")
    if tp and os.path.exists(tp):
        with open(tp, "rb") as fh:
            return fh.read()
    # Fall back to full image
    return get_image_bytes(upload_id)


def get_thumb_mime(upload_id: str) -> str:
    rec = get_upload(upload_id)
    if not rec:
        return "image/webp"
    tp = rec.get("thumb_path")
    if tp and os.path.exists(tp):
        return "image/webp"
    return rec.get("mime_type", "image/jpeg")


# ── Update ────────────────────────────────────────────────────────────────────

def update_vision_result(upload_id: str, result: dict) -> None:
    if result.get("ok"):
        with _db() as conn:
            conn.execute(
                """UPDATE ai_uploads
                   SET vision_status='done', vision_caption=?, vision_model=?, vision_error=NULL
                   WHERE id=?""",
                (result.get("caption"), result.get("model"), upload_id),
            )
    else:
        status = "unavailable" if not result.get("available", True) else "failed"
        with _db() as conn:
            conn.execute(
                """UPDATE ai_uploads
                   SET vision_status=?, vision_error=?, vision_model=?
                   WHERE id=?""",
                (status, result.get("error"), result.get("model"), upload_id),
            )


def mark_used(upload_id: str) -> None:
    with _db() as conn:
        conn.execute(
            "UPDATE ai_uploads SET used_in_message=1 WHERE id=?", (upload_id,)
        )


# ── Delete ────────────────────────────────────────────────────────────────────

def delete_upload(upload_id: str) -> bool:
    rec = get_upload(upload_id)
    if not rec:
        return False
    for path_key in ("stored_path", "thumb_path"):
        fp = rec.get(path_key)
        if fp and os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception as exc:
                logger.warning(f"Could not delete file {fp}: {exc}")
    with _db() as conn:
        conn.execute("UPDATE ai_uploads SET deleted=1 WHERE id=?", (upload_id,))
    logger.info(f"Deleted upload {upload_id} ({rec['filename']})")
    return True


# ── Cleanup ───────────────────────────────────────────────────────────────────

def cleanup_orphaned_uploads(max_age_hours: int = 48) -> int:
    """
    Remove uploads that were never attached to a sent message and are older
    than max_age_hours. Called periodically to prevent disk accumulation.
    """
    with _db() as conn:
        rows = conn.execute(
            """SELECT id FROM ai_uploads
               WHERE used_in_message=0
                 AND deleted=0
                 AND created_at < datetime('now', ?)""",
            (f"-{max_age_hours} hours",),
        ).fetchall()

    count = sum(1 for row in rows if delete_upload(row["id"]))
    if count:
        logger.info(f"Orphaned-upload cleanup: removed {count} file(s).")
    return count
