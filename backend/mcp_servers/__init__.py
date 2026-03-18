# MCP Servers package — tool servers for appointments, WhatsApp, calendar
from mcp_servers.appointments_server import handle_tool_direct as appointments_handler
from mcp_servers.whatsapp_server import handle_tool_direct as whatsapp_handler
from mcp_servers.calendar_server import handle_tool_direct as calendar_handler
from mcp_servers.registry import tool_registry

__all__ = [
    "appointments_handler",
    "whatsapp_handler",
    "calendar_handler",
    "tool_registry",
]
