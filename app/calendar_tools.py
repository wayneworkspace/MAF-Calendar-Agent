"""Google Calendar integration tools for Calendar Agent.

Provides 5 calendar tools + 1 current datetime helper tool wrapped for
Microsoft Agent Framework / LLM function calling.
"""
from __future__ import annotations

import functools
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Annotated, Any, Callable
from zoneinfo import ZoneInfo

from dateutil import parser as dtparser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from pydantic import Field

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
TZ_NAME = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")
TZ = ZoneInfo(TZ_NAME)

_service: Resource | None = None
log = logging.getLogger("calendar-tools")


def _tool(fn: Callable[..., str]) -> Callable[..., str]:
    """Decorator to catch exceptions in tools, log them, and return a JSON error string to the agent."""
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            log.exception("Tool %s failed: %s", fn.__name__, exc)
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"[:800]})

    return wrapper


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def get_calendar_service() -> Resource:
    """Lazily build an authenticated Google Calendar API client, refreshing token if expired."""
    global _service
    if _service is not None:
        return _service

    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError(f"Token file '{TOKEN_FILE}' not found. Run `python auth.py` first.")

    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    _service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    return _service


def reset_calendar_service() -> None:
    """Reset cached service instance (useful for testing or re-authentication)."""
    global _service
    _service = None


def _to_rfc3339(value: str) -> str:
    """Parse a natural/ISO datetime string and return an RFC3339 formatted string with timezone."""
    dt = dtparser.parse(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.isoformat()


def _fmt_event(ev: dict[str, Any]) -> dict[str, Any]:
    """Format raw Google Calendar API event dictionary into a simplified clean payload."""
    start = ev.get("start", {})
    end = ev.get("end", {})
    return {
        "id": ev.get("id"),
        "title": ev.get("summary", "(no title)"),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "location": ev.get("location"),
        "description": ev.get("description"),
        "attendees": [a.get("email") for a in ev.get("attendees", []) if isinstance(a, dict)],
        "link": ev.get("htmlLink"),
    }


def now_local() -> datetime:
    """Return the current datetime in the configured local timezone."""
    return datetime.now(TZ)


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
def get_current_datetime() -> str:
    """Get the current date, time, weekday, and timezone. Call before resolving relative dates."""
    n = now_local()
    return json.dumps({
        "now": n.isoformat(),
        "weekday": n.strftime("%A"),
        "timezone": TZ_NAME,
    })


def get_events(
    start: Annotated[str, Field(description="Range start, ISO 8601 string e.g. 2026-09-06T00:00:00")],
    end: Annotated[str, Field(description="Range end, ISO 8601 string e.g. 2026-09-06T23:59:59")],
    max_results: Annotated[int, Field(description="Maximum number of events to return", ge=1, le=50)] = 20,
) -> str:
    """List calendar events between start and end date/times."""
    svc = get_calendar_service()
    resp = (
        svc.events()
        .list(
            calendarId=CALENDAR_ID,
            timeMin=_to_rfc3339(start),
            timeMax=_to_rfc3339(end),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = [_fmt_event(e) for e in resp.get("items", [])]
    return json.dumps({"count": len(events), "events": events}, ensure_ascii=False)


def check_availability(
    start: Annotated[str, Field(description="Window start, ISO 8601 string")],
    end: Annotated[str, Field(description="Window end, ISO 8601 string")],
) -> str:
    """Check whether a time window is free. Returns 'free' or lists conflicting events."""
    svc = get_calendar_service()
    resp = (
        svc.freebusy()
        .query(
            body={
                "timeMin": _to_rfc3339(start),
                "timeMax": _to_rfc3339(end),
                "timeZone": TZ_NAME,
                "items": [{"id": CALENDAR_ID}],
            }
        )
        .execute()
    )
    busy = resp.get("calendars", {}).get(CALENDAR_ID, {}).get("busy", [])
    if not busy:
        return json.dumps({"status": "free", "conflicts": []})

    conflicts = json.loads(get_events(start, end)).get("events", [])
    return json.dumps({"status": "busy", "conflicts": conflicts}, ensure_ascii=False)


def create_event(
    title: Annotated[str, Field(description="Event title")],
    start: Annotated[str, Field(description="Start time in ISO 8601 format e.g. 2026-09-06T14:00:00")],
    end: Annotated[str | None, Field(description="End time in ISO 8601 format. Defaults to start + 1 hour")] = None,
    description: Annotated[str | None, Field(description="Optional event description or notes")] = None,
    location: Annotated[str | None, Field(description="Optional event location")] = None,
    attendees: Annotated[list[str] | None, Field(description="Optional attendee email addresses")] = None,
) -> str:
    """Create a new calendar event. ONLY call after user explicitly confirms details."""
    svc = get_calendar_service()
    start_dt = dtparser.parse(start)
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=TZ)
    end_dt = dtparser.parse(end) if end else start_dt + timedelta(hours=1)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=TZ)

    body: dict[str, Any] = {
        "summary": title,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": TZ_NAME},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": TZ_NAME},
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if attendees:
        body["attendees"] = [{"email": a} for a in attendees]

    ev = svc.events().insert(calendarId=CALENDAR_ID, body=body).execute()
    return json.dumps({"status": "created", "event": _fmt_event(ev)}, ensure_ascii=False)


def update_event(
    event_id: Annotated[str, Field(description="ID of event to update (obtained from get_events)")],
    title: Annotated[str | None, Field(description="New title")] = None,
    start: Annotated[str | None, Field(description="New start time in ISO 8601 format")] = None,
    end: Annotated[str | None, Field(description="New end time in ISO 8601 format")] = None,
    description: Annotated[str | None, Field(description="New event description")] = None,
    location: Annotated[str | None, Field(description="New location")] = None,
) -> str:
    """Update fields of an existing event. ONLY call after user explicitly confirms details."""
    svc = get_calendar_service()
    ev = svc.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()

    if title:
        ev["summary"] = title
    if description is not None:
        ev["description"] = description
    if location is not None:
        ev["location"] = location
    if start:
        ev["start"] = {"dateTime": _to_rfc3339(start), "timeZone": TZ_NAME}
    if end:
        ev["end"] = {"dateTime": _to_rfc3339(end), "timeZone": TZ_NAME}
    elif start:
        old_start_str = ev.get("start", {}).get("dateTime")
        old_end_str = ev.get("end", {}).get("dateTime")
        if old_start_str and old_end_str:
            old_start = dtparser.parse(old_start_str)
            old_end = dtparser.parse(old_end_str)
            duration = old_end - old_start
            new_start = dtparser.parse(_to_rfc3339(start))
            ev["end"] = {"dateTime": (new_start + duration).isoformat(), "timeZone": TZ_NAME}

    updated = svc.events().update(calendarId=CALENDAR_ID, eventId=event_id, body=ev).execute()
    return json.dumps({"status": "updated", "event": _fmt_event(updated)}, ensure_ascii=False)


def delete_event(
    event_id: Annotated[str, Field(description="ID of event to delete (obtained from get_events)")],
) -> str:
    """Delete an event permanently. ONLY call after user explicitly confirms."""
    svc = get_calendar_service()
    svc.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
    return json.dumps({"status": "deleted", "event_id": event_id})


ALL_TOOLS = [
    _tool(f)
    for f in (
        get_current_datetime,
        get_events,
        check_availability,
        create_event,
        update_event,
        delete_event,
    )
]
