"""Unit tests for app/main.py helper functions and client behavior."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.main import (
    _authorized,
    _retry_delay,
    _should_answer,
    _stamp,
    _strip_mention,
)


def test_authorized() -> None:
    user = MagicMock()
    user.id = 12345
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.main.ALLOWED_IDS", {12345})
        assert _authorized(user) is True

        mp.setattr("app.main.ALLOWED_IDS", {99999})
        assert _authorized(user) is False

        mp.setattr("app.main.ALLOWED_IDS", set())
        assert _authorized(user) is True


def test_strip_mention() -> None:
    assert _strip_mention(123, "<@123> Hello bot") == "Hello bot"
    assert _strip_mention(123, "<@!123>   Hello bot  ") == "Hello bot"


def test_stamp() -> None:
    stamped = _stamp("Check calendar")
    assert stamped.startswith("[Now:")
    assert "Check calendar" in stamped


def test_retry_delay() -> None:
    exc = Exception("Please retry in 15.5s due to rate limits")
    assert _retry_delay(exc, 3.0) == 16.5

    exc_generic = Exception("Generic connection reset")
    assert _retry_delay(exc_generic, 3.0) == 3.0
