"""ChemRender Middleware — 对所有 JSON 响应中的化学式自动转 Unicode 下标/上标。

Replaces the former JSONResponse.render monkey-patch with an explicit,
named Starlette BaseHTTPMiddleware. Only processes application/json responses.
"""

import json as _json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.utils.chem_render import render_chem_deep


class ChemRenderMiddleware(BaseHTTPMiddleware):
    """Middleware that applies chemical formula Unicode rendering to JSON responses.

    Only processes responses with Content-Type: application/json.
    Skips binary, HTML, and streaming responses.
    """

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # Read body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        try:
            data = _json.loads(body)
            rendered = render_chem_deep(data)
            new_body = _json.dumps(rendered, ensure_ascii=False).encode("utf-8")

            headers = dict(response.headers)
            headers["content-length"] = str(len(new_body))

            return Response(
                content=new_body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )
        except Exception:
            # If JSON parsing fails (shouldn't happen for valid JSON responses),
            # return the original response body unmodified.
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
