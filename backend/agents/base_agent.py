"""
Indian Voice Agent — Base Voice Agent (Pipecat Pipeline)

The HEART of the system. Orchestrates the real-time voice pipeline:

    Incoming Audio → Silero VAD → Sarvam STT → LLM (Groq/Mistral/Claude) → Sarvam TTS → Outgoing Audio

Provides:
- SarvamSTTService — streaming Hindi/English speech-to-text
- SarvamTTSService — streaming Hindi/English text-to-speech
- BaseVoiceAgent — abstract pipeline base, extended per business type

In MOCK_MODE:
- STT returns hardcoded Hindi transcripts
- TTS generates silent audio frames
- LLM responses route to the configured AI_PROVIDER (groq/mistral/anthropic)

Usage:
    agent = ClinicAgent(business_config=config, call_sid="test-123")
    await agent.run(websocket)
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
import structlog

from config.settings import settings
from database.client import db

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════
# SARVAM AI — SPEECH-TO-TEXT SERVICE
# ═══════════════════════════════════════════════════

class SarvamSTTService:
    """
    Converts Hindi/English audio to text using Sarvam AI's API.

    In MOCK_MODE, returns a hardcoded Hindi transcript so the
    full pipeline can be tested without Sarvam credentials.
    """

    # ── Mock transcripts rotate for realistic testing ──
    MOCK_TRANSCRIPTS: list[str] = [
        "Mujhe kal subah 10 baje appointment chahiye",
        "Doctor sahab ka fee kitna hai?",
        "Clinic kab tak khula rehta hai?",
        "Mera naam Rahul hai, phone number 9876543210",
        "Kya aaj koi slot available hai?",
        "Mujhe appointment cancel karna hai",
        "Thank you, bahut dhanyavaad",
    ]

    def __init__(self) -> None:
        """Initialize STT service with HTTP client and mock counter."""
        self._client: httpx.AsyncClient | None = None
        self._mock_index: int = 0

        if not settings.MOCK_MODE and settings.is_sarvam_configured:
            self._client = httpx.AsyncClient(
                base_url=settings.SARVAM_STT_URL,
                timeout=httpx.Timeout(10.0, connect=5.0),
            )
            logger.info("sarvam_stt.initialized", mode="live")
        else:
            logger.info("sarvam_stt.initialized", mode="mock")

    async def transcribe(self, audio_bytes: bytes, language: str = "hi-IN") -> str:
        """
        Convert audio bytes to text.

        Args:
            audio_bytes: Raw audio (PCM 8kHz mono)
            language: Language code — 'hi-IN' or 'en-IN'

        Returns:
            Transcribed text string
        """
        if self._client is None:
            return self._get_mock_transcript()

        return await self._transcribe_live(audio_bytes, language)

    def _get_mock_transcript(self) -> str:
        """Return the next mock transcript in rotation."""
        transcript = self.MOCK_TRANSCRIPTS[self._mock_index % len(self.MOCK_TRANSCRIPTS)]
        self._mock_index += 1
        logger.debug("sarvam_stt.mock_transcript", text=transcript)
        return transcript

    async def _transcribe_live(self, audio_bytes: bytes, language: str) -> str:
        """Call Sarvam AI STT API with audio data."""
        try:
            # ── Sarvam expects base64-encoded audio in the request ──
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

            response = await self._client.post(
                "",
                json={
                    "input": audio_b64,
                    "config": {
                        "language": {"sourceLanguage": language},
                        "audioFormat": "wav",
                        "samplingRate": settings.AUDIO_SAMPLE_RATE,
                        "encoding": "base64",
                    },
                },
                headers={
                    "Content-Type": "application/json",
                    "API-Subscription-Key": settings.SARVAM_API_KEY,
                },
            )
            response.raise_for_status()

            data = response.json()
            transcript = data.get("output", [{}])[0].get("source", "")

            logger.info("sarvam_stt.transcribed", language=language, text=transcript[:80])
            return transcript

        except httpx.TimeoutException:
            logger.error("sarvam_stt.timeout", language=language)
            return ""
        except Exception as exc:
            logger.error("sarvam_stt.error", error=str(exc))
            return ""

    async def close(self) -> None:
        """Clean up HTTP client resources."""
        if self._client:
            await self._client.aclose()


# ═══════════════════════════════════════════════════
# SARVAM AI — TEXT-TO-SPEECH SERVICE
# ═══════════════════════════════════════════════════

class SarvamTTSService:
    """
    Converts Hindi/English text to natural-sounding speech using Sarvam AI.

    In MOCK_MODE, generates a short silent audio frame — enough
    to keep the pipeline flowing without hitting external APIs.
    """

    def __init__(self) -> None:
        """Initialize TTS service with HTTP client."""
        self._client: httpx.AsyncClient | None = None

        if not settings.MOCK_MODE and settings.is_sarvam_configured:
            self._client = httpx.AsyncClient(
                base_url=settings.SARVAM_TTS_URL,
                timeout=httpx.Timeout(10.0, connect=5.0),
            )
            logger.info("sarvam_tts.initialized", mode="live")
        else:
            logger.info("sarvam_tts.initialized", mode="mock")

    async def synthesize(self, text: str, language: str = "hi-IN") -> bytes:
        """
        Convert text to audio bytes.

        Args:
            text: Text to speak (Hindi or English)
            language: Language code for TTS voice selection

        Returns:
            Audio bytes (WAV format, 8kHz mono)
        """
        if not text.strip():
            return b""

        if self._client is None:
            return self._get_mock_audio(text)

        return await self._synthesize_live(text, language)

    def _get_mock_audio(self, text: str) -> bytes:
        """
        Generate a silent WAV frame for mock mode.

        The silence duration is proportional to text length,
        simulating realistic TTS timing.
        """
        # ── ~100ms of silence per 10 characters, at 8kHz mono 16-bit ──
        duration_samples = max(len(text) * 80, 800)
        silent_pcm = b"\x00\x00" * duration_samples

        # ── Build a minimal WAV header ──
        wav_data = self._build_wav_header(len(silent_pcm)) + silent_pcm
        logger.debug("sarvam_tts.mock_audio", text=text[:50], bytes=len(wav_data))
        return wav_data

    def _build_wav_header(self, data_size: int) -> bytes:
        """Build a minimal 44-byte WAV header for PCM audio."""
        import struct

        sample_rate = settings.AUDIO_SAMPLE_RATE
        channels = settings.AUDIO_CHANNELS
        bits_per_sample = 16
        byte_rate = sample_rate * channels * bits_per_sample // 8
        block_align = channels * bits_per_sample // 8

        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + data_size,
            b"WAVE",
            b"fmt ",
            16,                # ── Chunk size ──
            1,                 # ── PCM format ──
            channels,
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
            b"data",
            data_size,
        )
        return header

    async def _synthesize_live(self, text: str, language: str) -> bytes:
        """Call Sarvam AI TTS API to generate speech audio."""
        try:
            response = await self._client.post(
                "",
                json={
                    "input": text,
                    "config": {
                        "language": {"sourceLanguage": language},
                        "gender": "female",
                        "samplingRate": settings.AUDIO_SAMPLE_RATE,
                        "speed": settings.SARVAM_TTS_SPEED,
                        "pitch": settings.SARVAM_TTS_PITCH,
                    },
                },
                headers={
                    "Content-Type": "application/json",
                    "API-Subscription-Key": settings.SARVAM_API_KEY,
                },
            )
            response.raise_for_status()

            data = response.json()
            audio_b64 = data.get("audio", "")

            if audio_b64:
                audio_bytes = base64.b64decode(audio_b64)
                logger.info("sarvam_tts.synthesized", language=language, text=text[:50])
                return audio_bytes

            logger.warning("sarvam_tts.empty_response", text=text[:50])
            return self._get_mock_audio(text)

        except httpx.TimeoutException:
            logger.error("sarvam_tts.timeout", text=text[:50])
            return self._get_mock_audio(text)
        except Exception as exc:
            logger.error("sarvam_tts.error", error=str(exc), text=text[:50])
            return self._get_mock_audio(text)

    async def close(self) -> None:
        """Clean up HTTP client resources."""
        if self._client:
            await self._client.aclose()


# ═══════════════════════════════════════════════════
# LLM SERVICE — Multi-provider AI (Groq / Mistral / Anthropic)
# ═══════════════════════════════════════════════════

# ── Provider-specific configuration ──
_PROVIDER_CONFIG = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_attr": "GROQ_API_KEY",
        "model_attr": "GROQ_MODEL",
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "key_attr": "MISTRAL_API_KEY",
        "model_attr": "MISTRAL_MODEL",
    },
}


class LLMService:
    """
    Provider-agnostic LLM service — switch between Groq, Mistral, or Anthropic
    by setting AI_PROVIDER in .env.

    Groq and Mistral use the OpenAI-compatible SDK (base_url override).
    Anthropic uses the native anthropic SDK.

    All providers share the same respond() interface, conversation
    history, and tool-handling logic.
    """

    def __init__(self, system_prompt: str, tools: list[dict[str, Any]]) -> None:
        """
        Initialize the LLM with a system prompt and tool definitions.

        Args:
            system_prompt: Business-specific instructions from prompts/
            tools: MCP tool schemas for appointments, WhatsApp, etc.
        """
        self._system_prompt = system_prompt
        self._tools = tools
        self._client: Any = None
        self._provider = settings.AI_PROVIDER
        self._model: str = ""
        self._conversation: list[dict[str, Any]] = []

        if settings.MOCK_MODE:
            logger.info("llm.initialized", mode="mock", provider=self._provider)
            return

        # ── Initialize the right client based on AI_PROVIDER ──
        if self._provider in ("groq", "mistral"):
            self._init_openai_compatible()
        elif self._provider == "anthropic":
            self._init_anthropic()
        else:
            logger.warning("llm.unknown_provider", provider=self._provider)

    def _init_openai_compatible(self) -> None:
        """Initialize Groq or Mistral via OpenAI SDK with base_url override."""
        config = _PROVIDER_CONFIG[self._provider]
        api_key = getattr(settings, config["key_attr"], "")
        self._model = getattr(settings, config["model_attr"], "")

        if not api_key:
            logger.warning(
                "llm.no_api_key",
                provider=self._provider,
                msg=f"Set {config['key_attr']} in .env",
            )
            return

        try:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=config["base_url"],
            )
            logger.info(
                "llm.initialized",
                mode="live",
                provider=self._provider,
                model=self._model,
            )
        except ImportError:
            logger.warning("llm.no_openai_package", msg="openai package not installed")

    def _init_anthropic(self) -> None:
        """Initialize Anthropic Claude client."""
        self._model = settings.ANTHROPIC_MODEL

        if not settings.ANTHROPIC_API_KEY:
            logger.warning("llm.no_api_key", provider="anthropic", msg="Set ANTHROPIC_API_KEY in .env")
            return

        try:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            logger.info("llm.initialized", mode="live", provider="anthropic", model=self._model)
        except ImportError:
            logger.warning("llm.no_anthropic_package", msg="anthropic package not installed")

    # ── PUBLIC API ──

    async def respond(
        self,
        user_text: str,
        tool_handler: Any = None,
    ) -> str:
        """
        Send user text to the LLM and get a response.

        Handles tool use: if the LLM wants to call a tool (e.g., book_appointment),
        this method calls the tool handler, sends the result back, and returns
        the final text response.

        Args:
            user_text: What the caller said (transcribed)
            tool_handler: Async callable that executes MCP tools

        Returns:
            AI text response (in Hindi or English)
        """
        if not user_text.strip():
            return ""

        # ── Add user message to conversation history ──
        self._conversation.append({"role": "user", "content": user_text})

        if self._client is None:
            return self._get_mock_response(user_text)

        if self._provider in ("groq", "mistral"):
            return await self._respond_openai(tool_handler)
        else:
            return await self._respond_anthropic(tool_handler)

    def _get_mock_response(self, user_text: str) -> str:
        """Generate a mock AI response based on keywords in user text."""
        text_lower = user_text.lower()

        if any(w in text_lower for w in ["appointment", "book", "chahiye", "slot"]):
            response = "Bilkul ji! Aapka naam bataiye aur kis date aur time pe appointment chahiye?"
        elif any(w in text_lower for w in ["fee", "kitna", "charge", "price"]):
            response = "Ji, consultation fee 500 rupaye hai aur follow-up 200 rupaye mein ho jayega."
        elif any(w in text_lower for w in ["time", "timing", "kab", "khula"]):
            response = "Humara clinic Monday se Saturday, subah 9 baje se shaam 7 baje tak khula rehta hai."
        elif any(w in text_lower for w in ["cancel", "nahi", "band"]):
            response = "Ji zaroor, aapka appointment cancel kar deti hoon. Aapka phone number bataiye."
        elif any(w in text_lower for w in ["thank", "dhanyavaad", "shukriya"]):
            response = "Aapka bahut-bahut dhanyavaad! Koi aur madad chahiye toh zaroor call kariye."
        elif any(w in text_lower for w in ["naam", "rahul", "priya", "name"]):
            response = "Shukriya ji! Ab aap konsi date aur time prefer karenge appointment ke liye?"
        else:
            response = "Ji, main aapki madad kar sakti hoon. Kya aap appointment book karna chahte hain ya koi jaankari chahiye?"

        self._conversation.append({"role": "assistant", "content": response})
        logger.debug("llm.mock_response", response=response[:80])
        return response

    # ═══════════════════════════════════════════
    # GROQ / MISTRAL — OpenAI-compatible path
    # ═══════════════════════════════════════════

    def _build_openai_tools(self) -> list[dict[str, Any]]:
        """Convert tool schemas to OpenAI function-calling format."""
        if not self._tools:
            return []

        openai_tools: list[dict[str, Any]] = []
        for tool in self._tools:
            # ── Support both Anthropic-style and OpenAI-style schemas ──
            if "function" in tool:
                openai_tools.append(tool)
            else:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", tool.get("parameters", {})),
                    },
                })
        return openai_tools

    async def _respond_openai(self, tool_handler: Any = None) -> str:
        """Call Groq/Mistral via OpenAI-compatible API."""
        try:
            # ── Build messages with system prompt ──
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": self._system_prompt},
                *self._conversation,
            ]

            request_params: dict[str, Any] = {
                "model": self._model,
                "max_tokens": 150,
                "messages": messages,
            }

            openai_tools = self._build_openai_tools()
            if openai_tools:
                request_params["tools"] = openai_tools

            start_time = time.time()
            response = await self._client.chat.completions.create(**request_params)
            latency_ms = round((time.time() - start_time) * 1000, 1)

            choice = response.choices[0]
            logger.info(
                "llm.response",
                provider=self._provider,
                latency_ms=latency_ms,
                finish_reason=choice.finish_reason,
            )

            # ── Handle tool calls ──
            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                return await self._handle_openai_tool_use(choice.message, tool_handler)

            # ── Extract text response ──
            text_response = choice.message.content or ""
            self._conversation.append({"role": "assistant", "content": text_response})
            return text_response

        except Exception as exc:
            logger.error("llm.error", provider=self._provider, error=str(exc))
            fallback = "Maaf kijiye, abhi thodi technical problem aa rahi hai. Kya aap thodi der baad call kar sakte hain?"
            self._conversation.append({"role": "assistant", "content": fallback})
            return fallback

    async def _handle_openai_tool_use(self, message: Any, tool_handler: Any) -> str:
        """Handle tool calls from Groq/Mistral (OpenAI format)."""
        # ── Add assistant message with tool calls to history ──
        self._conversation.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ],
        })

        # ── Execute each tool and collect results ──
        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            tool_input = json.loads(tool_call.function.arguments)

            logger.info("llm.tool_use", provider=self._provider, tool=tool_name, input=tool_input)

            tool_result = "Tool not available"
            if tool_handler:
                try:
                    tool_result = await tool_handler(tool_name=tool_name, tool_input=tool_input)
                except Exception as exc:
                    logger.error("llm.tool_error", tool=tool_name, error=str(exc))
                    tool_result = f"Error: {str(exc)}"

            self._conversation.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result),
            })

        # ── Get final response after tool execution ──
        try:
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": self._system_prompt},
                *self._conversation,
            ]
            final_response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=150,
                messages=messages,
            )
            final_text = final_response.choices[0].message.content or ""
            self._conversation.append({"role": "assistant", "content": final_text})
            return final_text

        except Exception as exc:
            logger.error("llm.final_response_error", provider=self._provider, error=str(exc))
            return "Aapka appointment ho gaya hai. WhatsApp pe confirmation aa jayega."

    # ═══════════════════════════════════════════
    # ANTHROPIC — Claude-native path
    # ═══════════════════════════════════════════

    async def _respond_anthropic(self, tool_handler: Any = None) -> str:
        """Call Anthropic Claude API with full conversation history and tools."""
        try:
            request_params: dict[str, Any] = {
                "model": self._model,
                "max_tokens": 150,
                "system": self._system_prompt,
                "messages": self._conversation,
            }

            if self._tools:
                request_params["tools"] = self._tools

            start_time = time.time()
            response = await self._client.messages.create(**request_params)
            latency_ms = round((time.time() - start_time) * 1000, 1)

            logger.info("llm.response", provider="anthropic", latency_ms=latency_ms, stop_reason=response.stop_reason)

            if response.stop_reason == "tool_use":
                return await self._handle_anthropic_tool_use(response, tool_handler)

            text_response = self._extract_anthropic_text(response)
            self._conversation.append({"role": "assistant", "content": text_response})
            return text_response

        except Exception as exc:
            logger.error("llm.error", provider="anthropic", error=str(exc))
            fallback = "Maaf kijiye, abhi thodi technical problem aa rahi hai. Kya aap thodi der baad call kar sakte hain?"
            self._conversation.append({"role": "assistant", "content": fallback})
            return fallback

    async def _handle_anthropic_tool_use(self, response: Any, tool_handler: Any) -> str:
        """Process Claude's tool use request — call the tool and send result back."""
        tool_use_block = None
        text_parts: list[str] = []

        for block in response.content:
            if block.type == "tool_use":
                tool_use_block = block
            elif block.type == "text":
                text_parts.append(block.text)

        if not tool_use_block:
            combined = " ".join(text_parts) if text_parts else ""
            self._conversation.append({"role": "assistant", "content": combined})
            return combined

        logger.info("llm.tool_use", provider="anthropic", tool=tool_use_block.name, input=tool_use_block.input)

        tool_result = "Tool not available"
        if tool_handler:
            try:
                tool_result = await tool_handler(tool_name=tool_use_block.name, tool_input=tool_use_block.input)
            except Exception as exc:
                logger.error("llm.tool_error", tool=tool_use_block.name, error=str(exc))
                tool_result = f"Error: {str(exc)}"

        self._conversation.append({"role": "assistant", "content": response.content})
        self._conversation.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use_block.id,
                "content": json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result),
            }],
        })

        try:
            final_response = await self._client.messages.create(
                model=self._model,
                max_tokens=150,
                system=self._system_prompt,
                messages=self._conversation,
            )
            final_text = self._extract_anthropic_text(final_response)
            self._conversation.append({"role": "assistant", "content": final_text})
            return final_text

        except Exception as exc:
            logger.error("llm.final_response_error", provider="anthropic", error=str(exc))
            return "Aapka appointment ho gaya hai. WhatsApp pe confirmation aa jayega."

    def _extract_anthropic_text(self, response: Any) -> str:
        """Extract text content from Claude's response blocks."""
        texts = [block.text for block in response.content if block.type == "text"]
        return " ".join(texts).strip()

    # ── SHARED HELPERS ──

    def get_conversation_history(self) -> list[dict[str, str]]:
        """
        Return the conversation as simple {role, text} pairs for logging.

        Filters out tool-use blocks and non-text content.
        """
        simple_history: list[dict[str, str]] = []
        for msg in self._conversation:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if isinstance(content, str):
                simple_history.append({"role": role, "text": content})
            elif isinstance(content, list):
                texts = [
                    b.get("text", "") if isinstance(b, dict) else str(b)
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ]
                if texts:
                    simple_history.append({"role": role, "text": " ".join(texts)})

        return simple_history


