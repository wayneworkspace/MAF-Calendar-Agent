"""
Discord entrypoint: Discord message → Calendar AI Agent → reply.

Run:  python main.py
Uses Discord's gateway (WebSocket), so it works from any laptop/VPS without a public URL.

The bot replies:
  • to every message in a DM with it
  • in servers, only when @mentioned (or in channels listed in DISCORD_CHANNEL_IDS)
Commands:  !reset  → forget this conversation   |   !help
"""
from __future__ import annotations

import logging
import os
import re

from dotenv import load_dotenv

load_dotenv()  # must run before importing agent/calendar_tools (they read env)

import discord  # noqa: E402

from agent import SessionStore, build_agent  # noqa: E402
from calendar_tools import TZ_NAME, now_local  # noqa: E402

# ---- Logging: console + rotating file (logs/bot.log, 5 x 2 MB) ----
from logging.handlers import RotatingFileHandler  # noqa: E402

os.makedirs("logs", exist_ok=True)
_fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
_file = RotatingFileHandler("logs/bot.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
_file.setFormatter(_fmt)
_console = logging.StreamHandler()
_console.setFormatter(_fmt)
logging.basicConfig(level=logging.INFO, handlers=[_console, _file])
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("discord").setLevel(logging.WARNING)
log = logging.getLogger("calendar-bot")

MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "2"))

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("DISCORD_BOT_TOKEN is not set (see .env.example)")

ALLOWED_IDS = {
    int(x) for x in os.environ.get("ALLOWED_DISCORD_USER_IDS", "").split(",") if x.strip()
}
# Optional: channels where the bot answers every message without being mentioned
AUTO_CHANNEL_IDS = {
    int(x) for x in os.environ.get("DISCORD_CHANNEL_IDS", "").split(",") if x.strip()
}

agent = build_agent()
sessions = SessionStore(agent)

intents = discord.Intents.default()
intents.message_content = True  # must also be enabled in the Developer Portal
intents.dm_messages = True
client = discord.Client(intents=intents)

HELP_TEXT = (
    "👋 Hi! I'm your Calendar Assistant.\n\n"
    "Try:\n"
    "• What's on my calendar tomorrow?\n"
    "• Am I free Friday 3–4pm?\n"
    "• Book a dentist appointment next Tuesday at 10am\n"
    "• Move my 2pm meeting to 4pm\n"
    "• Cancel the gym session on Saturday\n\n"
    "`!reset` — forget this conversation"
)


def _authorized(user: discord.abc.User) -> bool:
    if not ALLOWED_IDS:  # empty whitelist = allow everyone (not recommended)
        return True
    return user.id in ALLOWED_IDS


def _should_answer(message: discord.Message) -> bool:
    if isinstance(message.channel, discord.DMChannel):
        return True
    if message.channel.id in AUTO_CHANNEL_IDS:
        return True
    return client.user in message.mentions


def _strip_mention(text: str) -> str:
    return re.sub(rf"<@!?{client.user.id}>", "", text).strip()


async def _send_long(channel: discord.abc.Messageable, text: str) -> None:
    # Discord caps messages at 2000 chars
    for i in range(0, len(text), 1990):
        await channel.send(text[i : i + 1990])


def _retry_delay(exc: Exception, fallback: float) -> float:
    """Honour Google's 'Please retry in 52s' hint when present."""
    m = re.search(r"retry in (\d+(?:\.\d+)?)s", str(exc))
    return min(float(m.group(1)) + 1, 65.0) if m else fallback


def _stamp(text: str) -> str:
    n = now_local()
    return f"[Now: {n.strftime('%Y-%m-%d %H:%M')} {n.strftime('%A')} {TZ_NAME}] {text}"


async def _run_agent_with_retry(chat_id: int, text: str) -> str:
    """Call the agent; retry rate limits / network errors, waiting as long as the API asks."""
    import asyncio

    delay = 3.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            session = sessions.get(chat_id)
            response = await agent.run(_stamp(text), session=session)
            return (response.text or "").strip() or "(no response)"
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "credit balance" in msg or "billing" in msg:
                log.error("API billing problem: %s", exc)
                return "⛔ API credits exhausted or billing issue. Top up at console.anthropic.com → Billing."
            transient = any(k in msg for k in ("429", "rate", "503", "502", "timeout", "overloaded", "connection"))
            if transient and attempt < MAX_RETRIES:
                wait = _retry_delay(exc, delay)
                log.warning("transient error (attempt %s/%s) — retrying in %.0fs", attempt, MAX_RETRIES, wait)
                await asyncio.sleep(wait)
                delay *= 2
                continue
            log.exception("agent error")
            if "429" in msg or "rate" in msg:
                return "⏳ Model rate limit hit. Wait a minute and try again."
            return f"⚠️ Something went wrong: {exc}"
    return "⚠️ Gave up after retries."


async def _heartbeat() -> None:
    """Touch logs/heartbeat every 60s while connected (used by the Docker HEALTHCHECK)."""
    import asyncio

    while True:
        if not client.is_closed() and client.is_ready():
            with open("logs/heartbeat", "w") as f:
                f.write(str(int(__import__("time").time())))
        await asyncio.sleep(60)


@client.event
async def on_ready() -> None:
    log.info("Logged in as %s (id=%s). Calendar bot ready.", client.user, client.user.id)
    if not getattr(client, "_heartbeat_started", False):
        client.loop.create_task(_heartbeat())
        client._heartbeat_started = True


@client.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot or not _should_answer(message):
        return

    if not _authorized(message.author):
        await message.channel.send(
            f"⛔ Not authorized. Your Discord ID is `{message.author.id}`."
        )
        return

    text = _strip_mention(message.content)
    chat_id = message.channel.id  # one memory per DM / channel

    if text.lower() in {"!start", "!help"} or not text:
        await message.channel.send(HELP_TEXT)
        return
    if text.lower() == "!reset":
        sessions.reset(chat_id)
        await message.channel.send("🧹 Conversation memory cleared.")
        return

    log.info("chat=%s user=%s: %s", chat_id, message.author.id, text)

    async with message.channel.typing():
        reply = await _run_agent_with_retry(chat_id, text)

    await _send_long(message.channel, reply)


def main() -> None:
    log.info("Starting Discord bot… Press Ctrl+C to stop.")
    client.run(BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
