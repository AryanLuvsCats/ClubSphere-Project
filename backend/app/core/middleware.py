"""Security middleware: headers, HTTPS redirect, and request-size limits."""
from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.rate_limit import client_ip


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")

        if request.url.path.startswith(settings.API_V1_PREFIX):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            )

        if request.url.path.startswith(f"{settings.API_V1_PREFIX}/auth"):
            response.headers.setdefault("Cache-Control", "no-store")
            response.headers.setdefault("Pragma", "no-cache")

        if _request_is_https(request) and settings.HSTS_SECONDS > 0:
            value = f"max-age={settings.HSTS_SECONDS}"
            if settings.HSTS_INCLUDE_SUBDOMAINS:
                value += "; includeSubDomains"
            if settings.HSTS_PRELOAD:
                value += "; preload"
            response.headers.setdefault("Strict-Transport-Security", value)

        return response


def _request_is_https(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    direct = request.client.host if request.client else ""
    trusted = {ip.strip() for ip in settings.TRUSTED_PROXY_IPS if ip.strip()}
    if direct in trusted:
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
        return forwarded_proto.lower() == "https"
    return False


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if settings.force_https and not _request_is_https(request):
            url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(url), status_code=307)
        return await call_next(request)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )

            is_upload = request.url.path.startswith(
                f"{settings.API_V1_PREFIX}/uploads"
            )
            limit = (
                settings.MAX_UPLOAD_SIZE_BYTES + 1024 * 1024
                if is_upload
                else settings.MAX_REQUEST_BODY_BYTES
            )
            if length > limit:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body is too large"},
                )
        return await call_next(request)
