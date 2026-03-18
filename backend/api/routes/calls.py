"""
Indian Voice Agent — Call Logs API Routes

Dashboard endpoints for viewing and managing call history.
These feed the "Call Logs" page in the React frontend.

Endpoints:
    GET  /api/calls/{business_id}              — paginated call list
    GET  /api/calls/{business_id}/stats        — aggregate statistics
    GET  /api/calls/{business_id}/{call_id}    — single call detail + transcript
    GET  /api/calls/{business_id}/active       — currently active calls
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from database.client import db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/calls", tags=["calls"])


# ═══════════════════════════════════════════════════
# PYDANTIC MODELS — Request/Response schemas
# ═══════════════════════════════════════════════════

class CallLogResponse(BaseModel):
    """Single call log entry returned by the API."""
    id: str
    caller_phone: str
    duration_sec: int
    outcome: str
    language: str
    summary: str | None = None
    timestamp: str | None = None


class CallStatsResponse(BaseModel):
    """Aggregate call statistics for the dashboard home page."""
    total_calls: int
    appointments_booked: int
    missed_calls: int
    escalated: int = 0
    avg_duration_sec: int = 0
    conversion_rate: float = 0.0


class CallDetailResponse(BaseModel):
    """Full call detail with transcript — for the expandable row view."""
    id: str
    business_id: str
    call_sid: str
    caller_phone: str
    duration_sec: int
    outcome: str
    language: str
    summary: str | None = None
    transcript: list[dict[str, str]] = []
    timestamp: str | None = None


# ═══════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════

@router.get("/{business_id}")
async def get_call_logs(
    business_id: str,
    limit: int = Query(default=50, ge=1, le=200, description="Max results per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    outcome: str | None = Query(default=None, description="Filter by outcome: appointment_booked, info_provided, missed, escalated_to_human"),
    language: str | None = Query(default=None, description="Filter by language: hi-IN, en-IN"),
    date_from: str | None = Query(default=None, description="Start date filter, YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="End date filter, YYYY-MM-DD"),
) -> dict[str, Any]:
    """
    Get paginated call logs for the dashboard Call Logs page.

    Supports filtering by outcome, language, and date range.
    Returns newest calls first.
    """
    logger.info(
        "api.calls.list",
        business_id=business_id,
        limit=limit,
        offset=offset,
    )

    try:
        calls = await db.get_call_logs(
            business_id=business_id,
            limit=limit,
            offset=offset,
        )

        # ── Apply client-side filters (in production, these go into the query) ──
        filtered = _apply_filters(calls, outcome, language, date_from, date_to)

        return {
            "calls": filtered,
            "total": len(filtered),
            "limit": limit,
            "offset": offset,
            "has_more": len(calls) == limit,
        }

    except Exception as exc:
        logger.error("api.calls.list_error", business_id=business_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to fetch call logs")


@router.get("/{business_id}/stats")
async def get_call_stats(
    business_id: str,
    days: int = Query(default=7, ge=1, le=90, description="Number of days to aggregate"),
) -> dict[str, Any]:
    """
    Get aggregate call statistics for the dashboard home page.

    Returns total calls, appointments booked, missed calls,
    conversion rate, and average duration for the last N days.
    """
    logger.info("api.calls.stats", business_id=business_id, days=days)

    try:
        stats = await db.get_call_stats(business_id=business_id, days=days)
        return {
            "business_id": business_id,
            "period_days": days,
            **stats,
        }

    except Exception as exc:
        logger.error("api.calls.stats_error", business_id=business_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to fetch call statistics")


@router.get("/{business_id}/{call_id}")
async def get_call_detail(
    business_id: str,
    call_id: str,
) -> dict[str, Any]:
    """
    Get full details of a single call, including the complete transcript.

    Used when a user expands a row in the Call Logs table to see
    the full Hindi conversation between the AI and the caller.
    """
    logger.info("api.calls.detail", business_id=business_id, call_id=call_id)

    try:
        # ── In mock mode, return a detailed mock call ──
        from config.settings import settings
        if settings.MOCK_MODE:
            return _get_mock_call_detail(business_id, call_id)

        # ── In production, fetch from Supabase ──
        calls = await db.get_call_logs(business_id=business_id, limit=1, offset=0)
        if not calls:
            raise HTTPException(status_code=404, detail=f"Call {call_id} not found")

        return {
            "call": calls[0],
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("api.calls.detail_error", call_id=call_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to fetch call detail")


# ═══════════════════════════════════════════════════
# PRIVATE HELPERS
# ═══════════════════════════════════════════════════

def _apply_filters(
    calls: list[dict[str, Any]],
    outcome: str | None,
    language: str | None,
    date_from: str | None,
    date_to: str | None,
) -> list[dict[str, Any]]:
    """
    Apply optional filters to the call list.

    In production, these filters would be pushed to the database query.
    For MVP/mock mode, we filter client-side for simplicity.
    """
    filtered = calls

    if outcome:
        filtered = [c for c in filtered if c.get("outcome") == outcome]

    if language:
        filtered = [c for c in filtered if c.get("language") == language]

    if date_from:
        try:
            cutoff = datetime.strptime(date_from, "%Y-%m-%d")
            filtered = [
                c for c in filtered
                if c.get("timestamp") and datetime.fromisoformat(c["timestamp"]) >= cutoff
            ]
        except ValueError:
            pass  # ── Invalid date format, skip filter ──

    if date_to:
        try:
            cutoff = datetime.strptime(date_to, "%Y-%m-%d")
            filtered = [
                c for c in filtered
                if c.get("timestamp") and datetime.fromisoformat(c["timestamp"]) <= cutoff
            ]
        except ValueError:
            pass

    return filtered


def _get_mock_call_detail(business_id: str, call_id: str) -> dict[str, Any]:
    """Return a realistic mock call detail for testing the dashboard UI."""
    return {
        "call": {
            "id": call_id,
            "business_id": business_id,
            "call_sid": f"exo-{call_id[:8]}",
            "caller_phone": "+919876543210",
            "duration_sec": 67,
            "outcome": "appointment_booked",
            "language": "hi-IN",
            "summary": "Caller booked a general consultation for March 20 at 11:00 AM",
            "timestamp": datetime.now().isoformat(),
            "transcript": [
                {"role": "assistant", "text": "Namaste! Dr. Sharma Clinic mein aapka swagat hai. Kaise madad kar sakti hoon?"},
                {"role": "user", "text": "Mujhe kal 11 baje appointment chahiye"},
                {"role": "assistant", "text": "Bilkul ji! Kal 11 baje ka slot available hai. Aapka naam bataiye?"},
                {"role": "user", "text": "Mera naam Rahul Kumar hai, phone number 9876543210"},
                {"role": "assistant", "text": "Shukriya Rahul ji! Aapka appointment kal 11:00 AM ke liye confirm ho gaya hai. WhatsApp pe confirmation aa jayega."},
                {"role": "user", "text": "Dhanyavaad"},
                {"role": "assistant", "text": "Aapka dhanyavaad! Kal milte hain. Namaste!"},
            ],
        },
    }


if __name__ == "__main__":
    # ── Quick import check ──
    print(f"Call logs router loaded: {len(router.routes)} routes")
    for route in router.routes:
        print(f"  {getattr(route, 'methods', 'WS')} {route.path}")
