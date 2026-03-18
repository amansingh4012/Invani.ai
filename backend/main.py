"""
Indian Voice Agent — FastAPI Application Entry Point

Starts the FastAPI server with:
- REST API routes for the dashboard
- WebSocket endpoint for Pipecat voice pipeline
- Exotel webhook handler for incoming calls
- Health check endpoint for Railway deployment
- Simulate-call endpoint for local testing

Run: python main.py
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import structlog
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from api.middleware import setup_middleware, verify_exotel_signature
from api.routes.calls import router as calls_router
from api.routes.appointments import router as appointments_router
from api.routes.businesses import router as businesses_router
from config.settings import settings
from mcp_servers.registry import tool_registry

logger = structlog.get_logger(__name__)

# ── Track active calls for dashboard "live calls" feature ──
active_calls: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifecycle manager.

    Startup: log config, verify connections.
    Shutdown: clean up resources gracefully.
    """
    # ── STARTUP ──
    logger.info(
        "server.starting",
        host=settings.HOST,
        port=settings.PORT,
        mock_mode=settings.MOCK_MODE,
        debug=settings.DEBUG,
    )

    if settings.MOCK_MODE:
        logger.info("server.mock_mode", msg="Running in MOCK_MODE — no live API calls will be made")

    yield

    # ── SHUTDOWN ──
    # ── End any active calls gracefully ──
    for call_sid, call_info in active_calls.items():
        agent = call_info.get("agent")
        if agent:
            try:
                await agent.on_call_end()
            except Exception as exc:
                logger.error("server.shutdown.call_cleanup_error", call_sid=call_sid, error=str(exc))

    active_calls.clear()
    logger.info("server.shutdown", msg="Graceful shutdown complete")


# ── Create FastAPI app ──
app = FastAPI(
    title="Indian Voice Agent API",
    description="AI-powered phone receptionist for Indian SMEs — handles calls in Hindi, books appointments, sends WhatsApp confirmations",
    version="0.2.0",
    lifespan=lifespan,
)

# ── Wire up middleware ──
setup_middleware(app)


# ═══════════════════════════════════════════════════
# HEALTH CHECK — Railway uses this to verify the server is alive
# ═══════════════════════════════════════════════════

