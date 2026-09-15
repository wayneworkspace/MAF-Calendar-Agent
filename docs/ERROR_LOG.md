# ERROR_LOG — Calendar Agent

Format: **Symptom** → Root cause → Fix. Part A = hit during setup (2026-09-06). Part B = likely future issues.

---

## Part A — Errors hit during setup

### A1. `Unable to copy ... venvlauncher.exe to ... .venv\Scripts\python.exe`
Running `py -m venv .venv` while the prompt already showed `(.venv)`; project was in `OneDrive\Desktop`.
- Cause: venv already active (python.exe in use) + OneDrive sync locking files.
- Fix: `deactivate`; move project outside OneDrive; later replaced venv entirely with Docker.

### A2. `Move-Item : The process cannot access the file because it is being used by another process`
- Cause: `.venv` / OneDrive still holding file handles.
- Fix: `robocopy <src> <dst> /E /XD .venv logs __pycache__` (copy everything except the venv), rebuild in the new place.

### A3. `copy : Cannot find path '.env.example'`
- Cause: zip extracted one level too deep (`C:\Calendar_Agent\calendar-agent-v2\...`). Also Explorer hides dot-files.
- Fix: `cd` into the folder that contains `docker-compose.yml`; use `dir` in PowerShell to see dot-files.

### A4. Bot online in server but @mention gets no reply at all
- Cause: invite link only granted *Send Messages*; without **View Channels** the bot never receives channel messages.
- Fix: Server Settings → Roles → Calendar → enable View Channels, Send Messages, Read Message History. DMs work regardless (used to confirm the bot itself was fine).

### A5. [Gemini era] `404 This model models/gemini-2.5-flash is no longer available to new users`
- Cause: model retired for new accounts.
- Fix: `.env` → `GEMINI_MODEL=gemini-3.6-flash`; default in `app/agent.py` updated.

### A6. Every message answered twice
- Cause: two bot processes with the same token — old container from the previous folder name (`Calendar Agent` vs `Calendar_Agent` = two Compose projects) still running.
- Fix: `docker ps -a` → `docker stop $(docker ps -aq)` → `docker rm $(docker ps -aq)` → `docker compose up -d`. Verify `docker ps` shows one container.
- Tell-tale: replies with different wording = different code versions running.

### A7. [Gemini era] `400 Function call is missing a thought_signature in functionCall parts`
- Cause: Gemini 3.x signs tool calls (`extra_content.google.thought_signature`); the OpenAI-compatible client in Agent Framework drops that field on the next turn, Gemini rejects.
- Fix: `app/agent.py` → `message_preparer=_gemini_message_preparer`, which adds `extra_content: {"google": {"thought_signature": "skip_thought_signature_validator"}}` to every assistant `tool_calls` entry. Official sentinel from Google's docs. Verified working.

### A8. [Gemini era] `429 RESOURCE_EXHAUSTED ... free_tier_requests, limit: 5, model: gemini-3.6-flash`
- Cause: free tier = 5 requests/min per model. One question = 3 requests (think → time tool → calendar tool → answer), ×2 because of A6, plus retries 2 s apart.
- Fix: (1) kill duplicate instance; (2) inject `[Now: ...]` into each message instead of calling `get_current_datetime` → 2 requests per question; (3) retry honours Google's `retry in Ns` hint, `MAX_RETRIES=2`; (4) user-facing ⏳ message instead of stack trace.
- Still applies: send one message at a time. Upgrade path = enable billing or pick a model with higher free RPM.