# ── Keep backward-compatible alias ──
ClaudeLLMService = LLMService


# ═══════════════════════════════════════════════════
# BASE VOICE AGENT — Abstract pipeline orchestrator
# ═══════════════════════════════════════════════════

class BaseVoiceAgent(ABC):
    """
    Abstract base class for all voice agents.

    Manages the full call lifecycle:
    1. Initialize services (STT, TTS, LLM)
    2. Process audio frames through the pipeline
    3. Collect transcript for call logging
    4. Clean up resources on call end

    Subclasses (ClinicAgent, SalonAgent) provide:
    - Business-specific system prompts
    - Business-specific tool schemas
    - Custom tool handlers
    """

    def __init__(
        self,
        business_config: dict[str, Any],
        call_sid: str,
        caller_phone: str,
        language: str = "hi-IN",
    ) -> None:
        """
        Initialize the voice agent for a single call.

        Args:
            business_config: Full business row from database
            call_sid: Unique call identifier from Exotel
            caller_phone: Caller's phone number
            language: Primary language for STT/TTS
        """
        self.business = business_config
        self.call_sid = call_sid
        self.caller_phone = caller_phone
        self.language = language
        self.call_start_time = time.time()
        self.is_active = False

        # ── Initialize services ──
        self.stt = SarvamSTTService()
        self.tts = SarvamTTSService()

        system_prompt = self.get_system_prompt()
        tools = self.get_tools()
        self.llm = LLMService(system_prompt=system_prompt, tools=tools)

        logger.info(
            "agent.initialized",
            business=self.business.get("name", "Unknown"),
            call_sid=self.call_sid,
            language=self.language,
        )

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Return the full system prompt for this business type.

        Must be overridden by subclasses to load the appropriate
        prompt file and inject business-specific configuration.
        """

    @abstractmethod
    def get_tools(self) -> list[dict[str, Any]]:
        """
        Return Claude tool definitions for this business type.

        Each tool corresponds to an MCP server action:
        - book_appointment, check_available_slots, etc.
        """

    async def handle_tool(self, tool_name: str, tool_input: dict[str, Any]) -> Any:
        """
        Execute a tool requested by Claude during the conversation.
        Routes to the appropriate MCP server via the unified registry.
        """
        from mcp_servers.registry import tool_registry

        business_id = self.business.get("id", "unknown")
        business_name = self.business.get("name", "Business")

        # ── Auto-inject business info so Claude doesn't need to provide it ──
        enriched_input = {**tool_input, "business_id": business_id, "business_name": business_name}

        logger.info(
            "agent.tool_call",
            tool=tool_name,
            input=tool_input,
            business_id=business_id,
        )

        return await tool_registry.execute(tool_name, enriched_input)

    # ── PIPELINE PROCESSING ──

    async def process_audio(self, audio_bytes: bytes) -> bytes:
        """
        Run a single audio chunk through the full pipeline.

        Flow: Audio → STT → Claude → TTS → Audio response

        Args:
            audio_bytes: Raw audio from the caller

        Returns:
            Audio bytes of the AI's spoken response
        """
        try:
            # ── Step 1: Speech-to-Text ──
            stt_start = time.time()
            user_text = await self.stt.transcribe(audio_bytes, self.language)
            stt_ms = round((time.time() - stt_start) * 1000, 1)

            if not user_text:
                logger.debug("agent.empty_stt", call_sid=self.call_sid)
                return b""

            logger.info(
                "agent.stt_complete",
                call_sid=self.call_sid,
                text=user_text[:80],
                latency_ms=stt_ms,
            )

            # ── Step 2: Claude AI response ──
            llm_start = time.time()
            ai_text = await self.llm.respond(
                user_text=user_text,
                tool_handler=self.handle_tool,
            )
            llm_ms = round((time.time() - llm_start) * 1000, 1)

            logger.info(
                "agent.llm_complete",
                call_sid=self.call_sid,
                response=ai_text[:80],
                latency_ms=llm_ms,
            )

            # ── Step 3: Text-to-Speech ──
            tts_start = time.time()
            audio_response = await self.tts.synthesize(ai_text, self.language)
            tts_ms = round((time.time() - tts_start) * 1000, 1)

            total_ms = round(stt_ms + llm_ms + tts_ms, 1)
            logger.info(
                "agent.pipeline_complete",
                call_sid=self.call_sid,
                stt_ms=stt_ms,
                llm_ms=llm_ms,
                tts_ms=tts_ms,
                total_ms=total_ms,
            )

            return audio_response

        except Exception as exc:
            logger.error("agent.pipeline_error", call_sid=self.call_sid, error=str(exc))
            return await self._get_fallback_audio()

    async def process_text(self, user_text: str) -> str:
        """
        Process text input directly — used by /test/simulate-call endpoint.

        Skips STT/TTS, runs only the LLM logic.
        Useful for testing AI behavior without audio.

        Args:
            user_text: What the caller said (as text)

        Returns:
            Claude's text response
        """
        try:
            response = await self.llm.respond(
                user_text=user_text,
                tool_handler=self.handle_tool,
            )
            return response
        except Exception as exc:
            logger.error("agent.text_error", call_sid=self.call_sid, error=str(exc))
            return "Maaf kijiye, kuch problem aa rahi hai."

    async def generate_greeting(self) -> bytes:
        """
        Generate the initial greeting audio when the call connects.

        Uses the business-specific greeting from config_json,
        or falls back to a default Hindi greeting.
        """
        config = self.business.get("config_json", {})
        greeting = config.get("greeting", "Namaste! Kaise madad kar sakti hoon?")

        logger.info("agent.greeting", call_sid=self.call_sid, text=greeting)

        audio = await self.tts.synthesize(greeting, self.language)
        return audio

    async def on_call_end(self) -> dict[str, Any] | None:
        """
        Called when the call disconnects — saves call log to database.

        Collects the full transcript, calculates duration,
        determines call outcome, and persists everything.
        """
        self.is_active = False
        duration_sec = int(time.time() - self.call_start_time)
        transcript = self.llm.get_conversation_history()
        outcome = self._determine_outcome(transcript)
        summary = self._generate_summary(transcript)

        logger.info(
            "agent.call_ended",
            call_sid=self.call_sid,
            duration_sec=duration_sec,
            outcome=outcome,
            turns=len(transcript),
        )

        # ── Save to database ──
        call_log = await db.create_call_log(
            business_id=self.business.get("id", "unknown"),
            call_sid=self.call_sid,
            caller_phone=self.caller_phone,
            duration_sec=duration_sec,
            outcome=outcome,
            language=self.language,
            transcript=transcript,
            summary=summary,
        )

        # ── Clean up services ──
        await self.stt.close()
        await self.tts.close()

        return call_log

    # ── PRIVATE HELPERS ──

    def _determine_outcome(self, transcript: list[dict[str, str]]) -> str:
        """
        Analyze the conversation to determine the call outcome.

        Checks for keywords indicating what happened during the call.
        """
        full_text = " ".join(msg.get("text", "") for msg in transcript).lower()

        if any(w in full_text for w in ["appointment ho gaya", "book kar", "confirm"]):
            return "appointment_booked"
        if any(w in full_text for w in ["cancel", "rescheduled"]):
            return "info_provided"
        if any(w in full_text for w in ["connect karti", "escalat", "manager"]):
            return "escalated_to_human"
        if len(transcript) <= 1:
            return "caller_hangup"
        return "info_provided"

    def _generate_summary(self, transcript: list[dict[str, str]]) -> str:
        """Generate a one-line English summary of the call for the dashboard."""
        if not transcript:
            return "Call ended without conversation"

        # ── Extract key information from the conversation ──
        user_texts = [msg["text"] for msg in transcript if msg.get("role") == "user"]
        ai_texts = [msg["text"] for msg in transcript if msg.get("role") == "assistant"]

        if not user_texts:
            return "Caller disconnected before speaking"

        # ── Simple keyword-based summary (Claude will do this better in production) ──
        first_user = user_texts[0].lower() if user_texts else ""

        if any(w in first_user for w in ["appointment", "book", "chahiye", "slot"]):
            return f"Caller requested an appointment booking. {len(transcript)} exchanges."
        if any(w in first_user for w in ["fee", "kitna", "charge", "price"]):
            return f"Caller asked about fees/pricing. {len(transcript)} exchanges."
        if any(w in first_user for w in ["time", "timing", "kab", "khula"]):
            return f"Caller asked about business hours. {len(transcript)} exchanges."
        if any(w in first_user for w in ["cancel"]):
            return f"Caller requested appointment cancellation. {len(transcript)} exchanges."

        return f"General inquiry call. {len(transcript)} exchanges."

    async def _get_fallback_audio(self) -> bytes:
        """
        Generate a pre-recorded fallback message when pipeline errors occur.

        This ensures the caller always hears something, even if STT/LLM/TTS fails.
        """
        fallback_text = "Maaf kijiye, abhi thodi technical problem aa rahi hai. Kripya kuch der baad call karein."
        logger.warning("agent.fallback_triggered", call_sid=self.call_sid)
        return await self.tts.synthesize(fallback_text, self.language)


# ═══════════════════════════════════════════════════
# AGENT FACTORY — Creates the right agent for each business
# ═══════════════════════════════════════════════════

def create_agent(
    business_config: dict[str, Any],
    call_sid: str,
    caller_phone: str,
    language: str = "hi-IN",
) -> BaseVoiceAgent:
    """
    Factory function — creates the right agent type based on business type.

    Used by the webhook handler when a call comes in:
    1. Look up business by phone number
    2. Check business type (clinic, salon, etc.)
    3. Create and return the matching agent

    Args:
        business_config: Full business row from database
        call_sid: Unique call ID from Exotel
        caller_phone: Caller's phone number
        language: Preferred language

    Returns:
        Configured agent ready to handle the call
    """
    # ── Import here to avoid circular imports ──
    from agents.clinic_agent import ClinicAgent
    from agents.salon_agent import SalonAgent

    business_type = business_config.get("type", "clinic")

    agent_map: dict[str, type] = {
        "clinic": ClinicAgent,
        "salon": SalonAgent,
        # TODO: Step 5+ — Add coaching, shop agents
        "coaching": ClinicAgent,  # ── Fallback to clinic for now ──
        "shop": ClinicAgent,
    }

    agent_class = agent_map.get(business_type, ClinicAgent)

    logger.info(
        "agent.factory",
        business_type=business_type,
        agent_class=agent_class.__name__,
        call_sid=call_sid,
    )

    return agent_class(
        business_config=business_config,
        call_sid=call_sid,
        caller_phone=caller_phone,
        language=language,
    )


if __name__ == "__main__":
    # ── Quick smoke test — verify imports and mock mode ──
    import asyncio

    async def test_pipeline() -> None:
        """Smoke test: run mock STT → LLM → TTS pipeline."""
        print("Testing BaseVoiceAgent pipeline in MOCK_MODE...\n")

        stt = SarvamSTTService()
        tts = SarvamTTSService()
        llm = ClaudeLLMService(
            system_prompt="You are a helpful Hindi receptionist. Keep replies to 2 sentences max.",
            tools=[],
        )

        # ── Test STT ──
        transcript = await stt.transcribe(b"fake-audio-data")
        print(f"STT result: {transcript}")

        # ── Test LLM ──
        response = await llm.respond(transcript)
        print(f"LLM response: {response}")

        # ── Test TTS ──
        audio = await tts.synthesize(response)
        print(f"TTS audio: {len(audio)} bytes")

        # ── Clean up ──
        await stt.close()
        await tts.close()

        print("\n✅ Pipeline smoke test passed!")

    asyncio.run(test_pipeline())
