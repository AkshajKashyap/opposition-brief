"""Coach-facing view models derived from existing opposition analysis results.

This module deliberately contains presentation calculations only.  It does not
change the observations, evidence selection, or analyst review workflow.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from opposition_brief.analysis.metrics import channel_for_y, loss_zone
from opposition_brief.demo import DemoProject, evidence_events
from opposition_brief.models import MatchMetadata, NormalizedEvent
from opposition_brief.observations import CandidateObservation


@dataclass(frozen=True)
class ChartValue:
    label: str
    value: int


@dataclass(frozen=True)
class EvidenceItem:
    match: str
    date: str
    timestamp: str
    player: str
    action: str
    start: str
    end: str
    outcome: str


@dataclass(frozen=True)
class PatternView:
    """The soccer language and concise context needed by one product view."""

    observation: CandidateObservation
    title: str
    finding: str
    sample_label: str
    matches_label: str
    players: tuple[str, ...]
    why_review: str
    chart_title: str
    chart_values: tuple[ChartValue, ...]
    consistency: tuple[ChartValue, ...]
    evidence: tuple[EvidenceItem, ...]
    other_examples: tuple[EvidenceItem, ...]


def percentage(numerator: int, denominator: int) -> int:
    """Return a compact, deterministic percentage without divide-by-zero surprises."""
    return round(100 * numerator / denominator) if denominator else 0


def human_match_label(match: MatchMetadata) -> str:
    """Return a video-friendly match name without a provider identifier."""
    teams = " vs ".join(team for team in (match.home_team, match.away_team) if team) or "Match"
    return f"{teams} · {match.match_date or 'Date unavailable'}"


def soccer_timestamp(timestamp: str | None) -> str:
    """Convert provider HH:MM:SS timestamps into the familiar MM:SS form."""
    if not timestamp:
        return "—"
    try:
        hours, minutes, seconds = timestamp.split(":")
        total_minutes = int(hours) * 60 + int(minutes)
        return f"{total_minutes}:{int(float(seconds)):02d}"
    except (TypeError, ValueError):
        return timestamp


def prepare_pattern_views(project: DemoProject) -> list[PatternView]:
    """Prepare the two or three landing-page patterns from the existing project."""
    return [prepare_pattern_view(project, observation) for observation in project.observations]


def prepare_pattern_view(project: DemoProject, observation: CandidateObservation) -> PatternView:
    """Add relative context and readable evidence to an existing observation."""
    support = evidence_events(project, observation.supporting_event_ids)
    alternatives = evidence_events(project, observation.counterexample_event_ids)
    match_lookup = {match.match_id: match for match in project.matches}
    if observation.category == "Progression route":
        return _route_view(project, observation, support, alternatives, match_lookup)
    if observation.category == "Player involvement":
        return _player_view(project, observation, support, alternatives, match_lookup)
    return _loss_view(project, observation, support, alternatives, match_lookup)


def _route_view(
    project: DemoProject,
    observation: CandidateObservation,
    support: list[NormalizedEvent],
    alternatives: list[NormalizedEvent],
    matches: dict[int, MatchMetadata],
) -> PatternView:
    channel = observation.observation_id.removeprefix("progression-route-").title()
    counts = Counter(
        channel_for_y(event.start_y) or "Unknown" for event in project.analysis.progressions
    )
    total = len(project.analysis.progressions)
    share = percentage(len(support), total)
    route_phrase = {
        "Central": "through central areas",
        "Left": "down the left",
        "Right": "down the right",
    }.get(channel, f"through the {channel.lower()} channel")
    other_shares = ", ".join(
        f"{label.lower()} {percentage(counts[label], total)}%"
        for label in ("Left", "Central", "Right")
        if label != channel and counts[label]
    )
    return PatternView(
        observation=observation,
        title=f"{channel} progression was {project.opponent}'s most common route",
        finding=(
            f"{share}% of completed progressive actions began {route_phrase} "
            f"({len(support)} of {total}); {other_shares or 'no other channel was recorded'} ."
        ).replace(" .", "."),
        sample_label=f"{len(support)} completed progressive actions",
        matches_label=_coverage_label(support, project.matches),
        players=tuple(_leading_players(support)),
        why_review=(
            f"Repeated {channel.lower()} progressions may affect where the team chooses to set pressure."
        ),
        chart_title="Where completed progressions began",
        chart_values=tuple(
            ChartValue(label, percentage(counts[label], total))
            for label in ("Left", "Central", "Right")
        ),
        consistency=_match_counts(support, project.matches, matches),
        evidence=tuple(_evidence_item(event, matches) for event in support[:8]),
        other_examples=tuple(_evidence_item(event, matches) for event in alternatives[:8]),
    )


def _player_view(
    project: DemoProject,
    observation: CandidateObservation,
    support: list[NormalizedEvent],
    alternatives: list[NormalizedEvent],
    matches: dict[int, MatchMetadata],
) -> PatternView:
    player = (
        observation.observation_id.removeprefix("player-involvement-").replace("-", " ").title()
    )
    leader = next(
        (row for row in project.analysis.player_involvement if row["player"] == player),
        {"attempted": observation.sample_size, "completed": len(support)},
    )
    completed, total = len(support), len(project.analysis.progressions)
    return PatternView(
        observation=observation,
        title=f"{player} was heavily involved in progression",
        finding=(
            f"{player} completed {completed} progressive actions, {percentage(completed, total)}% "
            f"of the team total, from {int(leader['attempted'])} attempts."
        ),
        sample_label=f"{int(leader['attempted'])} progressive attempts",
        matches_label=_coverage_label(support, project.matches),
        players=(player,),
        why_review=(
            f"Review {player}'s possessions to see whether opponents can anticipate their role in build-up."
        ),
        chart_title="Share of completed progressive actions",
        chart_values=(
            ChartValue(player, percentage(completed, total)),
            ChartValue("Other players", percentage(total - completed, total)),
        ),
        consistency=_match_counts(support, project.matches, matches),
        evidence=tuple(_evidence_item(event, matches) for event in support[:8]),
        other_examples=tuple(_evidence_item(event, matches) for event in alternatives[:8]),
    )


def _loss_view(
    project: DemoProject,
    observation: CandidateObservation,
    support: list[NormalizedEvent],
    alternatives: list[NormalizedEvent],
    matches: dict[int, MatchMetadata],
) -> PatternView:
    zone = loss_zone(support[0]) if support else None
    zone = (
        zone
        or observation.observation_id.removeprefix("possession-loss-").replace("-", " ").title()
    )
    total = len(project.analysis.losses)
    return PatternView(
        observation=observation,
        title=f"{project.opponent} most often lost possession in the {zone.lower()}",
        finding=(
            f"{len(support)} of {total} recorded possession losses ({percentage(len(support), total)}%) "
            f"occurred in the {zone.lower()}; {len(alternatives)} happened elsewhere."
        ),
        sample_label=f"{len(support)} recorded possession losses",
        matches_label=_coverage_label(support, project.matches),
        players=tuple(_leading_players(support)),
        why_review=(
            "These moments may reveal repeatable pressure cues, but video is needed to understand why possession was lost."
        ),
        chart_title="Where possession losses occurred",
        chart_values=(
            ChartValue(zone, percentage(len(support), total)),
            ChartValue("Other zones", percentage(len(alternatives), total)),
        ),
        consistency=_match_counts(support, project.matches, matches),
        evidence=tuple(_evidence_item(event, matches) for event in support[:8]),
        other_examples=tuple(_evidence_item(event, matches) for event in alternatives[:8]),
    )


def _coverage_label(events: list[NormalizedEvent], matches: list[MatchMetadata]) -> str:
    observed = {event.match_id for event in events}
    return f"Observed in {len(observed)} of {len(matches)} matches"


def _match_counts(
    events: list[NormalizedEvent],
    project_matches: list[MatchMetadata],
    matches: dict[int, MatchMetadata],
) -> tuple[ChartValue, ...]:
    counts = Counter(event.match_id for event in events)
    return tuple(
        ChartValue(human_match_label(matches.get(match.match_id, match)), counts[match.match_id])
        for match in project_matches
    )


def _leading_players(events: list[NormalizedEvent], limit: int = 2) -> list[str]:
    counts = Counter(event.player for event in events if event.player)
    return [player for player, _ in counts.most_common(limit)]


def _evidence_item(event: NormalizedEvent, matches: dict[int, MatchMetadata]) -> EvidenceItem:
    match = matches.get(event.match_id)
    return EvidenceItem(
        match=human_match_label(match) if match else "Match unavailable",
        date=event.match_date or "Date unavailable",
        timestamp=soccer_timestamp(event.timestamp),
        player=event.player or "Unknown player",
        action=event.event_type or "Action unavailable",
        start=_location(event.start_x, event.start_y),
        end=_location(event.end_x, event.end_y),
        outcome=event.outcome or "—",
    )


def _location(x: float | None, y: float | None) -> str:
    return f"({x:.1f}, {y:.1f})" if x is not None and y is not None else "—"
