# ── PrimeDownloader / X Control Center ──────────────────────────────────────
# Runtime:  Python 3.12-slim
# Web:      FastAPI + Uvicorn on port 7860  (Hugging Face Spaces standard)
# Bots:     Main bot + Support bot run as background processes
# Database: SQLite (file-based, ephemeral on HF free tier)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# System dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg git curl && \
    rm -rf /var/lib/apt/lists/*

# Non-root user (Hugging Face requirement)
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy project files
COPY . .

# تثبيت الاعتمادات من المسار الصحيح
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r extracted_project/requirements.txt

# إنشاء مجلدات التشغيل وتعديل الصلاحيات
RUN mkdir -p database logs temp backups exports && \
    chown -R appuser:appuser /app

USER appuser

# ── Environment variables ─────────────────────────────────────────────────────
ENV CONTROL_PANEL_PORT=7860
ENV PROJECT_ROOT=/app

EXPOSE 7860

# ── Startup ───────────────────────────────────────────────────────────────────
# تشغيل البوت الأساسي وبوت الدعم ولوحة التحكم مباشرة بمساراتها الصحيحة
CMD bash -c "python extracted_project/bot.py & python extracted_project/support_bot/bot.py & python extracted_project/control_panel/server.py"

