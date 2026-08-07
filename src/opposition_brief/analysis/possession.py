"""Deterministic possession traces and non-causal downstream outcome summaries."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import pairwise

from opposition_brief.analysis.metrics import (
    channel_for_y,
    is_completed,
    is_possession_loss,
    is_progressive_attempt,
    loss_zone,
    third_for_x,
)
from opposition_brief.models import NormalizedEvent

FINAL_THIRD_X = 200 / 3
BOX_START_X = 85.0
BOX_MIN_Y = 22.5
BOX_MAX_Y = 77.5
MIN_ROUTE_POSSESSIONS = 5
MIN_PLAYER_GROUP = 5
MIN_PATHWAY_POSSESSIONS = 4

PossessionKey = tuple[int, int]


@dataclass(frozen=True)
class Possession:
    key: PossessionKey
    team: str | None
    events: tuple[NormalizedEvent, ...]
    pathway: tuple[str, ...]

    @property
    def match_id(self) -> int:
        return self.key[0]

    @property
    def start_event(self) -> NormalizedEvent:
        return self.events[0]


@dataclass(frozen=True)
class OutcomeRates:
    sample_size: int
    final_third_rate: int
    box_rate: int
    shot_rate: int


@dataclass(frozen=True)
class RouteOutcome:
    channel: str
    attempts: int
    completed: int
    possession_keys: tuple[PossessionKey, ...]
    outcomes: OutcomeRates
    by_match: tuple[tuple[int, OutcomeRates], ...]


@dataclass(frozen=True)
class PlayerAssociation:
    player: str
    with_outcomes: OutcomeRates
    without_outcomes: OutcomeRates
    matches_observed: tuple[int, ...]
    possession_keys: tuple[PossessionKey, ...]

    @property
    def box_difference(self) -> int:
        return self.with_outcomes.box_rate - self.without_outcomes.box_rate


@dataclass(frozen=True)
class PathwayOutcome:
    pathway: tuple[str, ...]
    possession_keys: tuple[PossessionKey, ...]
    outcomes: OutcomeRates
    matches_observed: tuple[int, ...]


@dataclass(frozen=True)
class TurnoverConsequence:
    zone: str
    loss_events: tuple[NormalizedEvent, ...]
    linked_possessions: tuple[PossessionKey, ...]
    outcomes: OutcomeRates
    matches_observed: tuple[int, ...]


@dataclass(frozen=True)
class PossessionAnalysis:
    possessions: tuple[Possession, ...]
    route_outcomes: tuple[RouteOutcome, ...]
    player_associations: tuple[PlayerAssociation, ...]
    pathways: tuple[PathwayOutcome, ...]
    turnover_consequences: tuple[TurnoverConsequence, ...]
    unassigned_events: int


def build_possession_analysis(events: list[NormalizedEvent], team: str) -> PossessionAnalysis:
    """Build transparent possession-level summaries from normalized event order."""
    possessions, unassigned_events = build_possessions(events)
    possession_by_key = {possession.key: possession for possession in possessions}
    team_possessions = [possession for possession in possessions if possession.team == team]
    return PossessionAnalysis(
        possessions=tuple(possessions),
        route_outcomes=route_outcomes(team_possessions),
        player_associations=player_associations(team_possessions),
        pathways=pathway_outcomes(team_possessions),
        turnover_consequences=turnover_consequences(events, possessions, possession_by_key, team),
        unassigned_events=unassigned_events,
    )


def build_possessions(events: list[NormalizedEvent]) -> tuple[list[Possession], int]:
    """Group each match's ordered events by provider possession ID without dropping gaps."""
    grouped: dict[PossessionKey, list[NormalizedEvent]] = defaultdict(list)
    unassigned_events = 0
    for event in sorted(events, key=lambda item: (item.match_id, item.event_index)):
        if event.possession_id is None:
            unassigned_events += 1
            continue
        grouped[(event.match_id, event.possession_id)].append(event)
    possessions = []
    for key, possession_events in grouped.items():
        ordered = tuple(sorted(possession_events, key=lambda item: item.event_index))
        team = next((event.possession_team for event in ordered if event.possession_team), None)
        team = team or next((event.team for event in ordered if event.team), None)
        possessions.append(Possession(key, team, ordered, pathway_for_events(ordered)))
    possessions.sort(
        key=lambda possession: (possession.match_id, possession.start_event.event_index)
    )
    return possessions, unassigned_events


