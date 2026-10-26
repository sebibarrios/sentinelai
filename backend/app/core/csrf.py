"""CSRF defense-in-depth: state-changing API calls must carry X-Requested-With.

The session cookie is already SameSite=Lax, so browsers won't attach it to cross-site
POSTs. As a second layer, a plain HTML form or a cross-site fetch can't set a custom
header without a CORS preflight, and preflights from other origins are refused. So a
request that has the header came from our own frontend (or a deliberate API client).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
HEADER = "x-requested-with"


class RequireCustomHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if (
            request.method in UNSAFE_METHODS
            and request.url.path.startswith("/api/")
            and not request.headers.get(HEADER)
        ):
            return JSONResponse(
                {
                    "error": {
                        "code": "csrf_header_missing",
                        "message": "Missing X-Requested-With header on a state-changing request.",
                        "details": None,
                    }
                },
                status_code=403,
            )
        return await call_next(request)
