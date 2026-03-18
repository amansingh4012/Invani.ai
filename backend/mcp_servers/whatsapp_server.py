"""
Indian Voice Agent — WhatsApp MCP Server

Model Context Protocol server that exposes WhatsApp messaging
tools to the Claude AI agent during voice calls.

Tools provided:
1. send_whatsapp         — Send a generic WhatsApp text message
2. send_appointment_confirmation — Send a formatted booking confirmation
3. send_reminder         — Send appointment reminder before the visit

Uses Meta's official Cloud API in production.
In MOCK_MODE, logs messages to console instead of sending.

Run standalone: python -m mcp_servers.whatsapp_server
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from config.settings import settings
from database.client import db

logger = structlog.get_logger(__name__)

# ── Create the MCP server instance ──
server = Server("whatsapp-server")


# ═══════════════════════════════════════════════════
# META CLOUD API — WhatsApp message sender
# ═══════════════════════════════════════════════════

async def _send_via_meta_api(phone: str, message: str) -> dict[str, Any]:
    """
    Send a WhatsApp message using Meta's Cloud API.

    In MOCK_MODE, logs the message and returns a fake success response.
    In production, makes the actual API call to graph.facebook.com.
    """
    if settings.MOCK_MODE or not settings.is_whatsapp_configured:
        logger.info(
            "whatsapp.mock_send",
            phone=phone,
            message=message[:80],
        )
        return {
            "success": True,
            "mock": True,
            "message_id": "mock-wa-msg-001",
        }

    try:
        url = f"{settings.WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": phone.replace("+", ""),
                    "type": "text",
                    "text": {"body": message},
                },
            )
            response.raise_for_status()

            data = response.json()
            message_id = data.get("messages", [{}])[0].get("id", "unknown")

            logger.info("whatsapp.sent", phone=phone, message_id=message_id)
            return {
                "success": True,
                "message_id": message_id,
            }

    except httpx.TimeoutException:
        logger.error("whatsapp.timeout", phone=phone)
        return {"success": False, "error": "WhatsApp API timeout"}
    except Exception as exc:
        logger.error("whatsapp.send_error", phone=phone, error=str(exc))
        return {"success": False, "error": str(exc)}


# ═══════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return all WhatsApp messaging tools available to Claude."""
    return [
        Tool(
            name="send_whatsapp",
            description=(
                "Send a text message via WhatsApp to a phone number. "
                "Use for general messages, updates, or custom notifications."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "business_id": {
                        "type": "string",
                        "description": "UUID of the business sending the message",
                    },
                    "phone": {
                        "type": "string",
                        "description": "Recipient's phone number with country code, e.g. +919876543210",
                    },
                    "message": {
                        "type": "string",
                        "description": "The text message content to send",
                    },
                },
                "required": ["business_id", "phone", "message"],
            },
        ),
        Tool(
            name="send_appointment_confirmation",
            description=(
                "Send a formatted WhatsApp appointment confirmation message. "
                "Call this right after a successful booking to confirm "
                "the appointment details with the patient/customer."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "business_id": {
                        "type": "string",
                        "description": "UUID of the business",
                    },
                    "phone": {
                        "type": "string",
                        "description": "Patient's WhatsApp number with country code",
                    },
                    "patient_name": {
                        "type": "string",
                        "description": "Patient's name to include in the message",
                    },
                    "date": {
                        "type": "string",
                        "description": "Appointment date (YYYY-MM-DD or readable format)",
                    },
                    "time": {
                        "type": "string",
                        "description": "Appointment time",
                    },
                    "service": {
                        "type": "string",
                        "description": "Service/consultation type",
                    },
                    "business_name": {
                        "type": "string",
                        "description": "Name of the business for the message header",
                    },
                },
                "required": ["business_id", "phone", "patient_name", "date", "time"],
            },
        ),
        Tool(
            name="send_reminder",
            description=(
                "Send an appointment reminder via WhatsApp. "
                "Typically used the day before or morning of the appointment."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "business_id": {
                        "type": "string",
                        "description": "UUID of the business",
                    },
                    "phone": {
                        "type": "string",
                        "description": "Patient's phone number",
                    },
                    "patient_name": {
                        "type": "string",
                        "description": "Patient's name",
                    },
                    "date": {
                        "type": "string",
                        "description": "Appointment date",
                    },
                    "time": {
                        "type": "string",
                        "description": "Appointment time",
                    },
                    "business_name": {
                        "type": "string",
                        "description": "Name of the business",
                    },
                },
                "required": ["business_id", "phone", "patient_name", "date", "time"],
            },
        ),
    ]


