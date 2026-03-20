"""
Indian Voice Agent — Calendar MCP Server

Model Context Protocol server that exposes calendar management
tools to the Claude AI agent during voice calls.

Tools provided:
1. add_calendar_event  — Add an event to the business calendar
2. get_day_schedule    — Get the full schedule for a specific day

This server manages the business owner's daily schedule view.
In MOCK_MODE, returns realistic fake schedule data.

Run standalone: python -m mcp_servers.calendar_server
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
server = Server("calendar-server")

# ── In-memory calendar events (for mock mode / MVP) ──
# In production, this would integrate with Google Calendar or similar
_today_str = datetime.now().strftime("%Y-%m-%d")

_mock_calendar: list[dict[str, Any]] = [
    {
        "id": "cal-001",
        "title": "Dr. Sharma — Morning OPD",
        "date": _today_str,
        "time": "09:00",
        "duration_min": 180,
        "type": "block",
    },
    {
        "id": "cal-002",
        "title": "Lunch Break",
        "date": _today_str,
        "time": "13:00",
        "duration_min": 60,
        "type": "break",
    },
    {
        "id": "cal-003",
        "title": "Dr. Sharma — Evening OPD",
        "date": _today_str,
        "time": "14:00",
        "duration_min": 240,
        "type": "block",
    },
]


# ═══════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return all calendar management tools available to Claude."""
    return [
        Tool(
            name="add_calendar_event",
            description=(
                "Add a new event to the business calendar. Use this for "
                "scheduling blocks, breaks, meetings, or any time-based "
                "events that affect appointment availability."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "business_id": {
                        "type": "string",
                        "description": "UUID of the business",
                    },
                    "title": {
                        "type": "string",
                        "description": "Title/name of the calendar event",
                    },
                    "date": {
                        "type": "string",
                        "description": "Event date in YYYY-MM-DD format",
                    },
                    "time": {
                        "type": "string",
                        "description": "Event start time in HH:MM format (24-hour)",
                    },
                    "duration_min": {
                        "type": "integer",
                        "description": "Duration in minutes, default 30",
                    },
                    "event_type": {
                        "type": "string",
                        "description": "Type of event: 'appointment', 'block', 'break', 'meeting'",
                        "enum": ["appointment", "block", "break", "meeting"],
                    },
                },
                "required": ["business_id", "title", "date", "time"],
            },
        ),
        Tool(
            name="get_day_schedule",
            description=(
                "Get the complete schedule for a business on a specific day. "
                "Returns all appointments and calendar events, ordered by time. "
                "Useful for understanding how busy a day is."
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
                        "description": "Date to get schedule for, in YYYY-MM-DD format",
                    },
                },
                "required": ["business_id", "date"],
            },
        ),
    ]


# ═══════════════════════════════════════════════════
# TOOL HANDLERS
# ═══════════════════════════════════════════════════

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Route calendar tool calls to the appropriate handler."""
    logger.info("mcp.calendar.tool_call", tool=name, args=arguments)

    try:
        if name == "add_calendar_event":
            result = await _handle_add_event(arguments)
        elif name == "get_day_schedule":
            result = await _handle_get_schedule(arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, default=str))]

    except Exception as exc:
        logger.error("mcp.calendar.error", tool=name, error=str(exc))
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]


async def _handle_add_event(args: dict[str, Any]) -> dict[str, Any]:
    """
    Add a new event to the business calendar.

    In MOCK_MODE, stores in the in-memory list.
    In production, this would create a Google Calendar event.
    """
    business_id = args["business_id"]
    title = args["title"]
    event_date = args["date"]
    event_time = args["time"]
    duration_min = args.get("duration_min", 30)
    event_type = args.get("event_type", "appointment")

    # ── Validate date format ──
    try:
        datetime.strptime(event_date, "%Y-%m-%d")
    except ValueError:
        return {"success": False, "error": f"Invalid date format: {event_date}"}

    # ── Validate time format ──
    try:
        datetime.strptime(event_time, "%H:%M")
    except ValueError:
        return {"success": False, "error": f"Invalid time format: {event_time}"}

    import uuid
    event = {
        "id": f"cal-{uuid.uuid4().hex[:8]}",
        "business_id": business_id,
        "title": title,
        "date": event_date,
        "time": event_time,
        "duration_min": duration_min,
        "type": event_type,
        "created_at": datetime.now().isoformat(),
    }

    # ── Store the event ──
    _mock_calendar.append(event)

    logger.info(
        "mcp.calendar.event_added",
        event_id=event["id"],
        title=title,
        date=event_date,
        time=event_time,
    )

    return {
        "success": True,
        "event_id": event["id"],
        "title": title,
        "date": event_date,
        "time": event_time,
        "duration_min": duration_min,
        "type": event_type,
        "message": f"Calendar event '{title}' added for {event_date} at {event_time}.",
    }


async def _handle_get_schedule(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get the complete schedule for a specific day.

    Combines calendar events AND booked appointments into
    a single chronological schedule. Gives the business owner
    and the AI agent a full picture of the day.
    """
    business_id = args["business_id"]
    schedule_date = args["date"]

    # ── Get calendar events for this date ──
    events = [
        e for e in _mock_calendar
        if e.get("date") == schedule_date
    ]

    # ── Get appointments from database ──
    appointments = await db.get_appointments_for_day(business_id, schedule_date)

    # ── Convert appointments to schedule format ──
    appointment_events = [
        {
            "id": appt.get("id", "unknown"),
            "title": f"📋 {appt.get('patient_name', 'Patient')} — {appt.get('service', 'Consultation')}",
            "date": schedule_date,
            "time": appt.get("time", "00:00"),
            "duration_min": 30,
            "type": "appointment",
            "status": appt.get("status", "confirmed"),
            "patient_name": appt.get("patient_name"),
            "patient_phone": appt.get("phone"),
        }
        for appt in appointments
    ]

    # ── Combine and sort by time ──
    full_schedule = sorted(
        events + appointment_events,
        key=lambda x: x.get("time", "00:00"),
    )

    # ── Calculate occupancy ──
    total_min = sum(e.get("duration_min", 30) for e in full_schedule)
    working_hours = 10  # ── Assume 10-hour working day ──
    occupancy_pct = round(min(total_min / (working_hours * 60) * 100, 100), 1)

    logger.info(
        "mcp.calendar.schedule_fetched",
        date=schedule_date,
        events=len(events),
        appointments=len(appointment_events),
        occupancy=occupancy_pct,
    )

    return {
        "date": schedule_date,
        "schedule": full_schedule,
        "calendar_events": len(events),
        "appointments": len(appointment_events),
        "total_items": len(full_schedule),
        "total_minutes_booked": total_min,
        "occupancy_percent": occupancy_pct,
        "message": (
            f"{len(full_schedule)} items on {schedule_date} ({occupancy_pct}% occupied)."
            if full_schedule
            else f"Nothing scheduled for {schedule_date}."
        ),
    }


# ═══════════════════════════════════════════════════
# IN-PROCESS HANDLER
# ═══════════════════════════════════════════════════

async def handle_tool_direct(
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    """Execute a calendar tool directly without MCP transport."""
    if tool_name == "add_calendar_event":
        return await _handle_add_event(tool_input)
    elif tool_name == "get_day_schedule":
        return await _handle_get_schedule(tool_input)
    else:
        return {"error": f"Unknown calendar tool: {tool_name}"}


# ═══════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════

async def main() -> None:
    """Run the calendar MCP server over stdio transport."""
    logger.info("mcp.calendar.starting", mock_mode=settings.MOCK_MODE)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
