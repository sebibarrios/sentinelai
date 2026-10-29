"""Only accept API traffic that came through the Next.js frontend.

When PROXY_SHARED_SECRET is set, the frontend's proxy attaches it to every /api
request (and strips any copy a browser tried to send). Requests without it, e.g.
someone calling the backend's public URL directly, are refused. That makes the
X-Sentinel-Client-IP header trustworthy, because only the frontend can set it.

The health check stays open so the hosting provider can monitor the service.
"""

import hmac
import ipaddress
import logging
from functools import cache

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings

logger = logging.getLogger("sentinelai.proxy_auth")

SECRET_HEADER = "x-sentinel-proxy-secret"  # noqa: S105 - a header name, not a secret
CLIENT_IP_HEADER = "x-sentinel-client-ip"
OPEN_PATHS = {"/api/v1/health"}


def has_valid_proxy_secret(request: Request) -> bool:
    secret = get_settings().proxy_shared_secret
    if not secret:
        return False
    supplied = request.headers.get(SECRET_HEADER, "")
    return hmac.compare_digest(supplied.encode(), secret.encode())  # constant-time


@cache
def _warn_missing_client_ip() -> None:
    logger.warning(
        "No client IP forwarded by the web app; per-IP rate limits are off. "
        "Set CLIENT_IP_HEADER on the web server to enable them."
    )


def client_ip(request: Request) -> str | None:
    """The visitor's IP for per-IP rate limits, or None if it isn't known.

    - Frontend vouched (valid secret) and forwarded an IP: that IP.
    - Frontend vouched but forwarded no IP (CLIENT_IP_HEADER not configured on the web
      server): None. The socket address would be the frontend's own IP, shared by every
      visitor, so a per-IP limit on it would let one attacker lock out the whole site.
      Per-account limits still apply.
    - No proxy secret configured (local development): the socket address.
    """
    if has_valid_proxy_secret(request):
        claimed = request.headers.get(CLIENT_IP_HEADER, "").strip()
        try:
            return str(ipaddress.ip_address(claimed))
        except ValueError:
            _warn_missing_client_ip()
            return None
    return request.client.host if request.client else None


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
