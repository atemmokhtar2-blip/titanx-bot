# ── PrimeDownloader / X Control Center ──────────────────────────────────────
# Runtime:  Python 3.12-slim
# Web:      FastAPI + Uvicorn on port 7860  (Hugging Face Spaces standard)
# Bots:     Main bot + Support bot run as background processes
# Database: SQLite (file-based, ephemeral on HF free tier)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# System dependencies
# - ffmpeg:  required by yt-dlp for video/audio merging and conversion
# - git:     required by GitPython (github_router)
# - curl:    useful for health-check probes
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg git curl && \
    rm -rf /var/lib/apt/lists/*

# Non-root user (Hugging Face requirement)
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create required runtime directories
RUN mkdir -p database logs temp backups exports && \
    chown -R appuser:appuser /app

USER appuser

# ── Environment variables ─────────────────────────────────────────────────────
# Web panel port — HF Spaces requires 7860
ENV CONTROL_PANEL_PORT=7860
# Set by HF Space Secrets (do NOT hardcode here):
#   TELEGRAM_BOT_TOKEN
#   SUPPORT_BOT_TOKEN
#   OWNER_ID
#   ADMIN_IDS
#   SUPPORT_BOT_USERNAME
#   REQUIRED_CHANNEL
#   SESSION_SECRET

EXPOSE 7860

# ── Startup ───────────────────────────────────────────────────────────────────
# Runs Main Bot + Support Bot as background processes,
# then starts the Control Panel in the foreground on port 7860.
# deploy.sh already handles this orchestration.
CMD ["bash", "-c", \
     "python bot.py & python support_bot/bot.py & python control_panel/server.py"]
