"""Explicit, deliberately narrow descriptive analyses for the first brief."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import hypot

from opposition_brief.models import NormalizedEvent

PROGRESSIVE_FORWARD_METERS = 10.0
PROGRESSIVE_GOAL_DISTANCE_REDUCTION = 10.0
MINIMUM_PLAYER_ACTIONS = 3


@dataclass(frozen=True)
class AnalysisResult:
    progression_routes: list[dict[str, object]]
    player_involvement: list[dict[str, object]]
    possession_losses: list[dict[str, object]]
    progressions: list[NormalizedEvent]
    progressive_attempts: list[NormalizedEvent]
    losses: list[NormalizedEvent]
    match_ids: list[int]


def channel_for_y(y: float | None) -> str | None:
    """Assign an action origin to left, central, or right thirds of pitch width."""
    if y is None:
        return None
    if y < 100 / 3:
        return "Left"
    if y < 200 / 3:
        return "Central"
    return "Right"


def third_for_x(x: float | None) -> str | None:
    """Assign a location to defending, middle, or attacking length third."""
    if x is None:
        return None
    if x < 100 / 3:
        return "Defensive third"
    if x < 200 / 3:
        return "Middle third"
    return "Attacking third"


def loss_zone(event: NormalizedEvent) -> str | None:
    """Return a readable 3x3 zone for a loss location."""
    third, channel = third_for_x(event.start_x), channel_for_y(event.start_y)
    return f"{third} / {channel}" if third and channel else None


def is_progressive_attempt(event: NormalizedEvent) -> bool:
    """Classify passes/carries that advance >=10 and reduce goal distance >=10.

    The opposition goal is (100, 50) on the canonical pitch.  Completion is
    checked separately, so incomplete progressive passes remain attempts.
    """
    if event.event_type not in {"Pass", "Carry"}:
        return False
    if None in (event.start_x, event.start_y, event.end_x, event.end_y):
        return False
    forward = event.end_x - event.start_x  # type: ignore[operator]
    start_goal_distance = hypot(100 - event.start_x, 50 - event.start_y)  # type: ignore[operator]
    end_goal_distance = hypot(100 - event.end_x, 50 - event.end_y)  # type: ignore[operator]
    return (
        forward >= PROGRESSIVE_FORWARD_METERS
        and start_goal_distance - end_goal_distance >= PROGRESSIVE_GOAL_DISTANCE_REDUCTION
    )


def is_completed(event: NormalizedEvent) -> bool:
    return event.outcome == "Completed"


def is_possession_loss(event: NormalizedEvent) -> bool:
    """Use event-level loss definitions; this is not a pressing-vulnerability model."""
    return (
        (event.event_type == "Pass" and event.outcome != "Completed")
        or event.event_type in {"Dispossessed", "Miscontrol"}
        or (event.event_type == "Dribble" and event.outcome != "Completed")
    )


def _sorted_rows(rows: list[dict[str, object]], keys: list[str]) -> list[dict[str, object]]:
    return sorted(rows, key=lambda row: tuple(str(row[key]) for key in keys))


def build_analysis(events: list[NormalizedEvent], team: str) -> AnalysisResult:
    """Aggregate the specified opponent's events across the supplied matches."""
    team_events = [event for event in events if event.team == team]
    attempts = [event for event in team_events if is_progressive_attempt(event)]
    progressions = [event for event in attempts if is_completed(event)]
    losses = [event for event in team_events if is_possession_loss(event)]

    route_counts: defaultdict[tuple[object, ...], int] = defaultdict(int)
    for event in progressions:
        route_counts[
            (
                channel_for_y(event.start_y),
                third_for_x(event.start_x),
                third_for_x(event.end_x),
                event.match_id,
            )
        ] += 1
    routes = _sorted_rows(
        [
            {
                "channel": key[0] or "Unknown",
                "origin_third": key[1] or "Unknown",
                "destination_third": key[2] or "Unknown",
                "match_id": key[3],
                "completed_progressions": count,
            }
            for key, count in route_counts.items()
        ],
        ["channel", "origin_third", "destination_third", "match_id"],
    )

    player_rows: dict[str, dict[str, object]] = {}
    match_sets: defaultdict[str, set[int]] = defaultdict(set)
    for event in attempts:
        player = event.player or "Unknown player"
        row = player_rows.setdefault(
            player,
            {"player": player, "attempted": 0, "completed": 0, "forward_distance": 0.0},
        )
        row["attempted"] = int(row["attempted"]) + 1
        if is_completed(event):
            row["completed"] = int(row["completed"]) + 1
            row["forward_distance"] = round(
                float(row["forward_distance"]) + (event.end_x or 0) - (event.start_x or 0), 1
            )
        match_sets[player].add(event.match_id)
    players = []
    for player, row in player_rows.items():
        attempted = int(row["attempted"])
        players.append(
            {
                **row,
                "completion_rate": round(100 * int(row["completed"]) / attempted, 1),
                "matches_observed": len(match_sets[player]),
                "small_sample": attempted < MINIMUM_PLAYER_ACTIONS,
            }
        )
    players.sort(
        key=lambda row: (-int(row["completed"]), -int(row["attempted"]), str(row["player"]))
    )

    loss_counts: defaultdict[tuple[object, ...], int] = defaultdict(int)
    for event in losses:
        loss_counts[(loss_zone(event), event.match_id)] += 1
    loss_rows = _sorted_rows(
        [
            {"zone": key[0] or "Unknown", "match_id": key[1], "losses": count}
            for key, count in loss_counts.items()
        ],
        ["zone", "match_id"],
    )
    return AnalysisResult(
        routes,
        players,
        loss_rows,
        progressions,
        attempts,
        losses,
        sorted({e.match_id for e in team_events}),
    )


def event_evidence(event: NormalizedEvent) -> dict[str, object]:
    """Produce a compact source row suitable for an analyst's video lookup."""
    return {
        "match": event.match_label,
        "period": event.period or "—",
        "timestamp": event.timestamp or "—",
        "player": event.player or "Unknown",
        "action": event.event_type or "Unknown",
        "start": _location(event.start_x, event.start_y),
        "end": _location(event.end_x, event.end_y),
        "outcome": event.outcome or "—",
    }


def _location(x: float | None, y: float | None) -> str:
    return f"({x:.1f}, {y:.1f})" if x is not None and y is not None else "—"
