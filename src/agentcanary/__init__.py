"""Public, typed contracts for local synthetic-canary evidence."""

from .models import Action, Canary, Event
from .protocols import EventSink, Monitor
from .store import Store, StoreError

__version__ = "0.1.0"
__all__ = ["Action", "Canary", "Event", "EventSink", "Monitor", "Store", "StoreError"]
