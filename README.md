# Calendar Agent

Personal Discord bot that manages my Google Calendar in natural language.
Built on **Microsoft Agent Framework** (Python) with **Claude (Haiku 4.5)** as the model, running in **Docker Desktop**.

> Setup from zero → `docs/TUTORIAL.md`. Things that broke and how they were fixed → `docs/ERROR_LOG.md`.

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
├── .env                  secrets + settings (only file you edit day-to-day; never commit)
├── docker-compose.yml    docker compose up -d
├── app/                  source code
│   ├── main.py           Discord client, whitelist, !help/!reset, retry on 429, rotating logs, heartbeat
│   ├── agent.py          Agent: AnthropicClient, instructions, sliding-window memory, session per chat
│   ├── calendar_tools.py 5 calendar tools + time tool, each wrapped to log/return errors
│   ├── auth.py           one-time Google OAuth → data/token.json (Docker-aware)
│   └── requirements.txt
├── docker/Dockerfile     non-root image, healthcheck
├── scripts/              non-Docker alternatives: run.bat / run.sh, install-windows.ps1 (Task Scheduler),
│                         install-linux.sh + calendar-bot.service (systemd)
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
docker compose run --rm -p 8765:8765 calendar-bot python auth.py   # re-login to Google
```

## Configuration (`.env`)

| Key | Notes |
|---|---|
| `DISCORD_BOT_TOKEN` | Developer Portal → Bot → Reset Token |
| `ALLOWED_DISCORD_USER_IDS` | comma-separated; empty = everyone (don't) |
| `DISCORD_CHANNEL_IDS` | optional; bot replies there without @mention |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys (prepaid credits; no free tier) |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` (cheap, fast, enough for tool routing). `claude-sonnet-5` for stronger reasoning |
| `GOOGLE_CALENDAR_ID` | `primary` or a specific calendar ID |
| `TIMEZONE` | IANA name, `Asia/Ho_Chi_Minh` |
| `GOOGLE_CREDENTIALS_FILE` / `GOOGLE_TOKEN_FILE` | keep `data/credentials.json` / `data/token.json` for Docker |
| `MEMORY_WINDOW` | turns kept per chat (20) |
| `MAX_RETRIES` | attempts on 429/5xx (2) |

## How to change things

- **Bot personality / language / rules** → `INSTRUCTIONS` in `app/agent.py`
- **Add a tool** → write a typed function in `app/calendar_tools.py`, add it to `ALL_TOOLS`; docstring = tool description
- **Confirmation policy** → rule 3 in `INSTRUCTIONS` (currently: confirm before create/update/delete)
- **Switch model provider** → replace `AnthropicClient(...)` in `app/agent.py` with another Agent Framework client (OpenAI, Azure, Foundry, Gemini via OpenAI-compatible endpoint — see ERROR_LOG A7 for the Gemini thought-signature workaround you'd need back).
- **Persistent memory across restarts** → serialise `AgentSession` per chat to SQLite in `SessionStore` (not done; in-RAM by design)
- **Another chat app** → only `app/main.py` changes; `agent.py`/`calendar_tools.py` stay the same
- **Run 24/7 without my PC** → copy folder incl. `.env` + `data/` to a VPS, same compose commands (see `scripts/` for systemd/Task Scheduler alternatives)

## Resource usage

RAM ~100–250 MB · image ~470 MB · CPU negligible · Claude Haiku ≈ $0.007 per question → ~$4/month at 20 questions/day (prepaid credits).

## Known gotchas (details in ERROR_LOG.md)

- Claude API has no free tier → top up credits and set a monthly spend limit in the console
- Two bot instances with one Discord token = duplicate replies (and double spend)
- OAuth app in Testing mode → token expires every 7 days → publish the app
- Project folder must be outside OneDrive
