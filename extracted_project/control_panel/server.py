"""Entry point for TitanX Control Panel — binds on all Replit-mapped ports."""
import sys
import os
import asyncio

# Force .pythonlibs FIRST — must happen before any other imports
_pythonlibs = "/home/runner/workspace/.pythonlibs/lib/python3.12/site-packages"
if _pythonlibs not in sys.path:
    sys.path.insert(0, _pythonlibs)

# Ensure extracted_project is importable
_here = os.path.dirname(os.path.abspath(__file__))
_extracted = os.path.dirname(_here)
if _extracted not in sys.path:
    sys.path.insert(1, _extracted)

import uvicorn  # noqa: E402
from control_panel.app import app  # noqa: E402


async def _serve(port: int):
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def _main():
    primary_port = int(os.getenv("CONTROL_PANEL_PORT", "5000"))
    # Also bind 8081 — both are mapped to externalPort 80 in .replit
    # Replit's proxy must find a live server on whichever port it checks first
    extra_ports = [8081]
    tasks = [asyncio.create_task(_serve(primary_port))]
    for p in extra_ports:
        if p != primary_port:
            tasks.append(asyncio.create_task(_serve(p)))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(_main())
