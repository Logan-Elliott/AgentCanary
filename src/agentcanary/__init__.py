"""Public, typed contracts for local synthetic-canary evidence."""

from .generator import SeedSpec, create_canary, seed
from .matching import DecodeError, EncodedMatchResult, MatchResult, PayloadTooLarge, TokenMatcher
from .models import Action, Canary, Event
from .monitors import InotifyMonitor, MonitorError
from .network import BlockingProxy, HTTPInspector, NetworkError
from .protocols import EventSink, Monitor
from .sdk import Observer, ToolInvocationError, ToolResult
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
    "MatchResult",
    "EncodedMatchResult",
    "DecodeError",
    "HTTPInspector",
    "BlockingProxy",
    "NetworkError",
    "PayloadTooLarge",
    "TokenMatcher",
    "Observer",
    "ToolInvocationError",
    "ToolResult",
    "InotifyMonitor",
    "MonitorError",
]
