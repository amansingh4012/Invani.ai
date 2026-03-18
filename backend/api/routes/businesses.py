"""
Indian Voice Agent — Businesses API Routes

Dashboard endpoints for managing business profiles and settings.
These feed the "Settings" page in the React frontend.

Endpoints:
    GET   /api/businesses/{business_id}            — get business config
    PATCH /api/businesses/{business_id}            — update business settings
    GET   /api/businesses/{business_id}/whatsapp   — WhatsApp message history
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config.settings import settings
from database.client import db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/businesses", tags=["businesses"])


# ═══════════════════════════════════════════════════
# PYDANTIC MODELS
# ═══════════════════════════════════════════════════

class UpdateBusinessRequest(BaseModel):
    """Request body for updating business settings from the dashboard."""
    name: str | None = Field(default=None, max_length=200, description="Business display name")
    config_json: dict[str, Any] | None = Field(default=None, description="Business configuration (greeting, services, timings, fees)")
    plan: str | None = Field(default=None, description="Subscription plan: starter, professional, enterprise")
    is_active: bool | None = Field(default=None, description="Whether the business is active")


class BusinessResponse(BaseModel):
    """Business profile returned by the API."""
    id: str
    name: str
    type: str
    phone_number: str
    config_json: dict[str, Any] = {}
    plan: str = "starter"
    is_active: bool = True


class WhatsAppMessageResponse(BaseModel):
    """Single WhatsApp message in the history."""
    id: str
    phone: str
    message: str
    direction: str
    status: str
    timestamp: str | None = None


# ═══════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════

@router.get("/{business_id}")
async def get_business(business_id: str) -> dict[str, Any]:
    """
    Get the full business profile and configuration.

    Returns everything the Settings page needs: business name,
    type, services, timings, fees, greeting message, etc.
    """
    logger.info("api.businesses.get", business_id=business_id)

    try:
        business = await db.get_business_by_id(business_id)

        if not business:
            raise HTTPException(status_code=404, detail=f"Business {business_id} not found")

        return {
            "business": business,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("api.businesses.get_error", business_id=business_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to fetch business")


@router.patch("/{business_id}")
async def update_business(
    business_id: str,
    body: UpdateBusinessRequest,
) -> dict[str, Any]:
    """
    Update business settings from the dashboard Settings page.

    Supports partial updates — only fields included in the request
    body will be modified. Other fields remain unchanged.
    """
    logger.info("api.businesses.update", business_id=business_id)

    # ── Build the updates dict (only non-None fields) ──
    updates: dict[str, Any] = {}

    if body.name is not None:
        updates["name"] = body.name

    if body.config_json is not None:
        # ── Validate config_json structure ──
        _validate_business_config(body.config_json)
        updates["config_json"] = body.config_json

    if body.plan is not None:
        valid_plans = {"starter", "professional", "enterprise"}
        if body.plan not in valid_plans:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid plan: {body.plan}. Must be one of: {', '.join(sorted(valid_plans))}",
            )
        updates["plan"] = body.plan

    if body.is_active is not None:
        updates["is_active"] = body.is_active

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        updated = await db.update_business(business_id, updates)

        if not updated:
            raise HTTPException(status_code=404, detail=f"Business {business_id} not found")

        logger.info(
            "api.businesses.updated",
            business_id=business_id,
            fields=list(updates.keys()),
        )

        return {
            "success": True,
            "business": updated,
            "updated_fields": list(updates.keys()),
            "message": f"Business settings updated: {', '.join(updates.keys())}",
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("api.businesses.update_error", business_id=business_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to update business settings")


@router.get("/{business_id}/whatsapp")
async def get_whatsapp_history(
    business_id: str,
    phone: str | None = Query(default=None, description="Filter by phone number"),
    limit: int = Query(default=50, ge=1, le=200, description="Max messages"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> dict[str, Any]:
    """
    Get WhatsApp message history for a business.

    Used by the Appointments page to show which confirmations/reminders
    were sent for each appointment, and by Settings for audit trail.
    """
    logger.info(
        "api.businesses.whatsapp",
        business_id=business_id,
        phone=phone,
    )

    try:
        if settings.MOCK_MODE:
            messages = _get_mock_whatsapp_messages(business_id, phone)
        else:
            messages = await _fetch_whatsapp_messages(business_id, phone, limit, offset)

        return {
            "messages": messages,
            "total": len(messages),
            "business_id": business_id,
            "filters": {"phone": phone},
        }

    except Exception as exc:
        logger.error("api.businesses.whatsapp_error", business_id=business_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to fetch WhatsApp messages")


# ═══════════════════════════════════════════════════
# PRIVATE HELPERS
# ═══════════════════════════════════════════════════

def _validate_business_config(config: dict[str, Any]) -> None:
    """
    Validate the structure of business config_json.

    Ensures required fields are present and types are correct
    before saving to the database.
    """
    # ── Greeting must be a string ──
    if "greeting" in config and not isinstance(config["greeting"], str):
        raise HTTPException(status_code=400, detail="greeting must be a string")

    # ── Services must be a list of strings ──
    if "services" in config:
        if not isinstance(config["services"], list):
            raise HTTPException(status_code=400, detail="services must be a list")
        if not all(isinstance(s, str) for s in config["services"]):
            raise HTTPException(status_code=400, detail="all services must be strings")

    # ── Timings must be a dict ──
    if "timings" in config and not isinstance(config["timings"], dict):
        raise HTTPException(status_code=400, detail="timings must be an object")

    # ── Fees must be numeric ──
    for fee_field in ["consultation_fee", "followup_fee"]:
        if fee_field in config:
            if not isinstance(config[fee_field], (int, float)):
                raise HTTPException(status_code=400, detail=f"{fee_field} must be a number")
            if config[fee_field] < 0:
                raise HTTPException(status_code=400, detail=f"{fee_field} cannot be negative")


async def _fetch_whatsapp_messages(
    business_id: str,
    phone: str | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """Fetch WhatsApp messages from Supabase with optional phone filter."""
    try:
        query = (
            db._client.table("whatsapp_messages")
            .select("*")
            .eq("business_id", business_id)
            .order("timestamp", desc=True)
            .range(offset, offset + limit - 1)
        )

        if phone:
            query = query.eq("phone", phone)

        response = query.execute()
        return response.data or []

    except Exception as exc:
        logger.error("api.businesses.whatsapp_fetch_error", error=str(exc))
        return []


def _get_mock_whatsapp_messages(
    business_id: str,
    phone: str | None,
) -> list[dict[str, Any]]:
    """Return realistic mock WhatsApp message history."""
    messages = [
        {
            "id": "mock-wa-001",
            "business_id": business_id,
            "phone": "+919876543210",
            "message": "✅ *Appointment Confirmed!*\n\n👤 *Name:* Rahul Kumar\n🏥 *Dr. Sharma Clinic*\n📅 *Date:* 2026-03-19\n🕐 *Time:* 10:00\n💊 *Service:* General Consultation\n\nPlease arrive 10 minutes early.\nThank you! 🙏",
            "direction": "outbound",
            "status": "sent",
            "message_type": "template",
            "timestamp": "2026-03-18T10:30:00",
        },
        {
            "id": "mock-wa-002",
            "business_id": business_id,
            "phone": "+919876543211",
            "message": "✅ *Appointment Confirmed!*\n\n👤 *Name:* Priya Singh\n🏥 *Dr. Sharma Clinic*\n📅 *Date:* 2026-03-19\n🕐 *Time:* 14:00\n💊 *Service:* Blood Test\n\nPlease arrive 10 minutes early.\nThank you! 🙏",
            "direction": "outbound",
            "status": "sent",
            "message_type": "template",
            "timestamp": "2026-03-18T11:15:00",
        },
        {
            "id": "mock-wa-003",
            "business_id": business_id,
            "phone": "+919876543210",
            "message": "🔔 *Appointment Reminder*\n\nHi Rahul! 👋\n\nAapka appointment kal hai:\n📅 2026-03-19 | 🕐 10:00\n🏥 Dr. Sharma Clinic\n\nKripya samay par aa jayein. Dhanyavaad! 🙏",
            "direction": "outbound",
            "status": "sent",
            "message_type": "template",
            "timestamp": "2026-03-18T18:00:00",
        },
        {
            "id": "mock-wa-004",
            "business_id": business_id,
            "phone": "+919876543214",
            "message": "Aapka appointment cancel ho gaya hai. Naya appointment book karne ke liye hamein call karein.",
            "direction": "outbound",
            "status": "sent",
            "message_type": "text",
            "timestamp": "2026-03-18T09:45:00",
        },
    ]

    # ── Apply phone filter if provided ──
    if phone:
        messages = [m for m in messages if m["phone"] == phone]

    return messages


if __name__ == "__main__":
    print(f"Businesses router loaded: {len(router.routes)} routes")
    for route in router.routes:
        print(f"  {getattr(route, 'methods', 'WS')} {route.path}")
