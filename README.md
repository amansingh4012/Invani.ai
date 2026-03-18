# 🇮🇳 Indian Voice Agent — AI-Powered Phone Receptionist for SMEs

> Production-ready AI voice agent that answers phone calls in Hindi,
> books appointments, sends WhatsApp confirmations, and gives business
> owners a real-time dashboard.

## 🏗️ Architecture

```
Caller → Exotel (telephony) → FastAPI webhook → Pipecat voice pipeline
                                                       │
                                    ┌──────────────────┤
                                    ▼                  ▼
                              Silero VAD         Sarvam STT
                           (voice activity)    (Hindi → text)
                                    │                  │
                                    └──────┬───────────┘
                                           ▼
                                    Claude Sonnet AI
                                    (intent + reply)
                                           │
                              ┌────────────┼────────────┐
                              ▼            ▼            ▼
                        MCP: Appts   MCP: WhatsApp  MCP: Calendar
                              │            │            │
                              └────────────┼────────────┘
                                           ▼
                                      Sarvam TTS
                                    (text → Hindi audio)
                                           │
                                           ▼
                                    Audio back to caller
```

## 📁 Project Structure

```
indian-voice-agent/
├── backend/           # Python 3.12 + FastAPI + Pipecat
│   ├── main.py        # FastAPI server + Exotel webhook
│   ├── config/        # Settings, env config, feature flags
│   ├── agents/        # Pipecat voice pipeline agents
│   ├── mcp_servers/   # MCP tool servers (appts, whatsapp, calendar)
│   ├── prompts/       # System prompts per business type
│   ├── database/      # Supabase client + schema
│   └── api/           # REST API routes + middleware
│
└── frontend/          # React 18 + TypeScript + Tailwind
    └── src/           # Dashboard pages, components, hooks
```

## 🚀 Quick Start

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
cp .env.example .env         # Fill in your API keys
python main.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## 🔧 Tech Stack

| Layer       | Technology                        |
|-------------|-----------------------------------|
| Backend     | Python 3.12, FastAPI, Pipecat     |
| AI Brain    | Anthropic Claude Sonnet           |
| Speech      | Sarvam AI (Hindi STT + TTS)       |
| VAD         | Silero VAD                        |
| Tools       | MCP SDK (3 tool servers)          |
| Database    | Supabase (PostgreSQL)             |
| Telephony   | Exotel (Indian phone numbers)     |
| WhatsApp    | Meta Cloud API                    |
| Frontend    | React 18, TypeScript, Tailwind    |
| UI Kit      | shadcn/ui + Recharts              |
| Deploy      | Railway (backend) + Vercel (frontend) |

## 🌐 Supported Languages

- Hindi (hi-IN) — primary
- English (en-IN) — secondary

## 📄 License

Private — All rights reserved.
