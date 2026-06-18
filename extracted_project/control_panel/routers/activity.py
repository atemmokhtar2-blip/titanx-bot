import os
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from ..auth import require_owner
from ..config import CONTROL_PANEL_DIR
from .. import activity_log

router = APIRouter(prefix="/activity")
templates = Jinja2Templates(directory=os.path.join(CONTROL_PANEL_DIR, "templates"))


@router.get("/api/events")
async def api_events(n: int = 50, session: dict = Depends(require_owner)):
    return {"events": activity_log.get_events(n)}


@router.post("/api/clear")
async def api_clear(session: dict = Depends(require_owner)):
    activity_log.clear()
    return {"ok": True}
