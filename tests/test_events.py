"""Integration tests for the EventBus."""

from __future__ import annotations

from typing import Any

import pytest

from game_toolbox.core.events import EventBus


class TestEventBusSubscribeEmit:
    """Tests for basic subscribe/emit behaviour."""

    def test_handler_receives_emitted_kwargs(self) -> None:
        """A subscribed handler receives all keyword arguments."""
        bus = EventBus()
        received: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: received.append(kw))

        bus.emit("progress", value=42, label="test")

        assert len(received) == 1
        assert received[0] == {"value": 42, "label": "test"}

    def test_multiple_handlers_all_called(self) -> None:
        """All handlers subscribed to the same event are called."""
        bus = EventBus()
        calls: list[str] = []
        bus.subscribe("done", lambda **_kw: calls.append("a"))
        bus.subscribe("done", lambda **_kw: calls.append("b"))

        bus.emit("done")

        assert calls == ["a", "b"]

    def test_emit_without_subscribers_is_noop(self) -> None:
        """Emitting an event with no subscribers does not raise."""
        bus = EventBus()
        bus.emit("unknown_event", data=123)

    def test_different_events_are_independent(self) -> None:
        """Subscribing to one event does not receive another."""
        bus = EventBus()
        received: list[str] = []
        bus.subscribe("alpha", lambda **_kw: received.append("alpha"))

        bus.emit("beta", x=1)

        assert received == []


class TestEventBusUnsubscribe:
    """Tests for handler removal."""

    def test_unsubscribed_handler_not_called(self) -> None:
        """After unsubscribe, the handler is no longer invoked."""
        bus = EventBus()
        calls: list[int] = []

        def handler(**_kw: Any) -> None:
            calls.append(1)

        bus.subscribe("tick", handler)
        bus.unsubscribe("tick", handler)
        bus.emit("tick")

        assert calls == []

    def test_unsubscribe_unknown_handler_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        """Removing a handler that was never subscribed logs a warning."""
        bus = EventBus()
        bus.unsubscribe("tick", lambda **_kw: None)

        assert "was not subscribed" in caplog.text


class TestEventBusErrorHandling:
    """Tests for handler error isolation."""

    def test_failing_handler_does_not_break_others(self, caplog: pytest.LogCaptureFixture) -> None:
        """A handler that raises does not prevent subsequent handlers."""
        bus = EventBus()
        results: list[str] = []

        def bad_handler(**_kw: Any) -> None:
            msg = "boom"
            raise RuntimeError(msg)

        bus.subscribe("go", bad_handler)
        bus.subscribe("go", lambda **_kw: results.append("ok"))

        bus.emit("go")

        assert results == ["ok"]
        assert "boom" in caplog.text
