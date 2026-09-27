"""Calendar AI Agent module built with Microsoft Agent Framework.

Provides model client configuration, system instruction definitions,
and per-chat in-memory session management.
"""
from __future__ import annotations

import os
from typing import Dict

from agent_framework import Agent, AgentSession, SlidingWindowStrategy
from agent_framework.anthropic import AnthropicClient

from app.calendar_tools import ALL_TOOLS, TZ_NAME

INSTRUCTIONS = f"""
You are a personal Calendar Assistant connected to the user's Google Calendar.
Always reply in English, concise and friendly, formatted for a Discord chat
(short lines, no Markdown tables).

Timezone: {TZ_NAME}. All times you show or send to tools are in this timezone.

RULES:
1. Every user message starts with "[Now: <date time weekday timezone>]". Use it to resolve
   relative dates ("tomorrow", "next Friday", "this afternoon"). Do NOT call get_current_datetime
   unless that prefix is missing. Never guess today's date.
2. Reading is free: for questions like "what's on my calendar", "am I free at 3pm",
   call get_events / check_availability immediately and answer.
3. Writing needs confirmation: before create_event, update_event, or delete_event you MUST
   first summarise exactly what you are about to do (title, date, start–end, location)
   and ask "Confirm? (yes/no)". Only call the tool after the user clearly says yes.
   If they change something, re-summarise and ask again.
4. Before creating an event, call check_availability for that slot. If it conflicts,
   tell the user and ask whether to proceed anyway or pick another time.
5. When updating or deleting, first use get_events to find the exact event and its id.
   If several match, list them and ask which one.
6. Default event length is 1 hour if the user gives no end time.
7. After a successful create/update/delete, confirm briefly with the final details.
8. Never invent events or ids. If a tool errors, say so plainly.
""".strip()


def build_agent() -> Agent:
    """Instantiate and configure the Calendar AI Agent."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (see .env.example)")

    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
    window = int(os.environ.get("MEMORY_WINDOW", "20"))

    client = AnthropicClient(model=model, api_key=api_key)

    return Agent(
        client=client,
        name="CalendarAgent",
        instructions=INSTRUCTIONS,
        tools=ALL_TOOLS,
        compaction_strategy=SlidingWindowStrategy(keep_last_groups=window),
    )


class SessionStore:
    """In-memory store for AgentSession instances keyed by Discord chat/channel ID."""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent
        self._sessions: Dict[int, AgentSession] = {}

    def get(self, chat_id: int) -> AgentSession:
        """Get existing session or create a new one for the given chat ID."""
        if chat_id not in self._sessions:
            self._sessions[chat_id] = self._agent.create_session(session_id=str(chat_id))
        return self._sessions[chat_id]

    def reset(self, chat_id: int) -> None:
        """Clear conversation memory for a given chat ID."""
        self._sessions.pop(chat_id, None)

    def clear_all(self) -> None:
        """Clear all stored sessions."""
        self._sessions.clear()
