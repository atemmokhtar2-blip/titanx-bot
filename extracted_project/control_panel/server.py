"""Entry point for TitanX Control Panel."""
import sys
import os

# Put .pythonlibs FIRST and remove conflicting Nix-store typing_extensions
_pythonlibs = "/home/runner/workspace/.pythonlibs/lib/python3.12/site-packages"
# Remove any nix-store paths that might shadow our .pythonlibs packages
sys.path = [_pythonlibs] + [
    p for p in sys.path
    if not (p.startswith("/nix/store") and any(
        pkg in p for pkg in ["typing-extensions", "pydantic", "starlette", "fastapi"]
    ))
]

# Ensure extracted_project is importable
_here = os.path.dirname(os.path.abspath(__file__))
_extracted = os.path.dirname(_here)
if _extracted not in sys.path:
    sys.path.insert(1, _extracted)

import uvicorn  # noqa: E402
from control_panel.app import app  # noqa: E402

if __name__ == "__main__":
    port = int(os.getenv("CONTROL_PANEL_PORT", "5000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
