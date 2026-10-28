"""Security headers on every API response.

The API only serves JSON, so its Content-Security-Policy can forbid everything: if a
response were ever rendered as a page, no script, style, or frame could load.
The interactive docs page is the exception, since it loads Swagger UI from a CDN.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings

DOCS_PATHS = ("/api/docs", "/api/openapi.json")

BASE_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cross-origin-resource-policy": "same-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}
JSON_ONLY = {
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    # Responses contain security data; never let browsers or proxies cache them.
    "cache-control": "no-store",
}
HSTS = ("strict-transport-security", "max-age=63072000; includeSubDomains")


class SecurityHeadersMiddleware:
    """Pure ASGI middleware (no response buffering), so streaming still works."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(BASE_HEADERS)
        if not scope["path"].startswith(DOCS_PATHS):
            headers.update(JSON_ONLY)
        if get_settings().is_production:
            headers[HSTS[0]] = HSTS[1]
        encoded = [(k.encode(), v.encode()) for k, v in headers.items()]

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                existing = {k.lower() for k, _ in message.get("headers", [])}
                message["headers"] = list(message.get("headers", [])) + [
                    h for h in encoded if h[0] not in existing
                ]
            await send(message)

        await self.app(scope, receive, send_with_headers)
