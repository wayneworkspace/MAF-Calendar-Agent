# Calendar Agent

Personal Discord bot that manages Google Calendar in natural language.
Built on **Microsoft Agent Framework** (Python) with **Claude (Haiku 4.5)** as the model, running in **Docker Desktop**.

> Setup from zero → `docs/TUTORIAL.md`. Common issues and solutions → `docs/ERROR_LOG.md`.

## What it does

- "What's on my calendar tomorrow?" → lists events
- "Am I free Friday 3–4pm?" → checks free/busy
- "Book dentist next Tuesday 10am" → summarises, asks **Confirm? (yes/no)**, then creates
- "Move my 2pm to 4pm" / "Cancel the gym session Saturday" → finds the event, confirms, updates/deletes
- Remembers the conversation per DM/channel (in RAM, sliding window of 20 turns); `!reset` clears it
- Only whitelisted Discord user IDs can use it

## Architecture

```
Discord (DM or @mention)
   │  discord.py gateway (WebSocket, no public URL needed)
   ▼
main.py ── whitelist ── "[Now: <date time tz>] <message>" ──▶ Agent (agent.py)
                                                               │  Claude Haiku 4.5 via
                                                               │  agent-framework-anthropic
                                                               ▼
                                                        calendar_tools.py
                                                        ├ get_events
                                                        ├ check_availability
                                                        ├ create_event   (confirm first)
                                                        ├ update_event   (confirm first)
                                                        ├ delete_event   (confirm first)
                                                        └ get_current_datetime (fallback)
                                                               │ Google Calendar API v3
                                                               ▼
                                                        data/token.json (OAuth, auto-refresh)
```

Equivalent to the n8n workflow: Chat trigger → AI Agent (model + window memory + tools) → reply.

## Layout

```
Calendar_Agent/
├── README.md
├── .env                  secrets + settings (never commit)
├── docker-compose.yml    docker compose up -d
├── app/                  source code
│   ├── main.py           Discord client, whitelist, !help/!reset, retry logic, rotating logs, heartbeat
│   ├── agent.py          Agent: AnthropicClient, instructions, sliding-window memory, session per chat
│   ├── calendar_tools.py 5 calendar tools + time tool, exception wrapper logging
│   ├── auth.py           one-time Google OAuth → data/token.json (Docker-aware)
│   └── requirements.txt
├── docker/Dockerfile     non-root image, healthcheck
├── tests/                unit test suite for tools, agent, and Discord client helpers
├── docs/                 TUTORIAL.md (setup from zero), ERROR_LOG.md (symptom → cause → fix)
├── data/                 credentials.json + token.json (mounted into container; never commit)
└── logs/                 bot.log (rotating 5×2 MB), heartbeat
```

## Commands

```powershell
docker compose up -d --build     # start / apply changes
docker compose down              # stop
docker compose logs -f           # live logs
docker ps                        # must show exactly one calendar-bot
docker compose run --rm -p 8765:8765 calendar-bot python app/auth.py   # re-login to Google
python3 -m pytest                # run automated unit tests
```

## Configuration (`.env`)

| Key | Notes |
|---|---|
| `DISCORD_BOT_TOKEN` | Developer Portal → Bot → Reset Token |
| `ALLOWED_DISCORD_USER_IDS` | comma-separated; empty = everyone (don't) |
| `DISCORD_CHANNEL_IDS` | optional; bot replies there without @mention |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys (prepaid credits) |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` (cheap, fast, tool routing) |
| `GOOGLE_CALENDAR_ID` | `primary` or a specific calendar ID |
| `TIMEZONE` | IANA name, `Asia/Ho_Chi_Minh` |
| `GOOGLE_CREDENTIALS_FILE` / `GOOGLE_TOKEN_FILE` | `data/credentials.json` / `data/token.json` for Docker |
| `MEMORY_WINDOW` | turns kept per chat (20) |
| `MAX_RETRIES` | attempts on 429/5xx (2) |

## How to change things

- **Bot personality / language / rules** → `INSTRUCTIONS` in `app/agent.py`
- **Add a tool** → write a typed function in `app/calendar_tools.py`, add it to `ALL_TOOLS`; docstring = tool description
- **Confirmation policy** → rule 3 in `INSTRUCTIONS` (confirm before create/update/delete)
- **Switch model provider** → replace `AnthropicClient(...)` in `app/agent.py` with another Agent Framework client
- **Persistent memory across restarts** → serialise `AgentSession` per chat to SQLite in `SessionStore`
