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
The folder must contain `docker-compose.yml` directly.

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
4. Copy the generated URL → open in browser → choose a server → Authorize.

### 2.3 Your user ID (whitelist)
1. Discord → User Settings → Advanced → **Developer Mode** ON.
2. Right-click your name → **Copy User ID** → `.env` → `ALLOWED_DISCORD_USER_IDS=`.
3. Optional: right-click a channel → Copy Channel ID → `DISCORD_CHANNEL_IDS=` (bot answers there without @mention).

## 3. Claude API key

1. https://console.anthropic.com → sign up.
2. **Billing** → add payment method → buy prepaid credits ($5 is plenty for months) → set a monthly spend limit.
3. **API Keys** → **Create Key** → name `calendar-agent` → copy.
4. `.env` → `ANTHROPIC_API_KEY=` and `ANTHROPIC_MODEL=claude-haiku-4-5`.

## 4. Google Calendar OAuth

All in https://console.cloud.google.com — create a project and select it in top-left.

### 4.1 Enable the API
Search bar → **Google Calendar API** → **Enable**.

### 4.2 Consent screen
1. Left menu **APIs & Services → OAuth consent screen** → **Get started**.
2. App name `Calendar Agent`, support email = your Gmail → Audience **External** → contact email → Create.
3. **Audience** → **Test users** → **+ Add users** → your Gmail → Save.

### 4.3 OAuth client
1. **Credentials** → **+ Create credentials** → **OAuth client ID**.
2. Type **Desktop app** → Create → **Download JSON**.
3. Save it as `C:\Calendar_Agent\data\credentials.json`.

### 4.4 One-time login (inside Docker)
```powershell
cd C:\Calendar_Agent
docker compose build
docker compose run --rm -p 8765:8765 calendar-bot python app/auth.py
```
Copy the printed `https://accounts.google.com/...` URL into your browser → sign in → allow → terminal shows `✅ Saved data/token.json`.

## 5. Run

```powershell
docker compose up -d --build
docker compose logs -f        # expect: "Logged in as Calendar#XXXX ... Calendar bot ready."
docker ps                     # exactly ONE calendar-bot container
```

## 6. Test in Discord

DM the bot or @mention it in the server:
1. `!help` → welcome text
2. `What's on my calendar tomorrow?` → events or "no events"
3. `Book a test meeting tomorrow at 3pm` → summary + **Confirm? (yes/no)** → `yes`
4. `Delete the test meeting tomorrow` → `yes`

## 7. Daily operation

| Task | Command |
|---|---|
| Start | `docker compose up -d` |
| Stop | `docker compose down` |
| Logs | `docker compose logs -f` or `logs\bot.log` |
| After editing `.env` or code | `docker compose up -d --build` |
| Run tests | `python3 -m pytest` |
| Clear bot memory | send `!reset` |
| Re-login to Google | delete `data\token.json`, redo step 4.4 |
