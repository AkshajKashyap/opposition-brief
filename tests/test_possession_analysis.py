"""Offline checks for possession-level outcome and priority rules."""

from __future__ import annotations

from opposition_brief.analysis.possession import (
    MIN_PATHWAY_POSSESSIONS,
    build_possession_analysis,
    pathway_for_events,
)
from opposition_brief.models import NormalizedEvent
from opposition_brief.observations import ReviewPriority, review_priority


def _event(
    index: int,
    possession: int,
    team: str,
    event_type: str,
    *,
    player: str = "Player A",
    start: tuple[float, float] = (40, 50),
    end: tuple[float, float] | None = (60, 50),
    outcome: str = "Completed",
    possession_team: str | None = None,
) -> NormalizedEvent:
    return NormalizedEvent(
        match_id=1,
        match_date="2024-01-01",
        competition="Test",
        season="2024",
        period=1,
        timestamp=f"00:00:{index:02d}.000",
        timestamp_seconds=float(index),
        team=team,
        opponent="B" if team == "A" else "A",
        player=player,
        recipient=None,
        event_type=event_type,
        outcome=outcome,
        possession_id=possession,
        possession_team=possession_team or team,
        start_x=start[0],
        start_y=start[1],
        end_x=end[0] if end else None,
        end_y=end[1] if end else None,
        source_event_id=f"event-{index}",
        event_index=index,
    )


def test_route_outcomes_only_count_later_events_in_the_same_possession() -> None:
    events = [
        _event(0, 1, "A", "Pass", start=(40, 50), end=(60, 50)),
        _event(1, 1, "A", "Carry", start=(60, 50), end=(90, 50)),
        _event(2, 1, "A", "Shot", start=(90, 50), end=None),
    ]
    analysis = build_possession_analysis(events, "A")
    central = next(route for route in analysis.route_outcomes if route.channel == "Central")
    assert central.completed == 2
    assert central.outcomes.sample_size == 1
    assert central.outcomes.final_third_rate == 100
    assert central.outcomes.box_rate == 100
    assert central.outcomes.shot_rate == 100


def test_pathways_collapse_repeated_zones_and_require_repeat_support() -> None:
    events = (
        _event(0, 1, "A", "Pass", start=(20, 20), end=(45, 20)),
        _event(1, 1, "A", "Carry", start=(45, 20), end=(75, 20)),
    )
    assert pathway_for_events(events) == (
        "Defensive third / Left",
        "Middle third / Left",
        "Attacking third / Left",
    )
    repeated = [
        _event(index, possession, "A", "Pass", start=(20, 20), end=(75, 20))
        for possession, index in enumerate(range(MIN_PATHWAY_POSSESSIONS), start=1)
    ]
    analysis = build_possession_analysis(repeated, "A")
    assert len(analysis.pathways) == 0  # one match alone cannot establish recurrence


def test_turnover_links_only_to_the_immediately_following_opponent_possession() -> None:
    events = [
        _event(0, 1, "A", "Miscontrol", start=(50, 50), end=None, outcome="Lost"),
        _event(1, 2, "B", "Pass", start=(40, 50), end=(90, 50)),
        _event(2, 2, "B", "Shot", start=(90, 50), end=None),
        _event(3, 3, "A", "Pass", start=(40, 50), end=(60, 50)),
    ]
    analysis = build_possession_analysis(events, "A")
    turnover = analysis.turnover_consequences[0]
    assert turnover.outcomes.sample_size == 1
    assert turnover.outcomes.box_rate == 100
    assert turnover.outcomes.shot_rate == 100


def test_priority_requires_sample_coverage_difference_and_consequence() -> None:
    assert review_priority(12, 3, 15, 20) is ReviewPriority.HIGH
    assert review_priority(12, 3, 14, 90) is ReviewPriority.MODERATE
    assert review_priority(5, 3, 30, 90) is ReviewPriority.LOW
