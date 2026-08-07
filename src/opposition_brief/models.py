"""Small provider-independent data models used by the first report slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MatchMetadata:
    """The match context required to give a raw event its meaning."""

    match_id: int
    match_date: str | None
    competition: str | None
    season: str | None
    home_team: str | None
    away_team: str | None

    def opponent_for(self, team: str | None) -> str | None:
        if team == self.home_team:
            return self.away_team
        if team == self.away_team:
            return self.home_team
        return None

    @property
    def label(self) -> str:
        teams = " vs ".join(team for team in (self.home_team, self.away_team) if team)
        return f"{self.match_date or 'Unknown date'} — {teams or f'Match {self.match_id}'}"


@dataclass(frozen=True)
class NormalizedEvent:
    """Provider-independent event schema; coordinates use a 0–100 pitch scale."""

    match_id: int
    match_date: str | None
    competition: str | None
    season: str | None
    period: int | None
    timestamp: str | None
    timestamp_seconds: float | None
    team: str | None
    opponent: str | None
    player: str | None
    recipient: str | None
    event_type: str | None
    outcome: str | None
    possession_id: int | None
    possession_team: str | None
    start_x: float | None
    start_y: float | None
    end_x: float | None
    end_y: float | None
    source_event_id: str | None = None
    event_index: int = 0

    @property
    def match_label(self) -> str:
        return f"{self.match_date or 'Unknown date'} · {self.match_id}"


@dataclass(frozen=True)
class ValidationWarning:
    """A non-fatal issue retained alongside the data rather than silently dropped."""

    match_id: int
    event_id: str | None
    field: str
    message: str


@dataclass(frozen=True)
class NormalizationResult:
    events: list[NormalizedEvent]
    warnings: list[ValidationWarning]


RawEvent = dict[str, Any]
