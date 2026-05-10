"""
POS Service — Cash Sessions API.
Endpoints for managing cash register shifts (open/close/status).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from loguru import logger

from api.auth import get_current_user
from services.cash_service import cash_service
from services.sheets_sync import sync_products_from_sheets
from services.time_utils import get_phuket_today

router = APIRouter(prefix="/api/v1/sessions", tags=["Sessions"])


class OpenSessionRequest(BaseModel):
    pier: str
    manager_id: int | None = None
    manager_name: str | None = None


class CloseSessionRequest(BaseModel):
    session_id: int
    pier: str | None = None


@router.get("/active")
async def get_active_session(
    pier: str,
    user: dict = Depends(get_current_user),
):
    """
    Returns the active (open) session for a pier, along with today's daily report.
    If no active session, still returns the daily report if sales exist.
    """
    today = get_phuket_today()
    daily_report = await cash_service.get_daily_report(pier, today)

    session_data = await cash_service.get_active_session(pier)
    if session_data:
        return {
            "status": "success",
            "data": {
                "active": True,
                "id": session_data.id,
                "pier": session_data.pier,
                "manager_id": session_data.manager_id,
                "manager_name": session_data.manager_name,
                "opened_at": session_data.opened_at.isoformat() if session_data.opened_at else None,
                "report": daily_report,
            },
        }
    else:
        return {
            "status": "success",
            "data": {
                "active": False,
                "report": daily_report if daily_report["sales_count"] > 0 else None,
            },
        }


@router.post("/open")
async def open_session(
    req: OpenSessionRequest,
    user: dict = Depends(get_current_user),
):
    """
    Opens a new cash session for a pier.
    Auto-syncs products from Google Sheets before opening.
    Returns the existing session if one is already open.
    """
    manager_id = req.manager_id or user.get("user_id", 0)
    manager_name = req.manager_name or user.get("username")

    # Auto-sync products on session open
    try:
        await sync_products_from_sheets()
        logger.info(f"Auto-synced products on session open for pier {req.pier}")
    except Exception as e:
        logger.warning(f"Auto-sync failed on session open: {e} (continuing anyway)")

    session_data = await cash_service.open_session(
        pier=req.pier,
        manager_id=manager_id,
        manager_name=manager_name,
    )

    return {
        "status": "success",
        "data": {
            "session_id": session_data.id,
            "pier": session_data.pier,
            "opened_at": session_data.opened_at.isoformat() if session_data.opened_at else None,
        },
    }


@router.post("/close")
async def close_session(
    req: CloseSessionRequest,
    user: dict = Depends(get_current_user),
):
    """
    Closes an active cash session.
    Returns the full daily report after closing.
    """
    success = await cash_service.close_session(req.session_id)

    # Return daily report
    daily_report = None
    if req.pier:
        today = get_phuket_today()
        daily_report = await cash_service.get_daily_report(req.pier, today)

    if success:
        return {"status": "success", "report": daily_report}
    else:
        raise HTTPException(status_code=404, detail="Session not found or already closed")


@router.get("/{session_id}/report")
async def get_session_report(
    session_id: int,
    user: dict = Depends(get_current_user),
):
    """Returns a detailed report for a specific session."""
    report = await cash_service.get_session_report(session_id)
    return {"status": "success", "data": report}
