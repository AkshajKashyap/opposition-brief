"""Deterministic, reviewable candidate observations derived from event aggregates."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from opposition_brief.analysis.metrics import AnalysisResult, channel_for_y, loss_zone
from opposition_brief.models import NormalizedEvent

MIN_MODERATE_EVENTS = 6
MIN_STRONG_EVENTS = 12


class EvidenceStrength(StrEnum):
    """Labels describe coverage and volume, never tactical certainty."""

    LOW = "Low"
    MODERATE = "Moderate"
    STRONG = "Strong"


@dataclass(frozen=True)
class CandidateObservation:
    """Immutable computed proposal that an analyst can review but not rewrite."""

    observation_id: str
    category: str
    title: str
    computed_claim: str
    interpretation: str
    sample_size: int
    matches_observed: tuple[int, ...]
    evidence_strength: EvidenceStrength
    supporting_event_ids: tuple[str, ...]
    counterexample_event_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.observation_id or not self.category or not self.title:
            raise ValueError("Candidate observations require an ID, category, and title.")
        if self.sample_size < 0:
            raise ValueError("Observation sample size cannot be negative.")
        if len(set(self.supporting_event_ids)) != len(self.supporting_event_ids):
            raise ValueError("Supporting event IDs must be unique.")
        if len(set(self.counterexample_event_ids)) != len(self.counterexample_event_ids):
            raise ValueError("Counterexample event IDs must be unique.")

    @property
    def is_small_sample(self) -> bool:
        return self.sample_size < MIN_MODERATE_EVENTS or len(self.matches_observed) < 2


def evidence_strength(
    sample_size: int, matches_observed: int, selected_match_count: int
) -> EvidenceStrength:
    """Return a deterministic coverage-aware label for an observation.

    Strong requires at least 12 supporting events across every selected match;
    Moderate requires at least six events across at least two matches. All
    remaining patterns are Low, including a high percentage from one match.
    """
    if (
        selected_match_count >= 2
        and sample_size >= MIN_STRONG_EVENTS
        and matches_observed == selected_match_count
    ):
        return EvidenceStrength.STRONG
    if sample_size >= MIN_MODERATE_EVENTS and matches_observed >= 2:
        return EvidenceStrength.MODERATE
    return EvidenceStrength.LOW


def build_candidate_observations(
    result: AnalysisResult, selected_match_count: int
) -> list[CandidateObservation]:
    """Propose up to three transparent observations with support and counterexamples."""
    observations: list[CandidateObservation] = []
    route = _route_observation(result, selected_match_count)
    player = _player_observation(result, selected_match_count)
    turnover = _turnover_observation(result, selected_match_count)
    for observation in (route, player, turnover):
        if observation is not None:
            observations.append(observation)
    return observations


def _route_observation(
    result: AnalysisResult, selected_match_count: int
) -> CandidateObservation | None:
    if not result.progressions:
        return None
    channel, _ = Counter(
        channel_for_y(event.start_y) or "Unknown" for event in result.progressions
    ).most_common(1)[0]
    support = _ordered(
        event
        for event in result.progressions
        if (channel_for_y(event.start_y) or "Unknown") == channel
    )
    counterexamples = _ordered(
        event
        for event in result.progressions
        if (channel_for_y(event.start_y) or "Unknown") != channel
    )
    return _observation(
        observation_id=f"progression-route-{channel.lower()}",
        category="Progression route",
        title=f"{channel} progression route",
        computed_claim=(
            f"{len(support)} completed progressive actions began in the {channel.lower()} channel "
            f"across {_match_count(support)} of {selected_match_count} selected matches."
        ),
        interpretation=(
            f"The available matches show repeated {channel.lower()} progression; this may warrant "
            "video review alongside actions from other channels."
        ),
        support=support,
        counterexamples=counterexamples,
        selected_match_count=selected_match_count,
    )


def _player_observation(
    result: AnalysisResult, selected_match_count: int
) -> CandidateObservation | None:
    if not result.player_involvement:
        return None
    leader = result.player_involvement[0]
    player = str(leader["player"])
    support = _ordered(
        event for event in result.progressions if (event.player or "Unknown player") == player
    )
    counterexamples = _ordered(
        event for event in result.progressions if (event.player or "Unknown player") != player
    )
    attempted = int(leader["attempted"])
    completed = int(leader["completed"])
    return _observation(
        observation_id=f"player-involvement-{_slug(player)}",
        category="Player involvement",
        title=f"{player} progression involvement",
        computed_claim=(
            f"{player} completed {completed} of {attempted} progressive attempts "
            f"({leader['completion_rate']}%) across {_match_count(support)} of {selected_match_count} selected matches."
        ),
        interpretation=(
            "The event data suggests this player was repeatedly involved in progression; "
            "review their possessions and compare them with other contributors."
        ),
        support=support,
        counterexamples=counterexamples,
        selected_match_count=selected_match_count,
        sample_size=attempted,
    )


def _turnover_observation(
    result: AnalysisResult, selected_match_count: int
) -> CandidateObservation | None:
    if not result.losses:
        return None
    zone, _ = Counter(loss_zone(event) or "Unknown" for event in result.losses).most_common(1)[0]
    support = _ordered(event for event in result.losses if (loss_zone(event) or "Unknown") == zone)
    counterexamples = _ordered(
        event for event in result.losses if (loss_zone(event) or "Unknown") != zone
    )
    return _observation(
        observation_id=f"possession-loss-{_slug(zone)}",
        category="Possession loss",
        title=f"Possession losses in {zone}",
        computed_claim=(
            f"{len(support)} event-defined possession losses occurred in {zone} across "
            f"{_match_count(support)} of {selected_match_count} selected matches."
        ),
        interpretation=(
            "This pattern may warrant video review for repeatable pressure cues; event data alone "
            "cannot establish why each turnover occurred."
        ),
        support=support,
        counterexamples=counterexamples,
        selected_match_count=selected_match_count,
    )


def _observation(
    observation_id: str,
    category: str,
    title: str,
    computed_claim: str,
    interpretation: str,
    support: list[NormalizedEvent],
    counterexamples: list[NormalizedEvent],
    selected_match_count: int,
    sample_size: int | None = None,
) -> CandidateObservation:
    count = len(support) if sample_size is None else sample_size
    matches = tuple(sorted({event.match_id for event in support}))
    limitations = [
        "Event data describes recorded actions, not tactical intent or the cause of an outcome.",
        "Counterexamples are comparison events, not statistical refutations.",
    ]
    if count < MIN_MODERATE_EVENTS or len(matches) < 2:
        limitations.append(
            "Small sample: treat this as a prompt for review, not a stable tendency."
        )
    return CandidateObservation(
        observation_id=observation_id,
        category=category,
        title=title,
        computed_claim=computed_claim,
        interpretation=interpretation,
        sample_size=count,
        matches_observed=matches,
        evidence_strength=evidence_strength(count, len(matches), selected_match_count),
        supporting_event_ids=tuple(
            event.source_event_id for event in support if event.source_event_id
        ),
        counterexample_event_ids=tuple(
            event.source_event_id for event in counterexamples if event.source_event_id
        ),
        limitations=tuple(limitations),
    )


def _ordered(events: Iterable[NormalizedEvent]) -> list[NormalizedEvent]:
    return sorted(
        events,
        key=lambda event: (
            event.match_date or "",
            event.period or 0,
            event.timestamp_seconds if event.timestamp_seconds is not None else -1,
            event.source_event_id or "",
        ),
    )


def _match_count(events: list[NormalizedEvent]) -> int:
    return len({event.match_id for event in events})


def _slug(value: str) -> str:
    return "-".join("".join(char.lower() if char.isalnum() else " " for char in value).split())
