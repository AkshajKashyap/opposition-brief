"""Deterministic, reviewable candidate observations derived from event aggregates."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from opposition_brief.analysis.metrics import AnalysisResult, channel_for_y, loss_zone
from opposition_brief.analysis.possession import PossessionAnalysis, PossessionKey
from opposition_brief.models import NormalizedEvent

MIN_MODERATE_EVENTS = 6
MIN_STRONG_EVENTS = 12
MIN_PRIORITY_SAMPLE = 6
MIN_PRIORITY_MATCHES = 2
HIGH_PRIORITY_SAMPLE = 12
HIGH_PRIORITY_DIFFERENCE = 15
MODERATE_PRIORITY_DIFFERENCE = 10


class EvidenceStrength(StrEnum):
    """Labels describe coverage and volume, never tactical certainty."""

    LOW = "Low"
    MODERATE = "Moderate"
    STRONG = "Strong"


class ReviewPriority(StrEnum):
    HIGH = "High review priority"
    MODERATE = "Moderate review priority"
    LOW = "Low / insufficient evidence"


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
    priority: ReviewPriority = ReviewPriority.LOW
    comparison_label: str = ""
    comparison_values: tuple[tuple[str, int], ...] = ()
    match_rates: tuple[tuple[int, int], ...] = ()
    supporting_possession_keys: tuple[PossessionKey, ...] = ()

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
    possession_analysis = result.possession_analysis
    if isinstance(possession_analysis, PossessionAnalysis):
        observations = _decision_relevant_observations(result, possession_analysis)
        if observations:
            return sorted(
                observations,
                key=lambda item: (
                    {ReviewPriority.HIGH: 0, ReviewPriority.MODERATE: 1, ReviewPriority.LOW: 2}[
                        item.priority
                    ],
                    -item.sample_size,
                    item.title,
                ),
            )[:5]
    route = _route_observation(result, selected_match_count)
    player = _player_observation(result, selected_match_count)
    turnover = _turnover_observation(result, selected_match_count)
    for observation in (route, player, turnover):
        if observation is not None:
            observations.append(observation)
    return observations


def review_priority(
    sample_size: int, matches: int, difference: int, outcome_rate: int
) -> ReviewPriority:
    """Apply centralized, non-opaque rules for video-review priority."""
    if (
        sample_size >= HIGH_PRIORITY_SAMPLE
        and matches >= 3
        and difference >= HIGH_PRIORITY_DIFFERENCE
        and outcome_rate >= 20
    ):
        return ReviewPriority.HIGH
    if (
        sample_size >= MIN_PRIORITY_SAMPLE
        and matches >= MIN_PRIORITY_MATCHES
        and difference >= MODERATE_PRIORITY_DIFFERENCE
        and outcome_rate >= 10
    ):
        return ReviewPriority.MODERATE
    return ReviewPriority.LOW


def _decision_relevant_observations(
    result: AnalysisResult, analysis: PossessionAnalysis
) -> list[CandidateObservation]:
    possessions = {possession.key: possession for possession in analysis.possessions}
    findings = _route_findings(result, analysis, possessions)
    findings.extend(_player_findings(result, analysis, possessions))
    findings.extend(_pathway_findings(analysis, possessions))
    findings.extend(_turnover_findings(analysis, possessions))
    return findings


def _route_findings(
    result: AnalysisResult,
    analysis: PossessionAnalysis,
    possessions: dict[PossessionKey, object],
) -> list[CandidateObservation]:
    findings = []
    for route in analysis.route_outcomes:
        if route.outcomes.sample_size < MIN_PRIORITY_SAMPLE:
            continue
        other_keys = [
            key
            for other in analysis.route_outcomes
            if other.channel != route.channel
            for key in other.possession_keys
        ]
        other_rate = _box_rate(other_keys, possessions)
        difference = route.outcomes.box_rate - other_rate
        priority = review_priority(
            route.outcomes.sample_size,
            len({key[0] for key in route.possession_keys}),
            difference,
            route.outcomes.box_rate,
        )
        if priority is ReviewPriority.LOW:
            continue
        support = [
            event
            for event in result.progressions
            if channel_for_y(event.start_y) == route.channel
            and _key(event) in route.possession_keys
        ]
        findings.append(
            _priority_observation(
                f"route-effectiveness-{route.channel.lower()}",
                "Progression route effectiveness",
                f"{route.channel} progression had a stronger box-entry association",
                (
                    f"Possessions with a completed {route.channel.lower()} progression were followed by a "
                    f"box entry {route.outcomes.box_rate}% of the time ({route.outcomes.sample_size} possessions), "
                    f"compared with {other_rate}% for possessions using other completed routes."
                ),
                "This route was associated with a higher downstream box-entry rate in the available matches and may warrant video review.",
                support,
                route.possession_keys,
                priority,
                "Box-entry rate after completed progression by route",
                ((route.channel, route.outcomes.box_rate), ("Other routes", other_rate)),
                route.by_match,
            )
        )
    return findings


def _player_findings(
    result: AnalysisResult,
    analysis: PossessionAnalysis,
    possessions: dict[PossessionKey, object],
) -> list[CandidateObservation]:
    findings = []
    for association in analysis.player_associations:
        difference = association.box_difference
        priority = review_priority(
            association.with_outcomes.sample_size,
            len(association.matches_observed),
            difference,
            association.with_outcomes.box_rate,
        )
        if priority is ReviewPriority.LOW:
            continue
        support = [
            event
            for event in result.progressions
            if event.player == association.player and _key(event) in association.possession_keys
        ]
        findings.append(
            _priority_observation(
                f"player-progression-association-{_slug(association.player)}",
                "Progression involvement association",
                f"{association.player}'s progression involvement had a stronger box-entry association",
                (
                    f"Qualifying possessions with {association.player} involved in an early completed progressive action "
                    f"entered the box {association.with_outcomes.box_rate}% of the time "
                    f"({association.with_outcomes.sample_size} possessions), compared with "
                    f"{association.without_outcomes.box_rate}% in other qualifying possessions."
                ),
                "This is an association: player involvement may reflect game state, field position, role, or possession quality. It may warrant video review.",
                support,
                association.possession_keys,
                priority,
                "Box-entry rate in qualifying possessions",
                (
                    (f"With {association.player}", association.with_outcomes.box_rate),
                    ("Other qualifying possessions", association.without_outcomes.box_rate),
                ),
                _match_box_rates(association.possession_keys, possessions),
            )
        )
    return findings


def _pathway_findings(
    analysis: PossessionAnalysis, possessions: dict[PossessionKey, object]
) -> list[CandidateObservation]:
    findings = []
    all_path_keys = {key for pathway in analysis.pathways for key in pathway.possession_keys}
    for pathway in analysis.pathways:
        other_rate = _box_rate(list(all_path_keys - set(pathway.possession_keys)), possessions)
        difference = pathway.outcomes.box_rate - other_rate
        priority = review_priority(
            pathway.outcomes.sample_size,
            len(pathway.matches_observed),
            difference,
            pathway.outcomes.box_rate,
        )
        if priority is ReviewPriority.LOW:
            continue
        readable = " → ".join(_readable_zone(zone) for zone in pathway.pathway)
        support = [possessions[key].start_event for key in pathway.possession_keys]  # type: ignore[attr-defined]
        findings.append(
            _priority_observation(
                f"buildup-path-{_slug('-'.join(pathway.pathway))}",
                "Recurring buildup path",
                f"{readable} was a recurring buildup path associated with box entries",
                (
                    f"This pathway appeared in {pathway.outcomes.sample_size} possessions across "
                    f"{len(pathway.matches_observed)} matches and reached the box {pathway.outcomes.box_rate}% "
                    f"of the time, compared with {other_rate}% for other qualifying pathways."
                ),
                "The path is a compact description of progressive-action zones, not a full tactical sequence. It may warrant video review.",
                support,
                pathway.possession_keys,
                priority,
                "Box-entry rate by pathway group",
                (("This pathway", pathway.outcomes.box_rate), ("Other pathways", other_rate)),
                _match_box_rates(pathway.possession_keys, possessions),
            )
        )
    return findings


def _turnover_findings(
    analysis: PossessionAnalysis, possessions: dict[PossessionKey, object]
) -> list[CandidateObservation]:
    findings = []
    for turnover in analysis.turnover_consequences:
        if turnover.outcomes.sample_size < MIN_PRIORITY_SAMPLE:
            continue
        other_keys = [
            key
            for other in analysis.turnover_consequences
            if other.zone != turnover.zone
            for key in other.linked_possessions
        ]
        other_rate = _box_rate(other_keys, possessions)
        difference = turnover.outcomes.box_rate - other_rate
        priority = review_priority(
            turnover.outcomes.sample_size,
            len(turnover.matches_observed),
            difference,
            turnover.outcomes.box_rate,
        )
        if priority is ReviewPriority.LOW:
            continue
        findings.append(
            _priority_observation(
                f"turnover-consequence-{_slug(turnover.zone)}",
                "Turnover consequence",
                f"Losses in {turnover.zone.lower()} were followed by more opponent box entries",
                (
                    f"Of {turnover.outcomes.sample_size} reliably linked opponent possessions after losses in "
                    f"{turnover.zone.lower()}, {turnover.outcomes.box_rate}% entered the box, compared with "
                    f"{other_rate}% after losses in other zones."
                ),
                "This sequence is an association after a loss, not proof of pressing vulnerability. It may warrant video review.",
                list(turnover.loss_events),
                turnover.linked_possessions,
                priority,
                "Opponent box-entry rate after Argentina losses",
                ((turnover.zone, turnover.outcomes.box_rate), ("Other loss zones", other_rate)),
                _match_box_rates(turnover.linked_possessions, possessions),
            )
        )
    return findings


def _priority_observation(
    observation_id: str,
    category: str,
    title: str,
    claim: str,
    interpretation: str,
    support: list[NormalizedEvent],
    possession_keys: tuple[PossessionKey, ...],
    priority: ReviewPriority,
    comparison_label: str,
    comparison_values: tuple[tuple[str, int], ...],
    match_rates: tuple[tuple[int, object], ...],
) -> CandidateObservation:
    matches = tuple(sorted({key[0] for key in possession_keys}))
    return CandidateObservation(
        observation_id=observation_id,
        category=category,
        title=title,
        computed_claim=claim,
        interpretation=interpretation,
        sample_size=len(possession_keys),
        matches_observed=matches,
        evidence_strength=evidence_strength(len(possession_keys), len(matches), 5),
        supporting_event_ids=tuple(
            event.source_event_id for event in _ordered(support) if event.source_event_id
        ),
        counterexample_event_ids=(),
        limitations=(
            "This is a non-causal association in the available event-data matches.",
            "Downstream outcomes are counted only from events later in the same possession.",
        ),
        priority=priority,
        comparison_label=comparison_label,
        comparison_values=comparison_values,
        match_rates=tuple(
            (match_id, rates.box_rate if hasattr(rates, "box_rate") else int(rates))
            for match_id, rates in match_rates
        ),
        supporting_possession_keys=possession_keys,
    )


def _box_rate(keys: list[PossessionKey], possessions: dict[PossessionKey, object]) -> int:
    selected = [possessions[key] for key in keys if key in possessions]
    hits = sum(
        any(
            (
                event.start_x is not None
                and event.start_x >= 85
                and 22.5 <= (event.start_y or -1) <= 77.5
            )
            or (
                event.end_x is not None
                and event.end_x >= 85
                and 22.5 <= (event.end_y or -1) <= 77.5
            )
            for event in possession.events  # type: ignore[attr-defined]
        )
        for possession in selected
    )
    return round(100 * hits / len(selected)) if selected else 0


def _match_box_rates(
    keys: tuple[PossessionKey, ...], possessions: dict[PossessionKey, object]
) -> tuple[tuple[int, int], ...]:
    by_match: dict[int, list[PossessionKey]] = {}
    for key in keys:
        by_match.setdefault(key[0], []).append(key)
    return tuple(
        (match_id, _box_rate(match_keys, possessions))
        for match_id, match_keys in sorted(by_match.items())
    )


def _key(event: NormalizedEvent) -> PossessionKey:
    assert event.possession_id is not None
    return event.match_id, event.possession_id


def _readable_zone(zone: str) -> str:
    return zone.replace(" third", " third").lower()


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
