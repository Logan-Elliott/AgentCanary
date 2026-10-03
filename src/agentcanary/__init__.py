"""Public, typed contracts for local synthetic-canary evidence."""

from .generator import SeedSpec, create_canary, seed
from .models import Action, Canary, Event
from .protocols import EventSink, Monitor
from .store import Store, StoreError
from .templates import GeneratedCanary, generate

__version__ = "0.1.0"
__all__ = [
    "Action",
    "Canary",
    "Event",
    "EventSink",
    "Monitor",
    "Store",
    "StoreError",
    "SeedSpec",
    "create_canary",
    "seed",
    "GeneratedCanary",
    "generate",
]
