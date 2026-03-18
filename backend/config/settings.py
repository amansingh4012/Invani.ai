"""
Indian Voice Agent — Application Configuration

Loads all settings from environment variables with sensible defaults.
Uses pydantic-settings for validation and type coercion.

Usage:
    from config.settings import settings
    print(settings.MOCK_MODE)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for the Indian Voice Agent backend.

    All values are loaded from .env file or environment variables.
    MOCK_MODE=true enables local testing without live API credentials.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Mode Flags ──
    MOCK_MODE: bool = Field(
        default=True,
        description="When True, uses mock services instead of live APIs",
    )
    DEBUG: bool = Field(default=True, description="Enable debug logging")

    # ── Server ──
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # ── Supabase ──
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # ── Anthropic (Claude AI) ──
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # ── Sarvam AI (Hindi STT + TTS) ──
    SARVAM_API_KEY: str = ""
    SARVAM_STT_URL: str = "https://api.sarvam.ai/speech-to-text-translate"
    SARVAM_TTS_URL: str = "https://api.sarvam.ai/text-to-speech"

    # ── Exotel (Indian Telephony) ──
    EXOTEL_SID: str = ""
    EXOTEL_API_KEY: str = ""
    EXOTEL_API_TOKEN: str = ""
    EXOTEL_SUBDOMAIN: str = ""
    EXOTEL_CALLER_ID: str = ""
    EXOTEL_WEBHOOK_SECRET: str = ""

    # ── WhatsApp (Meta Cloud API) ──
    WHATSAPP_API_URL: str = "https://graph.facebook.com/v21.0"
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""

    # ── Voice Pipeline ──
    SARVAM_STT_LANGUAGE: str = "hi-IN"
    SARVAM_TTS_SPEAKER: str = "meera"
    SARVAM_TTS_SPEED: float = 1.0
    SARVAM_TTS_PITCH: float = 0.0
    AUDIO_SAMPLE_RATE: int = 8000
    AUDIO_CHANNELS: int = 1
    VAD_THRESHOLD: float = 0.5
    VAD_MIN_SILENCE_MS: int = 300

    # ── Business Defaults ──
    DEFAULT_LANGUAGE: Literal["hi-IN", "en-IN"] = "hi-IN"
    DEFAULT_BUSINESS_TYPE: Literal["clinic", "salon", "coaching", "shop"] = "clinic"
    MAX_CALL_DURATION_SEC: int = 300
    ESCALATION_PHONE: str = "+919999999999"

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse comma-separated ALLOWED_ORIGINS into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @property
    def is_supabase_configured(self) -> bool:
        """Check if Supabase credentials are set (not empty)."""
        return bool(self.SUPABASE_URL and self.SUPABASE_ANON_KEY)

    @property
    def is_sarvam_configured(self) -> bool:
        """Check if Sarvam AI credentials are set."""
        return bool(self.SARVAM_API_KEY)

    @property
    def is_exotel_configured(self) -> bool:
        """Check if Exotel credentials are set."""
        return bool(self.EXOTEL_SID and self.EXOTEL_API_KEY)

    @property
    def is_whatsapp_configured(self) -> bool:
        """Check if WhatsApp credentials are set."""
        return bool(self.WHATSAPP_PHONE_NUMBER_ID and self.WHATSAPP_ACCESS_TOKEN)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached singleton Settings instance.

    Uses lru_cache so the .env file is only read once per process.
    """
    return Settings()


# ── Convenience alias — import this directly ──
settings = get_settings()
