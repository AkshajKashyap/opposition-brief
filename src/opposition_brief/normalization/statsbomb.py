"""StatsBomb Open Data adapter.

StatsBomb locations are 120 by 80.  This adapter maps them linearly to 0–100
by 0–100, with x increasing toward the attacking goal used by the source.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from opposition_brief.models import (
    MatchMetadata,
    NormalizationResult,
    NormalizedEvent,
    RawEvent,
    ValidationWarning,
)

PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0


def timestamp_to_seconds(timestamp: str | None) -> float | None:
    """Convert a StatsBomb ``HH:MM:SS.sss`` timestamp to seconds in period."""
    if not timestamp:
        return None
    try:
        hours, minutes, seconds = timestamp.split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (TypeError, ValueError):
        return None


def normalize_location(location: Any) -> tuple[float | None, float | None]:
    """Map a StatsBomb [x, y] location to 0–100 coordinates, or nulls."""
    if not isinstance(location, list | tuple) or len(location) < 2:
        return None, None
    try:
        x, y = float(location[0]), float(location[1])
    except (TypeError, ValueError):
        return None, None
    return round(x / PITCH_LENGTH * 100, 3), round(y / PITCH_WIDTH * 100, 3)


def _name(value: Any) -> str | None:
    return value.get("name") if isinstance(value, dict) else None


def _nested(event: RawEvent, key: str) -> dict[str, Any]:
    value = event.get(key)
    return value if isinstance(value, dict) else {}


def _event_outcome(event_type: str | None, detail: dict[str, Any]) -> str | None:
    if event_type in {"Pass", "Carry"}:
        return _name(detail.get("outcome")) or "Completed"
    if event_type == "Dribble":
        return _name(detail.get("outcome")) or "Completed"
    if event_type in {"Dispossessed", "Miscontrol"}:
        return "Lost"
    return _name(detail.get("outcome"))


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def normalize_events(raw_events: Iterable[RawEvent], match: MatchMetadata) -> NormalizationResult:
    """Normalize every supplied raw event and retain validation warnings.

    Invalid or partial events are represented with nullable fields, rather than
    being silently removed.  Event type, team, timestamp, and locations are
    reported when absent or malformed because they affect interpretation.
    """
    events: list[NormalizedEvent] = []
    warnings: list[ValidationWarning] = []
    for raw in raw_events:
        event_id = raw.get("id") if isinstance(raw.get("id"), str) else None
        event_type = _name(raw.get("type"))
        team = _name(raw.get("team"))
        timestamp = raw.get("timestamp") if isinstance(raw.get("timestamp"), str) else None
        if not event_type:
            warnings.append(
                ValidationWarning(match.match_id, event_id, "type", "Missing event type.")
            )
        if not team:
            warnings.append(
                ValidationWarning(match.match_id, event_id, "team", "Missing event team.")
            )
        if raw.get("timestamp") is not None and timestamp_to_seconds(timestamp) is None:
            warnings.append(
                ValidationWarning(match.match_id, event_id, "timestamp", "Malformed timestamp.")
            )

        detail_key = (event_type or "").lower().replace(" ", "_")
        detail = _nested(raw, detail_key)
        start_x, start_y = normalize_location(raw.get("location"))
        if raw.get("location") is not None and start_x is None:
            warnings.append(
                ValidationWarning(match.match_id, event_id, "location", "Malformed start location.")
            )
        end_x, end_y = normalize_location(detail.get("end_location"))
        if event_type in {"Pass", "Carry"} and detail.get("end_location") is None:
            warnings.append(
                ValidationWarning(
                    match.match_id, event_id, "end_location", "Missing action end location."
                )
            )
        elif detail.get("end_location") is not None and end_x is None:
            warnings.append(
                ValidationWarning(
                    match.match_id, event_id, "end_location", "Malformed end location."
                )
            )
        events.append(
            NormalizedEvent(
                match_id=match.match_id,
                match_date=match.match_date,
                competition=match.competition,
                season=match.season,
                period=_as_int(raw.get("period")),
                timestamp=timestamp,
                timestamp_seconds=timestamp_to_seconds(timestamp),
                team=team,
                opponent=match.opponent_for(team),
                player=_name(raw.get("player")),
                recipient=_name(detail.get("recipient")),
                event_type=event_type,
                outcome=_event_outcome(event_type, detail),
                possession_id=_as_int(raw.get("possession")),
                possession_team=_name(raw.get("possession_team")),
                start_x=start_x,
                start_y=start_y,
                end_x=end_x,
                end_y=end_y,
                source_event_id=event_id,
            )
        )
    return NormalizationResult(events, warnings)
