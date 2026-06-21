---
name: Vision Foundation V1
description: Multimodal image upload support added to AI workspace — architecture, constraints, and integration points.
---

## Rule
All image binary data lives on disk. The `ai_uploads.db` (separate from `bot.db`) stores only paths, metadata, and cached captions — never blobs or base64.

## Architecture
- **image_validator.py** — PIL-based validation (size, ext, MIME cross-check, corruption detect); rejects anything that isn't a real PNG/JPEG/WEBP
- **image_storage.py** — UUID-named files in `control_panel/uploads/`; WEBP thumbnails (320px max) in `uploads/thumbs/`; SQLite at `database/ai_uploads.db`; `init_uploads_db()` called at import time
- **vision_engine.py** — HF Inference API, model `Salesforce/blip-image-captioning-large`; handles 401/429/503/timeout with Arabic-friendly error strings; `available` flag distinguishes provider-down from API-error
- **image_handler.py** — Orchestrator: validate → store → optional vision; `analyze_uploads_for_chat()` called at send time (not upload time); uses cached caption if `vision_status=done`

## Routes (prefix /ai)
- `POST /api/upload` — multipart upload, returns {upload_id, thumb_url, image_url}
- `GET /uploads/{id}/image` — serve full file, auth required
- `GET /uploads/{id}/thumb` — serve WEBP thumbnail, auth required
- `DELETE /api/upload/{id}` — soft-delete (disk + DB)
- `POST /api/chat` — extended to accept `image_ids: list[str]`; calls vision at send time, prepends captions to augmented_msg before process_chat()

## Template changes (ai_workspace.html)
- "+" button (`.xai-attach-btn`) at LEFT of input box opens dropdown
- Preview strip (`.xai-img-preview-strip`) above input box, hidden when empty
- Drag-over overlay (`.xai-drag-overlay`) activates on `ondragover`
- Hidden `<input type=file>` multi-select, accepts PNG/JPG/WEBP
- `_xPendingImages[]` holds {_tempId, upload_id, thumb_url, filename, ok, uploading}
- `_appendUser()` accepts 4th `images` arg; renders `.xai-msg-images` grid
- Lightbox on click: replaces /thumb with /image in src

## Why separate DB
`ai_uploads.db` is separate from `bot.db` to keep AI workspace concerns isolated from the bot's operational data. Both are in `extracted_project/database/`.

## How to apply
When adding new vision features: import from `image_handler`, not from `image_storage` or `vision_engine` directly. Use `analyze_uploads_for_chat(upload_ids)` to get captions for a list of already-uploaded images.
