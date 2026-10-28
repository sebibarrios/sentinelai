"""Only accept API traffic that came through the Next.js frontend.

When PROXY_SHARED_SECRET is set, the frontend's proxy attaches it to every /api
request (and strips any copy a browser tried to send). Requests without it, e.g.
someone calling the backend's public URL directly, are refused. That makes the
X-Sentinel-Client-IP header trustworthy, because only the frontend can set it.

The health check stays open so the hosting provider can monitor the service.
"""

import hmac
import ipaddress

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings

SECRET_HEADER = "x-sentinel-proxy-secret"  # noqa: S105 - a header name, not a secret
CLIENT_IP_HEADER = "x-sentinel-client-ip"
OPEN_PATHS = {"/api/v1/health"}


def has_valid_proxy_secret(request: Request) -> bool:
    secret = get_settings().proxy_shared_secret
    if not secret:
        return False
    supplied = request.headers.get(SECRET_HEADER, "")
    return hmac.compare_digest(supplied.encode(), secret.encode())  # constant-time


def client_ip(request: Request) -> str:
    """The real client IP if the frontend vouched for it, else the socket peer."""
    if has_valid_proxy_secret(request):
        claimed = request.headers.get(CLIENT_IP_HEADER, "").strip()
        try:
            return str(ipaddress.ip_address(claimed))
        except ValueError:
            pass
    return request.client.host if request.client else "unknown"


class RequireProxySecretMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and get_settings().proxy_shared_secret
            and scope["path"].startswith("/api/")
            and scope["path"] not in OPEN_PATHS
            and not has_valid_proxy_secret(Request(scope))
        ):
            response = JSONResponse(
                {
                    "error": {
                        "code": "direct_access_forbidden",
                        "message": "This API is only reachable through the SentinelAI web app.",
                        "details": None,
                    }
                },
                status_code=403,
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
