"""
Indian Voice Agent — Clinic Agent

Specialized voice agent for medical clinics. Extends BaseVoiceAgent with:
- Clinic-specific system prompt (loaded from prompts/clinic.txt)
- Business FAQ injection (services, timings, fees)
- Tool schemas for appointment booking, WhatsApp, calendar

Usage:
    agent = ClinicAgent(business_config=config, call_sid="call-123", caller_phone="+919876543210")
    response = await agent.process_text("Mujhe appointment chahiye")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from agents.base_agent import BaseVoiceAgent
from database.client import db

logger = structlog.get_logger(__name__)

# ── Path to the clinic prompt template ──
PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "clinic.txt"


class ClinicAgent(BaseVoiceAgent):
    """
    Voice agent specialized for medical clinics.

    Handles:
    - Appointment booking (with slot availability checking)
    - FAQ about fees, timings, services
    - Emergency routing
    - WhatsApp appointment confirmations
    """

    def get_system_prompt(self) -> str:
        """
        Load the clinic prompt and inject business-specific details.

        Reads prompts/clinic.txt and appends the actual business
        config (services, timings, fees) so Claude has real data.
        """
        # ── Load base prompt template ──
        try:
            base_prompt = PROMPT_FILE.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning("clinic_agent.prompt_missing", path=str(PROMPT_FILE))
            base_prompt = "You are a friendly medical clinic receptionist AI. Speak in Hindi. Keep replies to 2 sentences max."

        # ── Inject business-specific configuration ──
        config = self.business.get("config_json", {})
        business_context = self._build_business_context(config)

        return f"{base_prompt}\n\n── THIS CLINIC'S ACTUAL DETAILS ──\n{business_context}"

    def _build_business_context(self, config: dict[str, Any]) -> str:
        """
        Format business config into readable context for the system prompt.

        Claude uses this to answer questions about THIS specific clinic.
        """
        sections: list[str] = []

        sections.append(f"Clinic Name: {self.business.get('name', 'Our Clinic')}")

        if "services" in config:
            services = ", ".join(config["services"])
            sections.append(f"Services Available: {services}")

        if "timings" in config:
            timings = config["timings"]
            timing_str = " | ".join(f"{k}: {v}" for k, v in timings.items())
            sections.append(f"Working Hours: {timing_str}")

        if "consultation_fee" in config:
            sections.append(f"Consultation Fee: ₹{config['consultation_fee']}")

        if "followup_fee" in config:
            sections.append(f"Follow-up Fee: ₹{config['followup_fee']}")

        if "address" in config:
            sections.append(f"Address: {config['address']}")

        if "doctors" in config:
            doctors = ", ".join(config["doctors"])
            sections.append(f"Doctors Available: {doctors}")

        return "\n".join(sections)

    def get_tools(self) -> list[dict[str, Any]]:
        """
        Return Claude tool schemas for clinic operations.

        These map to MCP server actions that the agent can invoke
        during a conversation to perform real actions.
        """
        return [
            {
                "name": "check_available_slots",
                "description": "Check available appointment slots for a specific date at this clinic. Returns a list of available time slots.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "Date to check slots for, in YYYY-MM-DD format. Example: 2025-03-20",
                        },
                    },
                    "required": ["date"],
                },
            },
            {
                "name": "book_appointment",
                "description": "Book an appointment at this clinic. Call this ONLY after confirming the slot is available and getting all required details from the caller.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "patient_name": {
                            "type": "string",
                            "description": "Full name of the patient",
                        },
                        "phone": {
                            "type": "string",
                            "description": "Patient's phone number with country code, e.g. +919876543210",
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
                            "description": "Type of consultation or service requested",
                        },
                    },
                    "required": ["patient_name", "phone", "date", "time", "service"],
                },
            },
            {
                "name": "cancel_appointment",
                "description": "Cancel an existing appointment. Requires the patient's phone number and appointment date.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "phone": {
                            "type": "string",
                            "description": "Patient's phone number that was used to book",
                        },
                        "date": {
                            "type": "string",
                            "description": "Date of the appointment to cancel, in YYYY-MM-DD format",
                        },
                    },
                    "required": ["phone", "date"],
                },
            },
            {
                "name": "send_appointment_confirmation",
                "description": "Send a WhatsApp confirmation message to the patient after booking. Call this right after a successful booking.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "phone": {
                            "type": "string",
                            "description": "Patient's WhatsApp number with country code",
                        },
                        "patient_name": {
                            "type": "string",
                            "description": "Patient's name for the message",
                        },
                        "date": {
                            "type": "string",
                            "description": "Appointment date",
                        },
                        "time": {
                            "type": "string",
                            "description": "Appointment time",
                        },
                    },
                    "required": ["phone", "patient_name", "date", "time"],
                },
            },
        ]




if __name__ == "__main__":
    import asyncio

    async def test_clinic_agent() -> None:
        """Smoke test: create a clinic agent and process text queries."""
        from database.client import MOCK_BUSINESS

        print("Testing ClinicAgent in MOCK_MODE...\n")

        agent = ClinicAgent(
            business_config=MOCK_BUSINESS,
            call_sid="test-clinic-001",
            caller_phone="+919876543210",
        )

        # ── Test system prompt loading ──
        prompt = agent.get_system_prompt()
        print(f"System prompt loaded: {len(prompt)} chars")
        print(f"First 200 chars:\n{prompt[:200]}\n")

        # ── Test tool schemas ──
        tools = agent.get_tools()
        print(f"Tools available: {[t['name'] for t in tools]}\n")

        # ── Test text processing ──
        test_messages = [
            "Mujhe appointment chahiye kal ke liye",
            "Doctor ka fee kitna hai?",
            "Clinic kab tak khula rehta hai?",
        ]

        for msg in test_messages:
            print(f"User: {msg}")
            response = await agent.process_text(msg)
            print(f"AI: {response}\n")

        # ── Test tool handling directly ──
        slots_result = await agent.handle_tool("check_available_slots", {"date": "2025-03-20"})
        print(f"Available slots: {slots_result}\n")

        # ── End call ──
        call_log = await agent.on_call_end()
        print(f"Call log saved: {call_log}\n")

        print("✅ ClinicAgent test passed!")

    asyncio.run(test_clinic_agent())
