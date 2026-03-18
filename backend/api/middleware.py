"""
Indian Voice Agent — API Middleware

Provides:
- CORS configuration for frontend dashboard access
- Request logging with structured logs
- Exotel webhook signature verification
- Error handling middleware that never crashes on a single bad request
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from config.settings import settings

logger = structlog.get_logger(__name__)


def setup_cors(app: FastAPI) -> None:
    """
    Configure CORS to allow the frontend dashboard to access the API.

    In development: allows localhost origins.
    In production: restrict to your Vercel domain.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every incoming request with method, path, status, and duration.

    Why: In a voice pipeline, debugging latency is critical. This middleware
    timestamps every request so we can spot slow API calls in production.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request, log timing, and return response."""
        start_time = time.time()
        request_id = f"req-{int(start_time * 1000) % 100000}"

        logger.info(
            "request.start",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        try:
            response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 1)

            logger.info(
                "request.complete",
                request_id=request_id,
                status=response.status_code,
                duration_ms=duration_ms,
            )
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms}ms"
            return response

        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000, 1)
            logger.error(
                "request.error",
                request_id=request_id,
                error=str(exc),
                duration_ms=duration_ms,
            )
            return Response(
                content='{"error": "Internal server error"}',
                status_code=500,
                media_type="application/json",
            )


def verify_exotel_signature(payload: bytes, signature: str) -> bool:
    """
    Verify that an incoming webhook request actually came from Exotel.

    Uses HMAC-SHA256 with the webhook secret from settings.
    In MOCK_MODE, always returns True for testing convenience.
    """
    if settings.MOCK_MODE:
        return True

    if not settings.EXOTEL_WEBHOOK_SECRET:
        logger.warning("exotel.no_secret", msg="Webhook secret not configured — skipping verification")
        return True

    expected = hmac.new(
        key=settings.EXOTEL_WEBHOOK_SECRET.encode(),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def setup_middleware(app: FastAPI) -> None:
    """Wire up all middleware to the FastAPI app — call this once at startup."""
    setup_cors(app)
    app.add_middleware(RequestLoggingMiddleware)
    logger.info("middleware.configured", mock_mode=settings.MOCK_MODE)
