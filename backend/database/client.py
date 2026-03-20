"""
Indian Voice Agent — Supabase Database Client

Provides async-friendly CRUD operations for all four tables:
businesses, appointments, call_logs, and whatsapp_messages.

In MOCK_MODE, returns realistic fake data without hitting Supabase.

Usage:
    from database.client import db

    # Get a business by phone number (Exotel webhook lookup)
    business = await db.get_business_by_phone("+911234567890")

    # Book an appointment
    appointment = await db.create_appointment(
        business_id="...", patient_name="Rahul", phone="+91...",
        date="2025-03-20", time="10:00", service="General Consultation"
    )
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog
from supabase import Client, create_client

from config.settings import settings

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════
# MOCK DATA — Used when MOCK_MODE=True
# ═══════════════════════════════════════════════════

MOCK_BUSINESS: dict[str, Any] = {
    "id": "mock-business-001",
    "name": "Dr. Sharma Clinic",
    "type": "clinic",
    "phone_number": "+911234567890",
    "config_json": {
        "greeting": "Namaste! Dr. Sharma Clinic mein aapka swagat hai.",
        "services": ["General Consultation", "Blood Test", "ECG"],
        "timings": {"mon_sat": "9:00 AM - 7:00 PM", "sunday": "Closed"},
        "consultation_fee": 500,
        "followup_fee": 200,
    },
    "plan": "starter",
    "is_active": True,
}

MOCK_SLOTS: list[str] = [
    "09:00", "09:30", "10:00", "10:30", "11:00",
    "11:30", "14:00", "14:30", "15:00", "15:30",
    "16:00", "16:30", "17:00", "17:30", "18:00",
]


# ═══════════════════════════════════════════════════
# DATABASE CLIENT CLASS
# ═══════════════════════════════════════════════════

class DatabaseClient:
    """
    Wraps Supabase client with typed methods for each table.

    Automatically falls back to mock data when MOCK_MODE is enabled,
    so the voice pipeline can be tested without a live database.
    """

    def __init__(self) -> None:
        """Initialize the database client — connects to Supabase or sets up mock mode."""
        self._client: Client | None = None

        if settings.MOCK_MODE:
            logger.info("database.mock_mode", msg="Using mock database — no Supabase connection")
        elif settings.is_supabase_configured:
            self._client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY,
            )
            logger.info("database.connected", url=settings.SUPABASE_URL)
        else:
            logger.warning("database.not_configured", msg="Supabase credentials missing — falling back to mock mode")

    # ── BUSINESSES ──

    async def get_business_by_phone(self, phone_number: str) -> dict[str, Any] | None:
        """
        Look up a business by its Exotel phone number.

        This is the first thing that happens when a call comes in —
        we need to know which business the caller is trying to reach.
        """
        if self._is_mock:
            logger.debug("mock.get_business_by_phone", phone=phone_number)
            return MOCK_BUSINESS

        try:
            response = (
                self._client.table("businesses")
                .select("*")
                .eq("phone_number", phone_number)
                .eq("is_active", True)
                .single()
                .execute()
            )
            return response.data
        except Exception as exc:
            logger.error("db.get_business_by_phone.error", phone=phone_number, error=str(exc))
            return None

    async def get_business_by_id(self, business_id: str) -> dict[str, Any] | None:
        """Fetch a business by its UUID — used by dashboard API routes."""
        if self._is_mock:
            return MOCK_BUSINESS

        try:
            response = (
                self._client.table("businesses")
                .select("*")
                .eq("id", business_id)
                .single()
                .execute()
            )
            return response.data
        except Exception as exc:
            logger.error("db.get_business_by_id.error", id=business_id, error=str(exc))
            return None

    async def update_business(self, business_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Update business configuration — used by Settings page."""
        if self._is_mock:
            logger.info("mock.update_business", id=business_id, updates=updates)
            return {**MOCK_BUSINESS, **updates}

        try:
            response = (
                self._client.table("businesses")
                .update(updates)
                .eq("id", business_id)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as exc:
            logger.error("db.update_business.error", id=business_id, error=str(exc))
            return None

    async def assign_number_from_pool(self, business_id: str) -> dict[str, Any] | None:
        """
        Assign an available Exotel Virtual Number from the pool to the business.
        """
        if self._is_mock:
            # Simulate grabbing an unused number
            mock_assigned_number = "+9108047361419"
            logger.info("mock.assign_number", id=business_id, number=mock_assigned_number)
            MOCK_BUSINESS["phone_number"] = mock_assigned_number
            return MOCK_BUSINESS

        try:
            # 1. Find an unassigned number
            pool_response = (
                self._client.table("number_pool")
                .select("*")
                .eq("is_assigned", False)
                .limit(1)
                .execute()
            )
            
            if not pool_response.data:
                logger.error("db.assign_number.no_numbers_available")
                raise ValueError("No unassigned numbers left in the pool")
                
            number_row = pool_response.data[0]
            phone_number = number_row["phone_number"]
            
            # 2. Assign to business
            business_update = (
                self._client.table("businesses")
                .update({"phone_number": phone_number})
                .eq("id", business_id)
                .execute()
            )
            
            if not business_update.data:
                raise ValueError(f"Business {business_id} not found")
                
            # 3. Mark number as assigned
            (
                self._client.table("number_pool")
                .update({"is_assigned": True, "assigned_to": business_id})
                .eq("phone_number", phone_number)
                .execute()
            )
            
            return business_update.data[0]
        except Exception as exc:
            logger.error("db.assign_number.error", id=business_id, error=str(exc))
            return None

    # ── APPOINTMENTS ──

    async def create_appointment(
        self,
        business_id: str,
        patient_name: str,
        phone: str,
        appt_date: str,
        appt_time: str,
        service: str = "general",
        notes: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Book a new appointment — called by the MCP appointments server
        after Claude confirms the slot is available.
        """
        if self._is_mock:
            mock_appt = {
                "id": str(uuid.uuid4()),
                "business_id": business_id,
                "patient_name": patient_name,
                "phone": phone,
                "date": appt_date,
                "time": appt_time,
                "service": service,
                "status": "confirmed",
                "notes": notes,
                "created_by": "ai_agent",
            }
            logger.info("mock.create_appointment", appointment=mock_appt)
            return mock_appt

        try:
            response = (
                self._client.table("appointments")
                .insert({
                    "business_id": business_id,
                    "patient_name": patient_name,
                    "phone": phone,
                    "date": appt_date,
                    "time": appt_time,
                    "service": service,
                    "status": "confirmed",
                    "notes": notes,
                    "created_by": "ai_agent",
                })
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as exc:
            logger.error("db.create_appointment.error", business_id=business_id, error=str(exc))
            return None

    async def get_available_slots(self, business_id: str, appt_date: str) -> list[str]:
        """
        Return available time slots for a given date.

        Compares all possible slots against already-booked appointments
        to find openings. In mock mode, removes a few slots to simulate bookings.
        """
        if self._is_mock:
            # ── Simulate some slots being taken ──
            booked = {"10:00", "14:00", "16:00"}
            available = [s for s in MOCK_SLOTS if s not in booked]
            logger.debug("mock.get_available_slots", date=appt_date, available=available)
            return available

        try:
            response = (
                self._client.table("appointments")
                .select("time")
                .eq("business_id", business_id)
                .eq("date", appt_date)
                .neq("status", "cancelled")
                .execute()
            )
            booked_times = {row["time"] for row in (response.data or [])}
            available = [s for s in MOCK_SLOTS if s not in booked_times]
            return available
        except Exception as exc:
            logger.error("db.get_available_slots.error", date=appt_date, error=str(exc))
            return MOCK_SLOTS  # ── Fallback: return all slots rather than blocking bookings ──

    async def cancel_appointment(self, phone: str, appt_date: str) -> bool:
        """Cancel an appointment by phone + date — called by MCP server."""
        if self._is_mock:
            logger.info("mock.cancel_appointment", phone=phone, date=appt_date)
            return True

        try:
            response = (
                self._client.table("appointments")
                .update({"status": "cancelled"})
                .eq("phone", phone)
                .eq("date", appt_date)
                .eq("status", "confirmed")
                .execute()
            )
            return bool(response.data)
        except Exception as exc:
            logger.error("db.cancel_appointment.error", phone=phone, error=str(exc))
            return False

    async def get_appointments_for_day(
        self, business_id: str, appt_date: str
    ) -> list[dict[str, Any]]:
        """Get all appointments for a business on a specific date."""
        if self._is_mock:
            return [
                {
                    "id": "mock-appt-001",
                    "patient_name": "Rahul Kumar",
                    "phone": "+919876543210",
                    "date": appt_date,
                    "time": "10:00",
                    "service": "General Consultation",
                    "status": "confirmed",
                },
                {
                    "id": "mock-appt-002",
                    "patient_name": "Priya Singh",
                    "phone": "+919876543211",
                    "date": appt_date,
                    "time": "14:00",
                    "service": "Blood Test",
                    "status": "confirmed",
                },
            ]

        try:
            response = (
                self._client.table("appointments")
                .select("*")
                .eq("business_id", business_id)
                .eq("date", appt_date)
                .order("time")
                .execute()
            )
            return response.data or []
        except Exception as exc:
            logger.error("db.get_appointments_for_day.error", date=appt_date, error=str(exc))
            return []

    async def update_appointment_status(self, appointment_id: str, status: str, notes: str | None = None) -> bool:
        """Update an appointment's status."""
        if self._is_mock:
            logger.info("mock.update_appointment_status", id=appointment_id, status=status)
            return True

        try:
            update_data = {"status": status}
            if notes is not None:
                update_data["notes"] = notes
                
            response = (
                self._client.table("appointments")
                .update(update_data)
                .eq("id", appointment_id)
                .execute()
            )
            return bool(response.data)
        except Exception as exc:
            logger.error("db.update_appointment_status.error", id=appointment_id, error=str(exc))
            return False

    # ── CALL LOGS ──

    async def create_call_log(
        self,
        business_id: str,
        call_sid: str,
        caller_phone: str,
        duration_sec: int = 0,
        outcome: str = "unknown",
        language: str = "hi-IN",
        transcript: list[dict[str, str]] | None = None,
        summary: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Record a completed call — called when the call ends.

        The transcript is stored as a JSONB array of {role, text} objects
        so the dashboard can display the full conversation.
        """
        if self._is_mock:
            mock_log = {
                "id": str(uuid.uuid4()),
                "business_id": business_id,
                "call_sid": call_sid,
                "caller_phone": caller_phone,
                "duration_sec": duration_sec,
                "outcome": outcome,
                "language": language,
                "transcript": transcript or [],
                "summary": summary,
            }
            logger.info("mock.create_call_log", call_log=mock_log)
            return mock_log

        try:
            response = (
                self._client.table("call_logs")
                .insert({
                    "business_id": business_id,
                    "call_sid": call_sid,
                    "caller_phone": caller_phone,
                    "duration_sec": duration_sec,
                    "outcome": outcome,
                    "language": language,
                    "transcript": transcript or [],
                    "summary": summary,
                })
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as exc:
            logger.error("db.create_call_log.error", call_sid=call_sid, error=str(exc))
            return None

    async def get_call_logs(
        self,
        business_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Fetch recent call logs for the dashboard — paginated."""
        if self._is_mock:
            return [
                {
                    "id": "mock-call-001",
                    "caller_phone": "+919876543210",
                    "duration_sec": 45,
                    "outcome": "appointment_booked",
                    "language": "hi-IN",
                    "summary": "Caller booked a general consultation for tomorrow at 10 AM",
                    "timestamp": datetime.now().isoformat(),
                },
                {
                    "id": "mock-call-002",
                    "caller_phone": "+919876543211",
                    "duration_sec": 30,
                    "outcome": "info_provided",
                    "language": "hi-IN",
                    "summary": "Caller asked about clinic timings and consultation fee",
                    "timestamp": datetime.now().isoformat(),
                },
            ]

        try:
            response = (
                self._client.table("call_logs")
                .select("*")
                .eq("business_id", business_id)
                .order("timestamp", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
            return response.data or []
        except Exception as exc:
            logger.error("db.get_call_logs.error", business_id=business_id, error=str(exc))
            return []

    # ── WHATSAPP MESSAGES ──

    async def log_whatsapp_message(
        self,
        business_id: str,
        phone: str,
        message: str,
        direction: str = "outbound",
        status: str = "sent",
        message_type: str = "text",
        meta_message_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Log a WhatsApp message — called after sending confirmation."""
        if self._is_mock:
            mock_msg = {
                "id": str(uuid.uuid4()),
                "business_id": business_id,
                "phone": phone,
                "message": message,
                "direction": direction,
                "status": status,
            }
            logger.info("mock.log_whatsapp_message", msg=mock_msg)
            return mock_msg

        try:
            response = (
                self._client.table("whatsapp_messages")
                .insert({
                    "business_id": business_id,
                    "phone": phone,
                    "message": message,
                    "direction": direction,
                    "status": status,
                    "message_type": message_type,
                    "meta_message_id": meta_message_id,
                })
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as exc:
            logger.error("db.log_whatsapp.error", phone=phone, error=str(exc))
            return None

    # ── DASHBOARD ANALYTICS ──

    async def get_call_stats(self, business_id: str, days: int = 7) -> dict[str, Any]:
        """
        Aggregate call statistics for the dashboard home page.

        Returns total calls, appointments booked, missed calls,
        and outcome breakdown for the last N days.
        """
        if self._is_mock:
            return {
                "total_calls": 47,
                "appointments_booked": 23,
                "missed_calls": 5,
                "escalated": 3,
                "avg_duration_sec": 42,
                "conversion_rate": 48.9,
            }

        try:
            from datetime import timedelta
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            response = (
                self._client.table("call_logs")
                .select("outcome, duration_sec")
                .eq("business_id", business_id)
                .gte("timestamp", cutoff)
                .execute()
            )

            logs = response.data or []
            total = len(logs)
            booked = sum(1 for l in logs if l["outcome"] == "appointment_booked")
            missed = sum(1 for l in logs if l["outcome"] == "missed")
            escalated = sum(1 for l in logs if l["outcome"] == "escalated_to_human")
            durations = [l["duration_sec"] for l in logs if l["duration_sec"]]

            return {
                "total_calls": total,
                "appointments_booked": booked,
                "missed_calls": missed,
                "escalated": escalated,
                "avg_duration_sec": sum(durations) // max(len(durations), 1),
                "conversion_rate": round((booked / max(total, 1)) * 100, 1),
            }
        except Exception as exc:
            logger.error("db.get_call_stats.error", business_id=business_id, error=str(exc))
            return {"total_calls": 0, "appointments_booked": 0, "missed_calls": 0}

    # ── HELPERS ──

    @property
    def _is_mock(self) -> bool:
        """Check if we should use mock data instead of Supabase."""
        return self._client is None or settings.MOCK_MODE


# ═══════════════════════════════════════════════════
# SINGLETON INSTANCE — import this directly
# ═══════════════════════════════════════════════════

db = DatabaseClient()
