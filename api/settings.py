"""
POS Service — Settings API.
Endpoints for viewing and managing dynamic POS configuration.
Protected by API Key authentication.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from loguru import logger

from api.auth import get_current_user
from services.settings_service import settings_service

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])


class UpdateSettingRequest(BaseModel):
    value: str
    description: str | None = None


@router.get("")
async def list_settings(user: dict = Depends(get_current_user)):
    """Returns all POS settings."""
    settings = await settings_service.get_all()
    return {"status": "success", "data": settings}


@router.get("/{key}")
async def get_setting(key: str, user: dict = Depends(get_current_user)):
    """Get a single setting by key."""
    value = await settings_service.get(key)
    if value == "" and key not in [s["key"] for s in await settings_service.get_all()]:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return {"status": "success", "data": {"key": key, "value": value}}


@router.put("/{key}")
async def update_setting(
    key: str,
    req: UpdateSettingRequest,
    user: dict = Depends(get_current_user),
):
    """Update a setting value. Creates the key if it doesn't exist."""
    result = await settings_service.set(key, req.value, req.description)
    return {"status": "success", "data": result}


@router.delete("/{key}")
async def delete_setting(key: str, user: dict = Depends(get_current_user)):
    """Delete a custom setting."""
    success = await settings_service.delete(key)
    if success:
        return {"status": "success", "message": f"Setting '{key}' deleted"}
    raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
