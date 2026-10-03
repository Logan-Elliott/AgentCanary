"""Small contracts for independently implemented evidence adapters."""

from typing import Protocol, runtime_checkable

from .models import Event


@runtime_checkable
class EventSink(Protocol):
    def record(self, event: Event) -> Event:
        """Persist evidence and return the event with its ingestion sequence."""
        ...


@runtime_checkable
class Monitor(Protocol):
    def start(self) -> None:
        """Begin observations; fail visibly if setup is unavailable."""
        ...

    def stop(self) -> None:
        """Finish observations and release resources."""
        ...
