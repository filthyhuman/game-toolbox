"""EventBus — decoupled Observer for progress, status, and error events."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

# Type alias for event handler callbacks.
EventHandler = Any  # Callable[..., None] — relaxed for mypy compatibility


class EventBus:
    """Simple publish/subscribe event bus for decoupled communication.

    Tools emit events (progress, log, error) through this bus.
    GUI and CLI layers subscribe independently.
    """

    def __init__(self) -> None:
        """Initialise an empty event bus."""
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event: str, handler: EventHandler) -> None:
        """Register a handler for a given event type.

        Args:
            event: The event name to subscribe to (e.g. ``"progress"``).
            handler: A callable that will be invoked when the event fires.
        """
        self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: EventHandler) -> None:
        """Remove a previously registered handler.

        Args:
            event: The event name.
            handler: The handler to remove.
        """
        try:
            self._handlers[event].remove(handler)
        except ValueError:
            logger.warning("Handler %r was not subscribed to event %r", handler, event)

    def emit(self, event: str, **kwargs: Any) -> None:
        """Fire an event, calling all subscribed handlers.

        Args:
            event: The event name to fire.
            **kwargs: Arbitrary data passed to each handler.
        """
        for handler in self._handlers.get(event, []):
            try:
                handler(**kwargs)
            except Exception:
                logger.exception("Error in handler %r for event %r", handler, event)