### A9. `❌ credentials.json not found` (while file sat in `data\`)
Two causes, hit in sequence:
- (a) `.env` lacked `GOOGLE_CREDENTIALS_FILE=data/credentials.json` / `GOOGLE_TOKEN_FILE=data/token.json`.
- (b) `app/auth.py`, `app/calendar_tools.py`, `docker/Dockerfile`, `docker-compose.yml` were still from the first zip (only `agent.py`/`main.py` had been replaced) — message printed `credentials.json` instead of `data/credentials.json` = old code. `docker compose run` also reuses the old image unless `docker compose build` runs first.
- Fix: replace all project files except `.env` and `data\`; `docker compose build`; rerun auth.

### A10. `Error 403: access_denied — Calendar Agent has not completed the Google verification process`
- Cause: OAuth app in Testing mode; my Gmail not on the test-user list.
- Fix: console.cloud.google.com/auth/audience → Test users → add Gmail → rerun auth (old URL had expired).

### A11. Bot: "ran into a system error while fetching your events" (no detail)
- Cause: tools swallowed exceptions, model only saw a generic failure.
- Fix: `_tool()` wrapper in `app/calendar_tools.py` logs the traceback (`docker compose logs`) and returns `{"error": "..."}` to the model, which now reports the real reason.

### A12. "Google Calendar API ... disabled or not enabled for this project" (`403 accessNotConfigured`)
- Cause: Calendar API never enabled in the Cloud project (the AI Studio project only had Gemini).
- Fix: APIs & Services → Library → Google Calendar API → Enable. No restart needed.

### A13. Secrets exposed in a screenshot / chat
- Cause: posted `.env` with Discord token + Gemini key visible, then pasted the key again in chat.
- Fix: Discord Bot → Reset Token; AI Studio → delete key → new key; update `.env`; `docker compose up -d`.

### A14. [Gemini era] 429 persists for hours — `quotaId: GenerateRequestsPerDay…`, `quotaValue: 20`
- Cause: Gemini free tier = 20 requests/**day** per model for gemini-3.6-flash. Resets midnight Pacific (14:00 VN). Per project, so rotating the key doesn't help. Retries only burned the next day's quota.
- Fix chosen: **migrated to Claude Haiku 4.5** (`agent-framework-anthropic`). Alternatives were Gemini billing or a Flash-Lite model.
- Code: `_gemini_message_preparer` removed from `app/agent.py`; `AnthropicClient(model=, api_key=)`.


---

## Part B — Likely future errors

### B1. `invalid_grant` / `Token has been expired or revoked` after ~7 days
- Cause: OAuth app in **Testing** mode → refresh tokens expire after 7 days.
- Fix now: delete `data\token.json`, rerun `docker compose run --rm -p 8765:8765 calendar-bot python auth.py`.
- Fix permanently: OAuth consent screen → **Publish app** (stays "unverified", fine for personal use). Also triggered by changing the Google password or revoking access at myaccount.google.com/permissions.

### B2. `docker: error during connect` / `Cannot connect to the Docker daemon`
- Docker Desktop not running. Start it; enable *Start when you sign in*.

### B3. Bot offline after Windows reboot
- Docker Desktop didn't autostart, or the container was stopped manually (`down` clears the restart policy). `docker compose up -d`.

### B4. `PrivilegedIntentsRequired` on startup
- Message Content Intent got turned off (or token belongs to a different app). Developer Portal → Bot → enable → Save → restart.

### B5. `401 Unauthorized` / `Improper token has been passed` (Discord)
- Token was reset in the portal but `.env` not updated, or `.env` edited without `docker compose up -d`.

### B6. `Bind for 0.0.0.0:8765 failed: port is already allocated`
- Previous auth container still alive. `docker ps -a` → stop/remove it, or use another port: `-p 8766:8766` with `AUTH_PORT=8766` in `.env`.

### B7. `data/token.json` is a directory / `IsADirectoryError`
- Happens if an old compose file mounted `./token.json` before the file existed (Docker creates a folder). Delete the folder, use the current compose (mounts `./data`).

### B8. `403 insufficientPermissions` on create/update/delete
- Token was issued with a read-only scope (e.g. changed `SCOPES`). Delete `data\token.json`, re-auth with `https://www.googleapis.com/auth/calendar`.

### B9. `404 notFound` on `calendarId`
- `GOOGLE_CALENDAR_ID` wrong. Use `primary` or the ID from Google Calendar → Settings → Integrate calendar.

### B10. Wrong day/time in answers
- `TIMEZONE` wrong, or VPS clock wrong (`date` / `timedatectl`). Times are computed in the container from `TIMEZONE`, not the host TZ.

### B11. `429 rate_limit_error` from Anthropic
- Per-minute request/token limits depend on usage tier (rises with spend). Retry logic waits and retries once; if persistent, check console.anthropic.com → Limits.

### B19. `400 credit balance is too low` / `billing`
- Prepaid credits used up or monthly spend limit reached. Bot replies "⛔ API credits exhausted". Top up at console.anthropic.com → Billing.

### B20. `404 model not found` (Anthropic)
- Model name in `ANTHROPIC_MODEL` retired or misspelled. Check https://docs.claude.com/en/docs/about-claude/models.

### B21. `agent_framework.anthropic` import error after rebuild
- `agent-framework-anthropic` is a pre-release; pip needs the explicit beta version pinned in `app/requirements.txt` (or `--pre`). Don't loosen the pin to `>=1.0.0`.

### B12. Bot answers but ignores the confirmation rule
- Instructions were edited/removed, or model changed. Re-check rule 3 in `INSTRUCTIONS` (`app/agent.py`); test with a create request.

### B13. Memory lost mid-conversation
- Container restarted (crash, `--build`, reboot) — memory is in RAM by design. `docker compose logs` shows the restart. Persist `AgentSession` to SQLite if this matters.

### B14. Disk filling up
- `logs/` is rotated (5×2 MB) and Docker logs capped (3×5 MB), so unlikely. Old images: `docker image prune`.

### B15. VPS: container starts, `Logged in`, but never replies
- Outbound firewall blocking Discord gateway (443/wss) or Google APIs; `curl https://discord.com` and `curl https://generativelanguage.googleapis.com` from the server.

### B16. VPS: `token.json` refresh fails with `PermissionError`
- `data/` copied as root, container runs as user `bot` (uid 1000). `chown -R 1000:1000 data logs`.

### B17. Discord message > 2000 chars
- Already split in `_send_long`; if a single line has no spaces it may still look odd — cosmetic only.

### B18. Model returns `(no response)`
- Model produced only tool calls / empty text (often after a 429 mid-loop). Ask again; if persistent, check `logs/bot.log` for the tool error.
