"""Baidu OAuth token manager — shared by all Baidu API clients.

In-memory cache with auto-refresh. Thread-safe for async usage.
"""
import os
import time
import logging
import httpx

logger = logging.getLogger(__name__)

BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"

# Module-level cache
_token: str = ""
_expires_at: float = 0.0


def _credentials() -> tuple[str, str]:
    key = os.getenv("BAIDU_OCR_API_KEY", "")
    secret = os.getenv("BAIDU_OCR_SECRET_KEY", "")
    return key, secret


async def get_token() -> str:
    """Return a valid Baidu access token, refreshing if needed.

    Caches the token in memory. Refreshes when fewer than 300 seconds remain.
    """
    global _token, _expires_at

    if _token and time.time() < _expires_at - 300:
        return _token

    key, secret = _credentials()
    if not key or not secret:
        raise RuntimeError("BAIDU_OCR_API_KEY and BAIDU_OCR_SECRET_KEY must be set")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            BAIDU_TOKEN_URL,
            params={
                "grant_type": "client_credentials",
                "client_id": key,
                "client_secret": secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    _token = data.get("access_token", "")
    if not _token:
        raise RuntimeError(f"Baidu token response missing access_token: {data}")

    expires_in = data.get("expires_in", 2592000)
    _expires_at = time.time() + expires_in
    logger.info("Baidu token refreshed, expires in %ds", expires_in)
    return _token
