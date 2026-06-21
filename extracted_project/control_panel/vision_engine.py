"""
Vision Engine — real image analysis via Hugging Face Inference API.
Model: Salesforce/blip-image-captioning-large (image-to-text, publicly available).
Gracefully degrades when the API is unavailable — NEVER fakes analysis results.
"""
import os
import logging
import httpx

logger = logging.getLogger(__name__)

_HF_API_BASE   = "https://api-inference.huggingface.co/models"
_PRIMARY_MODEL = "Salesforce/blip-image-captioning-large"
_HF_TIMEOUT    = 30.0   # seconds; BLIP cold-start can be slow


def _hf_headers() -> dict:
    token = os.getenv("HF_TOKEN", "").strip()
    h = {"Content-Type": "application/octet-stream"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def analyze_image(image_bytes: bytes, filename: str = "") -> dict:
    """
    Send image bytes to the Hugging Face Inference API and return a caption.

    Return schema:
        {
            "ok":        bool,
            "caption":   str | None,     # English caption from the model
            "provider":  str,
            "model":     str,
            "available": bool,           # False → provider unreachable
            "error":     str | None,     # Arabic-friendly error message
        }
    """
    _base = {
        "ok": False, "caption": None,
        "provider": "huggingface_inference_api",
        "model": _PRIMARY_MODEL,
        "available": True, "error": None,
    }

    if not image_bytes:
        return {**_base, "available": False, "error": "لم تُقدَّم بيانات الصورة."}

    url     = f"{_HF_API_BASE}/{_PRIMARY_MODEL}"
    headers = _hf_headers()

    try:
        resp = httpx.post(url, content=image_bytes, headers=headers, timeout=_HF_TIMEOUT)
    except httpx.TimeoutException:
        return {
            **_base,
            "available": True,
            "error": (
                f"انتهت مهلة الاتصال بـ Hugging Face ({_HF_TIMEOUT:.0f}s). "
                "قد يكون النموذج في حالة السبات — أعد المحاولة بعد 20 ثانية."
            ),
        }
    except httpx.RequestError as exc:
        return {
            **_base,
            "available": False,
            "error": f"تعذّر الاتصال بـ Hugging Face Inference API: {exc}",
        }

    # ── Handle HTTP status codes ──────────────────────────────────────────────
    sc = resp.status_code

    if sc == 401:
        return {
            **_base,
            "available": False,
            "error": "HF_TOKEN غير صالح أو منتهي الصلاحية (401 Unauthorized).",
        }

    if sc == 429:
        return {
            **_base,
            "available": True,
            "error": (
                "تجاوز حد معدل الطلبات على Hugging Face (429 Rate Limit). "
                "حاول لاحقاً أو أضف متغير البيئة HF_TOKEN للحصول على حصة أعلى."
            ),
        }

    if sc == 503:
        return {
            **_base,
            "available": True,
            "error": (
                "النموذج يُحمَّل حالياً على Hugging Face (503). "
                "أعد المحاولة بعد 20–30 ثانية."
            ),
        }

    if sc != 200:
        return {
            **_base,
            "available": True,
            "error": f"خطأ من خادم Hugging Face: HTTP {sc}. {resp.text[:200]}",
        }

    # ── Parse 200 response ────────────────────────────────────────────────────
    try:
        data = resp.json()
    except Exception as exc:
        return {
            **_base,
            "available": True,
            "error": f"تعذّر تحليل استجابة الـ API: {exc}",
        }

    # BLIP image-to-text: [{"generated_text": "a cat sitting on a mat"}]
    if isinstance(data, list) and data and "generated_text" in data[0]:
        caption = data[0]["generated_text"].strip()
        logger.info(
            f"Vision OK | model={_PRIMARY_MODEL} | file={filename!r} | "
            f"caption={caption[:80]!r}"
        )
        return {
            **_base,
            "ok": True,
            "caption": caption,
            "error": None,
        }

    # API returned an error body inside a 200
    if isinstance(data, dict) and "error" in data:
        err_msg = data["error"]
        if "loading" in err_msg.lower():
            return {
                **_base,
                "available": True,
                "error": (
                    f"النموذج لا يزال يُحمَّل: {err_msg}. "
                    "أعد المحاولة بعد 20 ثانية."
                ),
            }
        return {
            **_base,
            "available": True,
            "error": f"خطأ من نموذج Hugging Face: {err_msg}",
        }

    return {
        **_base,
        "available": True,
        "error": f"استجابة غير متوقعة من الـ API: {str(data)[:200]}",
    }
