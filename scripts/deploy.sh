#!/bin/bash
# TitanX — VM deployment entry point
# Starts all three services: Main Bot, Support Bot, Control Panel

export PYTHONPATH=/home/runner/workspace/.pythonlibs/lib/python3.12/site-packages:$PYTHONPATH

cd /home/runner/workspace/extracted_project

# Start Main Bot in background
python3 bot.py &
BOT_PID=$!
echo "[deploy] PrimeDownloader Bot started (PID $BOT_PID)"

# Start Support Bot in background
python3 support_bot/bot.py &
SUPPORT_PID=$!
echo "[deploy] Support Bot started (PID $SUPPORT_PID)"

# Start Control Panel in foreground (keeps container alive, serves port 5000)
echo "[deploy] Starting Control Panel on 0.0.0.0:5000 ..."
exec python3 /home/runner/workspace/extracted_project/control_panel/server.py
