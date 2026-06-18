"""TitanX Control Panel — main entry point.

Running `python main.py` (or clicking the Replit Run button) starts
the FastAPI control panel server on port 5000.
"""
import sys
import os

# ── Path bootstrap (must happen before any project imports) ────────────────
_here        = os.path.dirname(os.path.abspath(__file__))
_pythonlibs  = os.path.join(_here, ".pythonlibs", "lib", "python3.12", "site-packages")
_extracted   = os.path.join(_here, "extracted_project")

# .pythonlibs must be first so installed packages shadow the older Nix-store versions
for _p in (_pythonlibs, _extracted):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import uvicorn  # noqa: E402
from control_panel.app import app  # noqa: E402

if __name__ == "__main__":
    port = int(os.getenv("CONTROL_PANEL_PORT", "5000"))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True,
    )
