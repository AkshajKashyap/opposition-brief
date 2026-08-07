"""Coach-facing view models derived from existing opposition analysis results.

This module only changes how existing observations are explained and compared.
It does not add analytical categories, alter evidence selection, or change the
analyst review workflow.
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
    """A location-free, soccer-readable description of one event."""

    match: str
    date: str
    timestamp: str
    player: str
    description: str


@dataclass(frozen=True)
class PatternView:
    """The soccer language and comparison context needed by one product view."""

    observation: CandidateObservation
    title: str
    finding: str
    sample_label: str
    matches_label: str
    players: tuple[str, ...]
    players_label: str
    why_review: str
    chart_title: str
    chart_axis_label: str
    chart_values: tuple[ChartValue, ...]
    match_shares: tuple[ChartValue, ...]
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
    """Add readable evidence and comparison context to an existing observation."""
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
        channel_for_y(event.start_y) or "Location unavailable"
        for event in project.analysis.progressions
    )
    total = len(project.analysis.progressions)
    share = percentage(len(support), total)
    tied = list(counts.values()).count(counts[channel]) > 1
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
    title = (
        f"{channel} progression was among {project.opponent}'s most common routes"
        if tied
        else f"{channel} progression was {project.opponent}'s most common route"
    )
    return PatternView(
        observation=observation,
        title=title,
        finding=(
            f"{share}% of completed progressive actions began {route_phrase} "
            f"({len(support)} of {total}); {other_shares or 'no other channel was recorded'} ."
        ).replace(" .", "."),
        sample_label=f"{len(support)} completed progressive actions",
        matches_label=_coverage_label(support, project.matches),
        players=tuple(_leading_players(support)),
        players_label="Initiators of the representative actions",
        why_review=(
            f"These {channel.lower()} progressions may affect where the team chooses to set pressure."
        ),
        chart_title="Share of completed progressions by starting channel",
        chart_axis_label="Share of completed progressions (%)",
        chart_values=tuple(
            ChartValue(label, percentage(counts[label], total))
            for label in ("Left", "Central", "Right")
        ),
        match_shares=_match_shares(
            support, project.analysis.progressions, project.matches, matches
        ),
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
    player = str(project.analysis.player_involvement[0]["player"])
    leader = next(row for row in project.analysis.player_involvement if row["player"] == player)
    completed, total = len(support), len(project.analysis.progressions)
    highest_completed = int(project.analysis.player_involvement[0]["completed"])
    tied = (
        sum(
            int(row["completed"]) == highest_completed
            for row in project.analysis.player_involvement
        )
        > 1
    )
    title = (
        f"{player} was among {project.opponent}'s leaders for completed progression"
        if tied
        else f"{player} led {project.opponent} for completed progression"
    )
    return PatternView(
        observation=observation,
        title=title,
        finding=(
            f"{player} completed {completed} progressive actions, {percentage(completed, total)}% "
            f"of the team total, from {int(leader['attempted'])} attempts."
        ),
        sample_label=f"{int(leader['attempted'])} progressive attempts",
        matches_label=_coverage_label(support, project.matches),
        players=(player,),
        players_label="Leader in completed progressive actions",
        why_review=(
            f"Review {player}'s possessions to see whether opponents can anticipate their role in build-up."
        ),
        chart_title="Top players by completed progressive actions",
        chart_axis_label="Completed progressive actions",
        chart_values=tuple(
            ChartValue(str(row["player"]), int(row["completed"]))
            for row in project.analysis.player_involvement[:5]
        ),
        match_shares=_match_shares(
            support, project.analysis.progressions, project.matches, matches
        ),
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
    zone_counts = Counter(
        loss_zone(event) or "Location unavailable" for event in project.analysis.losses
    )
    total = len(project.analysis.losses)
    tied = list(zone_counts.values()).count(zone_counts[zone]) > 1
    title = (
        f"{zone} was among {project.opponent}'s most frequent recorded loss zones"
        if tied
        else f"{zone} was {project.opponent}'s most frequent recorded loss zone"
    )
    return PatternView(
        observation=observation,
        title=title,
        finding=(
            f"{len(support)} of {total} recorded possession losses ({percentage(len(support), total)}%) "
            f"occurred in the {zone.lower()}."
        ),
        sample_label=f"{len(support)} recorded possession losses",
        matches_label=_coverage_label(support, project.matches),
        players=tuple(_leading_players(support)),
        players_label="Players recorded as losing possession in this zone",
        why_review=(
            "These actions may reveal pressure cues, but video is needed to understand why possession was lost."
        ),
        chart_title="Share of all recorded possession losses by zone",
        chart_axis_label="Share of recorded possession losses (%)",
        chart_values=tuple(
            ChartValue(label, percentage(count, total))
            for label, count in sorted(zone_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        match_shares=_match_shares(support, project.analysis.losses, project.matches, matches),
        evidence=tuple(_evidence_item(event, matches) for event in support[:8]),
        other_examples=tuple(_evidence_item(event, matches) for event in alternatives[:8]),
    )


def _coverage_label(events: list[NormalizedEvent], matches: list[MatchMetadata]) -> str:
    observed = {event.match_id for event in events}
    return f"Observed in {len(observed)} of {len(matches)} matches"


def _match_shares(
    support: list[NormalizedEvent],
    comparison_events: list[NormalizedEvent],
    project_matches: list[MatchMetadata],
    matches: dict[int, MatchMetadata],
) -> tuple[ChartValue, ...]:
    support_counts = Counter(event.match_id for event in support)
    totals = Counter(event.match_id for event in comparison_events)
    return tuple(
        ChartValue(
            human_match_label(matches.get(match.match_id, match)),
            percentage(support_counts[match.match_id], totals[match.match_id]),
        )
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
        description=_soccer_description(event),
    )


def _soccer_description(event: NormalizedEvent) -> str:
    recipient = f" to {event.recipient}" if event.recipient else ""
    if event.event_type == "Pass":
        return (
            f"Completed a forward pass{recipient}."
            if event.outcome == "Completed"
            else f"Attempted a pass{recipient}, which was incomplete."
        )
    if event.event_type == "Carry":
        return "Carried the ball forward."
    if event.event_type == "Dispossessed":
        return "Was dispossessed."
    if event.event_type == "Miscontrol":
        return "Miscontrolled the ball."
    if event.event_type == "Dribble":
        return (
            "Completed a dribble."
            if event.outcome == "Completed"
            else "Lost the ball while dribbling."
        )
    return f"Recorded a {event.event_type or 'football'} action."