def reaches_final_third(events: tuple[NormalizedEvent, ...]) -> bool:
    """Whether an event later in scope has a start or end location in the final third."""
    return any(
        coordinate is not None and coordinate >= FINAL_THIRD_X
        for event in events
        for coordinate in (event.start_x, event.end_x)
    )


def enters_box(events: tuple[NormalizedEvent, ...]) -> bool:
    """Whether an event later in scope has a start or end location in the opponent box."""
    return any(
        _in_box(x, y)
        for event in events
        for x, y in ((event.start_x, event.start_y), (event.end_x, event.end_y))
    )


def produces_shot(events: tuple[NormalizedEvent, ...]) -> bool:
    return any(event.event_type == "Shot" for event in events)


def downstream_outcomes(possession: Possession, event: NormalizedEvent) -> tuple[bool, bool, bool]:
    """Evaluate only events after the qualifying event in its own possession."""
    later = tuple(item for item in possession.events if item.event_index > event.event_index)
    return reaches_final_third(later), enters_box(later), produces_shot(later)


def route_outcomes(possessions: list[Possession]) -> tuple[RouteOutcome, ...]:
    attempts = [
        event
        for possession in possessions
        for event in possession.events
        if is_progressive_attempt(event) and channel_for_y(event.start_y)
    ]
    completed = [event for event in attempts if is_completed(event)]
    possession_by_key = {possession.key: possession for possession in possessions}
    result = []
    for channel in ("Left", "Central", "Right"):
        channel_attempts = [event for event in attempts if channel_for_y(event.start_y) == channel]
        channel_completed = [
            event for event in completed if channel_for_y(event.start_y) == channel
        ]
        first_by_possession = _first_event_by_possession(channel_completed)
        selected = list(first_by_possession.values())
        result.append(
            RouteOutcome(
                channel=channel,
                attempts=len(channel_attempts),
                completed=len(channel_completed),
                possession_keys=tuple(sorted(first_by_possession)),
                outcomes=_rates(
                    [
                        downstream_outcomes(possession_by_key[_key(event)], event)
                        for event in selected
                    ]
                ),
                by_match=_route_by_match(selected, possession_by_key),
            )
        )
    return tuple(result)


def player_associations(possessions: list[Possession]) -> tuple[PlayerAssociation, ...]:
    """Compare qualified possessions with and without each player's early progression."""
    qualifying: dict[PossessionKey, list[NormalizedEvent]] = {}
    for possession in possessions:
        early_progressions = [
            event
            for event in possession.events
            if is_progressive_attempt(event)
            and is_completed(event)
            and event.start_x is not None
            and event.start_x < FINAL_THIRD_X
        ]
        if early_progressions:
            qualifying[possession.key] = early_progressions
    players = sorted(
        {event.player for events in qualifying.values() for event in events if event.player}
    )
    result = []
    for player in players:
        with_keys = [
            key
            for key, events in qualifying.items()
            if any(event.player == player for event in events)
        ]
        without_keys = [key for key in qualifying if key not in with_keys]
        if len(with_keys) < MIN_PLAYER_GROUP or len(without_keys) < MIN_PLAYER_GROUP:
            continue
        possession_by_key = {possession.key: possession for possession in possessions}
        result.append(
            PlayerAssociation(
                player=player,
                with_outcomes=_rates(
                    [_possession_outcomes(possession_by_key[key]) for key in with_keys]
                ),
                without_outcomes=_rates(
                    [_possession_outcomes(possession_by_key[key]) for key in without_keys]
                ),
                matches_observed=tuple(sorted({key[0] for key in with_keys})),
                possession_keys=tuple(sorted(with_keys)),
            )
        )
    return tuple(sorted(result, key=lambda item: (-item.box_difference, item.player)))


def pathway_for_events(events: tuple[NormalizedEvent, ...]) -> tuple[str, ...]:
    """Create a compact 2–5-zone path from meaningful forward-progressive actions."""
    zones = []
    for event in events:
        if not is_progressive_attempt(event):
            continue
        for x, y in ((event.start_x, event.start_y), (event.end_x, event.end_y)):
            zone = zone_label(x, y)
            if zone:
                zones.append(zone)
    collapsed = tuple(
        zone for index, zone in enumerate(zones) if not index or zone != zones[index - 1]
    )
    return collapsed[:5] if len(collapsed) >= 2 else ()


def zone_label(x: float | None, y: float | None) -> str | None:
    third, channel = third_for_x(x), channel_for_y(y)
    return f"{third} / {channel}" if third and channel else None