# ═══════════════════════════════════════════════════
# TOOL HANDLERS
# ═══════════════════════════════════════════════════

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Route WhatsApp tool calls to the appropriate handler."""
    logger.info("mcp.whatsapp.tool_call", tool=name, args=arguments)

    try:
        if name == "send_whatsapp":
            result = await _handle_send_whatsapp(arguments)
        elif name == "send_appointment_confirmation":
            result = await _handle_send_confirmation(arguments)
        elif name == "send_reminder":
            result = await _handle_send_reminder(arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, default=str))]

    except Exception as exc:
        logger.error("mcp.whatsapp.error", tool=name, error=str(exc))
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]


async def _handle_send_whatsapp(args: dict[str, Any]) -> dict[str, Any]:
    """Send a generic WhatsApp text message."""
    business_id = args["business_id"]
    phone = args["phone"]
    message = args["message"]

    # ── Send the message ──
    send_result = await _send_via_meta_api(phone, message)

    # ── Log to database for audit trail ──
    await db.log_whatsapp_message(
        business_id=business_id,
        phone=phone,
        message=message,
        direction="outbound",
        status="sent" if send_result.get("success") else "failed",
        meta_message_id=send_result.get("message_id"),
    )

    return {
        "success": send_result.get("success", False),
        "phone": phone,
        "message_id": send_result.get("message_id"),
        "message": "WhatsApp message sent successfully." if send_result.get("success") else "Failed to send.",
    }


async def _handle_send_confirmation(args: dict[str, Any]) -> dict[str, Any]:
    """
    Send a formatted appointment confirmation message.

    Builds a clean, professional confirmation with all booking details.
    """
    business_id = args["business_id"]
    phone = args["phone"]
    name = args["patient_name"]
    date = args["date"]
    appt_time = args["time"]
    service = args.get("service", "Consultation")
    business_name = args.get("business_name", "Our Clinic")

    # ── Build the confirmation message ──
    message = (
        f"✅ *Appointment Confirmed!*\n\n"
        f"👤 *Name:* {name}\n"
        f"🏥 *{business_name}*\n"
        f"📅 *Date:* {date}\n"
        f"🕐 *Time:* {appt_time}\n"
        f"💊 *Service:* {service}\n\n"
        f"Please arrive 10 minutes early.\n"
        f"For cancellation, please call us.\n\n"
        f"Thank you! 🙏"
    )

    send_result = await _send_via_meta_api(phone, message)

    await db.log_whatsapp_message(
        business_id=business_id,
        phone=phone,
        message=message,
        direction="outbound",
        status="sent" if send_result.get("success") else "failed",
        message_type="template",
        meta_message_id=send_result.get("message_id"),
    )

    return {
        "success": send_result.get("success", False),
        "phone": phone,
        "message_preview": message[:100],
        "message": f"Appointment confirmation sent to {phone}",
    }


async def _handle_send_reminder(args: dict[str, Any]) -> dict[str, Any]:
    """
    Send an appointment reminder message.

    Different tone from confirmation — friendly nudge for tomorrow.
    """
    business_id = args["business_id"]
    phone = args["phone"]
    name = args["patient_name"]
    date = args["date"]
    appt_time = args["time"]
    business_name = args.get("business_name", "Our Clinic")

    message = (
        f"🔔 *Appointment Reminder*\n\n"
        f"Hi {name}! 👋\n\n"
        f"Aapka appointment kal hai:\n"
        f"📅 {date} | 🕐 {appt_time}\n"
        f"🏥 {business_name}\n\n"
        f"Kripya samay par aa jayein. Dhanyavaad! 🙏"
    )

    send_result = await _send_via_meta_api(phone, message)

    await db.log_whatsapp_message(
        business_id=business_id,
        phone=phone,
        message=message,
        direction="outbound",
        status="sent" if send_result.get("success") else "failed",
        message_type="template",
        meta_message_id=send_result.get("message_id"),
    )

    return {
        "success": send_result.get("success", False),
        "phone": phone,
        "message": f"Reminder sent to {phone} for {date} at {appt_time}",
    }


# ═══════════════════════════════════════════════════
# IN-PROCESS HANDLER — Direct invocation from voice agent
# ═══════════════════════════════════════════════════

async def handle_tool_direct(
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    """Execute a WhatsApp tool directly without MCP transport."""
    if tool_name == "send_whatsapp":
        return await _handle_send_whatsapp(tool_input)
    elif tool_name == "send_appointment_confirmation":
        return await _handle_send_confirmation(tool_input)
    elif tool_name == "send_reminder":
        return await _handle_send_reminder(tool_input)
    else:
        return {"error": f"Unknown WhatsApp tool: {tool_name}"}


# ═══════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════

async def main() -> None:
    """Run the WhatsApp MCP server over stdio transport."""
    logger.info("mcp.whatsapp.starting", mock_mode=settings.MOCK_MODE)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
