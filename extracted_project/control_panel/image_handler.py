"""
Image Handler — orchestrates validate → store → vision analyze.
Entry point for the AI workspace upload pipeline.
"""
import logging
from typing import Optional

from .image_validator import validate_image, MAX_IMAGES_PER_MSG
from .image_storage import (
    store_image, get_upload, get_image_bytes,
    update_vision_result, mark_used,
)
from .vision_engine import analyze_image

logger = logging.getLogger(__name__)


def handle_upload(
    file_bytes:        bytes,
    original_filename: str,
    session_id:        Optional[str] = None,
    run_vision:        bool = False,
) -> dict:
    """
    Full upload pipeline: validate → store → (optional) vision.

    Returns:
        {
            "ok":         bool,
            "error":      str | None,
            "upload_id":  str | None,
            "thumb_url":  str | None,
            "image_url":  str | None,
            "width":      int | None,
            "height":     int | None,
            "filename":   str,
            "file_size":  int,
            "mime_type":  str | None,
            "vision":     dict | None,
        }
    """
    # ── Step 1: Validate ─────────────────────────────────────────────────────
    val = validate_image(file_bytes, original_filename)
    if not val["ok"]:
        return {
            "ok": False, "error": val["error"],
            "upload_id": None, "thumb_url": None, "image_url": None,
            "width": None, "height": None,
            "filename": original_filename, "file_size": len(file_bytes),
            "mime_type": None, "vision": None,
        }

    # ── Step 2: Store ────────────────────────────────────────────────────────
    try:
        record = store_image(
            file_bytes=file_bytes,
            original_filename=original_filename,
            mime_type=val["mime_type"],
            width=val["width"],
            height=val["height"],
            ext=val["ext"],
            session_id=session_id,
        )
    except Exception as exc:
        logger.error(f"store_image failed for {original_filename!r}: {exc}")
        return {
            "ok": False,
            "error": f"فشل حفظ الصورة على القرص: {exc}",
            "upload_id": None, "thumb_url": None, "image_url": None,
            "width": val["width"], "height": val["height"],
            "filename": original_filename, "file_size": len(file_bytes),
            "mime_type": val["mime_type"], "vision": None,
        }

    uid       = record["id"]
    thumb_url = f"/ai/uploads/{uid}/thumb"
    image_url = f"/ai/uploads/{uid}/image"

    result = {
        "ok": True, "error": None,
        "upload_id": uid,
        "thumb_url": thumb_url,
        "image_url": image_url,
        "width": val["width"], "height": val["height"],
        "filename": original_filename,
        "file_size": len(file_bytes),
        "mime_type": val["mime_type"],
        "vision": None,
    }

    # ── Step 3: Vision (optional at upload time) ─────────────────────────────
    if run_vision:
        result["vision"] = _run_vision(uid, file_bytes)

    return result


def _run_vision(upload_id: str, file_bytes: Optional[bytes] = None) -> dict:
    if file_bytes is None:
        file_bytes = get_image_bytes(upload_id)
    if not file_bytes:
        return {"ok": False, "error": "الصورة غير موجودة على القرص.", "available": False}
    vision = analyze_image(file_bytes)
    update_vision_result(upload_id, vision)
    return vision


def analyze_uploads_for_chat(upload_ids: list) -> list:
    """
    Analyze a list of upload_ids for inclusion in a chat message.
    Uses cached caption if already analysed; runs fresh otherwise.
    Returns one result dict per image.
    """
    results = []
    for uid in upload_ids[:MAX_IMAGES_PER_MSG]:
        rec = get_upload(uid)
        if not rec:
            results.append({
                "upload_id": uid, "ok": False,
                "error": "الصورة غير موجودة أو محذوفة.",
                "caption": None, "filename": None,
                "width": None, "height": None,
            })
            continue

        # Use cached caption
        if rec.get("vision_status") == "done" and rec.get("vision_caption"):
            results.append({
                "upload_id": uid, "ok": True,
                "caption": rec["vision_caption"],
                "filename": rec["filename"],
                "width": rec.get("width"),
                "height": rec.get("height"),
                "error": None,
            })
            mark_used(uid)
            continue

        # If a previous attempt was marked unavailable, skip re-trying
        if rec.get("vision_status") == "unavailable":
            results.append({
                "upload_id": uid, "ok": False,
                "caption": None,
                "filename": rec["filename"],
                "width": rec.get("width"),
                "height": rec.get("height"),
                "error": rec.get("vision_error") or "خدمة الرؤية غير متاحة حالياً.",
            })
            mark_used(uid)
            continue

        # Fresh analysis
        img_bytes = get_image_bytes(uid)
        vision    = _run_vision(uid, img_bytes)
        mark_used(uid)
        results.append({
            "upload_id": uid,
            "ok":        vision.get("ok", False),
            "caption":   vision.get("caption"),
            "filename":  rec["filename"],
            "width":     rec.get("width"),
            "height":    rec.get("height"),
            "error":     vision.get("error"),
        })
    return results