def pathway_outcomes(possessions: list[Possession]) -> tuple[PathwayOutcome, ...]:
    grouped: dict[tuple[str, ...], list[Possession]] = defaultdict(list)
    for possession in possessions:
        if possession.pathway:
            grouped[possession.pathway].append(possession)
    results = []
    for pathway, matching in grouped.items():
        matches = {possession.match_id for possession in matching}
        if len(matching) < MIN_PATHWAY_POSSESSIONS or len(matches) < 2:
            continue
        results.append(
            PathwayOutcome(
                pathway=pathway,
                possession_keys=tuple(possession.key for possession in matching),
                outcomes=_rates([_possession_outcomes(possession) for possession in matching]),
                matches_observed=tuple(sorted(matches)),
            )
        )
    return tuple(
        sorted(results, key=lambda item: (-item.outcomes.box_rate, -item.outcomes.sample_size))
    )


def turnover_consequences(
    events: list[NormalizedEvent],
    possessions: list[Possession],
    possession_by_key: dict[PossessionKey, Possession],
    team: str,
) -> tuple[TurnoverConsequence, ...]:
    """Link a team loss to the immediately following opponent possession when unambiguous."""
    by_match: dict[int, list[Possession]] = defaultdict(list)
    for possession in possessions:
        by_match[possession.match_id].append(possession)
    next_possession: dict[PossessionKey, Possession] = {}
    for match_possessions in by_match.values():
        for current, following in pairwise(match_possessions):
            next_possession[current.key] = following
    grouped: dict[str, list[tuple[NormalizedEvent, Possession | None]]] = defaultdict(list)
    for event in events:
        current = possession_by_key.get(_key(event)) if event.possession_id is not None else None
        if current is None or current.team != team or not is_possession_loss(event):
            continue
        zone = loss_zone(event) or "Location unavailable"
        following = next_possession.get(current.key)
        linked = following if following and following.team != team else None
        grouped[zone].append((event, linked))
    result = []
    for zone, pairs in grouped.items():
        linked = [possession for _, possession in pairs if possession is not None]
        result.append(
            TurnoverConsequence(
                zone=zone,
                loss_events=tuple(event for event, _ in pairs),
                linked_possessions=tuple(possession.key for possession in linked),
                outcomes=_rates([_possession_outcomes(possession) for possession in linked]),
                matches_observed=tuple(sorted({event.match_id for event, _ in pairs})),
            )
        )
    return tuple(
        sorted(result, key=lambda item: (-item.outcomes.shot_rate, -len(item.loss_events)))
    )


def _key(event: NormalizedEvent) -> PossessionKey:
    assert event.possession_id is not None
    return event.match_id, event.possession_id


def _first_event_by_possession(
    events: list[NormalizedEvent],
) -> dict[PossessionKey, NormalizedEvent]:
    selected: dict[PossessionKey, NormalizedEvent] = {}
    for event in events:
        key = _key(event)
        if key not in selected or event.event_index < selected[key].event_index:
            selected[key] = event
    return selected


def _rates(outcomes: list[tuple[bool, bool, bool]]) -> OutcomeRates:
    size = len(outcomes)
    return OutcomeRates(
        sample_size=size,
        final_third_rate=_percent(sum(item[0] for item in outcomes), size),
        box_rate=_percent(sum(item[1] for item in outcomes), size),
        shot_rate=_percent(sum(item[2] for item in outcomes), size),
    )


def _route_by_match(
    events: list[NormalizedEvent], possession_by_key: dict[PossessionKey, Possession]
) -> tuple[tuple[int, OutcomeRates], ...]:
    grouped: dict[int, list[tuple[bool, bool, bool]]] = defaultdict(list)
    for event in events:
        grouped[event.match_id].append(downstream_outcomes(possession_by_key[_key(event)], event))
    return tuple((match_id, _rates(outcomes)) for match_id, outcomes in sorted(grouped.items()))


def _possession_outcomes(possession: Possession) -> tuple[bool, bool, bool]:
    return (
        reaches_final_third(possession.events),
        enters_box(possession.events),
        produces_shot(possession.events),
    )


def _in_box(x: float | None, y: float | None) -> bool:
    return x is not None and y is not None and x >= BOX_START_X and BOX_MIN_Y <= y <= BOX_MAX_Y


def _percent(numerator: int, denominator: int) -> int:
    return round(100 * numerator / denominator) if denominator else 0
