# ERROR_LOG — Calendar Agent

Format: **Symptom** → Root cause → Fix. Part A = hit during setup. Part B = likely future issues.

---

## Part A — Setup and Operational Issues

### A1. Bot online in server but @mention gets no reply at all
- Cause: invite link only granted *Send Messages*; without **View Channels** the bot never receives channel messages.
- Fix: Server Settings → Roles → Calendar → enable View Channels, Send Messages, Read Message History. DMs work regardless.

### A2. Every message answered twice
- Cause: two bot processes with the same token — old container running in background.
- Fix: `docker ps -a` → `docker stop $(docker ps -aq)` → `docker rm $(docker ps -aq)` → `docker compose up -d`. Verify `docker ps` shows one container.

### A3. `❌ credentials.json not found`
- Cause: `.env` lacked `GOOGLE_CREDENTIALS_FILE=data/credentials.json` / `GOOGLE_TOKEN_FILE=data/token.json`.
- Fix: populate paths in `.env`; `docker compose build`; rerun auth flow.

### A4. `Error 403: access_denied — Calendar Agent has not completed the Google verification process`
- Cause: OAuth app in Testing mode; Gmail not on test user list.
- Fix: console.cloud.google.com/auth/audience → Test users → add Gmail.

### A5. Tools swallowed exceptions silently
- Cause: tools swallowed exceptions, model only saw generic failure.
- Fix: `_tool()` wrapper logs traceback and returns structured error JSON.

### A6. Google Calendar API disabled (`403 accessNotConfigured`)
- Cause: Calendar API not enabled in Cloud Console project.
- Fix: APIs & Services → Library → Google Calendar API → Enable.

---

## Part B — Common Edge Cases

### B1. `invalid_grant` / `Token has been expired or revoked` after 7 days
- Cause: OAuth app in Testing mode expires refresh tokens after 7 days.
- Fix: Re-authenticate via `auth.py` or set OAuth consent screen to **Publish app**.

### B2. `401 Unauthorized` / Discord token error
- Cause: Token changed in developer portal but `.env` not updated or container not restarted.
- Fix: Update `.env` and restart container via `docker compose up -d --build`.

### B3. `400 credit balance is too low` / Anthropic billing error
- Cause: Anthropic API account balance depleted.
- Fix: Top up credits at console.anthropic.com.
