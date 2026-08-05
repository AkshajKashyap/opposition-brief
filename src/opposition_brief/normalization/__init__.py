"""Provider-specific adapters that produce the canonical event schema."""

from .statsbomb import normalize_events, normalize_location, timestamp_to_seconds

__all__ = ["normalize_events", "normalize_location", "timestamp_to_seconds"]
