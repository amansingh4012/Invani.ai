"""
Indian Voice Agent — Unified MCP Tool Registry

Central registry that aggregates tools from ALL three MCP servers
into a single dispatcher. Used by:

1. Voice agents — via handle_tool() in ClinicAgent/SalonAgent
2. Test endpoints — via /test/mcp-tool for manual verification
3. Future: CLI debugging, batch processing

This replaces scattered imports by giving one clean interface:

    from mcp_servers.registry import tool_registry
    result = await tool_registry.execute("book_appointment", {...})
    all_tools = tool_registry.list_all()

"""

from __future__ import annotations

import json
from typing import Any

import structlog

from mcp_servers.appointments_server import (
    handle_tool_direct as appointments_handle,
    list_tools as appointments_list_tools,
)
from mcp_servers.whatsapp_server import (
    handle_tool_direct as whatsapp_handle,
    list_tools as whatsapp_list_tools,
)
from mcp_servers.calendar_server import (
    handle_tool_direct as calendar_handle,
    list_tools as calendar_list_tools,
)

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════
# TOOL ROUTING TABLE — maps tool name → server handler
# ═══════════════════════════════════════════════════

APPOINTMENT_TOOLS: set[str] = {
    "book_appointment",
    "check_available_slots",
    "cancel_appointment",
    "get_appointments_for_day",
}

WHATSAPP_TOOLS: set[str] = {
    "send_whatsapp",
    "send_appointment_confirmation",
    "send_reminder",
}

CALENDAR_TOOLS: set[str] = {
    "add_calendar_event",
    "get_day_schedule",
}


class MCPToolRegistry:
    """
    Unified registry that routes tool calls to the correct MCP server.

    Why a registry? Because the voice agent shouldn't need to know
    which server handles which tool — it just calls execute() and
    the registry dispatches to the right handler.
    """

    def __init__(self) -> None:
        """Initialize the registry with all known tool sets."""
        self._all_tool_names: set[str] = APPOINTMENT_TOOLS | WHATSAPP_TOOLS | CALENDAR_TOOLS
        logger.info(
            "mcp_registry.initialized",
            total_tools=len(self._all_tool_names),
            appointment_tools=len(APPOINTMENT_TOOLS),
            whatsapp_tools=len(WHATSAPP_TOOLS),
            calendar_tools=len(CALENDAR_TOOLS),
        )

    async def execute(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a tool by name, routing to the correct MCP server.

        Args:
            tool_name: Name of the MCP tool (e.g., "book_appointment")
            tool_input: Tool arguments as a dictionary

        Returns:
            Tool execution result as a dictionary
        """
        if tool_name not in self._all_tool_names:
            logger.warning("mcp_registry.unknown_tool", tool=tool_name)
            return {"error": f"Unknown tool: {tool_name}", "available_tools": sorted(self._all_tool_names)}

        logger.info("mcp_registry.execute", tool=tool_name)

        try:
            if tool_name in APPOINTMENT_TOOLS:
                return await appointments_handle(tool_name, tool_input)
            elif tool_name in WHATSAPP_TOOLS:
                return await whatsapp_handle(tool_name, tool_input)
            elif tool_name in CALENDAR_TOOLS:
                return await calendar_handle(tool_name, tool_input)
            else:
                return {"error": f"Tool routing failed for: {tool_name}"}

        except Exception as exc:
            logger.error("mcp_registry.execute_error", tool=tool_name, error=str(exc))
            return {"error": str(exc), "tool": tool_name}

    async def list_all(self) -> list[dict[str, Any]]:
        """
        Return tool definitions from all three MCP servers.

        Fetches the full Tool schema from each server's list_tools()
        and returns them in a flat list — useful for introspection
        and for the /test/mcp-tool endpoint's help output.
        """
        all_tools: list[dict[str, Any]] = []

        try:
            # ── Fetch from each server's list_tools function ──
            appt_tools = await appointments_list_tools()
            wa_tools = await whatsapp_list_tools()
            cal_tools = await calendar_list_tools()

            for tool in appt_tools:
                all_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "server": "appointments",
                    "input_schema": tool.inputSchema,
                })

            for tool in wa_tools:
                all_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "server": "whatsapp",
                    "input_schema": tool.inputSchema,
                })

            for tool in cal_tools:
                all_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "server": "calendar",
                    "input_schema": tool.inputSchema,
                })

        except Exception as exc:
            logger.error("mcp_registry.list_error", error=str(exc))

        return all_tools

    def get_server_for_tool(self, tool_name: str) -> str | None:
        """Return which MCP server handles a given tool name."""
        if tool_name in APPOINTMENT_TOOLS:
            return "appointments"
        if tool_name in WHATSAPP_TOOLS:
            return "whatsapp"
        if tool_name in CALENDAR_TOOLS:
            return "calendar"
        return None

    @property
    def tool_names(self) -> list[str]:
        """Return a sorted list of all available tool names."""
        return sorted(self._all_tool_names)

    @property
    def tool_count(self) -> int:
        """Return total number of registered tools."""
        return len(self._all_tool_names)


# ═══════════════════════════════════════════════════
# SINGLETON — Import this directly
# ═══════════════════════════════════════════════════

tool_registry = MCPToolRegistry()


if __name__ == "__main__":
    import asyncio

    async def test_registry() -> None:
        """Smoke test: list and execute tools via the registry."""
        print("Testing MCP Tool Registry...\n")

        # ── List all tools ──
        print(f"Total tools: {tool_registry.tool_count}")
        print(f"Tool names: {tool_registry.tool_names}\n")

        all_tools = await tool_registry.list_all()
        for tool in all_tools:
            print(f"  [{tool['server']}] {tool['name']}: {tool['description'][:60]}...")
        print()

        # ── Test check_available_slots ──
        result = await tool_registry.execute(
            "check_available_slots",
            {"business_id": "mock-business-001", "date": "2025-03-20"},
        )
        print(f"check_available_slots result:\n{json.dumps(result, indent=2)}\n")

        # ── Test book_appointment ──
        result = await tool_registry.execute(
            "book_appointment",
            {
                "business_id": "mock-business-001",
                "patient_name": "Rahul Kumar",
                "phone": "+919876543210",
                "date": "2025-03-20",
                "time": "11:00",
                "service": "General Consultation",
            },
        )
        print(f"book_appointment result:\n{json.dumps(result, indent=2)}\n")

        # ── Test send_appointment_confirmation ──
        result = await tool_registry.execute(
            "send_appointment_confirmation",
            {
                "business_id": "mock-business-001",
                "phone": "+919876543210",
                "patient_name": "Rahul Kumar",
                "date": "2025-03-20",
                "time": "11:00",
                "business_name": "Dr. Sharma Clinic",
            },
        )
        print(f"send_appointment_confirmation result:\n{json.dumps(result, indent=2)}\n")

        # ── Test get_day_schedule ──
        result = await tool_registry.execute(
            "get_day_schedule",
            {"business_id": "mock-business-001", "date": "2025-03-20"},
        )
        print(f"get_day_schedule result:\n{json.dumps(result, indent=2)}\n")

        # ── Test unknown tool ──
        result = await tool_registry.execute("nonexistent_tool", {})
        print(f"Unknown tool result:\n{json.dumps(result, indent=2)}\n")

        print("✅ MCP Tool Registry test passed!")

    asyncio.run(test_registry())
