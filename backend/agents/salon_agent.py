"""
Indian Voice Agent — Salon Agent

Specialized voice agent for beauty salons. Extends BaseVoiceAgent with:
- Salon-specific system prompt (loaded from prompts/salon.txt)
- Business FAQ injection (services, pricing, stylists)
- Tool schemas for appointment booking, WhatsApp, calendar

Usage:
    agent = SalonAgent(business_config=config, call_sid="call-456", caller_phone="+919876543210")
    response = await agent.process_text("Haircut ka appointment chahiye")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from agents.base_agent import BaseVoiceAgent
from database.client import db

logger = structlog.get_logger(__name__)

# ── Path to the salon prompt template ──
PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "salon.txt"


class SalonAgent(BaseVoiceAgent):
    """
    Voice agent specialized for beauty salons.

    Handles:
    - Appointment booking for beauty services
    - Price inquiries for haircut, facial, bridal packages
    - Stylist preference handling
    - WhatsApp appointment confirmations
    """

    def get_system_prompt(self) -> str:
        """
        Load the salon prompt and inject business-specific details.

        Reads prompts/salon.txt and appends actual salon config
        (services, pricing, stylists) so Claude has real data.
        """
        try:
            base_prompt = PROMPT_FILE.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning("salon_agent.prompt_missing", path=str(PROMPT_FILE))
            base_prompt = "You are a friendly beauty salon receptionist AI. Speak in Hindi. Keep replies to 2 sentences max."

        config = self.business.get("config_json", {})
        business_context = self._build_business_context(config)

        return f"{base_prompt}\n\n── THIS SALON'S ACTUAL DETAILS ──\n{business_context}"

    def _build_business_context(self, config: dict[str, Any]) -> str:
        """Format salon config into readable context for the system prompt."""
        sections: list[str] = []

        sections.append(f"Salon Name: {self.business.get('name', 'Our Salon')}")

        if "services" in config:
            services = ", ".join(config["services"])
            sections.append(f"Services Available: {services}")

        if "timings" in config:
            timings = config["timings"]
            timing_str = " | ".join(f"{k}: {v}" for k, v in timings.items())
            sections.append(f"Working Hours: {timing_str}")

        if "prices" in config:
            prices = config["prices"]
            price_lines = [f"  {service}: ₹{price}" for service, price in prices.items()]
            sections.append("Price List:\n" + "\n".join(price_lines))

        if "stylists" in config:
            stylists = ", ".join(config["stylists"])
            sections.append(f"Stylists Available: {stylists}")

        if "address" in config:
            sections.append(f"Address: {config['address']}")

        return "\n".join(sections)

    def get_tools(self) -> list[dict[str, Any]]:
        """
        Return Claude tool schemas for salon operations.

        Same core tools as clinic but with salon-specific descriptions.
        """
        return [
            {
                "name": "check_available_slots",
                "description": "Check available appointment slots for a specific date at this salon. Returns available time slots for booking.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "Date to check slots for, in YYYY-MM-DD format",
                        },
                    },
                    "required": ["date"],
                },
            },
            {
                "name": "book_appointment",
                "description": "Book a salon appointment. Call ONLY after confirming slot availability and collecting customer details.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "patient_name": {
                            "type": "string",
                            "description": "Customer's full name",
                        },
                        "phone": {
                            "type": "string",
                            "description": "Customer's phone number with country code",
                        },
                        "date": {
                            "type": "string",
                            "description": "Appointment date in YYYY-MM-DD format",
                        },
                        "time": {
                            "type": "string",
                            "description": "Appointment time in HH:MM format (24-hour)",
                        },
                        "service": {
                            "type": "string",
                            "description": "Type of beauty service requested (e.g., Haircut, Facial, Bridal Package)",
                        },
                    },
                    "required": ["patient_name", "phone", "date", "time", "service"],
                },
            },
            {
                "name": "cancel_appointment",
                "description": "Cancel an existing salon appointment by phone number and date.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "phone": {
                            "type": "string",
                            "description": "Customer's phone number used during booking",
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
                "description": "Send WhatsApp confirmation to the customer after booking a salon appointment.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "phone": {
                            "type": "string",
                            "description": "Customer's WhatsApp number",
                        },
                        "patient_name": {
                            "type": "string",
                            "description": "Customer's name for the message",
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

    async def test_salon_agent() -> None:
        """Smoke test the salon agent."""
        from database.client import MOCK_BUSINESS

        # ── Use salon config for testing ──
        salon_config = {
            **MOCK_BUSINESS,
            "name": "Glamour Beauty Salon",
            "type": "salon",
            "config_json": {
                "greeting": "Hello ji! Glamour Salon mein aapka swagat hai!",
                "services": ["Haircut", "Hair Spa", "Facial", "Bridal Package"],
                "timings": {"tue_sun": "10 AM - 8 PM", "monday": "Closed"},
                "address": "456 FC Road, Pune",
            },
        }

        print("Testing SalonAgent in MOCK_MODE...\n")

        agent = SalonAgent(
            business_config=salon_config,
            call_sid="test-salon-001",
            caller_phone="+919876543211",
        )

        test_messages = [
            "Haircut ka appointment chahiye",
            "Bridal package ka rate kya hai?",
        ]

        for msg in test_messages:
            print(f"User: {msg}")
            response = await agent.process_text(msg)
            print(f"AI: {response}\n")

        await agent.on_call_end()
        print("✅ SalonAgent test passed!")

    asyncio.run(test_salon_agent())
