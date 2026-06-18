import asyncio
import os
import re
import tempfile
from typing import Callable, Optional
import yt_dlp
from config.settings import TEMP_DIR, MAX_FILE_SIZE_BYTES, DOWNLOAD_TIMEOUT
from utils.helpers import sanitize_filename, format_duration, format_size, get_platform
from utils.logger import download_logger, error_logger
from utils.ffmpeg_check import FFMPEG_AVAILABLE, FFMPEG_PATH


def _extract_info_sync(url: str) -> dict:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "ignoreerrors": False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


async def analyze_url(url: str) -> dict | None:
    try:
        loop = asyncio.get_event_loop()
        info = await asyncio.wait_for(
            loop.run_in_executor(None, _extract_info_sync, url),
            timeout=30
        )
        if not info:
            return None

        formats = info.get("formats", [])
        platform = get_platform(url)

        quality_map = {}
        for f in formats:
            height = f.get("height")
            vcodec = f.get("vcodec", "none")
            acodec = f.get("acodec", "none")
            fmt_id = f.get("format_id", "")
            filesize = f.get("filesize") or f.get("filesize_approx") or 0

            if vcodec == "none" or not height:
                continue

            label = f"{height}p"
            if label not in quality_map:
                quality_map[label] = {
                    "label": label,
                    "height": height,
                    "format_id": fmt_id,
                    "filesize": filesize,
                    "has_audio": acodec != "none",
                }
            else:
                existing = quality_map[label]
                if filesize > existing["filesize"]:
                    quality_map[label] = {
                        "label": label,
                        "height": height,
                        "format_id": fmt_id,
                        "filesize": filesize,
                        "has_audio": acodec != "none",
                    }

        qualities = sorted(quality_map.values(), key=lambda x: x["height"])

        thumbnail = info.get("thumbnail", "")
        duration_secs = info.get("duration", 0)

        return {
            "title": info.get("title", "Unknown"),
            "uploader": info.get("uploader") or info.get("channel") or "Unknown",
            "duration": format_duration(int(duration_secs)) if duration_secs else "Unknown",
            "duration_secs": duration_secs,
            "thumbnail": thumbnail,
            "platform": platform,
            "qualities": qualities,
            "url": url,
            "webpage_url": info.get("webpage_url", url),
        }
    except asyncio.TimeoutError:
        error_logger.error(f"Timeout analyzing: {url}")
        return None
    except Exception as e:
        error_logger.error(f"Error analyzing {url}: {e}")
        return None


def _download_sync(url: str, fmt_id: str, out_path: str,
                   progress_hook: Callable = None) -> str:
    ydl_opts = {
        "format": fmt_id,
        "outtmpl": out_path,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "merge_output_format": "mp4",
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }],
        "postprocessor_args": ["-c:a", "aac"],
    }
    if FFMPEG_PATH:
        ydl_opts["ffmpeg_location"] = FFMPEG_PATH
    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    candidates = [
        out_path + ".mp4",
        out_path,
        out_path.replace(".%(ext)s", ".mp4"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    base = out_path.replace(".%(ext)s", "")
    for ext in [".mp4", ".mkv", ".webm", ".avi"]:
        if os.path.exists(base + ext):
            return base + ext

    raise FileNotFoundError(f"Downloaded file not found for {url}")


def _download_audio_sync(url: str, out_path: str,
                         progress_hook: Callable = None) -> str:
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_path,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "writethumbnail": False,
        "embedthumbnail": False,
    }
    if FFMPEG_PATH:
        ydl_opts["ffmpeg_location"] = FFMPEG_PATH
    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    mp3_path = out_path.replace(".%(ext)s", ".mp3")
    if os.path.exists(mp3_path):
        return mp3_path

    base = out_path.replace(".%(ext)s", "")
    if os.path.exists(base + ".mp3"):
        return base + ".mp3"

    raise FileNotFoundError("MP3 file not found after conversion")


async def download_video(url: str, format_id: str, quality_label: str,
                         progress_callback: Callable = None) -> str | None:
    safe_name = sanitize_filename(f"video_{hash(url) % 100000}_{quality_label}")
    out_path = os.path.join(TEMP_DIR, f"{safe_name}.%(ext)s")

    last_percent = [0]
    loop = asyncio.get_running_loop()

    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed") or 0
            eta = d.get("eta") or 0
            if total and progress_callback:
                pct = int(downloaded / total * 100)
                if pct >= last_percent[0] + 5:
                    last_percent[0] = pct
                    data = {"pct": pct, "downloaded": downloaded,
                            "total": total, "speed": speed, "eta": eta}
                    loop.call_soon_threadsafe(
                        lambda d=data: loop.create_task(progress_callback(d))
                    )

    try:

        fmt = f"{format_id}+bestaudio/best[height<={quality_label.replace('p', '')}]"
        file_path = await asyncio.wait_for(
            loop.run_in_executor(None, _download_sync, url, fmt, out_path, hook),
            timeout=DOWNLOAD_TIMEOUT
        )

        if not os.path.exists(file_path):
            return None

        size = os.path.getsize(file_path)
        if size > MAX_FILE_SIZE_BYTES:
            os.remove(file_path)
            raise FileTooLargeError(size)

        download_logger.info(f"Downloaded video: {url} [{quality_label}] -> {file_path}")
        return file_path

    except FileTooLargeError:
        raise
    except Exception as e:
        error_logger.error(f"Video download error {url}: {e}")
        return None


async def download_audio(url: str, progress_callback: Callable = None) -> str | None:
    safe_name = sanitize_filename(f"audio_{hash(url) % 100000}")
    out_path = os.path.join(TEMP_DIR, f"{safe_name}.%(ext)s")

    last_percent = [0]
    loop = asyncio.get_running_loop()

    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed") or 0
            eta = d.get("eta") or 0
            if total and progress_callback:
                pct = int(downloaded / total * 100)
                if pct >= last_percent[0] + 5:
                    last_percent[0] = pct
                    data = {"pct": pct, "downloaded": downloaded,
                            "total": total, "speed": speed, "eta": eta}
                    loop.call_soon_threadsafe(
                        lambda d=data: loop.create_task(progress_callback(d))
                    )

    try:
        file_path = await asyncio.wait_for(
            loop.run_in_executor(None, _download_audio_sync, url, out_path, hook),
            timeout=DOWNLOAD_TIMEOUT
        )

        if not os.path.exists(file_path):
            return None

        size = os.path.getsize(file_path)
        if size > MAX_FILE_SIZE_BYTES:
            os.remove(file_path)
            raise FileTooLargeError(size)

        download_logger.info(f"Downloaded audio: {url} -> {file_path}")
        return file_path

    except FileTooLargeError:
        raise
    except Exception as e:
        error_logger.error(f"Audio download error {url}: {e}")
        return None


class FileTooLargeError(Exception):
    def __init__(self, size: int):
        self.size = size
        super().__init__(f"File too large: {format_size(size)}")
