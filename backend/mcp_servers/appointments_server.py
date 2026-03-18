"""
Indian Voice Agent — Appointments MCP Server

Model Context Protocol server that exposes appointment management
tools to the Claude AI agent during voice calls.

Tools provided:
1. book_appointment     — Book a new appointment
2. check_available_slots — Check open time slots for a date
3. cancel_appointment    — Cancel an existing appointment
4. get_appointments_for_day — List all appointments for a date

Each tool delegates to the shared database client (database/client.py),
which handles both Supabase and MOCK_MODE transparently.

Run standalone: python -m mcp_servers.appointments_server
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from config.settings import settings
from database.client import db

logger = structlog.get_logger(__name__)

# ── Create the MCP server instance ──
server = Server("appointments-server")


# ═══════════════════════════════════════════════════
# TOOL DEFINITIONS — Registered with the MCP server
# ═══════════════════════════════════════════════════

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return all appointment management tools available to Claude."""
    return [
        Tool(
            name="book_appointment",
            description=(
                "Book a new appointment at the business. "
                "Call this ONLY after confirming the slot is available "
                "and collecting all required details from the caller."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "business_id": {
                        "type": "string",
                        "description": "UUID of the business to book at",
                    },
                    "patient_name": {
                        "type": "string",
                        "description": "Full name of the patient/customer",
                    },
                    "phone": {
                        "type": "string",
                        "description": "Phone number with country code, e.g. +919876543210",
                    },
                    "date": {
                        "type": "string",
                        "description": "Appointment date in YYYY-MM-DD format",
                    },
                    "time": {
                        "type": "string",
                        "description": "Appointment time in HH:MM format (24-hour), e.g. 10:00",
                    },
                    "service": {
                        "type": "string",
                        "description": "Type of service requested (e.g. General Consultation, Haircut)",
                    },
                },
                "required": ["business_id", "patient_name", "phone", "date", "time", "service"],
            },
        ),
        Tool(
            name="check_available_slots",
            description=(
                "Check which time slots are available for appointments "
                "on a specific date. Always call this BEFORE booking to "
                "confirm the requested time is open."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "business_id": {
                        "type": "string",
                        "description": "UUID of the business to check slots for",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date to check in YYYY-MM-DD format",
                    },
                },
                "required": ["business_id", "date"],
            },
        ),
        Tool(
            name="cancel_appointment",
            description=(
                "Cancel an existing confirmed appointment. "
                "Requires the patient's phone number and appointment date."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "Patient's phone number used during booking",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date of appointment to cancel, in YYYY-MM-DD format",
                    },
                },
                "required": ["phone", "date"],
            },
        ),
        Tool(
            name="get_appointments_for_day",
            description=(
                "Get a list of all appointments for a specific date. "
                "Useful for checking the day's schedule or finding "
                "a patient's appointment details."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "business_id": {
                        "type": "string",
                        "description": "UUID of the business",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date to list appointments for, in YYYY-MM-DD format",
                    },
                },
                "required": ["business_id", "date"],
            },
        ),
    ]


