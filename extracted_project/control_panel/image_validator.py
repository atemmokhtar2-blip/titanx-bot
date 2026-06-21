"""
Image Validator — validates uploaded images for security and format correctness.
Checks: file size, extension, actual MIME type from image data, and integrity via PIL.
No business logic. Returns structured result only.
"""
import io
import os
import logging
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

MAX_SIZE_BYTES      = 10 * 1024 * 1024   # 10 MB hard limit
MAX_IMAGES_PER_MSG  = 5

ALLOWED_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})

# PIL format string → MIME type
_FORMAT_TO_MIME: dict[str, str] = {
    "PNG":  "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
}

# Extension (normalised) → expected MIME
_EXT_TO_MIME: dict[str, str] = {
    ".png":  "image/png",
    ".jpeg": "image/jpeg",   # .jpg also normalises to .jpeg
    ".webp": "image/webp",
}


def validate_image(file_bytes: bytes, original_filename: str) -> dict:
    """
    Validate an image upload.

    Returns:
        {
            "ok":        bool,
            "error":     str | None,      # human-readable rejection reason
            "mime_type": str | None,      # detected from file content
            "width":     int | None,
            "height":    int | None,
            "ext":       str | None,      # normalised (.jpg → .jpeg)
            "format":    str | None,      # PIL format (PNG / JPEG / WEBP)
        }
    """
    out: dict = {
        "ok": False, "error": None,
        "mime_type": None, "width": None, "height": None,
        "ext": None, "format": None,
    }

    # ── 1. Empty file ────────────────────────────────────────────────────────
    if not file_bytes:
        out["error"] = "الملف فارغ — لم يُرسَل أي بيانات."
        return out

    # ── 2. Size limit ────────────────────────────────────────────────────────
    size = len(file_bytes)
    if size > MAX_SIZE_BYTES:
        mb = size / (1024 * 1024)
        out["error"] = (
            f"حجم الصورة ({mb:.1f} MB) يتجاوز الحد الأقصى المسموح (10 MB). "
            f"يرجى ضغط الصورة أو اختيار صورة أصغر."
        )
        return out

    # ── 3. Extension check ───────────────────────────────────────────────────
    _, raw_ext = os.path.splitext(original_filename)
    ext = raw_ext.lower().strip()
    if not ext:
        out["error"] = "الملف لا يحتوي على امتداد — تعذّر تحديد نوعه."
        return out
    if ext == ".jpg":
        ext = ".jpeg"
    if ext not in _EXT_TO_MIME:
        out["error"] = (
            f"الامتداد '{raw_ext}' غير مدعوم. "
            "الصيغ المقبولة: PNG ، JPG ، JPEG ، WEBP فقط."
        )
        return out

    # ── 4. Real image integrity (PIL verify) ─────────────────────────────────
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            img.verify()   # Raises on corrupted / truncated data
    except UnidentifiedImageError:
        out["error"] = (
            "الملف ليس صورة حقيقية أو صيغته غير مدعومة (فشل التعرف عليه)."
        )
        return out
    except Exception as exc:
        out["error"] = f"الصورة تالفة أو مقطوعة: {exc}"
        return out

    # Re-open after verify() (it closes the buffer internally)
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            img_format = img.format      # "PNG", "JPEG", "WEBP", ...
            width, height = img.size
    except Exception as exc:
        out["error"] = f"تعذّر قراءة أبعاد الصورة: {exc}"
        return out

    # ── 5. Format whitelist ──────────────────────────────────────────────────
    mime_type = _FORMAT_TO_MIME.get(img_format or "")
    if not mime_type:
        out["error"] = (
            f"صيغة الصورة الفعلية '{img_format}' غير مدعومة. "
            "المدعوم: PNG ، JPEG ، WEBP فقط."
        )
        return out

    # ── 6. Extension ↔ content cross-check ──────────────────────────────────
    expected_mime = _EXT_TO_MIME.get(ext)
    if expected_mime and mime_type != expected_mime:
        out["error"] = (
            f"تضارب: الامتداد '{raw_ext}' لكن محتوى الملف هو {img_format}. "
            "الملف قد يكون مزيّفاً أو تالفاً."
        )
        return out

    out.update({
        "ok": True, "error": None,
        "mime_type": mime_type,
        "width": width, "height": height,
        "ext": ext, "format": img_format,
    })
    return out
