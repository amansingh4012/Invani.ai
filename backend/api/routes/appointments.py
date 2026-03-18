"""
Indian Voice Agent — Appointments API Routes

Dashboard endpoints for managing appointments booked by the AI.
These feed the "Appointments" page in the React frontend.

Endpoints:
    GET   /api/appointments/{business_id}                    — list all appointments
    GET   /api/appointments/{business_id}/slots/{date}       — available slots for a date
    POST  /api/appointments/{business_id}                    — manually create appointment
    PATCH /api/appointments/{business_id}/{appointment_id}   — update status (cancel/complete)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from database.client import db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


# ═══════════════════════════════════════════════════
# PYDANTIC MODELS — Request/Response schemas
# ═══════════════════════════════════════════════════

class CreateAppointmentRequest(BaseModel):
    """Request body for manually creating an appointment from the dashboard."""
    patient_name: str = Field(min_length=1, max_length=100, description="Full name of the patient/customer")
    phone: str = Field(min_length=10, max_length=15, description="Phone number with country code")
    date: str = Field(description="Appointment date in YYYY-MM-DD format")
    time: str = Field(description="Appointment time in HH:MM format (24-hour)")
    service: str = Field(default="General Consultation", description="Type of service")
    notes: str | None = Field(default=None, max_length=500, description="Optional notes")


class UpdateAppointmentRequest(BaseModel):
    """Request body for updating an appointment status."""
    status: str = Field(description="New status: confirmed, cancelled, completed, no_show")
    notes: str | None = Field(default=None, max_length=500, description="Optional status change reason")


# ═══════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════

@router.get("/{business_id}")
async def get_appointments(
    business_id: str,
    date: str | None = Query(default=None, description="Filter by date, YYYY-MM-DD"),
    status: str | None = Query(default=None, description="Filter by status: confirmed, cancelled, completed"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> dict[str, Any]:
    """
    Get appointments for a business, optionally filtered by date and status.

    Used by the Appointments page calendar view and list view.
    Returns appointments sorted by date/time (newest first).
    """
    logger.info(
        "api.appointments.list",
        business_id=business_id,
        date=date,
        status=status,
    )

    try:
        # ── If a specific date is requested, use the optimized date query ──
        if date:
            appointments = await db.get_appointments_for_day(business_id, date)
        else:
            appointments = await _get_all_appointments(business_id, limit, offset)

        # ── Apply status filter client-side for MVP ──
        if status:
            appointments = [a for a in appointments if a.get("status") == status]

        return {
            "appointments": appointments,
            "total": len(appointments),
            "business_id": business_id,
            "filters": {
                "date": date,
                "status": status,
            },
        }

    except Exception as exc:
        logger.error("api.appointments.list_error", business_id=business_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to fetch appointments")


@router.get("/{business_id}/slots/{date}")
async def get_available_slots(
    business_id: str,
    date: str,
) -> dict[str, Any]:
    """
    Get available time slots for a specific date.

    Used by the manual appointment creation form to show
    which slots are still open for booking.
    """
    logger.info("api.appointments.slots", business_id=business_id, date=date)

    # ── Validate date format ──
    try:
        requested_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format: {date}. Use YYYY-MM-DD.",
        )

    # ── Check if date is in the past ──
    if requested_date < datetime.now().date():
        raise HTTPException(
            status_code=400,
            detail="Cannot check slots for past dates.",
        )

    try:
        slots = await db.get_available_slots(business_id, date)

        # ── Split into morning/afternoon for better UI display ──
        morning = [s for s in slots if int(s.split(":")[0]) < 12]
        afternoon = [s for s in slots if int(s.split(":")[0]) >= 12]

        return {
            "date": date,
            "available_slots": slots,
            "morning_slots": morning,
            "afternoon_slots": afternoon,
            "total_available": len(slots),
        }

    except Exception as exc:
        logger.error("api.appointments.slots_error", date=date, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to fetch available slots")


@router.post("/{business_id}")
async def create_appointment(
    business_id: str,
    body: CreateAppointmentRequest,
) -> dict[str, Any]:
    """
    Manually create an appointment from the dashboard.

    Used when the business owner wants to add a walk-in
    or phone booking directly, bypassing the AI voice agent.
    """
    logger.info(
        "api.appointments.create",
        business_id=business_id,
        patient=body.patient_name,
        date=body.date,
        time=body.time,
    )

    # ── Validate date ──
    try:
        requested_date = datetime.strptime(body.date, "%Y-%m-%d").date()
        if requested_date < datetime.now().date():
            raise HTTPException(status_code=400, detail="Cannot book appointments in the past")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {body.date}")

    # ── Validate time ──
    try:
        datetime.strptime(body.time, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid time format: {body.time}")

    # ── Check slot availability ──
    available = await db.get_available_slots(business_id, body.date)
    if body.time not in available:
        raise HTTPException(
            status_code=409,
            detail=f"Time slot {body.time} is not available on {body.date}",
        )

    try:
        appointment = await db.create_appointment(
            business_id=business_id,
            patient_name=body.patient_name,
            phone=body.phone,
            appt_date=body.date,
            appt_time=body.time,
            service=body.service,
            notes=body.notes,
        )

        if not appointment:
            raise HTTPException(status_code=500, detail="Failed to create appointment")

        logger.info(
            "api.appointments.created",
            appointment_id=appointment.get("id"),
            patient=body.patient_name,
        )

        return {
            "success": True,
            "appointment": appointment,
            "message": f"Appointment booked for {body.patient_name} on {body.date} at {body.time}",
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("api.appointments.create_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to create appointment")


@router.patch("/{business_id}/{appointment_id}")
async def update_appointment(
    business_id: str,
    appointment_id: str,
    body: UpdateAppointmentRequest,
) -> dict[str, Any]:
    """
    Update an appointment's status from the dashboard.

    Used for cancelling, completing, or marking no-shows.
    Only status changes are allowed — no rescheduling via this endpoint.
    """
    valid_statuses = {"confirmed", "cancelled", "completed", "no_show"}

    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {body.status}. Must be one of: {', '.join(sorted(valid_statuses))}",
        )

    logger.info(
        "api.appointments.update",
        business_id=business_id,
        appointment_id=appointment_id,
        new_status=body.status,
    )

    try:
        # ── For cancellation, use the existing cancel flow ──
        if body.status == "cancelled":
            # ── In mock mode, always succeeds ──
            from config.settings import settings
            if settings.MOCK_MODE:
                return {
                    "success": True,
                    "appointment_id": appointment_id,
                    "status": "cancelled",
                    "message": "Appointment cancelled successfully",
                }

        # ── For other status updates, use generic update ──
        # ── In production, this would call db.update_appointment() ──
        from config.settings import settings
        if settings.MOCK_MODE:
            return {
                "success": True,
                "appointment_id": appointment_id,
                "status": body.status,
                "message": f"Appointment status updated to {body.status}",
            }

        # ── Production path (Supabase) — TODO: add db.update_appointment() ──
        raise HTTPException(status_code=501, detail="Appointment update not yet implemented for production mode")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("api.appointments.update_error", appointment_id=appointment_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to update appointment")


# ═══════════════════════════════════════════════════
# PRIVATE HELPERS
# ═══════════════════════════════════════════════════

async def _get_all_appointments(
    business_id: str,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """
    Get all appointments (not date-filtered).

    In mock mode, returns a week of sample appointments.
    In production, queries Supabase with pagination.
    """
    from config.settings import settings

    if settings.MOCK_MODE:
        return _get_mock_appointments(business_id)

    try:
        from database.client import db as database
        response = (
            database._client.table("appointments")
            .select("*")
            .eq("business_id", business_id)
            .order("date", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return response.data or []
    except Exception as exc:
        logger.error("api.appointments.all_error", error=str(exc))
        return []


def _get_mock_appointments(business_id: str) -> list[dict[str, Any]]:
    """Return realistic mock appointments spanning several days."""
    return [
        {
            "id": "mock-appt-001",
            "business_id": business_id,
            "patient_name": "Rahul Kumar",
            "phone": "+919876543210",
            "date": "2026-03-19",
            "time": "10:00",
            "service": "General Consultation",
            "status": "confirmed",
            "created_by": "ai_agent",
        },
        {
            "id": "mock-appt-002",
            "business_id": business_id,
            "patient_name": "Priya Singh",
            "phone": "+919876543211",
            "date": "2026-03-19",
            "time": "14:00",
            "service": "Blood Test",
            "status": "confirmed",
            "created_by": "ai_agent",
        },
        {
            "id": "mock-appt-003",
            "business_id": business_id,
            "patient_name": "Amit Patel",
            "phone": "+919876543212",
            "date": "2026-03-20",
            "time": "11:30",
            "service": "ECG",
            "status": "confirmed",
            "created_by": "manual",
        },
        {
            "id": "mock-appt-004",
            "business_id": business_id,
            "patient_name": "Sunita Devi",
            "phone": "+919876543213",
            "date": "2026-03-18",
            "time": "09:30",
            "service": "General Consultation",
            "status": "completed",
            "created_by": "ai_agent",
        },
        {
            "id": "mock-appt-005",
            "business_id": business_id,
            "patient_name": "Vikram Mehta",
            "phone": "+919876543214",
            "date": "2026-03-18",
            "time": "15:00",
            "service": "Follow-up",
            "status": "cancelled",
            "created_by": "ai_agent",
        },
    ]


if __name__ == "__main__":
    print(f"Appointments router loaded: {len(router.routes)} routes")
    for route in router.routes:
        print(f"  {getattr(route, 'methods', 'WS')} {route.path}")
