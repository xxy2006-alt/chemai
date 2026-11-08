"""Unified API response helpers.

Usage in new endpoints:
    return response_ok(tasks=[...], total=5)
    return response_err("Student not found", code="NOT_FOUND")

Old endpoints (no wrapper) continue to work as-is.
"""


def response_ok(**kwargs) -> dict:
    """Standard success response: {success: true, data: {...}} or flat keys."""
    if "data" in kwargs:
        return {"success": True, "data": kwargs["data"]}
    return {"success": True, **kwargs}


def response_err(message: str, code: str = "ERROR", status: int = 400, **extra) -> dict:
    """Standard error response."""
    return {"success": False, "error": {"code": code, "message": message, "status": status, **extra}}
