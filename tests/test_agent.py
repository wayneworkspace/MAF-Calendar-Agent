"""Unit tests for app/agent.py."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.agent import SessionStore


def test_session_store_get_and_reset() -> None:
    mock_agent = MagicMock()
    mock_session = MagicMock()
    mock_agent.create_session.return_value = mock_session

    store = SessionStore(mock_agent)

    session1 = store.get(123)
    assert session1 == mock_session
    mock_agent.create_session.assert_called_once_with(session_id="123")

    session2 = store.get(123)
    assert session2 == mock_session
    assert mock_agent.create_session.call_count == 1

    store.reset(123)
    session3 = store.get(123)
    assert mock_agent.create_session.call_count == 2
