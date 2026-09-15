# TUTORIAL — Calendar Agent setup from zero (Windows + Docker Desktop)

Goal: Discord bot that reads/creates/updates/deletes Google Calendar events via Claude.
Time: ~30 min. Cost: ~$4/month on Claude Haiku (prepaid credits); Discord and Calendar API free.

---

## 0. Prerequisites

- Windows 10/11 with virtualization enabled (Docker needs WSL 2)
- A Google account
- Discord installed

Install **Docker Desktop**: https://www.docker.com/products/docker-desktop/
Start it, wait for the whale icon → "running". Verify: `docker --version`.
Settings → General → tick **Start Docker Desktop when you sign in**.

## 1. Project folder

Unzip the project to a folder **outside OneDrive**, e.g. `C:\Calendar_Agent`.
The folder must contain `docker-compose.yml` directly (not nested one level down).

```powershell
cd C:\Calendar_Agent
dir                      # confirm docker-compose.yml, app\, data\ are here
copy .env.example .env
notepad .env
```

Fill `.env` as you collect the values below. Keep these two lines exactly:
```
GOOGLE_CREDENTIALS_FILE=data/credentials.json
GOOGLE_TOKEN_FILE=data/token.json
```

## 2. Discord

### 2.1 Create the bot
1. https://discord.com/developers/applications → **New Application** → name `Calendar`.
2. Left menu **Bot** → **Reset Token** → copy → `.env` → `DISCORD_BOT_TOKEN=`.
3. Same page, scroll to **Privileged Gateway Intents** → turn ON **Message Content Intent** → **Save Changes**.

### 2.2 Invite it to a server
1. Left menu **OAuth2** → **URL Generator**.
2. Scopes: tick **`bot`** only.
3. Bot Permissions: **View Channels**, **Send Messages**, **Read Message History**.
4. Copy the generated URL → open in browser → choose a server (create a private one if needed) → Authorize.

### 2.3 Your user ID (whitelist)
1. Discord → User Settings → Advanced → **Developer Mode** ON.
2. Right-click your name → **Copy User ID** → `.env` → `ALLOWED_DISCORD_USER_IDS=`.
3. Optional: right-click a channel → Copy Channel ID → `DISCORD_CHANNEL_IDS=` (bot answers there without @mention).

## 3. Claude API key

1. https://console.anthropic.com → sign up (this is the developer console; a claude.ai subscription does NOT include API access).
2. **Billing** → add payment method → buy prepaid credits ($5 is plenty for months) → set a monthly spend limit (e.g. $10).
3. **API Keys** → **Create Key** → name `calendar-agent` → copy (shown once, starts with `sk-ant-`).
4. `.env` → `ANTHROPIC_API_KEY=` and `ANTHROPIC_MODEL=claude-haiku-4-5`.

## 4. Google Calendar OAuth

All in https://console.cloud.google.com — create a project (or use any existing one) and **select it** in the project picker, top-left.

### 4.1 Enable the API
Search bar → **Google Calendar API** → **Enable**.
(Direct link: https://console.cloud.google.com/apis/library/calendar-json.googleapis.com)

### 4.2 Consent screen
1. Left menu **APIs & Services → OAuth consent screen** (new UI: *Google Auth Platform*) → **Get started**.
2. App name `Calendar Agent`, support email = your Gmail → Audience **External** → contact email → Create.
3. **Audience** → **Test users** → **+ Add users** → your Gmail → Save.
   ⚠️ Without this you get `403 access_denied` at login.

### 4.3 OAuth client
1. **Credentials** → **+ Create credentials** → **OAuth client ID**.
2. Type **Desktop app** → Create → **Download JSON**.
3. Save it as `C:\Calendar_Agent\data\credentials.json`.

### 4.4 One-time login (inside Docker)
```powershell
cd C:\Calendar_Agent
docker compose build
docker compose run --rm -p 8765:8765 calendar-bot python auth.py
```
Copy the printed `https://accounts.google.com/...` URL into your browser →
sign in with the test-user Gmail → "unverified app" → **Advanced → Go to Calendar Agent** →
allow → browser shows "flow completed" → terminal shows `✅ Saved data/token.json`.

## 5. Run

```powershell
docker compose up -d --build
docker compose logs -f        # expect: "Logged in as Calendar#XXXX ... Calendar bot ready."
docker ps                     # exactly ONE calendar-bot container
```

## 6. Test in Discord

DM the bot (member list → Calendar → Message) or @mention it in the server.

1. `!help` → welcome text
2. `What's on my calendar tomorrow?` → events or "no events"
3. `Book a test meeting tomorrow at 3pm` → summary + **Confirm? (yes/no)** → `yes` → check Google Calendar
4. `Delete the test meeting tomorrow` → `yes`

Each question ≈ 2 API requests ≈ $0.007 on Haiku. Check spend at console.anthropic.com → Usage.

## 7. Daily operation

| Task | Command |
|---|---|
| Start | `docker compose up -d` |
| Stop | `docker compose down` |
| Logs | `docker compose logs -f` or `logs\bot.log` |
| After editing `.env` or code | `docker compose up -d --build` |
| Clear bot memory | send `!reset` |
| Re-login to Google | delete `data\token.json`, redo step 4.4 |

Bot runs only while Docker Desktop runs. For 24/7 without your PC: copy the folder
(incl. `.env` and `data\`) to a VPS and run the same `docker compose up -d --build`.

## 8. Security checklist

- Never screenshot/commit `.env` or `data\`. If a token leaks: Discord → Bot → Reset Token; AI Studio → delete key → new key.
- `ALLOWED_DISCORD_USER_IDS` must be set, or anyone in the server can drive your calendar.
- OAuth app in **Testing** mode: Google expires the refresh token every **7 days** → re-login needed.
  To stop that: OAuth consent screen → **Publish app** (no verification needed for personal use with a
  sensitive-scope warning) — then the token lasts indefinitely.
