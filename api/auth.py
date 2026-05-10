"""
POS Service — Authentication & Authorization.
Supports two auth modes:
  1. API Key (X-API-Key header) — for service-to-service (bot → POS)
  2. Telegram initData — for Mini App frontend (direct browser access)
"""
import hmac
import hashlib
import urllib.parse
import json
from typing import Optional

from fastapi import Header, HTTPException, Request, Depends
from loguru import logger

from config import config


async def verify_api_key(x_api_key: str = Header(default=None)) -> bool:
    """
    Dependency that validates the API key from X-API-Key header.
    Used for service-to-service authentication.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if x_api_key != config.API_KEY.get_secret_value():
        raise HTTPException(status_code=403, detail="Invalid API key")
    return True


def validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """
    Validate Telegram WebApp initData using HMAC-SHA256.
    Returns user dict if valid, None otherwise.
    """
    try:
        if not init_data:
            return None

        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        if "hash" not in parsed_data:
            return None

        hash_val = parsed_data.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))

        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if calculated_hash == hash_val:
            user_data = json.loads(parsed_data.get("user", "{}"))
            return user_data
        else:
            logger.warning("Telegram initData: hash mismatch")
    except Exception as e:
        logger.error(f"Telegram initData validation error: {e}")
    return None


async def get_current_user(request: Request) -> dict:
    """
    Unified auth dependency. Tries in order:
    1. X-API-Key header (service-to-service) — returns minimal user context from query/body
    2. Telegram initData (Mini App) — returns Telegram user data
    3. No auth — raises 401

    Returns dict with at least: {"user_id": int, "auth_method": str}
    """
    # 1. Try API Key auth
    api_key = request.headers.get("X-API-Key")
    if api_key:
        if api_key != config.API_KEY.get_secret_value():
            raise HTTPException(status_code=403, detail="Invalid API key")

        # Extract user context from query params or body
        user_id = request.query_params.get("manager_id")
        if not user_id and request.method == "POST":
            try:
                body = await request.json()
                user_id = body.get("manager_id")
            except Exception:
                pass

        return {
            "user_id": int(user_id) if user_id else 0,
            "auth_method": "api_key",
        }

    # 2. Try Telegram initData
    init_data = request.query_params.get("initData") or request.query_params.get("init_data")
    if not init_data and request.method == "POST":
        try:
            body = await request.json()
            init_data = body.get("initData") or body.get("init_data")
        except Exception:
            pass

    if init_data:
        for bot_token in config.bot_token_list:
            user_data = validate_telegram_init_data(init_data, bot_token)
            if user_data and user_data.get("id"):
                return {
                    "user_id": int(user_data["id"]),
                    "username": user_data.get("username"),
                    "full_name": user_data.get("first_name", ""),
                    "auth_method": "telegram",
                }

    # 3. Try token-based auth (URL token for backwards compatibility)
    token = request.query_params.get("token")
    if token:
        # Simple HMAC token verification
        user_id = _verify_simple_token(token)
        if user_id:
            return {
                "user_id": user_id,
                "auth_method": "token",
            }

    raise HTTPException(status_code=401, detail="Authentication required")


def _verify_simple_token(token: str) -> Optional[int]:
    """Verify a simple HMAC auth token. Returns user_id if valid."""
    import base64
    import time

    try:
        padding = "=" * (4 - len(token) % 4)
        decoded = base64.urlsafe_b64decode(token + padding).decode()
        parts = decoded.split(":")
        if len(parts) != 3:
            return None
        user_id_str, expires_str, signature = parts
        user_id = int(user_id_str)
        expires = int(expires_str)

        if time.time() > expires:
            return None

        # Try API_KEY first, then BOT_TOKENS
        secrets = [config.API_KEY.get_secret_value()] + config.bot_token_list
        
        expected_payload = f"{user_id}:{expires}"
        for secret in secrets:
            expected_sig = hmac.new(
                secret.encode(),
                expected_payload.encode(),
                hashlib.sha256,
            ).hexdigest()

            if hmac.compare_digest(signature, expected_sig):
                return user_id
    except Exception:
        pass
    return None
