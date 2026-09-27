"""Unit tests for app/calendar_tools.py."""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.calendar_tools import (
    TZ,
    TZ_NAME,
    _fmt_event,
    _to_rfc3339,
    _tool,
    check_availability,
    create_event,
    delete_event,
    get_current_datetime,
    get_events,
    now_local,
    reset_calendar_service,
    update_event,
)


def test_now_local() -> None:
    n = now_local()
    assert isinstance(n, datetime)
    assert n.tzinfo == TZ


def test_to_rfc3339() -> None:
    iso = _to_rfc3339("2026-09-06T10:00:00")
    assert "2026-09-06T10:00:00" in iso


def test_fmt_event() -> None:
    raw_ev = {
        "id": "ev123",
        "summary": "Team Sync",
        "start": {"dateTime": "2026-09-06T10:00:00+07:00"},
        "end": {"dateTime": "2026-09-06T11:00:00+07:00"},
        "location": "Room A",
        "description": "Weekly sync",
        "attendees": [{"email": "alice@example.com"}],
        "htmlLink": "https://calendar.google.com/event?id=ev123",
    }
    fmt = _fmt_event(raw_ev)
    assert fmt["id"] == "ev123"
    assert fmt["title"] == "Team Sync"
    assert fmt["attendees"] == ["alice@example.com"]


def test_tool_decorator_handles_exception() -> None:
    @_tool
    def failing_fn() -> str:
        raise ValueError("Something broke")

    res_json = failing_fn()
    data = json.loads(res_json)
    assert "error" in data
    assert "ValueError: Something broke" in data["error"]


def test_get_current_datetime() -> None:
    res = get_current_datetime()
    data = json.loads(res)
    assert "now" in data
    assert "weekday" in data
    assert data["timezone"] == TZ_NAME


@patch("app.calendar_tools.get_calendar_service")
def test_get_events(mock_svc_fn: MagicMock) -> None:
    mock_svc = MagicMock()
    mock_svc_fn.return_value = mock_svc
    mock_svc.events().list().execute.return_value = {
        "items": [
            {
                "id": "e1",
                "summary": "Meeting",
                "start": {"dateTime": "2026-09-06T10:00:00+07:00"},
                "end": {"dateTime": "2026-09-06T11:00:00+07:00"},
            }
        ]
    }

    res = get_events("2026-09-06T00:00:00", "2026-09-06T23:59:59")
    data = json.loads(res)
    assert data["count"] == 1
    assert data["events"][0]["title"] == "Meeting"


@patch("app.calendar_tools.get_calendar_service")
def test_check_availability_free(mock_svc_fn: MagicMock) -> None:
    mock_svc = MagicMock()
    mock_svc_fn.return_value = mock_svc
    mock_svc.freebusy().query().execute.return_value = {
        "calendars": {"primary": {"busy": []}}
    }

    res = check_availability("2026-09-06T14:00:00", "2026-09-06T15:00:00")
    data = json.loads(res)
    assert data["status"] == "free"
    assert data["conflicts"] == []


@patch("app.calendar_tools.get_calendar_service")
def test_create_event(mock_svc_fn: MagicMock) -> None:
    mock_svc = MagicMock()
    mock_svc_fn.return_value = mock_svc
    mock_svc.events().insert().execute.return_value = {
        "id": "new123",
        "summary": "Dentist",
        "start": {"dateTime": "2026-09-06T10:00:00+07:00"},
        "end": {"dateTime": "2026-09-06T11:00:00+07:00"},
    }

    res = create_event("Dentist", "2026-09-06T10:00:00")
    data = json.loads(res)
    assert data["status"] == "created"
    assert data["event"]["id"] == "new123"


@patch("app.calendar_tools.get_calendar_service")
def test_delete_event(mock_svc_fn: MagicMock) -> None:
    mock_svc = MagicMock()
    mock_svc_fn.return_value = mock_svc

    res = delete_event("ev123")
    data = json.loads(res)
    assert data["status"] == "deleted"
    assert data["event_id"] == "ev123"