@app.get("/health")
async def health_check() -> dict[str, str]:
    """Return server status — used by Railway for health monitoring."""
    return {
        "status": "healthy",
        "service": "indian-voice-agent",
        "mock_mode": str(settings.MOCK_MODE),
        "active_calls": str(len(active_calls)),
    }


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint — confirms the API is running."""
    return {
        "message": "Indian Voice Agent API is running",
        "docs": "/docs",
    }


# ═══════════════════════════════════════════════════
# EXOTEL WEBHOOK — Receives call notifications
# ═══════════════════════════════════════════════════

@app.post("/webhook/exotel")
async def exotel_webhook(request: Request) -> JSONResponse:
    """
    Handle incoming call notifications from Exotel.

    When someone calls a business phone number:
    1. Exotel sends a POST to this endpoint
    2. We look up which business owns that number
    3. We return a WebSocket URL for audio streaming

    In MOCK_MODE, accepts any JSON payload with CallSid, From, To fields.
    """
    try:
        # ── Parse the webhook payload ──
        body = await request.body()
        signature = request.headers.get("X-Exotel-Signature", "")

        # ── Verify webhook signature (skipped in mock mode) ──
        if not verify_exotel_signature(body, signature):
            logger.warning("webhook.invalid_signature")
            return JSONResponse(
                status_code=403,
                content={"error": "Invalid webhook signature"},
            )

        # ── Extract call data ──
        try:
            data = await request.json()
        except Exception:
            # ── Exotel sometimes sends form data ──
            form = await request.form()
            data = dict(form)

        call_sid = data.get("CallSid", str(uuid.uuid4()))
        caller_phone = data.get("From", "+910000000000")
        called_number = data.get("To", "+911234567890")
        call_status = data.get("Status", "ringing")

        logger.info(
            "webhook.received",
            call_sid=call_sid,
            from_phone=caller_phone,
            to_number=called_number,
            status=call_status,
        )

        # ── Look up the business by the called number ──
        from database.client import db

        business = await db.get_business_by_phone(called_number)

        if not business:
            logger.warning("webhook.business_not_found", phone=called_number)
            return JSONResponse(
                status_code=404,
                content={"error": "No business registered for this number"},
            )

        # ── Build WebSocket URL for audio streaming ──
        ws_host = request.headers.get("host", f"{settings.HOST}:{settings.PORT}")
        ws_protocol = "wss" if request.url.scheme == "https" else "ws"
        ws_url = f"{ws_protocol}://{ws_host}/ws/call/{call_sid}"

        logger.info(
            "webhook.call_routed",
            call_sid=call_sid,
            business=business.get("name"),
            ws_url=ws_url,
        )

        return JSONResponse(
            status_code=200,
            content={
                "status": "accepted",
                "call_sid": call_sid,
                "business_name": business.get("name"),
                "business_type": business.get("type"),
                "websocket_url": ws_url,
            },
        )

    except Exception as exc:
        logger.error("webhook.error", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error processing webhook"},
        )


# ═══════════════════════════════════════════════════
# WEBSOCKET — Real-time audio streaming with Pipecat
# ═══════════════════════════════════════════════════

@app.websocket("/ws/call/{call_sid}")
async def websocket_call(websocket: WebSocket, call_sid: str) -> None:
    """
    Handle a live voice call via WebSocket.

    Audio flows bidirectionally:
    - Receive: raw audio frames from Exotel/caller
    - Send: AI-generated audio responses back to caller

    The pipeline runs until the caller disconnects or
    MAX_CALL_DURATION_SEC is reached.
    """
    await websocket.accept()

    logger.info("ws.connected", call_sid=call_sid)

    # ── Extract call metadata from query params ──
    caller_phone = websocket.query_params.get("caller", "+910000000000")
    called_number = websocket.query_params.get("called", "+911234567890")
    language = websocket.query_params.get("language", settings.DEFAULT_LANGUAGE)

    # ── Look up business and create the right agent ──
    from agents.base_agent import create_agent
    from database.client import db

    business = await db.get_business_by_phone(called_number)
    if not business:
        logger.error("ws.no_business", called_number=called_number)
        await websocket.close(code=4004, reason="Business not found")
        return

    agent = create_agent(
        business_config=business,
        call_sid=call_sid,
        caller_phone=caller_phone,
        language=language,
    )
    agent.is_active = True

    # ── Track active call for dashboard ──
    active_calls[call_sid] = {
        "agent": agent,
        "business": business.get("name"),
        "caller": caller_phone,
        "started_at": time.time(),
    }

    try:
        # ── Send initial greeting ──
        greeting_audio = await agent.generate_greeting()
        if greeting_audio:
            await websocket.send_bytes(greeting_audio)

        # ── Main audio processing loop ──
        while agent.is_active:
            try:
                # ── Receive audio from caller (with timeout for call duration limit) ──
                raw_data = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=float(settings.MAX_CALL_DURATION_SEC),
                )

                if raw_data.get("type") == "websocket.disconnect":
                    logger.info("ws.caller_disconnected", call_sid=call_sid)
                    break

                # ── Handle binary audio data ──
                audio_bytes = raw_data.get("bytes")
                if audio_bytes:
                    response_audio = await agent.process_audio(audio_bytes)
                    if response_audio:
                        await websocket.send_bytes(response_audio)

                # ── Handle text commands (for testing/control) ──
                text_data = raw_data.get("text")
                if text_data:
                    command = json.loads(text_data)

                    if command.get("action") == "end_call":
                        logger.info("ws.end_call_command", call_sid=call_sid)
                        break

                    if command.get("action") == "text_input":
                        # ── For testing: send text through the pipeline ──
                        response_text = await agent.process_text(command.get("text", ""))
                        await websocket.send_text(json.dumps({
                            "type": "ai_response",
                            "text": response_text,
                        }))

            except asyncio.TimeoutError:
                logger.info("ws.call_timeout", call_sid=call_sid, max_sec=settings.MAX_CALL_DURATION_SEC)
                # ── Send a polite goodbye when max duration is reached ──
                goodbye = await agent.tts.synthesize(
                    "Call ki samay seema ho gayi hai. Dhanyavaad, phir se call karein.",
                    language,
                )
                if goodbye:
                    await websocket.send_bytes(goodbye)
                break

    except WebSocketDisconnect:
        logger.info("ws.disconnected", call_sid=call_sid)
    except Exception as exc:
        logger.error("ws.error", call_sid=call_sid, error=str(exc))
    finally:
        # ── Save call log and clean up ──
        call_log = await agent.on_call_end()
        active_calls.pop(call_sid, None)

        logger.info(
            "ws.call_complete",
            call_sid=call_sid,
            outcome=call_log.get("outcome") if call_log else "unknown",
        )

        try:
            await websocket.close()
        except Exception:
            pass  # ── Already closed ──


# ═══════════════════════════════════════════════════
# SIMULATE CALL — Test endpoint for MOCK_MODE
# ═══════════════════════════════════════════════════

@app.post("/test/simulate-call")
async def simulate_call(request: Request) -> JSONResponse:
    """
    Test the AI pipeline without a real phone call.

    Send a text message → get an AI response back.
    Useful for testing AI behavior, prompt tuning,
    and verifying the pipeline works end-to-end.

    Request body:
        {
            "message": "Mujhe kal 10 baje appointment chahiye",
            "business_phone": "+911234567890",
            "language": "hi-IN"
        }
    """
    try:
        data = await request.json()
        message = data.get("message", "")
        business_phone = data.get("business_phone", "+911234567890")
        language = data.get("language", settings.DEFAULT_LANGUAGE)

        if not message:
            return JSONResponse(
                status_code=400,
                content={"error": "Message is required"},
            )

        # ── Look up business ──
        from agents.base_agent import create_agent
        from database.client import db

        business = await db.get_business_by_phone(business_phone)
        if not business:
            return JSONResponse(
                status_code=404,
                content={"error": f"No business found for phone {business_phone}"},
            )

        # ── Create agent and process ──
        call_sid = f"sim-{uuid.uuid4().hex[:8]}"
        agent = create_agent(
            business_config=business,
            call_sid=call_sid,
            caller_phone="+919999999999",
            language=language,
        )

        response_text = await agent.process_text(message)

        # ── Get conversation state ──
        history = agent.llm.get_conversation_history()

        # ── Clean up ──
        await agent.stt.close()
        await agent.tts.close()

        return JSONResponse(
            status_code=200,
            content={
                "call_sid": call_sid,
                "business": business.get("name"),
                "user_message": message,
                "ai_response": response_text,
                "language": language,
                "conversation_turns": len(history),
            },
        )

    except Exception as exc:
        logger.error("simulate.error", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"error": f"Simulation failed: {str(exc)}"},
        )


# ═══════════════════════════════════════════════════
# ACTIVE CALLS — Dashboard API for live call status
# ═══════════════════════════════════════════════════

@app.get("/api/active-calls")
async def get_active_calls() -> JSONResponse:
    """
    Return currently active calls — used by dashboard for "live" view.

    Shows which calls are in progress right now, useful for
    the real-time dashboard feature.
    """
    calls = []
    for call_sid, info in active_calls.items():
        calls.append({
            "call_sid": call_sid,
            "business": info.get("business"),
            "caller": info.get("caller"),
            "duration_sec": int(time.time() - info.get("started_at", time.time())),
        })

    return JSONResponse(
        status_code=200,
        content={"active_calls": calls, "total": len(calls)},
    )


# ═══════════════════════════════════════════════════
# ROUTE REGISTRATION — Dashboard API routers
# ═══════════════════════════════════════════════════

app.include_router(calls_router)
app.include_router(appointments_router)
app.include_router(businesses_router)

logger.info(
    "routes.registered",
    routers=["calls", "appointments", "businesses"],
)


# ═══════════════════════════════════════════════════
# MCP TOOL TEST ENDPOINTS — Verify MCP servers directly
# ═══════════════════════════════════════════════════

@app.get("/test/mcp-tools")
async def list_mcp_tools() -> JSONResponse:
    """
    List all MCP tools available across all three servers.

    Returns tool names, descriptions, and which server handles each.
    Useful for debugging and verifying MCP server registration.
    """
    tools = await tool_registry.list_all()
    return JSONResponse(
        status_code=200,
        content={
            "total_tools": tool_registry.tool_count,
            "tools": tools,
        },
    )


@app.post("/test/mcp-tool")
async def test_mcp_tool(request: Request) -> JSONResponse:
    """
    Execute a single MCP tool directly for testing.

    Bypasses the voice pipeline — call any tool by name with arguments.
    Useful for verifying appointment booking, WhatsApp sending, etc.

    Request body:
        {
            "tool_name": "check_available_slots",
            "tool_input": {
                "business_id": "mock-business-001",
                "date": "2025-03-20"
            }
        }
    """
    try:
        data = await request.json()
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {})

        if not tool_name:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "tool_name is required",
                    "available_tools": tool_registry.tool_names,
                },
            )

        server = tool_registry.get_server_for_tool(tool_name)
        if not server:
            return JSONResponse(
                status_code=404,
                content={
                    "error": f"Unknown tool: {tool_name}",
                    "available_tools": tool_registry.tool_names,
                },
            )

        logger.info("test.mcp_tool", tool=tool_name, server=server)

        result = await tool_registry.execute(tool_name, tool_input)

        return JSONResponse(
            status_code=200,
            content={
                "tool_name": tool_name,
                "server": server,
                "result": result,
            },
        )

    except Exception as exc:
        logger.error("test.mcp_tool_error", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"error": f"Tool execution failed: {str(exc)}"},
        )


# ═══════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