# ═══════════════════════════════════════════════════
# TOOL HANDLERS — Execute the actual operations
# ═══════════════════════════════════════════════════

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    Route tool calls to the appropriate handler.

    Each handler delegates to the shared database client,
    which handles both Supabase and mock mode transparently.
    """
    logger.info("mcp.appointments.tool_call", tool=name, args=arguments)

    try:
        if name == "book_appointment":
            result = await _handle_book_appointment(arguments)
        elif name == "check_available_slots":
            result = await _handle_check_slots(arguments)
        elif name == "cancel_appointment":
            result = await _handle_cancel(arguments)
        elif name == "get_appointments_for_day":
            result = await _handle_get_day(arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, default=str))]

    except Exception as exc:
        logger.error("mcp.appointments.error", tool=name, error=str(exc))
        error_result = {"error": str(exc), "tool": name}
        return [TextContent(type="text", text=json.dumps(error_result))]


async def _handle_book_appointment(args: dict[str, Any]) -> dict[str, Any]:
    """
    Book a new appointment after validating inputs.

    Validates the date is not in the past, the time slot is available,
    then creates the appointment in the database.
    """
    business_id = args["business_id"]
    patient_name = args["patient_name"]
    phone = args["phone"]
    appt_date = args["date"]
    appt_time = args["time"]
    service = args["service"]

    # ── Validate date is not in the past ──
    try:
        requested_date = datetime.strptime(appt_date, "%Y-%m-%d").date()
        if requested_date < datetime.now().date():
            return {
                "success": False,
                "message": "Cannot book appointments in the past. Please choose a future date.",
            }
    except ValueError:
        return {
            "success": False,
            "message": f"Invalid date format: {appt_date}. Use YYYY-MM-DD format.",
        }

    # ── Validate time format ──
    try:
        datetime.strptime(appt_time, "%H:%M")
    except ValueError:
        return {
            "success": False,
            "message": f"Invalid time format: {appt_time}. Use HH:MM format (e.g., 10:00).",
        }

    # ── Check if slot is available before booking ──
    available_slots = await db.get_available_slots(business_id, appt_date)
    if appt_time not in available_slots:
        return {
            "success": False,
            "message": f"Time slot {appt_time} is not available on {appt_date}.",
            "available_slots": available_slots,
        }

    # ── Create the appointment ──
    appointment = await db.create_appointment(
        business_id=business_id,
        patient_name=patient_name,
        phone=phone,
        appt_date=appt_date,
        appt_time=appt_time,
        service=service,
    )

    if appointment:
        logger.info(
            "mcp.appointments.booked",
            appointment_id=appointment.get("id"),
            patient=patient_name,
            date=appt_date,
            time=appt_time,
        )
        return {
            "success": True,
            "appointment_id": appointment.get("id"),
            "patient_name": patient_name,
            "phone": phone,
            "date": appt_date,
            "time": appt_time,
            "service": service,
            "status": "confirmed",
            "message": f"Appointment booked for {patient_name} on {appt_date} at {appt_time}.",
        }

    return {
        "success": False,
        "message": "Failed to create appointment. Please try again.",
    }


async def _handle_check_slots(args: dict[str, Any]) -> dict[str, Any]:
    """
    Check available time slots for a given date.

    Returns a list of open time slots and a human-readable message.
    """
    business_id = args["business_id"]
    appt_date = args["date"]

    # ── Validate date format ──
    try:
        requested_date = datetime.strptime(appt_date, "%Y-%m-%d").date()
    except ValueError:
        return {"error": f"Invalid date format: {appt_date}. Use YYYY-MM-DD format."}

    available_slots = await db.get_available_slots(business_id, appt_date)

    # ── Format morning and afternoon slots for readability ──
    morning = [s for s in available_slots if int(s.split(":")[0]) < 12]
    afternoon = [s for s in available_slots if int(s.split(":")[0]) >= 12]

    logger.info(
        "mcp.appointments.slots_checked",
        date=appt_date,
        total=len(available_slots),
    )

    return {
        "date": appt_date,
        "available_slots": available_slots,
        "morning_slots": morning,
        "afternoon_slots": afternoon,
        "total_available": len(available_slots),
        "message": (
            f"{len(available_slots)} slots available on {appt_date}."
            if available_slots
            else f"No slots available on {appt_date}."
        ),
    }


async def _handle_cancel(args: dict[str, Any]) -> dict[str, Any]:
    """
    Cancel an existing appointment by phone number and date.

    Returns success/failure and a confirmation message.
    """
    phone = args["phone"]
    appt_date = args["date"]

    success = await db.cancel_appointment(phone=phone, appt_date=appt_date)

    if success:
        logger.info("mcp.appointments.cancelled", phone=phone, date=appt_date)
        return {
            "success": True,
            "phone": phone,
            "date": appt_date,
            "message": f"Appointment on {appt_date} has been cancelled successfully.",
        }

    return {
        "success": False,
        "message": f"Could not find a confirmed appointment for {phone} on {appt_date}.",
    }


async def _handle_get_day(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get all appointments for a specific date.

    Returns a list of appointment details, ordered by time.
    """
    business_id = args["business_id"]
    appt_date = args["date"]

    appointments = await db.get_appointments_for_day(business_id, appt_date)

    logger.info(
        "mcp.appointments.day_fetched",
        date=appt_date,
        count=len(appointments),
    )

    return {
        "date": appt_date,
        "appointments": appointments,
        "total": len(appointments),
        "message": (
            f"{len(appointments)} appointments on {appt_date}."
            if appointments
            else f"No appointments scheduled for {appt_date}."
        ),
    }


# ═══════════════════════════════════════════════════
# IN-PROCESS TOOL HANDLER
# Used when calling tools directly from the voice agent
# without going through MCP stdio transport.
# ═══════════════════════════════════════════════════

async def handle_tool_direct(
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute an appointment tool directly (without MCP transport).

    Used by the voice agent's tool handler when MCP servers
    run in-process rather than as separate stdio processes.
    """
    if tool_name == "book_appointment":
        return await _handle_book_appointment(tool_input)
    elif tool_name == "check_available_slots":
        return await _handle_check_slots(tool_input)
    elif tool_name == "cancel_appointment":
        return await _handle_cancel(tool_input)
    elif tool_name == "get_appointments_for_day":
        return await _handle_get_day(tool_input)
    else:
        return {"error": f"Unknown appointment tool: {tool_name}"}


# ═══════════════════════════════════════════════════
# ENTRY POINT — Run as standalone MCP server via stdio
# ═══════════════════════════════════════════════════

async def main() -> None:
    """Run the appointments MCP server over stdio transport."""
    logger.info("mcp.appointments.starting", mock_mode=settings.MOCK_MODE)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
