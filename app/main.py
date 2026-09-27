"""Discord entrypoint for Calendar AI Agent.

Handles Discord Gateway interactions, whitelist authentication, message processing,
and resilient agent execution with exponential backoff retries.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from logging.handlers import RotatingFileHandler
from typing import Set

from dotenv import load_dotenv

load_dotenv()

import discord  # noqa: E402

from app.agent import SessionStore, build_agent  # noqa: E402
from app.calendar_tools import TZ_NAME, now_local  # noqa: E402

# ---- Logging Setup ----
os.makedirs("logs", exist_ok=True)
_log_format = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

_file_handler = RotatingFileHandler("logs/bot.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
_file_handler.setFormatter(_log_format)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_log_format)

logging.basicConfig(level=logging.INFO, handlers=[_console_handler, _file_handler])
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("discord").setLevel(logging.WARNING)
log = logging.getLogger("calendar-bot")

MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "2"))
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

ALLOWED_IDS: Set[int] = {
    int(x) for x in os.environ.get("ALLOWED_DISCORD_USER_IDS", "").split(",") if x.strip()
}
AUTO_CHANNEL_IDS: Set[int] = {
    int(x) for x in os.environ.get("DISCORD_CHANNEL_IDS", "").split(",") if x.strip()
}

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
    """Check if a Discord user is authorized to interact with the bot."""
    if not ALLOWED_IDS:
        return True
    return user.id in ALLOWED_IDS


def _should_answer(client: discord.Client, message: discord.Message) -> bool:
    """Determine whether the message requires a response from the bot."""
    if isinstance(message.channel, discord.DMChannel):
        return True
    if message.channel.id in AUTO_CHANNEL_IDS:
        return True
    return client.user in message.mentions if client.user else False


def _strip_mention(bot_user_id: int, text: str) -> str:
    """Strip bot mention prefix from message text."""
    return re.sub(rf"<@!?{bot_user_id}>", "", text).strip()


async def _send_long(channel: discord.abc.Messageable, text: str) -> None:
    """Send message to channel, chunking into max 1990 chars to respect Discord limits."""
    for i in range(0, len(text), 1990):
        await channel.send(text[i : i + 1990])


def _retry_delay(exc: Exception, fallback: float) -> float:
    """Extract recommended delay from rate limit error message or return fallback."""
    m = re.search(r"retry in (\d+(?:\.\d+)?)s", str(exc))
    return min(float(m.group(1)) + 1, 65.0) if m else fallback


def _stamp(text: str) -> str:
    """Prefix message with current ISO datetime, weekday, and timezone."""
    n = now_local()
    return f"[Now: {n.strftime('%Y-%m-%d %H:%M')} {n.strftime('%A')} {TZ_NAME}] {text}"


class CalendarBotClient(discord.Client):
    """Custom Discord Client with integrated agent handling and heartbeat monitoring."""

    def __init__(self, intents: discord.Intents) -> None:
        super().__init__(intents=intents)
        self.agent = build_agent()
        self.sessions = SessionStore(self.agent)
        self._heartbeat_started = False

    async def run_agent_with_retry(self, chat_id: int, text: str) -> str:
        """Call agent with exponential backoff on transient network/rate-limit errors."""
        delay = 3.0
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                session = self.sessions.get(chat_id)
                response = await self.agent.run(_stamp(text), session=session)
                return (response.text or "").strip() or "(no response)"
            except Exception as exc:  # noqa: BLE001
                msg = str(exc).lower()
                if "credit balance" in msg or "billing" in msg:
                    log.error("API billing issue encountered: %s", exc)
                    return "⛔ API credits exhausted or billing issue. Please top up your API console."
                transient = any(
                    k in msg for k in ("429", "rate", "503", "502", "timeout", "overloaded", "connection")
                )
                if transient and attempt < MAX_RETRIES:
                    wait = _retry_delay(exc, delay)
                    log.warning("Transient error (attempt %d/%d) — retrying in %.0fs", attempt, MAX_RETRIES, wait)
                    await asyncio.sleep(wait)
                    delay *= 2
                    continue
                log.exception("Agent execution failure")
                if "429" in msg or "rate" in msg:
                    return "⏳ Model rate limit hit. Please wait a moment and try again."
                return f"⚠️ Something went wrong: {exc}"
        return "⚠️ Request failed after retries."

    async def _heartbeat_loop(self) -> None:
        """Touch logs/heartbeat file periodically for container health checking."""
        while not self.is_closed():
            if self.is_ready():
                try:
                    with open("logs/heartbeat", "w", encoding="utf-8") as f:
                        f.write(str(int(time.time())))
                except Exception as exc:  # noqa: BLE001
                    log.warning("Failed to write heartbeat: %s", exc)
            await asyncio.sleep(60)

    async def on_ready(self) -> None:
        """Triggered when Discord client connects and completes authentication."""
        if self.user:
            log.info("Logged in as %s (ID: %s). Calendar Bot ready.", self.user, self.user.id)
        if not self._heartbeat_started:
            self.loop.create_task(self._heartbeat_loop())
            self._heartbeat_started = True

    async def on_message(self, message: discord.Message) -> None:
        """Main message event handler."""
        if message.author.bot or not _should_answer(self, message):
            return

        if not _authorized(message.author):
            await message.channel.send(f"⛔ Not authorized. Your Discord ID is `{message.author.id}`.")
            return

        bot_id = self.user.id if self.user else 0
        text = _strip_mention(bot_id, message.content)
        chat_id = message.channel.id

        if text.lower() in {"!start", "!help"} or not text:
            await message.channel.send(HELP_TEXT)
            return

        if text.lower() == "!reset":
            self.sessions.reset(chat_id)
            await message.channel.send("🧹 Conversation memory cleared.")
            return

        log.info("chat=%s user=%s: %s", chat_id, message.author.id, text)

        async with message.channel.typing():
            reply = await self.run_agent_with_retry(chat_id, text)

        await _send_long(message.channel, reply)


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("DISCORD_BOT_TOKEN is not set in environment (see .env.example)")

    intents = discord.Intents.default()
    intents.message_content = True
    intents.dm_messages = True

    client = CalendarBotClient(intents=intents)
    log.info("Starting Discord bot… Press Ctrl+C to stop.")
    client.run(BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
